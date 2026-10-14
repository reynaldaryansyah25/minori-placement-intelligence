# Operasional AI, demo profesional, dan email MINORI

Semua fitur memakai adapter 9Router yang sama. AI menghasilkan bahan peninjauan;
mesin matching tetap menghitung eligibility, skor dan ranking. Publikasi lowongan
dan persetujuan pesan memerlukan staf berwenang. AI tidak mempunyai alat untuk
menulis database atau mengirim email.

## Konfigurasi tunggal

Seluruh profil membaca `.env`, yang diabaikan Git. Tidak diperlukan `.env.ai-test`.
Jangan membagikan API key atau token melalui screenshot/log.

```dotenv
LLM_ENABLED=true
NINE_ROUTER_BASE_URL=http://localhost:20128/v1
NINE_ROUTER_DOCKER_BASE_URL=http://host.docker.internal:20128/v1
NINE_ROUTER_API_KEY=<key gateway lokal>
NINE_ROUTER_MODEL=<ID hasil discovery yang berhasil diuji>
LLM_TIMEOUT_SECONDS=90
LLM_MAX_RETRIES=1
INTERNAL_API_TOKEN=<token existing, minimal 32 karakter>
REVIEWER_API_TOKEN=<token reviewer, minimal 16 karakter>
N8N_ENCRYPTION_KEY=<nilai existing, jangan diganti>
AI_TEST_API_TOKEN=<token acak khusus lingkungan uji>
AI_TEST_DRY_RUN=false
AI_TEST_CLOCK_AT=2026-10-14T05:00:00Z
DEMO_CLOCK_AT=
```

Pada verifikasi lokal, discovery `/v1/models` dan Chat Completions berhasil dengan
`cx/gpt-6-sol`. ID tersebut merupakan hasil discovery dan smoke test, bukan default
yang ditanam dalam adapter. Model Gemini yang diuji terlebih dahulu mengalami
timeout. Discovery saja tidak membuktikan sebuah model dapat dipanggil.

```powershell
python scripts/verify_ai_gateway.py --discover
python scripts/verify_ai_gateway.py
```

Input smoke merupakan lowongan Jepang fiktif. Script memvalidasi JSON, bukti
sumber, terjemahan, dan requirement review. Jangan menjalankan smoke provider
sebagai bagian dari tes otomatis.

## Database demo profesional

Profil `compose.demo.yaml` memilih volume `professional_demo_data` dan file
`professional-demo.db`. Volume `backend_data` lama tetap tersedia. Volume dan
workflow n8n tetap digunakan tanpa dihapus. Jangan memakai `down -v`.

```powershell
docker compose -f compose.yaml -f compose.demo.yaml build backend frontend
docker compose -f compose.yaml -f compose.demo.yaml up -d --no-deps --wait backend mailpit-demo
docker compose -f compose.yaml -f compose.demo.yaml exec -T backend python scripts/reset_demo.py
```

Perintah terakhir hanya preview: database yang dipilih, jumlah baris dan fingerprint.
Setelah memeriksa preview, konfirmasi reset:

```powershell
docker compose -f compose.yaml -f compose.demo.yaml exec -T backend python scripts/reset_demo.py --confirm RESET-MINORI-DEMO
docker compose -f compose.yaml -f compose.demo.yaml up -d --no-deps --wait frontend
docker compose -f compose.yaml -f compose.demo.yaml up -d --no-deps n8n
```

Reset hanya menerima environment `demo`, nama file khusus, migration head yang
benar dan identitas fixture profesional yang terverifikasi. Database dengan tabel
asing, data non-demo, kontak non-sintetis atau entitas tambahan yang belum
terverifikasi ditolak. Berkas backup dibuat di `demo-backups/` sebelum penggantian.
Dataset pengganti dibangun, diperiksa dan di-seed ulang di database sementara;
penggantian dilakukan dalam satu transaksi dengan foreign keys tetap aktif.
Perubahan database selama persiapan membatalkan reset.

Dataset memuat 24 kandidat sintetis, 10 lowongan, 8 penempatan aktif, 3 draf,
16 aktivitas dan 240 evaluasi matching sebenarnya. Persetujuan dan penempatan
dibuat melalui layanan bisnis. Tidak ada skor atau email terkirim yang dipalsukan.
Kontak kandidat memakai `.invalid`, belum diverifikasi dan belum menyetujui
pengiriman nyata. Dua reminder dapat didemokan segera, dengan aktivitas tetap
berada di masa depan.

