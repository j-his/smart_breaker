"""Demo mode controller — accelerated replay of synthetic household data.

Replays parquet data at 15 simulated minutes per real second,
generating SensorReading objects and broadcasting via WebSocket.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from backend import config
from backend.api.websocket import ws_manager, make_envelope
from backend.ingestion.receiver import process_sensor_reading
from backend.ingestion.validator import SensorReading, ChannelReading

logger = logging.getLogger(__name__)


class DemoController:
    """Replays synthetic parquet data at accelerated time scale."""

    def __init__(self):
        self.is_running: bool = False
        self._task: asyncio.Task | None = None
        self._df = None  # pandas DataFrame, loaded on start

    def start(self, start_hour: int = 6) -> None:
        """Load parquet and start the replay loop.

        Args:
            start_hour: Simulated starting hour (default 6 AM).
        """
        try:
            import pandas as pd
            parquet_path = config.DATA_DIR / "synthetic_household.parquet"
            if not parquet_path.exists():
                logger.error("Demo parquet not found: %s", parquet_path)
                return
            self._df = pd.read_parquet(parquet_path)
            logger.info("Demo mode loaded %d rows from parquet", len(self._df))
        except Exception as e:
            logger.error("Failed to load demo parquet: %s", e)
            return

        self.is_running = True
        self._start_hour = start_hour
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Demo mode started at hour %d", start_hour)

    def stop(self) -> None:
        """Stop the replay loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("Demo mode stopped")

    async def _run_loop(self) -> None:
        """Main loop: advance 15 simulated minutes every real second."""
        sim_minutes = self._start_hour * 60  # start at configured hour

        while self.is_running:
            try:
                reading = self._reading_at_time(sim_minutes)
                broadcast = await process_sensor_reading(reading, simulated=True)
                await ws_manager.broadcast(make_envelope("sensor_update", broadcast))

                # Advance 15 simulated minutes
                sim_minutes += 15

                # Wrap at midnight (1440 min) → back to start hour
                if sim_minutes >= 1440:
                    sim_minutes = self._start_hour * 60
                    logger.debug("Demo mode wrapped to hour %d", self._start_hour)

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Demo loop error: %s", e)
                await asyncio.sleep(1)

    def _reading_at_time(self, sim_minutes: int) -> SensorReading:
        """Extract a SensorReading from parquet at the given simulated minute.

        The parquet has 86,400 rows (60 days × 1440 min/day).
        We use sim_minutes as offset within a single day, picking a random day.
        """
        rows_per_day = 1440
        total_days = len(self._df) // rows_per_day if self._df is not None else 1

        # Cycle through days based on how many times we've wrapped
        day = 0  # use first day by default
        row_idx = (day * rows_per_day + sim_minutes) % len(self._df)
        row = self._df.iloc[row_idx]

        channels = []
        for i in range(4):
            col = f"ch{i}_watts"
            watts = float(row[col]) if col in row.index else 0.0
            assignment = config.DEFAULT_CHANNEL_ASSIGNMENTS[i]
            channels.append(ChannelReading(
                channel_id=i,
                assigned_zone=assignment["zone"],
                assigned_appliance=assignment["appliance"],
                current_amps=watts / config.VOLTAGE,
            ))

        return SensorReading(
            device_id="demo-replay",
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels=channels,
        )


# Singleton instance
demo_controller = DemoController()
