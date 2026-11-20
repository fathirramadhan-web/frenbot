"""Bot Telegram frenbot untuk Smartfren.
Admin-only, inline keyboard, login OTP, profil/kuota, beli paket (pulsa/QRIS),
auto-buy monitor, auto re-login via webhook OTP. Teks polos tanpa emoji."""
import io
import json
import os
import threading
import time
import traceback

from tg import Tg, btn
from mysf import MySFExt, quota_mb
from otpwebhook import OtpListener, auto_relogin

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "botstate.json")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except ValueError:
            pass
    return {}


def save_state(st):
    json.dump(st, open(STATE_FILE, "w", encoding="utf-8"), indent=1)


def fmt_profile(c):
    try:
        si = c.sub_info()
        rc = ((si.get("result") or {}).get("data") or {}).get("resultCustinfo") or {}
        if not rc:
            return "Gagal ambil profil: " + json.dumps(si)[:200]
        lines = [
            "Nomor: " + str(rc.get("mobileNo", c.s.get("mdn62", "?"))),
            "Pulsa: Rp " + str(rc.get("remBal", "?")),
            "Status: " + str(rc.get("status", "?")).replace("\n", " "),
            "Masa aktif kartu: " + str(rc.get("expDate", "?")),
            "Profil: " + str(rc.get("offerName", "?")),
        ]
        return "\n".join(lines)
    except SystemExit:
        return "Belum login."
    except Exception as e:
        return "Gagal ambil profil: " + str(e)


def fmt_quota(c):
    try:
        ap = c.active_plan()
        ben = ((ap.get("result") or {}).get("data") or {}).get("benefits") or {}
        if not ben:
            return "Gagal ambil kuota: " + json.dumps(ap)[:200]
        lines = []
        for p in ben.get("resultPackages") or []:
            lines.append("Paket: " + str(p.get("packName")) + " (s/d " + str(p.get("packExpDate")) + ")")
        for b in (ben.get("resultMainBenefit") or []) + (ben.get("resultOtherBenefit") or []):
            amt, desc = b.get("benAmount"), b.get("desc", "")
            try:
                a = float(amt)
                if desc == "Bytes":
                    amt = f"{a/1e9:.2f} GB" if a >= 1e9 else f"{a/1e6:.2f} MB"
                elif desc == "KB":
                    amt = f"{a/1e6:.2f} GB" if a >= 1e6 else f"{a/1e3:.2f} MB"
                elif desc == "Detik":
                    amt = "sepuasnya" if a >= 6048000 else f"{a/60:.0f} menit"
                else:
                    amt = f"{a:,.0f} {desc}"
            except (TypeError, ValueError):
                amt = str(amt)
            exp = b.get("benRemExpDate") or b.get("benExpDate") or ""
            lines.append(str(b.get("benName")) + ": " + amt + (" (" + exp + ")" if exp else ""))
        return "\n".join(lines) if lines else "Tidak ada data kuota."
    except SystemExit:
        return "Belum login."
    except Exception as e:
        return "Gagal ambil kuota: " + str(e)


def fmt_offers(off):
    data = off.get("data")
    items = []
    if isinstance(data, list):
        items = [p for p in data if isinstance(p, dict)]
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                items.extend([p for p in v if isinstance(p, dict)])
    out = []
    for p in items:
        code = p.get("code") or p.get("packID") or p.get("productCode")
        name = p.get("name") or p.get("packName") or p.get("productName") or code
        price = p.get("price") or p.get("packAmount") or 0
        if code:
            out.append({"code": str(code), "name": str(name), "price": price})
    return out


def kb_login():
    return [[btn("Login", "login")]]


def kb_profile():
    return [[btn("Cek Kuota", "check_quota"), btn("Beli Paket", "buy")],
            [btn("Auto-Buy", "auto_buy"), btn("Refresh", "refresh")],
            [btn("Logout", "logout")]]


def kb_back(target="back_profile"):
    return [[btn("Kembali", target)]]


def kb_payment(code):
    return [[btn("Bayar Pulsa", "pay_mcc_" + code)], [btn("Bayar QRIS", "pay_qris_" + code)],
            [btn("Kembali", "buy")]]


