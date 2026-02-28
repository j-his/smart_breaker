"""
Multi-task loss functions for the TFT model.

Three losses:
  - QuantileLoss      — pinball loss with optional peak-hour weighting
  - VAELoss           — reconstruction MSE + KL divergence for anomaly head
  - UncertaintyWeightedLoss — Kendall et al. 2018 homoscedastic multi-task weighting
"""
import torch
import torch.nn as nn


class QuantileLoss(nn.Module):
    """Quantile (pinball) loss with optional peak-hour weighting.

    For quantile q, the loss on a single sample is:
        if target >= prediction:  q * (target - prediction)
        else:                     (1-q) * (prediction - target)

    Peak-hour weighting doubles the loss weight during peak hours,
    teaching the model to be more accurate when TOU prices are highest.

    Args:
        quantiles: list of quantile levels (default: [0.1, 0.5, 0.9])
        peak_weight: multiplier for peak-hour samples (default: 2.0)
    """

    def __init__(self, quantiles: list[float] | None = None, peak_weight: float = 2.0):
        super().__init__()
        if quantiles is None:
            quantiles = [0.1, 0.5, 0.9]
        self.register_buffer("quantiles", torch.tensor(quantiles, dtype=torch.float32))
        self.peak_weight = peak_weight

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        is_peak: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Args:
            predictions: (B, horizon, channels, n_quantiles)
            targets:     (B, horizon, channels)
            is_peak:     (B, horizon) binary mask, optional
        Returns:
            scalar loss
        """
        # Expand targets to match quantile dim: (B, H, C) -> (B, H, C, Q)
        targets_exp = targets.unsqueeze(-1)

        errors = targets_exp - predictions  # (B, H, C, Q)
        # Pinball: q * max(error, 0) + (1-q) * max(-error, 0)
        q = self.quantiles  # (Q,)
        loss = torch.max(errors * q, torch.zeros_like(errors)) + \
               torch.max(-errors * (1 - q), torch.zeros_like(errors))

        # loss shape: (B, H, C, Q) — reduce over channels and quantiles
        loss = loss.mean(dim=(-1, -2))  # (B, H)

        # Apply peak-hour weighting
        if is_peak is not None:
            weight = torch.where(is_peak > 0.5, self.peak_weight, 1.0)
            loss = loss * weight

        return loss.mean()


class VAELoss(nn.Module):
    """VAE loss: reconstruction MSE + KL divergence.

    The KL term regularizes the latent space toward N(0, I).
    kl_weight controls the balance (beta-VAE style).

    Args:
        kl_weight: weight for KL divergence term (default: 0.1)
    """

    def __init__(self, kl_weight: float = 0.1):
        super().__init__()
        self.kl_weight = kl_weight

    def forward(
        self,
        recon: torch.Tensor,
        target: torch.Tensor,
        mu: torch.Tensor,
        logvar: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            recon:  (B, past_window, channels) — reconstructed signal
            target: (B, past_window, channels) — original signal
            mu:     (B, latent_dim)
            logvar: (B, latent_dim)
        Returns:
            scalar loss
        """
        recon_loss = nn.functional.mse_loss(recon, target)
        # KL divergence: -0.5 * mean(1 + logvar - mu^2 - exp(logvar))
        kl_loss = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        return recon_loss + self.kl_weight * kl_loss


class UncertaintyWeightedLoss(nn.Module):
    """Homoscedastic uncertainty weighting for multi-task learning.

    Learns a log-variance (log_var) per task. The effective weight for
    each task is precision = exp(-log_var), with a regularization term
    log_var to prevent all precisions from going to zero.

    Reference: Kendall, Gal & Cipolla (2018) — "Multi-Task Learning
    Using Uncertainty to Weigh Losses for Scene Geometry and Semantics"

    Args:
        n_tasks: number of tasks/heads (default: 4)
    """

    def __init__(self, n_tasks: int = 4):
        super().__init__()
        # Initialize log_vars to 0 → initial precision = 1.0 for all tasks
        self.log_vars = nn.Parameter(torch.zeros(n_tasks))

    def forward(
        self, losses: list[torch.Tensor]
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """
        Args:
            losses: list of N scalar loss tensors (one per task)
        Returns:
            (total_loss, info_dict)
            info_dict has keys: head_{i}_weight, head_{i}_raw_loss
        """
        total = torch.tensor(0.0, device=self.log_vars.device)
        info = {}

        for i, loss in enumerate(losses):
            precision = torch.exp(-self.log_vars[i])
            total = total + precision * loss + self.log_vars[i]
            info[f"head_{i}_weight"] = precision.item()
            info[f"head_{i}_raw_loss"] = loss.item()

        return total, info


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    torch.manual_seed(42)
    B, H, C, Q = 4, 24, 4, 3

    # QuantileLoss
    ql = QuantileLoss()
    preds = torch.randn(B, H, C, Q).abs()
    targets = torch.randn(B, H, C).abs()
    is_peak = (torch.rand(B, H) > 0.5).float()
    loss_q = ql(preds, targets)
    loss_q_peak = ql(preds, targets, is_peak=is_peak)
    assert loss_q.shape == ()
    assert loss_q.item() > 0
    assert loss_q_peak.shape == ()
    print(f"QuantileLoss:          {loss_q.item():.4f} (no peak), {loss_q_peak.item():.4f} (with peak)")

    # VAELoss
    vl = VAELoss()
    recon = torch.randn(B, 96, C)
    target = torch.randn(B, 96, C)
    mu = torch.randn(B, 16)
    logvar = torch.randn(B, 16)
    loss_v = vl(recon, target, mu, logvar)
    assert loss_v.shape == ()
    assert loss_v.item() > 0
    print(f"VAELoss:               {loss_v.item():.4f}")

    # UncertaintyWeightedLoss
    uwl = UncertaintyWeightedLoss(n_tasks=4)
    fake_losses = [torch.tensor(float(i + 1)) for i in range(4)]
    total, info = uwl(fake_losses)
    assert total.shape == ()
    assert "head_0_weight" in info
    assert "head_3_raw_loss" in info
    assert len(info) == 8  # 4 weights + 4 raw losses
    print(f"UncertaintyWeighted:   total={total.item():.4f}")
    for k, v in info.items():
        print(f"  {k}: {v:.4f}")

    print("\nAll loss function checks passed.")
