"""Evaluation: metrics + eval loop."""

from ebm_verus.eval.metrics import (
    EvalMetrics,
    EvalRecord,
    compute_eval_metrics,
    per_line_topk_recall,
    whole_impl_auroc,
    within_spec_ranking_accuracy,
)

__all__ = [
    "EvalMetrics",
    "EvalRecord",
    "compute_eval_metrics",
    "per_line_topk_recall",
    "whole_impl_auroc",
    "within_spec_ranking_accuracy",
]