Untuk demo dengan clock tetap, isi `DEMO_CLOCK_AT` dengan timestamp berzona,
jalankan Compose dengan profil demo, lalu reset dengan anchor yang sama. Contoh:
`2026-10-14T05:00:00Z` berarti 14 Oktober 2026, pukul 12.00 WIB. Clock hanya
diizinkan untuk `demo/test`; jam Windows tidak berubah. Pengujian dapat memajukan
clock melalui endpoint internal, maksimal tujuh hari setiap permintaan, tanpa
bergerak mundur. Setelah demonstrasi, kosongkan clock dan restart profil demo.

## Alur staf

**Analisis Lowongan:** tempel teks atau upload dokumen, pratinjau/pilih baris,
pilih **Analisis dengan AI**, tinjau tiga tab, koreksi form, konfirmasi pemeriksaan
dan simpan draf. Untuk batch, tinjau serta simpan setiap hasil sebagai draf
terpisah. Publikasi tetap memakai tindakan staf existing. Bukti, terjemahan dan
review disimpan sebagai metadata draf dan dipertahankan saat publikasi.

**Pencocokan Kandidat:** pilih detail hasil resmi, lalu **Jelaskan dengan AI**.
Nama, kontak dan identitas database kandidat tidak dikirim ke model. Output
berisi ringkasan, keunggulan, syarat yang belum dipenuhi, verifikasi dan langkah
administratif. Penjelasan menjadi kedaluwarsa saat input/hasil resmi berubah.

**Pusat Pengingat:** pilih reminder, **Susun Email dengan AI** atau **Gunakan
template**, edit subject/body, centang persetujuan, kemudian **Kirim Pengingat
Sekarang**. Jadwal WIB, nama dan lokasi resmi tetap wajib tercantum. AI hanya
menulis bahasa pengantar/penutup yang dibatasi; server memasukkan blok fakta.
Tidak ada instruksi persiapan, biaya atau nasihat medis yang ditebak model.

Persetujuan menyimpan snapshot immutable, actor autentikasi, fingerprint fakta,
revisi jadwal dan kunci idempotensi. Pekerjaan langsung tersedia pada `/due`.
Double click tidak membuat pekerjaan kedua. Revisi jadwal membatalkan pesan lama
dan mempertahankan snapshot untuk audit. Perubahan kandidat/tujuan sebelum claim
juga membatalkan persetujuan. Retry memakai snapshot yang sama.

Actor persetujuan berasal dari autentikasi backend, bukan nilai yang dapat
dipalsukan form. Autentikasi existing masih berbasis token bersama dan mencatat
`staff.admin`; identitas per orang memerlukan autentikasi staf individual pada
jalur produksi. Token bersama tidak membuktikan staf mana yang memegangnya.

Status **Email disiapkan** berada pada pratinjau; **Menunggu pengiriman** berarti
antrean sudah dibuat. **Terkirim ke server email** hanya berarti SMTP sukses,
bukan bukti penerimaan kandidat. **Gagal** dan riwayat percobaan tersedia terpisah.

## Batas dokumen dan hasil AI

Parser berada di FastAPI, bukan Streamlit. PDF/DOCX/XLSX/CSV/TXT maksimal 5 MB;
PDF maksimal 30 halaman; XLSX satu lembar; tabel maksimal 100 baris dan 30 kolom,
4.000 karakter per sel. Setiap lowongan maksimal 12.000 karakter dan satu batch
maksimal lima lowongan. Pilih bagian dokumen yang lebih kecil jika batas terlampaui.

Parser tidak menjalankan formula, makro, objek tertanam atau referensi eksternal.
Zip dengan traversal, enkripsi, deklarasi entitas atau ukuran dekompresi berlebihan
ditolak. PDF scan tanpa teks memerlukan OCR; OCR belum tersedia pada tugas ini.
Sumber diperlakukan sebagai data tak tepercaya dan tidak boleh mengganti instruksi
sistem model. JSON yang salah, quote yang tidak ada dalam sumber, atau tingkat
JLPT/JFT-Basic yang tidak didukung sumber ditolak. Informasi tanpa bukti dihapus
dan ditandai **Perlu Konfirmasi**. Validasi ini membantu review; staf tetap harus
memeriksa makna terjemahan terhadap dokumen asli.

## Endpoint tambahan

| Endpoint | Akses / tujuan |
|---|---|
| `GET /ai/status` | Baca; konfigurasi AI, bukan jaminan koneksi provider |
| `POST /ai/documents/preview` | Staf; multipart `file`, parsing dan pratinjau |
| `POST /ai/vacancies/analyze` | Staf; `text`, ekstraksi + terjemahan + review |
| `POST /ai/vacancies/batch` | Staf; `texts`, maksimal lima, tanpa publikasi |
| `POST /ai/matching/explanation` | Staf; pasangan kandidat/lowongan, hanya baca fakta |
| `GET /reminders/{id}/email/template` | Staf; fallback tanpa provider |
| `POST /reminders/{id}/email/draft` | Staf; AI menyiapkan pratinjau |
| `POST /reminders/{id}/email/approve` | Staf; `subject`, `body`, `facts_fingerprint`, `idempotency_key`, `confirmed=true` |
| `POST /internal/demo/clock` | Token internal; hanya demo/test, `now` berzona |

