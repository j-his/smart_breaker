"""
Multi-head attention variants for the Temporal Fusion Transformer.

Two classes:
  - MultiHeadAttention — standard scaled dot-product multi-head attention
  - InterpretableAttention — shared-value attention with averaged weights
    for temporal interpretability (TFT paper Section 4)
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiHeadAttention(nn.Module):
    """Standard scaled dot-product multi-head attention.

    Each head has independent Q, K, V projections. Output heads are
    concatenated and projected back to d_model.

    forward(query, key, value, mask=None):
        Returns (context, attn_weights)
        context: (B, seq_q, d_model)
        attn_weights: (B, n_heads, seq_q, seq_k)
    """

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads

        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_k)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        B, seq_q, _ = query.shape
        seq_k = key.shape[1]

        # Project and reshape: (B, seq, d_model) → (B, n_heads, seq, d_k)
        Q = self.w_q(query).view(B, seq_q, self.n_heads, self.d_k).transpose(1, 2)
        K = self.w_k(key).view(B, seq_k, self.n_heads, self.d_k).transpose(1, 2)
        V = self.w_v(value).view(B, seq_k, self.n_heads, self.d_k).transpose(1, 2)

        # Scaled dot-product: (B, n_heads, seq_q, seq_k)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        if mask is not None:
            scores = scores.masked_fill(mask == 0, float("-inf"))

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Weighted sum: (B, n_heads, seq_q, d_k)
        context = torch.matmul(attn_weights, V)

        # Concatenate heads: (B, seq_q, d_model)
        context = context.transpose(1, 2).contiguous().view(B, seq_q, self.d_model)
        context = self.w_o(context)

        return context, attn_weights


class InterpretableAttention(nn.Module):
    """Additive attention with shared value projection across heads.

    Key difference from standard MHA: all heads share a single V projection.
    After computing per-head attention weights, they are averaged to produce
    a single (B, seq_q, seq_k) weight matrix — directly interpretable as
    "which past timesteps influenced each future prediction."

    forward(query, key, value, mask=None):
        Returns (output, avg_attn)
        output: (B, seq_q, d_model)
        avg_attn: (B, seq_q, seq_k)  — averaged across heads
    """

    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads

        # Per-head Q and K projections
        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)

        # Shared value projection — single head dimension, then broadcast
        self.w_v = nn.Linear(d_model, self.d_k)

        self.w_o = nn.Linear(self.d_k, d_model)
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_k)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        B, seq_q, _ = query.shape
        seq_k = key.shape[1]

        # Per-head Q, K: (B, n_heads, seq, d_k)
        Q = self.w_q(query).view(B, seq_q, self.n_heads, self.d_k).transpose(1, 2)
        K = self.w_k(key).view(B, seq_k, self.n_heads, self.d_k).transpose(1, 2)

        # Shared V: (B, seq_k, d_k) — same for all heads
        V = self.w_v(value)  # (B, seq_k, d_k)

        # Scaled dot-product per head: (B, n_heads, seq_q, seq_k)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        if mask is not None:
            scores = scores.masked_fill(mask == 0, float("-inf"))

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Average across heads → (B, seq_q, seq_k)
        avg_attn = attn_weights.mean(dim=1)

        # Apply averaged attention to shared V: (B, seq_q, d_k)
        context = torch.matmul(avg_attn, V)

        # Project back to d_model
        output = self.w_o(context)

        return output, avg_attn


# ── Inline verification ──────────────────────────────────────────
if __name__ == "__main__":
    torch.manual_seed(42)
    B, seq, d_model, n_heads = 4, 96, 64, 8

    q = k = v = torch.randn(B, seq, d_model)

    mha = MultiHeadAttention(d_model, n_heads)
    ctx, weights = mha(q, k, v)
    print(f"MHA: out={tuple(ctx.shape)}, weights={tuple(weights.shape)}")
    assert ctx.shape == (B, seq, d_model)
    assert weights.shape == (B, n_heads, seq, seq)

    ia = InterpretableAttention(d_model, n_heads)
    out, avg = ia(q, k, v)
    print(f"InterpretableAttention: out={tuple(out.shape)}, weights={tuple(avg.shape)}")
    assert out.shape == (B, seq, d_model)
    assert avg.shape == (B, seq, seq)

    print("All attention checks passed.")
