"""Bounded audit context instead of arbitrary entity or provider payloads."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from minori.domain.catalogs import AuditEntityType
from minori.domain.entities import AuditLogData
from minori.schemas.common import Code, InputSchema, RecordFields, Reference


class AuditContext(InputSchema):
    synthetic: bool = False
    fixture: Code | None = None
    reason_code: Code | None = None
    previous_status: Code | None = None
    new_status: Code | None = None
    schedule_revision: int | None = None
    previous_scheduled_at: str | None = None
    scheduled_at: str | None = None
    previous_due_at: str | None = None
    due_at: str | None = None
    previous_planned_departure_at: str | None = None
    planned_departure_at: str | None = None
    attempt_number: int | None = None
    facts_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    delivery_mode: Literal["dry_run", "mailpit", "demo_recipient"] | None = None


class AuditLogCreate(InputSchema):
    reference: Reference
    actor_reference: Code
    action: Code
    entity_type: AuditEntityType
    entity_id: UUID
    occurred_at: AwareDatetime
    context: AuditContext

    def to_domain(self, data_type=AuditLogData) -> AuditLogData:
        values = self.model_dump()
        values["context"] = self.context.model_dump(exclude_none=True)
        return data_type(**values)


class AuditLogRead(AuditLogCreate, RecordFields):
    """Audit resource links are logical references retained independently of rows."""
