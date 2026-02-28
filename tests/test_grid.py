"""Tests for TOU rate lookup and grid data generation."""
import pytest
from datetime import datetime, timezone

from backend.grid.tou_rates import (
    get_tou_price,
    generate_grid_snapshot,
    generate_24h_forecast,
)


class TestTOURates:
    """PG&E E-TOU-C rate schedule tests."""

    def test_tou_price_peak_hours(self):
        """Peak hours (16-21) should match TOU schedule rates."""
        # Summer peak = 38 cents
        summer_peak = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
        assert get_tou_price(summer_peak) == 38.0

        # Winter peak = 34 cents
        winter_peak = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
        assert get_tou_price(winter_peak) == 34.0

    def test_tou_price_super_offpeak(self):
        """Super off-peak (0-7) should be the cheapest rate."""
        summer_night = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)
        winter_night = datetime(2026, 1, 15, 3, 0, tzinfo=timezone.utc)

        assert get_tou_price(summer_night) == 12.0
        assert get_tou_price(winter_night) == 11.0

        # Confirm it's cheaper than off-peak
        summer_offpeak = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
        assert get_tou_price(summer_night) < get_tou_price(summer_offpeak)

    def test_grid_snapshot_keys(self):
        """Grid snapshot must have all 5 frontend schema keys."""
        dt = datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)
        snapshot = generate_grid_snapshot(dt)

        expected_keys = {
            "tou_price_cents_kwh",
            "status",
            "renewable_pct",
            "carbon_intensity_gco2_kwh",
            "tou_period",
        }
        assert set(snapshot.keys()) == expected_keys

    def test_24h_forecast_length(self):
        """Forecast must have exactly 24 entries with hour field 0-23."""
        base = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        forecast = generate_24h_forecast(base)

        assert len(forecast) == 24
        assert [entry["hour"] for entry in forecast] == list(range(24))
