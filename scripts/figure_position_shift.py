"""Figure: buggy-line position shift across corpora + model predictions.

Reads:
  artifacts/sentinel_reliant/eval_records.jsonl  (model on real bugs)
  artifacts/ochiai_baseline/records.jsonl              (sft_safe held set, has labels)

Produces:
  docs/fig_position_shift.pdf
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent

def load_records(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            r["status"] = str(r.get("status","")).upper().split(".")[-1]
            out.append(r)
    return out

def gold_buggy_positions(recs: list[dict]) -> list[float]:
    out = []
    for r in recs:
        if r["status"] != "FAIL" or not r.get("buggy_line_indices"): continue
        n = len(r.get("per_line_energies") or [])
        if n < 2: continue
        for i in r["buggy_line_indices"]:
            if 0 <= i < n:
                out.append(i / (n - 1))
    return out

def pred_top1_positions(recs: list[dict]) -> list[float]:
    out = []
    for r in recs:
        if r["status"] != "FAIL" or not r.get("buggy_line_indices"): continue
        es = r.get("per_line_energies") or []
        if len(es) < 2: continue
        top1 = max(range(len(es)), key=lambda i: es[i])
        out.append(top1 / (len(es) - 1))
    return out

held_recs = load_records(REPO / "artifacts/ochiai_baseline/records.jsonl")
real_recs = load_records(REPO / "artifacts/sentinel_reliant/eval_records.jsonl")

# Gold buggy positions (from labels in both corpora)
held_gold = gold_buggy_positions(held_recs)
real_gold = gold_buggy_positions(real_recs)
# Model top-1 predictions (only real has these from the trained model; held
# would require dumping model records, which we haven't run yet -- skip and
# note in caption)
real_pred = pred_top1_positions(real_recs)

fig, ax = plt.subplots(1, 1, figsize=(5.5, 3.2))
bins = np.linspace(0.0, 1.0, 21)
ax.hist(held_gold, bins=bins, alpha=0.55, label=f"sft_safe gold ($n$={len(held_gold)})",
        color="#1f77b4", density=True, edgecolor="white", linewidth=0.5)
ax.hist(real_gold, bins=bins, alpha=0.55, label=f"verus dev-test gold ($n$={len(real_gold)})",
        color="#d62728", density=True, edgecolor="white", linewidth=0.5)
ax.hist(real_pred, bins=bins, alpha=0.0, density=True)  # invisible to grab y-range
# Overlay model predictions as a step line
hist, edges = np.histogram(real_pred, bins=bins, density=True)
centers = (edges[:-1] + edges[1:]) / 2
ax.plot(centers, hist, color="black", linewidth=1.6, label=f"model top-1 on dev-test ($n$={len(real_pred)})")

ax.set_xlabel("Relative position within impl (0 = first scorable line, 1 = last)")
ax.set_ylabel("Density")
ax.set_title("Buggy-line position shifts across corpora;\nmodel predictions track the dev-test distribution",
             fontsize=10)
ax.legend(loc="upper left", fontsize=8, frameon=False)
ax.set_xlim(0, 1)
ax.set_ylim(0, max(ax.get_ylim()) * 1.1)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
fig.tight_layout()
out = REPO / "docs/figures/fig_position_shift.pdf"
fig.savefig(out, bbox_inches="tight")
print(f"wrote {out}")
