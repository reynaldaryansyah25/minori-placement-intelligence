"""Placement selection and real administrative scheduling operations."""

from datetime import datetime, timedelta
from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import can_operate, get_current_actor
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.placement_timeline import (
    render_activity_card,
    render_pipeline_stepper,
)
from minori_frontend.components.presentation import detail_grid, section
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id, now_wib, parse_to_wib, to_iso_wib
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import STEP_LABELS


def render_pipeline_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    handoff = st.session_state.pop("placement_handoff_id", None)
    if handoff:
        st.session_state["selected_placement_id"] = handoff
        st.session_state["plc_search"] = ""
        st.session_state["placement_status_filter"] = None
    render_page_header(
        "Alur penempatan",
        "Kelola tahapan, jadwal kegiatan, dan persiapan keberangkatan setiap peserta.",
    )
    try:
        placements = read_all(
            client.list_placements,
        )
        candidates = {
            c["id"]: c
            for c in read_all(
                client.list_candidates,
            )
        }
        vacancies = {
            v["id"]: v
            for v in read_all(
                client.list_vacancies,
            )
        }
        approved = read_all(client.list_approved_candidates)
    except Exception as exc:
        show_api_error(exc)
        return
    with st.container(border=True):
        section("Kandidat disetujui staf", "Persetujuan tampil di sini sebelum penempatan dibuat.")
        if approved:
            waiting_options = {
                row["match_id"]: f"{row['candidate_name']} · {row['vacancy_title']}"
                for row in approved
            }
            approved_handoff = st.session_state.pop("approved_match_handoff", None)
            if approved_handoff in waiting_options:
                st.session_state["approved_match_selection"] = approved_handoff
            if st.session_state.get("approved_match_selection") not in waiting_options:
                st.session_state["approved_match_selection"] = next(iter(waiting_options))
            chosen = st.selectbox(
                "Persetujuan yang diproses",
                list(waiting_options),
                format_func=waiting_options.get,
                key="approved_match_selection",
            )
            waiting = next(row for row in approved if row["match_id"] == chosen)
            if waiting.get("reason"):
                st.info(waiting["reason"])
            if st.button(
                "Mulai persiapan penempatan",
                type="primary",
                disabled=not can_operate() or not waiting["can_start"],
            ):
                try:
                    created = client.create_placement(
                        "PLC-" + uuid4().hex[:12].upper(), chosen, get_current_actor()
                    )
                    st.session_state["placement_handoff_id"] = created["id"]
                    show_success(
                        "Penempatan dibuat. Lanjutkan dengan menjadwalkan aktivitas peserta."
                    )
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
        else:
            st.caption(
                "Belum ada persetujuan yang menunggu penempatan. Kandidat yang sudah ditempatkan tampil di daftar di bawah."
            )
    search, status_filter = st.columns([3, 1])
    with search:
        query = st.text_input(
            "Pencarian penempatan",
            placeholder="Cari kandidat atau posisi…",
            key="plc_search",
            label_visibility="collapsed",
        )
    with status_filter:
        status = st.selectbox(
            "Status penempatan",
            [None, "preparing", "in_progress", "completed", "cancelled"],
            format_func=lambda value: (
                "Semua status" if value is None else format_status_label(value)
            ),
            label_visibility="collapsed",
            key="placement_status_filter",
        )
    records = [
        p
        for p in placements
        if (not status or p.get("status") == status)
        and (
            not query
            or query.lower()
            in " ".join(
                [
                    candidates.get(p.get("candidate_id"), {}).get("full_name", ""),
                    vacancies.get(p.get("vacancy_id"), {}).get("title", ""),
                ]
            ).lower()
        )
    ]
    if not records:
        render_empty_state(
            "Penempatan tidak ditemukan",
            "Ubah pencarian atau buat penempatan dari kandidat yang telah disetujui.",
        )
        return
    with st.container(border=True):
        section("Daftar penempatan", "Pilih peserta untuk mengelola aktivitasnya.")
        selected = render_interactive_table(
            [
                {
                    "id": p["id"],
                    "Kandidat": candidates.get(p.get("candidate_id"), {}).get(
                        "full_name", "Kandidat tidak tersedia"
                    ),
                    "Posisi": vacancies.get(p.get("vacancy_id"), {}).get(
                        "title", "Lowongan tidak tersedia"
                    ),
                    "Status": format_status_label(p.get("status")),
                    "Rencana keberangkatan": format_datetime_id(p.get("planned_departure_at")),
                }
                for p in records
            ],
            key="placement_table",
            height=280,
            default_first=False,
        )
    options = {
        p["id"]: candidates.get(p["candidate_id"], {}).get("full_name", "Kandidat")
        + " · "
        + vacancies.get(p["vacancy_id"], {}).get("title", "Lowongan")
        for p in records
    }
    if selected:
        signature = records[selected[0]]["id"]
        if signature != st.session_state.get("placement_table_selection"):
            st.session_state["selected_placement_id"] = signature
            st.session_state["placement_table_selection"] = signature
    if st.session_state.get("selected_placement_id") not in options:
        st.session_state["selected_placement_id"] = records[0]["id"]
    pid = st.selectbox(
        "Peserta penempatan", list(options), format_func=options.get, key="selected_placement_id"
    )
    placement = next(p for p in records if p["id"] == pid)
    pid = placement["id"]
    candidate = candidates.get(placement.get("candidate_id"), {})
    vacancy = vacancies.get(placement.get("vacancy_id"), {})
    try:
        activities = client.list_activities(pid)
    except Exception as exc:
        show_api_error(exc)
        return
    with st.container(border=True):
        section(candidate.get("full_name", "Rincian penempatan"), vacancy.get("title", ""))
        render_status_badge(placement.get("status"))
        detail_grid(
            [
                ("Perusahaan", vacancy.get("employer_name")),
                ("Prefektur", vacancy.get("prefecture")),
                (
                    "Rencana keberangkatan",
                    format_datetime_id(placement.get("planned_departure_at")),
                ),
                ("Keberangkatan aktual", format_datetime_id(placement.get("actual_departure_at"))),
            ]
        )
        render_pipeline_stepper(activities)
        if st.button("Buka pengingat dan email peserta", width="stretch"):
            st.session_state["reminder_candidate_handoff"] = placement["candidate_id"]
            from minori_frontend.components.navigation import navigate_to

            navigate_to("reminder-center")
    listing, scheduling = st.columns([1.3, 1], gap="large")
    with listing:
        with st.container(border=True):
            section("Aktivitas penempatan", "Jadwal dan perkembangan kegiatan administratif")
            for activity in sorted(activities, key=lambda row: row.get("sequence_number", 0)):
                render_activity_card(activity)
                scheduled = parse_to_wib(activity.get("scheduled_at"))
                can_complete = (
                    activity.get("status") in {"scheduled", "in_progress"}
                    and scheduled
                    and scheduled <= now_wib()
                )
                if can_operate() and can_complete:
                    if st.button("Tandai selesai", key="comp_" + activity["id"]):
                        try:
                            client.update_activity(
                                pid,
                                activity["id"],
                                {
                                    "actor_reference": get_current_actor(),
                                    "status": "completed",
                                    "completed_at": to_iso_wib(now_wib()),
                                },
                            )
                            show_success("Aktivitas berhasil ditandai selesai.")
                            st.rerun()
                        except Exception as exc:
                            show_api_error(exc)
            if not activities:
                st.caption("Belum ada aktivitas yang dijadwalkan.")
    with scheduling:
        with st.container(border=True):
            section("Jadwalkan aktivitas", "Pengingat wawancara dan kesehatan disiapkan otomatis.")
            eligible_to_schedule = candidate.get("status") != "inactive" and placement.get(
                "status"
            ) in {"preparing", "in_progress"}
            if not eligible_to_schedule:
                st.info("Jadwal baru memerlukan kandidat dan penempatan yang aktif.")
            with st.form("form_add_activity"):
                kind = st.selectbox(
                    "Jenis kegiatan", list(STEP_LABELS), format_func=STEP_LABELS.get
                )
                day = st.date_input(
                    "Tanggal kegiatan",
                    value=(now_wib() + timedelta(days=3)).date(),
                    min_value=now_wib().date(),
                )
                at = st.time_input(
                    "Waktu kegiatan (WIB)",
                    value=now_wib().replace(hour=14, minute=0, second=0).time(),
                )
                location = st.text_input(
                    "Lokasi kegiatan", placeholder="Ruang atau lokasi kegiatan"
                )
                sequence = st.number_input(
                    "Urutan aktivitas",
                    min_value=1,
                    value=max((int(a.get("sequence_number", 0)) for a in activities), default=0)
                    + 1,
                )
                st.caption(
                    "Pemeriksaan kesehatan hanya menyimpan jadwal dan lokasi, tanpa hasil medis."
                )
                if st.form_submit_button(
                    "Simpan jadwal",
                    type="primary",
                    disabled=not can_operate() or not eligible_to_schedule,
                    width="stretch",
                ):
                    target = datetime.combine(day, at, tzinfo=now_wib().tzinfo)
                    if target <= now_wib():
                        st.error("Pilih waktu kegiatan yang masih akan datang.")
                    else:
                        try:
                            client.create_activity(
                                pid,
                                {
                                    "actor_reference": get_current_actor(),
                                    "code": "ACT-" + uuid4().hex[:12].upper(),
                                    "step_type": kind,
                                    "sequence_number": int(sequence),
                                    "scheduled_at": to_iso_wib(target),
                                    "location": location.strip() or None,
                                },
                            )
                            show_success("Jadwal kegiatan berhasil disimpan.")
                            st.rerun()
                        except Exception as exc:
                            show_api_error(exc)


if __name__ == "__main__":
    render_pipeline_page()
