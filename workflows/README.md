# Workflow n8n

Panduan mengonfigurasi dan menguji workflow reminder pada backend demo, n8n, dan Mailpit:
[AI operations](../docs/ai_operations.md).

`n8n/backend_health.json` adalah workflow manual yang meminta `/health` pada backend
di jaringan Docker. Tidak ada trigger terjadwal, credentials, atau proses bisnis.

Impor melalui editor n8n dengan **Import from File**. Atau jalankan:

```sh
docker compose exec n8n n8n import:workflow --input=/workflows/backend_health.json
```

Impor tidak menjalankan workflow. Buka workflow dan pilih **Execute workflow** untuk
memeriksa backend. Untuk n8n yang berjalan di luar jaringan Compose, ubah URL node
HTTP Request sesuai alamat backend. Jangan menyimpan secrets di JSON workflow.

Panduan AI operasional, demo profesional, dan konfigurasi workflow n8n: [AI operations](../docs/ai_operations.md).
