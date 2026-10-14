# Workflow n8n

Kontrak due → claim → send/simulate → complete/fail dijelaskan dalam
[panduan n8n](../docs/ai_operations.md#workflow-n8n).
Pertahankan workflow reminder existing saat memperbarui node.

## Pemeriksaan kesehatan

`n8n/backend_health.json` adalah workflow manual untuk `GET /health`;
bukan workflow reminder dan tidak mengirim email.

Pada instalasi baru, impor melalui **Import from File**, atau:

```powershell
docker compose -f compose.yaml -f compose.demo.yaml exec -T n8n n8n import:workflow --input=/workflows/backend_health.json
```

Impor tidak menjalankan workflow. Buka editor dan pilih **Execute workflow**.
Jika n8n berada di luar Compose, sesuaikan URL backend.

## Credentials dan pengujian

Simpan token HTTP/SMTP pada pengelola credentials, bukan JSON workflow.
Tujuan SMTP memakai `recipient_routing.effective_recipient`, bukan kontak sintetis.

Uji memakai [profil terpisah](../docs/ai_operations.md#pengujian-end-to-end).
Sandbox publik menggunakan layanan `n8n-sandbox`, tanpa perubahan workflow n8n utama.
`sandbox/reminders.json` memproses semua sesi aktif: recovery → due → claim →
validasi tujuan → SMTP Mailpit → complete/fail. Polling 15 detik dan cron 09.00 WIB
berjalan otomatis setelah bootstrap; pengiriman manual tetap memerlukan persetujuan.

`sandbox/prepare.cjs` mengimpor credentials privat dan workflow ke volume sandbox.
JSON hanya memuat ID credential, tanpa token/password. Riwayat bisnis tersimpan
pada backend sesi; payload eksekusi n8n tidak disimpan. Petunjuk restart dan tes
SMTP nyata tersedia pada [panduan sandbox](../docs/interactive_sandbox.md).
