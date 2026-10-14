"""Reminder generation, lease recovery, callbacks, and dry-run orchestration."""

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from minori.domain.ai import AiOutputError
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
from minori.domain.notification_templates import (
    ACTIVITY_LABELS,
    MANUAL_ACTIVITY_TEMPLATES,
    render_notification,
)
from minori.domain.operations import OperationsPorts, record_data
from minori.domain.reminders import DeliveryErrorCode, ReminderPolicy, is_automatic_reminder


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

    def _new(self, activity, placement, key, template, now, *, notice=False, manual=False):
        existing = self.ports.notification.get_by_deduplication_key(key)
        if existing:
            return existing
        due = (
            now
            if notice
            else activity.scheduled_at
            if manual
            else self.policy.scheduled_at(activity.scheduled_at, activity.step_type)
        )
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
        if current and current.approved_message:
            # A staff-approved snapshot is immutable; retain it when the schedule changes.
            self._abandon(current, now, DeliveryErrorCode.SCHEDULE_CHANGED)
            saved = self._save(
                current,
                status=NotificationStatus.CANCELLED,
                claimed_at=None,
                lease_expires_at=None,
                claim_token_hash=None,
                processed_at=now,
                last_error_code=DeliveryErrorCode.SCHEDULE_CHANGED,
            )
            self._audit(saved, "reminder.approval_invalidated", now, actor)
            return self._new(
                activity,
                placement,
                f"reminder:{activity.id}:r{activity.schedule_revision}",
                template,
                now,
            )
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
            if row.approved_message and not invalid:
                try:
                    _, digest = self.email_facts(row.id)
                    invalid = digest != row.approval_fingerprint
                except BusinessConflictError:
                    invalid = True
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

    def due(self, *, limit=100, offset=0, sandbox_ready=False):
        now = self.clock()
        with self.transaction():
            self._maintenance(now)
            if sandbox_ready:
                rows = [
                    row
                    for row in self._all(self.ports.queue, due_before=now)
                    if row.approved_message or is_automatic_reminder(row)
                ]
                return rows[offset : offset + limit]
            return self.ports.queue.list(due_before=now, limit=limit, offset=offset)

    def get(self, identifier):
        return self._get(identifier)

    def attempts(self, identifier, *, limit=100, offset=0):
        self._get(identifier)
        return self.ports.notification_attempt.list_for_notification(
            identifier, limit=limit, offset=offset
        )

    def claim(
        self,
        identifier=None,
        *,
        dry_run_only=False,
        require_approval=False,
        allow_automatic=False,
        on_claim=None,
    ):
        now = self.clock()
        with self.transaction():
            self._maintenance(now)
            eligible = self._get(identifier) if require_approval and identifier else None
            if require_approval and not (
                eligible
                and (
                    eligible.approved_message
                    or (allow_automatic and is_automatic_reminder(eligible))
                )
            ):
                raise BusinessConflictError(
                    "Persetujuan peserta demo diperlukan sebelum pengiriman."
                )
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
            if on_claim:
                on_claim(row)
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
            message = row.approved_message or render_notification(
                row.template_code, candidate.full_name, row.schedule_context
            )
            routing = self.policy.resolve_recipient(candidate.reference, dry_run=row.dry_run)
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
        return self.policy.resolve_recipient(candidate.reference, dry_run=row.dry_run)

    def prepare_activity_email(self, placement_id, activity_id, *, separate_manual=False):
        now = self.clock()
        with self.transaction():
            activity = self.ports.placement_stage.get(activity_id)
            placement = self.ports.placement.get(placement_id)
            if not activity or not placement or activity.placement_id != placement_id:
                raise RecordNotFoundError("Jadwal kegiatan tidak ditemukan pada penempatan ini.")
            candidate = self.ports.candidate.get(placement.candidate_id)
            if (
                candidate.status == CandidateStatus.INACTIVE
                or placement.status not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}
                or activity.status
                not in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}
                or not activity.scheduled_at
                or activity.scheduled_at <= now
            ):
                raise BusinessConflictError(
                    "Pilih kegiatan mendatang pada kandidat dan penempatan aktif."
                )
            self._maintenance(now)
            if separate_manual or activity.step_type.value in MANUAL_ACTIVITY_TEMPLATES:
                template = MANUAL_ACTIVITY_TEMPLATES.get(activity.step_type.value) or (
                    "interview_h3"
                    if activity.step_type == PlacementStepType.INTERVIEW
                    else "medical_h1"
                )
                row = self._new(
                    activity,
                    placement,
                    f"manual-activity:{activity.id}:r{activity.schedule_revision}",
                    template,
                    now,
                    manual=True,
                )
            else:
                row = self.sync_activity(activity, now)
            if not row or row.status != NotificationStatus.PENDING or row.attempt_count:
                raise BusinessConflictError(
                    "Pengingat kegiatan ini telah diproses. Pilih jadwal lain."
                )
            return row

    def email_facts(self, identifier):
        row = self._get(identifier)
        candidate = self.ports.candidate.get(row.candidate_id)
        activity = (
            self.ports.placement_stage.get(row.placement_stage_id)
            if row.placement_stage_id
            else None
        )
        placement = self.ports.placement.get(row.placement_id) if row.placement_id else None
        if not row.managed or not activity or not placement:
            raise BusinessConflictError(
                "Pengingat lama tidak memiliki jadwal operasional yang valid."
            )
        if (
            candidate.status == CandidateStatus.INACTIVE
            or activity.scheduled_at is None
            or activity.scheduled_at <= self.clock()
            or activity.status
            not in {PlacementStepStatus.SCHEDULED, PlacementStepStatus.IN_PROGRESS}
            or placement.status not in {PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS}
            or activity.schedule_revision != row.schedule_revision
            or row.template_code
            not in {"interview_h3", "medical_h1", *MANUAL_ACTIVITY_TEMPLATES.values()}
        ):
            raise BusinessConflictError("Kandidat atau jadwal berubah. Muat ulang pengingat.")
        from zoneinfo import ZoneInfo

        facts = {
            "candidate_name": candidate.full_name,
            "activity": ACTIVITY_LABELS[activity.step_type.value],
            "scheduled_wib": activity.scheduled_at.astimezone(ZoneInfo("Asia/Jakarta")).strftime(
                "%d-%m-%Y %H:%M WIB"
            ),
            "location": activity.location,
            "preparation_instructions": None,
            "sender": "MINORI Placement Intelligence",
            "schedule_revision": activity.schedule_revision,
        }
        protected = {
            "facts": facts,
            "candidate_status": candidate.status.value,
            "routing": self.recipient_routing(identifier),
            "dry_run": row.dry_run,
        }
        digest = hashlib.sha256(json.dumps(protected, sort_keys=True).encode()).hexdigest()
        return facts, digest

    def draft_email(self, identifier, gateway=None):
        row = self._get(identifier)
        facts, digest = self.email_facts(identifier)
        introduction = "Kami mengingatkan Anda mengenai kegiatan yang telah dijadwalkan."
        closing = "Terima kasih atas perhatian dan kerja sama Anda."
        if gateway:
            wording = gateway.generate("email", facts)
            # Free model wording cannot introduce facts. A constrained vocabulary permits
            # polite connective language; the server alone inserts dates/location/instructions.
            allowed = set(
                "kami mengingatkan anda mengenai kegiatan yang telah dijadwalkan ini merupakan pengingat untuk mengikuti sesuai jadwal tercantum di bawah silakan tinjau informasi berikut mohon perhatian dan konfirmasi kehadiran kepada staf terima kasih atas kerja sama waktu salam hormat tim minori placement intelligence dengan baik bapak ibu saudara saudari disiapkan membantu menyampaikan serta kembali pada email dapat menghubungi apabila ada pertanyaan berharap lancar partisipasi kesediaan jadwal pelaksanaan atasnya".split()
            )
            if any(
                word.casefold() not in allowed
                for word in re.findall(r"\w+", wording["introduction"] + " " + wording["closing"])
            ):
                raise AiOutputError(
                    "Bahasa draf AI memuat informasi yang perlu dikonfirmasi. Gunakan template aman."
                )
            introduction, closing = wording["introduction"], wording["closing"]
        subject = f"Pengingat {facts['activity']} — MINORI"
        body = (
            f"Halo {facts['candidate_name']},\n\n{introduction}\n\n"
            f"Kegiatan: {facts['activity']}\nJadwal: {facts['scheduled_wib']}\n"
            f"Lokasi: {facts['location'] or 'Perlu konfirmasi kepada staf'}\n"
            "Persiapan: belum ada instruksi tambahan yang tercatat; konfirmasikan kepada staf.\n\n"
            f"{closing}\n\n{facts['sender']}"
        )
        return {
            "subject": subject,
            "body": body,
            "facts": facts,
            "facts_fingerprint": digest,
            "schedule_revision": row.schedule_revision,
            "source": "ai" if gateway else "template",
        }

    def approve_email(self, identifier, subject, body, fingerprint, key, actor):
        now = self.clock()
        with self.transaction():
            row = self._get(identifier)
            facts, current = self.email_facts(identifier)
            if current != fingerprint:
                raise BusinessConflictError(
                    "Data kandidat, jadwal, atau penerima berubah. Susun ulang email."
                )
            message = {"subject": subject.strip(), "body": body.strip()}
            if (
                facts["scheduled_wib"] not in body
                or facts["candidate_name"] not in body
                or (facts["location"] and facts["location"] not in body)
            ):
                raise ValueError(
                    "Nama kandidat, jadwal WIB dan lokasi resmi harus tetap tercantum dalam pesan."
                )
            if not all(message.values()) or any(c in subject for c in "\r\n\x00") or "\x00" in body:
                raise ValueError("Subject dan isi email harus berupa teks yang valid.")
            if row.manual_request_key == key:
                if row.approved_message == message and row.approval_fingerprint == fingerprint:
                    return row
                raise BusinessConflictError(
                    "Kunci persetujuan sudah digunakan untuk pesan berbeda."
                )
            if (
                row.status != NotificationStatus.PENDING
                or row.attempt_count
                or row.approved_message
            ):
                raise BusinessConflictError(
                    "Pengingat sudah disetujui atau pernah diproses. Pengiriman ganda diblokir."
                )
            routing = self.recipient_routing(identifier)
            if not row.dry_run and (
                not routing["delivery_allowed"] or routing["routing_mode"] != "mailpit"
            ):
                raise BusinessConflictError(
                    "Pengiriman manual saat ini hanya diizinkan ke Mailpit lokal atau simulasi."
                )
            saved = self._save(
                row,
                approved_message=message,
                approved_by=actor,
                approved_at=now,
                approval_fingerprint=fingerprint,
                manual_request_key=key,
                scheduled_at=now,
                available_at=now,
            )
            self._audit(
                saved,
                "reminder.email_approved",
                now,
                actor,
                facts_fingerprint=fingerprint,
                schedule_revision=row.schedule_revision,
                delivery_mode=routing["routing_mode"],
            )
            return saved

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
