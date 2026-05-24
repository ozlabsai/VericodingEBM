"""Tests for L_spec (InfoNCE) and L_line (pairwise hinge). CPU-only.

We mock the ``ScorerOutput`` directly with hand-crafted energies so we can
verify the loss math without loading the backbone.
"""

from __future__ import annotations

import torch

from ebm_verus.data.dataset import Batch
from ebm_verus.data.types import Source, Status
from ebm_verus.model.scorer import ScorerOutput
from ebm_verus.training.losses import (
    compute_loss,
    l_line_hinge,
    l_spec_infonce,
)


def _make_batch(
    *,
    statuses: list[Status],
    sources: list[Source],
    spec_ids: list[str],
    traj_triples: list[list[int]],
    safe_broken: list[int],
    buggy_lines_per_b: list[list[int]],
    n_lines_per_b: list[int],
) -> Batch:
    B = len(statuses)
    return Batch(
        input_ids=torch.zeros((B, 1), dtype=torch.long),
        attention_mask=torch.ones((B, 1), dtype=torch.long),
        sentinel_positions=[torch.arange(n) for n in n_lines_per_b],
        buggy_line_indices=[torch.tensor(bl, dtype=torch.long) for bl in buggy_lines_per_b],
        statuses=statuses,
        sources=sources,
        spec_ids=spec_ids,
        traj_triples=traj_triples,
        safe_broken_indices=safe_broken,
    )


class TestLSpec:
    def test_pos_lower_energy_gives_low_loss(self) -> None:
        """When passing impl has clearly lower energy than failing impls,
        loss should be near zero."""
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL, Status.FAIL],
            sources=[Source.SYSTEM_TRAJECTORY] * 3,
            spec_ids=["s1", "s1", "s1"],
            traj_triples=[[0, 1, 2]],
            safe_broken=[],
            buggy_lines_per_b=[[], [], []],
            n_lines_per_b=[1, 1, 1],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0]) for _ in range(3)],
            whole_impl_energies=torch.tensor([-5.0, 5.0, 5.0]),  # pos very low
        )
        loss, n, _ = l_spec_infonce(batch, out)
        assert n == 1
        assert loss.item() < 0.01

    def test_pos_higher_energy_gives_high_loss(self) -> None:
        """When passing impl has higher energy than failing, loss is large."""
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL, Status.FAIL],
            sources=[Source.SYSTEM_TRAJECTORY] * 3,
            spec_ids=["s1", "s1", "s1"],
            traj_triples=[[0, 1, 2]],
            safe_broken=[],
            buggy_lines_per_b=[[], [], []],
            n_lines_per_b=[1, 1, 1],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0]) for _ in range(3)],
            whole_impl_energies=torch.tensor([5.0, -5.0, -5.0]),  # pos high, neg low — WRONG
        )
        loss, _, _ = l_spec_infonce(batch, out)
        assert loss.item() > 5.0

    def test_cross_spec_negatives_used(self) -> None:
        """A failing impl from a DIFFERENT spec should still serve as an extra
        negative for the current spec's triple."""
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL, Status.FAIL],
            sources=[Source.SYSTEM_TRAJECTORY] * 3,
            spec_ids=["s1", "s1", "s2"],   # index 2 is a different spec
            traj_triples=[[0, 1]],          # only s1's pair
            safe_broken=[],
            buggy_lines_per_b=[[], [], []],
            n_lines_per_b=[1, 1, 1],
        )
        # If cross-spec pooling works, index 2 contributes a negative.
        # Make pos clearly distinguishable from both neg.
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0]) for _ in range(3)],
            whole_impl_energies=torch.tensor([-3.0, 3.0, 3.0]),
        )
        loss_with, _, _ = l_spec_infonce(batch, out, pool_cross_spec_negatives=True)
        loss_without, _, _ = l_spec_infonce(batch, out, pool_cross_spec_negatives=False)
        # More negatives → softmax is over more items, so loss is slightly LARGER
        # at the same gap. This confirms cross-spec pooling actually adds entries.
        assert loss_with.item() > loss_without.item()

    def test_empty_triples_returns_zero(self) -> None:
        batch = _make_batch(
            statuses=[Status.FAIL],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[],
            buggy_lines_per_b=[[]],
            n_lines_per_b=[1],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0])],
            whole_impl_energies=torch.tensor([0.0]),
        )
        loss, n, _ = l_spec_infonce(batch, out)
        assert n == 0
        assert loss.item() == 0.0


class TestLLine:
    def test_buggy_higher_gives_low_loss(self) -> None:
        """When buggy line has energy > non-buggy + margin, loss is zero."""
        batch = _make_batch(
            statuses=[Status.FAIL],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[0],
            buggy_lines_per_b=[[1]],     # line 1 is the bug
            n_lines_per_b=[3],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0, 10.0, 0.0])],
            whole_impl_energies=torch.tensor([0.0]),
        )
        rng = torch.Generator().manual_seed(0)
        loss, n, _ = l_line_hinge(batch, out, margin=1.0, pairs_per_impl=4, rng=rng)
        assert n > 0
        assert loss.item() == 0.0

    def test_buggy_lower_gives_positive_loss(self) -> None:
        batch = _make_batch(
            statuses=[Status.FAIL],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[0],
            buggy_lines_per_b=[[1]],
            n_lines_per_b=[3],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([5.0, 0.0, 5.0])],   # non-buggy higher — WRONG
            whole_impl_energies=torch.tensor([0.0]),
        )
        rng = torch.Generator().manual_seed(0)
        loss, _, _ = l_line_hinge(batch, out, margin=1.0, pairs_per_impl=4, rng=rng)
        # margin (1.0) + non_buggy (5.0) - buggy (0.0) = 6.0
        assert loss.item() > 5.0

    def test_no_non_buggy_lines_skipped(self) -> None:
        """If every line is marked buggy, no contrast → skip impl."""
        batch = _make_batch(
            statuses=[Status.FAIL],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[0],
            buggy_lines_per_b=[[0, 1, 2]],  # all lines buggy
            n_lines_per_b=[3],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0, 0.0, 0.0])],
            whole_impl_energies=torch.tensor([0.0]),
        )
        loss, n, _ = l_line_hinge(batch, out, margin=1.0, pairs_per_impl=4)
        assert n == 0
        assert loss.item() == 0.0


