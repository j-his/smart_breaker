"""FastAPI application entry point for EnergyAI backend."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import api_router
from backend.api.websocket import ws_manager, make_envelope
from backend.ingestion.receiver import (
    hardware_fallback,
    process_sensor_reading,
)
from backend.ingestion.validator import SensorReading
from backend.scheduler import optimization_loop, grid_refresh_loop

logger = logging.getLogger(__name__)


# ── Synthetic Data Loop ──────────────────────────────────────────────────────

async def _synthetic_data_loop():
    """Generate and broadcast synthetic sensor data when hardware is offline."""
    while True:
        await asyncio.sleep(10)
        try:
            if not hardware_fallback.is_hardware_connected:
                reading = hardware_fallback.generate_synthetic_reading()
                broadcast = await process_sensor_reading(reading, simulated=True)
                await ws_manager.broadcast(make_envelope("sensor_update", broadcast))
        except Exception as e:
            logger.error("Synthetic data loop error: %s", e)


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    tasks = [
        asyncio.create_task(_synthetic_data_loop()),
        asyncio.create_task(optimization_loop()),
        asyncio.create_task(grid_refresh_loop()),
    ]
    logger.info("EnergyAI backend started (3 background loops)")
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("EnergyAI backend stopped")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EnergyAI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# ── WebSocket Endpoints ──────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """Real-time sensor and optimization data stream."""
    await ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "sensor_data":
                    reading = SensorReading(**msg["data"])
                    broadcast = await process_sensor_reading(reading, simulated=False)
                    await ws_manager.broadcast(make_envelope("sensor_update", broadcast))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                await ws_manager.send_to(
                    websocket,
                    make_envelope("error", {"message": str(e)}),
                )
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """Placeholder for LLM chat (Task 26)."""
    await ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            await ws_manager.send_to(
                websocket,
                make_envelope("chat_response", {
                    "message": "LLM chat not yet implemented (Task 26)",
                }),
            )
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
