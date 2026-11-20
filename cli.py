"""CLI interaktif frenbot."""
import json

from mysf import MySFExt, quota_mb
from bot import fmt_profile, fmt_quota, fmt_offers, fmt_package_detail, fmt_recommendation
from otpwebhook import auto_relogin


def main(listener=None):
    c = MySFExt()
    auto = {"active": False}
    print("FrenBot CLI - Smartfren. Ketik angka menu.")
    while True:
        print("\n=== MENU ===")
        print("1. Profil (pulsa, masa aktif)")
        print("2. Cek kuota")
        print("3. Daftar paket")
        print("4. Beli paket")
        print("5. Auto-buy (setup/status/stop)")
        print("6. Login")
        print("7. Logout")
        print("8. Rekomendasi paket (analisis kuota + nilai terbaik)")
        print("0. Keluar")
        try:
            ch = input("Pilih> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        try:
            if ch == "1":
                print(fmt_profile(c))
            elif ch == "2":
                print(fmt_quota(c))
            elif ch == "3":
                items = fmt_offers(c.offers())
                for i, p in enumerate(items):
                    print(f"{i+1}. {p['code']} | {p['name']} | Rp{p['price']}")
                if not items:
                    print("Tidak ada paket.")
            elif ch == "4":
                code = input("Kode paket> ").strip()
                d = c.package_details(code)
                if not d:
                    print("Paket tidak ditemukan.")
                    continue
                print(fmt_package_detail(d))
                m = input("Bayar (pulsa/qris)> ").strip().lower()
                method = "MCC" if m == "pulsa" else "QRIS"
                ok = input(f"Konfirmasi beli {code} via {m}? (y/n)> ").strip().lower()
                if ok != "y":
                    continue
                r = c.buy_package(code, method, name=d.get("name"), price=d.get("price"))
                print(json.dumps(r, ensure_ascii=False, indent=1)[:1500])
            elif ch == "5":
                if auto["active"]:
                    print("Auto-buy aktif:", auto)
                    if input("Stop? (y/n)> ").strip().lower() == "y":
                        auto["active"] = False
                        print("Dihentikan (thread berhenti di siklus berikutnya).")
                    continue
                iv = int(input("Interval menit> ").strip() or "20")
                th = int(input("Threshold MB (0=habis)> ").strip() or "0")
                code = input("Kode paket> ").strip()
                import threading

                def loop():
                    import time
                    while auto["active"]:
                        time.sleep(iv * 60)
                        if not auto["active"]:
                            break
                        ap = c.active_plan()
                        if str((ap.get("result") or {}).get("status")) != "0":
                            if not auto_relogin(c, listener, notify=print):
                                print("Auto-buy berhenti: sesi expired.")
                                auto["active"] = False
                                break
                            continue
                        mb = quota_mb(ap)
                        if mb is not None and mb > th:
                            print(f"[auto] kuota {mb:.1f} MB > {th} MB, skip")
                            continue
                        print("[auto] kuota menipis, membeli", code)
                        pkg = c.find_package(code) or {}
                        r = c.buy_package(code, "MCC", name=pkg.get("name"), price=pkg.get("price"))
                        print("[auto] hasil:", json.dumps(r, ensure_ascii=False)[:300])

                auto.update(active=True, interval=iv, threshold=th, code=code)
                threading.Thread(target=loop, daemon=True).start()
                print("Auto-buy aktif.")
            elif ch == "6":
                mdn = input("Nomor Smartfren> ").strip()
                r = c.request_otp(mdn)
                print(json.dumps(r, ensure_ascii=False))
                if r.get("status") == 0:
                    otp = input("Kode OTP> ").strip()
                    vr = c.verify_otp(otp)
                    print("Login OK" if vr.get("status") == 0 else json.dumps(vr, ensure_ascii=False))
            elif ch == "7":
                c.s = {}
                c._save()
                print("Logout OK.")
            elif ch == "8":
                print(fmt_recommendation(c.recommend()))
            elif ch == "0":
                break
        except SystemExit as e:
            print(e)
        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    main()
