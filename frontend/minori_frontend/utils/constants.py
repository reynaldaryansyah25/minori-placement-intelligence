"""Domain constants, visual design tokens, and Japanese prefecture catalogs."""

# --- Color Tokens (Japanese Minimalist Enterprise) ---
NAVY = "#17283f"
TEAL = "#0F766E"
BG = "#f6f8fb"
SURFACE = "#FFFFFF"
TEXT_PRIMARY = "#1c2a3d"
TEXT_SECONDARY = "#617087"
BORDER = "#e3e9f0"
SUCCESS = "#187451"
WARNING = "#B7791F"
DANGER = "#aa3b44"

# --- Status Colors & Badges ---
STATUS_COLORS: dict[str, dict[str, str]] = {
    # Eligibility
    "ELIGIBLE": {
        "bg": "#eaf7f1",
        "text": "#187451",
        "border": "#86EFAC",
        "label": "Memenuhi Persyaratan",
    },
    "NEEDS_REVIEW": {
        "bg": "#fff6e6",
        "text": "#a56815",
        "border": "#FDE68A",
        "label": "Perlu Verifikasi",
    },
    "NOT_ELIGIBLE": {
        "bg": "#fff0f1",
        "text": "#aa3b44",
        "border": "#FCA5A5",
        "label": "Belum Memenuhi Persyaratan",
    },
    # Vacancy
    "open": {"bg": "#eaf7f4", "text": "#0F766E", "border": "#99F6E4", "label": "Aktif"},
    "paused": {
        "bg": "#fff6e6",
        "text": "#a56815",
        "border": "#FDE68A",
        "label": "Ditunda",
    },
    "closed": {"bg": "#F1F5F9", "text": "#617087", "border": "#CBD5E1", "label": "Ditutup"},
    # Candidate
    "registered": {"bg": "#F1F5F9", "text": "#475569", "border": "#CBD5E1", "label": "Terdaftar"},
    "preparing": {
        "bg": "#fff6e6",
        "text": "#a56815",
        "border": "#FDE68A",
        "label": "Persiapan",
    },
    "ready": {"bg": "#eaf7f1", "text": "#187451", "border": "#86EFAC", "label": "Siap Ditempatkan"},
    "inactive": {
        "bg": "#F1F5F9",
        "text": "#94A3B8",
        "border": "#CBD5E1",
        "label": "Nonaktif",
    },
    # Match Staff Decision
    "proposed": {"bg": "#eff5ff", "text": "#0369A1", "border": "#BAE6FD", "label": "Diusulkan"},
    "approved": {
        "bg": "#eaf7f1",
        "text": "#187451",
        "border": "#86EFAC",
        "label": "Disetujui Staf",
    },
    "rejected": {"bg": "#fff0f1", "text": "#aa3b44", "border": "#FCA5A5", "label": "Ditolak Staf"},
    # Placement
    "in_progress": {
        "bg": "#eff5ff",
        "text": "#4338CA",
        "border": "#C7D2FE",
        "label": "Dalam Proses",
    },
    "completed": {
        "bg": "#eaf7f1",
        "text": "#187451",
        "border": "#86EFAC",
        "label": "Selesai",
    },
    "cancelled": {"bg": "#fff0f1", "text": "#991B1B", "border": "#FCA5A5", "label": "Dibatalkan"},
    # Placement Step
    "pending": {
        "bg": "#F1F5F9",
        "text": "#617087",
        "border": "#CBD5E1",
        "label": "Menunggu",
    },
    "scheduled": {"bg": "#eff5ff", "text": "#0284C7", "border": "#BAE6FD", "label": "Dijadwalkan"},
    # Reminder Notification
    "simulated": {
        "bg": "#eff3f8",
        "text": "#50627b",
        "border": "#DDD6FE",
        "label": "Simulasi Berhasil",
    },
    "sent": {
        "bg": "#eaf7f1",
        "text": "#187451",
        "border": "#86EFAC",
        "label": "Terkirim ke server email",
    },
    "failed": {"bg": "#fff0f1", "text": "#aa3b44", "border": "#FCA5A5", "label": "Gagal Kirim"},
    "missed": {"bg": "#fff6e6", "text": "#a56815", "border": "#FDE68A", "label": "Terlewat"},
    "draft": {"bg": "#F1F5F9", "text": "#475569", "border": "#CBD5E1", "label": "Draf"},
    "published": {"bg": "#eaf7f1", "text": "#187451", "border": "#86EFAC", "label": "Terbit"},
    "processing": {"bg": "#eff5ff", "text": "#416aa3", "border": "#eff5ff", "label": "Diproses"},
    "succeeded": {
        "bg": "#eaf7f1",
        "text": "#187451",
        "border": "#eaf7f1",
        "label": "Terkirim ke server email",
    },
    "abandoned": {
        "bg": "#fff6e6",
        "text": "#a56815",
        "border": "#fff6e6",
        "label": "Dijadwalkan ulang",
    },
}

# --- Programs ---
PROGRAMS = [
    ("titp", "TITP (Praktik kerja teknis)"),
    ("ssw", "SSW (Tokutei Ginou / Keahlian Khusus)"),
    ("engineer", "Engineer (tenaga ahli)"),
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
