"""Operational overview using live backend aggregates."""

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.components.feedback import show_api_error
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metrics
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import distribution, html, section, text
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import ACTION_LABELS, STEP_LABELS


def render_overview_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Ringkasan operasional",
        "Pantau kesiapan kandidat, kebutuhan tenaga kerja, dan agenda penempatan dalam satu tempat.",
    )
    try:
        summary = client.get_overview_summary()
    except Exception as exc:
        show_api_error(exc)
        return
    render_metrics(
        [
            (
                "Total kandidat",
                summary.get("total_candidates", 0),
                f"{summary.get('ready_candidates', 0)} siap ditempatkan",
            ),
            ("Lowongan aktif", summary.get("active_vacancies", 0), "Menerima kandidat"),
            ("Penempatan aktif", summary.get("active_placements", 0), "Dalam proses penempatan"),
            (
                "Antrean pengingat",
                summary.get("pending_reminders", 0),
                "Menunggu jadwal pengiriman",
            ),
        ]
    )
    attention, pipeline = st.columns([1.22, 1], gap="large")
    with attention:
        with st.container(border=True, key="action_center"):
            section("Perlu ditindaklanjuti", "Prioritas tim rekrutmen")
            for label, amount, detail, target in [
                (
                    "Verifikasi kandidat",
                    summary.get("needs_review_matches", 0),
                    "Tinjau persyaratan yang masih perlu dikonfirmasi",
                    "candidate-matching",
                ),
                (
                    "Persiapan kandidat",
                    summary.get("total_candidates", 0) - summary.get("ready_candidates", 0),
                    "Periksa kelengkapan profil dan kesiapan peserta",
                    "candidates",
                ),
                (
                    "Antrean pengingat",
                    summary.get("pending_reminders", 0),
                    "Pantau jadwal dan hasil pengiriman",
                    "reminder-center",
                ),
            ]:
                if st.button(f"{label} · {amount}", key="overview_" + target, width="stretch"):
                    from minori_frontend.components.navigation import navigate_to

                    navigate_to(target)
                st.caption(detail)
    with pipeline:
        with st.container(border=True):
            section("Alur penempatan", "Jumlah penempatan berdasarkan status")
            counts = summary.get("placements_by_status", {})
            distribution([(format_status_label(k), v) for k, v in counts.items()], color="navy")
            if not counts:
                st.caption("Belum ada penempatan yang tercatat.")
    agenda, eligibility = st.columns([1.22, 1], gap="large")
    with agenda:
        with st.container(border=True):
            section("Agenda terdekat", "Wawancara dan pemeriksaan kesehatan yang dijadwalkan")
            upcoming = summary.get("upcoming_activities", [])
            for item in upcoming[:5]:
                html(
                    f'<div class="event-row"><div><strong>{text(STEP_LABELS.get(item.get("step_type"), "Aktivitas"))}</strong>'
                    f"<p>{text(item.get('location') or 'Lokasi belum ditentukan')}</p></div>"
                    f'<span class="event-date">{text(format_datetime_id(item.get("scheduled_at")))}</span></div>'
                )
            if not upcoming:
                st.caption("Belum ada agenda yang dijadwalkan.")
    with eligibility:
        with st.container(border=True):
            section("Kelayakan pencocokan", "Hasil evaluasi persyaratan kandidat")
            distribution(
                [
                    ("Memenuhi persyaratan", summary.get("eligible_matches", 0)),
                    ("Perlu verifikasi", summary.get("needs_review_matches", 0)),
                    ("Belum memenuhi", summary.get("not_eligible_matches", 0)),
                ]
            )
    with st.container(border=True):
        section("Aktivitas terkini", "Pembaruan operasional yang tercatat")
        for item in summary.get("recent_audits", [])[:5]:
            html(
                f'<div class="event-row"><strong>{text(ACTION_LABELS.get(item.get("action"), "Data operasional diperbarui"))}</strong>'
                f'<span class="event-date">{text(format_datetime_id(item.get("occurred_at")))}</span></div>'
            )
        if not summary.get("recent_audits"):
            st.caption("Belum ada aktivitas yang tercatat.")


if __name__ == "__main__":
    render_overview_page()
