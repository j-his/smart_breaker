"""LLM narrator — event-driven insight generation.

Subscribes to event bus events and generates human-readable insights
using the LLM, then broadcasts them via WebSocket and optionally TTS.
"""
from __future__ import annotations

import logging
import uuid

from backend import config
from backend.api.websocket import ws_manager, make_envelope
from backend.db import log_insight
from backend.events import Event
from backend.llm.chat import chat_completion

logger = logging.getLogger(__name__)


async def on_schedule_updated(event: Event) -> None:
    """Handle SCHEDULE_UPDATED events — generate insight about moved tasks."""
    data = event.data
    optimized = data.get("optimized_events", [])

    # Find tasks that were actually moved
    moved = [
        e for e in optimized
        if e.get("optimized_start_hour") != e.get("original_start_hour")
    ]

    if not moved:
        logger.debug("Schedule updated but no tasks were moved, skipping insight")
        return

    titles = ", ".join(e.get("title", "task") for e in moved)
    savings = data.get("total_savings_cents", 0)
    carbon = data.get("total_carbon_avoided_g", 0)

    prompt = (
        f"The optimizer just rescheduled these tasks: {titles}. "
        f"Estimated savings: {savings:.1f} cents, {carbon:.0f}g CO2 avoided. "
        "Write a brief, friendly 1-2 sentence insight for the homeowner."
    )

    insight = await _generate_insight(
        prompt, category="schedule_optimization", severity="info"
    )
    await _broadcast_and_speak(insight)


async def on_anomaly_detected(event: Event) -> None:
    """Handle ANOMALY_DETECTED events — warn about unusual power usage."""
    data = event.data
    channel = data.get("channel_id", "unknown")
    watts = data.get("watts", 0)
    expected = data.get("expected_watts", 0)

    prompt = (
        f"An anomaly was detected on channel {channel}: "
        f"current usage is {watts}W vs expected {expected}W. "
        "Write a brief, helpful 1-2 sentence warning for the homeowner."
    )

    insight = await _generate_insight(
        prompt, category="anomaly", severity="warning"
    )
    await _broadcast_and_speak(insight)


async def on_grid_shift(event: Event) -> None:
    """Handle GRID_STATUS_CHANGED events — inform about grid status changes."""
    data = event.data
    old_status = data.get("old_status", "unknown")
    new_status = data.get("new_status", "unknown")
    price = data.get("tou_price_cents_kwh", 0)

    prompt = (
        f"Grid status changed from {old_status} to {new_status} "
        f"(current price: {price}¢/kWh). "
        "Write a brief, actionable 1-2 sentence insight for the homeowner."
    )

    insight = await _generate_insight(
        prompt, category="grid_status", severity="info"
    )
    await _broadcast_and_speak(insight)


async def _generate_insight(
    prompt: str,
    category: str,
    severity: str,
) -> dict:
    """Generate an insight dict via LLM, with fallback on failure.

    Returns:
        {message, category, severity, insight_id}
    """
    insight_id = str(uuid.uuid4())[:8]

    try:
        message = await chat_completion(
            user_message=prompt,
            system_prompt=(
                "You are EnergyAI's narrator. Generate concise, friendly insights "
                "about home energy events. Keep responses to 1-2 sentences."
            ),
            model=config.LLM_NARRATOR_MODEL,
            temperature=0.6,
            max_tokens=150,
        )
    except Exception as e:
        logger.error("Narrator LLM failed: %s", e)
        message = f"Energy update: {prompt[:100]}"

    return {
        "message": message,
        "category": category,
        "severity": severity,
        "insight_id": insight_id,
    }


async def _broadcast_and_speak(insight: dict) -> None:
    """Broadcast insight via WebSocket, persist to DB, then trigger TTS if enabled."""
    await ws_manager.broadcast(make_envelope("insight", insight))
    logger.info("Narrator insight [%s]: %s", insight["category"], insight["message"][:80])

    try:
        await log_insight(insight["message"], insight["category"], insight["severity"])
    except Exception:
        logger.debug("DB insight log failed", exc_info=True)

    # Lazy import to avoid circular dependency between llm/ and tts/
    if config.ELEVENLABS_TTS_ENABLED and config.ELEVENLABS_API_KEY:
        try:
            from backend.tts.voice import speak_insight
            await speak_insight(insight["message"], insight["insight_id"])
        except Exception as e:
            logger.warning("TTS failed for insight %s: %s", insight["insight_id"], e)
