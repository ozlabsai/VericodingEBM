"""Trivial baselines (length / keyword / random) on the real-bug corpus.

Writes records in the same schema as score_external_records.py so
analyze_records.py consumes them without modification. Output goes to
artifacts/baselines/{length,keyword,random}_records.jsonl.

Usage:
    uv run python scripts/baseline_trivial.py \
        --in artifacts/real_bugs/records.jsonl \
        --out-dir artifacts/baselines/

Baselines:
  - length: per-line energy = token-ish length of the line (longer = more suspicious)
  - keyword: per-line energy = count of bug-correlated keywords on the line.
    Two flavors are written:
      * keyword_verus: assert/ensures/invariant/requires/decreases/forall/exists/assume
      * keyword_marker: panic!/unwrap/unsafe/// FAILS/TODO/FIXME
  - random: per-line energy = uniform[0,1) for each line. Run with N seeds
    and average top-k/AUROC across seeds; emit one merged record file with
    the seed=0 draw plus a summary stats block.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from ebm_verus.data.line_policy import scorable_line_indices

VERUS_KEYWORDS = [
    "assert", "ensures", "invariant", "decreases", "requires",
    "forall", "exists", "assume", "recommends",
]
# Bug-correlated *Rust/Verus authorial* markers — distinct from the // FAILS
# pretraining-prior leak we already audited. Including // FAILS here lets us
# quantify exactly how much of the model's signal a 30-line regex could match.
MARKER_KEYWORDS = [
    "panic!", "unwrap", "unsafe", "// FAILS", "// TODO", "// FIXME",
    "assert!", "todo!", "unimplemented!",
]


def _length_score(line: str) -> float:
    # Simple token-ish proxy: split on whitespace + punctuation count.
    return float(len(line.strip()))


def _keyword_score(line: str, vocab: list[str]) -> float:
    s = 0
    for kw in vocab:
        if kw in line:
            s += 1
    # Tie-break by length so lines with no keywords don't all tie at 0.
    return float(s) + 1e-4 * len(line.strip())


def _status_from_str(s: str) -> str:
    s = str(s).upper()
    if "." in s:
        s = s.split(".")[-1]
    if s.endswith("PASS") or s.endswith("OK"):
        return "PASS"
    if s.endswith("FAIL") or s.endswith("ERR"):
        return "FAIL"
    return "UNKNOWN"


def _emit_record(out_f, r: dict, energies: list[float], scorable_texts: list[str],
                 buggy_sentinel: list[int], status: str, source_tag: str) -> None:
    whole = max(energies) if energies else 0.0
    out_f.write(json.dumps({
        "impl_id": r["impl_id"],
        "spec_id": r["spec_id"],
        "source": source_tag,
        "status": status,
        "whole_impl_energy": whole,
        "per_line_energies": energies,
        "buggy_line_indices": buggy_sentinel,
        "scorable_line_texts": scorable_texts,
    }) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--random-seed", type=int, default=0)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    print(f"loaded {len(raw)} records from {args.in_path}", flush=True)

    rng = random.Random(args.random_seed)

    out_files = {
        "length": (args.out_dir / "length_records.jsonl").open("w"),
        "keyword_verus": (args.out_dir / "keyword_verus_records.jsonl").open("w"),
        "keyword_marker": (args.out_dir / "keyword_marker_records.jsonl").open("w"),
        "random": (args.out_dir / "random_records.jsonl").open("w"),
    }

    n_written = 0
    n_skipped = 0
    try:
        for r in raw:
            impl_text = r.get("impl_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            status = _status_from_str(r.get("status", ""))
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))

            all_lines = impl_text.splitlines()
            scorable = scorable_line_indices(impl_text)
            scorable_texts = [all_lines[i] for i in scorable]
            if not scorable_texts:
                n_skipped += 1
                continue

            src_to_sentinel = {src: i for i, src in enumerate(scorable)}
            buggy_sentinel = sorted({
                src_to_sentinel[s]
                for s in buggy_source_lines
                if s in src_to_sentinel
            })

            length_e = [_length_score(t) for t in scorable_texts]
            kv_e = [_keyword_score(t, VERUS_KEYWORDS) for t in scorable_texts]
            km_e = [_keyword_score(t, MARKER_KEYWORDS) for t in scorable_texts]
            rand_e = [rng.random() for _ in scorable_texts]

            _emit_record(out_files["length"], r, length_e, scorable_texts,
                         buggy_sentinel, status, "baseline_length")
            _emit_record(out_files["keyword_verus"], r, kv_e, scorable_texts,
                         buggy_sentinel, status, "baseline_keyword_verus")
            _emit_record(out_files["keyword_marker"], r, km_e, scorable_texts,
                         buggy_sentinel, status, "baseline_keyword_marker")
            _emit_record(out_files["random"], r, rand_e, scorable_texts,
                         buggy_sentinel, status, "baseline_random")
            n_written += 1
    finally:
        for f in out_files.values():
            f.close()

    print(f"wrote {n_written} records (skipped {n_skipped}) to {args.out_dir}/", flush=True)
    print(f"  length_records.jsonl")
    print(f"  keyword_verus_records.jsonl")
    print(f"  keyword_marker_records.jsonl")
    print(f"  random_records.jsonl  (seed={args.random_seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
