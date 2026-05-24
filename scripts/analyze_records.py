"""Post-hoc analysis over dumped eval records.

Reads the JSONL emitted by dump_eval_records.py and runs all the cheap
analyses we owe a reviewer:

  * E2: bootstrap 95% CIs on top-1, top-3, AUROC
  * E3: z-score within-impl + top-k mean aggregator (varying k)
  * Triviality 1: per-line energy vs line-length Spearman corr
  * Triviality 3: distribution of buggy-line *position* (index / n_lines)
  * uniform-random top-k baseline for comparison

Usage:
    uv run python scripts/analyze_records.py --records artifacts/eval_records.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            # Normalize status to upper-case "PASS"/"FAIL"/"UNKNOWN".
            s = str(r.get("status", "")).upper()
            if "." in s:
                s = s.split(".")[-1]
            r["status"] = s
            out.append(r)
    return out


# ---------- metric primitives ----------

def _auc(scores: list[float], labels: list[int]) -> float | None:
    """Mann-Whitney AUC. labels: 1 = positive (FAIL), 0 = negative (PASS)."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = 0
    ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def _topk_recall(records: list[dict], k: int, score_key: str = "per_line_energies") -> tuple[float | None, int]:
    hits = 0
    n = 0
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r[score_key]
        if not es:
            continue
        n += 1
        keff = min(k, len(es))
        order = sorted(range(len(es)), key=lambda i: -es[i])
        top = set(order[:keff])
        if top & set(r["buggy_line_indices"]):
            hits += 1
    if n == 0:
        return None, 0
    return hits / n, n


def _uniform_topk(records: list[dict], k: int) -> float:
    """Closed-form expected top-k recall under uniform random selection.
    For each FAIL impl with N lines and B buggy: 1 - C(N-B, k) / C(N, k).
    """
    total = 0.0
    n = 0
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r["per_line_energies"]
        if not es:
            continue
        N = len(es)
        B = len(set(r["buggy_line_indices"]) & set(range(N)))
        if B == 0:
            continue
        keff = min(k, N)
        if N - B < keff:
            p_miss = 0.0
        else:
            p_miss = math.comb(N - B, keff) / math.comb(N, keff)
        total += (1.0 - p_miss)
        n += 1
    return total / n if n else 0.0


# ---------- z-score aggregator ----------

def _z_topk_mean(per_line: list[float], k: int) -> float:
    """Within-impl z-score normalize then take mean of top-k z values."""
    if not per_line:
        return 0.0
    mu = statistics.fmean(per_line)
    if len(per_line) > 1:
        sd = statistics.pstdev(per_line) or 1.0
    else:
        sd = 1.0
    z = [(e - mu) / sd for e in per_line]
    keff = min(k, len(z))
    return sum(sorted(z, reverse=True)[:keff]) / keff


def _max_aggregator(per_line: list[float]) -> float:
    return max(per_line) if per_line else 0.0


# ---------- analyses ----------

def analyze_basic(records: list[dict]) -> None:
    pass_e = [r["whole_impl_energy"] for r in records if r["status"] == "PASS"]
    fail_e = [r["whole_impl_energy"] for r in records if r["status"] == "FAIL"]
    print(f"\n[E0] n={len(records)} pass={len(pass_e)} fail={len(fail_e)}")
    scores = pass_e + fail_e
    labels = [0] * len(pass_e) + [1] * len(fail_e)
    auc = _auc(scores, labels)
    auc_s = f"{auc:.4f}" if auc is not None else "n/a (need both PASS and FAIL)"
    print(f"  AUROC (whole-impl aggregator) = {auc_s}")
    for k in (1, 3, 5):
        r, n = _topk_recall(records, k)
        uni = _uniform_topk(records, k)
        if r is None:
            print(f"  top-{k} recall = n/a (no FAIL impls with buggy_line_indices)")
            continue
        lift = (r / uni) if uni else float("nan")
        print(f"  top-{k} recall = {r:.4f}  (uniform = {uni:.4f}, lift = {lift:.2f}x, n={n})")


