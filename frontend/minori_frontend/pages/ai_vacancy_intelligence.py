"""AI Vacancy Intelligence workflow and manual structured draft editor."""

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import is_admin
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.formatting import format_status_label

SAMPLE_JAPANESE_JOB_TEXT = """
【職種】農業機械オペレーターおよび収穫作業員
【雇用形態】特定技能1号 (SSW)
【勤務地】愛知県豊橋市
【給与】月給 210,000円
【仕事内容】トラクター等の農業機械の運転操作、キャベツ・レタスの収穫、選別、出荷準備作業。
【応募資格】
・日本語能力：JFT-Basic A2以上 または JLPT N4以上
・農業分野の特定技能測定試験（耕種農業）合格者
・実務経験：農業実務経験6ヶ月以上歓迎
【募集人数】2名
"""


def render_ai_vacancy_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)
    can_mutate = is_admin()

    render_page_header(
        title="AI Vacancy Intelligence & Draf Lowongan",
        description="Analisis deskripsi pekerjaan Jepang, peninjauan draft terstruktur, validasi kualifikasi, dan publikasi resmi.",
        breadcrumb="MINORI Intelligence / AI Vacancy Intelligence",
    )

    # --- Section 1: AI Job Description Input & 9Router Boundary ---
    st.markdown("#### 1. Input Deskripsi Lowongan Berbahasa Jepang")
    st.markdown(
        """
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-bottom: 12px; font-size: 13px; color: #475569;">
            ℹ️ <b>Status Integrasi AI:</b> Integrasi model ekstraksi AI saat ini belum diaktifkan (menunggu endpoint use-case 9Router pada backend).
            Staf HR dapat menggunakan teks sumber di bawah ini sebagai acuan dan mengisi form draf terstruktur yang dapat disimpan serta dipublikasikan langsung ke database melalui API.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_raw, col_meta = st.columns([7, 3])
    with col_raw:
        st.text_area(
            "Teks Sumber Lowongan (Bahasa Jepang)",
            value=SAMPLE_JAPANESE_JOB_TEXT,
            height=200,
            help="Tempelkan deskripsi pekerjaan asli dari pemberi kerja Jepang atau dokumen job offer.",
        )
    with col_meta:
        src_channel = st.selectbox(
            "Saluran Sumber (Channel)", options=["email", "portal_partner", "otit", "direct"]
        )
        src_ref = st.text_input("Referensi Dokumen Sumber", value="DOC-AGRI-AICHI-2026")
        if st.button("🤖 Jalankan Ekstraksi AI (9Router)", use_container_width=True):
            st.warning(
                "⚠️ Integrasi AI belum diaktifkan (menunggu ketersediaan endpoint backend 9Router). Gunakan form review manual di bawah."
            )

    st.markdown(
        "<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>",
        unsafe_allow_html=True,
    )

    # --- Section 2: Structured Review and Draft Editor ---
    st.markdown("#### 2. Form Peninjauan & Penyuntingan Draf Lowongan")

    with st.form("form_draft_vacancy"):
        st.markdown("##### Identitas Lowongan")
        c1, c2 = st.columns(2)
        with c1:
            draft_ref = st.text_input("Nomor Referensi Draft *", value="DRAFT-AGRI-001")
            vac_ref = st.text_input("Target Referensi Lowongan Terbit *", value="VAC-AGRI-AICHI-01")
            title = st.text_input("Posisi / Judul Lowongan *", value="Operator Pertanian & Panen")
            employer = st.text_input(
                "Pemberi Kerja / Perusahaan *", value="Toyohashi Agri Cooperative KK"
            )
        with c2:
            prog = st.selectbox(
                "Program Penempatan *",
                options=[p[0] for p in PROGRAMS],
                index=1,
                format_func=lambda x: dict(PROGRAMS)[x],
            )
            sector = st.text_input("Sektor Industri *", value="Agriculture")
            pref = st.selectbox(
                "Prefektur Jepang *",
                options=JAPAN_PREFECTURES,
                index=JAPAN_PREFECTURES.index("Aichi"),
            )
            quota = st.number_input("Kuota Penempatan *", min_value=1, max_value=50, value=2)

        st.markdown("##### Persyaratan Imigrasi & Bahasa")
        c3, c4 = st.columns(2)
        with c3:
            min_exp = st.number_input(
                "Pengalaman Minimum (Bulan)", min_value=0, max_value=120, value=6
            )
            lang_test = st.selectbox("Jenis Tes Bahasa", options=["jft_basic", "jlpt"])
            lang_lvl = st.selectbox("Tingkat Minimum", options=["A2.2", "A2.1", "N4", "N3"])
        with c4:
            skills = st.text_input(
                "Keahlian Wajib (pisahkan koma)", value="AGRICULTURE_GENERAL, TRACTOR_OPERATION"
            )
            certs = st.text_input("Sertifikasi Wajib (pisahkan koma)", value="OTIT_AGRI_LEVEL3")

        col_save, col_pub = st.columns([1, 1])
        with col_save:
            btn_save = st.form_submit_button("💾 Simpan Sebagai Draf", use_container_width=True)
        with col_pub:
            btn_pub = st.form_submit_button(
                "🚀 Publikasikan Langsung ke Database", type="primary", use_container_width=True
            )

        if btn_save or btn_pub:
            if not can_mutate:
                st.error("Akses dibatasi: Anda berada dalam mode Read-Only.")
            elif not draft_ref or not title or not employer:
                st.error("Referensi draf, judul, dan pemberi kerja wajib diisi.")
            else:
                skills_list = [s.strip().upper() for s in skills.split(",") if s.strip()]
                certs_list = [c.strip().upper() for c in certs.split(",") if c.strip()]
                proposed_payload = {
                    "reference": vac_ref.strip(),
                    "title": title.strip(),
                    "employer_name": employer.strip(),
                    "program": prog,
                    "sector": sector.strip(),
                    "prefecture": pref,
                    "quota": quota,
                    "minimum_experience_months": min_exp,
                    "required_skills": skills_list,
                    "required_certifications": certs_list,
                    "preferred_skills": [],
                    "preferred_certifications": [],
                    "language_test_max_age_months": None,
                    "language_requirements": [{"test_type": lang_test, "minimum_level": lang_lvl}],
                    "status": "open",
                    "application_deadline": None,
                }
                draft_data = {
                    "reference": draft_ref.strip(),
                    "source_channel": src_channel,
                    "source_reference": src_ref.strip(),
                    "proposed_data": proposed_payload,
                    "status": "draft",
                    "published_vacancy_id": None,
                }
                try:
                    saved_draft = client.create_vacancy_draft(draft_data)
                    if btn_pub:
                        # Publish immediately
                        published = client.publish_vacancy_draft(saved_draft["id"])
                        show_success(
                            f"Lowongan #{published.get('reference')} berhasil dipublikasikan secara resmi ke database!"
                        )
                    else:
                        show_success(f"Draf #{saved_draft.get('reference')} berhasil disimpan!")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)

    # --- Section 3: Vacancy Drafts History ---
    st.markdown(
        "<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>",
        unsafe_allow_html=True,
    )
    st.markdown("#### 3. Riwayat Draf Lowongan (Vacancy Drafts)")

    try:
        drafts = client.list_vacancy_drafts()
    except Exception:
        drafts = []

    if not drafts:
        st.caption("Belum ada riwayat draf tersimpan.")
    else:
        draft_table = []
        for d in drafts:
            pdata = d.get("proposed_data", {})
            draft_table.append(
                {
                    "id": d.get("id"),
                    "Referensi Draf": d.get("reference"),
                    "Saluran": d.get("source_channel"),
                    "Ref Sumber": d.get("source_reference"),
                    "Judul Pekerjaan": pdata.get("title", "—"),
                    "Pemberi Kerja": pdata.get("employer_name", "—"),
                    "Status": format_status_label(d.get("status")),
                    "Lowongan Terbit": str(d.get("published_vacancy_id"))[:8]
                    if d.get("published_vacancy_id")
                    else "—",
                }
            )

        selected_d = render_interactive_table(draft_table, key="drafts_table", height=240)
        if selected_d and can_mutate:
            d_id = draft_table[selected_d[0]]["id"]
            draft_item = next((d for d in drafts if d["id"] == d_id), None)
            if draft_item and draft_item.get("status") != "published":
                if st.button("🚀 Publikasikan Draf Terpilih", key=f"pub_{d_id}"):
                    try:
                        pub = client.publish_vacancy_draft(d_id)
                        show_success(f"Lowongan {pub.get('title')} berhasil dipublikasikan!")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)


if __name__ == "__main__":
    render_ai_vacancy_page()
