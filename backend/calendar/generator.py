"""
Calendar output generator — iCal export and WebSocket message formatting.

Converts OptimizedEvent dicts into iCal format for calendar export
and wraps optimization results in WebSocket envelope format.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from icalendar import Calendar, Event


def optimized_to_ical(events: list[dict]) -> str:
    """Convert OptimizedEvent dicts into an iCal string.

    Each event becomes a VEVENT with SUMMARY, DTSTART, DTEND, UID.
    Moved events get a DESCRIPTION with original time and savings info.
    """
    cal = Calendar()
    cal.add("prodid", "-//EnergyAI//Optimized Schedule//EN")
    cal.add("version", "2.0")

    for evt in events:
        vevent = Event()
        vevent.add("summary", evt["title"])
        vevent.add("uid", evt["event_id"])

        # Parse ISO strings back to datetime
        opt_start = dateutil_parser.isoparse(evt["optimized_start"])
        opt_end = dateutil_parser.isoparse(evt["optimized_end"])
        vevent.add("dtstart", opt_start)
        vevent.add("dtend", opt_end)

        # Annotate moved events
        if evt.get("was_moved", False):
            orig_start = dateutil_parser.isoparse(evt["original_start"])
            desc = (
                f"Originally scheduled: {orig_start.strftime('%H:%M %Z')}\n"
                f"Savings: {evt.get('savings_cents', 0):.1f} cents\n"
                f"Carbon avoided: {evt.get('carbon_avoided_g', 0):.1f}g CO2"
            )
            vevent.add("description", desc)

        cal.add_component(vevent)

    return cal.to_ical().decode("utf-8")


def format_calendar_update_message(optimization_result_data: dict) -> dict:
    """Wrap optimization result data in a WebSocket envelope.

    Returns: {"type": "calendar_update", "timestamp": <ISO UTC>, "data": ...}
    """
    return {
        "type": "calendar_update",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": optimization_result_data,
    }
