"""Authenticated AI operations, document parsing and explicit email approval."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import AwareDatetime
from starlette.concurrency import run_in_threadpool

from minori.api.dependencies import (
    get_ai_gateway,
    get_ai_service,
    get_app_settings,
    get_reminder_service,
)
from minori.api.routes.placements import invoke
from minori.api.security import (
    AuthSession,
    require_internal_token,
    require_read_access,
    require_staff_access,
)
from minori.core.config import Settings
from minori.domain.ai import AiUnavailableError
from minori.integrations.documents import MAX_FILE_BYTES, DocumentError, parse_document
from minori.integrations.nine_router.structured import ValidatedAiGateway
from minori.schemas.ai import (
    BatchRequest,
    DocumentPreview,
    EmailApproval,
    EmailPreview,
    MatchingAiRead,
    MatchingAiRequest,
    TextRequest,
    VacancyAnalysis,
)
from minori.schemas.common import InputSchema
from minori.schemas.notification import NotificationRead
from minori.services.ai import AiService
from minori.services.reminders import ReminderService

router = APIRouter(tags=["AI operations"])
Staff = Annotated[AuthSession, Depends(require_staff_access)]
Ai = Annotated[AiService, Depends(get_ai_service)]
Reminder = Annotated[ReminderService, Depends(get_reminder_service)]
Gateway = Annotated[ValidatedAiGateway, Depends(get_ai_gateway)]


class DemoClockAdvance(InputSchema):
    now: AwareDatetime


@router.post("/internal/demo/clock", dependencies=[Depends(require_internal_token)])
def advance_clock(payload: DemoClockAdvance, request: Request):
    settings = request.app.state.settings
    if settings.app_env not in {"demo", "test"}:
        raise HTTPException(
            status_code=404, detail="Clock control is unavailable in this environment"
        )
    current = settings.demo_clock_at or datetime.now(UTC)
    if payload.now < current or payload.now > current + timedelta(days=7):
        raise HTTPException(
            status_code=422,
            detail="Demo clock can advance by at most seven days; cannot move backwards",
        )
    settings.demo_clock_at = payload.now
    return {"now": payload.now, "controlled": True}


def ai_invoke(operation, *args, **kwargs):
    try:
        return invoke(operation, *args, **kwargs)
    except AiUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/ai/status", dependencies=[Depends(require_read_access)])
def status(settings: Annotated[Settings, Depends(get_app_settings)]):
    # Configuration is not a claim of a successful model invocation.
    return {
        "enabled": settings.llm_enabled,
        "configured": bool(
            settings.llm_enabled and settings.nine_router_api_key and settings.nine_router_model
        ),
        "features": [
            "vacancy_analysis",
            "translation_review",
            "matching_explanation",
            "email_draft",
        ],
    }


@router.post("/ai/documents/preview", response_model=DocumentPreview)
async def preview(staff: Staff, file: Annotated[UploadFile, File()]):
    try:
        data = await file.read(MAX_FILE_BYTES + 1)
        return await run_in_threadpool(parse_document, file.filename or "", data)
    except DocumentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        await file.close()


@router.post("/ai/vacancies/analyze", response_model=VacancyAnalysis)
def analyze(request: TextRequest, service: Ai, staff: Staff):
    return ai_invoke(service.analyze, request.text)


@router.post("/ai/vacancies/batch", response_model=list[VacancyAnalysis])
def batch(request: BatchRequest, service: Ai, staff: Staff):
    # No writes until every selected source has a valid result; at most five calls.
    return [ai_invoke(service.analyze, text) for text in request.texts]


@router.post("/ai/matching/explanation", response_model=MatchingAiRead)
def explain(request: MatchingAiRequest, service: Ai, staff: Staff):
    return ai_invoke(service.explain, request.candidate_id, request.vacancy_id)


@router.get("/reminders/{notification_id}/email/template", response_model=EmailPreview)
def email_template(notification_id: UUID, service: Reminder, staff: Staff):
    return invoke(service.draft_email, notification_id)


@router.post(
    "/placements/{placement_id}/activities/{activity_id}/email/prepare",
    response_model=NotificationRead,
)
def prepare_activity_email(placement_id: UUID, activity_id: UUID, service: Reminder, staff: Staff):
    return invoke(service.prepare_activity_email, placement_id, activity_id)


@router.post("/reminders/{notification_id}/email/draft", response_model=EmailPreview)
def email_draft(notification_id: UUID, service: Reminder, gateway: Gateway, staff: Staff):
    return ai_invoke(service.draft_email, notification_id, gateway)


@router.post("/reminders/{notification_id}/email/approve", response_model=NotificationRead)
def approve(notification_id: UUID, request: EmailApproval, service: Reminder, staff: Staff):
    return invoke(
        service.approve_email,
        notification_id,
        request.subject,
        request.body,
        request.facts_fingerprint,
        request.idempotency_key,
        staff.actor_reference,
    )
