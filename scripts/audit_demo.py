"""Strip-FAILS audit demo: laptop-only, no GPU, no checkpoint, no API.

Takes two released eval-record files for the same model checkpoint --- one
scored with `// FAILS` markers intact (`no_surgery.jsonl`) and one scored on
the marker-stripped version of the corpus (`stripped.jsonl`) --- and reports
the top-k delta. A localizer that depends on the marker substring as a
shortcut will show a large positive delta (signal collapses when the marker
is removed); a leak-immune localizer sits near delta=0.

This is the 5-minute reproducibility demo for the paper's strip-FAILS audit
section. It needs only Python + numpy + (optional) scipy/sklearn.

Usage:
    python scripts/audit_demo.py \\
        --no-surgery artifacts/real_bugs/run7_step500/no_surgery.jsonl \\
        --stripped   artifacts/real_bugs/run7_step500/stripped.jsonl

    # Or for the post-fix run #10 (shows marker-aversion):
    python scripts/audit_demo.py \\
        --no-surgery artifacts/real_bugs/run10_no_surgery/eval_records.jsonl \\
        --stripped   artifacts/real_bugs/run10_stripped/eval_records.jsonl
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def _status(s):
    s = str(s).upper()
    if "." in s: s = s.split(".")[-1]
    if "FAIL" in s or "ERR" in s: return "FAIL"
    if "PASS" in s or "OK" in s: return "PASS"
    return "UNKNOWN"


def load(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            r["_status"] = _status(r.get("status", ""))
            out.append(r)
    return out


def topk_recall(records, k):
    """top-k recall over labeled FAIL impls."""
    fails = [r for r in records
             if r["_status"] == "FAIL" and r.get("buggy_line_indices")]
    if not fails:
        return None, 0
    hits = 0
    for r in fails:
        en = r.get("per_line_energies") or []
        if not en: continue
        ranked = sorted(range(len(en)), key=lambda i: -en[i])[:k]
        if any(t in set(r["buggy_line_indices"]) for t in ranked):
            hits += 1
    return hits / len(fails), len(fails)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-surgery", required=True, type=Path,
                    help="JSONL of eval records with markers intact.")
    ap.add_argument("--stripped", required=True, type=Path,
                    help="JSONL of eval records with markers stripped.")
    ap.add_argument("--output", type=Path,
                    help="(Optional) write the comparison as JSON.")
    args = ap.parse_args()

    if not args.no_surgery.exists():
        print(f"ERROR: not found: {args.no_surgery}", file=sys.stderr); return 2
    if not args.stripped.exists():
        print(f"ERROR: not found: {args.stripped}", file=sys.stderr); return 2

    ns = load(args.no_surgery)
    st = load(args.stripped)

    rows = []
    for k in (1, 3, 5):
        ns_v, n = topk_recall(ns, k)
        st_v, _ = topk_recall(st, k)
        delta = ns_v - st_v
        rows.append({"k": k, "with_markers": ns_v, "stripped": st_v,
                     "delta": delta, "n_fail": n})

    # Pretty print.
    print(f"=== Strip-FAILS audit ===")
    print(f"with markers: {args.no_surgery}")
    print(f"stripped:     {args.stripped}")
    print()
    print(f"  {'k':>3s}  {'with markers':>13s}  {'stripped':>10s}  {'delta':>8s}  {'n_FAIL':>7s}")
    print(f"  {'-'*3}  {'-'*13}  {'-'*10}  {'-'*8}  {'-'*7}")
    for row in rows:
        sign = "+" if row["delta"] >= 0 else ""
        print(f"  {row['k']:>3d}  {row['with_markers']:>13.3f}  {row['stripped']:>10.3f}  "
              f"{sign}{row['delta']:>7.3f}  {row['n_fail']:>7d}")
    print()
    # Interpretation.
    d1 = rows[0]["delta"]
    if abs(d1) <= 0.05:
        verdict = "marker-INVARIANT (delta-top-1 within +/-5pp)"
    elif d1 > 0:
        verdict = "marker-RELIANT (signal drops when marker removed)"
    else:
        verdict = "marker-AVERSE (signal IMPROVES when marker removed)"
    print(f"  Verdict: {verdict}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({
            "no_surgery_records": str(args.no_surgery),
            "stripped_records": str(args.stripped),
            "rows": rows,
            "verdict": verdict,
        }, indent=2))
        print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
