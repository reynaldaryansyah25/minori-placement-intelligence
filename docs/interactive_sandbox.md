# Demo publik interaktif

Port `8502` dan link HTTPS Funnel existing tetap sama. Frontend publik sekarang memakai backend sandbox dengan role `demo_operator`; setiap login mendapatkan database sintetis tersendiri. Dashboard staf `8501`, database utama, workflow n8n utama, Mailpit utama, dan konfigurasi 9Router tetap dipertahankan.

## Menjalankan dari PowerShell

Jalankan dari root repository dengan Docker Desktop aktif:

```powershell
.\.venv\Scripts\python.exe scripts/setup_sandbox.py
docker compose -f compose.public-demo.yaml config --quiet
docker compose -f compose.public-demo.yaml build backend-sandbox worker-sandbox frontend-public
docker compose -f compose.public-demo.yaml up -d --no-build backend-sandbox mailpit-sandbox worker-sandbox frontend-public
docker compose -f compose.public-demo.yaml ps
```

Setup hanya menambahkan `SANDBOX_GATEWAY_TOKEN` dan `SANDBOX_WORKER_TOKEN` ke `.env` yang diabaikan Git. Kredensial existing dan login publik tetap sama. Jangan memasukkan token admin/reviewer utama ke service sandbox. Jangan memakai `--remove-orphans` atau `down -v`: project Compose juga memiliki service utama.

Untuk pembaruan selanjutnya gunakan build/up yang sama. Hanya empat service sandbox/publik tersebut yang diganti. Backend harus satu proses, satu replica. Restart backend mengakhiri sesi aktif dan membersihkan salinan sesi lama; batas bersama per jam tetap tersimpan. Restart sandbox sebelum periode penilaian baru agar jadwal contoh relatif terhadap waktu startup terbaru.

Tidak ada perintah perubahan Funnel dalam setup. Target existing tetap `127.0.0.1:8502`.

AI memakai daftar cadangan `NINE_ROUTER_FALLBACK_MODELS` dari `.env` yang sama.
Saat primary terkena kuota/provider gagal, backend mencoba model cadangan teruji
melalui 9Router existing. Lihat `ai_operations.md` untuk urutan dan batas waktu.
Batas AI sesi/jam menghitung operasi pengguna; satu operasi dapat mencoba maksimal
empat model. Upload, RBAC, validasi keluaran dan persetujuan email tetap berlaku.
Untuk memasang pembaruan adapter hanya pada sandbox:

```powershell
docker compose -f compose.public-demo.yaml build backend-sandbox
docker compose -f compose.public-demo.yaml up -d --no-deps --no-build backend-sandbox
```

Login ulang setelah restart backend. Service staf, workflow n8n, Mailpit dan Funnel
tidak memerlukan perubahan. Pemeriksaan Funnel read-only:

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

Pada QA 14 Oktober 2026, Tailscale berjalan tetapi `serve status`/`funnel status`
melaporkan **No serve config** dan domain existing belum dapat di-resolve. Konfigurasi
tersebut tidak diubah otomatis. `PUBLIC_DEMO_HOST` juga belum cocok dengan DNSName
perangkat Tailscale yang sedang aktif. Aplikasi lokal dapat diuji penuh; akses publik HTTPS
baru dapat diverifikasi setelah pengelola memulihkan Funnel pada target `8502`.
Ikuti prosedur Funnel dalam `public_demo.md` bila pengelola memilih mengaktifkannya.

Pengelola dapat memeriksa nama perangkat tanpa menampilkan seluruh status akun:

```powershell
$demoTailnet = (& 'C:\Program Files\Tailscale\tailscale.exe' status --json | ConvertFrom-Json)
$demoTailnet.Self.DNSName
```

Pulihkan identitas/domain Tailscale existing yang memang akan dipakai, lalu pastikan
`PUBLIC_DEMO_HOST` sesuai. Bila pengelola menyetujui perubahan hostname, ubah field
tersebut sendiri dan recreate **frontend-public saja**. Setelah domain sesuai, perintah
manual untuk mengaktifkan target lokal adalah `tailscale funnel --bg 8502`. Perintah ini
tidak dijalankan selama tugas. Jangan mengganti domain secara diam-diam untuk melewati
kegagalan DNS/CORS.

Untuk menghentikan sandbox tanpa mengubah Funnel atau service utama:

```powershell
docker compose -f compose.public-demo.yaml stop frontend-public worker-sandbox backend-sandbox mailpit-sandbox
```

## Isolasi dan batas penggunaan

