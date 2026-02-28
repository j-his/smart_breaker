"""
Feature engineering pipeline for the TFT model.

Converts raw sensor DataFrames (from data_generator) into sliding-window
numpy arrays ready for model consumption.

Feature budget:
    past:   53 features (raw power, grid, temporal, TOU, rolling, cross-channel, lag, grid delta, calendar)
    future: 10 features (temporal + grid signals known ahead of time)
    static:  8 features (day_type one-hot + channel identity)
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass

from backend.config import ModelConfig


# ── Column Lists ────────────────────────────────────────────────────────────

CH_COLS = [f"ch{i}_watts" for i in range(4)]

PAST_COLS = (
    # Raw power (5)
    CH_COLS + ["total_watts"]
    # Grid signals (4)
    + ["renewable_pct", "carbon_intensity", "tou_price_cents", "temperature_f"]
    # Temporal cyclical (5)
    + ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"]
    # TOU flags (2)
    + ["is_peak", "is_super_offpeak"]
    # Rolling stats: 4 channels x 4 stats (16)
    + [f"ch{i}_{stat}_{w}" for i in range(4)
       for w in (4, 16) for stat in ("rmean", "rstd")]
    # Cross-channel (5)
    + [f"ch{i}_ratio" for i in range(4)] + ["n_active"]
    # Lag features (8)
    + [f"ch{i}_lag{lag}" for i in range(4) for lag in (4, 96)]
    # Grid delta (1)
    + ["price_delta"]
    # Calendar (7)
    + ["events_next_4h", "events_watts_next_4h", "time_to_next_event"]
    + [f"cal_active_ch{i}" for i in range(4)]
)
# 5 + 4 + 5 + 2 + 16 + 5 + 8 + 1 + 7 = 53

FUTURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
    "is_peak", "is_super_offpeak",
    "renewable_pct", "carbon_intensity", "tou_price_cents",
]
# 10

DAY_TYPE_MAP = {"workday": 0, "weekend": 1, "wfh": 2, "away": 3}


class FeatureEngine:
    """Builds sliding-window tensors from a household DataFrame + calendar events."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self._n_past = len(PAST_COLS)
        self._n_future = len(FUTURE_COLS)
        self._n_static = config.n_day_types + config.n_channels  # 4 + 4 = 8

    # ── Public Properties ───────────────────────────────────────────────────

    @property
    def n_past_features(self) -> int:
        return self._n_past

    @property
    def n_future_features(self) -> int:
        return self._n_future

    @property
    def n_static_features(self) -> int:
        return self._n_static

    # ── Main Entry Point ────────────────────────────────────────────────────

    def build_dataset(
        self,
        df: pd.DataFrame,
        calendars: list[list[dict]],
        resample_min: int = 15,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        """
        Full pipeline: DataFrame -> (past, future, static, targets).

        Returns:
            past:    (n_samples, past_window, 53)   float32
            future:  (n_samples, forecast_horizon, 10) float32
            static:  (n_samples, 8)                  float32
            targets: dict with keys forecast/nilm/anomaly/day_type
        """
        df = df.copy()

        # 1. Resample to target resolution
        df = self._resample(df, resample_min)

        # 2-8. Feature engineering
        df = self._add_temporal_features(df)
        df = self._add_tou_flags(df)
        df = self._add_rolling_stats(df)
        df = self._add_cross_channel(df)
        df = self._add_lag_features(df)
        df = self._add_grid_features(df)
        df = self._add_calendar_features(df, calendars)

        # 9. Forward-fill then back-fill the enriched DataFrame
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].ffill().bfill()

        # 10. Build sliding windows
        past, future, static, targets = self._build_sliding_windows(df)

        # 11. Safety net: replace any surviving NaN with 0
        past = np.nan_to_num(past, nan=0.0)
        future = np.nan_to_num(future, nan=0.0)
        static = np.nan_to_num(static, nan=0.0)
        targets = {
            k: np.nan_to_num(v.astype(float), nan=0.0).astype(v.dtype)
            for k, v in targets.items()
        }

        # 12. Cast to float32
        past = past.astype(np.float32)
        future = future.astype(np.float32)
        static = static.astype(np.float32)
        for k, v in targets.items():
            if v.dtype != np.int64:
                targets[k] = v.astype(np.float32)

        return past, future, static, targets

    # ── Private Helpers ─────────────────────────────────────────────────────

    def _resample(self, df: pd.DataFrame, resample_min: int) -> pd.DataFrame:
        """Resample to target resolution (e.g. 1-min -> 15-min)."""
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")

        # Separate numeric and categorical columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        has_day_type = "day_type" in df.columns

        rule = f"{resample_min}min"
        resampled = df[numeric_cols].resample(rule).mean()

        if has_day_type:
            day_type_resampled = df["day_type"].resample(rule).first()
            resampled = resampled.join(day_type_resampled)

        # Forward-fill then back-fill gaps from resampling
        numeric_cols_r = resampled.select_dtypes(include=[np.number]).columns
        resampled[numeric_cols_r] = resampled[numeric_cols_r].ffill().bfill()
        if has_day_type:
            resampled["day_type"] = resampled["day_type"].ffill().bfill()

        resampled = resampled.reset_index()
        return resampled

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cyclical hour and day-of-week encodings."""
        ts = pd.to_datetime(df["timestamp"])
        hour_frac = ts.dt.hour + ts.dt.minute / 60.0
        dow = ts.dt.dayofweek  # 0=Monday

        df["hour_sin"] = np.sin(2 * np.pi * hour_frac / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour_frac / 24)
        df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        df["is_weekend"] = (dow >= 5).astype(float)
        return df

    def _add_tou_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Time-of-use pricing flags based on PG&E E-TOU-C schedule."""
        ts = pd.to_datetime(df["timestamp"])
        hour = ts.dt.hour
        df["is_peak"] = ((hour >= 16) & (hour < 21)).astype(float)
        df["is_super_offpeak"] = ((hour < 7) | (hour >= 21)).astype(float)
        return df

    def _add_rolling_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rolling mean and std for each channel at windows 4 and 16."""
        for i in range(4):
            col = f"ch{i}_watts"
            for w in (4, 16):
                df[f"ch{i}_rmean_{w}"] = (
                    df[col].rolling(window=w, min_periods=1).mean()
                )
                df[f"ch{i}_rstd_{w}"] = (
                    df[col].rolling(window=w, min_periods=1).std().fillna(0)
                )
        return df

    def _add_cross_channel(self, df: pd.DataFrame) -> pd.DataFrame:
        """Channel ratios and active-channel count."""
        total = df["total_watts"] + 1e-8
        for i in range(4):
            df[f"ch{i}_ratio"] = df[f"ch{i}_watts"] / total
        df["n_active"] = sum(
            (df[f"ch{i}_watts"] > 50).astype(float) for i in range(4)
        )
        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lag features at 1h (4 steps) and 24h (96 steps)."""
        for i in range(4):
            col = f"ch{i}_watts"
            df[f"ch{i}_lag4"] = df[col].shift(4)
            df[f"ch{i}_lag96"] = df[col].shift(96)
        return df

    def _add_grid_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price momentum (first difference)."""
        df["price_delta"] = df["tou_price_cents"].diff()
        return df

    def _add_calendar_features(
        self, df: pd.DataFrame, calendars: list[list[dict]]
    ) -> pd.DataFrame:
        """Calendar-based features using O(events x timesteps) loop."""
        # Flatten all events across all days
        all_events = []
        for day_events in calendars:
            for ev in day_events:
                start = pd.Timestamp(ev["start"])
                end = pd.Timestamp(ev.get("end", ev["start"]))
                all_events.append({
                    "start": start,
                    "end": end,
                    "channel_id": ev.get("channel_id", 0),
                    "power_watts": ev.get("power_watts", 0),
                })

        n = len(df)
        events_next_4h = np.zeros(n)
        events_watts_next_4h = np.zeros(n)
        time_to_next_event = np.full(n, 24.0)  # capped at 24h
        cal_active = np.zeros((n, 4))

        ts = pd.to_datetime(df["timestamp"])
        four_hours = pd.Timedelta(hours=4)

        for ev in all_events:
            ev_start = ev["start"]
            ev_end = ev["end"]
            ch = ev["channel_id"]
            watts = ev["power_watts"]

            for idx in range(n):
                row_ts = ts.iloc[idx]
                delta_start = (ev_start - row_ts).total_seconds() / 3600.0

                # Count events starting within next 4 hours
                if 0 <= delta_start <= 4:
                    events_next_4h[idx] += 1
                    events_watts_next_4h[idx] += watts

                # Time to next event (capped at 24h)
                if delta_start >= 0 and delta_start < time_to_next_event[idx]:
                    time_to_next_event[idx] = delta_start

                # Is this event currently active?
                if ev_start <= row_ts < ev_end and 0 <= ch < 4:
                    cal_active[idx, ch] = 1.0

        df["events_next_4h"] = events_next_4h
        df["events_watts_next_4h"] = events_watts_next_4h
        df["time_to_next_event"] = time_to_next_event
        for i in range(4):
            df[f"cal_active_ch{i}"] = cal_active[:, i]

        return df

    def _build_sliding_windows(
        self, df: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
        """Assemble sliding-window numpy arrays from the enriched DataFrame."""
        pw = self.config.past_window       # 96
        fh = self.config.forecast_horizon  # 24
        future_steps = fh * 4              # 96 (at 15-min resolution)
        total_window = pw + future_steps   # 192

        n_samples = len(df) - total_window + 1
        if n_samples <= 0:
            raise ValueError(
                f"DataFrame too short ({len(df)} rows) for window size {total_window}"
            )

        # Extract arrays for past and future columns
        past_data = df[PAST_COLS].values    # (T, 53)
        future_data = df[FUTURE_COLS].values  # (T, 10)

        # Channel watts for targets
        ch_data = df[CH_COLS].values  # (T, 4)

        # Day type for static features and target
        day_type_series = df["day_type"].map(DAY_TYPE_MAP).fillna(0).astype(int)
        day_type_vals = day_type_series.values

        # Preallocate output arrays
        past = np.empty((n_samples, pw, self._n_past))
        future = np.empty((n_samples, fh, self._n_future))
        static = np.empty((n_samples, self._n_static))
        forecast_target = np.empty((n_samples, fh, 4))
        nilm_target = np.empty((n_samples, 4))
        anomaly_target = np.empty((n_samples, pw, 4))
        day_type_target = np.empty(n_samples, dtype=np.int64)

        for i in range(n_samples):
            # Past window: [i, i+pw)
            past[i] = past_data[i : i + pw]

            # Future window: [i+pw, i+pw+future_steps), subsampled every 4th step
            future_raw = future_data[i + pw : i + pw + future_steps]
            future[i] = future_raw[::4]  # every 4th step -> 24 hourly steps

            # Static: day_type one-hot at the boundary + channel identity
            dt_idx = day_type_vals[i + pw]
            one_hot = np.zeros(self.config.n_day_types)
            one_hot[dt_idx] = 1.0
            ch_identity = np.ones(self.config.n_channels)
            static[i] = np.concatenate([one_hot, ch_identity])

            # Targets
            future_ch = ch_data[i + pw : i + pw + future_steps]
            forecast_target[i] = future_ch[::4]  # (24, 4) hourly

            boundary_ch = ch_data[i + pw]  # channel watts at window boundary
            nilm_target[i] = (boundary_ch > 50).astype(float)

            anomaly_target[i] = ch_data[i : i + pw]  # reconstruction target

            day_type_target[i] = dt_idx

        targets = {
            "forecast": forecast_target,
            "nilm": nilm_target,
            "anomaly": anomaly_target,
            "day_type": day_type_target,
        }

        return past, future, static, targets
