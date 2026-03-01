"""Tests for the ingestion layer: validator, buffer, and fallback."""
import pytest
import numpy as np
from datetime import datetime, timezone

from backend.ingestion.validator import SensorReading, ChannelReading
from backend.ingestion.buffer import SensorBuffer
from backend.ingestion.fallback import HardwareFallback


def _make_channels(amps: list[float] | None = None):
    """Helper to create 4 ChannelReading dicts."""
    if amps is None:
        amps = [4.32, 20.0, 0.0, 15.0]
    assignments = [
        ("kitchen", "inductive_stove"),
        ("laundry_room", "dryer"),
        ("garage", "ev_charger"),
        ("bedroom", "air_conditioning"),
    ]
    return [
        {
            "channel_id": i,
            "assigned_zone": zone,
            "assigned_appliance": appliance,
            "current_amps": amps[i],
        }
        for i, (zone, appliance) in enumerate(assignments)
    ]


class TestValidator:
    """SensorReading validation tests."""

    def test_sensor_reading_validation(self):
        """Valid SensorReading with 4 channels parses correctly."""
        reading = SensorReading(
            device_id="esp32-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels=_make_channels(),
        )
        assert reading.device_id == "esp32-test"
        assert len(reading.channels) == 4

    def test_sensor_reading_wrong_channel_count(self):
        """SensorReading with != 4 channels raises ValueError."""
        with pytest.raises(ValueError, match="Expected 4 channels"):
            SensorReading(
                device_id="esp32-test",
                timestamp=datetime.now(timezone.utc).isoformat(),
                channels=_make_channels()[:2],  # only 2 channels
            )

    def test_to_watts_list(self):
        """to_watts_list converts amps to watts via 120V multiplication."""
        reading = SensorReading(
            device_id="esp32-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels=_make_channels([10.0, 20.0, 0.0, 5.0]),
        )
        watts = reading.to_watts_list()
        assert watts == [1200.0, 2400.0, 0.0, 600.0]

    def test_to_broadcast_dict_keys(self):
        """Broadcast dict channels must have iOS-expected keys."""
        reading = SensorReading(
            device_id="esp32-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            channels=_make_channels(),
        )
        broadcast = reading.to_broadcast_dict(simulated=False)

        assert "channels" in broadcast
        for ch in broadcast["channels"]:
            assert "assigned_zone" in ch
            assert "assigned_appliance" in ch
            assert "current_watts" in ch
            assert "is_active" in ch


    def test_channel_reading_without_zone_appliance(self):
        """ChannelReading with just channel_id + current_amps fills defaults from config."""
        ch = ChannelReading(channel_id=0, current_amps=10.0)
        assert ch.assigned_zone == "kitchen"
        assert ch.assigned_appliance == "inductive_stove"
        assert ch.get_watts() == 1200.0

    def test_channel_reading_with_power_watts(self):
        """When power_watts is provided, get_watts() returns it directly."""
        ch = ChannelReading(
            channel_id=1,
            assigned_zone="laundry_room",
            assigned_appliance="dryer",
            current_amps=20.0,
            power_watts=2500.0,
        )
        # Should use power_watts, not amps * voltage
        assert ch.get_watts() == 2500.0


class TestBuffer:
    """SensorBuffer ring buffer tests."""

    def test_buffer_add_and_size(self):
        """Adding readings increments size."""
        buf = SensorBuffer(window_size=10, n_features=8)
        buf.add([1.0] * 8)
        buf.add([2.0] * 8)
        assert buf.size == 2

    def test_buffer_is_full(self):
        """Buffer reports full when filled to capacity."""
        buf = SensorBuffer(window_size=3, n_features=8)
        for i in range(3):
            buf.add([float(i)] * 8)
        assert buf.is_full

    def test_buffer_get_window_shape(self):
        """get_window returns numpy array of shape (window_size, n_features)."""
        buf = SensorBuffer(window_size=10, n_features=8)
        buf.add([1.0] * 8)
        window = buf.get_window()
        assert isinstance(window, np.ndarray)
        assert window.shape == (10, 8)


class TestFallback:
    """HardwareFallback synthetic data tests."""

    def test_fallback_not_connected_initially(self):
        """Fallback reports not connected before any real data arrives."""
        fb = HardwareFallback(timeout_s=300)
        assert fb.is_hardware_connected is False

    def test_fallback_generates_valid_reading(self):
        """Synthetic reading has 4 channels."""
        fb = HardwareFallback(timeout_s=300)
        reading = fb.generate_synthetic_reading()
        assert len(reading.channels) == 4
        assert reading.device_id == "synthetic-fallback"
