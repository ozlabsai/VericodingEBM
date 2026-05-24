"""Closed-loop CEGIS demo (3-arm): specialist vs LLM-only vs LLM-self-judged.

For each FAIL impl in a subsample, run three repair conditions and check each
with Verus:

  - ARM A (SPECIALIST): top-3 lines from run #10 -> Claude rewrite-only-flagged.
    Does our specialist's localization help Claude repair?

  - ARM B (LLM-ONLY): spec -> Claude full-impl resample.
    How does this compare to letting Claude propose from scratch?

  - ARM C (LLM-SELF-JUDGED): two-pass Claude. First call: Claude localizes
    top-3 most-suspicious lines (ranking prompt). Second call: Claude
    rewrites those top-3 of its own picks.
    Do you even need the specialist if Claude is already a strong localizer?

Three numbers fall out (repair-rate-at-1 + paired McNemar between arms):
if A > C by a meaningful margin, the specialist matters operationally.
If A ~= C, the specialist is dominated by the LLM-self-judged baseline.

Usage:
    OPENROUTER_API_KEY=... uv run python scripts/cegis_demo_3arm.py \\
        --records artifacts/real_bugs/hybrid_averse_stripped/eval_records.jsonl \\
        --n 100 --verus /tmp/verus/verus-arm64-macos/verus \\
        --out artifacts/cegis/3arm_results.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_SLUG = "anthropic/claude-opus-4.7"

VERUS_FILE_TEMPLATE = """use vstd::prelude::*;

verus! {{

{body}

}} // verus!

fn main() {{}}
"""

TREATMENT_PROMPT = """You are an expert Verus (Rust + verification) engineer. The implementation below FAILS Verus verification. A bug localizer has flagged the top-3 most-likely-buggy lines.

## Specification (will be prepended to your output verbatim)
```rust
{spec_text}
```

## Implementation (FAILS verification)
```rust
{impl_text_with_markers}
```

## Flagged lines
Lines marked `<-- SUSPICIOUS` above are the top-3 lines our localizer flagged. They may or may not all be wrong; treat them as a hint.

## Your task
Rewrite the implementation so that the combined (spec + your impl) verifies under Verus. Keep changes minimal — do not rewrite untouched lines unless necessary. You may change the flagged lines, fix obvious mistakes elsewhere if they are clearly needed, and add proof annotations (`assert`, `assume`, `invariant`, `decreases`) anywhere they help.

## Output format (STRICT)
Return ONLY the rewritten implementation as a single fenced code block:
```rust
<your impl here>
```
Do NOT include:
- The specification (it is automatically prepended).
- A `use vstd::prelude::*;` or any other `use` statement at the top.
- A `verus! {{ ... }}` wrapper (it is added automatically).
- A `fn main() {{}}` (it is added automatically).
- Any prose, markdown, or explanation outside the code block."""

BASELINE_PROMPT = """You are an expert Verus (Rust + verification) engineer. The implementation below FAILS Verus verification. Your job: rewrite the implementation so it verifies. Unlike the specialist-guided arm, you receive no localization hint — you must decide what to change.

## Specification (will be prepended to your output verbatim)
```rust
{spec_text}
```

## Implementation (FAILS verification)
```rust
{impl_text}
```

## Your task
Rewrite the implementation so the combined (spec + your impl) verifies. You may rewrite as much or as little as you like, add proof annotations (`assert`, `assume`, `invariant`, `decreases`) wherever they help, and fix any obvious mistakes. If the existing implementation already looks correct to you, you may return it unchanged.

## Output format (STRICT)
Return ONLY the rewritten implementation as a single fenced code block:
```rust
<your impl here>
```
Do NOT include:
- The specification (it is automatically prepended).
- A `use vstd::prelude::*;` or any other `use` statement at the top.
- A `verus! {{ ... }}` wrapper (it is added automatically).
- A `fn main() {{}}` (it is added automatically).
- Any prose, markdown, or explanation outside the code block.
- An empty code block — if you genuinely have nothing to change, output the impl as-is."""


LLM_LOCALIZE_PROMPT = """You are an expert Verus (Rust + verification) reviewer. Below are a specification and an implementation. The implementation FAILS verification. Your job: identify which lines of the implementation are most likely the cause.

