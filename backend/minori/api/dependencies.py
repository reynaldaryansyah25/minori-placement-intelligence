"""Infrastructure adapters injected at the HTTP boundary."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from minori.core.config import Settings
from minori.repositories.health import SqlAlchemyDatabaseProbe
from minori.services.health import HealthService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.database.sessions()


def get_health_service(session: Annotated[Session, Depends(get_db_session)]) -> HealthService:
    return HealthService(SqlAlchemyDatabaseProbe(session))
