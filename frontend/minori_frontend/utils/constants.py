"""Domain constants, visual design tokens, and Japanese prefecture catalogs."""

# --- Color Tokens (Japanese Minimalist Enterprise) ---
NAVY = "#13263F"
TEAL = "#0F766E"
BG = "#F5F7FA"
SURFACE = "#FFFFFF"
TEXT_PRIMARY = "#1E293B"
TEXT_SECONDARY = "#64748B"
BORDER = "#E2E8F0"
SUCCESS = "#15803D"
WARNING = "#B7791F"
DANGER = "#B91C1C"

# --- Status Colors & Badges ---
STATUS_COLORS: dict[str, dict[str, str]] = {
    # Eligibility
    "ELIGIBLE": {
        "bg": "#DCFCE7",
        "text": "#15803D",
        "border": "#86EFAC",
        "label": "Memenuhi Persyaratan",
    },
    "NEEDS_REVIEW": {
        "bg": "#FEF3C7",
        "text": "#B45309",
        "border": "#FDE68A",
        "label": "Perlu Verifikasi",
    },
    "NOT_ELIGIBLE": {
        "bg": "#FEE2E2",
        "text": "#B91C1C",
        "border": "#FCA5A5",
        "label": "Belum Memenuhi Persyaratan",
    },
    # Vacancy
    "open": {"bg": "#CCFBF1", "text": "#0F766E", "border": "#99F6E4", "label": "Aktif"},
    "paused": {
        "bg": "#FEF3C7",
        "text": "#B45309",
        "border": "#FDE68A",
        "label": "Ditunda",
    },
    "closed": {"bg": "#F1F5F9", "text": "#64748B", "border": "#CBD5E1", "label": "Ditutup"},
    # Candidate
    "registered": {"bg": "#F1F5F9", "text": "#475569", "border": "#CBD5E1", "label": "Terdaftar"},
    "preparing": {
        "bg": "#FEF3C7",
        "text": "#B45309",
        "border": "#FDE68A",
        "label": "Persiapan",
    },
    "ready": {"bg": "#DCFCE7", "text": "#15803D", "border": "#86EFAC", "label": "Siap Ditempatkan"},
    "inactive": {
        "bg": "#F1F5F9",
        "text": "#94A3B8",
        "border": "#CBD5E1",
        "label": "Nonaktif",
    },
    # Match Staff Decision
    "proposed": {"bg": "#E0F2FE", "text": "#0369A1", "border": "#BAE6FD", "label": "Diusulkan"},
    "approved": {
        "bg": "#DCFCE7",
        "text": "#15803D",
        "border": "#86EFAC",
        "label": "Disetujui Staf",
    },
    "rejected": {"bg": "#FEE2E2", "text": "#B91C1C", "border": "#FCA5A5", "label": "Ditolak Staf"},
    # Placement
    "in_progress": {
        "bg": "#E0E7FF",
        "text": "#4338CA",
        "border": "#C7D2FE",
        "label": "Dalam Proses",
    },
    "completed": {
        "bg": "#DCFCE7",
        "text": "#15803D",
        "border": "#86EFAC",
        "label": "Selesai",
    },
    "cancelled": {"bg": "#FEE2E2", "text": "#991B1B", "border": "#FCA5A5", "label": "Dibatalkan"},
    # Placement Step
    "pending": {
        "bg": "#F1F5F9",
        "text": "#64748B",
        "border": "#CBD5E1",
        "label": "Menunggu Pengiriman",
    },
    "scheduled": {"bg": "#E0F2FE", "text": "#0284C7", "border": "#BAE6FD", "label": "Dijadwalkan"},
    # Reminder Notification
    "simulated": {
        "bg": "#EDE9FE",
        "text": "#6D28D9",
        "border": "#DDD6FE",
        "label": "Simulasi Berhasil",
    },
    "sent": {"bg": "#DCFCE7", "text": "#15803D", "border": "#86EFAC", "label": "Terkirim"},
    "failed": {"bg": "#FEE2E2", "text": "#B91C1C", "border": "#FCA5A5", "label": "Gagal Kirim"},
    "missed": {"bg": "#FEF3C7", "text": "#B45309", "border": "#FDE68A", "label": "Terlewat"},
    "draft": {"bg": "#F1F5F9", "text": "#475569", "border": "#CBD5E1", "label": "Draf"},
    "published": {"bg": "#DCFCE7", "text": "#15803D", "border": "#86EFAC", "label": "Terbit"},
}

# --- Programs ---
PROGRAMS = [
    ("titp", "TITP (Praktek Kerja Teknis / Magang)"),
    ("ssw", "SSW (Tokutei Ginou / Keahlian Khusus)"),
    ("engineer", "Engineer / Specialist in Humanities"),
]

PROGRAM_MAP = {k: v for k, v in PROGRAMS}

# --- Japanese Prefectures ---
JAPAN_PREFECTURES = [
    "Aichi",
    "Akita",
    "Aomori",
    "Chiba",
    "Ehime",
    "Fukui",
    "Fukuoka",
    "Fukushima",
    "Gifu",
    "Gunma",
    "Hiroshima",
    "Hokkaido",
    "Hyogo",
    "Ibaraki",
    "Ishikawa",
    "Iwate",
    "Kagawa",
    "Kagoshima",
    "Kanagawa",
    "Kochi",
    "Kumamoto",
    "Kyoto",
    "Mie",
    "Miyagi",
    "Miyazaki",
    "Nagano",
    "Nagasaki",
    "Nara",
    "Niigata",
    "Oita",
    "Okayama",
    "Okinawa",
    "Osaka",
    "Saga",
    "Saitama",
    "Shiga",
    "Shimane",
    "Shizuoka",
    "Tochigi",
    "Tokushima",
    "Tokyo",
    "Tottori",
    "Toyama",
    "Wakayama",
    "Yamagata",
    "Yamaguchi",
    "Yamanashi",
]

# --- Matching Scoring Weights ---
SCORE_WEIGHTS = {
    "japanese_language": {"weight": 0.35, "label": "Kemampuan Bahasa Jepang (35%)"},
    "relevant_experience": {"weight": 0.30, "label": "Pengalaman Kerja Relevan (30%)"},
    "additional_qualifications": {"weight": 0.20, "label": "Kualifikasi & Sertifikasi (20%)"},
    "readiness_and_preferences": {"weight": 0.15, "label": "Kesiapan & Preferensi Prefektur (15%)"},
}
