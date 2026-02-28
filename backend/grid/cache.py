"""Grid data cache with configurable TTL."""
import time
from datetime import datetime, timezone

from backend import config
from backend.grid import tou_rates


class GridCache:
    """Simple TTL cache for grid data to avoid redundant computations."""

    def __init__(self, ttl_seconds: int | None = None):
        self._ttl = ttl_seconds or config.GRID_CACHE_TTL_S
        self._snapshot: dict | None = None
        self._forecast: list[dict] | None = None
        self._snapshot_ts: float = 0
        self._forecast_ts: float = 0

    def get_current(self) -> dict:
        """Get current grid snapshot, regenerating if TTL expired."""
        now = time.monotonic()
        if self._snapshot is None or (now - self._snapshot_ts) > self._ttl:
            self._snapshot = tou_rates.generate_grid_snapshot(
                datetime.now(timezone.utc)
            )
            self._snapshot_ts = now
        return self._snapshot

    def get_forecast(self) -> list[dict]:
        """Get 24h forecast, regenerating if TTL expired."""
        now = time.monotonic()
        if self._forecast is None or (now - self._forecast_ts) > self._ttl:
            self._forecast = tou_rates.generate_24h_forecast(
                datetime.now(timezone.utc)
            )
            self._forecast_ts = now
        return self._forecast

    def invalidate(self) -> None:
        """Force cache refresh on next access."""
        self._snapshot = None
        self._forecast = None
        self._snapshot_ts = 0
        self._forecast_ts = 0
