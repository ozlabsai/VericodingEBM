"""Verus-keyword baseline: rank lines by presence of bug-likely keywords.

Research V4 §2.3: "If keyword-baseline scores near 0.85 on real bugs, our
+20pp claim should be reframed as +Xpp over keyword-baseline." Highest-EV
baseline to add before claiming the model has learned anything beyond DSL
syntax cues.

Score per line = bonus for containing each of {assert, ensures, invariant,
decreases, requires, forall, exists, assume}. Rank desc; top-k recall.

Reads a records.jsonl (scorable_line_texts present) and reports the same
top-k metrics as analyze_records.py.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

VERUS_KEYWORDS = [
    "assert", "ensures", "invariant", "decreases",
    "requires", "forall", "exists", "assume", "recommends",
]


def _kw_score(line: str) -> float:
    s = 0
    for kw in VERUS_KEYWORDS:
        if kw in line:
            s += 1
    # Heavier weight if multiple keywords; ties broken by line length (longer wins)
    return s + 0.001 * len(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, type=Path)
    args = ap.parse_args()

    records = []
    with args.records.open() as f:
        for line in f:
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            r["status"] = str(r.get("status","")).upper().split(".")[-1]
            records.append(r)
    print(f"loaded {len(records)} records")

    # Score with keyword baseline; compute top-1 / top-3 / top-5
    hits = {1: 0, 3: 0, 5: 0}
    n = 0
    uniform = {1: 0.0, 3: 0.0, 5: 0.0}
    for r in records:
        if r["status"] != "FAIL" or not r.get("buggy_line_indices"):
            continue
        texts = r.get("scorable_line_texts") or []
        if not texts: continue
        buggy = set(r["buggy_line_indices"])
        if not buggy & set(range(len(texts))):
            continue
        n += 1
        scores = [_kw_score(t) for t in texts]
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        for k in (1, 3, 5):
            keff = min(k, len(scores))
            if set(order[:keff]) & buggy:
                hits[k] += 1
            # uniform expectation (closed form)
            B = len(buggy & set(range(len(texts))))
            N = len(texts)
            from math import comb
            if N - B < keff:
                p_miss = 0.0
            else:
                p_miss = comb(N - B, keff) / comb(N, keff)
            uniform[k] += (1.0 - p_miss)

    print(f"\nVerus-keyword baseline on {n} FAIL records with labels:")
    for k in (1, 3, 5):
        topk = hits[k] / max(1, n)
        uni = uniform[k] / max(1, n)
        lift = topk / uni if uni > 0 else float('nan')
        print(f"  top-{k}: {topk:.4f}  (uniform = {uni:.4f}, lift = {lift:.2f}x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
