"""Notification records and attempts, without dispatch or reminder behavior."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, computed_field, model_validator

from minori.domain.catalogs import AttemptStatus, NotificationChannel, NotificationStatus
from minori.domain.reminders import is_automatic_reminder
from minori.schemas.common import Code, InputSchema, RecordFields, Reference


class NotificationCreate(InputSchema):
    approved_message: dict[str, str] | None = None
    approved_by: str | None = None
    approved_at: AwareDatetime | None = None
    approval_fingerprint: str | None = None
    manual_request_key: str | None = None
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
    managed: bool = False
    dry_run: bool = True
    available_at: AwareDatetime | None = None
    event_at: AwareDatetime | None = None
    schedule_revision: StrictInt = Field(default=1, gt=0)
    schedule_context: dict[str, str | int | None] = Field(default_factory=dict)
    attempt_count: StrictInt = Field(default=0, ge=0)
    max_attempts: StrictInt = Field(default=3, gt=0)
    claimed_at: AwareDatetime | None = None
    lease_expires_at: AwareDatetime | None = None
    claim_token_hash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    processed_at: AwareDatetime | None = None
    last_error_code: Code | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        if self.placement_stage_id and self.placement_id is None:
            raise ValueError("A placement step requires its placement ID")
        if (self.status == NotificationStatus.SENT) != (self.sent_at is not None):
            raise ValueError("Only sent intents must have a sent timestamp")
        if self.sent_at and self.sent_at < self.scheduled_at:
            raise ValueError("Sent timestamp precedes scheduled time")
        if self.status == NotificationStatus.PROCESSING:
            if (
                not self.claim_token_hash
                or not self.claimed_at
                or not self.lease_expires_at
                or self.lease_expires_at <= self.claimed_at
            ):
                raise ValueError("Processing notifications require a valid claim and lease")
        elif self.claimed_at is not None or self.lease_expires_at is not None:
            raise ValueError("Only processing notifications can hold a lease")
        if self.managed and (
            self.event_at is None or self.available_at is None or self.placement_stage_id is None
        ):
            raise ValueError(
                "Managed reminders require an activity, event and availability timestamp"
            )
        allowed = {"activity", "scheduled_at", "location", "timezone", "revision"}
        if set(self.schedule_context) - allowed:
            raise ValueError("Schedule context contains unsupported data")
        return self


class NotificationRead(NotificationCreate, RecordFields):
    """Queue state and optional staff-approved snapshot; claim secrets stay private."""

    claim_token_hash: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def delivery_kind(self) -> Literal["automatic", "manual", "legacy"]:
        if not self.managed:
            return "legacy"
        return "automatic" if is_automatic_reminder(self) else "manual"


class NotificationAttemptCreate(InputSchema):
    notification_id: UUID
    attempt_number: StrictInt = Field(gt=0)
    status: AttemptStatus
    attempted_at: AwareDatetime
    finished_at: AwareDatetime | None
    error_code: Code | None = Field(default=None, max_length=64)
    provider_reference: str | None = Field(default=None, min_length=1, max_length=120)
    claim_token_hash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.finished_at and self.finished_at < self.attempted_at:
            raise ValueError("Finished timestamp precedes attempted time")
        if (self.status in {AttemptStatus.FAILED, AttemptStatus.ABANDONED}) != (
            self.error_code is not None
        ):
            raise ValueError("Only failed attempts must have an error code")
        if (self.status == AttemptStatus.PROCESSING) != (self.finished_at is None):
            raise ValueError("Only processing attempts can have no finish timestamp")
        return self


class NotificationAttemptRead(NotificationAttemptCreate, RecordFields):
    """Attempt history is append-only through the repository interface."""

    claim_token_hash: str | None = Field(default=None, exclude=True)
