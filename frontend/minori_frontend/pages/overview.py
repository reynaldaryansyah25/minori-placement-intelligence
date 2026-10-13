"""Operational command center dashboard for Minori placement operations."""

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.components.feedback import show_api_error
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metric_card
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_status_label

ACTION_LABELS = {
    "fixture.created": "Pembuatan Catatan Data",
    "reminder.claimed": "Pengambilan Antrean Pengingat",
    "reminder.simulated": "Simulasi Pengiriman Selesai",
    "reminder.sent": "Pengiriman Notifikasi Berhasil",
    "reminder.rescheduled": "Penjadwalan Ulang Pengingat",
    "stage.completed": "Tahapan Selesai",
    "match.decided": "Keputusan Staf Disimpan",
    "evaluation.recomputed": "Evaluasi Matching Diperbarui",
}

ACTOR_LABELS = {
    "fixture.seed": "Sistem Minori",
    "reminder.worker": "Layanan Pengingat",
    "staff.admin": "Staf HR Minori",
    "reviewer": "Peninjau",
}


def render_overview_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)

    try:
        health = client.get_health()
        backend_status = "Connected" if health.get("status") == "ok" else "Degraded"
    except Exception:
        backend_status = "Disconnected"

    render_page_header(
        title="Command Center Operasional",
        description="Ringkasan waktu nyata penempatan tenaga kerja ke Jepang, status matching, dan antrean pengingat.",
        breadcrumb="MINORI Operations / Overview",
        backend_status=backend_status,
        demo_mode=settings.demo_mode,
    )

    try:
        summary = client.get_overview_summary()
    except Exception as exc:
        show_api_error(exc)
        return

    # --- KPI Cards Row ---
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_metric_card(
            label="Total Kandidat",
            value=summary.get("total_candidates", 0),
            subtext=f"{summary.get('ready_candidates', 0)} siap berangkat",
            badge="Kandidat",
            badge_type="info",
        )
    with c2:
        render_metric_card(
            label="Lowongan Aktif",
            value=summary.get("active_vacancies", 0),
            subtext="Menerima kandidat",
            badge="Lowongan",
            badge_type="success",
        )
    with c3:
        render_metric_card(
            label="Penempatan Aktif",
            value=summary.get("active_placements", 0),
            subtext="Dalam proses alur",
            badge="Penempatan",
            badge_type="info",
        )
    with c4:
        render_metric_card(
            label="Memenuhi Syarat",
            value=summary.get("eligible_matches", 0),
            subtext="Lolos evaluasi kualifikasi",
            badge="Lolos",
            badge_type="success",
        )
    with c5:
        render_metric_card(
            label="Perlu Verifikasi",
            value=summary.get("needs_review_matches", 0),
            subtext="Menunggu telaah staf",
            badge="Verifikasi",
            badge_type="warning",
        )
    with c6:
        render_metric_card(
            label="Antrean Pengingat",
            value=summary.get("pending_reminders", 0),
            subtext=f"{summary.get('simulated_reminders', 0)} simulasi sukses",
            badge="Pengingat",
            badge_type="neutral",
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # --- Action Center & Upcoming Activities ---
    col_act, col_dist = st.columns([1, 1])

    with col_act:
        with st.container(border=True):
            st.markdown(
                "<h3 style='margin:0 0 12px 0; font-size:15px; color:#13263F; font-weight:700;'>⚡ Agenda & Jadwal Terdekat</h3>",
                unsafe_allow_html=True,
            )
            upcoming = summary.get("upcoming_activities", [])
            if not upcoming:
                st.caption(
                    "Tidak ada wawancara atau pemeriksaan kesehatan terjadwal dalam waktu dekat."
                )
            else:
                for item in upcoming[:5]:
                    step_type = item.get("step_type", "Aktivitas")
                    step_title = (
                        "Pemeriksaan Kesehatan"
                        if step_type == "medical_check"
                        else (
                            "Wawancara Kerja"
                            if step_type == "interview"
                            else step_type.replace("_", " ").title()
                        )
                    )
                    sched = format_datetime_id(item.get("scheduled_at"))
                    venue = item.get("location") or "Lokasi belum ditentukan"
                    st.markdown(
                        f"""
                        <div style="border-left: 3px solid #0F766E; padding-left: 10px; margin-bottom: 10px;">
                            <div style="font-weight: 600; color: #13263F; font-size: 13px;">{step_title}</div>
                            <div style="font-size: 12px; color: #64748B;">📅 {sched} | 📍 {venue}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with col_dist:
        with st.container(border=True):
            st.markdown(
                "<h3 style='margin:0 0 12px 0; font-size:15px; color:#13263F; font-weight:700;'>📊 Distribusi Kelayakan Matching</h3>",
                unsafe_allow_html=True,
            )
            el_data = {
                "Status": ["Memenuhi Persyaratan", "Perlu Verifikasi", "Belum Memenuhi"],
                "Jumlah": [
                    summary.get("eligible_matches", 0),
                    summary.get("needs_review_matches", 0),
                    summary.get("not_eligible_matches", 0),
                ],
            }
            st.bar_chart(
                data=el_data, x="Jumlah", y="Status", horizontal=True, color="#0F766E", height=190
            )

    # --- Pipeline & Audit Log Overview ---
    col_pl, col_log = st.columns([1, 1])

    with col_pl:
        with st.container(border=True):
            st.markdown(
                "<h3 style='margin:0 0 12px 0; font-size:15px; color:#13263F; font-weight:700;'>📌 Tahapan Alur Penempatan</h3>",
                unsafe_allow_html=True,
            )
            pl_data = summary.get("placements_by_status", {})
            if pl_data:
                chart_df = {
                    "Status": [format_status_label(k) for k in pl_data.keys()],
                    "Jumlah": list(pl_data.values()),
                }
                st.bar_chart(
                    data=chart_df,
                    x="Jumlah",
                    y="Status",
                    horizontal=True,
                    color="#13263F",
                    height=190,
                )
            else:
                st.caption("Belum ada data status penempatan aktif.")

    with col_log:
        with st.container(border=True):
            st.markdown(
                "<h3 style='margin:0 0 12px 0; font-size:15px; color:#13263F; font-weight:700;'>📝 Catatan Aktivitas Terkini</h3>",
                unsafe_allow_html=True,
            )
            audits = summary.get("recent_audits", [])
            if not audits:
                st.caption("Belum ada riwayat aktivitas tercatat.")
            else:
                for a in audits[:5]:
                    dt = format_datetime_id(a.get("occurred_at"))
                    raw_actor = a.get("actor_reference", "staf")
                    actor_clean = ACTOR_LABELS.get(raw_actor, "Staf Operasional")
                    raw_act = a.get("action", "")
                    action_clean = ACTION_LABELS.get(raw_act, raw_act.replace("_", " ").title())
                    st.markdown(
                        f"""
                        <div style="font-size: 12px; color: #334155; padding: 6px 0; border-bottom: 1px solid #F1F5F9;">
                            <b>{actor_clean}</b>: {action_clean}
                            <span style="color: #64748B; float: right;">{dt}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


if __name__ == "__main__":
    render_overview_page()
