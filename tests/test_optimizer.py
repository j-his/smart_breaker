"""Tests for the MILP optimizer — TDD (written before implementation)."""
import pytest
from datetime import datetime, timezone, timedelta

from backend.optimizer.milp import optimize_schedule


@pytest.fixture
def simple_tasks():
    """3 tasks: dryer (deferrable), cook (fixed), EV (deferrable)."""
    return [
        {
            "id": "dryer-001",
            "title": "Run Dryer",
            "channel_id": 1,
            "power_watts": 2400,
            "duration_min": 60,
            "duration_hours": 1,
            "original_start_hour": 18,
            "earliest_start_hour": 0,
            "deadline_hour": 31,  # 18 + 1 + 12
        },
        {
            "id": "cook-001",
            "title": "Cook Dinner",
            "channel_id": 0,
            "power_watts": 1800,
            "duration_min": 60,
            "duration_hours": 1,
            "original_start_hour": 19,
            "earliest_start_hour": 19,
            "deadline_hour": 20,
        },
        {
            "id": "ev-001",
            "title": "Charge EV",
            "channel_id": 2,
            "power_watts": 3600,
            "duration_min": 240,
            "duration_hours": 4,
            "original_start_hour": 21,
            "earliest_start_hour": 0,
            "deadline_hour": 37,  # 21 + 4 + 12
        },
    ]


class TestMILPOptimizer:
    """MILP scheduling tests."""

    def test_optimizer_returns_results(self, simple_tasks, sample_grid_forecast_24h):
        """Optimizer should return a non-empty result list."""
        results = optimize_schedule(simple_tasks, sample_grid_forecast_24h)
        assert len(results) > 0

    def test_non_deferrable_stays_fixed(self, simple_tasks, sample_grid_forecast_24h):
        """Cook Dinner (non-deferrable) must stay at hour 19."""
        results = optimize_schedule(simple_tasks, sample_grid_forecast_24h)
        cook = next(r for r in results if r["task_id"] == "cook-001")
        assert cook["optimized_start_hour"] == 19

    def test_deferrable_tasks_moved_to_cheaper_hours(
        self, simple_tasks, sample_grid_forecast_24h
    ):
        """Dryer should move from peak (hour 18, 38c) to a cheaper slot."""
        results = optimize_schedule(simple_tasks, sample_grid_forecast_24h)
        dryer = next(r for r in results if r["task_id"] == "dryer-001")
        # Original was hour 18 (peak at 38c). Optimizer should find something cheaper.
        original_price = sample_grid_forecast_24h[18]["tou_price_cents_kwh"]
        opt_hour = dryer["optimized_start_hour"] % 24
        opt_price = sample_grid_forecast_24h[opt_hour]["tou_price_cents_kwh"]
        assert opt_price <= original_price

    def test_breaker_limit_respected(self, simple_tasks, sample_grid_forecast_24h):
        """With max_kw=5.0, no hour should exceed 5000W total."""
        results = optimize_schedule(
            simple_tasks, sample_grid_forecast_24h, max_kw=5.0
        )
        # Build a per-hour load map
        hourly_load = {}
        for r in results:
            task = next(t for t in simple_tasks if t["id"] == r["task_id"])
            for h_offset in range(task["duration_hours"]):
                hour = r["optimized_start_hour"] + h_offset
                hourly_load[hour] = hourly_load.get(hour, 0) + task["power_watts"]

        for hour, load in hourly_load.items():
            assert load <= 5000, f"Hour {hour} exceeds 5kW breaker limit: {load}W"
