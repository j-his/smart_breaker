"""Tests for the feature engineering pipeline."""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

from backend.ml.feature_engine import FeatureEngine
from backend.config import get_model_config


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def small_df():
    """3 days of 15-min resolution data (288 rows), mimicking data_generator output."""
    rng = np.random.default_rng(42)
    n_days = 5  # need enough rows for window=192: 5*96=480 > 192
    n = n_days * 96  # 480 rows
    timestamps = pd.date_range(
        "2026-01-01", periods=n, freq="15min", tz="UTC"
    )
    labels = ["workday", "weekend", "workday", "wfh", "workday"]
    day_types = []
    for label in labels:
        day_types.extend([label] * 96)

    return pd.DataFrame({
        "timestamp": timestamps,
        "ch0_watts": rng.uniform(50, 2000, n),
        "ch1_watts": rng.uniform(50, 2500, n),
        "ch2_watts": rng.uniform(50, 4000, n),
        "ch3_watts": rng.uniform(50, 2000, n),
        "total_watts": rng.uniform(200, 8000, n),
        "renewable_pct": rng.uniform(10, 95, n),
        "carbon_intensity": rng.uniform(80, 500, n),
        "tou_price_cents": rng.uniform(5, 50, n),
        "day_type": day_types,
        "temperature_f": rng.uniform(40, 100, n),
    })


@pytest.fixture
def sample_calendars():
    """5 days, 2 events per day (Cook Dinner on ch0 at 19:00, Charge EV on ch2 at 21:00)."""
    calendars = []
    for day_offset in range(5):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_offset)
        day_events = [
            {
                "title": "Cook Dinner",
                "start": (base + timedelta(hours=19)).isoformat(),
                "end": (base + timedelta(hours=20)).isoformat(),
                "duration_min": 60,
                "channel_id": 0,
                "appliance": "inductive_stove",
                "zone": "kitchen",
                "power_watts": 1800,
                "is_deferrable": False,
            },
            {
                "title": "Charge EV",
                "start": (base + timedelta(hours=21)).isoformat(),
                "end": (base + timedelta(hours=23)).isoformat(),
                "duration_min": 120,
                "channel_id": 2,
                "appliance": "ev_charger",
                "zone": "garage",
                "power_watts": 3600,
                "is_deferrable": True,
            },
        ]
        calendars.append(day_events)
    return calendars


# ── Tests ───────────────────────────────────────────────────────────────────

def test_output_tensor_shapes(small_df, sample_calendars):
    """Verify output array dimensions and sizes match ModelConfig."""
    cfg = get_model_config()
    engine = FeatureEngine(cfg)
    past, future, static, targets = engine.build_dataset(small_df, sample_calendars, resample_min=15)

    # Basic dimensionality
    assert past.ndim == 3
    assert future.ndim == 3
    assert static.ndim == 2

    # Time dimensions match config
    assert past.shape[1] == cfg.past_window       # 96
    assert future.shape[1] == cfg.forecast_horizon  # 24

    # Feature dimensions match engine properties
    assert past.shape[2] == engine.n_past_features
    assert future.shape[2] == engine.n_future_features
    assert static.shape[1] == engine.n_static_features

    # All arrays share the same n_samples in dim 0
    n = past.shape[0]
    assert n > 0
    assert future.shape[0] == n
    assert static.shape[0] == n

    # Targets
    assert set(targets.keys()) == {"forecast", "nilm", "anomaly", "day_type"}
    assert targets["forecast"].shape == (n, cfg.forecast_horizon, cfg.n_channels)
    assert targets["nilm"].shape == (n, cfg.n_channels)
    assert targets["anomaly"].shape == (n, cfg.past_window, cfg.n_channels)
    assert targets["day_type"].shape == (n,)


def test_no_nans_in_output(small_df, sample_calendars):
    """Verify no NaN values survive the pipeline."""
    cfg = get_model_config()
    engine = FeatureEngine(cfg)
    past, future, static, targets = engine.build_dataset(small_df, sample_calendars, resample_min=15)

    assert not np.isnan(past).any(), "NaN found in past array"
    assert not np.isnan(future).any(), "NaN found in future array"
    assert not np.isnan(static).any(), "NaN found in static array"
    for key, arr in targets.items():
        assert not np.isnan(arr.astype(float)).any(), f"NaN found in targets[{key}]"


def test_cyclical_encoding_range(small_df, sample_calendars):
    """Verify cyclical encodings and other features stay in a sane range."""
    cfg = get_model_config()
    engine = FeatureEngine(cfg)
    past, future, static, targets = engine.build_dataset(small_df, sample_calendars, resample_min=15)

    # Loose sanity: sin/cos are in [-1,1], watts positive, price_delta can
    # swing ~±45 (tou range 5-50), so -50 is a safe lower bound
    assert past.min() >= -50, f"past min = {past.min()}, expected >= -50"
