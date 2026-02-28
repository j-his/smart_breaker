"""Tests for the calendar-optimizer bridge."""
import pytest
from datetime import datetime, timezone, timedelta

from backend.calendar.parser import CalendarEvent
from backend.calendar.optimizer_bridge import (
    events_to_optimizer_tasks,
    optimizer_result_to_events,
)


@pytest.fixture
def base_date():
    return datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_events(base_date):
    """Mix of deferrable and non-deferrable events."""
    return [
        CalendarEvent(
            title="Run Dryer",
            start=base_date + timedelta(hours=18),
            end=base_date + timedelta(hours=19),
            id="dryer-001",
            channel_id=1,
            power_watts=2400,
            is_deferrable=True,
        ),
        CalendarEvent(
            title="Cook Dinner",
            start=base_date + timedelta(hours=19),
            end=base_date + timedelta(hours=20),
            id="cook-001",
            channel_id=0,
            power_watts=1800,
            is_deferrable=False,
        ),
    ]


class TestOptimizerBridge:
    """Calendar ↔ optimizer format conversion tests."""

    def test_events_to_optimizer_tasks_count(self, sample_events, base_date):
        """Should produce one task per event."""
        tasks = events_to_optimizer_tasks(sample_events, base_date)
        assert len(tasks) == len(sample_events)

    def test_deferrable_task_has_flexible_window(self, sample_events, base_date):
        """Deferrable tasks should have earliest_start=0, deadline > original."""
        tasks = events_to_optimizer_tasks(sample_events, base_date)
        dryer = next(t for t in tasks if t["id"] == "dryer-001")

        assert dryer["earliest_start_hour"] == 0
        assert dryer["deadline_hour"] > dryer["original_start_hour"]

    def test_non_deferrable_task_fixed_window(self, sample_events, base_date):
        """Non-deferrable tasks should have earliest = original, deadline = original + duration."""
        tasks = events_to_optimizer_tasks(sample_events, base_date)
        cook = next(t for t in tasks if t["id"] == "cook-001")

        assert cook["earliest_start_hour"] == cook["original_start_hour"]
        assert cook["deadline_hour"] == cook["original_start_hour"] + cook["duration_hours"]

    def test_optimizer_result_to_events_keys(
        self, sample_events, base_date, sample_grid_forecast_24h
    ):
        """Output dicts should have all OptimizedEvent keys."""
        optimizer_results = [
            {"task_id": "dryer-001", "optimized_start_hour": 3, "original_start_hour": 18},
        ]
        output = optimizer_result_to_events(
            sample_events, optimizer_results, base_date, sample_grid_forecast_24h
        )

        expected_keys = {
            "event_id", "title", "original_start", "original_end",
            "optimized_start", "optimized_end", "channel_id",
            "estimated_watts", "savings_cents", "carbon_avoided_g",
            "reason", "grid_status_at_time", "is_deferrable", "was_moved",
        }
        for event_dict in output:
            assert set(event_dict.keys()) == expected_keys
