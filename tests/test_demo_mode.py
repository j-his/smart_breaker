"""Tests for demo mode controller."""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from backend.simulator.demo_mode import DemoController


def _mock_dataframe():
    """Create a small mock DataFrame matching parquet schema."""
    n_rows = 1440  # 1 day of minute-level data
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "ch0_watts": rng.uniform(100, 2000, n_rows),
        "ch1_watts": rng.uniform(0, 2400, n_rows),
        "ch2_watts": rng.uniform(0, 3600, n_rows),
        "ch3_watts": rng.uniform(200, 1800, n_rows),
        "total_watts": rng.uniform(300, 9800, n_rows),
        "renewable_pct": rng.uniform(20, 80, n_rows),
        "carbon_intensity": rng.uniform(150, 400, n_rows),
        "tou_price_cents": rng.uniform(10, 40, n_rows),
        "day_type": ["workday"] * n_rows,
        "temperature_f": rng.uniform(55, 95, n_rows),
    })


class TestDemoMode:
    """Tests for DemoController."""

    def test_starts_in_stopped_state(self):
        """New controller should not be running."""
        ctrl = DemoController()
        assert ctrl.is_running is False

    def test_reading_at_time_returns_sensor_reading(self):
        """_reading_at_time should return a SensorReading with 4 channels."""
        ctrl = DemoController()
        ctrl._df = _mock_dataframe()

        reading = ctrl._reading_at_time(360)  # 6:00 AM

        from backend.ingestion.validator import SensorReading
        assert isinstance(reading, SensorReading)
        assert len(reading.channels) == 4
        assert reading.device_id == "demo-replay"
        # Verify watts are reasonable (positive values from our mock data)
        for ch in reading.channels:
            assert ch.current_amps >= 0

    def test_stop_sets_is_running_false(self):
        """stop() should set is_running to False."""
        ctrl = DemoController()
        ctrl.is_running = True
        ctrl.stop()
        assert ctrl.is_running is False

    def test_start_without_parquet_stays_stopped(self):
        """If parquet file doesn't exist, start should log error and not run."""
        ctrl = DemoController()

        with patch("backend.simulator.demo_mode.config") as mock_config:
            from pathlib import Path
            mock_config.DATA_DIR = Path("/nonexistent/path")
            mock_config.DEFAULT_CHANNEL_ASSIGNMENTS = [
                {"channel_id": i, "zone": "test", "appliance": "test"}
                for i in range(4)
            ]
            mock_config.VOLTAGE = 120

            ctrl.start(6)

            assert ctrl.is_running is False
