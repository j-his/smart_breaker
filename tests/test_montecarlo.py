"""Tests for Monte Carlo robustness scoring."""
import pytest

from backend.optimizer.montecarlo import monte_carlo_confidence


@pytest.fixture
def simple_tasks():
    """Small task set for fast Monte Carlo runs."""
    return [
        {
            "id": "mc-1",
            "title": "Dryer",
            "power_watts": 2400,
            "duration_hours": 1,
            "original_start_hour": 18,
            "earliest_start_hour": 0,
            "deadline_hour": 30,
        },
        {
            "id": "mc-2",
            "title": "EV Charge",
            "power_watts": 3600,
            "duration_hours": 4,
            "original_start_hour": 21,
            "earliest_start_hour": 0,
            "deadline_hour": 30,
        },
    ]


class TestMonteCarlo:
    """Tests for monte_carlo_confidence()."""

    @pytest.mark.asyncio
    async def test_returns_all_required_keys(self, simple_tasks, sample_grid_forecast_24h):
        result = await monte_carlo_confidence(
            simple_tasks, sample_grid_forecast_24h, n_iterations=5
        )
        assert "confidence" in result
        assert "savings_p10" in result
        assert "savings_p50" in result
        assert "savings_p90" in result
        assert "schedule_stability" in result
        assert "n_scenarios" in result

    @pytest.mark.asyncio
    async def test_confidence_and_stability_bounded(self, simple_tasks, sample_grid_forecast_24h):
        result = await monte_carlo_confidence(
            simple_tasks, sample_grid_forecast_24h, n_iterations=5
        )
        assert 0.0 <= result["confidence"] <= 1.0
        assert 0.0 <= result["schedule_stability"] <= 1.0

    @pytest.mark.asyncio
    async def test_percentiles_ordered(self, simple_tasks, sample_grid_forecast_24h):
        result = await monte_carlo_confidence(
            simple_tasks, sample_grid_forecast_24h, n_iterations=10
        )
        assert result["savings_p10"] <= result["savings_p50"]
        assert result["savings_p50"] <= result["savings_p90"]

    @pytest.mark.asyncio
    async def test_works_with_single_iteration(self, simple_tasks, sample_grid_forecast_24h):
        result = await monte_carlo_confidence(
            simple_tasks, sample_grid_forecast_24h, n_iterations=1
        )
        assert result["n_scenarios"] == 1
        assert result["confidence"] >= 0.0
