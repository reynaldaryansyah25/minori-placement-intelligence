"""Append-only machine evaluations, separated from manual staff associations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, UTCDateTime, enum_type
from minori.domain.matching import EligibilityStatus


class MatchEvaluation(IdentityTimestampMixin, Base):
    __tablename__ = "match_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "vacancy_id",
            "input_fingerprint",
            "evaluated_at",
            "algorithm_version",
            name="uq_match_evaluations_input_time",
        ),
        CheckConstraint(
            "total_score IS NULL OR (total_score >= 0 AND total_score <= 1)",
            name="evaluation_score_range",
        ),
        CheckConstraint(
            "(eligibility_status = 'ELIGIBLE' AND total_score IS NOT NULL) OR "
            "(eligibility_status != 'ELIGIBLE' AND total_score IS NULL)",
            name="eligibility_score",
        ),
        Index("ix_match_evaluations_pair_time", "candidate_id", "vacancy_id", "evaluated_at"),
        Index("ix_match_evaluations_vacancy_eligibility", "vacancy_id", "eligibility_status"),
    )
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id", ondelete="RESTRICT"))
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="RESTRICT"))
    eligibility_status: Mapped[EligibilityStatus] = mapped_column(
        enum_type(EligibilityStatus, "evaluation_eligibility")
    )
    total_score: Mapped[float | None]
    algorithm_version: Mapped[str] = mapped_column(String(80))
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[dict[str, object]] = mapped_column(JSON)
