"""Administrative timeline and activity cards, using live schedules."""

from minori_frontend.components.presentation import html, text
from minori_frontend.components.status_badge import get_status_badge_html
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.labels import STEP_LABELS


def render_pipeline_stepper(stages):
    markup = []
    for number, (kind, label) in enumerate(STEP_LABELS.items(), 1):
        active = [
            s for s in stages if s.get("step_type") == kind and s.get("status") != "cancelled"
        ]
        done = bool(active) and all(s.get("status") == "completed" for s in active)
        current = any(s.get("status") in {"scheduled", "in_progress"} for s in active)
        state = "done" if done else "current" if current else ""
        caption = "Selesai" if done else "Berjalan / terjadwal" if current else "Belum dijadwalkan"
        markup.append(
            f'<div class="timeline-step {state}"><div class="step-circle">{number}</div>'
            f'<div class="step-title">{text(label)}</div><div class="step-sub">{caption}</div></div>'
        )
    html('<div class="timeline" aria-label="Tahapan penempatan">' + "".join(markup) + "</div>")


def render_activity_card(activity):
    details = [format_datetime_id(activity.get("scheduled_at"))]
    if activity.get("location"):
        details.append(activity["location"])
    if activity.get("due_at"):
        details.append("Batas akhir: " + format_datetime_id(activity["due_at"]))
    if activity.get("completed_at"):
        details.append("Selesai: " + format_datetime_id(activity["completed_at"]))
    html(
        f'<div class="event-row"><div><strong>{text(STEP_LABELS.get(activity.get("step_type"), "Aktivitas"))}</strong>'
        f"<p>{text(' · '.join(details))}</p></div>{get_status_badge_html(activity.get('status'))}</div>"
    )
