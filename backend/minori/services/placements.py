"""Human decisions, capacity-checked placements, and administrative activity lifecycle."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from minori.domain.catalogs import (
    AuditEntityType,
    CandidateStatus,
    MatchSource,
    MatchStatus,
    PlacementStatus,
    PlacementStepStatus,
)
from minori.domain.entities import AuditLogData, MatchData, PlacementData, PlacementStageData
from minori.domain.errors import BusinessConflictError, RecordNotFoundError
from minori.domain.matching import EligibilityStatus
from minori.domain.matching_engine import MatchingEngine
from minori.domain.operations import OperationsPorts, ReminderCoordinator, record_data
from minori.domain.reminders import ACTIVITY_TRANSITIONS, PLACEMENT_TRANSITIONS, validate_transition


def utc_now():
    return datetime.now(UTC)


class PlacementService:
    def __init__(
        self, ports: OperationsPorts, transaction, reminders: ReminderCoordinator, clock=utc_now
    ):
        self.ports = ports
        self.transaction = transaction
        self.reminders = reminders
        self.clock = clock

    @staticmethod
    def _require(row, name):
        if row is None:
            raise RecordNotFoundError(f"{name} was not found")
        return row

    def _audit(self, row, action, actor, entity_type, now, **context):
        self.ports.audit_log.append(
            AuditLogData(
                reference="AUD-" + uuid4().hex.upper(),
                actor_reference=actor,
                action=action,
                entity_type=entity_type,
                entity_id=row.id,
                occurred_at=now,
                context=context,
            )
        )

    def get(self, identifier):
        return self._require(self.ports.placement.get(identifier), "Placement")

    def list(self, **filters):
        return self.ports.placement.list(**filters)

    def approved_candidates(self, *, limit=100, offset=0):
        """Explicit staff approvals waiting for a placement, with current business gates."""
        rows = []
        candidate_offset = 0
        now = self.clock()
        while True:
            candidates = self.ports.candidate.list(limit=100, offset=candidate_offset)
            for candidate in candidates:
                match_offset = 0
                while True:
                    matches = self.ports.match.list_for_candidate(
                        candidate.id, limit=100, offset=match_offset
                    )
                    for match in matches:
                        if match.status != MatchStatus.APPROVED or self.ports.placement.get_by_pair(
                            candidate.id, match.vacancy_id
                        ):
                            continue
                        vacancy = self.ports.vacancy.get(match.vacancy_id)
                        eligibility = (
                            MatchingEngine().evaluate(candidate, vacancy, now).eligibility_status
                        )
                        reason = None
                        if eligibility != EligibilityStatus.ELIGIBLE:
                            reason = (
                                "Lengkapi dan verifikasi persyaratan kandidat sebelum penempatan."
                            )
                        elif self.ports.placement.candidate_active(candidate.id):
                            reason = "Kandidat sudah memiliki penempatan aktif."
                        elif self.ports.placement.capacity_used(vacancy.id) >= vacancy.quota:
                            reason = "Kuota lowongan sudah terisi."
                        rows.append(
                            {
                                "match_id": match.id,
                                "candidate_id": candidate.id,
                                "vacancy_id": vacancy.id,
                                "candidate_name": candidate.full_name,
                                "vacancy_title": vacancy.title,
                                "employer_name": vacancy.employer_name,
                                "can_start": reason is None,
                                "reason": reason,
                            }
                        )
                    if len(matches) < 100:
                        break
                    match_offset += len(matches)
            if len(candidates) < 100:
                break
            candidate_offset += len(candidates)
        return sorted(rows, key=lambda item: (item["candidate_name"], item["vacancy_title"]))[
            offset : offset + limit
        ]

    def _activities(self, identifier):
        rows = []
        while True:
            page = self.ports.placement_stage.list_for_placement(
                identifier, limit=100, offset=len(rows)
            )
            rows.extend(page)
            if len(page) < 100:
                return rows

    def activities(self, identifier):
        self.get(identifier)
        return self._activities(identifier)

    def _pair(self, candidate_id, vacancy_id):
        return (
            self._require(self.ports.candidate.get(candidate_id), "Candidate"),
            self._require(self.ports.vacancy.get(vacancy_id), "Vacancy"),
        )

    def decide(self, candidate_id, vacancy_id, decision, actor, reason_code=None):
        now = self.clock()
        with self.transaction():
            candidate, vacancy = self._pair(candidate_id, vacancy_id)
            eligibility = MatchingEngine().evaluate(candidate, vacancy, now).eligibility_status
            if decision == MatchStatus.APPROVED and eligibility == EligibilityStatus.NOT_ELIGIBLE:
                raise BusinessConflictError(
                    "Candidate fails mandatory requirements; approval is blocked"
                )
            placement = self.ports.placement.get_by_pair(candidate_id, vacancy_id)
            if (
                decision == MatchStatus.REJECTED
                and placement
                and placement.status != PlacementStatus.CANCELLED
            ):
                raise BusinessConflictError(
                    "Cancel the existing placement before rejecting its match"
                )
            current = self.ports.match.get_by_pair(candidate_id, vacancy_id)
            if current and current.status == decision:
                return current
            if current:
                row = self.ports.match.replace(
                    current.id,
                    replace(record_data(current, MatchData), status=decision, reviewed_at=now),
                )
            else:
                row = self.ports.match.create(
                    MatchData(
                        candidate_id=candidate_id,
                        vacancy_id=vacancy_id,
                        source=MatchSource.MANUAL,
                        status=decision,
                        reviewed_at=now,
                    )
                )
            self._audit(
                row,
                "match.reviewed",
                actor,
                AuditEntityType.MATCH,
                now,
                previous_status=current.status.value if current else "proposed",
                new_status=decision.value,
                **({"reason_code": reason_code} if reason_code else {}),
            )
            return row

    def create(self, reference, match_id, actor, planned_departure_at=None):
        now = self.clock()
        with self.transaction():
            match = self._require(self.ports.match.get(match_id), "Match")
            if match.status != MatchStatus.APPROVED:
                raise BusinessConflictError("Placement requires explicit staff approval")
            candidate, vacancy = self._pair(match.candidate_id, match.vacancy_id)
            eligibility = MatchingEngine().evaluate(candidate, vacancy, now).eligibility_status
            if eligibility != EligibilityStatus.ELIGIBLE:
                raise BusinessConflictError(
                    "Placement requires current eligible, active candidate and vacancy"
                )
            current = self.ports.placement.get_by_pair(candidate.id, vacancy.id)
            if current:
                if (
                    current.reference == reference
                    and current.match_id == match_id
                    and current.planned_departure_at == planned_departure_at
                    and current.status == PlacementStatus.PREPARING
                ):
                    return current
                raise BusinessConflictError("This candidate-vacancy pair already has a placement")
            if self.ports.placement.candidate_active(candidate.id):
                raise BusinessConflictError("Candidate already has an active placement")
            if self.ports.placement.capacity_used(vacancy.id) >= vacancy.quota:
                raise BusinessConflictError("Vacancy capacity is exhausted")
            row = self.ports.placement.create(
                PlacementData(
                    reference=reference,
                    candidate_id=candidate.id,
                    vacancy_id=vacancy.id,
                    match_id=match.id,
                    planned_departure_at=planned_departure_at,
                )
            )
            self._audit(
                row,
                "placement.created",
                actor,
                AuditEntityType.PLACEMENT,
                now,
                new_status=row.status.value,
            )
            return row

    def update(
        self,
        identifier,
        actor,
        *,
        status=None,
        planned_departure_at=None,
        actual_departure_at=None,
        fields_set=frozenset(),
    ):
        now = self.clock()
        with self.transaction():
            row = self.get(identifier)
            target = status or row.status
            validate_transition(row.status, target, PLACEMENT_TRANSITIONS)
            if row.status in {PlacementStatus.CANCELLED, PlacementStatus.COMPLETED}:
                if target == row.status and not fields_set:
                    return row
                raise BusinessConflictError("Terminal placements cannot be edited")
            candidate, _ = self._pair(row.candidate_id, row.vacancy_id)
            if target == PlacementStatus.IN_PROGRESS:
                match = self.ports.match.get(row.match_id) if row.match_id else None
                if (
                    candidate.status == CandidateStatus.INACTIVE
                    or not match
                    or match.status != MatchStatus.APPROVED
                ):
                    raise BusinessConflictError(
                        "An active candidate and approved match are required"
                    )
            activities = self._activities(identifier)
            if target == PlacementStatus.COMPLETED and any(
                item.status not in {PlacementStepStatus.COMPLETED, PlacementStepStatus.CANCELLED}
                for item in activities
            ):
                raise BusinessConflictError(
                    "Finish or cancel outstanding activities before completing placement"
                )
            changes = {"status": target}
            if "planned_departure_at" in fields_set:
                changes["planned_departure_at"] = planned_departure_at
            if "actual_departure_at" in fields_set:
                if actual_departure_at and actual_departure_at > now:
                    raise BusinessConflictError("Actual departure cannot be in the future")
                changes["actual_departure_at"] = actual_departure_at
            data = replace(record_data(row, PlacementData), **changes)
            if data == record_data(row, PlacementData):
                return row
            saved = self.ports.placement.replace(row.id, data)
            if target == PlacementStatus.CANCELLED:
                for item in activities:
                    if item.status not in {
                        PlacementStepStatus.COMPLETED,
                        PlacementStepStatus.CANCELLED,
                    }:
                        cancelled = self.ports.placement_stage.replace(
                            item.id,
                            replace(
                                record_data(item, PlacementStageData),
                                status=PlacementStepStatus.CANCELLED,
                                schedule_revision=item.schedule_revision + 1,
                            ),
                        )
                        self.reminders.cancel_activity(cancelled, now, actor)
                        self._audit(
                            cancelled,
                            "activity.cancelled",
                            actor,
                            AuditEntityType.PLACEMENT_STAGE,
                            now,
                            previous_status=item.status.value,
                            new_status="cancelled",
                        )
            self._audit(
                saved,
                "placement.updated",
                actor,
                AuditEntityType.PLACEMENT,
                now,
                previous_status=row.status.value,
                new_status=saved.status.value,
                previous_planned_departure_at=(
                    row.planned_departure_at.isoformat() if row.planned_departure_at else "none"
                ),
                planned_departure_at=(
                    saved.planned_departure_at.isoformat() if saved.planned_departure_at else "none"
                ),
            )
            return saved

    def create_activity(self, placement_id, data: PlacementStageData, actor):
        now = self.clock()
        with self.transaction():
            placement = self.get(placement_id)
            if placement.status not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}:
                raise BusinessConflictError("Activities require an active placement")
            if data.scheduled_at:
                self._require_active_candidate(placement)
            if data.scheduled_at is not None and data.scheduled_at <= now:
                raise BusinessConflictError("New activities must be scheduled in the future")
            existing = self.ports.placement_stage.get_by_code(placement_id, data.code)
            if existing:
                if record_data(existing, PlacementStageData) == data:
                    return existing
                raise BusinessConflictError("Activity code already exists in this placement")
            row = self.ports.placement_stage.create(data)
            self.reminders.sync_activity(row, now, actor)
            self._audit(
                row,
                "activity.created",
                actor,
                AuditEntityType.PLACEMENT_STAGE,
                now,
                new_status=row.status.value,
                schedule_revision=row.schedule_revision,
            )
            return row

    def _require_active_candidate(self, placement):
        candidate = self._require(self.ports.candidate.get(placement.candidate_id), "Candidate")
        if candidate.status == CandidateStatus.INACTIVE:
            raise BusinessConflictError(
                "Cannot schedule an activity for an inactive candidate; reminders are disabled"
            )

    def update_activity(self, placement_id, identifier, actor, **changes):
        now = self.clock()
        with self.transaction():
            placement = self.get(placement_id)
            if placement.status not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}:
                raise BusinessConflictError("Activities require an active placement")
            row = self._require(self.ports.placement_stage.get(identifier), "Activity")
            if row.placement_id != placement_id:
                raise BusinessConflictError("Activity does not belong to this placement")
            target = changes.get("status") or row.status
            if row.status == PlacementStepStatus.PENDING and changes.get("scheduled_at"):
                target = changes.get("status") or PlacementStepStatus.SCHEDULED
            if target in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}:
                self._require_active_candidate(placement)
            validate_transition(row.status, target, ACTIVITY_TRANSITIONS)
            if row.status in {PlacementStepStatus.COMPLETED, PlacementStepStatus.CANCELLED}:
                if all(getattr(row, key) == value for key, value in changes.items()):
                    return row
                raise BusinessConflictError("Terminal activities cannot be edited")
            rescheduled = any(
                key in changes and changes[key] != getattr(row, key)
                for key in ("scheduled_at", "due_at", "location")
            )
            if rescheduled and (
                row.status == PlacementStepStatus.IN_PROGRESS
                or changes.get("scheduled_at", row.scheduled_at) is None
                or changes.get("scheduled_at", row.scheduled_at) <= now
            ):
                raise BusinessConflictError(
                    "Rescheduling requires a future schedule before activity starts"
                )
            if target == PlacementStepStatus.COMPLETED:
                completed = changes.get("completed_at") or now
                if completed > now or (row.scheduled_at and completed < row.scheduled_at):
                    raise BusinessConflictError(
                        "Completion must be after schedule and no later than now"
                    )
                changes["completed_at"] = completed
            elif target == PlacementStepStatus.IN_PROGRESS and (
                not row.scheduled_at or row.scheduled_at > now
            ):
                raise BusinessConflictError("Activity cannot start before its scheduled time")
            elif changes.get("completed_at"):
                raise BusinessConflictError("Only completed activities can include completion time")
            changes["status"] = target
            if rescheduled or target == PlacementStepStatus.CANCELLED:
                changes["schedule_revision"] = row.schedule_revision + 1
            data = replace(record_data(row, PlacementStageData), **changes)
            if data == record_data(row, PlacementStageData):
                return row
            saved = self.ports.placement_stage.replace(row.id, data)
            if target == PlacementStepStatus.CANCELLED:
                self.reminders.cancel_activity(saved, now, actor)
            else:
                self.reminders.sync_activity(saved, now, actor)
            self._audit(
                saved,
                "activity.updated",
                actor,
                AuditEntityType.PLACEMENT_STAGE,
                now,
                previous_status=row.status.value,
                new_status=saved.status.value,
                schedule_revision=saved.schedule_revision,
                previous_scheduled_at=row.scheduled_at.isoformat() if row.scheduled_at else "none",
                scheduled_at=saved.scheduled_at.isoformat() if saved.scheduled_at else "none",
                previous_due_at=row.due_at.isoformat() if row.due_at else "none",
                due_at=saved.due_at.isoformat() if saved.due_at else "none",
            )
            return saved
