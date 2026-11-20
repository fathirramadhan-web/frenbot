"""Client Telegram Bot API minimal (stdlib, long polling)."""
import json
import ssl
import sys
import time
import urllib.request
import urllib.error

CRLF = "\r\n"


class Tg:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"
        self.ctx = ssl.create_default_context()

    def call(self, method, **params):
        data = json.dumps(params).encode()
        last = {"ok": False, "error": "no attempt"}
        for attempt in range(3):
            req = urllib.request.Request(self.base + "/" + method, data=data,
                                         headers={"Content-Type": "application/json",
                                                  "Connection": "close"}, method="POST")
            try:
                r = urllib.request.urlopen(req, timeout=70, context=self.ctx)
                res = json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    res = json.loads(e.read().decode())
                except ValueError:
                    res = {"ok": False, "error": str(e)}
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            if res.get("ok"):
                return res
            last = res
            # jangan retry long-poll yang timeout normal
            if method == "getUpdates" and "timed out" in str(res.get("error", "")).lower():
                return res
            time.sleep(1 + attempt)
        if not last.get("ok") and method != "getUpdates":
            print(f"[tg] {method} gagal: {str(last)[:250]}", file=sys.stderr, flush=True)
        return last

    def get_updates(self, offset=None, timeout=50):
        p = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            p["offset"] = offset
        return self.call("getUpdates", **p)

    def send(self, chat_id, text, kb=None, parse_mode=None):
        p = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if kb is not None:
            p["reply_markup"] = {"inline_keyboard": kb}
        if parse_mode:
            p["parse_mode"] = parse_mode
        return self.call("sendMessage", **p)

    def edit(self, chat_id, msg_id, text, kb=None, parse_mode=None):
        p = {"chat_id": chat_id, "message_id": msg_id, "text": text, "disable_web_page_preview": True}
        if kb is not None:
            p["reply_markup"] = {"inline_keyboard": kb}
        if parse_mode:
            p["parse_mode"] = parse_mode
        r = self.call("editMessageText", **p)
        if not r.get("ok") and "message is not modified" in str(r.get("description", "")):
            return {"ok": True}
        return r

    def _multipart(self, method, chat_id, file_field, file_bytes, filename, caption, kb):
        boundary = "----frenbotboundary9a7c2e"
        parts = []
        fields = {"chat_id": str(chat_id), "caption": caption}
        if kb is not None:
            fields["reply_markup"] = json.dumps({"inline_keyboard": kb})
        for k, v in fields.items():
            parts.append(("--" + boundary + CRLF +
                          'Content-Disposition: form-data; name="' + k + '"' + CRLF + CRLF +
                          v + CRLF).encode())
        parts.append(("--" + boundary + CRLF +
                      'Content-Disposition: form-data; name="' + file_field + '"; filename="' + filename + '"' + CRLF +
                      "Content-Type: image/png" + CRLF + CRLF).encode())
        parts.append(file_bytes)
        parts.append((CRLF + "--" + boundary + "--" + CRLF).encode())
        body = b"".join(parts)
        last = {"ok": False, "error": "no attempt"}
        for attempt in range(3):
            req = urllib.request.Request(self.base + "/" + method, data=body,
                                         headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                                                  "Connection": "close"}, method="POST")
            try:
                r = urllib.request.urlopen(req, timeout=60, context=self.ctx)
                return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    last = json.loads(e.read().decode())
                except ValueError:
                    last = {"ok": False, "error": str(e)}
                return last
            except Exception as e:
                last = {"ok": False, "error": str(e)}
                time.sleep(1 + attempt)
        print(f"[tg] {method} gagal: {str(last)[:250]}", file=sys.stderr, flush=True)
        return last

    def send_photo(self, chat_id, photo_bytes, caption="", kb=None, filename="qr.png"):
        return self._multipart("sendPhoto", chat_id, "photo", photo_bytes, filename, caption, kb)

    def send_document(self, chat_id, file_bytes, caption="", kb=None, filename="file.png"):
        """Kirim file asli tanpa kompresi Telegram (penting untuk QR)."""
        return self._multipart("sendDocument", chat_id, "document", file_bytes, filename, caption, kb)

    def answer_cb(self, cb_id, text=None):
        p = {"callback_query_id": cb_id}
        if text:
            p["text"] = text
        return self.call("answerCallbackQuery", **p)

    def delete(self, chat_id, msg_id):
        return self.call("deleteMessage", chat_id=chat_id, message_id=msg_id)

    def set_my_commands(self, commands):
        return self.call("setMyCommands",
                         commands=[{"command": c, "description": d} for c, d in commands])


def btn(text, data):
    return {"text": text, "callback_data": data}
