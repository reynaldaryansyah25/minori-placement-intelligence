"""Application shell and multipage navigation entry point."""

import streamlit as st

from minori_frontend.api_client import BackendClient
from minori_frontend.auth import (
    apply_custom_token,
    get_current_role,
    get_profile,
    init_auth_state,
    switch_demo_role,
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

    # Sidebar Footer: Session, Role Switching & System Health
    with st.sidebar:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size: 11px; text-transform: uppercase; color: #94A3B8; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 6px;'>Sesi & Peran Akses</div>",
            unsafe_allow_html=True,
        )

        current_role = get_current_role()
        role_choices = ["admin", "reviewer"]
        role_labels = {
            "admin": "HR Staff (Admin/Tulis)",
            "reviewer": "Reviewer (Read-Only)",
        }

        selected_role = st.selectbox(
            "Pilih Peran Demo",
            options=role_choices,
            index=role_choices.index(current_role),
            format_func=lambda r: role_labels[r],
            label_visibility="collapsed",
            key="sidebar_role_select",
        )

        if selected_role != current_role:
            switch_demo_role(selected_role, settings)
            st.rerun()

        profile = get_profile()
        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 10px; margin-top: 6px; font-size: 11px;">
                <div style="font-weight: 600; color: #13263F;">{profile.display_name}</div>
                <div style="color: #64748B; margin-top: 2px;">{profile.description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("🔑 Masukkan Token Kustom", expanded=False):
            custom_tok = st.text_input("Bearer Token", type="password", key="custom_token_input")
            if st.button("Verifikasi & Terapkan", use_container_width=True):
                if apply_custom_token(custom_tok, client):
                    st.success("Token berhasil diverifikasi!")
                    st.rerun()
                else:
                    err = st.session_state.get("auth_error", "Token tidak valid")
                    st.error(err)

        # System Health Badge
        try:
            health = client.get_health()
            health_color = "#15803D"
            health_label = f"Connected (v{health.get('version', '0.1.0')})"
        except Exception:
            health_color = "#B91C1C"
            health_label = "Backend Offline"

        st.markdown(
            f"""
            <div style="border-top: 1px solid #E2E8F0; margin-top: 14px; padding-top: 10px; font-size: 11px; color: #64748B;">
                <div>Koneksi: <span style="color: {health_color}; font-weight: 600;">● {health_label}</span></div>
                <div>Database: SQLite WAL (Persisten)</div>
                <div>Zona Waktu: Asia/Jakarta (WIB)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Render Active Page
    nav.run()


if __name__ == "__main__":
    main()
