"""Candidate directory and qualification details backed by HTTP."""

from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import is_admin
from minori_frontend.components.candidate_form import candidate_fields
from minori_frontend.components.candidate_profile import render_candidate_profile
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.filters import render_filter_bar
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import section
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import language_label, program_short


@st.dialog("Profil dan kualifikasi kandidat", width="large")
def show_create_candidate_dialog(client, initial=None):
    initial = initial or {}
    try:
        vacancies = read_all(client.list_vacancies, status="open")
    except Exception as exc:
        show_api_error(exc)
        return
    with st.form("form_create_candidate"):
        payload = candidate_fields("candidate_edit_" + initial.get("id", "new"), initial)
        vacancy_options = {v["id"]: f"{v['title']} · {v['employer_name']}" for v in vacancies}
        vacancy_id = st.selectbox(
            "Lowongan untuk ditinjau",
            [None, *vacancy_options],
            format_func=lambda value: vacancy_options.get(value, "Pilih lowongan (opsional)"),
        )
        save = st.form_submit_button("Simpan kandidat", width="stretch")
        review = st.form_submit_button(
            "Simpan dan tinjau pencocokan", type="primary", disabled=not vacancies, width="stretch"
        )
        if save or review:
            if not all(payload[k] for k in ("full_name", "education_level", "domicile_city")):
                st.error("Lengkapi nama, pendidikan terakhir, dan kota domisili.")
                return
            if review and not vacancy_id:
                st.warning("Pilih lowongan yang akan ditinjau.")
                return
            try:
                payload["reference"] = (
                    initial.get("reference") or "CAND-" + uuid4().hex[:12].upper()
                )
                saved = (
                    client.replace_candidate(initial["id"], payload)
                    if initial
                    else client.create_candidate(payload)
                )
                st.session_state["candidate_saved_id"] = saved["id"]
                show_success(
                    "Profil disimpan dan pencocokan diperbarui berdasarkan kualifikasi resmi."
                )
                if review:
                    st.session_state["matching_handoff"] = {
                        "candidate_id": saved["id"],
                        "vacancy_id": vacancy_id,
                    }
                    from minori_frontend.components.navigation import navigate_to

                    navigate_to("candidate-matching")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)


def render_candidates_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    saved = st.session_state.pop("candidate_saved_id", None)
    if saved:
        st.session_state["candidate_detail_id"] = saved
        st.session_state["cand_query"] = ""
        st.session_state["cand_program"] = "all"
        st.session_state["cand_status"] = "all"
    render_page_header(
        "Kandidat", "Kelola profil, kualifikasi, dan kesiapan kandidat untuk penempatan di Jepang."
    )
    if is_admin() and st.button("Tambah kandidat", type="primary", icon=":material/add:"):
        show_create_candidate_dialog(client)
    filters = render_filter_bar(
        search_placeholder="Cari nama kandidat…",
        status_options=[
            ("ready", "Siap ditempatkan"),
            ("preparing", "Persiapan"),
            ("registered", "Terdaftar"),
            ("inactive", "Nonaktif"),
        ],
        key_prefix="cand",
    )
    try:
        candidates = read_all(
            client.list_candidates,
            query=filters.get("query"),
            program=filters.get("program"),
            status=filters.get("status"),
        )
    except Exception as exc:
        show_api_error(exc)
        return
    if not candidates:
        render_empty_state(
            "Kandidat tidak ditemukan", "Ubah pencarian atau filter untuk melihat kandidat lainnya."
        )
        return
    directory, detail = st.columns([1.45, 1], gap="large")
    with directory:
        with st.container(border=True):
            section("Daftar kandidat", f"{len(candidates)} kandidat sesuai pencarian")
            rows = [
                {
                    "id": c["id"],
                    "Nama kandidat": c.get("full_name"),
                    "Program": program_short(c.get("preferred_program")),
                    "Domisili": c.get("domicile_city"),
                    "Status": format_status_label(c.get("status")),
                    "Bahasa Jepang": ", ".join(
                        f"{language_label(t.get('test_type'))} {t.get('level')}"
                        for t in c.get("language_tests", [])
                    )
                    or "Belum tercatat",
                }
                for c in candidates
            ]
            selected = render_interactive_table(
                rows, key="candidates_table", height=400, default_first=False
            )
        options = {c["id"]: c["full_name"] for c in candidates}
        if selected:
            signature = candidates[selected[0]]["id"]
            if signature != st.session_state.get("candidate_table_selection"):
                st.session_state["candidate_detail_id"] = signature
                st.session_state["candidate_table_selection"] = signature
        if st.session_state.get("candidate_detail_id") not in options:
            st.session_state["candidate_detail_id"] = candidates[0]["id"]
        identifier = st.selectbox(
            "Kandidat yang ditinjau",
            list(options),
            format_func=options.get,
            key="candidate_detail_id",
        )
        selected_candidate = next(c for c in candidates if c["id"] == identifier)
    with detail:
        with st.container(border=True):
            render_candidate_profile(selected_candidate)
            if is_admin() and st.button("Edit profil dan kualifikasi", width="stretch"):
                show_create_candidate_dialog(client, selected_candidate)
            if st.button("Tinjau pencocokan kandidat", width="stretch"):
                st.session_state["matching_handoff"] = {"candidate_id": selected_candidate["id"]}
                from minori_frontend.components.navigation import navigate_to

                navigate_to("candidate-matching")
            if is_admin() and selected_candidate.get("status") != "inactive":
                with st.popover("Arsipkan kandidat", width="stretch"):
                    st.write(
                        "Kandidat akan menjadi nonaktif. Jadwal baru tidak dapat dibuat untuk kandidat ini."
                    )
                    if st.button("Konfirmasi arsip", key="btn_archive_cand", width="stretch"):
                        try:
                            client.archive_candidate(selected_candidate["id"])
                            show_success("Kandidat berhasil diarsipkan.")
                            st.rerun()
                        except Exception as exc:
                            show_api_error(exc)


if __name__ == "__main__":
    render_candidates_page()
