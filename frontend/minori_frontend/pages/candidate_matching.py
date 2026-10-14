"""Vacancy ranking, explainable evaluation, and existing staff operations."""

from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import get_current_actor, is_admin
from minori_frontend.components.candidate_profile import render_candidate_profile
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.matching_explanation import (
    render_matching_explanation,
    render_policy_note,
)
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import detail_grid, section
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_score, format_status_label
from minori_frontend.utils.labels import program_short


def render_matching_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Pencocokan kandidat",
        "Bandingkan kualifikasi dengan kebutuhan lowongan dan tinjau dasar penilaiannya.",
    )
    try:
        vacancies = read_all(client.list_vacancies, status="open") or read_all(
            client.list_vacancies,
        )
    except Exception as exc:
        show_api_error(exc)
        return
    if not vacancies:
        render_empty_state(
            "Belum ada lowongan", "Tambahkan lowongan sebelum mengevaluasi kecocokan kandidat."
        )
        return
    options = {v["id"]: f"{v['title']} · {v['employer_name']}" for v in vacancies}
    handoff = st.session_state.pop("matching_handoff", {})
    if handoff.get("vacancy_id") in options:
        st.session_state["matching_vac_select"] = handoff["vacancy_id"]
    if handoff.get("candidate_id"):
        st.session_state["selected_detail_candidate"] = handoff["candidate_id"]
        st.session_state["matching_view"] = "Semua kandidat"
        st.session_state.pop("matching_table_selection", None)
    preferred = st.session_state.get("selected_vacancy_id")
    selected_index = list(options).index(preferred) if preferred in options else 0
    selector, action = st.columns([4, 1], vertical_alignment="bottom")
    with selector:
        vacancy_id = st.selectbox(
            "Lowongan yang ditinjau",
            list(options),
            format_func=options.get,
            index=selected_index,
            key="matching_vac_select",
        )
    with action:
        if st.button("Evaluasi ulang", type="primary", disabled=not is_admin(), width="stretch"):
            try:
                with st.spinner("Mengevaluasi kualifikasi kandidat…"):
                    client.evaluate_matching(vacancy_id=vacancy_id)
                show_success("Evaluasi kandidat berhasil diperbarui.")
                st.rerun()
            except Exception as exc:
                show_api_error(exc)
    vacancy = next(v for v in vacancies if v["id"] == vacancy_id)
    with st.container(border=True):
        detail_grid(
            [
                ("Perusahaan", vacancy.get("employer_name")),
                ("Prefektur", vacancy.get("prefecture")),
                ("Program", program_short(vacancy.get("program"))),
                ("Kuota", f"{vacancy.get('quota')} peserta"),
            ]
        )
    try:
        ranking = read_all(client.get_ranking, vacancy_id)
        evaluations = read_all(client.get_current_candidates, vacancy_id)
        candidates = {
            c["id"]: c
            for c in read_all(
                client.list_candidates,
            )
        }
    except Exception as exc:
        show_api_error(exc)
        return
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        with st.container(border=True):
            section(
                "Kandidat untuk lowongan ini",
                "Peringkat hanya menampilkan kandidat yang memenuhi persyaratan.",
            )
            view = st.radio(
                "Tampilan kandidat",
                ["Semua kandidat", "Peringkat"],
                horizontal=True,
                label_visibility="collapsed",
                key="matching_view",
            )
            records = (
                ranking
                if view == "Peringkat"
                else list({ev["candidate_id"]: ev for ev in reversed(evaluations)}.values())
            )
            if not records:
                st.info(
                    "Belum ada hasil pada tampilan ini. Pilih Semua kandidat atau jalankan evaluasi ulang."
                )
            rows = [
                {
                    "candidate_id": row["candidate_id"],
                    "Kandidat": candidates.get(row["candidate_id"], {}).get(
                        "full_name", "Kandidat"
                    ),
                    "Kelayakan": format_status_label(row.get("eligibility_status", "ELIGIBLE")),
                    "Skor": format_score(row.get("total_score")),
                    "Keputusan": format_status_label(row.get("staff_status", "proposed")),
                }
                for row in records
            ]
            selected = render_interactive_table(
                rows, key="ranking_table", height=370, default_first=False
            )
    available = list(dict.fromkeys(row["candidate_id"] for row in (records or evaluations)))
    if not available:
        return
    signature = (
        (vacancy_id, view, records[selected[0]]["candidate_id"]) if selected and records else None
    )
    if signature and signature != st.session_state.get("matching_table_selection"):
        st.session_state["selected_detail_candidate"] = signature[2]
        st.session_state["matching_table_selection"] = signature
    if st.session_state.get("selected_detail_candidate") not in available:
        st.session_state["selected_detail_candidate"] = available[0]
    with right:
        with st.container(border=True):
            section("Rincian kecocokan")
            candidate_id = st.selectbox(
                "Kandidat yang ditinjau",
                available,
                format_func=lambda cid: candidates.get(cid, {}).get("full_name", "Kandidat"),
                key="selected_detail_candidate",
            )
            try:
                result = client.get_explanation(candidate_id, vacancy_id)
            except Exception as exc:
                show_api_error(exc)
                return
            render_matching_explanation(result)
            ai_key = "matching_ai_" + candidate_id + "_" + vacancy_id
            if st.button("Jelaskan dengan AI", disabled=not is_admin(), width="stretch"):
                try:
                    with st.spinner("Menjelaskan hasil resmi…"):
                        st.session_state[ai_key] = client.explain_with_ai(candidate_id, vacancy_id)
                except Exception as exc:
                    show_api_error(exc)
            explanation_ai = st.session_state.get(ai_key)
            if explanation_ai:
                if (
                    explanation_ai["official"].get("input_fingerprint")
                    != result.get("input_fingerprint")
                    or explanation_ai["official"]["eligibility_status"]
                    != result.get("eligibility_status")
                    or explanation_ai["official"]["total_score"] != result.get("total_score")
                    or explanation_ai["official"]["staff_status"]
                    != result.get("staff_status", "proposed")
                ):
                    st.info("Hasil resmi berubah. Jalankan kembali penjelasan AI.")
                else:
                    st.caption(
                        "Penjelasan AI untuk ditinjau staf; keputusan mengikuti hasil resmi di atas."
                    )
                    st.text(explanation_ai["narrative"]["summary"])
                    for key, label in [
                        ("strengths", "Keunggulan"),
                        ("unmet_requirements", "Belum dipenuhi"),
                        ("verification_needed", "Perlu verifikasi"),
                        ("next_steps", "Langkah administratif"),
                    ]:
                        st.write(label)
                        for item in explanation_ai["narrative"][key]:
                            st.text("• " + item)
            with st.expander("Profil kandidat"):
                render_candidate_profile(candidates.get(candidate_id, {}))
                if st.button("Edit kualifikasi kandidat", disabled=not is_admin(), width="stretch"):
                    st.session_state["candidate_saved_id"] = candidate_id
                    from minori_frontend.components.navigation import navigate_to

                    navigate_to("candidates")
            render_policy_note()
            status = result.get("staff_status", "proposed")
            render_status_badge(status)
            eligible = result.get("eligibility_status") == "ELIGIBLE"
            approve, reject = st.columns(2)
            with approve:
                if st.button(
                    "Setujui kandidat",
                    type="primary",
                    disabled=not is_admin()
                    or status == "approved"
                    or result.get("eligibility_status") == "NOT_ELIGIBLE",
                    width="stretch",
                ):
                    try:
                        decision = client.decide_match(
                            candidate_id, vacancy_id, "approved", get_current_actor()
                        )
                        st.session_state["approved_match_handoff"] = decision["id"]
                        show_success(
                            "Persetujuan disimpan. Lanjutkan persiapan penempatan peserta."
                        )
                        from minori_frontend.components.navigation import navigate_to

                        navigate_to("placement-pipeline")
                    except Exception as exc:
                        show_api_error(exc)
            with reject:
                if st.button(
                    "Tolak kandidat",
                    disabled=not is_admin() or status == "rejected",
                    width="stretch",
                ):
                    try:
                        client.decide_match(
                            candidate_id,
                            vacancy_id,
                            "rejected",
                            get_current_actor(),
                            reason_code="MANUAL_REJECT",
                        )
                        show_success("Keputusan penolakan berhasil disimpan.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)
            if eligible and status == "approved" and result.get("match_id"):
                try:
                    existing = read_all(
                        client.list_placements, candidate_id=candidate_id, vacancy_id=vacancy_id
                    )
                except Exception as exc:
                    show_api_error(exc)
                    return
                existing = [
                    p
                    for p in existing
                    if p["candidate_id"] == candidate_id and p["vacancy_id"] == vacancy_id
                ]
                if existing and st.button("Buka alur penempatan", width="stretch"):
                    st.session_state["placement_handoff_id"] = existing[0]["id"]
                    from minori_frontend.components.navigation import navigate_to

                    navigate_to("placement-pipeline")
                if not existing and st.button(
                    "Buat penempatan", disabled=not is_admin(), width="stretch"
                ):
                    try:
                        created = client.create_placement(
                            "PLC-" + uuid4().hex[:12].upper(),
                            result["match_id"],
                            get_current_actor(),
                        )
                        show_success("Penempatan berhasil dibuat.")
                        st.session_state["placement_handoff_id"] = created["id"]
                        from minori_frontend.components.navigation import navigate_to

                        navigate_to("placement-pipeline")
                    except Exception as exc:
                        show_api_error(exc)
            else:
                st.caption(
                    "Penempatan tersedia setelah kandidat memenuhi syarat dan disetujui staf."
                )


if __name__ == "__main__":
    render_matching_page()
