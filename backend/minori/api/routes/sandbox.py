"""Private session bootstrap and controls; never mounted on the primary backend."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from minori.api.dependencies import get_reminder_service
from minori.api.routes.placements import invoke as business_invoke
from minori.integrations.demo_sandbox import SandboxDenied
from minori.schemas.reminders import ClaimRequest
from minori.services.reminders import ReminderService

router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


def invoke(operation, *args):
    try:
        return operation(*args)
    except SandboxDenied as error:
        raise HTTPException(error.status, error.message) from None


@router.post("/sessions")
def create_session(request: Request):
    expected = "Bearer " + request.app.state.settings.sandbox_gateway_token.get_secret_value()
    if not secrets.compare_digest(
        request.headers.get("Authorization", "").encode(), expected.encode()
    ):
        raise HTTPException(401, "Akses demo tidak dapat diverifikasi.")
    token, row = invoke(request.app.state.sandbox.create)
    return {"session_token": token, **request.app.state.sandbox.usage(row)}


@router.get("/session")
def status(request: Request):
    return request.app.state.sandbox.usage(request.state.sandbox_session)


class ResetRequest(BaseModel):
    confirmed: bool


@router.post("/reset")
def reset(payload: ResetRequest, request: Request):
    if not payload.confirmed:
        raise HTTPException(422, "Konfirmasikan reset data sesi Anda.")
    return invoke(request.app.state.sandbox.reset, request.state.sandbox_session)


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.app.state.sandbox.revoke(request.state.sandbox_session)


@router.get("/worker/sessions")
def worker_sessions(request: Request):
    manager = request.app.state.sandbox
    with manager.lock:
        return {"sessions": [r.identifier for r in manager.sessions.values() if manager._alive(r)]}


Reminder = Annotated[ReminderService, Depends(get_reminder_service)]


@router.post("/reminders/generate")
def generate(service: Reminder):
    return business_invoke(service.generate)


@router.post("/reminders/recover")
def recover(service: Reminder):
    return business_invoke(service.recover)


@router.post("/reminders/simulate")
def simulate(payload: ClaimRequest, service: Reminder):
    return business_invoke(service.simulate, payload.notification_id)
