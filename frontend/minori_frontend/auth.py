"""Session state and role-based authentication management for the frontend."""

import time
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
        display_name="Staf Rekrutmen",
        actor_reference="staff.admin",
        description="Akses penuh: matching, keputusan staf, placement, dan reminder.",
    ),
    "reviewer": UserProfile(
        role="reviewer",
        display_name="Peninjau Operasional",
        actor_reference="reviewer.executive",
        description="Akses baca laporan, ranking, audit log, dan status penempatan.",
    ),
}


def init_auth_state(settings: "FrontendSettings") -> None:
    """Ensure session state contains valid authentication profile."""
    st.session_state["public_reviewer_mode"] = settings.public_reviewer_mode
    if settings.public_reviewer_mode:
        # Never keep a caller-supplied role/token when opening the public frontend.
        st.session_state.auth_role = "reviewer"
        st.session_state.actor_reference = PROFILES["reviewer"].actor_reference
        st.session_state.pop("auth_token", None)
        return
    if "auth_initialized" not in st.session_state:
        st.session_state.auth_initialized = True
        st.session_state.auth_role = "admin"
        default_token = (
            settings.internal_api_token.get_secret_value() if settings.internal_api_token else None
        )
        st.session_state.auth_token = default_token
        st.session_state.actor_reference = PROFILES["admin"].actor_reference
        st.session_state.auth_error = None


def get_current_role() -> RoleType:
    if st.session_state.get("public_reviewer_mode"):
        return "reviewer"
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
    if settings.public_reviewer_mode or st.session_state.get("public_reviewer_mode"):
        st.session_state.auth_role = "reviewer"
        st.session_state.pop("auth_token", None)
        return
    st.session_state.auth_role = role
    st.session_state.actor_reference = PROFILES[role].actor_reference
    st.session_state.auth_error = None

    if role == "admin":
        st.session_state.auth_token = (
            settings.internal_api_token.get_secret_value() if settings.internal_api_token else None
        )
    else:
        st.session_state.auth_token = (
            settings.reviewer_api_token.get_secret_value() if settings.reviewer_api_token else None
        )


def apply_custom_token(token: str, client: "BackendClient") -> bool:
    """Verify arbitrary token against the backend /auth/me endpoint."""
    if st.session_state.get("public_reviewer_mode") or client._settings.public_reviewer_mode:
        return False
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
    except Exception:
        st.session_state.auth_error = "Akses belum dapat diverifikasi. Hubungi pengelola."
        return False


def require_public_login(settings: "FrontendSettings") -> None:
    """Run before navigation, page rendering, and authenticated backend reads."""
    if not settings.public_reviewer_mode:
        return
    from minori_frontend.public_auth import LOGIN_THROTTLE, credential_fingerprint, session_valid

    if session_valid(st.session_state, settings):
        st.session_state.public_last_activity = time.monotonic()
        return
    expired = "public_authenticated_at" in st.session_state
    if expired or not st.session_state.get("public_login_initialized"):
        st.session_state.clear()
        st.session_state.public_login_initialized = True
    st.session_state.public_reviewer_mode = True
    st.session_state.auth_role = "reviewer"
    st.title("MINORI Placement Intelligence")
    st.caption("Masuk sebagai peninjau demo. Akses hanya untuk membaca data sintetis.")
    if expired:
        st.info("Sesi berakhir. Silakan masuk kembali.")
    with st.form("public_login", clear_on_submit=True):
        username = st.text_input("Nama pengguna", max_chars=128)
        password = st.text_input("Kata sandi", type="password", max_chars=1024)
        submitted = st.form_submit_button("Masuk", type="primary", width="stretch")
    if submitted:
        accepted, retry_after = LOGIN_THROTTLE.authenticate(username, password, settings)
        if not accepted:
            st.error(
                "Terlalu banyak percobaan. Coba kembali dalam beberapa menit."
                if retry_after
                else "Nama pengguna atau kata sandi tidak sesuai."
            )
        else:
            from minori_frontend.api_client import BackendClient

            try:
                # A misconfigured reviewer token must never turn into an admin session.
                identity = BackendClient(settings).verify_public_reviewer()
                if identity.get("role") != "reviewer":
                    raise ValueError("Invalid reviewer role")
            except Exception:
                st.error("Akses peninjau belum tersedia. Hubungi pengelola demo.")
            else:
                st.session_state.clear()
                st.session_state.update(
                    public_reviewer_mode=True,
                    auth_role="reviewer",
                    actor_reference=PROFILES["reviewer"].actor_reference,
                    public_authenticated_at=time.monotonic(),
                    public_last_activity=time.monotonic(),
                    public_credential_fingerprint=credential_fingerprint(settings),
                )
                st.rerun()
    st.stop()


def render_public_logout(settings):
    if settings.public_reviewer_mode and st.button("Keluar dari demo", width="stretch"):
        st.session_state.clear()
        st.rerun()


@st.fragment(run_every="15s")
def public_session_watchdog(settings):
    from minori_frontend.public_auth import session_valid

    if settings.public_reviewer_mode and not session_valid(st.session_state, settings):
        st.rerun(scope="app")
