# AI dan email pengingat

Semua fitur AI memakai gateway 9Router yang sama. Sumber dianggap data tak tepercaya;
model tidak mempunyai alat untuk menulis database/mengirim email.
Output harus lulus Pydantic dan pemeriksaan fakta.

## Konfigurasi AI

Isi pada satu `.env` dengan key dan model ID dari gateway lokal:

```dotenv
LLM_ENABLED=true
NINE_ROUTER_BASE_URL=http://127.0.0.1:20128/v1
NINE_ROUTER_DOCKER_BASE_URL=http://host.docker.internal:20128/v1
NINE_ROUTER_API_KEY=<key gateway>
NINE_ROUTER_MODEL=<ID model utama>
NINE_ROUTER_FALLBACK_MODELS=<ID cadangan 1>,<ID cadangan 2>,<ID cadangan 3>
LLM_TIMEOUT_SECONDS=90
LLM_ATTEMPT_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=1
```

Ganti placeholder `<...>`; cadangan boleh kosong dan maksimal tiga ID berbeda.
Status provider terhubung/discovery belum membuktikan Chat Completions berhasil.

```powershell
.\.venv\Scripts\python.exe scripts/verify_ai_gateway.py --discover
.\.venv\Scripts\python.exe scripts/verify_ai_gateway.py
```

Smoke test memakai sumber Jepang sintetis dan provider nyata.
Sesudah perubahan konfigurasi, recreate backend yang dipakai. Contoh sandbox:

```powershell
docker compose -f compose.public-demo.yaml up -d --no-deps --force-recreate --wait backend-sandbox
docker compose -f compose.public-demo.yaml exec -T backend-sandbox python scripts/verify_ai_gateway.py
```

Adapter mengirim `stream=false`. Timeout/koneksi gagal atau HTTP
408/429/500/502/503/504 mencoba model berikutnya. Dengan fallback, setiap model dicoba
sekali, maksimal empat percobaan; retry SDK dimatikan.
Timeout transport per percobaan memakai `LLM_ATTEMPT_TIMEOUT_SECONDS`;
tidak memulai percobaan baru setelah budget `LLM_TIMEOUT_SECONDS` habis.
HTTP 400/401/403/422 dan output tidak valid tidak dilewati dengan fallback.
Tanpa cadangan, timeout/retry SDK existing berlaku.

## Penggunaan dan batas dokumen

Analisis lowongan: upload/tempel → analisis → ekstraksi, terjemahan, review →
koreksi → simpan draf. Publikasi adalah tindakan staf.
Informasi tanpa bukti ditandai Perlu Konfirmasi; JLPT/JFT-Basic tidak disamakan.

Parser FastAPI mendukung PDF, DOCX, XLSX, CSV, TXT.
Batas staf 5 MB, sandbox 2 MB; PDF 30 halaman; Excel satu lembar;
tabel 100 baris/30 kolom; teks 12.000 karakter per lowongan; batch lima lowongan.
PDF scan memerlukan OCR. Makro, formula, referensi eksternal, dan arsip berbahaya tidak dieksekusi.

Matching: pilih hasil resmi → Jelaskan dengan AI.
Email: susun AI/template → edit → konfirmasi → kirim.
Backend memasukkan fakta resmi kandidat, kegiatan, waktu WIB, dan lokasi.
AI tidak mengubah hasil matching atau mengarang fakta jadwal.

## Endpoint

| Endpoint | Penggunaan |
| --- | --- |
| `GET /ai/status` | Konfigurasi, bukan tes koneksi |
| `POST /ai/documents/preview` | Parsing dan pratinjau |
| `POST /ai/vacancies/analyze` | Ekstraksi, terjemahan, review |
| `POST /ai/vacancies/batch` | Maksimal lima teks |
| `POST /ai/matching/explanation` | Narasi hasil resmi |
| `POST /placements/{placement_id}/activities/{activity_id}/email/prepare` | Siapkan email jadwal |
| `GET /reminders/{notification_id}/email/template` | Template tanpa AI |
| `POST /reminders/{notification_id}/email/draft` | Draf AI |
| `POST /reminders/{notification_id}/email/approve` | Snapshot/queue setelah `confirmed=true` |

AI/tindakan tulis memerlukan staf atau sesi sandbox berwenang.
Kontrak body lengkap tersedia pada Swagger UI.

## Workflow n8n

Pertahankan workflow reminder existing. Simpan token sebagai credential
**HTTP Header Auth**: nama `Authorization`, nilai `Bearer <token backend>`.
URL utama dalam Compose: `http://backend:8000`.

1. **Verifikasi Auth:** `GET /auth/me`.
2. **Ambil Reminder Jatuh Tempo:** `GET /internal/reminders/due?limit=50`;
   proses array sebagai item per pengingat.
