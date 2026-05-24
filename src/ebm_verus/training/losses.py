"""Contrastive losses for the energy-based scorer.

Conventions:
  * Higher energy = more likely buggy. Passing impls should have LOW energy;
    failing impls should have HIGH energy.
  * In InfoNCE form, the "logit" we softmax is ``-E`` (so low E becomes high
    probability of being the positive). This matches the standard EBM
    formulation ``p(x) ∝ exp(-E(x))``.

The two losses operate on disjoint subsets of the batch:
  * ``L_spec`` consumes ``Batch.traj_triples`` (system-trajectory mixed-label
    groups) plus all batch-level FAIL impls as cross-spec negatives.
  * ``L_line`` consumes ``Batch.safe_broken_indices`` (sft_safe broken impls
    with non-empty ``buggy_line_indices``).

If either subset is empty for a given batch, that loss returns a zero scalar
that still backprops (``0 * sum(params)``) so the optimizer doesn't complain.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ebm_verus.data.dataset import Batch
from ebm_verus.data.types import Status
from ebm_verus.model.scorer import ScorerOutput


@dataclass
class LossOutput:
    total: torch.Tensor
    spec: torch.Tensor
    line: torch.Tensor
    n_spec_groups: int     # number of triples that contributed
    n_line_pairs: int      # number of (buggy, non_buggy) pairs sampled
    spec_pos_minus_neg_mean: float | None  # diagnostic: mean (E_neg - E_pos) over groups
    line_buggy_minus_clean_mean: float | None  # diagnostic: mean (E_buggy - E_clean)


def _zero_loss_like(t: torch.Tensor) -> torch.Tensor:
    return (t * 0.0).sum()


def l_spec_infonce(
    batch: Batch,
    out: ScorerOutput,
    *,
    pool_cross_spec_negatives: bool = True,
) -> tuple[torch.Tensor, int, float | None]:
    """Within-spec InfoNCE, optionally pooling cross-spec failing impls as
    additional negatives.

    For each triple [pos_idx, *fail_idxs] in ``batch.traj_triples``:
        logits = -E(impl) for [pos_idx, *fail_idxs (+ cross-spec FAIL pool)]
        target = 0  (pos is at position 0)
        loss   = cross_entropy(logits, target)

    Cross-spec negatives are *other* batch elements with status=FAIL whose
    spec_id is NOT the current triple's spec_id. They're shared across all
    triples in the batch (no per-triple recomputation).
    """
    whole = out.whole_impl_energies  # (B,)
    if not batch.traj_triples:
        return _zero_loss_like(whole), 0, None

    # Pool cross-spec FAIL indices once.
    if pool_cross_spec_negatives:
        all_fail_idxs = [
            i for i, s in enumerate(batch.statuses) if s == Status.FAIL
        ]
    else:
        all_fail_idxs = []

    losses: list[torch.Tensor] = []
    diagnostic_diffs: list[float] = []
    for triple in batch.traj_triples:
        pos_idx = triple[0]
        local_neg_idxs = triple[1:]
        local_spec = batch.spec_ids[pos_idx]

        # Cross-spec negatives = FAIL impls whose spec differs AND are not
        # already in this triple.
        triple_set = set(triple)
        cross_neg_idxs = [
            i for i in all_fail_idxs
            if i not in triple_set and batch.spec_ids[i] != local_spec
        ]

        idxs = [pos_idx, *local_neg_idxs, *cross_neg_idxs]
        # Sanity: need at least one negative.
        if len(idxs) < 2:
            continue

        # logits = -E for each candidate. Positive is at position 0.
        logits = -whole[idxs]  # (k,)
        target = whole.new_zeros((), dtype=torch.long)
        loss = torch.nn.functional.cross_entropy(
            logits.unsqueeze(0), target.unsqueeze(0)
        )
        losses.append(loss)
        # diagnostic: how much lower is pos's energy than neg average?
        diagnostic_diffs.append(
            (whole[idxs[1:]].mean() - whole[pos_idx]).detach().float().item()
        )

    if not losses:
        return _zero_loss_like(whole), 0, None
    stacked = torch.stack(losses).mean()
    mean_diff = sum(diagnostic_diffs) / len(diagnostic_diffs) if diagnostic_diffs else None
    return stacked, len(losses), mean_diff


def l_line_hinge(
    batch: Batch,
    out: ScorerOutput,
    *,
    margin: float,
    pairs_per_impl: int = 4,
    rng: torch.Generator | None = None,
) -> tuple[torch.Tensor, int, float | None]:
    """Pairwise hinge over (buggy_line, non_buggy_line) pairs within each broken impl.

    For each broken impl in ``batch.safe_broken_indices``:
        sample up to ``pairs_per_impl`` (buggy_line, non_buggy_line) pairs
        loss += max(0, m + E(non_buggy) - E(buggy))

    Returns the mean loss across all sampled pairs.
    """
    per_line = out.per_line_energies
    if not batch.safe_broken_indices:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None

    losses: list[torch.Tensor] = []
    diagnostic_diffs: list[float] = []
    for b in batch.safe_broken_indices:
        e = per_line[b]                       # (n_lines,)
        buggy = batch.buggy_line_indices[b]   # (n_buggy,)
        n_lines = e.shape[0]
        if n_lines == 0 or buggy.numel() == 0:
            continue
        # The set of non-buggy line indices.
        all_idx = torch.arange(n_lines, device=e.device)
        buggy_set = set(buggy.tolist())
        non_buggy = torch.tensor(
            [i for i in all_idx.tolist() if i not in buggy_set],
            dtype=torch.long, device=e.device,
        )
        if non_buggy.numel() == 0:
            continue  # whole impl is "buggy" — no contrast available

        # Sample pairs.
        n_pairs = min(pairs_per_impl, buggy.numel() * non_buggy.numel())
        # ``rng`` is always a CPU generator (so the same seed is portable
        # across device placements). Sample indices on CPU, then move to
        # ``e.device`` for the gather. Cost: 2 tiny H2D transfers per impl.
        if rng is not None:
            buggy_idx = torch.randint(0, buggy.numel(), (n_pairs,), generator=rng)
            nonb_idx = torch.randint(0, non_buggy.numel(), (n_pairs,), generator=rng)
        else:
            buggy_idx = torch.randint(0, buggy.numel(), (n_pairs,))
            nonb_idx = torch.randint(0, non_buggy.numel(), (n_pairs,))
        buggy_pick = buggy[buggy_idx.to(buggy.device)]
        nonb_pick = non_buggy[nonb_idx.to(non_buggy.device)]

        e_buggy = e[buggy_pick]   # (n_pairs,)
        e_nonb = e[nonb_pick]     # (n_pairs,)
        pair_losses = torch.clamp(margin + e_nonb - e_buggy, min=0.0)
        losses.append(pair_losses)
        diagnostic_diffs.append((e_buggy.mean() - e_nonb.mean()).detach().float().item())

    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.cat(losses).mean()
    mean_diff = sum(diagnostic_diffs) / len(diagnostic_diffs) if diagnostic_diffs else None
    return stacked, sum(int(t.numel()) for t in losses), mean_diff


def l_impl_pair_logistic(
    batch: Batch,
    out: ScorerOutput,
    *,
    margin: float = 0.0,
) -> tuple[torch.Tensor, int, float | None]:
    """Logistic pairwise loss (LeCun 2006 §2.3) on whole-impl energies for
    (pass_impl, fail_impl) pairs in same spec.

    L = softplus(E_pos - E_neg + margin) = log(1 + exp(E_pos - E_neg + margin)).

    Unlike hinge, this asymptotes to zero but never reaches it — gradient
    persists even when positive beats negative by a wide margin. This is the
    fix for run-#9 / run-#10-v1 InfoNCE-style collapse where the contrastive
    loss saturates to exact zero and the inter-impl bias calibration gradient
    vanishes (Wang & Isola 2020 alignment-without-uniformity pathology).
    """
    if not batch.traj_triples:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    losses: list[torch.Tensor] = []
    diffs: list[float] = []
    for group in batch.traj_triples:
        if len(group) < 2:
            continue
        pos_idx = group[0]
        e_pos = out.whole_impl_energies[pos_idx]
        for neg_idx in group[1:]:
            e_neg = out.whole_impl_energies[neg_idx]
            losses.append(torch.nn.functional.softplus(e_pos - e_neg + margin))
            diffs.append((e_neg - e_pos).detach().float().item())
    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.stack(losses).mean()
    return stacked, len(losses), sum(diffs) / len(diffs)


def l_impl_pair_epa(
    batch: Batch,
    out: ScorerOutput,
    *,
    margin: float = 0.0,
    weak_weight: float = 0.2,
) -> tuple[torch.Tensor, int, float | None]:
    """Energy Preference Alignment loss (Hong et al., arXiv 2412.13862, Dec 2024).

    Replaces the Bradley-Terry / logistic pairwise loss with an EBM-native
    objective that has a unique MLE. For each PASS sibling, contrast against
    (a) one *strong* negative (the FAIL sibling, as in the existing loss) and
    (b) all other-impl negatives in the batch as *free weak* negatives.

    L_strong = softplus(E_pos - E_neg + margin)  -- same as logistic
    L_weak   = mean_k softplus(E_pos - E_other_k + margin) over all
              non-sibling impls in the batch
    L_total  = L_strong + weak_weight * L_weak

    The weak-negative pool gives EPA its unique-MLE property (vs. BT's
    underspecification) and matches our (PASS-sibling, FAIL-sibling, other-impl)
    data structure exactly. weak_weight=0.2 is the Hong et al. default.
    """
    if not batch.traj_triples:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None

    # Build the set of in-batch impl indices that are NOT in any traj_triple
    # (these are the free weak negatives — typically the safe broken impls).
    in_triple_idx = set()
    for group in batch.traj_triples:
        in_triple_idx.update(group)
    n_batch = out.whole_impl_energies.shape[0]
    weak_idx = [i for i in range(n_batch) if i not in in_triple_idx]

    strong_losses: list[torch.Tensor] = []
    weak_losses: list[torch.Tensor] = []
    diffs: list[float] = []
    for group in batch.traj_triples:
        if len(group) < 2:
            continue
        pos_idx = group[0]
        e_pos = out.whole_impl_energies[pos_idx]
        for neg_idx in group[1:]:
            e_neg = out.whole_impl_energies[neg_idx]
            strong_losses.append(
                torch.nn.functional.softplus(e_pos - e_neg + margin)
            )
            diffs.append((e_neg - e_pos).detach().float().item())
        # Weak negatives: contrast pos against every non-sibling impl.
        if weak_idx:
            e_weak = out.whole_impl_energies[weak_idx]  # (n_weak,)
            weak_losses.append(
                torch.nn.functional.softplus(e_pos - e_weak + margin).mean()
            )
    if not strong_losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    strong = torch.stack(strong_losses).mean()
    if weak_losses:
        weak = torch.stack(weak_losses).mean()
        total = strong + weak_weight * weak
    else:
        total = strong
    return total, len(strong_losses), sum(diffs) / len(diffs)


def l_line_listmle(
    batch: Batch,
    out: ScorerOutput,
    *,
    focal_gamma: float = 0.0,
    focal_balance: bool = False,
) -> tuple[torch.Tensor, int, float | None]:
    """Rank-aware listwise loss via ListMLE (Xia et al. 2008, ICML).

    Treats each impl as a ranked list with the buggy line(s) at the top.
    The likelihood of the target permutation factorizes as a product of
    Plackett-Luce CEs from the top down. Inherently weights top-1 most
    heavily (the first softmax has the most discriminative power), which
    is what we want for top-k localization.

    For each broken impl with k buggy lines:
      L = sum_{i=0..k-1} -log(exp(E[buggy_i]) / sum_{j in remaining} exp(E[j]))
    where "remaining" = unranked lines at step i.

    focal_gamma > 0: focal modulator (1 - p_target)^gamma on each per-step CE.
    focal_balance: weight each impl's loss by 1/n_buggy^0.5 so single-line
      bugs (the common case) get more gradient than multi-line bugs.
    """
    if not batch.safe_broken_indices:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    per_line = out.per_line_energies
    losses: list[torch.Tensor] = []
    confs: list[float] = []
    for b in batch.safe_broken_indices:
        e = per_line[b]
        buggy = batch.buggy_line_indices[b]
        n_lines = e.shape[0]
        n_buggy = int(buggy.numel())
        if n_lines < 2 or n_buggy == 0:
            continue
        # Build the top-down list: buggy lines first (in label order, which
        # is arbitrary but stable), then everything else.
        all_idx = torch.arange(n_lines, device=e.device)
        buggy_set = set(buggy.tolist())
        non_buggy = torch.tensor(
            [i for i in range(n_lines) if i not in buggy_set],
            dtype=torch.long, device=e.device,
        )
        # rank_order: [b_0, b_1, ..., b_{k-1}, non_0, non_1, ...]
        rank_order = torch.cat([buggy, non_buggy])

        step_losses: list[torch.Tensor] = []
        confs_b: list[float] = []
        # ListMLE: at each step i, softmax over remaining items, target = rank_order[i]
        for i in range(n_buggy):  # only loss-weight the buggy positions
            remaining = rank_order[i:]
            e_remaining = e.index_select(0, remaining)
            log_softmax = e_remaining.log_softmax(dim=-1)
            log_p_target = log_softmax[0]  # rank_order[i] is at position 0 of remaining
            per_step = -log_p_target
            if focal_gamma > 0:
                p = log_p_target.exp().detach()
                per_step = per_step * ((1.0 - p) ** focal_gamma)
            step_losses.append(per_step)
            confs_b.append(float(log_p_target.exp().detach().float().item()))
        impl_loss = torch.stack(step_losses).mean()
        if focal_balance:
            impl_loss = impl_loss / (float(n_buggy) ** 0.5)
        losses.append(impl_loss)
        if confs_b:
            confs.append(sum(confs_b) / len(confs_b))
    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.stack(losses).mean()
    return stacked, len(losses), (sum(confs) / len(confs)) if confs else None


# Keep legacy hinge variant for ablation/comparison.
def l_impl_pair_hinge(
    batch: Batch,
    out: ScorerOutput,
    *,
    margin: float,
) -> tuple[torch.Tensor, int, float | None]:
    """Pairwise HINGE on whole-impl energies. Saturates to zero past margin;
    kept for ablation. Production: use l_impl_pair_logistic instead."""
    if not batch.traj_triples:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    losses: list[torch.Tensor] = []
    diffs: list[float] = []
    for group in batch.traj_triples:
        if len(group) < 2:
            continue
        pos_idx = group[0]
        e_pos = out.whole_impl_energies[pos_idx]
        for neg_idx in group[1:]:
            e_neg = out.whole_impl_energies[neg_idx]
            losses.append(torch.clamp(margin + e_pos - e_neg, min=0.0))
            diffs.append((e_neg - e_pos).detach().float().item())
    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.stack(losses).mean()
    return stacked, len(losses), sum(diffs) / len(diffs)


def l_line_listwise(
    batch: Batch,
    out: ScorerOutput,
    *,
    label_smoothing: float = 0.05,
    focal_gamma: float = 0.0,
    focal_balance: bool = False,
) -> tuple[torch.Tensor, int, float | None]:
    """Within-impl listwise softmax cross-entropy. Treats per-line bug ID as
    a classification over the impl's lines, with the bug line as the target.

    For each broken impl with a single labeled bug line, computes
    -log(exp(E_b) / sum_i exp(E_i)) with optional label smoothing. If multiple
    bug lines are labeled, averages the loss over each bug-line target.

    Reference: ListNet (Cao et al. 2007); reduces to standard softmax-CE for
    one-positive lists.

    focal_gamma > 0: focal modulator (1 - p_target)^gamma on each per-target CE.
    focal_balance: divide each impl's loss by sqrt(n_buggy) so single-line
      bugs (the common case) get proportionally more gradient.
    """
    if not batch.safe_broken_indices:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    per_line = out.per_line_energies
    losses: list[torch.Tensor] = []
    confs: list[float] = []
    for b in batch.safe_broken_indices:
        e = per_line[b]
        buggy = batch.buggy_line_indices[b]
        n_lines = e.shape[0]
        if n_lines < 2 or buggy.numel() == 0:
            continue
        log_softmax = e.log_softmax(dim=-1)
        # Average CE over each labeled bug line target.
        per_target = -log_softmax[buggy]      # (n_buggy,)
        if label_smoothing > 0.0:
            # Smooth toward uniform: (1-eps) * CE(target) + eps * CE(uniform).
            uniform_ce = -log_softmax.mean()  # scalar
            per_target = (1.0 - label_smoothing) * per_target + label_smoothing * uniform_ce
        if focal_gamma > 0:
            p_target = log_softmax[buggy].exp().detach()  # (n_buggy,)
            per_target = per_target * ((1.0 - p_target) ** focal_gamma)
        impl_loss = per_target.mean()
        if focal_balance:
            impl_loss = impl_loss / (float(buggy.numel()) ** 0.5)
        losses.append(impl_loss)
        confs.append(log_softmax[buggy].exp().mean().detach().float().item())
    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.stack(losses).mean()
    return stacked, len(losses), (sum(confs) / len(confs)) if confs else None


def l_line_hinge_semi_hard(
    batch: Batch,
    out: ScorerOutput,
    *,
    margin: float,
    k: int = 3,
    rng: torch.Generator | None = None,
) -> tuple[torch.Tensor, int, float | None]:
    """Per-line pairwise hinge with semi-hard negative mining (FaceNet-style).

    Negative = uniformly sampled from the top-k highest-energy NON-bug lines.
    Top-k=3 by default avoids always-argmax collapse (Wu et al. 2017) while
    keeping gradient pressure on the hardest-discriminate cases.
    """
    if not batch.safe_broken_indices:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    per_line = out.per_line_energies
    losses: list[torch.Tensor] = []
    diffs: list[float] = []
    for b in batch.safe_broken_indices:
        e = per_line[b]
        buggy = batch.buggy_line_indices[b]
        n_lines = e.shape[0]
        if n_lines == 0 or buggy.numel() == 0:
            continue
        buggy_set = set(buggy.tolist())
        non_buggy = [i for i in range(n_lines) if i not in buggy_set]
        if not non_buggy:
            continue
        # Rank non-buggy lines by current energy (descending), pick top-k.
        non_buggy_t = torch.tensor(non_buggy, dtype=torch.long, device=e.device)
        nb_energies = e.index_select(0, non_buggy_t).detach()
        k_use = min(k, non_buggy_t.numel())
        topk_idx = torch.topk(nb_energies, k_use).indices
        # Sample one of the top-k uniformly per buggy line target.
        if rng is not None:
            choices = torch.randint(0, k_use, (buggy.numel(),), generator=rng)
        else:
            choices = torch.randint(0, k_use, (buggy.numel(),))
        chosen_nb = non_buggy_t[topk_idx[choices.to(topk_idx.device)]]
        e_b = e[buggy]
        e_nb = e[chosen_nb]
        # Logistic pairwise (LeCun 2006 §2.3): softplus(margin + E_nb - E_b).
        # Asymptotes to zero but never saturates — avoids the same collapse
        # mode as the impl-pair loss. Margin acts as a "preferred gap" rather
        # than a hard threshold.
        pair_loss = torch.nn.functional.softplus(margin + e_nb - e_b)
        losses.append(pair_loss)
        diffs.append((e_b.mean() - e_nb.mean()).detach().float().item())
    if not losses:
        ref = out.whole_impl_energies
        return _zero_loss_like(ref), 0, None
    stacked = torch.cat(losses).mean()
    return stacked, sum(int(t.numel()) for t in losses), (
        sum(diffs) / len(diffs) if diffs else None
    )


def compute_hybrid_loss(
    batch: Batch,
    out: ScorerOutput,
    *,
    lambda_scalar: float,
    lambda_listwise: float,
    lambda_pairwise: float,
    line_margin: float,
    listwise_label_smoothing: float = 0.05,
    semi_hard_k: int = 3,
    impl_pair_loss: str = "logistic",
    listwise_loss: str = "listnet",
    focal_gamma: float = 0.0,
    focal_balance: bool = False,
    epa_weak_weight: float = 0.2,
    rng: torch.Generator | None = None,
) -> LossOutput:
    """Run-#10 hybrid loss (Alt A+/v2): scalar impl-pair LOGISTIC + per-line
    listwise CE + per-line semi-hard LOGISTIC pairwise. All three are softplus-
    based (LeCun 2006 §2.3) — they asymptote to zero but never saturate to
    exact zero, avoiding the InfoNCE-style collapse that broke runs #8/#9.

    Knobs for run #11:
      impl_pair_loss: "logistic" (default) | "hinge" (A4) | "epa" (Hong 2024)
      listwise_loss:  "listnet"  (default) | "listmle" (rank-aware, Xia 2008)
      focal_gamma:    >0 applies focal modulator on per-target CE in listwise loss
      focal_balance:  divide listwise loss by sqrt(n_buggy) per impl
      epa_weak_weight: weight on EPA's weak-negative term (only used if impl_pair_loss=epa)
    """
    # One-shot diagnostic on first call: report batch composition so we can see
    # whether line=0.0000 in the log is a real saturation or a sampler bug.
    import os
    if os.environ.get("EBM_DEBUG_BATCH", "0") == "1":
        if not hasattr(compute_hybrid_loss, "_dbg_count"):
            compute_hybrid_loss._dbg_count = 0
        if compute_hybrid_loss._dbg_count < 5:
            n_safe_broken = len(batch.safe_broken_indices)
            n_traj_groups = len(batch.traj_triples)
            line_count_safe = [
                (out.per_line_energies[b].shape[0], batch.buggy_line_indices[b].numel())
                for b in batch.safe_broken_indices
            ]
            print(
                f"  [DBG batch #{compute_hybrid_loss._dbg_count}] "
                f"safe_broken={n_safe_broken} traj_groups={n_traj_groups} "
                f"safe_(n_lines,n_buggy)={line_count_safe[:6]}",
                flush=True,
            )
            compute_hybrid_loss._dbg_count += 1
    if impl_pair_loss == "hinge":
        scalar_loss, n_scalar, scalar_diff = l_impl_pair_hinge(batch, out, margin=1.0)
    elif impl_pair_loss == "epa":
        scalar_loss, n_scalar, scalar_diff = l_impl_pair_epa(
            batch, out, margin=0.0, weak_weight=epa_weak_weight,
        )
    else:
        scalar_loss, n_scalar, scalar_diff = l_impl_pair_logistic(batch, out, margin=0.0)
    if listwise_loss == "listmle":
        list_loss, n_list, _list_conf = l_line_listmle(
            batch, out, focal_gamma=focal_gamma, focal_balance=focal_balance,
        )
    else:
        list_loss, n_list, _list_conf = l_line_listwise(
            batch, out, label_smoothing=listwise_label_smoothing,
            focal_gamma=focal_gamma, focal_balance=focal_balance,
        )
    pair_loss, n_pair, pair_diff = l_line_hinge_semi_hard(
        batch, out, margin=line_margin, k=semi_hard_k, rng=rng,
    )
    total = (
        lambda_scalar * scalar_loss
        + lambda_listwise * list_loss
        + lambda_pairwise * pair_loss
    )
    return LossOutput(
        total=total,
        spec=scalar_loss.detach(),         # repurpose "spec" slot for scalar loss
        line=(list_loss + pair_loss).detach(),
        n_spec_groups=n_scalar,
        n_line_pairs=n_list + n_pair,
        spec_pos_minus_neg_mean=scalar_diff,
        line_buggy_minus_clean_mean=pair_diff,
    )


def compute_loss(
    batch: Batch,
    out: ScorerOutput,
    *,
    lambda_spec: float,
    lambda_line: float,
    line_margin: float,
    pairs_per_impl: int = 4,
    rng: torch.Generator | None = None,
) -> LossOutput:
    spec_loss, n_spec, spec_diff = l_spec_infonce(batch, out)
    line_loss, n_pairs, line_diff = l_line_hinge(
        batch, out, margin=line_margin, pairs_per_impl=pairs_per_impl, rng=rng,
    )
    total = lambda_spec * spec_loss + lambda_line * line_loss
    return LossOutput(
        total=total,
        spec=spec_loss.detach(),
        line=line_loss.detach(),
        n_spec_groups=n_spec,
        n_line_pairs=n_pairs,
        spec_pos_minus_neg_mean=spec_diff,
        line_buggy_minus_clean_mean=line_diff,
    )


def compute_orm_loss(
    batch: Batch,
    out: ScorerOutput,
    *,
    pos_weight: float = 1.0,
) -> LossOutput:
    """A5 ablation: ORM-style pointwise BCE on whole-impl energy vs PASS/FAIL.

    Same architecture (sentinel head + LSE aggregator) — only the loss
    changes. The whole-impl energy is treated as a logit (high = FAIL),
    BCE against the binary status label.

    This is the *outcome reward model* baseline from the Lightman/PRM
    literature. If even *this* baseline hits the AUROC ceiling on sibling
    broken/fixed pairs (Cobbe 2021 finding), it empirically confirms the
    info-theoretic ceiling argument: the limit is the data structure, not
    our loss.

    Impls with status=UNKNOWN are skipped.
    """
    whole = out.whole_impl_energies  # (B,)
    if whole.numel() == 0:
        return LossOutput(
            total=_zero_loss_like(whole),
            spec=_zero_loss_like(whole).detach(),
            line=_zero_loss_like(whole).detach(),
            n_spec_groups=0, n_line_pairs=0,
            spec_pos_minus_neg_mean=None, line_buggy_minus_clean_mean=None,
        )

    labels: list[float] = []
    keep_idx: list[int] = []
    for i, s in enumerate(batch.statuses):
        if s == Status.PASS:
            labels.append(0.0)
            keep_idx.append(i)
        elif s == Status.FAIL:
            labels.append(1.0)
            keep_idx.append(i)
        # UNKNOWN dropped
    if not keep_idx:
        return LossOutput(
            total=_zero_loss_like(whole),
            spec=_zero_loss_like(whole).detach(),
            line=_zero_loss_like(whole).detach(),
            n_spec_groups=0, n_line_pairs=0,
            spec_pos_minus_neg_mean=None, line_buggy_minus_clean_mean=None,
        )
    sel = whole.new_tensor(keep_idx, dtype=torch.long)
    logits = whole.index_select(0, sel)
    labels_t = whole.new_tensor(labels)
    pw = whole.new_tensor(pos_weight)
    loss = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, labels_t, pos_weight=pw, reduction="mean",
    )
    # Diagnostic: mean(E_FAIL) - mean(E_PASS).
    pass_mask = labels_t == 0.0
    fail_mask = labels_t == 1.0
    if pass_mask.any() and fail_mask.any():
        d = (logits[fail_mask].mean() - logits[pass_mask].mean()).detach().float().item()
    else:
        d = None

    return LossOutput(
        total=loss,
        spec=loss.detach(),  # report under "spec" since it's whole-impl
        line=_zero_loss_like(whole).detach(),
        n_spec_groups=len(keep_idx),
        n_line_pairs=0,
        spec_pos_minus_neg_mean=d,
        line_buggy_minus_clean_mean=None,
    )


def compute_bce_loss(
    batch: Batch,
    out: ScorerOutput,
    *,
    pos_weight: float = 10.0,
) -> LossOutput:
    """Pointwise BCE-with-logits on per-line buggy/not-buggy labels.

    This is the E7 ablation: same backbone + sentinel-head architecture, but
    pointwise supervision instead of contrastive. For each impl with non-empty
    ``buggy_line_indices``, label per-sentinel position as 1 if in
    ``buggy_line_indices`` else 0. Treat the per-line energy as a logit.

    Impls without ``buggy_line_indices`` (e.g., PASS or system_trajectory FAIL)
    contribute nothing — there's no supervision signal in this loss for them.

    ``pos_weight`` handles class imbalance: with ~1-3 buggy lines per ~30-line
    impl, the negative class is ~10x more common.

    Reports the same ``LossOutput`` shape with ``line`` field carrying the BCE
    loss and ``spec`` = 0 (BCE has no whole-impl term).
    """
    per_line = out.per_line_energies
    if not per_line:
        ref = out.whole_impl_energies
        return LossOutput(
            total=_zero_loss_like(ref),
            spec=_zero_loss_like(ref).detach(),
            line=_zero_loss_like(ref).detach(),
            n_spec_groups=0, n_line_pairs=0,
            spec_pos_minus_neg_mean=None, line_buggy_minus_clean_mean=None,
        )

    losses: list[torch.Tensor] = []
    diagnostic_diffs: list[float] = []
    n_impls_used = 0
    pw = per_line[0].new_tensor(pos_weight)
    for b in range(len(per_line)):
        e = per_line[b]
        buggy = batch.buggy_line_indices[b]
        n_lines = e.shape[0]
        if n_lines == 0 or buggy.numel() == 0:
            continue
        labels = e.new_zeros(n_lines)
        # buggy indices are sentinel-space (same as e). Clip to in-range.
        valid_buggy = buggy[(buggy >= 0) & (buggy < n_lines)]
        if valid_buggy.numel() == 0:
            continue
        labels[valid_buggy] = 1.0
        loss = torch.nn.functional.binary_cross_entropy_with_logits(
            e, labels, pos_weight=pw, reduction="mean"
        )
        losses.append(loss)
        # Diagnostic: mean(E_buggy) - mean(E_non_buggy)
        non_b = labels == 0.0
        if non_b.any() and (labels == 1.0).any():
            d = (e[labels == 1.0].mean() - e[non_b].mean()).detach().float().item()
            diagnostic_diffs.append(d)
        n_impls_used += 1

    ref = out.whole_impl_energies
    if not losses:
        z = _zero_loss_like(ref)
        return LossOutput(
            total=z, spec=z.detach(), line=z.detach(),
            n_spec_groups=0, n_line_pairs=0,
            spec_pos_minus_neg_mean=None, line_buggy_minus_clean_mean=None,
        )
    total = torch.stack(losses).mean()
    mean_diff = sum(diagnostic_diffs) / len(diagnostic_diffs) if diagnostic_diffs else None
    return LossOutput(
        total=total,
        spec=_zero_loss_like(ref).detach(),
        line=total.detach(),
        n_spec_groups=0,
        n_line_pairs=n_impls_used,
        spec_pos_minus_neg_mean=None,
        line_buggy_minus_clean_mean=mean_diff,
    )
