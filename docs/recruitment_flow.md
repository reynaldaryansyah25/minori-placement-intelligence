# Alur kandidat, pencocokan, penempatan, dan email kegiatan

## Penyebab alur sebelumnya terputus

Form kandidat hanya menyimpan profil singkat tanpa tes bahasa, sertifikat, atau pengalaman.
Pembuatan/perubahan kandidat dan lowongan juga belum memperbarui evaluasi matching.
Daftar pencocokan semula mengutamakan peringkat kandidat eligible dan riwayat evaluasi,
sehingga kandidat baru yang belum dievaluasi tidak terlihat. Pilihan baris pertama pada
tabel dapat menggantikan kandidat yang baru dipilih melalui navigasi antarhalaman.

Persetujuan matching belum memiliki antrean yang terlihat pada Alur Penempatan.
Pusat Pengingat hanya menampilkan notifikasi yang sudah ada; staf belum dapat memilih
peserta dan jadwal dokumen, orientasi, atau keberangkatan untuk menyiapkan email.

## Penggunaan oleh staf

1. Pada **Kandidat**, klik **Tambah kandidat** atau **Edit profil dan kualifikasi**.
   Lengkapi tes JLPT/JFT-Basic, sertifikat, pengalaman, dan preferensi sesuai data asli.
   Pilih **Lowongan untuk ditinjau**, lalu **Simpan dan tinjau pencocokan**.
2. **Pencocokan Kandidat** membuka kandidat dan lowongan tersebut. Tampilan
   **Semua kandidat** menyertakan kandidat yang perlu melengkapi persyaratan.
   Evaluasi, skor, dan kelayakan tetap dihitung oleh algoritma deterministik.
3. Staf meninjau lalu menyetujui hasil. **Alur Penempatan** menampilkan persetujuan
   pada bagian **Kandidat disetujui staf**. Klik **Mulai persiapan penempatan**.
   Kandidat yang tidak eligible, mempunyai penempatan aktif, atau menghadapi kuota
   penuh tetap mengikuti pembatasan bisnis yang berlaku.
4. Jadwalkan wawancara, pemeriksaan kesehatan, dokumen, orientasi, dan keberangkatan
   pada peserta yang dipilih. Isi tanggal, jam, dan lokasi resmi.
5. Klik **Buka pengingat dan email peserta**. Pada **Pusat Pengingat**, pilih kandidat
   dan jadwal, lalu **Siapkan email untuk jadwal ini**. Gunakan **Susun Email dengan AI**
   atau **Gunakan template**, edit pesan, centang persetujuan, lalu klik
   **Kirim Pengingat Sekarang**.
6. Pesan yang disetujui masuk antrean untuk n8n. Status **Terkirim ke server email**
   berarti SMTP dan callback berhasil, bukan bukti kandidat sudah membaca email.

Kandidat baru tidak otomatis disetujui atau ditempatkan. Kualifikasi yang belum diisi
tetap menjadi kekurangan persyaratan yang dapat diperbaiki melalui form kandidat.

## Kontrak backend

- `GET /matching/vacancies/{vacancy_id}/candidates`: evaluasi terkini untuk seluruh
  kandidat, termasuk yang belum memiliki riwayat evaluasi; mendukung paginasi.
- `GET /placements/approved-candidates`: persetujuan staf yang belum mempunyai
  penempatan untuk pasangan kandidat/lowongan tersebut, beserta alasan pembatasan.
- `POST /placements/{placement_id}/activities/{activity_id}/email/prepare`: menyiapkan
  notifikasi idempoten untuk revisi jadwal yang dipilih; memerlukan otorisasi staf.

Pembuatan/perubahan kandidat dan lowongan memperbarui evaluasi di transaksi yang sama.
Kegagalan evaluasi membatalkan penulisan profil; tidak ada kandidat tersimpan separuh.
Tidak ada perubahan skema database untuk perbaikan alur ini.

Wawancara H-3 dan pemeriksaan kesehatan H-1 tetap otomatis. Email dokumen, orientasi,
dan keberangkatan disiapkan secara manual dari jadwal resmi. Ketiganya tidak dapat
masuk hasil `due` atau diklaim sebelum snapshot pesan disetujui staf, meskipun
availability salah terisi lebih awal. Persetujuan membuat pekerjaan segera tersedia.
Perubahan revisi jadwal membatalkan notifikasi lama melalui mekanisme existing.

