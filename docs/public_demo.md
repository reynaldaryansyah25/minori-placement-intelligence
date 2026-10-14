# Demo publik dengan Tailscale Funnel pada Windows

## Batas akses

`frontend-public` melayani `127.0.0.1:8502` pada project/jaringan Docker existing.
Dashboard staf tetap di `127.0.0.1:8501`. Service publik tidak mempunyai token admin,
kredensial 9Router/n8n, mount `.env`, atau mount database. Ia hanya menerima token
reviewer dari environment dan mengakses FastAPI lewat HTTP di jaringan Docker.

Sebelum navigasi atau halaman bisnis dirender, pengunjung wajib masuk menggunakan
akun peninjau yang dikonfigurasi pengelola. Password disimpan sebagai hash scrypt
dengan salt acak, N=131072, r=8, p=1 sesuai rekomendasi
[OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
Password dan token API tidak dimasukkan ke cookie autentikasi atau
sesi aplikasi publik. Identitas token juga diperiksa ke `/auth/me`: role selain
`reviewer` ditolak, termasuk token admin yang salah dipasang sebagai token reviewer.

Default sesi: 15 menit tanpa aktivitas, maksimal satu jam. Pemeriksaan setiap aksi
server ditambah pemeriksaan idle setiap 15 detik. Logout, kedaluwarsa, dan restart
container menghapus sesi. Rotasi kredensial memerlukan recreate service publik.

Lima login gagal dalam lima menit mengunci akun peninjau selama lima menit. Batas
berlaku lintas sesi browser pada satu proses, sehingga membuka incognito atau
mengubah header IP tidak melewatinya. Akun dibagikan untuk demo terbatas; pembatasan
global dapat sementara menghalangi login sah ketika ada serangan. Jangan menjalankan
beberapa replica tanpa limiter bersama. Restart container mengosongkan limiter.

Frontend menolak seluruh metode tulis dan seluruh endpoint `/internal/` sebelum
HTTP dijalankan. FastAPI juga menolak token reviewer pada endpoint mutasi. Pengecekan
otorisasi operasi AI ditempatkan sebelum dependensi gateway agar selalu 401/403,
termasuk ketika AI dimatikan. Tombol staf di UI tetap tidak dapat digunakan.

## Hanya data sintetis

Halaman memakai respons backend aktual. Profil kandidat, lowongan, dan draf hanya
lolos apabila referensi dan fingerprint kontennya cocok dengan katalog seed sintetis
yang dibangun dari `seed_professional_demo` pada database sementara. Label `DEMO-`
saja tidak cukup. Profil yang berubah atau data tambahan tidak ditampilkan. Tanggal
dan status operasional dapat berubah; teks bebas, identitas, kualifikasi, serta
perusahaan harus tetap sesuai katalog. Relasi penempatan/jadwal/notifikasi juga
dibatasi ke seed tersebut dan lokasi sintetis yang dikenal.

Ringkasan dan laporan dihitung dari subset ini. Skor dan kelayakan dibaca dari
endpoint matching resmi; algoritma tidak disalin atau diubah. Kontak, isi/snapshot
email, tujuan SMTP, referensi provider, token klaim, serta audit staf tidak disertakan
dalam proyeksi publik. UUID tetap digunakan secara internal oleh server untuk relasi,
tetapi tidak ditampilkan sebagai informasi bisnis. Data tambahan di dashboard staf
tetap tersedia secara lokal.

Katalog berada di `frontend/minori_frontend/public_catalog.py`. Jika seed sintetis
resmi berubah, bangun ulang dengan `python scripts/build_public_demo_catalog.py`,
tinjau diff, lalu jalankan tes. Jangan mengganti fingerprint menggunakan data nyata.
Skrip ini mengarahkan Alembic secara eksplisit ke database sementara dan tidak
menggunakan `.env` database aplikasi.

## Menyiapkan dan memeriksa service lokal

Jalankan dari direktori repository pada PowerShell. Stack backend/demo/staf harus
sudah berjalan. Tidak perlu restart n8n, Mailpit, atau mengganti database.

```powershell
# Membuat password acak kuat. Nilainya tidak dicetak ke terminal/chat.
.venv/Scripts/python.exe scripts/setup_public_demo.py --generate
# ATAU pilih password sendiri secara interaktif (minimal 16 karakter):
# .venv/Scripts/python.exe scripts/setup_public_demo.py --username reviewer

docker compose -f compose.public-demo.yaml config --quiet
docker compose -f compose.public-demo.yaml build frontend-public
docker compose -f compose.public-demo.yaml up -d --no-deps --wait frontend-public
.venv/Scripts/python.exe scripts/verify_public_demo.py
```

Skrip setup hanya mengubah `PUBLIC_DEMO_USERNAME` dan `PUBLIC_DEMO_PASSWORD_HASH`
di `.env` existing; token backend tidak diganti. Mode publik ditetapkan langsung
pada service Compose, bukan global `.env`, supaya dashboard staf tidak berubah.
Pada mode generate, baca akun melalui `data/runtime/public-demo-access.txt`, berkas
yang diabaikan Git dan dibatasi ACL ke pengguna Windows yang menjalankan setup.
Simpan password pada password manager dan bagikan hanya kepada peninjau yang diizinkan.
File akses tidak masuk image/container dan tidak disajikan lewat Streamlit.

Buka `http://localhost:8502`. Uji URL langsung `/candidates` sebelum login: hanya
form masuk yang boleh terlihat. Setelah login, cek kedelapan halaman. Coba password
salah, logout, serta buka tab/browser baru. Port 8501 harus tetap menjadi dashboard
staf. Healthcheck publik hanya mengukur proses Streamlit; browser dan preflight
tetap diperlukan untuk membuktikan autentikasi dan RBAC.

Skrip runtime hanya menguji operasi tulis menggunakan token yang harus ditolak;
ia tidak mengirim mutasi dengan token admin, mengirim email, atau memanggil LLM.

## 9Router dan pemeriksaan listener

9Router sebelumnya mendengarkan `0.0.0.0:20128`. Dengan izin pengguna, listener
dibatasi ke `127.0.0.1` menggunakan opsi CLI resmi `--host`, tanpa mengganti model,
provider, atau kredensial. Akses `host.docker.internal:20128` dari Docker tetap harus
diverifikasi. Untuk menyalakan ulang dengan batas yang sama:

```powershell
./scripts/start_9router_local.ps1
Get-NetTCPConnection -State Listen -LocalPort 8000,8501,8502,5678,8025,20128 |
    Select-Object LocalAddress,LocalPort
```

Gunakan skrip ini atau `9router --host 127.0.0.1 --port 20128 --no-browser --skip-update`
untuk peluncuran berikutnya; perintah `9router` tanpa opsi host kembali memakai
default semua antarmuka. Tidak ada pengaturan model/provider yang diubah oleh skrip.

## Mengaktifkan Funnel secara manual

Funnel **tidak diaktifkan oleh kode atau skrip proyek**. Pengelola melakukan langkah
berikut setelah verifikasi lulus. Tailscale harus terpasang, masuk ke tailnet, dan
memenuhi persyaratan Funnel/HTTPS pada akun. Jangan mengganti mapping yang sudah
dipakai aplikasi lain. Periksa status sebelum memilih port HTTPS.

```powershell
$tailscaleExe = 'C:/Program Files/Tailscale/tailscale.exe'
& $tailscaleExe version
& $tailscaleExe status
& $tailscaleExe funnel status
# Pastikan PUBLIC_DEMO_HOST pada .env sama dengan hostname berikut (tanpa titik terakhir):
(& $tailscaleExe status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')
docker compose -f compose.public-demo.yaml up -d --no-deps --force-recreate --wait frontend-public
.venv/Scripts/python.exe scripts/verify_public_demo.py
# Hanya jika port HTTPS 443 belum digunakan konfigurasi lain:
& $tailscaleExe funnel --bg --https=443 http://127.0.0.1:8502
& $tailscaleExe funnel status
```

Bagikan URL HTTPS `.ts.net` yang ditampilkan CLI beserta akun demo melalui saluran
privat. Funnel dapat diakses internet; pengunjung tidak harus menjadi anggota tailnet.
Laptop, Docker Desktop, backend, dan frontend publik harus tetap aktif selama demo.
Login aplikasi tetap wajib. Sebelum menjalankan perintah `funnel --bg`, baca hostname
perangkat dengan `(& $tailscaleExe status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')`.
Isi `PUBLIC_DEMO_HOST` pada `.env` dengan hostname persis tersebut, tanpa protokol
atau path, kemudian recreate hanya `frontend-public`. Konfigurasi ini mengizinkan
origin WebSocket Funnel secara spesifik sambil mempertahankan CORS dan XSRF.
`localhost` tetap dapat dipakai untuk pengujian lokal.

Uji URL HTTPS dari perangkat/jaringan lain, termasuk
WebSocket Streamlit, login, logout, timeout, dan akses langsung ke halaman kandidat.
Jangan mematikan CORS atau XSRF untuk mengatasi masalah reverse proxy.

Hanya target `8502` yang boleh diteruskan. Jangan meneruskan port backend `8000`, staf
`8501`, n8n `5678`, Mailpit `8025`, atau 9Router `20128`.

## Mematikan akses publik dan mencabut sesi

```powershell
$tailscaleExe = 'C:/Program Files/Tailscale/tailscale.exe'
# Matikan mapping HTTPS yang khusus dipakai MINORI:
& $tailscaleExe funnel --https=443 off
& $tailscaleExe funnel status
docker compose -f compose.public-demo.yaml stop frontend-public
```

`tailscale funnel reset` menghapus semua konfigurasi Funnel pada mesin; gunakan hanya
jika tidak ada mapping aplikasi lain yang harus dipertahankan. Untuk rotasi password,
jalankan setup kembali, lalu `docker compose -f compose.public-demo.yaml up -d
--no-deps --force-recreate --wait frontend-public`. Restart juga dapat dipakai untuk
mencabut seluruh sesi aktif. Jangan menjalankan `down -v` atau `--remove-orphans`.

Referensi resmi: [Tailscale Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel),
[persyaratan Funnel](https://tailscale.com/docs/features/tailscale-funnel),
[Python scrypt](https://docs.python.org/3.12/library/hashlib.html#hashlib.scrypt),
[konteks sesi Streamlit](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.context).

## Hasil verifikasi 14 Oktober 2026

- Docker: `python scripts/verify.py` menyelesaikan seluruh 11 pemeriksaan dengan
  sukses. **363 tes lulus** dalam 261,00 detik pada image final, termasuk seluruh regresi existing,
  login publik, timeout, isolasi role/token, filter data, dan RBAC seluruh operasi tulis.
- Ruff lint/format serta konfigurasi Compose utama dan publik lulus.
- Verifier final memakai scrypt N=131072, r=8, p=1. Sebanyak 19 tes autentikasi
  terarah juga lulus pada host. Login nyata pada container sehat tanpa restart/OOM.
- Handshake WebSocket dengan origin HTTPS Tailscale yang dikonfigurasi diterima;
  origin asing ditolak 403 tanpa menonaktifkan CORS/XSRF. Pemeriksaan desktop 1440
  dan mobile 390 piksel tidak menunjukkan overflow halaman.
- Preflight runtime membuktikan **32 endpoint mutasi** menolak reviewer dan pengunjung
  anonim. Role admin lokal tetap benar dan kedua frontend sehat. Tidak ada mutasi
  ber-token admin yang dilakukan oleh preflight.
- Browser nyata: deep link anonim hanya menampilkan login; password salah ditolak;
  akun sah membuka dashboard reviewer dan kedelapan halaman. Kontrol operasi staf
  tidak dapat digunakan, kontak/isi email tidak ditampilkan, dan hanya seed sintetis
  terverifikasi yang muncul.
- Uji browser terisolasi pada port sementara 18502 membuktikan lockout lintas dua tab,
  login berhasil setelah lockout selesai, serta dashboard otomatis kembali ke login
  setelah sesi idle kedaluwarsa. Container sementara telah dihapus.
- Listener 9Router dibatasi ke localhost dengan izin pengguna. Discovery model host
  dan Docker tetap berhasil menggunakan model existing; tidak ada penggantian model
  atau kredensial. Tailscale sudah terpasang dan aktif pada tailnet, tetapi
  `tailscale funnel status` masih **No serve config**.
- Pembuatan katalog awal sempat mengikuti konfigurasi Alembic lokal dan menambahkan
  kolom migrasi pada `data/runtime/minori.db`. Kolom baru dipastikan kosong, perubahan
  dikembalikan melalui downgrade yang dijaga, dan fingerprint seluruh baris bisnis,
  foreign key, serta integritas diverifikasi. Revisi semula `placement_reminders`
  telah dipulihkan. Database demo persisten Docker tidak terkena; tidak ada reset data.

Log/bukti lokal versi final berada di `test-results/public-docker-final/`,
`test-results/public-runtime-preflight.log`, dan screenshot `test-results/public-*.jpg`;
semuanya diabaikan Git. Pengujian HTTPS internet melalui Funnel sengaja belum
dijalankan karena aktivasi harus dilakukan pengelola secara manual.
