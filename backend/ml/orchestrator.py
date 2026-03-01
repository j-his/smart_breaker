"""ML inference orchestrator — glue between sensor buffer, feature engine, model, and event bus.

Bridges the gap between raw sensor data arriving in the ring buffer and the
three-brain architecture: runs the TFT model, publishes results as events,
and exposes the latest result for API endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from backend import config
from backend.config import get_model_config, TRAIN
from backend.events import event_bus, ML_INFERENCE_COMPLETE, ANOMALY_DETECTED
from backend.api.websocket import ws_manager, make_envelope
from backend.db import update_user_pattern
from backend.ml.feature_engine import FeatureEngine
from backend.ml.inference import InferenceEngine

logger = logging.getLogger(__name__)

# Module-level singletons
_feature_engine: FeatureEngine | None = None
_inference_engine: InferenceEngine | None = None
_latest_result: dict | None = None


def init_inference() -> None:
    """Load the TFT checkpoint and create FeatureEngine + InferenceEngine singletons."""
    global _feature_engine, _inference_engine

    cfg = get_model_config()
    _feature_engine = FeatureEngine(cfg)
    _inference_engine = InferenceEngine()
    _inference_engine.load()
    logger.info("ML inference pipeline initialized")


async def run_inference(
    buffer_window: np.ndarray,
    grid_forecast: list[dict],
    calendar_events: list[dict] | None = None,
) -> dict | None:
    """Run the full inference pipeline: features → model → events.

    Args:
        buffer_window: (96, 8) sensor buffer array
        grid_forecast: 24-element grid forecast list
        calendar_events: optional calendar event dicts

    Returns:
        Result dict (or None if debounced / not initialized)
    """
    global _latest_result

    if _feature_engine is None or _inference_engine is None:
        logger.warning("Inference not initialized, skipping")
        return None

    now = datetime.now(timezone.utc)

    # Build model-ready tensors from raw buffer
    try:
        past, future, static = _feature_engine.build_realtime_window(
            buffer_window, now, grid_forecast, calendar_events
        )
    except Exception:
        logger.warning("Feature engine failed on buffer data", exc_info=True)
        return None

    # Run TFT model
    result = _inference_engine.predict(past, future, static)
    if result is None:
        return None  # debounced

    # Build a serializable result with keys that build_system_prompt expects
    forecast_p50 = result["forecast_p50"]  # (24, 4)
    avg_watts = float(forecast_p50.mean())
    peak_hour = int(forecast_p50.sum(axis=1).argmax())

    serializable = {
        "anomaly_score": result["anomaly_score"],
        "forecast_summary": f"Avg {avg_watts:.0f}W, peak at hour {peak_hour}",
        "day_type": result["day_type"],
        "day_type_confidence": result["day_type_confidence"],
        "attention_weights": result["attention_weights"].tolist(),
        "nilm_active": result["nilm_active"],
        "forecast_p50": forecast_p50.tolist(),
    }
    _latest_result = serializable

    # Track user behavior patterns (lightweight EMA per channel/hour)
    try:
        current_hour = now.hour
        day_type = result["day_type"]
        if buffer_window is not None and len(buffer_window) > 0:
            latest_reading = buffer_window[-1]
            for ch in range(min(4, len(latest_reading))):
                ch_watts = float(latest_reading[ch])
                await update_user_pattern(ch, day_type, current_hour, ch_watts)
    except Exception:
        logger.debug("Pattern update failed", exc_info=True)

    # Publish events
    await event_bus.publish(ML_INFERENCE_COMPLETE, serializable)

    # Broadcast ml_status to iOS (model_loaded, last_training, accuracy)
    await ws_manager.broadcast(make_envelope("ml_status", {
        "model_loaded": True,
        "last_training": now.isoformat(),
        "accuracy": result["day_type_confidence"],
    }))

    if result["anomaly_score"] > 0.7:
        channel_id = int(np.argmax(result["nilm_probs"]))
        assignments = config.DEFAULT_CHANNEL_ASSIGNMENTS
        ch_info = assignments[channel_id] if channel_id < len(assignments) else {}

        await event_bus.publish(ANOMALY_DETECTED, {
            "anomaly_score": result["anomaly_score"],
            "channel_id": channel_id,
            "watts": avg_watts,
            "expected_watts": avg_watts * 0.6,
        })

        # Broadcast anomaly_alert to iOS
        expected = avg_watts * 0.6
        deviation = ((avg_watts - expected) / expected * 100) if expected > 0 else 0
        await ws_manager.broadcast(make_envelope("anomaly_alert", {
            "channel_id": channel_id,
            "assigned_zone": ch_info.get("zone", "unknown"),
            "assigned_appliance": ch_info.get("appliance", "unknown"),
            "current_watts": avg_watts,
            "expected_watts": expected,
            "deviation_pct": round(deviation, 1),
            "message": f"Unusual power on {ch_info.get('appliance', 'channel ' + str(channel_id))} "
                       f"({avg_watts:.0f}W vs expected {expected:.0f}W)",
        }))

    logger.debug("Inference complete: anomaly=%.2f day=%s",
                 result["anomaly_score"], result["day_type"])
    return serializable


def get_latest_result() -> dict | None:
    """Return the most recent inference result (for API endpoints)."""
    return _latest_result
