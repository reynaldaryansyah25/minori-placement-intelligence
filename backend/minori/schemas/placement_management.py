"""Explicit human operations; ownership and revision fields are assigned by the service."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from minori.domain.catalogs import PlacementStatus, PlacementStepStatus, PlacementStepType
from minori.schemas.common import Code, InputSchema, Reference


class StaffDecision(InputSchema):
    candidate_id: UUID
    vacancy_id: UUID
    decision: Literal["approved", "rejected"]
    actor_reference: Code = Field(max_length=80)
    reason_code: Code | None = None


class PlacementRequest(InputSchema):
    reference: Reference
    match_id: UUID
    actor_reference: Code = Field(max_length=80)
    planned_departure_at: AwareDatetime | None = None


class PlacementUpdate(InputSchema):
    actor_reference: Code = Field(max_length=80)
    status: PlacementStatus | None = None
    planned_departure_at: AwareDatetime | None = None
    actual_departure_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def reject_null_status(self) -> Self:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null")
        return self


class ActivityRequest(InputSchema):
    actor_reference: Code = Field(max_length=80)
    code: Code = Field(max_length=64)
    step_type: PlacementStepType
    sequence_number: StrictInt = Field(gt=0)
    scheduled_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    location: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.due_at and (not self.scheduled_at or self.due_at < self.scheduled_at):
            raise ValueError("A deadline requires a scheduled start no later than the deadline")
        return self


class ActivityUpdate(InputSchema):
    actor_reference: Code = Field(max_length=80)
    status: PlacementStepStatus | None = None
    scheduled_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    location: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def reject_null_status(self) -> Self:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null")
        return self


class ActorRequest(InputSchema):
    actor_reference: Code = Field(max_length=80)
