"""REST API routes for the EnergyAI backend."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.websocket import ws_manager, make_envelope
from backend.ingestion.receiver import (
    sensor_buffer,
    hardware_fallback,
    grid_cache,
    process_sensor_reading,
)
from backend.ingestion.validator import SensorReading
from backend.calendar.parser import CalendarEvent, parse_ical, parse_json_tasks
from backend.optimizer.scheduler import run_optimization
from backend.events import event_bus, SETTINGS_CHANGED

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
}


# ── Helper ───────────────────────────────────────────────────────────────────

def _run_and_cache_optimization() -> dict:
    """Re-run optimizer with current state and cache the result."""
    if not _state["calendar_events"]:
        return _empty_optimization()

    result = run_optimization(
        _state["calendar_events"],
        alpha=_state["alpha"],
        beta=_state["beta"],
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


# ── Endpoints ────────────────────────────────────────────────────────────────

@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "hardware_connected": hardware_fallback.is_hardware_connected,
        "buffer_fill": sensor_buffer.size,
        "ws_clients": ws_manager.client_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/dashboard")
async def dashboard():
    grid = grid_cache.get_current()
    watts = [0.0, 0.0, 0.0, 0.0]
    if sensor_buffer.size > 0:
        window = sensor_buffer.get_window()
        latest = window[-1]
        watts = [float(latest[i]) for i in range(4)]

    return {
        "current_power": {
            "ch0": watts[0],
            "ch1": watts[1],
            "ch2": watts[2],
            "ch3": watts[3],
            "total": sum(watts),
        },
        "grid": grid,
        "hardware_connected": hardware_fallback.is_hardware_connected,
        "optimization": _state["last_optimization"] or _empty_optimization(),
    }


@api_router.get("/forecast")
async def forecast():
    grid_forecast = grid_cache.get_forecast()
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
    _state["calendar_events"].append(event)

    update = _run_and_cache_optimization()
    await ws_manager.broadcast(make_envelope("calendar_update", update))

    return {"status": "ok", "event_id": event.id, "optimization": update}


@api_router.post("/calendar/import")
async def calendar_import(req: CalendarImportRequest):
    if req.ical_data:
        events = parse_ical(req.ical_data)
    elif req.json_events:
        events = parse_json_tasks(req.json_events)
    else:
        raise HTTPException(status_code=400, detail="Provide ical_data or json_events")

    _state["calendar_events"].extend(events)

    update = _run_and_cache_optimization()
    await ws_manager.broadcast(make_envelope("calendar_update", update))

    return {"status": "ok", "imported": len(events), "optimization": update}


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

    await event_bus.publish(SETTINGS_CHANGED, {
        "alpha": _state["alpha"],
        "beta": _state["beta"],
    })

    return {
        "status": "ok",
        "alpha": _state["alpha"],
        "beta": _state["beta"],
    }


@api_router.get("/insights")
async def get_insights():
    return {"insights": _state["insights"][-20:]}


@api_router.get("/attention")
async def get_attention():
    return {"attention_weights": [], "message": "Placeholder for ML attention visualization"}
