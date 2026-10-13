"""Notification records and attempts, without dispatch or reminder behavior."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from minori.domain.catalogs import AttemptStatus, NotificationChannel, NotificationStatus
from minori.schemas.common import Code, InputSchema, RecordFields, Reference


class NotificationCreate(InputSchema):
    reference: Reference
    deduplication_key: str = Field(min_length=1, max_length=160)
    candidate_id: UUID
    template_code: Code
    scheduled_at: AwareDatetime
    channel: NotificationChannel = NotificationChannel.INTERNAL
    status: NotificationStatus = NotificationStatus.PENDING
    placement_id: UUID | None = None
    placement_stage_id: UUID | None = None
    sent_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        if self.placement_stage_id and self.placement_id is None:
            raise ValueError("A placement step requires its placement ID")
        if (self.status == NotificationStatus.SENT) != (self.sent_at is not None):
            raise ValueError("Only sent intents must have a sent timestamp")
        if self.sent_at and self.sent_at < self.scheduled_at:
            raise ValueError("Sent timestamp precedes scheduled time")
        return self


class NotificationRead(NotificationCreate, RecordFields):
    """No recipient contact data or message bodies are stored."""


class NotificationAttemptCreate(InputSchema):
    notification_id: UUID
    attempt_number: StrictInt = Field(gt=0)
    status: AttemptStatus
    attempted_at: AwareDatetime
    finished_at: AwareDatetime
    error_code: Code | None = Field(default=None, max_length=64)
    provider_reference: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.finished_at < self.attempted_at:
            raise ValueError("Finished timestamp precedes attempted time")
        if (self.status == AttemptStatus.FAILED) != (self.error_code is not None):
            raise ValueError("Only failed attempts must have an error code")
        return self


class NotificationAttemptRead(NotificationAttemptCreate, RecordFields):
    """Attempt history is append-only through the repository interface."""
