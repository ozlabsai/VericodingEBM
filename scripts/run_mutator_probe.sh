#!/usr/bin/env bash
# Mutator-fingerprint probe driver.
#
# Given a checkpoint dir, score real Verus bugs scraped from verus-lang/verus
# test suite, then run the same analyze_records.py as for held set so the
# numbers are directly comparable.
#
# Usage:
#   scripts/run_mutator_probe.sh <ckpt_dir>
#
# Outputs in artifacts/real_bugs/<ckpt_basename>/:
#   eval_records.jsonl   ← model's per-line energies on real bugs
#   analysis.txt         ← analyze_records.py output

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
outdir="artifacts/real_bugs/${base}"
mkdir -p "$outdir"

if [[ ! -f artifacts/real_bugs/records.jsonl ]]; then
  echo "==> scraping real bug records (first run)"
  uv run python scripts/scrape_verus_real_bugs.py --out artifacts/real_bugs/records.jsonl
fi

echo "==> scoring real bugs with $ckpt"
uv run python scripts/score_external_records.py \
  --config configs/default.yaml \
  --ckpt-dir "$ckpt" \
  --in artifacts/real_bugs/records.jsonl \
  --out "$outdir/eval_records.jsonl" 2>&1 | tee "$outdir/score.log"

echo "==> analyzing"
uv run python scripts/analyze_records.py \
  --records "$outdir/eval_records.jsonl" \
  --bootstrap-iters 1000 2>&1 | tee "$outdir/analysis.txt"

echo ""
echo "DONE. Outputs in $outdir/"
echo ""
echo "Compare to held-set result for the same checkpoint:"
echo "  held-set top-3 should be ~0.95"
echo "  real-bug top-3 (above) is the mutator-fingerprint test"
echo "  If real-bug top-3 drops to <0.5: model is a mutator detector"
echo "  If real-bug top-3 stays >0.7: model has learned bug semantics"
