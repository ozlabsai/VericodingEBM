#!/usr/bin/env bash
# Run the full post-training evaluation pipeline against a checkpoint.
# Produces every number we owe a reviewer.
#
# Usage:
#   scripts/run_full_eval.sh <ckpt_dir>
#
# Outputs in artifacts/<ckpt_basename>/:
#   model_records.jsonl     ← model's per-line energies on held set
#   ochiai_records.jsonl    ← Ochiai SBFL baseline
#   ppl_records.jsonl       ← frozen-Qwen per-line PPL baseline
#   model_analysis.txt      ← analyze_records.py output for model
#   ochiai_analysis.txt     ← analyze_records.py output for Ochiai
#   ppl_analysis.txt        ← analyze_records.py output for PPL
#   hero.html, hero.txt     ← hand-crafted bug viz

set -euo pipefail
ckpt="${1:-}"
if [[ -z "$ckpt" ]]; then
  echo "usage: $0 <ckpt_dir>" >&2
  exit 1
fi
if [[ ! -d "$ckpt" ]]; then
  echo "ckpt dir not found: $ckpt" >&2
  exit 1
fi

base=$(basename "$ckpt")
outdir="artifacts/${base}"
mkdir -p "$outdir"

echo "==> [1/6] dump model records"
uv run python scripts/dump_eval_records.py \
  --config configs/default.yaml \
  --ckpt-dir "$ckpt" \
  --out "$outdir/model_records.jsonl" 2>&1 | tee "$outdir/model_dump.log"

echo "==> [2/6] dump Ochiai baseline (CPU, ~30s)"
uv run python scripts/baseline_ochiai.py \
  --config configs/default.yaml \
  --out "$outdir/ochiai_records.jsonl" 2>&1 | tee "$outdir/ochiai_dump.log"

echo "==> [3/6] dump Qwen-PPL baseline (GPU forward, ~20m on A100)"
uv run python scripts/baseline_qwen_ppl.py \
  --config configs/default.yaml \
  --out "$outdir/ppl_records.jsonl" 2>&1 | tee "$outdir/ppl_dump.log"

echo "==> [4/6] analyze model records"
uv run python scripts/analyze_records.py \
  --records "$outdir/model_records.jsonl" \
  --bootstrap-iters 500 2>&1 | tee "$outdir/model_analysis.txt"

echo "==> [5/6] analyze Ochiai + PPL"
uv run python scripts/analyze_records.py \
  --records "$outdir/ochiai_records.jsonl" \
  --bootstrap-iters 500 2>&1 | tee "$outdir/ochiai_analysis.txt"
uv run python scripts/analyze_records.py \
  --records "$outdir/ppl_records.jsonl" \
  --bootstrap-iters 500 2>&1 | tee "$outdir/ppl_analysis.txt"

echo "==> [6/6] hero example"
uv run python scripts/hero_example.py \
  --config configs/default.yaml \
  --ckpt-dir "$ckpt" \
  --out-html "$outdir/hero.html" \
  --out-text "$outdir/hero.txt"

echo ""
echo "DONE. Outputs in $outdir/"
ls -la "$outdir/"
