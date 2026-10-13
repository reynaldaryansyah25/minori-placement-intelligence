"""Vacancy directory and requirements, with native operational controls."""

from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import is_admin
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.filters import render_filter_bar
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import chips, detail_grid, section
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.components.vacancy_form import vacancy_fields, valid_vacancy
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import SECTOR_LABELS, catalog_label, language_label, program_short


@st.dialog("Tambah lowongan", width="large")
def show_create_vacancy_dialog(client):
    with st.form("form_create_vacancy"):
        payload = vacancy_fields("create_vac")
        if st.form_submit_button(
            "Simpan lowongan", type="primary", width="stretch"
        ) and valid_vacancy(payload):
            payload["reference"] = "VAC-" + uuid4().hex[:12].upper()
            try:
                client.create_vacancy(payload)
                show_success("Lowongan berhasil ditambahkan.")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)


def render_vacancies_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Lowongan",
        "Temukan kebutuhan tenaga kerja, persyaratan, dan kuota penerimaan dari pemberi kerja.",
    )
    if is_admin() and st.button("Tambah lowongan", type="primary", icon=":material/add:"):
        show_create_vacancy_dialog(client)
    filters = render_filter_bar(
        search_placeholder="Cari posisi atau perusahaan…",
        status_options=[("open", "Aktif"), ("paused", "Ditunda"), ("closed", "Ditutup")],
        key_prefix="vac",
    )
    try:
        vacancies = read_all(
            client.list_vacancies,
            query=filters.get("query"),
            program=filters.get("program"),
            status=filters.get("status"),
        )
    except Exception as exc:
        show_api_error(exc)
        return
    if not vacancies:
        render_empty_state(
            "Lowongan tidak ditemukan", "Ubah pencarian atau filter untuk melihat lowongan lainnya."
        )
        return
    directory, detail = st.columns([1.45, 1], gap="large")
    with directory:
        with st.container(border=True):
            section("Daftar lowongan", f"{len(vacancies)} lowongan sesuai pencarian")
            selected = render_interactive_table(
                [
                    {
                        "id": v["id"],
                        "Posisi": v.get("title"),
                        "Perusahaan": v.get("employer_name"),
                        "Prefektur": v.get("prefecture"),
                        "Program": program_short(v.get("program")),
                        "Kuota": v.get("quota"),
                        "Status": format_status_label(v.get("status")),
                    }
                    for v in vacancies
                ],
                key="vacancies_table",
                height=400,
            )
        vacancy = vacancies[selected[0] if selected else 0]
    with detail:
        with st.container(border=True):
            section(vacancy.get("title", "Rincian lowongan"), vacancy.get("employer_name", ""))
            render_status_badge(vacancy.get("status"))
            detail_grid(
                [
                    ("Program", program_short(vacancy.get("program"))),
                    ("Prefektur", vacancy.get("prefecture")),
                    ("Sektor", catalog_label(vacancy.get("sector"), SECTOR_LABELS)),
                    ("Kuota", f"{vacancy.get('quota')} peserta"),
                    ("Pengalaman minimum", f"{vacancy.get('minimum_experience_months', 0)} bulan"),
                    (
                        "Bahasa Jepang",
                        " / ".join(
                            f"{language_label(r.get('test_type'))} {r.get('minimum_level')}"
                            for r in vacancy.get("language_requirements", [])
                        )
                        or "Tidak disyaratkan",
                    ),
                ]
            )
            st.caption("Keahlian wajib")
            chips(
                [catalog_label(value) for value in vacancy.get("required_skills", [])]
                or ["Tidak disyaratkan"]
            )
            st.caption("Sertifikasi wajib")
            chips(
                [catalog_label(value) for value in vacancy.get("required_certifications", [])]
                or ["Tidak disyaratkan"]
            )
            if st.button("Cocokkan kandidat", type="primary", width="stretch"):
                st.session_state.selected_vacancy_id = vacancy["id"]
                st.session_state.pop("matching_vac_select", None)
                from minori_frontend.components.navigation import navigate_to

                navigate_to("candidate-matching")
            if is_admin() and vacancy.get("status") == "open":
                with st.popover("Tutup lowongan", width="stretch"):
                    st.write("Lowongan ini tidak lagi menerima kandidat baru.")
                    if st.button("Konfirmasi penutupan", width="stretch"):
                        try:
                            client.close_vacancy(vacancy["id"])
                            show_success("Lowongan berhasil ditutup.")
                            st.rerun()
                        except Exception as exc:
                            show_api_error(exc)


if __name__ == "__main__":
    render_vacancies_page()
