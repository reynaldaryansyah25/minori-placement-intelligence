# Data pengembangan

File JSON pada `dummy/` berisi 8 kandidat, 5 lowongan, serta contoh placement,
wawancara, medical check-up, notification, dan history yang sepenuhnya fiktif.
Seed memvalidasi schemas dan memasukkan data hanya ketika dijalankan secara eksplisit.
`runtime/` dibuat saat aplikasi atau migrasi
berjalan dan diabaikan oleh Git. Database lokal memakai `runtime/minori.db`;
container memakai volume Docker yang persisten. Jangan menyimpan data kandidat
sebenarnya dalam repository atau fixtures pengujian.
