"""Concrete audit repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import AuditLog
from minori.domain.catalogs import AuditEntityType
from minori.domain.entities import (
    AuditLogData,
    AuditLogRecord,
)
from minori.repositories.mapping import pagination, to_record
from minori.schemas.audit import AuditLogCreate


class SqlAlchemyAuditLogRepository:
    """Append-only history; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, data: AuditLogData) -> AuditLogRecord:
        values = asdict(AuditLogCreate.model_validate(asdict(data)).to_domain())
        row = AuditLog(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, AuditLogRecord)

    def get(self, identifier: UUID) -> AuditLogRecord | None:
        row = self._session.get(AuditLog, identifier)
        return None if row is None else to_record(row, AuditLogRecord)

    def get_by_reference(self, reference: str) -> AuditLogRecord | None:
        row = self._session.scalar(select(AuditLog).where(AuditLog.reference == reference))
        return None if row is None else to_record(row, AuditLogRecord)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        entity_type: AuditEntityType | None = None,
        entity_id: UUID | None = None,
    ) -> list[AuditLogRecord]:
        pagination(limit, offset)
        query = select(AuditLog)
        if entity_type is not None:
            query = query.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.where(AuditLog.entity_id == entity_id)
        rows = self._session.scalars(
            query.order_by(AuditLog.created_at, AuditLog.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, AuditLogRecord) for row in rows]
