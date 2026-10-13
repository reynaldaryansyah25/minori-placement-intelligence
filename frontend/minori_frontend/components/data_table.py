"""Interactive data table rendering with column configuration and row selection."""

from typing import Any, Literal

import streamlit as st

SelectionMode = Literal[
    "multi-cell",
    "multi-column",
    "multi-row",
    "single-cell",
    "single-column",
    "single-row",
    "single-row-required",
]


def render_interactive_table(
    data: list[dict[str, Any]],
    column_config: dict[str, Any] | None = None,
    key: str = "table",
    selection_mode: SelectionMode = "single-row",
    height: int = 380,
) -> list[int]:
    """Render an interactive dataframe with selection support."""
    if not data:
        return []

    event = st.dataframe(
        data,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        key=key,
        on_select="rerun",
        selection_mode=selection_mode,
        height=height,
    )

    selected_rows = event.selection.rows if hasattr(event, "selection") else []
    return selected_rows
