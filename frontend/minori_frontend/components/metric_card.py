"""Ashby-style operational metric card component."""

import streamlit as st


def render_metric_card(
    label: str,
    value: str | int | float,
    subtext: str | None = None,
    badge: str | None = None,
    badge_type: str = "neutral",
) -> None:
    """Render a clean, high-density KPI card."""
    badge_colors = {
        "success": ("#DCFCE7", "#15803D"),
        "warning": ("#FEF3C7", "#B45309"),
        "danger": ("#FEE2E2", "#B91C1C"),
        "info": ("#E0F2FE", "#0284C7"),
        "neutral": ("#F1F5F9", "#475569"),
    }
    bg, fg = badge_colors.get(badge_type, badge_colors["neutral"])

    badge_html = (
        f"<span style='background-color: {bg}; color: {fg}; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; float: right;'>{badge}</span>"
        if badge
        else ""
    )
    subtext_html = f"<div class='minori-metric-subtext'>{subtext}</div>" if subtext else ""

    card_html = f"""
    <div class="minori-metric">
        {badge_html}
        <div class="minori-metric-label">{label}</div>
        <div class="minori-metric-value">{value}</div>
        {subtext_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
