"""Placement ownership and administrative interview/medical scheduling."""

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
from minori.domain.catalogs import PlacementStatus, PlacementStepStatus, PlacementStepType

if TYPE_CHECKING:
    from minori.db.models.candidate import Candidate
    from minori.db.models.match import Match
    from minori.db.models.notification import Notification
    from minori.db.models.vacancy import Vacancy


class Placement(ReferenceMixin, IdentityTimestampMixin, Base):
    __tablename__ = "placements"
    __table_args__ = (
        UniqueConstraint("candidate_id", "vacancy_id"),
        UniqueConstraint("id", "candidate_id"),
        ForeignKeyConstraint(
            ["match_id", "candidate_id", "vacancy_id"],
            ["matches.id", "matches.candidate_id", "matches.vacancy_id"],
            name="fk_placements_match_pair",
            ondelete="RESTRICT",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"), index=True
    )
    vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True
    )
    match_id: Mapped[UUID | None] = mapped_column(index=True)
    status: Mapped[PlacementStatus] = mapped_column(
        enum_type(PlacementStatus, "placement_status"),
        default=PlacementStatus.PREPARING,
        index=True,
    )
    planned_departure_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    actual_departure_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    candidate: Mapped[Candidate] = relationship(back_populates="placements")
    vacancy: Mapped[Vacancy] = relationship(back_populates="placements")
    match: Mapped[Match | None] = relationship(back_populates="placements", foreign_keys=[match_id])
    steps: Mapped[list[PlacementStage]] = relationship(
        back_populates="placement",
        order_by="PlacementStage.sequence_number",
        passive_deletes="all",
        lazy="selectin",
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="placement", foreign_keys="Notification.placement_id", passive_deletes="all"
    )


class PlacementStage(IdentityTimestampMixin, Base):
    __tablename__ = "placement_stages"
    __table_args__ = (
        UniqueConstraint("placement_id", "code", name="uq_placement_stages_code"),
        UniqueConstraint("placement_id", "sequence_number", name="uq_placement_stages_sequence"),
        UniqueConstraint("id", "placement_id", name="uq_placement_stages_owner"),
        CheckConstraint("sequence_number > 0", name="positive_sequence"),
        CheckConstraint("schedule_revision > 0", name="positive_schedule_revision"),
        CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
        CheckConstraint(
            "due_at IS NULL OR (scheduled_at IS NOT NULL AND due_at >= scheduled_at)",
            name="schedule_range",
        ),
        CheckConstraint(
            "status NOT IN ('scheduled','in_progress') OR scheduled_at IS NOT NULL",
            name="scheduled_status",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="completion_timestamp",
        ),
        CheckConstraint(
            "completed_at IS NULL OR scheduled_at IS NULL OR completed_at >= scheduled_at",
            name="completion_range",
        ),
        Index("ix_placement_stages_status_scheduled_at", "status", "scheduled_at"),
    )

    placement_id: Mapped[UUID] = mapped_column(
        ForeignKey("placements.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    step_type: Mapped[PlacementStepType] = mapped_column(enum_type(PlacementStepType, "step_type"))
    sequence_number: Mapped[int]
    schedule_revision: Mapped[int] = mapped_column(default=1, server_default="1")
    status: Mapped[PlacementStepStatus] = mapped_column(
        enum_type(PlacementStepStatus, "step_status"), default=PlacementStepStatus.PENDING
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    location: Mapped[str | None] = mapped_column(String(160))
    placement: Mapped[Placement] = relationship(back_populates="steps")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="placement_stage",
        foreign_keys="Notification.placement_stage_id",
        passive_deletes="all",
    )
