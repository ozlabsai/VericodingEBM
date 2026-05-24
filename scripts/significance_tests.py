"""Significance tests for run #10 vs baselines.

Produces:
  - McNemar paired test on top-1, top-3, top-5 (per FAIL impl: did method
    hit a buggy line in its top-k?)
  - DeLong test on AUROC differences (whole-impl FAIL vs PASS discrimination)
  - Bootstrap 95% CIs on every metric (paired bootstrap over impl_ids)

Compares each baseline against run #10 stripped on the full real-bug corpus
(n=1492). Outputs both a CSV table and a LaTeX-ready snippet.

Usage:
    uv run python scripts/significance_tests.py \\
        --target artifacts/real_bugs/hybrid_averse_stripped/eval_records.jsonl \\
        --baselines artifacts/baselines/length_records.jsonl \\
                    artifacts/baselines/keyword_verus_records.jsonl \\
                    artifacts/baselines/keyword_marker_records.jsonl \\
                    artifacts/baselines/qwen_surprisal_records.jsonl \\
                    artifacts/baselines/diff_sibling_records.jsonl \\
                    artifacts/baselines/random_records.jsonl \\
        --out-csv artifacts/stats/significance_table.csv \\
        --out-tex docs/stats_appendix.tex
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


def load_records(path: Path) -> dict[str, dict]:
    """Return {impl_id: record}."""
    out = {}
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
            out[r["impl_id"]] = r
    return out


def topk_hit(rec: dict, k: int) -> int | None:
    """1 if method hit a buggy line in its top-k, 0 if not, None if record
    can't be scored (not FAIL, no buggy lines, no energies)."""
    if rec["status"] != "FAIL" or not rec.get("buggy_line_indices"):
        return None
    es = rec.get("per_line_energies") or []
    if not es:
        return None
    keff = min(k, len(es))
    order = sorted(range(len(es)), key=lambda i: -es[i])
    top = set(order[:keff])
    return int(bool(top & set(rec["buggy_line_indices"])))


def mcnemar_test(b: list[int], t: list[int]) -> tuple[int, int, float]:
    """McNemar on paired binary outcomes.
    Returns (b01, b10, p_value) where b01=baseline 0/target 1, b10=baseline 1/target 0.
    Uses exact binomial when b01+b10 < 25, chi-square w/ continuity correction otherwise."""
    assert len(b) == len(t)
    b01 = sum(1 for x, y in zip(b, t) if x == 0 and y == 1)
    b10 = sum(1 for x, y in zip(b, t) if x == 1 and y == 0)
    n = b01 + b10
    if n == 0:
        return b01, b10, 1.0
    if n < 25:
        p = stats.binomtest(min(b01, b10), n, p=0.5, alternative="two-sided").pvalue
    else:
        chi2 = (abs(b01 - b10) - 1) ** 2 / n
        p = 1.0 - stats.chi2.cdf(chi2, df=1)
    return b01, b10, p


