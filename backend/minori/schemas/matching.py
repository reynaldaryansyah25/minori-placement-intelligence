"""Validated matching requests, structured explanations, and explicit staff decisions."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from minori.domain.catalogs import MatchStatus
from minori.domain.matching import SCORING_WEIGHTS, CheckOutcome, EligibilityStatus, ReasonCode
from minori.schemas.common import InputSchema, RecordFields


class EvaluationRequest(InputSchema):
    candidate_id: UUID | None = None
    vacancy_id: UUID | None = None
    as_of: AwareDatetime | None = None


class RuleCheckRead(InputSchema):
    code: ReasonCode
    outcome: CheckOutcome
    requirement: str
    message: str
    evidence: dict[str, object]


class ScoreComponentRead(InputSchema):
    name: str
    weight: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    contribution: float = Field(ge=0, le=1)
    formula: str
    evidence: dict[str, object]


class ExplanationRead(InputSchema):
    reason_codes: list[ReasonCode]
    checks: list[RuleCheckRead]
    unmet_requirements: list[RuleCheckRead]
    verification_needed: list[RuleCheckRead]
    score_components: list[ScoreComponentRead]
    score_used_for_ranking: bool
    policy: str


class EvaluationCreate(InputSchema):
    candidate_id: UUID
    vacancy_id: UUID
    eligibility_status: EligibilityStatus
    total_score: float | None = Field(ge=0, le=1)
    algorithm_version: str = Field(min_length=1, max_length=80)
    evaluated_at: AwareDatetime
    input_fingerprint: str = Field(pattern="^[a-f0-9]{64}$")
    explanation: ExplanationRead

    @model_validator(mode="after")
    def validate_score(self) -> Self:
        if (self.eligibility_status == EligibilityStatus.ELIGIBLE) != (
            self.total_score is not None
        ):
            raise ValueError("Only eligible evaluations have a total ranking score")
        components = self.explanation.score_components
        if len(components) != 4 or len({item.name for item in components}) != 4:
            raise ValueError("Four distinct score components are required")
        if abs(sum(item.weight for item in components) - 1) > 1e-8:
            raise ValueError("Score weights must sum to one")
        weights = dict(SCORING_WEIGHTS)
        if any(
            item.name not in weights or item.weight != weights[item.name] for item in components
        ):
            raise ValueError("Components must use the published scoring policy")
        if any(abs(item.contribution - item.weight * item.score) > 1e-8 for item in components):
            raise ValueError("Invalid weighted contribution")
        if (
            self.total_score is not None
            and abs(self.total_score - sum(item.contribution for item in components)) > 1e-8
        ):
            raise ValueError("Total does not equal the weighted component sum")
        explanation = self.explanation
        failed = [item for item in explanation.checks if item.outcome == CheckOutcome.FAIL]
        review = [item for item in explanation.checks if item.outcome == CheckOutcome.REVIEW]
        expected = (
            EligibilityStatus.NOT_ELIGIBLE
            if failed
            else EligibilityStatus.NEEDS_REVIEW
            if review
            else EligibilityStatus.ELIGIBLE
        )
        if (
            expected != self.eligibility_status
            or explanation.unmet_requirements != failed
            or explanation.verification_needed != review
            or explanation.reason_codes
            != list(dict.fromkeys(item.code for item in explanation.checks))
            or explanation.score_used_for_ranking != (expected == EligibilityStatus.ELIGIBLE)
        ):
            raise ValueError("Eligibility and explanation disagree")
        return self


class EvaluationRead(EvaluationCreate, RecordFields):
    """Stored evaluation snapshot."""


class MatchingResultRead(EvaluationCreate):
    evaluation_id: UUID | None
    candidate_reference: str
    vacancy_reference: str
    staff_status: MatchStatus
    match_id: UUID | None
    is_stale: bool
    active_recommendation: bool


class EvaluationBatchRead(InputSchema):
    evaluated_count: int
    results: list[MatchingResultRead]


class RankedMatchingRead(MatchingResultRead):
    rank: int = Field(ge=1)
