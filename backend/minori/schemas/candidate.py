"""Candidate and qualification contracts with test-specific language validation."""

from datetime import date
from typing import Self

from pydantic import Field, StrictInt, model_validator

from minori.domain.catalogs import (
    CandidateStatus,
    LanguageTestType,
    Program,
    validate_language_level,
)
from minori.domain.entities import (
    CandidateData,
    CertificationData,
    ExperienceData,
    LanguageTestData,
)
from minori.schemas.common import Code, InputSchema, NonBlank, RecordFields, Reference


class LanguageTestCreate(InputSchema):
    test_type: LanguageTestType
    level: str
    taken_on: date
    score: StrictInt | None = None

    @model_validator(mode="after")
    def validate_test(self) -> Self:
        validate_language_level(self.test_type, self.level)
        maximum = 180 if self.test_type == LanguageTestType.JLPT else 250
        minimum = 0 if self.test_type == LanguageTestType.JLPT else 10
        if self.score is not None and not minimum <= self.score <= maximum:
            raise ValueError("Score is outside this test's scale")
        if self.test_type == LanguageTestType.JFT_BASIC and self.score is not None:
            expected = (
                "A2.2"
                if self.score >= 200
                else ("A2.1" if self.score >= 175 else "A1" if self.score >= 145 else None)
            )
            if self.level != expected:
                raise ValueError("JFT-Basic score and assessed level disagree")
        return self


class CertificationCreate(InputSchema):
    code: Code
    name: NonBlank
    issuer: NonBlank
    issued_on: date
    expires_on: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.expires_on and self.expires_on < self.issued_on:
            raise ValueError("Certification expiry precedes issue date")
        return self


class ExperienceCreate(InputSchema):
    employer_name: NonBlank
    sector: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    started_on: date
    ended_on: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.ended_on and self.ended_on < self.started_on:
            raise ValueError("Employment end precedes its start")
        return self


class CandidateCreate(InputSchema):
    reference: Reference
    full_name: NonBlank
    preferred_program: Program
    education_level: str = Field(min_length=1, max_length=80)
    domicile_city: str = Field(min_length=1, max_length=80)
    status: CandidateStatus = CandidateStatus.REGISTERED
    skills: list[Code] = Field(default_factory=list, max_length=50)
    preferred_prefectures: list[str] = Field(default_factory=list, max_length=47)
    language_tests: list[LanguageTestCreate] = Field(default_factory=list, max_length=30)
    certifications: list[CertificationCreate] = Field(default_factory=list, max_length=50)
    experiences: list[ExperienceCreate] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_unique_children(self) -> Self:
        groups = [
            [(item.test_type, item.taken_on) for item in self.language_tests],
            [(item.code, item.issued_on) for item in self.certifications],
            [(item.employer_name, item.role, item.started_on) for item in self.experiences],
            self.skills,
            [item.casefold() for item in self.preferred_prefectures],
        ]
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("Duplicate candidate qualifications or skills")
        if any(not item.strip() or len(item) > 80 for item in self.preferred_prefectures):
            raise ValueError("Prefecture preferences must contain 1..80 characters")
        self.preferred_prefectures = [item.strip() for item in self.preferred_prefectures]
        return self

    def to_domain(self, data_type=CandidateData) -> CandidateData:
        values = self.model_dump(exclude={"language_tests", "certifications", "experiences"})
        values["skills"] = tuple(self.skills)
        values["preferred_prefectures"] = tuple(self.preferred_prefectures)
        return data_type(
            **values,
            language_tests=tuple(item.to_domain(LanguageTestData) for item in self.language_tests),
            certifications=tuple(item.to_domain(CertificationData) for item in self.certifications),
            experiences=tuple(item.to_domain(ExperienceData) for item in self.experiences),
        )


class CandidateRead(CandidateCreate, RecordFields):
    """Detached aggregate response without recursive ORM relationships."""