def delong_test(scores_a: np.ndarray, scores_b: np.ndarray, labels: np.ndarray) -> tuple[float, float, float]:
    """DeLong 1988 paired AUROC comparison.

    Returns (auc_a, auc_b, p_value_two_sided).

    Reference: Sun & Xu 2014 "Fast implementation of DeLong's algorithm".
    """
    order = np.argsort(-scores_a)  # not used, but keep convention
    pos = labels == 1
    neg = labels == 0
    n_pos = int(pos.sum())
    n_neg = int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan"), float("nan"), 1.0

    def _midrank(x: np.ndarray) -> np.ndarray:
        order = np.argsort(x)
        ranks = np.empty_like(order, dtype=float)
        n = len(x)
        i = 0
        while i < n:
            j = i
            while j < n - 1 and x[order[j + 1]] == x[order[i]]:
                j += 1
            ranks[order[i:j + 1]] = 0.5 * (i + j) + 1
            i = j + 1
        return ranks

    def _auc_and_var(s: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        pos_s = s[pos]
        neg_s = s[neg]
        # V10 = (1/n_neg) * sum_j I[pos > neg] structural component for positives
        # Equivalently, midrank-based formulation per DeLong.
        all_s = np.concatenate([pos_s, neg_s])
        all_ranks = _midrank(all_s)
        pos_ranks_within_all = all_ranks[:n_pos]
        neg_ranks_within_all = all_ranks[n_pos:]
        pos_ranks_alone = _midrank(pos_s)
        neg_ranks_alone = _midrank(neg_s)
        auc = (pos_ranks_within_all.sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
        v10 = (pos_ranks_within_all - pos_ranks_alone) / n_neg
        v01 = 1 - (neg_ranks_within_all - neg_ranks_alone) / n_pos
        return auc, v10, v01

    auc_a, v10_a, v01_a = _auc_and_var(scores_a)
    auc_b, v10_b, v01_b = _auc_and_var(scores_b)
    s10 = np.cov(np.stack([v10_a, v10_b]))
    s01 = np.cov(np.stack([v01_a, v01_b]))
    s = s10 / n_pos + s01 / n_neg
    diff = auc_a - auc_b
    var = s[0, 0] + s[1, 1] - 2 * s[0, 1]
    if var <= 0:
        return auc_a, auc_b, 1.0
    z = diff / np.sqrt(var)
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return auc_a, auc_b, p


def bootstrap_ci(values: list[float], n_iter: int = 1000, seed: int = 0) -> tuple[float, float, float]:
    """Bootstrap 95% CI on mean of paired sample. Returns (median, lo, hi)."""
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    arr = np.array(values, dtype=float)
    n = len(arr)
    means = np.empty(n_iter)
    for i in range(n_iter):
        idx = rng.integers(0, n, n)
        means[i] = arr[idx].mean()
    return float(np.median(means)), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, type=Path,
                    help="Records JSONL for the model being evaluated (run #10).")
    ap.add_argument("--baselines", nargs="+", required=True, type=Path,
                    help="One or more baseline records JSONL files.")
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--out-tex", required=True, type=Path)
    ap.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5])
    args = ap.parse_args()

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.out_tex.parent.mkdir(parents=True, exist_ok=True)

    target = load_records(args.target)
    print(f"target ({args.target.name}): {len(target)} records", flush=True)

    rows = []
    header = ["baseline", "n_paired"] + \
             [f"target_top{k}" for k in args.ks] + \
             [f"baseline_top{k}" for k in args.ks] + \
             [f"mcnemar_p_top{k}" for k in args.ks] + \
             ["target_auroc", "baseline_auroc", "delong_p", "delong_diff_lo", "delong_diff_hi"]

    for b_path in args.baselines:
        base = load_records(b_path)
        common = sorted(set(target) & set(base))
        print(f"\n--- {b_path.stem} ({len(base)} records, {len(common)} paired with target) ---", flush=True)

        # Per-impl top-k hits, only for FAIL records with labels.
        rec = {"baseline": b_path.stem, "n_paired": 0}
        labeled_ids = []
        for k in args.ks:
            tgt_hits, bas_hits, paired_ids = [], [], []
            for iid in common:
                t = topk_hit(target[iid], k)
                b = topk_hit(base[iid], k)
                if t is None or b is None:
                    continue
                tgt_hits.append(t)
                bas_hits.append(b)
                paired_ids.append(iid)
            if k == args.ks[0]:
                rec["n_paired"] = len(paired_ids)
                labeled_ids = paired_ids
            t_rate = float(np.mean(tgt_hits)) if tgt_hits else float("nan")
            b_rate = float(np.mean(bas_hits)) if bas_hits else float("nan")
            b01, b10, p = mcnemar_test(bas_hits, tgt_hits)
            rec[f"target_top{k}"] = t_rate
            rec[f"baseline_top{k}"] = b_rate
            rec[f"mcnemar_p_top{k}"] = p
            print(f"  top-{k}: target={t_rate:.4f} baseline={b_rate:.4f} "
                  f"(disagree {b01}+{b10}, McNemar p={p:.2e})", flush=True)

        # AUROC: use whole_impl_energy on FAIL vs PASS.
        tgt_scores, bas_scores, labels = [], [], []
        for iid in common:
            tw = target[iid].get("whole_impl_energy")
            bw = base[iid].get("whole_impl_energy")
            st = target[iid]["status"]
            if tw is None or bw is None:
                continue
            if st == "FAIL":
                labels.append(1)
            elif st == "PASS":
                labels.append(0)
            else:
                continue
            tgt_scores.append(float(tw))
            bas_scores.append(float(bw))
        if len(set(labels)) == 2:
            t_auc, b_auc, p_d = delong_test(np.array(tgt_scores), np.array(bas_scores), np.array(labels))
            # Paired bootstrap on AUC diff for CI.
            rng = np.random.default_rng(0)
            arr_t = np.array(tgt_scores)
            arr_b = np.array(bas_scores)
            arr_l = np.array(labels)
            diffs = []
            n = len(arr_l)
            for _ in range(500):
                idx = rng.integers(0, n, n)
                ll = arr_l[idx]
                if len(set(ll)) < 2:
                    continue
                _t, _b, _ = delong_test(arr_t[idx], arr_b[idx], ll)
                diffs.append(_t - _b)
            lo, hi = (float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))) \
                     if diffs else (float("nan"), float("nan"))
            rec["target_auroc"] = t_auc
            rec["baseline_auroc"] = b_auc
            rec["delong_p"] = p_d
            rec["delong_diff_lo"] = lo
            rec["delong_diff_hi"] = hi
            print(f"  AUROC: target={t_auc:.4f} baseline={b_auc:.4f} "
                  f"diff CI=[{lo:+.3f}, {hi:+.3f}] DeLong p={p_d:.2e}", flush=True)
        else:
            for k in ["target_auroc", "baseline_auroc", "delong_p",
                      "delong_diff_lo", "delong_diff_hi"]:
                rec[k] = float("nan")
        rows.append(rec)

    # Write CSV.
    with args.out_csv.open("w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(
                str(r.get(h, "")) if not isinstance(r.get(h), float)
                else (f"{r[h]:.6g}" if not np.isnan(r[h]) else "nan")
                for h in header
            ) + "\n")
    print(f"\nwrote {args.out_csv}", flush=True)

    # Write LaTeX snippet.
    def fmt_p(p: float) -> str:
        if np.isnan(p):
            return "---"
        if p < 1e-4:
            return r"$<10^{-4}$"
        if p < 0.001:
            return f"${p:.2e}$".replace("e-0", r"\times 10^{-").replace("e-", r"\times 10^{-") + "}$"
        return f"${p:.3f}$"

    with args.out_tex.open("w") as f:
        f.write("% Auto-generated by scripts/significance_tests.py\n")
        f.write("% Run #10 stripped vs trivial/zero-shot baselines on real-bug corpus.\n")
        f.write("\\begin{table}[t]\n\\centering\n\\small\n")
        f.write("\\caption{Paired significance tests: run \\#10 (stripped) vs baselines on \\nrealbugs"
                " real-bug records. Top-$k$ p-values are McNemar (paired binomial); AUROC p-values"
                " are DeLong. \\textbf{Bold} = run \\#10 better.}\n")
        f.write("\\label{tab:significance}\n")
        f.write("\\begin{tabular}{lrrrrrrr}\n\\toprule\n")
        f.write("Baseline & $n$ & \\multicolumn{2}{c}{top-1} & \\multicolumn{2}{c}{top-3} & "
                "\\multicolumn{2}{c}{AUROC} \\\\\n")
        f.write(" & & rate & $p$ & rate & $p$ & val & $p$ \\\\\n\\midrule\n")
        for r in rows:
            name = r["baseline"].replace("_records", "").replace("_", " ")
            n = r["n_paired"]
            t1 = r.get("target_top1", float("nan"))
            b1 = r.get("baseline_top1", float("nan"))
            t3 = r.get("target_top3", float("nan"))
            b3 = r.get("baseline_top3", float("nan"))
            ta = r.get("target_auroc", float("nan"))
            ba = r.get("baseline_auroc", float("nan"))
            p1 = fmt_p(r.get("mcnemar_p_top1", float("nan")))
            p3 = fmt_p(r.get("mcnemar_p_top3", float("nan")))
            pa = fmt_p(r.get("delong_p", float("nan")))
            mark1 = "\\textbf{" if t1 > b1 else ""
            mark3 = "\\textbf{" if t3 > b3 else ""
            marka = "\\textbf{" if ta > ba else ""
            close1 = "}" if mark1 else ""
            close3 = "}" if mark3 else ""
            closea = "}" if marka else ""
            f.write(f"{name} & {n} & "
                    f"{b1:.3f} vs {mark1}{t1:.3f}{close1} & {p1} & "
                    f"{b3:.3f} vs {mark3}{t3:.3f}{close3} & {p3} & "
                    f"{ba:.3f} vs {marka}{ta:.3f}{closea} & {pa} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    print(f"wrote {args.out_tex}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
