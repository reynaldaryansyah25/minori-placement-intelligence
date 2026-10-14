# MINORI Placement Intelligence

Aplikasi operasional rekrutmen dan penempatan tenaga kerja ke Jepang dengan arsitektur
**Modular Monolith dan prinsip Clean Architecture**, dilengkapi antarmuka frontend
**Japanese Minimalist Enterprise** berbasis Python 3.12 dan Streamlit.

Sistem menyediakan operasional penempatan menyeluruh:
- **Operational Command Center (Overview):** Metrik KPI real-time, action center, dan log audit.
- **Candidates Directory:** Profil kandidat, skor JLPT/JFT-Basic, sertifikasi kompetensi, dan riwayat kerja.
- **Vacancies Explorer:** Manajemen lowongan kerja Jepang, spesifikasi bahasa alternatif, dan kuota.
- **Candidate Matching (Showcase):** Peringkat deterministik, explainability engine, rincian bobot skor (35% Bahasa, 30% Pengalaman, 20% Sertifikasi, 15% Preferensi), dan persetujuan staf.
- **Placement Pipeline:** Stepper tahapan seleksi (Interview ➔ Medical ➔ Dokumen ➔ Orientasi ➔ Terbang) dan penjadwalan sadar zona waktu WIB.
- **Reminder Center:** Monitoring pengingat, dry-run simulation, pemulihan sewa (*lease*), dan penelusuran riwayat percobaan.
- **AI Vacancy Intelligence:** Ekstraksi teks/PDF/DOCX/XLSX/CSV/TXT, terjemahan Indonesia dan pemeriksaan persyaratan melalui 9Router, lalu koreksi dan publikasi oleh staf.
- **Reports & Analytics:** Distribusi kategori, ringkasan kendala kualifikasi, dan ekspor CSV resmi RFC 4180.
- **Role-Based Access Control (RBAC):** Pemisahan tegas peran HR Staff (Admin/Tulis) dan Reviewer (Read-Only) di frontend dan backend.

## Struktur repository

```text
minori-placement-intelligence/
├── backend/
│   ├── minori/
│   │   ├── api/                 # Router dan dependency injection
│   │   ├── core/                # Settings dan logging
│   │   ├── domain/              # Eligibility, scoring, ranking, entities dan port
│   │   ├── services/            # Use case
│   │   ├── repositories/        # Adapter SQLAlchemy
│   │   ├── schemas/             # DTO Pydantic
│   │   ├── db/models/           # 14 tabel ORM; engine, session, inspection, seeding
│   │   ├── integrations/nine_router/
│   │   └── main.py
│   └── alembic/versions/        # Migrasi bisnis, matching, dan placement_reminders.py
├── frontend/
│   ├── app.py                  # Entry point Streamlit
│   ├── minori_frontend/         # UI dan HTTP client
│   └── .streamlit/config.toml
├── workflows/n8n/backend_health.json
├── data/dummy/                 # candidates.json, vacancies.json, placement_data.json
├── scripts/                    # Bootstrap, lock, verifikasi, smoke test
├── tests/                      # unit, integration, architecture
├── docs/                       # Arsitektur dan operasional
├── test-results/               # Ringkasan dan artefak pengujian
├── .env.example
├── .gitattributes
├── .gitignore
├── .dockerignore
├── AGENTS.md
├── alembic.ini
├── pyproject.toml
├── requirements.lock
├── Dockerfile
└── compose.yaml
```

## Dependencies

Python **3.12** diperlukan. Dependency langsung dideklarasikan sekali di
`pyproject.toml`; versi hasil instalasi dikunci dalam `requirements.lock`.

| Kelompok | Dependency |
| --- | --- |
| Backend | FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, pydantic-settings |
| Integrasi dan HTTP | OpenAI SDK, HTTPX |
| Frontend extra | Streamlit, pandas (format tabel) |
| Development extra | Pytest, pytest-cov, Ruff |
| Build package | setuptools |
| Infrastructure | Docker Engine, Docker Compose, image n8n |

SQLite disertakan oleh Python. SDK OpenAI digunakan hanya sebagai client API
OpenAI-compatible menuju 9Router. HTTPX dipakai frontend dan TestClient; transport
SDK OpenAI merupakan dependency transitif SDK. Ruff menyediakan lint dan format,
sedangkan pytest-cov menghasilkan bukti cakupan pengujian.

## Instalasi lokal

Jalankan dari root repository dengan Python 3.12:

```sh
python scripts/bootstrap.py
```

