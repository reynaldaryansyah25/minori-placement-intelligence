"""Session state and role-based authentication management for the frontend."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import streamlit as st

if TYPE_CHECKING:
    from minori_frontend.api_client import BackendClient
    from minori_frontend.config import FrontendSettings

RoleType = Literal["admin", "reviewer"]


@dataclass(frozen=True)
class UserProfile:
    role: RoleType
    display_name: str
    actor_reference: str
    description: str


PROFILES: dict[RoleType, UserProfile] = {
    "admin": UserProfile(
        role="admin",
        display_name="Staff Rekrutmen (Admin)",
        actor_reference="staff.admin",
        description="Akses penuh: matching, keputusan staf, placement, dan reminder.",
    ),
    "reviewer": UserProfile(
        role="reviewer",
        display_name="Reviewer Eksekutif (Read-Only)",
        actor_reference="reviewer.executive",
        description="Akses baca laporan, ranking, audit log, dan status penempatan.",
    ),
}


def init_auth_state(settings: "FrontendSettings") -> None:
    """Ensure session state contains valid authentication profile."""
    if "auth_initialized" not in st.session_state:
        st.session_state.auth_initialized = True
        st.session_state.auth_role = "admin"
        default_token = (
            settings.internal_api_token.get_secret_value()
            if settings.internal_api_token
            else "demo_staff_token"
        )
        st.session_state.auth_token = default_token
        st.session_state.actor_reference = PROFILES["admin"].actor_reference
        st.session_state.auth_error = None


def get_current_role() -> RoleType:
    return st.session_state.get("auth_role", "admin")


def is_admin() -> bool:
    return get_current_role() == "admin"


def get_current_token() -> str | None:
    return st.session_state.get("auth_token")


def get_current_actor() -> str:
    return st.session_state.get("actor_reference", "staff.admin")


def get_profile() -> UserProfile:
    role = get_current_role()
    return PROFILES.get(role, PROFILES["admin"])


def switch_demo_role(role: RoleType, settings: "FrontendSettings") -> None:
    """Switch active demo role using configured backend tokens."""
    st.session_state.auth_role = role
    st.session_state.actor_reference = PROFILES[role].actor_reference
    st.session_state.auth_error = None

    if role == "admin":
        st.session_state.auth_token = (
            settings.internal_api_token.get_secret_value()
            if settings.internal_api_token
            else "demo_staff_token"
        )
    else:
        st.session_state.auth_token = (
            settings.reviewer_api_token.get_secret_value()
            if settings.reviewer_api_token
            else "demo_reviewer_token"
        )


def apply_custom_token(token: str, client: "BackendClient") -> bool:
    """Verify arbitrary token against the backend /auth/me endpoint."""
    cleaned = token.strip()
    if not cleaned:
        st.session_state.auth_error = "Token tidak boleh kosong"
        return False
    try:
        user_info = client.verify_token(cleaned)
        backend_role = user_info.get("role", "admin")
        role_key: RoleType = "reviewer" if backend_role == "reviewer" else "admin"
        st.session_state.auth_role = role_key
        st.session_state.auth_token = cleaned
        st.session_state.actor_reference = user_info.get(
            "actor_reference", PROFILES[role_key].actor_reference
        )
        st.session_state.auth_error = None
        return True
    except Exception as exc:
        st.session_state.auth_error = f"Token tidak valid: {exc}"
        return False
