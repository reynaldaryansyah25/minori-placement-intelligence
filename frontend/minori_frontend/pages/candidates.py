"""Candidate directory and qualification details backed by HTTP."""

from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import is_admin
from minori_frontend.components.candidate_profile import render_candidate_profile
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.filters import render_filter_bar
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import section
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import SKILL_LABELS, catalog_label, language_label, program_short


@st.dialog("Tambah kandidat")
def show_create_candidate_dialog(client):
    with st.form("form_create_candidate"):
        left, right = st.columns(2)
        with left:
            name = st.text_input("Nama lengkap *")
            program = st.selectbox(
                "Program penempatan",
                [p[0] for p in PROGRAMS],
                format_func=lambda x: dict(PROGRAMS)[x],
            )
            education = st.text_input("Pendidikan terakhir *")
        with right:
            city = st.text_input("Kota domisili *")
            status = st.selectbox(
                "Status awal", ["registered", "preparing", "ready"], format_func=format_status_label
            )
            preferences = st.multiselect("Preferensi prefektur", JAPAN_PREFECTURES)
        skills = st.multiselect(
            "Keahlian", list(SKILL_LABELS), format_func=catalog_label, accept_new_options=True
        )
        if st.form_submit_button("Simpan kandidat", type="primary", width="stretch"):
            if not all(value.strip() for value in (name, education, city)):
                st.error("Lengkapi nama, pendidikan terakhir, dan kota domisili.")
                return
            try:
                client.create_candidate(
                    {
                        "reference": "CAND-" + uuid4().hex[:12].upper(),
                        "full_name": name.strip(),
                        "preferred_program": program,
                        "education_level": education.strip(),
                        "domicile_city": city.strip(),
                        "status": status,
                        "skills": [s.strip().lower().replace(" ", "_") for s in skills],
                        "preferred_prefectures": preferences,
                        "language_tests": [],
                        "certifications": [],
                        "experiences": [],
                    }
                )
                show_success("Kandidat berhasil ditambahkan.")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)


def render_candidates_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
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
            selected = render_interactive_table(rows, key="candidates_table", height=400)
        selected_candidate = candidates[selected[0] if selected else 0]
    with detail:
        with st.container(border=True):
            render_candidate_profile(selected_candidate)
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
