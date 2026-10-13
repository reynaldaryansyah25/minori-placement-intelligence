"""Japanese vacancy explorer and requirement specification management."""

from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import is_admin
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.filters import render_filter_bar
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.formatting import format_program, format_status_label


@st.dialog("Tambah Lowongan Kerja Jepang")
def show_create_vacancy_dialog(client: BackendClient) -> None:
    with st.form("form_create_vacancy"):
        st.markdown("##### Identitas Lowongan")
        col1, col2 = st.columns(2)
        with col1:
            ref = st.text_input("Nomor Referensi *", placeholder="VAC-JP-001")
            title = st.text_input("Judul Lowongan *", placeholder="Operator Pertanian Lapangan")
            employer = st.text_input(
                "Pemberi Kerja / Perusahaan *", placeholder="Yamada Agri Farm KK"
            )
            prog = st.selectbox(
                "Program Penempatan *",
                options=[p[0] for p in PROGRAMS],
                format_func=lambda x: dict(PROGRAMS)[x],
            )
        with col2:
            sector = st.text_input("Sektor Industri *", value="Agriculture")
            pref = st.selectbox(
                "Prefektur Jepang *",
                options=JAPAN_PREFECTURES,
                index=JAPAN_PREFECTURES.index("Aichi"),
            )
            quota = st.number_input(
                "Kuota Penempatan (Peserta) *", min_value=1, max_value=100, value=2
            )
            min_exp = st.number_input(
                "Pengalaman Minimum (Bulan)", min_value=0, max_value=120, value=6
            )

        st.markdown("##### Persyaratan Kompetensi & Bahasa")
        req_skills_raw = st.text_input(
            "Skill Wajib (pisahkan koma)", placeholder="AGRICULTURE_GENERAL, TRACTOR_OPERATION"
        )
        req_certs_raw = st.text_input(
            "Sertifikasi Wajib (pisahkan koma)", placeholder="OTIT_AGRI_LEVEL3"
        )
        lang_test = st.selectbox("Pilihan Jenis Tes Bahasa", options=["jlpt", "jft_basic"])
        lang_lvl = st.selectbox("Level Minimum", options=["N4", "N3", "N2", "A2.2", "A2.1"])

        submitted = st.form_submit_button(
            "Simpan Lowongan", type="primary", use_container_width=True
        )
        if submitted:
            if not ref or not title or not employer:
                st.error("Nomor referensi, judul, dan nama pemberi kerja wajib diisi.")
                return

            req_skills = [s.strip().upper() for s in req_skills_raw.split(",") if s.strip()]
            req_certs = [c.strip().upper() for c in req_certs_raw.split(",") if c.strip()]
            payload = {
                "reference": ref.strip(),
                "title": title.strip(),
                "employer_name": employer.strip(),
                "program": prog,
                "sector": sector.strip(),
                "prefecture": pref,
                "quota": quota,
                "minimum_experience_months": min_exp,
                "required_skills": req_skills,
                "required_certifications": req_certs,
                "preferred_skills": [],
                "preferred_certifications": [],
                "language_test_max_age_months": None,
                "language_requirements": [{"test_type": lang_test, "minimum_level": lang_lvl}],
                "status": "open",
                "application_deadline": None,
            }
            try:
                created = client.create_vacancy(payload)
                show_success(f"Lowongan {created.get('title')} berhasil dipublikasikan!")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)


