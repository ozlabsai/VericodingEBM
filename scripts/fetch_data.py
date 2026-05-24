"""Fetch the two raw data files from HuggingFace into data/raw/.

Usage:
    uv run python scripts/fetch_data.py

Idempotent — skips already-present files unless --force.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "microsoft/Verus_Training_Data"

# Always fetched — these are the load-bearing files for L_spec and L_line.
CORE_FILES = {
    "system_trajectory_843.jsonl": "system_trajectory_843.jsonl",
    "sft_safe_25k.json": "sft_safe_25k.json",
}

# Optional — gated behind --include-large. The 15.7GB sft_part1 is a potential
# Saturday scale-up for L_line (see scripts/audit_sft_part1.py before using).
EXTRA_FILES = {
    "sft_part2_4557.json": "sft_part2_4557.json",
    "algorithmic_trajectory_9040.jsonl": "algorithmic_trajectory_9040.jsonl",
    "sft_part1_6.9M.json": "sft_part1_6.9M.json",   # the 15.7GB one
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=Path("data/raw"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-large", action="store_true",
                        help="Also fetch the 15.7GB sft_part1_6.9M.json (rare).")
    parser.add_argument("--include-extras", action="store_true", default=False,
                        help="Fetch the medium-size files (sft_part2_4557, "
                             "algorithmic_trajectory_9040) — required by configs "
                             "that reference them.")
    args = parser.parse_args()

    files = dict(CORE_FILES)
    if args.include_extras or args.include_large:
        files["sft_part2_4557.json"] = "sft_part2_4557.json"
        files["algorithmic_trajectory_9040.jsonl"] = "algorithmic_trajectory_9040.jsonl"
    if args.include_large:
        files["sft_part1_6.9M.json"] = "sft_part1_6.9M.json"
        print("  NOTE: --include-large will pull ~16GB. Make sure you have disk + bandwidth.")

    args.dest.mkdir(parents=True, exist_ok=True)

    for local_name, hub_name in files.items():
        target = args.dest / local_name
        # If the local target is a symlink to /tmp/... (left over from smoke
        # test), remove it first so we don't write into /tmp.
        if target.is_symlink():
            print(f"  removing stale symlink: {target} -> {os.readlink(target)}")
            target.unlink()
        if target.exists() and not args.force:
            size_mb = target.stat().st_size / 1_000_000
            print(f"  {target} already present ({size_mb:.1f} MB) — skipping")
            continue

        print(f"  fetching {hub_name} from {REPO_ID} ...")
        path = hf_hub_download(
            repo_id=REPO_ID,
            filename=hub_name,
            repo_type="dataset",
            local_dir=str(args.dest),
        )
        size_mb = Path(path).stat().st_size / 1_000_000
        print(f"  -> {path} ({size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
