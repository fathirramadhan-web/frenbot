"""
MySF (Smartfren) API client - hasil reverse engineering aplikasi MySF v7.58.0
Stdlib only (Python 3.8+). Cek pulsa, kuota, masa aktif, paket - tanpa aplikasi.

Auth:
- Login: POST /sfpas/registry/v4/signin/mdn/request {mdn} -> OTP via SMS
         POST /sfpas/registry/v4/signin/mdn/verify {mdn, otp} -> session_id (24 jam)
         + refresh_token (30 hari)
- Refresh: POST /sfpas/registry/v4/signin/refresh-token, header
           Authorization: Bearer <refresh_token> (tanpa body)
- Data: header Authorization: Session <session_id> (BUKAN Bearer!)

Sesi disimpan di mysf_session.json sebelah file ini. Jangan bagikan file itu.

CLI:
    python mysf_client.py login 0881xxxxxxx   # minta OTP
    python mysf_client.py otp 123456          # verifikasi (mdn dari sesi/login terakhir)
    python mysf_client.py info                # pulsa + kuota + masa aktif
    python mysf_client.py refresh             # perpanjang sesi manual
    python mysf_client.py raw getSubInfoDetailRev
"""

import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(HERE, "mysf_session.json")

SFPAS_V4 = "https://custinfo.smartfren.com/sfpas/registry/v4"
INFO_SERVICE = "https://transactional-mysf.smartfren.com/info-service/api"
ENGINE = "https://custinfo.smartfren.com/engine"

# parameter device yang dikirim app di setiap JSON-RPC info-service
DEVICE = ["android", "Xiaomi", "2312DRA50G", "14", "mySF", "7.58.0", "", 1080, "id", "", ""]


def _post(url, body=None, headers=None):
    h = {"User-Agent": "mySF/7.58.0 (Android 14)", "Accept": "application/json"}
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body is not None else b""
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context())
        return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", "replace"))
        except ValueError:
            return {"_http_error": e.code}


def normalize_mdn(mdn):
    m = mdn.strip().replace(" ", "").replace("-", "")
    if m.startswith("+"):
        m = m[1:]
    if m.startswith("0"):
        m = "62" + m[1:]
    return m


