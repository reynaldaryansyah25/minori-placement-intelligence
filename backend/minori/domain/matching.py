"""Explainable matching values, policy, and persistence ports; standard library only."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from minori.domain.entities import RecordMetadata

ALGORITHM_VERSION = "employer_rules_2026_10"
SCORING_WEIGHTS = (
    ("language", 0.35),
    ("experience", 0.30),
    ("additional_qualifications", 0.20),
    ("preference_readiness", 0.15),
)


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CheckOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    INFO = "INFO"


class ReasonCode(StrEnum):
    PROGRAM_ACCEPTED = "PROGRAM_ACCEPTED"
    PROGRAM_MISMATCH = "PROGRAM_MISMATCH"
    CANDIDATE_ACTIVE = "CANDIDATE_ACTIVE"
    CANDIDATE_INACTIVE = "CANDIDATE_INACTIVE"
    READINESS_UNCONFIRMED = "READINESS_UNCONFIRMED"
    VACANCY_OPEN = "VACANCY_OPEN"
    VACANCY_PAUSED = "VACANCY_PAUSED"
    VACANCY_CLOSED = "VACANCY_CLOSED"
    DEADLINE_VALID = "DEADLINE_VALID"
    DEADLINE_PASSED = "DEADLINE_PASSED"
    LANGUAGE_ACCEPTED = "LANGUAGE_ACCEPTED"
    LANGUAGE_NOT_REQUIRED = "LANGUAGE_NOT_REQUIRED"
    LANGUAGE_BELOW_MINIMUM = "LANGUAGE_BELOW_MINIMUM"
    LANGUAGE_EVIDENCE_MISSING = "LANGUAGE_EVIDENCE_MISSING"
    LANGUAGE_EVIDENCE_OUTDATED = "LANGUAGE_EVIDENCE_OUTDATED"
    FUTURE_LANGUAGE_TEST = "FUTURE_LANGUAGE_TEST"
    CERTIFICATION_VALID = "CERTIFICATION_VALID"
    CERTIFICATION_MISSING = "CERTIFICATION_MISSING"
    CERTIFICATION_EXPIRED = "CERTIFICATION_EXPIRED"
    CERTIFICATION_NOT_YET_VALID = "CERTIFICATION_NOT_YET_VALID"
    SKILL_PRESENT = "SKILL_PRESENT"
    SKILL_MISSING = "SKILL_MISSING"
    EXPERIENCE_SUFFICIENT = "EXPERIENCE_SUFFICIENT"
    EXPERIENCE_INSUFFICIENT = "EXPERIENCE_INSUFFICIENT"
    EXPERIENCE_EVIDENCE_MISSING = "EXPERIENCE_EVIDENCE_MISSING"
    EXPERIENCE_OVERLAP_MERGED = "EXPERIENCE_OVERLAP_MERGED"
    FUTURE_EXPERIENCE_IGNORED = "FUTURE_EXPERIENCE_IGNORED"
    PREFECTURE_PREFERENCE_UNKNOWN = "PREFECTURE_PREFERENCE_UNKNOWN"


@dataclass(frozen=True, kw_only=True)
class RuleCheck:
    code: ReasonCode
    outcome: CheckOutcome
    requirement: str
    message: str
    evidence: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class ScoreComponent:
    name: str
    weight: float
    score: float
    contribution: float
    formula: str
    evidence: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class EligibilityResult:
    status: EligibilityStatus
    checks: tuple[RuleCheck, ...]
    language_score: float
    language_evidence: dict[str, object]
    relevant_days: int
    relevant_months: float


@dataclass(frozen=True, kw_only=True)
class MatchingEvaluation:
    candidate_id: UUID
    vacancy_id: UUID
    eligibility_status: EligibilityStatus
    total_score: float | None
    algorithm_version: str
    evaluated_at: datetime
    input_fingerprint: str
    explanation: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class EvaluationRecord(MatchingEvaluation, RecordMetadata):
    """Append-only snapshot, independent of the staff decision in Match."""


class EvaluationRepository(Protocol):
    def append(self, evaluation: MatchingEvaluation) -> EvaluationRecord: ...
    def find_identical(self, evaluation: MatchingEvaluation) -> EvaluationRecord | None: ...
    def get(self, identifier: UUID) -> EvaluationRecord | None: ...
    def latest(self, candidate_id: UUID, vacancy_id: UUID) -> EvaluationRecord | None: ...
    def list(
        self,
        *,
        candidate_id: UUID | None = None,
        vacancy_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationRecord]: ...


TransactionFactory = Callable[[], AbstractContextManager]
