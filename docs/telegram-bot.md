# Telegram Bot

## Setup

1. Create a bot via @BotFather and get the token.
2. Get your Telegram user ID (use @userinfobot).
3. Fill .env in the frenbot folder:

```
BOT_TOKEN=your_token_here
ADMIN_ID=your_user_id

# Optional: enable auto re-login via OTP webhook
OTP_WEBHOOK_PORT=8081
OTP_WEBHOOK_SECRET=your_secret
```

## Run

```bash
python frenbot.py --bot
```

## Usage

1. Start — send /start to the bot.
2. Login — tap Login, send your Smartfren number (e.g. 0881xxxxxxxx), then
   reply with the OTP received via SMS. Jika sesi sudah tersimpan dari
   CLI/MCP, bot langsung menampilkan profil tanpa login ulang.
3. Profil — pulsa, masa aktif kartu, status nomor, profil paket.
4. Cek Kuota — sisa kuota internet, nelpon, SMS, dan paket aktif.
5. Beli Paket — pilih paket dari daftar (atau kirim kode manual). Bot
   menampilkan detail paket dulu (harga + diskon, masa berlaku, benefit,
   promo, deskripsi, link S&K). Tekan Beli Paket, pilih bayar Pulsa atau
   QRIS, konfirmasi. QRIS dikirim sebagai gambar QR; status pembayaran
   dipoll otomatis dan hasilnya diberitahukan.
6. Auto-Buy — pilih interval, threshold MB, paket, lalu mulai. Bot memonitor
   kuota di background dan membeli otomatis via pulsa saat kuota habis atau
   di bawah threshold.

## Bot Commands

- /start : show main menu (or profile if session active)

All other interactions are through inline keyboard buttons. Bot hanya
merespons ADMIN_ID; pesan dari user lain diabaikan.

## Auto Re-login

If an OTP webhook listener is configured (OTP_WEBHOOK_PORT), the bot will
automatically renew the session when it expires during auto-buy monitoring:
refresh token dicoba dulu; kalau habis, bot meminta OTP baru dan menunggu
SMS yang diteruskan webhook. See docs/auto-relogin.md.
