"""Session controls for the isolated public demonstration."""

import streamlit as st
from minori_frontend.components.feedback import show_api_error


def render_sandbox_controls(client, *, key_prefix="sandbox_sidebar"):
    st.caption("Demo interaktif · Data sintetis · Email hanya ke Mailpit lokal")
    if st.button("Perbarui status demo", width="stretch", key=key_prefix + "_refresh"):
        st.rerun()
    with st.expander("Penggunaan & reset sesi"):
        try:
            usage = client.sandbox_status()
            for key, label in {
                "ai": "Analisis AI",
                "writes": "Operasi tulis",
                "emails": "Email uji",
                "uploads": "Unggahan",
                "resets": "Reset data",
            }.items():
                st.caption(f"{label}: {usage['used'][key]} / {usage['limits'][key]}")
            st.caption(
                "Gunakan informasi sintetis saja. Unggahan maksimal 2 MB. Reset hanya mengembalikan data sesi Anda; batas penggunaan tetap berlaku."
            )
            confirmed = st.checkbox(
                "Hapus perubahan dan pulihkan data demo sesi saya.", key=key_prefix + "_confirm"
            )
            if st.button(
                "Reset data sesi",
                disabled=not confirmed,
                width="stretch",
                key=key_prefix + "_reset",
            ):
                client.reset_sandbox()
                keep = {
                    key: value
                    for key, value in st.session_state.items()
                    if key
                    in {
                        "public_authenticated_at",
                        "public_last_activity",
                        "public_credential_fingerprint",
                        "public_reviewer_mode",
                        "sandbox_session_token",
                        "interactive_demo_mode",
                        "auth_role",
                        "actor_reference",
                    }
                }
                st.session_state.clear()
                st.session_state.update(keep)
                st.session_state.minori_feedback = "Data sintetis sesi Anda berhasil dipulihkan."
                st.rerun()
        except Exception as exc:
            show_api_error(exc)
