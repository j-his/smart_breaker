"""CLI script to generate synthetic household data."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from backend.config import SYNTH_DAYS, SYNTH_OUTPUT, SYNTH_CALENDARS_DIR
from backend.ml.data_generator import HouseholdSimulator


def main():
    print(f"Generating {SYNTH_DAYS} days of synthetic household data...")
    sim = HouseholdSimulator(seed=42, n_days=SYNTH_DAYS)
    df, calendars = sim.generate()

    # Save sensor + grid data
    SYNTH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SYNTH_OUTPUT, index=False)
    print(f"  Sensor data: {SYNTH_OUTPUT} ({len(df):,} rows, {df.memory_usage(deep=True).sum() / 1e6:.1f} MB)")

    # Save calendars as JSON
    SYNTH_CALENDARS_DIR.mkdir(parents=True, exist_ok=True)
    for day_idx, day_events in enumerate(calendars):
        path = SYNTH_CALENDARS_DIR / f"day_{day_idx:03d}.json"
        with open(path, "w") as f:
            json.dump(day_events, f, indent=2)
    total_events = sum(len(d) for d in calendars)
    print(f"  Calendars: {len(calendars)} days, {total_events} total events")
    print("Done.")


if __name__ == "__main__":
    main()
