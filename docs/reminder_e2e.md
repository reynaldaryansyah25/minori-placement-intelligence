# Pengujian integrasi reminder dan n8n

## Penyebab insiden

Diagnosis 14 Oktober 2026 pada database container `/app/data/runtime/minori.db`:
`DEMO-PLC-AGRI` masih `in_progress`, tetapi kandidatnya `inactive`.
`INTERVIEW_UJI_H3_01` tersimpan sebagai interview `scheduled`. `sync_activity()`
melewati kandidat nonaktif, sehingga tidak membuat `interview_h3`. Reminder lama
adalah satu notifikasi legacy `managed=false` dan satu `medical_h1` yang sudah
`cancelled`. Keduanya memang tidak memenuhi filter `/internal/reminders/due`.
Schema sudah `placement_reminders`; hash service yang dimuat dari site-packages
cocok dengan source dalam image dan checkout saat diagnosis. Transaksi memakai
`BEGIN IMMEDIATE`, flush repository, lalu satu commit untuk aktivitas, reminder,
dan audit. Tidak ditemukan bukti kehilangan commit atau versi container lama.

Backend sekarang menolak penjadwalan kandidat nonaktif dengan HTTP 409 yang
menyebutkan bahwa reminder dinonaktifkan. Pembatalan tetap diperbolehkan. Tidak ada
perubahan status kandidat atau reminder manual pada data existing.

Compose sebelumnya juga tidak meneruskan `NOTIFICATION_DELIVERY_MODE`,
`MAILPIT_INBOX_EMAIL`, dan `DEMO_NOTIFICATION_RECIPIENT`. Ketiganya kini diteruskan.
Routing mengikuti `dry_run` yang tersimpan pada masing-masing reminder. Mode
Mailpit selalu memilih inbox Mailpit meskipun override penerima demo terisi.

## Lingkungan uji terpisah

Jalankan dari root repository. `.env` harus sudah memiliki `INTERNAL_API_TOKEN`
privat; gunakan credential Header Auth yang sama di n8n. Jangan menyalin token ke
JSON workflow atau log.

```powershell
docker compose -f compose.yaml -f compose.reminder-test.yaml build backend-reminder-test
docker compose -f compose.yaml -f compose.reminder-test.yaml up -d --wait backend-reminder-test mailpit-reminder-test
docker compose -f compose.yaml -f compose.reminder-test.yaml exec -T backend-reminder-test python scripts/verify_reminder_delivery.py
docker compose -f compose.yaml -f compose.reminder-test.yaml run --rm --no-deps backend-reminder-test python scripts/verify.py
docker compose config --quiet
```

