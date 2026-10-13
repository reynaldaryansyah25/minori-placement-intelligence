"""Readable qualification checks and weighted scores returned by the backend."""

import json

import streamlit as st
from minori_frontend.components.presentation import html, section, text
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_score

COMPONENT_LABELS = {
    "language": "Bahasa Jepang",
    "experience": "Pengalaman relevan",
    "additional_qualifications": "Keahlian dan sertifikasi",
    "preference_readiness": "Preferensi dan kesiapan",
}


def _safe_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            pass
    return {}


def render_matching_explanation(result):
    result = _safe_dict(result)
    explanation = _safe_dict(result.get("explanation"))
    eligibility = result.get("eligibility_status")
    render_status_badge(eligibility)
    score = format_score(result.get("total_score")) if eligibility == "ELIGIBLE" else "—"
    html(
        f'<div class="event-row"><div><p>Skor kecocokan</p><div class="score-value">{text(score)}</div></div>'
        "<small>Skor digunakan setelah seluruh<br>persyaratan wajib terpenuhi.</small></div>"
    )
    if result.get("is_stale"):
        st.warning(
            "Data telah berubah sejak evaluasi terakhir. Evaluasi ulang sebelum mengambil keputusan."
        )
    scores, checks = st.tabs(["Rincian skor", "Persyaratan"])
    with scores:
        components = explanation.get("score_components", [])
        for component in components:
            if not isinstance(component, dict):
                continue
            amount = min(100, max(0, float(component.get("score") or 0) * 100))
            weight = float(component.get("weight") or 0) * 100
            contribution = float(component.get("contribution") or 0) * 100
            html(
                f'<div class="bars"><div><div class="bar-head">'
                f"<span>{text(COMPONENT_LABELS.get(component.get('name'), 'Komponen penilaian'))} · {weight:.0f}%</span>"
                f'<strong>{contribution:.1f} poin</strong></div><div class="bar-track" role="img" '
                f'aria-label="Nilai {amount:.1f} persen"><div class="bar-fill" style="width:{amount:.1f}%"></div></div></div></div>'
            )
        if not components:
            st.caption("Skor belum dihitung karena persyaratan wajib masih perlu ditinjau.")
    with checks:
        for check in explanation.get("checks", []):
            if not isinstance(check, dict):
                continue
            outcome = str(check.get("outcome", "")).lower()
            outcome_label = {
                "pass": "Terpenuhi",
                "fail": "Belum terpenuhi",
                "review": "Perlu verifikasi",
                "info": "Informasi",
            }.get(outcome, "Informasi")
            color = {"pass": "#187451", "fail": "#aa3b44", "review": "#a56815"}.get(
                outcome, "#617087"
            )
            message = str(check.get("message") or "Tinjau kelengkapan dokumen kandidat.")
            for old, new in (
                ("Skill", "Keahlian"),
                ("open", "aktif"),
                ("union hari", "hari kerja tanpa tumpang tindih"),
            ):
                message = message.replace(old, new)
            html(
                f'<div class="event-row"><div><strong style="color:{color}">{text(outcome_label)}</strong>'
                f"<p>{text(message)}</p></div></div>"
            )
        if not explanation.get("checks"):
            st.caption("Pemeriksaan persyaratan belum tersedia.")
    st.caption("Evaluasi terakhir: " + format_datetime_id(result.get("evaluated_at")))
    with st.expander("Tentang penilaian"):
        st.write(
            "Penilaian mengikuti persyaratan pemberi kerja. Persetujuan staf tetap diperlukan sebelum penempatan."
        )
        for name, weight in [
            ("Bahasa Jepang", 35),
            ("Pengalaman relevan", 30),
            ("Keahlian dan sertifikasi", 20),
            ("Preferensi dan kesiapan", 15),
        ]:
            st.caption(f"{name}: {weight}%")


def render_policy_note():
    section("Keputusan staf", "Tinjau persyaratan dan profil sebelum memberikan persetujuan.")
