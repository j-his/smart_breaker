"""REST API routes for the EnergyAI backend."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.api.websocket import ws_manager, make_envelope
from backend.ingestion.receiver import (
    sensor_buffer,
    hardware_fallback,
    grid_cache,
    process_sensor_reading,
)
from backend.ingestion.validator import SensorReading
from backend.calendar.parser import CalendarEvent, parse_ical, parse_json_tasks, _apply_appliance_defaults
from backend.calendar.generator import optimized_to_ical
from backend.optimizer.scheduler import run_optimization
from backend.events import event_bus, SETTINGS_CHANGED, SCHEDULE_UPDATED
from backend import config

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api")


# ── Request Models ───────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    title: str
    channel_id: int | None = None
    estimated_watts: int = 0
    estimated_duration_min: int = 60
    deadline: str | None = None
    is_deferrable: bool = True
    priority: str = "medium"


class SettingsRequest(BaseModel):
    alpha: float | None = None
    beta: float | None = None
    narration_enabled: bool | None = None
    voice_id: str | None = None


class CalendarImportRequest(BaseModel):
    ical_data: str | None = None
    json_events: list[dict] | None = None


# ── Module State ─────────────────────────────────────────────────────────────

_state: dict = {
    "calendar_events": [],
    "last_optimization": None,
    "alpha": 0.5,
    "beta": 0.5,
    "insights": [],
    "narration_enabled": True,
    "voice_id": config.ELEVENLABS_VOICE_ID,
}


# ── Helper ───────────────────────────────────────────────────────────────────

def _run_and_cache_optimization(
    grid_forecast: list[dict] | None = None,
    user_patterns: list[dict] | None = None,
) -> dict:
    """Re-run optimizer with current state and cache the result."""
    if not _state["calendar_events"]:
        return _empty_optimization()

    result = run_optimization(
        _state["calendar_events"],
        grid_forecast=grid_forecast,
        alpha=_state["alpha"],
        beta=_state["beta"],
        user_patterns=user_patterns,
    )
    update = result.to_calendar_update()
    _state["last_optimization"] = update
    return update


def _empty_optimization() -> dict:
    return {
        "optimized_events": [],
        "total_savings_cents": 0,
        "total_carbon_avoided_g": 0,
        "optimization_confidence": 0.0,
    }


def record_insight(insight: dict) -> None:
    """Append an insight to the in-memory store (capped at 50)."""
    _state["insights"].append(insight)
    if len(_state["insights"]) > 50:
        _state["insights"] = _state["insights"][-50:]


# ── Endpoints ────────────────────────────────────────────────────────────────

@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "hardware_connected": hardware_fallback.is_hardware_connected,
        "buffer_fill": f"{sensor_buffer.size}/{sensor_buffer.capacity}",
        "ws_clients": ws_manager.client_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/dashboard")
async def dashboard():
    grid = await grid_cache.get_current()
    watts = [0.0, 0.0, 0.0, 0.0]
    if sensor_buffer.size > 0:
        window = sensor_buffer.get_window()
        latest = window[-1]
        watts = [float(latest[i]) for i in range(4)]

    return {
        "current_power": {
            "ch0_watts": watts[0],
            "ch1_watts": watts[1],
            "ch2_watts": watts[2],
            "ch3_watts": watts[3],
            "total_watts": sum(watts),
        },
        "grid": grid,
        "hardware_connected": hardware_fallback.is_hardware_connected,
        "optimization": _state["last_optimization"] or _empty_optimization(),
    }


@api_router.get("/forecast")
async def forecast():
    grid_forecast = await grid_cache.get_forecast()
    return {"grid_forecast_24h": grid_forecast}


@api_router.get("/schedule")
async def schedule():
    return _state["last_optimization"] or _empty_optimization()


@api_router.post("/tasks")
async def add_task(task: TaskRequest):
    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=5)
    end = start + timedelta(minutes=task.estimated_duration_min)

    if task.deadline:
        from dateutil import parser as dateutil_parser
        deadline_dt = dateutil_parser.isoparse(task.deadline)
    else:
        deadline_dt = end + timedelta(hours=12)

    event = CalendarEvent(
        title=task.title,
        start=start,
        end=end,
        channel_id=task.channel_id,
        power_watts=task.estimated_watts,
        is_deferrable=task.is_deferrable,
        priority=task.priority,
    )
    _apply_appliance_defaults(event)
    _state["calendar_events"].append(event)

    try:
        forecast = await grid_cache.get_forecast()
        update = _run_and_cache_optimization(grid_forecast=forecast)
    except Exception:
        logger.warning("Optimization failed after adding task, using empty result", exc_info=True)
        update = _empty_optimization()
    await ws_manager.broadcast(make_envelope("calendar_update", update))
    await event_bus.publish(SCHEDULE_UPDATED, update)

    return {"event_id": event.id, "message": "Task added and schedule re-optimized"}


@api_router.post("/calendar/import")
async def calendar_import(req: CalendarImportRequest):
    if req.ical_data:
        events = parse_ical(req.ical_data)
    elif req.json_events:
        events = parse_json_tasks(req.json_events)
    else:
        raise HTTPException(status_code=400, detail="Provide ical_data or json_events")

    _state["calendar_events"].extend(events)

    try:
        forecast = await grid_cache.get_forecast()
        update = _run_and_cache_optimization(grid_forecast=forecast)
    except Exception:
        logger.warning("Optimization failed after calendar import, using empty result", exc_info=True)
        update = _empty_optimization()
    await ws_manager.broadcast(make_envelope("calendar_update", update))
    await event_bus.publish(SCHEDULE_UPDATED, update)

    deferrable = sum(1 for e in events if e.is_deferrable)
    non_deferrable = len(events) - deferrable
    return {
        "events_imported": len(events),
        "deferrable_events": deferrable,
        "non_deferrable_events": non_deferrable,
        "message": f"Imported {len(events)} events ({deferrable} deferrable, {non_deferrable} fixed). Schedule re-optimized.",
    }


@api_router.post("/sensor")
async def sensor_ingest(reading: SensorReading):
    broadcast = await process_sensor_reading(reading, simulated=False)
    await ws_manager.broadcast(make_envelope("sensor_update", broadcast))
    return {"status": "ok"}


@api_router.post("/settings")
async def update_settings(settings: SettingsRequest):
    if settings.alpha is not None:
        _state["alpha"] = settings.alpha
    if settings.beta is not None:
        _state["beta"] = settings.beta
    if settings.narration_enabled is not None:
        _state["narration_enabled"] = settings.narration_enabled
    if settings.voice_id is not None:
        _state["voice_id"] = settings.voice_id

    await event_bus.publish(SETTINGS_CHANGED, {
        "alpha": _state["alpha"],
        "beta": _state["beta"],
        "narration_enabled": _state["narration_enabled"],
        "voice_id": _state["voice_id"],
    })

    return {
        "alpha": _state["alpha"],
        "beta": _state["beta"],
        "narration_enabled": _state["narration_enabled"],
        "voice_id": _state["voice_id"],
    }


@api_router.get("/voices")
async def get_voices():
    """Return available TTS voices, with the current selection marked."""
    voices = [
        {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "desc": "Warm British Storyteller", "gender": "male"},
        {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "desc": "Mature, Reassuring", "gender": "female"},
        {"id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "desc": "Clear British Educator", "gender": "female"},
        {"id": "cjVigY5qzO86Huf0OWal", "name": "Eric", "desc": "Smooth, Trustworthy", "gender": "male"},
        {"id": "cgSgspJ2msm6clMCkdW9", "name": "Jessica", "desc": "Playful, Bright, Warm", "gender": "female"},
        {"id": "SAz9YHcvj6GT2YYXdXww", "name": "River", "desc": "Relaxed, Neutral", "gender": "neutral"},
        {"id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie", "desc": "Deep Australian", "gender": "male"},
        {"id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "desc": "Professional, Knowledgeable", "gender": "female"},
        {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam", "desc": "Energetic, Young", "gender": "male"},
        {"id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger", "desc": "Laid-Back, Casual", "gender": "male"},
    ]
    return {"voices": voices, "current_voice_id": _state["voice_id"]}


@api_router.get("/insights")
async def get_insights():
    return {"insights": _state["insights"][-20:]}


@api_router.get("/attention")
async def get_attention():
    try:
        from backend.ml.orchestrator import get_latest_result
        result = get_latest_result()
        if result and result.get("attention_weights"):
            return {
                "attention_weights": result["attention_weights"],
                "day_type": result.get("day_type"),
                "anomaly_score": result.get("anomaly_score"),
            }
    except ImportError:
        pass
    return {"attention_weights": [], "message": "No ML data yet"}


@api_router.get("/calendar.ics")
async def calendar_ics():
    """Subscribable iCal feed of the optimized schedule.

    iOS: Settings -> Calendar -> Accounts -> Add Subscribed Calendar
    URL: http://<server-ip>:8000/api/calendar.ics
    """
    opt = _state["last_optimization"]
    if not opt or not opt.get("optimized_events"):
        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//EnergyAI//Optimized Schedule//EN\r\n"
            "VERSION:2.0\r\n"
            "X-WR-CALNAME:SaveBox Calendar\r\n"
            "END:VCALENDAR\r\n"
        )
    else:
        ics_content = optimized_to_ical(opt["optimized_events"])

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="energyai.ics"',
        },
    )
