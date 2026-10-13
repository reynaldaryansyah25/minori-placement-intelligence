"""Shared token authentication and role-based access for staff mutations and reviewers."""

import hmac
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


class UserRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


@dataclass(frozen=True)
class AuthSession:
    role: UserRole
    actor_reference: str

    @property
    def can_write(self) -> bool:
        return self.role == UserRole.ADMIN


def get_current_user(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> AuthSession:
    settings = request.app.state.settings
    admin_token = settings.internal_api_token
    reviewer_token = settings.reviewer_api_token

    # Allow unauthenticated access for legacy test suites when running in test environment with no configured tokens
    if (
        settings.app_env == "test"
        and admin_token is None
        and reviewer_token is None
        and credentials is None
    ):
        return AuthSession(role=UserRole.ADMIN, actor_reference="test.synthetic")

    if admin_token is None and reviewer_token is None:
        raise HTTPException(status_code=503, detail="API authentication is not configured")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if admin_token is not None and hmac.compare_digest(
        token.encode(), admin_token.get_secret_value().encode()
    ):
        return AuthSession(role=UserRole.ADMIN, actor_reference="staff.admin")

    if reviewer_token is not None and hmac.compare_digest(
        token.encode(), reviewer_token.get_secret_value().encode()
    ):
        return AuthSession(role=UserRole.REVIEWER, actor_reference="reviewer.executive")

    raise HTTPException(
        status_code=401,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_read_access(
    user: Annotated[AuthSession, Depends(get_current_user)],
) -> AuthSession:
    return user


def require_staff_access(
    user: Annotated[AuthSession, Depends(get_current_user)],
) -> AuthSession:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Reviewer role has read-only access. Staff or administrator credentials required.",
        )
    return user


def require_internal_token(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> None:
    configured = request.app.state.settings.internal_api_token
    if configured is None:
        raise HTTPException(status_code=503, detail="Internal API authentication is not configured")
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(
            credentials.credentials.encode(), configured.get_secret_value().encode()
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
