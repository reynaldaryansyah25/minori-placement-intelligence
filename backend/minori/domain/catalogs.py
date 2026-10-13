"""Business vocabularies and language rules independent of frameworks."""

from enum import StrEnum


class Program(StrEnum):
    TITP = "titp"
    SSW = "ssw"
    ENGINEER = "engineer"


class CandidateStatus(StrEnum):
    REGISTERED = "registered"
    PREPARING = "preparing"
    READY = "ready"
    INACTIVE = "inactive"


class VacancyStatus(StrEnum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class DraftStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    REJECTED = "rejected"


class LanguageTestType(StrEnum):
    JLPT = "jlpt"
    JFT_BASIC = "jft_basic"


LANGUAGE_LEVELS = {
    LanguageTestType.JLPT: ("N5", "N4", "N3", "N2", "N1"),
    LanguageTestType.JFT_BASIC: ("A1", "A2.1", "A2.2"),
}


def validate_language_level(test_type: LanguageTestType, level: str) -> None:
    """Validate the test's own vocabulary without equating different tests."""
    if level not in LANGUAGE_LEVELS[test_type]:
        raise ValueError(f"Invalid level for {test_type.value}: {level}")


class MatchStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchSource(StrEnum):
    MANUAL = "manual"
    IMPORT = "import"


class PlacementStatus(StrEnum):
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PlacementStepType(StrEnum):
    INTERVIEW = "interview"
    MEDICAL_CHECK = "medical_check"
    DOCUMENTS = "documents"
    ORIENTATION = "orientation"
    DEPARTURE = "departure"


class PlacementStepStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class NotificationChannel(StrEnum):
    INTERNAL = "internal"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PROCESSING = "processing"
    SIMULATED = "simulated"
    MISSED = "missed"


class AttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PROCESSING = "processing"
    SIMULATED = "simulated"
    ABANDONED = "abandoned"


class AuditEntityType(StrEnum):
    CANDIDATE = "candidate"
    VACANCY = "vacancy"
    PLACEMENT = "placement"
    NOTIFICATION = "notification"
    MATCH = "match"
    PLACEMENT_STAGE = "placement_stage"
