"""Audit the 15.7GB sft_part1_6.9M.json without loading it into memory.

Streams the JSON array with ijson. Sample first --n-rows (default 50000) rows,
report:
  - schema (keys present)
  - status / rewrite_reason value distribution
  - fraction that has a parseable rust block in input AND an error message
    (the prerequisites for being a usable debugging pair)
  - estimated diff size distribution by running our parser logic on a sample
  - extrapolation to estimate total usable debugging pairs in the 6.9M file

Usage:
    .venv/bin/python scripts/audit_sft_part1.py --path data/raw/sft_part1_6.9M.json --n-rows 50000

Run remotely on the RunPod box during training, or locally if we choose to
download the file. Doesn't write artifacts; just prints summary.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import time
from collections import Counter
from pathlib import Path

import ijson

_RUST_BLOCK_RE = re.compile(r"```rust\s*\n(.*?)```", re.DOTALL)
_ERROR_BLOCK_RE = re.compile(
    r"The error messages are[^\n]*\n+\s*```(?:rust)?\s*\n(.*?)```", re.DOTALL
)


def _extract_rust(text: str) -> str | None:
    m = _RUST_BLOCK_RE.search(text or "")
    return m.group(1).rstrip() if m else None


def _has_error_block(text: str) -> bool:
    return bool(_ERROR_BLOCK_RE.search(text or ""))


def _line_diff_size(a: str, b: str) -> int:
    la = a.splitlines()
    lb = b.splitlines()
    sm = difflib.SequenceMatcher(a=la, b=lb, autojunk=False)
    return sum(
        (i2 - i1) for tag, i1, i2, _j1, _j2 in sm.get_opcodes()
        if tag in ("replace", "delete")
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--n-rows", type=int, default=50_000,
                   help="how many rows to sample from the start of the file")
    p.add_argument("--diff-sample", type=int, default=500,
                   help="of debugging-candidate rows, how many to actually diff "
                        "(expensive)")
    args = p.parse_args()

    if not args.path.exists():
        print(f"ERROR: {args.path} does not exist", file=sys.stderr)
        return 2

    size_mb = args.path.stat().st_size / 1_000_000
    print("=" * 72)
    print(f"audit: {args.path}")
    print(f"  size: {size_mb:.1f} MB")
    print(f"  sampling first {args.n_rows} rows ...")
    print("=" * 72)

    t0 = time.time()
    schema_keys: Counter = Counter()
    status_field: Counter = Counter()
    rewrite_reasons: Counter = Counter()
    n_with_rust = 0
    n_with_error = 0
    n_debugging_candidate = 0
    diff_sizes: list[int] = []

    n_diffed = 0
    n_seen = 0

    with args.path.open("rb") as f:
        items = ijson.items(f, "item")
        for row in items:
            n_seen += 1
            if n_seen > args.n_rows:
                break

            # schema (first 100 rows only — cheap)
            if n_seen <= 100:
                for k in row.keys():
                    schema_keys[k] += 1

            input_text = row.get("input") or ""
            output_text = row.get("output") or ""

            rr = row.get("rewrite_reason")
            if rr is not None:
                rewrite_reasons[str(rr)[:80]] += 1

            st = row.get("status")
            if st is not None:
                status_field[str(st)[:40]] += 1

            broken = _extract_rust(input_text)
            has_err = _has_error_block(input_text)
            fixed = _extract_rust(output_text) or output_text.strip()

            if broken:
                n_with_rust += 1
            if has_err:
                n_with_error += 1

            # A "debugging candidate" needs: broken rust block + error message +
            # a fixed-side block. Same prereqs as our sft_safe parser.
            if broken and has_err and fixed and n_debugging_candidate < args.n_rows:
                n_debugging_candidate += 1

                if n_diffed < args.diff_sample:
                    try:
                        from ebm_verus.data.line_policy import split_spec_impl
                        _, b_impl = split_spec_impl(broken)
                        _, f_impl = split_spec_impl(fixed)
                        if b_impl.strip() and f_impl.strip():
                            d = _line_diff_size(b_impl, f_impl)
                            diff_sizes.append(d)
                            n_diffed += 1
                    except Exception:
                        pass

            if n_seen % 5000 == 0:
                dt = time.time() - t0
                rate = n_seen / max(dt, 0.001)
                print(f"  ... {n_seen:>7d}/{args.n_rows} rows in {dt:.1f}s "
                      f"({rate:.0f} rows/s)", flush=True)

    dt = time.time() - t0
    print()
    print("=" * 72)
    print(f"scanned {n_seen} rows in {dt:.1f}s ({n_seen/max(dt,0.001):.0f} rows/s)")
    print("=" * 72)

    print()
    print("schema (keys observed in first 100 rows):")
    for k, c in schema_keys.most_common():
        print(f"  {k:30s} present in {c}/100")

    print()
    print(f"input field has rust block:        {n_with_rust}/{n_seen} ({100*n_with_rust/n_seen:.1f}%)")
    print(f"input field has error block:       {n_with_error}/{n_seen} ({100*n_with_error/n_seen:.1f}%)")
    print(f"debugging-candidate (both + fixed):{n_debugging_candidate}/{n_seen} "
          f"({100*n_debugging_candidate/n_seen:.1f}%)")

    if rewrite_reasons:
        print()
        print("rewrite_reason values (sample):")
        for v, c in rewrite_reasons.most_common(10):
            print(f"  {v!r:40s}  {c}")

    if status_field:
        print()
        print("status field values:")
        for v, c in status_field.most_common(10):
            print(f"  {v!r:30s}  {c}")

    if diff_sizes:
        diff_sizes.sort()
        n = len(diff_sizes)
        le3 = sum(1 for d in diff_sizes if 1 <= d <= 3)
        print()
        print(f"line-diff size (sample of {n} debugging candidates):")
        print(f"  p25={diff_sizes[n//4]} p50={diff_sizes[n//2]} "
              f"p75={diff_sizes[3*n//4]} p99={diff_sizes[int(0.99*n)]}")
        print(f"  diffs in [1, 3] (useful for L_line): {le3}/{n} ({100*le3/n:.1f}%)")
        usable_frac = (n_debugging_candidate / n_seen) * (le3 / n)
        # Extrapolate: total file is ~6.9M rows
        est_usable = int(6_900_000 * usable_frac)
        print()
        print(f"extrapolation:")
        print(f"  usable debugging-pair fraction (debug_cand × diff_ok): "
              f"{100*usable_frac:.2f}%")
        print(f"  estimated usable pairs in full 6.9M file: ~{est_usable:,}")
        print(f"  compare to sft_safe_25k: ~9,894 pairs")
        if est_usable > 100_000:
            print(f"  -> ~{est_usable/9894:.1f}x more L_line data than sft_safe_25k.")

    print()
    print("=" * 72)
    print("decision rule:")
    if diff_sizes and (le3 / len(diff_sizes)) > 0.5 and n_debugging_candidate / n_seen > 0.05:
        print("  WORTHWHILE — schema matches, usable fraction is non-trivial.")
        print("  Saturday upgrade plan: download, parse with same sft_safe parser,")
        print("  add to data/raw/, expect ~10-80x more L_line training data.")
    else:
        print("  MARGINAL — schema/fractions don't strongly support a scale-up.")
        print("  Stick with sft_safe_25k for L_line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
