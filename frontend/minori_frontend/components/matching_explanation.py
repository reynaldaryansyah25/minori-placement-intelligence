"""Detailed score breakdown and eligibility explanation for the matching engine."""

from typing import Any

import streamlit as st
from minori_frontend.utils.formatting import format_score


def render_matching_explanation(result: dict[str, Any]) -> None:
    """Render comprehensive explainable matching panel."""
    eligibility = result.get("eligibility_status", "UNKNOWN")
    explanation = result.get("explanation", {})
    score = result.get("total_score")
    is_stale = result.get("is_stale", False)

    # Top summary card
    st.markdown(
        f"""
        <div class="minori-card" style="border-left: 4px solid {"#15803D" if eligibility == "ELIGIBLE" else ("#B7791F" if eligibility == "NEEDS_REVIEW" else "#B91C1C")};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 0.8125rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Status Kelayakan (Eligibility)</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #13263F; margin-top: 2px;">
                        {"Lolos Seleksi Persyaratan (ELIGIBLE)" if eligibility == "ELIGIBLE" else ("Memerlukan Verifikasi Staf (NEEDS_REVIEW)" if eligibility == "NEEDS_REVIEW" else "Tidak Memenuhi Persyaratan (NOT_ELIGIBLE)")}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.8125rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Total Match Score</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #13263F;">
                        {format_score(score) if eligibility == "ELIGIBLE" else "—"}
                    </div>
                </div>
            </div>
            {"<div style='margin-top: 6px; font-size: 12px; color: #B45309;'>⚠️ Evaluasi ini berstatus stale karena profil kandidat atau lowongan telah diperbarui sejak evaluasi terakhir.</div>" if is_stale else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if eligibility != "ELIGIBLE":
        st.info(
            "Sesuai aturan bisnis MINORI: Total Match Score hanya dihitung dan diranking bagi kandidat dengan status **ELIGIBLE**. "
            "Kandidat dengan status *Needs Review* atau *Not Eligible* tidak diikutkan dalam ranking kuota penempatan sebelum persyaratan terpenuhi."
        )

    # Tabs for breakdown and audit checks
    tab_score, tab_checks, tab_policy = st.tabs(
        ["Bobot Skor (Breakdown)", "Pemeriksaan Persyaratan", "Kebijakan & Algoritma"]
    )

    with tab_score:
        score_components = explanation.get("score_components", [])
        if score_components:
            for comp in score_components:
                name = comp.get("name", "Komponen")
                weight = comp.get("weight", 0.0)
                comp_score = comp.get("score", 0.0)
                contrib = comp.get("contribution", 0.0)
                formula = comp.get("formula", "")
                evidence = comp.get("evidence", [])

                pct_score = comp_score * 100
                weight_pct = int(round(weight * 100))

                st.markdown(
                    f"""
                    <div style="margin-bottom: 12px; padding: 10px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-weight: 600; color: #13263F; font-size: 0.875rem;">{name} (Bobot {weight_pct}%)</span>
                            <span style="font-weight: 700; color: #0F766E; font-size: 0.875rem;">{pct_score:.1f}% (Kontribusi: {contrib * 100:.2f} poin)</span>
                        </div>
                        <div class="score-progress-bar-container">
                            <div class="score-progress-bar-fill" style="width: {pct_score}%;"></div>
                        </div>
                        <div style="font-size: 12px; color: #64748B;">Rumus: <code>{formula}</code></div>
                        {f"<div style='font-size: 12px; color: #334155; margin-top: 4px;'><b>Bukti/Fakta:</b> {', '.join(evidence)}</div>" if evidence else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Detail skor tidak tersedia atau belum dihitung.")

    with tab_checks:
        checks = explanation.get("checks", [])
        if checks:
            for chk in checks:
                outcome = chk.get("outcome", "")
                icon = "✅" if outcome == "pass" else ("⚠️" if outcome == "review" else "❌")
                color = (
                    "#15803D"
                    if outcome == "pass"
                    else ("#B45309" if outcome == "review" else "#B91C1C")
                )
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid #F1F5F9;">
                        <span style="font-size: 14px; margin-right: 8px;">{icon}</span>
                        <div>
                            <div style="font-weight: 600; font-size: 13px; color: {color};">[{chk.get("code")}] {chk.get("requirement")}</div>
                            <div style="font-size: 12px; color: #475569;">{chk.get("message")}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        unmet = explanation.get("unmet_requirements", [])
        if unmet:
            st.markdown(
                "<div style='margin-top: 10px; font-weight: 600; color: #B91C1C; font-size: 13px;'>Persyaratan Belum Terpenuhi:</div>",
                unsafe_allow_html=True,
            )
            for u in unmet:
                st.markdown(f"- ❌ {u}")

        verify = explanation.get("verification_needed", [])
        if verify:
            st.markdown(
                "<div style='margin-top: 10px; font-weight: 600; color: #B45309; font-size: 13px;'>Memerlukan Verifikasi Manual Staf:</div>",
                unsafe_allow_html=True,
            )
            for v in verify:
                st.markdown(f"- ⚠️ {v}")

    with tab_policy:
        policy = explanation.get("policy", {})
        st.markdown(f"- **Versi Algoritma:** `{result.get('algorithm_version', '1.0.0')}`")
        st.markdown(f"- **Fingerprint Input:** `{result.get('input_fingerprint', '—')}`")
        st.markdown(f"- **Waktu Evaluasi:** `{result.get('evaluated_at', '—')}`")
        if isinstance(policy, dict):
            st.markdown(f"- **Kebijakan Minimum Score:** `{policy.get('minimum_score', '—')}`")
        elif isinstance(policy, str):
            st.markdown(f"- **Kebijakan Evaluasi:** `{policy}`")
