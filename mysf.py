"""Extensi client MySF: offers, beli paket (pulsa/QRIS), polling status bayar."""
import json
import ssl
import time
import urllib.request
import urllib.error
import http.cookiejar

from mysf_client import MySFClient, normalize_mdn, _post, INFO_SERVICE

WEB = "https://www.smartfren.com"
PAY = WEB + "/payment/v2/api"
PURCHASE_SERVICE = "https://custinfo.smartfren.com/purchase-service/api"
DEVICE = ["android", "Xiaomi", "2312DRA50G", "14", "mySF", "7.58.0", "", 1080, "id", "", ""]


def quota_mb(active_plan_resp):
    """Total sisa kuota internet (MB) dari benefit utama + lainnya."""
    ben = ((active_plan_resp.get("result") or {}).get("data") or {}).get("benefits") or {}
    total = 0.0
    found = False
    for b in (ben.get("resultMainBenefit") or []) + (ben.get("resultOtherBenefit") or []):
        name = (b.get("benName") or "").lower()
        if not any(k in name for k in ("kuota", "internet", "data")):
            continue
        if "nelpon" in name or "sms" in name or "voice" in name:
            continue
        try:
            a = float(b.get("benAmount"))
        except (TypeError, ValueError):
            continue
        desc = b.get("desc", "")
        mb = a / 1e6 if desc == "Bytes" else (a / 1e3 if desc == "KB" else a)
        total += mb
        found = True
    return total if found else None


