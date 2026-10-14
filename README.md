# MINORI Placement Intelligence

Sistem demonstrasi rekrutmen dan penempatan tenaga kerja ke Jepang, mencakup **candidate matching yang dapat dijelaskan**, **analisis lowongan berbantuan AI**, dan **pengingat jadwal otomatis**. Dibangun dengan Python 3.12, FastAPI, Streamlit, SQLAlchemy/SQLite, n8n, dan gateway LLM 9Router.

> **Demo sintetis.** Seluruh data demonstrasi berasal dari dataset fiktif. Email pengingat masuk ke Mailpit lokal, **bukan** ke alamat kandidat nyata. Sistem ini adalah implementasi studi kasus, bukan layanan produksi.

## Coba aplikasi

- **Dashboard reviewer (HTTPS):** https://reyyy.taile4cb4f.ts.net/ — tersedia ketika laptop penyelenggara dan Tailscale Funnel aktif. Login reviewer diperlukan. Reviewer dapat mencoba operasi pada sandbox per sesi; sistem staf utama tetap lokal dan terisolasi.
- **Dashboard staf lokal:** http://localhost:8501
- **API lokal:** http://localhost:8000/docs
- **n8n lokal:** http://localhost:5678
- **Mailpit lokal:** http://localhost:8025

Akun demo disampaikan secara privat. **Jangan commit kredensial**, file `.env`, ataupun file `data/runtime/public-demo-access.txt`.

## Fitur utama

| Modul | Kemampuan |
| --- | --- |
| Overview | Ringkasan kandidat, lowongan, placement, dan aktivitas |
| Candidates & Vacancies | Kelola profil, kualifikasi, lowongan, dan persyaratan Jepang |
| AI Vacancy Intelligence | Ekstraksi berkas, terjemahan, serta tinjauan persyaratan dengan persetujuan staf |
| Candidate Matching | Evaluasi kelayakan, ranking, penjelasan skor 35% bahasa / 30% pengalaman / 20% sertifikasi / 15% preferensi |
| Placement Pipeline | Keputusan staf, wawancara, medical, dokumen, orientasi, dan jadwal |
| Reminder Center | Pengingat interview H-3 dan medical H-1; status pengiriman, retry, dan audit |
| Reports | Laporan operasional dan ekspor CSV |

**Matching dan penilaian eligibility dijalankan secara deterministik**, bukan diserahkan kepada model bahasa. LLM berperan membantu ekstraksi, terjemahan, review, dan penyusunan penjelasan. Pengiriman reminder menggunakan n8n dan Mailpit pada lingkungan demo.

## Menjalankan di Windows dengan Docker

Prasyarat: Docker Desktop, Python 3.12, dan 9Router lokal jika ingin menggunakan fitur AI.

```powershell
python scripts/bootstrap.py
# Isi .env dengan konfigurasi lokal, termasuk token internal dan pengaturan 9Router.
docker compose -f compose.yaml -f compose.demo.yaml up -d --build --wait
docker compose -f compose.yaml -f compose.demo.yaml ps
```

Konfigurasi AI di `.env` menggunakan `LLM_ENABLED`, `NINE_ROUTER_API_KEY`, `NINE_ROUTER_MODEL`, dan `NINE_ROUTER_DOCKER_BASE_URL=http://host.docker.internal:20128/v1`. Jangan menaruh kunci API dalam kode atau dokumentasi.

Frontend publik memakai login existing dan backend/database sandbox terpisah yang **tidak menerima token admin utama**. Ikuti [panduan sandbox interaktif](docs/interactive_sandbox.md) untuk Compose, reset sesi, budget, AI 9Router, dan worker email Mailpit terisolasi. Aktifkan hanya setelah mengikuti [panduan deployment publik](docs/public_demo.md) dan melakukan verifikasi login serta isolasi akses.

Workflow n8n dijalankan pada jaringan Docker internal dan menggunakan antrean backend; pengaturan node dan kredensial dijelaskan dalam [panduan AI dan n8n](docs/ai_operations.md).

## Verifikasi

```powershell
.\.venv\Scripts\python.exe scripts/verify.py
.\.venv\Scripts\python.exe scripts/verify_public_demo.py
```

Tes mencakup domain matching, API, database, workflow reminder, autentikasi, dan RBAC. Verifikasi publik terakhir yang dicatat dalam proyek pada 14 Oktober 2026 melaporkan **380 tes regresi Docker lulus** ditambah satu tes perbaikan reset UI yang dijalankan terpisah. Ruff, 11 pemeriksaan verify.py, migrasi Alembic, isolasi kredensial/database, serta browser desktop/mobile juga diverifikasi. Dua email uji diterima Mailpit sandbox. Akses HTTPS publik belum dapat diverifikasi karena Funnel saat audit belum memiliki serve config dan hostname perangkat berbeda dari PUBLIC_DEMO_HOST; konfigurasi Funnel tidak diubah otomatis.

## Dokumentasi teknis

- [Arsitektur sistem](docs/architecture.md)
- [Database dan ERD](docs/database.md)
- [Algoritma candidate matching](docs/matching.md)
- [Placement dan reminder](docs/placements_reminders.md)
- [AI, n8n, dan email demo](docs/ai_operations.md)
- [Konfigurasi dan operasional](docs/operations.md)
- [Deployment reviewer dengan Tailscale Funnel](docs/public_demo.md)
- [Workflow n8n](workflows/README.md)

Kontrak API interaktif tersedia melalui Swagger UI FastAPI pada `http://localhost:8000/docs`. Semua layanan internal tetap terikat ke localhost/jaringan Docker dan **tidak diteruskan ke Funnel**.

Lisensi, izin penggunaan data, dan adapter email produksi memerlukan keputusan terpisah sebelum pemakaian di luar demo.
