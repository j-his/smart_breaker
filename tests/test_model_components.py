"""
Tests for TFT model components: GLU, GRN, VSN.

Tests written before implementation (TDD). Each test verifies shape
contracts and mathematical properties of the building blocks.
"""
import torch
import pytest


def test_glu_output_shape():
    """GLU preserves shape: (B, T, d_model) → (B, T, d_model)."""
    from backend.ml.model.components import GatedLinearUnit

    glu = GatedLinearUnit(d_model=64)
    x = torch.randn(8, 96, 64)
    out = glu(x)
    assert out.shape == (8, 96, 64)


def test_grn_output_shape_same_dim():
    """GRN with d_input == d_model uses identity skip connection."""
    from backend.ml.model.components import GatedResidualNetwork

    grn = GatedResidualNetwork(d_input=64, d_model=64)
    x = torch.randn(8, 96, 64)
    out = grn(x)
    assert out.shape == (8, 96, 64)


def test_grn_output_shape_different_dim():
    """GRN with d_input != d_model exercises the skip_proj path."""
    from backend.ml.model.components import GatedResidualNetwork

    grn = GatedResidualNetwork(d_input=32, d_model=64)
    x = torch.randn(8, 96, 32)
    out = grn(x)
    assert out.shape == (8, 96, 64)


def test_grn_with_context():
    """GRN accepts an optional context tensor that biases the hidden state."""
    from backend.ml.model.components import GatedResidualNetwork

    grn = GatedResidualNetwork(d_input=64, d_model=64, d_context=32)
    x = torch.randn(8, 96, 64)
    context = torch.randn(8, 96, 32)
    out = grn(x, context=context)
    assert out.shape == (8, 96, 64)


def test_vsn_output_shape():
    """VSN returns (output, weights) with correct shapes."""
    from backend.ml.model.components import VariableSelectionNetwork

    vsn = VariableSelectionNetwork(d_input=16, d_model=64, n_vars=5)
    x = torch.randn(8, 96, 80)  # 5 vars * 16 features each
    out, weights = vsn(x)
    assert out.shape == (8, 96, 64)
    assert weights.shape == (8, 96, 5)


def test_vsn_weights_sum_to_one():
    """VSN selection weights sum to 1.0 along the variable dimension (softmax)."""
    from backend.ml.model.components import VariableSelectionNetwork

    vsn = VariableSelectionNetwork(d_input=16, d_model=64, n_vars=5)
    x = torch.randn(8, 96, 80)
    _, weights = vsn(x)
    sums = weights.sum(dim=-1)
    assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)
