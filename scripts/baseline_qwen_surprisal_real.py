"""Frozen Qwen per-line surprisal baseline on the real-bug corpus.

Adapts baseline_qwen_ppl.py (which runs on the synthetic held set) to score
artifacts/real_bugs/records.jsonl using the same per-line NLL protocol.

Per Hindle 2012 / Karampatsis 2020: per-line average negative log-likelihood
under a frozen code LM (no LoRA, no head). Tests whether finetuning earns
its keep over the pretraining prior.

Output schema matches score_external_records.py so analyze_records.py
consumes it without modification.

Usage:
    uv run python scripts/baseline_qwen_surprisal_real.py \\
        --config configs/run10_hybrid.yaml \\
        --in artifacts/real_bugs/records.jsonl \\
        --out artifacts/baselines/qwen_surprisal_records.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status


def _resolve_dtype(p):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[p]


def _status_from_str(s):
    s = s.upper()
    if s.endswith("PASS") or s.endswith("OK"):
        return Status.PASS
    if s.endswith("FAIL") or s.endswith("ERR"):
        return Status.FAIL
    return Status.UNKNOWN


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"device: {device}", flush=True)

    raw = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    print(f"loaded {len(raw)} records from {args.in_path}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    dtype = _resolve_dtype(cfg["train"]["precision"])
    # MPS fp16 overflows Qwen's 151k-vocab softmax (gives NaN); use fp32 there.
    # bf16 on MPS is also flaky. fp32 is slower but numerically safe.
    if device.type == "mps":
        dtype = torch.float32
        print("  (MPS detected, forcing fp32 to avoid softmax overflow)", flush=True)
    print(f"loading {cfg['model']['backbone']} (dtype={dtype})", flush=True)
    # MPS+GQA SDPA has a known shape-inference bug; force eager attention there.
    attn_impl = "eager" if device.type == "mps" else None
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model"]["backbone"],
        torch_dtype=dtype,
        attn_implementation=attn_impl,
    ).to(device)
    model.eval()

    max_len = int(cfg["data"]["max_seq_len"])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    n_written, n_skipped = 0, 0
    with args.out.open("w") as f_out:
        for r in raw:
            spec_text = r.get("spec_text", "")
            impl_text = r.get("impl_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))
            ex = Example(
                source=Source.SFT_SAFE,
                spec_id=r["spec_id"],
                impl_id=r["impl_id"],
                spec_text=spec_text,
                impl_text=impl_text,
                status=_status_from_str(r.get("status", "")),
                buggy_lines=buggy_source_lines,
            )
            t = tokenize_example(ex, tokenizer, max_length=max_len)
            if t is None or not t.sentinel_positions:
                n_skipped += 1
                continue

            input_ids = torch.tensor([t.input_ids], device=device)
            with torch.no_grad():
                out = model(input_ids)
                logits = out.logits
            log_probs = F.log_softmax(logits.float(), dim=-1)

            sent_pos = list(t.sentinel_positions)
            prev = t.spec_token_count - 1
            energies = []
            ids = t.input_ids
            for sp in sent_pos:
                start = prev + 1
                end = sp
                if end <= start:
                    energies.append(0.0)
                    prev = sp
                    continue
                tok_ids = torch.tensor(ids[start:end], device=device)
                lp_slice = log_probs[0, start - 1:end - 1, :]
                gathered = lp_slice.gather(1, tok_ids.unsqueeze(1)).squeeze(1)
                energies.append(float(-gathered.mean().item()))
                prev = sp

            all_lines = impl_text.splitlines()
            scorable = scorable_line_indices(impl_text)
            scorable_texts = [all_lines[i] for i in scorable][: len(energies)]
            src_to_sent = {s: i for i, s in enumerate(scorable)}
            buggy_sent = sorted({
                src_to_sent[s] for s in buggy_source_lines
                if s in src_to_sent and src_to_sent[s] < len(energies)
            })

            whole = sum(energies) / len(energies) if energies else 0.0
            f_out.write(json.dumps({
                "impl_id": ex.impl_id,
                "spec_id": ex.spec_id,
                "source": "baseline_qwen_surprisal",
                "status": ex.status.value,
                "whole_impl_energy": whole,
                "per_line_energies": energies,
                "buggy_line_indices": buggy_sent,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
            n_written += 1
            if n_written % 50 == 0:
                print(f"  {n_written}/{len(raw)} scored", flush=True)
    print(f"DONE: wrote {n_written}, skipped {n_skipped} -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
