"""Notification intents and immutable attempts; no dispatch or reminder logic."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, ReferenceMixin, UTCDateTime, enum_type
from minori.domain.catalogs import AttemptStatus, NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from minori.db.models.candidate import Candidate
    from minori.db.models.placement import Placement, PlacementStage


class Notification(ReferenceMixin, IdentityTimestampMixin, Base):
    approved_message: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    approved_by: Mapped[str | None] = mapped_column(String(80))
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approval_fingerprint: Mapped[str | None] = mapped_column(String(64))
    manual_request_key: Mapped[str | None] = mapped_column(String(80))
    __tablename__ = "notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["placement_id", "candidate_id"],
            ["placements.id", "placements.candidate_id"],
            name="fk_notifications_placement_candidate",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["placement_stage_id", "placement_id"],
            ["placement_stages.id", "placement_stages.placement_id"],
            name="fk_notifications_step_placement",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "placement_stage_id IS NULL OR placement_id IS NOT NULL", name="step_parent"
        ),
        CheckConstraint(
            "(status = 'sent' AND sent_at IS NOT NULL) OR (status != 'sent' AND sent_at IS NULL)",
            name="sent_timestamp",
        ),
        CheckConstraint("sent_at IS NULL OR sent_at >= scheduled_at", name="sent_range"),
        CheckConstraint(
            "schedule_revision > 0 AND attempt_count >= 0 AND max_attempts > 0",
            name="queue_counters",
        ),
        CheckConstraint(
            "(status = 'processing' AND claimed_at IS NOT NULL AND "
            "lease_expires_at > claimed_at AND claim_token_hash IS NOT NULL) OR "
            "(status != 'processing' AND claimed_at IS NULL AND lease_expires_at IS NULL)",
            name="claim_state",
        ),
        CheckConstraint(
            "managed = 0 OR (event_at IS NOT NULL AND available_at IS NOT NULL "
            "AND placement_stage_id IS NOT NULL)",
            name="managed_schedule",
        ),
        Index("ix_notifications_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_notifications_queue_due", "managed", "status", "available_at"),
        Index("ix_notifications_manual_request_key", "manual_request_key", unique=True),
    )

    deduplication_key: Mapped[str] = mapped_column(String(160), unique=True)
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), index=True
    )
    placement_id: Mapped[UUID | None] = mapped_column(index=True)
    placement_stage_id: Mapped[UUID | None] = mapped_column(index=True)
    template_code: Mapped[str] = mapped_column(String(80))
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime())
    channel: Mapped[NotificationChannel] = mapped_column(
        enum_type(NotificationChannel, "notification_channel"), default=NotificationChannel.INTERNAL
    )
    status: Mapped[NotificationStatus] = mapped_column(
        enum_type(NotificationStatus, "notification_status"), default=NotificationStatus.PENDING
    )
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    managed: Mapped[bool] = mapped_column(default=False, server_default="0")
    dry_run: Mapped[bool] = mapped_column(default=True, server_default="1")
    available_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    event_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    schedule_revision: Mapped[int] = mapped_column(default=1, server_default="1")
    schedule_context: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    attempt_count: Mapped[int] = mapped_column(default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(default=3, server_default="3")
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    claim_token_hash: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    candidate: Mapped[Candidate] = relationship(
        back_populates="notifications", foreign_keys=[candidate_id]
    )
    placement: Mapped[Placement | None] = relationship(
        back_populates="notifications", foreign_keys=[placement_id]
    )
    placement_stage: Mapped[PlacementStage | None] = relationship(
        back_populates="notifications", foreign_keys=[placement_stage_id]
    )
    attempts: Mapped[list[NotificationAttempt]] = relationship(
        back_populates="notification",
        order_by="NotificationAttempt.attempt_number",
        passive_deletes="all",
        lazy="selectin",
    )


class NotificationAttempt(IdentityTimestampMixin, Base):
    __tablename__ = "notification_attempts"
    __table_args__ = (
        UniqueConstraint("notification_id", "attempt_number"),
        CheckConstraint("attempt_number > 0", name="positive_attempt"),
        CheckConstraint("finished_at IS NULL OR finished_at >= attempted_at", name="attempt_range"),
        CheckConstraint(
            "(status = 'processing' AND finished_at IS NULL) OR "
            "(status != 'processing' AND finished_at IS NOT NULL)",
            name="attempt_finish",
        ),
        CheckConstraint(
            "(status IN ('succeeded','simulated','processing') AND error_code IS NULL) OR "
            "(status IN ('failed','abandoned') AND error_code IS NOT NULL)",
            name="error_status",
        ),
    )

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="RESTRICT"), index=True
    )
    attempt_number: Mapped[int]
    status: Mapped[AttemptStatus] = mapped_column(enum_type(AttemptStatus, "attempt_status"))
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider_reference: Mapped[str | None] = mapped_column(String(120))
    claim_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    notification: Mapped[Notification] = relationship(back_populates="attempts")
