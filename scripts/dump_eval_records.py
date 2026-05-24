"""Run the trained scorer over the held set and dump per-impl records.

Outputs a JSONL file where each line is one impl with its per-line energies,
buggy-line indices, status, and source. This is the cache that all downstream
analyses (z-score aggregator, baselines, triviality checks, bootstrap CIs)
read from -- so we only do the (expensive) GPU forward pass once.

Usage:
    uv run python scripts/dump_eval_records.py \
        --config configs/default.yaml \
        --ckpt-dir checkpoints/run/final \
        --out artifacts/eval_records.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import yaml

from ebm_verus.constants import SENTINEL_TOKEN  # noqa: F401
from ebm_verus.data import load_all, split_examples
from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.eval.loop import run_eval
from ebm_verus.model.scorer import EnergyScorer


def _resolve_dtype(precision: str) -> torch.dtype:
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", type=Path, default=None,
                    help="Directory with adapter/ and head.pt. If omitted, dumps untrained.")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--batch-size", type=int, default=8)
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

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    lora = cfg["model"]["lora"]
    model = EnergyScorer(
        backbone_name=cfg["model"]["backbone"],
        lora_rank=int(lora["rank"]),
        lora_alpha=int(lora["alpha"]),
        lora_dropout=float(lora["dropout"]),
        lora_target_modules=tuple(lora["target_modules"]),
        embed_lora_rank=int(lora["embed_lora_rank"]),
        head_hidden_dim=int(cfg["model"]["head"]["hidden_dim"]),
        head_dropout=float(cfg["model"]["head"]["dropout"]),
        head_init_std=float(cfg["model"]["head"]["init_std"]),
        torch_dtype=_resolve_dtype(cfg["train"]["precision"]),
        gradient_checkpointing=False,
    ).to(device)

    if args.ckpt_dir is not None:
        print(f"loading ckpt: {args.ckpt_dir}", flush=True)
        model.load_trainable(args.ckpt_dir)
    else:
        print("WARN: no --ckpt-dir; UNTRAINED head", flush=True)

    lse_t_end = float(cfg["model"]["lse"]["temp_end"])
    records, metrics = run_eval(
        model, held_ex, tokenizer,
        max_length=int(cfg["data"]["max_seq_len"]),
        batch_size=args.batch_size,
        lse_temperature=lse_t_end,
        device=device,
    )
    print(
        f"auroc={metrics.whole_impl_auroc} top1={metrics.per_line_top1_recall} "
        f"top3={metrics.per_line_top3_recall} rank_acc={metrics.within_spec_ranking_accuracy} "
        f"n={metrics.n_impls}",
        flush=True,
    )

    # Build impl_id -> (source, impl_text, scorable_line_texts) lookup.
    # scorable_line_texts is aligned with sentinel positions (and therefore with
    # per_line_energies / buggy_line_indices) -- modulo truncation which we
    # accept and reflect by zipping to min length.
    impl_lookup: dict[str, dict] = {}
    for ex in held_ex:
        all_lines = ex.impl_text.splitlines()
        scorable = scorable_line_indices(ex.impl_text)
        scorable_texts = [all_lines[i] for i in scorable]
        impl_lookup[ex.impl_id] = {
            "source": ex.source.value if hasattr(ex.source, "value") else str(ex.source),
            "impl_text": ex.impl_text,
            "scorable_line_texts": scorable_texts,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_lines_truncated = 0
    with args.out.open("w") as f:
        for r in records:
            info = impl_lookup.get(r.impl_id, {})
            scorable_texts = info.get("scorable_line_texts", [])
            n_eval_lines = len(r.per_line_energies)
            if scorable_texts and len(scorable_texts) > n_eval_lines:
                n_lines_truncated += 1
            scorable_texts = scorable_texts[:n_eval_lines]
            f.write(json.dumps({
                "impl_id": r.impl_id,
                "spec_id": r.spec_id,
                "source": info.get("source"),
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "whole_impl_energy": r.whole_impl_energy,
                "per_line_energies": r.per_line_energies,
                "buggy_line_indices": r.buggy_line_indices,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
    print(f"wrote {len(records)} -> {args.out}  ({n_lines_truncated} impls had source-line text truncated by tokenizer max_len)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
