# Sandbox demo interaktif

Frontend 8502 menggunakan login, backend terpisah, dan database sintetis per sesi.

## Persiapan pertama

Selesaikan [instalasi lokal](../README.md#instalasi-di-windows).
Jika login belum dikonfigurasi, buat sekali:

```powershell
.\.venv\Scripts\python.exe scripts/setup_public_demo.py --generate
```

Akun tersimpan pada berkas privat `data/runtime/public-demo-access.txt`.
Setup ulang mengganti hash/password; lewati langkah ini untuk mempertahankan akun existing.

```powershell
.\.venv\Scripts\python.exe scripts/setup_sandbox.py
docker compose -f compose.public-demo.yaml config --quiet
docker compose -f compose.public-demo.yaml up -d --build --wait backend-sandbox mailpit-sandbox n8n-sandbox frontend-public
```

Setup sandbox hanya mengisi rahasia yang kosong dalam `.env`.
Frontend tidak menerima token utama atau key 9Router; AI hanya di backend sandbox.
Buka `http://localhost:8502`. Untuk HTTPS ikuti [Funnel](public_demo.md).

## Isolasi dan batas

Setiap login mendapat 24 kandidat, 10 lowongan, 8 penempatan, 3 draf, matching,
dan jadwal sintetis. Volume `sandbox_data` terpisah dari backend utama.
Backend, n8n, dan Mailpit sandbox tidak mempunyai port host.

Backend menegakkan role demo, scope sesi, upload, dan kontak `.invalid`.
Token sesi disimpan server-side. Email efektif selalu `mailpit@minori.local`
melalui `mailpit-sandbox:1025`, tanpa relay internet.

| Batas default | Nilai |
| --- | --- |
| Durasi / idle sesi | 60 / 15 menit |
| Login gagal | 5 dalam 5 menit; lockout 5 menit |
| AI / tulis / upload / email per sesi | 12 / 80 / 10 / 5 |
| Ukuran upload / batch | 2 MB / 5 lowongan |
| Reset per sesi | 2 |
| Request bisnis per sesi | 120 per menit |
| Sesi aktif / pembukaan sesi | 8 / 12 per jam |
| AI / email bersama | 60 / 30 per jam |

Satu operasi AI dapat mencoba maksimal empat model.
Reset/login baru tidak menghapus batas bersama; journal bersama bertahan setelah restart.
Jalankan backend satu proses/replica.

## Alur pengujian

1. Buka halaman langsung sebelum login; hanya form masuk boleh terlihat.
2. Login → Analisis Lowongan → upload/tempel → analisis → tinjau ekstraksi,
   terjemahan, review → koreksi → simpan draf.
3. Tambah kandidat sintetis → matching → periksa hasil resmi →
   Jelaskan dengan AI → keputusan demo.
4. Buat penempatan dari approved dan eligible → jadwalkan kegiatan mendatang →
   periksa pengingat H-3/H-1.
5. Pusat Pengingat → pilih kandidat/jadwal → susun AI/template → edit →
   konfirmasi → kirim.
6. Tunggu polling n8n (15 detik), lalu perbarui status/riwayat.
7. Logout/login ulang memberi database baru; sesi browser lain tidak melihat data sebelumnya.

Dokumen, orientasi, dan keberangkatan memakai tindakan email jadwal.
Wawancara H-3 dan pemeriksaan kesehatan H-1 dikirim otomatis pada 09.00 WIB,
tanpa konfirmasi tambahan. Pengingat terlambat diproses segera selama kegiatan
masih mendatang. Untuk pesan yang Anda susun sendiri, pilih **Siapkan email manual**;
pekerjaan terpisah tetap memerlukan konfirmasi subject, isi, jadwal, dan tujuan.
Pengingat otomatis dan manual sama-sama memakai kuota email sesi.
Workflow n8n utama tidak digunakan.
Status sent berarti server email menerima pesan, bukan inbox kandidat.
Pusat Pengingat menampilkan jenis pengiriman, jumlah percobaan, status, dan riwayat
dari database sesi Anda. Sesi lain tidak dapat membaca bukti tersebut.

## Reset dan pembaruan

Gunakan **Penggunaan & reset sesi**, konfirmasi, lalu reset.
Reset ditolak selama request/pengiriman diproses; budget dan sesi lain tetap berlaku.
Backup sesi privat dibersihkan bersama sesi.

Pembaruan backend saja:

```powershell
docker compose -f compose.public-demo.yaml build backend-sandbox
docker compose -f compose.public-demo.yaml up -d --no-deps --no-build --wait backend-sandbox
```

Login ulang setelah restart. Build/up service lain hanya jika kodenya berubah.
Jangan memakai `--remove-orphans` atau `down -v`.

Untuk migrasi dari worker lama, jalankan `scripts/setup_sandbox.py` terlebih dahulu.
Script menambahkan `SANDBOX_N8N_ENCRYPTION_KEY` hanya jika belum ada; rahasia utama
dan akun login tetap sama. Hentikan worker lama sebelum mengaktifkan n8n:

```powershell
docker stop minori-placement-intelligence-worker-sandbox-1
docker compose -f compose.public-demo.yaml build backend-sandbox frontend-public n8n-sandbox
docker compose -f compose.public-demo.yaml up -d --no-deps --no-build --wait backend-sandbox n8n-sandbox frontend-public
```

Bootstrap mengimpor workflow dan credentials ke volume `n8n_sandbox_data` tersendiri,
mengenkripsi credentials, menghapus berkas sementara, lalu mempublikasikan workflow.
Kunci sandbox harus tetap sama ketika volume dipakai kembali. n8n sandbox hanya
terhubung ke jaringan internal aplikasi dan Mailpit; tidak ada port UI atau webhook publik.
UI n8n sandbox dinonaktifkan; status dan riwayat pengiriman dibaca melalui dashboard reviewer.
Funnel pada 8502 tidak perlu diubah.

## Tes workflow dan SMTP terisolasi

Profil berikut memakai project tersendiri, database/n8n tmpfs, Mailpit privat,
dan clock test. Tidak mengubah jam Windows atau database demo utama.
Workflow diuji melalui engine n8n native, termasuk kegagalan SMTP pada port lokal
tertutup, retry, isolasi sesi, persetujuan manual, dan batas tiga percobaan.

```powershell
docker compose -p minori-n8n-sandbox-test -f compose.public-demo.yaml -f compose.n8n-sandbox-test.yaml up -d --build --wait backend-sandbox mailpit-sandbox n8n-sandbox
.\.venv\Scripts\python.exe scripts/verify_sandbox_n8n.py
docker compose -p minori-n8n-sandbox-test -f compose.public-demo.yaml -f compose.n8n-sandbox-test.yaml down
```

Mulai stack test baru sebelum mengulang tes; fixture clock hanya boleh maju.
Hasil aman tanpa token/isi pesan tersimpan di `test-results/n8n-sandbox-e2e.json`.
Pada runtime normal, cron 09.00 WIB dan polling 15 detik menggunakan waktu server.
Callback HTTP diulang maksimal tiga kali dengan token yang sama. SMTP sendiri
tidak diulang oleh node; backend menjadwalkan retry 10/20 detik, maksimal tiga
klaim dan selalu sebelum kegiatan dimulai. Recovery menangani lease kedaluwarsa.

## Pemeriksaan dan penghentian

Preflight membutuhkan stack staf dan sandbox pada port default:

```powershell
.\.venv\Scripts\python.exe scripts/verify_public_demo.py
.\.venv\Scripts\python.exe -m pytest tests/integration/test_interactive_sandbox.py tests/integration/test_public_demo.py
```

Menghentikan hanya service sandbox:

```powershell
docker compose -f compose.public-demo.yaml stop frontend-public n8n-sandbox backend-sandbox mailpit-sandbox
```

Periksa riwayat sebelum mengulang SMTP setelah callback terputus; exactly-once
tidak dijamin. Mematikan HTTPS dijelaskan pada [akses publik](public_demo.md#mematikan-akses).
