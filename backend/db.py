"""SQLite persistence layer for EnergyAI sensor data, optimizations, and insights."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import aiosqlite

from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "energyai.db"

# ── Schema ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ch0_watts REAL NOT NULL,
    ch1_watts REAL NOT NULL,
    ch2_watts REAL NOT NULL,
    ch3_watts REAL NOT NULL,
    total_watts REAL NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS optimization_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    n_events INTEGER NOT NULL,
    n_moved INTEGER NOT NULL,
    total_savings_cents REAL NOT NULL,
    total_carbon_avoided_g REAL NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    events_json TEXT
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info'
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_opt_ts ON optimization_log(timestamp);
"""


# ── Init ────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


# ── Writes ──────────────────────────────────────────────────────────────────

async def log_sensor_reading(watts: list[float], simulated: bool = False) -> None:
    """Insert a sensor reading (4 channels + total)."""
    ts = datetime.now(timezone.utc).isoformat()
    w = (watts + [0.0, 0.0, 0.0, 0.0])[:4]
    total = sum(w)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO sensor_log (timestamp, ch0_watts, ch1_watts, ch2_watts, ch3_watts, total_watts, simulated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, w[0], w[1], w[2], w[3], total, int(simulated)),
        )
        await db.commit()


async def log_optimization(result_data: dict) -> None:
    """Insert an optimization result."""
    ts = datetime.now(timezone.utc).isoformat()
    events = result_data.get("optimized_events", [])
    n_events = len(events)
    n_moved = sum(1 for e in events if e.get("was_moved"))
    savings = result_data.get("total_savings_cents", 0.0)
    carbon = result_data.get("total_carbon_avoided_g", 0.0)
    confidence = result_data.get("optimization_confidence", 0.0)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO optimization_log (timestamp, n_events, n_moved, total_savings_cents, total_carbon_avoided_g, confidence, events_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, n_events, n_moved, savings, carbon, confidence, json.dumps(events)),
        )
        await db.commit()


async def log_insight(message: str, category: str, severity: str) -> None:
    """Insert an insight message."""
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO insights (timestamp, message, category, severity) VALUES (?, ?, ?, ?)",
            (ts, message, category, severity),
        )
        await db.commit()


# ── Reads ───────────────────────────────────────────────────────────────────

async def get_recent_sensor_data(hours: int = 24, limit: int = 1440) -> list[dict]:
    """Return recent sensor readings, newest first."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sensor_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_optimization_history(limit: int = 50) -> list[dict]:
    """Return recent optimization runs (without full events JSON)."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, timestamp, n_events, n_moved, total_savings_cents, total_carbon_avoided_g, confidence "
            "FROM optimization_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
