"""CLI script to fine-tune a pretrained TFT model on new data.

Loads an existing checkpoint and trains further with a lower learning rate.
Useful for adapting a synthetic-data model to real ESP32 sensor data.

Usage:
    python scripts/finetune_model.py                          # defaults
    python scripts/finetune_model.py --epochs 30 --lr 1e-5    # custom
    MODEL_PROFILE=gpu python scripts/finetune_model.py        # GPU model
"""
import sys
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
import pandas as pd
from backend.config import (
    get_model_config, TrainConfig, TRAIN,
    SYNTH_OUTPUT, SYNTH_CALENDARS_DIR,
)
from backend.ml.feature_engine import FeatureEngine
from backend.ml.model.tft import TemporalFusionTransformer
from backend.ml.trainer import TFTTrainer


def main():
    parser = argparse.ArgumentParser(description="Fine-tune a pretrained TFT model")
    parser.add_argument("--checkpoint", type=str, default=TRAIN.checkpoint_path,
                        help="Path to pretrained checkpoint")
    parser.add_argument("--data", type=str, default=str(SYNTH_OUTPUT),
                        help="Path to parquet data file")
    parser.add_argument("--calendars", type=str, default=str(SYNTH_CALENDARS_DIR),
                        help="Path to calendars directory")
    parser.add_argument("--epochs", type=int, default=20,
                        help="Number of fine-tuning epochs (default: 20)")
    parser.add_argument("--lr", type=float, default=1e-5,
                        help="Learning rate (default: 1e-5, ~100x lower than pretraining)")
    parser.add_argument("--patience", type=int, default=5,
                        help="Early stopping patience (default: 5)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output checkpoint path (default: overwrites input)")
    args = parser.parse_args()

    # Load data
    print("Loading data...")
    df = pd.read_parquet(args.data)
    print(f"  Sensor data: {len(df):,} rows")

    cal_dir = Path(args.calendars)
    cal_files = sorted(cal_dir.glob("day_*.json"))
    calendars = []
    for f in cal_files:
        with open(f) as fh:
            calendars.append(json.load(fh))
    total_events = sum(len(d) for d in calendars)
    print(f"  Calendars: {len(calendars)} days, {total_events} events")

    # Build dataset
    cfg = get_model_config()
    fe = FeatureEngine(cfg)
    print("Building dataset...")
    past, future, static, targets = fe.build_dataset(df, calendars)
    print(f"  Dataset: {past.shape[0]} samples")

    # Load pretrained model
    print(f"Loading pretrained checkpoint: {args.checkpoint}")
    model = TemporalFusionTransformer(
        cfg,
        n_past_features=fe.n_past_features,
        n_future_features=fe.n_future_features,
        n_static_features=fe.n_static_features,
    )
    state_dict = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {n_params:,}")

    # Fine-tune config
    output_path = args.output or args.checkpoint
    ft_config = TrainConfig(
        epochs=args.epochs,
        lr=args.lr,
        patience=args.patience,
        checkpoint_path=output_path,
    )
    print(f"  Fine-tune: {ft_config.epochs} epochs, lr={ft_config.lr}, patience={ft_config.patience}")

    # Train
    trainer = TFTTrainer(model, config=ft_config)
    history = trainer.train(past, future, static, targets)

    print(f"\nFinal train loss: {history['train_loss'][-1]:.4f}")
    print(f"Final val loss:   {history['val_loss'][-1]:.4f}")
    print(f"Total epochs:     {len(history['train_loss'])}")
    print(f"Checkpoint saved: {output_path}")


if __name__ == "__main__":
    main()
