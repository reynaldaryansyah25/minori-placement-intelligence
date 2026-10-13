# Hasil pemeriksaan

`verification.md` menyimpan ringkasan hasil yang benar-benar dieksekusi. Script
`verify.py` menghasilkan `checks.json`, log pemeriksaan, `pytest.xml`, `coverage.xml`,
dan laporan HTML `coverage/index.html`. Script `smoke_test.py` menghasilkan
`smoke.json` dan log runtime. Bootstrap menyimpan `installation.log`.
`verify_containers.py` menyimpan `containers.json` untuk status layanan, HTTP,
query database, dependency runtime, dan komunikasi frontend ke backend di Docker.

Artefak runtime diabaikan oleh Git. Simpan ringkasan tanpa credentials bila perlu
membagikan hasil. Hasil tes adapter lokal tidak membuktikan akses ke instance
9Router atau validitas kredensial sebenarnya.
