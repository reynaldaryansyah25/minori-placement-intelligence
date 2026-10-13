"""Register all business tables before configuring mappers or Alembic metadata."""

from minori.db.models.audit import AuditLog
from minori.db.models.candidate import (
    Candidate,
    CandidateCertification,
    CandidateExperience,
    CandidateLanguageTest,
)
from minori.db.models.match import Match
from minori.db.models.matching_evaluation import MatchEvaluation
from minori.db.models.notification import Notification, NotificationAttempt
from minori.db.models.placement import Placement, PlacementStage
from minori.db.models.vacancy import Vacancy, VacancyDraft, VacancyLanguageRequirement

MODEL_TYPES = (
    Candidate,
    CandidateLanguageTest,
    CandidateCertification,
    CandidateExperience,
    Vacancy,
    VacancyLanguageRequirement,
    VacancyDraft,
    Match,
    MatchEvaluation,
    Placement,
    PlacementStage,
    Notification,
    NotificationAttempt,
    AuditLog,
)

__all__ = [
    "MODEL_TYPES",
    "AuditLog",
    "Candidate",
    "CandidateCertification",
    "CandidateExperience",
    "CandidateLanguageTest",
    "Match",
    "MatchEvaluation",
    "Notification",
    "NotificationAttempt",
    "Placement",
    "PlacementStage",
    "Vacancy",
    "VacancyDraft",
    "VacancyLanguageRequirement",
]