class MySFExt(MySFClient):
    # ---------- offers ----------
    @staticmethod
    def _flatten_avail(data):
        """Normalisasi katalog avail-package-rev (category>subCategory>products)."""
        items = []
        cats = data.get("category") if isinstance(data, dict) else data
        if not isinstance(cats, list):
            return items
        for cat in cats:
            if not isinstance(cat, dict):
                continue
            subs = cat.get("subCategory") or []
            prods = cat.get("products") or []
            for sub in subs:
                prods = prods + (sub.get("products") or []) if isinstance(sub, dict) else prods
            for p in prods:
                if not isinstance(p, dict):
                    continue
                code = p.get("PackID") or p.get("packID") or p.get("code") or p.get("productCode")
                if not code:
                    continue
                items.append({"code": str(code),
                              "name": p.get("PackName") or p.get("name") or str(code),
                              "price": p.get("price") or 0,
                              "validity": p.get("ExpireDate") or p.get("validity"),
                              "brand": p.get("brand"), "category": cat.get("name"),
                              "raw": p})
        return items

    def offers(self):
        """Paket yang bisa dibeli untuk nomor ini (get-avail-package-rev),
        fallback ke katalog package-list web."""
        r = self._rpc("get-avail-package-rev", "getAvailPackageRev",
                      "getAvailPackageRev", [self.s["mdn62"]] + DEVICE)
        res = (r.get("result") or {})
        if str(res.get("status")) == "0" and res.get("data"):
            items = self._flatten_avail(res["data"])
            if items:
                return {"source": "avail-package-rev", "data": items}
        # fallback: katalog web (tanpa login)
        out = []
        for cat in ("kuota", "5g", "unlimited", "addon"):
            try:
                pl = self._web_package_list(cat)
                for tab in (pl.get("result") or {}).get("data", []):
                    for p in tab.get("products", []):
                        out.append({"code": p.get("code"), "name": p.get("name"),
                                    "price": p.get("price"), "validity": p.get("validity"),
                                    "benefits": p.get("benefits"), "tab": tab.get("tab")})
            except Exception:
                pass
        return {"source": "web-catalog", "data": out}

    def _web_hello(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                         urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        r = urllib.request.Request(WEB + "/api/hello", data=b"",
                                   headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}, method="POST")
        tok = json.loads(op.open(r, timeout=30).read())["data"]["token"]
        for k, v in (("prod", "1"), ("staging", "0")):
            cj.set_cookie(http.cookiejar.Cookie(0, k, v, None, False, "www.smartfren.com",
                                                True, False, "/", True, True, None, False, None, None, {}))
        return op, tok

    def _web_post(self, op, path, body, headers=None):
        h = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
             "Accept": "application/json", "Origin": WEB, "Referer": WEB + "/"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(WEB + path, data=json.dumps(body).encode(), headers=h, method="POST")
        try:
            return json.loads(op.open(req, timeout=40).read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8", "replace"))
            except ValueError:
                return {"_http_error": e.code}

    def _web_package_list(self, category):
        op, tok = self._web_hello()
        return self._web_post(op, "/api/package-list",
                              {"id": "0", "jsonrpc": "2.0", "method": "getWebListPackage", "category": category},
                              {"language": "id", "Authorization": "Bearer " + tok})

    def find_package(self, code):
        """Cari paket by code di offers; kembalikan dict {code,name,price,...}."""
        off = self.offers()
        for p in off.get("data") or []:
            if isinstance(p, dict) and p.get("code") == code:
                return p
        # fallback katalog web
        for cat in ("kuota", "5g", "unlimited", "addon"):
            try:
                pl = self._web_package_list(cat)
                for tab in (pl.get("result") or {}).get("data", []):
                    for p in tab.get("products", []):
                        if p.get("code") == code:
                            return p
            except Exception:
                pass
        return None

    # ---------- pembelian ----------
    def buy_package(self, code, method="MCC", name=None, price=None):
        """Beli paket untuk nomor sendiri via payment aggregator web.
        method: MCC (pulsa), QRIS, DANA, GOPAY, OVO, SHOPEE, BCAVA, ...
        Return dict respons payment-order (status 1 = order dibuat)."""
        pkg = None
        if price is None or name is None:
            pkg = self.find_package(code)
            if pkg:
                price = price if price is not None else pkg.get("price")
                name = name or pkg.get("name") or code
        if price is None:
            return {"error": "harga paket tidak diketahui; kirim price manual"}
        price = int(price)
        name = name or code
        mdn = self.s.get("mdn") or self.s.get("mdn62")
        op, hello = self._web_hello()
        goods = [{"id": code, "productCode": code, "partnerCode": "", "typeItem": "productCode",
                  "name": name, "price": price, "promoPrice": 0, "extendData": {"mdn": mdn}}]
        # 1. options utk validasi method + service fee
        opts = self._web_post(op, "/payment/v2/api/payment-options",
                              {"type": "buypackage", "product_code": code, "total_payment": price,
                               "session_id": hello, "partner": "MYWEB"},
                              {"session-type": "hello", "language": "id"})
        fee = 0
        chosen = None
        if opts.get("status") == 0:
            for o in opts["data"].get("options", []):
                if o.get("method", "").upper() == method.upper():
                    chosen = o
                    fee = o.get("serviceFee", 0) or 0
                    break
        if opts.get("status") != 0:
            # paket ini tidak punya metode online (mis. paket khusus pulsa)
            if method.upper() == "MCC":
                return self.buy_by_balance(code, price)
            return {"error": "Paket ini tidak mendukung pembayaran online (QRIS/e-wallet/VA), kemungkinan khusus pulsa. Pilih paket lain atau isi pulsa dulu.", "options": opts}
        if chosen is None and method.upper() != "MCC":
            return {"error": f"metode {method} tidak tersedia", "options": opts}
        # 2. order
        body = {
            "type": "buypackage",
            "extend_data": {"mdn": mdn},
            "total_payment": goods,
            "customer_email": "",
            "payment_method": method.upper(),
            "payment_service": fee,
            "account_name": "",
            "account_email": "",
            "payment_mdn": mdn,
            "host_name": "www.smartfren.com",
            "reference_id": "",
            "partner": "MYWEB",
            "order_id": "",
            "transaction_id": "",
        }
        r = self._web_post(op, "/payment/v2/api/payment-order", body,
                           {"session-type": "hello", "X-Is-Mobile": "0", "language": "id"})
        return r

    def buy_by_balance(self, code, price):
        """Paket khusus pulsa: beli langsung via purchase-service (jalur app).
        Memotong pulsa; gagal bila saldo kurang."""
        body = {"id": str(int(time.time() * 1000)), "jsonrpc": "2.0", "method": "buyPackageByBalance",
                "params": [self.s["session_id"], "", "id", "", code, int(price), ""]}
        r = _post(PURCHASE_SERVICE + "/buy-package-by-balance?buyPackageByBalance", body,
                  {"Authorization": "Session " + self.s["session_id"], "Accept-Language": "id"})
        res = r.get("result") or {}
        data = res.get("data")
        msg = res.get("msg") or ""
        # catatan: status "0" bisa berarti gagal (msg berisi alasan); sukses bila data objek / msg sukses
        ok = str(res.get("status")) == "0" and (
            isinstance(data, dict) or "success" in msg.lower() or "berhasil" in msg.lower())
        if ok:
            ref = (data.get("reference") or data.get("transactionId") or "PULSA") if isinstance(data, dict) else "PULSA"
            return {"status": 1, "data": {"reference": ref, "payments": [{"method": "MCC"}]},
                    "_source": "purchase-service", "raw": res}
        return {"error": msg or "gagal beli via pulsa", "raw": r}

    def payment_status(self, reference):
        op, hello = self._web_hello()
        return self._web_post(op, "/payment/v2/api/payment-status", {"reference": reference},
                              {"session-type": "hello", "language": "id"})

    def ppob_status(self, reference):
        op, hello = self._web_hello()
        return self._web_post(op, "/payment/v2/api/ucms-ppob-status", {"reference": reference},
                              {"session-type": "hello", "language": "id"})

    def poll_payment(self, reference, tries=60, delay=5):
        for _ in range(tries):
            r = self.ppob_status(reference)
            ps = r.get("paymentStatus")
            fs = r.get("fulfillmentStatus")
            if ps in (2, "2", "paid", "SUCCESS") or fs in (2, "2", "SUCCESS", "FULFILLED"):
                return {"status": "paid", "raw": r}
            if ps in (3, "3", "expired", "EXPIRED", "FAILED", "CANCELLED"):
                return {"status": "expired", "raw": r}
            time.sleep(delay)
        return {"status": "timeout"}
