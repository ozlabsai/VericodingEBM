"""A1: Ochiai SBFL baseline over sibling sets.

For each (spec, sibling-set) group on the held set:
  - 'Failing runs' = FAIL siblings of this spec
  - 'Passing runs' = PASS siblings of this spec
  - For each candidate line L in the *target FAIL impl*:
      ef = #FAIL siblings whose impl contains L (normalized line)
      ep = #PASS siblings whose impl contains L
      nf = #FAIL siblings whose impl does NOT contain L
      Ochiai(L) = ef / sqrt((ef + nf) * (ef + ep))   (0 if denom = 0)
  - Per-line energy = Ochiai(L)
  - top-k recall computed against buggy_line_indices the same way as ours.

Reads the *same held set* the model was evaluated on (uses split_examples
with the same seed). Emits the same JSONL shape so analyze_records.py
consumes it.

Lines are normalized: stripped of leading/trailing whitespace, comments
removed, blank lines dropped (matches scorable_line_indices semantics).

Output: artifacts/baseline_ochiai_records.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from ebm_verus.data import load_all, split_examples
from ebm_verus.data.line_policy import is_scorable_line, scorable_line_indices
from ebm_verus.data.types import Status


def _normalize_line(s: str) -> str:
    # Strip whitespace, drop trailing line comments (// ...).
    s = s.strip()
    if "//" in s:
        s = s.split("//", 1)[0].rstrip()
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    examples = load_all(
        system_trajectory_path=cfg["data"]["system_trajectory_path"],
        sft_safe_path=cfg["data"]["sft_safe_path"],
        max_diff_lines=int(cfg["data"]["max_diff_lines"]),
        extra_trajectory_paths=cfg["data"].get("extra_trajectory_paths") or None,
        extra_sft_paths=cfg["data"].get("extra_sft_paths") or None,
    )
    _train_ex, held_ex = split_examples(
        examples,
        n_eval_traj_specs=int(cfg["data"]["split"]["n_eval_specs"]),
        sft_eval_frac=float(cfg["data"]["split"]["sft_eval_frac"]),
        seed=int(cfg["data"]["split"]["seed"]),
    )
    print(f"held={len(held_ex)}", flush=True)

    # Group by spec_id so siblings are co-located.
    by_spec: dict[str, list] = defaultdict(list)
    for ex in held_ex:
        by_spec[ex.spec_id].append(ex)

    n_have_siblings = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for ex in held_ex:
            siblings = by_spec[ex.spec_id]
            pass_sibs = [s for s in siblings if s.status == Status.PASS and s.impl_id != ex.impl_id]
            fail_sibs = [s for s in siblings if s.status == Status.FAIL and s.impl_id != ex.impl_id]
            # Need at least one sibling on the FAIL side to have any Ochiai signal.
            # PASS side optional; without it Ochiai degenerates to "line present in any
            # FAIL sibling" which is still a defensible structural baseline.
            if not (pass_sibs or fail_sibs):
                # No sibling info — emit zeros so top-k recall is just random.
                # Don't skip: we want the same impl set as our model for fair n.
                pass

            # Build scorable line texts in sentinel order.
            all_lines = ex.impl_text.splitlines()
            scorable = scorable_line_indices(ex.impl_text)
            scorable_texts = [all_lines[i] for i in scorable]
            n_lines = len(scorable_texts)

            # Tally per-normalized-line presence across siblings.
            fail_presence: dict[str, int] = defaultdict(int)
            pass_presence: dict[str, int] = defaultdict(int)
            for s in fail_sibs:
                seen = set()
                for li in s.impl_text.splitlines():
                    if is_scorable_line(li):
                        seen.add(_normalize_line(li))
                for k in seen:
                    fail_presence[k] += 1
            for s in pass_sibs:
                seen = set()
                for li in s.impl_text.splitlines():
                    if is_scorable_line(li):
                        seen.add(_normalize_line(li))
                for k in seen:
                    pass_presence[k] += 1

            n_fail = len(fail_sibs)
            n_pass = len(pass_sibs)
            if n_fail > 0 or n_pass > 0:
                n_have_siblings += 1

            energies: list[float] = []
            for ln in scorable_texts:
                key = _normalize_line(ln)
                ef = fail_presence.get(key, 0)
                ep = pass_presence.get(key, 0)
                nf = n_fail - ef
                # Self-line: this impl always "contains" its own line; add +1
                # if this impl is in the FAIL side of the spectrum.
                if ex.status == Status.FAIL:
                    ef += 1
                    nf = max(0, nf)  # unchanged
                denom = math.sqrt((ef + nf) * (ef + ep)) if (ef + nf) and (ef + ep) else 0.0
                ochiai = (ef / denom) if denom > 0 else 0.0
                # Energy = Ochiai (high = suspicious). Buggy lines should rank high.
                energies.append(float(ochiai))

            # Buggy line indices: same mapping as the model (sentinel-space).
            # Reconstruct from ex.buggy_lines (source-line space) via scorable list.
            source_to_sentinel = {src: i for i, src in enumerate(scorable)}
            buggy_sentinel = sorted({source_to_sentinel[b] for b in ex.buggy_lines if b in source_to_sentinel})

            whole = max(energies) if energies else 0.0
            f.write(json.dumps({
                "impl_id": ex.impl_id,
                "spec_id": ex.spec_id,
                "source": ex.source.value,
                "status": ex.status.value,
                "whole_impl_energy": whole,
                "per_line_energies": energies,
                "buggy_line_indices": buggy_sentinel,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
    print(f"wrote {len(held_ex)} records ({n_have_siblings} had >=1 sibling) -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
