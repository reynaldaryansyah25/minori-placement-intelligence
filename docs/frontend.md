# Panduan Operasional Frontend MINORI Placement Intelligence

Dokumen ini menjelaskan arsitektur antarmuka, design system, hierarki navigasi,
kontrol otorisasi (RBAC), serta cara pengoperasian seluruh 8 halaman pada
**MINORI Placement Intelligence**.

---

## 1. Design Direction — Japanese Minimalist Enterprise

Antarmuka dibangun dengan Streamlit (Python 3.12) menggunakan filosofi desain
**Japanese Minimalist Enterprise** yang terinspirasi dari Ashby ATS dan Greenhouse Recruiting:
tenang, modern, fungsional, dan padat informasi (*information-dense*).

### Design Tokens
- **Primary Navy:** `#13263F` (Header, sidebar branding, kartu judul)
- **Primary Teal:** `#0F766E` (Aksen utama, tombol primer, metrik lolos)
- **Main Background:** `#F5F7FA` (Latar belakang netral yang tenang)
- **Surface / Card Background:** `#FFFFFF` (Permukaan kartu dan panel data)
- **Primary Text:** `#1E293B` (Tipografi teks utama, kontras tinggi)
- **Secondary Text:** `#64748B` (Keterangan, subtitle, metadata pembantu)
- **Border:** `#E2E8F0` (Garis tepi tipis 1px, pembatas rapi)
- **Success:** `#15803D` (Badge status Eligible, Sent, Ready, Selesai)
- **Warning:** `#B7791F` (Badge Needs Review, Paused, Preparing, Pending)
- **Danger:** `#B91C1C` (Badge Not Eligible, Closed, Inactive, Gagal)

### Prinsip No AI-Slop
Antarmuka menolak ornamen berlebihan:
- Tanpa gradien neon ungu-biru atau efek glassmorphism kabur.
- Tanpa emoji sebagai ikon navigasi utama; navigasi menggunakan Streamlit Material icons konsisten.
- Tanpa kartu KPI raksasa kosong; setiap angka berasal langsung dari database SQLite.
- Tanpa kalimat pemasaran bombastis; seluruh teks menggunakan Bahasa Indonesia operasional.

---

## 2. Struktur Modul Frontend

Frontend diorganisir dalam paket `frontend/minori_frontend/` dengan pemisahan tanggung jawab yang tegas:

```text
frontend/
├── .streamlit/
│   └── config.toml                  # Tema Streamlit resmi (#0F766E, #F5F7FA)
└── minori_frontend/
    ├── app.py                       # Application shell & st.navigation entrypoint
    ├── config.py                    # FrontendSettings (Pydantic)
    ├── api_client.py                # HTTP client dengan error mapping & token injection
    ├── auth.py                      # Session state RBAC & demo profile switcher
    ├── components/                  # Komponen UI reusable
    │   ├── candidate_profile.py     # Drawer rincian kualifikasi & pengalaman
    │   ├── confirmation.py          # Dialog konfirmasi aksi destruktif
    │   ├── data_table.py            # Tabel interaktif dengan st.dataframe
    │   ├── empty_state.py           # State visual saat data kosong
    │   ├── feedback.py              # Alert banner & technical error modal
    │   ├── filters.py               # Bar pencarian & filter modular
    │   ├── layout.py                # Injeksi CSS token enterprise
    │   ├── matching_explanation.py  # Kartu rincian bobot skor (35%, 30%, 20%, 15%)
    │   ├── metric_card.py           # Kartu KPI ringkas bergaya Ashby
    │   ├── navigation.py            # Definisi st.Page untuk seluruh 8 halaman
    │   ├── notification_history.py  # Detail log & pembeda dry-run vs live
    │   ├── page_header.py           # Header judul, deskripsi, dan status koneksi
    │   ├── placement_timeline.py    # Pipeline stepper & kartu aktivitas
    │   └── status_badge.py          # Pil status berkode warna semantik
    ├── pages/                       # 8 Halaman Operasional
    │   ├── overview.py              # Operational Command Center
    │   ├── candidates.py            # Direktori & profil kandidat
    │   ├── vacancies.py             # Job explorer & spesifikasi lowongan
    │   ├── candidate_matching.py    # Halaman unggulan ranking & explainability
    │   ├── placement_pipeline.py    # Pipeline penempatan & penjadwalan
    │   ├── reminder_center.py       # Monitoring pengingat & dry-run simulation
    │   ├── ai_vacancy_intelligence.py # Input teks Jepang & draft lowongan manual
    │   └── reports.py               # Analitik & ekspor CSV resmi
    └── utils/                       # Utilitas pembantu
        ├── constants.py             # 47 Prefektur Jepang, katalog program, bobot skor
        ├── dates.py                 # Konversi waktu sadar zona Asia/Jakarta (WIB)
        ├── formatting.py            # Skala skor 0-100, format yen, pembersih UUID
        └── validation.py            # Validator formulir & rentang tanggal
```

---

## 3. Akses Role-Based Access Control (RBAC)

Aplikasi menyediakan peralihan peran langsung pada sidebar bawah:
1. **HR Staff (Admin/Tulis):**
   - Menggunakan `INTERNAL_API_TOKEN` server-side.
   - Memiliki izin penuh untuk membuat, memperbarui, menyetujui match, menjadwalkan aktivitas, dan mempublikasikan lowongan.
