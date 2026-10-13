"""Candidate management HTTP routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from minori.api.dependencies import get_candidate_service
from minori.api.routes.placements import Limit, Offset, invoke
from minori.api.security import require_read_access, require_staff_access
from minori.domain.catalogs import CandidateStatus, Program
from minori.schemas.candidate import CandidateCreate, CandidateRead
from minori.services.candidates import CandidateService

router = APIRouter(prefix="/candidates", tags=["Candidates"])
Service = Annotated[CandidateService, Depends(get_candidate_service)]
read_auth = [Depends(require_read_access)]
staff_auth = [Depends(require_staff_access)]


@router.get("", response_model=list[CandidateRead], dependencies=read_auth)
def list_candidates(
    service: Service,
    query: Annotated[str | None, Query(max_length=80)] = None,
    preferred_program: Program | None = None,
    status: CandidateStatus | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        service.list,
        query=query,
        preferred_program=preferred_program,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{candidate_id}", response_model=CandidateRead, dependencies=read_auth)
def get_candidate(candidate_id: UUID, service: Service):
    return invoke(service.get, candidate_id)


@router.post("", response_model=CandidateRead, status_code=201, dependencies=staff_auth)
def create_candidate(request: CandidateCreate, service: Service):
    return invoke(service.create, request.to_domain())


@router.put("/{candidate_id}", response_model=CandidateRead, dependencies=staff_auth)
def replace_candidate(candidate_id: UUID, request: CandidateCreate, service: Service):
    return invoke(service.replace, candidate_id, request.to_domain())


@router.delete("/{candidate_id}", response_model=CandidateRead, dependencies=staff_auth)
def archive_candidate(candidate_id: UUID, service: Service):
    return invoke(service.archive, candidate_id)
