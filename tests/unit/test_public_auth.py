"""Public login secrets, shared throttling, expiry, and credential isolation."""

from copy import deepcopy

import pytest
from minori_frontend.config import FrontendSettings
from minori_frontend.public_auth import (
    LoginThrottle,
    credential_fingerprint,
    password_hash,
    session_valid,
    valid_password_hash,
    verify_password,
)
from pydantic import ValidationError

PASSWORD = "Synthetic-public-password-for-tests"


@pytest.fixture
def public_settings():
    return FrontendSettings(
        _env_file=None,
        public_reviewer_mode=True,
        reviewer_api_token="synthetic-reviewer-api-token",
        public_demo_username="synthetic-reviewer",
        public_demo_password_hash=password_hash(PASSWORD),
    )


def test_scrypt_hash_has_random_salt_and_constant_format():
    first, second = password_hash(PASSWORD), password_hash(PASSWORD)
    assert first != second and PASSWORD not in first
    assert valid_password_hash(first)
    assert verify_password(PASSWORD, first)
    assert not verify_password("wrong", first)
    assert not verify_password("x" * 1025, first)


@pytest.mark.parametrize(
    "value",
    ["", "plain-password", "scrypt:bad:bad", "scrypt:" + "aa" * 16 + ":nohash", "pbkdf:aa:bb"],
)
def test_invalid_hash_fails_closed(value):
    assert not valid_password_hash(value)
    assert not verify_password(PASSWORD, value)


def test_public_settings_reject_admin_token_and_missing_login(public_settings):
    values = public_settings.model_dump()
    with pytest.raises(ValidationError):
        FrontendSettings(
            _env_file=None, **{**values, "internal_api_token": "must-never-enter-public"}
        )
    for key in ("public_demo_username", "public_demo_password_hash", "reviewer_api_token"):
        with pytest.raises(ValidationError):
            FrontendSettings(_env_file=None, **{**values, key: None})


def test_shared_limit_cannot_be_bypassed_by_new_session_or_username(public_settings):
    throttle = LoginThrottle()
    for i in range(public_settings.public_login_max_attempts):
        accepted, retry = throttle.authenticate(
            "new-session-user-" + str(i), "wrong", public_settings, now=100 + i
        )
        assert not accepted
    assert retry == public_settings.public_login_lockout_seconds
    assert (
        throttle.authenticate("synthetic-reviewer", PASSWORD, public_settings, now=110)[0] is False
    )
    assert throttle.authenticate("synthetic-reviewer", PASSWORD, public_settings, now=405) == (
        True,
        0,
    )


def test_login_failure_window_expires(public_settings):
    throttle = LoginThrottle()
    for i in range(4):
        assert not throttle.authenticate("synthetic-reviewer", "wrong", public_settings, now=i)[0]
    assert throttle.authenticate("synthetic-reviewer", "wrong", public_settings, now=310) == (
        False,
        0,
    )
    assert throttle.authenticate("synthetic-reviewer", PASSWORD, public_settings, now=311) == (
        True,
        0,
    )


def test_idle_absolute_timeout_and_rotation(public_settings):
    state = {
        "public_authenticated_at": 100,
        "public_last_activity": 100,
        "public_credential_fingerprint": credential_fingerprint(public_settings),
    }
    assert session_valid(state, public_settings, now=101)
    assert not session_valid({}, public_settings, now=101)
    assert not session_valid(
        state, public_settings, now=100 + public_settings.public_session_idle_seconds
    )
    assert not session_valid({**state, "public_last_activity": 3700}, public_settings, now=3700)
    assert not session_valid(state, public_settings, now=99)
    changed = deepcopy(public_settings)
    changed.public_demo_password_hash = password_hash("another-synthetic-password")
    # Reconstruct through validation so the hash is wrapped as SecretStr.
    changed = FrontendSettings(_env_file=None, **changed.model_dump())
    assert not session_valid(state, changed, now=101)