def render_vacancies_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)

    render_page_header(
        title="Lowongan Penempatan Jepang",
        description="Eksplorasi posisi kerja, persyaratan pemberi kerja, kuota penerimaan, dan kualifikasi imigrasi.",
        breadcrumb="MINORI Operations / Vacancies",
    )

    can_mutate = is_admin()
    if can_mutate:
        col_btn, _ = st.columns([2, 8])
        with col_btn:
            if st.button("➕ Tambah Lowongan", type="primary", use_container_width=True):
                show_create_vacancy_dialog(client)

    # Filter bar
    status_options = [
        ("open", "Aktif (Open)"),
        ("paused", "Ditunda (Paused)"),
        ("closed", "Tutup (Closed)"),
    ]
    filters = render_filter_bar(
        search_placeholder="Cari judul, employer, atau referensi...",
        show_program=True,
        show_status=True,
        status_options=status_options,
        key_prefix="vac",
    )

    try:
        vacancies = client.list_vacancies(
            query=filters.get("query"),
            program=filters.get("program"),
            status=filters.get("status"),
        )
    except Exception as exc:
        show_api_error(exc)
        return

    if not vacancies:
        render_empty_state(
            title="Tidak ada lowongan ditemukan",
            description="Tidak ada data lowongan yang sesuai dengan kriteria filter.",
        )
        return

    # Table view
    table_data = []
    for v in vacancies:
        lang_reqs = v.get("language_requirements", [])
        lang_str = (
            " / ".join(f"{r.get('test_type').upper()} {r.get('minimum_level')}" for r in lang_reqs)
            if lang_reqs
            else "Bebas"
        )
        table_data.append(
            {
                "id": v.get("id"),
                "Referensi": v.get("reference"),
                "Posisi / Judul": v.get("title"),
                "Pemberi Kerja": v.get("employer_name"),
                "Program": format_program(v.get("program")),
                "Prefektur": v.get("prefecture"),
                "Kuota": v.get("quota"),
                "Status": format_status_label(v.get("status")),
                "Syarat Bahasa": lang_str,
                "Min. Pengalaman": f"{v.get('minimum_experience_months', 0)} bln",
            }
        )

    st.markdown("##### Pilih Lowongan untuk Melihat Rincian")
    selected_indices = render_interactive_table(table_data, key="vacancies_table", height=300)

    selected_vac: dict[str, Any] | None = None
    if selected_indices:
        selected_row = selected_indices[0]
        selected_id = table_data[selected_row]["id"]
        try:
            selected_vac = client.get_vacancy(selected_id)
        except Exception as exc:
            show_api_error(exc)
    else:
        selected_vac = vacancies[0]

    if selected_vac:
        st.markdown(
            "<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True,
        )
        col_info, col_actions = st.columns([7, 3])

        with col_info:
            st.markdown(
                f"""
                <div class="minori-card">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <div>
                            <h3 style="margin: 0; color: #13263F; font-size: 1.25rem;">{selected_vac.get("title")}</h3>
                            <div style="font-size: 13px; color: #64748B; margin-top: 2px;">
                                <b>{selected_vac.get("employer_name")}</b> • Prefektur: <b>{selected_vac.get("prefecture")}</b> • Sektor: {selected_vac.get("sector")}
                            </div>
                        </div>
                        <div>
                            <span style="font-size: 12px; font-weight: 600; color: #0F766E; background: #CCFBF1; padding: 4px 8px; border-radius: 4px;">
                                Kuota: {selected_vac.get("quota")} Peserta
                            </span>
                        </div>
                    </div>
                    <div style="margin-top: 14px; font-size: 13px; line-height: 1.6; color: #334155;">
                        <div>📋 <b>Program:</b> {format_program(selected_vac.get("program"))}</div>
                        <div>⏱️ <b>Pengalaman Minimum:</b> {selected_vac.get("minimum_experience_months", 0)} Bulan</div>
                        <div>🗣️ <b>Persyaratan Bahasa (Alternatif):</b> {", ".join(f"{r.get('test_type').upper()} min. {r.get('minimum_level')}" for r in selected_vac.get("language_requirements", [])) or "Tidak ada syarat khusus"}</div>
                        <div>🛠️ <b>Skill Wajib:</b> {", ".join(selected_vac.get("required_skills", [])) or "—"}</div>
                        <div>📜 <b>Sertifikasi Wajib:</b> {", ".join(selected_vac.get("required_certifications", [])) or "—"}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_actions:
            st.markdown("##### Tindakan Operasional")
            if st.button(
                "🎯 Cocokkan Kandidat (Matching)", type="primary", use_container_width=True
            ):
                st.session_state.selected_vacancy_id = selected_vac.get("id")
                st.switch_page("pages/candidate_matching.py")

            if can_mutate and selected_vac.get("status") == "open":
                if st.button("🔒 Tutup Lowongan (Close)", use_container_width=True):
                    try:
                        client.close_vacancy(selected_vac["id"])
                        show_success(f"Lowongan {selected_vac.get('title')} ditutup.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)


if __name__ == "__main__":
    render_vacancies_page()