Database layanan `backend-reminder-test` adalah `/app/data/runtime/reminder-test.db`
di tmpfs. Tidak ada mount volume database backend maupun n8n. Recreate/remove
layanan uji menghapus database uji; Mailpit uji juga memakai penyimpanan sementara.
Layanan existing tidak perlu dihentikan. Port HTTP uji adalah 18000 dan UI Mailpit
uji adalah [http://localhost:18025](http://localhost:18025).

Untuk membuktikan SMTP, aktifkan pengiriman hanya pada backend uji:

```powershell
$env:REMINDER_TEST_DRY_RUN = 'false'
docker compose -f compose.yaml -f compose.reminder-test.yaml up -d --no-deps --wait backend-reminder-test
docker compose -f compose.yaml -f compose.reminder-test.yaml exec -T backend-reminder-test python scripts/verify_reminder_delivery.py --send-mailpit
docker compose -f compose.yaml -f compose.reminder-test.yaml exec -T backend-reminder-test python scripts/prepare_reminder_demo.py --run-id N8N01
```

Skrip verifikasi membuat dua aktivitas lewat API, memastikan **dua reminder due
langsung tersedia tanpa `/generate`**, menguji claim eksklusif, failure, backoff,
retry, penolakan token lama, callback idempoten, dan history attempts. Pada mode
SMTP, skrip mengirim hanya ke `mailpit-reminder-test:1025`, lalu memeriksa Message-ID
dan penerima melalui API Mailpit sebelum callback `sent`. Tidak ada relay SMTP,
provider internet, atau pengiriman ke `intended_recipient` kandidat sintetis.

`prepare_reminder_demo.py` membuat kandidat aktif, lowongan, approval, placement,
dan dua aktivitas dengan prefix `DEMO-RMD-<run-id>`. Skrip tidak melakukan PUT,
DELETE, reset database, atau membuat reminder secara langsung. Run ID yang sudah
ada ditolak sebelum penulisan pertama; gunakan ID baru untuk pengulangan. ID dan
waktu reminder dicetak, tanpa payload kandidat atau token.

Waktu dihitung deterministik dari anchor dan zona `Asia/Jakarta`, delivery 09:00:
setelah 09:00 interview tiga hari lagi dan medical besok, keduanya pukul 14:00.
Sebelum 09:00 dipakai catch-up: interview dua hari lagi dan medical hari ini
pukul 14:00. Dengan demikian reminder sudah due dan aktivitas tetap di masa depan.
`--at 2026-10-14T10:00:00+07:00` tersedia untuk reproduksi; gunakan anchor yang
masih menghasilkan aktivitas di masa depan relatif terhadap clock backend.

## Jalankan workflow n8n yang sudah ada

Tidak perlu membuat ulang/import workflow. Untuk uji, ubah konfigurasi node yang
sudah ada:

1. Base URL dari container n8n: `http://backend-reminder-test:8000`. Dari host:
   `http://127.0.0.1:18000`. Gunakan Header Auth `Authorization: Bearer <token>`.
2. GET `/internal/reminders/due` harus memuat `interview_h3` dan `medical_h1` dari
   placement hasil `N8N01`. Untuk membatasi scope, filter `placement_id` di n8n
   setelah GET due; endpoint due menerima `limit`/`offset`, bukan `placement_id`.
3. POST `/internal/reminders/claim` dengan `{"notification_id":"<id>"}`.
   Respons `null` berarti tidak ada claim; hentikan item tersebut. Simpan
   `claim_token` untuk callback, jangan memakai token reminder sebelumnya.
4. Jika `notification.dry_run=true`, lewati SMTP dan POST
   `/internal/reminders/<id>/complete` dengan
   `{"claim_token":"<claim_token>","outcome":"simulated"}`. Alternatif satu
   langkah: POST `/internal/reminders/simulate` dengan `notification_id`.
5. Jika `dry_run=false`, kirim hanya jika `recipient_routing.delivery_allowed=true`
   dan `routing_mode=mailpit`. SMTP host `mailpit-reminder-test`, port 1025,
   tanpa autentikasi/TLS. To = `recipient_routing.effective_recipient`, yaitu
   `mailpit@minori.local`; subject/body = `message.subject`/`message.body`.
   Jangan memakai `intended_recipient`. Mailpit uji tidak dikonfigurasi sebagai relay.
6. Setelah SMTP berhasil, POST `/internal/reminders/<id>/complete` dengan
   `{"claim_token":"<claim_token>","outcome":"sent","provider_reference":"mailpit:<message-id>"}`.
   Provider reference wajib, 1–120 karakter, hanya huruf/angka/`_ . : -`;
   buang tanda `< > @` dari Message-ID SMTP atau gunakan ID dari API Mailpit.
   Kegagalan SMTP: POST `/internal/reminders/<id>/fail` dengan
   `{"claim_token":"<claim_token>","error_code":"PROVIDER_TIMEOUT"}` atau
   `PROVIDER_UNAVAILABLE`/`PROVIDER_REJECTED`. Jangan menandai gagal sebagai sent.
7. Periksa GET `/reminders/<id>/attempts` dan UI Mailpit. Failure mengembalikan
   `pending` dengan `available_at` berikutnya selama masih bisa retry. Claim
   sebelum waktu tersebut mengembalikan null. Uji Compose memakai backoff 1/2
   detik; backend biasa tetap memakai konfigurasi default 60/3600 detik.
   Setelah lease kedaluwarsa, panggil POST `/internal/reminders/recover` atau
   polling due; token lama ditolak 409. Simulasi tidak mengisi `sent_at`.

Mode delivery disimpan ketika reminder dibuat. Mengubah environment tidak
mengubah reminder existing: siapkan run ID baru setelah berpindah mode. Skrip
verifikasi otomatis mengonsumsi reminder miliknya; jalankan `prepare_reminder_demo.py`
sesudahnya supaya n8n mendapat dua item pending baru. Jalankan workflow sebelum
medical dimulai; jika terlambat, siapkan run baru.

## Memakai backend demo biasa

Jika diperlukan, bangun ulang backend sesudah perubahan kode/settings:

```powershell
docker compose up -d --build --no-deps backend
docker compose exec -T backend python scripts/diagnose_reminders.py --placement-reference DEMO-PLC-AGRI
docker compose exec -T backend python scripts/prepare_reminder_demo.py --run-id DEMO01
```

Perintah terakhir menambah skenario ber-prefix baru melalui HTTP pada database
demo, tanpa menyentuh `DEMO-PLC-AGRI`. Jangan mengaktifkan ulang kandidat existing
hanya untuk mendapatkan reminder. Gunakan konfigurasi default `NOTIFICATION_DRY_RUN=true`
untuk simulasi. Pengujian SMTP yang terdokumentasi memakai layanan uji terpisah.
Jika menggunakan Mailpit existing, pastikan hostname SMTP n8n memang dapat
diresolusikan di jaringan Compose dan tidak ada konfigurasi relay.

Diagnostik membuka SQLite dengan `mode=ro` dan hanya mencetak status, waktu,
schema, lokasi database, serta hash source. Database host `data/runtime/minori.db`
berbeda dari named volume `/app/data/runtime/minori.db` dalam Docker; seeding
lokal tidak otomatis menyiapkan database container. Tidak ada bind mount source
pada backend, sehingga perubahan kode perlu rebuild/recreate, bukan sekadar restart.

Untuk membersihkan **hanya layanan uji**:

```powershell
docker compose -f compose.yaml -f compose.reminder-test.yaml rm -sf backend-reminder-test mailpit-reminder-test
Remove-Item Env:REMINDER_TEST_DRY_RUN -ErrorAction SilentlyContinue
```

Jangan memakai `down -v` pada project demo karena dapat menghapus volume existing.

## Hasil verifikasi 14 Oktober 2026

| Perintah/pemeriksaan | Hasil |
| --- | --- |
| `python -m pytest tests/unit/test_reminder_demo.py tests/unit/test_reminder_policy.py tests/integration/test_placement_reminders.py -q --basetemp=test-results/reminder-focused-temp --tb=short` | 68 lulus pada tahap awal; satu regression test tambahan tercakup dalam suite penuh berikutnya |
| `docker compose -f compose.yaml -f compose.reminder-test.yaml run --rm --no-deps backend-reminder-test python scripts/verify.py` | Exit 0; 280 tes lulus, pip check, Ruff, format, Alembic upgrade/check, seed dua kali, integritas database, matching, dan HTTP reminder lulus |
| `... exec -T backend-reminder-test python scripts/verify_reminder_delivery.py` | Dua due; simulasi, failure, retry, callback idempoten, token lama dan attempt history lulus |
| `... exec -T backend-reminder-test python scripts/verify_reminder_delivery.py --send-mailpit` | Dua email tertangkap di inbox lokal; status sent, retry dan callback lulus |
| Probe HTTP dari proses Node di container n8n | Dua due: interview_h3 dan medical_h1; routing Mailpit benar; API Mailpit memuat dua email |
| Probe koneksi SMTP dari container n8n | Greeting SMTP 220 diterima dari mailpit-reminder-test:1025 |
| `docker compose config --quiet` dan versi gabungan file uji | Keduanya exit 0 setelah verifikasi Python |
| `docker compose up -d --build --no-deps --wait backend` dan diagnostik sesudahnya | Backend healthy, source terpasang sesuai; tiga aktivitas dan dua reminder existing pada DEMO-PLC-AGRI tetap sama |
| POST jadwal interview pada placement existing berkandidat inactive setelah rebuild | HTTP 409 dengan detail inactive candidate; aktivitas existing tetap sama |

Percobaan Pytest lokal pertama gagal pada pembuatan direktori temp sandbox Windows,
sebelum tes berjalan; pengulangan memakai basetemp di workspace lulus. Percobaan
verifikasi Docker pertama menemukan izin cache Ruff untuk pengguna non-root;
image uji diperbaiki dan verifikasi penuh diulang sampai exit 0. Provider LLM tidak
dipanggil. Workflow n8n belum dieksekusi/diedit; akses dari container n8n dan seluruh
kontrak backend/SMTP diverifikasi secara terpisah.

Skenario `DEMO-RMD-N8N01-PLC` ditinggalkan pending pada backend uji port 18000:
interview 16 Oktober 2026 14:00 WIB dan medical 14 Oktober 2026 14:00 WIB.
Kedua reminder due sejak 13 Oktober 2026 09:00 WIB, dengan catch-up saat pembuatan.
Backend uji menggunakan dry_run=false dan routing Mailpit; backend demo biasa
tetap dry_run=true. Skenario uji hilang saat layanan uji dibuat ulang; gunakan
skrip persiapan dengan run ID baru jika diperlukan.
