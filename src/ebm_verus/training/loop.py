"""Training loop: bf16 + LoRA + cosine-warmup + LSE temp anneal + stop-point."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import PreTrainedTokenizerBase

from ebm_verus.data.dataset import (
    Batch,
    MixedSourceIterableDataset,
    make_collate_fn,
)
from ebm_verus.data.types import Example
from ebm_verus.eval.loop import run_eval
from ebm_verus.eval.metrics import EvalMetrics
from ebm_verus.model.head import lse_temperature_schedule
from ebm_verus.model.scorer import EnergyScorer
from ebm_verus.training.losses import (
    LossOutput,
    compute_bce_loss,
    compute_hybrid_loss,
    compute_loss,
    compute_orm_loss,
)


class StopPointTriggered(RuntimeError):
    """Raised when the Friday-midnight stop-point condition is met."""


@dataclass
class TrainConfig:
    lr: float
    betas: tuple[float, float]
    weight_decay: float
    warmup_frac: float
    cosine_end_frac: float

    epochs: int
    micro_batch_size: int
    grad_accum: int
    max_length: int
    examples_per_batch_target: int

    lambda_spec: float
    lambda_line: float
    line_margin: float
    pairs_per_impl: int

    lse_temp_start: float
    lse_temp_end: float

    batch_min_traj_triples: int
    batch_min_safe_pairs: int

    eval_every_n_steps: int

    stop_point_min_steps: int
    stop_point_loss_window: int
    stop_point_min_eval_auroc_epoch_1: float

    log_every: int
    seed: int

    # Optional: cap total steps regardless of epochs (for sanity runs).
    max_steps: int | None = None

    # Counterfactual marker augmentation (V6 fix for // FAIL leak).
    # k=1 disables; k=4 means 1 original + 3 marker-perturbed copies per Example.
    marker_aug_k: int = 1
    marker_aug_prob: float = 0.5
    marker_aug_positive_prob: float = 0.3
    marker_aug_mode: str = "v6"

    # Where to dump LoRA + head state. None disables checkpointing.
    # Saves at end of run and once per eval (overwrites "latest.pt").
    checkpoint_dir: str | None = None

    # Ablation mode. "contrastive" = default (L_spec + L_line). "bce" = pointwise
    # BCE on per-line buggy labels (E7 ablation for the EBM-framing claim).
    # "hybrid" = run #10 Alt A+/v2: scalar impl-pair hinge + per-line listwise CE
    # + per-line semi-hard pairwise hinge. Requires scorer with scalar_head=True.
    loss_mode: str = "contrastive"
    bce_pos_weight: float = 10.0

    # Hybrid (run #10) loss weights.
    lambda_scalar: float = 1.0
    lambda_listwise: float = 1.0
    lambda_pairwise: float = 0.3
    listwise_label_smoothing: float = 0.05
    semi_hard_k: int = 3
    # A4 ablation: "logistic" (run #10 default) | "hinge" (revert to pre-fix).
    impl_pair_loss: str = "logistic"
    # Run #11 knobs.
    listwise_loss: str = "listnet"     # "listnet" (default) | "listmle"
    focal_gamma: float = 0.0           # >0 applies focal modulator on listwise CE
    focal_balance: bool = False        # divide listwise loss by sqrt(n_buggy) per impl
    epa_weak_weight: float = 0.2       # only used if impl_pair_loss == "epa"


def _make_schedule(
    optimizer: torch.optim.Optimizer,
    *,
    total_steps: int,
    warmup_frac: float,
    cosine_end_frac: float,
) -> torch.optim.lr_scheduler.LambdaLR:
    warmup_steps = max(1, int(warmup_frac * total_steps))

    def lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        progress = min(1.0, max(0.0, progress))
        return cosine_end_frac + (1.0 - cosine_end_frac) * 0.5 * (1.0 + math.cos(math.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def _trainable_params(model: torch.nn.Module) -> list[torch.nn.Parameter]:
    return [p for p in model.parameters() if p.requires_grad]


def train(
    model: EnergyScorer,
    tokenizer: PreTrainedTokenizerBase,
    train_examples: list[Example],
    eval_examples: list[Example],
    config: TrainConfig,
    *,
    device: torch.device,
    wandb_run=None,
) -> None:
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    collate = make_collate_fn(pad_id)

    dataset = MixedSourceIterableDataset(
        train_examples,
        tokenizer,
        batch_size=config.examples_per_batch_target,
        min_traj_triples=config.batch_min_traj_triples,
        min_safe_pairs=config.batch_min_safe_pairs,
        max_length=config.max_length,
        seed=config.seed,
        marker_aug_k=getattr(config, "marker_aug_k", 1),
        marker_aug_prob=getattr(config, "marker_aug_prob", 0.5),
        marker_aug_positive_prob=getattr(config, "marker_aug_positive_prob", 0.3),
        marker_aug_mode=getattr(config, "marker_aug_mode", "v6"),
    )

    loader = DataLoader(
        dataset,
        batch_size=None,
        collate_fn=lambda items: items,
        num_workers=0,
    )

    optimizer = AdamW(
        _trainable_params(model),
        lr=config.lr,
        betas=config.betas,
        weight_decay=config.weight_decay,
    )

    steps_per_epoch = max(1, len(train_examples) // config.examples_per_batch_target)
    total_steps = config.epochs * steps_per_epoch
    if config.max_steps is not None:
        total_steps = min(total_steps, config.max_steps)
    scheduler = _make_schedule(
        optimizer,
        total_steps=total_steps,
        warmup_frac=config.warmup_frac,
        cosine_end_frac=config.cosine_end_frac,
    )

    rng = torch.Generator().manual_seed(config.seed)

    step = 0
    loss_window: deque[float] = deque(maxlen=config.stop_point_loss_window)
    epoch_eval_auroc: float | None = None

    model.train()
    for epoch in range(config.epochs):
        if config.max_steps is not None and step >= config.max_steps:
            break
        dataset.set_epoch(epoch)
        loader_iter = iter(loader)
        for _ in range(steps_per_epoch):
            if config.max_steps is not None and step >= config.max_steps:
                break
            try:
                tokenized = next(loader_iter)
            except StopIteration:
                break

            micro_chunks = [
                tokenized[i : i + config.micro_batch_size]
                for i in range(0, len(tokenized), config.micro_batch_size)
            ]
            optimizer.zero_grad(set_to_none=True)
            accumulated: list[LossOutput] = []
            for micro in micro_chunks:
                if not micro:
                    continue
                batch: Batch = collate(micro)
                input_ids = batch.input_ids.to(device)
                attn = batch.attention_mask.to(device)
                sent_pos = [s.to(device) for s in batch.sentinel_positions]
                batch.buggy_line_indices = [b.to(device) for b in batch.buggy_line_indices]

                lse_t = lse_temperature_schedule(
                    step, total_steps, config.lse_temp_start, config.lse_temp_end
                )
                out = model(input_ids, attn, sent_pos, lse_temperature=lse_t)
                if config.loss_mode == "bce":
                    loss_out = compute_bce_loss(
                        batch, out, pos_weight=config.bce_pos_weight,
                    )
                elif config.loss_mode == "orm":
                    loss_out = compute_orm_loss(
                        batch, out, pos_weight=config.bce_pos_weight,
                    )
                elif config.loss_mode == "hybrid":
                    loss_out = compute_hybrid_loss(
                        batch, out,
                        lambda_scalar=config.lambda_scalar,
                        lambda_listwise=config.lambda_listwise,
                        lambda_pairwise=config.lambda_pairwise,
                        line_margin=config.line_margin,
                        listwise_label_smoothing=config.listwise_label_smoothing,
                        semi_hard_k=config.semi_hard_k,
                        impl_pair_loss=config.impl_pair_loss,
                        listwise_loss=config.listwise_loss,
                        focal_gamma=config.focal_gamma,
                        focal_balance=config.focal_balance,
                        epa_weak_weight=config.epa_weak_weight,
                        rng=rng,
                    )
                else:
                    loss_out = compute_loss(
                        batch, out,
                        lambda_spec=config.lambda_spec,
                        lambda_line=config.lambda_line,
                        line_margin=config.line_margin,
                        pairs_per_impl=config.pairs_per_impl,
                        rng=rng,
                    )
                (loss_out.total / max(1, len(micro_chunks))).backward()
                accumulated.append(loss_out)

            torch.nn.utils.clip_grad_norm_(_trainable_params(model), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            total_loss = sum(l.total.detach().float().item() for l in accumulated) / max(1, len(accumulated))
            spec_loss = sum(l.spec.float().item() for l in accumulated) / max(1, len(accumulated))
            line_loss = sum(l.line.float().item() for l in accumulated) / max(1, len(accumulated))
            loss_window.append(total_loss)

            if step % config.log_every == 0:
                print(
                    f"step={step:>6d} epoch={epoch} "
                    f"loss={total_loss:.4f} spec={spec_loss:.4f} line={line_loss:.4f} "
                    f"lse_T={lse_t:.3f} lr={scheduler.get_last_lr()[0]:.2e}",
                    flush=True,
                )
                if wandb_run is not None:
                    wandb_run.log({
                        "train/loss": total_loss,
                        "train/loss_spec": spec_loss,
                        "train/loss_line": line_loss,
                        "train/lse_temperature": lse_t,
                        "train/lr": scheduler.get_last_lr()[0],
                        "train/step": step,
                        "train/epoch": epoch,
                    }, step=step)

            step += 1

            if step > 0 and step % config.eval_every_n_steps == 0:
                metrics = _do_eval(
                    model, tokenizer, eval_examples, config, device,
                    lse_temperature=lse_temperature_schedule(
                        step, total_steps, config.lse_temp_start, config.lse_temp_end
                    ),
                    wandb_run=wandb_run, step=step,
                )
                if epoch == 0:
                    epoch_eval_auroc = metrics.whole_impl_auroc
                if config.checkpoint_dir is not None:
                    try:
                        model.save_trainable(f"{config.checkpoint_dir}/latest")
                        print(f"  [ckpt] saved latest @ step={step}", flush=True)
                    except Exception as e:
                        print(f"  [ckpt] save failed @ step={step}: {e}", flush=True)

        # End-of-epoch evaluation.
        metrics = _do_eval(
            model, tokenizer, eval_examples, config, device,
            lse_temperature=lse_temperature_schedule(
                step, total_steps, config.lse_temp_start, config.lse_temp_end
            ),
            wandb_run=wandb_run, step=step,
        )
        if epoch == 0:
            epoch_eval_auroc = metrics.whole_impl_auroc

        if epoch == 0 and step >= config.stop_point_min_steps:
            if len(loss_window) >= config.stop_point_loss_window:
                w = list(loss_window)
                first_half = sum(w[: len(w) // 2]) / max(1, len(w) // 2)
                second_half = sum(w[len(w) // 2 :]) / max(1, len(w) - len(w) // 2)
                loss_not_decreasing = second_half >= first_half * 0.98
                auroc_too_low = (
                    epoch_eval_auroc is not None
                    and epoch_eval_auroc < config.stop_point_min_eval_auroc_epoch_1
                )
                if loss_not_decreasing and auroc_too_low:
                    raise StopPointTriggered(
                        f"Stop-point triggered after epoch 1: "
                        f"loss_window first_half={first_half:.4f} "
                        f"second_half={second_half:.4f}, "
                        f"epoch_1 AUROC={epoch_eval_auroc:.4f} "
                        f"(threshold={config.stop_point_min_eval_auroc_epoch_1}). "
                        "Consider BCE fallback per PLAN.md cut-order #7."
                    )

    # Final save (best-effort; don't crash the run if disk full / permission).
    if config.checkpoint_dir is not None:
        try:
            model.save_trainable(f"{config.checkpoint_dir}/final")
            print(f"  [ckpt] saved final @ step={step}", flush=True)
        except Exception as e:
            print(f"  [ckpt] final save failed: {e}", flush=True)


def _do_eval(
    model, tokenizer, examples, config, device, *, lse_temperature, wandb_run, step
) -> EvalMetrics:
    t0 = time.time()
    _records, metrics = run_eval(
        model, examples, tokenizer,
        max_length=config.max_length,
        batch_size=config.micro_batch_size,
        lse_temperature=lse_temperature,
        device=device,
    )
    dt = time.time() - t0
    print(
        f"  [eval @ step={step}] auroc={metrics.whole_impl_auroc!r} "
        f"top1={metrics.per_line_top1_recall!r} top3={metrics.per_line_top3_recall!r} "
        f"rank_acc={metrics.within_spec_ranking_accuracy!r} "
        f"n={metrics.n_impls} ({dt:.1f}s)",
        flush=True,
    )
    if wandb_run is not None:
        wandb_run.log({
            "eval/auroc": metrics.whole_impl_auroc,
            "eval/per_line_top1": metrics.per_line_top1_recall,
            "eval/per_line_top3": metrics.per_line_top3_recall,
            "eval/within_spec_ranking_acc": metrics.within_spec_ranking_accuracy,
            "eval/n_impls": metrics.n_impls,
            "eval/energy_mean_pass": metrics.energy_mean_pass,
            "eval/energy_mean_fail": metrics.energy_mean_fail,
            "eval/energy_std": metrics.energy_std,
            "eval/step": step,
        }, step=step)
    return metrics
