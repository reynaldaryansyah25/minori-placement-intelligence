"""Conditional queue claims and attempt lifecycle inside immediate transactions."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from minori.db.models import Candidate, Notification, NotificationAttempt, Placement, PlacementStage
from minori.domain.catalogs import (
    AttemptStatus,
    CandidateStatus,
    NotificationStatus,
    PlacementStatus,
    PlacementStepStatus,
)
from minori.domain.entities import NotificationAttemptRecord, NotificationRecord
from minori.domain.errors import BusinessConflictError
from minori.domain.notification_templates import MANUAL_ACTIVITY_TEMPLATES
from minori.repositories.mapping import pagination, require_row, to_record


class SqlAlchemyNotificationQueue:
    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _approved_for_delivery():
        return Notification.template_code.not_in(
            list(MANUAL_ACTIVITY_TEMPLATES.values())
        ) | Notification.approved_at.is_not(None)

    def list(
        self,
        *,
        status=None,
        due_before=None,
        placement_id=None,
        active_only=False,
        limit=100,
        offset=0,
    ):
        pagination(limit, offset)
        query = select(Notification)
        if active_only:
            query = query.where(
                Notification.managed.is_(True),
                Notification.status.in_(
                    [NotificationStatus.PENDING, NotificationStatus.PROCESSING]
                ),
            )
        if status is not None:
            query = query.where(Notification.status == status)
        if due_before is not None:
            query = query.where(
                self._approved_for_delivery(),
                Notification.managed.is_(True),
                Notification.status == NotificationStatus.PENDING,
                Notification.available_at <= due_before,
                Notification.event_at > due_before,
            )
        if placement_id is not None:
            query = query.where(Notification.placement_id == placement_id)
        rows = self._session.scalars(
            query.order_by(Notification.scheduled_at, Notification.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, NotificationRecord) for row in rows]

    def for_activity(self, identifier):
        rows = self._session.scalars(
            select(Notification)
            .where(Notification.placement_stage_id == identifier, Notification.managed.is_(True))
            .order_by(Notification.created_at, Notification.id)
        ).all()
        return [to_record(row, NotificationRecord) for row in rows]

    def claim(self, identifier, now, token_hash, lease_expires_at, *, dry_run_only=False):
        live_activity = (
            select(PlacementStage.id)
            .join(Placement)
            .join(Candidate, Candidate.id == Placement.candidate_id)
            .where(
                Placement.status.in_([PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS]),
                Candidate.status != CandidateStatus.INACTIVE,
                PlacementStage.status.in_(
                    [PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS]
                ),
            )
        )
        query = select(Notification.id).where(
            self._approved_for_delivery(),
            Notification.managed.is_(True),
            Notification.status == NotificationStatus.PENDING,
            Notification.available_at <= now,
            Notification.event_at > now,
            Notification.attempt_count < Notification.max_attempts,
            (
                Notification.placement_stage_id.in_(live_activity)
                | Notification.template_code.in_(["schedule_changed", "schedule_cancelled"])
            ),
        )
        if identifier is not None:
            query = query.where(Notification.id == identifier)
        if dry_run_only:
            query = query.where(Notification.dry_run.is_(True))
        selected = self._session.scalar(
            query.order_by(Notification.available_at, Notification.id).limit(1)
        )
        if selected is None:
            return None
        changed = self._session.execute(
            update(Notification)
            .where(
                Notification.id == selected,
                self._approved_for_delivery(),
                Notification.status == NotificationStatus.PENDING,
                Notification.available_at <= now,
                Notification.event_at > now,
                Notification.attempt_count < Notification.max_attempts,
            )
            .values(
                status=NotificationStatus.PROCESSING,
                claimed_at=now,
                lease_expires_at=lease_expires_at,
                claim_token_hash=token_hash,
                attempt_count=Notification.attempt_count + 1,
                processed_at=None,
                last_error_code=None,
            )
        )
        if changed.rowcount != 1:
            return None
        self._session.flush()
        return to_record(
            self._session.get(Notification, selected, populate_existing=True), NotificationRecord
        )

    def finish_attempt(
        self,
        notification_id,
        attempt_number,
        *,
        status,
        finished_at,
        error_code=None,
        provider_reference=None,
    ):
        row = require_row(
            self._session.scalar(
                select(NotificationAttempt).where(
                    NotificationAttempt.notification_id == notification_id,
                    NotificationAttempt.attempt_number == attempt_number,
                )
            ),
            notification_id,
        )
        if row.status != AttemptStatus.PROCESSING:
            raise BusinessConflictError("Attempt has already been finalized")
        row.status = status
        row.finished_at = finished_at
        row.error_code = error_code
        row.provider_reference = provider_reference
        self._session.flush()

    def last_attempt(self, identifier):
        row = self._session.scalar(
            select(NotificationAttempt)
            .where(NotificationAttempt.notification_id == identifier)
            .order_by(NotificationAttempt.attempt_number.desc())
            .limit(1)
        )
        return None if row is None else to_record(row, NotificationAttemptRecord)
