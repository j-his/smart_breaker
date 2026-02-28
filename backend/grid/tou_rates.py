"""
PG&E TOU (Time-of-Use) rate lookup and CAISO-modeled grid data generation.

Provides deterministic grid signals (solar/wind/carbon/price) for optimization,
modeled after real CAISO patterns without random noise.
"""
from datetime import datetime, timezone, timedelta

from backend import config


# ── PG&E E-TOU-C Rate Schedule ──────────────────────────────────────────────
# Rates in cents/kWh
TOU_SCHEDULE = {
    "summer": {  # Jun-Sep
        "peak": 38,           # 16:00-21:00
        "off_peak": 22,       # 07:00-16:00 and 21:00-24:00
        "super_off_peak": 12, # 00:00-07:00
    },
    "winter": {  # Oct-May
        "peak": 34,
        "off_peak": 20,
        "super_off_peak": 11,
    },
}


def get_season(dt: datetime) -> str:
    """Return 'summer' (Jun-Sep) or 'winter' (Oct-May)."""
    return "summer" if 6 <= dt.month <= 9 else "winter"


def get_tou_period(dt: datetime) -> str:
    """Return TOU period for the given hour: 'peak', 'off_peak', or 'super_off_peak'."""
    h = dt.hour
    if 16 <= h < 21:
        return "peak"
    elif 0 <= h < 7:
        return "super_off_peak"
    else:
        return "off_peak"


def get_tou_price(dt: datetime) -> float:
    """Return TOU price in cents/kWh for the given datetime."""
    season = get_season(dt)
    period = get_tou_period(dt)
    return float(TOU_SCHEDULE[season][period])


def get_grid_status(price_cents: float) -> str:
    """Map price to traffic-light status: green (<=15), yellow (16-25), red (>25)."""
    if price_cents <= 15:
        return "green"
    elif price_cents <= 25:
        return "yellow"
    else:
        return "red"


def _solar_contribution(hour: int) -> float:
    """Deterministic solar output peaking ~1PM, modeled on CAISO data."""
    if 6 <= hour <= 18:
        import math
        return max(0.0, 60.0 * math.sin(math.pi * (hour - 6) / 12))
    return 0.0


def _wind_contribution(hour: int) -> float:
    """Deterministic wind output, stronger at night."""
    import math
    return 10.0 + 8.0 * math.sin(2 * math.pi * (hour - 2) / 24)


def generate_grid_snapshot(dt: datetime) -> dict:
    """Generate a grid snapshot matching the frontend GridSnapshot schema.

    Returns dict with keys: tou_price_cents_kwh, status,
    renewable_pct, carbon_intensity_gco2_kwh, tou_period.
    """
    price = get_tou_price(dt)
    solar = _solar_contribution(dt.hour)
    wind = _wind_contribution(dt.hour)
    renewable_pct = round(30.0 + solar + wind, 1)
    carbon = round(400.0 - 3.0 * renewable_pct, 1)

    return {
        "tou_price_cents_kwh": price,
        "status": get_grid_status(price),
        "renewable_pct": renewable_pct,
        "carbon_intensity_gco2_kwh": carbon,
        "tou_period": get_tou_period(dt),
    }


def generate_24h_forecast(base_dt: datetime) -> list[dict]:
    """Generate 24 GridHour dicts starting from base_dt (hour 0).

    Each dict: hour, tou_price_cents_kwh, status, renewable_pct,
    carbon_intensity_gco2_kwh.
    """
    forecast = []
    for h in range(24):
        dt = base_dt.replace(hour=h, minute=0, second=0, microsecond=0)
        solar = _solar_contribution(h)
        wind = _wind_contribution(h)
        renewable_pct = round(30.0 + solar + wind, 1)
        carbon = round(400.0 - 3.0 * renewable_pct, 1)
        price = get_tou_price(dt)

        forecast.append({
            "hour": h,
            "tou_price_cents_kwh": price,
            "status": get_grid_status(price),
            "renewable_pct": renewable_pct,
            "carbon_intensity_gco2_kwh": carbon,
            "tou_period": get_tou_period(dt),
        })
    return forecast
