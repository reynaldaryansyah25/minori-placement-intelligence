"""Shared native form fields for creating or reviewing a vacancy."""

import streamlit as st
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.labels import SECTOR_LABELS, SKILL_LABELS, catalog_label, language_label


def vacancy_fields(prefix, initial=None):
    values = initial or {}
    left, right = st.columns(2)
    with left:
        title = st.text_input(
            "Posisi pekerjaan *", value=values.get("title", ""), key=prefix + "_title"
        )
        employer = st.text_input(
            "Perusahaan pemberi kerja *",
            value=values.get("employer_name", ""),
            key=prefix + "_employer",
        )
        program = st.selectbox(
            "Program",
            [p[0] for p in PROGRAMS],
            index=[p[0] for p in PROGRAMS].index(values.get("program", "ssw")),
            format_func=lambda x: dict(PROGRAMS)[x],
            key=prefix + "_program",
        )
        sector_options = list(dict.fromkeys([*SECTOR_LABELS, values.get("sector", "agriculture")]))
        sector = st.selectbox(
            "Sektor",
            sector_options,
            index=sector_options.index(values.get("sector", "agriculture")),
            format_func=lambda x: catalog_label(x, SECTOR_LABELS),
            key=prefix + "_sector",
        )
    with right:
        prefecture = st.selectbox(
            "Prefektur",
            JAPAN_PREFECTURES,
            index=JAPAN_PREFECTURES.index(values.get("prefecture", "Aichi")),
            key=prefix + "_prefecture",
        )
        quota = st.number_input(
            "Kuota peserta", min_value=1, value=int(values.get("quota", 1)), key=prefix + "_quota"
        )
        minimum = st.number_input(
            "Pengalaman minimum (bulan)",
            min_value=0,
            value=int(values.get("minimum_experience_months", 0)),
            key=prefix + "_experience",
        )
    reqs = values.get("language_requirements", [])
    req = reqs[0] if reqs else {"test_type": "jlpt", "minimum_level": "N4"}
    lang_col, level_col = st.columns(2)
    with lang_col:
        test = st.selectbox(
            "Tes bahasa",
            ["jlpt", "jft_basic"],
            index=["jlpt", "jft_basic"].index(req["test_type"]),
            format_func=language_label,
            key=prefix + "_test",
        )
    with level_col:
        # Both vocabularies remain available inside a form; validate the pair before POST.
        levels = ["N5", "N4", "N3", "N2", "N1", "A1", "A2.1", "A2.2"]
        level = st.selectbox(
            "Tingkat minimum",
            levels,
            index=levels.index(req["minimum_level"]),
            key=prefix + "_level",
        )
    skill_options = list(dict.fromkeys([*SKILL_LABELS, *values.get("required_skills", [])]))
    skills = st.multiselect(
        "Keahlian wajib",
        skill_options,
        default=values.get("required_skills", []),
        format_func=catalog_label,
        accept_new_options=True,
        key=prefix + "_skills",
    )
    cert_options = list(dict.fromkeys([*SKILL_LABELS, *values.get("required_certifications", [])]))
    certs = st.multiselect(
        "Sertifikasi wajib",
        cert_options,
        default=values.get("required_certifications", []),
        format_func=catalog_label,
        accept_new_options=True,
        key=prefix + "_certs",
    )
    return {
        **values,
        "title": title.strip(),
        "employer_name": employer.strip(),
        "program": program,
        "sector": sector,
        "prefecture": prefecture,
        "quota": int(quota),
        "minimum_experience_months": int(minimum),
        "required_skills": [s.strip().lower().replace(" ", "_") for s in skills],
        "required_certifications": [s.strip().lower().replace(" ", "_") for s in certs],
        "language_requirements": [{"test_type": test, "minimum_level": level}, *reqs[1:]],
        "status": "open",
    }


def valid_vacancy(values):
    if not values["title"] or not values["employer_name"]:
        st.error("Lengkapi posisi pekerjaan dan perusahaan pemberi kerja.")
        return False
    req = values["language_requirements"][0]
    if (req["test_type"] == "jlpt") != req["minimum_level"].startswith("N"):
        st.error(
            "Sesuaikan tingkat minimum dengan jenis tes: JLPT memakai N1–N5, JFT-Basic memakai A1–A2.2."
        )
        return False
    return True
