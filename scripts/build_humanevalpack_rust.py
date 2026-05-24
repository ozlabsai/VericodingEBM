"""Convert HumanEvalPack-Rust into our (spec, impl, status, buggy_lines) format.

Output: artifacts/transfer/humanevalpack_rust/records.jsonl
  - 164 PASS records (canonical_solution)
  - 164 FAIL records (buggy_solution), with buggy_lines derived via difflib
    against the canonical solution.

The combined corpus (328 records, 50/50 split) is the OOD test set: same task
distribution, but model never saw any of these solutions and the code is
vanilla Rust (not Verus). If signal transfers, it's not Verus-syntax-bound.

Usage:
    uv run python scripts/build_humanevalpack_rust.py \\
        --out artifacts/transfer/humanevalpack_rust/records.jsonl
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

from datasets import load_dataset


def build_spec(r: dict) -> str:
    """Spec = declaration (signature + imports) + docstring as a comment block.
    This mirrors how the Verus model expects spec text: machine-checkable
    contract-ish thing the impl must satisfy. For HEP-Rust we substitute
    docstring + signature since there are no Verus contracts."""
    decl = (r.get("declaration") or "").rstrip()
    doc = (r.get("docstring") or "").strip()
    # Normalize doc as a Rust // comment block so the model sees commented text.
    if doc:
        doc_lines = [f"// {ln}" if ln else "//" for ln in doc.split("\n")]
        doc_block = "\n".join(doc_lines)
    else:
        doc_block = ""
    return f"{doc_block}\n{decl}".strip() if doc_block else decl


def diff_buggy_lines(canonical: str, buggy: str) -> list[int]:
    """Return source-line indices in `buggy` that differ from `canonical`.

    Uses difflib.unified_diff. Indices are 0-based into `buggy.splitlines()`.
    Falls back to all-of-buggy if the diff parser gets confused (rare).
    """
    a = canonical.splitlines()
    b = buggy.splitlines()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: set[int] = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        # 'replace', 'insert', 'delete' — flag the changed lines on the b side.
        # For 'delete' (lines removed from canonical), the relevant line in
        # `buggy` is just before/at the removal point; we flag j1 as the
        # closest-affected line.
        if tag == "delete":
            out.add(min(j1, len(b) - 1) if len(b) > 0 else 0)
        else:
            for j in range(j1, j2):
                if 0 <= j < len(b):
                    out.add(j)
    return sorted(out)


def short_id(s: str, prefix: str) -> str:
    h = hashlib.sha1(s.encode()).hexdigest()[:12]
    return f"{prefix}-{h}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("bigcode/humanevalpack", "rust", split="test")
    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))
    print(f"loaded {len(ds)} HumanEvalPack-Rust records", flush=True)

    n_pass = n_fail = n_skipped = 0
    multi_line_bugs = 0
    with args.out.open("w") as f:
        for r in ds:
            spec_text = build_spec(r)
            task = r["task_id"]  # e.g. "Rust/0"
            canonical = r.get("canonical_solution") or ""
            buggy = r.get("buggy_solution") or ""
            if not canonical.strip() or not buggy.strip():
                n_skipped += 1
                continue

            spec_id = short_id(spec_text, f"hep-{task.replace('/', '-')}-spec")

            # PASS record (canonical solution).
            pass_rec = {
                "source": "humanevalpack_rust",
                "source_file": task,
                "test_name": r.get("entry_point") or "",
                "spec_id": spec_id,
                "impl_id": short_id(spec_text + canonical,
                                    f"hep-{task.replace('/', '-')}-pass"),
                "spec_text": spec_text,
                "impl_text": canonical,
                "status": "PASS",
                "buggy_lines": [],
                "outcome": "PASS",
                "bug_type": None,
                "failure_symptoms": None,
            }
            f.write(json.dumps(pass_rec) + "\n")
            n_pass += 1

            # FAIL record (buggy solution + diff-derived buggy lines).
            buggy_lines = diff_buggy_lines(canonical, buggy)
            if len(buggy_lines) > 1:
                multi_line_bugs += 1
            fail_rec = {
                "source": "humanevalpack_rust",
                "source_file": task,
                "test_name": r.get("entry_point") or "",
                "spec_id": spec_id,
                "impl_id": short_id(spec_text + buggy,
                                    f"hep-{task.replace('/', '-')}-fail"),
                "spec_text": spec_text,
                "impl_text": buggy,
                "status": "FAIL",
                "buggy_lines": buggy_lines,
                "outcome": "FAIL",
                "bug_type": r.get("bug_type"),
                "failure_symptoms": r.get("failure_symptoms"),
            }
            f.write(json.dumps(fail_rec) + "\n")
            n_fail += 1

    print(f"wrote {n_pass} PASS + {n_fail} FAIL = {n_pass + n_fail} records "
          f"(skipped {n_skipped}, multi-line bugs: {multi_line_bugs})", flush=True)
    print(f"  -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
