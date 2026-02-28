"""Hardware fallback — generates synthetic sensor data when ESP32 is offline."""
import time
import math
import random
from datetime import datetime, timezone

from backend import config
from backend.ingestion.validator import SensorReading, ChannelReading


class HardwareFallback:
    """Detects ESP32 dropout and generates synthetic readings."""

    def __init__(self, timeout_s: int | None = None):
        self._timeout = timeout_s or config.HARDWARE_TIMEOUT_S
        self._last_real_data: float | None = None

    def record_real_data(self) -> None:
        """Call this when a real hardware reading arrives."""
        self._last_real_data = time.monotonic()

    @property
    def is_hardware_connected(self) -> bool:
        """True if we received real data within the timeout window."""
        if self._last_real_data is None:
            return False
        return (time.monotonic() - self._last_real_data) < self._timeout

    def generate_synthetic_reading(self) -> SensorReading:
        """Generate a plausible synthetic reading based on time-of-day patterns."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Time-of-day usage patterns (fraction of max watts)
        patterns = {
            "inductive_stove": 0.7 if 17 <= hour <= 20 else (0.3 if 7 <= hour <= 9 else 0.0),
            "dryer": 0.8 if 10 <= hour <= 14 else 0.0,
            "ev_charger": 0.9 if 0 <= hour <= 6 else 0.0,
            "air_conditioning": 0.6 if 12 <= hour <= 22 else 0.2,
        }

        channels = []
        for assignment in config.DEFAULT_CHANNEL_ASSIGNMENTS:
            appliance = assignment["appliance"]
            max_watts = config.APPLIANCE_WATTS.get(appliance, 500)
            pattern = patterns.get(appliance, 0.1)

            # Add some noise
            noise = 1.0 + random.uniform(-0.15, 0.15)
            watts = max_watts * pattern * noise
            amps = max(0.0, watts / config.VOLTAGE)

            channels.append(ChannelReading(
                channel_id=assignment["channel_id"],
                assigned_zone=assignment["zone"],
                assigned_appliance=appliance,
                current_amps=round(amps, 2),
            ))

        return SensorReading(
            device_id="synthetic-fallback",
            timestamp=now.isoformat(),
            channels=channels,
        )
