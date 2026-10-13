"""Overview schema for operational KPI dashboard."""

from datetime import datetime

from pydantic import BaseModel


class UpcomingActivityRead(BaseModel):
    placement_id: str
    stage_id: str
    code: str
    step_type: str
    status: str
    scheduled_at: datetime | None
    location: str | None


class OverviewSummaryRead(BaseModel):
    total_candidates: int
    ready_candidates: int
    active_vacancies: int
    active_placements: int
    eligible_matches: int
    needs_review_matches: int
    not_eligible_matches: int
    pending_reminders: int
    simulated_reminders: int
    sent_reminders: int
    failed_reminders: int
    missed_reminders: int
    vacancies_by_status: dict[str, int]
    vacancies_by_program: dict[str, int]
    placements_by_status: dict[str, int]
    upcoming_activities: list[UpcomingActivityRead]
    recent_audits: list[dict]
