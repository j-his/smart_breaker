"""
Synthetic household power data + mock calendar generator.

Generates N days of realistic 4-channel power readings at 1-minute resolution,
correlated calendar events, and parallel grid signal data modeled on CAISO patterns.

Usage:
    sim = HouseholdSimulator(seed=42, n_days=60)
    df, calendars = sim.generate()
    df.to_parquet("data/synthetic_household.parquet")
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass


# ── Appliance Draw Curve Definitions ─────────────────────────────────────────

@dataclass
class ApplianceProfile:
    name: str
    base_watts: float
    noise_pct: float  # jitter as fraction of base_watts

    def draw_curve(self, t: np.ndarray, duration: float) -> np.ndarray:
        """Override in subclasses for realistic waveforms. t in [0, duration]."""
        return np.full_like(t, self.base_watts, dtype=float)


class StoveProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Cycles between low simmer and high heat
        phase = np.sin(2 * np.pi * t / duration * 3)
        return self.base_watts * (0.7 + 0.3 * phase)


class DryerProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Alternates heating element ON/OFF (square-ish wave)
        cycle = (np.sin(2 * np.pi * t / duration * 4) > 0).astype(float)
        return self.base_watts * (0.4 + 0.6 * cycle)


class EVChargerProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Mostly constant with slight taper at end
        taper = np.where(t / duration > 0.85, 1.0 - (t / duration - 0.85) * 3, 1.0)
        return self.base_watts * np.clip(taper, 0.2, 1.0)


class ACProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Compressor cycling: ON for ~70% of each cycle
        cycle = (np.sin(2 * np.pi * t / duration * 6) > -0.4).astype(float)
        return self.base_watts * (0.15 + 0.85 * cycle)


class WaterHeaterProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Spike then exponential taper
        return self.base_watts * np.exp(-3 * t / duration)


class DishwasherProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Three phases: wash (100%), rinse (30%), dry (80%)
        frac = t / duration
        return self.base_watts * np.where(
            frac < 0.35, 1.0, np.where(frac < 0.6, 0.3, 0.8)
        )


class OvenProfile(ApplianceProfile):
    def draw_curve(self, t, duration):
        # Thermostat cycling
        cycle = (np.sin(2 * np.pi * t / duration * 2) > 0).astype(float)
        return self.base_watts * (0.5 + 0.5 * cycle)


APPLIANCE_PROFILES = {
    "inductive_stove": StoveProfile("inductive_stove", 1800, 0.03),
    "dryer": DryerProfile("dryer", 2400, 0.03),
    "ev_charger": EVChargerProfile("ev_charger", 3600, 0.02),
    "air_conditioning": ACProfile("air_conditioning", 1800, 0.04),
    "water_heater": WaterHeaterProfile("water_heater", 4500, 0.03),
    "dishwasher": DishwasherProfile("dishwasher", 1200, 0.03),
    "oven": OvenProfile("oven", 2500, 0.02),
    "lighting": ApplianceProfile("lighting", 200, 0.01),
}

# ── Channel-to-Appliance Default Mapping ─────────────────────────────────────
DEFAULT_CHANNELS = [
    {"channel_id": 0, "zone": "kitchen", "appliance": "inductive_stove"},
    {"channel_id": 1, "zone": "laundry_room", "appliance": "dryer"},
    {"channel_id": 2, "zone": "garage", "appliance": "ev_charger"},
    {"channel_id": 3, "zone": "bedroom", "appliance": "air_conditioning"},
]

# ── User Behavior Probability Distributions ──────────────────────────────────
# (appliance_for_channel, channel_id, mean_start_hour, std_hours,
#  {day_type: prob}, (min_dur, max_dur))
BEHAVIOR_PATTERNS = [
    ("inductive_stove", 0, 7.0, 0.5, {"workday": 0.7, "weekend": 0.5, "wfh": 0.8, "away": 0.0}, (15, 30)),   # breakfast
    ("inductive_stove", 0, 12.0, 0.5, {"workday": 0.2, "weekend": 0.6, "wfh": 0.7, "away": 0.0}, (20, 45)),  # lunch
    ("inductive_stove", 0, 19.0, 0.7, {"workday": 0.85, "weekend": 0.8, "wfh": 0.85, "away": 0.0}, (30, 90)),  # dinner
    ("dryer", 1, 10.0, 2.0, {"workday": 0.15, "weekend": 0.7, "wfh": 0.3, "away": 0.0}, (45, 75)),
    ("ev_charger", 2, 21.5, 1.0, {"workday": 0.6, "weekend": 0.3, "wfh": 0.2, "away": 0.0}, (180, 360)),
    ("air_conditioning", 3, 14.0, 3.0, {"workday": 0.5, "weekend": 0.7, "wfh": 0.8, "away": 0.1}, (60, 360)),
]

# Calendar event titles corresponding to appliance usage
EVENT_TITLES = {
    ("inductive_stove", 7): "Make Breakfast",
    ("inductive_stove", 12): "Cook Lunch",
    ("inductive_stove", 19): "Cook Dinner",
    ("dryer", 10): "Run Dryer (Laundry)",
    ("ev_charger", 21): "Charge EV",
    ("air_conditioning", 14): "AC Cooling",
}

DEFERRABLE_SET = {"dryer", "ev_charger", "dishwasher", "water_heater"}

# ── Day-Type Markov Chain ────────────────────────────────────────────────────
DAY_TYPE_TRANSITIONS = {
    "workday": {"workday": 0.7, "weekend": 0.15, "wfh": 0.1, "away": 0.05},
    "weekend": {"workday": 0.6, "weekend": 0.2, "wfh": 0.1, "away": 0.1},
    "wfh": {"workday": 0.5, "weekend": 0.15, "wfh": 0.3, "away": 0.05},
    "away": {"workday": 0.4, "weekend": 0.2, "wfh": 0.1, "away": 0.3},
}


class HouseholdSimulator:
    """Generates synthetic household power data with correlated calendars."""

    def __init__(self, seed: int = 42, n_days: int = 60,
                 channels: list[dict] | None = None):
        self.rng = np.random.default_rng(seed)
        self.n_days = n_days
        self.channels = channels or DEFAULT_CHANNELS
        self.minutes_per_day = 1440

    def generate(self) -> tuple[pd.DataFrame, list[list[dict]]]:
        """Generate full dataset. Returns (DataFrame, list_of_daily_calendar_events)."""
        total_minutes = self.n_days * self.minutes_per_day
        timestamps = [
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=m)
            for m in range(total_minutes)
        ]

        # Initialize arrays
        ch_data = np.zeros((total_minutes, 4))  # 4 channels
        day_types = self._generate_day_sequence()
        temperatures = self._generate_temperature_curve(total_minutes)
        grid = self._generate_grid_signals(total_minutes)
        all_calendars: list[list[dict]] = []

        # Generate each day
        for day_idx in range(self.n_days):
            start = day_idx * self.minutes_per_day
            end = start + self.minutes_per_day
            day_type = day_types[day_idx]
            temp_today = temperatures[start:end]
            day_events = []

            # Add baseline (always-on loads: ~50-150W per channel)
            for ch in range(4):
                baseline = 30 + self.rng.random() * 50
                ch_data[start:end, ch] += baseline

            # HVAC scaling with temperature (channel 3 = AC)
            if day_type != "away":
                self._add_hvac_load(ch_data, start, end, temp_today, day_type)

            # Sample and add appliance events based on behavior patterns
            for pattern in BEHAVIOR_PATTERNS:
                appliance, ch, hour_mean, hour_std, probs, dur_range = pattern
                prob = probs.get(day_type, 0)
                if self.rng.random() < prob:
                    start_hour = self.rng.normal(hour_mean, hour_std)
                    start_hour = np.clip(start_hour, 0, 23.5)
                    duration_min = int(self.rng.integers(dur_range[0], dur_range[1] + 1))
                    start_min = int(start_hour * 60)
                    end_min = min(start_min + duration_min, self.minutes_per_day)

                    # Generate draw curve
                    profile = APPLIANCE_PROFILES.get(appliance)
                    if profile:
                        t = np.arange(end_min - start_min, dtype=float)
                        curve = profile.draw_curve(t, float(end_min - start_min))
                        # Add noise
                        noise = 1.0 + self.rng.normal(0, profile.noise_pct, len(t))
                        curve = curve * noise
                        ch_data[start + start_min:start + end_min, ch] += curve

                    # Create calendar event
                    title_key = (appliance, int(round(hour_mean)))
                    title = EVENT_TITLES.get(title_key, f"Use {appliance.replace('_', ' ').title()}")
                    event_start = timestamps[start + start_min]
                    event_end = timestamps[start + min(end_min, self.minutes_per_day - 1)]
                    day_events.append({
                        "title": title,
                        "start": event_start.isoformat(),
                        "end": event_end.isoformat(),
                        "duration_min": end_min - start_min,
                        "channel_id": ch,
                        "appliance": appliance,
                        "zone": self.channels[ch]["zone"],
                        "power_watts": int(profile.base_watts) if profile else 1000,
                        "is_deferrable": appliance in DEFERRABLE_SET,
                    })

            # Add random anomaly (~5% of days)
            if self.rng.random() < 0.05:
                anomaly_ch = self.rng.integers(0, 4)
                anomaly_start = self.rng.integers(0, self.minutes_per_day - 60)
                ch_data[start + anomaly_start:start + anomaly_start + 60, anomaly_ch] *= 3.0

            # Add sensor dropout (~3% of days)
            if self.rng.random() < 0.03:
                dropout_start = self.rng.integers(0, self.minutes_per_day - 30)
                ch_data[start + dropout_start:start + dropout_start + 30, :] = np.nan

            all_calendars.append(day_events)

        # Clip negatives from noise
        ch_data = np.clip(ch_data, 0, None)

        # Build DataFrame
        df = pd.DataFrame({
            "timestamp": timestamps,
            "ch0_watts": ch_data[:, 0],
            "ch1_watts": ch_data[:, 1],
            "ch2_watts": ch_data[:, 2],
            "ch3_watts": ch_data[:, 3],
            "total_watts": np.nansum(ch_data, axis=1),
            "renewable_pct": grid["renewable_pct"],
            "carbon_intensity": grid["carbon_intensity"],
            "tou_price_cents": grid["tou_price_cents"],
            "day_type": np.repeat(day_types, self.minutes_per_day),
            "temperature_f": temperatures,
        })

        return df, all_calendars

    def _generate_day_sequence(self) -> list[str]:
        """Markov chain for day types."""
        days = []
        current = "workday"
        for i in range(self.n_days):
            # Force weekends on actual Sat/Sun positions
            day_of_week = i % 7
            if day_of_week in (5, 6):
                current = "weekend"
            else:
                probs = DAY_TYPE_TRANSITIONS[current]
                # Remove weekend from weekday transitions
                weekday_probs = {k: v for k, v in probs.items() if k != "weekend"}
                total = sum(weekday_probs.values())
                weekday_probs = {k: v / total for k, v in weekday_probs.items()}
                current = self.rng.choice(
                    list(weekday_probs.keys()),
                    p=list(weekday_probs.values()),
                )
            days.append(current)
        return days

    def _generate_temperature_curve(self, total_minutes: int) -> np.ndarray:
        """Sinusoidal seasonal + daily temperature variation."""
        t = np.arange(total_minutes, dtype=float)
        day_frac = t / self.minutes_per_day
        # Seasonal: winter=40F, summer=90F (sinusoidal over 365 days)
        seasonal = 65 + 25 * np.sin(2 * np.pi * (day_frac - 80) / 365)
        # Daily: cooler at night, warmer afternoon
        hour_frac = (t % self.minutes_per_day) / self.minutes_per_day
        daily = -8 + 16 * np.sin(np.pi * (hour_frac - 0.25))
        # Noise
        noise = self.rng.normal(0, 2, total_minutes)
        return seasonal + daily + noise

    def _generate_grid_signals(self, total_minutes: int) -> dict[str, np.ndarray]:
        """CAISO-modeled grid signals at 1-min resolution."""
        t = np.arange(total_minutes, dtype=float)
        hour_of_day = (t % self.minutes_per_day) / 60

        # Solar contribution: bell curve peaking at 1 PM
        solar = np.maximum(0, 65 * np.exp(-0.5 * ((hour_of_day - 13) / 3) ** 2))
        # Wind: stronger at night
        wind = 10 + 8 * np.sin(2 * np.pi * (hour_of_day - 2) / 24)
        renewable_pct = np.clip(25 + solar + wind + self.rng.normal(0, 3, total_minutes), 10, 95)

        # Carbon intensity: inversely correlated with renewables
        carbon_intensity = np.clip(450 - 3.5 * renewable_pct + self.rng.normal(0, 15, total_minutes), 80, 500)

        # TOU pricing: PG&E E-TOU-C schedule
        tou_price = np.where(
            (hour_of_day >= 16) & (hour_of_day < 21), 38,  # peak
            np.where(
                ((hour_of_day >= 0) & (hour_of_day < 7)) | (hour_of_day >= 21), 12,  # super off-peak
                22  # off-peak
            )
        ).astype(float)
        # Add slight daily noise
        tou_price = tou_price + self.rng.normal(0, 0.5, total_minutes)

        return {
            "renewable_pct": np.round(renewable_pct, 1),
            "carbon_intensity": np.round(carbon_intensity, 1),
            "tou_price_cents": np.round(np.clip(tou_price, 5, 50), 1),
        }

    def _add_hvac_load(self, ch_data: np.ndarray, start: int, end: int,
                       temp: np.ndarray, day_type: str):
        """Add temperature-dependent HVAC load to channel 3 (AC)."""
        # AC kicks in above 75F, heating below 55F
        ac_load = np.where(temp > 75, (temp - 75) * 120, 0)  # ~120W per degree above 75
        heat_load = np.where(temp < 55, (55 - temp) * 100, 0)
        hvac = ac_load + heat_load
        # Compressor cycling noise
        cycling = (np.sin(np.linspace(0, 40 * np.pi, len(hvac))) > -0.3).astype(float)
        hvac = hvac * cycling * (0.8 if day_type == "wfh" else 1.0)
        ch_data[start:end, 3] += hvac
