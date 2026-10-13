"""Placement operational pipeline and administrative stages scheduling."""

from datetime import timedelta
from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import get_current_actor, is_admin
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.placement_timeline import (
    render_activity_card,
    render_pipeline_stepper,
)
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id, now_wib, to_iso_wib
from minori_frontend.utils.formatting import format_status_label


def render_pipeline_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)
    can_mutate = is_admin()
    actor = get_current_actor()

    render_page_header(
        title="Pipeline Penempatan Tenaga Kerja",
        description="Pelacakan tahapan wawancara, pemeriksaan medis, visa & dokumen, orientasi, dan jadwal keberangkatan ke Jepang.",
        breadcrumb="MINORI Operations / Placement Pipeline",
    )

    # Fetch placements
    try:
        placements = client.list_placements()
        candidates_map = {c["id"]: c for c in client.list_candidates()}
        vacancies_map = {v["id"]: v for v in client.list_vacancies()}
    except Exception as exc:
        show_api_error(exc)
        return

    if not placements:
        render_empty_state(
            title="Belum ada penempatan aktif",
            description="Penempatan dibuat dari hasil pencocokan kandidat yang telah disetujui staf di halaman Candidate Matching.",
        )
        return

    # Filter Bar
    search_q = st.text_input(
        "Cari referensi penempatan...", placeholder="PLC-...", key="plc_search"
    )
    filtered_placements = [
        p for p in placements if not search_q or search_q.lower() in p.get("reference", "").lower()
    ]

    # Table of Placements
    table_data = []
    for p in filtered_placements:
        cid = p.get("candidate_id")
        vid = p.get("vacancy_id")
        cname = candidates_map.get(cid, {}).get("full_name", str(cid)[:8])
        vtitle = vacancies_map.get(vid, {}).get("title", str(vid)[:8])
        table_data.append(
            {
                "id": p.get("id"),
                "Referensi": p.get("reference"),
                "Nama Kandidat": cname,
                "Posisi Lowongan": vtitle,
                "Status": format_status_label(p.get("status")),
                "Rencana Berangkat": format_datetime_id(p.get("planned_departure_at")),
            }
        )

    st.markdown("##### Pilih Penempatan untuk Mengelola Aktivitas")
    selected_indices = render_interactive_table(table_data, key="placement_table", height=240)

    selected_p: dict[str, Any] | None = None
    if selected_indices:
        selected_id = table_data[selected_indices[0]]["id"]
        selected_p = next((p for p in placements if p["id"] == selected_id), None)
    else:
        selected_p = filtered_placements[0]

    if not selected_p:
        return

    st.markdown(
        "<hr style='margin: 14px 0; border: none; border-top: 1px solid #E2E8F0;'>",
        unsafe_allow_html=True,
    )

    # Details of Selected Placement
    pid = selected_p["id"]
    cand_info = candidates_map.get(selected_p.get("candidate_id"), {})
    vac_info = vacancies_map.get(selected_p.get("vacancy_id"), {})

    st.markdown(
        f"""
        <div class="minori-card">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div>
                    <h3 style="margin: 0; color: #13263F; font-size: 1.25rem;">Penempatan #{selected_p.get("reference")}</h3>
                    <div style="font-size: 13px; color: #64748B; margin-top: 2px;">
                        Kandidat: <b>{cand_info.get("full_name")}</b> ({cand_info.get("reference")}) &nbsp; | &nbsp;
                        Posisi: <b>{vac_info.get("title")}</b> ({vac_info.get("employer_name")})
                    </div>
                </div>
                <div>
                    <span style="font-size: 12px; font-weight: 600; color: #13263F; background: #E0E7FF; padding: 4px 8px; border-radius: 4px;">
                        Status: {format_status_label(selected_p.get("status"))}
                    </span>
                </div>
            </div>
            <div style="margin-top: 10px; font-size: 13px; color: #334155;">
                <div>🛫 <b>Rencana Keberangkatan:</b> {format_datetime_id(selected_p.get("planned_departure_at"))}</div>
                {f"<div>✈️ <b>Keberangkatan Nyata:</b> {format_datetime_id(selected_p.get('actual_departure_at'))}</div>" if selected_p.get("actual_departure_at") else ""}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch stages / activities for this placement
    try:
        activities = client.list_activities(pid)
    except Exception as exc:
        show_api_error(exc)
        activities = []

    # Visual Greenhouse-like Pipeline Stepper
    st.markdown("##### Tahapan Pipeline Penempatan")
    render_pipeline_stepper(activities)

    # Activities List and Action Form
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    col_act_list, col_act_form = st.columns([6, 4])

    with col_act_list:
        st.markdown("##### Daftar Aktivitas Administratif Terjadwal")
        if not activities:
            st.caption("Belum ada aktivitas administratif terjadwal untuk penempatan ini.")
        else:
            for act in sorted(activities, key=lambda x: x.get("sequence_number", 0)):
                render_activity_card(act)
                if can_mutate and act.get("status") != "completed":
                    col_m1, col_m2 = st.columns([1, 1])
                    with col_m1:
                        st_name = (
                            "Pemeriksaan Kesehatan"
                            if act.get("step_type") == "medical_check"
                            else (
                                "Wawancara Kerja"
                                if act.get("step_type") == "interview"
                                else "Tahapan"
                            )
                        )
                        if st.button(f"✓ Tandai Selesai ({st_name})", key=f"comp_{act['id']}"):
                            try:
                                client.update_activity(
                                    pid,
                                    act["id"],
                                    {
                                        "actor_reference": actor,
                                        "status": "completed",
                                        "completed_at": to_iso_wib(now_wib()),
                                    },
                                )
                                show_success("Aktivitas ditandai selesai!")
                                st.rerun()
                            except Exception as exc:
                                show_api_error(exc)

    with col_act_form:
        if can_mutate:
            st.markdown("##### ➕ Jadwalkan Aktivitas Baru")
            with st.form("form_add_activity"):
                step_type = st.selectbox(
                    "Jenis Tahapan",
                    options=["interview", "medical_check", "documents", "orientation", "departure"],
                    format_func=lambda s: s.replace("_", " ").title(),
                )
                code = st.text_input(
                    "Kode Unik Aktivitas *", value=f"{step_type.upper()[:4]}_{len(activities) + 1}"
                )
                seq = st.number_input(
                    "Urutan Langkah (Sequence) *",
                    min_value=1,
                    max_value=20,
                    value=len(activities) + 1,
                )
                days_ahead = st.slider("Jadwal (Hari ke depan)", min_value=1, max_value=60, value=3)
                location = st.text_input(
                    "Lokasi / Ruang Administratif", placeholder="Ruang Wawancara Minori Jakarta"
                )

                st.caption(
                    "ℹ️ Catatan privasi: Pemeriksaan medis hanya mencatat jadwal dan lokasi administratif, tanpa menyimpan diagnosis atau temuan medis."
                )

                act_submit = st.form_submit_button(
                    "Simpan Aktivitas", type="primary", use_container_width=True
                )
                if act_submit:
                    target_time = now_wib() + timedelta(days=days_ahead, hours=2)
                    payload = {
                        "actor_reference": actor,
                        "code": code.strip().upper(),
                        "step_type": step_type,
                        "sequence_number": int(seq),
                        "scheduled_at": to_iso_wib(target_time),
                        "location": location.strip() if location else None,
                    }
                    try:
                        client.create_activity(pid, payload)
                        show_success("Aktivitas berhasil ditambahkan ke jadwal!")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
        else:
            st.info(
                "Mode Reviewer: Hanya staf yang berhak menambahkan atau mengubah jadwal aktivitas."
            )


if __name__ == "__main__":
    render_pipeline_page()
