"""
Bridge between calendar events and the MILP optimizer format.

Converts CalendarEvent instances into optimizer task dicts (for input)
and converts optimizer results back into OptimizedEvent dicts (for output).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.calendar.parser import CalendarEvent
from backend.config import APPLIANCE_TIME_WINDOWS


def events_to_optimizer_tasks(
    events: list[CalendarEvent],
    base_date: datetime,
) -> list[dict]:
    """Convert CalendarEvent list into optimizer task dicts for the MILP solver.

    Each task dict has: id, title, channel_id, power_watts, duration_min,
    duration_hours, original_start_hour, earliest_start_hour, deadline_hour.

    Deferrable tasks are clamped to appliance time windows so the solver
    never schedules, e.g., a dryer run at 3 AM.
    """
    tasks = []
    for event in events:
        original_start_hour = int(
            (event.start - base_date).total_seconds() / 3600
        )
        duration_min = event.duration_min
        duration_hours = max(1, (duration_min + 59) // 60)  # ceil to full hours

        if event.is_deferrable:
            earliest_start_hour = 0
            deadline_hour = min(original_start_hour + duration_hours + 12, 48)

            # Clamp to appliance time window (e.g., dryer only 7am-10pm)
            if event.appliance_name and event.appliance_name in APPLIANCE_TIME_WINDOWS:
                win_start, win_end = APPLIANCE_TIME_WINDOWS[event.appliance_name]
                # Clamp earliest to today's window start
                earliest_start_hour = max(earliest_start_hour, win_start)
                # Clamp deadline to today's window end first;
                # if that's too tight, allow tomorrow's window
                today_end = win_end
                tomorrow_end = 24 + win_end
                if deadline_hour <= today_end or today_end - earliest_start_hour >= duration_hours:
                    deadline_hour = min(deadline_hour, today_end)
                else:
                    # Task can't fit today — push to tomorrow's window
                    earliest_start_hour = 24 + win_start
                    deadline_hour = min(deadline_hour, tomorrow_end)
                # Safety: ensure there's room for the task
                if deadline_hour - earliest_start_hour < duration_hours:
                    deadline_hour = earliest_start_hour + duration_hours
        else:
            earliest_start_hour = original_start_hour
            deadline_hour = original_start_hour + duration_hours

        tasks.append({
            "id": event.id,
            "title": event.title,
            "channel_id": event.channel_id,
            "power_watts": event.power_watts,
            "duration_min": duration_min,
            "duration_hours": duration_hours,
            "original_start_hour": original_start_hour,
            "earliest_start_hour": earliest_start_hour,
            "deadline_hour": deadline_hour,
        })
    return tasks


def optimizer_result_to_events(
    original_events: list[CalendarEvent],
    optimizer_results: list[dict],
    base_date: datetime,
    grid_forecast: list[dict],
) -> list[dict]:
    """Convert MILP results back into OptimizedEvent dicts for the frontend.

    Returns dicts matching the WebSocket calendar_update schema.
    """
    # Index optimizer results by task_id
    result_map = {r["task_id"]: r for r in optimizer_results}

    optimized = []
    for event in original_events:
        result = result_map.get(event.id)
        if result:
            opt_start_hour = result["optimized_start_hour"]
        else:
            # Non-deferrable or not in results — keep original
            opt_start_hour = int(
                (event.start - base_date).total_seconds() / 3600
            )

        original_start_hour = int(
            (event.start - base_date).total_seconds() / 3600
        )
        was_moved = opt_start_hour != original_start_hour

        opt_start_dt = base_date + timedelta(hours=opt_start_hour)
        opt_end_dt = opt_start_dt + timedelta(minutes=event.duration_min)

        # Calculate savings and carbon avoided
        savings_cents = 0.0
        carbon_avoided_g = 0.0
        grid_status = "yellow"

        if grid_forecast and was_moved:
            orig_hour_idx = original_start_hour % len(grid_forecast)
            opt_hour_idx = opt_start_hour % len(grid_forecast)
            orig_slot = grid_forecast[orig_hour_idx]
            opt_slot = grid_forecast[opt_hour_idx]

            duration_hours = max(1, (event.duration_min + 59) // 60)
            kwh = event.power_watts * duration_hours / 1000.0

            orig_price = orig_slot.get("tou_price_cents_kwh", 0)
            opt_price = opt_slot.get("tou_price_cents_kwh", 0)
            savings_cents = round((orig_price - opt_price) * kwh, 2)

            # Carbon key — use the renamed key
            orig_carbon = orig_slot.get(
                "carbon_intensity_gco2_kwh",
                orig_slot.get("carbon_intensity", 0),
            )
            opt_carbon = opt_slot.get(
                "carbon_intensity_gco2_kwh",
                opt_slot.get("carbon_intensity", 0),
            )
            carbon_avoided_g = round((orig_carbon - opt_carbon) * kwh, 2)

            grid_status = opt_slot.get("status", "yellow")
        elif grid_forecast:
            hour_idx = opt_start_hour % len(grid_forecast)
            grid_status = grid_forecast[hour_idx].get("status", "yellow")

        optimized.append({
            "event_id": event.id,
            "title": event.title,
            "original_start": event.start.isoformat(),
            "original_end": event.end.isoformat(),
            "optimized_start": opt_start_dt.isoformat(),
            "optimized_end": opt_end_dt.isoformat(),
            "channel_id": event.channel_id,
            "estimated_watts": event.power_watts,
            "savings_cents": savings_cents,
            "carbon_avoided_g": carbon_avoided_g,
            "reason": f"Moved to {grid_status} period (hour {opt_start_hour}) saving {savings_cents:.0f}¢" if was_moved else "Kept at original time",
            "grid_status_at_time": grid_status,
            "is_deferrable": event.is_deferrable,
            "was_moved": was_moved,
        })

    return optimized
