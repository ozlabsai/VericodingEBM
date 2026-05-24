"""Diff-from-sibling-PASS baseline (Renieris & Reiss ASE'03).

For each impl in records.jsonl, find sibling impls (same spec_id) that have
status=PASS. Score each line of the target impl by:

    energy(line) = 1 - max_{sibling PASS} char_jaccard(line, nearest line in sibling)

i.e., lines that are LEAST like any line in any PASS sibling rank highest.
Lines that appear verbatim in a PASS sibling score 0 (not suspicious).

When the target impl has NO PASS sibling, every line scores 0 (uninformative
fallback — the record is still emitted so the file is comparable, but
analyze_records.py will treat it as no-signal).

Output schema matches score_external_records.py.

Usage:
    uv run python scripts/baseline_diff_sibling.py \\
        --in artifacts/real_bugs/records.jsonl \\
        --out artifacts/baselines/diff_sibling_records.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from ebm_verus.data.line_policy import scorable_line_indices


def _normalize_line(s: str) -> str:
    s = s.strip()
    if "//" in s:
        s = s.split("//", 1)[0].rstrip()
    return s


def _char_jaccard(a: str, b: str) -> float:
    """Character-bigram Jaccard similarity. Cheap, robust to whitespace.

    1.0 = identical strings; 0.0 = no shared bigrams.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ag = {a[i:i + 2] for i in range(len(a) - 1)} or {a}
    bg = {b[i:i + 2] for i in range(len(b) - 1)} or {b}
    inter = len(ag & bg)
    union = len(ag | bg)
    return inter / union if union else 0.0


def _status_str(s) -> str:
    s = str(s).upper()
    if "." in s:
        s = s.split(".")[-1]
    if "PASS" in s or "OK" in s:
        return "PASS"
    if "FAIL" in s or "ERR" in s:
        return "FAIL"
    return "UNKNOWN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    raw = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    print(f"loaded {len(raw)} records from {args.in_path}", flush=True)

    by_spec: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        by_spec[r["spec_id"]].append(r)

    n_with_pass = 0
    n_without_pass = 0
    n_written = 0
    n_skipped = 0
    with args.out.open("w") as f_out:
        for r in raw:
            impl_text = r.get("impl_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            status = _status_str(r.get("status", ""))
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))

            all_lines = impl_text.splitlines()
            scorable = scorable_line_indices(impl_text)
            scorable_texts = [all_lines[i] for i in scorable]
            if not scorable_texts:
                n_skipped += 1
                continue

            # Collect PASS siblings' scorable lines (normalized).
            pass_sib_lines: list[str] = []
            for sib in by_spec[r["spec_id"]]:
                if sib.get("impl_id") == r.get("impl_id"):
                    continue
                if _status_str(sib.get("status", "")) != "PASS":
                    continue
                sib_text = sib.get("impl_text", "")
                sib_all = sib_text.splitlines()
                sib_scorable = scorable_line_indices(sib_text)
                for i in sib_scorable:
                    pass_sib_lines.append(_normalize_line(sib_all[i]))

            if pass_sib_lines:
                n_with_pass += 1
                sib_set = set(pass_sib_lines)
                # For each line in target, find best similarity to any sibling line.
                # Use exact-match fast path then fall back to bigram Jaccard.
                energies = []
                for ln in scorable_texts:
                    norm = _normalize_line(ln)
                    if not norm:
                        energies.append(0.0)
                        continue
                    if norm in sib_set:
                        energies.append(0.0)  # identical => not suspicious
                        continue
                    # Bigram Jaccard against each sibling line (cap search for speed).
                    best = 0.0
                    for sib_ln in pass_sib_lines:
                        if not sib_ln:
                            continue
                        s = _char_jaccard(norm, sib_ln)
                        if s > best:
                            best = s
                            if best >= 0.99:
                                break
                    energies.append(1.0 - best)
            else:
                n_without_pass += 1
                energies = [0.0] * len(scorable_texts)

            src_to_sent = {s: i for i, s in enumerate(scorable)}
            buggy_sent = sorted({
                src_to_sent[s] for s in buggy_source_lines
                if s in src_to_sent
            })

            whole = max(energies) if energies else 0.0
            f_out.write(json.dumps({
                "impl_id": r["impl_id"],
                "spec_id": r["spec_id"],
                "source": "baseline_diff_sibling",
                "status": status,
                "whole_impl_energy": whole,
                "per_line_energies": energies,
                "buggy_line_indices": buggy_sent,
                "scorable_line_texts": scorable_texts,
                # Diagnostic: did this record have a PASS sibling at all?
                "has_pass_sibling": bool(pass_sib_lines),
            }) + "\n")
            n_written += 1
            if n_written % 200 == 0:
                print(f"  {n_written}/{len(raw)} scored ({n_with_pass} w/ PASS sib)", flush=True)

    print(f"DONE: wrote {n_written}, skipped {n_skipped}", flush=True)
    print(f"  with PASS sibling: {n_with_pass}  (informative)", flush=True)
    print(f"  without:           {n_without_pass}  (energies all zero)", flush=True)
    print(f"  -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
