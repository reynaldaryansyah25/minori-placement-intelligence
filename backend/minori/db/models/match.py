"""Persisted staff associations, separated from append-only machine evaluations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, UTCDateTime, enum_type
from minori.domain.catalogs import MatchSource, MatchStatus

if TYPE_CHECKING:
    from minori.db.models.candidate import Candidate
    from minori.db.models.placement import Placement
    from minori.db.models.vacancy import Vacancy


class Match(IdentityTimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("candidate_id", "vacancy_id"),
        UniqueConstraint("id", "candidate_id", "vacancy_id"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="score_range"),
        CheckConstraint(
            "(status = 'proposed' AND reviewed_at IS NULL) OR "
            "(status IN ('approved','rejected') AND reviewed_at IS NOT NULL)",
            name="review_timestamp",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), index=True
    )
    vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        enum_type(MatchStatus, "match_status"), default=MatchStatus.PROPOSED, index=True
    )
    source: Mapped[MatchSource] = mapped_column(
        enum_type(MatchSource, "match_source"), default=MatchSource.MANUAL
    )
    score: Mapped[float | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    candidate: Mapped[Candidate] = relationship(back_populates="matches")
    vacancy: Mapped[Vacancy] = relationship(back_populates="matches")
    placements: Mapped[list[Placement]] = relationship(
        back_populates="match", foreign_keys="Placement.match_id", passive_deletes="all"
    )
