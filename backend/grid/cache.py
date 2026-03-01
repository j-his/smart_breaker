"""Grid data cache with configurable TTL and optional WattTime integration."""
import logging
import time
from datetime import datetime, timezone

from backend import config
from backend.grid import tou_rates

logger = logging.getLogger(__name__)


class GridCache:
    """TTL cache for grid data, optionally merging live WattTime carbon data.

    When ENABLE_WATTTIME is True, carbon_intensity comes from the WattTime API.
    TOU prices and renewable_pct always come from the local tou_rates model
    (WattTime doesn't provide price or renewable data).
    Falls back to local simulation if the API call fails.
    """

    def __init__(self, ttl_seconds: int | None = None):
        self._ttl = ttl_seconds or config.GRID_CACHE_TTL_S
        self._snapshot: dict | None = None
        self._forecast: list[dict] | None = None
        self._snapshot_ts: float = 0
        self._forecast_ts: float = 0
        self._watttime = None
        if config.ENABLE_WATTTIME:
            from backend.grid.watttime import WattTimeClient
            self._watttime = WattTimeClient()
            logger.info("GridCache: WattTime integration enabled (region=%s)", config.WATTTIME_REGION)

    async def get_current(self) -> dict:
        """Get current grid snapshot, regenerating if TTL expired."""
        now = time.monotonic()
        if self._snapshot is None or (now - self._snapshot_ts) > self._ttl:
            snapshot = tou_rates.generate_grid_snapshot(
                datetime.now(timezone.utc)
            )
            # Overlay live carbon data from WattTime if available
            if self._watttime:
                try:
                    wt_data = await self._watttime.get_current_index()
                    snapshot["carbon_intensity_gco2_kwh"] = wt_data["carbon_intensity_gco2_kwh"]
                    logger.debug("WattTime carbon: %.1f gCO2/kWh", wt_data["carbon_intensity_gco2_kwh"])
                except Exception as e:
                    logger.warning("WattTime current index failed, using local sim: %s", e)
            self._snapshot = snapshot
            self._snapshot_ts = now
        return self._snapshot

    async def get_forecast(self) -> list[dict]:
        """Get 24h forecast, regenerating if TTL expired."""
        now = time.monotonic()
        if self._forecast is None or (now - self._forecast_ts) > self._ttl:
            forecast = tou_rates.generate_24h_forecast(
                datetime.now(timezone.utc)
            )
            # Overlay live carbon forecast from WattTime if available
            if self._watttime:
                try:
                    wt_forecast = await self._watttime.get_forecast()
                    wt_by_hour = {p["hour"]: p["carbon_intensity_gco2_kwh"] for p in wt_forecast}
                    for item in forecast:
                        if item["hour"] in wt_by_hour:
                            item["carbon_intensity_gco2_kwh"] = wt_by_hour[item["hour"]]
                    logger.debug("WattTime forecast merged (%d hours)", len(wt_by_hour))
                except Exception as e:
                    logger.warning("WattTime forecast failed, using local sim: %s", e)
            self._forecast = forecast
            self._forecast_ts = now
        return self._forecast

    def invalidate(self) -> None:
        """Force cache refresh on next access."""
        self._snapshot = None
        self._forecast = None
        self._snapshot_ts = 0
        self._forecast_ts = 0
