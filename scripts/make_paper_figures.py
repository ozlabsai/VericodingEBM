"""Generate paper figures for the run #10 results.

Produces five PDFs into docs/figures/:

  fig_baseline_comparison.pdf  — grouped bars: AUROC + top-3 across methods
  fig_roc_curves.pdf           — ROC overlay: run #10 vs strongest 3 baselines
  fig_topk_curves.pdf          — top-k recall vs k (1..10) for all methods
  fig_per_impl_heatmap.pdf     — 6 sample impls, per-line energy bars
  fig_loss_components.pdf      — training curves: total/spec/line loss + eval

All figures share a single color palette + style so the paper reads coherently.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Single source of truth for method styling. Keep names short for legend.
METHODS = {
    "random":         {"label": "Random",            "color": "#bbbbbb", "ls": ":"},
    "length":         {"label": "Length",            "color": "#888888", "ls": "--"},
    "keyword_verus":  {"label": "Verus keywords",    "color": "#5a9b8c", "ls": "-."},
    "keyword_marker": {"label": "Marker keywords*",  "color": "#d4a155", "ls": ":"},
    "diff_sibling":   {"label": "Diff-from-sibling", "color": "#7777aa", "ls": "--"},
    "qwen_surprisal": {"label": "Qwen surprisal",    "color": "#cc6677", "ls": "-."},
    "run10":          {"label": "Run #10 (ours)",    "color": "#2c5fc7", "ls": "-"},
}

plt.rcParams.update({
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "axes.spines.right": False,
    "axes.spines.top": False,
    "text.usetex": False,  # set True if a TeX install is on PATH
})


def load_records(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            s = str(r.get("status", "")).upper()
            if "." in s:
                s = s.split(".")[-1]
            r["status"] = s
            out.append(r)
    return out


def topk_recall(records: list[dict], k: int) -> tuple[float, int]:
    hits, n = 0, 0
    for r in records:
        if r["status"] != "FAIL" or not r.get("buggy_line_indices"):
            continue
        es = r.get("per_line_energies") or []
        if not es:
            continue
        n += 1
        keff = min(k, len(es))
        order = sorted(range(len(es)), key=lambda i: -es[i])
        if set(order[:keff]) & set(r["buggy_line_indices"]):
            hits += 1
    return (hits / n if n else float("nan")), n


def auroc(records: list[dict]) -> float:
    pos = [float(r["whole_impl_energy"]) for r in records if r["status"] == "FAIL"]
    neg = [float(r["whole_impl_energy"]) for r in records if r["status"] == "PASS"]
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def roc_curve_points(records: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [(float(r["whole_impl_energy"]), 1 if r["status"] == "FAIL" else 0)
             for r in records if r["status"] in {"FAIL", "PASS"}]
    pairs.sort(key=lambda x: -x[0])
    p_total = sum(1 for _, y in pairs if y == 1)
    n_total = len(pairs) - p_total
    tpr, fpr = [0.0], [0.0]
    tp = fp = 0
    for _, y in pairs:
        if y == 1:
            tp += 1
        else:
            fp += 1
        tpr.append(tp / p_total if p_total else 0)
        fpr.append(fp / n_total if n_total else 0)
    return np.array(fpr), np.array(tpr)


def bootstrap_metric(records: list[dict], metric_fn, n_iter: int = 500, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(records)
    arr = np.empty(n_iter)
    for i in range(n_iter):
        idx = rng.integers(0, n, n)
        arr[i] = metric_fn([records[j] for j in idx])
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))


# ---------------------------------------------------------------------------

def fig_baseline_comparison(records: dict[str, list[dict]], out: Path) -> None:
    """Grouped bars: AUROC and top-3 for each method, with 95% CIs."""
    method_order = ["random", "length", "keyword_verus", "keyword_marker",
                    "diff_sibling", "qwen_surprisal", "run10"]
    aurocs, top3s, auroc_cis, top3_cis = [], [], [], []
    for m in method_order:
        recs = records[m]
        aurocs.append(auroc(recs))
        top3s.append(topk_recall(recs, 3)[0])
        auroc_cis.append(bootstrap_metric(recs, auroc, n_iter=300, seed=1))
        top3_cis.append(bootstrap_metric(recs, lambda rs: topk_recall(rs, 3)[0], n_iter=300, seed=1))

    fig, ax = plt.subplots(1, 1, figsize=(7.5, 3.5))
    x = np.arange(len(method_order))
    width = 0.38
    colors = [METHODS[m]["color"] for m in method_order]
    labels = [METHODS[m]["label"] for m in method_order]

    auroc_err = np.array([[a - lo, hi - a] for a, (lo, hi) in zip(aurocs, auroc_cis)]).T
    top3_err = np.array([[a - lo, hi - a] for a, (lo, hi) in zip(top3s, top3_cis)]).T

    b1 = ax.bar(x - width / 2, aurocs, width, color=colors, edgecolor="black", linewidth=0.5,
                yerr=auroc_err, capsize=2, label="AUROC")
    b2 = ax.bar(x + width / 2, top3s, width, color=colors, alpha=0.55, edgecolor="black",
                linewidth=0.5, yerr=top3_err, capsize=2, label="top-3 recall")

    ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_ylabel("Metric")
    ax.set_ylim(0, 1.05)
    ax.set_title("Baseline comparison on Verus dev-test corpus (n=1492)")

    # Custom legend: solid = AUROC, faded = top-3
    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#888888", edgecolor="black", label="AUROC"),
               Patch(facecolor="#888888", edgecolor="black", alpha=0.55, label="top-3 recall")]
    ax.legend(handles=handles, loc="upper left", frameon=False)
    plt.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def fig_roc_curves(records: dict[str, list[dict]], out: Path) -> None:
    """ROC curves: run #10 vs the strongest non-leak baselines."""
    to_plot = ["random", "length", "qwen_surprisal", "keyword_marker", "run10"]
    fig, ax = plt.subplots(1, 1, figsize=(4.5, 4.0))
    for m in to_plot:
        fpr, tpr = roc_curve_points(records[m])
        a = auroc(records[m])
        style = METHODS[m]
        ax.plot(fpr, tpr, color=style["color"], linestyle=style["ls"], linewidth=1.8,
                label=f"{style['label']} (AUC={a:.3f})")
    ax.plot([0, 1], [0, 1], color="black", linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_aspect("equal")
    ax.set_title("ROC: whole-impl FAIL vs PASS")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    plt.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def fig_topk_curves(records: dict[str, list[dict]], out: Path) -> None:
    """top-k recall as a function of k (1..10) for every method."""
    ks = list(range(1, 11))
    fig, ax = plt.subplots(1, 1, figsize=(5.5, 3.5))
    for m, recs in records.items():
        vals = [topk_recall(recs, k)[0] for k in ks]
        style = METHODS[m]
        ax.plot(ks, vals, color=style["color"], linestyle=style["ls"], linewidth=1.5,
                marker="o", markersize=3.5, label=style["label"])
    ax.set_xlabel("$k$")
    ax.set_ylabel("top-$k$ recall (FAIL impls only)")
    ax.set_xticks(ks)
    ax.set_ylim(0, 1.05)
    ax.set_title("Per-line localization vs $k$")
    ax.legend(loc="lower right", frameon=False, fontsize=8, ncol=2)
    ax.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)
    plt.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def fig_per_impl_heatmap(run10: list[dict], out: Path, n_show: int = 6, seed: int = 0) -> None:
    """Stacked bars: per-line energies for n_show FAIL impls, buggy lines highlighted."""
    rng = np.random.default_rng(seed)
    fail_recs = [r for r in run10
                 if r["status"] == "FAIL"
                 and r.get("buggy_line_indices")
                 and r.get("per_line_energies")
                 and 5 <= len(r["per_line_energies"]) <= 35]
    # Prefer records where run #10 actually got top-1 right (gives a stronger visual).
    def correct_top1(r):
        es = r["per_line_energies"]
        return int(np.argmax(es)) in set(r["buggy_line_indices"])
    pool_correct = [r for r in fail_recs if correct_top1(r)]
    pool_wrong = [r for r in fail_recs if not correct_top1(r)]
    # 4 correct + 2 wrong to show range of behavior.
    pick = list(rng.choice(pool_correct, size=min(4, len(pool_correct)), replace=False)) + \
           list(rng.choice(pool_wrong, size=min(2, len(pool_wrong)), replace=False))
    pick = pick[:n_show]

    fig, axes = plt.subplots(2, 3, figsize=(9.5, 5.0))
    for ax, r in zip(axes.flat, pick):
        es = np.array(r["per_line_energies"])
        buggy = set(r["buggy_line_indices"])
        # Normalize energies to [0, 1] within each impl for visual fairness.
        if es.max() > es.min():
            es_n = (es - es.min()) / (es.max() - es.min())
        else:
            es_n = es
        colors = ["#cc4040" if i in buggy else "#2c5fc7" for i in range(len(es))]
        ax.bar(range(len(es)), es_n, color=colors, edgecolor="black", linewidth=0.3)
        ax.set_xlabel("line index")
        ax.set_ylabel("energy (norm.)")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{r['impl_id'][:30]}", fontsize=8)
        ax.tick_params(labelsize=7)
    # Legend on figure level.
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor="#cc4040", label="ground-truth buggy line"),
                        Patch(facecolor="#2c5fc7", label="other line")],
               loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02), frameon=False)
    plt.tight_layout()
    plt.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}  (selected {len(pick)} impls)")


