# Akses publik melalui Tailscale Funnel

Siapkan [sandbox](interactive_sandbox.md) dan uji login lokal terlebih dahulu.
Funnel hanya meneruskan `127.0.0.1:8502`; layanan lain tetap lokal/internal.

## Login dan otorisasi

Login wajib sebelum halaman bisnis. Password berupa hash scrypt dengan salt acak.
Sesi dibatasi durasi/idle dan login gagal dibatasi lintas sesi browser.

Frontend hanya menerima credential bootstrap sandbox. Token sesi dibuat setelah
login dan disimpan server-side. Role demo bekerja pada database sesi sendiri.
Token reviewer backend utama tetap read-only; token sandbox ditolak backend utama.

Gunakan data sintetis dan domain kontak `.invalid`.
Credentials, kontak sensitif, UUID operasional, dan raw error tidak ditampilkan.

## Hostname

Tailscale harus terpasang, login, dan memenuhi
[persyaratan Funnel](https://tailscale.com/docs/features/tailscale-funnel).
Periksa konfigurasi existing:

```powershell
$tailscaleExe = 'C:/Program Files/Tailscale/tailscale.exe'
& $tailscaleExe funnel status
$demoHostname = (& $tailscaleExe status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')
$demoHostname
```

Isi `PUBLIC_DEMO_HOST` dalam `.env` dengan hostname perangkat, tanpa protokol/path.
Pertahankan domain existing bila sudah digunakan.
Sesudah sesuai, recreate frontend saja:

```powershell
docker compose -f compose.public-demo.yaml up -d --no-deps --force-recreate --wait frontend-public
.\.venv\Scripts\python.exe scripts/verify_public_demo.py
```

CORS/XSRF tetap aktif. Laptop, Docker Desktop, dan service sandbox harus berjalan.

## Mengaktifkan akses

Pengelola menjalankan secara manual setelah verifikasi lulus.
Port HTTPS 443 harus tersedia atau merupakan mapping MINORI:

```powershell
& $tailscaleExe funnel --bg --https=443 http://127.0.0.1:8502
& $tailscaleExe funnel status
```

Bagikan URL HTTPS dan akun secara privat. Uji login, AI, logout, timeout, serta
isolasi sesi dari jaringan lain. Jangan meneruskan 8000, 8501, 5678, 8025, atau 20128.

## Listener lokal

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8501,8502,5678,8025,20128 |
    Select-Object LocalAddress,LocalPort
```

Untuk 9Router loopback gunakan `scripts/start_9router_local.ps1`, lalu uji koneksi
Docker melalui smoke test AI. Script tidak mengganti model/provider atau credentials.

## Mematikan akses

```powershell
$tailscaleExe = 'C:/Program Files/Tailscale/tailscale.exe'
& $tailscaleExe funnel --https=443 off
& $tailscaleExe funnel status
docker compose -f compose.public-demo.yaml stop frontend-public
```

Jangan memakai `funnel reset` bila mapping aplikasi lain masih dibutuhkan.
Restart frontend/backend sandbox mencabut seluruh sesi aplikasi.
Rotasi login memerlukan setup password dan recreate frontend; token utama tetap.

Referensi: [Tailscale Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel).
