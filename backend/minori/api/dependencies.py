"""Infrastructure adapters injected at the HTTP boundary."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from minori.core.config import Settings
from minori.repositories.health import SqlAlchemyDatabaseProbe
from minori.repositories.provider import Repositories, provide_repositories
from minori.services.health import HealthService
from minori.services.matching import MatchingService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.database.sessions()


def get_health_service(session: Annotated[Session, Depends(get_db_session)]) -> HealthService:
    return HealthService(SqlAlchemyDatabaseProbe(session))


def get_repositories(session: Annotated[Session, Depends(get_db_session)]) -> Repositories:
    """Provide all persistence ports using the same request-owned session."""
    return provide_repositories(session)


def get_matching_service(session: Annotated[Session, Depends(get_db_session)]) -> MatchingService:
    repositories = provide_repositories(session)
    return MatchingService(
        repositories.candidate,
        repositories.vacancy,
        repositories.match,
        repositories.evaluation,
        session.begin,
    )
