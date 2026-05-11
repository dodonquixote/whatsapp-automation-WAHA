# WhatsApp Blast Dashboard

Dashboard SPA untuk mengirim WhatsApp blast menggunakan WAHA backend.

## Struktur
```
whatsapp-blast/
├── index.html       ← Entry point
├── css/
│   └── style.css    ← Semua styling (dark industrial theme)
└── js/
    └── main.js      ← Semua logika JavaScript (vanilla ES6+)
```

## Cara Menjalankan

### Option 1: Python HTTP Server
```bash
cd whatsapp-blast
python3 -m http.server 3000
# Buka: http://localhost:3000
```

### Option 2: Node.js
```bash
cd whatsapp-blast
npx serve .
```

### Option 3: VS Code Live Server
Buka `index.html` → klik kanan → "Open with Live Server"

## Konfigurasi Backend
Edit baris di `js/main.js`:
```js
const API = 'http://localhost:8000';
```

## Fitur
- ✅ Session management (start, logout, QR refresh)
- ✅ Real-time status polling setiap 3 detik
- ✅ Real-time QR polling setiap 2 detik (saat belum connected)
- ✅ Upload CSV/XLSX dengan drag & drop
- ✅ Auto-detect headers & validasi kolom NOMOR
- ✅ Template dengan placeholder `{{nama_kolom}}`
- ✅ Additional global fields
- ✅ Preview template real-time
- ✅ Pengaturan delay yang detail
- ✅ Toast notifications
- ✅ Responsive (mobile-friendly)

## API Endpoints yang Digunakan
| Method | Endpoint | Kegunaan |
|--------|----------|----------|
| GET | `/waha/status` | Cek status sesi |
| POST | `/api/sessions/start` | Mulai sesi |
| POST | `/api/sessions/logout` | Logout sesi |
| GET | `/waha/qr?restart=true/false` | Ambil QR Code |
| POST | `/send-blast-dynamic` | Kirim blast |
