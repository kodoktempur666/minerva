# Homka / AppTG Multi-Account Auto Bot

Bot otomatisasi tap & smart upgrade untuk Telegram Mini App Game (apptg.biz) yang mendukung **Multi-Account** menggunakan otentikasi manual `init_data`.

## Fitur Utama
1. **Multi-Account Support**: Tambahkan akun sebanyak yang Anda inginkan di `config.json`.
2. **2 Pilihan Mode Eksekusi**:
   * `"concurrent"`: Semua akun berjalan bersamaan dalam *thread* terpisah secara real-time.
   * `"sequential"`: Akun bergantian (*round-robin*) menghabiskan energi satu per satu, cocok untuk menghemat kuota / menghindari limit IP.
3. **Proxy per Akun (Opsional)**: Mendukung HTTP/HTTPS proxy terpisah untuk setiap akun agar tidak terdeteksi satu IP.
4. **Auto UUID Client ID**: Jika `client_id` dikosongkan/null, bot otomatis men-generate UUID unik untuk akun tersebut dan menyimpannya.
5. **Smart ROI-Based Upgrade**: Otomatis memilih dan membeli upgrade yang paling cepat balik modal (ROI tertinggi) tanpa boros koin.
6. **Auto Daily Streak & Full Boost**: Otomatis klaim reward harian dan aktivasi full energy boost.

---

## Struktur `config.json`

```json
{
  "settings": {
    "mode": "concurrent",          // "concurrent" (bersamaan) atau "sequential" (bergantian)
    "auto_tap": true,
    "min_taps_batch": 5,
    "max_taps_batch": 12,
    "min_delay_sec": 1.5,
    "max_delay_sec": 3.0,
    "auto_daily": true,
    "auto_boost": true,
    "auto_upgrade": true,
    "max_upgrade_cost": 15000,
    "min_reserve_coins": 1000,
    "level_caps": {
      "regenLvl": 5,
      "tapLvl": 3,
      "enLvl": 3,
      "seeds": 5,
      "wheel": 4,
      "house": 3,
      "friends": 2,
      "farm": 1,
      "factory": 0,
      "rocket": 0
    }
  },
  "accounts": [
    {
      "name": "Akun 1",
      "enabled": true,
      "init_data": "user=%7B...%7D&hash=...",
      "client_id": "065e82e6-d8d4-46fd-b2f1-0b0bfa1373dc",
      "ref_code": "ref_6311855705",
      "proxy": null
    },
    {
      "name": "Akun 2",
      "enabled": true,
      "init_data": "user=%7B...%7D&hash=...",
      "client_id": null,
      "ref_code": "ref_6311855705",
      "proxy": "http://username:password@ip:port"
    }
  ]
}
```

---

## Cara Menambah Akun Baru
1. Buka akun Telegram kedua Anda (di Telegram Web / Desktop).
2. Buka Mini App game-nya, buka **Console** F12, dan ketik:
   ```javascript
   Telegram.WebApp.initData
   ```
3. Copy teksnya, lalu buka `config.json` dan tambahkan blok akun baru ke dalam daftar `"accounts"`.
4. Atur `"enabled": true`. Nilai `"client_id"` boleh diisi `null` karena bot akan otomatis membuatnya secara mandiri.

---

## Cara Menjalankan

```powershell
python C:\Users\User\apptg_bot\bot.py
```
*(Tekan `Ctrl + C` untuk menghentikan semua akun secara aman)*.
