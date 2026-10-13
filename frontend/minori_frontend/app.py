"""Operational landing page for verifying the project foundation."""

import httpx
import streamlit as st

from minori_frontend.api_client import BackendClient
from minori_frontend.config import FrontendSettings


def main() -> None:
    st.set_page_config(page_title="MINORI Placement Intelligence", page_icon="🌱", layout="wide")
    st.title("MINORI Placement Intelligence")
    st.caption("Konsol operasional sistem penempatan tenaga kerja ke Jepang")
    st.subheader("Kesehatan layanan")
    st.button("Periksa ulang", help="Memuat ulang status backend dan database.")
    settings = FrontendSettings()
    try:
        health = BackendClient(settings).get_health()
    except (httpx.HTTPError, ValueError):
        st.error("Backend belum siap. Periksa layanan backend dan koneksi database.")
    else:
        backend_column, database_column, version_column = st.columns(3)
        backend_column.metric("Backend", str(health.get("status", "unknown")))
        database_column.metric("Database", str(health.get("database", "unknown")))
        version_column.metric("Versi", str(health.get("version", "unknown")))
        st.success("Backend dan database dapat diakses.")
    st.info("Fondasi sistem tersedia. Kapabilitas penempatan akan ditambahkan sesuai kebutuhan.")


if __name__ == "__main__":
    main()
