"""Webhook OTP (auto re-login).
POST /api/otp {from, body} dengan header X-Webhook-Secret; GET /health."""
import json
import re
import threading
import queue
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAT_SPECIFIC = re.compile(r"(?:kode\s*(?:otp|verifikasi)|otp\s*(?:code|kode))[^\d]*(\d{4,6})", re.I)
PAT_6 = re.compile(r"\b(\d{6})\b")
PAT_4 = re.compile(r"\b(\d{4})\b")


def parse_otp(body):
    for p in (PAT_SPECIFIC, PAT_6, PAT_4):
        m = p.search(body or "")
        if m:
            return m.group(1)
    return ""


def norm_phone(p):
    p = (p or "").strip().replace(" ", "").replace("-", "").lstrip("+")
    if p.startswith("62"):
        p = p[2:]
    elif p.startswith("0"):
        p = p[1:]
    return p


class OtpListener:
    def __init__(self, port, secret=""):
        self.port = port
        self.secret = secret
        self.waiters = {}
        self.mu = threading.Lock()
        self.server = None

    def start(self):
        lst = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                else:
                    self._send(404, {"status": "not_found"})

            def do_POST(self):
                if self.path != "/api/otp":
                    return self._send(404, {"status": "not_found"})
                if lst.secret and self.headers.get("X-Webhook-Secret") != lst.secret:
                    return self._send(401, {"status": "unauthorized"})
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    payload = json.loads(self.rfile.read(n).decode())
                except Exception:
                    return self._send(400, {"status": "bad_request"})
                otp = parse_otp(payload.get("body", ""))
                if not otp:
                    return self._send(200, {"status": "no_otp_found"})
                ok = lst.dispatch(payload.get("from", ""), otp)
                self._send(200, {"status": "dispatched" if ok else "no_waiter", "otp": otp})

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def dispatch(self, frm, otp):
        nf = norm_phone(frm)
        with self.mu:
            ch = self.waiters.get(nf)
            if ch is None and len(self.waiters) == 1:
                ch = next(iter(self.waiters.values()))
            if ch is None:
                for ph, c in self.waiters.items():
                    if ph in nf or nf in ph:
                        ch = c
                        break
            if ch is not None:
                try:
                    ch.put_nowait(otp)
                    return True
                except queue.Full:
                    pass
        return False

    def wait_otp(self, phone, timeout=180):
        q = queue.Queue(maxsize=1)
        np = norm_phone(phone)
        with self.mu:
            self.waiters[np] = q
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None
        finally:
            with self.mu:
                if self.waiters.get(np) is q:
                    del self.waiters[np]


_last_relogin = {}


def auto_relogin(client, listener, notify=None):
    """Refresh dulu; kalau gagal dan ada listener, minta OTP + tunggu webhook.
    Cooldown 2 menit per nomor. Return True bila sesi baru aktif."""
    mdn = client.s.get("mdn", "")
    now = time.time()
    if now - _last_relogin.get(mdn, 0) < 120:
        return False
    _last_relogin[mdn] = now
    r = client.refresh()
    if (r.get("data") or {}).get("result", {}).get("session_id"):
        if notify:
            notify("Sesi diperpanjang otomatis (refresh token).")
        return True
    if listener is None:
        return False
    if notify:
        notify("Sesi expired. Meminta OTP baru untuk auto re-login...")
    rr = client.request_otp(mdn)
    if rr.get("status") != 0:
        return False
    otp = listener.wait_otp(mdn, timeout=180)
    if not otp:
        if notify:
            notify("Auto re-login gagal: OTP tidak diterima dalam 3 menit.")
        return False
    vr = client.verify_otp(otp)
    ok = vr.get("status") == 0
    if notify:
        notify("Auto re-login berhasil. Melanjutkan monitor." if ok else "Auto re-login gagal: OTP ditolak.")
    return ok