def kb_confirm():
    return [[btn("Ya, Beli", "confirm_buy"), btn("Batal", "back_profile")]]


def kb_offers(items, prefix, extra=None):
    kb = []
    for p in items[:10]:
        label = p["name"][:40]
        if p.get("price"):
            label += f" (Rp{int(p['price']):,})".replace(",", ".")
        kb.append([btn(label, prefix + p["code"][:48])])
    if extra:
        kb.extend(extra)
    kb.append([btn("Kembali", "back_profile")])
    return kb


def kb_auto_interval():
    return [[btn("20 menit", "auto_20"), btn("50 menit", "auto_50")],
            [btn("Custom", "auto_custom")], [btn("Kembali", "back_profile")]]


def kb_auto_thresh():
    return [[btn("Habis (0 MB)", "auto_thresh_0"), btn("100 MB", "auto_thresh_100")],
            [btn("200 MB", "auto_thresh_200"), btn("Custom", "auto_thresh_custom")],
            [btn("Kembali", "back_profile")]]


def kb_auto_pay():
    return [[btn("Mulai (bayar pulsa)", "auto_pay_pulsa")], [btn("Kembali", "back_profile")]]


def kb_auto_running():
    return [[btn("Stop Auto-Buy", "auto_stop")], [btn("Kembali", "back_profile")]]


def qr_png(data):
    try:
        import segno
        q = segno.make(data, error="m")
        buf = io.BytesIO()
        q.save(buf, kind="png", scale=10, border=4)
        return buf.getvalue()
    except ImportError:
        return None


def qris_crc_valid(payload):
    """QRIS EMVCo: CRC16 CCITT-FALSE atas payload sampai termasuk '6304'."""
    if not payload or len(payload) < 8:
        return False
    i = payload.rfind("6304")
    if i < 0 or i + 8 > len(payload):
        return False
    crc = 0xFFFF
    for ch in payload[: i + 4].encode("ascii", "replace"):
        crc ^= ch << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return payload[i + 4 : i + 8].upper() == f"{crc:04X}"


