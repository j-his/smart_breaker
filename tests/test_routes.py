"""Tests for REST API routes."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

from fastapi import FastAPI
from backend.api.routes import api_router


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the API router."""
    _app = FastAPI()
    _app.include_router(api_router)
    return _app


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRoutes:
    """REST API endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """GET /api/health returns status ok with all required keys."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "hardware_connected" in data
        assert "buffer_fill" in data
        assert "ws_clients" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_dashboard_structure(self, client):
        """GET /api/dashboard has current_power, grid, hardware_connected, optimization."""
        resp = await client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_power" in data
        assert "grid" in data
        assert "hardware_connected" in data
        assert "optimization" in data

    @pytest.mark.asyncio
    async def test_forecast_24_items(self, client):
        """GET /api/forecast returns 24 grid forecast entries with tou_period."""
        resp = await client.get("/api/forecast")
        assert resp.status_code == 200
        data = resp.json()
        forecast = data["grid_forecast_24h"]
        assert len(forecast) == 24
        for entry in forecast:
            assert "tou_period" in entry

    @pytest.mark.asyncio
    async def test_schedule_empty_default(self, client):
        """GET /api/schedule returns iOS-aligned field names in empty response."""
        resp = await client.get("/api/schedule")
        assert resp.status_code == 200
        data = resp.json()
        assert "optimized_events" in data
        assert "optimization_confidence" in data
        assert "total_savings_cents" in data

    @pytest.mark.asyncio
    async def test_settings_update(self, client):
        """POST /api/settings updates alpha/beta and echoes values."""
        resp = await client.post("/api/settings", json={"alpha": 0.7, "beta": 0.3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["alpha"] == 0.7
        assert data["beta"] == 0.3

    @pytest.mark.asyncio
    async def test_sensor_endpoint(self, client):
        """POST /api/sensor accepts a valid reading."""
        reading = {
            "device_id": "esp32-test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channels": [
                {"channel_id": 0, "assigned_zone": "kitchen", "assigned_appliance": "inductive_stove", "current_amps": 4.0},
                {"channel_id": 1, "assigned_zone": "laundry_room", "assigned_appliance": "dryer", "current_amps": 20.0},
                {"channel_id": 2, "assigned_zone": "garage", "assigned_appliance": "ev_charger", "current_amps": 0.0},
                {"channel_id": 3, "assigned_zone": "bedroom", "assigned_appliance": "air_conditioning", "current_amps": 15.0},
            ],
        }
        resp = await client.post("/api/sensor", json=reading)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_calendar_import_no_data_400(self, client):
        """POST /api/calendar/import with no data returns 400."""
        resp = await client.post("/api/calendar/import", json={})
        assert resp.status_code == 400
