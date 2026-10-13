# Pedoman pengembangan MINORI

Repository ini menggunakan Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic,
SQLite, Streamlit, n8n, SDK OpenAI untuk 9Router, Pytest, dan Docker Compose.

## Batas arsitektur

- Backend merupakan modular monolith. Kelompokkan kode menurut kapabilitas dan
  tanggung jawab di dalam lapisan yang tersedia ketika kapabilitas ditambahkan.
- `domain` hanya bergantung pada standard library. Definisikan kontrak port di sini.
- `services` menjalankan use case dan hanya mengimpor `domain` serta standard library.
- `repositories` mengimplementasikan port persistensi melalui `db` dan SQLAlchemy.
- `integrations` menyediakan adapter layanan eksternal, termasuk 9Router.
- `schemas` memuat kontrak Pydantic untuk transport HTTP.
- `api` menerjemahkan HTTP dan menyusun dependensi melalui dependency injection.
- `core` menangani konfigurasi dan logging; `db` mengelola engine, sesi, dan metadata.
- `main.py` merupakan composition root. Frontend hanya mengakses backend lewat HTTP.
- Dilarang mengakses SQLite langsung dari frontend atau workflow n8n.

## Batas pekerjaan

Jaga fondasi tetap kecil. Penambahan matching, reminder, extraction, atau tabel bisnis
memerlukan permintaan pengguna yang mencakup fitur tersebut. Hindari abstraksi generic
CRUD, framework tambahan, file placeholder kosong, atau dependency yang tidak digunakan.
Gunakan nama berdasarkan tanggung jawab; jangan memberi nama berbasis urutan pengembangan.

## Konfigurasi dan pemeriksaan

Simpan kredensial melalui environment variables. Jangan commit `.env`, database,
log, data pribadi, atau hasil pengujian yang memuat konfigurasi sensitif. Jangan
mencetak key, prompt, payload kandidat, atau seluruh settings ke log.
`pyproject.toml` adalah sumber dependency langsung; `requirements.lock` adalah constraints
hasil resolusi. Semua perubahan skema harus melalui Alembic, bukan `create_all()`.

Jalankan `python scripts/verify.py`, kemudian `docker compose config --quiet` untuk
perubahan infrastruktur. Uji perilaku yang berubah; tes tidak boleh memanggil provider
LLM sebenarnya. Laporkan perintah yang dieksekusi, hasilnya, dan keterbatasannya dengan jujur.