def analyze_aggregator_sweep(records: list[dict]) -> None:
    """A3: PRM-literature standard. Same per-line energies, swap aggregators.
    Reports whole-impl AUROC for {mean, max, min, last, sum, neg-sum-neg-logprob}.
    """
    print("\n[A3] aggregator sweep (same per-line energies, different whole-impl reducer)")
    pass_recs = [r for r in records if r["status"] == "PASS"]
    fail_recs = [r for r in records if r["status"] == "FAIL"]
    if not pass_recs or not fail_recs:
        print("  (need both PASS and FAIL records)")
        return

    def _ms(es):  # mean-subtracted (kills per-impl additive-bias drift)
        if not es:
            return []
        m = sum(es) / len(es)
        return [e - m for e in es]

    aggregators = {
        "mean": lambda es: sum(es) / len(es) if es else 0.0,
        "max":  lambda es: max(es) if es else 0.0,
        "min":  lambda es: min(es) if es else 0.0,
        "last": lambda es: es[-1] if es else 0.0,
        "sum":  lambda es: sum(es) if es else 0.0,
        # PRM-style "product of probabilities" = sum of log-probs.
        # We treat energy E as a logit; logp(line is OK) = -log(1 + exp(E)) (softplus(-E)... ish);
        # whole-impl bad-score = sum_i softplus(E_i). For ranking, equivalent to sum of softplus.
        "softplus_sum": lambda es: sum(math.log1p(math.exp(min(20.0, e))) for e in es) if es else 0.0,
        # Shift-invariant reducers — defend against inter-impl bias-term drift
        # (the run #9 AUROC inversion is the textbook signature of this).
        "ms_max":   lambda es: max(_ms(es)) if es else 0.0,
        "ms_top3":  lambda es: sum(sorted(_ms(es), reverse=True)[:3]) / max(1, min(3, len(es))) if es else 0.0,
        "ms_top1_minus_min": lambda es: (max(_ms(es)) - min(_ms(es))) if es else 0.0,
    }

    for name, fn in aggregators.items():
        scores = [fn(r["per_line_energies"]) for r in pass_recs + fail_recs]
        labels = [0] * len(pass_recs) + [1] * len(fail_recs)
        auc = _auc(scores, labels)
        auc_s = f"{auc:.4f}" if auc is not None else "n/a"
        print(f"  {name:14s}: AUROC = {auc_s}")


def analyze_zscore_aggregator(records: list[dict]) -> None:
    print("\n[E3] z-score within-impl + top-k mean aggregator")
    pass_recs = [r for r in records if r["status"] == "PASS"]
    fail_recs = [r for r in records if r["status"] == "FAIL"]
    for k in (1, 2, 3, 5):
        pass_scores = [_z_topk_mean(r["per_line_energies"], k) for r in pass_recs]
        fail_scores = [_z_topk_mean(r["per_line_energies"], k) for r in fail_recs]
        auc = _auc(pass_scores + fail_scores, [0] * len(pass_scores) + [1] * len(fail_scores))
        print(f"  k={k}: AUROC = {auc:.4f}")
    pass_scores = [_max_aggregator(r["per_line_energies"]) for r in pass_recs]
    fail_scores = [_max_aggregator(r["per_line_energies"]) for r in fail_recs]
    auc = _auc(pass_scores + fail_scores, [0] * len(pass_scores) + [1] * len(fail_scores))
    print(f"  max (raw, no z): AUROC = {auc:.4f}")


