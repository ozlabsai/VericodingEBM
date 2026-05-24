# Trivial baselines on real-bug corpus (n=1492, line-labeled n=609)

Same eval pipeline as `run10_stripped` (`scripts/analyze_records.py`).
All numbers from `artifacts/real_bugs/records.jsonl`.

## Full corpus (n=1492, 609 line-labeled)

| Baseline | AUROC (95% CI) | top-1 | top-3 | top-5 |
|---|---|---|---|---|
| Random (seed=0) | 0.405 [0.34, 0.46] | 0.105 | 0.366 | 0.539 |
| Length (longer = sus) | 0.463 [0.39, 0.53] | 0.328 | 0.668 | 0.818 |
| Keyword (Verus: `assert/ensures/invariant/...`) | 0.373 [0.32, 0.43] | 0.544 | 0.767 | 0.892 |
| Keyword (marker: `// FAILS/panic!/unwrap/...`) | 0.673 [0.63, 0.72] | **0.997** | **1.000** | **1.000** |
| Diff-from-sibling-PASS (uninformative on 91%) | 0.476 [0.44, 0.52] | 0.072 | 0.250 | 0.417 |
| Qwen surprisal (frozen, fp32) | 0.597 [0.54, 0.66] | 0.002 | 0.141 | 0.340 |
| **Run #10 stripped** | **0.778 [0.72, 0.83]** | **0.560** | **0.839** | **0.936** |

## Sibling-subset (n=128, 86 line-labeled) — fair comparison for diff-sibling

Only 128/1492 records have at least one PASS sibling (same spec). Restricting
to this subset lets us compare Renieris-style diff baselines against run #10
on equal footing.

| Method on n=128 subset | AUROC (95% CI) | top-1 | top-3 | top-5 |
|---|---|---|---|---|
| Diff-from-sibling-PASS | 0.520 [0.36, 0.68] | 0.419 | 0.640 | 0.767 |
| **Run #10 stripped** | **0.697 [0.54, 0.84]** | **0.721** | **0.930** | **0.977** |

Run #10 beats diff-sibling by +30pp top-1 and +29pp top-3 on the exact subset
where diff-sibling is supposed to be most competitive.

## Read

1. **AUROC**: Run #10 (0.78) clearly beats every trivial baseline including the
   marker-keyword leak detector (0.67). The 95% CIs do not overlap with any
   non-marker baseline. The marker-keyword AUROC is itself only 0.67 — the
   markers are powerful at *line* selection but only moderate at *impl*
   discrimination (a buggy impl can have markers in non-buggy places too).
2. **Top-k recall**: Run #10 beats length and Verus-keyword baselines on top-3
   (+17pp and +7pp respectively) but the marker-keyword baseline saturates at
   100% — that is the leak this project's `strip_fails` audit was designed
   to expose, and it is the reason `run10_stripped` (which removes markers)
   is the canonical comparison.
3. **The marker-keyword baseline at top-1=0.997 is the formal statement of
   the marker leak**: comparing models against `records.jsonl` *without*
   stripping markers is meaningless — a 9-keyword regex saturates the metric.
4. **Diff-from-sibling-PASS** (Renieris & Reiss ASE'03) reaches top-3=0.64
   on the 128-record subset where PASS siblings exist, but run #10 reaches
   top-3=0.93 on the same subset *and* covers the other 91% of records the
   diff baseline can't score. The model is not just "diff against siblings."

## Significance test gates

Run #10 vs each baseline is what McNemar / DeLong need to verify (Task #79).
Visual inspection of CIs:
- AUROC: Run #10 [0.72, 0.83] vs marker [0.63, 0.72] → non-overlapping at 95%, p < 0.05 expected.
- Top-3: Run #10 0.839 vs length 0.668 — large effect; McNemar should be far below 0.001.

## Notes

- The `length` baseline's top-3 = 0.668 is consistent with what
  `analyze_records.py` reported as the "length baseline" lift in earlier
  runs.
- `Triviality 3` in run #10's analyze output flagged buggy-line position
  median = 0.74 (later in impls), which is why length and random both
  outperform their *uniform* expectation on top-k: long lines tend to
  cluster later in the file, where bugs also cluster.
