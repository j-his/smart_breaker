"""
Full Temporal Fusion Transformer assembly.

Wires together all components from Tasks 6-9:
  - components.py → GatedResidualNetwork
  - attention.py  → (via encoder/decoder)
  - encoder.py    → TemporalEncoder
  - decoder.py    → TemporalDecoder
  - heads.py      → 4 prediction heads

Two classes:
  - PositionalEncoding — hybrid sinusoidal + learnable time-of-day
  - TemporalFusionTransformer — the complete model
"""
import math

import torch
import torch.nn as nn

from backend.ml.model.components import GatedResidualNetwork
from backend.ml.model.decoder import TemporalDecoder
from backend.ml.model.encoder import TemporalEncoder
from backend.ml.model.heads import (
    AnomalyVAEHead,
    DayTypeHead,
    NILMHead,
    QuantileForecastHead,
)


class PositionalEncoding(nn.Module):
    """Hybrid positional encoding: sinusoidal base + learnable time-of-day.

    Standard sinusoidal encoding provides absolute position information.
    A learnable embedding on top allows the model to adapt positional
    representations during training (e.g., learning that position 0-95
    maps to specific times of day at 15-min resolution).

    Input:  (B, seq, d_model)
    Output: (B, seq, d_model)
    """

    def __init__(self, d_model: int, max_len: int = 200):
        super().__init__()

        # Fixed sinusoidal base
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float)
            * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

        # Learnable additive component
        self.learned = nn.Parameter(torch.zeros(1, max_len, d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.shape[1]
        return x + self.pe[:, :seq_len, :] + self.learned[:, :seq_len, :]


class TemporalFusionTransformer(nn.Module):
    """Complete TFT model with encoder-decoder and 4 prediction heads.

    Pipeline:
        1. Project past/future/static features to d_model
        2. Static context GRNs produce selection and enrichment contexts
        3. Variable GRNs (with static context) select relevant features
        4. Positional encoding + Temporal Encoder on past
        5. Positional encoding + Temporal Decoder on future (cross-attends to encoder)
        6. Enrichment GRN combines decoder output with static context
        7. Four heads produce task-specific outputs

    Forward returns a dict with 7 keys:
        forecast, nilm, anomaly_recon, anomaly_mu, anomaly_logvar,
        day_type, attention_weights
    """

    def __init__(
        self,
        cfg,
        n_past_features: int,
        n_future_features: int,
        n_static_features: int,
    ):
        super().__init__()
        d = cfg.d_model

        # ── Input projections ────────────────────────────────────
        self.past_proj = nn.Linear(n_past_features, d)
        self.future_proj = nn.Linear(n_future_features, d)
        self.static_proj = nn.Linear(n_static_features, d)

        # ── Static context GRNs ──────────────────────────────────
        # c_s: context for variable selection
        # c_e: context for temporal enrichment
        self.static_grn_c_s = GatedResidualNetwork(d, d, dropout=cfg.dropout)
        self.static_grn_c_e = GatedResidualNetwork(d, d, dropout=cfg.dropout)

        # ── Variable selection GRNs (with static context) ────────
        self.past_grn = GatedResidualNetwork(
            d, d, d_context=d, dropout=cfg.dropout
        )
        self.future_grn = GatedResidualNetwork(
            d, d, d_context=d, dropout=cfg.dropout
        )

        # ── Temporal processing ──────────────────────────────────
        self.pos_encoder = PositionalEncoding(d)
        self.encoder = TemporalEncoder(
            d, cfg.n_heads, cfg.d_ff, cfg.n_encoder_layers, cfg.dropout
        )
        self.decoder = TemporalDecoder(
            d, cfg.n_heads, cfg.d_ff, cfg.n_decoder_layers, cfg.dropout
        )

        # ── Enrichment ───────────────────────────────────────────
        self.enrichment_grn = GatedResidualNetwork(
            d, d, d_context=d, dropout=cfg.dropout
        )

        # ── Prediction heads ─────────────────────────────────────
        self.forecast_head = QuantileForecastHead(
            d, cfg.n_channels, cfg.forecast_horizon, cfg.n_quantiles
        )
        self.nilm_head = NILMHead(d, cfg.n_channels)
        self.anomaly_head = AnomalyVAEHead(
            d, cfg.latent_dim, cfg.past_window, cfg.n_channels
        )
        self.day_type_head = DayTypeHead(d, cfg.n_day_types, cfg.dropout)

    def forward(
        self,
        past: torch.Tensor,
        future: torch.Tensor,
        static: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            past:   (B, past_window, n_past_features)
            future: (B, forecast_horizon, n_future_features)
            static: (B, n_static_features)
        Returns:
            dict with keys: forecast, nilm, anomaly_recon, anomaly_mu,
                            anomaly_logvar, day_type, attention_weights
        """
        # ── 1. Input projections ──────────────────────────────────
        past_emb = self.past_proj(past)       # (B, past_window, d)
        future_emb = self.future_proj(future) # (B, horizon, d)
        static_emb = self.static_proj(static) # (B, d)

        # ── 2. Static context vectors ─────────────────────────────
        # Expand static to (B, 1, d) for broadcasting with temporal dims
        static_2d = static_emb.unsqueeze(1)
        c_s = self.static_grn_c_s(static_2d).squeeze(1)  # (B, d) — selection
        c_e = self.static_grn_c_e(static_2d).squeeze(1)  # (B, d) — enrichment

        # ── 3. Variable selection (with static context) ───────────
        # Expand context to match temporal length
        c_s_past = c_s.unsqueeze(1).expand_as(past_emb)     # (B, past_window, d)
        c_s_future = c_s.unsqueeze(1).expand_as(future_emb) # (B, horizon, d)

        past_selected = self.past_grn(past_emb, context=c_s_past)
        future_selected = self.future_grn(future_emb, context=c_s_future)

        # ── 4. Positional encoding + Encoder ──────────────────────
        past_pos = self.pos_encoder(past_selected)
        encoder_out = self.encoder(past_pos)  # (B, past_window, d)

        # ── 5. Positional encoding + Decoder ──────────────────────
        future_pos = self.pos_encoder(future_selected)
        decoder_out, attn_weights = self.decoder(
            future_pos, encoder_out
        )  # (B, horizon, d), (B, horizon, past_window)

        # ── 6. Enrichment with static context ─────────────────────
        c_e_dec = c_e.unsqueeze(1).expand_as(decoder_out)  # (B, horizon, d)
        enriched = self.enrichment_grn(decoder_out, context=c_e_dec)

        # ── 7. Prediction heads ───────────────────────────────────
        forecast = self.forecast_head(enriched)              # (B, H, C, Q)
        nilm = self.nilm_head(encoder_out[:, -1, :])         # (B, C)
        recon, mu, logvar = self.anomaly_head(encoder_out)    # (B, P, C), (B, L), (B, L)
        day_type = self.day_type_head(encoder_out)            # (B, n_day_types)

        return {
            "forecast": forecast,
            "nilm": nilm,
            "anomaly_recon": recon,
            "anomaly_mu": mu,
            "anomaly_logvar": logvar,
            "day_type": day_type,
            "attention_weights": attn_weights,
        }


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    from backend.config import get_model_config

    torch.manual_seed(42)
    cfg = get_model_config()  # CPU profile
    n_past, n_future, n_static = 53, 10, 8
    B = 4

    model = TemporalFusionTransformer(cfg, n_past, n_future, n_static)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n_params:,}")

    past = torch.randn(B, cfg.past_window, n_past)
    future = torch.randn(B, cfg.forecast_horizon, n_future)
    static = torch.randn(B, n_static)

    out = model(past, future, static)
    for k, v in out.items():
        print(f"  {k}: {tuple(v.shape)}")

    assert out["forecast"].shape == (B, 24, 4, 3)
    assert out["nilm"].shape == (B, 4)
    assert out["anomaly_recon"].shape == (B, 96, 4)
    assert out["anomaly_mu"].shape == (B, 16)
    assert out["anomaly_logvar"].shape == (B, 16)
    assert out["day_type"].shape == (B, 4)
    assert out["attention_weights"].shape == (B, 24, 96)
    assert (out["forecast"] >= 0).all(), "Forecast must be non-negative"
    print("All TFT assembly checks passed.")
