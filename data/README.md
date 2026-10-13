# Data pengembangan

`dummy/candidates.json` hanya berisi data fiktif. File ini belum menjadi kontrak
domain dan tidak diimpor ke SQLite. `runtime/` dibuat saat aplikasi atau migrasi
berjalan dan diabaikan oleh Git. Database lokal memakai `runtime/minori.db`;
container memakai volume Docker yang persisten. Jangan menyimpan data kandidat
sebenarnya dalam repository atau fixtures pengujian.
