# Frenbot

Python-based tool for managing Smartfren accounts via Telegram Bot, Terminal CLI, or MCP Server (for AI agents).

## Features

- SMS OTP login with session caching (session 24 jam, refresh token 30 hari)
- Profile, balance (pulsa), masa aktif, and quota checking
- Browse recommended packages per nomor (semua paket, pagination) + katalog web per kategori (kuota, 5G, roaming)
- Detail paket sebelum beli (benefit, masa berlaku, harga diskon, promo, S&K)
- Rekomendasi cerdas: analisis sisa kuota + estimasi hari tersisa, verdict beli/tidak, dan paket nilai terbaik (harga per GB) dengan cek eligibilitas QRIS/pulsa
- Purchase packages (Pulsa / QRIS)
- Auto-buy monitor (auto-purchase when quota is depleted or below a custom MB threshold)
- Auto re-login via refresh token and OTP webhook (session renewal without manual intervention)
- MCP server for AI agent integration

## Requirements

- Python 3.8+ (stdlib; tidak perlu framework)
- Nomor Smartfren aktif untuk login via OTP SMS
- Akun Telegram + token bot dari @BotFather (khusus mode bot)
- Opsional: segno (pip install segno) untuk gambar QRIS; tanpa it, QRIS dikirim sebagai teks

## Quick Start

```bash
git clone https://github.com/fathirramadhan-web/frenbot.git
cd frenbot
cp .env.example .env   # isi token bila pakai mode bot
pip install segno      # opsional: gambar QRIS
python frenbot.py --cli
```

Login pertama: menu 6 (Login), masukkan nomor Smartfren (contoh 0881xxxxxxxx),
balas kode OTP dari SMS. Sesi tersimpan di mysf_session.json (gitignored) dan
dipakai bersama oleh semua mode, jadi login cukup sekali.

## Modes

- --bot : Telegram bot (requires .env config)
- --cli : Interactive terminal menu
- --mcp : MCP server for AI agents (stdio)

```bash
python frenbot.py --bot   # Telegram bot
python frenbot.py --cli   # Terminal menu
python frenbot.py --mcp   # MCP server
```

## Telegram Bot Setup

1. Buat bot di @BotFather (/newbot), salin token.
2. Dapatkan user ID Telegram kamu (mis. lewat @userinfobot).
3. Isi .env:

```
BOT_TOKEN=token_dari_botfather
ADMIN_ID=user_id_telegram_kamu
```

4. Jalankan python frenbot.py --bot
5. Di Telegram: /start. Bila sesi sudah ada, profil langsung tampil; kalau
   belum, tekan Login, kirim nomor, balas OTP.

Menu bot: Cek Kuota, Beli Paket (pulsa/QRIS dengan konfirmasi), Auto-Buy
(wizard interval, threshold MB, paket), Refresh, Logout. Bot hanya merespons
ADMIN_ID; user lain diabaikan.

Pembelian QRIS: bot mengirim gambar QR sebagai file (tanpa kompresi) supaya
mudah di-scan, lalu mempoll status pembayaran dan mengabari hasilnya.

## Environment Variables

- BOT_TOKEN : required for bot mode. Telegram bot token from BotFather.
- ADMIN_ID : required for bot mode. Your Telegram user ID; bot hanya merespons ID ini.
- OTP_WEBHOOK_PORT : optional. Port for OTP webhook listener (e.g. 8081).
- OTP_WEBHOOK_SECRET : optional. Shared secret for webhook authentication.

Isi di file .env dalam folder frenbot (copy dari .env.example), atau export
langsung sebagai environment variable.

## MCP Server (AI Agent)

Jalankan python frenbot.py --mcp. Contoh konfigurasi mcporter / Claude Desktop
(ganti path sesuai lokasi clone):

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

Tools: login, submit_otp, logout, get_profile, get_quota,
get_recommended_offers, get_recommendations, get_web_catalog,
get_package_details, buy_package, start_auto_buy, auto_buy_status,
stop_auto_buy.

Panduan agent: coba get_profile dulu (sesi biasanya sudah tersimpan); kalau
perlu login, panggil login lalu STOP dan minta OTP ke user, baru submit_otp.
Konfirmasi harga dengan get_package_details sebelum buy_package. Auto-buy
bergantung pada saldo pulsa. Detail: docs/mcp-server.md dan
frenbot-skills/SKILL.md.

## Auto Re-login

Sesi diperpanjang otomatis via refresh token (30 hari). Bila refresh token
habis dan webhook OTP dikonfigurasi (OTP_WEBHOOK_PORT + SMS forwarder yang
meneruskan SMS ke /api/otp), bot meminta OTP baru dan login ulang sendiri.
Setup lengkap: docs/auto-relogin.md.

## Project Structure

- frenbot.py : entry point (--bot / --cli / --mcp)
- bot.py : handler Telegram (inline keyboard, admin-only)
- mysf.py : client API Smartfren (offers, beli paket, payment)
- mysf_client.py : client inti MySF (login OTP, refresh, profil, kuota)
- tg.py : client Telegram Bot API minimal (stdlib, retry, multipart)
- otpwebhook.py : listener webhook OTP + auto re-login
- mcp.py : MCP server stdio
- cli.py : menu terminal
- config.py : pembaca .env
- docs/ : panduan per mode
- frenbot-skills/SKILL.md : skill untuk AI agent

## Security Notes

- .env dan mysf_session.json berisi token/kredensial aktif dan sudah di-gitignore.
  Jangan pernah commit atau membagikan file itu.
- Bot hanya merespons ADMIN_ID yang dikonfigurasi.
- Pembelian memakai uang sungguhan: selalu ada langkah konfirmasi; auto-buy
  hanya aktif setelah wizard selesai dan hanya membayar via pulsa.
- Jangan jalankan auto-buy tanpa saldo pulsa yang cukup.

## Documentation

- Telegram Bot: docs/telegram-bot.md
- CLI Mode: docs/cli.md
- MCP Server: docs/mcp-server.md
- Auto Re-login (OTP Webhook): docs/auto-relogin.md

## Disclaimer

This project is an unofficial tool that interacts with Smartfren MySF
services for personal automation purposes, using standard HTTP interactions
similar to those made by the official app. It is not affiliated with
Smartfren or XLSMART.

Automation is subject to Smartfren/XLSMART Terms of Service. Purchases use
real money. This project is intended for educational and personal use on
your own account only. Use at your own risk.
