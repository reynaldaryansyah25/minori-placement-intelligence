"""Escaped display primitives shared by operational Streamlit pages."""

from html import escape
from textwrap import dedent

import streamlit as st


def text(value) -> str:
    return escape(str(value if value is not None else "—"), quote=True)


def html(markup: str) -> None:
    # Render in the app DOM, without Markdown code fences or an iframe.
    st.html(dedent(markup).strip())


def section(title: str, description: str = "") -> None:
    html(f'<div class="section-head"><h3>{text(title)}</h3><p>{text(description)}</p></div>')


def detail_grid(items: list[tuple[str, object]]) -> None:
    html(
        '<div class="detail-grid">'
        + "".join(
            f'<div><div class="detail-label">{text(label)}</div>'
            f'<div class="detail-value">{text(value)}</div></div>'
            for label, value in items
        )
        + "</div>"
    )


def chips(values) -> None:
    html(
        '<div class="chips">'
        + "".join(f'<span class="chip">{text(v)}</span>' for v in values)
        + "</div>"
    )


def distribution(items: list[tuple[str, int]], *, color="teal") -> None:
    maximum = max((count for _, count in items), default=0) or 1
    html(
        '<div class="bars">'
        + "".join(
            f'<div><div class="bar-head"><span>{text(label)}</span><strong>{count}</strong></div>'
            f'<div class="bar-track" role="img" aria-label="{text(label)}: {count}">'
            f'<div class="bar-fill {color}" style="width:{count / maximum * 100:.2f}%"></div></div></div>'
            for label, count in items
        )
        + "</div>"
    )
