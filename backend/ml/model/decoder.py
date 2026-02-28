"""
Temporal decoder for the Temporal Fusion Transformer.

Architecture per layer:
    Masked Self-Attention → Cross-Attention → GRN → GLU gate → LayerNorm

The last layer uses InterpretableAttention for cross-attention,
producing averaged attention weights for temporal visualization.
"""
import torch
import torch.nn as nn

from backend.ml.model.attention import InterpretableAttention, MultiHeadAttention
from backend.ml.model.components import GatedLinearUnit, GatedResidualNetwork


class TemporalDecoderLayer(nn.Module):
    """Single decoder layer with optional interpretable cross-attention.

    When interpretable=True, cross-attention uses InterpretableAttention
    (shared value projection, averaged weights) instead of standard MHA.

    forward(x, encoder_out, self_mask=None) → (output, cross_weights)
        cross_weights: (B, n_heads, seq_q, seq_k) or (B, seq_q, seq_k)
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        d_ff: int,
        dropout: float = 0.1,
        interpretable: bool = False,
    ):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, n_heads, dropout)
        self.norm1 = nn.LayerNorm(d_model)

        # Cross-attention: interpretable for last layer, standard otherwise
        if interpretable:
            self.cross_attn = InterpretableAttention(d_model, n_heads, dropout)
        else:
            self.cross_attn = MultiHeadAttention(d_model, n_heads, dropout)

        self.norm2 = nn.LayerNorm(d_model)
        self.grn = GatedResidualNetwork(d_model, d_model, d_hidden=d_ff, dropout=dropout)
        self.gate = GatedLinearUnit(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        encoder_out: torch.Tensor,
        self_mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # Masked self-attention (causal)
        self_out, _ = self.self_attn(x, x, x, self_mask)
        x = self.norm1(x + self.dropout(self_out))

        # Cross-attention to encoder
        cross_out, cross_weights = self.cross_attn(x, encoder_out, encoder_out)
        x = self.norm2(x + self.dropout(cross_out))

        # GRN → Gate with residual
        grn_out = self.grn(x)
        gated = self.gate(grn_out)
        x = self.norm3(x + self.dropout(gated))

        return x, cross_weights


class TemporalDecoder(nn.Module):
    """Stack of N TemporalDecoderLayers.

    The last layer uses interpretable=True so its cross-attention weights
    can be used for temporal visualization (Responsible AI prize track).

    forward(x, encoder_out, self_mask=None) → (output, attn_weights)
        attn_weights: (B, seq_q, seq_k) — from last layer's interpretable attention
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
            [
                TemporalDecoderLayer(
                    d_model,
                    n_heads,
                    d_ff,
                    dropout,
                    interpretable=(i == n_layers - 1),  # last layer only
                )
                for i in range(n_layers)
            ]
        )

    def forward(
        self,
        x: torch.Tensor,
        encoder_out: torch.Tensor,
        self_mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        attn_weights = None
        for layer in self.layers:
            x, attn_weights = layer(x, encoder_out, self_mask)
        # attn_weights from last layer is (B, seq_q, seq_k) — interpretable
        return x, attn_weights


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    torch.manual_seed(42)
    B, past_seq, future_seq, d_model = 4, 96, 24, 64
    n_heads, d_ff, n_layers = 8, 128, 2

    encoder_out = torch.randn(B, past_seq, d_model)
    decoder_in = torch.randn(B, future_seq, d_model)

    dec = TemporalDecoder(d_model, n_heads, d_ff, n_layers)
    out, attn = dec(decoder_in, encoder_out)
    print(f"Decoder: {tuple(out.shape)}, Attn: {tuple(attn.shape)}")
    assert out.shape == (B, future_seq, d_model)
    assert attn.shape == (B, future_seq, past_seq)
    print("Decoder check passed.")
