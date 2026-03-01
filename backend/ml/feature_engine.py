"""
Feature engineering pipeline for the TFT model.

Converts raw sensor DataFrames (from data_generator) into sliding-window
numpy arrays ready for model consumption.

Feature budget:
    past:   53 features (raw power, grid, temporal, TOU, rolling, cross-channel, lag, grid delta, calendar)
    future: 10 features (temporal + grid signals known ahead of time)
    static:  8 features (day_type one-hot + channel identity)
"""
import math
from datetime import datetime, timezone

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

    # ── Real-Time Feature Bridge ─────────────────────────────────────────────

    def build_realtime_window(
        self,
        buffer_window: np.ndarray,
        now: datetime,
        grid_forecast: list[dict],
        calendar_events: list[dict] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert a live SensorBuffer window into model-ready tensors.

        Unlike build_dataset() which operates on full DataFrames, this method
        works with the raw (96, 8) ring buffer and computes all 53 past features,
        10 future features, and 8 static features from scratch.

        Args:
            buffer_window: (96, 8) array — [ch0-3, total, renewable, carbon, price]
            now: current UTC datetime
            grid_forecast: 24-element list of hourly grid forecast dicts
            calendar_events: optional list of event dicts with start/end/channel_id/power_watts

        Returns:
            (past, future, static) as float32 numpy arrays:
                past:   (96, 53)
                future: (24, 10)
                static: (8,)
        """
        T = buffer_window.shape[0]  # 96
        cal_events = calendar_events or []

        # ── Past Features (96, 53) ──────────────────────────────────────────

        # Raw power (5): ch0-3 + total — directly from buffer cols 0-4
        raw_power = buffer_window[:, :5]  # (96, 5)

        # Grid signals (4): renewable, carbon, price from buffer + temperature
        month = now.month
        temp_f = 72.0 if month in (11, 12, 1, 2, 3) else 85.0
        grid_signals = np.column_stack([
            buffer_window[:, 5],   # renewable_pct
            buffer_window[:, 6],   # carbon_intensity
            buffer_window[:, 7],   # tou_price_cents
            np.full(T, temp_f),    # temperature_f (seasonal default)
        ])  # (96, 4)

        # Temporal cyclical (5): sin/cos hour, sin/cos dow, is_weekend
        # Build timestamps for each of the 96 steps (15-min intervals backward from now)
        step_hours = np.arange(T - 1, -1, -1) * 0.25  # hours ago
        ts_hours = np.array([
            (now.hour + now.minute / 60.0) - h for h in step_hours
        ]) % 24.0
        # Day-of-week for each step
        base_dow = now.weekday()
        ts_dows = np.array([
            (base_dow - h // 24) % 7 for h in step_hours
        ], dtype=float)

        hour_sin = np.sin(2 * math.pi * ts_hours / 24.0)
        hour_cos = np.cos(2 * math.pi * ts_hours / 24.0)
        dow_sin = np.sin(2 * math.pi * ts_dows / 7.0)
        dow_cos = np.cos(2 * math.pi * ts_dows / 7.0)
        is_weekend = (ts_dows >= 5).astype(np.float32)
        temporal = np.column_stack([hour_sin, hour_cos, dow_sin, dow_cos, is_weekend])  # (96, 5)

        # TOU flags (2): is_peak (16-21), is_super_offpeak (<7 or >=21)
        is_peak = ((ts_hours >= 16) & (ts_hours < 21)).astype(np.float32)
        is_super_offpeak = ((ts_hours < 7) | (ts_hours >= 21)).astype(np.float32)
        tou_flags = np.column_stack([is_peak, is_super_offpeak])  # (96, 2)

        # Rolling stats (16): rmean/rstd at windows 4 and 16 for each channel
        rolling_parts = []
        for i in range(4):
            ch_col = buffer_window[:, i]
            for w in (4, 16):
                # Cumulative rolling via pandas-like logic, min_periods=1
                cumsum = np.cumsum(np.insert(ch_col, 0, 0))
                means = np.empty(T)
                stds = np.empty(T)
                for t in range(T):
                    start = max(0, t - w + 1)
                    window_vals = ch_col[start:t + 1]
                    means[t] = window_vals.mean()
                    stds[t] = window_vals.std() if len(window_vals) > 1 else 0.0
                rolling_parts.append(means)
                rolling_parts.append(stds)
        rolling_stats = np.column_stack(rolling_parts)  # (96, 16)

        # Cross-channel (5): ch_ratio for each + n_active
        total_safe = buffer_window[:, 4] + 1e-8
        ch_ratios = np.column_stack([
            buffer_window[:, i] / total_safe for i in range(4)
        ])  # (96, 4)
        n_active = np.sum(buffer_window[:, :4] > 50, axis=1, keepdims=True).astype(np.float32)
        cross_channel = np.column_stack([ch_ratios, n_active])  # (96, 5)

        # Lag features (8): shift ch0-3 by 4 and 96
        lag_parts = []
        for i in range(4):
            ch_col = buffer_window[:, i]
            lag4 = np.empty(T)
            lag4[:4] = 0.0
            lag4[4:] = ch_col[:-4]
            lag96 = np.zeros(T)  # all zeros since we only have 96 steps
            lag_parts.extend([lag4, lag96])
        lag_features = np.column_stack(lag_parts)  # (96, 8)

        # Grid delta (1): first difference of price column
        price_col = buffer_window[:, 7]
        price_delta = np.empty(T)
        price_delta[0] = 0.0
        price_delta[1:] = np.diff(price_col)
        price_delta = price_delta.reshape(-1, 1)  # (96, 1)

        # Calendar features (7): events_next_4h, watts_next_4h, time_to_next, cal_active_ch0-3
        events_next_4h = np.zeros(T)
        events_watts_next_4h = np.zeros(T)
        time_to_next_event = np.full(T, 24.0)
        cal_active = np.zeros((T, 4))

        if cal_events:
            for t_idx in range(T):
                step_dt_hour = ts_hours[t_idx]
                for ev in cal_events:
                    ev_start = ev.get("start")
                    ev_end = ev.get("end")
                    if ev_start is None:
                        continue
                    if isinstance(ev_start, str):
                        from dateutil import parser as dp
                        ev_start = dp.isoparse(ev_start)
                        ev_end = dp.isoparse(ev_end) if ev_end else ev_start
                    delta_h = (ev_start - now).total_seconds() / 3600.0
                    if 0 <= delta_h <= 4:
                        events_next_4h[t_idx] += 1
                        events_watts_next_4h[t_idx] += ev.get("power_watts", 0)
                    if delta_h >= 0 and delta_h < time_to_next_event[t_idx]:
                        time_to_next_event[t_idx] = delta_h
                    ch = ev.get("channel_id", 0)
                    if ev_start <= now and (ev_end is None or now < ev_end) and 0 <= ch < 4:
                        cal_active[t_idx, ch] = 1.0

        calendar_feats = np.column_stack([
            events_next_4h, events_watts_next_4h, time_to_next_event,
            cal_active[:, 0], cal_active[:, 1], cal_active[:, 2], cal_active[:, 3],
        ])  # (96, 7)

        # Assemble past: 5+4+5+2+16+5+8+1+7 = 53
        past = np.concatenate([
            raw_power, grid_signals, temporal, tou_flags,
            rolling_stats, cross_channel, lag_features, price_delta,
            calendar_feats,
        ], axis=1).astype(np.float32)  # (96, 53)

        # ── Future Features (24, 10) ────────────────────────────────────────

        future = np.zeros((self.config.forecast_horizon, self._n_future), dtype=np.float32)
        for h_idx in range(min(len(grid_forecast), self.config.forecast_horizon)):
            entry = grid_forecast[h_idx]
            future_hour = (now.hour + h_idx + 1) % 24
            future_dow = (now.weekday() + (now.hour + h_idx + 1) // 24) % 7

            future[h_idx, 0] = math.sin(2 * math.pi * future_hour / 24.0)
            future[h_idx, 1] = math.cos(2 * math.pi * future_hour / 24.0)
            future[h_idx, 2] = math.sin(2 * math.pi * future_dow / 7.0)
            future[h_idx, 3] = math.cos(2 * math.pi * future_dow / 7.0)
            future[h_idx, 4] = 1.0 if future_dow >= 5 else 0.0
            future[h_idx, 5] = 1.0 if 16 <= future_hour < 21 else 0.0
            future[h_idx, 6] = 1.0 if future_hour < 7 or future_hour >= 21 else 0.0
            future[h_idx, 7] = entry.get("renewable_pct", 0.0)
            future[h_idx, 8] = entry.get("carbon_intensity_gco2_kwh", 0.0)
            future[h_idx, 9] = entry.get("tou_price_cents_kwh", 0.0)

        # ── Static Features (8) ─────────────────────────────────────────────

        # Day type one-hot: default workday [1,0,0,0]
        day_type_oh = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Channel identity: all channels present [1,1,1,1]
        ch_identity = np.ones(self.config.n_channels, dtype=np.float32)
        static = np.concatenate([day_type_oh, ch_identity])  # (8,)

        # NaN safety
        past = np.nan_to_num(past, nan=0.0)
        future = np.nan_to_num(future, nan=0.0)
        static = np.nan_to_num(static, nan=0.0)

        return past, future, static

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