Script membuat `.venv`, memasang backend beserta extra frontend dan development,
membuat `.env` dari contoh, serta menghasilkan key enkripsi n8n acak tanpa
mencetaknya. Konfigurasi yang sudah diisi tetap dipertahankan. Jangan commit `.env`.

Aktifkan virtual environment di PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Di Linux/macOS:

```sh
source .venv/bin/activate
```

Jika kebijakan PowerShell membatasi aktivasi, jalankan interpreter langsung,
misalnya `.\.venv\Scripts\python.exe scripts/verify.py`; aktivasi tidak wajib.

```sh
python -m alembic upgrade head
python scripts/seed_database.py
python -m uvicorn minori.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Buka terminal lain dengan virtual environment yang sama, lalu jalankan Streamlit
dari direktorinya agar `.streamlit/config.toml` terbaca:

```sh
cd frontend
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
```

Backend: [health](http://127.0.0.1:8000/health) dan
[Swagger UI](http://127.0.0.1:8000/docs). Frontend:
[Streamlit](http://127.0.0.1:8501). Port CLI dapat diubah langsung; sesuaikan
`BACKEND_BASE_URL` ketika port backend lokal berubah.

## Menjalankan Docker

Pastikan Docker Engine aktif dan `.env` sudah dibuat oleh bootstrap:

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
python scripts/verify_containers.py
```

Compose menjalankan backend, frontend, dan n8n dengan healthcheck dan volume
persisten. Backend menjalankan Alembic sebelum Uvicorn. Backend dan frontend memakai
target berbeda dalam satu Dockerfile, pengguna non-root, dan dependency runtime
tanpa alat pengujian. Image Python dikunci dengan digest dan versi n8n dikonfigurasi
melalui environment. n8n memakai SQLite sendiri pada volume terpisah.

Buka [n8n](http://localhost:5678), buat akun owner, dan impor workflow manual sesuai
[panduan workflow](workflows/README.md). Variabel `BACKEND_PORT`, `FRONTEND_PORT`,
dan `N8N_PORT` mengatur port host Compose. Akses port terikat ke localhost.

```sh
docker compose logs --tail=50 backend frontend n8n
docker compose stop
```

## Konfigurasi 9Router

Isi `.env` menggunakan kredensial dan ID model dari instance 9Router:

```dotenv
LLM_ENABLED=true
NINE_ROUTER_BASE_URL=http://127.0.0.1:20128/v1
NINE_ROUTER_API_KEY=
NINE_ROUTER_MODEL=
NINE_ROUTER_DOCKER_BASE_URL=http://host.docker.internal:20128/v1
```

Isi kedua nilai kosong sebelum mengaktifkan LLM. Settings menolak konfigurasi yang
tidak lengkap. Model dan key tidak memiliki default di kode. Integrasi tidak
dipanggil otomatis saat startup, health check, atau pembukaan frontend. Instance
9Router dikelola terpisah dan belum disediakan sebagai service Compose.

## Pengujian

```sh
python scripts/verify.py
python scripts/smoke_test.py
python scripts/verify_matching.py --base-url http://127.0.0.1:8000
python scripts/verify_reminders.py
```

Pemeriksaan mencakup dependency, lint, format, batas arsitektur, settings, response
HTTP 200/503, SQLite, migrasi upgrade/downgrade, kontrak request 9Router terhadap
server lokal, render Streamlit, seluruh 40 pasangan matching, scoring, explanation,
dan API. Smoke test menjalankan proses backend serta
frontend sebenarnya, memeriksa HTTP, lalu menghentikannya.

Hasil nyata tersedia pada [ringkasan verifikasi](test-results/verification.md).
Log, JUnit XML, coverage XML/HTML, dan JSON hasil eksekusi disimpan di
`test-results/` dan diabaikan oleh Git. Tes 9Router lokal tidak memverifikasi
instance atau kredensial LLM pengguna.

Panduan lebih lanjut: [panduan frontend](docs/frontend.md),
[arsitektur](docs/architecture.md),
[struktur database dan ERD](docs/database.md),
[algoritma matching](docs/matching.md), [kontrak API](docs/api.md),
[placement dan reminder](docs/placements_reminders.md),
[operasional](docs/operations.md), dan [pedoman pengembangan](AGENTS.md).

Panduan AI operasional, demo profesional, dan konfigurasi workflow n8n: [AI operations](docs/ai_operations.md).

Persiapan frontend publik dengan login reviewer, Tailscale Funnel, dan prosedur
mematikan akses: [demo publik Windows](docs/public_demo.md).
