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
5. Rekomendasi — analisis sisa kuota + estimasi hari tersisa, verdict perlu
   beli atau tidak, dan 5 paket nilai terbaik (harga per GB) dari seluruh
   katalog, masing-masing dicek eligibilitas bayarnya (online/QRIS atau
   khusus pulsa). Tekan tombol paket untuk langsung ke detail dan beli.
6. Beli Paket — semua paket rekomendasi tampil dengan pagination (10 per
   halaman, tombol Sebelumnya/Berikutnya), plus tombol Katalog Web untuk
   kategori kuota/5G/roaming dan Kode Manual. Pilih paket: bot menampilkan
   detail dulu (harga + diskon, masa berlaku, benefit, promo, deskripsi,
   link S&K). Tekan Beli Paket, pilih bayar Pulsa atau QRIS, konfirmasi.
   QRIS dikirim sebagai gambar QR; status pembayaran dipoll otomatis dan
   hasilnya diberitahukan.
7. Auto-Buy — pilih interval, threshold MB, paket, lalu mulai. Bot memonitor
   kuota di background dan membeli otomatis via pulsa saat kuota habis atau
   di bawah threshold.

## Bot Commands

Menu command terdaftar di Telegram (muncul saat mengetik / di chat):

- /start : menu utama (atau profil bila sesi aktif)
- /profil : pulsa, masa aktif, status nomor
- /kuota : sisa kuota internet, nelpon, SMS + paket aktif
- /paket : katalog paket lengkap + beli
- /rekomendasi : analisis kuota + paket nilai terbaik
- /beli KODE : beli cepat by kode paket (tanpa argumen: diminta kode)
- /autobuy : setup / status / stop auto-buy
- /refresh : muat ulang profil
- /login : login via OTP SMS
- /logout : hapus sesi
- /bantuan : daftar command

Semua aksi juga tersedia lewat tombol inline keyboard. Bot hanya
merespons ADMIN_ID; pesan dari user lain diabaikan.

## Auto Re-login

If an OTP webhook listener is configured (OTP_WEBHOOK_PORT), the bot will
automatically renew the session when it expires during auto-buy monitoring:
refresh token dicoba dulu; kalau habis, bot meminta OTP baru dan menunggu
SMS yang diteruskan webhook. See docs/auto-relogin.md.
