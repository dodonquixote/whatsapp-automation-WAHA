Setup dan menjalankan project WA Blast

1) Isi nilai di file `.env` yang sudah dibuat di root project:


Account credentials for WAHA service (optional):

- `USERNAME` — username akun WAHA (contoh: admin)
- `PASSWORD` — password akun WAHA (contoh: admin123)

These are read from `/.env` and passed into the `waha` container via `docker-compose`.

2) Jalankan dengan Docker Compose (direkomendasikan):

```bash
# dari folder project root (tempat docker-compose.yml berada)
docker-compose up --build -d
# lihat logs
docker-compose logs -f backend
```

3) Jalankan dashboard Streamlit:

```bash
python -m pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

4) Alur blast seperti n8n (tanpa Data Table):

- Upload file CSV/XLSX berisi data kreator dari dashboard.
- Isi data campaign (`campaign`, `produk`, `komisi`, `sow`, `link_affiliate`, `link_group`).
- Isi minimal 1 template pesan.
- Template placeholder yang didukung: `{{username}}`, `{{campaign}}`, `{{product}}`, `{{komisi}}`, `{{sow}}`, `{{link_affiliate}}`, `{{namapenerima}}`, `{{no}}`, `{{alamat}}`, `{{nama}}`, `{{link_grup}}`.
- Backend akan melakukan mapping data kreator dari kolom CSV/XLSX, pilih template secara acak per baris, lalu kirim dengan delay bertahap dan batch rest.

5) Jika ingin menjalankan backend secara lokal tanpa Docker:

- Pastikan Python 3.10+ terpasang.
- Pasang dependensi:

```bash
python -m pip install -r backend/requirements.txt
```

- Eksport environment pada Windows (PowerShell):

```powershell
setx WAHA_URL "http://localhost:3000"
setx WAHA_SESSION "default"
setx WAHA_API_KEY "<isi_api_key_anda>"
# restart terminal agar env ter-load
```

- Jalankan server:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Catatan: Kode backend sudah membaca `WAHA_API_KEY` dari environment dan akan menambahkan header `x-api-key` dan `Authorization: Bearer ...` pada request ke WAHA.
