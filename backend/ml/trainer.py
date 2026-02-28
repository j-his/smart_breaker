"""
TFT training pipeline with multi-task loss and early stopping.

TFTTrainer wraps the TemporalFusionTransformer model and handles:
  - Device detection (CUDA/CPU)
  - 5 loss functions: QuantileLoss, BCEWithLogitsLoss, VAELoss, CrossEntropyLoss, UncertaintyWeightedLoss
  - AdamW optimizer with CosineAnnealingWarmRestarts scheduler
  - Train/val split, DataLoader creation
  - Early stopping with best-model checkpointing
"""
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from backend.config import TrainConfig, TRAIN, get_model_config
from backend.ml.losses import QuantileLoss, VAELoss, UncertaintyWeightedLoss
from backend.ml.model.tft import TemporalFusionTransformer


class TFTTrainer:
    """Trains a TemporalFusionTransformer with multi-task loss.

    The trainer manages 4 per-head losses (forecast, NILM, anomaly, day_type)
    combined through UncertaintyWeightedLoss. It handles train/val splitting,
    batching, gradient clipping, early stopping, and checkpointing.
    """

    def __init__(self, model: TemporalFusionTransformer, config: TrainConfig = TRAIN):
        self.config = config

        # Device detection
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")
        print(f"Training device: {self.device}")

        self.model = model.to(self.device)

        # Loss functions
        self.quantile_loss = QuantileLoss()
        self.bce_loss = nn.BCEWithLogitsLoss()
        self.vae_loss = VAELoss()
        self.ce_loss = nn.CrossEntropyLoss()
        self.multi_task_loss = UncertaintyWeightedLoss(n_tasks=4)

        # Move loss modules to device
        self.quantile_loss.to(self.device)
        self.multi_task_loss.to(self.device)

        # Optimizer: model params + multi-task loss params (log_vars)
        self.optimizer = torch.optim.AdamW(
            list(model.parameters()) + list(self.multi_task_loss.parameters()),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )

        # Scheduler: cosine annealing with warm restarts
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer, T_0=10, T_mult=2
        )

    def train(
        self,
        past: np.ndarray,
        future: np.ndarray,
        static: np.ndarray,
        targets: dict[str, np.ndarray],
        val_split_idx: int | None = None,
    ) -> dict[str, list]:
        """Run full training loop.

        Args:
            past:    (N, past_window, 53) float32
            future:  (N, forecast_horizon, 10) float32
            static:  (N, 8) float32
            targets: dict with keys forecast/nilm/anomaly/day_type
            val_split_idx: index to split train/val (default: last ~16%)

        Returns:
            history dict with keys: train_loss, val_loss, head_losses
        """
        # Convert numpy -> torch tensors
        past_t = torch.tensor(past, dtype=torch.float32)
        future_t = torch.tensor(future, dtype=torch.float32)
        static_t = torch.tensor(static, dtype=torch.float32)
        forecast_t = torch.tensor(targets["forecast"], dtype=torch.float32)
        nilm_t = torch.tensor(targets["nilm"], dtype=torch.float32)
        anomaly_t = torch.tensor(targets["anomaly"], dtype=torch.float32)
        day_type_t = torch.tensor(targets["day_type"], dtype=torch.long)

        # Train/val split
        n = past_t.shape[0]
        if val_split_idx is None:
            val_split_idx = n - max(1, int(n * 0.16))

        train_ds = TensorDataset(
            past_t[:val_split_idx], future_t[:val_split_idx],
            static_t[:val_split_idx], forecast_t[:val_split_idx],
            nilm_t[:val_split_idx], anomaly_t[:val_split_idx],
            day_type_t[:val_split_idx],
        )
        val_ds = TensorDataset(
            past_t[val_split_idx:], future_t[val_split_idx:],
            static_t[val_split_idx:], forecast_t[val_split_idx:],
            nilm_t[val_split_idx:], anomaly_t[val_split_idx:],
            day_type_t[val_split_idx:],
        )

        train_loader = DataLoader(
            train_ds, batch_size=self.config.batch_size, shuffle=True, drop_last=True
        )
        val_loader = DataLoader(
            val_ds, batch_size=self.config.batch_size, shuffle=False
        )

        print(f"Train samples: {len(train_ds)}, Val samples: {len(val_ds)}")
        print(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

        # Training loop
        history = {"train_loss": [], "val_loss": [], "head_losses": []}
        best_val_loss = float("inf")
        patience_counter = 0
        start_time = time.time()

        for epoch in range(1, self.config.epochs + 1):
            # ── Training phase ──
            self.model.train()
            train_total = 0.0
            train_count = 0

            for batch in train_loader:
                p, f, s, t_fc, t_nilm, t_anom, t_dt = [
                    b.to(self.device) for b in batch
                ]

                self.optimizer.zero_grad()
                out = self.model(p, f, s)

                # Per-head losses
                loss_forecast = self.quantile_loss(out["forecast"], t_fc)
                loss_nilm = self.bce_loss(out["nilm"], t_nilm)
                loss_anomaly = self.vae_loss(
                    out["anomaly_recon"], t_anom,
                    out["anomaly_mu"], out["anomaly_logvar"],
                )
                loss_day_type = self.ce_loss(out["day_type"], t_dt)

                # Combined multi-task loss
                total_loss, info = self.multi_task_loss(
                    [loss_forecast, loss_nilm, loss_anomaly, loss_day_type]
                )

                total_loss.backward()
                nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.config.grad_clip
                )
                self.optimizer.step()

                train_total += total_loss.item()
                train_count += 1

            self.scheduler.step()
            avg_train = train_total / max(train_count, 1)

            # ── Validation phase ──
            self.model.eval()
            val_total = 0.0
            val_count = 0

            with torch.no_grad():
                for batch in val_loader:
                    p, f, s, t_fc, t_nilm, t_anom, t_dt = [
                        b.to(self.device) for b in batch
                    ]
                    out = self.model(p, f, s)

                    loss_forecast = self.quantile_loss(out["forecast"], t_fc)
                    loss_nilm = self.bce_loss(out["nilm"], t_nilm)
                    loss_anomaly = self.vae_loss(
                        out["anomaly_recon"], t_anom,
                        out["anomaly_mu"], out["anomaly_logvar"],
                    )
                    loss_day_type = self.ce_loss(out["day_type"], t_dt)

                    total_loss, info = self.multi_task_loss(
                        [loss_forecast, loss_nilm, loss_anomaly, loss_day_type]
                    )
                    val_total += total_loss.item()
                    val_count += 1

            avg_val = val_total / max(val_count, 1)

            history["train_loss"].append(avg_train)
            history["val_loss"].append(avg_val)
            history["head_losses"].append(info)

            # ── Early stopping + checkpointing ──
            if avg_val < best_val_loss:
                best_val_loss = avg_val
                patience_counter = 0
                torch.save(self.model.state_dict(), self.config.checkpoint_path)
            else:
                patience_counter += 1

            # ── Logging (every 10 epochs) ──
            if epoch % 10 == 0 or epoch == 1:
                elapsed = time.time() - start_time
                lr = self.optimizer.param_groups[0]["lr"]
                print(
                    f"Epoch {epoch:3d}/{self.config.epochs} | "
                    f"train={avg_train:.4f} val={avg_val:.4f} | "
                    f"best_val={best_val_loss:.4f} patience={patience_counter} | "
                    f"lr={lr:.6f} | {elapsed:.0f}s"
                )

            if patience_counter >= self.config.patience:
                print(f"Early stopping at epoch {epoch} (patience={self.config.patience})")
                break

        # Load best checkpoint
        self.model.load_state_dict(
            torch.load(self.config.checkpoint_path, map_location=self.device, weights_only=True)
        )
        elapsed = time.time() - start_time
        print(f"Training complete: {epoch} epochs in {elapsed:.1f}s, best_val={best_val_loss:.4f}")

        return history
