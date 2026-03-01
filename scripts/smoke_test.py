"""
End-to-end smoke test for EnergyAI REST API.

Requires the server to be running: uvicorn backend.main:app --port 8000
Tests all 9 REST endpoints against a live server.

Usage:
    cd smart_breaker/
    python scripts/smoke_test.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'backend' imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

BASE_URL = "http://localhost:8000"
passed = 0
failed = 0


async def test(name: str, coro):
    """Run a single test, catch exceptions gracefully."""
    global passed, failed
    try:
        await coro
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1


async def run_smoke_tests():
    global passed, failed

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as c:
        print("\nEnergyAI Smoke Test")
        print("=" * 50)

        # 1. Health check
        async def t1():
            r = await c.get("/api/health")
            assert r.status_code == 200, f"status {r.status_code}"
            assert r.json()["status"] == "ok", f"got {r.json()}"
        await test("GET /api/health", t1())

        # 2. Dashboard
        async def t2():
            r = await c.get("/api/dashboard")
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            assert "current_power" in d, "missing current_power"
            assert "grid" in d, "missing grid"
            print(f"         total power: {d['current_power']['total']} W")
        await test("GET /api/dashboard", t2())

        # 3. Forecast
        async def t3():
            r = await c.get("/api/forecast")
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            assert len(d["grid_forecast_24h"]) == 24, f"got {len(d['grid_forecast_24h'])} hours"
        await test("GET /api/forecast", t3())

        # 4. Calendar import
        async def t4():
            events = [
                {"title": "Run Dishwasher", "start": "2026-03-01T10:00:00Z", "end": "2026-03-01T11:00:00Z",
                 "power_watts": 1200, "channel_id": 0, "is_deferrable": True},
                {"title": "Charge EV", "start": "2026-03-01T22:00:00Z", "end": "2026-03-02T06:00:00Z",
                 "power_watts": 3600, "channel_id": 2, "is_deferrable": True},
                {"title": "Cook Dinner", "start": "2026-03-01T18:00:00Z", "end": "2026-03-01T19:00:00Z",
                 "power_watts": 1800, "channel_id": 0, "is_deferrable": False},
            ]
            r = await c.post("/api/calendar/import", json={"json_events": events})
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            print(f"         imported: {d['imported']} events")
        await test("POST /api/calendar/import", t4())

        # 5. Schedule
        async def t5():
            r = await c.get("/api/schedule")
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            assert "optimized_events" in d, f"missing optimized_events, got keys: {list(d.keys())}"
        await test("GET /api/schedule", t5())

        # 6. Add task
        async def t6():
            r = await c.post("/api/tasks", json={
                "title": "Run Dryer",
                "estimated_watts": 2400,
                "estimated_duration_min": 60,
                "channel_id": 1,
                "is_deferrable": True,
                "priority": 3,
            })
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            print(f"         task status: {d['status']}")
        await test("POST /api/tasks", t6())

        # 7. Settings
        async def t7():
            r = await c.post("/api/settings", json={"alpha": 0.7, "beta": 0.3})
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            assert d["alpha"] == 0.7, f"alpha={d.get('alpha')}"
            assert d["beta"] == 0.3, f"beta={d.get('beta')}"
        await test("POST /api/settings", t7())

        # 8. Sensor ingest
        async def t8():
            r = await c.post("/api/sensor", json={
                "device_id": "smoke-test",
                "channels": [
                    {"channel_id": 0, "current_amps": 10.0, "power_watts": 1200.0},
                    {"channel_id": 1, "current_amps": 20.0, "power_watts": 2400.0},
                    {"channel_id": 2, "current_amps": 0.0, "power_watts": 0.0},
                    {"channel_id": 3, "current_amps": 15.0, "power_watts": 1800.0},
                ],
            })
            assert r.status_code == 200, f"status {r.status_code}"
        await test("POST /api/sensor", t8())

        # 9. Insights
        async def t9():
            r = await c.get("/api/insights")
            assert r.status_code == 200, f"status {r.status_code}"
            d = r.json()
            print(f"         insights count: {len(d['insights'])}")
        await test("GET /api/insights", t9())

    # Summary
    print("=" * 50)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print("SMOKE TEST FAILED")
        sys.exit(1)
    else:
        print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(run_smoke_tests())
