"""Monte Carlo robustness scoring for schedule confidence.

Perturbs grid prices and task durations, re-runs the MILP solver many times,
and produces confidence metrics: stability, savings percentiles, and an
overall confidence score.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import random
from collections import defaultdict

import numpy as np

from backend.optimizer.milp import optimize_schedule
from backend import config

logger = logging.getLogger(__name__)


async def monte_carlo_confidence(
    tasks: list[dict],
    grid_forecast_24h: list[dict],
    n_iterations: int = config.MONTE_CARLO_ITERATIONS,
    price_noise: float = 0.15,
    duration_noise: float = 0.075,
    alpha: float = config.DEFAULT_ALPHA,
    beta: float = config.DEFAULT_BETA,
) -> dict:
    """Run Monte Carlo simulation over the MILP scheduler.

    Args:
        tasks: Optimizer task dicts (same format as optimize_schedule input).
        grid_forecast_24h: 24-element grid forecast.
        n_iterations: Number of perturbed scenarios to run.
        price_noise: Max fractional perturbation on grid prices (±15%).
        duration_noise: Max fractional perturbation on task durations (±7.5%).
        alpha: Cost weight passed to optimizer.
        beta: Carbon weight passed to optimizer.

    Returns:
        Dict with keys: confidence, savings_p10, savings_p50, savings_p90,
        schedule_stability, n_scenarios.
    """
    if not tasks or not grid_forecast_24h:
        return {
            "confidence": 0.0,
            "savings_p10": 0.0,
            "savings_p50": 0.0,
            "savings_p90": 0.0,
            "schedule_stability": 0.0,
            "n_scenarios": 0,
        }

    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *(
            loop.run_in_executor(
                None,
                _run_single_scenario,
                tasks,
                grid_forecast_24h,
                price_noise,
                duration_noise,
                alpha,
                beta,
            )
            for _ in range(n_iterations)
        )
    )

    # Collect per-task start hours across scenarios
    task_hours: dict[str, list[int]] = defaultdict(list)
    savings_list: list[float] = []

    for scenario_results, scenario_savings in results:
        savings_list.append(scenario_savings)
        for r in scenario_results:
            task_hours[r["task_id"]].append(r["optimized_start_hour"])

    # Schedule stability: fraction of scenarios where each task lands on its mode hour
    stability_scores = []
    for tid, hours in task_hours.items():
        if not hours:
            continue
        mode_hour = max(set(hours), key=hours.count)
        frac_on_mode = hours.count(mode_hour) / len(hours)
        stability_scores.append(frac_on_mode)
    schedule_stability = float(np.mean(stability_scores)) if stability_scores else 0.0

    # Savings percentiles
    savings_arr = np.array(savings_list) if savings_list else np.array([0.0])
    savings_p10 = float(np.percentile(savings_arr, 10))
    savings_p50 = float(np.percentile(savings_arr, 50))
    savings_p90 = float(np.percentile(savings_arr, 90))

    # Coefficient of variation
    cv = float(np.std(savings_arr) / np.mean(savings_arr)) if np.mean(savings_arr) != 0 else 1.0
    cv = min(cv, 1.0)  # cap at 1

    # Confidence = stability * 0.6 + (1 - CV) * 0.4
    confidence = schedule_stability * 0.6 + (1.0 - cv) * 0.4
    confidence = max(0.0, min(1.0, confidence))

    return {
        "confidence": round(confidence, 4),
        "savings_p10": round(savings_p10, 2),
        "savings_p50": round(savings_p50, 2),
        "savings_p90": round(savings_p90, 2),
        "schedule_stability": round(schedule_stability, 4),
        "n_scenarios": n_iterations,
    }


def _perturb_grid(
    grid_forecast_24h: list[dict],
    noise: float,
) -> list[dict]:
    """Return a copy with prices perturbed by ±noise fraction."""
    perturbed = []
    for entry in grid_forecast_24h:
        e = dict(entry)
        factor = 1.0 + random.uniform(-noise, noise)
        e["tou_price_cents_kwh"] = max(0, e.get("tou_price_cents_kwh", 0) * factor)
        factor_c = 1.0 + random.uniform(-noise, noise)
        e["carbon_intensity_gco2_kwh"] = max(
            0, e.get("carbon_intensity_gco2_kwh", 0) * factor_c
        )
        perturbed.append(e)
    return perturbed


def _perturb_tasks(tasks: list[dict], noise: float) -> list[dict]:
    """Return a copy with durations perturbed by ±noise fraction."""
    perturbed = []
    for t in tasks:
        t2 = dict(t)
        factor = 1.0 + random.uniform(-noise, noise)
        t2["duration_hours"] = max(1, round(t2.get("duration_hours", 1) * factor))
        perturbed.append(t2)
    return perturbed


def _run_single_scenario(
    tasks: list[dict],
    grid_forecast_24h: list[dict],
    price_noise: float,
    duration_noise: float,
    alpha: float,
    beta: float,
) -> tuple[list[dict], float]:
    """Run one perturbed scenario. Returns (results, estimated_savings_cents)."""
    p_grid = _perturb_grid(grid_forecast_24h, price_noise)
    p_tasks = _perturb_tasks(tasks, duration_noise)

    results = optimize_schedule(p_tasks, p_grid, alpha=alpha, beta=beta)

    # Estimate savings: difference between original and optimized placement
    savings = 0.0
    for r in results:
        orig_h = r["original_start_hour"]
        opt_h = r["optimized_start_hour"]
        if orig_h != opt_h:
            task = next((t for t in p_tasks if t["id"] == r["task_id"]), None)
            if task:
                orig_price = p_grid[orig_h % len(p_grid)].get("tou_price_cents_kwh", 0)
                opt_price = p_grid[opt_h % len(p_grid)].get("tou_price_cents_kwh", 0)
                kwh = task.get("power_watts", 0) * task.get("duration_hours", 1) / 1000.0
                savings += (orig_price - opt_price) * kwh

    return results, savings
