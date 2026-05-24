"""Baseline: per-line perplexity from frozen Qwen2.5-Coder, no contrastive head.

For each held impl:
  1. Reconstruct the same sentinel-inserted token sequence the trainer used.
  2. Forward Qwen2.5-Coder (no LoRA, no head).
  3. For each "scorable line", compute mean -log p(token | prefix) over the
     tokens belonging to that line (tokens between consecutive sentinels).
  4. Use that as the per-line energy.

This is the R10 baseline: "raw LM, no contrastive training". If we beat it,
the contrastive heads do work that perplexity alone cannot.

Outputs a JSONL with the same shape as dump_eval_records.py so analyze_records.py
can consume it directly.
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
from ebm_verus.data import load_all, split_examples
from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example


def _resolve_dtype(precision: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

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

    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    sentinel_id = tokenizer.encode(
        cfg["model"].get("sentinel_token", SENTINEL_TOKEN), add_special_tokens=False
    )[0]

    dtype = _resolve_dtype(cfg["train"]["precision"])
    print(f"loading {cfg['model']['backbone']} (dtype={dtype})", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model"]["backbone"], torch_dtype=dtype
    ).to(device)
    model.eval()

    max_len = int(cfg["data"]["max_seq_len"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    n_skipped = 0
    with args.out.open("w") as f:
        for ex in held_ex:
            t = tokenize_example(ex, tokenizer, max_length=max_len)
            if t is None or not t.sentinel_positions:
                n_skipped += 1
                continue
            input_ids = torch.tensor([t.input_ids], device=device)
            with torch.no_grad():
                out = model(input_ids)
                logits = out.logits  # (1, L, V)
            # log p(token_i | prefix) = log_softmax(logits[i-1])[token_i]
            log_probs = F.log_softmax(logits.float(), dim=-1)
            # For each sentinel boundary, gather tokens in [prev+1 : sent_pos] inclusive
            # (the tokens of the line preceding the sentinel). Mean neg-log-prob = "energy".
            sent_pos = list(t.sentinel_positions)
            # The first scorable line's tokens start after spec_token_count.
            prev = t.spec_token_count - 1  # tokens after this index are impl
            energies: list[float] = []
            ids = t.input_ids
            for sp in sent_pos:
                # Tokens of the current line: positions (prev+1 .. sp-1) inclusive,
                # i.e. ids[prev+1:sp]. Their log-p is log_probs[0, k-1, ids[k]].
                start = prev + 1
                end = sp  # exclusive (sentinel itself is excluded)
                if end <= start:
                    energies.append(0.0)
                    prev = sp
                    continue
                tok_ids = torch.tensor(ids[start:end], device=device)
                # log_probs[0, k-1, ids[k]] for k in [start, end)
                lp_slice = log_probs[0, start - 1:end - 1, :]
                gathered = lp_slice.gather(1, tok_ids.unsqueeze(1)).squeeze(1)
                # energy = mean negative log-prob
                energies.append(float(-gathered.mean().item()))
                prev = sp

            all_lines = ex.impl_text.splitlines()
            scorable = scorable_line_indices(ex.impl_text)
            scorable_texts = [all_lines[i] for i in scorable][: len(energies)]
            # Whole-impl energy: mean per-line (matches the LM baseline framing).
            whole = sum(energies) / len(energies) if energies else 0.0
            f.write(json.dumps({
                "impl_id": ex.impl_id,
                "spec_id": ex.spec_id,
                "source": ex.source.value,
                "status": ex.status.value,
                "whole_impl_energy": whole,
                "per_line_energies": energies,
                "buggy_line_indices": sorted(t.buggy_line_indices),
                "scorable_line_texts": scorable_texts,
            }) + "\n")
            n_written += 1
            if n_written % 50 == 0:
                print(f"  {n_written} done", flush=True)
    print(f"wrote {n_written} (skipped {n_skipped}) -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
