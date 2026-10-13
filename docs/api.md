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

## Placement, aktivitas, dan reminder

Semua POST/PATCH/DELETE berikut serta seluruh /internal/reminders memerlukan
Authorization: Bearer <INTERNAL_API_TOKEN>. Token berasal dari environment dan
bootstrap menghasilkan token privat. Belum dikonfigurasi: 503; salah/hilang: 401.
Shared token ini belum merupakan sistem akun/role staf.

| Method | Path | Kontrak |
| --- | --- | --- |
| POST | /matching/decisions | candidate_id, vacancy_id, decision approved/rejected, actor_reference, reason_code opsional |
| POST | /placements | reference, match_id approved, actor_reference, planned_departure_at opsional |
| GET | /placements | query pada reference placement/kandidat; filter status/candidate_id/vacancy_id; limit/offset |
| GET | /placements/{placement_id} | Detail placement |
| PATCH | /placements/{placement_id} | actor_reference; status/planned_departure_at/actual_departure_at opsional |
| DELETE | /placements/{placement_id} | Body actor_reference; pembatalan logis, history dipertahankan |
| GET | /placements/{placement_id}/activities | Daftar aktivitas administratif |
| POST | /placements/{placement_id}/activities | actor_reference, code, step_type, sequence_number; scheduled_at/due_at/location opsional |
| PATCH | /placements/{placement_id}/activities/{activity_id} | actor_reference; status/scheduled_at/due_at/completed_at/location opsional |
| GET | /audit-logs | Filter entity_type/entity_id; limit/offset |
| GET | /reminders | Filter status/due_before/placement_id; limit/offset |
| GET | /reminders/{notification_id} | Status, jadwal, mode, jumlah attempt dan error code aman |
| GET | /reminders/{notification_id}/attempts | Riwayat attempt dengan limit/offset |
| POST | /internal/reminders/generate | Tanpa body; sinkronisasi reminder dengan aktivitas |
| POST | /internal/reminders/recover | Tanpa body; recovery lease dan invalidasi reminder |
| GET | /internal/reminders/due | Maintenance lalu reminder due; limit/offset |
| POST | /internal/reminders/claim | Body {} atau notification_id; ClaimRead atau null bila tidak tersedia |
| POST | /internal/reminders/{notification_id}/complete | claim_token, outcome simulated/sent; provider_reference wajib untuk sent |
| POST | /internal/reminders/{notification_id}/fail | claim_token dan error_code enum aman |
| POST | /internal/reminders/simulate | Body {} atau notification_id; claim + dry-run completion, hasil atau null |

Sukses memakai 200. UUID tidak ditemukan: 404. Transisi ilegal, kuota habis,
approval belum ada, claim invalid, atau konflik constraint: 409. Input, offset,
timezone, atau field tidak dikenal: 422. Gangguan SQLite: 503 tanpa SQL/exception
provider. Jadwal baru/perubahan harus di masa depan.

GET /reminders?due_before adalah filter baca. GET internal/due juga menjalankan
maintenance agar expired/inactive tidak ditawarkan. ClaimRead memuat notification,
claim_token, message {subject, body}. Token asli hanya ada pada respons claim;
GET history tidak memuat claim hash atau body pesan. Provider kelak dipanggil
setelah claim selesai dan diikuti callback; claim bukan bukti pengiriman.

Status notification: pending, processing, simulated, sent, failed, cancelled,
missed. Simulated memiliki sent_at null. Status attempt: processing, simulated,
succeeded, failed, abandoned. finished_at null hanya saat processing. Failure
menerima error code enum termasuk PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT,
PROVIDER_REJECTED; teks error bebas ditolak.

Contoh body aktivitas:

```json
{
  "actor_reference": "staff.synthetic",
  "code": "INTERVIEW",
  "step_type": "interview",
  "sequence_number": 1,
  "scheduled_at": "2026-10-16T14:00:00+07:00",
  "location": "Ruang Contoh"
}
```

Sesuaikan tanggal menjadi masa depan. Medical menggunakan step_type medical_check
tanpa field hasil/diagnosis. Documents memakai scheduled_at untuk awal pengumpulan
dan due_at sebagai deadline. Lihat [placement/reminder](placements_reminders.md)
untuk aturan kalender, retry, idempotensi, dan batas pengiriman eksternal.
