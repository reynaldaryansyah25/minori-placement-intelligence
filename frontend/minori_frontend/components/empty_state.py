"""Calm empty states with optional real actions."""

import streamlit as st
from minori_frontend.components.presentation import html, text


def render_empty_state(title, description, icon=None, action_label=None, on_action=None):
    html(
        f'<div class="minori-card" style="text-align:center;padding:34px 20px">'
        f'<h3 style="font-size:14px">{text(title)}</h3>'
        f'<p style="font-size:12px;color:var(--muted)">{text(description)}</p></div>'
    )
    if action_label and on_action and st.button(action_label):
        on_action()
