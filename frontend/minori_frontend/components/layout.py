"""Global enterprise CSS injection and page container layout."""

import streamlit as st

ENTERPRISE_CSS = """
<style>
/* --- Japanese Minimalist Enterprise Design Tokens --- */
:root {
    --navy: #13263F;
    --teal: #0F766E;
    --bg: #F5F7FA;
    --surface: #FFFFFF;
    --text-primary: #1E293B;
    --text-secondary: #64748B;
    --border: #E2E8F0;
    --success: #15803D;
    --warning: #B7791F;
    --danger: #B91C1C;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Base Body and App Background */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    font-family: var(--font-sans) !important;
    color: var(--text-primary) !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebarNav"] {
    padding-top: 0.5rem;
}

/* Cards & Surfaces */
.minori-card {
    background-color: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: 0 1px 2px rgba(19, 38, 63, 0.04);
    margin-bottom: 1rem;
}

.minori-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.75rem;
    margin-bottom: 1rem;
}

.minori-card-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--navy);
    margin: 0;
}

/* Metric Display Cards */
.minori-metric {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 2px rgba(19, 38, 63, 0.04);
    min-height: 100px;
}

.minori-metric-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.25rem;
}

.minori-metric-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--navy);
    line-height: 1.2;
}

.minori-metric-subtext {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}

/* Status Badge Pills */
.status-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.4;
    border: 1px solid transparent;
}

/* Button & Form Accents */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: var(--teal) !important;
    border-color: var(--teal) !important;
    color: #FFFFFF !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}

div[data-testid="stButton"] > button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}

div[data-testid="stButton"] > button:hover {
    border-color: var(--teal) !important;
}

/* Cleaner Streamlit Elements */
div[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* Visual Progress Bar */
.score-progress-bar-container {
    background-color: #F1F5F9;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
    margin: 4px 0 8px 0;
}

.score-progress-bar-fill {
    height: 100%;
    background-color: var(--teal);
    border-radius: 4px;
}

/* Timeline Stepper */
.stepper-item {
    display: flex;
    align-items: flex-start;
    padding: 8px 0;
}

.stepper-circle {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background-color: var(--teal);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 600;
    margin-right: 12px;
    flex-shrink: 0;
}

.stepper-circle.pending {
    background-color: #CBD5E1;
    color: #475569;
}
</style>
"""


def apply_theme() -> None:
    """Inject corporate CSS stylesheet into page."""
    st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
