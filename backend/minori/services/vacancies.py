import builtins
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from uuid import UUID

from minori.domain.catalogs import DraftStatus, LanguageTestType, Program, VacancyStatus
from minori.domain.entities import (
    LanguageRequirementData,
    VacancyData,
    VacancyDraftData,
    VacancyDraftRecord,
    VacancyRecord,
)
from minori.domain.errors import RecordNotFoundError
from minori.domain.repositories import VacancyDraftRepository, VacancyRepository

TransactionFactory = Callable[[], AbstractContextManager[object]]


class VacancyService:
    def __init__(
        self,
        vacancies: VacancyRepository,
        drafts: VacancyDraftRepository,
        transaction: TransactionFactory,
    ) -> None:
        self._vacancies = vacancies
        self._drafts = drafts
        self._transaction = transaction

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        program: Program | None = None,
        status: VacancyStatus | None = None,
        query: str | None = None,
    ) -> list[VacancyRecord]:
        return self._vacancies.list(
            limit=limit,
            offset=offset,
            program=program,
            status=status,
            query=query,
        )

    def get(self, identifier: UUID) -> VacancyRecord:
        record = self._vacancies.get(identifier)
        if record is None:
            raise RecordNotFoundError(f"Vacancy {identifier} does not exist")
        return record

    def get_by_reference(self, reference: str) -> VacancyRecord:
        record = self._vacancies.get_by_reference(reference)
        if record is None:
            raise RecordNotFoundError(f"Vacancy reference {reference} does not exist")
        return record

    def create(self, data: VacancyData) -> VacancyRecord:
        with self._transaction():
            return self._vacancies.create(data)

    def replace(self, identifier: UUID, data: VacancyData) -> VacancyRecord:
        with self._transaction():
            return self._vacancies.replace(identifier, data)

    def close(self, identifier: UUID) -> VacancyRecord:
        with self._transaction():
            return self._vacancies.archive(identifier)

    def list_drafts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: DraftStatus | None = None,
    ) -> builtins.list[VacancyDraftRecord]:
        return self._drafts.list(limit=limit, offset=offset, status=status)

    def get_draft(self, identifier: UUID) -> VacancyDraftRecord:
        record = self._drafts.get(identifier)
        if record is None:
            raise RecordNotFoundError(f"Vacancy draft {identifier} does not exist")
        return record

    def create_draft(self, data: VacancyDraftData) -> VacancyDraftRecord:
        with self._transaction():
            return self._drafts.create(data)

    def update_draft(self, identifier: UUID, data: VacancyDraftData) -> VacancyDraftRecord:
        with self._transaction():
            return self._drafts.replace(identifier, data)

    def publish_draft(
        self, draft_id: UUID, vacancy_data: VacancyData | None = None
    ) -> VacancyRecord:
        with self._transaction():
            draft = self.get_draft(draft_id)
            if vacancy_data is None:
                p = draft.proposed_data

                raw_deadline = p.get("application_deadline")
                deadline: datetime | None = None
                if isinstance(raw_deadline, datetime):
                    deadline = raw_deadline
                elif isinstance(raw_deadline, str):
                    try:
                        deadline = datetime.fromisoformat(raw_deadline)
                    except ValueError:
                        deadline = None

                raw_max_age = p.get("language_test_max_age_months")
                max_age_months: int | None = None
                if isinstance(raw_max_age, int):
                    max_age_months = raw_max_age
                elif isinstance(raw_max_age, str) and raw_max_age.isdigit():
                    max_age_months = int(raw_max_age)

                raw_quota = p.get("quota", 1)
                quota_val = (
                    int(raw_quota)
                    if isinstance(raw_quota, (int, str)) and str(raw_quota).isdigit()
                    else 1
                )

                raw_exp = p.get("minimum_experience_months", 0)
                exp_val = (
                    int(raw_exp)
                    if isinstance(raw_exp, (int, str)) and str(raw_exp).isdigit()
                    else 0
                )

                raw_req_skills = p.get("required_skills", ())
                req_skills: tuple[str, ...] = (
                    tuple(str(s) for s in raw_req_skills)
                    if isinstance(raw_req_skills, (list, tuple))
                    else ()
                )

                raw_req_certs = p.get("required_certifications", ())
                req_certs: tuple[str, ...] = (
                    tuple(str(c) for c in raw_req_certs)
                    if isinstance(raw_req_certs, (list, tuple))
                    else ()
                )

                raw_pref_skills = p.get("preferred_skills", ())
                pref_skills: tuple[str, ...] = (
                    tuple(str(s) for s in raw_pref_skills)
                    if isinstance(raw_pref_skills, (list, tuple))
                    else ()
                )

                raw_pref_certs = p.get("preferred_certifications", ())
                pref_certs: tuple[str, ...] = (
                    tuple(str(c) for c in raw_pref_certs)
                    if isinstance(raw_pref_certs, (list, tuple))
                    else ()
                )

                raw_lang = p.get("language_requirements", ())
                lang_reqs: list[LanguageRequirementData] = []
                if isinstance(raw_lang, (list, tuple)):
                    for req in raw_lang:
                        if isinstance(req, dict):
                            lang_reqs.append(
                                LanguageRequirementData(
                                    test_type=LanguageTestType(str(req.get("test_type", ""))),
                                    minimum_level=str(req.get("minimum_level", "")),
                                )
                            )

                vacancy_data = VacancyData(
                    reference=str(p.get("reference", draft.reference)),
                    title=str(p.get("title", "")),
                    employer_name=str(p.get("employer_name", "")),
                    program=Program(str(p.get("program", "SSW"))),
                    sector=str(p.get("sector", "")),
                    prefecture=str(p.get("prefecture", "")),
                    quota=quota_val,
                    minimum_experience_months=exp_val,
                    required_skills=req_skills,
                    required_certifications=req_certs,
                    preferred_skills=pref_skills,
                    preferred_certifications=pref_certs,
                    status=VacancyStatus(str(p.get("status", "open"))),
                    application_deadline=deadline,
                    language_test_max_age_months=max_age_months,
                    language_requirements=tuple(lang_reqs),
                )
            vacancy = self._vacancies.create(vacancy_data)
            updated_draft_data = VacancyDraftData(
                reference=draft.reference,
                source_channel=draft.source_channel,
                source_reference=draft.source_reference,
                proposed_data=draft.proposed_data,
                status=DraftStatus.PUBLISHED,
                published_vacancy_id=vacancy.id,
                analysis_metadata=draft.analysis_metadata,
            )
            self._drafts.replace(draft_id, updated_draft_data)
            return vacancy
