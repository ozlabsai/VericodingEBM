"""Significance tests + subgroup analyses for the paper.

Consumes JSONL records emitted by score_external_records.py (or dump_eval_records.py).
Computes:
  1. McNemar's exact test on paired top-k correctness (our model vs length-baseline).
  2. DeLong AUROC-difference test (our model vs length-baseline whole-impl).
  3. Per-bug-type breakdown (regex on `// FAILS` context).
  4. |B|-stratified top-k (|B|=1, 2, >=3).
  5. Impl-length stratified top-k (tertiles).

Usage:
    uv run python scripts/significance_and_subgroups.py \
        --records artifacts/sentinel_reliant/eval_records.jsonl
"""
from __future__ import annotations
import argparse, json, math, re, sys
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
            s = str(r.get("status", "")).upper().split(".")[-1]
            r["status"] = s
            out.append(r)
    return out


# ---------- shared metric primitives ----------

def _topk_hit(scores: list[float], buggy: set[int], k: int) -> bool:
    if not scores or not buggy:
        return False
    k_eff = min(k, len(scores))
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return bool(set(order[:k_eff]) & buggy)


def _length_scores(scorable_texts: list[str]) -> list[float]:
    return [float(len(t)) for t in scorable_texts]


# ---------- 1. McNemar ----------

def mcnemar(records: list[dict], k: int = 3) -> dict:
    """Paired test: per-impl, did our-model-top-k hit the buggy set AND/OR did length-baseline.
    n01 = our wins (we hit, length missed), n10 = length wins, n00/n11 = ties.
    Mid-p exact test (preferred for small counts).
    """
    n00 = n01 = n10 = n11 = 0
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r.get("per_line_energies") or []
        texts = r.get("scorable_line_texts") or []
        if not es or len(texts) != len(es):
            continue
        buggy = set(r["buggy_line_indices"])
        ours = _topk_hit(es, buggy, k)
        length = _topk_hit(_length_scores(texts), buggy, k)
        if ours and length:
            n11 += 1
        elif ours and not length:
            n01 += 1
        elif not ours and length:
            n10 += 1
        else:
            n00 += 1
    # Exact mid-p McNemar
    b, c = n01, n10
    n_disc = b + c
    if n_disc == 0:
        p = 1.0
    else:
        # P(X <= min(b,c)) under Binom(n_disc, 0.5) two-sided
        lo = min(b, c)
        # exact two-sided binomial p (mid-p variant)
        p_one = sum(math.comb(n_disc, i) for i in range(lo + 1)) / (2 ** n_disc)
        p_mid = p_one - 0.5 * (math.comb(n_disc, lo) / (2 ** n_disc))
        p = min(1.0, 2.0 * p_mid)
    return {
        "k": k, "n11": n11, "n01_ours_only": n01,
        "n10_length_only": n10, "n00": n00,
        "n_total": n00 + n01 + n10 + n11,
        "ours_topk": (n11 + n01) / max(1, n00 + n01 + n10 + n11),
        "length_topk": (n11 + n10) / max(1, n00 + n01 + n10 + n11),
        "p_value_mcnemar_exact": p,
    }


# ---------- 2. DeLong ----------

def _ranks(values: list[float]) -> list[float]:
    # Returns midranks (ties get average rank), 1-indexed.
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-indexed midrank
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _auc_from_scores(scores: list[float], labels: list[int]) -> tuple[float, list[float], list[float]]:
    """Return (AUC, V10_positive_contribs, V01_negative_contribs) for DeLong.
    labels: 1=positive (FAIL), 0=negative (PASS).
    """
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    m, n = len(pos), len(neg)
    if m == 0 or n == 0:
        return float("nan"), [], []
    # Wilcoxon AUC via ranks
    all_ranks = _ranks(pos + neg)
    rank_pos = all_ranks[:m]
    auc = (sum(rank_pos) - m * (m + 1) / 2.0) / (m * n)
    # Structural components V10[i] = P(score(pos_i) > Y), V01[j] = P(X > score(neg_j))
    # Compute by counting per element against the other class.
    V10 = []
    for s in pos:
        wins = sum(1 for x in neg if s > x) + 0.5 * sum(1 for x in neg if s == x)
        V10.append(wins / n)
    V01 = []
    for s in neg:
        wins = sum(1 for x in pos if x > s) + 0.5 * sum(1 for x in pos if x == s)
        V01.append(wins / m)
    return auc, V10, V01


