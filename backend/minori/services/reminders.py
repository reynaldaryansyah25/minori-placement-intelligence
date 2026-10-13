"""Reminder generation, lease recovery, callbacks, and dry-run orchestration."""

import hashlib
import hmac
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from minori.domain.catalogs import (
    AttemptStatus,
    AuditEntityType,
    CandidateStatus,
    NotificationStatus,
    PlacementStatus,
    PlacementStepStatus,
    PlacementStepType,
)
from minori.domain.entities import AuditLogData, NotificationAttemptData, NotificationData
from minori.domain.errors import BusinessConflictError, RecordNotFoundError
from minori.domain.notification_templates import render_notification
from minori.domain.operations import OperationsPorts, record_data
from minori.domain.reminders import DeliveryErrorCode, ReminderPolicy


def utc_now():
    return datetime.now(UTC)


class ReminderService:
    def __init__(self, ports: OperationsPorts, transaction, policy: ReminderPolicy, clock=utc_now):
        self.ports = ports
        self.transaction = transaction
        self.policy = policy
        self.clock = clock

    def _audit(self, row, action, now, actor="reminder.worker", **context):
        self.ports.audit_log.append(
            AuditLogData(
                reference="AUD-" + uuid4().hex.upper(),
                actor_reference=actor,
                action=action,
                entity_type=AuditEntityType.NOTIFICATION,
                entity_id=row.id,
                occurred_at=now,
                context=context,
            )
        )

    def _save(self, row, **values):
        return self.ports.notification.replace(
            row.id, replace(record_data(row, NotificationData), **values)
        )

    @staticmethod
    def _all(repository, **filters):
        rows = []
        while True:
            page = repository.list(limit=100, offset=len(rows), **filters)
            rows.extend(page)
            if len(page) < 100:
                return rows

    def _get(self, identifier):
        row = self.ports.notification.get(identifier)
        if row is None:
            raise RecordNotFoundError("Notification was not found")
        return row

    def _context(self, activity):
        return {
            "activity": activity.step_type.value,
            "scheduled_at": activity.scheduled_at.isoformat(),
            "location": activity.location,
            "timezone": self.policy.timezone,
            "revision": activity.schedule_revision,
        }

    def _new(self, activity, placement, key, template, now, *, notice=False):
        existing = self.ports.notification.get_by_deduplication_key(key)
        if existing:
            return existing
        due = now if notice else self.policy.scheduled_at(activity.scheduled_at, activity.step_type)
        expired = not notice and activity.scheduled_at <= now
        row = self.ports.notification.create(
            NotificationData(
                reference="NTF-" + uuid4().hex.upper(),
                deduplication_key=key,
                candidate_id=placement.candidate_id,
                placement_id=placement.id,
                placement_stage_id=activity.id,
                template_code=template,
                scheduled_at=due,
                available_at=max(now, due),
                event_at=(
                    max(now + timedelta(days=1), activity.scheduled_at)
                    if notice
                    else activity.scheduled_at
                ),
                schedule_revision=activity.schedule_revision,
                schedule_context=self._context(activity),
                managed=True,
                dry_run=self.policy.dry_run,
                max_attempts=self.policy.max_attempts,
                status=NotificationStatus.MISSED if expired else NotificationStatus.PENDING,
                processed_at=now if expired else None,
                last_error_code=DeliveryErrorCode.EVENT_PASSED if expired else None,
            )
        )
        self._audit(row, "reminder.created", now)
        return row

    def _abandon(self, row, now, error):
        if row.status == NotificationStatus.PROCESSING:
            self.ports.queue.finish_attempt(
                row.id,
                row.attempt_count,
                status=AttemptStatus.ABANDONED,
                finished_at=now,
                error_code=error,
            )

    def cancel_activity(self, activity, now, actor, *, notice=True):
        delivered = False
        for row in self.ports.queue.for_activity(activity.id):
            if row.status in {NotificationStatus.SENT, NotificationStatus.SIMULATED}:
                delivered = True
                continue
            if row.status == NotificationStatus.CANCELLED:
                continue
            self._abandon(row, now, DeliveryErrorCode.ACTIVITY_CANCELLED)
            saved = self._save(
                row,
                status=NotificationStatus.CANCELLED,
                claimed_at=None,
                lease_expires_at=None,
                claim_token_hash=None,
                processed_at=now,
                last_error_code=DeliveryErrorCode.ACTIVITY_CANCELLED,
            )
            self._audit(saved, "reminder.cancelled", now, actor)
        if (
            delivered
            and notice
            and activity.scheduled_at
            and activity.step_type
            in {
                PlacementStepType.INTERVIEW,
                PlacementStepType.MEDICAL_CHECK,
            }
        ):
            placement = self.ports.placement.get(activity.placement_id)
            return self._new(
                activity,
                placement,
                f"notice:{activity.id}:r{activity.schedule_revision}:cancelled",
                "schedule_cancelled",
                now,
                notice=True,
            )
        return None

    def sync_activity(self, activity, now, actor="reminder.generator"):
        if activity.step_type not in {PlacementStepType.INTERVIEW, PlacementStepType.MEDICAL_CHECK}:
            return None
        placement = self.ports.placement.get(activity.placement_id)
        candidate = self.ports.candidate.get(placement.candidate_id)
        if (
            activity.status not in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}
            or not activity.scheduled_at
            or placement.status not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}
            or candidate.status == CandidateStatus.INACTIVE
        ):
            self.cancel_activity(activity, now, actor, notice=False)
            return None
        template = (
            "interview_h3" if activity.step_type == PlacementStepType.INTERVIEW else "medical_h1"
        )
        history = [
            row
            for row in self.ports.queue.for_activity(activity.id)
            if row.template_code == template
        ]
        current = max(
            history,
            key=lambda row: (row.schedule_revision, row.created_at, str(row.id)),
            default=None,
        )
        if current and current.schedule_revision == activity.schedule_revision:
            return current
        if current and current.status not in {
            NotificationStatus.SENT,
            NotificationStatus.SIMULATED,
        }:
            self._abandon(current, now, DeliveryErrorCode.SCHEDULE_CHANGED)
            due = self.policy.scheduled_at(activity.scheduled_at, activity.step_type)
            expired = activity.scheduled_at <= now
            saved = self._save(
                current,
                schedule_revision=activity.schedule_revision,
                schedule_context=self._context(activity),
                scheduled_at=due,
                available_at=max(now, due),
                event_at=activity.scheduled_at,
                status=NotificationStatus.MISSED if expired else NotificationStatus.PENDING,
                claimed_at=None,
                lease_expires_at=None,
                claim_token_hash=None,
                processed_at=now if expired else None,
                last_error_code=DeliveryErrorCode.EVENT_PASSED if expired else None,
                max_attempts=current.attempt_count + self.policy.max_attempts,
            )
            self._audit(
                saved,
                "reminder.rescheduled",
                now,
                actor,
                schedule_revision=activity.schedule_revision,
            )
            return saved
        if current:
            self._new(
                activity,
                placement,
                f"notice:{activity.id}:r{activity.schedule_revision}:changed",
                "schedule_changed",
                now,
                notice=True,
            )
        return self._new(
            activity,
            placement,
            f"reminder:{activity.id}:r{activity.schedule_revision}",
            template,
            now,
        )

    def _retry(self, row, now, error, *, abandoned=False):
        self.ports.queue.finish_attempt(
            row.id,
            row.attempt_count,
            status=AttemptStatus.ABANDONED if abandoned else AttemptStatus.FAILED,
            finished_at=now,
            error_code=error,
        )
        available = now + self.policy.backoff(row.attempt_count)
        retry = row.attempt_count < row.max_attempts and available < row.event_at
        status = (
            NotificationStatus.PENDING
            if retry
            else NotificationStatus.MISSED
            if available >= row.event_at
            else NotificationStatus.FAILED
        )
        saved = self._save(
            row,
            status=status,
            available_at=available,
            claimed_at=None,
            lease_expires_at=None,
            processed_at=now,
            last_error_code=error,
        )
        self._audit(
            saved,
            "reminder.retry_scheduled" if retry else "reminder.failed",
            now,
            reason_code=error,
            attempt_number=row.attempt_count,
        )
        return saved

    def _maintenance(self, now):
        changed = 0
        for row in self._all(self.ports.queue, active_only=True):
            if not row.managed or row.status not in {
                NotificationStatus.PENDING,
                NotificationStatus.PROCESSING,
            }:
                continue
            candidate = self.ports.candidate.get(row.candidate_id)
            activity = self.ports.placement_stage.get(row.placement_stage_id)
            placement = self.ports.placement.get(row.placement_id)
            notice = row.template_code in {"schedule_changed", "schedule_cancelled"}
            invalid = candidate.status == CandidateStatus.INACTIVE or (
                not notice
                and (
                    activity.status
                    not in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}
                    or placement.status
                    not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}
                    or row.schedule_revision != activity.schedule_revision
                )
            )
            if invalid or row.event_at <= now:
                error = (
                    DeliveryErrorCode.RECIPIENT_INACTIVE
                    if invalid
                    else DeliveryErrorCode.EVENT_PASSED
                )
                self._abandon(row, now, error)
                saved = self._save(
                    row,
                    status=NotificationStatus.CANCELLED if invalid else NotificationStatus.MISSED,
                    claimed_at=None,
                    lease_expires_at=None,
                    claim_token_hash=None,
                    processed_at=now,
                    last_error_code=error,
                )
                self._audit(saved, "reminder.invalidated", now, reason_code=error)
                changed += 1
            elif row.status == NotificationStatus.PROCESSING and row.lease_expires_at <= now:
                self._retry(row, now, DeliveryErrorCode.LEASE_EXPIRED, abandoned=True)
                changed += 1
        return changed

    def generate(self):
        now = self.clock()
        with self.transaction():
            self._maintenance(now)
            rows = []
            for activity in self._all(self.ports.placement_stage):
                result = self.sync_activity(activity, now)
                if result:
                    rows.append(result)
            return rows

    def recover(self):
        with self.transaction():
            return {"recovered_count": self._maintenance(self.clock())}

    def list(self, **filters):
        return self.ports.queue.list(**filters)

    def due(self, *, limit=100, offset=0):
        now = self.clock()
        with self.transaction():
            self._maintenance(now)
            return self.ports.queue.list(due_before=now, limit=limit, offset=offset)

    def get(self, identifier):
        return self._get(identifier)

    def attempts(self, identifier, *, limit=100, offset=0):
        self._get(identifier)
        return self.ports.notification_attempt.list_for_notification(
            identifier, limit=limit, offset=offset
        )

    def claim(self, identifier=None, *, dry_run_only=False):
        now = self.clock()
        with self.transaction():
            self._maintenance(now)
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            row = self.ports.queue.claim(
                identifier,
                now,
                digest,
                now + timedelta(seconds=self.policy.lease_seconds),
                dry_run_only=dry_run_only,
            )
            if row is None:
                return None
            self.ports.notification_attempt.append(
                NotificationAttemptData(
                    notification_id=row.id,
                    attempt_number=row.attempt_count,
                    status=AttemptStatus.PROCESSING,
                    attempted_at=now,
                    finished_at=None,
                    claim_token_hash=digest,
                )
            )
            candidate = self.ports.candidate.get(row.candidate_id)
            message = render_notification(
                row.template_code, candidate.full_name, row.schedule_context
            )
            routing = self.policy.resolve_recipient(candidate.reference)
            self._audit(row, "reminder.claimed", now, attempt_number=row.attempt_count)
            return {
                "notification": row,
                "claim_token": token,
                "message": message,
                "recipient_routing": routing,
            }

    def recipient_routing(self, identifier):
        row = self._get(identifier)
        candidate = self.ports.candidate.get(row.candidate_id)
        return self.policy.resolve_recipient(candidate.reference)

    def complete(
        self, identifier, token, *, simulated=False, error_code=None, provider_reference=None
    ):
        now = self.clock()
        invalid = False
        result = None
        with self.transaction():
            self._maintenance(now)
            row = self._get(identifier)
            digest = hashlib.sha256(token.encode()).hexdigest()
            attempt = self.ports.queue.last_attempt(identifier)
            if not row.claim_token_hash or not hmac.compare_digest(row.claim_token_hash, digest):
                invalid = True
            elif row.status != NotificationStatus.PROCESSING:
                expected = (
                    AttemptStatus.FAILED
                    if error_code
                    else AttemptStatus.SIMULATED
                    if simulated
                    else AttemptStatus.SUCCEEDED
                )
                if (
                    attempt
                    and attempt.claim_token_hash == digest
                    and attempt.status == expected
                    and attempt.error_code == error_code
                    and attempt.provider_reference == provider_reference
                ):
                    result = row
                else:
                    invalid = True
            elif error_code is not None:
                result = self._retry(row, now, error_code)
            else:
                if row.dry_run != simulated:
                    raise BusinessConflictError(
                        "Callback outcome does not match notification delivery mode"
                    )
                if simulated and provider_reference is not None:
                    raise BusinessConflictError(
                        "Simulated delivery cannot have a provider reference"
                    )
                if not simulated and provider_reference is None:
                    raise BusinessConflictError("Real delivery requires a provider reference")
                self.ports.queue.finish_attempt(
                    row.id,
                    row.attempt_count,
                    status=AttemptStatus.SIMULATED if simulated else AttemptStatus.SUCCEEDED,
                    finished_at=now,
                    provider_reference=provider_reference,
                )
                result = self._save(
                    row,
                    status=NotificationStatus.SIMULATED if simulated else NotificationStatus.SENT,
                    sent_at=None if simulated else now,
                    processed_at=now,
                    claimed_at=None,
                    lease_expires_at=None,
                    last_error_code=None,
                )
                self._audit(
                    result,
                    "reminder.simulated" if simulated else "reminder.sent",
                    now,
                    attempt_number=row.attempt_count,
                )
        if invalid:
            # Maintenance must commit even when the caller supplies an obsolete token.
            raise BusinessConflictError(
                "Claim is invalid, expired, cancelled, or already finalized differently"
            )
        return result

    def simulate(self, identifier=None):
        if not self.policy.dry_run:
            raise BusinessConflictError("Simulation endpoint requires dry-run mode")
        claimed = self.claim(identifier, dry_run_only=True)
        if claimed is None:
            return None
        row = claimed["notification"]
        if not row.dry_run:
            self.complete(
                row.id, claimed["claim_token"], error_code=DeliveryErrorCode.PROVIDER_REJECTED
            )
            raise BusinessConflictError("This notification was configured for real delivery")
        return self.complete(row.id, claimed["claim_token"], simulated=True)
