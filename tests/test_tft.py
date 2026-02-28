"""Tests for the full Temporal Fusion Transformer assembly."""
import os

import torch

from backend.config import ModelConfig, get_model_config
from backend.ml.model.tft import TemporalFusionTransformer

N_PAST = 53
N_FUTURE = 10
N_STATIC = 8


def _make_model(cfg: ModelConfig) -> TemporalFusionTransformer:
    return TemporalFusionTransformer(cfg, N_PAST, N_FUTURE, N_STATIC)


def test_forward_pass_shapes():
    """Validate all output dict shapes match the API contract."""
    torch.manual_seed(42)
    cfg = get_model_config()  # CPU profile by default
    model = _make_model(cfg)
    model.eval()

    B = 4
    past = torch.randn(B, cfg.past_window, N_PAST)
    future = torch.randn(B, cfg.forecast_horizon, N_FUTURE)
    static = torch.randn(B, N_STATIC)

    with torch.no_grad():
        out = model(past, future, static)

    assert set(out.keys()) == {
        "forecast", "nilm", "anomaly_recon",
        "anomaly_mu", "anomaly_logvar", "day_type", "attention_weights",
    }
    assert out["forecast"].shape == (B, cfg.forecast_horizon, cfg.n_channels, cfg.n_quantiles)
    assert out["nilm"].shape == (B, cfg.n_channels)
    assert out["anomaly_recon"].shape == (B, cfg.past_window, cfg.n_channels)
    assert out["anomaly_mu"].shape == (B, cfg.latent_dim)
    assert out["anomaly_logvar"].shape == (B, cfg.latent_dim)
    assert out["day_type"].shape == (B, cfg.n_day_types)
    assert out["attention_weights"].shape == (B, cfg.forecast_horizon, cfg.past_window)

    # Forecast must be non-negative (Softplus output)
    assert (out["forecast"] >= 0).all()


def test_parameter_count():
    """CPU profile should have between 50K and 2M parameters."""
    cfg = get_model_config()
    model = _make_model(cfg)
    n_params = sum(p.numel() for p in model.parameters())
    assert 50_000 < n_params < 2_000_000, f"CPU params={n_params:,} out of range"


def test_gpu_profile_builds():
    """GPU profile should have >500K parameters and produce correct shapes."""
    cfg = ModelConfig(
        d_model=192,
        n_heads=12,
        n_encoder_layers=4,
        n_decoder_layers=4,
        d_ff=384,
        dropout=0.1,
        past_window=96,
        forecast_horizon=24,
        n_channels=4,
        n_quantiles=3,
        n_day_types=4,
        n_appliance_types=8,
        latent_dim=32,
    )
    model = _make_model(cfg)
    n_params = sum(p.numel() for p in model.parameters())
    assert n_params > 500_000, f"GPU params={n_params:,} should be >500K"

    # Quick forward pass sanity check
    B = 2
    model.eval()
    with torch.no_grad():
        out = model(
            torch.randn(B, cfg.past_window, N_PAST),
            torch.randn(B, cfg.forecast_horizon, N_FUTURE),
            torch.randn(B, N_STATIC),
        )
    assert out["forecast"].shape == (B, 24, 4, 3)
