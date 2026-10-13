"""Employer eligibility checks with explicit evidence and deterministic time boundaries."""

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

from minori.domain.catalogs import LANGUAGE_LEVELS, CandidateStatus, VacancyStatus
from minori.domain.entities import CandidateData, VacancyData
from minori.domain.matching import (
    CheckOutcome,
    EligibilityResult,
    EligibilityStatus,
    ReasonCode,
    RuleCheck,
)

MONTH_DAYS = 365.2425 / 12


def subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month = divmod(month_index, 12)
    return date(year, month + 1, min(value.day, monthrange(year, month + 1)[1]))


def valid_certification_codes(candidate: CandidateData, on: date) -> set[str]:
    return {
        item.code
        for item in candidate.certifications
        if item.issued_on <= on and (item.expires_on is None or item.expires_on >= on)
    }


def relevant_experience(candidate: CandidateData, sector: str, on: date) -> tuple[int, bool, bool]:
    """Union inclusive employment days; overlaps never add extra experience."""
    intervals = []
    future = False
    for item in candidate.experiences:
        if item.sector.strip().casefold() != sector.strip().casefold():
            continue
        future |= item.started_on > on or (item.ended_on is not None and item.ended_on > on)
        end = min(item.ended_on or on, on)
        if item.started_on <= end:
            intervals.append((item.started_on, end + timedelta(days=1)))
    merged = []
    overlap = False
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            overlap |= start < merged[-1][1]
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum((end - start).days for start, end in merged), overlap, future


