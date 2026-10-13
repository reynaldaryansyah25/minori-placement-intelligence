"""User feedback alerts, errors, and toast notifications."""

import streamlit as st
from minori_frontend.api_client import ApiClientError


def show_api_error(exc: Exception) -> None:
    """Format and display an API error clearly to HR staff."""
    if isinstance(exc, ApiClientError):
        st.error(exc.message)
        if exc.detail and exc.detail != exc.message:
            with st.expander("Detail teknis error"):
                st.code(exc.detail, language="json")
    else:
        st.error(f"Terjadi kesalahan sistem: {exc}")


def show_success(message: str) -> None:
    st.success(message)


def show_warning(message: str) -> None:
    st.warning(message)


def show_info(message: str) -> None:
    st.info(message)
