"""Shared native form fields for creating or reviewing a vacancy."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import streamlit as st
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.labels import SECTOR_LABELS, SKILL_LABELS, catalog_label, language_label


def vacancy_fields(prefix, initial=None, *, allow_unknown=False):
    values = initial or {}
    left, right = st.columns(2)
    with left:
        title = st.text_input(
            "Posisi pekerjaan *", value=values.get("title") or "", key=prefix + "_title"
        )
        employer = st.text_input(
            "Perusahaan pemberi kerja *",
            value=values.get("employer_name") or "",
            key=prefix + "_employer",
        )
        programs = ([None] if allow_unknown else []) + [p[0] for p in PROGRAMS]
        program_value = values.get("program") if allow_unknown else values.get("program", "ssw")
        program = st.selectbox(
            "Program",
            programs,
            index=programs.index(program_value),
            format_func=lambda x: dict(PROGRAMS).get(x, "Perlu Konfirmasi"),
            key=prefix + "_program",
        )
        sector_value = (
            values.get("sector") if allow_unknown else values.get("sector", "agriculture")
        )
        sector_options = list(
            dict.fromkeys([*([None] if allow_unknown else []), *SECTOR_LABELS, sector_value])
        )
        sector = st.selectbox(
            "Sektor",
            sector_options,
            index=sector_options.index(sector_value),
            format_func=lambda x: catalog_label(x, SECTOR_LABELS) if x else "Perlu Konfirmasi",
            key=prefix + "_sector",
        )
    with right:
        prefecture_value = (
            values.get("prefecture") if allow_unknown else values.get("prefecture", "Aichi")
        )
        prefectures = list(
            dict.fromkeys(
                [*([None] if allow_unknown else []), *JAPAN_PREFECTURES, prefecture_value]
            )
        )
        prefecture = st.selectbox(
            "Prefektur",
            prefectures,
            index=prefectures.index(prefecture_value),
            format_func=lambda x: x or "Perlu Konfirmasi",
            key=prefix + "_prefecture",
        )
        quota = st.number_input(
            "Kuota peserta",
            min_value=0 if allow_unknown else 1,
            value=int(values.get("quota") or (0 if allow_unknown else 1)),
            key=prefix + "_quota",
        )
        minimum = st.number_input(
            "Pengalaman minimum (bulan)",
            min_value=0,
            value=values.get("minimum_experience_months")
            if allow_unknown
            else int(values.get("minimum_experience_months", 0)),
            key=prefix + "_experience",
        )
    reqs = values.get("language_requirements", [])
    req = reqs[0] if reqs else {"test_type": None, "minimum_level": "N4"}
    lang_col, level_col = st.columns(2)
    with lang_col:
        test = st.selectbox(
            "Tes bahasa",
            [None, "jlpt", "jft_basic"],
            index=[None, "jlpt", "jft_basic"].index(req["test_type"]),
            format_func=lambda x: (
                language_label(x) if x else "Belum tercatat / tidak disyaratkan setelah konfirmasi"
            ),
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
    preferred_skills = st.multiselect(
        "Keahlian tambahan",
        list(dict.fromkeys([*SKILL_LABELS, *values.get("preferred_skills", [])])),
        default=values.get("preferred_skills", []),
        format_func=catalog_label,
        accept_new_options=True,
        key=prefix + "_preferred_skills",
    )
    preferred_certs = st.multiselect(
        "Sertifikasi tambahan",
        list(dict.fromkeys([*SKILL_LABELS, *values.get("preferred_certifications", [])])),
        default=values.get("preferred_certifications", []),
        format_func=catalog_label,
        accept_new_options=True,
        key=prefix + "_preferred_certs",
    )
    raw_deadline = values.get("application_deadline")
    deadline = st.date_input(
        "Tenggat pendaftaran (opsional)",
        value=datetime.fromisoformat(raw_deadline).date() if raw_deadline else None,
        key=prefix + "_deadline",
    )
    return {
        **values,
        "title": title.strip(),
        "employer_name": employer.strip(),
        "program": program,
        "sector": sector,
        "prefecture": prefecture,
        "quota": int(quota),
        "minimum_experience_months": int(minimum) if minimum is not None else None,
        "required_skills": [s.strip().lower().replace(" ", "_") for s in skills],
        "required_certifications": [s.strip().lower().replace(" ", "_") for s in certs],
        "preferred_skills": [s.strip().lower().replace(" ", "_") for s in preferred_skills],
        "preferred_certifications": [s.strip().lower().replace(" ", "_") for s in preferred_certs],
        "language_requirements": [{"test_type": test, "minimum_level": level}, *reqs[1:]]
        if test
        else [],
        "application_deadline": datetime.combine(
            deadline, time(23, 59), ZoneInfo("Asia/Jakarta")
        ).isoformat()
        if deadline
        else None,
        "status": "open",
    }


def valid_vacancy(values):
    if not values["title"] or not values["employer_name"]:
        st.error("Lengkapi posisi pekerjaan dan perusahaan pemberi kerja.")
        return False
    if (
        not values["program"]
        or not values["sector"]
        or not values["prefecture"]
        or not values["quota"]
        or values["minimum_experience_months"] is None
    ):
        st.error("Konfirmasikan program, sektor, prefektur, kuota dan pengalaman minimum.")
        return False
    if not values["language_requirements"]:
        return True
    req = values["language_requirements"][0]
    if (req["test_type"] == "jlpt") != req["minimum_level"].startswith("N"):
        st.error(
            "Sesuaikan tingkat minimum dengan jenis tes: JLPT memakai N1–N5, JFT-Basic memakai A1–A2.2."
        )
        return False
    return True
