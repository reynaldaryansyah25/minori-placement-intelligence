"""Inward-facing data access ports; callers own transactions."""

from typing import Protocol
from uuid import UUID

from minori.domain.catalogs import (
    AuditEntityType,
    CandidateStatus,
    DraftStatus,
    Program,
    VacancyStatus,
)
from minori.domain.entities import (
    AuditLogData,
    AuditLogRecord,
    CandidateData,
    CandidateRecord,
    MatchData,
    MatchRecord,
    NotificationAttemptData,
    NotificationAttemptRecord,
    NotificationData,
    NotificationRecord,
    PlacementData,
    PlacementRecord,
    PlacementStageData,
    PlacementStageRecord,
    VacancyData,
    VacancyDraftData,
    VacancyDraftRecord,
    VacancyRecord,
)


class CandidateRepository(Protocol):
    """Candidate data access contract with externally owned transactions."""

    def create(self, data: CandidateData) -> CandidateRecord: ...
    def get(self, identifier: UUID) -> CandidateRecord | None: ...
    def get_by_reference(self, reference: str) -> CandidateRecord | None: ...
    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        preferred_program: Program | None = None,
        status: CandidateStatus | None = None,
    ) -> list[CandidateRecord]: ...
    def replace(self, identifier: UUID, data: CandidateData) -> CandidateRecord: ...
    def archive(self, identifier: UUID) -> CandidateRecord: ...


class VacancyRepository(Protocol):
    """Vacancy data access contract with externally owned transactions."""

    def create(self, data: VacancyData) -> VacancyRecord: ...
    def get(self, identifier: UUID) -> VacancyRecord | None: ...
    def get_by_reference(self, reference: str) -> VacancyRecord | None: ...
    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        program: Program | None = None,
        status: VacancyStatus | None = None,
    ) -> list[VacancyRecord]: ...
    def replace(self, identifier: UUID, data: VacancyData) -> VacancyRecord: ...
    def archive(self, identifier: UUID) -> VacancyRecord: ...


class VacancyDraftRepository(Protocol):
    """VacancyDraft data access contract with externally owned transactions."""

    def create(self, data: VacancyDraftData) -> VacancyDraftRecord: ...
    def get(self, identifier: UUID) -> VacancyDraftRecord | None: ...
    def get_by_reference(self, reference: str) -> VacancyDraftRecord | None: ...
    def list(
        self, *, limit: int = 100, offset: int = 0, status: DraftStatus | None = None
    ) -> list[VacancyDraftRecord]: ...
    def replace(self, identifier: UUID, data: VacancyDraftData) -> VacancyDraftRecord: ...


class MatchRepository(Protocol):
    """Match data access contract with externally owned transactions."""

    def create(self, data: MatchData) -> MatchRecord: ...
    def get(self, identifier: UUID) -> MatchRecord | None: ...
    def get_by_pair(self, candidate_id: UUID, vacancy_id: UUID) -> MatchRecord | None: ...
    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[MatchRecord]: ...
    def replace(self, identifier: UUID, data: MatchData) -> MatchRecord: ...


class PlacementRepository(Protocol):
    """Placement data access contract with externally owned transactions."""

    def create(self, data: PlacementData) -> PlacementRecord: ...
    def get(self, identifier: UUID) -> PlacementRecord | None: ...
    def get_by_reference(self, reference: str) -> PlacementRecord | None: ...
    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[PlacementRecord]: ...
    def replace(self, identifier: UUID, data: PlacementData) -> PlacementRecord: ...
    def get_by_pair(self, candidate_id: UUID, vacancy_id: UUID) -> PlacementRecord | None: ...
    def list(
        self,
        *,
        query: str | None = None,
        status=None,
        candidate_id=None,
        vacancy_id=None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PlacementRecord]: ...
    def capacity_used(self, vacancy_id: UUID) -> int: ...
    def candidate_active(self, candidate_id: UUID) -> bool: ...


class PlacementStageRepository(Protocol):
    """PlacementStage data access contract with externally owned transactions."""

    def create(self, data: PlacementStageData) -> PlacementStageRecord: ...
    def get(self, identifier: UUID) -> PlacementStageRecord | None: ...
    def get_by_code(self, placement_id: UUID, code: str) -> PlacementStageRecord | None: ...
    def list_for_placement(
        self, placement_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[PlacementStageRecord]: ...
    def replace(self, identifier: UUID, data: PlacementStageData) -> PlacementStageRecord: ...
    def list(self, *, limit: int = 100, offset: int = 0) -> list[PlacementStageRecord]: ...


class NotificationRepository(Protocol):
    """Notification data access contract with externally owned transactions."""

    def create(self, data: NotificationData) -> NotificationRecord: ...
    def get(self, identifier: UUID) -> NotificationRecord | None: ...
    def get_by_deduplication_key(self, deduplication_key: str) -> NotificationRecord | None: ...
    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[NotificationRecord]: ...
    def replace(self, identifier: UUID, data: NotificationData) -> NotificationRecord: ...


class NotificationAttemptRepository(Protocol):
    """NotificationAttempt data access contract with externally owned transactions."""

    def append(self, data: NotificationAttemptData) -> NotificationAttemptRecord: ...
    def get(self, identifier: UUID) -> NotificationAttemptRecord | None: ...
    def get_by_number(
        self, notification_id: UUID, attempt_number: int
    ) -> NotificationAttemptRecord | None: ...
    def list_for_notification(
        self, notification_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[NotificationAttemptRecord]: ...


class AuditLogRepository(Protocol):
    """AuditLog data access contract with externally owned transactions."""

    def append(self, data: AuditLogData) -> AuditLogRecord: ...
    def get(self, identifier: UUID) -> AuditLogRecord | None: ...
    def get_by_reference(self, reference: str) -> AuditLogRecord | None: ...
    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        entity_type: AuditEntityType | None = None,
        entity_id: UUID | None = None,
    ) -> list[AuditLogRecord]: ...
