"""Calendar-based demo remains executable before/at/after the delivery hour."""

from datetime import UTC, datetime

import pytest
from minori.domain.catalogs import PlacementStepType
from minori.domain.reminders import ReminderPolicy

from scripts.prepare_reminder_demo import activity_times


@pytest.mark.parametrize("hour,minute", [(0, 0), (8, 59), (9, 0), (14, 0), (23, 59)])
def test_both_demo_events_are_future_and_reminders_are_due(hour, minute):
    now = datetime.fromisoformat(f"2026-10-14T{hour:02}:{minute:02}:00+07:00").astimezone(UTC)
    schedules = activity_times(now)
    assert schedules == activity_times(now)
    for kind, event in schedules.items():
        assert ReminderPolicy().scheduled_at(event, PlacementStepType(kind)) <= now < event