Due, claim, complete, fail, recovery dan attempts existing tetap kompatibel.
Callback selalu menggunakan `notification.id` dan `claim_token` dari claim yang
sama. Token claim tidak disimpan plaintext. Snapshot pesan tersedia sebagai
`message.subject` dan `message.body` pada response claim.

## Perubahan manual workflow n8n existing

Workflow **MINORI - Automated Placement Reminders** tidak diimpor ulang atau
ditimpa. Audit menunjukkan recipient literal sintetis dan teks `(Expression)`
pada kondisi claim perlu dikoreksi sebelum workflow dijalankan.

1. Kredensial HTTP Header Auth: nama `Authorization` tanpa spasi; nilai
   `Bearer <INTERNAL_API_TOKEN>` tanpa quote atau tambahan teks. Gunakan kredensial
   yang sama pada semua node HTTP internal. `/auth/me` memverifikasi autentikasi.
2. **Ambil Reminder Jatuh Tempo:** `GET http://backend:8000/internal/reminders/due?limit=50`.
   Pastikan output array diproses sebagai item per reminder. Jangan memakai UUID tetap.
3. **Klaim Pengingat:** POST `/internal/reminders/claim`, body JSON
   `{"notification_id": "={{ $json.id }}"}` melalui expression editor n8n.
4. **Periksa Hasil Klaim:** boolean expression
   `={{ !!$json.notification?.id && typeof $json.claim_token === 'string' && $json.claim_token.length >= 32 }}`
   harus true. Hapus teks literal `(Expression)`. Cabang false berhenti.
5. **Periksa Mode Pengiriman:** periksa boolean `notification.dry_run`.
   Dry-run langsung menuju **Catat Hasil Simulasi**, tanpa SMTP.
6. Pada cabang non-dry-run, tambahkan pemeriksaan tujuan sebelum SMTP:
   `recipient_routing.delivery_allowed === true`, `routing_mode === 'mailpit'`,
   dan `effective_recipient` tersedia. Jika gagal, panggil fail dengan
   `PROVIDER_REJECTED`, bukan complete simulated.
7. **Send an Email:** SMTP host `mailpit-demo`, port `1025`, SSL/TLS dan autentikasi
   dimatikan untuk sink lokal. From `pengingat@minori.local`; To
   `={{ $json.recipient_routing.effective_recipient }}`; subject
   `={{ $json.message.subject }}`; body text `={{ $json.message.body }}`.
   Hapus penerima literal `.invalid`. Tetap gunakan Continue using error output.
8. **Catat Email Terkirim:** URL
   `={{ 'http://backend:8000/internal/reminders/' + $('Klaim Pengingat').item.json.notification.id + '/complete' }}`.
   Body: token dari `$('Klaim Pengingat').item.json.claim_token`, outcome `sent`,
   provider reference dari Message-ID SMTP yang benar, misalnya expression existing
   `={{ $json.messageId.replace(/[^A-Za-z0-9_.:-]/g, '').slice(0,120) }}`.
   Jangan membuat provider reference palsu jika SMTP tidak memberikan hasil.
9. **Catat Email Gagal:** URL `/internal/reminders/{id}/fail`, token dari claim
   yang sama; kode `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE` atau `PROVIDER_REJECTED`
   sesuai kegagalan. Jangan mengirim raw error sebagai kode.
10. **Catat Hasil Simulasi:** `/complete`, token dari claim, outcome `simulated`,
    tanpa provider reference.
11. Tambahkan Schedule Trigger pada workflow yang sama dengan interval 30 detik
    dan batas batch di atas. Manual trigger existing tetap tersedia. Ini membuat
    pesan staf diproses segera dan tidak menunggu cron 09.00. Tidak diperlukan
    webhook publik. Recovery dapat dipanggil dengan token internal saat diperlukan.

Aktifkan retry HTTP pada callback dengan body/token/reference yang sama. Jika
SMTP sukses tetapi callback gagal, retry callback terlebih dahulu. Jangan
mengulang SMTP hanya karena callback timeout. SMTP tidak menjamin exactly-once:
lease yang kedaluwarsa setelah penerimaan SMTP dapat menyebabkan pengiriman
ulang. Periksa Message-ID di Mailpit/riwayat sebelum recovery manual. Idempotency
di backend mencegah claim/callback/persetujuan ganda, tetapi tidak menghapus
ketidakpastian antara dua sistem setelah koneksi terputus.

