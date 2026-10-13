"""Read APIs and authenticated worker contracts for future HTTP automation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime

from minori.api.dependencies import get_reminder_service
from minori.api.routes.placements import Limit, Offset, invoke
from minori.api.security import require_internal_token, require_read_access
from minori.domain.catalogs import NotificationStatus
from minori.schemas.notification import NotificationAttemptRead, NotificationRead
from minori.schemas.reminders import (
    ClaimRead,
    ClaimRequest,
    CompletionRequest,
    FailureRequest,
    RecipientRoutingRead,
    RecoveryRead,
)
from minori.services.reminders import ReminderService

router = APIRouter(prefix="/reminders", tags=["Reminders"])
internal_router = APIRouter(
    prefix="/internal/reminders",
    tags=["Internal reminders"],
    dependencies=[Depends(require_internal_token)],
)
Service = Annotated[ReminderService, Depends(get_reminder_service)]
read_auth = [Depends(require_read_access)]


@router.get("", response_model=list[NotificationRead], dependencies=read_auth)
def reminders(
    service: Service,
    status: NotificationStatus | None = None,
    due_before: AwareDatetime | None = None,
    placement_id: UUID | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        service.list,
        status=status,
        due_before=due_before,
        placement_id=placement_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{notification_id}", response_model=NotificationRead, dependencies=read_auth)
def detail(notification_id: UUID, service: Service):
    return invoke(service.get, notification_id)


@router.get(
    "/{notification_id}/attempts",
    response_model=list[NotificationAttemptRead],
    dependencies=read_auth,
)
def attempts(notification_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    return invoke(service.attempts, notification_id, limit=limit, offset=offset)


@router.get(
    "/{notification_id}/routing",
    response_model=RecipientRoutingRead,
    dependencies=read_auth,
)
def recipient_routing(notification_id: UUID, service: Service):
    return invoke(service.recipient_routing, notification_id)


@internal_router.post("/generate", response_model=list[NotificationRead])
def generate(service: Service):
    return invoke(service.generate)


@internal_router.post("/recover", response_model=RecoveryRead)
def recover(service: Service):
    return invoke(service.recover)


@internal_router.get("/due", response_model=list[NotificationRead])
def due(service: Service, limit: Limit = 100, offset: Offset = 0):
    return invoke(service.due, limit=limit, offset=offset)


@internal_router.post("/claim", response_model=ClaimRead | None)
def claim(request: ClaimRequest, service: Service):
    return invoke(service.claim, request.notification_id)


@internal_router.post("/{notification_id}/complete", response_model=NotificationRead)
def complete(notification_id: UUID, request: CompletionRequest, service: Service):
    return invoke(
        service.complete,
        notification_id,
        request.claim_token,
        simulated=request.outcome == "simulated",
        provider_reference=request.provider_reference,
    )


@internal_router.post("/{notification_id}/fail", response_model=NotificationRead)
def fail(notification_id: UUID, request: FailureRequest, service: Service):
    return invoke(
        service.complete, notification_id, request.claim_token, error_code=request.error_code
    )


@internal_router.post("/simulate", response_model=NotificationRead | None)
def simulate(request: ClaimRequest, service: Service):
    return invoke(service.simulate, request.notification_id)
