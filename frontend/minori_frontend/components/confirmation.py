"""Confirmation modal and popover dialogs for destructive staff actions."""

import streamlit as st


@st.dialog("Konfirmasi Tindakan")
def show_confirmation_dialog(
    title: str,
    warning_text: str,
    action_button_label: str,
    on_confirm,
    is_danger: bool = True,
) -> None:
    """Render a confirmation modal dialog before mutating records."""
    st.markdown(f"**{title}**")
    st.markdown(
        f"<p style='color: #64748B; font-size: 0.875rem;'>{warning_text}</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Batal", use_container_width=True):
            st.rerun()
    with col2:
        btn_type = "primary" if not is_danger else "secondary"
        if st.button(action_button_label, type=btn_type, use_container_width=True):
            on_confirm()
            st.rerun()
