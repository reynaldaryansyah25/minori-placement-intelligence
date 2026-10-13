# Hasil verifikasi Placement Management dan Reminder Backend

Dijalankan 13 Oktober 2026, Asia/Bangkok (UTC+07:00). Pemeriksaan lokal final
selesai pukul 21:52, pemeriksaan Docker/API final pukul 21:56. Angka di bawah
berasal dari perintah yang benar-benar dieksekusi, tanpa n8n atau provider pengiriman.

## Hasil nyata

- **242 tes lulus**, tanpa skip, dalam **130.17 detik** pada full run final.
- **56 tes baru** ditambahkan; seluruh 186 tes sebelumnya tetap lulus.
- Coverage gabungan statement/branch: **94%** (2989 statements, 482 branches).
- Ruff check lulus; format check: **120 files already formatted**.
- pip check lokal, backend Docker, frontend Docker: tidak ada dependency rusak.
- scripts/verify.py exit code 0, passed=true, seed_idempotent=true.
- Alembic upgrade/check lokal dan Docker lulus; **No new upgrade operations detected**.
- Head: placement_reminders; empat migration lama/baru berurutan tanpa menghapus revisi.
- SQLite lokal/Docker: integrity_check=ok, foreign_keys=1, WAL, tanpa pelanggaran FK.
- Dua proses Python independen berebut reminder: tepat satu claim berhasil dan satu
  attempt tersimpan. Dua proses berebut kursi terakhir: tepat satu placement dibuat.
- Retry/backoff, batas attempt, lease expiry/recovery, callback invalid/identik,
  cancellation, perubahan jadwal, audit rollback, serta auth internal diuji.
- Alur end-to-end melalui **Uvicorn dan HTTP nyata** lulus di lokal dan Docker Linux.
- Backend/frontend image final berhasil dibangun; ketiga layanan lokal yang sudah
  ada healthy. Volume lama dipertahankan; tidak ada deployment eksternal.
- Smoke lokal lulus: backend/database ok, Streamlit health ok, frontend HTTP 200.
- Semua **40 hasil matching tetap sama**: 2 ELIGIBLE, 2 NEEDS_REVIEW, 36 NOT_ELIGIBLE.
  Domain eligibility.py, scoring.py, dan matching_engine.py tidak diubah.
- API matching live pada Docker diverifikasi kembali dari host.
- Worker HTTP memakai token environment berhasil mengakses backend. Pada database
  persisten tidak ada reminder managed due, sehingga due_count=0 dan processed=[].
  Simulasi pengiriman dibuktikan pada database terisolasi, bukan diklaim dari antrean kosong.

## Bukti alur end-to-end tanpa n8n

verify_reminders.py membuat database sementara berisi satu kandidat/lowongan
fiktif yang memenuhi syarat, kemudian menjalankan server FastAPI nyata dan HTTP:

1. Staf memanggil matching/decisions dan keputusan approved tersimpan.
2. Placement dibuat setelah approval, eligibility terkini, status, dan kuota diperiksa.
3. Interview dijadwalkan, dengan reminder H-3 pukul 09:00 Asia/Jakarta.
4. Reminder H-3 tersimpan pada 2026-10-13T02:00:00Z.
5. Claim pertama menghasilkan processing; claim kedua untuk ID sama mengembalikan null.
6. Callback dry-run menghasilkan simulated, sent_at=null, satu attempt simulated selesai.
7. Jadwal interview diubah; revision menjadi 2. Pengulangan PATCH identik tidak
   menambah revision. Hanya satu pengingat interview pending untuk jadwal baru;
   hasil simulated lama menjadi history dan satu notice perubahan dibuat.
8. Medical check-up menghasilkan medical_h1 dan diproses simulated, dengan satu
   attempt tambahan. Kasus catch-up tidak membutuhkan email atau WhatsApp.
9. GET placement/activities/reminders/attempts/audit berhasil dan integritas SQLite ok.

