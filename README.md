# VericodingEBM

**Where to Look: Energy-Based Per-Line Fault Localization for Verus Vericoding.**

A 1.5B-parameter discriminative energy-based model (Qwen2.5-Coder-1.5B + LoRA, sentinel-token per-line head) that scores every line of a Verus implementation with an energy proxy for "this line is the bug."

Submitted to the Apart × Atlas Computing **Secure Program Synthesis Hackathon, Track 3 (Vericoding)**.

📄 **Paper:** [`paper/main.pdf`](paper/main.pdf) (22 pages)
🤗 **Model:** [`OzLabs/VericodingEBM`](https://huggingface.co/OzLabs/VericodingEBM) (LoRA adapter + heads, 523 MB)
🤗 **Data:** [`OzLabs/VericodingEBM-data`](https://huggingface.co/datasets/OzLabs/VericodingEBM-data) (training corpora, 365 MB)
⚡ **5-minute demo:** see [Quickstart](#quickstart-5-min-no-gpu-no-api) below

---

## Headline results

| Measurement | Specialist (run #10, 1.5B) | Best frontier LLM | Verdict |
|---|---|---|---|
| Per-line top-3 recall on Verus dev-test (n=609 FAILs) | **0.84** | 0.74 (Claude Opus 4.7) | specialist wins |
| Whole-impl discrimination AUROC | **0.87** | 0.91 (GPT-5.5) | LLM wins |
| Closed-loop CEGIS repair@1 (n=100) | 25% (specialist-guided) | 30% (LLM self-judged) | LLM wins |
| Marker-leak audit (top-1 delta when `// FAILS` markers stripped) | **−52pp** (averse) | **±5pp** (invariant) | both honest, opposite direction |

The specialist beats every static baseline by a wide margin and matches a $200/run frontier LLM on per-line top-3; LLMs match or beat it on the two other measurements. The marker-leak audit reveals three regimes of `// FAILS` dependency in the wild. Full numbers and statistical tests in the paper.

---

## Quickstart (5 min, no GPU, no API)

The strip-FAILS audit is the paper's reproducibility centerpiece. It runs on a laptop with only the Python standard library, against released eval-record JSONLs shipped in this repo.

```bash
# 1. Clone
git clone git@github.com:ozlabsai/VericodingEBM.git
cd VericodingEBM

# 2. Run the audit on the canonical paper run (#10, marker-averse)
python scripts/audit_demo.py \
  --no-surgery artifacts/real_bugs/run10_no_surgery/eval_records.jsonl \
  --stripped   artifacts/real_bugs/run10_stripped/eval_records.jsonl
```

Expected output (matches paper Table 7):

```
=== Strip-FAILS audit ===
    k   with markers    stripped     delta   n_FAIL
  ---  -------------  ----------  --------  -------
    1          0.038       0.560   -0.522      609
    3          0.238       0.839   -0.601      609
    5          0.501       0.936   -0.435      609

  Verdict: marker-AVERSE (signal IMPROVES when marker removed)
```

The same demo against the **run #7** checkpoint (which leaked via markers) shows the opposite regime:

```bash
python scripts/audit_demo.py \
  --no-surgery artifacts/run7_step500/no_surgery.jsonl \
  --stripped   artifacts/run7_step500/stripped.jsonl
# → Verdict: marker-RELIANT
```

The same demo against any LLM baseline shows the third regime (marker-invariant, |delta| ≤ 5pp).

That is the leak-audit finding in three commands.

---

## Interactive demo

A precomputed energy-manifold viewer ships in `demo/frontend/dist/`. To
inspect it:

```bash
python3 -m http.server --directory demo/frontend/dist 8000
# → open http://localhost:8000
```

Two side-by-side UMAPs (impl-level + line-level) over the 1492 dev-test
records, colored by per-line and whole-impl energy. Click any point to drill
into source code with per-line energies. Live model scoring is disabled in
this static build; see `demo/README.md` for the dynamic mode.

## Repository layout

```
paper/main.pdf           — the 22-page submission paper
docs/main.tex            — paper source
docs/references.bib      — bibliography
docs/figures/            — generated paper figures

src/ebm_verus/           — training code (Qwen+LoRA, sentinel-token head)
  data/                  — dataset + counterfactual marker augmentation
  model/                 — scorer + scalar attention-pool head
  training/              — loop, losses (logistic pair + ListNet + semi-hard)

scripts/
  audit_demo.py          — 5-min laptop audit (DEMO ENTRY)
  train.py               — training entry (needs GPU)
  score_external_records.py
  strip_fails_reeval.py  — heavyweight re-eval with markers stripped (GPU)
  make_paper_figures.py
  figure_position_shift.py
  analyze_records.py

configs/                 — run configs (run10_hybrid.yaml is canonical)
artifacts/               — released eval records (see Reproducing section)
demo/                    — interactive manifold viewer (static site in dist/)
```

Internal docs (handoffs, research notebook, planning) live in `.internal/` and are gitignored.

---

## Reproducing paper tables

All analyses run from released JSONLs in `artifacts/` — no GPU, no API key.

| Paper item | Source data | Script |
|---|---|---|
| Table 2 (static baselines) | `artifacts/baselines/*.jsonl` | `scripts/analyze_records.py` |
| Table 3 (LLM disc baselines) | `artifacts/baselines/llm_disc/*.jsonl` | `scripts/analyze_records.py` |
| Table 6 (3-arm CEGIS) | `artifacts/cegis/3arm_results_v2.jsonl`, `summary_3arm.json` | precomputed |
| Table 7 (strip-FAILS audit) | `artifacts/real_bugs/run10_*` | `scripts/audit_demo.py` |
| Table 8 (ablations A1–A4) | `artifacts/ablations/*/` | `scripts/audit_demo.py` per ablation |
| Table 10 (run #7 pre-audit) | `artifacts/run7_step500/*` | `scripts/audit_demo.py` |
| Figure 1 (position shift) | `artifacts/ochiai_baseline/records.jsonl`, `artifacts/real_bugs/run7_step500/eval_records.jsonl` | `scripts/figure_position_shift.py` |
| Figures 2–3 | `artifacts/baselines/`, summary jsons | `scripts/make_paper_figures.py` |

---

## Model + data downloads

Both are on the Hugging Face Hub:

```python
from huggingface_hub import snapshot_download

# Trained model (LoRA adapter + per-line head + scalar head, ~523 MB)
ckpt_dir = snapshot_download("OzLabs/VericodingEBM")

# Training corpora (~365 MB total across 4 JSON / JSONL files)
data_dir = snapshot_download("OzLabs/VericodingEBM-data", repo_type="dataset")
```

The model expects the Qwen2.5-Coder-1.5B-Instruct base, which `transformers` downloads automatically on first load.

## Training (GPU)

For completeness — not needed to reproduce paper analyses.

```bash
uv sync
# Drop the four data files from OzLabs/VericodingEBM-data into data/raw/ first.
uv run python scripts/train.py --config configs/run10_hybrid.yaml
```

Runs on a single H100 (80 GB); ~4 hours wall-clock for the canonical config. Checkpoints land in `checkpoints/` (gitignored).

---

## Dependencies

Managed with [uv](https://docs.astral.sh/uv/). For the audit demo, Python stdlib is enough; for training, see `pyproject.toml`.

---

## Citation

If you use this work, please cite the paper in `paper/main.pdf`. BibTeX coming with the final submission.

## License

[MIT](LICENSE).
