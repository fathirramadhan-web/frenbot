#!/data/data/com.termux/files/usr/bin/bash
# Jalankan frenbot di Termux. Wake-lock mencegah HP sleep mematikan bot.
cd "$HOME/frenbot"

# Izinkan akses penyimpanan sekali (untuk baca/copy mysf_session.json).
termux-setup-storage 2>/dev/null || true

# Kunci wake supaya CPU tidak tidur saat layar mati.
termux-wake-lock
echo "Wake-lock aktif. Bot jalan di background."

# Matikan proses lama kalau ada.
pkill -f "frenbot.py --bot" 2>/dev/null || true
sleep 1

nohup python frenbot.py --bot > bot.log 2>&1 &
echo "PID: $!"
echo "Cek log: tail -f bot.log"
echo "Hentikan: pkill -f 'frenbot.py --bot'; termux-wake-unlock"
