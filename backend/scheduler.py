"""Background scheduler loops for periodic optimization and grid refresh."""
from __future__ import annotations

import asyncio
import logging

from backend import config
from backend.api.websocket import ws_manager, make_envelope
from backend.api.routes import _state, _run_and_cache_optimization
from backend.ingestion.receiver import grid_cache

logger = logging.getLogger(__name__)


async def optimization_loop():
    """Re-run optimizer periodically when calendar events exist."""
    while True:
        await asyncio.sleep(config.OPTIMIZER_RERUN_INTERVAL_S)
        try:
            if _state["calendar_events"]:
                logger.info("Background optimization triggered (%d events)",
                            len(_state["calendar_events"]))
                update = _run_and_cache_optimization()
                await ws_manager.broadcast(make_envelope("calendar_update", update))
        except Exception as e:
            logger.error("Optimization loop error: %s", e)


async def grid_refresh_loop():
    """Invalidate grid cache and broadcast fresh data periodically."""
    while True:
        await asyncio.sleep(config.GRID_CACHE_TTL_S)
        try:
            grid_cache.invalidate()
            grid_data = grid_cache.get_current()
            await ws_manager.broadcast(make_envelope("grid_status", grid_data))
            logger.debug("Grid cache refreshed")
        except Exception as e:
            logger.error("Grid refresh loop error: %s", e)
