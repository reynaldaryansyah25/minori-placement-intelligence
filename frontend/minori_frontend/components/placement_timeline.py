"""Greenhouse-inspired pipeline stepper and administrative activity timeline."""

from typing import Any

import streamlit as st
from minori_frontend.utils.dates import format_datetime_id


def render_pipeline_stepper(stages: list[dict[str, Any]]) -> None:
    """Render horizontal visual progression stepper across stages."""
    stage_types = [
        ("interview", "Interview"),
        ("medical_check", "Medical Check"),
        ("documents", "Dokumen"),
        ("orientation", "Orientasi"),
        ("departure", "Keberangkatan"),
    ]

    cols = st.columns(len(stage_types))
    by_type = {s.get("step_type"): s for s in stages}

    for idx, (code, label) in enumerate(stage_types):
        item = by_type.get(code)
        status = item.get("status", "pending") if item else "pending"

        if status == "completed":
            circle_style = "background-color: #15803D; color: white;"
            icon = "✓"
        elif status in ("scheduled", "in_progress"):
            circle_style = "background-color: #0F766E; color: white;"
            icon = str(idx + 1)
        else:
            circle_style = "background-color: #E2E8F0; color: #64748B;"
            icon = str(idx + 1)

        with cols[idx]:
            st.markdown(
                f"""
                <div style="text-align: center; padding: 4px;">
                    <div style="width: 28px; height: 28px; border-radius: 50%; {circle_style} margin: 0 auto 4px auto; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px;">
                        {icon}
                    </div>
                    <div style="font-size: 12px; font-weight: 600; color: #13263F;">{label}</div>
                    <div style="font-size: 11px; color: #64748B;">{status.title()}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_activity_card(activity: dict[str, Any]) -> None:
    """Render administrative activity card with scheduled times and venue."""
    step_type = activity.get("step_type", "activity")
    status = activity.get("status", "pending")
    sched = format_datetime_id(activity.get("scheduled_at"))
    due = format_datetime_id(activity.get("due_at"))
    completed = format_datetime_id(activity.get("completed_at"))
    location = activity.get("location")

    st.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <span style="font-weight: 600; color: #13263F; font-size: 14px;">
                    {activity.get("code", "STEP")} — {step_type.replace("_", " ").title()} (Urutan ke-{activity.get("sequence_number", 1)})
                </span>
                <span>
                    <span class="status-pill" style="font-size: 11px;">{status.upper()}</span>
                </span>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: #475569;">
                {f"📅 <b>Jadwal:</b> {sched} &nbsp; " if sched != "—" else ""}
                {f"⏱️ <b>Batas Akhir:</b> {due} &nbsp; " if due != "—" else ""}
                {f"📍 <b>Lokasi/Ruang:</b> {location} &nbsp; " if location else ""}
                {f"✅ <b>Selesai:</b> {completed}" if completed != "—" else ""}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
