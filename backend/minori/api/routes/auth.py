"""Authentication and session verification routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from minori.api.security import AuthSession, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class AuthMeResponse(BaseModel):
    authenticated: bool
    role: str
    actor_reference: str
    can_write: bool


@router.get("/me", response_model=AuthMeResponse)
def get_me(user: Annotated[AuthSession, Depends(get_current_user)]) -> AuthMeResponse:
    return AuthMeResponse(
        authenticated=True,
        role=user.role.value,
        actor_reference=user.actor_reference,
        can_write=user.can_write,
    )