Hasil lokal dan Docker: **1 placement, 2 aktivitas, 4 notifications, 2 attempts,
13 audit logs**. Empat notifications terdiri dari interview simulated lama,
interview pending baru, notice perubahan, dan medical simulated. Tidak ada reminder
utama pending ganda. Database sementara dibersihkan setelah laporan diverifikasi;
proses server dihentikan. Tidak ada data medis, diagnosis, kontak nyata, atau token
pada laporan. Template dirender dalam respons claim yang terlindungi.

## Database persisten dan migration

Database tetap **14 tabel bisnis**, tanpa model Placement/PlacementStage duplikat.
Data persisten lokal/Docker tetap: candidates=8, vacancies=5, matches=4,
match_evaluations=40, placements=4, placement_stages=8, notifications=2 legacy,
notification_attempts=2 legacy, audit_logs=19. Bersama qualification/draft tables,
total tetap **125 baris bisnis**. Kedua seed Docker menambahkan 0 record dan counts sama.

Urutan: foundation -> placement_database -> explainable_matching -> placement_reminders.
Migration baru menambah schedule_revision pada PlacementStage; field snapshot,
mode dry-run, counters, availability, lease, processed time dan safe error pada
Notification; claim hash serta lifecycle processing pada NotificationAttempt;
dan audit entity match/placement_stage. Simulated berbeda dari sent.

Legacy notification default managed=false dan tidak diambil worker. Semua UUID,
status lama, sent_at, FK composite, dan attempt lama dipertahankan. Token claim
hanya disimpan sebagai hash. Constraint enum/rentang/lease/attempt finish serta
index queue ditambahkan. Tiga unique constraints aktivitas kini memakai nama
berbeda agar tidak hilang saat reflection/batch migration SQLite.

Migration memakai transaksi DDL SQLite eksplisit, FK dimatikan hanya pada koneksi
migrasi, foreign_key_check sebelum commit, dan FK diaktifkan kembali. Upgrade graph
populated, round-trip kosong, preservation legacy, dan downgrade refusal dengan
history baru diuji. SQL offline untuk migration reminder ditolak karena batch
rebuild membutuhkan koneksi online.

## Perintah yang dieksekusi

Interpreter lokal: .venv/Scripts/python.exe. TEMP/TMP sandbox diarahkan ke
test-results/temp. Log runtime diabaikan Git.

```sh
python -m pip install --constraint requirements.lock -e '.[frontend,dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/unit/test_reminder_policy.py tests/integration/test_placement_reminders.py -q -x --tb=short
python scripts/verify.py
python scripts/verify_reminders.py
python scripts/smoke_test.py
python scripts/verify_matching.py --base-url http://127.0.0.1:8000
python scripts/reminder_worker.py --simulate

docker compose config --quiet
docker compose --progress plain build backend frontend
docker compose run --rm --no-deps backend python scripts/verify_reminders.py
docker compose up -d --no-build --wait --wait-timeout 120 backend frontend
docker compose exec -T backend python -m alembic upgrade head
docker compose exec -T backend python -m alembic check
docker compose exec -T backend python scripts/seed_database.py
docker compose exec -T backend python scripts/seed_database.py
python scripts/verify_containers.py
```

verify.py juga menjalankan pip check, Ruff, seluruh Pytest dengan coverage,
Alembic upgrade/check, seed dua kali, check_database.py, 40 pasangan matching,
dan verify_reminders.py. Bootstrap helper berhasil menghasilkan INTERNAL_API_TOKEN
privat dalam .env tanpa mengubah key yang telah terisi atau mencetak token.

## Temuan yang diperbaiki sebelum verifikasi final

- Reflection batch SQLite sempat kehilangan unique constraint aktivitas akibat
  nama lama yang bertabrakan. Snapshot skema lengkap dengan nama unik memulihkan
  seluruh constraint; tes kode/sequence dan migration legacy sekarang lulus.
- Penambahan method list membutuhkan deferred annotations agar tidak menutupi
  built-in list pada annotation method berikutnya; sudah diperbaiki.
- Pengujian menangkap metadata audit placement yang sempat diterapkan ke aktivitas.
  Metadata dipisahkan sesuai record; full suite final 242/242 lulus.
