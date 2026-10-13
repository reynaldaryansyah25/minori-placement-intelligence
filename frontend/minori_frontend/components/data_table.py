"""Bounded native Streamlit tables with stable selection across pagination."""

import hashlib
import json
from typing import Any, Literal

import pandas as pd
import streamlit as st
from minori_frontend.utils.constants import STATUS_COLORS

SelectionMode = Literal["single-row", "multi-row"]
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
    "Referensi",
    "Referensi Draf",
    "Ref Sumber",
    "Error",
    "Skills",
}


def display_rows(data):
    return [{k: v for k, v in row.items() if k not in TECHNICAL_COLUMNS} for row in data]


def render_interactive_table(
    data: list[dict[str, Any]],
    column_config=None,
    key="table",
    selection_mode: SelectionMode = "single-row",
    height=380,
    hide_technical_columns=True,
    page_size=10,
) -> list[int]:
    if not data:
        return []
    fingerprint = hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    state_key = f"{key}_page_{fingerprint}"
    page = min(st.session_state.get(state_key, 0), (len(data) - 1) // page_size)
    start = page * page_size
    visible = display_rows(data[start : start + page_size])
    frame = pd.DataFrame(visible)
    status_columns = [
        column
        for column in ("Status", "Kelayakan", "Keputusan", "Hasil")
        if column in frame.columns
    ]
    if status_columns:
        colors = {
            value[
                "label"
            ]: f"background-color: {value['bg']}; color: {value['text']}; font-weight: 650"
            for value in STATUS_COLORS.values()
        }
        frame = frame.style.map(lambda value: colors.get(value, ""), subset=status_columns)
    config = {k: v for k, v in (column_config or {}).items() if k not in TECHNICAL_COLUMNS}
    event = st.dataframe(
        frame,
        column_config=config,
        width="stretch",
        hide_index=True,
        key=f"{key}_{fingerprint}_{page}",
        on_select="rerun",
        selection_mode=selection_mode,
        height=min(height, 38 + len(visible) * 36),
        row_height=36,
    )
    selected = event.selection.rows if hasattr(event, "selection") else []
    if len(data) > page_size:
        count, previous, following = st.columns([6, 2, 2], vertical_alignment="center")
        count.caption(f"{start + 1}–{min(start + page_size, len(data))} dari {len(data)} data")
        if previous.button(
            "Sebelumnya", key=f"{key}_previous", disabled=page == 0, width="stretch"
        ):
            st.session_state[state_key] = page - 1
            st.rerun()
        if following.button(
            "Berikutnya",
            key=f"{key}_next",
            disabled=start + page_size >= len(data),
            width="stretch",
        ):
            st.session_state[state_key] = page + 1
            st.rerun()
    else:
        st.caption(f"{len(data)} data · Pilih baris untuk membuka rincian")
    return [start + index for index in selected] or [start]
