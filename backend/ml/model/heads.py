"""
Prediction heads for the Temporal Fusion Transformer.

Four nn.Module classes, each consuming encoder/decoder output and
producing a task-specific prediction:
  - QuantileForecastHead — (B, horizon, n_channels, n_quantiles)
  - NILMHead             — (B, n_channels) appliance-on logits
  - AnomalyVAEHead       — VAE reconstruction + (mu, logvar)
  - DayTypeHead           — (B, n_day_types) classification logits
"""
import torch
import torch.nn as nn


class QuantileForecastHead(nn.Module):
    """Quantile regression head for energy load forecasting.

    Takes decoder output and produces non-negative quantile predictions
    (p10, p50, p90) per channel per horizon step. Softplus ensures
    non-negative watt predictions.

    Input:  (B, horizon, d_model)
    Output: (B, horizon, n_channels, n_quantiles)
    """

    def __init__(
        self,
        d_model: int,
        n_channels: int,
        horizon: int,
        n_quantiles: int = 3,
    ):
        super().__init__()
        self.n_channels = n_channels
        self.n_quantiles = n_quantiles
        self.horizon = horizon

        out_dim = n_channels * n_quantiles
        self.net = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Linear(d_model, out_dim),
            nn.Softplus(),  # non-negative power predictions
        )

    def forward(self, decoder_out: torch.Tensor) -> torch.Tensor:
        # decoder_out: (B, horizon, d_model)
        B = decoder_out.shape[0]
        raw = self.net(decoder_out)  # (B, horizon, n_channels * n_quantiles)
        return raw.view(B, self.horizon, self.n_channels, self.n_quantiles)


class NILMHead(nn.Module):
    """Non-Intrusive Load Monitoring head.

    Uses the last timestep of encoder output to classify which
    appliances are currently active.

    Input:  (B, d_model) — encoder_out[:, -1, :]
    Output: (B, n_channels) logits
    """

    def __init__(self, d_model: int, n_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Linear(d_model, n_channels),
        )

    def forward(self, last_encoder: torch.Tensor) -> torch.Tensor:
        # last_encoder: (B, d_model)
        return self.net(last_encoder)


class AnomalyVAEHead(nn.Module):
    """Variational Autoencoder head for anomaly detection.

    Encodes the past window into a latent distribution (mu, logvar),
    samples via reparameterization trick (training only), and decodes
    back to reconstruct the original 4-channel power signal.

    Input:  (B, past_window, d_model)
    Output: (reconstruction, mu, logvar)
        reconstruction: (B, past_window, n_channels)
        mu:     (B, latent_dim)
        logvar: (B, latent_dim)
    """

    def __init__(
        self,
        d_model: int,
        latent_dim: int,
        past_window: int,
        n_channels: int,
    ):
        super().__init__()
        self.past_window = past_window
        self.n_channels = n_channels
        self.latent_dim = latent_dim

        # Encoder: pool over time → latent distribution
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc_mu = nn.Linear(d_model, latent_dim)
        self.fc_logvar = nn.Linear(d_model, latent_dim)

        # Decoder: latent → reconstruction
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, d_model),
            nn.ReLU(),
            nn.Linear(d_model, past_window * n_channels),
        )

    def forward(
        self, encoder_out: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        B = encoder_out.shape[0]

        # Pool: (B, past_window, d_model) → (B, d_model)
        pooled = self.pool(encoder_out.transpose(1, 2)).squeeze(-1)

        mu = self.fc_mu(pooled)          # (B, latent_dim)
        logvar = self.fc_logvar(pooled)  # (B, latent_dim)

        # Reparameterization trick (training only)
        if self.training:
            std = torch.exp(0.5 * logvar)
            eps = torch.randn_like(std)
            z = mu + eps * std
        else:
            z = mu

        # Decode: (B, latent_dim) → (B, past_window * n_channels)
        recon = self.decoder(z)
        recon = recon.view(B, self.past_window, self.n_channels)

        return recon, mu, logvar


class DayTypeHead(nn.Module):
    """Day-type classification head.

    Mean-pools encoder output over time and classifies into one of
    n_day_types categories (workday, weekend, wfh, away).

    Input:  (B, past_window, d_model)
    Output: (B, n_day_types) logits
    """

    def __init__(self, d_model: int, n_day_types: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, n_day_types),
        )

    def forward(self, encoder_out: torch.Tensor) -> torch.Tensor:
        # Mean pool over time: (B, past_window, d_model) → (B, d_model)
        pooled = encoder_out.mean(dim=1)
        return self.net(pooled)


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    torch.manual_seed(42)
    B, past_window, horizon, d_model = 4, 96, 24, 64
    n_channels, n_quantiles, latent_dim, n_day_types = 4, 3, 16, 4

    decoder_out = torch.randn(B, horizon, d_model)
    encoder_out = torch.randn(B, past_window, d_model)

    # Forecast
    fh = QuantileForecastHead(d_model, n_channels, horizon, n_quantiles)
    forecast = fh(decoder_out)
    print(f"Forecast: {tuple(forecast.shape)}")
    assert forecast.shape == (B, horizon, n_channels, n_quantiles)
    assert (forecast >= 0).all(), "Softplus should produce non-negative values"

    # NILM
    nh = NILMHead(d_model, n_channels)
    nilm = nh(encoder_out[:, -1, :])
    print(f"NILM: {tuple(nilm.shape)}")
    assert nilm.shape == (B, n_channels)

    # Anomaly VAE
    ah = AnomalyVAEHead(d_model, latent_dim, past_window, n_channels)
    ah.train()
    recon, mu, logvar = ah(encoder_out)
    print(f"Anomaly recon: {tuple(recon.shape)}, mu: {tuple(mu.shape)}")
    assert recon.shape == (B, past_window, n_channels)
    assert mu.shape == (B, latent_dim)
    assert logvar.shape == (B, latent_dim)

    # Day Type
    dh = DayTypeHead(d_model, n_day_types)
    day_type = dh(encoder_out)
    print(f"DayType: {tuple(day_type.shape)}")
    assert day_type.shape == (B, n_day_types)

    print("All head checks passed.")
