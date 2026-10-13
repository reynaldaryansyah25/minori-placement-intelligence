"""Candidate management page with directory, profiles, and CRUD operations."""

from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import is_admin
from minori_frontend.components.candidate_profile import render_candidate_profile
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.filters import render_filter_bar
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.formatting import format_program, format_status_label


@st.dialog("Tambah Kandidat Baru")
def show_create_candidate_dialog(client: BackendClient) -> None:
    with st.form("form_create_candidate"):
        st.markdown("##### Informasi Administratif")
        col1, col2 = st.columns(2)
        with col1:
            ref = st.text_input("Nomor Referensi *", placeholder="CAND-ID-001")
            full_name = st.text_input("Nama Lengkap *", placeholder="Nama Kandidat")
            prog = st.selectbox(
                "Program Penempatan *",
                options=[p[0] for p in PROGRAMS],
                format_func=lambda x: dict(PROGRAMS)[x],
            )
        with col2:
            edu = st.text_input("Pendidikan Terakhir *", value="SMK Teknik")
            domicile = st.text_input("Kota Domisili *", value="Jakarta")
            status = st.selectbox(
                "Status Awal", options=["registered", "preparing", "ready"], index=0
            )

        st.markdown("##### Keahlian & Preferensi")
        skills_raw = st.text_input(
            "Kode Keahlian (pisahkan dengan koma)", placeholder="AGRICULTURE_GENERAL, WELDING_ARC"
        )
        prefs = st.multiselect(
            "Preferensi Prefektur Jepang", options=JAPAN_PREFECTURES, default=["Tokyo", "Aichi"]
        )

        submitted = st.form_submit_button(
            "Simpan Kandidat", type="primary", use_container_width=True
        )
        if submitted:
            if not ref or not full_name:
                st.error("Nomor referensi dan nama lengkap wajib diisi.")
                return

            skills = [s.strip().upper() for s in skills_raw.split(",") if s.strip()]
            payload = {
                "reference": ref.strip(),
                "full_name": full_name.strip(),
                "preferred_program": prog,
                "education_level": edu.strip(),
                "domicile_city": domicile.strip(),
                "status": status,
                "skills": skills,
                "preferred_prefectures": prefs,
                "language_tests": [],
                "certifications": [],
                "experiences": [],
            }
            try:
                created = client.create_candidate(payload)
                show_success(f"Kandidat {created.get('full_name')} berhasil ditambahkan!")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)


def render_candidates_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)

    render_page_header(
        title="Direktori Kandidat",
        description="Kelola profil kualifikasi, sertifikasi, kemampuan bahasa Jepang, dan preferensi kerja peserta.",
        breadcrumb="MINORI Operations / Candidates",
    )

    # Top action bar
    can_mutate = is_admin()
    if can_mutate:
        col_btn, _ = st.columns([2, 8])
        with col_btn:
            if st.button("➕ Tambah Kandidat", type="primary", use_container_width=True):
                show_create_candidate_dialog(client)
    else:
        st.info("Mode Reviewer: Akses penambahan dan pengubahan data kandidat dinonaktifkan.")

    # Filter bar
    status_options = [
        ("ready", "Siap Ditempatkan"),
        ("preparing", "Persiapan/Pelatihan"),
        ("registered", "Terdaftar"),
        ("inactive", "Nonaktif/Arsip"),
    ]
    filters = render_filter_bar(
        search_placeholder="Cari nama atau referensi...",
        show_program=True,
        show_status=True,
        status_options=status_options,
        key_prefix="cand",
    )

    try:
        candidates = client.list_candidates(
            query=filters.get("query"),
            program=filters.get("program"),
            status=filters.get("status"),
        )
    except Exception as exc:
        show_api_error(exc)
        return

    if not candidates:
        render_empty_state(
            title="Tidak ada kandidat ditemukan",
            description="Tidak ada profil kandidat yang cocok dengan kriteria filter pencarian Anda.",
        )
        return

    # Table View
    table_data = []
    for c in candidates:
        tests = c.get("language_tests", [])
        lang_summary = (
            ", ".join(f"{t.get('test_type').upper()} {t.get('level')}" for t in tests)
            if tests
            else "Belum tes"
        )
        table_data.append(
            {
                "id": c.get("id"),
                "Referensi": c.get("reference"),
                "Nama Lengkap": c.get("full_name"),
                "Program": format_program(c.get("preferred_program")),
                "Domisili": c.get("domicile_city"),
                "Status": format_status_label(c.get("status")),
                "Bahasa Jepang": lang_summary,
                "Skills": ", ".join(c.get("skills", [])) or "—",
            }
        )

    st.markdown("##### Pilih Kandidat untuk Melihat Detail")
    selected_indices = render_interactive_table(
        table_data,
        key="candidates_table",
        height=320,
    )

    selected_candidate: dict[str, Any] | None = None
    if selected_indices:
        selected_row = selected_indices[0]
        selected_id = table_data[selected_row]["id"]
        try:
            selected_candidate = client.get_candidate(selected_id)
        except Exception as exc:
            show_api_error(exc)
    else:
        # Default select first
        selected_candidate = candidates[0]

    if selected_candidate:
        st.markdown(
            "<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True,
        )
        render_candidate_profile(selected_candidate)

        if can_mutate:
            col_arch, _ = st.columns([2, 8])
            with col_arch:
                if selected_candidate.get("status") != "inactive":
                    if st.button("📁 Arsipkan Kandidat", key="btn_archive_cand"):
                        try:
                            client.archive_candidate(selected_candidate["id"])
                            show_success(
                                f"Kandidat {selected_candidate.get('full_name')} diarsipkan."
                            )
                            st.rerun()
                        except Exception as exc:
                            show_api_error(exc)


if __name__ == "__main__":
    render_candidates_page()
