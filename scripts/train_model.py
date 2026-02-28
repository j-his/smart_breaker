"""CLI script to train the TFT model on synthetic household data."""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from backend.config import get_model_config, SYNTH_OUTPUT, SYNTH_CALENDARS_DIR
from backend.ml.feature_engine import FeatureEngine
from backend.ml.model.tft import TemporalFusionTransformer
from backend.ml.trainer import TFTTrainer


def main():
    # Load synthetic data
    print("Loading synthetic data...")
    df = pd.read_parquet(SYNTH_OUTPUT)
    print(f"  Sensor data: {len(df):,} rows")

    # Load calendars
    cal_files = sorted(SYNTH_CALENDARS_DIR.glob("day_*.json"))
    calendars = []
    for f in cal_files:
        with open(f) as fh:
            calendars.append(json.load(fh))
    total_events = sum(len(d) for d in calendars)
    print(f"  Calendars: {len(calendars)} days, {total_events} events")

    # Build dataset
    cfg = get_model_config()
    fe = FeatureEngine(cfg)
    print("Building dataset (this may take a few minutes)...")
    past, future, static, targets = fe.build_dataset(df, calendars)
    print(f"  Dataset: {past.shape[0]} samples")
    print(f"  Past: {past.shape}, Future: {future.shape}, Static: {static.shape}")

    # Create model
    model = TemporalFusionTransformer(
        cfg,
        n_past_features=fe.n_past_features,
        n_future_features=fe.n_future_features,
        n_static_features=fe.n_static_features,
    )
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {n_params:,}")

    # Train
    trainer = TFTTrainer(model)
    history = trainer.train(past, future, static, targets)

    print(f"\nFinal train loss: {history['train_loss'][-1]:.4f}")
    print(f"Final val loss:   {history['val_loss'][-1]:.4f}")
    print(f"Total epochs:     {len(history['train_loss'])}")


if __name__ == "__main__":
    main()
