"""Compact enterprise page header with title, functional description, and connection badges."""

import streamlit as st


def render_page_header(
    title: str,
    description: str,
    breadcrumb: str | None = None,
    backend_status: str = "Connected",
    demo_mode: bool = True,
) -> None:
    """Render crisp, functional Ashby-style page header without excessive vertical padding."""
    col1, col2 = st.columns([3, 1])

    with col1:
        if breadcrumb:
            st.markdown(
                f"<div style='font-size: 0.75rem; color: #64748B; margin-bottom: 2px;'>{breadcrumb}</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<h1 style='font-size: 1.5rem; font-weight: 700; color: #13263F; margin: 0; line-height: 1.2;'>{title}</h1>"
            f"<p style='font-size: 0.875rem; color: #64748B; margin: 4px 0 0 0;'>{description}</p>",
            unsafe_allow_html=True,
        )

    with col2:
        status_color = "#15803D" if backend_status == "Connected" else "#B91C1C"
        status_bg = "#DCFCE7" if backend_status == "Connected" else "#FEE2E2"
        demo_badge = (
            "<span style='background-color: #FEF3C7; color: #B45309; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 6px;'>Demo Data</span>"
            if demo_mode
            else ""
        )
        st.markdown(
            f"<div style='text-align: right; margin-top: 6px;'>"
            f"<span style='background-color: {status_bg}; color: {status_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;'>● {backend_status}</span>"
            f"{demo_badge}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
