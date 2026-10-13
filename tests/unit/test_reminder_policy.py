"""Calendar dates, DST boundaries, templates, and lifecycle rules."""

from datetime import UTC, datetime, time, timedelta

import pytest
from minori.core.config import Settings
from minori.domain.catalogs import PlacementStatus, PlacementStepType
from minori.domain.errors import BusinessConflictError
from minori.domain.notification_templates import render_notification
from minori.domain.reminders import PLACEMENT_TRANSITIONS, ReminderPolicy, validate_transition


@pytest.mark.parametrize("dry_run", [True, False])
def test_mailpit_routing_never_uses_candidate_or_demo_override(dry_run):
    policy = ReminderPolicy(
        dry_run=dry_run,
        notification_delivery_mode="mailpit",
        demo_notification_recipient="unused@example.invalid",
    )
    routing = policy.resolve_recipient("DEMO-CAND-TEST")
    assert routing["delivery_allowed"] is (not dry_run)
    assert routing["effective_recipient"] == (None if dry_run else "mailpit@minori.local")
    assert routing["routing_mode"] == ("dry_run" if dry_run else "mailpit")


@pytest.mark.parametrize(
    "kind,expected",
    [
        (PlacementStepType.INTERVIEW, "2026-10-13T02:00:00+00:00"),
        (PlacementStepType.MEDICAL_CHECK, "2026-10-15T02:00:00+00:00"),
    ],
)
def test_calendar_offsets_send_at_nine_jakarta(kind, expected):
    event = datetime.fromisoformat("2026-10-16T14:00:00+07:00")
    assert ReminderPolicy().scheduled_at(event, kind).isoformat() == expected


def test_offset_uses_local_calendar_date_not_utc_or_seventy_two_hours():
    event = datetime.fromisoformat("2026-03-01T00:30:00+07:00")
    expected = datetime.fromisoformat("2026-02-26T09:00:00+07:00")
    assert ReminderPolicy().scheduled_at(event, PlacementStepType.INTERVIEW) == expected
    assert event - timedelta(days=3) != expected


def test_configured_timezone_and_delivery_time():
    policy = ReminderPolicy(timezone="Asia/Tokyo", delivery_time=time(8, 15))
    event = datetime.fromisoformat("2026-01-02T00:15:00+09:00")
    assert policy.scheduled_at(event, PlacementStepType.MEDICAL_CHECK) == datetime.fromisoformat(
        "2026-01-01T08:15:00+09:00"
    )


@pytest.mark.parametrize("event", ["2026-03-11T10:00:00-04:00", "2026-11-04T10:00:00-05:00"])
def test_dst_calendar_day_at_safe_wall_time(event):
    policy = ReminderPolicy(timezone="America/New_York")
    scheduled = policy.scheduled_at(datetime.fromisoformat(event), PlacementStepType.INTERVIEW)
    assert scheduled.hour in {13, 14}


@pytest.mark.parametrize(
    "event,wall",
    [
        ("2026-03-11T10:00:00-04:00", time(2, 30)),
        ("2026-11-04T10:00:00-05:00", time(1, 30)),
    ],
)
def test_ambiguous_or_nonexistent_delivery_wall_time_is_rejected(event, wall):
    with pytest.raises(ValueError, match="ambiguous|exist"):
        ReminderPolicy(timezone="America/New_York", delivery_time=wall).scheduled_at(
            datetime.fromisoformat(event), PlacementStepType.INTERVIEW
        )


def test_retry_backoff_is_exponential_and_bounded():
    policy = ReminderPolicy(retry_base_seconds=60, retry_max_seconds=300)
    assert [policy.backoff(i).total_seconds() for i in range(1, 6)] == [60, 120, 240, 300, 300]


@pytest.mark.parametrize(
    "current,target,allowed",
    [
        (PlacementStatus.PREPARING, PlacementStatus.IN_PROGRESS, True),
        (PlacementStatus.PREPARING, PlacementStatus.COMPLETED, False),
        (PlacementStatus.IN_PROGRESS, PlacementStatus.COMPLETED, True),
        (PlacementStatus.IN_PROGRESS, PlacementStatus.CANCELLED, True),
        (PlacementStatus.CANCELLED, PlacementStatus.PREPARING, False),
        (PlacementStatus.COMPLETED, PlacementStatus.IN_PROGRESS, False),
    ],
)
def test_placement_transition_rules(current, target, allowed):
    if allowed:
        validate_transition(current, target, PLACEMENT_TRANSITIONS)
    else:
        with pytest.raises(BusinessConflictError):
            validate_transition(current, target, PLACEMENT_TRANSITIONS)


@pytest.mark.parametrize(
    "code", ["interview_h3", "medical_h1", "schedule_changed", "schedule_cancelled"]
)
def test_templates_are_indonesian_administrative_and_have_no_medical_results(code):
    message = render_notification(
        code,
        "Kandidat Fiktif",
        {
            "activity": "medical_check" if code == "medical_h1" else "interview",
            "scheduled_at": "2026-10-16T07:00:00+00:00",
            "timezone": "Asia/Jakarta",
            "location": "Ruang Contoh",
        },
    )
    assert "Kandidat Fiktif" in message["body"]
    assert "16-10-2026 14:00 Asia/Jakarta" in message["body"]
    assert "diagnosis" not in message["body"].lower()


@pytest.mark.parametrize(
    "change",
    [
        {"business_timezone": "Invalid/Zone"},
        {"reminder_delivery_time": "09:00:01"},
        {"internal_api_token": "short"},
        {"notification_lease_seconds": 0},
    ],
)
def test_invalid_reminder_settings_are_rejected(change):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **change)


def test_dry_run_is_default_and_token_is_masked():
    settings = Settings(_env_file=None, internal_api_token="x" * 40)
    assert settings.notification_dry_run and settings.business_timezone == "Asia/Jakarta"
    assert "x" * 40 not in repr(settings)
    with pytest.raises(ValueError):
        ReminderPolicy().scheduled_at(datetime(2026, 1, 1), PlacementStepType.INTERVIEW)
    with pytest.raises(ValueError):
        ReminderPolicy().scheduled_at(datetime(2026, 1, 1, tzinfo=UTC), PlacementStepType.DOCUMENTS)
