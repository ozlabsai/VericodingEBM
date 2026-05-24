"""Tests for eval metrics. CPU-only."""

from __future__ import annotations

import math

import pytest

from ebm_verus.data.types import Status
from ebm_verus.eval.metrics import (
    EvalRecord,
    compute_eval_metrics,
    per_line_topk_recall,
    whole_impl_auroc,
    within_spec_ranking_accuracy,
)


def _r(impl_id: str, spec_id: str, status: Status, e: float,
       per_line: list[float] | None = None, buggy: list[int] | None = None) -> EvalRecord:
    return EvalRecord(
        impl_id=impl_id, spec_id=spec_id, status=status,
        whole_impl_energy=e,
        per_line_energies=per_line or [],
        buggy_line_indices=buggy or [],
    )


class TestAUROC:
    def test_perfect_ranking(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, -2.0),
            _r("b", "s1", Status.PASS, -1.0),
            _r("c", "s2", Status.FAIL, 1.0),
            _r("d", "s2", Status.FAIL, 2.0),
        ]
        auroc, n_p, n_f = whole_impl_auroc(records)
        assert auroc == pytest.approx(1.0)
        assert n_p == 2 and n_f == 2

    def test_inverted_ranking(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, 2.0),
            _r("b", "s2", Status.FAIL, -2.0),
        ]
        auroc, *_ = whole_impl_auroc(records)
        assert auroc == pytest.approx(0.0)

    def test_missing_class_returns_none(self) -> None:
        records = [_r("a", "s1", Status.PASS, -1.0)]
        auroc, n_p, n_f = whole_impl_auroc(records)
        assert auroc is None
        assert n_p == 1 and n_f == 0


class TestPerLineTopK:
    def test_top1_hit(self) -> None:
        records = [
            _r("a", "s1", Status.FAIL, 0.0,
               per_line=[0.0, 5.0, 1.0], buggy=[1]),
        ]
        rec, n = per_line_topk_recall(records, k=1)
        assert rec == pytest.approx(1.0)
        assert n == 1

    def test_top1_miss(self) -> None:
        records = [
            _r("a", "s1", Status.FAIL, 0.0,
               per_line=[5.0, 0.0, 1.0], buggy=[1]),  # top-1 is index 0, not buggy
        ]
        rec, _ = per_line_topk_recall(records, k=1)
        assert rec == pytest.approx(0.0)

    def test_top3_finds_within_window(self) -> None:
        records = [
            _r("a", "s1", Status.FAIL, 0.0,
               per_line=[5.0, 4.0, 0.0, 3.0, 0.0], buggy=[3]),
        ]
        # top-3 by energy = {0, 1, 3}. 3 is buggy → hit.
        rec, _ = per_line_topk_recall(records, k=3)
        assert rec == pytest.approx(1.0)

    def test_pass_impls_ignored(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, 0.0,
               per_line=[1.0, 0.0], buggy=[1]),  # PASS w/ buggy=[1] — weird but should be ignored
            _r("b", "s1", Status.FAIL, 0.0,
               per_line=[5.0, 0.0], buggy=[0]),  # FAIL, top-1 correct
        ]
        rec, n = per_line_topk_recall(records, k=1)
        assert n == 1  # only the FAIL impl was evaluated
        assert rec == pytest.approx(1.0)

    def test_empty_buggy_skipped(self) -> None:
        records = [
            _r("a", "s1", Status.FAIL, 0.0,
               per_line=[5.0, 0.0], buggy=[]),
        ]
        rec, n = per_line_topk_recall(records, k=1)
        assert n == 0
        assert rec is None


class TestWithinSpecRanking:
    def test_correct_ranking(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, -1.0),
            _r("b", "s1", Status.FAIL, 1.0),
        ]
        acc, n = within_spec_ranking_accuracy(records)
        assert acc == pytest.approx(1.0)
        assert n == 1

    def test_incorrect_ranking(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, 1.0),
            _r("b", "s1", Status.FAIL, -1.0),
        ]
        acc, _ = within_spec_ranking_accuracy(records)
        assert acc == pytest.approx(0.0)

    def test_single_label_spec_excluded(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, -1.0),  # s1 has only PASS
            _r("b", "s2", Status.PASS, -1.0),
            _r("c", "s2", Status.FAIL, 1.0),
        ]
        acc, n = within_spec_ranking_accuracy(records)
        assert n == 1  # only s2 is mixed
        assert acc == pytest.approx(1.0)


class TestComputeAll:
    def test_full_metrics(self) -> None:
        records = [
            _r("a", "s1", Status.PASS, -1.0, per_line=[-1.0, -1.0], buggy=[]),
            _r("b", "s1", Status.FAIL, 1.0,  per_line=[2.0, 0.0], buggy=[0]),
        ]
        m = compute_eval_metrics(records)
        assert m.n_impls == 2
        assert m.n_pass == 1 and m.n_fail == 1
        assert m.whole_impl_auroc == pytest.approx(1.0)
        assert m.per_line_top1_recall == pytest.approx(1.0)
        assert m.within_spec_ranking_accuracy == pytest.approx(1.0)
        assert m.energy_mean_pass == pytest.approx(-1.0)
        assert m.energy_mean_fail == pytest.approx(1.0)
        assert m.energy_std is not None and m.energy_std > 0
