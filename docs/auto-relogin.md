# Auto Re-login (OTP Webhook)

When a Smartfren session expires during automation (e.g. auto-buy), Frenbot
renews it automatically:

1. Refresh token dicoba dulu (berlaku 30 hari) — tanpa OTP, tanpa interaksi.
2. Kalau refresh token habis, Frenbot meminta OTP baru ke nomor terdaftar.
3. SMS forwarder di HP/router meneruskan SMS ke webhook Frenbot.
4. OTP di-parse dari isi SMS, dikirim ke verify, sesi baru aktif.
5. Auto-buy lanjut dengan sesi baru.

## Architecture

```
HP / router (SMS forwarder)
   |  SMS OTP masuk
   |  POST http://IP_PC:8081/api/otp  (header X-Webhook-Secret)
   v
Frenbot (PC/VPS)
   HTTP server (:8081/api/otp)
   -> parse OTP (regex)
   -> submit ke /signin/mdn/verify
   -> sesi baru, auto-buy resume
```

## Setup

### Step 1: Configure Frenbot

Add to .env in the frenbot folder:

```
OTP_WEBHOOK_PORT=8081
OTP_WEBHOOK_SECRET=your-random-secret-here
```

Buka port di firewall bila PC/VPS di belakang firewall.

### Step 2: Configure SMS Forwarder

Pasang aplikasi SMS forwarder di HP Android (atau router OpenWrt dengan
SMS forwarder) yang bisa POST webhook saat SMS masuk. Arahkan ke:

```
WEBHOOK_URL=http://IP_PC:8081/api/otp
WEBHOOK_SECRET=your-random-secret-here
```

Secret harus sama dengan OTP_WEBHOOK_SECRET di .env.

### Step 3: Test

Health check:

```bash
curl http://IP_PC:8081/health
# Expected: ok
```

Simulasi webhook OTP:

```bash
curl -X POST http://IP_PC:8081/api/otp \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-random-secret-here" \
  -d '{"from":"Smartfren","body":"Kode OTP mySF Anda: 654321. Jangan berikan ke siapapun."}'
```

## Webhook API

### POST /api/otp

Headers:
- Content-Type: application/json (required)
- X-Webhook-Secret: must match OTP_WEBHOOK_SECRET if configured

Request body:

```json
{"from": "Smartfren", "body": "Kode OTP mySF Anda: 123456. Jangan berikan kepada siapapun."}
```

Responses:

```json
{"status":"dispatched","otp":"123456"}
{"status":"no_waiter","otp":"123456"}
{"status":"no_otp_found"}
```

### GET /health

Returns ok — useful for uptime monitoring.

## OTP Parsing

Priority order:
1. Pattern spesifik: "Kode OTP/verifikasi ... 123456" (4-6 digit)
2. Generic 6 digit berdiri sendiri
3. Generic 4 digit berdiri sendiri

## Behavior

- Backward compatible — tanpa OTP_WEBHOOK_PORT, perilaku tidak berubah
  (login manual; refresh token tetap otomatis).
- Cooldown — minimum 2 menit antar percobaan re-login per nomor.
- Timeout — jika OTP tidak diterima dalam 3 menit, re-login gagal dan
  auto-buy berhenti.
- Fallback — bila auto re-login gagal, user diberitahu dan login manual
  diperlukan.
- Berlaku di mode bot, CLI, dan MCP.
