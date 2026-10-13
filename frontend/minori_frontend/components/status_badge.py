"""Color-coded status badge pills for tables and detail panels."""

import streamlit as st
from minori_frontend.utils.constants import STATUS_COLORS


def get_status_badge_html(status: str | None) -> str:
    """Generate HTML snippet for inline status badge."""
    if not status:
        return "<span class='status-pill' style='background:#F1F5F9; color:#64748B;'>—</span>"
    key = status.upper() if status.upper() in STATUS_COLORS else status.lower()
    config = STATUS_COLORS.get(key)
    if not config:
        label = "Belum tersedia"
        return f"<span class='status-pill' style='background:#F1F5F9; color:#475569; border-color:#CBD5E1;'>{label}</span>"

    bg = config["bg"]
    fg = config["text"]
    border = config["border"]
    label = config["label"]
    return f"<span class='status-pill' style='background-color:{bg}; color:{fg}; border-color:{border};'>{label}</span>"


def render_status_badge(status: str | None) -> None:
    """Render a standalone status badge pill."""
    st.html(get_status_badge_html(status))
