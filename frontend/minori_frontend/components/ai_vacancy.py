"""Native upload, bounded row selection and review of AI-generated source analysis."""

import hashlib

import streamlit as st
from minori_frontend.auth import can_operate
from minori_frontend.components.feedback import show_api_error
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.constants import PROGRAMS
from minori_frontend.utils.labels import SECTOR_LABELS, catalog_label

FIELDS = {
    "title",
    "employer_name",
    "sector",
    "program",
    "prefecture",
    "quota",
    "minimum_experience_months",
    "language_requirements",
    "required_skills",
    "preferred_skills",
    "required_certifications",
    "preferred_certifications",
    "application_deadline",
}
LABELS = {
    "title": "Posisi",
    "employer_name": "Perusahaan",
    "sector": "Sektor",
    "program": "Program",
    "prefecture": "Prefektur",
    "quota": "Kuota",
    "minimum_experience_months": "Pengalaman minimum",
    "language_requirements": "Persyaratan bahasa",
    "required_skills": "Keahlian wajib",
    "preferred_skills": "Keahlian tambahan",
    "required_certifications": "Sertifikasi wajib",
    "preferred_certifications": "Sertifikasi tambahan",
    "application_deadline": "Tenggat pendaftaran",
}


def extraction_label(field, value):
    if value in (None, []):
        return "Perlu Konfirmasi"
    if field == "program":
        return dict(PROGRAMS).get(value, "Perlu Konfirmasi")
    if field == "sector":
        return catalog_label(value, SECTOR_LABELS)
    return str(value)


def source_controls(client):
    maximum = 2 if FrontendSettings().interactive_demo_mode else 5
    upload = st.file_uploader(
        "Upload dokumen",
        type=["pdf", "docx", "xlsx", "csv", "txt"],
        max_upload_size=maximum,
        disabled=not can_operate(),
        help=f"Maksimal {maximum} MB. Excel/CSV: satu lembar, judul kolom dan maksimal 100 baris.",
    )
    if upload and st.button("Pratinjau dokumen", disabled=not can_operate()):
        try:
            preview = client.preview_document(upload.name, upload.getvalue(), upload.type)
            st.session_state["ai_document_preview"] = preview
            st.session_state["ai_upload_digest"] = hashlib.sha256(upload.getvalue()).hexdigest()
        except Exception as exc:
            show_api_error(exc)
    preview = (
        st.session_state.get("ai_document_preview")
        if upload
        and st.session_state.get("ai_upload_digest")
        == hashlib.sha256(upload.getvalue()).hexdigest()
        else None
    )
    texts = [st.session_state.get("vacancy_source_text", "").strip()]
    st.session_state["ai_source_document_name"] = upload.name if preview else "Analisis teks"
    if preview:
        rows = preview["rows"]
        st.dataframe(
            [{"Baris": r["number"], "Pratinjau": r["preview"]} for r in rows],
            hide_index=True,
            height=200,
        )
        indexes = st.multiselect(
            "Lowongan yang dianalisis",
            list(range(len(rows))),
            default=[0] if rows else [],
            max_selections=5,
            format_func=lambda i: f"Baris {rows[i]['number']}: {rows[i]['preview'][:60]}",
        )
        texts = [rows[i]["text"] for i in indexes]
    if st.button(
        "Analisis dengan AI",
        type="primary",
        disabled=not can_operate() or not texts or not all(texts),
        width="stretch",
    ):
        try:
            results = []
            with st.spinner("Menganalisis, menerjemahkan, dan memeriksa persyaratan…"):
                for text in texts:
                    results.append(
                        {
                            "analysis": client.analyze_vacancy(text),
                            "source_digest": hashlib.sha256(text.encode()).hexdigest(),
                        }
                    )
            st.session_state["ai_vacancy_results"] = results
        except Exception as exc:
            show_api_error(exc)


def analysis_review():
    results = st.session_state.get("ai_vacancy_results", [])
    if not results:
        return None, None
    selected = st.selectbox(
        "Hasil lowongan untuk ditinjau",
        list(range(len(results))),
        format_func=lambda i: (
            f"Lowongan {i + 1} · {results[i]['analysis']['extraction'].get('title') or 'Perlu konfirmasi'}"
        ),
    )
    result = results[selected]
    st.session_state["ai_vacancy_selected_analysis"] = result["analysis"]
    st.session_state["ai_vacancy_selected_number"] = selected + 1
    analysis = result["analysis"]
    extraction = analysis["extraction"]
    tabs = st.tabs(["Hasil Ekstraksi", "Terjemahan Indonesia", "Pemeriksaan Persyaratan"])
    with tabs[0]:
        st.caption(
            "Data AI harus dikonfirmasi staf. Informasi kosong tidak merupakan persyaratan yang terverifikasi."
        )
        st.dataframe(
            [
                {
                    "Informasi": LABELS.get(k, k),
                    "Hasil": extraction_label(k, v),
                }
                for k, v in extraction.items()
                if k in FIELDS and not isinstance(v, list)
            ],
            hide_index=True,
        )
        for item in extraction["evidence"]:
            st.caption(LABELS.get(item["field"], "Bukti persyaratan"))
            st.text(item["quote"])
        if extraction["missing_fields"]:
            st.warning(
                "Perlu Konfirmasi: "
                + ", ".join(
                    LABELS.get(k, "Informasi tambahan") for k in extraction["missing_fields"]
                )
            )
    with tabs[1]:
        st.text(analysis["translation"])
    with tabs[2]:
        for key, title in [
            ("mandatory", "Wajib"),
            ("preferred", "Nilai tambah"),
            ("missing", "Informasi belum tersedia"),
            ("ambiguities", "Ambiguitas"),
            ("contradictions", "Pertentangan"),
            ("questions", "Pertanyaan untuk perusahaan"),
        ]:
            st.write(title)
            for item in analysis["review"][key]:
                st.text("• " + item)
        for item in analysis["review"]["evidence"]:
            st.text(item["quote"])
    return {k: v for k, v in extraction.items() if k in FIELDS}, result["source_digest"]
