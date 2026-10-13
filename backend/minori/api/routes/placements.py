"""Placement and administrative activity HTTP transport."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, OperationalError

from minori.api.dependencies import get_placement_service, get_repositories
from minori.api.security import require_internal_token
from minori.domain.catalogs import (
    AuditEntityType,
    MatchStatus,
    PlacementStatus,
    PlacementStepStatus,
)
from minori.domain.entities import PlacementStageData
from minori.domain.errors import BusinessConflictError, RecordNotFoundError
from minori.repositories.provider import Repositories
from minori.schemas.audit import AuditLogRead
from minori.schemas.match import MatchRead
from minori.schemas.placement import PlacementRead, PlacementStageRead
from minori.schemas.placement_management import (
    ActivityRequest,
    ActivityUpdate,
    ActorRequest,
    PlacementRequest,
    PlacementUpdate,
    StaffDecision,
)
from minori.services.placements import PlacementService

router = APIRouter(tags=["Placements"])
Service = Annotated[PlacementService, Depends(get_placement_service)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
authenticated = [Depends(require_internal_token)]


def invoke(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BusinessConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=409, detail="Database conflict; retry the complete request"
        ) from error
    except OperationalError as error:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from error


@router.post("/matching/decisions", response_model=MatchRead, dependencies=authenticated)
def decide(request: StaffDecision, service: Service):
    return invoke(
        service.decide,
        request.candidate_id,
        request.vacancy_id,
        MatchStatus(request.decision),
        request.actor_reference,
        request.reason_code,
    )


@router.post("/placements", response_model=PlacementRead, dependencies=authenticated)
def create(request: PlacementRequest, service: Service):
    return invoke(
        service.create,
        request.reference,
        request.match_id,
        request.actor_reference,
        request.planned_departure_at,
    )


@router.get("/placements", response_model=list[PlacementRead])
def search(
    service: Service,
    query: Annotated[str | None, Query(max_length=80)] = None,
    status: PlacementStatus | None = None,
    candidate_id: UUID | None = None,
    vacancy_id: UUID | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        service.list,
        query=query,
        status=status,
        candidate_id=candidate_id,
        vacancy_id=vacancy_id,
        limit=limit,
        offset=offset,
    )


@router.get("/placements/{placement_id}", response_model=PlacementRead)
def get(placement_id: UUID, service: Service):
    return invoke(service.get, placement_id)


@router.patch(
    "/placements/{placement_id}", response_model=PlacementRead, dependencies=authenticated
)
def update(placement_id: UUID, request: PlacementUpdate, service: Service):
    values = request.model_dump(exclude_unset=True, exclude={"actor_reference"})
    return invoke(
        service.update,
        placement_id,
        request.actor_reference,
        fields_set=frozenset(values),
        **values,
    )


@router.delete(
    "/placements/{placement_id}", response_model=PlacementRead, dependencies=authenticated
)
def cancel(placement_id: UUID, request: ActorRequest, service: Service):
    return invoke(
        service.update, placement_id, request.actor_reference, status=PlacementStatus.CANCELLED
    )


@router.get("/placements/{placement_id}/activities", response_model=list[PlacementStageRead])
def activities(placement_id: UUID, service: Service):
    return invoke(service.activities, placement_id)


@router.post(
    "/placements/{placement_id}/activities",
    response_model=PlacementStageRead,
    dependencies=authenticated,
)
def create_activity(placement_id: UUID, request: ActivityRequest, service: Service):
    data = PlacementStageData(
        placement_id=placement_id,
        **request.model_dump(exclude={"actor_reference"}),
        status=PlacementStepStatus.SCHEDULED
        if request.scheduled_at
        else PlacementStepStatus.PENDING,
    )
    return invoke(service.create_activity, placement_id, data, request.actor_reference)


@router.patch(
    "/placements/{placement_id}/activities/{activity_id}",
    response_model=PlacementStageRead,
    dependencies=authenticated,
)
def update_activity(
    placement_id: UUID, activity_id: UUID, request: ActivityUpdate, service: Service
):
    return invoke(
        service.update_activity,
        placement_id,
        activity_id,
        request.actor_reference,
        **request.model_dump(exclude_unset=True, exclude={"actor_reference"}),
    )


@router.get("/audit-logs", response_model=list[AuditLogRead])
def audit(
    repositories: Annotated[Repositories, Depends(get_repositories)],
    entity_type: AuditEntityType | None = None,
    entity_id: UUID | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        repositories.audit_log.list,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