def delong_two_sample(scores_a: list[float], scores_b: list[float], labels: list[int]) -> dict:
    """DeLong test for two AUCs from the same data."""
    auc_a, V10_a, V01_a = _auc_from_scores(scores_a, labels)
    auc_b, V10_b, V01_b = _auc_from_scores(scores_b, labels)
    m = len(V10_a)
    n = len(V01_a)
    if m == 0 or n == 0 or math.isnan(auc_a) or math.isnan(auc_b):
        return {"auc_a": auc_a, "auc_b": auc_b, "diff": float("nan"),
                "se": float("nan"), "z": float("nan"), "p_value": float("nan")}

    def _cov(X: list[float], Y: list[float]) -> float:
        mx, my = sum(X) / len(X), sum(Y) / len(Y)
        return sum((X[i] - mx) * (Y[i] - my) for i in range(len(X))) / (len(X) - 1) if len(X) > 1 else 0.0

    s10 = _cov(V10_a, V10_a) / m
    s10ab = _cov(V10_a, V10_b) / m
    s10b = _cov(V10_b, V10_b) / m
    s01 = _cov(V01_a, V01_a) / n
    s01ab = _cov(V01_a, V01_b) / n
    s01b = _cov(V01_b, V01_b) / n
    var_diff = (s10 - 2 * s10ab + s10b) + (s01 - 2 * s01ab + s01b)
    se = math.sqrt(var_diff) if var_diff > 0 else float("nan")
    diff = auc_a - auc_b
    z = diff / se if se and not math.isnan(se) else float("nan")
    # Two-sided normal p
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2)))) if not math.isnan(z) else float("nan")
    return {"auc_a": auc_a, "auc_b": auc_b, "diff": diff, "se": se, "z": z, "p_value": p}


# ---------- 3. Per-bug-type ----------

_BUG_TYPE_PATTERNS = [
    ("assert",     re.compile(r"\bassert\b")),
    ("ensures",    re.compile(r"\bensures\b")),
    ("invariant",  re.compile(r"\binvariant\b")),
    ("decreases",  re.compile(r"\bdecreases\b")),
    ("requires",   re.compile(r"\brequires\b")),
    ("forall",     re.compile(r"\bforall\b|\bexists\b")),
]


def _classify_bug(text: str) -> str:
    for name, pat in _BUG_TYPE_PATTERNS:
        if pat.search(text):
            return name
    return "other"


def per_bug_type(records: list[dict], k: int = 3) -> dict:
    """For each record's FAILS line, classify by lexical context, then top-k hit rate per category."""
    buckets: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r.get("per_line_energies") or []
        texts = r.get("scorable_line_texts") or []
        if not es or len(texts) != len(es):
            continue
        buggy = set(r["buggy_line_indices"])
        ours_hit = _topk_hit(es, buggy, k)
        # Classify by the text content of the first buggy line.
        i = min(buggy)
        if i >= len(texts):
            continue
        cat = _classify_bug(texts[i])
        buckets[cat].append(ours_hit)
    return {
        cat: {
            "n": len(hits),
            "topk": sum(hits) / max(1, len(hits)),
        }
        for cat, hits in sorted(buckets.items(), key=lambda x: -len(x[1]))
    }


# ---------- 4. |B|-stratified ----------