class TestComputeLoss:
    def test_both_terms_combined(self) -> None:
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL, Status.FAIL],
            sources=[Source.SYSTEM_TRAJECTORY, Source.SYSTEM_TRAJECTORY, Source.SFT_SAFE],
            spec_ids=["s1", "s1", "s2"],
            traj_triples=[[0, 1]],
            safe_broken=[2],
            buggy_lines_per_b=[[], [], [0]],
            n_lines_per_b=[2, 2, 2],
        )
        # Force gradient to flow: use energies that require_grad.
        per_line = [torch.tensor([0.0, 0.0], requires_grad=True) for _ in range(3)]
        whole = torch.tensor([-1.0, 1.0, 1.0], requires_grad=True)
        out = ScorerOutput(per_line_energies=per_line, whole_impl_energies=whole)

        rng = torch.Generator().manual_seed(0)
        result = compute_loss(
            batch, out,
            lambda_spec=1.0, lambda_line=1.0, line_margin=1.0,
            pairs_per_impl=4, rng=rng,
        )
        assert result.total.requires_grad
        assert result.n_spec_groups == 1
        assert result.n_line_pairs > 0
        # Gradient flow check.
        result.total.backward()
        assert whole.grad is not None
        assert per_line[2].grad is not None


class TestBCELoss:
    def test_buggy_line_gets_higher_loss_when_low_energy(self) -> None:
        from ebm_verus.training.losses import compute_bce_loss
        # One impl, 3 lines, line[1] is buggy. Energies say line[2] is highest
        # (wrong) -- BCE on line[1] should produce non-trivial loss.
        batch = _make_batch(
            statuses=[Status.FAIL],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[0],
            buggy_lines_per_b=[[1]],
            n_lines_per_b=[3],
        )
        per_line = [torch.tensor([0.0, -2.0, 5.0], requires_grad=True)]
        whole = torch.tensor([5.0], requires_grad=True)
        out = ScorerOutput(per_line_energies=per_line, whole_impl_energies=whole)
        result = compute_bce_loss(batch, out, pos_weight=5.0)
        assert result.total.item() > 0.5  # buggy line has negative energy = high loss
        assert result.n_line_pairs == 1
        result.total.backward()
        assert per_line[0].grad is not None

    def test_no_buggy_lines_returns_zero_loss(self) -> None:
        from ebm_verus.training.losses import compute_bce_loss
        batch = _make_batch(
            statuses=[Status.PASS],
            sources=[Source.SFT_SAFE],
            spec_ids=["s1"],
            traj_triples=[],
            safe_broken=[],
            buggy_lines_per_b=[[]],
            n_lines_per_b=[3],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0, 0.0, 0.0])],
            whole_impl_energies=torch.tensor([0.0]),
        )
        result = compute_bce_loss(batch, out)
        assert result.total.item() == 0.0


class TestORMLoss:
    def test_pass_low_fail_high_gives_low_loss(self) -> None:
        from ebm_verus.training.losses import compute_orm_loss
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL],
            sources=[Source.SFT_SAFE] * 2,
            spec_ids=["s1", "s1"],
            traj_triples=[],
            safe_broken=[],
            buggy_lines_per_b=[[], []],
            n_lines_per_b=[1, 1],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0]), torch.tensor([0.0])],
            whole_impl_energies=torch.tensor([-5.0, 5.0], requires_grad=True),
        )
        result = compute_orm_loss(batch, out)
        # PASS energy = -5 (sigmoid << 0.5), FAIL energy = 5 (sigmoid >> 0.5).
        # Both predictions match labels -> BCE near zero.
        assert result.total.item() < 0.1

    def test_inverted_predictions_give_high_loss(self) -> None:
        from ebm_verus.training.losses import compute_orm_loss
        batch = _make_batch(
            statuses=[Status.PASS, Status.FAIL],
            sources=[Source.SFT_SAFE] * 2,
            spec_ids=["s1", "s1"],
            traj_triples=[],
            safe_broken=[],
            buggy_lines_per_b=[[], []],
            n_lines_per_b=[1, 1],
        )
        out = ScorerOutput(
            per_line_energies=[torch.tensor([0.0]), torch.tensor([0.0])],
            whole_impl_energies=torch.tensor([5.0, -5.0], requires_grad=True),
        )
        result = compute_orm_loss(batch, out)
        # Inverted predictions: loss should be very high.
        assert result.total.item() > 4.0
        result.total.backward()
        assert out.whole_impl_energies.grad is not None
