# Matching kandidat yang dapat dijelaskan

Matching menggunakan aturan pemberi kerja dan standard library Python. Domain
tidak memanggil LLM, database, atau framework. EligibilityEngine,
WeightedScoringEngine, RankingEngine, dan ExplanationEngine disusun oleh
MatchingEngine. MatchingService mengelola use case melalui port repository.

## Kelayakan dan keputusan staf

`match_evaluations.eligibility_status` memuat ELIGIBLE, NOT_ELIGIBLE, atau
NEEDS_REVIEW. `matches.status` tetap memuat keputusan staf proposed, approved,
atau rejected. Evaluasi tidak membuat atau mengubah Match manual, score lama,
reviewed_at, source, atau relasi placement. Tanpa asosiasi manual, respons
menampilkan staff_status=proposed dan match_id=null sebagai usulan yang belum
memiliki keputusan tersimpan. Rejected mengecualikan pasangan dari ranking aktif
walaupun persyaratan terpenuhi.

Semua pemeriksaan dilakukan, sehingga kegagalan tidak menyembunyikan kebutuhan
verifikasi lainnya. Adanya FAIL menghasilkan NOT_ELIGIBLE; tanpa FAIL tetapi
ada REVIEW menghasilkan NEEDS_REVIEW; selain itu ELIGIBLE. INFO tidak memblokir.

| Pemeriksaan | Aturan |
| --- | --- |
| Program | preferred_program kandidat sama dengan program lowongan |
| Kandidat | inactive gagal; registered/preparing perlu konfirmasi kesiapan; ready lolos |
| Lowongan | hanya open lolos; paused/closed gagal |
| Deadline | lewat jika as_of > deadline; tepat pada deadline diterima; null tanpa batas |
| Bahasa | setidaknya satu alternatif jenis tes mencapai minimum pada skala tes sendiri |
| Sertifikasi wajib | kode sama, issued_on <= tanggal evaluasi, expires_on null atau >= tanggal evaluasi |
| Skill wajib | seluruh kode wajib ada pada skills kandidat |
| Pengalaman | union hari di sektor sama memenuhi minimum_experience_months |

Kode skill/sertifikasi dibandingkan persis; sektor memakai strip dan casefold.
Tidak ada inferensi dari nama pekerjaan. Sertifikasi wajib yang tidak tercatat
atau kedaluwarsa gagal. Sertifikat yang baru berlaku setelah evaluasi perlu review
bila tidak ada bukti valid lainnya. Renewal dengan kode sama dapat memenuhi syarat
melalui sertifikat valid. Masa berlaku inklusif menggunakan tanggal UTC.

Bukti bahasa yang belum ada, belum berlaku, atau melewati kebijakan umur tes perlu
review; bukti valid dengan level terlalu rendah gagal. Pengalaman kosong dengan
minimum positif perlu review. Riwayat tersedia tetapi kurang relevan gagal. Hari
masa depan diabaikan; bila minimum belum terpenuhi dan ada riwayat relevan bertanggal
masa depan, perlu review. Kompetensi yang tidak tercatat tidak dianggap dimiliki.

Level bahasa merupakan hasil tes yang dinyatakan dalam profil; engine tidak
memverifikasi keaslian dokumen. Raw score JLPT tidak menentukan kelulusan karena
nilai per bagian tidak disimpan.

## Bahasa dan pengalaman

