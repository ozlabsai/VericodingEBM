"""Deep leak audit: for FAIL records where we got top-1 RIGHT,
how often was the predicted line a verbatim train-line?

Compares two populations:
  POPULATION A: real-bug records where our model's top-1 hit the buggy line
  POPULATION B: real-bug records where our model's top-1 missed

For each, computes: (i) fraction of predicted-top-1 lines that appear
verbatim in training corpus, (ii) average n-gram overlap with nearest
training line.

If A's "in train" rate is significantly higher than B's, that's evidence
the model is winning by recognizing memorized-stereotype lines.
"""
from __future__ import annotations
import argparse, json, sys, math, hashlib
from pathlib import Path
import yaml

from ebm_verus.data import load_all
from ebm_verus.data.line_policy import is_scorable_line


def _strip_comments(line: str) -> str:
    if "//" in line:
        line = line.split("//", 1)[0]
    return line.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--records", required=True, type=Path,
                    help="model-scored real-bug eval records")
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
    train_lines: set[str] = set()
    for ex in train_examples:
        for line in ex.impl_text.splitlines():
            if is_scorable_line(line):
                train_lines.add(_strip_comments(line))

    # Load model-scored records
    real_records = []
    with args.records.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            real_records.append(json.loads(line))
    print(f"{len(real_records)} records loaded", flush=True)

    pop_top1_hit = []
    pop_top1_miss = []
    pop_top3_hit = []
    pop_top3_miss = []
    for r in real_records:
        status = str(r.get("status","")).upper().split(".")[-1]
        if status != "FAIL" or not r.get("buggy_line_indices"):
            continue
        es = r.get("per_line_energies") or []
        texts = r.get("scorable_line_texts") or []
        if not es or len(texts) != len(es):
            continue
        buggy = set(r["buggy_line_indices"])
        # top-1 predicted index
        order = sorted(range(len(es)), key=lambda i: -es[i])
        top1 = order[0]
        top3 = set(order[:min(3, len(order))])
        top1_text = _strip_comments(texts[top1])
        top1_in_train = top1_text in train_lines
        top1_hit = top1 in buggy
        top3_hit = bool(top3 & buggy)

        # Also: is the GROUND-TRUTH buggy line(s) in train?
        gt_lines = []
        for i in buggy:
            if 0 <= i < len(texts):
                gt_lines.append(_strip_comments(texts[i]))
        gt_in_train = any(line in train_lines for line in gt_lines)

        entry = {
            "top1_in_train": top1_in_train,
            "gt_in_train": gt_in_train,
            "top1_text": top1_text,
        }
        if top1_hit:
            pop_top1_hit.append(entry)
        else:
            pop_top1_miss.append(entry)
        if top3_hit:
            pop_top3_hit.append(entry)
        else:
            pop_top3_miss.append(entry)

    print(f"\n=== Top-1 analysis (n={len(pop_top1_hit)+len(pop_top1_miss)}) ===")
    for name, pop in [("HIT (top-1 correct)", pop_top1_hit),
                      ("MISS (top-1 wrong)",  pop_top1_miss)]:
        n = len(pop)
        if n == 0:
            print(f"  {name}: empty")
            continue
        in_train = sum(1 for p in pop if p["top1_in_train"])
        gt_in_train = sum(1 for p in pop if p["gt_in_train"])
        print(f"  {name}: n={n}")
        print(f"    pred-top1 line is in training: {in_train}/{n} ({100*in_train/n:.1f}%)")
        print(f"    ground-truth buggy line is in training: {gt_in_train}/{n} ({100*gt_in_train/n:.1f}%)")

    print(f"\n=== Top-3 analysis (n={len(pop_top3_hit)+len(pop_top3_miss)}) ===")
    for name, pop in [("HIT (top-3 caught)",   pop_top3_hit),
                      ("MISS (top-3 missed)",  pop_top3_miss)]:
        n = len(pop)
        if n == 0:
            print(f"  {name}: empty")
            continue
        gt_in_train = sum(1 for p in pop if p["gt_in_train"])
        print(f"  {name}: n={n}")
        print(f"    ground-truth buggy line is in training: {gt_in_train}/{n} ({100*gt_in_train/n:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
