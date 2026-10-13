"""Vacancy and vacancy draft HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from minori.api.dependencies import get_vacancy_service
from minori.api.routes.placements import Limit, Offset, invoke
from minori.api.security import require_read_access, require_staff_access
from minori.domain.catalogs import DraftStatus, Program, VacancyStatus
from minori.schemas.vacancy import (
    VacancyCreate,
    VacancyDraftCreate,
    VacancyDraftRead,
    VacancyRead,
)
from minori.services.vacancies import VacancyService

router = APIRouter(prefix="/vacancies", tags=["Vacancies"])
Service = Annotated[VacancyService, Depends(get_vacancy_service)]
read_auth = [Depends(require_read_access)]
staff_auth = [Depends(require_staff_access)]


@router.get("", response_model=list[VacancyRead], dependencies=read_auth)
def list_vacancies(
    service: Service,
    query: Annotated[str | None, Query(max_length=80)] = None,
    program: Program | None = None,
    status: VacancyStatus | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        service.list,
        query=query,
        program=program,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/drafts", response_model=list[VacancyDraftRead], dependencies=read_auth)
def list_drafts(
    service: Service,
    status: DraftStatus | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(service.list_drafts, status=status, limit=limit, offset=offset)


@router.get("/drafts/{draft_id}", response_model=VacancyDraftRead, dependencies=read_auth)
def get_draft(draft_id: UUID, service: Service):
    return invoke(service.get_draft, draft_id)


@router.post("/drafts", response_model=VacancyDraftRead, status_code=201, dependencies=staff_auth)
def create_draft(request: VacancyDraftCreate, service: Service):
    return invoke(service.create_draft, request.to_domain())


@router.put("/drafts/{draft_id}", response_model=VacancyDraftRead, dependencies=staff_auth)
def update_draft(draft_id: UUID, request: VacancyDraftCreate, service: Service):
    return invoke(service.update_draft, draft_id, request.to_domain())


@router.post(
    "/drafts/{draft_id}/publish",
    response_model=VacancyRead,
    status_code=201,
    dependencies=staff_auth,
)
def publish_draft(draft_id: UUID, service: Service):
    return invoke(service.publish_draft, draft_id)


@router.get("/{vacancy_id}", response_model=VacancyRead, dependencies=read_auth)
def get_vacancy(vacancy_id: UUID, service: Service):
    return invoke(service.get, vacancy_id)


@router.post("", response_model=VacancyRead, status_code=201, dependencies=staff_auth)
def create_vacancy(request: VacancyCreate, service: Service):
    return invoke(service.create, request.to_domain())


@router.put("/{vacancy_id}", response_model=VacancyRead, dependencies=staff_auth)
def replace_vacancy(vacancy_id: UUID, request: VacancyCreate, service: Service):
    return invoke(service.replace, vacancy_id, request.to_domain())


@router.delete("/{vacancy_id}", response_model=VacancyRead, dependencies=staff_auth)
def close_vacancy(vacancy_id: UUID, service: Service):
    return invoke(service.close, vacancy_id)
