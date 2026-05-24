"""Audit #1: verifier-cited line vs actual bug line in system_trajectory.

Originally meant to spot-check 20 FAIL rows to see if Verus error messages cite
the *introducing* line of a bug or the *consuming* line. We already noticed
during smoke-test that FAIL rows in this dataset have empty ``log`` fields —
this script confirms that finding rigorously and closes the question.

Outcome: if FAIL log fields are systematically empty, the design decision
(critique 1a: drop verifier-cited lines from L_line) is correct by necessity,
not just by safety. L_line runs only on sft_safe diff labels.

Usage:
    uv run python scripts/audit_logs.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path("data/raw/system_trajectory_843.jsonl")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    print(f"audit: log-field availability in FAIL rows of {path}")
    print("=" * 64)

    by_status: Counter = Counter()
    log_lens_by_status: dict[str, list[int]] = {}
    samples: dict[str, list] = {"success": [], "error": [], "timeout": []}
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            status = row.get("status", "?")
            by_status[status] += 1
            log = row.get("log") or ""
            log_lens_by_status.setdefault(status, []).append(len(log))
            if len(samples.get(status, [])) < 2:
                samples.setdefault(status, []).append(row)

    print(f"row counts: {dict(by_status)}")
    print()
    print("log-field length distribution by status:")
    for status, lens in log_lens_by_status.items():
        n = len(lens)
        zero = sum(1 for x in lens if x == 0)
        nonzero = [x for x in lens if x > 0]
        if nonzero:
            mean = sum(nonzero) / len(nonzero)
            mx = max(nonzero)
        else:
            mean, mx = 0, 0
        print(
            f"  status={status:8s} n={n:>5d} "
            f"empty={zero:>5d} ({100*zero/n:.1f}%) "
            f"nonempty_mean={mean:.0f} max={mx}"
        )

    # Look at one nonempty log per status for eyeball context
    print()
    print("sample log content per status:")
    for status in ("success", "error", "timeout"):
        if status not in samples or not samples[status]:
            continue
        for row in samples[status]:
            log = row.get("log") or ""
            if log:
                print(f"  --- status={status} log[:300] ---")
                print("  " + log[:300].replace("\n", "\n  "))
                break
        else:
            print(f"  --- status={status}: all sampled rows have empty log ---")

    print()
    print("=" * 64)
    print("conclusion:")
    fail_lens = log_lens_by_status.get("error", []) + log_lens_by_status.get("timeout", [])
    if fail_lens and all(x == 0 for x in fail_lens):
        print("  ALL FAIL rows have empty log fields. Verifier-cited-line idea")
        print("  is structurally unavailable. Critique 1a resolution holds by")
        print("  necessity: L_line uses only sft_safe diffs.")
    elif fail_lens:
        nonempty = sum(1 for x in fail_lens if x > 0)
        print(f"  {nonempty}/{len(fail_lens)} FAIL rows have nonempty logs.")
        print("  Inspect their content to decide if verifier-cited lines can")
        print("  be reliably extracted. If <70% have parseable line numbers,")
        print("  the critique 1a resolution (drop them) stands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