- Temuan format/import Ruff diperbaiki. Tidak ada instalasi dependency yang gagal.

Tidak ada kegagalan verifikasi wajib yang masih tersisa.

## Batas operasional

- Approval manusia tetap tindakan eksplisit. Shared token dan actor_reference belum
  menyediakan login akun/role atau pembuktian identitas individu staf.
- Dry-run default true. Tidak ada adapter email/WhatsApp, workflow n8n baru,
  dashboard bisnis, atau deployment eksternal. Tidak ada pengiriman sungguhan.
- Tidak ada scheduler background. Pemanggil menjalankan generate/claim/recover/due
  secara berkala; script worker dapat dipakai tanpa n8n.
- SQLite mempunyai satu writer; BEGIN IMMEDIATE menegakkan eksklusivitas dan
  validasi kuota. Timeout writer dapat menghasilkan 503 untuk retry request.
- Lease menjamin satu claim aktif di database, bukan exactly-once delivery provider.
  Worker yang mengirim lalu mati sebelum callback dapat menyebabkan pengiriman
  ulang. Retry terbatas juga tidak menjamin keberhasilan. Sent adalah acknowledgement
  worker; provider idempotency/reconciliation belum diimplementasikan.
- Perubahan jadwal mencabut claim, tetapi tidak dapat menarik kembali pesan yang
  mungkin sudah dikirim provider. History attempt terminal tetap dipertahankan.
- Coverage 94% bukan klaim semua branch diuji; pemeriksaan wajib dan skenario utama lulus.

Rumus kalender, transisi, retry, templates dan autentikasi dijelaskan di
../docs/placements_reminders.md. Kontrak 20 endpoint baru tersedia di ../docs/api.md;
model/ERD di ../docs/database.md. Algoritma matching dan visibilitas GitHub tidak diubah.

## File baru

```text
backend/alembic/versions/placement_reminders.py
backend/minori/api/routes/placements.py
backend/minori/api/routes/reminders.py
backend/minori/api/security.py
backend/minori/domain/notification_templates.py
backend/minori/domain/operations.py
backend/minori/domain/reminders.py
backend/minori/repositories/notification_queue.py
backend/minori/schemas/placement_management.py
backend/minori/schemas/reminders.py
backend/minori/services/placements.py
backend/minori/services/reminders.py
docs/placements_reminders.md
scripts/reminder_worker.py
scripts/verify_reminders.py
tests/integration/test_placement_reminders.py
tests/unit/test_reminder_policy.py
```

## File diperbarui

```text
.env.example
Dockerfile
README.md
backend/alembic/env.py
backend/minori/api/dependencies.py
backend/minori/core/config.py
backend/minori/db/models/notification.py
backend/minori/db/models/placement.py
backend/minori/db/session.py
backend/minori/domain/catalogs.py
backend/minori/domain/entities.py
backend/minori/domain/errors.py
backend/minori/domain/repositories.py
backend/minori/main.py
backend/minori/repositories/placement.py
backend/minori/repositories/provider.py
backend/minori/schemas/audit.py
backend/minori/schemas/notification.py
backend/minori/schemas/placement.py
compose.yaml
docs/api.md
docs/architecture.md
docs/database.md
docs/operations.md
pyproject.toml
scripts/bootstrap.py
scripts/verify.py
test-results/verification.md
```

Total **17 file baru dan 28 diperbarui**. tzdata yang sudah ada dalam lock kini
menjadi dependency langsung agar ZoneInfo tersedia konsisten di Windows/Linux;
tidak ada teknologi baru atau dependency duplikat.

Bukti runtime: checks.json, tests.log, pytest.xml, coverage.xml/HTML, reminders.log,
matching.log, database.log, docker_reminder_http.json, reminder_matching_api.json,
reminder_worker_http.json, containers.json, smoke.json, docker build/start/migration
logs, dan dua JSON seed Docker. Semuanya diabaikan Git; laporan ini aman dibagikan
karena hanya memuat hasil dan data fiktif tanpa credentials.
