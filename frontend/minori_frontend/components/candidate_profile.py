"""Candidate qualifications, without identifiers or internal catalog codes."""

import streamlit as st
from minori_frontend.components.presentation import chips, detail_grid, html, text
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.utils.formatting import format_program
from minori_frontend.utils.labels import SECTOR_LABELS, catalog_label, language_label


def render_candidate_profile(candidate):
    name = candidate.get("full_name") or "Kandidat"
    initials = "".join(part[0] for part in name.split()[:2])
    html(
        f'<div class="profile-head"><div class="avatar">{text(initials)}</div><div>'
        f"<h3>{text(name)}</h3><p>{text(candidate.get('domicile_city'))} · {text(candidate.get('education_level'))}</p></div></div>"
    )
    render_status_badge(candidate.get("status"))
    detail_grid(
        [
            ("Program", format_program(candidate.get("preferred_program"))),
            (
                "Preferensi prefektur",
                ", ".join(candidate.get("preferred_prefectures", [])) or "Semua prefektur",
            ),
        ]
    )
    language, experience, certification = st.tabs(["Kualifikasi", "Pengalaman", "Sertifikasi"])
    with language:
        st.caption("Kemampuan bahasa Jepang")
        tests = candidate.get("language_tests", [])
        if tests:
            for item in tests:
                detail_grid(
                    [
                        (language_label(item.get("test_type")), item.get("level")),
                        ("Tanggal tes", item.get("taken_on")),
                    ]
                )
        else:
            st.caption("Belum ada hasil tes bahasa yang tercatat.")
        st.caption("Keahlian")
        chips([catalog_label(skill) for skill in candidate.get("skills", [])])
        if not candidate.get("skills"):
            st.caption("Belum ada keahlian yang tercatat.")
    with experience:
        for item in candidate.get("experiences", []):
            html(
                f'<div class="event-row"><div><strong>{text(item.get("role"))}</strong>'
                f"<p>{text(item.get('employer_name'))} · {text(catalog_label(item.get('sector'), SECTOR_LABELS))}</p>"
                f"<p>{text(item.get('started_on'))} – {text(item.get('ended_on') or 'Sekarang')}</p></div></div>"
            )
        if not candidate.get("experiences"):
            st.caption("Belum ada pengalaman kerja yang tercatat.")
    with certification:
        for item in candidate.get("certifications", []):
            html(
                f'<div class="event-row"><div><strong>{text(item.get("name"))}</strong>'
                f"<p>{text(item.get('issuer'))}</p><p>Terbit: {text(item.get('issued_on'))} · "
                f"Berlaku hingga: {text(item.get('expires_on') or 'Tidak dibatasi')}</p></div></div>"
            )
        if not candidate.get("certifications"):
            st.caption("Belum ada sertifikasi yang tercatat.")
