"""Operational command center dashboard for Minori placement operations."""

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.components.feedback import show_api_error
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metric_card
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id


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
        description="Ringkasan waktu nyata penempatan tenaga kerja ke Jepang, matching, dan antrean pengingat.",
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
            badge="Pool Aktif",
            badge_type="info",
        )
    with c2:
        render_metric_card(
            label="Lowongan Aktif",
            value=summary.get("active_vacancies", 0),
            subtext="Menerima kandidat",
            badge="Open",
            badge_type="success",
        )
    with c3:
        render_metric_card(
            label="Placement Aktif",
            value=summary.get("active_placements", 0),
            subtext="Dalam proses pipeline",
            badge="Pipeline",
            badge_type="info",
        )
    with c4:
        render_metric_card(
            label="Matches Eligible",
            value=summary.get("eligible_matches", 0),
            subtext="Lolos verifikasi kuota",
            badge="Lolos",
            badge_type="success",
        )
    with c5:
        render_metric_card(
            label="Needs Review",
            value=summary.get("needs_review_matches", 0),
            subtext="Memerlukan aksi staf",
            badge="Perhatian",
            badge_type="warning",
        )
    with c6:
        render_metric_card(
            label="Pengingat Pending",
            value=summary.get("pending_reminders", 0),
            subtext=f"{summary.get('simulated_reminders', 0)} dry-run",
            badge="Antrean",
            badge_type="neutral",
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --- Action Center & Upcoming Activities ---
    col_act, col_dist = st.columns([1, 1])

    with col_act:
        st.markdown(
            """
            <div class="minori-card">
                <div class="minori-card-header">
                    <h3 class="minori-card-title">⚡ Action Center & Jadwal Terdekat</h3>
                </div>
            """,
            unsafe_allow_html=True,
        )

        upcoming = summary.get("upcoming_activities", [])
        if not upcoming:
            st.caption("Tidak ada wawancara atau pemeriksaan medis terjadwal dalam waktu dekat.")
        else:
            for item in upcoming[:5]:
                step_title = item.get("step_type", "Aktivitas").replace("_", " ").title()
                sched = format_datetime_id(item.get("scheduled_at"))
                venue = item.get("location") or "Lokasi belum ditentukan"
                st.markdown(
                    f"""
                    <div style="border-left: 3px solid #0F766E; padding-left: 10px; margin-bottom: 10px;">
                        <div style="font-weight: 600; color: #13263F; font-size: 13px;">{item.get("code")} — {step_title}</div>
                        <div style="font-size: 12px; color: #64748B;">📅 {sched} | 📍 {venue}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

    with col_dist:
        st.markdown(
            """
            <div class="minori-card">
                <div class="minori-card-header">
                    <h3 class="minori-card-title">📊 Distribusi Kelayakan Matching (Eligibility)</h3>
                </div>
            """,
            unsafe_allow_html=True,
        )

        el_data = {
            "Status": ["Eligible", "Needs Review", "Not Eligible"],
            "Jumlah": [
                summary.get("eligible_matches", 0),
                summary.get("needs_review_matches", 0),
                summary.get("not_eligible_matches", 0),
            ],
        }
        st.bar_chart(data=el_data, x="Status", y="Jumlah", color="#0F766E", height=200)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Pipeline & Audit Log Overview ---
    col_pl, col_log = st.columns([1, 1])

    with col_pl:
        st.markdown(
            """
            <div class="minori-card">
                <div class="minori-card-header">
                    <h3 class="minori-card-title">📌 Status Penempatan (Placement Pipeline)</h3>
                </div>
            """,
            unsafe_allow_html=True,
        )
        pl_data = summary.get("placements_by_status", {})
        if pl_data:
            chart_df = {
                "Status": [k.replace("_", " ").title() for k in pl_data.keys()],
                "Jumlah": list(pl_data.values()),
            }
            st.bar_chart(data=chart_df, x="Status", y="Jumlah", color="#13263F", height=200)
        else:
            st.caption("Belum ada data status penempatan aktif.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_log:
        st.markdown(
            """
            <div class="minori-card">
                <div class="minori-card-header">
                    <h3 class="minori-card-title">📝 Aktivitas Audit Terakhir (Audit Log)</h3>
                </div>
            """,
            unsafe_allow_html=True,
        )
        audits = summary.get("recent_audits", [])
        if not audits:
            st.caption("Belum ada log audit tercatat.")
        else:
            for a in audits[:5]:
                dt = format_datetime_id(a.get("occurred_at"))
                st.markdown(
                    f"""
                    <div style="font-size: 12px; color: #334155; padding: 4px 0; border-bottom: 1px solid #F1F5F9;">
                        <b>{a.get("actor_reference")}</b>: {a.get("action")} pada <i>{a.get("entity_type")}</i>
                        <span style="color: #64748B; float: right;">{dt}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_overview_page()
