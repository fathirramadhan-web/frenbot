"""MCP server stdio frenbot (login, otp, profil, kuota,
offers, detail, buy, auto-buy). Jalankan: python frenbot.py --mcp"""
import json
import sys
import threading
import time

from mysf import MySFExt, quota_mb
from otpwebhook import auto_relogin

TOOLS = [
    {"name": "login", "description": "Mulai login Smartfren: kirim OTP via SMS ke nomor. Setelah ini STOP dan minta kode OTP ke user, lalu panggil submit_otp.",
     "inputSchema": {"type": "object", "properties": {"mdn": {"type": "string", "description": "Nomor Smartfren, contoh 0881xxxxxxxx"}}, "required": ["mdn"]}},
    {"name": "submit_otp", "description": "Verifikasi kode OTP SMS untuk menyelesaikan login.",
     "inputSchema": {"type": "object", "properties": {"otp": {"type": "string"}}, "required": ["otp"]}},
    {"name": "logout", "description": "Hapus sesi tersimpan.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_profile", "description": "Profil: pulsa, masa aktif, status nomor.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_quota", "description": "Sisa kuota internet, nelpon, SMS + paket aktif.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_recommended_offers", "description": "Daftar paket yang bisa dibeli beserta kode dan harga.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_package_details", "description": "Detail paket by kode (harga, benefit, masa berlaku).",
     "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "buy_package", "description": "Beli paket. payment_method: pulsa atau qris. Konfirmasi harga ke user sebelum memanggil.",
     "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "payment_method": {"type": "string", "enum": ["pulsa", "qris"]}}, "required": ["code", "payment_method"]}},
    {"name": "start_auto_buy", "description": "Monitor background: beli otomatis via pulsa saat kuota <= threshold MB.",
     "inputSchema": {"type": "object", "properties": {"interval_minutes": {"type": "integer"}, "code": {"type": "string"}, "threshold_mb": {"type": "integer"}}, "required": ["interval_minutes", "code", "threshold_mb"]}},
    {"name": "auto_buy_status", "description": "Status monitor auto-buy.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "stop_auto_buy", "description": "Hentikan monitor auto-buy.", "inputSchema": {"type": "object", "properties": {}}},
]


class McpServer:
    def __init__(self, listener=None):
        self.c = MySFExt()
        self.listener = listener
        self.auto_stop = threading.Event()
        self.auto_cfg = {}
        self.auto_thread = None

    def log(self, *a):
        print("[frenbot-mcp]", *a, file=sys.stderr, flush=True)

    def call_tool(self, name, args):
        c = self.c
        if name == "login":
            r = c.request_otp(args["mdn"])
            return "OTP dikirim. Minta kode OTP ke user lalu panggil submit_otp. Respons: " + json.dumps(r, ensure_ascii=False)
        if name == "submit_otp":
            r = c.verify_otp(args["otp"])
            return ("Login berhasil." if r.get("status") == 0 else "Login gagal: ") + json.dumps(r, ensure_ascii=False)[:500]
        if name == "logout":
            self.stop_auto()
            c.s = {}
            c._save()
            return "Logout OK."
        if name == "get_profile":
            from bot import fmt_profile
            return fmt_profile(c)
        if name == "get_quota":
            from bot import fmt_quota
            return fmt_quota(c)
        if name == "get_recommended_offers":
            from bot import fmt_offers
            items = fmt_offers(c.offers())
            return json.dumps(items, ensure_ascii=False, indent=1) if items else "Tidak ada paket tersedia."
        if name == "get_package_details":
            d = c.package_details(args["code"])
            return json.dumps(d, ensure_ascii=False, indent=1) if d else "Paket tidak ditemukan: " + args["code"]
        if name == "buy_package":
            method = "MCC" if args["payment_method"] == "pulsa" else "QRIS"
            r = c.buy_package(args["code"], method)
            return json.dumps(r, ensure_ascii=False)[:2000]
        if name == "start_auto_buy":
            self.start_auto(int(args["interval_minutes"]), args["code"], int(args["threshold_mb"]))
            return f"Auto-buy aktif: tiap {args['interval_minutes']} menit, paket {args['code']}, threshold {args['threshold_mb']} MB, bayar pulsa."
        if name == "auto_buy_status":
            if self.auto_thread and self.auto_thread.is_alive():
                return "Aktif: " + json.dumps(self.auto_cfg)
            return "Tidak aktif."
        if name == "stop_auto_buy":
            self.stop_auto()
            return "Auto-buy dihentikan."
        return "Tool tidak dikenal: " + name

    def start_auto(self, interval, code, thresh):
        self.stop_auto()
        self.auto_cfg = {"interval_minutes": interval, "code": code, "threshold_mb": thresh}
        self.auto_stop = threading.Event()

        def loop():
            while not self.auto_stop.wait(max(1, interval) * 60):
                try:
                    ap = self.c.active_plan()
                    if str((ap.get("result") or {}).get("status")) != "0":
                        if not auto_relogin(self.c, self.listener, notify=self.log):
                            self.log("auto-buy berhenti: sesi expired")
                            break
                        continue
                    mb = quota_mb(ap)
                    if mb is not None and mb > thresh:
                        continue
                    self.log("auto-buy: kuota", mb, "<=", thresh, "-> beli", code)
                    pkg = self.c.find_package(code) or {}
                    r = self.c.buy_package(code, "MCC", name=pkg.get("name"), price=pkg.get("price"))
                    self.log("auto-buy hasil:", json.dumps(r, ensure_ascii=False)[:300])
                except Exception as e:
                    self.log("auto-loop error:", e)

        self.auto_thread = threading.Thread(target=loop, daemon=True)
        self.auto_thread.start()

    def stop_auto(self):
        self.auto_stop.set()

    def serve(self):
        self.log("MCP server siap (stdio)")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except ValueError:
                continue
            method = req.get("method", "")
            rid = req.get("id")
            if method == "initialize":
                resp = {"protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "frenbot-smartfren", "version": "1.0.0"}}
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                resp = {}
            elif method == "tools/list":
                resp = {"tools": TOOLS}
            elif method == "tools/call":
                p = req.get("params", {})
                try:
                    text = self.call_tool(p.get("name"), p.get("arguments") or {})
                    resp = {"content": [{"type": "text", "text": text}]}
                except SystemExit as e:
                    resp = {"content": [{"type": "text", "text": str(e)}], "isError": True}
                except Exception as e:
                    resp = {"content": [{"type": "text", "text": "Error: " + str(e)}], "isError": True}
            else:
                if rid is None:
                    continue
                resp = None
                err = {"code": -32601, "message": "method not found: " + method}
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": err}), flush=True)
                continue
            if rid is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": resp}), flush=True)


def main(listener=None):
    McpServer(listener).serve()


if __name__ == "__main__":
    main()
