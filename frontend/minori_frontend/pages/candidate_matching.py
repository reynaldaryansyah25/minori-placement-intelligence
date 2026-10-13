"""Candidate Matching & Explainable Scoring Explorer — Flagship Operational Page."""

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import get_current_actor, is_admin
from minori_frontend.components.candidate_profile import render_candidate_profile
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.matching_explanation import render_matching_explanation
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_program, format_score, format_status_label


def render_matching_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)

    render_page_header(
        title="Candidate Matching & Explainability Engine",
        description="Mesin evaluasi kelayakan kandidat berbasis aturan kualifikasi, pembobotan transparan, dan keputusan staf HR.",
        breadcrumb="MINORI Intelligence / Candidate Matching",
    )

    can_mutate = is_admin()
    actor = get_current_actor()

    # --- Top Bar: Vacancy Selector & Evaluation Control ---
    try:
        vacancies = client.list_vacancies(status="open")
        if not vacancies:
            vacancies = client.list_vacancies()
    except Exception as exc:
        show_api_error(exc)
        return

    if not vacancies:
        render_empty_state(
            title="Tidak ada lowongan tersedia",
            description="Tambahkan lowongan kerja terlebih dahulu untuk melakukan proses matching.",
        )
        return

    vac_options = {
        v["id"]: f"{v['title']} ({v['employer_name']}) — Kuota: {v['quota']}" for v in vacancies
    }

    # Check if a vacancy was pre-selected from Vacancies page
    preselected_id = st.session_state.get("selected_vacancy_id")
    default_idx = 0
    if preselected_id and preselected_id in vac_options:
        default_idx = list(vac_options.keys()).index(preselected_id)

    col_select, col_eval = st.columns([7, 3])
    with col_select:
        selected_vac_id = st.selectbox(
            "Pilih Lowongan Kerja Target",
            options=list(vac_options.keys()),
            format_func=lambda vid: vac_options[vid],
            index=default_idx,
            key="matching_vac_select",
        )
    with col_eval:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if can_mutate:
            if st.button("⚡ Evaluasi Ulang (Recompute)", type="primary", use_container_width=True):
                try:
                    with st.spinner("Menghitung ulang evaluasi kualifikasi..."):
                        client.evaluate_matching(vacancy_id=selected_vac_id)
                    show_success("Evaluasi matching berhasil diperbarui secara atomik!")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
        else:
            st.button(
                "⚡ Evaluasi Ulang (Recompute)",
                disabled=True,
                help="Hanya staf/admin yang dapat melakukan recompute.",
                use_container_width=True,
            )

    # Fetch vacancy details
    current_vac = next((v for v in vacancies if v["id"] == selected_vac_id), None)
    if not current_vac:
        return

    # Vacancy info badge
    st.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; color: #334155;">
            <b>Pemberi Kerja:</b> {current_vac.get("employer_name")} &nbsp; | &nbsp;
            <b>Prefektur:</b> {current_vac.get("prefecture")} &nbsp; | &nbsp;
            <b>Program:</b> {format_program(current_vac.get("program"))} &nbsp; | &nbsp;
            <b>Kapasitas Kuota:</b> <span style="color:#0F766E; font-weight:700;">{current_vac.get("quota")} Peserta</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch ranking list
    try:
        ranking_list = client.get_ranking(selected_vac_id)
    except Exception as exc:
        show_api_error(exc)
        ranking_list = []

    # Fetch all evaluation history / results for this vacancy (to include Needs Review & Not Eligible)
    try:
        all_evals = client.list_matching_results(vacancy_id=selected_vac_id)
    except Exception:
        all_evals = []

    # Fetch all candidates map
    try:
        all_candidates = {c["id"]: c for c in client.list_candidates()}
    except Exception:
        all_candidates = {}

    st.markdown("#### 1. Peringkat Kandidat Eligible (Live Ranking)")

    if not ranking_list:
        st.warning(
            "Belum ada kandidat berstatus ELIGIBLE yang lolos untuk lowongan ini. "
            "Gunakan tombol 'Evaluasi Ulang' atau periksa tab Semua Pasangan di bawah."
        )
    else:
        rank_table_data = []
        for r in ranking_list:
            cid = r.get("candidate_id")
            cand_obj = all_candidates.get(cid, {})
            tests = cand_obj.get("language_tests", [])
            lang_str = (
                ", ".join(f"{t.get('test_type').upper()} {t.get('level')}" for t in tests)
                if tests
                else "—"
            )

            rank_table_data.append(
                {
                    "Rank": f"#{r.get('rank')}",
                    "candidate_id": cid,
                    "Nama Kandidat": cand_obj.get("full_name", r.get("candidate_reference")),
                    "Referensi": r.get("candidate_reference"),
                    "Program": format_program(cand_obj.get("preferred_program")),
                    "Kualifikasi Bahasa": lang_str,
                    "Kelayakan": "ELIGIBLE",
                    "Total Match Score": format_score(r.get("total_score")),
                    "Keputusan Staf": format_status_label(r.get("staff_status")),
                }
            )

        render_interactive_table(
            rank_table_data,
            key="ranking_table",
            height=240,
        )

    # View all evaluated pairs (including NEEDS_REVIEW and NOT_ELIGIBLE)
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 2. Eksplorasi Evaluasi Detail & Penjelasan Kelayakan")

    pair_options = {}
    for ev in all_evals:
        cid = ev.get("candidate_id")
        cand_obj = all_candidates.get(cid, {})
        cname = cand_obj.get("full_name", ev.get("candidate_reference", "Kandidat"))
        status_label = ev.get("eligibility_status")
        pair_options[cid] = f"{cname} ({ev.get('candidate_reference')}) — [{status_label}]"

    if not pair_options:
        st.info(
            "Belum ada riwayat evaluasi tersimpan. Klik 'Evaluasi Ulang (Recompute)' di atas untuk mengevaluasi semua kandidat."
        )
        return

    selected_cid = st.selectbox(
        "Pilih Kandidat untuk Ditinjau Rincian Skor & Pemeriksaannya",
        options=list(pair_options.keys()),
        format_func=lambda cid: pair_options[cid],
        key="selected_detail_candidate",
    )

    try:
        explanation_result = client.get_explanation(selected_cid, selected_vac_id)
    except Exception as exc:
        show_api_error(exc)
        return

    # Render Matching Explanation Panel
    render_matching_explanation(explanation_result)

    # Candidate Profile drawer
    selected_cand_obj = all_candidates.get(selected_cid)
    if selected_cand_obj:
        with st.expander("👤 Lihat Profil Lengkap Kandidat", expanded=False):
            render_candidate_profile(selected_cand_obj)

    # --- Staff Action Section ---
    st.markdown("#### 3. Keputusan Staf & Operasi Penempatan")
    current_staff_status = explanation_result.get("staff_status", "proposed")
    is_eligible = explanation_result.get("eligibility_status") == "ELIGIBLE"
    match_id = explanation_result.get("match_id")

    col_dec1, col_dec2, col_dec3 = st.columns([1, 1, 1])

    with col_dec1:
        st.markdown("**Status Staf Saat Ini:**")
        render_status_badge(current_staff_status)

    with col_dec2:
        if can_mutate:
            if current_staff_status != "approved":
                if st.button(
                    "✅ Setujui Kandidat (Approve)", type="primary", use_container_width=True
                ):
                    try:
                        client.decide_match(
                            candidate_id=selected_cid,
                            vacancy_id=selected_vac_id,
                            decision="approved",
                            actor_reference=actor,
                        )
                        show_success("Kandidat berhasil disetujui untuk lowongan ini!")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
            else:
                st.info("Kandidat telah disetujui staf.")
        else:
            st.caption("Aksi persetujuan memerlukan akses staf/admin.")

    with col_dec3:
        if can_mutate:
            if current_staff_status != "rejected":
                if st.button("❌ Tolak Kandidat (Reject)", use_container_width=True):
                    try:
                        client.decide_match(
                            candidate_id=selected_cid,
                            vacancy_id=selected_vac_id,
                            decision="rejected",
                            actor_reference=actor,
                            reason_code="MANUAL_REJECT",
                        )
                        show_success("Kandidat ditolak untuk lowongan ini.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
        else:
            st.caption("Aksi penolakan memerlukan akses staf/admin.")

    # Create Placement Action (Only if Approved and Eligible)
    st.markdown(
        "<hr style='margin: 14px 0; border: none; border-top: 1px solid #E2E8F0;'>",
        unsafe_allow_html=True,
    )
    if is_eligible and current_staff_status == "approved" and match_id:
        st.markdown("##### 🚀 Alokasi Penempatan (Create Placement)")
        st.caption(
            "Kandidat telah lolos seleksi kelayakan dan disetujui staf. Siap dialokasikan ke kuota penempatan resmi."
        )
        if can_mutate:
            with st.form("form_create_placement"):
                pref_code = f"PLC-{selected_cand_obj.get('reference', 'CAND')[:10]}-{current_vac.get('reference', 'VAC')[:10]}"
                plc_ref = st.text_input("Nomor Referensi Penempatan", value=pref_code)
                plc_submit = st.form_submit_button(
                    "Buat Penempatan Resmi (Placement)", type="primary"
                )
                if plc_submit:
                    try:
                        created_plc = client.create_placement(
                            reference=plc_ref.strip(),
                            match_id=match_id,
                            actor_reference=actor,
                        )
                        show_success(f"Penempatan #{created_plc.get('reference')} berhasil dibuat!")
                        st.switch_page("pages/placement_pipeline.py")
                    except Exception as exc:
                        show_api_error(exc)
        else:
            st.info("Pembuatan penempatan memerlukan otorisasi staf admin.")
    else:
        st.caption(
            "💡 Penempatan resmi hanya dapat dibuat setelah kandidat dinyatakan **ELIGIBLE** dan disetujui (**APPROVED**) oleh staf."
        )


if __name__ == "__main__":
    render_matching_page()