## Specification
```rust
{spec_text}
```

## Implementation (numbered, scorable lines only)
```rust
{numbered_impl}
```

The line numbers above are *scorable-line indices* (0-based). Some source lines (blank, brace-only, pure comment) are excluded.

Return ONLY a JSON object with this exact shape:
{{"top_lines": [a, b, c, d, e]}}
where a..e are five integer line indices from the numbered list above, in order from *most* suspicious to *least* suspicious. Do not include any explanation, markdown, or text outside the JSON."""


def parse_code_block(content: str) -> str | None:
    """Extract the first ```rust ... ``` code block from model output and strip
    any LLM-added wrappers (top-level `use vstd::*;`, `verus!{ ... }`,
    `fn main()`) so we can re-wrap consistently."""
    m = re.search(r"```(?:rust|verus|rs)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if m:
        code = m.group(1).strip()
    else:
        s = content.strip()
        if not s or s.startswith("```"):
            return None
        code = s
    # Strip any top-level `use vstd::...;` lines (we add our own wrapper).
    code = re.sub(r"^\s*use\s+vstd[^;]*;\s*$", "", code, flags=re.MULTILINE)
    # Strip any `use verus_builtin::...;` lines if outside verus! — we wrap.
    # If the LLM nested everything in `verus! { ... }`, unwrap it.
    m_verus = re.search(r"verus!\s*\{\s*(.*?)\s*\}\s*(//[^\n]*)?\s*$", code, re.DOTALL)
    if m_verus:
        code = m_verus.group(1).strip()
    # Strip any standalone `fn main() {}` we'll add our own.
    code = re.sub(r"^\s*fn\s+main\s*\(\s*\)\s*\{\s*\}\s*$", "", code, flags=re.MULTILINE)
    return code.strip() if code.strip() else None


def format_impl_with_markers(impl_text: str, scorable_indices: list[int],
                              top3_line_indices: list[int]) -> str:
    """Append `<-- SUSPICIOUS` markers to the top-3 lines (using *sentinel*
    indices that map back to source lines via `scorable_indices`).

    top3_line_indices are positions into `scorable_indices`.
    """
    src_lines = impl_text.splitlines()
    # Map sentinel index -> source line index
    flagged_src_lines = set()
    for sent_idx in top3_line_indices[:3]:
        if 0 <= sent_idx < len(scorable_indices):
            flagged_src_lines.add(scorable_indices[sent_idx])

    out = []
    for i, line in enumerate(src_lines):
        if i in flagged_src_lines:
            # Avoid touching lines that already have a comment that would conflict
            out.append(f"{line}  // <-- SUSPICIOUS")
        else:
            out.append(line)
    return "\n".join(out)


def derive_top3_from_record(rec: dict) -> list[int]:
    """Extract top-3 sentinel indices from a scored record."""
    energies = rec.get("per_line_energies") or []
    if not energies:
        return []
    indexed = list(enumerate(energies))
    indexed.sort(key=lambda x: -x[1])
    return [i for i, _ in indexed[:3]]


def parse_llm_top_lines(content: str, n_lines: int) -> list[int]:
    """Extract top_lines list from Claude's ranking response. Returns at most
    5 valid in-range indices, deduped, in order. Robust to code fences."""
    candidates: list[int] = []
    try:
        obj = json.loads(content)
        candidates = obj.get("top_lines", []) or []
    except Exception:
        m = re.search(r"\{[^{}]*?top_lines[^{}]*?\[([^\]]*)\][^{}]*?\}",
                      content, re.DOTALL)
        if m:
            candidates = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
        else:
            candidates = [int(x) for x in re.findall(r"-?\d+", content)][:5]
    seen = set()
    out: list[int] = []
    for c in candidates:
        try:
            c = int(c)
        except (TypeError, ValueError):
            continue
        if 0 <= c < n_lines and c not in seen:
            seen.add(c)
            out.append(c)
            if len(out) >= 5:
                break
    return out


def derive_scorable_indices(impl_text: str) -> list[int]:
    """Mimic the data-pipeline scorable-line policy. Lines that are blank,
    pure-brace, or pure-comment are non-scorable; everything else is."""
    out = []
    for i, line in enumerate(impl_text.splitlines()):
        s = line.strip()
        if not s:
            continue
        if s in ("{", "}", "{}", "()", ");") or s.startswith(")"):
            continue
        # pure comment line
        if s.startswith("//") and "// FAILS" not in s:
            # comments are non-scorable; FAILS-marked comments are already stripped
            continue
        out.append(i)
    return out


def run_verus(verus_bin: str, spec_text: str, impl_text: str, timeout: int = 30) -> dict:
    """Wrap (spec + impl) in a verus!{...} file and call the Verus binary.
    Returns {verified: bool, n_verified: int, n_errors: int, stderr: str}."""
    body = (spec_text.rstrip() + "\n\n" + impl_text.rstrip()).strip()
    src = VERUS_FILE_TEMPLATE.format(body=body)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [verus_bin, path],
            capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout + r.stderr).strip()
        # "verification results::" line is the canonical signal but not always
        # emitted (some Verus errors are reported before verification starts —
        # parse errors, unsupported features, etc.).
        m = re.search(r"verification results::\s*(\d+)\s*verified,\s*(\d+)\s*errors", out)
        if m:
            n_verified, n_errors = int(m.group(1)), int(m.group(2))
        else:
            # No verification-results line: did anything verify? Count `error:` lines as failures.
            n_verified = 0
            n_errors = len(re.findall(r"^error:", out, re.MULTILINE))
            if n_errors == 0 and r.returncode == 0:
                # Verus returned success without verification-results line — treat as nothing-to-verify
                n_errors = 0
        verified = (r.returncode == 0) and (n_errors == 0) and (n_verified > 0 or True)
        # ^ For our purposes: returncode==0 AND no error: lines AND no
        # verification-results showing errors. The (n_verified>0 or True) is
        # because some impls are pure runtime-only — we still want them to
        # count as "verifies" if Verus didn't complain.
        verified = (r.returncode == 0) and (n_errors == 0)
        return {
            "verified": verified,
            "n_verified": n_verified,
            "n_errors": n_errors,
            "returncode": r.returncode,
            "stderr_tail": out[-1500:],
        }
    except subprocess.TimeoutExpired:
        return {"verified": False, "n_verified": 0, "n_errors": -1,
                "returncode": -1, "stderr_tail": "TIMEOUT"}
    finally:
        try: os.unlink(path)
        except OSError: pass


async def call_claude(client: httpx.AsyncClient, prompt: str, api_key: str,
                      max_retries: int = 2) -> str | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ebm-verus",
        "X-Title": "EBM-Verus CEGIS demo",
    }
    body = {
        "model": MODEL_SLUG,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    for attempt in range(max_retries + 1):
        try:
            r = await client.post(OPENROUTER_URL, headers=headers, json=body, timeout=120)
            if r.status_code != 200:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
    return None


async def repair_one(client: httpx.AsyncClient, rec: dict, api_key: str,
                     verus_bin: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        spec_text = rec.get("spec_text", "") or ""
        impl_text = rec.get("impl_text", "") or ""
        if not spec_text.strip() or not impl_text.strip():
            return {"impl_id": rec.get("impl_id"), "skipped": "empty_text"}
        # Strip // FAILS markers from the impl shown to the LLM.
        impl_clean = "\n".join(
            line.split("// FAILS", 1)[0].rstrip() if "// FAILS" in line else line
            for line in impl_text.splitlines()
        )

        # Sanity check: does the ORIGINAL impl actually fail Verus locally?
        baseline_verus = run_verus(verus_bin, spec_text, impl_clean)

        scorable = derive_scorable_indices(impl_clean)
        all_lines = impl_clean.splitlines()
        scorable_texts = [all_lines[i] for i in scorable]
        n_scorable = len(scorable_texts)

        # ---- ARM A: SPECIALIST top-3 -> Claude rewrite ----
        spec_top3_sent = derive_top3_from_record(rec)
        impl_with_spec_markers = format_impl_with_markers(
            impl_clean, scorable, spec_top3_sent)
        a_prompt = TREATMENT_PROMPT.format(
            spec_text=spec_text, impl_text_with_markers=impl_with_spec_markers)
        a_content = await call_claude(client, a_prompt, api_key)
        a_code = parse_code_block(a_content or "")
        a_verus = run_verus(verus_bin, spec_text, a_code) if a_code else None

        # ---- ARM B: LLM-only spec -> full resample ----
        b_prompt = BASELINE_PROMPT.format(spec_text=spec_text, impl_text=impl_clean)
        b_content = await call_claude(client, b_prompt, api_key)
        b_code = parse_code_block(b_content or "")
        b_verus = run_verus(verus_bin, spec_text, b_code) if b_code else None

        # ---- ARM C: LLM-SELF-JUDGED two-pass ----
        # First call: Claude localizes top-5 of its own choice.
        llm_top_lines: list[int] = []
        if n_scorable > 0:
            numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(scorable_texts))
            loc_prompt = LLM_LOCALIZE_PROMPT.format(
                spec_text=spec_text, numbered_impl=numbered)
            loc_content = await call_claude(client, loc_prompt, api_key)
            if loc_content:
                llm_top_lines = parse_llm_top_lines(loc_content, n_scorable)
        # Second call: same TREATMENT_PROMPT but with Claude's own top-3 flagged.
        llm_top3 = llm_top_lines[:3]
        if llm_top3:
            impl_with_llm_markers = format_impl_with_markers(
                impl_clean, scorable, llm_top3)
            c_prompt = TREATMENT_PROMPT.format(
                spec_text=spec_text, impl_text_with_markers=impl_with_llm_markers)
            c_content = await call_claude(client, c_prompt, api_key)
            c_code = parse_code_block(c_content or "")
            c_verus = run_verus(verus_bin, spec_text, c_code) if c_code else None
        else:
            c_content = None
            c_code = None
            c_verus = None

        return {
            "impl_id": rec.get("impl_id"),
            "spec_id": rec.get("spec_id"),
            "baseline_orig_impl_verifies": baseline_verus.get("verified"),
            # Arm A: specialist-guided
            "arm_a_specialist_verifies": (a_verus or {}).get("verified"),
            "arm_a_n_errors": (a_verus or {}).get("n_errors"),
            "arm_a_code_len": len(a_code) if a_code else 0,
            "arm_a_raw": (a_content or "")[:500],
            "arm_a_top3_sent": spec_top3_sent,
            # Arm B: LLM-only full resample
            "arm_b_llm_only_verifies": (b_verus or {}).get("verified"),
            "arm_b_n_errors": (b_verus or {}).get("n_errors"),
            "arm_b_code_len": len(b_code) if b_code else 0,
            "arm_b_raw": (b_content or "")[:500],
            # Arm C: LLM-self-judged (localize + rewrite)
            "arm_c_llm_self_verifies": (c_verus or {}).get("verified"),
            "arm_c_n_errors": (c_verus or {}).get("n_errors"),
            "arm_c_code_len": len(c_code) if c_code else 0,
            "arm_c_raw": (c_content or "")[:500],
            "arm_c_llm_top_lines": llm_top_lines,
        }


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided mid-p McNemar exact test on (b=10, c=01) discordant pairs."""
    if b + c == 0:
        return 1.0
    from math import comb
    n = b + c
    k = min(b, c)
    # Sum P(X<=k) + P(X>=n-k) for X~Binom(n, 0.5)
    p = 0.0
    for i in range(0, k + 1):
        p += comb(n, i)
    p_two = (2 * p) / (2 ** n)
    return min(1.0, p_two)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, type=Path,
                    help="JSONL of scored records (run10_stripped/eval_records.jsonl)")
    ap.add_argument("--raw-records", type=Path,
                    default=Path("artifacts/real_bugs/records.jsonl"),
                    help="Raw records with spec_text/impl_text to join against.")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verus", required=True, help="path to verus binary")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--concurrency", type=int, default=4)
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

    # Scored records (have per-line energies, no spec/impl text)
    scored = [json.loads(l) for l in args.records.open() if l.strip()]
    # Raw records (have spec_text/impl_text)
    raw_by_id = {}
    if args.raw_records.exists():
        for line in args.raw_records.open():
            if not line.strip(): continue
            r = json.loads(line)
            raw_by_id[r["impl_id"]] = r
    print(f"loaded {len(scored)} scored, {len(raw_by_id)} raw records", flush=True)
    # Join + filter FAILs with usable text + per-line energies
    fails = []
    for r in scored:
        if not str(r.get("status", "")).upper().endswith("FAIL"):
            continue
        if not r.get("per_line_energies"):
            continue
        if not r.get("buggy_line_indices"):
            continue
        raw = raw_by_id.get(r["impl_id"])
        if raw is None:
            continue
        if not raw.get("spec_text") or not raw.get("impl_text"):
            continue
        merged = dict(r)
        merged["spec_text"] = raw["spec_text"]
        merged["impl_text"] = raw["impl_text"]
        fails.append(merged)
    # Filter to "tractable" cases: single buggy line, short impls. The repair
    # task on complex Verus proofs (opaque types, trait bounds, etc.) is well
    # outside what a one-shot Claude call can solve; we exclude those so the
    # demo measures whether localization helps in the regime where any LLM
    # could plausibly succeed.
    def _tractable(r):
        n_scorable = len(r.get("per_line_energies") or [])
        n_buggy = len(r.get("buggy_line_indices") or [])
        impl_lines = (r.get("impl_text") or "").count("\n") + 1
        return n_buggy == 1 and 2 <= n_scorable <= 20 and impl_lines <= 25
    tractable_fails = [r for r in fails if _tractable(r)]
    print(f"joined: {len(fails)} usable FAILs, {len(tractable_fails)} tractable "
          f"(|B|=1, scorable<=20, impl<=25 lines)", flush=True)
    rng = random.Random(args.seed)
    sample = rng.sample(tractable_fails, min(args.n, len(tractable_fails)))
    print(f"sampling {len(sample)}", flush=True)

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
                    r = await repair_one(client, rec, api_key, args.verus, sem)
                    async with write_lock:
                        f_out.write(json.dumps(r) + "\n")
                        f_out.flush()
                        n_done += 1
                        if n_done % 5 == 0:
                            print(f"  {n_done}/{len(sample)} done", flush=True)
                tasks = [_task(r) for r in sample]
                await asyncio.gather(*tasks)

    asyncio.run(_run())

    # Aggregate.
    records = [json.loads(l) for l in args.out.open() if l.strip()]
    n_total = len(records)
    base_orig_verifies = sum(1 for r in records if r.get("baseline_orig_impl_verifies"))
    n_a = sum(1 for r in records if r.get("arm_a_specialist_verifies"))
    n_b = sum(1 for r in records if r.get("arm_b_llm_only_verifies"))
    n_c = sum(1 for r in records if r.get("arm_c_llm_self_verifies"))

    def _pair(arm1_key: str, arm2_key: str) -> dict:
        """Return McNemar counts and p-value for arm1 vs arm2."""
        b = sum(1 for r in records if r.get(arm1_key) and not r.get(arm2_key))
        c = sum(1 for r in records if r.get(arm2_key) and not r.get(arm1_key))
        return {"only_arm1": b, "only_arm2": c, "mcnemar_p": mcnemar_exact(b, c)}

    summary = {
        "n_records_evaluated": n_total,
        "sanity_orig_impl_verifies": base_orig_verifies,
        "sanity_orig_impl_verifies_rate": base_orig_verifies / max(1, n_total),
        # Arms
        "arm_a_specialist": {
            "repair_at_1": n_a,
            "repair_rate": n_a / max(1, n_total),
        },
        "arm_b_llm_only": {
            "repair_at_1": n_b,
            "repair_rate": n_b / max(1, n_total),
        },
        "arm_c_llm_self_judged": {
            "repair_at_1": n_c,
            "repair_rate": n_c / max(1, n_total),
        },
        # Pairwise McNemars (the load-bearing one is A vs C).
        "mcnemar_specialist_vs_llm_self": _pair(
            "arm_a_specialist_verifies", "arm_c_llm_self_verifies"),
        "mcnemar_specialist_vs_llm_only": _pair(
            "arm_a_specialist_verifies", "arm_b_llm_only_verifies"),
        "mcnemar_llm_self_vs_llm_only": _pair(
            "arm_c_llm_self_verifies", "arm_b_llm_only_verifies"),
    }
    print("\n=== CEGIS 3-ARM SUMMARY ===")
    print(json.dumps(summary, indent=2))
    summary_path = args.out.parent / "summary_3arm.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out} and {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
