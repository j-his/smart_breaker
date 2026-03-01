"""Tests for the FastAPI main application."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import app


class TestMainApp:
    """FastAPI application tests."""

    def test_app_is_fastapi(self):
        """The app object should be a FastAPI instance."""
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    @pytest.mark.asyncio
    async def test_health_through_app(self):
        """Full integration: GET /api/health through the main app."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """CORS middleware should set Access-Control-Allow-Origin."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.options(
                "/api/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert "access-control-allow-origin" in resp.headers

    @pytest.mark.asyncio
    async def test_health_still_works_after_wiring(self):
        """GET /api/health should still work after event bus + demo mode wiring."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "ws_clients" in data

    @pytest.mark.asyncio
    async def test_cors_still_works_after_wiring(self):
        """CORS should still function correctly after narrator + demo wiring."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.options(
                "/api/dashboard",
                headers={
                    "Origin": "http://192.168.1.100:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert resp.status_code == 200
            assert "access-control-allow-origin" in resp.headers
