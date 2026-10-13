"""Compose session-scoped concrete adapters behind inward-facing ports."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from minori.domain import repositories as ports
from minori.domain.matching import EvaluationRepository
from minori.domain.reminders import NotificationQueue
from minori.repositories.audit import SqlAlchemyAuditLogRepository
from minori.repositories.candidate import SqlAlchemyCandidateRepository
from minori.repositories.match import SqlAlchemyMatchRepository
from minori.repositories.matching import SqlAlchemyEvaluationRepository
from minori.repositories.notification import (
    SqlAlchemyNotificationAttemptRepository,
    SqlAlchemyNotificationRepository,
)
from minori.repositories.notification_queue import SqlAlchemyNotificationQueue
from minori.repositories.placement import (
    SqlAlchemyPlacementRepository,
    SqlAlchemyPlacementStageRepository,
)
from minori.repositories.vacancy import (
    SqlAlchemyVacancyDraftRepository,
    SqlAlchemyVacancyRepository,
)


@dataclass(frozen=True)
class Repositories:
    candidate: ports.CandidateRepository
    vacancy: ports.VacancyRepository
    vacancy_draft: ports.VacancyDraftRepository
    match: ports.MatchRepository
    evaluation: EvaluationRepository
    placement: ports.PlacementRepository
    placement_stage: ports.PlacementStageRepository
    notification: ports.NotificationRepository
    notification_attempt: ports.NotificationAttemptRepository
    audit_log: ports.AuditLogRepository
    queue: NotificationQueue


def provide_repositories(session: Session) -> Repositories:
    return Repositories(
        candidate=SqlAlchemyCandidateRepository(session),
        vacancy=SqlAlchemyVacancyRepository(session),
        vacancy_draft=SqlAlchemyVacancyDraftRepository(session),
        match=SqlAlchemyMatchRepository(session),
        evaluation=SqlAlchemyEvaluationRepository(session),
        placement=SqlAlchemyPlacementRepository(session),
        placement_stage=SqlAlchemyPlacementStageRepository(session),
        notification=SqlAlchemyNotificationRepository(session),
        notification_attempt=SqlAlchemyNotificationAttemptRepository(session),
        audit_log=SqlAlchemyAuditLogRepository(session),
        queue=SqlAlchemyNotificationQueue(session),
    )
