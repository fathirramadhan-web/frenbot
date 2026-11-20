# MCP Server

## Run

```bash
python frenbot.py --mcp
```

Server berbicara JSON-RPC over stdio (protocol MCP 2024-11-05).

## Agent Configuration

mcporter / Claude Desktop / agent lain yang mendukung MCP stdio:

```json
{
  "mcpServers": {
    "frenbot": {
      "command": "python",
      "args": ["/path/to/frenbot/frenbot.py", "--mcp"]
    }
  }
}
```

Server mengelola sesi sendiri lewat mysf_session.json; tidak perlu
environment variable tambahan untuk mode MCP.

## Available Tools

Authentication:
- login(mdn) — mulai login; memicu OTP SMS ke nomor. Setelah ini STOP dan
  minta kode OTP ke user.
- submit_otp(otp) — selesaikan login dengan kode OTP.
- logout() — hapus sesi tersimpan.

Account & Quota:
- get_profile() — pulsa, masa aktif, status nomor.
- get_quota() — sisa kuota internet/nelpon/SMS + paket aktif.

Packages & Purchasing:
- get_recommended_offers() — daftar paket + kode + harga.
- get_recommendations() — analisis heuristik: sisa kuota, estimasi hari
  tersisa, verdict perlu beli/tidak, top 5 paket harga per GB terbaik
  dengan eligibilitas pembayaran (online/QRIS vs pulsa).
- get_web_catalog(category) — katalog web per kategori: kuota, 5g, roaming
  (paket di luar rekomendasi personal, termasuk postpaid).
- get_package_details(code) — detail paket (harga, benefit, masa berlaku).
- buy_package(code, payment_method) — beli; payment_method: pulsa atau qris.

Automation:
- start_auto_buy(interval_minutes, code, threshold_mb) — monitor background,
  beli otomatis via pulsa saat kuota <= threshold.
- auto_buy_status() — status monitor.
- stop_auto_buy() — hentikan monitor.

## Usage Guidelines

1. Coba get_profile dulu; sesi biasanya sudah tersimpan. Kalau gagal karena
   belum login, panggil login, minta OTP ke user, lalu submit_otp.
2. Untuk pertanyaan umum akun/kuota, pakai get_profile atau get_quota.
3. Sebelum buy_package, konfirmasi harga lewat get_package_details.
   Pembelian memakai uang sungguhan.
4. Untuk start_auto_buy, tanyakan interval, kode paket, dan threshold MB;
   ingatkan bahwa auto-buy bergantung pada saldo pulsa.

## Quick Test

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' | python frenbot.py --mcp
```
