"""Source review and structured vacancy drafts supported by the existing API."""

from uuid import uuid4

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import can_operate
from minori_frontend.components.ai_vacancy import analysis_review, source_controls
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import section
from minori_frontend.components.vacancy_form import vacancy_fields, valid_vacancy
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import SOURCE_LABELS


def render_ai_vacancy_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Analisis lowongan",
        "Tinjau dokumen pemberi kerja dan siapkan draf lowongan sebelum diterbitkan.",
    )
    st.caption(
        "AI membantu ekstraksi, terjemahan dan pemeriksaan. Staf mengonfirmasi data sebelum publikasi."
    )
    try:
        drafts = read_all(
            client.list_vacancy_drafts,
        )
    except Exception as exc:
        show_api_error(exc)
        return
    source, review = st.columns([1, 1.2], gap="large")
    with source:
        with st.container(border=True):
            section("Dokumen sumber", "Gunakan teks asli sebagai acuan untuk meninjau persyaratan.")
            st.text_area(
                "Teks lowongan",
                value="",
                placeholder="Tempel teks lowongan dari pemberi kerja…",
                height=210,
                key="vacancy_source_text",
                help="Teks acuan hanya tersedia selama sesi ini. Simpan dokumen asli di arsip tim.",
            )
            channel = st.selectbox(
                "Sumber lowongan", list(SOURCE_LABELS), format_func=SOURCE_LABELS.get
            )
            source_name = st.text_input(
                "Nama dokumen sumber", placeholder="Contoh: Penawaran kerja Oktober", max_chars=120
            )
            source_controls(client)
        ai_values, ai_digest = analysis_review()
        with st.container(border=True):
            section("Draf tersimpan", f"{len(drafts)} draf dari layanan penempatan")
            selected = render_interactive_table(
                [
                    {
                        "id": d["id"],
                        "Posisi": d.get("proposed_data", {}).get("title", "Belum diisi"),
                        "Perusahaan": d.get("proposed_data", {}).get(
                            "employer_name", "Belum diisi"
                        ),
                        "Status": format_status_label(d.get("status")),
                    }
                    for d in drafts
                ],
                key="drafts_table",
                height=250,
                page_size=5,
            )
            if not drafts:
                st.caption("Belum ada draf yang disimpan.")
    with review:
        with st.container(border=True):
            section(
                "Peninjauan lowongan", "Pastikan data sesuai dokumen sumber sebelum menerbitkan."
            )
            mode = st.radio(
                "Draf yang dikerjakan",
                ["Draf baru", "Draf tersimpan"],
                horizontal=True,
                disabled=not drafts,
                label_visibility="collapsed",
            )
            draft = (
                drafts[selected[0]] if mode == "Draf tersimpan" and drafts and selected else None
            )
            published = draft and draft.get("status") == "published"
            if published:
                st.info(
                    "Draf ini telah diterbitkan. Pilih Draf baru untuk menyiapkan lowongan lain."
                )
            prefix = "draft_" + (
                draft["id"] if draft else ("ai_" + ai_digest[:12] if ai_digest else "new")
            )
            with st.form("form_draft_vacancy_" + prefix):
                proposed = vacancy_fields(
                    prefix,
                    draft.get("proposed_data") if draft else ai_values,
                    allow_unknown=bool(ai_values and not draft),
                )
                confirmed = (
                    st.checkbox(
                        "Saya telah memeriksa bukti sumber dan mengonfirmasi informasi yang belum tersedia.",
                        key=prefix + "_confirmed",
                    )
                    if ai_values and not draft
                    else True
                )
                save_col, publish_col = st.columns(2)
                save = save_col.form_submit_button(
                    "Simpan draf", disabled=not can_operate() or bool(published), width="stretch"
                )
                publish = publish_col.form_submit_button(
                    "Terbitkan lowongan",
                    type="primary",
                    disabled=not can_operate() or bool(published),
                    width="stretch",
                )
                if (save or publish) and not confirmed:
                    st.warning("Konfirmasikan hasil peninjauan sebelum menyimpan atau menerbitkan.")
                if (save or publish) and confirmed and valid_vacancy(proposed):
                    proposed.setdefault("reference", "VAC-" + uuid4().hex[:12].upper())
                    payload = {
                        "reference": draft["reference"]
                        if draft
                        else "DRAFT-" + uuid4().hex[:12].upper(),
                        "source_channel": draft["source_channel"] if draft else channel,
                        "source_reference": draft["source_reference"]
                        if draft
                        else (
                            (
                                source_name.strip()
                                or st.session_state.get("ai_source_document_name", "Analisis teks")
                            )[:75]
                            + " — Lowongan "
                            + str(st.session_state.get("ai_vacancy_selected_number", 1))
                            + " — "
                            + ai_digest[:10]
                            if ai_values
                            else source_name.strip() or "Peninjauan manual"
                        ),
                        "proposed_data": proposed,
                        "status": "draft",
                        "published_vacancy_id": None,
                        "analysis_metadata": draft.get("analysis_metadata")
                        if draft
                        else st.session_state.get("ai_vacancy_selected_analysis")
                        if ai_values
                        else None,
                    }
                    try:
                        saved = (
                            client.update_vacancy_draft(draft["id"], payload)
                            if draft
                            else client.create_vacancy_draft(payload)
                        )
                        if publish:
                            client.publish_vacancy_draft(saved["id"])
                            show_success("Lowongan berhasil diterbitkan.")
                        else:
                            show_success("Draf lowongan berhasil disimpan.")
                        st.rerun()
                    except Exception as exc:
                        show_api_error(exc)


if __name__ == "__main__":
    render_ai_vacancy_page()