## n8n, Mailpit, dan pengujian

Workflow dan kredensial n8n pengguna tidak diubah. Semua jenis email menggunakan kontrak
due → claim → SMTP/simulasi → complete/fail yang sama. Ikuti konfigurasi node pada
[ai_operations.md](ai_operations.md): validasi `delivery_allowed`, `dry_run`, dan
`recipient_routing.effective_recipient`; gunakan snapshot `message.subject/body`
serta `claim_token` dari klaim terkait. Pengiriman segera memerlukan polling singkat
terautentikasi pada workflow existing; jadwal harian saja menunda pesan manual.

Pengujian menggunakan `compose.ai-test.yaml`, token dari `.env` yang sama, database
tmpfs terpisah, dan SMTP `mailpit-ai-test:1025`. Tujuan efektif wajib
`mailpit@minori.local`; kontak kandidat sintetis `.invalid` tidak menjadi tujuan SMTP.
Database demo persisten dan volume n8n tidak direset.

```powershell
python scripts/verify.py
docker compose config --quiet
docker compose -f compose.ai-test.yaml config --quiet
docker compose -f compose.ai-test.yaml build backend-ai-test frontend-ai-test
docker compose -f compose.ai-test.yaml up -d --wait
docker compose -f compose.ai-test.yaml run --rm --no-deps -e LLM_ENABLED=false backend-ai-test python scripts/verify.py
```

Buka aplikasi uji di `http://localhost:18501` dan Mailpit di
`http://localhost:18035`. Jangan menggunakan `down -v` atau `--remove-orphans`;
stack demo dan n8n mempunyai nama project Compose yang sama.

Tes regresi mencakup refresh matching atomik, kandidat belum memenuhi syarat,
persetujuan dan antrean penempatan, persiapan lima kegiatan, RBAC, idempotensi,
snapshot pesan, penghalang klaim sebelum persetujuan, dan navigasi antarhalaman.

## Hasil verifikasi 14 Oktober 2026

- Image backend/frontend dibangun ulang dan stack demo diperbarui tanpa reset volume.
- `python scripts/verify.py` di container uji: **344 tes lulus**, seluruh 11 pemeriksaan
  berhasil, termasuk Ruff, format, Alembic upgrade/check, seed idempoten, matching,
  dan reminder. Durasi Pytest 523,01 detik. Semua tes otomatis menggunakan mock LLM.
- Eksekusi Windows: 343 lulus dan satu tes awal Streamlit timeout saat build image
  berjalan bersamaan. Tes yang sama dijalankan ulang sendiri: lulus dalam 5,22 detik.
- Konfigurasi Compose utama, demo, dan AI test lolos `config --quiet`.
- Browser nyata: edit profil berkualifikasi → pilih lowongan → simpan dan tinjau →
  setujui kandidat sintetis → antrean persetujuan → mulai penempatan → simpan jadwal
  dokumen → buka email peserta → edit subject → konfirmasi. Pengiriman tanpa centang
  persetujuan ditolak. Kandidat dan lowongan tetap terpilih sepanjang navigasi.
- Probe HTTP/SMTP terpisah dari dalam container n8n memproses **lima** snapshot email
  yang disetujui, masing-masing satu percobaan sukses. Kelimanya masuk Mailpit lokal;
  callback `sent` serta callback ulang idempoten berhasil. Workflow pengguna tidak
  dijalankan atau diubah oleh probe ini.
- AI nyata melalui konfigurasi gateway existing berhasil menyusun email orientasi.
  Skor matching kandidat uji tetap 86/100 dan keputusan staf tidak berubah oleh AI.

| Kegiatan | ID pesan Mailpit |
| --- | --- |
| Dokumen | `1iuYItGFimwiymqjRUsIl0` |
| Wawancara | `1PN6boNJ02YBgUXKilIz3U` |
| Keberangkatan | `0y4fdbT8pvXUpXWYityRJm` |
| Pemeriksaan kesehatan | `0u4QIpi1hmgX7tASTYqYuk` |
| Orientasi | `4FzzaRDzZWaLYINIWYZiZ4` |

Seluruh tujuan efektif adalah `mailpit@minori.local`. Data pengujian alur dibuat
pada database AI test sementara; kandidat dan penempatan tambahan tidak dimasukkan
ke database demo persisten. Bukti lokal tersimpan pada `test-results/recruitment-e2e.json`
dan `test-results/recruitment-docker/` yang diabaikan Git.
