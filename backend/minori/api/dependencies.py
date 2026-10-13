"""Infrastructure adapters injected at the HTTP boundary."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from minori.core.config import Settings
from minori.db.session import immediate_transaction
from minori.domain.reminders import ReminderPolicy
from minori.repositories.health import SqlAlchemyDatabaseProbe
from minori.repositories.provider import Repositories, provide_repositories
from minori.services.candidates import CandidateService
from minori.services.health import HealthService
from minori.services.matching import MatchingService
from minori.services.overview import OverviewService
from minori.services.placements import PlacementService
from minori.services.reminders import ReminderService
from minori.services.vacancies import VacancyService


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


def reminder_policy(settings: Settings) -> ReminderPolicy:
    return ReminderPolicy(
        timezone=settings.business_timezone,
        delivery_time=settings.reminder_delivery_time,
        dry_run=settings.notification_dry_run,
        lease_seconds=settings.notification_lease_seconds,
        max_attempts=settings.notification_max_attempts,
        retry_base_seconds=settings.notification_retry_base_seconds,
        retry_max_seconds=settings.notification_retry_max_seconds,
        demo_notification_recipient=settings.demo_notification_recipient,
        notification_delivery_mode=settings.notification_delivery_mode,
        mailpit_inbox_email=settings.mailpit_inbox_email,
    )


def get_reminder_service(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ReminderService:
    return ReminderService(
        provide_repositories(session),
        lambda: immediate_transaction(session),
        reminder_policy(settings),
    )


def get_placement_service(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> PlacementService:
    ports = provide_repositories(session)

    def transaction():
        return immediate_transaction(session)

    reminder = ReminderService(ports, transaction, reminder_policy(settings))
    return PlacementService(ports, transaction, reminder)


def get_candidate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CandidateService:
    ports = provide_repositories(session)
    return CandidateService(ports.candidate, lambda: immediate_transaction(session))


def get_vacancy_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> VacancyService:
    ports = provide_repositories(session)
    return VacancyService(
        ports.vacancy, ports.vacancy_draft, lambda: immediate_transaction(session)
    )


def get_overview_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> OverviewService:
    ports = provide_repositories(session)
    return OverviewService(
        ports.candidate,
        ports.vacancy,
        ports.placement,
        ports.placement_stage,
        ports.notification,
        ports.evaluation,
        ports.audit_log,
    )
