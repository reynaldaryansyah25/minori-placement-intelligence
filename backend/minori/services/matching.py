"""Matching use cases with atomic writes through inward-facing repository contracts."""

from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID

from minori.domain.catalogs import MatchStatus
from minori.domain.entities import CandidateData, VacancyData
from minori.domain.errors import RecordNotFoundError
from minori.domain.matching import (
    EligibilityStatus,
    EvaluationRepository,
    MatchingEvaluation,
    TransactionFactory,
)
from minori.domain.matching_engine import MatchingEngine, RankingEngine
from minori.domain.repositories import CandidateRepository, MatchRepository, VacancyRepository


def utc_now() -> datetime:
    return datetime.now(UTC)


class MatchingService:
    def __init__(
        self,
        candidates: CandidateRepository,
        vacancies: VacancyRepository,
        matches: MatchRepository,
        evaluations: EvaluationRepository,
        transaction: TransactionFactory,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.candidates = candidates
        self.vacancies = vacancies
        self.matches = matches
        self.evaluations = evaluations
        self.transaction = transaction
        self.clock = clock
        self.engine = MatchingEngine()

    @staticmethod
    def _require(record, identifier):
        if record is None:
            raise RecordNotFoundError(f"Record {identifier} does not exist")
        return record

    @staticmethod
    def _all(repository):
        records = []
        while True:
            page = repository.list(limit=100, offset=len(records))
            records.extend(page)
            if len(page) < 100:
                return sorted(records, key=lambda item: (item.reference, str(item.id)))

    def _selected(self, repository, identifier):
        return (
            [self._require(repository.get(identifier), identifier)]
            if identifier is not None
            else self._all(repository)
        )

    def _time(self, as_of):
        now = self.clock()
        selected = as_of or now
        if selected.tzinfo is None or selected.utcoffset() is None:
            raise ValueError("Evaluation time must include a timezone")
        if selected > now:
            raise ValueError("Future evaluation times are not supported")
        return selected

    def _evaluate(self, candidate_id, vacancy_id, as_of):
        results = []
        candidates = self._selected(self.candidates, candidate_id)
        vacancies = self._selected(self.vacancies, vacancy_id)
        for candidate in candidates:
            for vacancy in vacancies:
                evaluation = self.engine.evaluate(candidate, vacancy, as_of)
                stored = self.evaluations.find_identical(evaluation) or self.evaluations.append(
                    evaluation
                )
                results.append(self._view(stored, candidate, vacancy, self.clock()))
        return results

    def evaluate(
        self,
        *,
        candidate_id: UUID | None = None,
        vacancy_id: UUID | None = None,
        as_of: datetime | None = None,
    ) -> list[dict]:
        as_of = self._time(as_of)
        with self.transaction():
            return self._evaluate(candidate_id, vacancy_id, as_of)

    def replace_candidate(self, identifier: UUID, data: CandidateData) -> list[dict]:
        with self.transaction():
            self.candidates.replace(identifier, data)
            return self._evaluate(identifier, None, self.clock())

    def refresh_candidate(self, identifier: UUID):
        """Refresh within the caller's candidate-write transaction."""
        return self._evaluate(identifier, None, self.clock())

    def refresh_vacancy(self, identifier: UUID):
        """Refresh within the caller's vacancy-write transaction."""
        return self._evaluate(None, identifier, self.clock())

    def current_candidates(self, vacancy_id, *, limit=100, offset=0):
        vacancy = self._require(self.vacancies.get(vacancy_id), vacancy_id)
        now = self.clock()
        return [
            self._view(
                self.engine.evaluate(candidate, vacancy, now), candidate, vacancy, now, current=True
            )
            for candidate in self._all(self.candidates)[offset : offset + limit]
        ]

    def replace_vacancy(self, identifier: UUID, data: VacancyData) -> list[dict]:
        with self.transaction():
            self.vacancies.replace(identifier, data)
            return self._evaluate(None, identifier, self.clock())

    def _view(self, evaluation, candidate, vacancy, now, *, current=False):
        live = evaluation if current else self.engine.evaluate(candidate, vacancy, now)
        stale = (
            evaluation.input_fingerprint != live.input_fingerprint
            or evaluation.algorithm_version != live.algorithm_version
            or evaluation.eligibility_status != live.eligibility_status
            or evaluation.total_score != live.total_score
            or evaluation.explanation != live.explanation
        )
        manual = self.matches.get_by_pair(candidate.id, vacancy.id)
        status = manual.status if manual else MatchStatus.PROPOSED
        return {
            **{item.name: getattr(evaluation, item.name) for item in fields(MatchingEvaluation)},
            "evaluation_id": getattr(evaluation, "id", None),
            "candidate_reference": candidate.reference,
            "vacancy_reference": vacancy.reference,
            "staff_status": status,
            "match_id": manual.id if manual else None,
            "is_stale": stale,
            "active_recommendation": (
                not stale
                and live.eligibility_status == EligibilityStatus.ELIGIBLE
                and status != MatchStatus.REJECTED
            ),
        }

    def explain(self, candidate_id: UUID, vacancy_id: UUID) -> dict:
        candidate = self._require(self.candidates.get(candidate_id), candidate_id)
        vacancy = self._require(self.vacancies.get(vacancy_id), vacancy_id)
        now = self.clock()
        evaluation = self.engine.evaluate(candidate, vacancy, now)
        return self._view(evaluation, candidate, vacancy, now, current=True)

    def results(
        self,
        *,
        candidate_id: UUID | None = None,
        vacancy_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        if candidate_id is not None:
            self._require(self.candidates.get(candidate_id), candidate_id)
        if vacancy_id is not None:
            self._require(self.vacancies.get(vacancy_id), vacancy_id)
        now = self.clock()
        return [
            self._view(
                item,
                self._require(self.candidates.get(item.candidate_id), item.candidate_id),
                self._require(self.vacancies.get(item.vacancy_id), item.vacancy_id),
                now,
            )
            for item in self.evaluations.list(
                candidate_id=candidate_id, vacancy_id=vacancy_id, limit=limit, offset=offset
            )
        ]

    def result(self, identifier: UUID) -> dict:
        item = self._require(self.evaluations.get(identifier), identifier)
        return self._view(
            item,
            self._require(self.candidates.get(item.candidate_id), item.candidate_id),
            self._require(self.vacancies.get(item.vacancy_id), item.vacancy_id),
            self.clock(),
        )

    def ranking(self, vacancy_id: UUID, *, limit: int = 100, offset: int = 0) -> list[dict]:
        vacancy = self._require(self.vacancies.get(vacancy_id), vacancy_id)
        now = self.clock()
        candidates = self._all(self.candidates)
        by_id = {candidate.id: candidate for candidate in candidates}
        pairs = [
            (candidate, self.engine.evaluate(candidate, vacancy, now)) for candidate in candidates
        ]
        ranked = []
        for item in RankingEngine().rank(pairs):
            view = self._view(item, by_id[item.candidate_id], vacancy, now, current=True)
            if view["active_recommendation"]:
                ranked.append({**view, "rank": len(ranked) + 1})
        return ranked[offset : offset + limit]
