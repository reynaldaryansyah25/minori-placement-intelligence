"""Calendar reminder policy, queue values, and ports independent of frameworks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from minori.domain.catalogs import PlacementStatus, PlacementStepStatus, PlacementStepType
from minori.domain.entities import NotificationRecord
from minori.domain.errors import BusinessConflictError


class DeliveryErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    SCHEDULE_CHANGED = "SCHEDULE_CHANGED"
    ACTIVITY_CANCELLED = "ACTIVITY_CANCELLED"
    EVENT_PASSED = "EVENT_PASSED"
    RECIPIENT_INACTIVE = "RECIPIENT_INACTIVE"


@dataclass(frozen=True)
class ReminderPolicy:
    timezone: str = "Asia/Jakarta"
    delivery_time: time = time(9, 0)
    dry_run: bool = True
    lease_seconds: int = 120
    max_attempts: int = 3
    retry_base_seconds: int = 60
    retry_max_seconds: int = 3600
    demo_notification_recipient: str | None = None
    notification_delivery_mode: str = "dry_run"
    mailpit_inbox_email: str = "mailpit@minori.local"

    def resolve_recipient(
        self, candidate_reference: str, *, dry_run: bool | None = None
    ) -> dict[str, object]:
        clean_ref = candidate_reference.lower().replace("_", "-").strip()
        intended = f"kandidat-{clean_ref}@demo.minori.internal"

        if self.dry_run if dry_run is None else dry_run:
            effective = None
            mode = "dry_run"
            allowed = False
        elif self.notification_delivery_mode == "mailpit":
            effective = self.mailpit_inbox_email
            mode = "mailpit"
            allowed = True
        elif (
            self.demo_notification_recipient and self.notification_delivery_mode == "demo_recipient"
        ):
            effective = self.demo_notification_recipient
            mode = "demo_recipient"
            allowed = True
        else:
            effective = None
            mode = "dry_run"
            allowed = False

        return {
            "intended_recipient": intended,
            "effective_recipient": effective,
            "routing_mode": mode,
            "delivery_allowed": allowed,
            "safety_notice": (
                "Mode demo: email fiktif kandidat dialihkan secara aman ke inbox pengujian lokal "
                "atau dry-run dan tidak dikirim ke pihak luar."
            ),
        }

    def __post_init__(self):
        ZoneInfo(self.timezone)
        if self.delivery_time.tzinfo is not None:
            raise ValueError("Delivery time must be a local wall-clock time")
        if (
            min(
                self.lease_seconds,
                self.max_attempts,
                self.retry_base_seconds,
                self.retry_max_seconds,
            )
            <= 0
        ):
            raise ValueError("Lease and retry settings must be positive")

    def scheduled_at(self, event_at: datetime, kind: PlacementStepType) -> datetime:
        if event_at.tzinfo is None or event_at.utcoffset() is None:
            raise ValueError("Event timestamp must include a timezone")
        days = {PlacementStepType.INTERVIEW: 3, PlacementStepType.MEDICAL_CHECK: 1}
        if kind not in days:
            raise ValueError("Only interview and medical check reminders have a calendar offset")
        zone = ZoneInfo(self.timezone)
        local_date = event_at.astimezone(zone).date() - timedelta(days=days[kind])
        local = datetime.combine(local_date, self.delivery_time, zone)
        # Reject ambiguous/nonexistent wall times instead of silently choosing a DST offset.
        if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
            raise ValueError("Reminder wall time is ambiguous or does not exist in this timezone")
        if local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local.replace(
            tzinfo=None
        ):
            raise ValueError("Reminder wall time does not exist in this timezone")
        return local.astimezone(UTC)

    def backoff(self, attempt_number: int) -> timedelta:
        seconds = min(
            self.retry_max_seconds, self.retry_base_seconds * 2 ** min(30, attempt_number - 1)
        )
        return timedelta(seconds=seconds)


PLACEMENT_TRANSITIONS = {
    PlacementStatus.PREPARING: {PlacementStatus.IN_PROGRESS, PlacementStatus.CANCELLED},
    PlacementStatus.IN_PROGRESS: {PlacementStatus.COMPLETED, PlacementStatus.CANCELLED},
    PlacementStatus.COMPLETED: set(),
    PlacementStatus.CANCELLED: set(),
}
ACTIVITY_TRANSITIONS = {
    PlacementStepStatus.PENDING: {PlacementStepStatus.SCHEDULED, PlacementStepStatus.CANCELLED},
    PlacementStepStatus.SCHEDULED: {
        PlacementStepStatus.IN_PROGRESS,
        PlacementStepStatus.COMPLETED,
        PlacementStepStatus.CANCELLED,
    },
    PlacementStepStatus.IN_PROGRESS: {PlacementStepStatus.COMPLETED, PlacementStepStatus.CANCELLED},
    PlacementStepStatus.COMPLETED: set(),
    PlacementStepStatus.CANCELLED: set(),
}


def validate_transition(current, target, transitions) -> None:
    if target != current and target not in transitions[current]:
        raise BusinessConflictError(f"Transition {current.value} -> {target.value} is not allowed")


class NotificationQueue(Protocol):
    """Queue operations are called within an externally owned immediate transaction."""

    def list(
        self,
        *,
        status=None,
        due_before=None,
        placement_id=None,
        active_only=False,
        limit=100,
        offset=0,
    ) -> list[NotificationRecord]: ...
    def for_activity(self, identifier: UUID) -> list[NotificationRecord]: ...
    def claim(
        self,
        identifier: UUID | None,
        now: datetime,
        token_hash: str,
        lease_expires_at: datetime,
        *,
        dry_run_only=False,
    ) -> NotificationRecord | None: ...
    def finish_attempt(
        self,
        notification_id: UUID,
        attempt_number: int,
        *,
        status,
        finished_at: datetime,
        error_code: str | None = None,
        provider_reference: str | None = None,
    ) -> None: ...
    def last_attempt(self, identifier: UUID): ...
