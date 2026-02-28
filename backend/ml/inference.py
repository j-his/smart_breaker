"""
Inference engine for the TFT model.

Loads a trained checkpoint, runs predictions with debouncing, and
post-processes raw model outputs into human-readable dicts ready
for the WebSocket / REST layer.
"""
import time

import numpy as np
import torch

from backend.config import get_model_config, TRAIN, INFERENCE_DEBOUNCE_S
from backend.ml.model.tft import TemporalFusionTransformer

DAY_TYPE_LABELS = ["workday", "weekend", "wfh", "away"]


class InferenceEngine:
    """Wraps a trained TFT model for real-time inference.

    Features:
      - Auto device detection (CUDA/CPU)
      - Debounced prediction (skips if called within INFERENCE_DEBOUNCE_S)
      - Numpy-in / dict-out interface (no torch leakage to callers)
      - Auto batch-dim expansion for single samples
    """

    def __init__(self):
        self.model: TemporalFusionTransformer | None = None
        self.device = torch.device("cpu")
        self._last_inference_time: float = 0.0

    def load(
        self,
        checkpoint_path: str | None = None,
        n_past_features: int = 53,
        n_future_features: int = 10,
        n_static_features: int = 8,
    ) -> None:
        """Load a trained TFT checkpoint.

        Args:
            checkpoint_path: path to model.pt (default: from TRAIN config)
            n_past_features: number of past input features (default: 53)
            n_future_features: number of future input features (default: 10)
            n_static_features: number of static input features (default: 8)
        """
        if checkpoint_path is None:
            checkpoint_path = TRAIN.checkpoint_path

        cfg = get_model_config()

        # Device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        # Build model and load weights
        self.model = TemporalFusionTransformer(
            cfg, n_past_features, n_future_features, n_static_features
        )
        state_dict = torch.load(checkpoint_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()

        n_params = sum(p.numel() for p in self.model.parameters())
        print(f"InferenceEngine loaded: {n_params:,} params on {self.device}")

    def predict(
        self,
        past_features: np.ndarray,
        future_features: np.ndarray,
        static_features: np.ndarray,
        force: bool = False,
    ) -> dict | None:
        """Run inference and return post-processed results.

        Args:
            past_features:    (past_window, 53) or (B, past_window, 53)
            future_features:  (forecast_horizon, 10) or (B, forecast_horizon, 10)
            static_features:  (8,) or (B, 8)
            force: if True, skip debounce check

        Returns:
            dict with keys: forecast, forecast_p50, nilm_probs, nilm_active,
                            anomaly_score, day_type, day_type_confidence,
                            attention_weights
            None if debounced (called too recently)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Debounce check
        now = time.time()
        if not force and (now - self._last_inference_time) < INFERENCE_DEBOUNCE_S:
            return None
        self._last_inference_time = now

        # Auto-add batch dim if needed
        if past_features.ndim == 2:
            past_features = past_features[np.newaxis]
        if future_features.ndim == 2:
            future_features = future_features[np.newaxis]
        if static_features.ndim == 1:
            static_features = static_features[np.newaxis]

        # Convert to tensors
        past_t = torch.tensor(past_features, dtype=torch.float32, device=self.device)
        future_t = torch.tensor(future_features, dtype=torch.float32, device=self.device)
        static_t = torch.tensor(static_features, dtype=torch.float32, device=self.device)

        # Forward pass
        with torch.no_grad():
            out = self.model(past_t, future_t, static_t)

        # Post-process (move to CPU numpy)
        forecast = out["forecast"][0].cpu().numpy()          # (24, 4, 3)
        forecast_p50 = forecast[:, :, 1]                     # (24, 4) — median quantile

        nilm_logits = out["nilm"][0].cpu()                   # (4,)
        nilm_probs = torch.sigmoid(nilm_logits).numpy()      # (4,)
        nilm_active = (nilm_probs > 0.5).tolist()            # list[bool]

        # Anomaly score: normalized reconstruction error
        recon = out["anomaly_recon"][0].cpu().numpy()         # (96, 4)
        # We don't have the original past here, so use reconstruction magnitude
        # as a proxy. The actual anomaly detection compares against known data
        # at the orchestrator level. For now, use the VAE's own mu norm.
        mu = out["anomaly_mu"][0].cpu().numpy()               # (latent_dim,)
        anomaly_score = float(np.clip(np.linalg.norm(mu) / 10.0, 0.0, 1.0))

        # Day type classification
        day_logits = out["day_type"][0].cpu()                 # (n_day_types,)
        day_probs = torch.softmax(day_logits, dim=0)
        day_idx = int(torch.argmax(day_probs))
        day_type = DAY_TYPE_LABELS[day_idx]
        day_type_confidence = float(day_probs[day_idx])

        # Attention weights (may be useful for interpretability)
        attn = out["attention_weights"][0].cpu().numpy()      # (24, 96)

        return {
            "forecast": forecast,                  # (24, 4, 3)
            "forecast_p50": forecast_p50,          # (24, 4)
            "nilm_probs": nilm_probs,              # (4,)
            "nilm_active": nilm_active,            # list[bool]
            "anomaly_score": anomaly_score,        # float 0-1
            "day_type": day_type,                  # str
            "day_type_confidence": day_type_confidence,  # float 0-1
            "attention_weights": attn,             # (24, 96) or None
        }


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    import os

    # Try to load real checkpoint if available
    checkpoint = TRAIN.checkpoint_path
    if not os.path.exists(checkpoint):
        print(f"No checkpoint at {checkpoint}, creating dummy for verification...")
        cfg = get_model_config()
        dummy_model = TemporalFusionTransformer(cfg, 53, 10, 8)
        os.makedirs(os.path.dirname(checkpoint), exist_ok=True)
        torch.save(dummy_model.state_dict(), checkpoint)

    engine = InferenceEngine()
    engine.load()

    cfg = get_model_config()
    past = np.random.randn(cfg.past_window, 53).astype(np.float32)
    future = np.random.randn(cfg.forecast_horizon, 10).astype(np.float32)
    static = np.random.randn(8).astype(np.float32)

    result = engine.predict(past, future, static, force=True)
    assert result is not None

    print("Output keys and shapes:")
    for k, v in result.items():
        if isinstance(v, np.ndarray):
            print(f"  {k}: {v.shape} {v.dtype}")
        else:
            print(f"  {k}: {v}")

    # Verify shapes
    assert result["forecast"].shape == (24, 4, 3)
    assert result["forecast_p50"].shape == (24, 4)
    assert result["nilm_probs"].shape == (4,)
    assert len(result["nilm_active"]) == 4
    assert 0.0 <= result["anomaly_score"] <= 1.0
    assert result["day_type"] in DAY_TYPE_LABELS
    assert 0.0 <= result["day_type_confidence"] <= 1.0
    assert result["attention_weights"].shape == (24, 96)

    # Test debouncing
    result2 = engine.predict(past, future, static, force=False)
    assert result2 is None, "Should be debounced"
    print("\nDebounce test passed (returned None as expected)")

    print("\nAll inference engine checks passed.")
