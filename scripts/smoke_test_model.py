"""Smoke-test the model forward+backward path without loading the real Qwen.

Constructs a tiny fake backbone with random weights that has the right interface
(an embedding + a few transformer layers) and runs an end-to-end step:
  data -> tokenize -> collate -> forward -> losses -> backward -> step

Useful for catching wiring bugs (shape mismatches, missing .to(device), grad
flow breaks) before spending GPU time on Qwen. Runs on CPU in ~30s.

Usage:
    uv run python scripts/smoke_test_model.py
"""

from __future__ import annotations

import sys

import torch
import torch.nn as nn
from torch.optim import AdamW
from transformers import AutoTokenizer

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data import (
    Example,
    Source,
    Status,
    make_collate_fn,
    tokenize_example,
)
from ebm_verus.model.head import PerLineEnergyHead, normalized_lse
from ebm_verus.training.losses import compute_loss


class _TinyBackbone(nn.Module):
    """Random-init micro-transformer with the same interface signature as Qwen.

    Just enough to produce (B, L, D) hidden states from input_ids.
    """

    def __init__(self, vocab_size: int, hidden_size: int = 64, n_layers: int = 2) -> None:
        super().__init__()
        self.embed = nn.Embedding(vocab_size, hidden_size)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=4,
            dim_feedforward=128,
            dropout=0.0,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=n_layers)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        h = self.embed(input_ids)
        # turn HF-style mask (1=keep) into a key_padding_mask (True=ignore)
        kp = (attention_mask == 0)
        h = self.encoder(h, src_key_padding_mask=kp)
        return h


class _MiniScorer(nn.Module):
    """Mimics EnergyScorer's interface but uses a tiny CPU-only backbone."""

    def __init__(self, vocab_size: int, hidden_size: int = 64) -> None:
        super().__init__()
        self.backbone = _TinyBackbone(vocab_size, hidden_size)
        self.head = PerLineEnergyHead(in_dim=hidden_size, hidden_dim=32, dropout=0.0)

    def forward(self, input_ids, attention_mask, sentinel_positions, *, lse_temperature):
        hidden = self.backbone(input_ids, attention_mask)
        per_line = []
        whole_impl = []
        for b, sp in enumerate(sentinel_positions):
            if sp.numel() == 0:
                per_line.append(hidden.new_zeros((0,)))
                whole_impl.append(hidden.new_zeros(()))
                continue
            h = hidden[b].index_select(0, sp.to(hidden.device))
            e = self.head(h.float())
            per_line.append(e)
            whole_impl.append(normalized_lse(e, lse_temperature))

        from ebm_verus.model.scorer import ScorerOutput
        return ScorerOutput(
            per_line_energies=per_line,
            whole_impl_energies=torch.stack(whole_impl),
        )


def _make_synthetic_examples() -> list[Example]:
    """Two specs, mixed-label, plus one sft_safe (broken, fixed) pair."""
    spec1 = (
        "use vstd::prelude::*;\n"
        "verus! {\n"
        "fn add_one(n: u32) -> (r: u32)\n"
        "    requires n < 1000,\n"
        "    ensures r == n + 1,\n"
        "{\n"
    )
    impl_pass = "    n + 1\n}\n"
    impl_fail = "    n + 2\n}\n"  # wrong!

    ex_pass = Example(
        source=Source.SYSTEM_TRAJECTORY, spec_id="s1", impl_id="s1-rep0",
        spec_text=spec1, impl_text=impl_pass, status=Status.PASS,
        buggy_lines=set(), rep_index=0,
    )
    ex_fail = Example(
        source=Source.SYSTEM_TRAJECTORY, spec_id="s1", impl_id="s1-rep1",
        spec_text=spec1, impl_text=impl_fail, status=Status.FAIL,
        buggy_lines=set(), rep_index=1,
    )

    spec2 = (
        "fn double(n: u32) -> (r: u32)\n"
        "    requires n < 100,\n"
        "    ensures r == n * 2,\n"
        "{\n"
    )
    impl_broken = "    n + n\n    let x = 0;\n}\n"   # extra line, line 1 buggy
    impl_fixed  = "    n * 2\n    let x = 0;\n}\n"
    ex_broken = Example(
        source=Source.SFT_SAFE, spec_id="s2", impl_id="s2-broken",
        spec_text=spec2, impl_text=impl_broken, status=Status.FAIL,
        buggy_lines={0}, sibling_impl_id="s2-fixed",
    )
    ex_fixed = Example(
        source=Source.SFT_SAFE, spec_id="s2", impl_id="s2-fixed",
        spec_text=spec2, impl_text=impl_fixed, status=Status.PASS,
        buggy_lines=set(), sibling_impl_id="s2-broken",
    )

    return [ex_pass, ex_fail, ex_broken, ex_fixed]


