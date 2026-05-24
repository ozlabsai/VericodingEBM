"""Re-run only Arm B (LLM-only resample) with the fixed prompt that includes
the failing impl as anchor. Merge results back into the 3-arm jsonl.

The original Arm B prompt asked Claude to write an impl from spec alone, which
collapsed (38% empty code blocks) on records where the spec was already
self-contained. The new prompt shows Claude the failing impl and asks for
a rewrite without localization hints — apples-to-apples with Arms A and C
in terms of input shape, only differing in the (lack of) localization signal.

Usage:
    OPENROUTER_API_KEY=... uv run python scripts/cegis_rerun_arm_b.py \\
        --records artifacts/real_bugs/run10_stripped/eval_records.jsonl \\
        --orig artifacts/cegis/3arm_results.jsonl \\
        --raw-records artifacts/real_bugs/records.jsonl \\
        --verus /tmp/verus/verus-arm64-macos/verus \\
        --out artifacts/cegis/3arm_results_v2.jsonl \\
        --concurrency 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx

# Reuse helpers from the main script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cegis_demo_3arm import (
    BASELINE_PROMPT, MODEL_SLUG, OPENROUTER_URL,
    call_claude, parse_code_block, run_verus,
)


async def rerun_b_one(client: httpx.AsyncClient, rec: dict, raw: dict,
                       api_key: str, verus_bin: str,
                       sem: asyncio.Semaphore) -> dict:
    async with sem:
        spec_text = raw.get("spec_text", "") or ""
        impl_text = raw.get("impl_text", "") or ""
        if not spec_text.strip() or not impl_text.strip():
            return {**rec, "_arm_b_rerun_skipped": "empty_text"}
        impl_clean = "\n".join(
            line.split("// FAILS", 1)[0].rstrip() if "// FAILS" in line else line
            for line in impl_text.splitlines()
        )

        b_prompt = BASELINE_PROMPT.format(spec_text=spec_text, impl_text=impl_clean)
        b_content = await call_claude(client, b_prompt, api_key)
        b_code = parse_code_block(b_content or "")
        b_verus = run_verus(verus_bin, spec_text, b_code) if b_code else None

        return {
            **rec,
            "arm_b_llm_only_verifies": (b_verus or {}).get("verified"),
            "arm_b_n_errors": (b_verus or {}).get("n_errors"),
            "arm_b_code_len": len(b_code) if b_code else 0,
            "arm_b_raw": (b_content or "")[:500],
            "_arm_b_rerun": True,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True, type=Path,
                    help="Original 3arm results JSONL to re-run Arm B on.")
    ap.add_argument("--raw-records", type=Path,
                    default=Path("artifacts/real_bugs/records.jsonl"))
    ap.add_argument("--verus", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        return 2

    orig = [json.loads(l) for l in args.orig.open() if l.strip()]
    raw_by_id = {}
    for line in args.raw_records.open():
        if not line.strip(): continue
        r = json.loads(line)
        raw_by_id[r["impl_id"]] = r
    print(f"loaded {len(orig)} original records, {len(raw_by_id)} raw")

    # Re-run ALL of them — cheap (~$1) and ensures the new prompt's effect on
    # records where the old prompt happened to succeed is also captured.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    n_done = 0
    write_lock = asyncio.Lock()

    async def _run():
        nonlocal n_done
        timeout = httpx.Timeout(180.0, connect=30.0)
        with args.out.open("w") as f_out:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async def _task(rec):
                    nonlocal n_done
                    raw = raw_by_id.get(rec["impl_id"])
                    if raw is None:
                        async with write_lock:
                            f_out.write(json.dumps(rec) + "\n")
                            f_out.flush()
                            n_done += 1
                        return
                    new_rec = await rerun_b_one(client, rec, raw, api_key, args.verus, sem)
                    async with write_lock:
                        f_out.write(json.dumps(new_rec) + "\n")
                        f_out.flush()
                        n_done += 1
                        if n_done % 10 == 0:
                            print(f"  {n_done}/{len(orig)} done", flush=True)
                tasks = [_task(r) for r in orig]
                await asyncio.gather(*tasks)
    asyncio.run(_run())

    # Aggregate Arm B before/after.
    new = [json.loads(l) for l in args.out.open() if l.strip()]
    old_b = sum(1 for r in orig if r.get("arm_b_llm_only_verifies"))
    new_b = sum(1 for r in new if r.get("arm_b_llm_only_verifies"))
    old_no_code = sum(1 for r in orig if not r.get("arm_b_llm_only_verifies") and (r.get("arm_b_code_len") or 0) == 0)
    new_no_code = sum(1 for r in new if not r.get("arm_b_llm_only_verifies") and (r.get("arm_b_code_len") or 0) == 0)
    print(f"\nArm B old (empty-block-bug prompt): repair {old_b}/{len(orig)} = {old_b/len(orig):.2%}, no_code {old_no_code}")
    print(f"Arm B new (anchor-included prompt):  repair {new_b}/{len(new)} = {new_b/len(new):.2%}, no_code {new_no_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
