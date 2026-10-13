"""Application shell and multipage navigation entry point."""

import streamlit as st

from minori_frontend.api_client import BackendClient
from minori_frontend.auth import (
    get_profile,
    init_auth_state,
)
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.navigation import get_navigation_pages
from minori_frontend.config import FrontendSettings


def main() -> None:
    st.set_page_config(
        page_title="MINORI Placement Intelligence",
        page_icon="🇯🇵",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    settings = FrontendSettings()
    init_auth_state(settings)
    apply_theme()

    client = BackendClient(settings)

    # Sidebar Header & Branding
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 4px 0 12px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="background-color: #13263F; color: white; width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 15px;">
                        M
                    </div>
                    <div>
                        <div style="font-size: 1rem; font-weight: 700; color: #13263F; line-height: 1.1;">MINORI Group</div>
                        <div style="font-size: 0.75rem; color: #64748B; font-weight: 500;">Placement Intelligence</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Multipage Router
    nav = st.navigation(get_navigation_pages())

    # Sidebar Footer: Verified Staff Profile & Operational Status
    with st.sidebar:
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        profile = get_profile()
        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; font-size: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-weight: 700; color: #13263F;">{profile.display_name}</div>
                    <span style="font-size: 10px; font-weight: 600; color: #0F766E; background: #CCFBF1; padding: 2px 6px; border-radius: 4px;">Aktif</span>
                </div>
                <div style="color: #64748B; margin-top: 3px; font-size: 11px;">{profile.description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Operational System Badge
        try:
            client.get_health()
            system_online = True
        except Exception:
            system_online = False

        status_text = "Sistem Operasional Aktif" if system_online else "Menghubungkan ke Server..."
        status_color = "#15803D" if system_online else "#B91C1C"

        st.markdown(
            f"""
            <div style="border-top: 1px solid #E2E8F0; margin-top: 14px; padding-top: 10px; font-size: 11px; color: #64748B;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="color: {status_color}; font-size: 10px;">●</span>
                    <span style="font-weight: 500; color: #334155;">{status_text}</span>
                </div>
                <div style="margin-top: 4px; color: #94A3B8;">Waktu Operasional: WIB (UTC+7)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Render Active Page
    nav.run()


if __name__ == "__main__":
    main()
