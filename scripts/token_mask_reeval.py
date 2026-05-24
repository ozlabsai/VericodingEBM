"""Embedding-surgery re-evaluation: zero out marker-token rows in input_embeddings.

Hypothesis: the // FAILS marker leak is mediated by specific Qwen-pretraining
token embeddings (FAILS/fails/FAIL). If we replace their input-embedding rows
with the mean of neutral comment tokens BEFORE scoring, we should:
  - Match strip-FAILS top-3 (~0.60) on the un-modified real-bug corpus,
    proving the leak was the marker embedding itself.
  - Possibly exceed strip-FAILS if the model has additional non-marker signal
    that strip-FAILS removes by deleting context.

Output records carry the same schema as strip_fails_reeval.py so analyze_records.py
works without modification.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import yaml

from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer


# The leak vocabulary actually observed in the real-bug corpus (audit at
# 2026-05-22): FAILS (970) + fails (21) + FAIL (6) account for ~99% of
# label-correlated comment markers. TODO (7) is too generic to risk.
MARKER_STRINGS = ["FAILS", "fails", "FAIL"]
# Neutral comment tokens we'll average over to construct the replacement embedding.
NEUTRAL_STRINGS = ["// ok", "// note", "// here", "// impl", "// proof", "// let"]


def _resolve_dtype(p: str) -> torch.dtype:
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[p]


def _status_from_str(s: str) -> Status:
    s = s.upper()
    if s.endswith("PASS") or s.endswith("OK"):
        return Status.PASS
    if s.endswith("FAIL") or s.endswith("ERR"):
        return Status.FAIL
    return Status.UNKNOWN


def _collect_token_ids(tok, strings: list[str]) -> set[int]:
    ids: set[int] = set()
    for s in strings:
        for variant in (s, " " + s):
            enc = tok.encode(variant, add_special_tokens=False)
            ids.update(enc)
    return ids


def _apply_embedding_surgery(model: EnergyScorer, tok) -> tuple[list[int], list[int]]:
    """Replace input-embedding rows for marker token IDs with the mean of neutral
    comment tokens. Returns (marker_ids, neutral_ids) for logging."""
    marker_ids = sorted(_collect_token_ids(tok, MARKER_STRINGS))
    neutral_ids = sorted(_collect_token_ids(tok, NEUTRAL_STRINGS))

    base_emb = model.backbone.get_input_embeddings()
    weight = getattr(base_emb, "base_layer", base_emb).weight

    with torch.no_grad():
        neutral_vec = weight[neutral_ids].mean(dim=0)
        for tid in marker_ids:
            weight[tid] = neutral_vec
    return marker_ids, neutral_ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", required=True, type=Path)
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

    raw = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    print(f"loaded {len(raw)} input records", flush=True)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tok.pad_token_id is None:
        tok.pad_token_id = tok.eos_token_id

    lora = cfg["model"]["lora"]
    # Auto-detect hybrid checkpoint: if the ckpt dir has scalar_head.pt,
    # we need scalar_head=True so EnergyScorer builds the matching module.
    scalar_head = (args.ckpt_dir / "scalar_head.pt").exists() if args.ckpt_dir else False
    if scalar_head:
        print(f"  detected scalar_head.pt → building hybrid scorer", flush=True)
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
        scalar_head=scalar_head,
    ).to(device)
    print(f"loading ckpt: {args.ckpt_dir}", flush=True)
    model.load_trainable(args.ckpt_dir)
    model.eval()

    marker_ids, neutral_ids = _apply_embedding_surgery(model, tok)
    print(f"embedding surgery: replaced {len(marker_ids)} marker rows "
          f"with mean of {len(neutral_ids)} neutral-comment rows.", flush=True)
    print(f"  marker IDs: {marker_ids}", flush=True)
    print(f"  neutral IDs: {neutral_ids}", flush=True)

    max_len = int(cfg["data"]["max_seq_len"])
    lse_t = float(cfg["model"]["lse"]["temp_end"])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    n_written, n_skipped = 0, 0
    with args.out.open("w") as f_out:
        for r in raw:
            impl_text = r.get("impl_text", "")
            spec_text = r.get("spec_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))
            ex = Example(
                source=Source.SFT_SAFE,
                spec_id=r["spec_id"], impl_id=r["impl_id"],
                spec_text=spec_text, impl_text=impl_text,
                status=_status_from_str(r.get("status", "")),
                buggy_lines=buggy_source_lines,
            )
            t = tokenize_example(ex, tok, max_length=max_len)
            if t is None or not t.sentinel_positions:
                n_skipped += 1
                continue
            input_ids = torch.tensor([t.input_ids], device=device)
            attn = torch.ones_like(input_ids)
            sent_pos = [torch.tensor(t.sentinel_positions, device=device)]
            with torch.no_grad():
                out = model(input_ids, attn, sent_pos, lse_temperature=lse_t)
            per_line = out.per_line_energies[0].float().cpu().tolist()
            whole = float(out.whole_impl_energies[0].float().cpu().item())
            all_lines = impl_text.splitlines()
            scorable = scorable_line_indices(impl_text)
            scorable_texts = [all_lines[i] for i in scorable][: len(per_line)]
            src_to_sent = {s: i for i, s in enumerate(scorable)}
            buggy_sent = sorted({src_to_sent[s] for s in buggy_source_lines
                                  if s in src_to_sent and src_to_sent[s] < len(per_line)})
            f_out.write(json.dumps({
                "impl_id": ex.impl_id, "spec_id": ex.spec_id,
                "source": "verus_real_token_masked",
                "status": ex.status.value,
                "whole_impl_energy": whole,
                "per_line_energies": per_line,
                "buggy_line_indices": buggy_sent,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
            n_written += 1
            if n_written % 100 == 0:
                print(f"  {n_written} done", flush=True)
    print(f"DONE: wrote {n_written}, skipped {n_skipped}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
