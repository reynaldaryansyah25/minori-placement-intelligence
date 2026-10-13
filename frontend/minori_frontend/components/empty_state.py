"""Clean operational empty state display."""

import streamlit as st


def render_empty_state(
    title: str,
    description: str,
    icon: str = "📁",
    action_label: str | None = None,
    on_action=None,
) -> None:
    """Render a clean, minimal empty state box without flashy illustrations."""
    st.markdown(
        f"""
        <div style="
            background: #FFFFFF;
            border: 1px dashed #CBD5E1;
            border-radius: 8px;
            padding: 2.5rem 1.5rem;
            text-align: center;
            margin: 1rem 0;
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-size: 1rem; font-weight: 600; color: #13263F; margin-bottom: 0.25rem;">{title}</div>
            <div style="font-size: 0.875rem; color: #64748B; max-width: 460px; margin: 0 auto;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_label and on_action:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button(action_label, use_container_width=True):
                on_action()
