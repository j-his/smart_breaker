"""LLM context assembler — builds structured system prompts from live state."""
from __future__ import annotations

from backend import config


def build_system_prompt(
    sensor_state: dict | None = None,
    grid_status: dict | None = None,
    grid_forecast: list[dict] | None = None,
    ml_result: dict | None = None,
    optimization: dict | None = None,
    channel_assignments: list[dict] | None = None,
) -> str:
    """Build a system prompt for the EnergyAI chat LLM.

    Each parameter adds a section to the prompt. None values are skipped,
    allowing graceful degradation when subsystems haven't produced data yet.

    Returns:
        A multi-section system prompt string.
    """
    assignments = channel_assignments or config.DEFAULT_CHANNEL_ASSIGNMENTS

    sections = [_role_preamble(), _format_home_setup(assignments)]

    if sensor_state is not None:
        sections.append(_format_current_power(sensor_state, assignments))

    if grid_status is not None:
        sections.append(_format_grid_conditions(grid_status))

    if grid_forecast is not None:
        sections.append(_format_grid_forecast(grid_forecast))

    if ml_result is not None:
        sections.append(_format_ml_analysis(ml_result))

    if optimization is not None:
        sections.append(_format_current_schedule(optimization))

    return "\n\n".join(sections)


# ── Section Formatters ──────────────────────────────────────────────────────


def _role_preamble() -> str:
    return (
        "You are EnergyAI, a smart home energy assistant. "
        "You help homeowners understand their electricity usage, save money, "
        "and reduce carbon emissions. Be concise, friendly, and actionable. "
        "When suggesting changes, explain the cost and carbon impact."
    )


def _format_home_setup(assignments: list[dict]) -> str:
    lines = ["## Home Setup"]
    for ch in assignments:
        lines.append(
            f"- Channel {ch['channel_id']}: {ch['zone']} / {ch['appliance']}"
        )
    return "\n".join(lines)


def _format_current_power(sensor_state: dict, assignments: list[dict]) -> str:
    lines = ["## Current Power"]
    channels = sensor_state.get("channels", [])
    for ch in channels:
        cid = ch.get("channel_id", "?")
        watts = ch.get("current_watts", 0)
        zone = ch.get("assigned_zone", "unknown")
        lines.append(f"- Ch{cid} ({zone}): {watts:.0f} W")
    total = sensor_state.get("total_watts") or sum(
        c.get("current_watts", 0) for c in channels
    )
    lines.append(f"- Total: {total:.0f} W")
    return "\n".join(lines)


def _format_grid_conditions(grid_status: dict) -> str:
    lines = ["## Grid Conditions"]
    price = grid_status.get("tou_price_cents_kwh", "N/A")
    status = grid_status.get("status", "unknown")
    renewable = grid_status.get("renewable_pct", "N/A")
    carbon = grid_status.get("carbon_intensity_gco2_kwh", "N/A")
    period = grid_status.get("tou_period", "unknown")
    lines.append(f"- TOU Price: {price} ¢/kWh ({period})")
    lines.append(f"- Grid Status: {status}")
    lines.append(f"- Renewable: {renewable}%")
    lines.append(f"- Carbon Intensity: {carbon} gCO2/kWh")
    return "\n".join(lines)


def _format_grid_forecast(grid_forecast: list[dict]) -> str:
    # Only include next 6 hours to save tokens
    lines = ["## Grid Forecast (next 6h)"]
    for entry in grid_forecast[:6]:
        h = entry.get("hour", "?")
        price = entry.get("tou_price_cents_kwh", "?")
        status = entry.get("status", "?")
        carbon = entry.get("carbon_intensity_gco2_kwh", "?")
        lines.append(f"- Hour {h}: {price}¢/kWh, {status}, {carbon} gCO2")
    return "\n".join(lines)


def _format_ml_analysis(ml_result: dict) -> str:
    lines = ["## ML Analysis"]
    if "anomaly" in ml_result:
        lines.append(f"- Anomaly detected: {ml_result['anomaly']}")
    if "forecast_summary" in ml_result:
        lines.append(f"- Forecast: {ml_result['forecast_summary']}")
    if "confidence" in ml_result:
        lines.append(f"- Model confidence: {ml_result['confidence']:.0%}")
    if not any(k in ml_result for k in ("anomaly", "forecast_summary", "confidence")):
        lines.append(f"- Raw: {ml_result}")
    return "\n".join(lines)


def _format_current_schedule(optimization: dict) -> str:
    lines = ["## Current Schedule"]
    events = optimization.get("optimized_events", [])
    if not events:
        lines.append("- No scheduled events")
        return "\n".join(lines)
    for ev in events:
        title = ev.get("title", "Untitled")
        start = ev.get("optimized_start", ev.get("optimized_start_hour", "?"))
        lines.append(f"- {title}: starts at hour {start}")
    savings = optimization.get("total_savings_cents", 0)
    carbon = optimization.get("total_carbon_avoided_g", 0)
    if savings or carbon:
        lines.append(f"- Projected savings: {savings:.1f}¢, {carbon:.0f}g CO2 avoided")
    return "\n".join(lines)
