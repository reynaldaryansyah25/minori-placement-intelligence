"""Indonesian staff vocabulary for backend catalog values."""

STEP_LABELS = {
    "interview": "Wawancara",
    "medical_check": "Pemeriksaan kesehatan",
    "documents": "Dokumen",
    "orientation": "Orientasi",
    "departure": "Keberangkatan",
}
TEMPLATE_LABELS = {
    "interview_h3": "Wawancara · H-3",
    "interview_schedule": "Jadwal wawancara",
    "medical_h1": "Pemeriksaan kesehatan · H-1",
    "schedule_changed": "Perubahan jadwal",
    "schedule_cancelled": "Pembatalan jadwal",
}
SECTOR_LABELS = {
    "agriculture": "Pertanian",
    "food_service": "Layanan makanan",
    "caregiving": "Perawatan lansia",
    "manufacturing": "Manufaktur",
    "engineering": "Teknik",
    "accommodation": "Perhotelan",
    "construction": "Konstruksi",
    "welding": "Pengelasan",
}
SKILL_LABELS = {
    "crop_care": "Perawatan tanaman",
    "farm_safety": "Keselamatan pertanian",
    "tractor_operation": "Pengoperasian traktor",
    "food_preparation": "Persiapan makanan",
    "hygiene": "Kebersihan pangan",
    "caregiving_support": "Pendampingan lansia",
    "workplace_communication": "Komunikasi kerja",
    "welding_arc": "Las busur",
    "quality_control": "Pengendalian mutu",
    "cad_design": "Perancangan CAD",
    "machine_operation": "Pengoperasian mesin",
    "guest_service": "Pelayanan tamu",
    "housekeeping": "Tata graha",
    "agriculture_general": "Pertanian umum",
    "agriculture_skill": "Sertifikasi pertanian",
    "food_service_skill": "Sertifikasi layanan makanan",
    "caregiving_skill": "Sertifikasi perawatan lansia",
    "otit_agri_level3": "Sertifikasi pertanian tingkat 3",
}
SOURCE_LABELS = {
    "email": "Email",
    "portal_partner": "Portal mitra",
    "otit": "OTIT",
    "direct": "Pemberi kerja",
}
ACTION_LABELS = {
    "fixture.created": "Data awal ditambahkan",
    "match.reviewed": "Keputusan pencocokan disimpan",
    "match.decided": "Keputusan pencocokan disimpan",
    "placement.created": "Penempatan dibuat",
    "placement.updated": "Penempatan diperbarui",
    "activity.created": "Aktivitas dijadwalkan",
    "activity.updated": "Aktivitas diperbarui",
    "reminder.created": "Pengingat disiapkan",
    "reminder.claimed": "Pengingat diproses",
    "reminder.simulated": "Simulasi pengiriman selesai",
    "reminder.sent": "Pengingat terkirim",
    "reminder.retry_scheduled": "Pengiriman dijadwalkan ulang",
    "reminder.failed": "Pengiriman memerlukan pemeriksaan",
    "reminder.cancelled": "Pengingat dibatalkan",
    "reminder.rescheduled": "Jadwal pengingat diperbarui",
    "reminder.invalidated": "Status pengingat diperbarui",
    "evaluation.recomputed": "Evaluasi pencocokan diperbarui",
}


def catalog_label(value, catalog=SKILL_LABELS):
    if not value:
        return "—"
    return catalog.get(str(value).lower(), str(value).replace("_", " ").capitalize())


def language_label(test):
    return "JFT-Basic" if test == "jft_basic" else str(test or "").upper()


def program_short(value):
    return {"ssw": "SSW", "titp": "TITP", "engineer": "Engineer"}.get(value, "—")
