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
docker compose -f compose.public-demo.yaml up -d --build --wait backend-sandbox mailpit-sandbox worker-sandbox frontend-public
```

Setup sandbox hanya mengisi rahasia yang kosong dalam `.env`.
Frontend tidak menerima token utama atau key 9Router; AI hanya di backend sandbox.
Buka `http://localhost:8502`. Untuk HTTPS ikuti [Funnel](public_demo.md).

## Isolasi dan batas

Setiap login mendapat 24 kandidat, 10 lowongan, 8 penempatan, 3 draf, matching,
dan jadwal sintetis. Volume `sandbox_data` terpisah dari backend utama.
Backend, worker, dan Mailpit sandbox tidak mempunyai port host.

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
6. Tunggu polling worker, lalu perbarui status/riwayat.
7. Logout/login ulang memberi database baru; sesi browser lain tidak melihat data sebelumnya.

Dokumen, orientasi, dan keberangkatan memakai tindakan email jadwal.
Worker hanya mengambil pesan yang disetujui. Workflow n8n utama tidak digunakan.
Status sent berarti server email menerima pesan, bukan inbox kandidat.

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

## Pemeriksaan dan penghentian

Preflight membutuhkan stack staf dan sandbox pada port default:

```powershell
.\.venv\Scripts\python.exe scripts/verify_public_demo.py
.\.venv\Scripts\python.exe -m pytest tests/integration/test_interactive_sandbox.py tests/integration/test_public_demo.py
```

Menghentikan hanya service sandbox:

```powershell
docker compose -f compose.public-demo.yaml stop frontend-public worker-sandbox backend-sandbox mailpit-sandbox
```

Periksa riwayat sebelum mengulang SMTP setelah callback terputus; exactly-once
tidak dijamin. Mematikan HTTPS dijelaskan pada [akses publik](public_demo.md#mematikan-akses).