class EligibilityEngine:
    def evaluate(
        self, candidate: CandidateData, vacancy: VacancyData, as_of: datetime
    ) -> EligibilityResult:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Evaluation time must include a timezone")
        as_of = as_of.astimezone(UTC)
        on = as_of.date()
        checks = []

        def add(code, outcome, requirement, message, **evidence):
            checks.append(
                RuleCheck(
                    code=code,
                    outcome=outcome,
                    requirement=requirement,
                    message=message,
                    evidence=evidence,
                )
            )

        if candidate.preferred_program == vacancy.program:
            add(
                ReasonCode.PROGRAM_ACCEPTED,
                CheckOutcome.PASS,
                "program",
                "Program kandidat sesuai dengan lowongan.",
                program=vacancy.program.value,
            )
        else:
            add(
                ReasonCode.PROGRAM_MISMATCH,
                CheckOutcome.FAIL,
                "program",
                "Program pilihan kandidat berbeda dari program lowongan.",
                preferred=candidate.preferred_program.value,
                required=vacancy.program.value,
            )
        if candidate.status == CandidateStatus.INACTIVE:
            add(
                ReasonCode.CANDIDATE_INACTIVE,
                CheckOutcome.FAIL,
                "candidate_status",
                "Kandidat nonaktif tidak dapat direkomendasikan.",
            )
        elif candidate.status != CandidateStatus.READY:
            add(
                ReasonCode.READINESS_UNCONFIRMED,
                CheckOutcome.REVIEW,
                "candidate_status",
                "Staf perlu mengonfirmasi kesiapan kandidat sebelum rekomendasi aktif.",
                status=candidate.status.value,
            )
        else:
            add(
                ReasonCode.CANDIDATE_ACTIVE,
                CheckOutcome.PASS,
                "candidate_status",
                "Kandidat aktif dan siap.",
            )
        vacancy_codes = {
            VacancyStatus.OPEN: ReasonCode.VACANCY_OPEN,
            VacancyStatus.PAUSED: ReasonCode.VACANCY_PAUSED,
            VacancyStatus.CLOSED: ReasonCode.VACANCY_CLOSED,
        }
        add(
            vacancy_codes[vacancy.status],
            CheckOutcome.PASS if vacancy.status == VacancyStatus.OPEN else CheckOutcome.FAIL,
            "vacancy_status",
            "Lowongan harus berstatus open untuk rekomendasi aktif.",
            status=vacancy.status.value,
        )
        expired = vacancy.application_deadline is not None and as_of > vacancy.application_deadline
        add(
            ReasonCode.DEADLINE_PASSED if expired else ReasonCode.DEADLINE_VALID,
            CheckOutcome.FAIL if expired else CheckOutcome.PASS,
            "application_deadline",
            "Batas waktu lamaran telah lewat." if expired else "Batas waktu lamaran masih berlaku.",
            deadline=vacancy.application_deadline.isoformat()
            if vacancy.application_deadline
            else None,
        )

        language_score, language_evidence = self._language(candidate, vacancy, on, add)
        valid_codes = valid_certification_codes(candidate, on)
        for code in sorted(vacancy.required_certifications):
            history = [item for item in candidate.certifications if item.code == code]
            if code in valid_codes:
                reason, outcome = ReasonCode.CERTIFICATION_VALID, CheckOutcome.PASS
            elif any(item.issued_on > on for item in history):
                reason, outcome = ReasonCode.CERTIFICATION_NOT_YET_VALID, CheckOutcome.REVIEW
            elif history:
                reason, outcome = ReasonCode.CERTIFICATION_EXPIRED, CheckOutcome.FAIL
            else:
                reason, outcome = ReasonCode.CERTIFICATION_MISSING, CheckOutcome.FAIL
            add(
                reason,
                outcome,
                f"certification:{code}",
                "Sertifikasi wajib harus sudah terbit dan berlaku pada tanggal evaluasi.",
                certification_code=code,
                valid=code in valid_codes,
                history=[
                    {
                        "issued_on": item.issued_on.isoformat(),
                        "expires_on": item.expires_on.isoformat() if item.expires_on else None,
                    }
                    for item in sorted(history, key=lambda item: item.issued_on)
                ],
            )
        for code in sorted(vacancy.required_skills):
            present = code in candidate.skills
            add(
                ReasonCode.SKILL_PRESENT if present else ReasonCode.SKILL_MISSING,
                CheckOutcome.PASS if present else CheckOutcome.FAIL,
                f"skill:{code}",
                "Skill wajib tercatat." if present else "Skill wajib belum tercatat.",
                skill=code,
            )

        days, overlap, future = relevant_experience(candidate, vacancy.sector, on)
        months = days / MONTH_DAYS
        if overlap:
            add(
                ReasonCode.EXPERIENCE_OVERLAP_MERGED,
                CheckOutcome.INFO,
                "experience",
                "Periode pengalaman yang tumpang tindih dihitung satu kali.",
            )
        if future:
            add(
                ReasonCode.FUTURE_EXPERIENCE_IGNORED,
                CheckOutcome.INFO,
                "experience",
                "Hari pengalaman setelah tanggal evaluasi tidak dihitung.",
            )
        if months >= vacancy.minimum_experience_months:
            reason, outcome = ReasonCode.EXPERIENCE_SUFFICIENT, CheckOutcome.PASS
        elif not candidate.experiences or future:
            reason, outcome = ReasonCode.EXPERIENCE_EVIDENCE_MISSING, CheckOutcome.REVIEW
        else:
            reason, outcome = ReasonCode.EXPERIENCE_INSUFFICIENT, CheckOutcome.FAIL
        add(
            reason,
            outcome,
            "experience",
            "Pengalaman relevan memakai sektor yang sama dan union hari.",
            sector=vacancy.sector,
            unique_days=days,
            months=round(months, 6),
            minimum_months=vacancy.minimum_experience_months,
        )
        if not candidate.preferred_prefectures:
            add(
                ReasonCode.PREFECTURE_PREFERENCE_UNKNOWN,
                CheckOutcome.INFO,
                "preference",
                "Preferensi prefektur belum tersedia; skor lokasi menggunakan nilai 0.5.",
            )
        status = EligibilityStatus.ELIGIBLE
        if any(item.outcome == CheckOutcome.FAIL for item in checks):
            status = EligibilityStatus.NOT_ELIGIBLE
        elif any(item.outcome == CheckOutcome.REVIEW for item in checks):
            status = EligibilityStatus.NEEDS_REVIEW
        return EligibilityResult(
            status=status,
            checks=tuple(checks),
            language_score=language_score,
            language_evidence=language_evidence,
            relevant_days=days,
            relevant_months=months,
        )

    def _language(self, candidate, vacancy, on, add):
        if not vacancy.language_requirements:
            add(
                ReasonCode.LANGUAGE_NOT_REQUIRED,
                CheckOutcome.PASS,
                "language",
                "Lowongan tidak menetapkan persyaratan bahasa.",
            )
            return 1.0, {"not_required": True}
        accepted = []
        alternatives = []
        has_current = has_old = has_future = False
        cutoff = (
            subtract_months(on, vacancy.language_test_max_age_months)
            if vacancy.language_test_max_age_months
            else None
        )
        for requirement in sorted(vacancy.language_requirements, key=lambda item: item.test_type):
            levels = LANGUAGE_LEVELS[requirement.test_type]
            minimum = levels.index(requirement.minimum_level)
            history = sorted(
                (
                    item
                    for item in candidate.language_tests
                    if item.test_type == requirement.test_type
                ),
                key=lambda item: (item.taken_on, item.level),
            )
            current = [
                item
                for item in history
                if item.taken_on <= on and (cutoff is None or item.taken_on >= cutoff)
            ]
            has_current |= bool(current)
            has_old |= any(
                item.taken_on <= on and cutoff and item.taken_on < cutoff for item in history
            )
            has_future |= any(item.taken_on > on for item in history)
            best = max(
                current, key=lambda item: (levels.index(item.level), item.taken_on), default=None
            )
            passed = best is not None and levels.index(best.level) >= minimum
            evidence = {
                "test_type": requirement.test_type.value,
                "minimum_level": requirement.minimum_level,
                "best_level": best.level if best else None,
                "accepted": passed,
                "taken_on": best.taken_on.isoformat() if best else None,
                "history": [
                    {"level": item.level, "taken_on": item.taken_on.isoformat()} for item in history
                ],
            }
            alternatives.append(evidence)
            if passed:
                remaining = len(levels) - 1 - minimum
                surplus = (levels.index(best.level) - minimum) / remaining if remaining else 0.0
                accepted.append(
                    (round(0.6 + 0.4 * surplus, 6), requirement.test_type.value, evidence)
                )
        if accepted:
            # Utility relative to each threshold, never a cross-test level conversion.
            score, _, selected = sorted(accepted, key=lambda item: (-item[0], item[1]))[0]
            add(
                ReasonCode.LANGUAGE_ACCEPTED,
                CheckOutcome.PASS,
                "language",
                "Setidaknya satu alternatif tes memenuhi level minimum pada skala tes itu sendiri.",
                alternatives=alternatives,
                selected=selected,
            )
            if has_future:
                add(
                    ReasonCode.FUTURE_LANGUAGE_TEST,
                    CheckOutcome.INFO,
                    "language",
                    "Riwayat tes setelah tanggal evaluasi diabaikan; bukti lain sudah memenuhi.",
                )
        else:
            score, selected = 0.0, None
            if has_future:
                reason, outcome = ReasonCode.FUTURE_LANGUAGE_TEST, CheckOutcome.REVIEW
            elif has_old:
                reason, outcome = ReasonCode.LANGUAGE_EVIDENCE_OUTDATED, CheckOutcome.REVIEW
            elif has_current:
                reason, outcome = ReasonCode.LANGUAGE_BELOW_MINIMUM, CheckOutcome.FAIL
            else:
                reason, outcome = ReasonCode.LANGUAGE_EVIDENCE_MISSING, CheckOutcome.REVIEW
            add(
                reason,
                outcome,
                "language",
                "Belum ada bukti bahasa yang memenuhi alternatif lowongan.",
                alternatives=alternatives,
            )
        return score, {
            "alternatives": alternatives,
            "selected": selected,
            "age_cutoff": cutoff.isoformat() if cutoff else None,
        }
