"""Shared test fixtures for EnergyAI backend tests."""
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta


@pytest.fixture
def sample_sensor_reading():
    """A single sensor reading as it arrives from hardware."""
    return {
        "device_id": "esp32-demo-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channels": [
            {
                "channel_id": 0,
                "assigned_zone": "kitchen",
                "assigned_appliance": "inductive_stove",
                "current_amps": 4.32,
            },
            {
                "channel_id": 1,
                "assigned_zone": "laundry_room",
                "assigned_appliance": "dryer",
                "current_amps": 20.0,
            },
            {
                "channel_id": 2,
                "assigned_zone": "garage",
                "assigned_appliance": "ev_charger",
                "current_amps": 0.0,
            },
            {
                "channel_id": 3,
                "assigned_zone": "bedroom",
                "assigned_appliance": "air_conditioning",
                "current_amps": 15.0,
            },
        ],
    }


@pytest.fixture
def sample_task_list():
    """A list of calendar tasks for the optimizer."""
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {
            "id": "task-001",
            "title": "Run Dryer",
            "channel_id": 1,
            "power_watts": 2400,
            "duration_min": 60,
            "original_start": base + timedelta(hours=18),
            "deadline": base + timedelta(hours=24),
            "is_deferrable": True,
            "priority": "low",
        },
        {
            "id": "task-002",
            "title": "Cook Dinner",
            "channel_id": 0,
            "power_watts": 1800,
            "duration_min": 60,
            "original_start": base + timedelta(hours=19),
            "deadline": base + timedelta(hours=21),
            "is_deferrable": False,
            "priority": "high",
        },
        {
            "id": "task-003",
            "title": "Charge EV",
            "channel_id": 2,
            "power_watts": 3600,
            "duration_min": 240,
            "original_start": base + timedelta(hours=21),
            "deadline": base + timedelta(hours=30),  # next day 6 AM
            "is_deferrable": True,
            "priority": "medium",
        },
        {
            "id": "task-004",
            "title": "Run Dishwasher",
            "channel_id": 0,
            "power_watts": 1200,
            "duration_min": 90,
            "original_start": base + timedelta(hours=20),
            "deadline": base + timedelta(hours=30),
            "is_deferrable": True,
            "priority": "low",
        },
    ]


@pytest.fixture
def sample_grid_forecast_24h():
    """24-hour grid forecast with CAISO-modeled patterns."""
    hours = []
    for h in range(24):
        # Solar ramp: peaks at noon-2 PM
        solar = max(0, 60 * np.sin(np.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0
        renewable_pct = 30 + solar  # base 30% + solar contribution
        # Carbon inversely correlated with renewables
        carbon = 400 - 3 * renewable_pct
        # TOU pricing: PG&E E-TOU-C pattern
        if 0 <= h < 7 or 21 <= h < 24:
            price = 12  # super off-peak
        elif 16 <= h < 21:
            price = 38  # peak
        else:
            price = 22  # off-peak
        # Status
        if price <= 15:
            status = "green"
        elif price <= 25:
            status = "yellow"
        else:
            status = "red"
        hours.append({
            "hour": h,
            "renewable_pct": round(renewable_pct, 1),
            "carbon_intensity": round(carbon, 1),
            "tou_price_cents_kwh": price,
            "status": status,
        })
    return hours


@pytest.fixture
def sample_forecast_array():
    """Mock ML forecast output: 24h x 4 channels x 3 quantiles."""
    rng = np.random.default_rng(42)
    # Shape: (24, 4, 3) — hours x channels x quantiles (p10, p50, p90)
    base = np.array([500, 2400, 3600, 1800])  # per-channel base watts
    forecast = np.zeros((24, 4, 3))
    for h in range(24):
        for ch in range(4):
            center = base[ch] * (0.5 + 0.5 * rng.random())
            forecast[h, ch, 0] = center * 0.8   # p10
            forecast[h, ch, 1] = center          # p50
            forecast[h, ch, 2] = center * 1.2    # p90
    return forecast
