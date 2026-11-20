# CLI Mode

## Run

```bash
python frenbot.py --cli
```

## Menu

```
1. Profil (pulsa, masa aktif)
2. Cek kuota
3. Daftar paket
4. Beli paket
5. Auto-buy (setup/status/stop)
6. Login
7. Logout
8. Rekomendasi paket (analisis kuota + nilai terbaik)
0. Keluar
```

## Examples

Cek pulsa dan kuota: pilih 1 lalu 2.

Beli paket: pilih 3 untuk melihat daftar kode paket, pilih 4, masukkan kode
paket, pilih metode (pulsa/qris), konfirmasi y. Pembelian memakai uang
sungguhan; selalu cek harga di detail paket sebelum konfirmasi.

Login: pilih 6, masukkan nomor Smartfren, balas kode OTP dari SMS. Sesi
tersimpan di mysf_session.json dan dipakai bersama dengan mode bot/MCP.

Auto-buy: pilih 5, masukkan interval (menit), threshold (MB, 0 = hanya saat
habis), dan kode paket. Monitor berjalan di background selama CLI hidup;
pembelian otomatis via pulsa. Pilih 5 lagi untuk melihat status atau stop.

## Notes

- Jika webhook OTP dikonfigurasi di .env, auto re-login aktif juga di CLI.
- Tanpa segno, QRIS ditampilkan sebagai string teks.
