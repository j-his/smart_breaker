"""FastAPI application entry point for EnergyAI backend."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.api.routes import api_router, _state
from backend.api.websocket import ws_manager, make_envelope
from backend.events import (
    event_bus,
    SCHEDULE_UPDATED,
    ANOMALY_DETECTED,
    GRID_STATUS_CHANGED,
)
from backend.ingestion.receiver import (
    hardware_fallback,
    sensor_buffer,
    grid_cache,
    process_sensor_reading,
)
from backend.ingestion.validator import SensorReading
from backend.llm.context import build_system_prompt
from backend.llm.chat import chat_stream
from backend.llm.narrator import on_schedule_updated, on_anomaly_detected, on_grid_shift
from backend.simulator.demo_mode import demo_controller
from backend.db import init_db
from backend.scheduler import optimization_loop, grid_refresh_loop, inference_loop

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
    # Initialize database
    await init_db()

    # Wire narrator event bus subscriptions
    event_bus.subscribe(SCHEDULE_UPDATED, on_schedule_updated)
    event_bus.subscribe(ANOMALY_DETECTED, on_anomaly_detected)
    event_bus.subscribe(GRID_STATUS_CHANGED, on_grid_shift)
    logger.info("Narrator subscribed to event bus")

    # Initialize ML inference pipeline (non-fatal if checkpoint is missing)
    try:
        from backend.ml.orchestrator import init_inference
        init_inference()
        logger.info("ML inference pipeline ready")
    except Exception as e:
        logger.warning("ML inference init skipped: %s", e)

    # Start demo mode if enabled
    if config.DEMO_MODE:
        demo_controller.start(6)
        logger.info("Demo mode started")

    tasks = [
        asyncio.create_task(_synthetic_data_loop()),
        asyncio.create_task(optimization_loop()),
        asyncio.create_task(grid_refresh_loop()),
        asyncio.create_task(inference_loop()),
    ]
    logger.info("EnergyAI backend started (4 background loops)")
    yield

    # Shutdown
    if config.DEMO_MODE:
        demo_controller.stop()
        logger.info("Demo mode stopped")

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
    """LLM chat via Groq streaming with full context."""
    await ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                user_message = msg.get("message", msg.get("text", raw))
            except json.JSONDecodeError:
                user_message = raw

            # Build system prompt from current live state
            sensor_state = None
            if sensor_buffer.size > 0:
                window = sensor_buffer.get_window()
                latest = window[-1]
                sensor_state = {
                    "channels": [
                        {
                            "channel_id": i,
                            "assigned_zone": config.DEFAULT_CHANNEL_ASSIGNMENTS[i]["zone"],
                            "current_watts": float(latest[i]),
                        }
                        for i in range(4)
                    ],
                    "total_watts": float(latest[4]) if len(latest) > 4 else sum(float(latest[i]) for i in range(4)),
                }

            # Get latest ML result if available
            ml_result = None
            try:
                from backend.ml.orchestrator import get_latest_result
                ml_result = get_latest_result()
            except ImportError:
                pass

            system_prompt = build_system_prompt(
                sensor_state=sensor_state,
                grid_status=await grid_cache.get_current(),
                ml_result=ml_result,
                optimization=_state.get("last_optimization"),
                recent_insights=_state.get("insights", []),
            )

            # Stream LLM response
            full_text = ""
            async for chunk in chat_stream(user_message, system_prompt=system_prompt):
                full_text += chunk
                await ws_manager.send_to(
                    websocket,
                    make_envelope("chat_response", {"chunk": chunk, "done": False}),
                )

            # Final message with full text
            await ws_manager.send_to(
                websocket,
                make_envelope("chat_response", {"message": full_text, "done": True}),
            )

            # Speak the response aloud if narration is enabled
            narration_on = _state.get("narration_enabled", True)
            has_text = bool(full_text.strip())
            logger.info("Chat TTS check: narration=%s, has_text=%s, text_len=%d",
                        narration_on, has_text, len(full_text))
            if narration_on and has_text:
                try:
                    import uuid
                    from backend.tts.voice import speak_to_client
                    msg_id = str(uuid.uuid4())[:8]
                    logger.info("Chat TTS: sending %d chars to ElevenLabs (id=%s)", len(full_text), msg_id)
                    await speak_to_client(full_text, websocket, msg_id)
                    logger.info("Chat TTS: complete for id=%s", msg_id)
                except Exception:
                    logger.error("Chat TTS failed", exc_info=True)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
