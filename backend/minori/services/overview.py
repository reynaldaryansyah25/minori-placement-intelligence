"""Operational overview and summary use cases across domain boundaries."""

from dataclasses import dataclass
from datetime import UTC, datetime

from minori.domain.catalogs import (
    CandidateStatus,
    NotificationStatus,
    PlacementStatus,
    PlacementStepStatus,
    VacancyStatus,
)
from minori.domain.matching import EligibilityStatus
from minori.domain.repositories import (
    AuditLogRepository,
    CandidateRepository,
    NotificationRepository,
    PlacementRepository,
    PlacementStageRepository,
    VacancyRepository,
)


@dataclass(frozen=True)
class UpcomingActivityItem:
    placement_id: str
    stage_id: str
    code: str
    step_type: str
    status: str
    scheduled_at: datetime | None
    location: str | None


@dataclass(frozen=True)
class OverviewSummary:
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
    upcoming_activities: list[UpcomingActivityItem]
    recent_audits: list[dict]


class OverviewService:
    def __init__(
        self,
        candidates: CandidateRepository,
        vacancies: VacancyRepository,
        placements: PlacementRepository,
        stages: PlacementStageRepository,
        notifications: NotificationRepository,
        evaluations,
        audit_logs: AuditLogRepository,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._candidates = candidates
        self._vacancies = vacancies
        self._placements = placements
        self._stages = stages
        self._notifications = notifications
        self._evaluations = evaluations
        self._audit_logs = audit_logs
        self.clock = clock

    @staticmethod
    def _all(fetch, *args):
        rows = []
        while True:
            page = fetch(*args, limit=100, offset=len(rows))
            rows.extend(page)
            if len(page) < 100:
                return rows

    def get_summary(self) -> OverviewSummary:
        all_candidates = self._all(self._candidates.list)
        total_candidates = len(all_candidates)
        ready_candidates = sum(1 for c in all_candidates if c.status == CandidateStatus.READY)

        all_vacancies = self._all(self._vacancies.list)
        active_vacancies = sum(1 for v in all_vacancies if v.status == VacancyStatus.OPEN)
        vacancies_by_status: dict[str, int] = {}
        vacancies_by_program: dict[str, int] = {}
        for v in all_vacancies:
            vacancies_by_status[v.status.value] = vacancies_by_status.get(v.status.value, 0) + 1
            vacancies_by_program[v.program.value] = vacancies_by_program.get(v.program.value, 0) + 1

        all_placements = self._all(self._placements.list)
        active_placements = sum(
            1
            for p in all_placements
            if p.status in (PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS)
        )
        placements_by_status: dict[str, int] = {}
        for p in all_placements:
            placements_by_status[p.status.value] = placements_by_status.get(p.status.value, 0) + 1

        # Evaluations
        # Repository orders newest evaluations first. Count each pair once, across all pages.
        latest = {}
        for evaluation in self._all(self._evaluations.list):
            latest.setdefault((evaluation.candidate_id, evaluation.vacancy_id), evaluation)
        all_evals = list(latest.values())
        eligible_matches = sum(
            1 for e in all_evals if e.eligibility_status == EligibilityStatus.ELIGIBLE
        )
        needs_review_matches = sum(
            1 for e in all_evals if e.eligibility_status == EligibilityStatus.NEEDS_REVIEW
        )
        not_eligible_matches = sum(
            1 for e in all_evals if e.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
        )

        # Notifications
        # Use pagination or list query
        pending_reminders = 0
        simulated_reminders = 0
        sent_reminders = 0
        failed_reminders = 0
        missed_reminders = 0
        for cand in all_candidates:
            for notif in self._all(self._notifications.list_for_candidate, cand.id):
                if notif.status == NotificationStatus.PENDING:
                    pending_reminders += 1
                elif notif.status.value == "simulated":
                    simulated_reminders += 1
                elif notif.status == NotificationStatus.SENT:
                    sent_reminders += 1
                elif notif.status == NotificationStatus.FAILED:
                    failed_reminders += 1
                elif notif.status == NotificationStatus.MISSED:
                    missed_reminders += 1

        # Upcoming activities: scheduled stages with scheduled_at in future
        now = self.clock()
        upcoming: list[UpcomingActivityItem] = []
        all_stages = self._all(self._stages.list)
        for stage in all_stages:
            if (
                stage.status == PlacementStepStatus.SCHEDULED
                and stage.scheduled_at is not None
                and stage.scheduled_at >= now
            ):
                upcoming.append(
                    UpcomingActivityItem(
                        placement_id=str(stage.placement_id),
                        stage_id=str(stage.id),
                        code=stage.code,
                        step_type=stage.step_type.value,
                        status=stage.status.value,
                        scheduled_at=stage.scheduled_at,
                        location=stage.location,
                    )
                )
        upcoming.sort(key=lambda item: item.scheduled_at or now)

        # Recent audits
        recent_audits = [
            {
                "reference": a.reference,
                "actor_reference": a.actor_reference,
                "action": a.action,
                "entity_type": a.entity_type.value,
                "entity_id": str(a.entity_id),
                "occurred_at": a.occurred_at.isoformat(),
            }
            for a in self._audit_logs.list(limit=10)
        ]

        return OverviewSummary(
            total_candidates=total_candidates,
            ready_candidates=ready_candidates,
            active_vacancies=active_vacancies,
            active_placements=active_placements,
            eligible_matches=eligible_matches,
            needs_review_matches=needs_review_matches,
            not_eligible_matches=not_eligible_matches,
            pending_reminders=pending_reminders,
            simulated_reminders=simulated_reminders,
            sent_reminders=sent_reminders,
            failed_reminders=failed_reminders,
            missed_reminders=missed_reminders,
            vacancies_by_status=vacancies_by_status,
            vacancies_by_program=vacancies_by_program,
            placements_by_status=placements_by_status,
            upcoming_activities=upcoming[:10],
            recent_audits=recent_audits,
        )
