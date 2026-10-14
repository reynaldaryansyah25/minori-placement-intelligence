# MINORI Placement Intelligence

Aplikasi demonstrasi rekrutmen dan penempatan tenaga kerja ke Jepang dengan FastAPI,
Streamlit, SQLite, n8n, dan AI melalui 9Router. Data demo bersifat sintetis;
email pengujian diarahkan ke Mailpit lokal.

## Fitur

- Kandidat, kualifikasi, lowongan, dan draf lowongan.
- Kelayakan, skor berbobot, peringkat, dan keputusan staf.
- Ekstraksi dokumen, terjemahan, review persyaratan, dan penjelasan matching dengan AI.
- Penempatan, wawancara, pemeriksaan kesehatan, dokumen, orientasi, dan keberangkatan.
- Pengingat H-3/H-1, email yang disetujui staf, serta riwayat pengiriman.
- Laporan, ekspor CSV, dan sandbox publik dengan database per sesi.

Matching memakai algoritma deterministik. AI membantu peninjauan dan penyusunan teks;
publikasi, keputusan staf, dan pengiriman email tetap memerlukan persetujuan.

## Instalasi di Windows

Prasyarat: Git, Python 3.12, Docker Desktop dengan Linux containers, dan Docker Compose
2.24.4 atau lebih baru untuk [tag `!override`](https://docs.docker.com/reference/compose-file/merge/).

Jalankan di PowerShell:

```powershell
git clone https://github.com/reynaldaryansyah25/minori-placement-intelligence.git
Set-Location minori-placement-intelligence
python scripts/bootstrap.py
docker compose -f compose.yaml -f compose.demo.yaml config --quiet
docker compose -f compose.yaml -f compose.demo.yaml up -d --build --wait backend frontend n8n mailpit-demo
docker compose -f compose.yaml -f compose.demo.yaml exec -T backend python scripts/seed_professional_demo.py
```

Bootstrap membuat lingkungan Python dan satu `.env`, serta mengisi rahasia yang masih
kosong. Nilai existing dipertahankan. AI default nonaktif; ikuti [konfigurasi AI](docs/ai_operations.md).
Seed ditujukan untuk database demo profesional pada instalasi baru dan dapat diulang
tanpa menggandakan entitas demo.

| Layanan | Alamat lokal |
| --- | --- |
| Dashboard staf | http://localhost:8501 |
| Kontrak API | http://localhost:8000/docs |
| n8n | http://localhost:5678 |
| Mailpit demo | http://localhost:8025 |
| Sandbox, setelah disiapkan | http://localhost:8502 |

Buat akun owner n8n saat pertama kali membuka dashboard. Konfigurasikan workflow
sesuai [panduan n8n](docs/ai_operations.md#workflow-n8n).
Akun login publik disiapkan terpisah dan dibagikan secara privat.

## Pengujian

```powershell
.\.venv\Scripts\python.exe scripts/verify.py
.\.venv\Scripts\python.exe scripts/verify_containers.py
```

`verify.py` memeriksa dependency, Ruff, Pytest, migrasi, seed, integritas, matching,
dan reminder pada database sementara dengan mock AI.
`verify_containers.py` membutuhkan stack staf yang sudah berjalan.

## Dokumentasi

- [Konfigurasi dan operasional](docs/operations.md)
- [Arsitektur](docs/architecture.md)
- [Database dan reset demo](docs/database.md)
- [Algoritma matching](docs/matching.md)
- [Penempatan dan kontrak reminder](docs/placements_reminders.md)
- [AI, email, dan n8n](docs/ai_operations.md)
- [Sandbox interaktif](docs/interactive_sandbox.md)
- [HTTPS dengan Tailscale Funnel](docs/public_demo.md)
- [Berkas workflow](workflows/README.md)

Kredensial, database, dan hasil pengujian lokal tidak disimpan dalam Git.
Hanya frontend sandbox port 8502 yang boleh diteruskan ke akses publik.
