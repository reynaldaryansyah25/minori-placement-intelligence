"""Candidate management use cases with inward-facing port boundaries."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import UUID

from minori.domain.catalogs import CandidateStatus, Program
from minori.domain.entities import CandidateData, CandidateRecord
from minori.domain.errors import RecordNotFoundError
from minori.domain.repositories import CandidateRepository

TransactionFactory = Callable[[], AbstractContextManager[object]]


class CandidateService:
    def __init__(
        self,
        repository: CandidateRepository,
        transaction: TransactionFactory,
    ) -> None:
        self._repository = repository
        self._transaction = transaction

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        preferred_program: Program | None = None,
        status: CandidateStatus | None = None,
        query: str | None = None,
    ) -> list[CandidateRecord]:
        return self._repository.list(
            limit=limit,
            offset=offset,
            preferred_program=preferred_program,
            status=status,
            query=query,
        )

    def get(self, identifier: UUID) -> CandidateRecord:
        record = self._repository.get(identifier)
        if record is None:
            raise RecordNotFoundError(f"Candidate {identifier} does not exist")
        return record

    def get_by_reference(self, reference: str) -> CandidateRecord:
        record = self._repository.get_by_reference(reference)
        if record is None:
            raise RecordNotFoundError(f"Candidate reference {reference} does not exist")
        return record

    def create(self, data: CandidateData) -> CandidateRecord:
        with self._transaction():
            return self._repository.create(data)

    def replace(self, identifier: UUID, data: CandidateData) -> CandidateRecord:
        with self._transaction():
            return self._repository.replace(identifier, data)

    def archive(self, identifier: UUID) -> CandidateRecord:
        with self._transaction():
            return self._repository.archive(identifier)
