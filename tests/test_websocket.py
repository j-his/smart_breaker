"""Tests for WebSocket connection manager."""
import pytest
from backend.api.websocket import ConnectionManager, make_envelope


class TestWebSocketManager:
    """ConnectionManager unit tests."""

    def test_manager_starts_empty(self):
        """A new manager should have zero clients."""
        mgr = ConnectionManager()
        assert mgr.client_count == 0

    def test_make_envelope_structure(self):
        """make_envelope should return dict with type, timestamp, data keys."""
        env = make_envelope("test_event", {"key": "value"})
        assert set(env.keys()) == {"type", "timestamp", "data"}

    def test_make_envelope_type(self):
        """make_envelope type field should match the argument."""
        env = make_envelope("sensor_update", {"watts": 1200})
        assert env["type"] == "sensor_update"
        assert env["data"] == {"watts": 1200}
