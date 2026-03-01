"""
Optimization orchestrator — ties together grid data, calendar parsing,
the optimizer bridge, and the MILP solver into a single pipeline.

This is the main entry point for running schedule optimization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend import config
from backend.grid import tou_rates
from backend.calendar.parser import CalendarEvent
from backend.calendar.optimizer_bridge import (
    events_to_optimizer_tasks,
    optimizer_result_to_events,
)
from backend.optimizer.milp import optimize_schedule


@dataclass
class OptimizationResult:
    """Result of a full optimization run."""

    events: list[dict]
    total_savings_cents: float
    total_carbon_avoided_g: float
    confidence: float = 0.87  # placeholder for Monte Carlo (Task 28)

    def to_calendar_update(self) -> dict:
        """Format as a WebSocket calendar_update payload."""
        return {
            "optimized_events": self.events,
            "total_savings_cents": self.total_savings_cents,
            "total_carbon_avoided_g": self.total_carbon_avoided_g,
            "optimization_confidence": self.confidence,
        }


def run_optimization(
    calendar_events: list[CalendarEvent],
    grid_forecast: list[dict] | None = None,
    alpha: float = config.DEFAULT_ALPHA,
    beta: float = config.DEFAULT_BETA,
    max_kw: float = config.MAX_BREAKER_KW,
    user_patterns: list[dict] | None = None,
) -> OptimizationResult:
    """Run the full optimization pipeline.

    1. Compute base_date (midnight UTC today)
    2. Generate grid_forecast if not provided
    3. Convert events → optimizer tasks
    4. Run MILP solver
    5. Convert results → OptimizedEvent dicts
    6. Aggregate savings/carbon totals
    7. Return OptimizationResult
    """
    # Step 1: base date
    now = datetime.now(timezone.utc)
    base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Step 2: grid forecast
    if grid_forecast is None:
        grid_forecast = tou_rates.generate_24h_forecast(base_date)

    # Step 3: events → optimizer tasks
    tasks = events_to_optimizer_tasks(calendar_events, base_date)

    # Step 4: MILP
    optimizer_results = optimize_schedule(
        tasks, grid_forecast, alpha=alpha, beta=beta, max_kw=max_kw,
        user_patterns=user_patterns,
    )

    # Step 5: results → OptimizedEvent dicts
    optimized_events = optimizer_result_to_events(
        calendar_events, optimizer_results, base_date, grid_forecast
    )

    # Step 6: aggregate totals
    total_savings = sum(e["savings_cents"] for e in optimized_events)
    total_carbon = sum(e["carbon_avoided_g"] for e in optimized_events)

    # Step 7: return
    return OptimizationResult(
        events=optimized_events,
        total_savings_cents=round(total_savings, 2),
        total_carbon_avoided_g=round(total_carbon, 2),
    )
