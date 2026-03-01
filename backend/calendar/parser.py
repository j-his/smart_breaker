"""
Calendar event parser — iCal and JSON formats.

Parses user calendar data into CalendarEvent dataclass instances,
with automatic appliance inference from event titles.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from icalendar import Calendar

from backend import config


@dataclass
class CalendarEvent:
    """A parsed calendar event with energy metadata."""

    title: str
    start: datetime
    end: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: int | None = None
    power_watts: int = 0
    is_deferrable: bool = False
    priority: str = "medium"
    appliance_name: str | None = None

    @property
    def duration_min(self) -> int:
        """Duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)


# ── Appliance inference from event title ─────────────────────────────────────

# Keywords mapped to appliance names (lowercase matching)
_KEYWORD_MAP = {
    "dryer": "dryer",
    "laundry": "dryer",
    "ev": "ev_charger",
    "charger": "ev_charger",
    "charge": "ev_charger",
    "tesla": "ev_charger",
    "dishwasher": "dishwasher",
    "dishes": "dishwasher",
    "water heater": "water_heater",
    "stove": "inductive_stove",
    "cook": "inductive_stove",
    "dinner": "inductive_stove",
    "breakfast": "inductive_stove",
    "lunch": "inductive_stove",
    "oven": "oven",
    "bake": "oven",
    "ac": "air_conditioning",
    "air conditioning": "air_conditioning",
    "cooling": "air_conditioning",
    "light": "lighting",
}


def _guess_appliance(title: str) -> str | None:
    """Infer appliance name from event title keywords."""
    lower = title.lower()
    for keyword, appliance in _KEYWORD_MAP.items():
        if keyword in lower:
            return appliance
    return None


def _apply_appliance_defaults(event: CalendarEvent) -> CalendarEvent:
    """Fill in power_watts, is_deferrable, and appliance_name from config."""
    appliance = _guess_appliance(event.title)
    if appliance:
        event.appliance_name = appliance
        if event.power_watts == 0:
            event.power_watts = config.APPLIANCE_WATTS.get(appliance, 0)
        event.is_deferrable = appliance in config.DEFERRABLE_APPLIANCES
    return event


def parse_ical(ics_data: str) -> list[CalendarEvent]:
    """Parse an iCalendar string into CalendarEvent instances."""
    cal = Calendar.from_ical(ics_data)
    events = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("SUMMARY", "Untitled"))
        dtstart = component.get("DTSTART").dt
        dtend = component.get("DTEND").dt
        uid = str(component.get("UID", uuid.uuid4()))

        # Ensure timezone-aware datetimes
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=timezone.utc)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=timezone.utc)

        event = CalendarEvent(
            title=summary,
            start=dtstart,
            end=dtend,
            id=uid,
        )
        _apply_appliance_defaults(event)
        events.append(event)

    return events


def parse_json_tasks(tasks: list[dict]) -> list[CalendarEvent]:
    """Parse a list of JSON task dicts into CalendarEvent instances."""
    events = []
    for t in tasks:
        start = dateutil_parser.isoparse(t["start"])
        end = dateutil_parser.isoparse(t["end"])

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        event = CalendarEvent(
            title=t.get("title", "Untitled"),
            start=start,
            end=end,
            id=t.get("id", str(uuid.uuid4())),
            channel_id=t.get("channel_id"),
            power_watts=t.get("power_watts", 0),
            is_deferrable=t.get("is_deferrable", False),
            priority=t.get("priority", "medium"),
            appliance_name=t.get("appliance_name"),
        )
        # Only apply defaults if power wasn't explicitly provided
        if event.power_watts == 0:
            _apply_appliance_defaults(event)
        events.append(event)

    return events
