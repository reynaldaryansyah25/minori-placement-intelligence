"""Immutable database input and output values for inward-facing repository ports."""

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from minori.domain.catalogs import (
    AttemptStatus,
    AuditEntityType,
    CandidateStatus,
    DraftStatus,
    LanguageTestType,
    MatchSource,
    MatchStatus,
    NotificationChannel,
    NotificationStatus,
    PlacementStatus,
    PlacementStepStatus,
    PlacementStepType,
    Program,
    VacancyStatus,
)


@dataclass(frozen=True, kw_only=True)
class RecordMetadata:
    id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class LanguageTestData:
    test_type: LanguageTestType
    level: str
    taken_on: date
    score: int | None = None


@dataclass(frozen=True, kw_only=True)
class CertificationData:
    code: str
    name: str
    issuer: str
    issued_on: date
    expires_on: date | None = None


@dataclass(frozen=True, kw_only=True)
class ExperienceData:
    employer_name: str
    sector: str
    role: str
    started_on: date
    ended_on: date | None = None


@dataclass(frozen=True, kw_only=True)
class LanguageRequirementData:
    test_type: LanguageTestType
    minimum_level: str


@dataclass(frozen=True, kw_only=True)
class CandidateData:
    reference: str
    full_name: str
    preferred_program: Program
    education_level: str
    domicile_city: str
    skills: tuple[str, ...] = ()
    status: CandidateStatus = CandidateStatus.REGISTERED
    language_tests: tuple[LanguageTestData, ...] = ()
    certifications: tuple[CertificationData, ...] = ()
    experiences: tuple[ExperienceData, ...] = ()


@dataclass(frozen=True, kw_only=True)
class CandidateRecord(CandidateData, RecordMetadata):
    """Candidate snapshot detached from SQLAlchemy and its session."""


@dataclass(frozen=True, kw_only=True)
class VacancyData:
    reference: str
    title: str
    employer_name: str
    program: Program
    sector: str
    prefecture: str
    quota: int
    minimum_experience_months: int = 0
    required_skills: tuple[str, ...] = ()
    required_certifications: tuple[str, ...] = ()
    language_requirements: tuple[LanguageRequirementData, ...] = ()
    status: VacancyStatus = VacancyStatus.OPEN
    application_deadline: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class VacancyRecord(VacancyData, RecordMetadata):
    """Vacancy requirements are employer data, not inferred eligibility rules."""


@dataclass(frozen=True, kw_only=True)
class VacancyDraftData:
    reference: str
    source_channel: str
    source_reference: str
    proposed_data: dict[str, object]
    status: DraftStatus = DraftStatus.DRAFT
    published_vacancy_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class VacancyDraftRecord(VacancyDraftData, RecordMetadata):
    """Validated draft snapshot awaiting explicit review."""


@dataclass(frozen=True, kw_only=True)
class MatchData:
    candidate_id: UUID
    vacancy_id: UUID
    status: MatchStatus = MatchStatus.PROPOSED
    source: MatchSource = MatchSource.MANUAL
    score: float | None = None
    reviewed_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class MatchRecord(MatchData, RecordMetadata):
    """Stored association; no matching or scoring algorithm is provided."""


@dataclass(frozen=True, kw_only=True)
class PlacementData:
    reference: str
    candidate_id: UUID
    vacancy_id: UUID
    match_id: UUID | None = None
    status: PlacementStatus = PlacementStatus.PREPARING
    planned_departure_at: datetime | None = None
    actual_departure_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class PlacementRecord(PlacementData, RecordMetadata):
    """Administrative placement snapshot."""


@dataclass(frozen=True, kw_only=True)
class PlacementStageData:
    placement_id: UUID
    code: str
    step_type: PlacementStepType
    sequence_number: int
    status: PlacementStepStatus = PlacementStepStatus.PENDING
    scheduled_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    location: str | None = None


@dataclass(frozen=True, kw_only=True)
class PlacementStageRecord(PlacementStageData, RecordMetadata):
    """Scheduling data with no medical findings or diagnosis fields."""


@dataclass(frozen=True, kw_only=True)
class NotificationData:
    reference: str
    deduplication_key: str
    candidate_id: UUID
    template_code: str
    scheduled_at: datetime
    channel: NotificationChannel = NotificationChannel.INTERNAL
    status: NotificationStatus = NotificationStatus.PENDING
    placement_id: UUID | None = None
    placement_stage_id: UUID | None = None
    sent_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class NotificationRecord(NotificationData, RecordMetadata):
    """Notification intent; repositories do not dispatch messages."""


@dataclass(frozen=True, kw_only=True)
class NotificationAttemptData:
    notification_id: UUID
    attempt_number: int
    status: AttemptStatus
    attempted_at: datetime
    finished_at: datetime
    error_code: str | None = None
    provider_reference: str | None = None


@dataclass(frozen=True, kw_only=True)
class NotificationAttemptRecord(NotificationAttemptData, RecordMetadata):
    """Immutable delivery history without raw provider payloads."""


@dataclass(frozen=True, kw_only=True)
class AuditLogData:
    reference: str
    actor_reference: str
    action: str
    entity_type: AuditEntityType
    entity_id: UUID
    occurred_at: datetime
    context: dict[str, str | bool | int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class AuditLogRecord(AuditLogData, RecordMetadata):
    """Append-only operational history through the repository interface."""
