# Frontend MINORI Placement Intelligence

Frontend tetap menggunakan Streamlit. Semua data dan operasi bisnis melalui
HTTP ke FastAPI; tidak ada akses SQLite, pengganti backend, atau workflow n8n baru.

## Referensi dan komponen

Bahasa visual mengikuti `minori_design_reference.html` yang diberikan pengguna:
navy `#17283f`, teal `#0f766e`, latar `#f6f8fb`, kartu putih,
border `#e3e9f0`, radius 12 px, dan font Inter/Segoe UI dengan fallback sistem.
Tidak ada data contoh HTML yang dimasukkan ke aplikasi.

Sidebar, header, kartu ringkasan, badge status, panel detail, diagram batang, dan
timeline memakai komponen bersama. Form, tombol, dialog, filter, pilihan baris,
tab, pagination, dan unduhan menggunakan widget Streamlit asli. Markup display
kecil dirender melalui `st.html` dalam DOM aplikasi, tanpa iframe; semua teks
dinamis di-escape. Grafik menampilkan hitungan backend, tanpa angka dekoratif.

`frontend/app.py` adalah entry point. Letaknya di luar paket menghindari konflik
auto-discovery folder `pages` dengan router `st.navigation`. Shell dan delapan
modul halaman tetap berada di `frontend/minori_frontend/`.

## Menjalankan frontend

Dari root repository, gunakan environment dan token server yang sudah dikonfigurasi:

```powershell
cd frontend
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
```

Menjalankan dari folder frontend memuat `.streamlit/config.toml`. Konfigurasi
CORS dan perlindungan XSRF yang sudah ada dipertahankan. Tampilan selalu memakai
tema terang yang sesuai referensi.

Untuk menerapkan perubahan frontend saja:

```powershell
docker compose build frontend
docker compose up -d --no-deps --wait frontend
```

Perintah tersebut tidak membuat ulang backend atau n8n. Frontend menggunakan
`BACKEND_BASE_URL` dan kredensial server yang sudah tersedia. Token dan pemilih
peran tidak ditampilkan. Hak tulis pada sesi tetap membatasi tombol; backend
memvalidasi otorisasi setiap permintaan.

## Delapan halaman

| Halaman | Operasi |
| --- | --- |
| Ringkasan | Metrik backend, prioritas, agenda, distribusi status, aktivitas terkini, tautan menuju halaman terkait |
| Kandidat | Pencarian/filter, pagination, profil kualifikasi, tambah kandidat, arsip dengan konfirmasi |
| Lowongan | Pencarian/filter, persyaratan, tambah/tutup lowongan, navigasi ke pencocokan dengan lowongan terpilih |
| Pencocokan Kandidat | Evaluasi ulang, peringkat/semua kandidat, rincian skor dan pemeriksaan, keputusan staf, pembuatan penempatan |
| Alur Penempatan | Pencarian/filter, timeline, daftar kegiatan, tandai selesai, penjadwalan dengan tanggal dan waktu WIB |
| Pusat Pengingat | Filter antrean, sinkronisasi, pemulihan, simulasi, tujuan pengiriman aktual, riwayat percobaan |
| Analisis Lowongan | Teks sumber sebagai acuan sesi, draf dari backend, penyuntingan, penyimpanan dan penerbitan draf |
| Laporan & Analitik | Distribusi backend, evaluasi yang perlu ditinjau, unduhan CSV dengan nama dan status yang mudah dibaca |

Ekstraksi AI otomatis belum memiliki endpoint use case pada backend saat ini.
Tidak ada tombol ekstraksi yang berpura-pura bekerja. Peninjauan manual,
penyimpanan, penyuntingan, dan penerbitan draf merupakan operasi API yang nyata.
Teks sumber hanya menjadi acuan dalam sesi; dokumen asli tetap perlu diarsipkan
oleh tim.

## Perilaku tampilan

- Identifier, UUID, kode template, kode error, referensi internal dan token tidak
  dirender untuk staf. Identifier tetap digunakan internal untuk memanggil API.
- Tabel menampilkan sepuluh baris per halaman; riwayat pendek memakai lima baris.
  Pemilihan baris tetap menunjuk record yang benar setelah berpindah halaman.
- Koleksi API diambil per 100 catatan sampai selesai, sehingga laporan tidak
  berhenti pada halaman pertama API. Seluruh angka tetap bersumber dari backend.
- Kolom status diberi warna melalui pandas Styler yang didukung tabel Streamlit.
  pandas sudah ada dalam constraints dan sekarang menjadi dependency frontend
  langsung karena dipakai untuk format tabel.
- CSV mengganti UUID dengan nama kandidat/posisi, memakai label Indonesia, dan
  melindungi sel teks yang dapat dianggap formula spreadsheet.
- Error layanan tampil sebagai langkah yang dapat dilakukan staf, tanpa raw
  response, stack trace, atau detail konfigurasi.
- Kandidat nonaktif dan penempatan terminal tidak dapat dijadwalkan lewat form.
  Penyelesaian aktivitas tersedia setelah waktu kegiatan dimulai.
- Pada layar sempit, panel menjadi satu kolom, kartu ringkasan menjadi dua kolom,
  dan menu native menyediakan akses ke seluruh halaman. Tabel/timeline dapat
  digeser di dalam komponennya tanpa melebarkan halaman.

## Verifikasi 14 Oktober 2026

`python scripts/verify.py` selesai dengan exit 0: **289 tes lulus**, pip check,
Ruff, format, migrasi/check drift, seed idempoten, integritas database, matching,
dan verifikasi reminder. Database verifikasi bersifat sementara. Provider LLM
nyata tidak dipanggil.

Regression tests frontend menggunakan HTTP transport palsu, bukan data aplikasi
live. Cakupannya meliputi delapan halaman, pagination dan identitas record,
pencarian tanpa hasil, escaping teks backend, penyamaran error, pembatasan akses
baca, koleksi lebih dari 100 catatan, ekspor CSV, serta kontrak API simulasi dan
penyimpanan draf.

Pemeriksaan browser langsung dilakukan pada desktop (termasuk viewport
1440 × 1000) dan **seluruh delapan halaman pada mobile 390 × 819**.
Tidak ditemukan exception UI, HTML mentah, atau overflow horizontal pada halaman.
Navigasi sidebar/menu, drawer mobile, dan tampilan tabel/panel diperiksa langsung.
Bukti screenshot dan pengukuran DOM tersimpan lokal dalam `test-results/`
yang tidak masuk Git.

Smoke HTTP melalui `scripts/smoke_test.py` juga lulus (exit 0) dengan database uji
terpisah yang dimigrasikan lebih dahulu: backend health OK, Streamlit health OK,
dan halaman frontend HTTP 200. Percobaan awal wrapper smoke menemukan file SQLite
terkunci saat cleanup Windows; pengulangan dengan direktori pengujian terisolasi
yang dipertahankan sebagai artefak selesai tanpa error. Database demo tidak disentuh.

`docker compose config --quiet` lulus. Image frontend dibangun dan hanya layanan
frontend dibuat ulang; backend, n8n, dan layanan pengujian reminder tetap berjalan.
