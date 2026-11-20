#!/data/data/com.termux/files/usr/bin/bash
# frenbot - installer untuk Termux (HP Android, gratis tanpa kartu)
set -e

echo "=== frenbot Termux installer ==="
echo "HP harus terus menyala dan terhubung internet. Bot pakai long polling,"
echo "jadi tidak butuh IP publik / port forwarding / webhook."

pkg update -y
pkg install -y python git termux-api
pip install --upgrade pip setuptools wheel
pip install segno

cd "$HOME"
if [ ! -d frenbot ]; then
  git clone https://github.com/fathirramadhan-web/frenbot.git
fi
cd frenbot

# Simpan secret. Tidak pernah ditampilkan di layar.
read -p "BOT_TOKEN (dari @BotFather): " BOT_TOKEN
read -p "ADMIN_ID (chat ID Telegram kamu): " ADMIN_ID
read -sp "SESSION_JSON (isi mysf_session.json, bisa kosong lalu /login di bot): " SESSION_JSON
echo

cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_ID=$ADMIN_ID
OTP_WEBHOOK_PORT=8081
EOF

# Tulis sesi kalau diisi. Kalau kosong, kirim /login ke bot nanti.
if [ -n "$SESSION_JSON" ]; then
  printf '%s' "$SESSION_JSON" > mysf_session.json
  echo "Sesi tersimpan."
else
  echo "Sesi kosong. Kirim /login ke bot untuk OTP."
fi

chmod +x run.sh
echo
echo "=== Selesai. Jalankan: ./run.sh ==="
