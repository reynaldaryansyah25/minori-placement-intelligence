"""Minimal append-only audit records without entity snapshots or sensitive payloads."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, ReferenceMixin, UTCDateTime, enum_type
from minori.domain.catalogs import AuditEntityType


class AuditLog(ReferenceMixin, IdentityTimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_time", "entity_type", "entity_id", "occurred_at"),
    )

    actor_reference: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[AuditEntityType] = mapped_column(
        enum_type(AuditEntityType, "audit_entity_type")
    )
    entity_id: Mapped[UUID] = mapped_column(Uuid(native_uuid=False))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    context: Mapped[dict[str, str | bool | int]] = mapped_column(JSON, default=dict)
