"""Reusable filter bar components for tables and pipeline views."""

from typing import Any

import streamlit as st
from minori_frontend.utils.constants import PROGRAMS


def render_filter_bar(
    *,
    search_placeholder: str = "Cari nama atau referensi...",
    show_program: bool = True,
    show_status: bool = True,
    status_options: list[tuple[str, str]] | None = None,
    key_prefix: str = "filter",
) -> dict[str, Any]:
    """Render a clean filter bar in a horizontal row."""
    filters: dict[str, Any] = {}

    cols = st.columns([4, 3, 3] if (show_program and show_status) else [5, 5])
    col_idx = 0

    with cols[col_idx]:
        filters["query"] = st.text_input(
            "Pencarian",
            placeholder=search_placeholder,
            label_visibility="collapsed",
            key=f"{key_prefix}_query",
        )
    col_idx += 1

    if show_program:
        with cols[col_idx]:
            prog_opts = [("all", "Semua Program")] + PROGRAMS
            choice = st.selectbox(
                "Program",
                options=[opt[0] for opt in prog_opts],
                format_func=lambda code: next(opt[1] for opt in prog_opts if opt[0] == code),
                label_visibility="collapsed",
                key=f"{key_prefix}_program",
            )
            filters["program"] = None if choice == "all" else choice
        col_idx += 1

    if show_status and status_options:
        with cols[col_idx]:
            stat_opts = [("all", "Semua Status")] + status_options
            choice = st.selectbox(
                "Status",
                options=[opt[0] for opt in stat_opts],
                format_func=lambda code: next(opt[1] for opt in stat_opts if opt[0] == code),
                label_visibility="collapsed",
                key=f"{key_prefix}_status",
            )
            filters["status"] = None if choice == "all" else choice

    return filters
