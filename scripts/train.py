"""Training CLI entrypoint.

Usage:
    uv run python scripts/train.py --config configs/default.yaml

This is the GPU-side entrypoint. It:
  1. Loads config
  2. Streams the two raw datasets into Examples
  3. Splits spec-disjoint train/eval
  4. Loads the Qwen backbone + builds the EnergyScorer
  5. Initializes wandb if available
  6. Runs the training loop
  7. Catches StopPointTriggered cleanly so the orchestrator can pivot
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import torch
import yaml

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data import load_all, split_examples
from ebm_verus.model.scorer import EnergyScorer
from ebm_verus.training import StopPointTriggered, TrainConfig, train


def _resolve_dtype(precision: str) -> torch.dtype:
    return {
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }[precision]


def _build_train_config(cfg: dict) -> TrainConfig:
    t = cfg["train"]
    lse = cfg["model"]["lse"]
    # Hard guard: the sampler truncates to micro_batch * grad_accum. If that's
    # smaller than 3*min_traj_triples + 2*min_safe_pairs, the batch will silently
    # drop the contrastive groups and BOTH losses will collapse to 0.
    examples_per_batch = int(t["micro_batch_size"]) * int(t["grad_accum"])
    needed = 3 * int(t["batch_min_traj_triples"]) + 2 * int(t["batch_min_safe_pairs"])
    if examples_per_batch < needed:
        raise ValueError(
            f"batch shape too small: micro_batch * grad_accum = {examples_per_batch} "
            f"but need >= {needed} to fit "
            f"{t['batch_min_traj_triples']} traj triples (3 impls each) + "
            f"{t['batch_min_safe_pairs']} safe pairs (2 impls each). "
            f"Increase micro_batch_size or grad_accum, OR reduce batch_min_*."
        )
    return TrainConfig(
        lr=float(t["lr"]),
        betas=tuple(t["betas"]),
        weight_decay=float(t["weight_decay"]),
        warmup_frac=float(t["warmup_frac"]),
        cosine_end_frac=float(t["cosine_end_frac"]),
        epochs=int(t["epochs"]),
        micro_batch_size=int(t["micro_batch_size"]),
        grad_accum=int(t["grad_accum"]),
        max_length=int(cfg["data"]["max_seq_len"]),
        examples_per_batch_target=int(t["micro_batch_size"]) * int(t["grad_accum"]),
        lambda_spec=float(t["loss_weights"]["spec"]),
        lambda_line=float(t["loss_weights"]["line"]),
        line_margin=float(t["line_loss"]["margin"]),
        pairs_per_impl=4,
        lse_temp_start=float(lse["temp_start"]),
        lse_temp_end=float(lse["temp_end"]),
        batch_min_traj_triples=int(t["batch_min_traj_triples"]),
        batch_min_safe_pairs=int(t["batch_min_safe_pairs"]),
        eval_every_n_steps=int(cfg["eval"]["every_n_steps"]),
        stop_point_min_steps=int(t["stop_point"]["min_train_steps_before_check"]),
        stop_point_loss_window=int(t["stop_point"]["loss_plateau_window"]),
        stop_point_min_eval_auroc_epoch_1=float(t["stop_point"]["min_eval_auroc_epoch_1"]),
        log_every=int(cfg["logging"]["log_every"]),
        seed=int(cfg["data"]["split"]["seed"]),
        checkpoint_dir=cfg.get("checkpoint", {}).get("dir"),
        loss_mode=str(t.get("loss_mode", "contrastive")),
        bce_pos_weight=float(t.get("bce_pos_weight", 10.0)),
        marker_aug_k=int(t.get("marker_aug_k", 1)),
        marker_aug_prob=float(t.get("marker_aug_prob", 0.5)),
        marker_aug_positive_prob=float(t.get("marker_aug_positive_prob", 0.3)),
        marker_aug_mode=str(t.get("marker_aug_mode", "v6")),
        lambda_scalar=float(t.get("lambda_scalar", 1.0)),
        lambda_listwise=float(t.get("lambda_listwise", 1.0)),
        lambda_pairwise=float(t.get("lambda_pairwise", 0.3)),
        listwise_label_smoothing=float(t.get("listwise_label_smoothing", 0.05)),
        semi_hard_k=int(t.get("semi_hard_k", 3)),
        impl_pair_loss=str(t.get("impl_pair_loss", "logistic")),
        listwise_loss=str(t.get("listwise_loss", "listnet")),
        focal_gamma=float(t.get("focal_gamma", 0.0)),
        focal_balance=bool(t.get("focal_balance", False)),
        epa_weak_weight=float(t.get("epa_weak_weight", 0.2)),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--no-wandb", action="store_true")
    parser.add_argument("--device", default=None,
                        help="Override device (default: cuda if available else cpu)")
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Cap total training steps regardless of epochs (sanity runs)")
    parser.add_argument("--resume", type=Path, default=None,
                        help="Resume from a saved checkpoint dir (adapter/ + head.pt). "
                             "Loads LoRA + head weights into the freshly-built model before training.")
    parser.add_argument("--embed-surgery", action="store_true",
                        help="Before training, replace input-embedding rows for FAILS/fails/FAIL "
                             "tokens with the mean of neutral comment-token embeddings. Used in "
                             "run #9 to remove the Qwen pretraining-prior leak.")
    args = parser.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_str)
    print(f"device: {device}", flush=True)

    # ---- data
    print("loading raw datasets ...", flush=True)
    examples = load_all(
        system_trajectory_path=cfg["data"]["system_trajectory_path"],
        sft_safe_path=cfg["data"]["sft_safe_path"],
        max_diff_lines=int(cfg["data"]["max_diff_lines"]),
        extra_trajectory_paths=cfg["data"].get("extra_trajectory_paths") or None,
        extra_sft_paths=cfg["data"].get("extra_sft_paths") or None,
    )
    print(f"  loaded {len(examples)} examples", flush=True)
    train_ex, held_ex = split_examples(
        examples,
        n_eval_traj_specs=int(cfg["data"]["split"]["n_eval_specs"]),
        sft_eval_frac=float(cfg["data"]["split"]["sft_eval_frac"]),
        seed=int(cfg["data"]["split"]["seed"]),
    )
    print(f"  split: train={len(train_ex)} held_out={len(held_ex)}", flush=True)

    # ---- model
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    sentinel = cfg["model"].get("sentinel_token", SENTINEL_TOKEN)
    sid = tokenizer.encode(sentinel, add_special_tokens=False)
    assert len(sid) == 1, f"sentinel {sentinel!r} not a single token: {sid}"
    print(f"sentinel: {sentinel!r} -> id {sid[0]}", flush=True)

    print("building scorer ...", flush=True)
    lora_cfg = cfg["model"]["lora"]
    use_scalar_head = (cfg["train"].get("loss_mode") == "hybrid")
    model = EnergyScorer(
        backbone_name=cfg["model"]["backbone"],
        lora_rank=int(lora_cfg["rank"]),
        lora_alpha=int(lora_cfg["alpha"]),
        lora_dropout=float(lora_cfg["dropout"]),
        lora_target_modules=tuple(lora_cfg["target_modules"]),
        embed_lora_rank=int(lora_cfg["embed_lora_rank"]),
        head_hidden_dim=int(cfg["model"]["head"]["hidden_dim"]),
        head_dropout=float(cfg["model"]["head"]["dropout"]),
        head_init_std=float(cfg["model"]["head"]["init_std"]),
        torch_dtype=_resolve_dtype(cfg["train"]["precision"]),
        gradient_checkpointing=bool(cfg["train"]["gradient_checkpointing"]),
        scalar_head=use_scalar_head,
    ).to(device)
    print(
        f"  trainable params: {model.trainable_parameter_count():,} "
        f"/ total {model.total_parameter_count():,}",
        flush=True,
    )

    if args.resume is not None:
        print(f"  resuming from checkpoint: {args.resume}", flush=True)
        model.load_trainable(args.resume)
        print(f"  checkpoint loaded.", flush=True)

    if args.embed_surgery:
        # Replace input-embedding rows for FAILS/fails/FAIL with the mean of
        # neutral comment-token embeddings. This kills the Qwen pretraining-prior
        # leak at the source before any further training.
        marker_strings = ["FAILS", "fails", "FAIL"]
        neutral_strings = ["// ok", "// note", "// here", "// impl", "// proof", "// let"]
        marker_ids, neutral_ids = set(), set()
        for s in marker_strings:
            for v in (s, " " + s):
                marker_ids.update(tokenizer.encode(v, add_special_tokens=False))
        for s in neutral_strings:
            for v in (s, " " + s):
                neutral_ids.update(tokenizer.encode(v, add_special_tokens=False))
        base_emb = model.backbone.get_input_embeddings()
        weight = getattr(base_emb, "base_layer", base_emb).weight
        with torch.no_grad():
            neutral_vec = weight[sorted(neutral_ids)].mean(dim=0)
            for tid in sorted(marker_ids):
                weight[tid] = neutral_vec
        print(f"  embed-surgery: replaced {len(marker_ids)} marker rows "
              f"with mean of {len(neutral_ids)} neutral rows.", flush=True)
        print(f"  marker IDs: {sorted(marker_ids)}", flush=True)

    # ---- wandb
    wandb_run = None
    if not args.no_wandb:
        try:
            import wandb
            wandb_run = wandb.init(
                project=cfg["logging"]["wandb_project"],
                config=cfg,
                dir=os.environ.get("WANDB_DIR", "wandb"),
            )
        except Exception as e:
            print(f"wandb disabled: {e}", flush=True)

    train_cfg = _build_train_config(cfg)
    if args.max_steps is not None:
        train_cfg.max_steps = args.max_steps
        print(f"  max_steps override: {args.max_steps}", flush=True)
    try:
        train(
            model=model,
            tokenizer=tokenizer,
            train_examples=train_ex,
            eval_examples=held_ex,
            config=train_cfg,
            device=device,
            wandb_run=wandb_run,
        )
    except StopPointTriggered as e:
        print(f"\n!! STOP-POINT TRIGGERED !!\n{e}", file=sys.stderr, flush=True)
        if wandb_run is not None:
            wandb_run.summary["stop_point_triggered"] = True
            wandb_run.summary["stop_point_message"] = str(e)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
