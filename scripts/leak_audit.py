"""Leak audit: detect training-vs-real-bug-corpus overlap.

For each verus_real record, check whether its impl_text or spec_text
appears (whitespace-normalized) anywhere in the training corpus.

Also computes:
  - Spec-text overlap (normalized hash)
  - Impl-text overlap (normalized hash)
  - Token-n-gram overlap (k=5, top-overlap %)
  - For each FAIL real-bug record, check if the FAILS-marked line
    appears verbatim in any training record (with or without // FAILS stripped)

Usage:
  uv run python scripts/leak_audit.py --config configs/default.yaml \
      --real artifacts/real_bugs/records.jsonl \
      --out artifacts/real_bugs/leak_audit.txt
"""
from __future__ import annotations
import argparse, hashlib, json, sys, re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from ebm_verus.data import load_all
from ebm_verus.data.line_policy import is_scorable_line


def _norm(s: str) -> str:
    return "".join(s.split())

def _hash(s: str) -> str:
    return hashlib.sha1(_norm(s).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _strip_comments(line: str) -> str:
    # Remove trailing line comments to compare semantic content.
    if "//" in line:
        line = line.split("//", 1)[0]
    return line.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--real", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    print("loading training data ...", flush=True)
    train_examples = load_all(
        system_trajectory_path=cfg["data"]["system_trajectory_path"],
        sft_safe_path=cfg["data"]["sft_safe_path"],
        max_diff_lines=int(cfg["data"]["max_diff_lines"]),
        extra_trajectory_paths=cfg["data"].get("extra_trajectory_paths") or None,
        extra_sft_paths=cfg["data"].get("extra_sft_paths") or None,
    )
    print(f"  {len(train_examples)} training examples", flush=True)

    # Build training-side indices.
    train_spec_hashes: set[str] = set()
    train_impl_hashes: set[str] = set()
    train_lines: set[str] = set()
    train_lines_nocomment: set[str] = set()
    for ex in train_examples:
        train_spec_hashes.add(_hash(ex.spec_text))
        train_impl_hashes.add(_hash(ex.impl_text))
        for line in ex.impl_text.splitlines():
            if is_scorable_line(line):
                train_lines.add(line.strip())
                train_lines_nocomment.add(_strip_comments(line))

    print(f"  train: {len(train_spec_hashes)} unique-spec hashes, "
          f"{len(train_impl_hashes)} unique-impl hashes, "
          f"{len(train_lines)} unique scorable lines",
          flush=True)

    # Load real-bug records.
    real_records = []
    with args.real.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            real_records.append(json.loads(line))
    print(f"  {len(real_records)} real-bug records loaded", flush=True)

    # Run the audits.
    n = len(real_records)
    spec_overlap_count = 0
    impl_overlap_count = 0
    fail_with_marker = 0
    fails_line_overlap = 0
    fails_line_overlap_stripped = 0
    line_overlap_per_record: list[float] = []
    pure_buggy_line_overlap_stripped = 0
    pure_buggy_line_n = 0
    for r in real_records:
        spec_hash = _hash(r["spec_text"])
        impl_hash = _hash(r["impl_text"])
        if spec_hash in train_spec_hashes:
            spec_overlap_count += 1
        if impl_hash in train_impl_hashes:
            impl_overlap_count += 1
        # Per-line overlap fraction
        impl_lines = [l for l in r["impl_text"].splitlines() if is_scorable_line(l)]
        if not impl_lines:
            continue
        overlap_strict = sum(1 for l in impl_lines if l.strip() in train_lines)
        line_overlap_per_record.append(overlap_strict / len(impl_lines))
        # The FAILS-marked buggy line(s)
        if r["status"] == "FAIL" and r.get("buggy_lines"):
            fail_with_marker += 1
            all_lines = r["impl_text"].splitlines()
            for i in r["buggy_lines"]:
                if 0 <= i < len(all_lines):
                    bline = all_lines[i].strip()
                    bline_stripped = _strip_comments(all_lines[i])
                    pure_buggy_line_n += 1
                    if bline_stripped in train_lines_nocomment:
                        pure_buggy_line_overlap_stripped += 1
                    if bline in train_lines:
                        fails_line_overlap += 1
                    if bline_stripped in train_lines_nocomment:
                        fails_line_overlap_stripped += 1

    out_lines = []
    out_lines.append(f"LEAK AUDIT — train vs verus-real-bug corpus")
    out_lines.append(f"==========================================")
    out_lines.append(f"  Real records: {n}")
    out_lines.append(f"  Train examples: {len(train_examples)}")
    out_lines.append(f"")
    out_lines.append(f"  SPEC-text overlap (whitespace-normalized hash):")
    out_lines.append(f"    {spec_overlap_count}/{n}  ({100*spec_overlap_count/max(1,n):.1f}%)")
    out_lines.append(f"  IMPL-text overlap (whitespace-normalized hash):")
    out_lines.append(f"    {impl_overlap_count}/{n}  ({100*impl_overlap_count/max(1,n):.1f}%)")
    out_lines.append(f"")
    if line_overlap_per_record:
        avg_lo = sum(line_overlap_per_record) / len(line_overlap_per_record)
        n_50 = sum(1 for x in line_overlap_per_record if x >= 0.5)
        n_90 = sum(1 for x in line_overlap_per_record if x >= 0.9)
        out_lines.append(f"  PER-RECORD scorable-line overlap (line text exact match):")
        out_lines.append(f"    mean fraction overlap: {avg_lo:.3f}")
        out_lines.append(f"    records with >= 50% line overlap: {n_50}/{n}  ({100*n_50/max(1,n):.1f}%)")
        out_lines.append(f"    records with >= 90% line overlap: {n_90}/{n}  ({100*n_90/max(1,n):.1f}%)")
    out_lines.append(f"")
    out_lines.append(f"  FAILS-line label leakage:")
    out_lines.append(f"    real FAIL records with buggy_lines: {fail_with_marker}")
    out_lines.append(f"    total buggy-line label sites: {pure_buggy_line_n}")
    out_lines.append(f"    sites where buggy line exact-matches a train-line: "
                     f"{fails_line_overlap}  ({100*fails_line_overlap/max(1,pure_buggy_line_n):.1f}%)")
    out_lines.append(f"    sites where buggy line matches train-line (comments stripped): "
                     f"{fails_line_overlap_stripped}  ({100*fails_line_overlap_stripped/max(1,pure_buggy_line_n):.1f}%)")
    report = "\n".join(out_lines)
    print(report, flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report + "\n")
    print(f"\nwrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
