"""Detailed score breakdown and eligibility explanation for the matching engine."""

import json
from typing import Any

import streamlit as st
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_score


def _safe_dict(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


COMPONENT_LABELS = {
    "language": "Kemampuan Bahasa Jepang",
    "experience": "Pengalaman Kerja Relevan",
    "additional_qualifications": "Sertifikasi & Kualifikasi Tambahan",
    "preference_readiness": "Kesesuaian Preferensi & Kesiapan",
}


def render_matching_explanation(result: dict[str, Any] | str | None) -> None:
    """Render comprehensive explainable matching panel without technical jargon."""
    res_dict = _safe_dict(result)
    eligibility = res_dict.get("eligibility_status", "UNKNOWN")
    explanation = _safe_dict(res_dict.get("explanation"))
    score = res_dict.get("total_score")
    is_stale = res_dict.get("is_stale", False)

    # Human-friendly eligibility presentation
    if eligibility == "ELIGIBLE":
        status_label = "Memenuhi Persyaratan"
        card_border = "#15803D"
    elif eligibility == "NEEDS_REVIEW":
        status_label = "Perlu Verifikasi Staf"
        card_border = "#B7791F"
    else:
        status_label = "Belum Memenuhi Persyaratan"
        card_border = "#B91C1C"

    # Top summary card
    st.markdown(
        f"""
        <div class="minori-card" style="border-left: 4px solid {card_border};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 0.8125rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Status Kelayakan Rekrutmen</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #13263F; margin-top: 2px;">
                        {status_label}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.8125rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Skor Kecocokan (Match Score)</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #13263F;">
                        {format_score(score) if eligibility == "ELIGIBLE" else "—"}
                    </div>
                </div>
            </div>
            {"<div style='margin-top: 6px; font-size: 12px; color: #B45309;'>⚠️ Evaluasi ini memerlukan peninjauan ulang karena data kandidat atau lowongan baru saja diperbarui.</div>" if is_stale else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if eligibility != "ELIGIBLE":
        st.info(
            "Total Match Score hanya dihitung untuk kandidat yang berstatus **Memenuhi Persyaratan**. "
            "Kandidat yang masih memerlukan verifikasi atau belum memenuhi syarat disaring terlebih dahulu agar kuota penempatan terisi secara tepat."
        )

    # Tabs for breakdown and audit checks
    tab_score, tab_checks, tab_policy = st.tabs(
        ["Bobot Skor Evaluasi", "Pemeriksaan Persyaratan", "Kebijakan & Bobot Penilaian"]
    )

    with tab_score:
        score_components = explanation.get("score_components", [])
        if isinstance(score_components, list) and score_components:
            for comp in score_components:
                if not isinstance(comp, dict):
                    continue
                raw_name = comp.get("name", "Komponen")
                name = COMPONENT_LABELS.get(raw_name, raw_name.replace("_", " ").title())
                weight = float(comp.get("weight", 0.0) or 0.0)
                comp_score = float(comp.get("score", 0.0) or 0.0)
                contrib = float(comp.get("contribution", 0.0) or 0.0)
                evidence = comp.get("evidence", [])

                pct_score = comp_score * 100
                weight_pct = int(round(weight * 100))

                evidence_text = ""
                if isinstance(evidence, list) and evidence:
                    evidence_text = ", ".join(str(e) for e in evidence)
                elif isinstance(evidence, dict) and evidence:
                    evidence_text = ", ".join(f"{k}: {v}" for k, v in evidence.items())

                st.markdown(
                    f"""
                    <div style="margin-bottom: 12px; padding: 10px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px;">
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-weight: 600; color: #13263F; font-size: 0.875rem;">{name} (Porsi {weight_pct}%)</span>
                            <span style="font-weight: 700; color: #0F766E; font-size: 0.875rem;">Nilai: {pct_score:.1f}% (Kontribusi: {contrib * 100:.1f} poin)</span>
                        </div>
                        <div class="score-progress-bar-container">
                            <div class="score-progress-bar-fill" style="width: {min(100.0, max(0.0, pct_score))}%;"></div>
                        </div>
                        {f"<div style='font-size: 12px; color: #475569; margin-top: 6px;'><b>Fakta Dokumen:</b> {evidence_text}</div>" if evidence_text else ""}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption(
                "Rincian pembobotan skor tidak tersedia atau kandidat belum lolos syarat eliminasi."
            )

    with tab_checks:
        checks = explanation.get("checks", [])
        if isinstance(checks, list) and checks:
            for chk in checks:
                if not isinstance(chk, dict):
                    continue
                outcome = str(chk.get("outcome", "")).lower()
                icon = "✅" if outcome == "pass" else ("⚠️" if outcome == "review" else "❌")
                color = (
                    "#15803D"
                    if outcome == "pass"
                    else ("#B45309" if outcome == "review" else "#B91C1C")
                )
                req_title = str(chk.get("requirement", "Persyaratan")).replace("_", " ").title()
                msg = str(chk.get("message", "Pemeriksaan selesai."))

                st.markdown(
                    f"""
                    <div style="display: flex; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid #F1F5F9;">
                        <span style="font-size: 15px; margin-right: 8px; line-height: 1.2;">{icon}</span>
                        <div>
                            <div style="font-weight: 600; font-size: 13px; color: {color};">{req_title}</div>
                            <div style="font-size: 12px; color: #475569; margin-top: 2px;">{msg}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        unmet = explanation.get("unmet_requirements", [])
        if isinstance(unmet, list) and unmet:
            st.markdown(
                "<div style='margin-top: 12px; font-weight: 600; color: #B91C1C; font-size: 13px;'>Persyaratan Yang Belum Terpenuhi:</div>",
                unsafe_allow_html=True,
            )
            for u in unmet:
                st.markdown(f"- ❌ {u}")

        verify = explanation.get("verification_needed", [])
        if isinstance(verify, list) and verify:
            st.markdown(
                "<div style='margin-top: 12px; font-weight: 600; color: #B45309; font-size: 13px;'>Perlu Verifikasi Manual Staf:</div>",
                unsafe_allow_html=True,
            )
            for v in verify:
                st.markdown(f"- ⚠️ {v}")

    with tab_policy:
        evaluated_at = res_dict.get("evaluated_at")
        st.markdown(f"- **Waktu Evaluasi Terakhir:** {format_datetime_id(evaluated_at)}")
        st.markdown(
            "- **Prinsip Seleksi:** Penilaian transparan berbasis bukti dokumen dan persyaratan pemberi kerja."
        )
        st.markdown(
            """
            - **Struktur Bobot Baku Minori:**
              - Kemampuan Bahasa Jepang: **35%** (JLPT / JFT-Basic resmi)
              - Pengalaman Kerja Terkait: **30%** (Riwayat kerja di sektor relevan)
              - Sertifikasi & Keahlian Khusus: **20%** (Kualifikasi teknis profesi)
              - Kesesuaian Preferensi & Kesiapan: **15%** (Kecocokan prefektur & status kandidat)
            """
        )
