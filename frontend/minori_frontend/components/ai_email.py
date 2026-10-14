"""Explicit staff review and confirmation, with HTTP-only delivery orchestration."""

from uuid import uuid4

import streamlit as st
from minori_frontend.auth import can_operate
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.config import FrontendSettings


def render_email_actions(client, reminder, routing):
    if FrontendSettings().public_reviewer_mode and not FrontendSettings().interactive_demo_mode:
        return
    if not reminder.get("managed") or reminder.get("template_code") not in {
        "interview_h3",
        "medical_h1",
        "documents_schedule",
        "orientation_schedule",
        "departure_schedule",
    }:
        return
    identifier = reminder["id"]
    prefix = "email_" + identifier
    state = prefix + "_preview"
    st.divider()
    st.write("Email pengingat")
    if reminder.get("approved_message"):
        st.info(
            "Menunggu pengiriman"
            if reminder.get("status") in {"pending", "processing"}
            else "Pesan telah diproses. Lihat riwayat percobaan."
        )
        with st.expander("Pesan yang disetujui"):
            st.text(reminder["approved_message"]["subject"])
            st.text(reminder["approved_message"]["body"])
        return
    disabled = (
        not can_operate()
        or reminder.get("status") != "pending"
        or bool(reminder.get("attempt_count"))
    )
    ai_col, fallback = st.columns(2)
    choice = (
        "ai"
        if ai_col.button(
            "Susun Email dengan AI", disabled=disabled, width="stretch", key=prefix + "_ai"
        )
        else None
    )
    if fallback.button(
        "Gunakan template", disabled=disabled, width="stretch", key=prefix + "_template"
    ):
        choice = "template"
    if choice:
        try:
            with st.spinner("Menyiapkan draf email…"):
                result = client.draft_reminder_email(identifier, template=choice == "template")
            st.session_state[state] = result
            st.session_state[prefix + "_subject"] = result["subject"]
            st.session_state[prefix + "_body"] = result["body"]
            st.session_state[prefix + "_request_key"] = uuid4().hex
            st.session_state[prefix + "_confirm"] = False
        except Exception as exc:
            show_api_error(exc)
            st.info("Jika AI tidak tersedia, gunakan template untuk melanjutkan.")
    preview = st.session_state.get(state)
    if not preview:
        return
    st.caption("Email disiapkan. Belum ada pekerjaan pengiriman sampai staf mengonfirmasi.")
    with st.form(prefix + "_review"):
        subject = st.text_input("Subject", key=prefix + "_subject", max_chars=160)
        body = st.text_area("Isi email", key=prefix + "_body", height=280, max_chars=8000)
        st.caption(
            "Tujuan efektif: " + (routing.get("effective_recipient") or "Simulasi, tanpa SMTP")
        )
        confirmed = st.checkbox(
            "Saya menyetujui subject, isi pesan, jadwal dan tujuan pengiriman di atas.",
            key=prefix + "_confirm",
        )
        submit = st.form_submit_button(
            "Kirim Pengingat Sekarang", type="primary", disabled=disabled, width="stretch"
        )
        if submit:
            if not confirmed:
                st.warning("Konfirmasi staf diperlukan sebelum membuat pekerjaan pengiriman.")
            elif not subject.strip() or not body.strip():
                st.warning("Lengkapi subject dan isi email.")
            else:
                try:
                    client.approve_reminder_email(
                        identifier,
                        {
                            "subject": subject,
                            "body": body,
                            "confirmed": True,
                            "facts_fingerprint": preview["facts_fingerprint"],
                            "idempotency_key": st.session_state[prefix + "_request_key"],
                        },
                    )
                    show_success(
                        "Pesan disetujui dan menunggu worker sandbox ke Mailpit lokal."
                        if FrontendSettings().interactive_demo_mode
                        else "Pesan disetujui dan menunggu pengiriman melalui antrean n8n."
                    )
                    st.session_state.pop(state, None)
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
