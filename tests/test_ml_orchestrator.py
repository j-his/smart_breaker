"""Tests for the ML inference orchestrator and real-time feature bridge."""
import pytest
import numpy as np
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from backend.config import get_model_config
from backend.ml.feature_engine import FeatureEngine


@pytest.fixture
def feature_engine():
    cfg = get_model_config()
    return FeatureEngine(cfg)


@pytest.fixture
def buffer_window():
    """Simulated (96, 8) sensor buffer: [ch0-3, total, renewable, carbon, price]."""
    rng = np.random.default_rng(42)
    buf = np.zeros((96, 8), dtype=np.float32)
    buf[:, 0] = rng.uniform(100, 600, 96)    # ch0 watts
    buf[:, 1] = rng.uniform(0, 2500, 96)     # ch1 watts
    buf[:, 2] = rng.uniform(0, 3800, 96)     # ch2 watts
    buf[:, 3] = rng.uniform(200, 2000, 96)   # ch3 watts
    buf[:, 4] = buf[:, :4].sum(axis=1)       # total
    buf[:, 5] = rng.uniform(20, 90, 96)      # renewable_pct
    buf[:, 6] = rng.uniform(100, 500, 96)    # carbon_intensity
    buf[:, 7] = rng.uniform(10, 40, 96)      # tou_price
    return buf


@pytest.fixture
def grid_forecast_24(sample_grid_forecast_24h):
    return sample_grid_forecast_24h


class TestBuildRealtimeWindow:
    """Test the real-time feature bridge that converts buffer → model tensors."""

    def test_output_shapes(self, feature_engine, buffer_window, grid_forecast_24):
        now = datetime.now(timezone.utc)
        past, future, static = feature_engine.build_realtime_window(
            buffer_window, now, grid_forecast_24
        )
        assert past.shape == (96, 53), f"Expected (96, 53), got {past.shape}"
        assert future.shape == (24, 10), f"Expected (24, 10), got {future.shape}"
        assert static.shape == (8,), f"Expected (8,), got {static.shape}"

    def test_output_dtypes(self, feature_engine, buffer_window, grid_forecast_24):
        now = datetime.now(timezone.utc)
        past, future, static = feature_engine.build_realtime_window(
            buffer_window, now, grid_forecast_24
        )
        assert past.dtype == np.float32
        assert future.dtype == np.float32
        assert static.dtype == np.float32

    def test_no_nans(self, feature_engine, buffer_window, grid_forecast_24):
        now = datetime.now(timezone.utc)
        past, future, static = feature_engine.build_realtime_window(
            buffer_window, now, grid_forecast_24
        )
        assert not np.isnan(past).any(), "Past tensor contains NaN"
        assert not np.isnan(future).any(), "Future tensor contains NaN"
        assert not np.isnan(static).any(), "Static tensor contains NaN"

    def test_with_calendar_events(self, feature_engine, buffer_window, grid_forecast_24):
        now = datetime.now(timezone.utc)
        events = [
            {
                "start": now,
                "end": now.replace(hour=(now.hour + 1) % 24),
                "channel_id": 0,
                "power_watts": 1500,
            }
        ]
        past, future, static = feature_engine.build_realtime_window(
            buffer_window, now, grid_forecast_24, calendar_events=events
        )
        assert past.shape == (96, 53)
        assert not np.isnan(past).any()


@pytest.mark.asyncio
async def test_inference_publishes_ml_complete():
    """Mock InferenceEngine.predict and verify ML_INFERENCE_COMPLETE is published."""
    from backend.events import EventBus, ML_INFERENCE_COMPLETE

    received = []

    async def handler(event):
        received.append(event)

    mock_predict_result = {
        "forecast": np.zeros((24, 4, 3)),
        "forecast_p50": np.zeros((24, 4)),
        "nilm_probs": np.array([0.9, 0.1, 0.0, 0.8]),
        "nilm_active": [True, False, False, True],
        "anomaly_score": 0.3,
        "day_type": "workday",
        "day_type_confidence": 0.92,
        "attention_weights": np.zeros((24, 96)),
    }

    with patch("backend.ml.orchestrator._feature_engine") as mock_fe, \
         patch("backend.ml.orchestrator._inference_engine") as mock_ie, \
         patch("backend.ml.orchestrator.event_bus") as mock_bus:

        mock_fe.build_realtime_window.return_value = (
            np.zeros((96, 53), dtype=np.float32),
            np.zeros((24, 10), dtype=np.float32),
            np.zeros(8, dtype=np.float32),
        )
        mock_ie.predict.return_value = mock_predict_result
        mock_bus.publish = AsyncMock()

        from backend.ml.orchestrator import run_inference
        buf = np.zeros((96, 8), dtype=np.float32)
        forecast = [{"hour": h, "renewable_pct": 50, "carbon_intensity_gco2_kwh": 300,
                      "tou_price_cents_kwh": 20} for h in range(24)]
        result = await run_inference(buf, forecast)

        assert result is not None
        assert "anomaly_score" in result
        assert "forecast_summary" in result
        # ML_INFERENCE_COMPLETE should have been published
        mock_bus.publish.assert_any_call(ML_INFERENCE_COMPLETE, result)


@pytest.mark.asyncio
async def test_anomaly_publishes_event():
    """When anomaly_score > 0.7, ANOMALY_DETECTED should be published."""
    from backend.events import ANOMALY_DETECTED

    mock_predict_result = {
        "forecast": np.zeros((24, 4, 3)),
        "forecast_p50": np.ones((24, 4)) * 500,
        "nilm_probs": np.array([0.9, 0.1, 0.0, 0.8]),
        "nilm_active": [True, False, False, True],
        "anomaly_score": 0.85,
        "day_type": "workday",
        "day_type_confidence": 0.92,
        "attention_weights": np.zeros((24, 96)),
    }

    with patch("backend.ml.orchestrator._feature_engine") as mock_fe, \
         patch("backend.ml.orchestrator._inference_engine") as mock_ie, \
         patch("backend.ml.orchestrator.event_bus") as mock_bus:

        mock_fe.build_realtime_window.return_value = (
            np.zeros((96, 53), dtype=np.float32),
            np.zeros((24, 10), dtype=np.float32),
            np.zeros(8, dtype=np.float32),
        )
        mock_ie.predict.return_value = mock_predict_result
        mock_bus.publish = AsyncMock()

        from backend.ml.orchestrator import run_inference
        buf = np.zeros((96, 8), dtype=np.float32)
        forecast = [{"hour": h, "renewable_pct": 50, "carbon_intensity_gco2_kwh": 300,
                      "tou_price_cents_kwh": 20} for h in range(24)]
        result = await run_inference(buf, forecast)

        # Both ML_INFERENCE_COMPLETE and ANOMALY_DETECTED should be published
        call_args = [call[0][0] for call in mock_bus.publish.call_args_list]
        assert ANOMALY_DETECTED in call_args
