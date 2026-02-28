"""
Temporal encoder for the Temporal Fusion Transformer.

Architecture per layer:
    Self-Attention → LayerNorm → GRN → GLU gate → LayerNorm

The encoder processes the past window, producing contextual
representations that the decoder cross-attends to.
"""
import torch
import torch.nn as nn

from backend.ml.model.attention import MultiHeadAttention
from backend.ml.model.components import GatedLinearUnit, GatedResidualNetwork


class TemporalEncoderLayer(nn.Module):
    """Single encoder layer: self-attention → GRN with gated residual.

    forward(x, mask=None) → tensor same shape as x
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, n_heads, dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.grn = GatedResidualNetwork(d_model, d_model, d_hidden=d_ff, dropout=dropout)
        self.gate = GatedLinearUnit(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self, x: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        # Self-attention with residual
        attn_out, _ = self.self_attn(x, x, x, mask)
        x = self.norm1(x + self.dropout(attn_out))

        # GRN → Gate with residual
        grn_out = self.grn(x)
        gated = self.gate(grn_out)
        x = self.norm2(x + self.dropout(gated))

        return x


class TemporalEncoder(nn.Module):
    """Stack of N TemporalEncoderLayers.

    forward(x, mask=None) → encoder output of same shape as input
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        n_layers: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.layers = nn.ModuleList(
            [TemporalEncoderLayer(d_model, n_heads, d_ff, dropout) for _ in range(n_layers)]
        )

    def forward(
        self, x: torch.Tensor, mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        for layer in self.layers:
            x = layer(x, mask)
        return x


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    torch.manual_seed(42)
    B, seq, d_model, n_heads, d_ff, n_layers = 4, 96, 64, 8, 128, 2

    x = torch.randn(B, seq, d_model)
    enc = TemporalEncoder(d_model, n_heads, d_ff, n_layers)
    out = enc(x)
    print(f"Encoder: {tuple(out.shape)}")
    assert out.shape == (B, seq, d_model)
    print("Encoder check passed.")
