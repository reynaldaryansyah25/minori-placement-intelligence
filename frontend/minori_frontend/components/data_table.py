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

TECHNICAL_COLUMNS = {
    "id",
    "candidate_id",
    "vacancy_id",
    "placement_id",
    "placement_stage_id",
    "match_id",
    "notification_id",
    "evaluation_id",
    "claim_token_hash",
    "input_fingerprint",
    "lease_expires_at",
    "claimed_at",
    "schedule_revision",
    "schedule_context",
    "created_at",
    "updated_at",
}


def render_interactive_table(
    data: list[dict[str, Any]],
    column_config: dict[str, Any] | None = None,
    key: str = "table",
    selection_mode: SelectionMode = "single-row",
    height: int = 380,
    hide_technical_columns: bool = True,
) -> list[int]:
    """Render an interactive dataframe with selection support and auto-hidden UUIDs."""
    if not data:
        return []

    config = dict(column_config or {})
    if hide_technical_columns and data:
        for k in data[0].keys():
            if k in TECHNICAL_COLUMNS and k not in config:
                config[k] = None

    event = st.dataframe(
        data,
        column_config=config,
        use_container_width=True,
        hide_index=True,
        key=key,
        on_select="rerun",
        selection_mode=selection_mode,
        height=height,
    )

    selected_rows = event.selection.rows if hasattr(event, "selection") else []
    return selected_rows
