"""Tests for synthetic household data generation."""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from backend.ml.data_generator import HouseholdSimulator


@pytest.fixture
def simulator():
    return HouseholdSimulator(seed=42, n_days=3)


def test_generates_correct_columns(simulator):
    df, calendars = simulator.generate()
    expected_cols = {
        "timestamp", "ch0_watts", "ch1_watts", "ch2_watts", "ch3_watts",
        "total_watts", "renewable_pct", "carbon_intensity", "tou_price_cents",
        "day_type", "temperature_f",
    }
    assert expected_cols.issubset(set(df.columns))


def test_correct_row_count(simulator):
    df, _ = simulator.generate()
    # 3 days x 1440 minutes/day = 4320 rows
    assert len(df) == 3 * 1440


def test_power_values_non_negative(simulator):
    df, _ = simulator.generate()
    for ch in range(4):
        col = df[f"ch{ch}_watts"].dropna()
        assert (col >= 0).all()


def test_total_equals_sum_of_channels(simulator):
    df, _ = simulator.generate()
    # Drop NaN rows (from simulated sensor dropout) before comparison
    valid = df.dropna(subset=["ch0_watts", "ch1_watts", "ch2_watts", "ch3_watts"])
    ch_sum = valid["ch0_watts"] + valid["ch1_watts"] + valid["ch2_watts"] + valid["ch3_watts"]
    np.testing.assert_allclose(valid["total_watts"], ch_sum, atol=0.01)


def test_calendar_generated_per_day(simulator):
    _, calendars = simulator.generate()
    assert len(calendars) == 3  # one list per day


def test_calendar_events_have_required_fields(simulator):
    _, calendars = simulator.generate()
    required = {"title", "start", "end", "channel_id", "power_watts", "is_deferrable"}
    for day_events in calendars:
        for event in day_events:
            assert required.issubset(set(event.keys())), f"Missing fields in {event}"


def test_grid_values_in_range(simulator):
    df, _ = simulator.generate()
    assert (df["renewable_pct"] >= 0).all()
    assert (df["renewable_pct"] <= 100).all()
    assert (df["carbon_intensity"] >= 0).all()
    assert (df["tou_price_cents"] >= 0).all()


def test_day_types_are_valid(simulator):
    df, _ = simulator.generate()
    valid = {"workday", "weekend", "wfh", "away"}
    assert set(df["day_type"].unique()).issubset(valid)
