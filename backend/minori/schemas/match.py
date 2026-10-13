"""Staff decisions and legacy scores; machine eligibility has its own evaluation contract."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from minori.domain.catalogs import MatchSource, MatchStatus
from minori.schemas.common import InputSchema, RecordFields


class MatchCreate(InputSchema):
    candidate_id: UUID
    vacancy_id: UUID
    status: MatchStatus = MatchStatus.PROPOSED
    source: MatchSource = MatchSource.MANUAL
    score: float | None = Field(default=None, ge=0, le=1)
    reviewed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        if (self.status != MatchStatus.PROPOSED) != (self.reviewed_at is not None):
            raise ValueError("Reviewed associations require a review timestamp")
        return self


class MatchRead(MatchCreate, RecordFields):
    """Staff decision snapshot; matching never overwrites these fields."""
