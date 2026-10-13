# Hasil verifikasi database MINORI

Dijalankan pada 13 Oktober 2026, Asia/Bangkok (UTC+07:00). Verifikasi lokal terakhir
pukul 19:15; verifikasi container pukul 19:10 dan Alembic check Linux pukul 19:12.

## Hasil nyata

- **95 tes lulus**, tanpa skip, dalam **33.94 detik** pada pemeriksaan terakhir.
- Coverage gabungan statement/branch menurut pytest-cov: **96%**.
- Ruff check lulus; Ruff format check melaporkan **87 files already formatted**.
- pip check lokal, backend Docker, dan frontend Docker: **No broken requirements found**.
- Alembic upgrade head sukses, dengan urutan foundation -> placement_database.
- Alembic check lokal dan di Linux Docker: **No new upgrade operations detected**.
- SQLite lokal dan Docker: foreign keys aktif, WAL, integrity check ok, dan tidak
  ada pelanggaran foreign key. Database berada pada head migration yang sebenarnya.
- Seed pertama menghasilkan 35 record dataset tingkat atas, beserta anak aggregate
  dan audit; keseluruhan **85 baris bisnis pada 13 tabel**. Seed berikutnya membuat
  **0 record baru**; jumlah setiap tabel tetap sama. Ini dijalankan di lokal dan Docker.
- Tes seeding membandingkan seluruh UUID di semua tabel serta menjaga penyuntingan
  kandidat. Kegagalan fixture mengembalikan seluruh insert melalui rollback.
- Tes migrasi mempertahankan data existing_records dari sebelum upgrade, mendukung
  rollback database kosong, dan menolak downgrade berisi data sebelum DROP apa pun.
- Image backend/frontend berhasil dibangun. Backend, frontend, dan n8n healthy pada
  volume yang sudah tersedia; tidak ada penghapusan volume.
- Smoke test lokal: backend HTTP 200, database ok, Streamlit health ok, frontend HTTP 200.
- Verifikasi container: frontend dan n8n dapat mengakses backend; head dan data bisnis
  terverifikasi. Layanan dibiarkan berjalan di localhost.
- Dependencies dan requirements.lock tetap menggunakan versi yang sebelumnya terpasang.

## Perintah yang dieksekusi

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m alembic upgrade head
python -m alembic check
python scripts/seed_database.py
python scripts/seed_database.py
python scripts/check_database.py
python scripts/verify.py
python scripts/smoke_test.py
docker compose config --quiet
docker compose --progress plain build
docker compose up -d --no-build --wait --wait-timeout 120
docker compose exec -T backend python scripts/seed_database.py
docker compose exec -T backend python scripts/seed_database.py
docker compose exec -T backend python -m alembic check
python scripts/verify_containers.py
```

Perintah Python lokal memakai interpreter .venv. verify.py juga membandingkan
keluaran kedua seed dan mencatat seed_idempotent=true. Perintah check_database
Docker dijalankan oleh verify_containers.py. JSON keluaran kedua seed Docker
tersimpan sebagai docker_seed_initial.json dan docker_seed_repeat.json.

## Jumlah data lokal dan Docker

| Tabel | Baris |
| --- | --- |
| candidates | 8 |
| candidate_language_tests | 9 |
| candidate_certifications | 7 |
| candidate_experiences | 7 |
| vacancies | 5 |
| vacancy_language_requirements | 8 |
| vacancy_drafts | 2 |
| matches | 4 |
| placements | 4 |
| placement_stages | 8 |
| notifications | 2 |
| notification_attempts | 2 |
| audit_logs | 19 |

## Cakupan dan batasan

Candidate dan Vacancy memiliki data bahasa, sertifikasi, pengalaman, program,
requirements, serta kuota. Match hanya menyimpan asosiasi manual pada fixture;
score tidak dihitung. Notification dan attempt adalah data sintetis, tanpa dispatcher
atau pengiriman. Jadwal medical hanya data administratif, tanpa hasil medis.

Tidak ada algoritma matching, integrasi LLM tambahan, dashboard bisnis, endpoint CRUD
bisnis, atau workflow reminder yang ditambahkan. Akses 9Router sebenarnya masih
belum diuji karena bukan cakupan pekerjaan database ini. Python Code node n8n masih
memerlukan runner yang tidak disediakan image; pemeriksaan HTTP n8n lulus.

Seed menjamin idempotensi untuk eksekusi berurutan, dan tidak menimpa baris existing.
Dua seeder konkuren dapat berkonflik pada unique key dan rollback; bukan jaminan
konkurensi. Audit dan attempt bersifat append-only pada antarmuka repository,
bukan proteksi terhadap SQL langsung. updated_at ditangani SQLAlchemy, tanpa trigger
untuk writer SQL eksternal. Tidak ada jaminan otomatis atas eligibility program,
kuota terpakai, atau transisi status bisnis.

Angka coverage bukan klaim cakupan sempurna: script Streamlit yang dieksekusi dinamis
serta subprocess tidak seluruhnya dicatat. Render frontend tetap diuji dengan AppTest.
Tidak ada kegagalan verifikasi wajib yang masih tersisa.

## File baru

```text
backend/alembic/versions/business_tables.py
backend/minori/db/inspection.py
backend/minori/db/models/__init__.py
backend/minori/db/models/audit.py
backend/minori/db/models/candidate.py
backend/minori/db/models/common.py
backend/minori/db/models/match.py
backend/minori/db/models/notification.py
backend/minori/db/models/placement.py
backend/minori/db/models/vacancy.py
backend/minori/db/seeding.py
backend/minori/domain/catalogs.py
backend/minori/domain/entities.py
backend/minori/domain/errors.py
backend/minori/domain/repositories.py
backend/minori/repositories/audit.py
backend/minori/repositories/candidate.py
backend/minori/repositories/mapping.py
backend/minori/repositories/match.py
backend/minori/repositories/notification.py
backend/minori/repositories/placement.py
backend/minori/repositories/provider.py
backend/minori/repositories/vacancy.py
backend/minori/schemas/audit.py
backend/minori/schemas/candidate.py
backend/minori/schemas/common.py
backend/minori/schemas/match.py
backend/minori/schemas/notification.py
backend/minori/schemas/placement.py
backend/minori/schemas/vacancy.py
data/dummy/placement_data.json
data/dummy/vacancies.json
docs/database.md
scripts/seed_database.py
tests/integration/test_business_models.py
tests/integration/test_business_repositories.py
tests/integration/test_seeding.py
tests/unit/test_business_schemas.py
```

## File diperbarui

```text
.dockerignore
Dockerfile
README.md
backend/alembic/env.py
backend/minori/api/dependencies.py
backend/minori/db/base.py
data/README.md
data/dummy/candidates.json
docs/architecture.md
docs/operations.md
scripts/check_database.py
scripts/verify.py
scripts/verify_containers.py
test-results/verification.md
tests/conftest.py
tests/integration/test_migrations.py
```

Struktur dan ERD lengkap tersedia di ../docs/database.md. Bukti runtime disimpan dalam
checks.json, pytest.xml, tests.log, coverage.xml, coverage/index.html, database.log,
seed_initial.log, seed_repeat.log, smoke.json, containers.json, dan kedua JSON seed Docker.
Artefak runtime tersebut diabaikan Git; ringkasan ini dapat di-commit tanpa kredensial.