Skala JLPT diurutkan N5, N4, N3, N2, N1. Skala JFT-Basic diurutkan A1, A2.1,
A2.2; A2.2 adalah label A2. Alternatif jenis tes berasal dari lowongan, tanpa
konversi buatan antarjenis tes. Referensi:
[JLPT resmi](https://www.jlpt.jp/sp/e/about/levelsummary.html) dan
[Japan Foundation](https://www.jpf.go.jp/jft-basic/e/about/index.html).

Engine memilih level tertinggi yang sudah diambil untuk tiap jenis tes yang
diterima; jika level sama, tanggal terbaru dipilih. Tes lebih baru dengan level
lebih rendah tidak menghapus bukti sebelumnya. language_test_max_age_months adalah
kebijakan pemberi kerja opsional: pengurangan bulan kalender dengan penyesuaian
akhir bulan; tepat pada cutoff diterima. Null tidak menerapkan expiry tes buatan.

Pengalaman memakai interval inklusif started_on sampai min(ended_on, tanggal
evaluasi); ended_on null dihitung sampai evaluasi. Periode relevan yang tumpang
tindih digabung. Bulan normalisasi = hari unik / (365.2425 / 12). Ini definisi
operasional engine, bukan pembulatan masa kerja administratif.

## Scoring

Bobot pada domain/matching.py berjumlah satu:

`S = 0.35 L + 0.30 E + 0.20 X + 0.15 P`

Komponen dibatasi 0..1 dan dibulatkan enam desimal. Kontribusi bobot dan total
dibulatkan delapan desimal. Total disimpan hanya untuk ELIGIBLE; status lain
memiliki total_score null. Komponen diagnostik tetap tersedia bagi advisor dan
tidak menggantikan persyaratan wajib. Score adalah utility terhadap lowongan,
bukan probabilitas keberhasilan penempatan.

| Komponen | Normalisasi |
| --- | --- |
| L: bahasa | Untuk bukti lolos: 0.6 + 0.4 × (indeks kandidat − indeks minimum) / (indeks tertinggi tes − indeks minimum). Jika denominator nol: 0.6, karena tes tidak membuktikan level surplus. Tidak lolos: 0; tanpa persyaratan: 1. Ambil utility maksimum dari alternatif yang diterima; tie memakai nama tes alfabetis. |
| E: pengalaman | min(1, bulan relevan / max(24, 2 × minimum bulan)). Target minimal 24 juga berlaku jika minimum nol. |
| X: tambahan | 0.5 × cakupan preferred_skills + 0.5 × cakupan preferred_certifications valid. Target wajib dikeluarkan dari target tambahan. Daftar target kosong mendapat nilai netral 1 untuk subkomponen itu. Kompetensi di luar target tidak menambah skor. |
| P: preferensi/kesiapan | 0.4 × kesamaan program + 0.3 × kesamaan prefektur + 0.3 × kesiapan. Program/prefektur cocok=1, berbeda=0; prefektur belum diisi=0.5. Kesiapan ready=1, preparing=0.5, registered/inactive=0. |

L adalah utility surplus terhadap threshold pemberi kerja pada tes itu. Utility
sama antarjenis tes tidak menyatakan kemampuan linguistik setara. Raw score tes
berbeda tidak dibandingkan. Daftar tambahan kosong pada data lama tidak mendapat
penalti baru.

Contoh Ayu/AGRI dan Bagus/FOOD: L=0.6, E=1, X=1, P=0.85.
`S = 0.21 + 0.30 + 0.20 + 0.1275 = 0.8375`.

## Ranking dan perubahan data

Ranking live hanya berisi eligible yang tidak rejected. Urutan: total score
menurun, reference kandidat menaik, UUID kandidat menaik. Kuota tidak memotong
ranking atau mengalokasikan placement; gunakan pagination untuk membatasi respons.
Lowongan paused/closed/lewat deadline memiliki ranking kosong.

POST evaluasi memakai satu waktu untuk seluruh pasangan dan satu transaksi.
History append-only melalui repository. Unique key pasangan, fingerprint, waktu,
dan versi algoritma mencegah duplikasi pengulangan identik. Waktu baru menambah
history. Request konkuren dapat berkonflik pada unique key/writer SQLite; pemanggil
dapat mengulang request. Keputusan manual tidak berubah.

Fingerprint SHA-256 memuat input algoritma dengan urutan koleksi canonical.
Nama kandidat, domisili, pendidikan, judul, dan timestamp CRUD tidak menentukan
score. Explanation history tidak menyimpan nama kandidat, diagnosis, kontak,
atau dokumen pribadi.

PUT kandidat menghitung ulang seluruh lowongannya; PUT lowongan menghitung ulang
seluruh kandidatnya. Penggantian aggregate dan hasil evaluasi atomik: kegagalan
mengembalikan keduanya. Reference tidak dapat berubah.

Writer di luar use case dapat memanggil POST dengan candidate_id/vacancy_id untuk
recompute. Tidak ada watcher terhadap SQL eksternal. GET history memberi is_stale
jika input, versi, kelayakan, skor, atau explanation berbeda dari evaluasi saat ini.
active_recommendation false untuk stale/rejected. Ranking dan explanation memakai
data/waktu saat ini tanpa menulis history, sehingga deadline dan perubahan status
tidak mengandalkan snapshot lama. Respons live memiliki evaluation_id null.

as_of dapat memakai waktu lampau dengan profil yang tersedia saat request; tidak
merekonstruksi profil historis. Waktu masa depan/tanpa timezone ditolak. Timestamp
disimpan UTC; tanggal expiry, tes, dan pengalaman memakai tanggal UTC.

## Explanation dan fixture

Respons memuat reason_codes unik dalam urutan pemeriksaan; checks dengan outcome
PASS/FAIL/REVIEW/INFO; unmet_requirements; verification_needed; score_components
dengan formula, evidence, weight, score, contribution; serta score_used_for_ranking.
Pydantic memeriksa konsistensi explanation dan hasil. Katalog reason code berada
di domain/matching.py, termasuk PROGRAM_MISMATCH, CANDIDATE_INACTIVE,
READINESS_UNCONFIRMED, VACANCY_PAUSED, DEADLINE_PASSED, LANGUAGE_ACCEPTED,
LANGUAGE_EVIDENCE_MISSING, CERTIFICATION_EXPIRED, dan EXPERIENCE_OVERLAP_MERGED.

Seluruh 40 kombinasi pada 2026-10-13T00:00:00Z diuji:

| Kandidat | AGRI | FOOD | CARE | WELD | ENG |
| --- | --- | --- | --- | --- | --- |
| Ayu / AGRI | ELIGIBLE 0.8375 | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Bagus / FOOD | NOT_ELIGIBLE | ELIGIBLE 0.8375 | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Citra / CARE | NOT_ELIGIBLE | NOT_ELIGIBLE | NEEDS_REVIEW | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Damar / WELD | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NEEDS_REVIEW | NOT_ELIGIBLE |
| Eka / ENG | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Fitri / HOTEL | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Gilang / TRAINEE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |
| Hana / INACTIVE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE | NOT_ELIGIBLE |

Citra/Damar perlu konfirmasi kesiapan; ENG paused; Hana inactive. Baseline: 2 eligible,
2 needs review, 36 not eligible. Ranking AGRI hanya Ayu, FOOD hanya Bagus, lainnya
kosong. Angka fixture adalah ekspektasi tes, tidak digunakan dalam algoritma.

```sh
python scripts/verify_matching.py
python scripts/verify_matching.py --base-url http://127.0.0.1:8000
docker compose exec -T backend python scripts/verify_matching.py --base-url http://127.0.0.1:8000
```

Script memakai fixture 8 kandidat/5 lowongan yang belum disunting, menjalankan
evaluasi dua kali, memeriksa hasil/ID, serta detail/explanation/ranking lewat HTTP.
Dibatasi development/test. Perubahan fixture yang disengaja membutuhkan pembaruan
ekspektasi. Kontrak API dapat diperiksa melalui `http://localhost:8000/docs`; hasil
verifikasi dapat direproduksi dengan perintah di atas.