- Login scrypt, pembatasan percobaan login bersama, timeout idle/absolut, CORS, XSRF, dan port loopback tetap aktif. Token sesi backend disimpan dalam memori server Streamlit, tidak dalam widget, URL atau browser storage. Gateway bootstrap hanya dapat membuka sesi, bukan menjalankan CRUD. Worker hanya memiliki akses antrean.
- Setiap sesi mendapat 24 kandidat, 10 lowongan, 8 penempatan, 3 draf, matching dari engine, jadwal dan pengingat sintetis. Skema dibuat melalui migrasi Alembic existing. Volume baru `sandbox_data` tidak terhubung ke service utama.
- Network `sandbox_app` dan `sandbox_mail` bersifat internal. Backend memakai network tersendiri untuk 9Router host; frontend memakai bridge tersendiri agar port loopback tetap dapat dipetakan pada Docker Desktop. Worker hanya mengenal SMTP `mailpit-sandbox:1025` dan penerima tetap `mailpit@minori.local`. Mailpit sandbox tidak memiliki relay, port host, atau network keluar. Semua service sandbox terpisah dari network utama.
- Hanya frontend memetakan `127.0.0.1:8502`. API, worker, dan Mailpit sandbox tidak memetakan port host. Frontend tidak menerima key 9Router maupun kredensial utama.
- Per sesi: 12 panggilan AI, 80 operasi tulis, 10 unggahan, 5 pekerjaan email, 2 reset, maksimal 120 permintaan bisnis per menit. Unggahan maksimal 2 MB, batch maksimal 5 lowongan. Percobaan tidak valid tetap dapat menghabiskan budget. Persetujuan berulang pada pengingat yang sama tidak menambah hitungan email dan tetap divalidasi idempotency.
- Bersama: 8 sesi aktif, 12 pembukaan sesi per jam, 60 panggilan AI serta 30 pekerjaan email per jam. Logout/login dan reset tidak menghapus batas per jam. Batas bersama disimpan dalam volume sandbox agar restart tidak menjadi jalan pintas.
- Timeout idle 15 menit, absolut 60 menit, mengikuti `PUBLIC_SESSION_*`. Logout mencabut token. Worker boleh menyelesaikan callback klaim yang sudah berjalan setelah logout, tetapi tidak mengambil pekerjaan baru.
- Reset hanya memulihkan data sesi pemanggil dan mempertahankan budget. Salinan sebelum reset disimpan sebagai backup privat sampai sesi dibersihkan. Reset ditolak selama request/pengiriman sedang diproses. Reviewer lain tidak terkena reset tersebut.

Gunakan identitas dan dokumen sintetis saja. Email kontak kandidat yang diinput harus memakai domain `.invalid`. Data sesi bersifat sementara, bukan arsip operasional.

## Alur uji browser

1. Buka link HTTPS existing atau `http://localhost:8502`. Sebelum login hanya form masuk yang tersedia. Login existing tetap berlaku; label **Sandbox · Data sintetis** harus terlihat.
2. **Analisis lowongan:** unggah dokumen sintetis, **Pratinjau dokumen**, pilih baris, **Analisis dengan AI**. Tinjau ekstraksi, terjemahan dan pemeriksaan persyaratan. Koreksi kolom wajib lalu **Simpan draf**. Publikasi tetap keputusan manusia; PDF scan memerlukan OCR.
3. **Kandidat:** tambah kandidat sintetis. **Pencocokan kandidat:** pilih lowongan/kandidat, periksa hasil resmi, **Jelaskan dengan AI**, lalu beri keputusan demo. AI tidak mengubah skor atau kelayakan.
4. **Alur penempatan:** pilih kandidat disetujui, buat penempatan, simpan jadwal wawancara mendatang. Pengingat H-3 dibuat otomatis, pemeriksaan kesehatan memakai H-1. Dokumen/orientasi/keberangkatan memakai tindakan email jadwal existing.
5. **Pusat pengingat:** pilih kandidat dan jadwal, siapkan email, **Susun Email dengan AI**, edit, centang persetujuan, **Kirim Pengingat Sekarang**. Draf belum dikirim sebelum persetujuan.
6. Tunggu sekitar 3–10 detik, klik **Perbarui status demo** atau **Perbarui riwayat**, lalu pilih pengingat dan lihat riwayat. Sukses berarti **Terkirim ke server email**, bukan diterima kandidat. Pengingat seed yang belum disetujui tidak otomatis dikirim.
7. Buka **Penggunaan & reset sesi**, konfirmasi reset; jumlah data kembali ke dataset awal sementara pemakaian tetap tercatat. Logout/login memberi database baru; sesi reviewer lain tetap utuh.

## Worker email

Tugas ini memilih alternatif **worker terisolasi**, tanpa perubahan workflow n8n. Worker polling setiap 3 detik melalui HTTP autentikasi; tidak mengakses SQLite. Ia menggunakan kontrak due → claim → SMTP → complete/fail existing dengan scope sesi privat.

Sebelum SMTP worker memeriksa `delivery_allowed`, `dry_run=false`, routing Mailpit, dan penerima efektif tetap. Callback memakai claim token sesuai serta provider reference valid. Gagal SMTP dicatat sebagai `PROVIDER_UNAVAILABLE`; retry 10–60 detik, maksimal 3 percobaan. Klaim ganda ditolak. Persetujuan menyimpan snapshot, fingerprint jadwal, aktor sesi dari server, dan idempotency key.

SMTP tidak menjamin exactly-once. Jika Mailpit menerima pesan tetapi callback gagal, pemulihan lease dapat mengirim ulang. Status processing/retry menunjukkan ketidakpastian ini. Jangan mengklaim penerimaan kandidat hanya dari SMTP sukses. Riwayat percobaan di dashboard menjadi catatan backend; bukti Mailpit diperiksa terpisah saat QA.

## Verifikasi operator

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/verify.py
docker compose config --quiet
docker compose -f compose.public-demo.yaml config --quiet
.\.venv\Scripts\python.exe scripts/verify_public_demo.py
```

`scripts/verify_sandbox_isolation.py --record` menyimpan fingerprint sebelum perubahan runtime di `test-results/`, tanpa secrets/data bisnis. Jalankan tanpa `--record` setelah QA untuk membandingkan container, database, kredensial utama, definisi workflow n8n dan konfigurasi Funnel. Baseline existing tidak boleh ditimpa. Tes otomatis menggunakan mock LLM/SMTP; smoke test 9Router dan Mailpit nyata dilakukan terpisah.
