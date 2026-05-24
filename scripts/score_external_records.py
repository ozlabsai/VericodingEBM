"""Score Example-shaped JSONL records with a trained checkpoint.

Companion to scrape_verus_real_bugs.py: reads records emitted by the scraper
(each line has spec_text, impl_text, status, buggy_lines, etc.), instantiates
the trained EnergyScorer, runs forward, dumps per-line energies in the same
format analyze_records.py consumes.

Usage:
    uv run python scripts/score_external_records.py \
        --config configs/default.yaml \
        --ckpt-dir checkpoints/run/final \
        --in artifacts/real_bugs/records.jsonl \
        --out artifacts/real_bugs/eval_records.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import yaml

from ebm_verus.constants import SENTINEL_TOKEN  # noqa: F401
from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer


def _resolve_dtype(precision: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def _status_from_str(s: str) -> Status:
    s = s.upper()
    if s.endswith("PASS") or s.endswith("OK"):
        return Status.PASS
    if s.endswith("FAIL") or s.endswith("ERR"):
        return Status.FAIL
    return Status.UNKNOWN


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", type=Path, default=None)
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

    # Load records.
    raw_records: list[dict] = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw_records.append(json.loads(line))
    print(f"loaded {len(raw_records)} input records from {args.in_path}", flush=True)

    # Tokenizer + model.
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    lora = cfg["model"]["lora"]
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
    if args.ckpt_dir is not None:
        print(f"loading ckpt: {args.ckpt_dir}", flush=True)
        model.load_trainable(args.ckpt_dir)
    else:
        print("WARN: no --ckpt-dir; UNTRAINED head", flush=True)
    model.eval()

    max_len = int(cfg["data"]["max_seq_len"])
    lse_t = float(cfg["model"]["lse"]["temp_end"])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    n_written = 0
    n_skipped = 0
    with args.out.open("w") as f_out:
        for r in raw_records:
            spec_text = r.get("spec_text", "")
            impl_text = r.get("impl_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            status = _status_from_str(r.get("status", ""))
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))

            ex = Example(
                source=Source.SFT_SAFE,  # placeholder; only used for typing
                spec_id=r["spec_id"],
                impl_id=r["impl_id"],
                spec_text=spec_text,
                impl_text=impl_text,
                status=status,
                buggy_lines=buggy_source_lines,
            )
            t = tokenize_example(ex, tokenizer, max_length=max_len)
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

            # buggy_line_indices reported here are in *sentinel space* (matches
            # the rest of the eval pipeline). Map source→sentinel via the scorable
            # list.
            src_to_sentinel = {src: i for i, src in enumerate(scorable)}
            buggy_sentinel = sorted({
                src_to_sentinel[s]
                for s in buggy_source_lines
                if s in src_to_sentinel and src_to_sentinel[s] < len(per_line)
            })

            f_out.write(json.dumps({
                "impl_id": ex.impl_id,
                "spec_id": ex.spec_id,
                "source": r.get("source", "verus_real"),
                "source_file": r.get("source_file"),
                "test_name": r.get("test_name"),
                "status": status.value,
                "whole_impl_energy": whole,
                "per_line_energies": per_line,
                "buggy_line_indices": buggy_sentinel,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
            n_written += 1
            if n_written % 50 == 0:
                print(f"  {n_written}/{len(raw_records)} scored", flush=True)
    print(f"wrote {n_written} records (skipped {n_skipped}) -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
