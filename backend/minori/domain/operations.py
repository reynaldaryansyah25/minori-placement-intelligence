"""Ports needed by placement and reminder use cases; no adapter imports."""

from dataclasses import fields
from typing import Protocol

from minori.domain.reminders import NotificationQueue
from minori.domain.repositories import (
    AuditLogRepository,
    CandidateRepository,
    MatchRepository,
    NotificationAttemptRepository,
    NotificationRepository,
    PlacementRepository,
    PlacementStageRepository,
    VacancyRepository,
)


class OperationsPorts(Protocol):
    candidate: CandidateRepository
    vacancy: VacancyRepository
    match: MatchRepository
    placement: PlacementRepository
    placement_stage: PlacementStageRepository
    notification: NotificationRepository
    notification_attempt: NotificationAttemptRepository
    audit_log: AuditLogRepository
    queue: NotificationQueue


def record_data(record, data_type):
    """Copy only input fields when replacing a detached record."""
    return data_type(**{item.name: getattr(record, item.name) for item in fields(data_type)})


class ReminderCoordinator(Protocol):
    def sync_activity(self, activity, now, actor): ...
    def cancel_activity(self, activity, now, actor, *, notice=True): ...