def analyze_bootstrap(records: list[dict], iters: int = 500, seed: int = 0) -> None:
    print(f"\n[E2] bootstrap CIs (iters={iters})")
    rng = random.Random(seed)
    auc_samples = []
    top1_samples = []
    top3_samples = []
    n = len(records)
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        sample = [records[i] for i in idx]
        scores = [r["whole_impl_energy"] for r in sample]
        labels = [1 if r["status"] == "FAIL" else 0 for r in sample]
        auc = _auc(scores, labels)
        if auc is not None:
            auc_samples.append(auc)
        r1, _ = _topk_recall(sample, 1)
        r3, _ = _topk_recall(sample, 3)
        if r1 is not None:
            top1_samples.append(r1)
        if r3 is not None:
            top3_samples.append(r3)

    def _ci(xs):
        if not xs:
            return ("n/a", "n/a", "n/a")
        xs = sorted(xs)
        return (xs[len(xs) // 2], xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs))])

    for name, xs in [("AUROC", auc_samples), ("top1", top1_samples), ("top3", top3_samples)]:
        med, lo, hi = _ci(xs)
        if isinstance(med, str):
            print(f"  {name}: n/a")
        else:
            print(f"  {name}: median={med:.4f} 95% CI=[{lo:.4f}, {hi:.4f}]")


def analyze_triviality(records: list[dict]) -> None:
    print("\n[Triv] per-line energy vs line-position; buggy-line position distribution")

    # Triv 3: position distribution of buggy lines (as fraction of impl length).
    positions = []
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        N = len(r["per_line_energies"])
        if N == 0:
            continue
        for i in r["buggy_line_indices"]:
            if 0 <= i < N:
                positions.append(i / max(1, N - 1))
    if positions:
        positions.sort()
        q25 = positions[len(positions) // 4]
        q50 = positions[len(positions) // 2]
        q75 = positions[3 * len(positions) // 4]
        print(f"  buggy-line position: median={q50:.2f} Q25={q25:.2f} Q75={q75:.2f} n={len(positions)}")

    # Sanity: position of top-1 prediction (does our model also cluster?)
    pred_positions = []
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r["per_line_energies"]
        if not es:
            continue
        top1 = max(range(len(es)), key=lambda i: es[i])
        pred_positions.append(top1 / max(1, len(es) - 1))
    if pred_positions:
        pred_positions.sort()
        q25 = pred_positions[len(pred_positions) // 4]
        q50 = pred_positions[len(pred_positions) // 2]
        q75 = pred_positions[3 * len(pred_positions) // 4]
        print(f"  pred-top1 position:  median={q50:.2f} Q25={q25:.2f} Q75={q75:.2f} n={len(pred_positions)}")

    # Triv 1: rank correlation between energy and position rank (sentinel index).
    # If buggy-line distribution and pred-top1 distribution both cluster the same
    # way, energy could be position-confounded. Approximate Spearman per-impl
    # then average.
    correlations = []
    for r in records:
        es = r["per_line_energies"]
        N = len(es)
        if N < 3:
            continue
        # Spearman vs index = correlation between rank(energy) and 0..N-1.
        order = sorted(range(N), key=lambda i: es[i])
        rank = [0] * N
        for r_, i in enumerate(order):
            rank[i] = r_
        # corr(rank, 0..N-1) via formula
        mean_r = (N - 1) / 2
        num = sum((rank[i] - mean_r) * (i - mean_r) for i in range(N))
        den = (N * (N**2 - 1)) / 12  # variance of 0..N-1 times N
        if den == 0:
            continue
        correlations.append(num / den)
    if correlations:
        avg = sum(correlations) / len(correlations)
        print(f"  Spearman(per-line-energy, position) per-impl mean = {avg:+.4f} (|.| < 0.2 desired)")


def analyze_line_length_baseline(records: list[dict]) -> None:
    print("\n[Baseline] line-length: rank lines by character count desc, then top-k recall")
    # Per-impl top-k against same buggy_line_indices.
    have_text = [r for r in records if r.get("scorable_line_texts")]
    if not have_text:
        print("  (no scorable_line_texts in records; rerun dump to include them)")
        return
    # Inject a length-as-energy field locally.
    aug = []
    for r in have_text:
        lens = [len(t) for t in r["scorable_line_texts"]]
        rr = dict(r)
        rr["per_line_energies_length"] = lens
        aug.append(rr)
    for k in (1, 3):
        ours, _ = _topk_recall(aug, k, score_key="per_line_energies")
        baseline, n = _topk_recall(aug, k, score_key="per_line_energies_length")
        uni = _uniform_topk(aug, k)
        ours_s = f"{ours:.4f}" if ours is not None else "n/a"
        base_s = f"{baseline:.4f}" if baseline is not None else "n/a"
        print(f"  top-{k}: ours={ours_s}  length-baseline={base_s}  uniform={uni:.4f}  (n={n})")


def analyze_by_source(records: list[dict]) -> None:
    print("\n[R3] split by source")
    by_src = defaultdict(list)
    for r in records:
        key = r.get("source") or r["impl_id"].split("-")[0]
        by_src[key].append(r)
    for src, recs in sorted(by_src.items()):
        n = len(recs)
        pass_n = sum(1 for r in recs if r["status"] == "PASS")
        fail_n = sum(1 for r in recs if r["status"] == "FAIL")
        scores = [r["whole_impl_energy"] for r in recs]
        labels = [1 if r["status"] == "FAIL" else 0 for r in recs]
        auc = _auc(scores, labels)
        top3, n3 = _topk_recall(recs, 3)
        auc_s = f"{auc:.4f}" if auc is not None else "n/a"
        top3_s = f"{top3:.4f}" if top3 is not None else "n/a"
        print(f"  {src:20s} n={n:5d} pass={pass_n:5d} fail={fail_n:5d} AUROC={auc_s} top3={top3_s} (n_line={n3})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, type=Path)
    ap.add_argument("--bootstrap-iters", type=int, default=500)
    args = ap.parse_args()

    records = load_records(args.records)
    print(f"loaded {len(records)} records")

    analyze_basic(records)
    analyze_aggregator_sweep(records)
    analyze_zscore_aggregator(records)
    analyze_bootstrap(records, iters=args.bootstrap_iters)
    analyze_triviality(records)
    analyze_line_length_baseline(records)
    analyze_by_source(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
