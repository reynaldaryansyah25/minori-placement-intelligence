"""Password verification and process-wide throttling for the single public reviewer account."""

import hashlib
import hmac
import secrets
import threading
import time
from collections import deque

SCRYPT_N = 131072
SCRYPT_MAX_MEMORY = 256 * 1024 * 1024
HASH_VERSION = "scrypt-v1"


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=8, p=1, dklen=32, maxmem=SCRYPT_MAX_MEMORY
    )
    return f"{HASH_VERSION}:{salt.hex()}:{digest.hex()}"


def valid_password_hash(encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split(":")
        return (
            algorithm == HASH_VERSION
            and len(bytes.fromhex(salt)) == 16
            and len(bytes.fromhex(digest)) == 32
        )
    except (ValueError, TypeError):
        return False


def verify_password(password: str, encoded: str) -> bool:
    if not valid_password_hash(encoded) or len(password) > 1024:
        return False
    _, salt, expected = encoded.split(":")
    actual = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=SCRYPT_N,
        r=8,
        p=1,
        dklen=32,
        maxmem=SCRYPT_MAX_MEMORY,
    )
    return hmac.compare_digest(actual, bytes.fromhex(expected))


def credential_fingerprint(settings) -> str:
    # Rotating either credential revokes sessions on their next server action.
    parts = [
        settings.public_demo_username,
        settings.public_demo_password_hash,
        settings.sandbox_gateway_token
        if settings.interactive_demo_mode
        else settings.reviewer_api_token,
    ]
    return hashlib.sha256("\0".join(p.get_secret_value() for p in parts).encode()).hexdigest()


class LoginThrottle:
    """One configured account, one shared limit; new sessions or spoofed IPs cannot bypass it."""

    def __init__(self):
        self._lock = threading.Lock()
        self._failures = deque()
        self._locked_until = 0.0
        self._fingerprint = None

    def authenticate(self, username, password, settings, *, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            fingerprint = credential_fingerprint(settings)
            if self._fingerprint != fingerprint:
                self._failures.clear()
                self._locked_until = 0.0
                self._fingerprint = fingerprint
            if now < self._locked_until:
                return False, max(1, int(self._locked_until - now))
            while (
                self._failures and self._failures[0] <= now - settings.public_login_window_seconds
            ):
                self._failures.popleft()
            matches = hmac.compare_digest(
                username.encode(), settings.public_demo_username.get_secret_value().encode()
            )
            # Perform the password KDF even for an unknown username.
            matches = (
                verify_password(password, settings.public_demo_password_hash.get_secret_value())
                and matches
            )
            if matches:
                self._failures.clear()
                return True, 0
            self._failures.append(now)
            if len(self._failures) >= settings.public_login_max_attempts:
                self._locked_until = now + settings.public_login_lockout_seconds
                return False, settings.public_login_lockout_seconds
            return False, 0


LOGIN_THROTTLE = LoginThrottle()


def session_valid(state, settings, *, now=None):
    now = time.monotonic() if now is None else now
    issued = state.get("public_authenticated_at")
    used = state.get("public_last_activity")
    return (
        issued is not None
        and used is not None
        and 0 <= now - issued < settings.public_session_max_seconds
        and 0 <= now - used < settings.public_session_idle_seconds
        and state.get("public_credential_fingerprint") == credential_fingerprint(settings)
    )
