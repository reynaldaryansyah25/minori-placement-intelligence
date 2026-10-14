"""Editable candidate facts; no qualifications are invented from vacancy requirements."""

import re
import unicodedata

import pandas as pd
import streamlit as st
from minori_frontend.utils.constants import JAPAN_PREFECTURES, PROGRAMS
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import SECTOR_LABELS, SKILL_LABELS, catalog_label


def _date(value):
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _editor(label, rows, columns, dates, config, key):
    st.write(label)
    frame = pd.DataFrame(rows, columns=columns)
    for name in dates:
        frame[name] = pd.to_datetime(frame[name])
    result = st.data_editor(
        frame, num_rows="dynamic", hide_index=True, width="stretch", column_config=config, key=key
    )
    return result.to_dict("records")


def candidate_fields(prefix, initial=None):
    value = initial or {}
    left, right = st.columns(2)
    with left:
        name = st.text_input(
            "Nama lengkap *", value=value.get("full_name", ""), key=prefix + "_name"
        )
        programs = dict(PROGRAMS)
        program = st.selectbox(
            "Program penempatan",
            list(programs),
            index=list(programs).index(value.get("preferred_program", "ssw")),
            format_func=programs.get,
            key=prefix + "_program",
        )
        education = st.text_input(
            "Pendidikan terakhir *",
            value=value.get("education_level", ""),
            key=prefix + "_education",
        )
    with right:
        city = st.text_input(
            "Kota domisili *", value=value.get("domicile_city", ""), key=prefix + "_city"
        )
        statuses = ["registered", "preparing", "ready", "inactive"]
        status = st.selectbox(
            "Status kesiapan",
            statuses,
            index=statuses.index(value.get("status", "registered")),
            format_func=format_status_label,
            key=prefix + "_status",
        )
        email = st.text_input(
            "Email kandidat (opsional)", value=value.get("email") or "", key=prefix + "_email"
        )
    preferences = st.multiselect(
        "Preferensi prefektur",
        JAPAN_PREFECTURES,
        default=value.get("preferred_prefectures", []),
        key=prefix + "_preferences",
    )
    skills = st.multiselect(
        "Keahlian",
        list(dict.fromkeys([*SKILL_LABELS, *value.get("skills", [])])),
        default=value.get("skills", []),
        format_func=catalog_label,
        accept_new_options=True,
        key=prefix + "_skills",
    )
    st.caption(
        "Isi kualifikasi berdasarkan dokumen kandidat. Tambahkan baris sesuai kebutuhan; jangan menyalin persyaratan lowongan sebagai kualifikasi kandidat."
    )
    languages = _editor(
        "Hasil tes bahasa",
        [
            {
                "Tes": "JLPT" if row["test_type"] == "jlpt" else "JFT-Basic",
                "Tingkat": row["level"],
                "Tanggal tes": row["taken_on"],
                "Skor (opsional)": row.get("score"),
            }
            for row in value.get("language_tests", [])
        ],
        ["Tes", "Tingkat", "Tanggal tes", "Skor (opsional)"],
        ["Tanggal tes"],
        {
            "Tes": st.column_config.SelectboxColumn(options=["JLPT", "JFT-Basic"], required=True),
            "Tingkat": st.column_config.SelectboxColumn(
                options=["N5", "N4", "N3", "N2", "N1", "A1", "A2.1", "A2.2"], required=True
            ),
            "Tanggal tes": st.column_config.DateColumn(required=True),
            "Skor (opsional)": st.column_config.NumberColumn(min_value=0, max_value=250, step=1),
        },
        prefix + "_languages",
    )
    certificate_catalog = {
        catalog_label(code): code
        for code in SKILL_LABELS
        if "certificate" in code or "_skill" in code or "otit_" in code
    }
    certificate_catalog.update(
        {row["name"]: row["code"] for row in value.get("certifications", [])}
    )
    certificates = _editor(
        "Sertifikasi",
        [
            {
                "Nama sertifikat": row["name"],
                "Penerbit": row["issuer"],
                "Tanggal terbit": row["issued_on"],
                "Berlaku sampai": row.get("expires_on"),
            }
            for row in value.get("certifications", [])
        ],
        ["Nama sertifikat", "Penerbit", "Tanggal terbit", "Berlaku sampai"],
        ["Tanggal terbit", "Berlaku sampai"],
        {
            "Nama sertifikat": st.column_config.SelectboxColumn(
                options=list(certificate_catalog), required=True
            ),
            "Tanggal terbit": st.column_config.DateColumn(required=True),
            "Berlaku sampai": st.column_config.DateColumn(),
        },
        prefix + "_certificates",
    )
    sectors = {
        catalog_label(code, SECTOR_LABELS): code
        for code in [*SECTOR_LABELS, *(row["sector"] for row in value.get("experiences", []))]
    }
    experiences = _editor(
        "Pengalaman kerja",
        [
            {
                "Perusahaan": row["employer_name"],
                "Sektor": catalog_label(row["sector"], SECTOR_LABELS),
                "Posisi": row["role"],
                "Mulai": row["started_on"],
                "Selesai": row.get("ended_on"),
            }
            for row in value.get("experiences", [])
        ],
        ["Perusahaan", "Sektor", "Posisi", "Mulai", "Selesai"],
        ["Mulai", "Selesai"],
        {
            "Sektor": st.column_config.SelectboxColumn(options=list(sectors), required=True),
            "Mulai": st.column_config.DateColumn(required=True),
            "Selesai": st.column_config.DateColumn(),
        },
        prefix + "_experiences",
    )
    previous_codes = {
        (row["name"], row["issuer"]): row["code"] for row in value.get("certifications", [])
    }
    qualification_data = {
        "language_tests": [
            {
                "test_type": "jlpt" if row["Tes"] == "JLPT" else "jft_basic",
                "level": row["Tingkat"],
                "taken_on": _date(row["Tanggal tes"]),
                "score": None if pd.isna(row["Skor (opsional)"]) else int(row["Skor (opsional)"]),
            }
            for row in languages
        ],
        "certifications": [
            {
                "code": previous_codes.get((row["Nama sertifikat"], row["Penerbit"]))
                or certificate_catalog.get(row["Nama sertifikat"])
                or re.sub(
                    r"[^a-z0-9]+",
                    "_",
                    unicodedata.normalize("NFKD", str(row["Nama sertifikat"]))
                    .encode("ascii", "ignore")
                    .decode()
                    .lower(),
                ).strip("_")[:80],
                "name": row["Nama sertifikat"],
                "issuer": row["Penerbit"],
                "issued_on": _date(row["Tanggal terbit"]),
                "expires_on": _date(row["Berlaku sampai"]),
            }
            for row in certificates
        ],
        "experiences": [
            {
                "employer_name": row["Perusahaan"],
                "sector": sectors.get(row["Sektor"], ""),
                "role": row["Posisi"],
                "started_on": _date(row["Mulai"]),
                "ended_on": _date(row["Selesai"]),
            }
            for row in experiences
        ],
    }
    same_email = (email.strip() or None) == value.get("email")
    return {
        "full_name": name.strip(),
        "preferred_program": program,
        "education_level": education.strip(),
        "domicile_city": city.strip(),
        "status": status,
        "email": email.strip() or None,
        "email_verified": bool(same_email and value.get("email_verified")),
        "email_consent": bool(same_email and value.get("email_consent")),
        "skills": [s.strip().lower().replace(" ", "_") for s in skills],
        "preferred_prefectures": preferences,
        **qualification_data,
    }
