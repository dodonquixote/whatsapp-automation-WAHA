# Manual Book WhatsApp Automations

Versi: 1.0
Tanggal: 2026-05-06

Dokumen ini menjelaskan cara menjalankan dan menggunakan proyek WhatsApp Automations yang terdiri dari WAHA, backend FastAPI, dashboard Streamlit, dan frontend statis.

## 1. Gambaran Umum

Program ini digunakan untuk mengelola sesi WhatsApp melalui WAHA, menampilkan QR untuk pairing, serta melakukan blast pesan menggunakan data dari CSV atau Excel.

Komponen utama:
- WAHA sebagai engine WhatsApp.
- Backend FastAPI sebagai penghubung ke WAHA.
- Dashboard Streamlit sebagai antarmuka pengguna.
- Frontend statis berbasis HTML, CSS, dan JavaScript.

## 2. Struktur Project

- `docker-compose.yml` untuk menjalankan seluruh service.
- `backend/` berisi server FastAPI.
- `dashboard/` berisi aplikasi Streamlit.
- `frontend/` berisi dashboard statis.

## 3. Kebutuhan Sistem

- Docker dan Docker Compose, direkomendasikan.
- Python 3.10+ jika ingin menjalankan komponen secara lokal.
- Koneksi internet untuk mengunduh image WAHA dan dependensi Python.

## 4. Instalasi dengan Docker

1. Pastikan file `.env` ada di root project.
2. Jalankan perintah berikut dari folder root project:

```bash
docker-compose up --build -d
```

3. Cek status service:

```bash
docker-compose ps
```

4. Cek log backend bila perlu:

```bash
docker-compose logs -f backend
```

## 5. Konfigurasi Environment

Contoh isi `.env`:

```env
WAHA_API_KEY=isi_api_key_anda
WAHA_SESSION=default
USERNAME=admin
PASSWORD=admin123
WAHA_PRINT_QR=True
```

Keterangan:
- `WAHA_API_KEY` untuk autentikasi ke WAHA jika diperlukan.
- `WAHA_SESSION` adalah nama session WhatsApp.
- `USERNAME` dan `PASSWORD` dipakai oleh container WAHA.

## 6. Alamat Akses

Jika menjalankan dengan Docker Compose, alamat defaultnya:
- WAHA: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Dashboard Streamlit: `http://localhost:8501`

## 7. Cara Menggunakan Dashboard

### 7.1 Menghubungkan WhatsApp

1. Buka dashboard Streamlit.
2. Klik `Start Session`.
3. Scan QR code yang muncul pada sidebar.
4. Jika sudah terhubung, status akan berubah menjadi connected.

### 7.2 Logout Session

Klik `Logout Session` untuk memutus koneksi session WhatsApp dari WAHA.

### 7.3 Refresh QR

Klik `Refresh QR` jika QR belum muncul atau perlu dibuat ulang.

## 8. Dynamic Blast

Fitur utama dashboard adalah Dynamic Blast.

Langkah penggunaan:
1. Upload file CSV, XLSX, atau XLS.
2. Pastikan file memiliki kolom nomor WhatsApp bernama `NOMOR`.
3. Tulis pesan template menggunakan placeholder.
4. Tambahkan field tambahan bila diperlukan.
5. Atur delay dan batch sesuai kebutuhan.
6. Jalankan blast melalui tombol yang tersedia pada dashboard.

## 9. Format File Input

Contoh CSV minimal:

```csv
NOMOR,username,nama,alamat
6281234567890,joko,Joko Santoso,Jakarta
6281987654321,sari,Sari Dewi,Bandung
```

Catatan:
- Sistem membaca CSV dengan beberapa encoding umum.
- Untuk Excel, gunakan `.xlsx` atau `.xls`.

## 10. Template Pesan

Template menggunakan placeholder dengan format `{{nama_kolom}}`.

Contoh:

```text
Halo {{username}},
Kami punya informasi untuk Anda.
Nomor Anda: {{NOMOR}}
```

Placeholder bersifat case-sensitive, jadi nama field harus sama persis dengan header data.

## 11. Endpoint Penting

Backend menyediakan endpoint berikut:
- `GET /waha/status` untuk cek status session.
- `GET /waha/qr?restart=true|false` untuk mengambil QR.
- `POST /api/sessions/start` untuk memulai session.
- `POST /api/sessions/logout` untuk logout session.

## 12. Menjalankan Secara Lokal Tanpa Docker

### Backend

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Dashboard

```bash
python -m pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

### Frontend Statis

```bash
cd frontend
python -m http.server 3000
```

## 13. Troubleshooting

### QR tidak muncul

- Pastikan service WAHA berjalan.
- Pastikan `WAHA_PRINT_QR=True` di file `.env`.
- Coba klik `Refresh QR`.

### Dashboard tidak bisa terhubung ke backend

- Pastikan backend berjalan di port 8000.
- Jika lokal, pastikan `BACKEND_URL` mengarah ke `http://localhost:8000`.

### File CSV gagal dibaca

- Periksa delimiter dan encoding file.
- Pastikan header file valid.

## 14. Catatan Keamanan

- Jangan commit file `.env` ke repository.
- Simpan kredensial WAHA secara lokal.

## 15. Ringkasan Alur Kerja

1. Jalankan service dengan Docker Compose.
2. Buka dashboard.
3. Start session WAHA.
4. Scan QR.
5. Upload data penerima.
6. Tulis template pesan.
7. Jalankan blast.

## 16. Penutup

Manual book ini dapat dikembangkan menjadi versi PDF atau dibagi per komponen menjadi beberapa file terpisah jika diperlukan.