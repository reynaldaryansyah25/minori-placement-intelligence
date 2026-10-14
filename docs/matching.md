# Matching kandidat

Domain menjalankan pemeriksaan kelayakan, scoring berbobot, ranking, dan penjelasan
tanpa bergantung pada model AI.

## Kelayakan

| Hasil | Makna |
| --- | --- |
| `ELIGIBLE` | Seluruh persyaratan wajib lolos |
| `NEEDS_REVIEW` | Tidak ada kegagalan wajib, tetapi bukti/kesiapan perlu diperiksa |
| `NOT_ELIGIBLE` | Setidaknya satu persyaratan wajib gagal |

Engine memeriksa program, kesiapan kandidat, status lowongan, tenggat, bahasa,
sertifikasi, keahlian, serta pengalaman sektor terkait. Semua pemeriksaan ditampilkan.

- Kandidat `ready` dapat lolos; `registered/preparing` perlu peninjauan; `inactive` gagal.
- Lowongan harus `open`; tepat pada tenggat masih diterima.
- Bahasa memenuhi salah satu alternatif tes yang dinyatakan lowongan.
  Bukti yang belum tersedia/belum berlaku atau melewati batas umur tes perlu ditinjau.
- Semua keahlian wajib harus ada dan sertifikasi wajib harus valid saat evaluasi.
- Pengalaman relevan dihitung tanpa menduplikasi hari tumpang tindih.

JLPT dan JFT-Basic memakai skala sendiri dan tidak dikonversi otomatis.
Keaslian bukti tetap diperiksa staf.

## Skor

Hanya `ELIGIBLE` mempunyai total skor; hasil lain menyimpan `null`.
Komponen diagnostik dapat tersedia untuk peninjauan.

`S = 0.35 L + 0.30 E + 0.20 X + 0.15 P`

| Komponen | Bobot | Perhitungan |
| --- | --- | --- |
| Bahasa (L) | 35% | Utility level terhadap minimum pada tes yang sama |
| Pengalaman (E) | 30% | `min(1, bulan_relevan / max(24, 2 × minimum_bulan))` |
| Kualifikasi tambahan (X) | 20% | Rata-rata cakupan keahlian dan sertifikasi tambahan valid |
| Preferensi/kesiapan (P) | 15% | `0.4 × program + 0.3 × prefektur + 0.3 × kesiapan` |

Utility bahasa = `0.6 + 0.4 × surplus_level / sisa_level`;
sisa level nol bernilai 0.6, tanpa syarat bahasa bernilai 1.
Target tambahan kosong bernilai netral 1; preferensi prefektur kosong bernilai 0.5.
Kesiapan: `ready=1`, `preparing=0.5`, `registered/inactive=0`.
Bulan relevan = hari unik / `(365.2425 / 12)`.
Komponen dibatasi 0–1; dashboard menampilkan total 0–100.

## Peringkat dan keputusan staf

Ranking memakai eligible terkini yang tidak ditolak staf:
skor menurun, referensi kandidat menaik, lalu identitas internal sebagai pemutus seri.
Kuota tidak otomatis mengalokasikan kandidat.

Keputusan `proposed/approved/rejected` terpisah dari kelayakan.
`NEEDS_REVIEW` dapat dicatat approved, tetapi pembuatan penempatan tetap memerlukan
`ELIGIBLE` terkini. Tidak eligible tidak dapat disetujui.

Use case perubahan kandidat/lowongan memperbarui evaluasi pasangan terkait.
Riwayat menyimpan fingerprint, versi, waktu, komponen, bukti, dan alasan.
Ranking/penjelasan membaca data terkini; riwayat yang berbeda ditandai usang.

**Jelaskan dengan AI** hanya menyusun narasi hasil resmi, tanpa mengubah
skor, kelayakan, peringkat, atau keputusan staf.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_matching_engine.py tests/integration/test_matching.py
```

Pengujian lengkap dengan database sementara tersedia melalui `scripts/verify.py`.
Kontrak API tersedia pada `http://localhost:8000/docs`.
