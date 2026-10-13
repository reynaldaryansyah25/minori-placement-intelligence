# Workflow n8n

`n8n/backend_health.json` adalah workflow manual yang meminta `/health` pada backend
di jaringan Docker. Tidak ada trigger terjadwal, credentials, atau proses bisnis.

Impor melalui editor n8n dengan **Import from File**. Atau jalankan:

```sh
docker compose exec n8n n8n import:workflow --input=/workflows/backend_health.json
```

Impor tidak menjalankan workflow. Buka workflow dan pilih **Execute workflow** untuk
memeriksa backend. Untuk n8n yang berjalan di luar jaringan Compose, ubah URL node
HTTP Request sesuai alamat backend. Jangan menyimpan secrets di JSON workflow.
