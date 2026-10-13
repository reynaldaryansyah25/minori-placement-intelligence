# Hasil verifikasi fondasi MINORI

Dieksekusi pada **13 Oktober 2026**, zona **Asia/Bangkok (UTC+07:00)**.
Pemeriksaan lokal tercatat pukul 17:59; pemeriksaan container terakhir pukul 18:09.

## Lingkungan

Python lokal **3.12.10** dalam `.venv`; Python container **3.12.15**.
Docker Engine **29.7.2**, Compose **5.5.0**, n8n **2.43.4**.
Image Python dikunci dengan digest. `requirements.lock` memuat **65** versi hasil resolusi.

| Dependency langsung | Versi terpasang |
| --- | --- |
| FastAPI | 0.143.0 |
| Uvicorn | 0.54.0 |
| SQLAlchemy | 2.1.4 |
| Alembic | 1.20.0 |
| Pydantic | 2.14.1 |
| pydantic-settings | 2.15.0 |
| OpenAI SDK | 3.29.0 |
| HTTPX | 0.28.1 |
| Streamlit | 1.65.0 |
| Pytest | 9.1.1 |
| pytest-cov | 7.1.0 |
| Ruff | 0.17.0 |

Setuptools digunakan melalui build isolation. SQLite disediakan oleh Python.

## Perintah dan hasil nyata

| Pemeriksaan | Perintah dieksekusi | Hasil |
| --- | --- | --- |
| Instalasi lokal | `python scripts/bootstrap.py` | Berhasil setelah percobaan ulang dengan izin eksekusi yang diperlukan |
| Dependency lokal | `python -m pip check` | No broken requirements found |
| Lint | `python -m ruff check .` | All checks passed |
| Format | `python -m ruff format --check .` | 51 files already formatted |
| Tes dasar dan arsitektur | `python scripts/verify.py` | **28 passed**, 39.92 detik; tidak ada tes dilewati |
| Coverage | pytest-cov melalui verify | **89%** menurut instrumen |
| Migrasi lokal | `python -m alembic upgrade head` | Revisi foundation aktif |
| Drift skema | `python -m alembic check` | No new upgrade operations detected |
| Query SQLite | `python scripts/check_database.py` | SELECT 1 = 1; foreign keys = 1; journal mode = wal |
| Startup lokal | `python scripts/smoke_test.py` | Backend HTTP 200; Streamlit health ok; frontend HTTP 200; proses dihentikan setelah tes |
| Validasi Compose | `docker compose config --quiet` | Exit code 0 |
| Build Linux | `docker compose --progress plain build` | Backend dan frontend berhasil dibangun |
| Image n8n | `docker compose pull n8n` | Berhasil |
| Startup Docker | `docker compose up -d --no-build --wait --wait-timeout 120` | Ketiga layanan healthy |
| Konfigurasi n8n akhir | `docker compose up -d --no-build --wait --wait-timeout 120 n8n` | Healthy setelah pembaruan variabel webhook |
| Pemeriksaan container akhir | `python scripts/verify_containers.py` | Lulus; hasil di containers.json |
| Impor workflow | `docker compose exec -T n8n n8n import:workflow --input=/workflows/backend_health.json` | Successfully imported 1 workflow |
| Diff | `git diff --check` | Tidak ada kesalahan whitespace |
| File pribadi | `git check-ignore` untuk .env, venv, database, log | Diabaikan Git |
| Penamaan | Pencarian istilah terlarang pada sumber dan dokumentasi | Tidak ditemukan |

Container backend dan frontend masing-masing menjalankan `python -m pip check` dan
menghasilkan **No broken requirements found**. Request frontend ke backend dan
n8n ke backend melalui jaringan Compose lulus. Endpoint readiness n8n menghasilkan
`{"status":"ok"}`. SQLite aplikasi lokal dan container hanya memiliki tabel
`alembic_version`; data dummy tidak diimpor.

Respons backend yang benar-benar diterima:

```json
{
  "status": "ok",
  "application": "MINORI Placement Intelligence",
  "version": "0.1.0",
  "database": "ok"
}
```

## Perbaikan dan batas verifikasi

Percobaan awal pembuatan venv gagal karena sandbox Windows menolak penulisan wheel
ensurepip ke direktori sementara. Pembuatan venv serta instalasi ulang dengan izin
eksekusi yang diperlukan berhasil. Dependency Python proyek selesai diinstal.

Tes frontend awal mengalami timeout AppTest bawaan 3 detik saat render pertama.
Timeout tes disesuaikan menjadi 15 detik; pemeriksaan ulang lengkap lulus.
Coverage belum mencatat script UI dinamis AppTest dan subprocess migrasi sebagai
cakupan penuh. Render UI dan migrasi diuji dengan assertion perilaku.

Log n8n mengidentifikasi variabel webhook lama; Compose sudah menggunakan
`N8N_WEBHOOK_URL`. Image masih memberi pemberitahuan deprecasi mode task runner
internal dan beberapa nilai default mendatang. **Python task runner n8n gagal mulai**
karena image tidak menyediakan Python 3, sehingga **Python Code node n8n belum tersedia**.
Workflow health memakai Manual Trigger dan HTTP Request. Backend Python sendiri
tersedia dan berhasil diuji. Runner eksternal tidak ditambahkan karena tidak
diperlukan oleh ruang lingkup fondasi ini.

Workflow berhasil diimpor sebagai draft nonaktif. Koneksi HTTP n8n ke backend diuji;
eksekusi workflow melalui editor belum dijalankan. Buat akun owner di UI n8n untuk
penggunaan interaktif.

**9Router sebenarnya belum diuji** karena key dan model pengguna belum diisi.
Kontrak adapter diuji dengan server HTTP lokal, key dan model fiktif. LLM tetap
dinonaktifkan; tidak ada request ke provider sebenarnya.

Ketiga container dibiarkan berjalan pada localhost. Bukti lokal tersimpan di
`installation.log`, `checks.json`, `pytest.xml`, `coverage.xml`, `coverage/index.html`,
`smoke.json`, dan `containers.json`. Artefak runtime tersebut diabaikan Git.
