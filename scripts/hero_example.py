"""Hero example: render a per-line heatmap for a hand-crafted buggy Verus impl.

This is the PLAN section 7.1 deliverable. We pick a famous off-by-one bug
(binary search returns wrong index when the target is at the last position)
and render the trained model's per-line energy as a heatmap.

Usage:
    uv run python scripts/hero_example.py \
        --config configs/default.yaml \
        --ckpt-dir checkpoints/run/final \
        --out-html artifacts/hero.html \
        --out-text artifacts/hero.txt

Without --ckpt-dir the model is untrained (sanity check that the viz pipeline
works; energies will be near-uniform garbage).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import yaml

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data.line_policy import scorable_line_indices, split_spec_impl
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer
from ebm_verus.viz.heatmap import HeatmapInput, render_html, render_text


# Hand-crafted Verus binary search with an off-by-one error.
# The spec says it returns the index of `target` in a sorted slice, or
# len if not present. The bug: the loop initializes `hi = arr.len() - 1`
# (off by one — should be `arr.len()`), and the comparison `lo < hi`
# loses the last index. Correct version commented inline.
HERO_VERUS = r"""
use vstd::prelude::*;

verus! {

fn binary_search(arr: &Vec<u64>, target: u64) -> (result: usize)
    requires
        forall|i: int, j: int| 0 <= i < j < arr.len() ==> arr[i] <= arr[j],
    ensures
        result == arr.len() || (result < arr.len() && arr[result as int] == target),
{
    let mut lo: usize = 0;
    let mut hi: usize = arr.len() - 1;             // BUG: should be arr.len()
    while lo < hi                                  // BUG: should be lo < hi without -1 above, or lo < hi with hi = arr.len()
        invariant
            0 <= lo <= hi <= arr.len(),
            forall|i: int| 0 <= i < lo ==> arr[i] < target,
            forall|i: int| hi <= i < arr.len() ==> arr[i] > target,
        decreases hi - lo,
    {
        let mid: usize = lo + (hi - lo) / 2;
        if arr[mid] == target {
            return mid;
        } else if arr[mid] < target {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return arr.len();
}

} // verus!
""".strip()


def _resolve_dtype(precision: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", type=Path, default=None)
    ap.add_argument("--out-html", type=Path, default=Path("artifacts/hero.html"))
    ap.add_argument("--out-text", type=Path, default=Path("artifacts/hero.txt"))
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

    spec_text, impl_text = split_spec_impl(HERO_VERUS)
    if not impl_text.strip():
        print("FATAL: hero impl is empty after split_spec_impl", file=sys.stderr)
        return 1

    ex = Example(
        source=Source.SFT_SAFE,  # arbitrary; only needed for typing
        spec_id="hero-binsearch",
        impl_id="hero-binsearch-broken",
        spec_text=spec_text,
        impl_text=impl_text,
        status=Status.FAIL,
        buggy_lines=set(),  # we'll let the model speak; this is hand-crafted
    )

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    t = tokenize_example(ex, tokenizer, max_length=int(cfg["data"]["max_seq_len"]))
    if t is None:
        print("FATAL: tokenize_example returned None", file=sys.stderr)
        return 1

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
        model.load_trainable(args.ckpt_dir)
    model.eval()

    input_ids = torch.tensor([t.input_ids], device=device)
    attn = torch.ones_like(input_ids)
    sent_pos = [torch.tensor(t.sentinel_positions, device=device)]
    with torch.no_grad():
        out = model(input_ids, attn, sent_pos, lse_temperature=float(cfg["model"]["lse"]["temp_end"]))
    energies = out.per_line_energies[0].float().cpu().tolist()
    whole = float(out.whole_impl_energies[0].float().cpu().item())

    all_lines = ex.impl_text.splitlines()
    scorable_ix = scorable_line_indices(ex.impl_text)
    scorable_texts = [all_lines[i] for i in scorable_ix][: len(energies)]
    print(f"whole_impl_energy = {whole:.4f}")
    print(f"per_line: n={len(energies)}")
    for i, (line, e) in enumerate(zip(scorable_texts, energies)):
        print(f"  {i:3d} E={e:+.3f}  {line}")

    h = HeatmapInput(
        spec_text=ex.spec_text,
        scorable_lines=scorable_texts,
        per_line_energies=energies,
        buggy_line_indices=[],
        title=f"Binary search with off-by-one (whole-impl E = {whole:+.3f})",
    )
    args.out_html.parent.mkdir(parents=True, exist_ok=True)
    args.out_html.write_text(render_html(h))
    args.out_text.write_text(render_text(h))
    print(f"wrote {args.out_html}, {args.out_text}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
