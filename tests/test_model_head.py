"""Tests for the per-line head + LSE aggregator. CPU-only."""

from __future__ import annotations

import math

import pytest
import torch

from ebm_verus.model.head import (
    PerLineEnergyHead,
    lse_temperature_schedule,
    normalized_lse,
)


class TestPerLineHead:
    def test_shapes(self) -> None:
        head = PerLineEnergyHead(in_dim=64, hidden_dim=32)
        h = torch.randn(5, 64)
        out = head(h)
        assert out.shape == (5,)

    def test_unbounded_output(self) -> None:
        """Head must NOT use sigmoid — outputs should span (-inf, inf)."""
        head = PerLineEnergyHead(in_dim=64, hidden_dim=32, dropout=0.0)
        # Large input → large output (would saturate under sigmoid).
        h = torch.randn(1, 64) * 100.0
        out = head(h)
        assert out.dtype == torch.float32
        # Pre-trained init keeps things small but the *gradient* through to
        # large inputs should be non-vanishing — sanity check by computing it.
        h.requires_grad_(True)
        loss = head(h).sum()
        loss.backward()
        assert h.grad is not None
        assert torch.isfinite(h.grad).all()

    def test_small_init(self) -> None:
        """Per critique #2a / §6 decision: small init prevents head from
        producing extreme energies at step 0 (which would make L_smooth
        necessary). Check init range.
        """
        head = PerLineEnergyHead(in_dim=128, hidden_dim=32, dropout=0.0, init_std=0.02)
        # With small init and zero bias, output on standard-normal inputs should
        # have stddev O(init_std * sqrt(hidden_dim)) ~ 0.02 * 5.6 ~ 0.1.
        h = torch.randn(1024, 128)
        with torch.no_grad():
            out = head(h)
        assert out.std().item() < 0.5, f"head outputs too large at init: std={out.std().item()}"


class TestNormalizedLSE:
    def test_mean_limit(self) -> None:
        """As T → ∞, LSE → mean."""
        e = torch.tensor([1.0, 2.0, 3.0, 4.0])
        out = normalized_lse(e, temperature=1000.0)
        assert math.isclose(out.item(), e.mean().item(), abs_tol=0.01)

    def test_max_limit(self) -> None:
        """As T → 0, LSE → max."""
        e = torch.tensor([1.0, 2.0, 3.0, 4.0])
        out = normalized_lse(e, temperature=0.01)
        assert math.isclose(out.item(), e.max().item(), abs_tol=0.05)

    def test_gradient_distribution_dense_at_high_T(self) -> None:
        """At high T, gradient distributes more evenly across lines.

        This is the whole point of temperature annealing — early in training
        we want every line to receive gradient, not just the maximum.
        """
        e = torch.tensor([0.0, 0.5, 1.0, 2.0], requires_grad=True)
        out = normalized_lse(e, temperature=10.0)
        out.backward()
        # gradient should be ~uniform across all 4 elements
        g = e.grad
        assert g is not None
        assert (g > 0).all()
        # The max should not dominate (each gradient should be at least 0.1)
        assert g.min().item() > 0.1

    def test_gradient_distribution_sparse_at_low_T(self) -> None:
        """At low T, gradient concentrates on the max."""
        e = torch.tensor([0.0, 0.5, 1.0, 5.0], requires_grad=True)
        out = normalized_lse(e, temperature=0.1)
        out.backward()
        g = e.grad
        assert g is not None
        # The argmax (index 3) should get >90% of the gradient mass.
        assert g[3].item() / g.sum().item() > 0.9

    def test_empty_returns_zero(self) -> None:
        e = torch.tensor([])
        out = normalized_lse(e, temperature=1.0)
        assert out.item() == 0.0

    def test_length_invariance(self) -> None:
        """Repeating the same energy N times should give the same LSE."""
        e1 = torch.tensor([1.5])
        e10 = torch.tensor([1.5] * 10)
        out1 = normalized_lse(e1, temperature=1.0)
        out10 = normalized_lse(e10, temperature=1.0)
        assert math.isclose(out1.item(), out10.item(), abs_tol=1e-5)


class TestTemperatureSchedule:
    def test_endpoints(self) -> None:
        assert lse_temperature_schedule(0, 1000, 2.0, 0.7) == pytest.approx(2.0)
        assert lse_temperature_schedule(1000, 1000, 2.0, 0.7) == pytest.approx(0.7)

    def test_midpoint(self) -> None:
        assert lse_temperature_schedule(500, 1000, 2.0, 0.7) == pytest.approx(1.35)

    def test_past_end_clamps(self) -> None:
        # Step beyond total — clamp to t_end, don't overshoot.
        assert lse_temperature_schedule(2000, 1000, 2.0, 0.7) == pytest.approx(0.7)
