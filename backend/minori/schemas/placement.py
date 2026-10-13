"""Administrative placement scheduling with timezone-aware timestamps."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from minori.domain.catalogs import PlacementStatus, PlacementStepStatus, PlacementStepType
from minori.schemas.common import Code, InputSchema, RecordFields, Reference


class PlacementCreate(InputSchema):
    reference: Reference
    candidate_id: UUID
    vacancy_id: UUID
    match_id: UUID | None = None
    status: PlacementStatus = PlacementStatus.PREPARING
    planned_departure_at: AwareDatetime | None = None
    actual_departure_at: AwareDatetime | None = None


class PlacementRead(PlacementCreate, RecordFields):
    """Placement ownership is immutable in the repository update operation."""


class PlacementStageCreate(InputSchema):
    placement_id: UUID
    code: Code = Field(max_length=64)
    step_type: PlacementStepType
    sequence_number: StrictInt = Field(gt=0)
    schedule_revision: StrictInt = Field(default=1, gt=0)
    status: PlacementStepStatus = PlacementStepStatus.PENDING
    scheduled_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    location: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_schedule(self) -> Self:
        if self.status in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}:
            if self.scheduled_at is None:
                raise ValueError("Scheduled steps require a schedule timestamp")
        if self.due_at and (self.scheduled_at is None or self.due_at < self.scheduled_at):
            raise ValueError("Due timestamp must follow the scheduled timestamp")
        if (self.status == PlacementStepStatus.COMPLETED) != (self.completed_at is not None):
            raise ValueError("Only completed steps must have a completion timestamp")
        if self.completed_at and self.scheduled_at and self.completed_at < self.scheduled_at:
            raise ValueError("Completion precedes scheduled time")
        return self


class PlacementStageRead(PlacementStageCreate, RecordFields):
    """Medical scheduling contains no medical result or diagnosis fields."""
