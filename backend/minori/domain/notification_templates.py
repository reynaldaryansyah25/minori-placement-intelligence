"""Indonesian administrative templates with no contact details or medical findings."""

from datetime import datetime
from zoneinfo import ZoneInfo

TEMPLATE_CODES = {
    "interview_h3",
    "medical_h1",
    "schedule_changed",
    "schedule_cancelled",
}


def render_notification(template_code: str, candidate_name: str, context: dict) -> dict[str, str]:
    if template_code not in TEMPLATE_CODES:
        raise ValueError("Unknown notification template")
    activity = "wawancara" if context["activity"] == "interview" else "medical check-up"
    when = datetime.fromisoformat(context["scheduled_at"]).astimezone(ZoneInfo(context["timezone"]))
    schedule = when.strftime("%d-%m-%Y %H:%M") + " " + context["timezone"]
    location = context.get("location") or "akan diinformasikan staf"
    if template_code == "schedule_cancelled":
        subject = f"Pembatalan jadwal {activity}"
        body = (
            f"Jadwal {activity} pada {schedule} dibatalkan. Hubungi staf untuk informasi lanjutan."
        )
    elif template_code == "schedule_changed":
        subject = f"Perubahan jadwal {activity}"
        body = f"Jadwal {activity} diperbarui menjadi {schedule}. Lokasi: {location}."
    else:
        offset = "H-3" if template_code == "interview_h3" else "H-1"
        subject = f"Pengingat {activity} {offset}"
        body = (
            f"Anda dijadwalkan mengikuti {activity} pada {schedule}. Lokasi: {location}. "
            "Mohon konfirmasi kehadiran kepada staf dan ikuti instruksi administratif."
        )
    return {"subject": subject, "body": f"Halo {candidate_name},\n\n{body}\n\nTim MINORI"}