class Bot:
    def __init__(self, token, admin_id, listener=None):
        self.tg = Tg(token)
        self.admin = int(admin_id)
        self.listener = listener
        self.state = load_state()
        self.c = MySFExt()
        self.auto_thread = None
        self.auto_stop = threading.Event()
        self.lock = threading.Lock()

    # ---------- helpers ----------
    def logged_in(self):
        return bool(self.c.s.get("session_id"))

    def st(self, key=None, val=None):
        if key is None:
            return self.state
        if val is None:
            return self.state.get(key)
        self.state[key] = val
        save_state(self.state)

    def notify(self, text):
        self.tg.send(self.admin, text)

    def ensure_session(self):
        """Refresh hanya bila sesi benar-benar ditolak (-100). Return True bila bisa lanjut."""
        if not self.logged_in():
            return False
        si = self.c.sub_info()
        res = si.get("result") or {}
        if str(res.get("status")) == "0":
            return True
        if str(res.get("status")) == "-100" or "Tidak Valid" in str(res.get("msg", "")):
            r = self.c.refresh()
            return bool((r.get("data") or {}).get("result", {}).get("session_id"))
        return True

    # ---------- run ----------
    def run(self):
        print("[frenbot] polling mulai, admin:", self.admin, flush=True)
        if self.st("auto_active") and self.logged_in():
            self.start_auto(resume=True)
        # sapa admin saat startup supaya langsung terlihat bot hidup
        try:
            if self.logged_in() and self.ensure_session():
                r = self.tg.send(self.admin, "Frenbot aktif.\n\n" + fmt_profile(self.c) + "\n\nPilih aksi:", kb_profile())
            else:
                r = self.tg.send(self.admin, "Frenbot aktif. Tekan Login untuk mulai.", kb_login())
            print("[frenbot] sapaan startup:", r.get("ok"), flush=True)
        except Exception:
            traceback.print_exc()
        offset = None
        while True:
            try:
                r = self.tg.get_updates(offset=offset, timeout=50)
                if not r.get("ok"):
                    print("[frenbot] getUpdates gagal:", r, flush=True)
                    time.sleep(5)
                    continue
                for u in r.get("result", []):
                    offset = u["update_id"] + 1
                    print("[frenbot] update:", json.dumps(u, ensure_ascii=False)[:300], flush=True)
                    try:
                        self.handle(u)
                    except Exception:
                        traceback.print_exc()
            except KeyboardInterrupt:
                break
            except Exception:
                traceback.print_exc()
                time.sleep(3)

    def handle(self, u):
        if "callback_query" in u:
            cq = u["callback_query"]
            if cq["from"]["id"] != self.admin:
                return
            self.tg.answer_cb(cq["id"])
            self.on_callback(cq["data"], cq["message"]["chat"]["id"], cq["message"]["message_id"])
        elif "message" in u:
            m = u["message"]
            if m.get("from", {}).get("id") != self.admin:
                return
            text = (m.get("text") or "").strip()
            if not text:
                return
            if text.startswith("/start"):
                self.on_start(m["chat"]["id"])
            elif text.startswith("/"):
                return
            else:
                self.on_text(m["chat"]["id"], text)

    # ---------- start / menu ----------
    def on_start(self, chat):
        if self.logged_in() and self.ensure_session():
            self.tg.send(chat, fmt_profile(self.c) + "\n\nPilih aksi:", kb_profile())
        else:
            self.tg.send(chat, "FrenBot - Smartfren via Telegram.\n\n"
                               "Login otomatis, cek profil dan kuota, beli paket, auto-buy.\n\n"
                               "Tekan Login untuk mulai.", kb_login())

    def on_callback(self, data, chat, msg):
        edit = lambda t, kb=None: self.tg.edit(chat, msg, t, kb)
        if data == "login":
            self.st("await", "phone")
            edit("Kirim nomor Smartfren kamu.\nContoh: 0881xxxxxxxx")
        elif data in ("back_profile", "refresh"):
            if not self.logged_in():
                return edit("Belum login.", kb_login())
            edit(fmt_profile(self.c) + "\n\nPilih aksi:", kb_profile())
        elif data == "check_quota":
            if not self.logged_in():
                return edit("Belum login.", kb_login())
            edit("Mengambil data kuota...")
            edit(fmt_quota(self.c) + "\n\nPilih aksi:", kb_profile())
        elif data == "buy":
            if not self.logged_in():
                return edit("Belum login.", kb_login())
            edit("Mengambil daftar paket...")
            items = fmt_offers(self.c.offers())
            self.st("offers", items)
            if not items:
                return edit("Tidak ada paket tersedia untuk nomor ini.", kb_back("buy"))
            edit("Pilih paket:", kb_offers(items, "pkg_", [[btn("Kode Paket Manual", "pkg_custom")]]))
        elif data == "pkg_custom":
            self.st("await", "code")
            edit("Kirim kode paket yang ingin dibeli.\nContoh: K100GB30DCLM_QB")
        elif data.startswith("pkg_"):
            code = data[4:]
            self.show_payment(chat, msg, code)
        elif data.startswith("pay_mcc_") or data.startswith("pay_qris_"):
            if data.startswith("pay_mcc_"):
                method, code = "MCC", data[len("pay_mcc_"):]
            else:
                method, code = "QRIS", data[len("pay_qris_"):]
            self.prepare_buy(chat, msg, code, method)
        elif data == "confirm_buy":
            self.do_buy(chat, msg)
        elif data == "auto_buy":
            self.auto_menu(chat, msg)
        elif data in ("auto_20", "auto_50"):
            self.st("auto_int", int(data[5:]))
            edit(f"Interval: {self.st('auto_int')} menit.\n\nPilih batas minimum kuota:", kb_auto_thresh())
        elif data == "auto_custom":
            self.st("await", "auto_int")
            edit("Kirim interval monitor dalam menit.\nContoh: 30")
        elif data.startswith("auto_thresh_"):
            v = data[12:]
            if v == "custom":
                self.st("await", "auto_thresh")
                return edit("Kirim batas minimum kuota dalam MB.\nContoh: 500")
            self.st("auto_thresh", int(v))
            self.auto_pick_package(chat, msg)
        elif data.startswith("auto_pkg_"):
            code = data[9:]
            if code == "custom":
                self.st("await", "auto_code")
                return edit("Kirim kode paket untuk auto-buy.\nContoh: K100GB30DCLM_QB")
            self.st("auto_code", code)
            edit(f"Interval: {self.st('auto_int')} menit\nBatas: {self.st('auto_thresh')} MB\nPaket: {code}\n\nPembayaran via pulsa.", kb_auto_pay())
        elif data == "auto_pay_pulsa":
            self.start_auto(chat, msg)
        elif data == "auto_stop":
            self.stop_auto()
            edit("Auto-buy dihentikan.", kb_profile())
        elif data == "logout":
            self.stop_auto()
            self.c.s = {}
            self.c._save()
            self.state = {}
            save_state(self.state)
            edit("Sudah logout.", kb_login())

    # ---------- teks masuk ----------
    def on_text(self, chat, text):
        aw = self.st("await")
        if aw == "phone":
            self.st("await", None)
            r = self.c.request_otp(text)
            if r.get("status") == 0:
                self.st("await", "otp")
                self.tg.send(chat, f"OTP dikirim ke {text}.\nBalas kode OTP yang masuk via SMS.")
            else:
                self.tg.send(chat, "Gagal minta OTP: " + json.dumps(r, ensure_ascii=False)[:300], kb_login())
        elif aw == "otp":
            self.st("await", None)
            r = self.c.verify_otp(text)
            if r.get("status") == 0:
                self.tg.send(chat, "Login berhasil.\n\n" + fmt_profile(self.c), kb_profile())
            else:
                self.tg.send(chat, "OTP ditolak: " + json.dumps(r, ensure_ascii=False)[:300], kb_login())
        elif aw == "code":
            self.st("await", None)
            self.show_payment(chat, None, text)
        elif aw == "auto_int":
            if not text.isdigit() or int(text) <= 0:
                return self.tg.send(chat, "Masukkan angka menit yang valid. Contoh: 30")
            self.st("await", None)
            self.st("auto_int", int(text))
            self.tg.send(chat, f"Interval: {text} menit.\n\nPilih batas minimum kuota:", kb_auto_thresh())
        elif aw == "auto_thresh":
            if not text.isdigit():
                return self.tg.send(chat, "Masukkan angka MB yang valid. Contoh: 500")
            self.st("await", None)
            self.st("auto_thresh", int(text))
            self.auto_pick_package(chat, None)
        elif aw == "auto_code":
            self.st("await", None)
            self.st("auto_code", text)
            self.tg.send(chat, f"Interval: {self.st('auto_int')} menit\nBatas: {self.st('auto_thresh')} MB\nPaket: {text}\n\nPembayaran via pulsa.", kb_auto_pay())
        elif text.replace(" ", "").isdigit() and len(text.replace(" ", "")) >= 9:
            self.st("await", "phone")
            self.on_text(chat, text)

    # ---------- beli ----------
    def show_payment(self, chat, msg, code):
        send = (lambda t, kb=None: self.tg.edit(chat, msg, t, kb)) if msg else (lambda t, kb=None: self.tg.send(chat, t, kb))
        send("Paket: " + code + "\n\nPembayaran via:", kb_payment(code))

    def prepare_buy(self, chat, msg, code, method):
        edit = lambda t, kb=None: self.tg.edit(chat, msg, t, kb)
        edit("Mengambil info paket...")
        pkg = self.c.find_package(code)
        if not pkg:
            return edit("Paket tidak ditemukan: " + code, kb_back("buy"))
        price = int(pkg.get("price") or 0)
        name = pkg.get("name") or code
        if method == "QRIS":
            op, hello = self.c._web_hello()
            opts = self.c._web_post(op, "/payment/v2/api/payment-options",
                                    {"type": "buypackage", "product_code": code, "total_payment": price,
                                     "session_id": hello, "partner": "MYWEB"},
                                    {"session-type": "hello", "language": "id"})
            if opts.get("status") != 0:
                return edit("Paket ini tidak mendukung QRIS (kemungkinan khusus pulsa). Pilih paket lain.", kb_back("buy"))
        self.st("pending", {"code": code, "method": method, "name": name, "price": price})
        text = f"Paket: {name}\nKode: {code}\nHarga: Rp{price:,}".replace(",", ".")
        if method == "MCC":
            si = self.c.sub_info()
            rc = ((si.get("result") or {}).get("data") or {}).get("resultCustinfo") or {}
            bal = int(rc.get("remBal") or 0)
            if bal < price:
                return edit(f"Pulsa tidak cukup.\nPulsa: Rp{bal:,}\nHarga: Rp{price:,}".replace(",", "."), kb_back("buy"))
            text += f"\nPulsa: Rp{bal:,}".replace(",", ".")
        text += f"\nBayar: {'pulsa' if method == 'MCC' else 'QRIS'}\n\nLanjutkan membeli paket ini?"
        edit(text, kb_confirm())

    def do_buy(self, chat, msg):
        p = self.st("pending")
        self.st("pending", None)
        if not p:
            return self.tg.edit(chat, msg, "Tidak ada pembelian tertunda.", kb_profile())
        self.tg.edit(chat, msg, "Memproses pembelian...")
        r = self.c.buy_package(p["code"], p["method"], name=p["name"], price=p["price"])
        self.handle_buy_result(chat, r, p)

    def handle_buy_result(self, chat, r, p):
        if r.get("error") or (r.get("status") not in (1, 104, "1", "104")):
            msg = "Gagal beli: " + json.dumps(r, ensure_ascii=False)[:400]
            return self.tg.send(chat, msg, kb_profile())
        data = r.get("data") or {}
        if isinstance(data, str):
            data = {"reference": "MCC", "payments": [{"method": "MCC", "mimeContent": data}]}
        ref = data.get("reference", "")
        pays = data.get("payments") or []
        pay = pays[0] if pays else {}
        method = (pay.get("method") or p["method"]).upper()
        if method == "QRIS" or pay.get("mimeContent", "").startswith("000201"):
            qr = pay.get("mimeContent", "")
            valid = qris_crc_valid(qr)
            print(f"[frenbot] QRIS payload: len={len(qr)} head={qr[:20]} tail={qr[-12:]} crc_valid={valid}", flush=True)
            png = qr_png(qr)
            cap = f"Scan QRIS untuk bayar.\nPaket: {p['name']}\nOrder: {ref}\nBuka gambar ukuran penuh bila sulit di-scan."
            if not valid:
                cap += "\nPeringatan: payload QRIS dari server tidak lolos cek CRC. Bila gagal scan, ulangi order atau pakai metode lain."
            if png:
                r = self.tg.send_document(chat, png, cap, kb_back(), filename="qris.png")
                if not r.get("ok"):
                    self.tg.send_photo(chat, png, cap, kb_back())
            else:
                self.tg.send(chat, cap + "\n\nQRIS (string):\n" + qr, kb_back())
            threading.Thread(target=self.poll_pay, args=(chat, ref), daemon=True).start()
        elif method == "MCC":
            self.tg.send(chat, f"Order dibuat, pembayaran pulsa diproses.\nPaket: {p['name']}\nOrder: {ref}", kb_profile())
            threading.Thread(target=self.poll_pay, args=(chat, ref), daemon=True).start()
        else:
            acct = pay.get("account", "")
            self.tg.send(chat, f"Order dibuat.\nPaket: {p['name']}\nMetode: {method}\nNomor/akun bayar: {acct}\nOrder: {ref}\nSelesaikan pembayaran sebelum {pay.get('expiresAt', '?')}.", kb_profile())
            threading.Thread(target=self.poll_pay, args=(chat, ref), daemon=True).start()

    def poll_pay(self, chat, ref):
        if not ref or ref == "MCC":
            return
        try:
            r = self.c.poll_payment(ref, tries=60, delay=5)
            st = r.get("status")
            if st == "paid":
                self.tg.send(chat, f"Pembayaran berhasil.\nOrder: {ref}", kb_profile())
            elif st == "expired":
                self.tg.send(chat, f"Pembayaran expired/gagal.\nOrder: {ref}", kb_profile())
            else:
                self.tg.send(chat, f"Status pembayaran belum konfirmasi (timeout).\nOrder: {ref}\nCek manual di aplikasi.", kb_profile())
        except Exception as e:
            self.tg.send(chat, "Gagal cek status bayar: " + str(e))

    # ---------- auto-buy ----------
    def auto_menu(self, chat, msg):
        edit = lambda t, kb=None: self.tg.edit(chat, msg, t, kb)
        if self.st("auto_active"):
            return edit(self.auto_status_text(), kb_auto_running())
        edit("Masukkan waktu monitor untuk cek sisa kuota:", kb_auto_interval())

    def auto_status_text(self):
        th = self.st("auto_thresh") or 0
        ths = "habis (0 MB)" if th == 0 else f"< {th} MB"
        return (f"Auto-Buy aktif.\nInterval: {self.st('auto_int')} menit\n"
                f"Batas kuota: {ths}\nPaket: {self.st('auto_code')}\nBayar: pulsa\n\nMonitor berjalan di background.")

    def auto_pick_package(self, chat, msg):
        send = (lambda t, kb=None: self.tg.edit(chat, msg, t, kb)) if msg else (lambda t, kb=None: self.tg.send(chat, t, kb))
        send("Mengambil rekomendasi paket...")
        items = fmt_offers(self.c.offers())
        th = self.st("auto_thresh") or 0
        ths = "habis (0 MB)" if th == 0 else f"< {th} MB"
        send(f"Interval: {self.st('auto_int')} menit\nBatas kuota: {ths}\n\nPilih paket untuk auto-buy:",
             kb_offers(items, "auto_pkg_", [[btn("Kode Paket Manual", "auto_pkg_custom")]]))

    def start_auto(self, chat=None, msg=None, resume=False):
        if not self.st("auto_int") or not self.st("auto_code"):
            if chat and msg:
                self.tg.edit(chat, msg, "Konfigurasi belum lengkap. Mulai ulang.", kb_auto_interval())
            return
        self.stop_auto()
        self.st("auto_active", True)
        self.auto_stop = threading.Event()
        self.auto_thread = threading.Thread(target=self.auto_loop, daemon=True)
        self.auto_thread.start()
        if chat and msg:
            self.tg.edit(chat, msg, self.auto_status_text(), kb_auto_running())
        elif chat:
            self.tg.send(chat, self.auto_status_text(), kb_auto_running())
        print("[frenbot] auto-buy mulai:", self.st("auto_int"), "menit, paket", self.st("auto_code"))

    def stop_auto(self):
        self.auto_stop.set()
        self.st("auto_active", False)

    def auto_loop(self):
        interval = max(1, int(self.st("auto_int") or 20)) * 60
        code = self.st("auto_code")
        while not self.auto_stop.wait(interval):
            try:
                if not self.logged_in():
                    break
                ap = self.c.active_plan()
                res = ap.get("result") or {}
                if str(res.get("status")) != "0":
                    ok = auto_relogin(self.c, self.listener, notify=self.notify)
                    if not ok:
                        self.notify("Auto-buy dihentikan: sesi expired. Login ulang manual.")
                        self.st("auto_active", False)
                        break
                    continue
                mb = quota_mb(ap)
                th = float(self.st("auto_thresh") or 0)
                if mb is not None and mb > th:
                    print(f"[frenbot] auto-buy: kuota {mb:.1f} MB > {th} MB, skip")
                    continue
                self.notify(f"Auto-Buy: kuota {'habis' if mb is None else f'{mb:.1f} MB'} (batas {th:.0f} MB). Membeli {code} via pulsa...")
                pkg = self.c.find_package(code) or {}
                r = self.c.buy_package(code, "MCC", name=pkg.get("name"), price=pkg.get("price"))
                if r.get("status") in (1, 104, "1", "104"):
                    self.notify(f"Auto-Buy berhasil: {code}\n" + json.dumps(r.get("data", {}), ensure_ascii=False)[:300])
                else:
                    self.notify("Auto-Buy gagal: " + json.dumps(r, ensure_ascii=False)[:300])
            except Exception as e:
                print("[frenbot] auto-loop error:", e)
                traceback.print_exc()
        print("[frenbot] auto-buy berhenti")
