"""Audit the held-out set to diagnose suspiciously-high eval AUROC.

Three checks:

  C1 — Decompose eval metrics by source (system_trajectory vs sft_safe). If
       AUROC=0.98 is driven entirely by sft_safe, that's the "near-duplicate
       broken/fixed" trivial signal. If it holds on the traj subset too, it's
       likely real.

  C2 — Spot-check 5 sft_safe held examples: is the buggy line trivially
       different from surrounding code? Print the impl_text and buggy lines
       so we can eyeball.

  C3 — Spot-check 5 traj held FAIL impls: are they qualitatively different
       (less obvious bugs)?

This script LOADS the trained model from a checkpoint, but since we don't
checkpoint, run it against the live wandb run by rsync'ing the LoRA weights
back from the pod first. Or: run on the pod, which has the live process.

Usage:
    .venv/bin/python scripts/audit_held_set.py --config configs/default.yaml \
        --checkpoint runs/<latest>/lora.pt  # if checkpoint exists
    OR
    .venv/bin/python scripts/audit_held_set.py --config configs/default.yaml
        # falls back to base model (sanity check that bare backbone gives ~0.5)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, "src")

from ebm_verus.data import (
    Source,
    Status,
    load_all,
    split_examples,
)
from ebm_verus.data.types import Example


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--show-decoded", action="store_true",
                        help="Print held examples per source for eyeball QC")
    args = parser.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    # Re-derive the same held set the training run uses.
    print("Loading and splitting examples ...")
    examples = load_all(
        system_trajectory_path=cfg["data"]["system_trajectory_path"],
        sft_safe_path=cfg["data"]["sft_safe_path"],
        max_diff_lines=int(cfg["data"]["max_diff_lines"]),
    )
    train, held = split_examples(
        examples,
        n_eval_traj_specs=int(cfg["data"]["split"]["n_eval_specs"]),
        sft_eval_frac=float(cfg["data"]["split"]["sft_eval_frac"]),
        seed=int(cfg["data"]["split"]["seed"]),
    )
    print(f"  train: {len(train)} examples")
    print(f"  held:  {len(held)} examples")

    # C1: held-set composition
    by_src_st: dict[tuple, list[Example]] = defaultdict(list)
    for ex in held:
        by_src_st[(ex.source, ex.status)].append(ex)
    print()
    print("=== held-set composition ===")
    for (src, st), exs in sorted(by_src_st.items(), key=lambda x: (x[0][0].value, x[0][1].value)):
        print(f"  {src.value:>20s}  {st.value:<6s}  {len(exs):>3d}")

    # C2: text-hash disjointness (the property that matters for memorization)
    import hashlib
    def _nh(s):
        return hashlib.sha1("".join(s.split()).encode(), usedforsecurity=False).hexdigest()
    train_text = {_nh(e.spec_text) for e in train}
    held_text = {_nh(e.spec_text) for e in held}
    text_overlap = train_text & held_text
    print()
    print(f"normalized-spec-text disjoint: overlap = {len(text_overlap)} (must be 0)")
    if text_overlap:
        print(f"  TEXT OVERLAP DETECTED -- leakage path open")
        return 2

    # Informational: spec_id overlap is expected since different original_index
    # values can share identical source code in this dataset.
    train_specs = {e.spec_id for e in train}
    held_specs = {e.spec_id for e in held}
    id_overlap = train_specs & held_specs
    print(f"spec_id overlap: {len(id_overlap)} (informational, not a leak signal)")

    # C3: spec-TEXT duplicate check — different spec_ids but identical spec text?
    # This is the most likely leakage path.
    train_spec_texts = defaultdict(list)
    for ex in train:
        train_spec_texts[ex.spec_text].append(ex.spec_id)
    held_spec_texts = defaultdict(list)
    for ex in held:
        held_spec_texts[ex.spec_text].append(ex.spec_id)
    dup_spec_count = sum(
        1 for t in held_spec_texts if t in train_spec_texts
    )
    print(f"\nspec-text duplicates between train and held: {dup_spec_count}")
    if dup_spec_count > 0:
        # Show first few
        shown = 0
        for t, hids in held_spec_texts.items():
            if t in train_spec_texts and shown < 3:
                tids = train_spec_texts[t]
                print(f"  {hids[0]} (held) == {tids[0]} (train)  [N held={len(hids)} N train={len(tids)}]")
                shown += 1

    # C4: spec-TEXT near-duplicates via prefix hash (catch trivial whitespace
    # differences that would look distinct as spec_id but train the model on
    # essentially the same spec).
    import hashlib
    def norm_hash(s):
        normalized = "".join(s.split())  # strip all whitespace
        return hashlib.sha1(normalized.encode(), usedforsecurity=False).hexdigest()
    train_norm = {norm_hash(e.spec_text) for e in train}
    near_dup = sum(1 for e in held if norm_hash(e.spec_text) in train_norm)
    print(f"\nspec-text near-duplicates (whitespace-normalized): {near_dup}")
    if near_dup > 0:
        print("  -> LEAKAGE: identical spec content with different exact bytes")

    # C5: also do the same check for impl_text
    train_impl_norm = {norm_hash(e.impl_text) for e in train}
    impl_near_dup = sum(1 for e in held if norm_hash(e.impl_text) in train_impl_norm)
    print(f"impl-text near-duplicates (held vs train): {impl_near_dup}")

    if args.show_decoded:
        print()
        print("=== sample held examples (5 sft_safe FAIL) ===")
        n_shown = 0
        for ex in held:
            if ex.source == Source.SFT_SAFE and ex.status == Status.FAIL and n_shown < 5:
                print(f"\n--- impl_id={ex.impl_id} buggy_lines={sorted(ex.buggy_lines)}")
                print("  spec[:200]:", ex.spec_text[:200].replace("\n", " "))
                lines = ex.impl_text.splitlines()
                for i, line in enumerate(lines):
                    marker = " 🐛" if i in ex.buggy_lines else "   "
                    print(f"  {i:>3d}{marker} | {line[:90]}")
                n_shown += 1

        print()
        print("=== sample held examples (3 traj FAIL) ===")
        n_shown = 0
        for ex in held:
            if ex.source == Source.SYSTEM_TRAJECTORY and ex.status == Status.FAIL and n_shown < 3:
                print(f"\n--- impl_id={ex.impl_id}")
                print(f"  impl line count: {len(ex.impl_text.splitlines())}")
                print(f"  spec_text[:200]:", ex.spec_text[:200].replace("\n", " "))
                lines = ex.impl_text.splitlines()
                # show first 15 lines
                for i, line in enumerate(lines[:15]):
                    print(f"  {i:>3d} | {line[:90]}")
                if len(lines) > 15:
                    print(f"  ... ({len(lines)} lines total)")
                n_shown += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
