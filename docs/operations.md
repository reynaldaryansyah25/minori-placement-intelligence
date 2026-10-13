# Operasional

## Konfigurasi

`.env.example` adalah kontrak konfigurasi. `scripts/bootstrap.py` membuat `.env`,
menghasilkan `N8N_ENCRYPTION_KEY` acak, dan mempertahankan nilai yang sudah diisi.
Process environment mengalahkan `.env`. `.env` dan database tidak masuk Git atau
build context Docker. Path database relatif selalu diselesaikan dari root repository.
Untuk instalasi package di luar checkout, tentukan `MINORI_PROJECT_ROOT` secara eksplisit.

LLM dinonaktifkan secara default. Untuk mengaktifkannya isi `LLM_ENABLED=true`,
`NINE_ROUTER_BASE_URL`, `NINE_ROUTER_API_KEY`, dan `NINE_ROUTER_MODEL`. Gunakan ID
model persis dari dashboard router. Backend di Docker menggunakan
`NINE_ROUTER_DOCKER_BASE_URL`, misalnya `http://host.docker.internal:20128/v1` untuk
router di host. Router harus dapat diakses dari jaringan container. Jangan memakai
localhost container untuk merujuk layanan pada host.

Compose mengikat port ke `127.0.0.1`. HTTP lokal memakai
`N8N_SECURE_COOKIE=false`; gunakan HTTPS dan secure cookie bila deployment dibuat
untuk akses eksternal. Konfigurasi fondasi ini belum menyediakan autentikasi API.
Buat akun owner di UI n8n saat pertama kali digunakan. Jangan mengubah encryption
key setelah credentials n8n dibuat. Database aplikasi dan SQLite n8n memakai volume
berbeda.

## Database dan migrasi

```sh
python -m alembic upgrade head
python -m alembic current
python scripts/seed_database.py
python scripts/seed_database.py
python scripts/check_database.py
```

Untuk perubahan model mendatang, impor model ORM di `backend/alembic/env.py`,
buat revisi dengan `python -m alembic revision --autogenerate -m "deskripsi_perubahan"`,
kemudian tinjau isi migrasi sebelum menjalankannya. Gunakan nama deskriptif. Jangan
memakai `Base.metadata.create_all()` sebagai pengganti migrasi.

Backend container menjalankan migrasi sebelum Uvicorn. Konfigurasi memakai satu
worker dan volume database lokal. Backup SQLite harus menyertakan konsistensi WAL;
gunakan SQLite backup API atau hentikan layanan saat mengambil backup file.

## Verifikasi

```sh
python scripts/verify.py
python scripts/smoke_test.py
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
python scripts/verify_containers.py
```

`verify.py` mencatat dependency, lint, format, Pytest, migrasi, drift schema,
dua eksekusi seed, perbandingan idempotensi, dan query database. Pemeriksaan database
membandingkan revisi dengan head Alembic dan mencakup seluruh model, foreign keys,
serta integritas SQLite. Smoke test membuka port lokal sementara, menjalankan backend
dan Streamlit, memeriksa endpoint HTTP, lalu menghentikan kedua proses.
Tes frontend menggunakan Streamlit AppTest untuk memeriksa tampilan sukses dan gagal.

Seed Docker dijalankan secara eksplisit dengan
`docker compose exec -T backend python scripts/seed_database.py`.
Jalankan dua kali untuk memeriksa idempotensi. Schema bisnis dan sifat transaksi
dijelaskan dalam [struktur database](database.md). Downgrade yang akan menghapus
data bisnis ditolak; jangan menghapus volume untuk memperbarui skema.

```sh
docker compose logs --tail=50 backend frontend n8n
docker compose stop
docker compose start
```

`stop` mempertahankan container dan volume. `down` menghapus container dan jaringan
serta mempertahankan volume. Penghapusan volume menghilangkan database, credentials,
dan workflow tersimpan; lakukan hanya jika memang ingin menghapus data tersebut.

## Dependency

Sumber dependency langsung adalah `pyproject.toml`. `requirements.lock` menyimpan
versi hasil resolusi sebagai constraints; Docker memasang dependency sesuai extra
masing-masing tanpa memasang alat pengujian. SQLite tersedia melalui standard library
Python. n8n disediakan oleh image Docker, bukan package Python. Setelah pembaruan
dependency yang disengaja, gunakan venv bersih, jalankan seluruh pemeriksaan, lalu
`python scripts/lock_dependencies.py`. Uji juga build Linux karena lock dibuat pada
Python 3.12 Windows. Jangan memasang dependency global untuk menjalankan proyek.
