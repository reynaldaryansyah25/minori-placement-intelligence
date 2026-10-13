# API Matching

Swagger UI lokal: http://127.0.0.1:8000/docs. Matching tidak memanggil LLM.
Kontrak memakai JSON, UUID, dan datetime sadar timezone.

| Method | Path | Fungsi |
| --- | --- | --- |
| GET | /health | Health backend/database |
| POST | /matching/evaluations | Evaluasi dan simpan history satu pasangan atau cakupan terpilih |
| GET | /matching/results | History; filter candidate_id/vacancy_id, limit 1..100, offset >=0 |
| GET | /matching/results/{evaluation_id} | Snapshot tersimpan dengan freshness saat ini |
| GET | /matching/vacancies/{vacancy_id}/ranking | Ranking live eligible yang tidak rejected; limit/offset |
| GET | /matching/candidates/{candidate_id}/vacancies/{vacancy_id}/explanation | Explanation live |
| PUT | /matching/candidates/{candidate_id} | Ganti profil penuh dan recompute seluruh lowongan secara atomik |
| PUT | /matching/vacancies/{vacancy_id} | Ganti lowongan penuh dan recompute seluruh kandidat secara atomik |

POST menerima `{}` untuk semua pasangan. candidate_id saja mengevaluasi seorang
kandidat terhadap seluruh lowongan; vacancy_id saja mengevaluasi seluruh kandidat
terhadap satu lowongan; keduanya untuk satu pasangan. as_of opsional menggunakan
waktu server jika tidak diisi; waktu masa depan ditolak. Profil yang dievaluasi
adalah profil saat request dengan waktu acuan yang diberikan.

```json
{
  "candidate_id": "<UUID kandidat>",
  "vacancy_id": "<UUID lowongan>",
  "as_of": "2026-10-13T00:00:00Z"
}
```

Ganti placeholder dengan UUID valid. POST/PUT mengembalikan
`{"evaluated_count": jumlah, "results": [...]}`. GET collection mengembalikan array.
Ranking memuat rank global mulai satu sebelum pagination. History diurutkan
evaluated_at menurun, created_at menurun, UUID menaik. GET tidak menulis history.

Result memuat candidate_id, vacancy_id, candidate_reference, vacancy_reference,
eligibility_status, total_score, staff_status, match_id, evaluation_id,
algorithm_version, evaluated_at, input_fingerprint, is_stale, active_recommendation,
dan explanation. evaluation_id null pada respons live; match_id null jika belum
ada asosiasi staf tersimpan. Total score hanya tersedia bagi ELIGIBLE.

Explanation memuat reason_codes, checks, unmet_requirements, verification_needed,
score_components, score_used_for_ranking, dan policy. Component memuat name, weight,
score, contribution, formula, evidence. Check memuat code, outcome, requirement,
message, evidence. Kontrak ini dapat menjadi input advisor tanpa menafsirkan teks
alasan bebas.

PUT menerima CandidateCreate/VacancyCreate lengkap seperti fixture JSON tanpa
id/created_at/updated_at. Koleksi yang tidak diisi kembali ke default kosong;
ini penggantian aggregate penuh. Reference dan kepemilikan history dipertahankan.
Field tambahan opsional: preferred_prefectures pada kandidat; preferred_skills,
preferred_certifications, language_test_max_age_months pada lowongan.

| HTTP | Makna |
| --- | --- |
| 200 | Evaluasi/query/update selesai |
| 404 | Candidate/vacancy/evaluation tidak ditemukan |
| 422 | Input/UUID/timestamp/pagination invalid atau reference berubah |
| 409 | Konflik database; transaksi di-rollback |
| 503 | Database sementara tidak tersedia; request dapat diulang |

Konflik/kegagalan database tidak mengekspos SQL atau payload internal. Mutasi
berhasil setelah commit. Endpoint tidak mengubah approved/rejected, membuat
placement, atau mengirim reminder. Lihat [algoritma](matching.md).

Contoh PowerShell:

```powershell
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/matching/evaluations -ContentType application/json -Body '{"as_of":"2026-10-13T00:00:00Z"}'
$result.evaluated_count
$eligible = $result.results | Where-Object eligibility_status -eq ELIGIBLE
$vacancyId = $eligible[0].vacancy_id
Invoke-RestMethod "http://127.0.0.1:8000/matching/vacancies/$vacancyId/ranking"
```