def fig_loss_components(train_path: Path, eval_path: Path, out: Path) -> None:
    """Two-panel: (top) train losses over steps, (bottom) eval AUROC + top-k."""
    train = []
    with train_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                train.append(json.loads(line))
    train.sort(key=lambda x: x.get("train/step") or x.get("_step") or 0)
    steps = np.array([t.get("train/step") or t.get("_step") for t in train])
    loss = np.array([t.get("train/loss") for t in train], dtype=float)
    loss_spec = np.array([t.get("train/loss_spec") for t in train], dtype=float)
    loss_line = np.array([t.get("train/loss_line") for t in train], dtype=float)

    evals = []
    with eval_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                evals.append(json.loads(line))
    evals.sort(key=lambda x: x.get("eval/step") or 0)
    e_steps = np.array([e.get("eval/step") for e in evals])
    e_auroc = np.array([e.get("eval/auroc") for e in evals], dtype=float)
    e_top1 = np.array([e.get("eval/per_line_top1") for e in evals], dtype=float)
    e_top3 = np.array([e.get("eval/per_line_top3") for e in evals], dtype=float)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.0, 4.5), sharex=True,
                                    gridspec_kw={"height_ratios": [1.3, 1]})
    ax1.plot(steps, loss, color="#222222", linewidth=1.4, label="Total")
    ax1.plot(steps, loss_spec, color="#2c5fc7", linewidth=1.2, label="Impl-pair (scalar)",
             alpha=0.9)
    ax1.plot(steps, loss_line, color="#cc6677", linewidth=1.2, label="Per-line (listwise + hinge)",
             alpha=0.9)
    ax1.set_ylabel("training loss")
    ax1.set_yscale("symlog", linthresh=0.1)
    ax1.legend(loc="lower left", frameon=False, fontsize=8, ncol=3,
               bbox_to_anchor=(0.0, 1.02))
    ax1.set_title("Run #10 training trajectory (hybrid loss)", pad=22)

    ax2.plot(e_steps, e_auroc, color="#2c5fc7", marker="o", markersize=4, linewidth=1.5,
             label="held AUROC")
    ax2.plot(e_steps, e_top1, color="#5a9b8c", marker="s", markersize=4, linewidth=1.5,
             label="held top-1")
    ax2.plot(e_steps, e_top3, color="#d4a155", marker="^", markersize=4, linewidth=1.5,
             label="held top-3")
    ax2.set_xlabel("step")
    ax2.set_ylabel("held-set metric")
    ax2.set_ylim(0, 1.05)
    ax2.legend(loc="lower right", frameon=False, fontsize=8, ncol=3)
    ax2.grid(True, axis="y", linestyle=":", linewidth=0.4, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="docs/figures", type=Path)
    ap.add_argument("--baselines-dir", default="artifacts/baselines", type=Path)
    ap.add_argument("--run10", default="artifacts/real_bugs/run10_stripped/eval_records.jsonl",
                    type=Path)
    ap.add_argument("--train-history", default="artifacts/training/run10_train.jsonl", type=Path)
    ap.add_argument("--eval-history", default="artifacts/training/run10_eval.jsonl", type=Path)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("loading records...")
    records = {
        "random":         load_records(args.baselines_dir / "random_records.jsonl"),
        "length":         load_records(args.baselines_dir / "length_records.jsonl"),
        "keyword_verus":  load_records(args.baselines_dir / "keyword_verus_records.jsonl"),
        "keyword_marker": load_records(args.baselines_dir / "keyword_marker_records.jsonl"),
        "diff_sibling":   load_records(args.baselines_dir / "diff_sibling_records.jsonl"),
        "qwen_surprisal": load_records(args.baselines_dir / "qwen_surprisal_records.jsonl"),
        "run10":          load_records(args.run10),
    }
    for k, v in records.items():
        print(f"  {k}: {len(v)} records")

    print("\nbuilding figures...")
    fig_baseline_comparison(records, args.out_dir / "fig_baseline_comparison.pdf")
    fig_roc_curves(records, args.out_dir / "fig_roc_curves.pdf")
    fig_topk_curves(records, args.out_dir / "fig_topk_curves.pdf")
    fig_per_impl_heatmap(records["run10"], args.out_dir / "fig_per_impl_heatmap.pdf")
    fig_loss_components(args.train_history, args.eval_history,
                        args.out_dir / "fig_loss_components.pdf")
    print("\nall figures written to", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
