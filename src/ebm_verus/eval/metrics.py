"""Evaluation metrics for the energy-based scorer.

All metrics work over *rankings* of energies, not thresholds — energies are
unbounded scalars, so absolute values are not meaningful, only relative
ordering is.

Implemented:
  * whole_impl_auroc: rank impls by E and check separation from labels
  * per_line_topk_recall: on FAIL impls with known buggy_lines, does the
    top-k highest-energy line set intersect the labeled buggy set?
  * within_spec_ranking_accuracy: on mixed-label spec groups, does the
    PASS impl score lower than every FAIL impl?

These metrics expect *aggregated* eval outputs (numpy/Python lists), not raw
tensors. The eval loop is responsible for running the model and collecting
per-example results into the dataclass.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import roc_auc_score

from ebm_verus.data.types import Status


@dataclass
class EvalRecord:
    """One eval-time output per impl, accumulated by the eval loop."""

    impl_id: str
    spec_id: str
    status: Status
    whole_impl_energy: float
    per_line_energies: list[float]
    buggy_line_indices: list[int]   # in sentinel-space (NOT source-line-space)


@dataclass
class EvalMetrics:
    whole_impl_auroc: float | None
    n_impls: int
    n_pass: int
    n_fail: int

    per_line_top1_recall: float | None
    per_line_top3_recall: float | None
    n_line_eval_impls: int            # number of FAIL impls with buggy_lines used

    within_spec_ranking_accuracy: float | None
    n_mixed_specs: int

    # Diagnostic distributions.
    energy_mean_pass: float | None = None
    energy_mean_fail: float | None = None
    energy_std: float | None = None

    by_source: dict[str, dict] = field(default_factory=dict)


def whole_impl_auroc(records: list[EvalRecord]) -> tuple[float | None, int, int]:
    """AUROC ranking FAIL above PASS. Returns ``(auroc, n_pass, n_fail)``.

    Returns ``(None, ...)`` if either class is missing.
    """
    y_true: list[int] = []
    y_score: list[float] = []
    for r in records:
        if r.status == Status.PASS:
            y_true.append(0)
            y_score.append(r.whole_impl_energy)
        elif r.status == Status.FAIL:
            y_true.append(1)
            y_score.append(r.whole_impl_energy)
        # UNKNOWN dropped
    n_pass = y_true.count(0)
    n_fail = y_true.count(1)
    if n_pass == 0 or n_fail == 0:
        return None, n_pass, n_fail
    return float(roc_auc_score(y_true, y_score)), n_pass, n_fail


def per_line_topk_recall(records: list[EvalRecord], k: int) -> tuple[float | None, int]:
    """Top-k recall over impls labeled FAIL with non-empty buggy_lines.

    For each such impl:
      top_k = indices of the k highest per-line energies
      hit   = 1 if top_k ∩ buggy_lines is non-empty, else 0
    Returns mean hit rate, plus n_impls evaluated.
    """
    hits = 0
    n = 0
    for r in records:
        if r.status != Status.FAIL or not r.buggy_line_indices:
            continue
        if not r.per_line_energies:
            continue
        n += 1
        energies = np.asarray(r.per_line_energies)
        k_eff = min(k, energies.shape[0])
        top_k = set(np.argsort(-energies)[:k_eff].tolist())
        if top_k & set(r.buggy_line_indices):
            hits += 1
    if n == 0:
        return None, 0
    return hits / n, n


def within_spec_ranking_accuracy(records: list[EvalRecord]) -> tuple[float | None, int]:
    """Fraction of mixed-label specs where every PASS impl has lower E than every
    FAIL impl. Only counted for specs that have both labels among held-out impls.
    """
    by_spec: dict[str, list[EvalRecord]] = defaultdict(list)
    for r in records:
        by_spec[r.spec_id].append(r)
    correct = 0
    total = 0
    for _spec, group in by_spec.items():
        pass_es = [g.whole_impl_energy for g in group if g.status == Status.PASS]
        fail_es = [g.whole_impl_energy for g in group if g.status == Status.FAIL]
        if not pass_es or not fail_es:
            continue
        total += 1
        if max(pass_es) < min(fail_es):
            correct += 1
    if total == 0:
        return None, 0
    return correct / total, total


def compute_eval_metrics(records: list[EvalRecord]) -> EvalMetrics:
    auroc, n_pass, n_fail = whole_impl_auroc(records)
    top1, n_line1 = per_line_topk_recall(records, k=1)
    top3, n_line3 = per_line_topk_recall(records, k=3)
    rank_acc, n_mixed = within_spec_ranking_accuracy(records)

    pass_energies = [r.whole_impl_energy for r in records if r.status == Status.PASS]
    fail_energies = [r.whole_impl_energy for r in records if r.status == Status.FAIL]
    all_energies = pass_energies + fail_energies

    return EvalMetrics(
        whole_impl_auroc=auroc,
        n_impls=len(records),
        n_pass=n_pass,
        n_fail=n_fail,
        per_line_top1_recall=top1,
        per_line_top3_recall=top3,
        n_line_eval_impls=n_line1 or 0,
        within_spec_ranking_accuracy=rank_acc,
        n_mixed_specs=n_mixed,
        energy_mean_pass=float(np.mean(pass_energies)) if pass_energies else None,
        energy_mean_fail=float(np.mean(fail_energies)) if fail_energies else None,
        energy_std=float(np.std(all_energies)) if all_energies else None,
    )
