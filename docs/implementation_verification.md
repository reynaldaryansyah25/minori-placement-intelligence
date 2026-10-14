# Hasil implementasi MINORI — 14 Oktober 2026

## Penyebab dan perbaikan

Insiden reminder awal bukan kehilangan commit. Kandidat pada `DEMO-PLC-AGRI`
berstatus `inactive`, sehingga `sync_activity()` tidak membuat reminder baru;
dua pengingat lama merupakan notifikasi legacy dan pengingat yang dibatalkan.
Diagnosis transaksi, migration head, database runtime dan hash kode telah dicatat
di [laporan reminder](reminder_e2e.md). Backend menolak penjadwalan kandidat
nonaktif dengan konflik bisnis yang jelas. Tidak ada reminder yang ditambahkan
langsung melalui SQL untuk menutupi masalah tersebut.

AI sebelumnya belum aktif: konfigurasi gateway tidak mempunyai key yang valid.
Discovery model berhasil tetapi panggilan Chat Completions pertama ditolak 401;
model Gemini yang dicoba kemudian mengalami timeout. Model hasil discovery
`cx/gpt-6-sol` berhasil dipanggil dari host dan backend Docker melalui 9Router.
Key dan konfigurasi lokal hanya berada di `.env`, yang diabaikan Git.
`.env.ai-test` telah dihapus; profil uji memakai variabel `AI_TEST_*` dalam `.env`
yang sama, dengan token dan clock terpisah dari demo utama.

Dataset baru mengungkap ringkasan dashboard yang hanya menghitung 100 evaluasi
pertama. Overview kini membaca seluruh halaman dan menghitung evaluasi terbaru
per pasangan. Angka resmi menjadi 16 ELIGIBLE, 4 NEEDS_REVIEW dan 220 NOT_ELIGIBLE.
QA model nyata juga menemukan penyebutan skor 0,86 sementara UI memakai 86/100;
adapter menerima skala staf secara eksplisit dan service menolak penyebutan skor
yang tidak sesuai. Skor dan keputusan mesin matching tidak diubah AI.

Verifikasi Windows menemukan launcher virtualenv meninggalkan proses anak
Uvicorn yang mengunci log sementara. Skrip verifikasi kini menghentikan hanya
process tree yang dibuatnya sebelum membersihkan direktori sementara.
Skrip HTTP yang memakai waktu nyata juga mengosongkan clock demo yang diwarisi,
sehingga tidak mencampurkan jam nyata dengan clock tetap dari Compose pengujian.

## Fitur operasional

- FastAPI mem-parsing PDF, DOCX, XLSX, CSV dan TXT dengan batas ukuran/teks/baris,
  pemeriksaan arsip dan penolakan PDF scan tanpa teks yang memerlukan OCR.
- Ekstraksi tervalidasi, terjemahan Indonesia, review persyaratan dan bukti sumber
  memakai gateway yang sama; JLPT dan JFT-Basic tetap terpisah.
- CSV dua lowongan Jepang telah dianalisis melalui browser. Pertentangan nama
  perusahaan ditandai. Staf mengoreksi lalu menyimpan satu hasil sebagai draf;
  tidak ada publikasi otomatis.
- Penjelasan matching menggunakan fakta resmi tanpa nama/kontak kandidat.
  Browser menampilkan skor 86/100 yang tetap sama sesudah panggilan AI.
- AI menyusun email dengan blok fakta jadwal dari server. Subject/body dapat
  diedit; persetujuan eksplisit membuat snapshot dan pekerjaan yang langsung due.
  Fallback template, idempotensi, pembatalan persetujuan saat jadwal berubah,
  audit, claim lease, callback dan retry tetap memakai antrean existing.
- Tombol kirim tanpa centang persetujuan diuji di browser dan tidak membuat
  pekerjaan. Streamlit tidak membuka koneksi SMTP.