3. **Klaim Pengingat:** `POST /internal/reminders/claim`;
   body `notification_id` dengan expression `{{ $json.id }}`.
4. **Periksa Hasil Klaim:** lanjut hanya jika `notification.id` dan
   `claim_token` tersedia; hasil null berhenti.
5. **Periksa Mode Pengiriman:** dry-run ke callback simulated tanpa SMTP.
   Cabang SMTP memeriksa `delivery_allowed=true` dan mode mailpit.
6. **Send an Email:** host `mailpit-demo`, port 1025, tanpa TLS/auth untuk sink lokal.
   From `pengingat@minori.local`; To dari `recipient_routing.effective_recipient`;
   subject/body dari `message.subject/body`.
7. **Catat Email Terkirim:** `POST /internal/reminders/{notification.id}/complete`,
   token node claim yang sama, `outcome=sent`, referensi SMTP valid.
8. **Catat Email Gagal:** endpoint fail dengan token claim yang sama dan kode
   `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, atau `PROVIDER_REJECTED`.
9. **Catat Hasil Simulasi:** endpoint complete, `outcome=simulated`,
   tanpa provider reference.
10. Gunakan polling terkontrol, misalnya 30 detik, untuk memproses pesan manual segera.

Gunakan expression editor, bukan teks literal. Callback mengambil data melalui
node Klaim Pengingat, misalnya `$('Klaim Pengingat').item.json.claim_token`.
Gunakan referensi provider yang memenuhi kontrak API; jangan membuat nilai palsu.
Jika SMTP sukses tetapi callback gagal, retry callback dengan body identik terlebih dahulu.

URL callback pada expression editor:

```javascript
{{ 'http://backend:8000/internal/reminders/' + $('Klaim Pengingat').item.json.notification.id + '/complete' }}
```

Untuk kegagalan ganti akhiran menjadi `/fail`. `provider_reference` maksimal
120 karakter dan hanya menerima huruf, angka, `_`, `.`, `:`, `-`.
Jika node SMTP menyediakan `messageId`, normalisasikan nilai itu sebelum callback:

```javascript
{{ $json.messageId.replace(/[^A-Za-z0-9_.:-]/g, '').slice(0,120) }}
```

Jika referensi tidak tersedia atau hasil normalisasi kosong, periksa hasil SMTP;
jangan mencatat sukses dengan referensi buatan.

Sandbox memakai worker terisolasi dan Mailpit tersendiri, bukan workflow utama.

## Pengujian end-to-end

Tes otomatis: `scripts/verify.py`, menggunakan mock AI.
Untuk smoke provider/SMTP lokal, isi `AI_TEST_API_TOKEN` dengan token uji acak
minimal 32 karakter, berbeda dari token utama, pada `.env` yang sama.

```dotenv
AI_TEST_DRY_RUN=false
AI_TEST_CLOCK_AT=2026-10-14T05:00:00Z
```

Clock di atas adalah waktu fixture terkontrol, bukan jam Windows.

```powershell
docker compose -f compose.ai-test.yaml config --quiet
docker compose -f compose.ai-test.yaml up -d --build --wait backend-ai-test frontend-ai-test mailpit-ai-test
.\.venv\Scripts\python.exe scripts/verify_ai_e2e.py --mode test
```

Profil memakai tmpfs, port API 18100, frontend 18501, Mailpit 18035.
Probe membutuhkan container n8n utama yang berjalan; ia tidak mengubah workflow
pengguna, tetapi memproses queue dan mengirim pesan ke Mailpit uji.

Sebelum menguji node workflow sendiri, kembalikan pekerjaan awal ke pending:

```powershell
docker compose -f compose.ai-test.yaml up -d --no-deps --force-recreate --wait backend-ai-test
```

Gunakan workflow uji tersendiri atau salinan workflow yang tidak aktif:
URL `http://backend-ai-test:8000`, credential uji, SMTP `mailpit-ai-test:1025`.
Jalankan manual, periksa Mailpit `http://localhost:18035`, status, dan riwayat.
Eksekusi ulang tidak boleh mengirim pekerjaan sent. Workflow/credentials utama
tetap dipertahankan.

Simulasi: set `AI_TEST_DRY_RUN=true`, recreate backend uji, gunakan callback
simulated tanpa SMTP melalui Manual Trigger workflow uji. Jangan memakai probe
`verify_ai_e2e.py` pada mode dry-run; probe tersebut memerlukan pengiriman Mailpit.
Failure/retry/deduplikasi/callback diuji oleh Pytest.

Pengiriman internet/WhatsApp tidak diaktifkan. Produksi memerlukan adapter, SMTP sah,
verifikasi/persetujuan penerima, dan otorisasi staf tersendiri.
