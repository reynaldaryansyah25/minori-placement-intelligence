# Penempatan dan reminder

## Alur penempatan

Staf menyimpan keputusan melalui `POST /matching/decisions`.
Penempatan memerlukan pasangan approved, kelayakan terkini `ELIGIBLE`,
kuota tersedia, dan kandidat tanpa penempatan aktif lain.

Status: `preparing → in_progress → completed`.
Preparing/in_progress dapat menjadi cancelled. Completed dan cancelled terminal;
completed tetap memakai kuota. Pembatalan mempertahankan riwayat.

Aktivitas meliputi wawancara, pemeriksaan kesehatan, dokumen, orientasi, dan
keberangkatan. Jadwal baru/perubahan harus di masa depan.
Revisi jadwal/lokasi menaikkan `schedule_revision`.

## Jadwal otomatis

- Wawancara H-3 dan pemeriksaan kesehatan H-1 pada default 09.00 WIB.
- Perhitungan menggunakan hari kalender, termasuk akhir pekan.
- Jika waktu reminder lewat tetapi kegiatan masih mendatang, antrean tersedia segera.
- Kegiatan yang sudah dimulai tidak dikirimi pengingat terlambat.

`PlacementService.create_activity()` dan `ReminderService.sync_activity()`
menyimpan aktivitas serta reminder dalam transaksi yang sama.
Dokumen, orientasi, dan keberangkatan tersedia melalui tindakan email manual.

## Persetujuan manual

Susun AI/template → edit → konfirmasi → **Kirim Pengingat Sekarang**.
Backend menyimpan snapshot, pemberi persetujuan, fingerprint fakta, revisi jadwal,
dan idempotency key. Pekerjaan langsung tersedia; Streamlit tidak mengirim SMTP.

Perubahan jadwal/kandidat/tujuan dapat membatalkan persetujuan lama.
Double click dengan kunci yang sama tidak membuat pekerjaan tambahan.
Sandbox hanya menyerahkan pekerjaan yang sudah disetujui kepada worker.

## Kontrak worker

Endpoint utama memerlukan bearer token internal.
Worker sandbox menggunakan credential tersendiri dan scope sesi server.

| Metode dan endpoint | Fungsi |
| --- | --- |
| `POST /internal/reminders/generate` | Sinkronisasi aktivitas |
| `GET /internal/reminders/due` | Antrean tersedia |
| `POST /internal/reminders/claim` | Klaim dengan `notification_id` |
| `POST /internal/reminders/{id}/complete` | Catat sent/simulated |
| `POST /internal/reminders/{id}/fail` | Catat kegagalan |
| `POST /internal/reminders/recover` | Pulihkan lease |
| `GET /reminders/{id}/attempts` | Riwayat percobaan |

Claim tidak tersedia mengembalikan `null`.
Claim berhasil memuat `notification.id`, `claim_token`, `recipient_routing`,
dan `message.subject/body`.

Sebelum SMTP: `dry_run=false`, `delivery_allowed=true`, mode `mailpit`;
tujuan wajib `recipient_routing.effective_recipient`, bukan kontak sintetis.

```json
{
  "claim_token": "<token claim yang sama>",
  "outcome": "sent",
  "provider_reference": "<referensi provider valid>"
}
```

Dry-run memakai `outcome=simulated`, tanpa SMTP/provider reference.
Callback gagal memakai `claim_token` dan `error_code`:
`PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, atau `PROVIDER_REJECTED`.

## Retry dan status

Claim menambah attempt dan lease, default 120 detik.
Backoff = `min(maksimum, awal × 2^(nomor_percobaan−1))`;
default maksimal tiga percobaan. Token lama dan callback yang tidak konsisten ditolak.
Callback identik dapat diulang secara idempoten sesuai attempt aktif/terakhir.

Revisi jadwal mencabut lease lama. Recovery menandai kehilangan lease sebagai
abandoned lalu menerapkan budget retry. SMTP tidak menjamin exactly-once:
jika SMTP sukses tetapi callback gagal, retry callback terlebih dahulu dan periksa
Mailpit sebelum mengulang pengiriman.

Dashboard membedakan email disiapkan, menunggu pengiriman, terkirim ke server email,
dan gagal. Status sent bukan bukti kandidat telah membaca/menerima pesan di inbox pribadi.

Pengujian menggunakan `scripts/verify.py` dan
[profil n8n/SMTP terpisah](ai_operations.md#pengujian-end-to-end).
