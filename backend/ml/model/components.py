"""
Core building blocks for the Temporal Fusion Transformer.

Three nn.Module classes:
  - GatedLinearUnit  (GLU)  — sigmoid gating on linear projections
  - GatedResidualNetwork (GRN) — nonlinear transform with skip connection + GLU
  - VariableSelectionNetwork (VSN) — learned per-variable weighting via softmax
"""
import torch
import torch.nn as nn


class GatedLinearUnit(nn.Module):
    """Element-wise sigmoid gating over two parallel linear projections.

    forward(x):  sigmoid(W_gate @ x + b_gate) * (W_val @ x + b_val)
    Shape: (batch, seq, d_model) → (batch, seq, d_model)
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.fc_val = nn.Linear(d_model, d_model)
        self.fc_gate = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.fc_gate(x)) * self.fc_val(x)


class GatedResidualNetwork(nn.Module):
    """Nonlinear processing with gated skip connection and optional context.

    Architecture:
        hidden = ELU(fc1(x) [+ context_proj(context)])
        hidden = GLU(dropout(fc2(hidden)))
        output = LayerNorm(skip(x) + hidden)

    When d_input != d_model, a linear skip projection maps the residual.
    When d_context is provided, context is projected and added to the hidden state.
    """

    def __init__(
        self,
        d_input: int,
        d_model: int,
        d_hidden: int | None = None,
        d_context: int | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        d_hidden = d_hidden or d_model

        self.fc1 = nn.Linear(d_input, d_hidden)
        self.fc2 = nn.Linear(d_hidden, d_model)
        self.elu = nn.ELU()
        self.dropout = nn.Dropout(dropout)
        self.glu = GatedLinearUnit(d_model)
        self.layer_norm = nn.LayerNorm(d_model)

        self.context_proj = (
            nn.Linear(d_context, d_hidden) if d_context is not None else None
        )
        self.skip_proj = (
            nn.Linear(d_input, d_model) if d_input != d_model else None
        )

    def forward(
        self, x: torch.Tensor, context: torch.Tensor | None = None
    ) -> torch.Tensor:
        residual = self.skip_proj(x) if self.skip_proj is not None else x

        hidden = self.fc1(x)
        if context is not None and self.context_proj is not None:
            hidden = hidden + self.context_proj(context)
        hidden = self.elu(hidden)
        hidden = self.dropout(self.fc2(hidden))
        hidden = self.glu(hidden)

        return self.layer_norm(residual + hidden)


class VariableSelectionNetwork(nn.Module):
    """Learned weighting over input variables via softmax selection.

    Splits the concatenated input into per-variable chunks, computes
    softmax attention weights with a selection GRN, then returns the
    weighted sum of individually-processed variable embeddings.

    Returns:
        (output, weights) where output is (B, T, d_model) and
        weights is (B, T, n_vars) summing to 1.0 along dim=-1.
    """

    def __init__(
        self,
        d_input: int,
        d_model: int,
        n_vars: int,
        d_context: int | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.n_vars = n_vars
        self.d_input = d_input

        self.var_grns = nn.ModuleList(
            [
                GatedResidualNetwork(d_input, d_model, d_context=d_context, dropout=dropout)
                for _ in range(n_vars)
            ]
        )
        self.selection_grn = GatedResidualNetwork(
            d_input=d_input * n_vars,
            d_model=n_vars,
            d_context=d_context,
            dropout=dropout,
        )
        self.softmax = nn.Softmax(dim=-1)

    def forward(
        self, x: torch.Tensor, context: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (batch, seq, n_vars * d_input)
        var_inputs = torch.chunk(x, self.n_vars, dim=-1)  # list of (B, T, d_input)

        # Selection weights from the full concatenated input
        weights = self.softmax(self.selection_grn(x, context))  # (B, T, n_vars)

        # Per-variable processing through individual GRNs
        processed = torch.stack(
            [grn(v, context) for grn, v in zip(self.var_grns, var_inputs)],
            dim=-2,
        )  # (B, T, n_vars, d_model)

        # Weighted sum across variables
        output = (processed * weights.unsqueeze(-1)).sum(dim=-2)  # (B, T, d_model)

        return output, weights
