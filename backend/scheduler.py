"""Background scheduler loops for periodic optimization and grid refresh."""
from __future__ import annotations

import asyncio
import logging

from backend import config
from backend.api.websocket import ws_manager, make_envelope
from backend.api.routes import _state, _run_and_cache_optimization
from backend.db import log_optimization
from backend.events import event_bus, SCHEDULE_UPDATED, GRID_STATUS_CHANGED
from backend.ingestion.receiver import grid_cache, sensor_buffer

logger = logging.getLogger(__name__)

# Track last grid TOU period for change detection
_last_grid_status: str | None = None


async def optimization_loop():
    """Re-run optimizer periodically when calendar events exist."""
    from backend.optimizer.montecarlo import monte_carlo_confidence
    from backend.calendar.optimizer_bridge import events_to_optimizer_tasks
    from backend.db import get_user_patterns
    from backend.ml.orchestrator import get_latest_result

    while True:
        await asyncio.sleep(config.OPTIMIZER_RERUN_INTERVAL_S)
        try:
            if _state["calendar_events"]:
                logger.info("Background optimization triggered (%d events)",
                            len(_state["calendar_events"]))

                # Fetch live grid forecast
                forecast = await grid_cache.get_forecast()

                # Fetch user behavior patterns for current day type
                patterns = []
                try:
                    ml_result = get_latest_result()
                    if ml_result and ml_result.get("day_type"):
                        patterns = await get_user_patterns(ml_result["day_type"])
                except Exception:
                    logger.debug("Pattern fetch failed", exc_info=True)

                # Run MILP in executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                update = await loop.run_in_executor(
                    None, _run_and_cache_optimization, forecast, patterns
                )

                # Run Monte Carlo for real confidence score
                try:
                    from datetime import datetime, timezone
                    base_date = datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0)
                    tasks = events_to_optimizer_tasks(
                        _state["calendar_events"], base_date)
                    mc = await monte_carlo_confidence(
                        tasks, forecast,
                        alpha=_state["alpha"], beta=_state["beta"])
                    update["optimization_confidence"] = mc["confidence"]
                    _state["last_optimization"] = update
                except Exception:
                    logger.debug("Monte Carlo failed, using default confidence",
                                 exc_info=True)

                try:
                    await log_optimization(update)
                except Exception:
                    logger.debug("DB optimization log failed", exc_info=True)
                await ws_manager.broadcast(make_envelope("calendar_update", update))
                await event_bus.publish(SCHEDULE_UPDATED, update)
        except Exception as e:
            logger.error("Optimization loop error: %s", e)


async def grid_refresh_loop():
    """Invalidate grid cache and broadcast fresh data periodically."""
    global _last_grid_status

    while True:
        await asyncio.sleep(config.GRID_CACHE_TTL_S)
        try:
            grid_cache.invalidate()
            grid_data = await grid_cache.get_current()
            forecast = await grid_cache.get_forecast()
            await ws_manager.broadcast(make_envelope("grid_status", {
                "current": grid_data,
                "forecast_next_3h": forecast[:3],
            }))

            # Detect TOU period changes and publish event
            new_status = grid_data.get("tou_period")
            if _last_grid_status is not None and new_status != _last_grid_status:
                await event_bus.publish(GRID_STATUS_CHANGED, {
                    "old_status": _last_grid_status,
                    "new_status": new_status,
                    "tou_price_cents_kwh": grid_data.get("tou_price_cents_kwh", 0),
                })
            _last_grid_status = new_status

            logger.debug("Grid cache refreshed")
        except Exception as e:
            logger.error("Grid refresh loop error: %s", e)


async def inference_loop():
    """Run ML inference periodically when enough sensor data is available."""
    from backend.ml.orchestrator import run_inference

    while True:
        await asyncio.sleep(config.INFERENCE_DEBOUNCE_S)
        try:
            if sensor_buffer.size < 16:
                continue

            buffer_window = sensor_buffer.get_window()
            grid_forecast = await grid_cache.get_forecast()
            cal_events = [
                {"start": e.start, "end": e.end,
                 "channel_id": e.channel_id, "power_watts": e.power_watts}
                for e in _state.get("calendar_events", [])
                if hasattr(e, "start")
            ]
            await run_inference(buffer_window, grid_forecast, cal_events)
        except Exception as e:
            logger.error("Inference loop error: %s", e)
