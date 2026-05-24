"""Audit #5: rep0/rep1/rep2 edit distance + all-fail differential failure rate.

Two questions:

  Q1 — How correlated are repetition=0, =1, =2 impls within the same spec?
       If they're near-identical (e.g. CEGIS only changes 1-2 lines per rep),
       the within-spec InfoNCE is comparing near-duplicates with different
       verdicts — useful for fine-grained training but worth being aware of
       for the writeup framing.

  Q2 — Of the all-fail triples (no PASS in the rep0/1/2 set), how many have
       *differential* failure? i.e., do the 3 attempts produce different
       error kinds / different verifier outputs? If >50% have differential
       failure, we can extract a soft within-spec ranking (least failing →
       most failing) and use it as additional L_spec signal — currently
       wasted, since these triples contribute zero gradient.

Usage:
    uv run python scripts/audit_trajectory.py
"""

from __future__ import annotations

import difflib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT = Path("data/raw/system_trajectory_843.jsonl")


def _extract_code(row: dict) -> str:
    """Pull the code that represents this impl attempt.

    For PASS rows: ``verified_code``.
    For FAIL rows: ``original_item.output`` (the model's failing attempt),
    falling back to ``original_item.input`` if output is empty/missing.
    """
    status = row.get("status", "")
    if status == "success":
        return row.get("verified_code") or ""
    # FAIL: pull from original_item
    raw = row.get("original_item")
    if isinstance(raw, str):
        try:
            oi = json.loads(raw)
        except Exception:
            return ""
    elif isinstance(raw, dict):
        oi = raw
    else:
        return ""
    out = oi.get("output") or ""
    if out:
        return out
    return oi.get("input") or ""


def _norm_status(s: str) -> str:
    return {"success": "PASS", "error": "FAIL", "timeout": "FAIL"}.get(s, "?")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    print(f"audit: rep0/rep1/rep2 stats on {path}")
    print("=" * 72)

    rows_by_spec: dict[int, list[dict]] = defaultdict(list)
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            spec = row.get("original_index")
            if spec is None:
                continue
            rows_by_spec[spec].append(row)

    print(f"specs: {len(rows_by_spec)}")
    counts = [len(v) for v in rows_by_spec.values()]
    print(f"impls-per-spec dist: min={min(counts)} mean={statistics.mean(counts):.2f} max={max(counts)}")
    print()

    # Q1: rep0 vs rep_max line-level diff per spec.
    # (Char-level SequenceMatcher is O(n*m) and impls can be 60k+ chars —
    # too slow. Line-level diff is the right grain anyway.)
    print("Q1 — rep0 vs latest-rep line-level diff per spec:")
    line_changes: list[int] = []
    line_frac: list[float] = []
    for spec, rows in rows_by_spec.items():
        rows = sorted(rows, key=lambda r: r.get("repetition", 0))
        if len(rows) < 2:
            continue
        code0 = _extract_code(rows[0])
        code_last = _extract_code(rows[-1])
        if not code0 or not code_last:
            continue
        l0 = code0.splitlines()
        l1 = code_last.splitlines()
        sm = difflib.SequenceMatcher(a=l0, b=l1, autojunk=False)
        n_changed = sum(
            (i2 - i1) for tag, i1, i2, _j1, _j2 in sm.get_opcodes()
            if tag in ("replace", "delete")
        )
        line_changes.append(n_changed)
        total = max(1, len(l0))
        line_frac.append(n_changed / total)
    if line_changes:
        line_changes.sort()
        line_frac.sort()
        n = len(line_changes)
        print(f"  n_specs_with_2plus_reps = {n}")
        print(f"  changed lines (rep0 -> last): "
              f"p50={line_changes[n//2]} "
              f"p90={line_changes[int(0.9*n)]} "
              f"p99={line_changes[int(0.99*n)]} "
              f"max={max(line_changes)}")
        print(f"  changed fraction of file: "
              f"p25={line_frac[n//4]:.3f} "
              f"p50={line_frac[n//2]:.3f} "
              f"p75={line_frac[3*n//4]:.3f}")
        near_iden = sum(1 for f in line_frac if f <= 0.05)
        print(f"    specs where <=5% of lines changed: {near_iden} "
              f"({100*near_iden/n:.1f}%)")
    print()

    # Q2: all-fail triple differential
    print("Q2 — all-fail triples + differential failure:")
    n_specs = 0
    n_mixed = 0
    n_allpass = 0
    n_allfail = 0
    n_allfail_with_differential = 0
    allfail_details: list[tuple[int, list[str], list[int]]] = []

    for spec, rows in rows_by_spec.items():
        n_specs += 1
        statuses = [_norm_status(r.get("status", "")) for r in rows]
        if "PASS" in statuses and "FAIL" in statuses:
            n_mixed += 1
        elif all(s == "PASS" for s in statuses):
            n_allpass += 1
        elif all(s == "FAIL" for s in statuses):
            n_allfail += 1
            # Differential markers: distinct return_code OR distinct raw status
            return_codes = sorted({r.get("return_code") for r in rows})
            raw_statuses = sorted({r.get("status") for r in rows})
            # Also check: distinct original_item.output content (if any has it)
            outputs = []
            for r in rows:
                raw = r.get("original_item")
                if isinstance(raw, str):
                    try:
                        oi = json.loads(raw)
                        out = oi.get("output") or ""
                        outputs.append(len(out))
                    except Exception:
                        outputs.append(0)
                else:
                    outputs.append(0)
            differential = (
                len(return_codes) > 1
                or len(raw_statuses) > 1
                or len(set(outputs)) > 1
            )
            if differential:
                n_allfail_with_differential += 1
            allfail_details.append((spec, raw_statuses, outputs))

    print(f"  total specs: {n_specs}")
    print(f"  mixed (>=1 PASS + >=1 FAIL): {n_mixed} ({100*n_mixed/n_specs:.1f}%)")
    print(f"  all-PASS:    {n_allpass} ({100*n_allpass/n_specs:.1f}%)")
    print(f"  all-FAIL:    {n_allfail} ({100*n_allfail/n_specs:.1f}%)")
    if n_allfail:
        pct = 100 * n_allfail_with_differential / n_allfail
        print(f"    of those, with differential failure: "
              f"{n_allfail_with_differential}/{n_allfail} ({pct:.1f}%)")
        # Show 3 examples
        print("  sample all-fail specs (status_set, output_lens):")
        for spec, raws, outs in allfail_details[:3]:
            print(f"    spec={spec}  raw_statuses={raws}  output_lens={outs}")

    print()
    print("=" * 72)
    print("conclusion:")
    if line_frac:
        median_frac = line_frac[len(line_frac)//2]
        if median_frac <= 0.1:
            print(f"  Q1: rep0/last line-change fraction p50 = {median_frac:.3f} — "
                  f"the attempts are highly correlated.")
            print("       Writeup: frame as 'CEGIS trajectory, not iid samples'.")
        else:
            print(f"  Q1: rep0/last line-change fraction p50 = {median_frac:.3f} — "
                  f"attempts diverge meaningfully.")
    if n_allfail:
        pct = 100 * n_allfail_with_differential / n_allfail
        if pct >= 50:
            print(f"  Q2: {pct:.1f}% of all-FAIL triples have differential failure.")
            print("       Worth adding soft-rank contrast (least-failing -> most-failing)")
            print("       at lambda_softrank ~ 0.3, recovering signal from a previously")
            print(f"       dead {n_allfail} specs.")
        else:
            print(f"  Q2: only {pct:.1f}% of all-FAIL triples have differential failure.")
            print("       Not worth the engineering complexity — skip soft-rank.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
