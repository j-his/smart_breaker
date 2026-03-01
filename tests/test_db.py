"""Tests for the SQLite persistence layer."""
import pytest
import aiosqlite

from backend.db import (
    init_db,
    log_sensor_reading,
    log_insight,
    log_optimization,
    get_recent_sensor_data,
    get_optimization_history,
)


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp directory for test isolation."""
    monkeypatch.setattr("backend.db.DB_PATH", tmp_path / "test.db")


@pytest.mark.asyncio
async def test_init_db_creates_tables(tmp_path):
    """init_db should create all 4 tables and 2 indexes."""
    await init_db()
    async with aiosqlite.connect(str(tmp_path / "test.db")) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    assert "sensor_log" in tables
    assert "optimization_log" in tables
    assert "insights" in tables
    assert "settings" in tables


@pytest.mark.asyncio
async def test_sensor_reading_roundtrip(tmp_path):
    """log_sensor_reading should persist and get_recent_sensor_data should retrieve."""
    await init_db()
    await log_sensor_reading([500.0, 2400.0, 0.0, 1800.0], simulated=True)
    rows = await get_recent_sensor_data()
    assert len(rows) == 1
    assert rows[0]["ch0_watts"] == 500.0
    assert rows[0]["total_watts"] == 4700.0
    assert rows[0]["simulated"] == 1


@pytest.mark.asyncio
async def test_log_insight_persists(tmp_path):
    """log_insight should write to the insights table."""
    await init_db()
    await log_insight("Grid shifted to off-peak", "grid_status", "info")
    async with aiosqlite.connect(str(tmp_path / "test.db")) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM insights")
        rows = [dict(r) for r in await cursor.fetchall()]
    assert len(rows) == 1
    assert rows[0]["message"] == "Grid shifted to off-peak"
    assert rows[0]["category"] == "grid_status"
    assert rows[0]["severity"] == "info"


@pytest.mark.asyncio
async def test_log_optimization_stores_and_retrieves(tmp_path):
    """log_optimization should persist and get_optimization_history should retrieve."""
    await init_db()
    await log_optimization({
        "optimized_events": [{"title": "Run Dryer", "was_moved": True}],
        "total_savings_cents": 12.5,
        "total_carbon_avoided_g": 150,
        "optimization_confidence": 0.87,
    })
    rows = await get_optimization_history()
    assert len(rows) == 1
    assert rows[0]["n_events"] == 1
    assert rows[0]["n_moved"] == 1
    assert rows[0]["total_savings_cents"] == 12.5
