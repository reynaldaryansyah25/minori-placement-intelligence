"""Bounded AI transport contracts with evidence and no publication permissions."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from minori.domain.catalogs import Program
from minori.schemas.common import Code, InputSchema
from minori.schemas.vacancy import LanguageRequirementCreate

Text = Annotated[str, Field(min_length=1, max_length=12000)]
Short = Annotated[str, Field(min_length=1, max_length=160)]
Paragraph = Annotated[str, Field(min_length=1, max_length=2000)]
Items = Annotated[list[Paragraph], Field(max_length=20)]


class TextRequest(InputSchema):
    text: Text


class BatchRequest(InputSchema):
    texts: list[Text] = Field(min_length=1, max_length=5)


class Evidence(InputSchema):
    field: Short
    quote: str = Field(min_length=1, max_length=1000)


class Extraction(InputSchema):
    title: Short | None = None
    employer_name: Short | None = None
    sector: Short | None = None
    program: Program | None = None
    prefecture: Short | None = None
    quota: int | None = Field(default=None, gt=0, le=10000)
    minimum_experience_months: int | None = Field(default=None, ge=0, le=1200)
    language_requirements: list[LanguageRequirementCreate] = Field(
        default_factory=list, max_length=2
    )
    required_skills: list[Code] = Field(default_factory=list, max_length=50)
    preferred_skills: list[Code] = Field(default_factory=list, max_length=50)
    required_certifications: list[Code] = Field(default_factory=list, max_length=50)
    preferred_certifications: list[Code] = Field(default_factory=list, max_length=50)
    application_deadline: AwareDatetime | None = None
    evidence: list[Evidence] = Field(default_factory=list, max_length=40)
    missing_fields: list[Short] = Field(default_factory=list, max_length=20)
    ambiguities: Items = Field(default_factory=list)


class RequirementReview(InputSchema):
    mandatory: Items = Field(default_factory=list)
    preferred: Items = Field(default_factory=list)
    missing: Items = Field(default_factory=list)
    ambiguities: Items = Field(default_factory=list)
    contradictions: Items = Field(default_factory=list)
    questions: Items = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list, max_length=40)


class VacancyAnalysis(InputSchema):
    extraction: Extraction
    translation: str = Field(min_length=1, max_length=16000)
    review: RequirementReview


class MatchingAiRequest(InputSchema):
    candidate_id: UUID
    vacancy_id: UUID


class MatchingNarrative(InputSchema):
    summary: Paragraph
    strengths: Items
    unmet_requirements: Items
    verification_needed: Items
    next_steps: Items


class MatchingAiRead(InputSchema):
    official: dict
    narrative: MatchingNarrative
    facts_fingerprint: str


class EmailWording(InputSchema):
    # The model writes connective language, never the authoritative facts block.
    introduction: str = Field(min_length=1, max_length=500)
    closing: str = Field(min_length=1, max_length=500)


class EmailPreview(InputSchema):
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    facts_fingerprint: str
    schedule_revision: int
    source: Literal["ai", "template"]
    facts: dict


class EmailApproval(InputSchema):
    subject: str = Field(min_length=1, max_length=160, pattern=r"^[^\r\n]+$")
    body: str = Field(min_length=1, max_length=8000)
    facts_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]+$")
    idempotency_key: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    confirmed: Literal[True]


class DocumentRow(InputSchema):
    number: int
    text: Text
    preview: str


class DocumentPreview(InputSchema):
    rows: list[DocumentRow] = Field(max_length=100)
    kind: str
    warning: str | None = None