2. **Reviewer (Read-Only):**
   - Menggunakan `REVIEWER_API_TOKEN` server-side.
   - Memiliki izin membaca seluruh dasbor, peringkat, profil, dan laporan.
   - Endpoint mutasi backend secara otomatis menolak aksi dengan status `403 Forbidden`. Frontend secara visual mengunci tombol tindakan dan menampilkan badge penanda mode tinjau.
3. **Kustom Token Expander:**
   - Memungkinkan penguji memasukkan token Bearer kustom untuk diverifikasi langsung ke endpoint `GET /auth/me`.

---

## 4. Panduan Operasional Per Halaman

### 1. Overview (Dashboard Operasional)
- **Metrik Utama:** Total Kandidat, Kandidat Siap (Ready), Lowongan Terbuka, Penempatan Aktif, Eligible Matches, dan Pengingat Menunggu.
- **Action Center:** Menampilkan kandidat yang memerlukan verifikasi manual serta pengingat bermasalah.
- **Jadwal Mendatang:** Tabel 7 hari ke depan untuk janji temu wawancara kerja dan medical check-up pra-keberangkatan.
- **Riwayat Audit:** Menampilkan entri log audit transaksi terbaru dari SQLite.

### 2. Candidates (Direktori Kandidat)
- **Pencarian & Filter:** Cari kandidat berdasarkan nama atau referensi, filter berdasarkan program (TITP, Tokutei Ginou/SSW, Engineer), dan status kesiapan.
- **Tabel Data:** Kolom nama, kode referensi, domisili, program, status, dan keahlian.
- **Drawer Profil:** Membuka riwayat skor JLPT/JFT-Basic, masa berlaku sertifikasi kompetensi, riwayat pekerjaan sebelumnya, dan prefektur tujuan di Jepang.
- **Tambah/Arsipkan Kandidat:** Form pembuatan kandidat baru dan tombol arsip (status `inactive`) dengan dialog konfirmasi.

### 3. Vacancies (Lowongan Kerja Jepang)
- **Job Explorer:** Daftar lowongan aktif dengan kuota penempatan, lokasi prefektur (Tokyo, Osaka, Aichi, Ibaraki, dsb.), dan sektor industri.
- **Detail Kebutuhan:** Menampilkan syarat bahasa Jepang alternatif, keahlian wajib, sertifikasi OTIT/SSW yang diminta, dan batas waktu lamaran.
- **Aksi Cepat:** Tombol "Lihat Kandidat Cocok" mengarahkan pengguna langsung ke halaman Candidate Matching dengan lowongan yang sudah terpilih.

### 4. Candidate Matching (Halaman Unggulan)
- **Peringkat Deterministik:** Menampilkan kandidat lolos peringkat teratas berdasarkan evaluasi multi-kriteria backend.
- **Rincian Skor Bobot Nyata:**
  - Kemampuan Bahasa Jepang: 35%
  - Pengalaman Kerja Terkait: 30%
  - Sertifikasi & Kualifikasi Tambahan: 20%
  - Kesiapan & Preferensi Lokasi: 15%
- **Explainability Engine:** Penjelasan rinci kriteria yang terpenuhi dan kriteria yang belum lolos (*reason codes*). Kandidat `NEEDS_REVIEW` dan `NOT_ELIGIBLE` tidak diberi skor kelulusan palsu.
- **Keputusan Staf & Pembuatan Penempatan:** Tombol setujui (*Approve*) atau tolak (*Reject*), dan tombol langsung untuk membuat catatan penempatan resmi jika memenuhi kuota dan kelayakan.

### 5. Placement Pipeline
- **Visual Candidate Pipeline:** Stepper tahapan: *Wawancara Employer* ➔ *Medical Check-up* ➔ *Dokumen & COE* ➔ *Orientasi Pra-Terbang* ➔ *Keberangkatan Jepang*.
- **Penjadwalan Aktivitas:** Staf dapat menjadwalkan wawancara dan MCU dengan waktu sadar zona WIB.
- **Privasi Medis Terjaga:** Model dan form hanya menyimpan status jadwal MCU tanpa menyimpan data hasil medis, rekam medis, atau diagnosis kandidat.

### 6. Reminder Center
- **Monitoring Antrean Notifikasi:** Status pil: `pending`, `simulated`, `sent`, `failed`, `missed`.
- **Pembedaan Tegas Simulasi vs Pengiriman Nyata:** Status `simulated` secara eksplisit ditandai sebagai uji coba kalender dry-run, bukan pengiriman nyata.
- **Aksi Operasional:** Tombol sinkronisasi antrean, pemulihan sewa (*recover lease*), dan eksekusi simulasi dry-run secara terkontrol.

### 7. AI Vacancy Intelligence
- **Input Teks Lowongan Asli:** Area masukan untuk menempel teks lowongan berbahasa Jepang dari perusahaan penerima.
- **Status Integrasi AI:** Menampilkan pemberitahuan transparan bahwa integrasi ekstraksi AI otomatis saat ini menunggu penyelesaian endpoint 9Router backend.
- **Alur Draf Lowongan Manual:** Staf dapat menyunting seluruh atribut draf pekerjaan (kuota, prefektur, syarat bahasa) secara terstruktur, menyimpannya ke database sebagai `draft`, dan mempublikasikannya menjadi lowongan resmi (`open`) melalui tombol persetujuan manusia.

### 8. Reports & Analytics
- **Distribusi Kategori:** Grafik distribusi status kandidat, sebaran sektor pekerjaan, dan ringkasan kendala kualifikasi yang paling sering belum terpenuhi.
- **Ekspor Dokumen CSV:** Menyediakan tombol unduh CSV resmi berstandar RFC 4180 untuk data kandidat, lowongan, dan notifikasi.
