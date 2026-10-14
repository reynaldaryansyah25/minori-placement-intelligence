"""Native Streamlit shell for MINORI operations."""

import streamlit as st

from minori_frontend.api_client import BackendClient
from minori_frontend.auth import (
    get_profile,
    init_auth_state,
    public_session_watchdog,
    render_public_logout,
    require_public_login,
)
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.navigation import get_navigation_pages
from minori_frontend.components.presentation import html, text
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id, now_wib


def main() -> None:
    st.set_page_config(
        page_title="MINORI Placement Intelligence", layout="wide", initial_sidebar_state="auto"
    )
    try:
        settings = FrontendSettings()
    except Exception:
        st.error("Konfigurasi akses aplikasi belum tersedia. Hubungi pengelola.")
        st.stop()
    init_auth_state(settings)
    require_public_login(settings)
    if settings.public_reviewer_mode:
        public_session_watchdog(settings)
    apply_theme()
    client = BackendClient(settings)
    pages = get_navigation_pages()
    nav = st.navigation(pages, position="hidden")
    with st.sidebar:
        render_public_logout(settings)
        html(
            '<div class="brand"><div class="brand-mark">M</div><div>'
            '<div class="brand-title">MINORI Group</div>'
            '<div class="brand-sub">Placement Intelligence</div></div></div>'
        )
        for index, page in enumerate(pages):
            if index in (0, 6):
                html(f'<div class="nav-label">{"Ruang kerja" if index == 0 else "Wawasan"}</div>')
            with st.container(key="nav_active" if page.title == nav.title else f"nav_item_{index}"):
                st.page_link(page, label=page.title, icon=page.icon, width="stretch")
        try:
            online = client.get_health().get("status") == "ok"
        except Exception:
            online = False
        profile = get_profile()
        html(
            f'<div class="sidebar-status"><strong>{text(profile.display_name)}</strong>'
            f'<span class="status-dot {"" if online else "offline"}"></span>'
            f"{'Sistem terhubung' if online else 'Layanan belum terhubung'}"
            '<div style="margin-top:6px">Waktu operasional · WIB (UTC+7)</div></div>'
        )
    demo = '<span class="demo-pill">Lingkungan demo</span>' if settings.demo_mode else ""
    with st.container(key="mobile_nav"):
        with st.popover("Menu", icon=":material/menu:"):
            for page in pages:
                st.page_link(page, label=page.title, icon=page.icon)
    html(
        f'<div class="topbar"><span>MINORI / <b>{text(nav.title)}</b></span>'
        f'<div class="topbar-right"><span class="top-date">{text(format_datetime_id(now_wib().isoformat()))}</span>{demo}</div></div>'
    )
    if message := st.session_state.pop("minori_feedback", None):
        st.success(message)
    nav.run()


if __name__ == "__main__":
    main()
