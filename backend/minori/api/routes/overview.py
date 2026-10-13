"""Operational overview and analytics summary routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from minori.api.dependencies import get_overview_service
from minori.api.routes.placements import invoke
from minori.api.security import require_read_access
from minori.schemas.overview import OverviewSummaryRead
from minori.services.overview import OverviewService

router = APIRouter(prefix="/overview", tags=["Overview"])
Service = Annotated[OverviewService, Depends(get_overview_service)]
read_auth = [Depends(require_read_access)]


@router.get("/summary", response_model=OverviewSummaryRead, dependencies=read_auth)
def get_summary(service: Service) -> OverviewSummaryRead:
    summary = invoke(service.get_summary)
    return OverviewSummaryRead(
        total_candidates=summary.total_candidates,
        ready_candidates=summary.ready_candidates,
        active_vacancies=summary.active_vacancies,
        active_placements=summary.active_placements,
        eligible_matches=summary.eligible_matches,
        needs_review_matches=summary.needs_review_matches,
        not_eligible_matches=summary.not_eligible_matches,
        pending_reminders=summary.pending_reminders,
        simulated_reminders=summary.simulated_reminders,
        sent_reminders=summary.sent_reminders,
        failed_reminders=summary.failed_reminders,
        missed_reminders=summary.missed_reminders,
        vacancies_by_status=summary.vacancies_by_status,
        vacancies_by_program=summary.vacancies_by_program,
        placements_by_status=summary.placements_by_status,
        upcoming_activities=[
            {
                "placement_id": item.placement_id,
                "stage_id": item.stage_id,
                "code": item.code,
                "step_type": item.step_type,
                "status": item.status,
                "scheduled_at": item.scheduled_at,
                "location": item.location,
            }
            for item in summary.upcoming_activities
        ],
        recent_audits=summary.recent_audits,
    )