def main() -> int:
    print("=" * 64)
    print("smoke-test: model forward+backward path (CPU, fake backbone)")
    print("=" * 64)

    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B")
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    sid = tokenizer.encode(SENTINEL_TOKEN, add_special_tokens=False)
    assert len(sid) == 1
    print(f"  sentinel id: {sid[0]}, vocab_size: {tokenizer.vocab_size}")

    examples = _make_synthetic_examples()
    tokenized = []
    for ex in examples:
        t = tokenize_example(ex, tokenizer, max_length=512)
        if t is None:
            print(f"  !! tokenize_example dropped {ex.impl_id}")
            return 2
        tokenized.append(t)
        print(f"  tokenized {ex.impl_id}: "
              f"len={len(t.input_ids)} sentinels={len(t.sentinel_positions)} "
              f"buggy_idx={sorted(t.buggy_line_indices)}")

    collate = make_collate_fn(pad_id)
    batch = collate(tokenized)
    print(f"  collated batch: input_ids {tuple(batch.input_ids.shape)} "
          f"traj_triples={batch.traj_triples} "
          f"safe_broken={batch.safe_broken_indices}")

    # Build the mini-scorer with same vocab as Qwen (so embedding indices align).
    vocab_size = len(tokenizer) if hasattr(tokenizer, "__len__") else tokenizer.vocab_size
    # Use a slightly larger size to include added tokens.
    vocab_size = max(vocab_size, sid[0] + 1)
    model = _MiniScorer(vocab_size=vocab_size, hidden_size=64)
    optim = AdamW(model.parameters(), lr=1e-3)

    print()
    print("  running 3 forward+backward steps ...")
    rng = torch.Generator().manual_seed(0)
    for step in range(3):
        optim.zero_grad(set_to_none=True)
        out = model(
            batch.input_ids, batch.attention_mask, batch.sentinel_positions,
            lse_temperature=1.5,
        )
        loss = compute_loss(
            batch, out,
            lambda_spec=1.0, lambda_line=1.0, line_margin=1.0,
            pairs_per_impl=4, rng=rng,
        )
        loss.total.backward()
        # Confirm gradient actually reached the backbone.
        embed_grad = model.backbone.embed.weight.grad
        embed_grad_norm = embed_grad.norm().item() if embed_grad is not None else 0.0
        head_grad = model.head.fc2.weight.grad
        head_grad_norm = head_grad.norm().item() if head_grad is not None else 0.0
        print(
            f"  step={step} "
            f"loss={loss.total.item():.4f} "
            f"spec={loss.spec.item():.4f} "
            f"line={loss.line.item():.4f} "
            f"n_spec={loss.n_spec_groups} n_pairs={loss.n_line_pairs} "
            f"|grad_embed|={embed_grad_norm:.3e} "
            f"|grad_head|={head_grad_norm:.3e}"
        )
        if embed_grad_norm == 0:
            print("  !! zero gradient on backbone embeddings — wiring is broken")
            return 3
        if head_grad_norm == 0:
            print("  !! zero gradient on head — wiring is broken")
            return 3
        optim.step()

    print()
    print("=" * 64)
    print("model smoke-test PASSED — wiring is healthy")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
