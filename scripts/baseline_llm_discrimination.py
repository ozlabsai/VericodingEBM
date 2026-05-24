"""LLM zero-shot DISCRIMINATION baseline via OpenRouter (apples-to-apples AUROC).

Same 5 models, same OpenRouter slugs, same stripped corpus, same 220 records
as scripts/baseline_llm_zeroshot.py — but a different prompt: ask the model
to output {pass, fail} + a calibration score in [0, 1] for "probability this
impl fails verification." That score is what we use as whole_impl_energy
for a like-for-like AUROC comparison with our trained scalar head.

Output: artifacts/baselines/llm_disc/llm_<slug>_records.jsonl
Schema is the same as the rank-based baseline so analyze_records.py works
without modification; per_line_energies are all 0 (this baseline does not
do per-line ranking, by design).

Usage:
    uv run python scripts/baseline_llm_discrimination.py \\
        --in artifacts/real_bugs/records.jsonl \\
        --out-dir artifacts/baselines/llm_disc/ \\
        --n 200 --concurrency 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path

import httpx

from ebm_verus.data.line_policy import scorable_line_indices

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = [
    ("claude-opus-4.7",  "anthropic/claude-opus-4.7"),
    ("deepseek-v4-pro",  "deepseek/deepseek-v4-pro"),
    ("qwen3.7-max",      "qwen/qwen3.7-max"),
    ("gpt-5.5",          "openai/gpt-5.5"),
    ("gemini-3.5-flash", "google/gemini-3.5-flash"),
]

DISCRIMINATION_PROMPT = """You are an expert Verus (Rust + verification) reviewer. Below are a specification and an implementation. Your job: judge whether this implementation will pass Verus verification.

## Specification
```rust
{spec_text}
```

## Implementation
```rust
{impl_text}
```

Return ONLY a JSON object with this exact shape:
{{"verdict": "pass" | "fail", "p_fail": <float in [0,1]>}}
where:
  - "verdict" is your best single label;
  - "p_fail" is your calibrated probability that this implementation FAILS Verus verification. Higher = more likely to fail. Use the full range — confidently-passing impls should get values near 0, confidently-failing impls near 1, uncertain cases around 0.5.

Do not include any explanation, markdown, or text outside the JSON."""


def strip_fails(impl_text: str) -> str:
    out = []
    for line in impl_text.splitlines():
        if "// FAILS" in line:
            line = line.split("// FAILS", 1)[0].rstrip()
        out.append(line)
    return "\n".join(out)


def _status_str(s) -> str:
    s = str(s).upper()
    if "." in s: s = s.split(".")[-1]
    if "PASS" in s or "OK" in s: return "PASS"
    if "FAIL" in s or "ERR" in s: return "FAIL"
    return "UNKNOWN"


def build_prompt(spec_text: str, impl_text: str) -> str:
    return DISCRIMINATION_PROMPT.format(spec_text=spec_text, impl_text=impl_text)


def parse_response(content: str) -> tuple[str | None, float | None]:
    """Extract (verdict, p_fail) from the model's response. Robust to extra prose."""
    try:
        obj = json.loads(content)
        v = obj.get("verdict")
        p = obj.get("p_fail")
        if isinstance(v, str):
            v = v.strip().lower()
            if v not in ("pass", "fail"):
                v = None
        if isinstance(p, (int, float)):
            p = float(p)
            if not (0.0 <= p <= 1.0):
                p = max(0.0, min(1.0, p))
        else:
            p = None
        return v, p
    except Exception:
        pass
    # Regex fallback
    v_match = re.search(r'"verdict"\s*:\s*"(pass|fail)"', content, re.IGNORECASE)
    p_match = re.search(r'"p_fail"\s*:\s*([0-9.]+)', content)
    v = v_match.group(1).lower() if v_match else None
    if p_match:
        try:
            p = float(p_match.group(1))
            p = max(0.0, min(1.0, p))
        except (TypeError, ValueError):
            p = None
    else:
        p = None
    return v, p


