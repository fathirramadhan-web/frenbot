# frenbot di HP Android (Termux) - gratis, tanpa kartu

Kenapa ini jalan: bot Telegram memakai **long polling** (`getUpdates`), bukan webhook.
Jadi tidak perlu server dengan IP publik, tidak perlu port forwarding, tidak perlu domain.
Yang dibutuhkan cuma proses Python yang terus hidup dan koneksi internet.

HP tetap menyala = bot tetap jalan, walau PC mati.

## Langkah

1. Install **Termux** dari F-Droid (bukan Play Store — versi Play Store sudah usang).
   Juga install **Termux:API** (F-Droid) supaya `termux-wake-lock` tersedia.

2. Buka Termux, jalankan:

   ```
   pkg update -y && pkg install -y curl
   curl -fsSL https://raw.githubusercontent.com/fathirramadhan-web/frenbot/main/deploy/termux/setup.sh | bash
   ```

3. Script akan tanya:
   - BOT_TOKEN — dari @BotFather
   - ADMIN_ID — chat ID Telegram kamu
   - SESSION_JSON — isi `mysf_session.json` (boleh dikosongkan, lalu kirim `/login` ke bot)

4. Setelah selesai:

   ```
   cd ~/frenbot
   ./run.sh
   ```

## Penting: jangan sampai HP sleep

`run.sh` sudah memanggil `termux-wake-lock`. Ini mencegah Android mematikan CPU saat
layar mati. Tanpa ini bot akan mati sendiri setelah beberapa menit.

- Cek wake-lock: `termux-wake-lock` (aktif) / `termux-wake-unlock` (mati)
- Cek bot hidup: `tail -f bot.log`
- Matikan bot: `pkill -f "frenbot.py --bot" && termux-wake-unlock`

## Auto-start saat HP reboot (opsional)

Install **Termux:Boot** dari F-Droid, lalu buat:

```
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/frenbot <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd $HOME/frenbot
nohup python frenbot.py --bot > bot.log 2>&1 &
EOF
chmod +x ~/.termux/boot/frenbot
```

Setelah itu bot otomatis jalan setiap HP menyala.

Tapi ada syarat supaya benar-benar auto:

1. **Buka Termux:Boot satu kali** setelah install. Di Android 8+, sistem tidak
   mengirim sinyal boot ke aplikasi yang belum pernah dibuka setelah reboot.
   Tanpa ini, bot tidak jalan walau file boot sudah ada.
2. **Matikan battery optimization** untuk Termux dan Termux:Boot:
   Settings → Apps → Termux → Battery → Unrestricted / Don't optimize.
3. **Izinkan autostart** (HP Xiaomi/Oppo/Vivo/Realme/Samsung):
   Settings → Apps → Termux → Auto-start → ON.
   HP OEM sering memblokir aplikasi jalan sendiri setelah reboot tanpa ini.
4. Sinyal boot hanya dikirim saat **reboot**, bukan saat HP benar-benar mati lalu
   dinyalakan ulang dari keadaan mati total — tapi untuk kasus itu tetap sama:
   Termux:Boot dipanggil saat sistem selesai boot.

Setelah reboot, cek dengan `tail -f ~/frenbot/bot.log`. Kalau tidak ada log
baru, buka Termux:Boot sekali lalu jalankan `./frenbot/run.sh`.

## Catatan sesi

`mysf_session.json` berisi token refresh 30 hari. Setelah lewat 30 hari, kirim
`/login` ke bot — OTP dikirim ke nomor Smartfren, lalu masukkan kode lewat bot.
Sesi akan ditimpa otomatis.

Sesi disimpan lokal di HP (tidak dikirim ke server mana pun). Jangan pernah
tempel isi `mysf_session.json` di chat publik.
