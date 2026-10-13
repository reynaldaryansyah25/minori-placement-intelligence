"""Concrete notification repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import Notification, NotificationAttempt
from minori.domain.entities import (
    NotificationAttemptData,
    NotificationAttemptRecord,
    NotificationData,
    NotificationRecord,
)
from minori.repositories.mapping import pagination, preserve_identity, require_row, to_record
from minori.schemas.notification import NotificationAttemptCreate, NotificationCreate


class SqlAlchemyNotificationRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: NotificationData) -> NotificationRecord:
        values = NotificationCreate.model_validate(asdict(data)).model_dump()
        row = Notification(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, NotificationRecord)

    def get(self, identifier: UUID) -> NotificationRecord | None:
        row = self._session.get(Notification, identifier)
        return None if row is None else to_record(row, NotificationRecord)

    def get_by_deduplication_key(self, deduplication_key: str) -> NotificationRecord | None:
        row = self._session.scalar(
            select(Notification).where(Notification.deduplication_key == deduplication_key)
        )
        return None if row is None else to_record(row, NotificationRecord)

    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[NotificationRecord]:
        pagination(limit, offset)
        query = select(Notification)
        query = query.where(Notification.candidate_id == candidate_id)
        rows = self._session.scalars(
            query.order_by(Notification.created_at, Notification.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, NotificationRecord) for row in rows]

    def replace(self, identifier: UUID, data: NotificationData) -> NotificationRecord:
        row = require_row(self._session.get(Notification, identifier), identifier)
        values = NotificationCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(
            row,
            values,
            (
                "reference",
                "deduplication_key",
                "candidate_id",
                "placement_id",
                "placement_stage_id",
            ),
        )
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, NotificationRecord)


class SqlAlchemyNotificationAttemptRepository:
    """Append-only history; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, data: NotificationAttemptData) -> NotificationAttemptRecord:
        values = NotificationAttemptCreate.model_validate(asdict(data)).model_dump()
        row = NotificationAttempt(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, NotificationAttemptRecord)

    def get(self, identifier: UUID) -> NotificationAttemptRecord | None:
        row = self._session.get(NotificationAttempt, identifier)
        return None if row is None else to_record(row, NotificationAttemptRecord)

    def get_by_number(
        self, notification_id: UUID, attempt_number: int
    ) -> NotificationAttemptRecord | None:
        row = self._session.scalar(
            select(NotificationAttempt).where(
                NotificationAttempt.notification_id == notification_id,
                NotificationAttempt.attempt_number == attempt_number,
            )
        )
        return None if row is None else to_record(row, NotificationAttemptRecord)

    def list_for_notification(
        self, notification_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[NotificationAttemptRecord]:
        pagination(limit, offset)
        query = select(NotificationAttempt)
        query = query.where(NotificationAttempt.notification_id == notification_id)
        rows = self._session.scalars(
            query.order_by(NotificationAttempt.attempt_number, NotificationAttempt.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [to_record(row, NotificationAttemptRecord) for row in rows]
