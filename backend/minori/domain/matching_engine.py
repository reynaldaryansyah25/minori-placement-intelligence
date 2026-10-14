"""Pure evaluation, explanation, input freshness, and deterministic ranking."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from minori.domain.eligibility import EligibilityEngine
from minori.domain.entities import CandidateRecord, VacancyRecord
from minori.domain.matching import (
    ALGORITHM_VERSION,
    CheckOutcome,
    EligibilityStatus,
    MatchingEvaluation,
)
from minori.domain.scoring import WeightedScoringEngine


def input_fingerprint(candidate: CandidateRecord, vacancy: VacancyRecord) -> str:
    """Hash only fields consumed by the algorithm, independent of row ordering and names."""
    values = {
        "candidate": {
            key: value
            for key, value in asdict(candidate).items()
            if key
            not in {
                "created_at",
                "updated_at",
                "full_name",
                "education_level",
                "domicile_city",
                "reference",
                "email",
                "email_verified",
                "email_consent",
            }
        },
        "vacancy": {
            key: value
            for key, value in asdict(vacancy).items()
            if key not in {"created_at", "updated_at", "title", "employer_name", "reference"}
        },
    }
    # Child collections and code sets have no semantic order.
    for aggregate in values.values():
        for key, value in aggregate.items():
            if isinstance(value, tuple):
                aggregate[key] = sorted(
                    value, key=lambda item: json.dumps(item, sort_keys=True, default=str)
                )
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


class ExplanationEngine:
    def explain(self, eligibility, components) -> dict[str, object]:
        checks = [asdict(item) for item in eligibility.checks]
        return {
            "reason_codes": list(dict.fromkeys(item.code.value for item in eligibility.checks)),
            "checks": checks,
            "unmet_requirements": [item for item in checks if item["outcome"] == CheckOutcome.FAIL],
            "verification_needed": [
                item for item in checks if item["outcome"] == CheckOutcome.REVIEW
            ],
            "score_components": [asdict(item) for item in components],
            "score_used_for_ranking": eligibility.status == EligibilityStatus.ELIGIBLE,
            "policy": "Employer rules only; staff approval and immigration decisions are separate.",
        }


class MatchingEngine:
    def evaluate(
        self, candidate: CandidateRecord, vacancy: VacancyRecord, as_of: datetime
    ) -> MatchingEvaluation:
        eligibility = EligibilityEngine().evaluate(candidate, vacancy, as_of)
        components = WeightedScoringEngine().score(
            candidate, vacancy, eligibility, as_of.astimezone(UTC).date()
        )
        total = (
            round(sum(item.contribution for item in components), 8)
            if eligibility.status == EligibilityStatus.ELIGIBLE
            else None
        )
        return MatchingEvaluation(
            candidate_id=candidate.id,
            vacancy_id=vacancy.id,
            eligibility_status=eligibility.status,
            total_score=total,
            evaluated_at=as_of.astimezone(UTC),
            algorithm_version=ALGORITHM_VERSION,
            input_fingerprint=input_fingerprint(candidate, vacancy),
            explanation=ExplanationEngine().explain(eligibility, components),
        )


class RankingEngine:
    def rank(
        self, evaluations: list[tuple[CandidateRecord, MatchingEvaluation]]
    ) -> list[MatchingEvaluation]:
        eligible = [
            (candidate, result)
            for candidate, result in evaluations
            if result.eligibility_status == EligibilityStatus.ELIGIBLE
        ]
        return [
            result
            for _, result in sorted(
                eligible,
                key=lambda item: (-item[1].total_score, item[0].reference, str(item[0].id)),
            )
        ]
