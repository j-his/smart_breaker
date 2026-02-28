"""Tests for calendar output generator."""
import pytest
from datetime import datetime, timezone, timedelta

from backend.calendar.generator import (
    optimized_to_ical,
    format_calendar_update_message,
)


@pytest.fixture
def sample_optimized_events():
    """Sample OptimizedEvent dicts for testing output generation."""
    return [
        {
            "event_id": "dryer-001",
            "title": "Run Dryer",
            "original_start": "2026-06-15T18:00:00+00:00",
            "original_end": "2026-06-15T19:00:00+00:00",
            "optimized_start": "2026-06-15T03:00:00+00:00",
            "optimized_end": "2026-06-15T04:00:00+00:00",
            "channel_id": 1,
            "estimated_watts": 2400,
            "savings_cents": 62.4,
            "carbon_avoided_g": 180.0,
            "reason": "",
            "grid_status_at_time": "green",
            "is_deferrable": True,
            "was_moved": True,
        },
        {
            "event_id": "cook-001",
            "title": "Cook Dinner",
            "original_start": "2026-06-15T19:00:00+00:00",
            "original_end": "2026-06-15T20:00:00+00:00",
            "optimized_start": "2026-06-15T19:00:00+00:00",
            "optimized_end": "2026-06-15T20:00:00+00:00",
            "channel_id": 0,
            "estimated_watts": 1800,
            "savings_cents": 0.0,
            "carbon_avoided_g": 0.0,
            "reason": "",
            "grid_status_at_time": "red",
            "is_deferrable": False,
            "was_moved": False,
        },
    ]


class TestCalendarGenerator:
    """Calendar output generation tests."""

    def test_optimized_to_ical_contains_events(self, sample_optimized_events):
        """iCal string should contain a VEVENT for each event."""
        ical_str = optimized_to_ical(sample_optimized_events)

        assert "BEGIN:VCALENDAR" in ical_str
        assert ical_str.count("BEGIN:VEVENT") == len(sample_optimized_events)
        assert "Run Dryer" in ical_str
        assert "Cook Dinner" in ical_str

    def test_moved_event_has_description(self, sample_optimized_events):
        """Events that were moved should include a DESCRIPTION with savings."""
        ical_str = optimized_to_ical(sample_optimized_events)

        # Unfold iCal line continuations (RFC 5545: CRLF + space = continuation)
        unfolded = ical_str.replace("\r\n ", "")

        # The moved event (dryer) should have a description
        assert "DESCRIPTION" in unfolded
        assert "Savings" in unfolded
        assert "Carbon avoided" in unfolded

    def test_format_calendar_update_message_keys(self):
        """WebSocket envelope should have type, timestamp, and data keys."""
        data = {"events": [], "total_savings_cents": 0}
        message = format_calendar_update_message(data)

        assert set(message.keys()) == {"type", "timestamp", "data"}
        assert message["type"] == "calendar_update"
        assert message["data"] is data