Kontrak endpoint tambahan, batas parser, RBAC dan alur staf lengkap tersedia di
[panduan operasional AI](ai_operations.md#endpoint-tambahan).

## Database yang benar-benar dipakai

Frontend utama port 8501 mengakses backend demo port 8000 dengan database
`/app/data/runtime/professional-demo.db` pada volume `professional_demo_data`.
Volume `backend_data` lama dan `n8n_data` tidak dihapus. Reset telah melalui
preview, konfirmasi, pembangunan dataset sementara, backup dan pemeriksaan
foreign key/integritas. Tidak digunakan `docker compose down -v`.

Hasil seed: 24 kandidat sintetis, 10 lowongan sintetis, 8 penempatan sah,
3 draf, 16 aktivitas, 16 reminder, 240 evaluasi matching dan 48 audit awal.
Setelah E2E dan QA: 4 draf, 3 reminder sent, 13 pending, 3 percobaan pengiriman
dan 55 audit. Draf keempat adalah hasil AI yang dikoreksi dan disimpan melalui UI.
Kontak sintetis menggunakan `.invalid` dan belum diverifikasi/disetujui untuk
pengiriman nyata.

Pada demo utama `/due` sekarang kosong karena dua reminder awal dan satu pesan
manual telah benar-benar diproses. Riwayat tidak dihapus untuk membuatnya due
kembali. Backend uji port 18100 telah disiapkan ulang pada tmpfs: **dua reminder
pending H-3/H-1 tersedia**, dengan aktivitas di masa depan dan clock tetap.
Frontend uji port 18501 memakai source frontend yang sama dengan demo utama.

Reset menolak root tambahan di luar fixture terverifikasi. Karena draf hasil QA
telah disimpan di demo utama, reset konservatif akan melindunginya dengan menolak
reset. Untuk pengulangan workflow gunakan recreate backend uji tmpfs sebagaimana
didokumentasikan, tanpa menghapus hasil review staf.

## Pengiriman yang dibuktikan

Probe HTTP/SMTP dijalankan **di container n8n**, tanpa mengubah atau menjalankan
workflow pengguna. Probe memvalidasi routing, claim, SMTP Message-ID, receipt
Mailpit, callback success dan pengulangan callback yang idempoten.

Mailpit demo port 8025 menerima tiga email:

| Pesan | Receipt Mailpit |
|---|---|
| Wawancara H-3 | `4dhrs05bvUNPPsXKJ6aATJ` |
| Pemeriksaan kesehatan H-1 | `2HE7A44pi00lNVxArLVGgx` |
| Email AI yang diedit dan disetujui staf | `3wYKUm74iITbuUIf4Ft25Q` |

Ketiganya ditujukan ke `mailpit@minori.local`. Smoke ulang pada kode akhir
mengirim tiga email tambahan ke Mailpit uji port 18035; inbox uji berisi enam
pesan dari dua putaran verifikasi. Tidak digunakan SMTP internet atau alamat
kandidat sintetis sebagai penerima efektif. Callback sent membuktikan penerimaan
server email; bukan bukti email diterima kandidat.

Uji runtime simulasi terpisah membuktikan: dua item due, aktivitas masa depan,
klaim ganda ditolak, error code ilegal ditolak, failure callback idempoten,
backoff dipatuhi, token lama ditolak, lease recovery dan complete simulated
idempoten. Jumlah pesan Mailpit tidak bertambah pada uji simulasi ini.

## Verifikasi

Pytest otomatis menggunakan mock LLM; panggilan provider nyata terpisah.
`python scripts/verify.py` pada Windows selesai dengan exit 0: 333 tes lulus,
dependency check, Ruff lint/format, Alembic upgrade/check, seed idempoten,
integritas/FK, matching dan reminder HTTP seluruhnya berhasil. Skrip reminder
juga diuji tersendiri dengan clock demo diwarisi dan exit 0 setelah perbaikan.
Verifikasi pada runner Docker Compose juga selesai dengan exit 0: **333 tes
lulus** dan seluruh 11 pemeriksaan berhasil pada Python 3.12.15. Runner uji
diperbarui dengan perbaikan harness sebelum putaran akhir; image Compose akhir
juga telah dibangun kembali. Satu AppTest mengalami timeout awal 15 detik saat
build dan tes host/container berjalan bersamaan; putaran penuh terakhir lulus
tanpa mengubah assertion atau batas timeout tersebut.

| Perintah/pemeriksaan yang dieksekusi | Hasil akhir |
|---|---|
| `python scripts/verify.py`, Windows Python 3.12.10 | Exit 0; 333 passed; 11 pemeriksaan berhasil |
| `python scripts/verify.py`, runner `backend-ai-test` melalui Compose | Exit 0; 333 passed; 11 pemeriksaan berhasil |
| `python -m ruff check .` dan `python -m ruff format --check .` | Exit 0 di host dan Docker |
| `docker compose config --quiet`, profil demo dan profil AI-test | Exit 0 pada ketiga konfigurasi |
| `python -m alembic upgrade head` / `check`, backend demo | Head `ai_message_snapshots`; tidak ada schema drift |
| `python scripts/check_database.py`, backend demo | FK aktif; integrity `ok`; 24 kandidat, 10 lowongan, 8 penempatan |
| `python scripts/verify_ai_gateway.py`, host dan Docker | Model nyata berhasil; hasil tervalidasi |
| `python scripts/verify_ai_e2e.py --mode test --output test-results/ai-e2e-final.json` | Parsing lima format, AI dan SMTP/callback berhasil |
| E2E `--mode demo` pada database demo yang dipilih | Tiga email benar-benar diterima Mailpit demo |
| Probe callback runtime pada backend AI-test | Retry/recovery/simulasi berhasil; tambahan SMTP 0 |
| Browser desktop/mobile, delapan halaman | 16 pemeriksaan selesai render; tidak ada exception/UUID/overflow halaman |

Ringkasan mesin terakhir terdapat pada `test-results/checks.json` (Windows) dan
`test-results/docker-final/checks.json` (Docker); keduanya `passed=true`.
Output penuh tersimpan dalam `test-results/final-local-verify-after-cleanup.log`
dan `test-results/final-docker-verify.log`. Artefak ini tetap lokal dan tidak
di-commit.

Browser QA mencakup seluruh delapan halaman pada viewport CSS 1440×1000 dan
390×844. Setiap halaman selesai render tanpa exception Streamlit, traceback,
UUID yang terlihat atau overflow horizontal halaman. Tabel memakai pagination;
overflow di dalam tabel tetap dapat digulir. Upload CSV, dua hasil AI, tiga tab
review, koreksi/simpan draf, penjelasan matching, edit email dan konfirmasi wajib
diperiksa langsung. Label sektor dan status pengiriman akhir juga diperiksa.

Bukti lokal:

- `test-results/ai-e2e-final.json`: E2E model nyata pada kode akhir dan SMTP uji.
- `test-results/ai-demo-e2e.json`: receipt dan callback demo utama.
- `test-results/runtime-callbacks.json`: simulasi, failure/retry dan recovery.
- `test-results/runtime-summary.json`: jumlah data, due dan penerima Mailpit.
- `test-results/browser-ai-qa.json`: 16 pemeriksaan halaman/viewport.
- `test-results/mailpit-demo-proof.jpg`: tiga email pada inbox demo.
- `test-results/ai-matching-final.jpg`: penjelasan AI dengan skor resmi.
- `test-results/reports-mobile-final.jpg`: tampilan mobile akhir.

## Perubahan manual n8n yang masih diperlukan

Workflow **MINORI - Automated Placement Reminders** tetap ada dan tidak ditimpa.
Sebelum menjalankannya, ikuti
[petunjuk node existing](ai_operations.md#perubahan-manual-workflow-n8n-existing):

1. Normalisasi Header Auth `Authorization: Bearer ...`.
2. Hapus teks literal `(Expression)` pada pemeriksaan claim dan tangani claim null.
3. Validasi dry-run serta `delivery_allowed`, mode routing dan penerima efektif.
4. Ganti penerima literal `.invalid` dengan `recipient_routing.effective_recipient`.
5. SMTP demo `mailpit-demo:1025`, tanpa TLS/auth; subject/body dari claim.
6. Callback memakai `notification.id`, `claim_token`, outcome dan provider reference
   dari pengiriman yang sama; fail memakai kode yang diizinkan.
7. Tambahkan polling terkontrol setiap 30 detik pada workflow yang sama untuk
   pekerjaan manual, dan retry HTTP callback sebelum mempertimbangkan ulang SMTP.

[Langkah uji n8n terisolasi](ai_operations.md#uji-workflow-n8n-sendiri-setelah-probe)
menjelaskan penggantian sementara URL/token/SMTP ke layanan uji yang sudah berisi
dua reminder due. Jangan mengaktifkan workflow dengan penerima literal lama.
Keberhasilan probe tidak diklaim sebagai keberhasilan eksekusi workflow pengguna.

## Batas yang tetap berlaku

OCR belum tersedia; staf tetap meninjau makna hasil AI dan mengisi informasi
penting yang kosong sebelum menyimpan draf pada mekanisme existing. Autentikasi
existing berbasis token bersama sehingga audit persetujuan mencatat `staff.admin`,
bukan identitas individual pemegang token. Produksi tetap membatasi dry-run;
pengiriman nyata membutuhkan autentikasi individual, penerima terverifikasi dan
consent serta SMTP yang sah. SMTP tidak menjamin exactly-once jika penerimaan SMTP
berhasil tetapi callback gagal; periksa receipt sebelum recovery/pengiriman ulang.

## File yang berubah

Daftar di bawah mencakup source, migrasi, Compose, dependency, tes dan dokumentasi.
Konfigurasi rahasia, database/backup, log, screenshot dan artefak pengujian
tetap lokal dan diabaikan Git.

```text
.env.example
backend/alembic/versions/ai_message_snapshots.py
backend/minori/api/ai_input_limits.py
backend/minori/api/dependencies.py
backend/minori/api/routes/ai.py
backend/minori/core/config.py
backend/minori/db/models/candidate.py
backend/minori/db/models/notification.py
backend/minori/db/models/vacancy.py
backend/minori/db/professional_demo.py
backend/minori/domain/ai.py
backend/minori/domain/entities.py
backend/minori/domain/matching_engine.py
backend/minori/domain/reminders.py
backend/minori/integrations/documents.py
backend/minori/integrations/nine_router/structured.py
backend/minori/main.py
backend/minori/schemas/ai.py
backend/minori/schemas/audit.py
backend/minori/schemas/candidate.py
backend/minori/schemas/notification.py
backend/minori/schemas/vacancy.py
backend/minori/services/ai.py
backend/minori/services/overview.py
backend/minori/services/reminders.py
backend/minori/services/vacancies.py
compose.ai-test.yaml
compose.demo.yaml
compose.yaml
Dockerfile
docs/ai_operations.md
docs/frontend.md
docs/implementation_verification.md
frontend/minori_frontend/api_client.py
frontend/minori_frontend/components/ai_email.py
frontend/minori_frontend/components/ai_vacancy.py
frontend/minori_frontend/components/feedback.py
frontend/minori_frontend/components/notification_history.py
frontend/minori_frontend/components/vacancy_form.py
frontend/minori_frontend/pages/ai_vacancy_intelligence.py
frontend/minori_frontend/pages/candidate_matching.py
frontend/minori_frontend/pages/reminder_center.py
frontend/minori_frontend/utils/constants.py
frontend/minori_frontend/utils/labels.py
pyproject.toml
README.md
requirements.lock
scripts/reset_demo.py
scripts/seed_professional_demo.py
scripts/verify_ai_e2e.py
scripts/verify_ai_gateway.py
scripts/verify_reminders.py
tests/integration/test_ai_operations.py
tests/integration/test_demo_refinement.py
tests/integration/test_frontend.py
workflows/README.md
```