class MySFClient:
    def __init__(self, session_file=SESSION_FILE):
        self.session_file = session_file
        self.s = {}
        if os.path.exists(session_file):
            self.s = json.load(open(session_file, encoding="utf-8"))

    def _save(self):
        json.dump(self.s, open(self.session_file, "w", encoding="utf-8"), indent=1)

    # ---------- auth ----------
    def request_otp(self, mdn):
        mdn = mdn.strip()
        r = _post(SFPAS_V4 + "/signin/mdn/request", {"mdn": mdn})
        if r.get("status") == 0:
            self.s["mdn"] = mdn
            self._save()
        return r

    def verify_otp(self, otp, mdn=None):
        mdn = mdn or self.s.get("mdn")
        if not mdn:
            raise SystemExit("mdn belum ada; jalankan login <nomor> dulu")
        r = _post(SFPAS_V4 + "/signin/mdn/verify", {"mdn": mdn, "otp": str(otp)})
        res = (r.get("data") or {}).get("result") or {}
        if r.get("status") == 0 and res.get("session_id"):
            self.s.update({
                "mdn": mdn,
                "mdn62": normalize_mdn(mdn),
                "session_id": res["session_id"],
                "refresh_token": res.get("refresh_token", ""),
            })
            self._save()
        return r

    def refresh(self):
        rt = self.s.get("refresh_token")
        if not rt:
            raise SystemExit("tidak ada refresh_token; login ulang")
        r = _post(SFPAS_V4 + "/signin/refresh-token",
                  headers={"Authorization": "Bearer " + rt})
        res = (r.get("data") or {}).get("result") or {}
        if res.get("session_id"):
            self.s["session_id"] = res["session_id"]
            if res.get("refresh_token"):
                self.s["refresh_token"] = res["refresh_token"]
            self._save()
        return r

    # ---------- data ----------
    def _rpc(self, path, qs, method, params, lang=False):
        if not self.s.get("session_id"):
            raise SystemExit("belum login; jalankan login <nomor> lalu otp <kode>")
        body = {"id": 0, "jsonrpc": "2.0", "method": method, "params": params}
        if lang:
            body["lang"] = "id"
        url = f"{INFO_SERVICE}/{path}?{qs}"
        hdr = {"Authorization": "Session " + self.s["session_id"], "Accept-Language": "id"}
        r = _post(url, body, hdr)
        result = r.get("result") or {}
        if str(result.get("status")) in ("-100",) or "Tidak Valid" in str(result.get("msg", "")):
            # sesi habis -> coba refresh sekali
            rr = self.refresh()
            if (rr.get("data") or {}).get("result", {}).get("session_id"):
                hdr["Authorization"] = "Session " + self.s["session_id"]
                r = _post(url, body, hdr)
        # status "1" tanpa data: sesi baru biasanya belum propagasi; retry sebentar
        for _ in range(2):
            result = r.get("result") or {}
            if str(result.get("status")) != "1" or result.get("data"):
                break
            time.sleep(2)
            r = _post(url, body, hdr)
        return r

    def sub_info(self):
        """Pulsa, masa aktif, status nomor, profil pelanggan."""
        return self._rpc("get-sub-info-detail", "getSubInfoDetailRev",
                         "getSubInfoDetailRev", [self.s["mdn62"]] + DEVICE, lang=True)

    def active_plan(self):
        """Paket aktif + sisa kuota per benefit."""
        return self._rpc("get-active-plan-info", "getActivePlanInfo",
                         "getActivePlanInfo", [self.s["mdn62"], self.s["mdn62"]] + DEVICE)

    def status_subscriber(self):
        return self._rpc("get-status-subscriber", "getStatusSubscriber",
                         "getStatusSubscriber", [self.s["mdn62"]] + DEVICE)

    def subscriber_bonus(self):
        return self._rpc("get-subscriber-bonus", "getSubscriberBonus",
                         "getSubscriberBonus", [self.s["mdn62"]] + DEVICE)

    # ---------- tampilan ----------
    def summary(self):
        si = self.sub_info()
        ap = self.active_plan()
        rc = ((si.get("result") or {}).get("data") or {}).get("resultCustinfo") or {}
        lines = []
        lines.append(f"Nomor: {rc.get('mobileNo', self.s.get('mdn62', '?'))}")
        lines.append(f"Pulsa: Rp {rc.get('remBal', '?')}")
        lines.append(f"Status: {str(rc.get('status', '?')).replace(chr(10), ' ')}")
        lines.append(f"Masa aktif kartu: {rc.get('expDate', '?')}")
        lines.append(f"Profil: {rc.get('offerName', '?')}")
        ben = ((ap.get("result") or {}).get("data") or {}).get("benefits") or {}
        packs = ben.get("resultPackages") or []
        if packs:
            lines.append("Paket aktif:")
            for p in packs:
                lines.append(f"- {p.get('packName')} (s/d {p.get('packExpDate')})")
        mains = ben.get("resultMainBenefit") or []
        others = ben.get("resultOtherBenefit") or []
        if mains or others:
            lines.append("Kuota & benefit:")
            for b in mains + others:
                amt = b.get("benAmount")
                desc = b.get("desc", "")
                try:
                    a = float(amt)
                    if desc == "Bytes":
                        amt = f"{a/1e9:.2f} GB" if a >= 1e9 else f"{a/1e6:.2f} MB"
                    elif desc == "KB":
                        amt = f"{a/1e6:.2f} GB" if a >= 1e6 else f"{a/1e3:.2f} MB"
                    elif desc == "Detik":
                        amt = "Sepuasnya" if a >= 6048000 else f"{a/60:.0f} menit"
                    else:
                        amt = f"{a:,.0f} {desc}"
                except (TypeError, ValueError):
                    amt = str(amt)
                exp = b.get("benRemExpDate") or b.get("benExpDate") or ""
                lines.append(f"- {b.get('benName')}: {amt} ({exp})")
        return "\n".join(lines)


def main():
    c = MySFClient()
    args = sys.argv[1:]
    if not args or args[0] == "info":
        print(c.summary())
    elif args[0] == "login":
        print(json.dumps(c.request_otp(args[1]), ensure_ascii=False))
    elif args[0] == "otp":
        r = c.verify_otp(args[1], args[2] if len(args) > 2 else None)
        ok = r.get("status") == 0
        print("LOGIN OK" if ok else json.dumps(r, ensure_ascii=False))
    elif args[0] == "refresh":
        r = c.refresh()
        print("REFRESH OK" if (r.get("data") or {}).get("result", {}).get("session_id")
              else json.dumps(r, ensure_ascii=False))
    elif args[0] == "raw":
        m = args[1]
        fn = {"getSubInfoDetailRev": c.sub_info, "getActivePlanInfo": c.active_plan,
              "getStatusSubscriber": c.status_subscriber, "getSubscriberBonus": c.subscriber_bonus}
        print(json.dumps(fn[m](), ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
