# Hasil verifikasi Matching Engine MINORI

Dijalankan pada 13 Oktober 2026, Asia/Bangkok (UTC+07:00). Pemeriksaan lokal
terakhir selesai pukul 20:14; smoke lokal pukul 20:16; verifikasi API dan
container final pukul 20:18. Seluruh angka di bawah berasal dari eksekusi nyata.

## Hasil nyata

- **186 tes lulus**, tanpa skip, dalam **112.99 detik** pada run final.
- Coverage gabungan statement/branch: **97%** (2097 statements, 260 branches).
- Ruff check lulus; format check: **103 files already formatted**.
- pip check lokal, image backend, dan image frontend: tidak ada dependency rusak.
- scripts/verify.py selesai dengan exit code 0, passed=true dan seed_idempotent=true.
- Alembic upgrade dan check lokal/Docker lulus; **No new upgrade operations detected**.
- Head database adalah explainable_matching, setelah foundation dan placement_database.
- SQLite lokal/Docker: integrity_check=ok, foreign_keys=1, WAL, tanpa pelanggaran FK.
- Seluruh **40 pasangan** diuji di domain, SQLite, FastAPI TestClient, API dari host,
  dan API dari dalam backend Docker. Pengulangan identik mempertahankan evaluation ID.
- Hasil fixture: **2 ELIGIBLE, 2 NEEDS_REVIEW, 36 NOT_ELIGIBLE**.
- Matching tidak mengubah empat Match manual, keputusan approved/rejected, source,
  reviewed_at, score manual lama, maupun relasi placement.
- Seed lokal/Docker dijalankan dua kali; seluruh record lama dipertahankan dan
  masing-masing pengulangan Docker menambahkan **0 record baru**.
- Image backend/frontend final berhasil dibangun dan dijalankan. Ketiga layanan
  yang sudah tersedia healthy. Volume data dipertahankan.
- API HTTP diverifikasi untuk POST evaluasi, GET history/detail, explanation,
  dan ranking. PUT/recompute atomik, input invalid, 404, konflik 409, dan error
  database 503 diverifikasi dengan integration tests.
- Smoke lokal: backend HTTP 200/database ok, Streamlit health ok/frontend HTTP 200.
- Dependencies, requirements.lock, konfigurasi 9Router, workflow n8n, dan frontend
  bisnis tidak diubah. Tidak ada penggunaan LLM untuk matching.

## Database dan hasil fixture

Migrasi baru hanya menambahkan tabel match_evaluations serta empat kolom:
candidates.preferred_prefectures, vacancies.preferred_skills,
vacancies.preferred_certifications, vacancies.language_test_max_age_months.
Tabel parent lama tidak direbuild dan data lama tidak dihapus.

| Tabel | Baris lokal dan Docker |
| --- | --- |
| candidates | 8 |
| candidate_language_tests | 9 |
| candidate_certifications | 7 |
| candidate_experiences | 7 |
| vacancies | 5 |
| vacancy_language_requirements | 8 |
| vacancy_drafts | 2 |
| matches | 4 |
| match_evaluations | 40 |
| placements | 4 |
| placement_stages | 8 |
| notifications | 2 |
| notification_attempts | 2 |
| audit_logs | 19 |

Total **125 baris bisnis pada 14 tabel**: 85 baris fixture lama dan 40 evaluasi.
Alembic version table tidak dihitung sebagai data bisnis.

Waktu acuan fixture adalah 2026-10-13T00:00:00Z. Ayu/AGRI dan Bagus/FOOD
eligible dengan score **0.8375**. Citra/CARE dan Damar/WELD needs review karena
status preparing memerlukan konfirmasi kesiapan. Eka/ENG tidak direkomendasikan
karena ENG paused; Hana inactive. Seluruh pasangan lain not eligible.
Ranking live saat pemeriksaan: AGRI hanya Ayu; FOOD hanya Bagus; CARE/WELD/ENG kosong.
Matriks seluruh pasangan tersedia di ../docs/matching.md dan matching_api.json.

## Perintah yang dieksekusi

Interpreter lokal menggunakan .venv/Scripts/python.exe. TEMP dan TMP pada run
sandbox diarahkan ke test-results/temp dalam workspace.

```sh
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/unit/test_matching_engine.py tests/integration/test_matching.py -q -x --tb=short
python -m pytest tests/integration/test_migrations.py tests/integration/test_matching.py -q -x --tb=short
python scripts/verify.py
python scripts/smoke_test.py
python scripts/verify_matching.py --base-url http://127.0.0.1:8000

docker compose config --quiet
docker compose --progress plain build backend frontend
docker compose up -d --no-build --wait --wait-timeout 120 backend frontend
docker compose exec -T backend python -m alembic upgrade head
docker compose exec -T backend python -m alembic check
docker compose exec -T backend python scripts/verify_matching.py --base-url http://127.0.0.1:8000
docker compose exec -T backend python scripts/seed_database.py
docker compose exec -T backend python scripts/seed_database.py
python scripts/verify_containers.py
```

