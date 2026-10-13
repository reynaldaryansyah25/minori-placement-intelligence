"""HTTP matching transport; calculations and persistence live behind the service."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, OperationalError

from minori.api.dependencies import get_matching_service
from minori.api.security import require_read_access, require_staff_access
from minori.domain.errors import RecordNotFoundError
from minori.schemas.candidate import CandidateCreate
from minori.schemas.matching import (
    EvaluationBatchRead,
    EvaluationRequest,
    MatchingResultRead,
    RankedMatchingRead,
)
from minori.schemas.vacancy import VacancyCreate
from minori.services.matching import MatchingService

router = APIRouter(prefix="/matching", tags=["Matching"])
Service = Annotated[MatchingService, Depends(get_matching_service)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
read_auth = [Depends(require_read_access)]
staff_auth = [Depends(require_staff_access)]


def invoke(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except RecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        raise HTTPException(
            status_code=409, detail="Database conflict; retry the complete request."
        ) from error
    except OperationalError as error:
        raise HTTPException(
            status_code=503, detail="Database is temporarily unavailable."
        ) from error


@router.post("/evaluations", response_model=EvaluationBatchRead, dependencies=staff_auth)
def evaluate(request: EvaluationRequest, service: Service):
    results = invoke(service.evaluate, **request.model_dump())
    return {"evaluated_count": len(results), "results": results}


@router.get("/results", response_model=list[MatchingResultRead], dependencies=read_auth)
def results(
    service: Service,
    candidate_id: UUID | None = None,
    vacancy_id: UUID | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return invoke(
        service.results,
        candidate_id=candidate_id,
        vacancy_id=vacancy_id,
        limit=limit,
        offset=offset,
    )


@router.get("/results/{evaluation_id}", response_model=MatchingResultRead, dependencies=read_auth)
def result(evaluation_id: UUID, service: Service):
    return invoke(service.result, evaluation_id)


@router.get(
    "/vacancies/{vacancy_id}/ranking",
    response_model=list[RankedMatchingRead],
    dependencies=read_auth,
)
def ranking(vacancy_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    return invoke(service.ranking, vacancy_id, limit=limit, offset=offset)


@router.get(
    "/candidates/{candidate_id}/vacancies/{vacancy_id}/explanation",
    response_model=MatchingResultRead,
    dependencies=read_auth,
)
def explanation(candidate_id: UUID, vacancy_id: UUID, service: Service):
    return invoke(service.explain, candidate_id, vacancy_id)


@router.put(
    "/candidates/{candidate_id}", response_model=EvaluationBatchRead, dependencies=staff_auth
)
def replace_candidate(candidate_id: UUID, request: CandidateCreate, service: Service):
    results = invoke(service.replace_candidate, candidate_id, request.to_domain())
    return {"evaluated_count": len(results), "results": results}


@router.put("/vacancies/{vacancy_id}", response_model=EvaluationBatchRead, dependencies=staff_auth)
def replace_vacancy(vacancy_id: UUID, request: VacancyCreate, service: Service):
    results = invoke(service.replace_vacancy, vacancy_id, request.to_domain())
    return {"evaluated_count": len(results), "results": results}