## Pengujian terisolasi dan bukti

```powershell
python scripts/verify.py
docker compose config --quiet
docker compose -f compose.ai-test.yaml config --quiet
docker compose -f compose.ai-test.yaml up -d --build --wait
docker compose -f compose.ai-test.yaml exec -T backend-ai-test python scripts/verify_ai_gateway.py
python scripts/verify_ai_e2e.py --mode test
```

Profil uji memakai tmpfs dan clock tetap, tanpa mount database backend/n8n lama.
Frontend uji: `http://localhost:18501`; backend: `http://localhost:18100`;
Mailpit: `http://localhost:18035`. Pengujian provider terpisah dari Pytest:
tes otomatis menggunakan mock LLM dan tidak memanggil gateway nyata.

Script E2E melakukan HTTP parsing lima format, panggilan AI nyata, pemeriksaan
score immutable, edit/persetujuan/idempotensi email, lalu menjalankan probe kontrak
HTTP dan SMTP di container n8n. Probe tersebut tidak mengubah atau mengeksekusi
workflow pengguna yang masih memerlukan koreksi node di atas. Receipt Mailpit
dan callback success benar-benar diverifikasi. Hasil disimpan pada
`test-results/ai-e2e.json`, yang diabaikan Git. Semua SMTP probe memakai hostname
Mailpit Compose yang dibatasi dan alamat `mailpit@minori.local`, tanpa relay internet.

### Uji workflow n8n sendiri setelah probe

Probe mengonsumsi dua reminder awal serta satu persetujuan manual. Karena itu
`/due` pada demo yang sudah diuji dapat kosong: lihat riwayat dan Mailpit sebelum
menganggap sinkronisasi gagal. Jangan mengirim ulang notifikasi berstatus `sent`.

Untuk mengulang workflow tanpa menghapus hasil peninjauan pada database demo,
siapkan ulang **hanya backend uji tmpfs**:

```powershell
docker compose -f compose.ai-test.yaml up -d --no-deps --force-recreate --wait backend-ai-test
```

Ini mengembalikan dataset uji dengan dua reminder `pending` yang sudah jatuh tempo
pada `AI_TEST_CLOCK_AT`; kedua kegiatan tetap di masa depan. Pada workflow existing,
ubah sementara seluruh URL backend menjadi `http://backend-ai-test:8000`, pilih
credential Header Auth uji yang membaca nilai `AI_TEST_API_TOKEN` dari `.env`, dan
gunakan SMTP `mailpit-ai-test:1025`. Jangan menimpa credential demo existing.
Lakukan koreksi node di atas, lalu jalankan Manual Trigger. Pastikan H-3/H-1 masuk
`http://localhost:18035`, status menjadi `sent`, dan eksekusi kedua tidak mengirim
ulang. Gunakan reminder masa depan lainnya untuk menguji persetujuan manual dari
frontend `http://localhost:18501`.

Untuk simulasi, set `AI_TEST_DRY_RUN=true` dalam `.env` untuk **layanan uji**,
recreate backend uji dan jalankan workflow; callback harus `outcome=simulated`
tanpa penambahan pesan di Mailpit. Untuk failure/retry, klaim satu item uji, panggil
`fail` dengan `PROVIDER_UNAVAILABLE`, majukan clock internal dua detik, dan klaim
ulang memakai token baru; token lama harus ditolak. Batas retry dan recovery juga
diuji Pytest tanpa SMTP internet. Kembalikan URL `backend:8000`, credential demo,
dan SMTP `mailpit-demo:1025` setelah pengujian. Jangan aktifkan polling selama
konfigurasi tujuan dan mode belum benar.

Untuk memverifikasi profil demo yang telah di-reset, gunakan
`python scripts/verify_ai_e2e.py --mode demo --output test-results/ai-demo-e2e.json`.
Perintah ini membuat satu persetujuan manual pada reminder masa depan dan benar-benar
mengirim reminder jatuh tempo ke Mailpit demo. Jalankan hanya saat pengiriman uji
tersebut memang diinginkan. Untuk uji ulang, pilih data demo terverifikasi dan reset
dengan prosedur preview/backup; jangan menyunting tabel notifikasi secara manual.

## Pengiriman produksi

Tombol kirim tidak membuka pengiriman email nyata. Persetujuan manual saat ini
hanya mendukung Mailpit lokal atau simulasi; konfigurasi produksi menolak mode
pengiriman selain dry-run. Jalur produksi memerlukan adapter SMTP terpisah,
verifikasi email, persetujuan penerima dan otorisasi staf yang disiapkan tersendiri.
Field kontak optional telah ditambahkan melalui Alembic, tetapi data demo tidak
memenuhi persyaratan pengiriman produksi. Tidak ada pengiriman WhatsApp.
