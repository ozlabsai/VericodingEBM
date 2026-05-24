"""Smoke-test the data pipeline on real data files.

Usage:
    uv run python scripts/smoke_test_data.py \
        --system-traj data/raw/system_trajectory_843.jsonl \
        --sft-safe    data/raw/sft_safe_25k.json

Prints:
  - parsed example counts (per source, per status)
  - mixed-label spec stats (the load-bearing property for L_spec)
  - impl line-count distribution (catches parser regressions where impls come
    out empty or pathologically long)
  - tokenized length distribution (catches max_length truncation issues)
  - spec-level split + disjointness assertion on REAL data
  - one decoded example per (source, status) combination for eyeball inspection

CPU-only. Should complete in <2 minutes on the local laptop.

If this script crashes or prints suspicious numbers, do NOT start GPU training.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from transformers import AutoTokenizer

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data import (
    Source,
    Status,
    load_all,
    split_examples,
    tokenize_example,
)


def _human(n: int) -> str:
    for unit, div in [("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)]:
        if n >= div:
            return f"{n / div:.1f}{unit}"
    return str(n)


def _percentiles(xs: list[int], ps: list[int]) -> dict[int, float]:
    if not xs:
        return {p: float("nan") for p in ps}
    xs = sorted(xs)
    out = {}
    for p in ps:
        k = max(0, min(len(xs) - 1, int(p / 100 * (len(xs) - 1))))
        out[p] = xs[k]
    return out


def _stat_block(xs: list[int], label: str) -> str:
    if not xs:
        return f"  {label}: (empty)"
    pcts = _percentiles(xs, [50, 90, 95, 99, 100])
    return (
        f"  {label}: n={len(xs)} "
        f"mean={statistics.mean(xs):.1f} "
        f"min={min(xs)} "
        f"p50={pcts[50]:.0f} p90={pcts[90]:.0f} "
        f"p95={pcts[95]:.0f} p99={pcts[99]:.0f} "
        f"max={pcts[100]:.0f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system-traj", type=Path, required=True)
    parser.add_argument("--sft-safe", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--show-decoded", action="store_true",
                        help="Print one decoded example per (source, status) — for eyeball QC")
    parser.add_argument("--tokenize-sample", type=int, default=200,
                        help="Tokenize this many random examples to measure length distribution")
    args = parser.parse_args()

    # ---- file existence ----------------------------------------------------
    for p in (args.system_traj, args.sft_safe):
        if not p.exists():
            print(f"  !! missing data file: {p}", file=sys.stderr)
            print("     drop the file in place (or re-pull from HF) and re-run.",
                  file=sys.stderr)
            return 2

    # ---- config + tokenizer ------------------------------------------------
    with args.config.open() as f:
        cfg = yaml.safe_load(f)
    max_length = int(cfg["data"]["max_seq_len"])
    backbone = cfg["model"]["backbone"]
    max_diff_lines = int(cfg["data"]["max_diff_lines"])

    print("=" * 72)
    print(f"smoke-test: data pipeline on real files")
    print("=" * 72)
    print(f"  system_trajectory: {args.system_traj}")
    print(f"  sft_safe:          {args.sft_safe}")
    print(f"  config:            {args.config}")
    print(f"  max_length:        {max_length}")
    print(f"  max_diff_lines:    {max_diff_lines}")
    print(f"  backbone:          {backbone}")
    print()

    # ---- load --------------------------------------------------------------
    print("[1/5] parsing both datasets ...")
    examples = load_all(
        system_trajectory_path=args.system_traj,
        sft_safe_path=args.sft_safe,
        max_diff_lines=max_diff_lines,
    )
    print(f"  parsed {_human(len(examples))} examples total")

    # ---- per-source / per-status breakdown --------------------------------
    print()
    print("[2/5] per-source + per-status breakdown ...")
    by_source: dict[Source, Counter] = defaultdict(Counter)
    impl_lines: dict[Source, list[int]] = defaultdict(list)
    buggy_counts: list[int] = []
    for ex in examples:
        by_source[ex.source][ex.status] += 1
        impl_lines[ex.source].append(len(ex.impl_text.splitlines()))
        if ex.buggy_lines:
            buggy_counts.append(len(ex.buggy_lines))

    for source, counts in by_source.items():
        total = sum(counts.values())
        breakdown = " ".join(f"{s.value}={n}" for s, n in counts.items())
        print(f"  {source.value:20s} n={total:>6d}  {breakdown}")
    print()
    print("  impl line-count distribution per source:")
    for source, xs in impl_lines.items():
        print(_stat_block(xs, f"    {source.value}"))
    if buggy_counts:
        print()
        print("  buggy_lines size (per FAIL example with non-empty labels):")
        print(_stat_block(buggy_counts, "    buggy_lines"))

    # ---- mixed-label spec stats (load-bearing for L_spec) ------------------
    print()
    print("[3/5] mixed-label spec stats (load-bearing for L_spec) ...")
    by_spec_traj: dict[str, list[Status]] = defaultdict(list)
    for ex in examples:
        if ex.source == Source.SYSTEM_TRAJECTORY:
            by_spec_traj[ex.spec_id].append(ex.status)
    n_specs = len(by_spec_traj)
    n_mixed = sum(
        1 for sts in by_spec_traj.values()
        if Status.PASS in sts and Status.FAIL in sts
    )
    n_allpass = sum(1 for sts in by_spec_traj.values() if all(s == Status.PASS for s in sts))
    n_allfail = sum(1 for sts in by_spec_traj.values() if all(s == Status.FAIL for s in sts))
    print(f"  system_trajectory specs: {n_specs}")
    print(f"    mixed (≥1 PASS + ≥1 FAIL): {n_mixed} ({100*n_mixed/max(1,n_specs):.1f}%)")
    print(f"    all-pass:                   {n_allpass}")
    print(f"    all-fail:                   {n_allfail}")
    if n_mixed == 0:
        print("  !! ZERO mixed-label specs — L_spec will get NO gradient. Aborting.")
        return 3

    safe_pairs = sum(1 for ex in examples
                     if ex.source == Source.SFT_SAFE and ex.status == Status.FAIL)
    print(f"  sft_safe broken impls (L_line source): {safe_pairs}")

    # ---- tokenized length distribution ------------------------------------
    print()
    print(f"[4/5] tokenizing a sample of {args.tokenize_sample} examples ...")
    tokenizer = AutoTokenizer.from_pretrained(backbone)
    sentinel_id = tokenizer.encode(SENTINEL_TOKEN, add_special_tokens=False)
    assert len(sentinel_id) == 1, f"sentinel must be single token; got {sentinel_id}"
    print(f"  sentinel {SENTINEL_TOKEN!r} -> id {sentinel_id[0]}")

    import random
    rng = random.Random(0)
    sample = rng.sample(examples, k=min(args.tokenize_sample, len(examples)))
    tok_lens: list[int] = []
    n_sentinel: list[int] = []
    n_dropped = 0
    drop_reasons: Counter = Counter()
    for ex in sample:
        out = tokenize_example(ex, tokenizer, max_length=max_length)
        if out is None:
            n_dropped += 1
            # Re-run with a much larger cap to see why
            big = tokenize_example(ex, tokenizer, max_length=10**9)
            if big is None:
                drop_reasons["no_scorable_lines_or_sentinel_mismatch"] += 1
            elif len(big.input_ids) > max_length:
                drop_reasons["over_max_length"] += 1
            else:
                drop_reasons["unknown"] += 1
            continue
        tok_lens.append(len(out.input_ids))
        n_sentinel.append(len(out.sentinel_positions))

    print(f"  sampled: {len(sample)}, tokenized OK: {len(tok_lens)}, dropped: {n_dropped}")
    if n_dropped:
        for r, c in drop_reasons.most_common():
            print(f"    dropped ({r}): {c}")
    print(_stat_block(tok_lens, "    total input length (tokens)"))
    print(_stat_block(n_sentinel, "    sentinel count (= scorable lines)"))

    over_4k = sum(1 for x in tok_lens if x > 4096)
    if tok_lens:
        print(f"  > {over_4k}/{len(tok_lens)} examples would exceed 4k context "
              f"({100 * over_4k / len(tok_lens):.1f}%)")

    # ---- split + disjointness ---------------------------------------------
    print()
    print("[5/5] running spec-level split on real data ...")
    train, held = split_examples(
        examples,
        n_eval_traj_specs=int(cfg["data"]["split"]["n_eval_specs"]),
        sft_eval_frac=float(cfg["data"]["split"]["sft_eval_frac"]),
        seed=int(cfg["data"]["split"]["seed"]),
    )
    train_specs = {e.spec_id for e in train}
    held_specs = {e.spec_id for e in held}
    overlap = train_specs & held_specs
    print(f"  train: {len(train)} examples across {len(train_specs)} specs")
    print(f"  held:  {len(held)} examples across {len(held_specs)} specs")
    print(f"  overlap (must be 0): {len(overlap)}")
    if overlap:
        print("  !! train/eval spec overlap — split is broken")
        return 4

    # split breakdown by source
    train_by_src = Counter(e.source.value for e in train)
    held_by_src = Counter(e.source.value for e in held)
    print(f"  train per source: {dict(train_by_src)}")
    print(f"  held  per source: {dict(held_by_src)}")

    # mixed-label spec counts in train vs held
    def _mixed_in(exs):
        d = defaultdict(list)
        for e in exs:
            if e.source == Source.SYSTEM_TRAJECTORY:
                d[e.spec_id].append(e.status)
        return sum(1 for s in d.values() if Status.PASS in s and Status.FAIL in s)
    print(f"  mixed-label traj specs in train: {_mixed_in(train)}")
    print(f"  mixed-label traj specs in held:  {_mixed_in(held)}")

    # ---- optional decoded eyeball check -----------------------------------
    if args.show_decoded:
        print()
        print("[bonus] one decoded example per (source, status) ...")
        seen: set[tuple[str, str]] = set()
        for ex in examples:
            key = (ex.source.value, ex.status.value)
            if key in seen:
                continue
            seen.add(key)
            print()
            print(f"  ---- {key} ----")
            print(f"  spec_id: {ex.spec_id}  impl_id: {ex.impl_id}")
            print(f"  buggy_lines: {sorted(ex.buggy_lines) if ex.buggy_lines else '(none)'}")
            print("  spec_text[:300]:")
            print(_indent(ex.spec_text[:300], "    "))
            print("  impl_text[:300]:")
            print(_indent(ex.impl_text[:300], "    "))

    print()
    print("=" * 72)
    print("smoke-test PASSED — data pipeline ready for GPU training")
    print("=" * 72)
    return 0


def _indent(s: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in s.splitlines())


if __name__ == "__main__":
    sys.exit(main())
