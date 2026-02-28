"""Tests for the optimization orchestrator."""
import pytest
from datetime import datetime, timezone, timedelta

from backend.calendar.parser import CalendarEvent
from backend.optimizer.scheduler import run_optimization


@pytest.fixture
def mixed_events():
    """A mix of deferrable and non-deferrable events for end-to-end testing."""
    now = datetime.now(timezone.utc)
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        CalendarEvent(
            title="Run Dryer",
            start=base + timedelta(hours=18),
            end=base + timedelta(hours=19),
            id="dryer-e2e",
            channel_id=1,
            power_watts=2400,
            is_deferrable=True,
        ),
        CalendarEvent(
            title="Cook Dinner",
            start=base + timedelta(hours=19),
            end=base + timedelta(hours=20),
            id="cook-e2e",
            channel_id=0,
            power_watts=1800,
            is_deferrable=False,
        ),
        CalendarEvent(
            title="Charge EV",
            start=base + timedelta(hours=21),
            end=base + timedelta(hours=25),
            id="ev-e2e",
            channel_id=2,
            power_watts=3600,
            is_deferrable=True,
        ),
    ]


class TestOrchestrator:
    """End-to-end optimization pipeline tests."""

    def test_run_optimization_returns_result(self, mixed_events):
        """run_optimization should return an OptimizationResult with events."""
        result = run_optimization(mixed_events)
        assert result.events is not None
        assert len(result.events) == len(mixed_events)

    def test_optimization_has_savings(self, mixed_events):
        """total_savings_cents should be >= 0."""
        result = run_optimization(mixed_events)
        assert result.total_savings_cents >= 0

    def test_to_calendar_update_keys(self, mixed_events):
        """to_calendar_update() should have the required WebSocket schema keys."""
        result = run_optimization(mixed_events)
        update = result.to_calendar_update()

        expected_keys = {"type", "events", "total_savings_cents",
                         "total_carbon_avoided_g", "confidence"}
        assert set(update.keys()) == expected_keys
        assert update["type"] == "calendar_update"
