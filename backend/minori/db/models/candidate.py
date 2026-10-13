"""Candidate aggregate and normalized language, certification, and work history."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, ReferenceMixin, enum_type
from minori.domain.catalogs import CandidateStatus, LanguageTestType, Program

if TYPE_CHECKING:
    from minori.db.models.match import Match
    from minori.db.models.notification import Notification
    from minori.db.models.placement import Placement

LANGUAGE_CHECK = (
    "(test_type = 'jlpt' AND level IN ('N1','N2','N3','N4','N5')) OR "
    "(test_type = 'jft_basic' AND level IN ('A1','A2.1','A2.2'))"
)


class Candidate(ReferenceMixin, IdentityTimestampMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint("length(trim(reference)) > 0", name="reference_not_blank"),
    )

    full_name: Mapped[str] = mapped_column(String(160))
    preferred_program: Mapped[Program] = mapped_column(
        enum_type(Program, "candidate_program"), index=True
    )
    education_level: Mapped[str] = mapped_column(String(80))
    domicile_city: Mapped[str] = mapped_column(String(80))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[CandidateStatus] = mapped_column(
        enum_type(CandidateStatus, "candidate_status"),
        default=CandidateStatus.REGISTERED,
        index=True,
    )
    language_tests: Mapped[list[CandidateLanguageTest]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    certifications: Mapped[list[CandidateCertification]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    experiences: Mapped[list[CandidateExperience]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    matches: Mapped[list[Match]] = relationship(back_populates="candidate", passive_deletes="all")
    placements: Mapped[list[Placement]] = relationship(
        back_populates="candidate", passive_deletes="all"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="candidate", passive_deletes="all", foreign_keys="Notification.candidate_id"
    )


class CandidateLanguageTest(IdentityTimestampMixin, Base):
    __tablename__ = "candidate_language_tests"
    __table_args__ = (
        UniqueConstraint("candidate_id", "test_type", "taken_on"),
        CheckConstraint(LANGUAGE_CHECK, name="test_level_pair"),
        CheckConstraint(
            "score IS NULL OR (test_type = 'jlpt' AND score BETWEEN 0 AND 180) OR "
            "(test_type = 'jft_basic' AND score BETWEEN 10 AND 250)",
            name="score_range",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    test_type: Mapped[LanguageTestType] = mapped_column(
        enum_type(LanguageTestType, "language_test_type")
    )
    level: Mapped[str] = mapped_column(String(8))
    taken_on: Mapped[date] = mapped_column(Date)
    score: Mapped[int | None]
    candidate: Mapped[Candidate] = relationship(back_populates="language_tests")


class CandidateCertification(IdentityTimestampMixin, Base):
    __tablename__ = "candidate_certifications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "code", "issued_on"),
        CheckConstraint("expires_on IS NULL OR expires_on >= issued_on", name="validity_range"),
        CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    issuer: Mapped[str] = mapped_column(String(160))
    issued_on: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    candidate: Mapped[Candidate] = relationship(back_populates="certifications")


class CandidateExperience(IdentityTimestampMixin, Base):
    __tablename__ = "candidate_experiences"
    __table_args__ = (
        UniqueConstraint("candidate_id", "employer_name", "role", "started_on"),
        CheckConstraint("ended_on IS NULL OR ended_on >= started_on", name="employment_range"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    employer_name: Mapped[str] = mapped_column(String(160))
    sector: Mapped[str] = mapped_column(String(80), index=True)
    role: Mapped[str] = mapped_column(String(120))
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    candidate: Mapped[Candidate] = relationship(back_populates="experiences")
