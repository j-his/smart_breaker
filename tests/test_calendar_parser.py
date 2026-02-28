"""Tests for calendar parser — iCal and JSON task parsing."""
import pytest
from datetime import datetime, timezone, timedelta

from backend.calendar.parser import CalendarEvent, parse_ical, parse_json_tasks


# ── iCal test data ───────────────────────────────────────────────────────────
SAMPLE_ICS = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
SUMMARY:Run Dryer
DTSTART:20260615T100000Z
DTEND:20260615T110000Z
UID:test-event-001
END:VEVENT
BEGIN:VEVENT
SUMMARY:Cook Dinner
DTSTART:20260615T190000Z
DTEND:20260615T203000Z
UID:test-event-002
END:VEVENT
END:VCALENDAR
"""


class TestCalendarParser:
    """Calendar parsing tests."""

    def test_parse_ical_event_count(self):
        """Parsing a 2-event ICS string should return 2 events."""
        events = parse_ical(SAMPLE_ICS)
        assert len(events) == 2

    def test_parse_ical_event_fields(self):
        """Parsed iCal events should have correct title, start hour, duration."""
        events = parse_ical(SAMPLE_ICS)
        dryer = next(e for e in events if "Dryer" in e.title)

        assert dryer.title == "Run Dryer"
        assert dryer.start.hour == 10
        assert dryer.duration_min == 60

    def test_parse_json_tasks(self):
        """JSON tasks with explicit power_watts and is_deferrable should parse."""
        tasks = [
            {
                "title": "Run Dryer",
                "start": "2026-06-15T10:00:00Z",
                "end": "2026-06-15T11:00:00Z",
                "power_watts": 2400,
                "is_deferrable": True,
            },
            {
                "title": "Cook Dinner",
                "start": "2026-06-15T19:00:00Z",
                "end": "2026-06-15T20:30:00Z",
                "power_watts": 1800,
                "is_deferrable": False,
            },
        ]
        events = parse_json_tasks(tasks)

        assert len(events) == 2
        dryer = next(e for e in events if "Dryer" in e.title)
        assert dryer.power_watts == 2400
        assert dryer.is_deferrable is True

    def test_calendar_event_duration(self):
        """CalendarEvent duration_min property should compute correctly (90 min)."""
        start = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 15, 11, 30, tzinfo=timezone.utc)
        event = CalendarEvent(
            title="Test Event",
            start=start,
            end=end,
        )
        assert event.duration_min == 90
