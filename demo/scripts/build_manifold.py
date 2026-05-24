"""Precompute embeddings + UMAP 2D coords for the energy-manifold demo.

For every record in artifacts/real_bugs/records.jsonl:
  - tokenize with sentinels (same path as score_external_records.py)
  - run the run #10 checkpoint, but capture sentinel hidden states directly
  - emit per-line rows: (impl_id, line_idx, line_text, energy, is_buggy, embed[D])
  - emit per-impl row: (impl_id, spec_id, status, whole_impl_energy, mean_embed[D])

Then fit a UMAP per scope (impl + line), persist the fitted transformers so the
demo backend can project user-typed lines into the same 2D space.

Outputs:
  demo/backend/data/impl_manifold.parquet
  demo/backend/data/line_manifold.parquet
  demo/backend/data/umap_impl.joblib
  demo/backend/data/umap_line.joblib

Usage:
    uv run python demo/scripts/build_manifold.py \\
        --config configs/run10_hybrid.yaml \\
        --ckpt-dir checkpoints/run10_final \\
        --records artifacts/real_bugs/records.jsonl \\
        --out-dir demo/backend/data
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
import yaml
from glass_box_umap import GlassBoxUMAP

from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer


def _resolve_dtype(p):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[p]


def _status_from_str(s):
    s = str(s).upper()
    if "." in s:
        s = s.split(".")[-1]
    if "PASS" in s or "OK" in s:
        return Status.PASS
    if "FAIL" in s or "ERR" in s:
        return Status.FAIL
    return Status.UNKNOWN


def _pick_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", required=True, type=Path)
    ap.add_argument("--records", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap number of records (for fast smoke tests).")
    ap.add_argument("--umap-neighbors", type=int, default=30)
    ap.add_argument("--umap-min-dist", type=float, default=0.1)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with args.config.open() as f:
        cfg = yaml.safe_load(f)

    device = _pick_device()
    dtype = _resolve_dtype(cfg["train"]["precision"])
    if device.type == "mps":
        # MPS fp16/bf16 softmax overflow on Qwen 151k vocab; force fp32.
        dtype = torch.float32
        # MPS+GQA SDPA has a shape-inference bug on Qwen2.5; force eager attn
        # by monkey-patching AutoModelForCausalLM.from_pretrained (the scorer
        # itself doesn't expose attn_implementation as a constructor arg).
        import transformers
        _orig_from_pretrained = transformers.AutoModelForCausalLM.from_pretrained
        def _patched(name, **kw):
            kw.setdefault("attn_implementation", "eager")
            return _orig_from_pretrained(name, **kw)
        transformers.AutoModelForCausalLM.from_pretrained = _patched
    print(f"device: {device}, dtype: {dtype}", flush=True)

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    lora = cfg["model"]["lora"]
    scalar_head = (args.ckpt_dir / "scalar_head.pt").exists()
    print(f"  scalar_head detected: {scalar_head}", flush=True)
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
        torch_dtype=dtype,
        gradient_checkpointing=False,
        scalar_head=scalar_head,
    ).to(device)
    model.load_trainable(args.ckpt_dir)
    model.eval()

    raw = []
    with args.records.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    if args.limit:
        raw = raw[: args.limit]
    print(f"loaded {len(raw)} records", flush=True)

    max_len = int(cfg["data"]["max_seq_len"])
    lse_t = float(cfg["model"]["lse"]["temp_end"])

    line_rows = []
    impl_rows = []
    line_embeds = []
    impl_embeds = []

    n_skipped = 0
    for ri, r in enumerate(raw):
        impl_text = r.get("impl_text", "")
        spec_text = r.get("spec_text", "")
        if not impl_text.strip():
            n_skipped += 1
            continue
        status = _status_from_str(r.get("status", ""))
        buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))

        ex = Example(
            source=Source.SFT_SAFE,
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
        sent_pos = torch.tensor(t.sentinel_positions, device=device)

        with torch.no_grad():
            hidden = model._hidden_states(input_ids, attn)
            h_lines = hidden[0].index_select(0, sent_pos)
            e_lines = model.head(h_lines.float()).squeeze(-1)
            if scalar_head:
                e_whole = model.scalar_head(hidden[0].float(), attn[0])
            else:
                from ebm_verus.model.scorer import normalized_lse
                e_whole = normalized_lse(e_lines, lse_t)

        per_line = np.atleast_1d(e_lines.float().cpu().numpy())
        h_lines_np = h_lines.float().cpu().numpy()
        if h_lines_np.ndim == 1:
            h_lines_np = h_lines_np[None, :]
        whole = float(e_whole.float().cpu().item())
        impl_embed = h_lines_np.mean(axis=0)

        all_lines = impl_text.splitlines()
        scorable = scorable_line_indices(impl_text)
        scorable_texts = [all_lines[i] for i in scorable][: len(per_line)]
        src_to_sent = {s: i for i, s in enumerate(scorable)}
        buggy_sent = {src_to_sent[s] for s in buggy_source_lines
                      if s in src_to_sent and src_to_sent[s] < len(per_line)}

        impl_rows.append({
            "impl_id": r["impl_id"],
            "spec_id": r["spec_id"],
            "status": status.value,
            "whole_impl_energy": whole,
            "n_lines": len(per_line),
            "has_pass_sibling": False,
            "spec_text": spec_text,
            "impl_text": impl_text,
        })
        impl_embeds.append(impl_embed)

        for li, (line_text, energy, embed_vec) in enumerate(
            zip(scorable_texts, per_line, h_lines_np)
        ):
            line_rows.append({
                "impl_id": r["impl_id"],
                "spec_id": r["spec_id"],
                "impl_status": status.value,
                "line_idx": li,
                "line_text": line_text,
                "energy": float(energy),
                "is_buggy": li in buggy_sent,
            })
            line_embeds.append(embed_vec)

        if (ri + 1) % 50 == 0:
            print(f"  {ri + 1}/{len(raw)} processed "
                  f"({len(line_rows)} lines, {len(impl_rows)} impls)", flush=True)

    print(f"DONE encoding: {len(impl_rows)} impls, {len(line_rows)} lines "
          f"(skipped {n_skipped})", flush=True)

    by_spec = defaultdict(list)
    for r in impl_rows:
        by_spec[r["spec_id"]].append(r)
    for r in impl_rows:
        sibs = [s for s in by_spec[r["spec_id"]]
                if s["impl_id"] != r["impl_id"] and s["status"] == "PASS"]
        r["has_pass_sibling"] = bool(sibs)

    impl_X = np.stack(impl_embeds).astype(np.float32)
    line_X = np.stack(line_embeds).astype(np.float32)
    print(f"impl_X: {impl_X.shape}, line_X: {line_X.shape}", flush=True)

    # Glass Box UMAP: parametric UMAP with provably locally-linear encoder
    # (PReLU + zero-bias linear) so per-feature contributions are exact.
    # PCA-preprocess to 64 dims to keep encoder training fast; the package
    # back-projects gradients to the original 1536-d feature space when
    # compute_contributions() is called.
    common_kwargs = dict(
        n_components=2,
        n_neighbors=args.umap_neighbors,
        min_dist=args.umap_min_dist,
        metric="cosine",
        pca_components=64,
        epochs=100,
        random_state=42,
        num_workers=0,   # required when random_state is set
        quiet=False,
    )

    print(f"fitting impl GlassBoxUMAP {common_kwargs}", flush=True)
    impl_umap = GlassBoxUMAP(**common_kwargs)
    impl_xy = impl_umap.fit_transform(impl_X)
    # L2-norm contributions across the 2 output dims → (n_samples, n_features).
    # Top-k feature contributions per point captured below.
    print("computing impl contributions...", flush=True)
    impl_contrib_l2 = impl_umap.compute_contributions(impl_X, reduction="l2")

    print(f"fitting line GlassBoxUMAP {common_kwargs}", flush=True)
    line_umap = GlassBoxUMAP(**common_kwargs)
    line_xy = line_umap.fit_transform(line_X)
    print("computing line contributions...", flush=True)
    line_contrib_l2 = line_umap.compute_contributions(line_X, reduction="l2")

    # Store top-10 contributing feature dims per point (storing all 1536 per
    # row is too big for parquet; top-k is what the demo would surface anyway).
    TOPK = 10
    impl_top_idx = np.argsort(-impl_contrib_l2, axis=1)[:, :TOPK]
    impl_top_val = np.take_along_axis(impl_contrib_l2, impl_top_idx, axis=1)
    line_top_idx = np.argsort(-line_contrib_l2, axis=1)[:, :TOPK]
    line_top_val = np.take_along_axis(line_contrib_l2, line_top_idx, axis=1)

    for i, (r, (x, y)) in enumerate(zip(impl_rows, impl_xy)):
        r["x"] = float(x)
        r["y"] = float(y)
        r["top_feature_idx"] = impl_top_idx[i].astype(int).tolist()
        r["top_feature_contrib"] = impl_top_val[i].astype(float).tolist()
    for i, (r, (x, y)) in enumerate(zip(line_rows, line_xy)):
        r["x"] = float(x)
        r["y"] = float(y)
        r["top_feature_idx"] = line_top_idx[i].astype(int).tolist()
        r["top_feature_contrib"] = line_top_val[i].astype(float).tolist()

    impl_table = pa.Table.from_pylist(impl_rows)
    line_table = pa.Table.from_pylist(line_rows)
    pq.write_table(impl_table, args.out_dir / "impl_manifold.parquet")
    pq.write_table(line_table, args.out_dir / "line_manifold.parquet")
    joblib.dump(impl_umap, args.out_dir / "umap_impl.joblib")
    joblib.dump(line_umap, args.out_dir / "umap_line.joblib")
    print(f"wrote:")
    print(f"  {args.out_dir}/impl_manifold.parquet  ({len(impl_rows)} rows)")
    print(f"  {args.out_dir}/line_manifold.parquet  ({len(line_rows)} rows)")
    print(f"  {args.out_dir}/umap_impl.joblib")
    print(f"  {args.out_dir}/umap_line.joblib")
    return 0


if __name__ == "__main__":
    sys.exit(main())
