"""LLM zero-shot bug-line ranking baseline via OpenRouter.

Subsamples 200 records from artifacts/real_bugs/records.jsonl, strips //FAILS
markers (same audit treatment as run10_stripped), then asks each LLM to rank
the top-5 most-likely-buggy lines via structured JSON.

Models hit (all via OpenRouter):
  - anthropic/claude-opus-4.7
  - openai/gpt-5.5-pro
  - google/gemini-3.5-flash
  - qwen/qwen3.7-max

Output per model: artifacts/baselines/llm_<slug>_records.jsonl
Schema matches score_external_records.py so analyze_records.py + the
significance script consume it without modification.

Usage:
    uv run python scripts/baseline_llm_zeroshot.py \\
        --in artifacts/real_bugs/records.jsonl \\
        --out-dir artifacts/baselines/llm/ \\
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

PROMPT_TEMPLATE = """You are an expert Verus (Rust + verification) reviewer. Below are a specification and an implementation. The implementation FAILS verification. Your job: identify which lines of the implementation are most likely the cause.

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


def strip_fails(impl_text: str) -> str:
    """Same as scripts/strip_fails_reeval.py — drop the //FAILS leak."""
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


def build_prompt(spec_text: str, scorable_texts: list[str]) -> str:
    numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(scorable_texts))
    return PROMPT_TEMPLATE.format(spec_text=spec_text, numbered_impl=numbered)


def parse_response(content: str, n_lines: int) -> list[int]:
    """Extract top_lines from the model's response. Tolerates code fences and
    junk; returns at most 5 valid in-range indices, deduped, in order."""
    # Try JSON parse on the whole string first.
    candidates: list[int] = []
    try:
        obj = json.loads(content)
        candidates = obj.get("top_lines", []) or []
    except Exception:
        # Fall back: regex out an integer list.
        m = re.search(r"\{[^{}]*?top_lines[^{}]*?\[([^\]]*)\][^{}]*?\}", content, re.DOTALL)
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


def topk_to_energies(top_lines: list[int], n_lines: int) -> list[float]:
    """Convert ranked top-5 indices into per-line energies.
    Top-ranked line gets the highest energy (= most suspicious in our
    convention); ranks 1..5 get energies 5,4,3,2,1; everything else gets 0."""
    energies = [0.0] * n_lines
    for rank, idx in enumerate(top_lines):
        if 0 <= idx < n_lines:
            energies[idx] = float(5 - rank)
    return energies


async def call_model(client: httpx.AsyncClient, slug: str, prompt: str,
                     api_key: str, max_retries: int = 2) -> tuple[str | None, dict | None]:
    """Returns (content, usage_dict). content is None on failure."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ebm-verus",
        "X-Title": "EBM-Verus zero-shot baseline",
    }
    # max_tokens covers BOTH reasoning + visible output for thinking models
    # (gpt-5.5, gemini-3.5, claude-opus-4.7). Give 1500 budget so a few hundred
    # reasoning tokens still leaves room for the JSON answer.
    body = {
        "model": slug,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
        # Cap thinking budget low — we don't need deep reasoning to pick 5 lines.
        "reasoning": {"max_tokens": 400},
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

        prompt = build_prompt(spec_text, scorable_texts)
        content, usage = await call_model(client, slug, prompt, api_key)
        top_lines = parse_response(content or "", n_lines) if content else []
        energies = topk_to_energies(top_lines, n_lines)
        # whole-impl energy: max of per-line (consistent with other baselines)
        whole = max(energies) if energies else 0.0

        return {
            "impl_id": record["impl_id"],
            "spec_id": record["spec_id"],
            "source": f"baseline_llm_{label}",
            "status": _status_str(record.get("status", "")),
            "whole_impl_energy": whole,
            "per_line_energies": energies,
            "buggy_line_indices": buggy_sent,
            "scorable_line_texts": scorable_texts,
            "_llm_top_lines": top_lines,
            "_llm_usage": usage,
            "_llm_raw": (content or "")[:300],   # truncated raw for diagnosis
            "_llm_failed": content is None or not top_lines,
        }


async def run_one_model(label: str, slug: str, records: list[dict],
                        out_path: Path, api_key: str, concurrency: int) -> dict:
    sem = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(120.0, connect=30.0)
    n_done = 0
    n_failed = 0
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
    ap.add_argument("--n", type=int, default=200, help="Subsample size.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--models", nargs="+", default=[m[0] for m in MODELS],
                    help="Subset of labels to run; defaults to all four.")
    args = ap.parse_args()

    # Load OpenRouter key (.env file).
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

    # Load + subsample records.
    raw = [json.loads(l) for l in args.in_path.open() if l.strip()]
    print(f"loaded {len(raw)} records", flush=True)
    fail_with_labels = [r for r in raw if _status_str(r.get("status", "")) == "FAIL" and r.get("buggy_lines")]
    print(f"FAIL with labels: {len(fail_with_labels)}", flush=True)
    rng = random.Random(args.seed)
    if len(fail_with_labels) > args.n:
        sample = rng.sample(fail_with_labels, args.n)
    else:
        sample = fail_with_labels
    # Plus a small PASS sample so AUROC is well-defined (~10%).
    pass_recs = [r for r in raw if _status_str(r.get("status", "")) == "PASS"]
    n_pass = min(len(pass_recs), max(15, args.n // 10))
    sample += rng.sample(pass_recs, n_pass) if pass_recs else []
    print(f"subsample: {len(sample)} records ({len(sample)-n_pass} FAIL + {n_pass} PASS)", flush=True)

    selected = [m for m in MODELS if m[0] in args.models]
    print(f"running {len(selected)} models: {[m[0] for m in selected]}", flush=True)

    async def _main():
        summaries = []
        for label, slug in selected:
            out_path = args.out_dir / f"llm_{label}_records.jsonl"
            print(f"\n=== {label} ({slug}) -> {out_path.name} ===", flush=True)
            s = await run_one_model(label, slug, sample, out_path, api_key,
                                    args.concurrency)
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
