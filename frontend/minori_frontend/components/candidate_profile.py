"""Detailed candidate profile panel showing qualifications and Japanese job readiness."""

from typing import Any

import streamlit as st
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.utils.formatting import format_program


def render_candidate_profile(candidate: dict[str, Any]) -> None:
    """Render full candidate credentials, tests, experiences, and preferences."""
    st.markdown(
        f"""
        <div class="minori-card" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div>
                    <h3 style="margin: 0; color: #13263F; font-size: 1.25rem;">{candidate.get("full_name", "—")}</h3>
                    <div style="color: #64748B; font-size: 0.8125rem; margin-top: 2px;">
                        Referensi: <b>{candidate.get("reference", "—")}</b> | Domisili: {candidate.get("domicile_city", "—")}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Kemampuan Bahasa & Skill", "Riwayat Pengalaman", "Sertifikasi", "Preferensi & Admin"]
    )

    with tab1:
        st.markdown("**Hasil Tes Bahasa Jepang (JLPT / JFT-Basic)**")
        tests = candidate.get("language_tests", [])
        if tests:
            for t in tests:
                score_str = f" • Skor: {t.get('score')}" if t.get("score") is not None else ""
                st.markdown(
                    f"- **{str(t.get('test_type')).upper()} {t.get('level')}** (Tanggal tes: {t.get('taken_on')}{score_str})"
                )
        else:
            st.caption("Belum ada riwayat tes bahasa resmi tercatat.")

        st.markdown(
            "<hr style='margin: 12px 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True,
        )
        st.markdown("**Keahlian & Kompetensi Kerja (Skills)**")
        skills = candidate.get("skills", [])
        if skills:
            skills_html = " ".join(
                f"<span style='background:#F1F5F9; color:#1E293B; padding:3px 8px; border-radius:4px; font-size:12px; margin-right:4px; display:inline-block; margin-bottom:4px;'>{s}</span>"
                for s in skills
            )
            st.markdown(skills_html, unsafe_allow_html=True)
        else:
            st.caption("Belum ada kode keahlian terdaftar.")

    with tab2:
        st.markdown("**Riwayat Pekerjaan Sebelumnya**")
        experiences = candidate.get("experiences", [])
        if experiences:
            for exp in experiences:
                ended = exp.get("ended_on") or "Sekarang"
                st.markdown(
                    f"""
                    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:10px; margin-bottom:8px;">
                        <div style="font-weight:600; color:#13263F;">{exp.get("role")} — {exp.get("employer_name")}</div>
                        <div style="font-size:12px; color:#64748B;">Sektor: {exp.get("sector")} • Periode: {exp.get("started_on")} s/d {ended}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Tidak ada riwayat pekerjaan sebelumnya.")

    with tab3:
        st.markdown("**Sertifikasi & Lisensi Resmi**")
        certs = candidate.get("certifications", [])
        if certs:
            for c in certs:
                exp_str = (
                    f" • Berlaku s/d: {c.get('expires_on')}"
                    if c.get("expires_on")
                    else " • Berlaku seumur hidup"
                )
                st.markdown(
                    f"- **{c.get('name')}** (`{c.get('code')}`) diterbitkan oleh *{c.get('issuer')}* ({c.get('issued_on')}{exp_str})"
                )
        else:
            st.caption("Belum ada sertifikasi terdaftar.")

    with tab4:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                f"**Program Pilihan:** {format_program(candidate.get('preferred_program'))}"
            )
            st.markdown(f"**Pendidikan Terakhir:** {candidate.get('education_level', '—')}")
            st.markdown("**Status Kesiapan:**")
            render_status_badge(candidate.get("status"))
        with col_b:
            st.markdown("**Preferensi Prefektur Jepang:**")
            prefs = candidate.get("preferred_prefectures", [])
            if prefs:
                st.write(", ".join(prefs))
            else:
                st.caption("Terbuka untuk semua prefektur di Jepang.")
