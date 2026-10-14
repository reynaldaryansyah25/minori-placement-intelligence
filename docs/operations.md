# Konfigurasi dan operasional

Jalankan perintah dari root repository menggunakan PowerShell.
Selesaikan [instalasi awal](../README.md#instalasi-di-windows) terlebih dahulu.

## Environment

Gunakan satu `.env` berdasarkan `.env.example`. Process environment mengalahkan
nilai berkas. Jangan mengganti `N8N_ENCRYPTION_KEY` setelah credentials n8n dibuat.

| Konfigurasi | Penggunaan |
| --- | --- |
| `INTERNAL_API_TOKEN` | Staf dan worker internal backend utama |
| `REVIEWER_API_TOKEN` | Akses baca backend utama; mutasi ditolak |
| `N8N_ENCRYPTION_KEY` | Enkripsi credentials n8n |
| `NINE_ROUTER_*`, `LLM_*` | Gateway AI backend |
| `PUBLIC_DEMO_*`, `PUBLIC_SESSION_*` | Login dan batas sesi publik |
| `SANDBOX_*` | Credentials dan batas sandbox |
| `NOTIFICATION_*` | Mode, lease, dan retry pengingat |

Jangan mengaktifkan `PUBLIC_REVIEWER_MODE` atau `INTERACTIVE_DEMO_MODE` secara global
di `.env`; Compose publik menetapkannya hanya pada sandbox.

## Profil Docker

| Profil | Database dan layanan |
| --- | --- |
| `compose.yaml` | Staf/backend/n8n lokal, volume `backend_data`, default dry-run |
| `compose.yaml + compose.demo.yaml` | `professional_demo_data/professional-demo.db` dan Mailpit demo |
| `compose.public-demo.yaml` | Backend per sesi, frontend 8502, n8n dan Mailpit sandbox |
| `compose.ai-test.yaml` | Database uji tmpfs dan port uji terpisah |
| `compose.reminder-test.yaml` | Uji reminder terisolasi tanpa AI |

Gunakan profil yang sama saat menjalankan/menghentikan layanan. Profil publik dan
uji berbagi nama project dengan stack staf. Jangan memakai `--remove-orphans`
atau `down -v`; layanan lain, database, dan volume n8n harus dipertahankan.

```powershell
docker compose -f compose.yaml -f compose.demo.yaml ps
docker compose -f compose.yaml -f compose.demo.yaml logs --tail 50 backend frontend
docker compose -f compose.yaml -f compose.demo.yaml stop backend frontend n8n mailpit-demo
docker compose -f compose.yaml -f compose.demo.yaml start backend frontend n8n mailpit-demo
```

`stop` mempertahankan container dan volume. Pembaruan kode memerlukan build/recreate
service yang berubah. Restart backend sandbox mengakhiri sesi aktif.

## Menjalankan tanpa Docker

Jalur ini memakai `DATABASE_URL` dalam `.env`, bukan volume Docker.
Pilih database development sebelum migrasi:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn minori.main:create_app --factory --host 127.0.0.1 --port 8000
```

Di terminal kedua dari root repository:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

Dashboard staf lokal memakai token admin server dan tidak boleh dipublikasikan.

## Pemeriksaan

```powershell
.\.venv\Scripts\python.exe scripts/verify.py
docker compose -f compose.yaml -f compose.demo.yaml config --quiet
.\.venv\Scripts\python.exe scripts/verify_containers.py
docker compose -f compose.yaml -f compose.demo.yaml exec -T backend python -m alembic current
docker compose -f compose.yaml -f compose.demo.yaml exec -T backend python -m alembic check
```

`verify.py` memakai database sementara dan mock AI.
Jangan menjalankan `seed_database.py` atau `verify_matching.py --base-url`
pada database demo profesional; keduanya mengandalkan fixture development lama.

## Pemeliharaan

Skema dikelola Alembic. SQLite menggunakan WAL dan satu writer; jalankan satu proses
backend dengan volume lokal. Backup database aktif memakai SQLite backup API.
Lihat [reset demo](database.md#reset-demo), [AI](ai_operations.md), dan [sandbox](interactive_sandbox.md).

Dependency langsung berada di `pyproject.toml`; `requirements.lock` adalah constraints.
Gunakan lingkungan virtual dan jalankan verifikasi setelah pembaruan dependency.
