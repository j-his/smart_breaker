"""
MILP task scheduler using Google OR-Tools.

Optimizes when to run deferrable appliances to minimize a weighted
combination of electricity cost and carbon emissions, subject to
household breaker capacity constraints.
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from backend import config


def optimize_schedule(
    tasks: list[dict],
    grid_forecast_24h: list[dict],
    alpha: float = config.DEFAULT_ALPHA,
    beta: float = config.DEFAULT_BETA,
    max_kw: float = config.MAX_BREAKER_KW,
    user_patterns: list[dict] | None = None,
) -> list[dict]:
    """Run MILP optimization over task schedule.

    Args:
        tasks: List of task dicts from events_to_optimizer_tasks.
        grid_forecast_24h: 24-element list of grid hour dicts.
        alpha: Weight for electricity cost (0-1).
        beta: Weight for carbon emissions (0-1).
        max_kw: Maximum total kW allowed in any single hour (breaker limit).

    Returns:
        List of {task_id, optimized_start_hour, original_start_hour} dicts.
    """
    horizon = 48  # 48-hour planning window

    # Extend grid forecast to 48h by repeating the 24h pattern
    grid = []
    for h in range(horizon):
        grid.append(grid_forecast_24h[h % len(grid_forecast_24h)])

    # Separate deferrable and non-deferrable tasks
    deferrable = [t for t in tasks if t["earliest_start_hour"] != t["original_start_hour"]]
    fixed = [t for t in tasks if t["earliest_start_hour"] == t["original_start_hour"]]

    # ── Build CP-SAT model ──────────────────────────────────────────────────
    model = cp_model.CpModel()

    # Decision variables: x[i][h] = 1 if deferrable task i starts at hour h
    x = {}
    for i, task in enumerate(deferrable):
        earliest = task["earliest_start_hour"]
        latest = min(task["deadline_hour"] - task["duration_hours"], horizon - task["duration_hours"])
        for h in range(earliest, latest + 1):
            x[(i, h)] = model.new_bool_var(f"x_{i}_{h}")

    # Constraint 1: Each deferrable task starts exactly once
    for i, task in enumerate(deferrable):
        earliest = task["earliest_start_hour"]
        latest = min(task["deadline_hour"] - task["duration_hours"], horizon - task["duration_hours"])
        model.add_exactly_one(x[(i, h)] for h in range(earliest, latest + 1))

    # Constraint 2: Breaker limit per hour
    max_watts = int(max_kw * 1000)
    for h in range(horizon):
        # Fixed task contributions at this hour
        fixed_load = 0
        for t in fixed:
            if t["original_start_hour"] <= h < t["original_start_hour"] + t["duration_hours"]:
                fixed_load += t["power_watts"]

        # Deferrable task contributions (conditional on start hour)
        deferrable_terms = []
        for i, task in enumerate(deferrable):
            earliest = task["earliest_start_hour"]
            latest = min(task["deadline_hour"] - task["duration_hours"], horizon - task["duration_hours"])
            for s in range(earliest, latest + 1):
                # Task i running at hour h if it started at hour s
                if s <= h < s + task["duration_hours"]:
                    deferrable_terms.append(x[(i, s)] * task["power_watts"])

        if deferrable_terms:
            model.add(sum(deferrable_terms) + fixed_load <= max_watts)
        # If only fixed load, no constraint needed (already placed)

    # ── Objective: minimize α×cost + β×carbon ───────────────────────────────
    scale = 100  # integer scaling for CP-SAT (which works in integers)
    objective_terms = []

    for i, task in enumerate(deferrable):
        earliest = task["earliest_start_hour"]
        latest = min(task["deadline_hour"] - task["duration_hours"], horizon - task["duration_hours"])
        kwh = task["power_watts"] * task["duration_hours"] / 1000.0

        for h in range(earliest, latest + 1):
            # Compute cost over all hours the task would be active
            total_price = 0.0
            total_carbon = 0.0
            for offset in range(task["duration_hours"]):
                slot = grid[(h + offset) % len(grid)]
                total_price += slot.get("tou_price_cents_kwh", 0)
                total_carbon += slot.get(
                    "carbon_intensity_gco2_kwh",
                    slot.get("carbon_intensity", 0),
                )

            cost_score = alpha * total_price * kwh
            carbon_score = beta * total_carbon * kwh / 100.0  # normalize carbon
            combined = int((cost_score + carbon_score) * scale)

            objective_terms.append(x[(i, h)] * combined)

    # ── Pattern penalty: prefer hours where user is less active on channel ──
    pattern_by_ch_hour: dict[tuple[int, int], float] = {}
    if user_patterns:
        for p in user_patterns:
            pattern_by_ch_hour[(p["channel_id"], p["hour"])] = p["avg_watts"]

    if pattern_by_ch_hour:
        PATTERN_WEIGHT = 0.1
        for i, task in enumerate(deferrable):
            earliest = task["earliest_start_hour"]
            latest = min(task["deadline_hour"] - task["duration_hours"],
                         horizon - task["duration_hours"])
            ch = task.get("channel_id")
            if ch is None:
                continue
            for h in range(earliest, latest + 1):
                usage = pattern_by_ch_hour.get((ch, h % 24), 0)
                penalty = int(PATTERN_WEIGHT * usage / 100.0 * scale)
                if penalty > 0:
                    objective_terms.append(x[(i, h)] * penalty)

    if objective_terms:
        model.minimize(sum(objective_terms))

    # ── Solve ───────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.solve(model)

    # ── Extract results ─────────────────────────────────────────────────────
    results = []

    # Fixed tasks stay where they are
    for t in fixed:
        results.append({
            "task_id": t["id"],
            "optimized_start_hour": t["original_start_hour"],
            "original_start_hour": t["original_start_hour"],
        })

    # Deferrable tasks — read from solution
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for i, task in enumerate(deferrable):
            earliest = task["earliest_start_hour"]
            latest = min(task["deadline_hour"] - task["duration_hours"], horizon - task["duration_hours"])
            for h in range(earliest, latest + 1):
                if solver.value(x[(i, h)]):
                    results.append({
                        "task_id": task["id"],
                        "optimized_start_hour": h,
                        "original_start_hour": task["original_start_hour"],
                    })
                    break
    else:
        # Fallback: keep deferrable at original times
        for t in deferrable:
            results.append({
                "task_id": t["id"],
                "optimized_start_hour": t["original_start_hour"],
                "original_start_hour": t["original_start_hour"],
            })

    return results