verify.py menjalankan pip check, Ruff, Pytest dengan coverage, upgrade/check Alembic,
seed dua kali, integritas database, dan verify_matching.py lokal. Container verifier
menjalankan pemeriksaan database dan dependencies di runtime Linux, serta komunikasi
HTTP frontend/n8n ke backend yang sudah tersedia.

## Regresi dan kendala yang telah diperbaiki

- Tes awal terhalang izin direktori TEMP Windows di sandbox. TEMP/TMP workspace
  menyelesaikannya; ini bukan kegagalan instalasi dependency.
- Alembic check awal menemukan Float migration berbeda dari Double yang dipetakan
  ORM SQLAlchemy. Storage migration disamakan dan check final lulus.
- Tes downgrade lama menemukan DDL parsial sebelum migrasi berikutnya menolak data
  populated. Migrasi baru kini preflight sebelum DROP; target foundation/base/-2
  menolak tanpa mengubah tabel, head, atau data. Upgrade graph populated tetap
  mempertahankan seluruh relasi serta score manual lama.
- Pemeriksaan Ruff awal menemukan format/import; seluruh temuan telah diperbaiki.

Tidak ada kegagalan verifikasi wajib yang masih tersisa.

## Cakupan dan batas operasional

Eligibility memeriksa program, status, deadline, alternatif bahasa, riwayat tes,
sertifikasi valid, skill wajib, dan union pengalaman relevan. Scoring memakai
0.35 bahasa + 0.30 pengalaman + 0.20 tambahan + 0.15 preferensi/kesiapan; total hanya
bagi eligible. Detail normalisasi dan reason codes ada di ../docs/matching.md.

Matching menilai data pemberi kerja dan profil yang tercatat; keaslian dokumen,
keputusan imigrasi, dan alokasi kuota tidak ditentukan otomatis. Preferensi lokasi
kosong mendapat nilai netral 0.5. Riwayat as_of memakai profil saat request, bukan
rekonstruksi profil historis. History append-only melalui repository, tanpa proteksi
terhadap SQL langsung. Request konkuren dapat memerlukan retry akibat constraint
atau writer SQLite.

Recompute otomatis berada pada service/PUT API. Writer SQL eksternal perlu memanggil
POST evaluasi. GET history menandai hasil stale, dan ranking/explanation selalu memakai
data serta waktu terkini sehingga inactive/paused/closed/deadline lewat tidak menjadi
rekomendasi aktif. Tidak ada watcher database, workflow reminder, dashboard bisnis,
atau integrasi LLM tambahan. Pengaturan repository GitHub tidak diubah.

## File baru

```text
backend/alembic/versions/matching_evaluations.py
backend/minori/api/routes/matching.py
backend/minori/db/models/matching_evaluation.py
backend/minori/domain/eligibility.py
backend/minori/domain/matching.py
backend/minori/domain/matching_engine.py
backend/minori/domain/scoring.py
backend/minori/repositories/matching.py
backend/minori/schemas/matching.py
backend/minori/services/matching.py
docs/api.md
docs/matching.md
scripts/verify_matching.py
tests/integration/test_matching.py
tests/unit/test_matching_engine.py
tests/unit/test_matching_service.py
```

## File diperbarui

```text
Dockerfile
README.md
backend/minori/api/dependencies.py
backend/minori/db/models/__init__.py
backend/minori/db/models/candidate.py
backend/minori/db/models/match.py
backend/minori/db/models/vacancy.py
backend/minori/domain/entities.py
backend/minori/main.py
backend/minori/repositories/provider.py
backend/minori/schemas/candidate.py
backend/minori/schemas/match.py
backend/minori/schemas/vacancy.py
docs/architecture.md
docs/database.md
docs/operations.md
scripts/verify.py
test-results/verification.md
tests/integration/test_migrations.py
```

Total: **16 file baru dan 19 file diperbarui**. Bukti runtime diabaikan Git:
checks.json, tests.log, pytest.xml, coverage.xml/HTML, matching.log,
matching_api.json, docker_matching.json, database.log, seed logs, smoke.json,
containers.json, docker_build.log, docker_start.log, docker_migration logs,
dan kedua JSON seed Docker. Ringkasan ini tidak menyimpan credentials atau data nyata.
