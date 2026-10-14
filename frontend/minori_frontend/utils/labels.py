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
    "food_processing": "Pengolahan makanan",
    "nursing_care": "Perawatan lansia",
    "hospitality": "Perhotelan",
    "building_cleaning": "Kebersihan gedung",
    "automobile_maintenance": "Perawatan otomotif",
    "fishery": "Perikanan",
    "food_service": "Layanan makanan",
    "caregiving": "Perawatan lansia",
    "manufacturing": "Manufaktur",
    "engineering": "Teknik",
    "accommodation": "Perhotelan",
    "construction": "Konstruksi",
    "welding": "Pengelasan",
}
SKILL_LABELS = {
    "vegetable_cultivation": "Budidaya sayuran",
    "teamwork": "Kerja sama tim",
    "food_safety": "Keamanan pangan",
    "elderly_care": "Pendampingan lansia",
    "welding": "Pengelasan",
    "hospitality_service": "Layanan perhotelan",
    "building_cleaning": "Perawatan kebersihan gedung",
    "construction_safety": "Keselamatan konstruksi",
    "automotive_maintenance": "Perawatan otomotif",
    "fish_handling": "Penanganan hasil perikanan",
    "restaurant_service": "Layanan restoran",
    "crop_care_certificate": "Sertifikat perawatan tanaman",
    "food_safety_certificate": "Sertifikat keamanan pangan",
    "elderly_care_certificate": "Sertifikat pendampingan lansia",
    "welding_certificate": "Sertifikat pengelasan",
    "hospitality_service_certificate": "Sertifikat layanan perhotelan",
    "building_cleaning_certificate": "Sertifikat kebersihan gedung",
    "construction_safety_certificate": "Sertifikat keselamatan konstruksi",
    "automotive_maintenance_certificate": "Sertifikat perawatan otomotif",
    "fish_handling_certificate": "Sertifikat penanganan hasil perikanan",
    "restaurant_service_certificate": "Sertifikat layanan restoran",
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
