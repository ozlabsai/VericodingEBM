"""Eval loop: run the scorer over a list of Examples and collect EvalRecords."""

from __future__ import annotations

import torch
from transformers import PreTrainedTokenizerBase

from ebm_verus.data.dataset import make_collate_fn
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, TokenizedExample
from ebm_verus.eval.metrics import EvalRecord, compute_eval_metrics, EvalMetrics
from ebm_verus.model.scorer import EnergyScorer


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


@torch.no_grad()
def run_eval(
    model: EnergyScorer,
    examples: list[Example],
    tokenizer: PreTrainedTokenizerBase,
    *,
    max_length: int,
    batch_size: int,
    lse_temperature: float,
    device: torch.device,
) -> tuple[list[EvalRecord], EvalMetrics]:
    """Run model in inference mode over examples; return per-impl records + summary."""
    was_training = model.training
    model.eval()
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    collate = make_collate_fn(pad_id)

    tokenized: list[TokenizedExample] = []
    for ex in examples:
        t = tokenize_example(ex, tokenizer, max_length=max_length)
        if t is not None:
            tokenized.append(t)

    records: list[EvalRecord] = []
    for chunk in _chunks(tokenized, batch_size):
        batch = collate(chunk)
        input_ids = batch.input_ids.to(device)
        attn = batch.attention_mask.to(device)
        sent_pos = [s.to(device) for s in batch.sentinel_positions]
        out = model(
            input_ids, attn, sent_pos, lse_temperature=lse_temperature
        )
        whole = out.whole_impl_energies.float().cpu().tolist()
        for i, item in enumerate(chunk):
            per_line = out.per_line_energies[i].float().cpu().tolist()
            records.append(
                EvalRecord(
                    impl_id=item.example.impl_id,
                    spec_id=item.example.spec_id,
                    status=item.example.status,
                    whole_impl_energy=whole[i],
                    per_line_energies=per_line,
                    buggy_line_indices=sorted(item.buggy_line_indices),
                )
            )

    metrics = compute_eval_metrics(records)
    if was_training:
        model.train()
    return records, metrics