async def call_model(client: httpx.AsyncClient, slug: str, prompt: str,
                     api_key: str, max_retries: int = 2) -> tuple[str | None, dict | None]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ebm-verus",
        "X-Title": "EBM-Verus discrimination baseline",
    }
    body = {
        "model": slug,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 800,   # smaller — only a tiny JSON answer expected
        "response_format": {"type": "json_object"},
        "reasoning": {"max_tokens": 300},
    }
    for attempt in range(max_retries + 1):
        try:
            r = await client.post(OPENROUTER_URL, headers=headers, json=body, timeout=90)
            if r.status_code != 200:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None, {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return content, data.get("usage")
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return None, {"error": str(e)[:200]}
    return None, None


async def score_record(client: httpx.AsyncClient, slug: str, label: str,
                       record: dict, api_key: str, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        impl_text = strip_fails(record.get("impl_text", "") or "")
        spec_text = record.get("spec_text", "") or ""
        if not impl_text.strip():
            return None

        all_lines = impl_text.splitlines()
        scorable = scorable_line_indices(impl_text)
        scorable_texts = [all_lines[i] for i in scorable]
        n_lines = len(scorable_texts)
        if n_lines == 0:
            return None

        buggy_source = set(int(i) for i in record.get("buggy_lines", []))
        src_to_sent = {s: i for i, s in enumerate(scorable)}
        buggy_sent = sorted({src_to_sent[s] for s in buggy_source if s in src_to_sent})

        prompt = build_prompt(spec_text, impl_text)
        content, usage = await call_model(client, slug, prompt, api_key)
        verdict, p_fail = parse_response(content or "") if content else (None, None)
        failed = (content is None) or (verdict is None and p_fail is None)
        # whole_impl_energy = p_fail directly (higher = more likely to fail = higher energy).
        # If only verdict is present, fall back to 1.0 (fail) / 0.0 (pass).
        if p_fail is not None:
            whole = float(p_fail)
        elif verdict == "fail":
            whole = 1.0
        elif verdict == "pass":
            whole = 0.0
        else:
            whole = 0.5  # neutral fallback for failed parses

        return {
            "impl_id": record["impl_id"],
            "spec_id": record["spec_id"],
            "source": f"baseline_llm_disc_{label}",
            "status": _status_str(record.get("status", "")),
            "whole_impl_energy": whole,
            "per_line_energies": [0.0] * n_lines,
            "buggy_line_indices": buggy_sent,
            "scorable_line_texts": scorable_texts,
            "_llm_verdict": verdict,
            "_llm_p_fail": p_fail,
            "_llm_usage": usage,
            "_llm_raw": (content or "")[:300],
            "_llm_failed": failed,
        }


async def run_one_model(label: str, slug: str, records: list[dict],
                        out_path: Path, api_key: str, concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(120.0, connect=30.0)
    n_done = n_failed = 0
    total_in = total_out = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock = asyncio.Lock()
    with out_path.open("w") as f_out:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async def _task(rec):
                nonlocal n_done, n_failed, total_in, total_out
                r = await score_record(client, slug, label, rec, api_key, sem)
                if r is None:
                    return
                if r.get("_llm_failed"):
                    n_failed += 1
                else:
                    u = r.get("_llm_usage") or {}
                    total_in += int(u.get("prompt_tokens") or 0)
                    total_out += int(u.get("completion_tokens") or 0)
                async with write_lock:
                    f_out.write(json.dumps(r) + "\n")
                    f_out.flush()
                    n_done += 1
                    if n_done % 20 == 0:
                        print(f"  [{label}] {n_done}/{len(records)} done "
                              f"(failed={n_failed}, in={total_in}, out={total_out})",
                              flush=True)
            tasks = [_task(r) for r in records]
            await asyncio.gather(*tasks)
    return {"label": label, "slug": slug, "n_done": n_done, "n_failed": n_failed,
            "tokens_in": total_in, "tokens_out": total_out, "out": str(out_path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--n", type=int, default=200, help="FAIL subsample size; PASS is added on top (~10%).")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--models", nargs="+", default=[m[0] for m in MODELS])
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

    raw = [json.loads(l) for l in args.in_path.open() if l.strip()]
    print(f"loaded {len(raw)} records", flush=True)
    fail_with_labels = [r for r in raw if _status_str(r.get("status", "")) == "FAIL" and r.get("buggy_lines")]
    print(f"FAIL with labels: {len(fail_with_labels)}", flush=True)
    rng = random.Random(args.seed)
    sample = rng.sample(fail_with_labels, min(args.n, len(fail_with_labels)))
    # PASS records — bigger this time for a better AUROC signal (50 instead of 20).
    pass_recs = [r for r in raw if _status_str(r.get("status", "")) == "PASS"]
    n_pass = min(len(pass_recs), max(50, args.n // 4))
    sample += rng.sample(pass_recs, n_pass) if pass_recs else []
    print(f"subsample: {len(sample)} records ({len(sample)-n_pass} FAIL + {n_pass} PASS)", flush=True)

    selected = [m for m in MODELS if m[0] in args.models]
    print(f"running {len(selected)} models: {[m[0] for m in selected]}", flush=True)

    async def _main():
        summaries = []
        for label, slug in selected:
            out_path = args.out_dir / f"llm_disc_{label}_records.jsonl"
            print(f"\n=== {label} ({slug}) -> {out_path.name} ===", flush=True)
            s = await run_one_model(label, slug, sample, out_path, api_key, args.concurrency)
            summaries.append(s)
        return summaries

    summaries = asyncio.run(_main())
    summary_path = args.out_dir / "_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2))
    print(f"\n=== ALL DONE ===")
    for s in summaries:
        print(f"  {s['label']:20} done={s['n_done']:>4}  failed={s['n_failed']:>3}  "
              f"in={s['tokens_in']:>7}  out={s['tokens_out']:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
