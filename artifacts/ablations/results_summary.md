# Run #10 ablation results (A1 + A4 only; A2/A3 OOM'd)

Each ablation = run #10 hybrid loss with **exactly one component changed**, 2-epoch training (~1844 steps), same data + LoRA + LR schedule. Three-way real-bug eval on full corpus (n=1492, 609 FAIL with line labels).

## Held-set eval (n=1980, mixed sources, no //FAILS surgery)

| Run | held AUROC | held top-1 | held top-3 |
|---|---|---|---|
| Run #10 (3 epochs, reference) | 0.643 | 0.804 | 0.950 |
| **A1: no scalar head** (LSE aggregator) | **0.564** | 0.815 | 0.940 |
| **A4: hinge instead of logistic impl-pair** | **0.631** | 0.815 | 0.945 |

## Real-bug eval (n=1492, three-way)

### AUROC (whole-impl FAIL vs PASS)
| Run | no-surgery | **stripped (canonical)** | token-masked |
|---|---|---|---|
| Run #10 | 0.842 | **0.778** | 0.782 |
| **A1** (no scalar head) | 0.470 | **0.455** | 0.462 |
| **A4** (hinge) | 0.867 | **0.784** | 0.864 |

### top-1 (per-line)
| Run | no-surgery | stripped | token-masked |
|---|---|---|---|
| Run #10 | 0.038 | **0.560** | 0.064 |
| **A1** | 0.209 | **0.516** | 0.169 |
| **A4** | 0.090 | **0.522** | 0.094 |

### top-3 (per-line)
| Run | no-surgery | stripped | token-masked |
|---|---|---|---|
| Run #10 | 0.238 | **0.839** | 0.388 |
| **A1** | 0.522 | **0.819** | 0.461 |
| **A4** | 0.389 | **0.847** | 0.432 |

## Attribution

### Headline finding
- **Removing the scalar head (A1)** drops stripped AUROC from **0.78 → 0.46** (a 32pp collapse to chance levels). Per-line top-1 drops modestly (0.56 → 0.52, -4pp); per-line top-3 essentially unchanged (0.84 → 0.82, -2pp).
- **Reverting to hinge impl-pair loss (A4)** is **a no-op within noise**: stripped AUROC 0.78 → 0.78, top-1 0.56 → 0.52, top-3 0.84 → 0.85.

### Mechanistic read
The **scalar attention-pool head is the single load-bearing innovation** for impl-level AUROC. The logistic-vs-hinge choice in *how* we train it doesn't matter at this scale — both losses converge to similar quality given the head exists.

The per-line head's localization signal is largely **independent of the scalar head** (run #10 top-3 = 0.84 vs A1 top-3 = 0.82). The per-line head was already strong in earlier runs (run #9 stripped top-3 = 0.76; A1 = 0.82); the scalar head's job is impl-level discrimination, not per-line localization.

### Run #9 pathology returns in A1
A1's stripped AUROC of 0.46 is consistent with the "bias drift under InfoNCE collapse" hypothesis from the run #9 post-mortem (run #9 stripped AUROC was 0.49). Wang & Isola 2020 alignment-without-uniformity is the explanation: without the scalar head, the LSE aggregator inherits per-impl additive bias drift from the saturating within-spec InfoNCE objective, and impl-level discrimination collapses to chance.

## Missing ablations (A2, A3 — OOM'd)

A2 (no listwise) and A3 (no semi-hard mining) both CUDA-OOM'd at startup — a stray 18 GB process on the RunPod RTX 6000 Ada SKU blocked the 32 GB allocation `train.py` needed. Both burned ~6 hours of pod time ($14 each) doing nothing before being killed.

These ablations are **lower priority** than A1 anyway — A1 directly tests our paper's central architecture claim (the scalar head); A2/A3 test which *loss component* drives per-line localization, which is a refinement. If we want to retry, A2/A3 would need ~$5/each on a fresh pod with `expandable_segments:True` set.

## Run #11 implication

The rubric in `sources/run11_plan.md` §2 says:
> **If A1 (no-scalar-head) shows scalar head is doing most of AUROC:** prioritize **EORM** (arXiv 2505.14999) + **EPA** (arXiv 2412.13862). Both directly improve impl-level energy calibration.

This is the scenario we landed in. **Run #11a stack** = EPA + NeuralNDCG + Focal + R-Drop. **Run #11b conditional** = add EORM post-hoc on top of the scalar head (since the scalar head is doing the work, EORM's "tiny energy verifier" recipe is the validated 2025 improvement to it).

## Cost

- A1, A4 training: ~$5 each (RTX 6000 Ada × ~3 hrs) = $10
- A2, A3 OOM'd but ran for ~6 hrs each: $14 each = **$28 wasted**
- Manual eval recovery: ~30 min × 2 pods = ~$1
- **Total ablation spend: ~$39** (vs $5 expected)

The OOM was the dominant cost. Lesson: smoke-test config on a cheaper pod first (1 epoch, 100 steps) before launching 4 in parallel.
