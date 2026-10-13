"""Worker contracts expose a one-time claim token without storing it in plaintext."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from minori.domain.reminders import DeliveryErrorCode
from minori.schemas.common import InputSchema
from minori.schemas.notification import NotificationRead


class ClaimRequest(InputSchema):
    notification_id: UUID | None = None


class MessageRead(InputSchema):
    subject: str
    body: str


class ClaimRead(InputSchema):
    notification: NotificationRead
    claim_token: str
    message: MessageRead


class CompletionRequest(InputSchema):
    claim_token: str = Field(min_length=32, max_length=128)
    outcome: Literal["simulated", "sent"]
    provider_reference: str | None = Field(
        default=None, min_length=1, max_length=120, pattern="^[A-Za-z0-9_.:-]+$"
    )


class FailureRequest(InputSchema):
    claim_token: str = Field(min_length=32, max_length=128)
    error_code: DeliveryErrorCode


class RecoveryRead(InputSchema):
    recovered_count: int
