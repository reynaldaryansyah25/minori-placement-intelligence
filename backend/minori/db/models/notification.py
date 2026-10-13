"""Notification intents and immutable attempts; no dispatch or reminder logic."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
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
        Index("ix_notifications_status_scheduled_at", "status", "scheduled_at"),
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
        CheckConstraint("finished_at >= attempted_at", name="attempt_range"),
        CheckConstraint(
            "(status = 'succeeded' AND error_code IS NULL) OR "
            "(status = 'failed' AND error_code IS NOT NULL)",
            name="error_status",
        ),
    )

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="RESTRICT"), index=True
    )
    attempt_number: Mapped[int]
    status: Mapped[AttemptStatus] = mapped_column(enum_type(AttemptStatus, "attempt_status"))
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime())
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider_reference: Mapped[str | None] = mapped_column(String(120))
    notification: Mapped[Notification] = relationship(back_populates="attempts")