def b_stratified(records: list[dict], k: int = 3) -> dict:
    """Bucket records by |B|=1, 2, >=3 and report top-k."""
    buckets: dict[str, list[bool]] = {"|B|=1": [], "|B|=2": [], "|B|>=3": []}
    for r in records:
        if r["status"] != "FAIL" or not r["buggy_line_indices"]:
            continue
        es = r.get("per_line_energies") or []
        if not es:
            continue
        buggy = set(r["buggy_line_indices"])
        b = len(buggy)
        key = "|B|=1" if b == 1 else "|B|=2" if b == 2 else "|B|>=3"
        buckets[key].append(_topk_hit(es, buggy, k))
    return {
        key: {"n": len(hits), "topk": (sum(hits) / max(1, len(hits)))}
        for key, hits in buckets.items()
    }


# ---------- 5. Length-stratified ----------

def length_stratified(records: list[dict], k: int = 3) -> dict:
    """Bucket records by impl line-count tertile and report top-k."""
    eligible = [
        r for r in records
        if r["status"] == "FAIL" and r["buggy_line_indices"] and r.get("per_line_energies")
    ]
    if not eligible:
        return {}
    eligible.sort(key=lambda r: len(r["per_line_energies"]))
    n = len(eligible)
    t1, t2 = n // 3, (2 * n) // 3
    buckets = {"short": eligible[:t1], "medium": eligible[t1:t2], "long": eligible[t2:]}
    out = {}
    for name, recs in buckets.items():
        hits = [_topk_hit(r["per_line_energies"], set(r["buggy_line_indices"]), k) for r in recs]
        n_lines = [len(r["per_line_energies"]) for r in recs]
        out[name] = {
            "n": len(hits),
            "topk": sum(hits) / max(1, len(hits)),
            "n_lines_p50": sorted(n_lines)[len(n_lines) // 2] if n_lines else 0,
            "n_lines_range": [min(n_lines), max(n_lines)] if n_lines else [0, 0],
        }
    return out


# ---------- driver ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, type=Path)
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    records = load_records(args.records)
    print(f"loaded {len(records)} records from {args.records}")

    print("\n[McNemar] paired top-3: our model vs length-baseline")
    mc = mcnemar(records, k=args.k)
    for k, v in mc.items():
        print(f"  {k}: {v}")

    print("\n[DeLong] whole-impl AUROC: our model vs length-baseline (per-impl max length as score)")
    a_scores, b_scores, labels = [], [], []
    for r in records:
        if r["status"] not in ("PASS", "FAIL"):
            continue
        es = r.get("per_line_energies") or []
        texts = r.get("scorable_line_texts") or []
        if not es or len(texts) != len(es):
            continue
        a_scores.append(r.get("whole_impl_energy", max(es) if es else 0.0))
        # length-baseline whole-impl proxy: max line length
        b_scores.append(max((len(t) for t in texts), default=0.0))
        labels.append(1 if r["status"] == "FAIL" else 0)
    dl = delong_two_sample(a_scores, b_scores, labels)
    for k, v in dl.items():
        print(f"  {k}: {v}")

    print("\n[Per-bug-type] top-3 by `// FAILS` line lexical context")
    bt = per_bug_type(records, k=args.k)
    for cat, stats in bt.items():
        print(f"  {cat:14s}: n={stats['n']:4d}  top-{args.k} = {stats['topk']:.3f}")

    print("\n[|B|-stratified] top-3 by buggy-line count")
    bs = b_stratified(records, k=args.k)
    for key, stats in bs.items():
        print(f"  {key:8s}: n={stats['n']:4d}  top-{args.k} = {stats['topk']:.3f}")

    print("\n[Length-stratified] top-3 by impl line-count tertile")
    ls = length_stratified(records, k=args.k)
    for key, stats in ls.items():
        print(f"  {key:8s}: n={stats['n']:4d}  top-{args.k} = {stats['topk']:.3f}  "
              f"n_lines p50={stats['n_lines_p50']}  range={stats['n_lines_range']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
