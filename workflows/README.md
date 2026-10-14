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
Sandbox publik menggunakan worker tersendiri, tanpa perubahan workflow n8n utama.
