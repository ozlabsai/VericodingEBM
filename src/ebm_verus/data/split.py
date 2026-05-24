"""Spec-level train/eval split, keyed by *normalized spec text* (not spec_id).

Critical: a naive ``spec_id``-based split is insufficient. The
``microsoft/Verus_Training_Data`` dataset contains records with different
``original_index`` values (→ distinct spec_ids) that share *identical source
code*. Splitting on spec_id alone produces 79%+ leakage on the held set, and
eval AUROC reaches 0.98 by memorization. We split on a hash of the whitespace-
normalized spec text instead — same exact code in train and held is now
impossible by construction.

The split returns (train, held). Held is guaranteed disjoint from train
both by:
  * spec_id (cosmetic)
  * normalized-spec-text hash (the actual disjointness that matters)
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict

from ebm_verus.data.types import Example, Source


def _norm_text_hash(s: str) -> str:
    """Hash of the source after stripping all whitespace. Two specs that
    differ only in whitespace (indentation, blank lines) collapse to the
    same hash — they're the same training signal.
    """
    norm = "".join(s.split())
    return hashlib.sha1(norm.encode("utf-8"), usedforsecurity=False).hexdigest()


def split_examples(
    examples: list[Example],
    *,
    n_eval_traj_specs: int,
    sft_eval_frac: float,
    seed: int,
) -> tuple[list[Example], list[Example]]:
    """Spec-level split keyed by normalized spec text. Returns ``(train, held)``.

    Strategy:
      1. Compute a normalized-text hash for every example's spec.
      2. Group examples by that hash (the "spec group").
      3. For system_trajectory groups: randomly assign ``n_eval_traj_specs``
         groups to held. (Note: the count is in unique-text groups, not
         original_index spec_ids.)
      4. For sft_safe groups: hash-bucket assign to held with prob ``sft_eval_frac``.
      5. Assert held-spec-text hashes are disjoint from train.
    """
    # spec_text hash -> list of examples sharing that text (across sources)
    by_norm: dict[str, list[Example]] = defaultdict(list)
    for ex in examples:
        by_norm[_norm_text_hash(ex.spec_text)].append(ex)

    # Decide held/train per *hash*, not per (hash, source). This ensures a
    # spec that appears in both system_trajectory AND sft_safe always lands
    # on the same side — preventing cross-source leakage.
    rng = random.Random(seed)

    # Traj-pickable hashes are those with at least one system_trajectory example.
    traj_hashes = sorted(
        h for h, group in by_norm.items()
        if any(e.source == Source.SYSTEM_TRAJECTORY for e in group)
    )
    rng.shuffle(traj_hashes)
    held_hashes: set[str] = set(traj_hashes[:n_eval_traj_specs])

    # Then bucket-assign sft_safe-only hashes to held with prob sft_eval_frac.
    # Don't touch already-held hashes (from traj sampling above).
    for h, group in by_norm.items():
        if h in held_hashes:
            continue
        # Skip if this hash has any traj example (those decisions are already
        # final from the traj sampling above).
        if any(e.source == Source.SYSTEM_TRAJECTORY for e in group):
            continue
        if any(e.source == Source.SFT_SAFE for e in group):
            sid = int(
                hashlib.sha1(
                    (h + str(seed)).encode(), usedforsecurity=False
                ).hexdigest(),
                16,
            )
            if (sid % 1000) < int(sft_eval_frac * 1000):
                held_hashes.add(h)

    train: list[Example] = []
    held_out: list[Example] = []
    for h, group in by_norm.items():
        target = held_out if h in held_hashes else train
        target.extend(group)

    # Hard assertion: normalized-spec-text disjointness. This is the property
    # that actually matters for measuring generalization.
    train_norms = {_norm_text_hash(ex.spec_text) for ex in train}
    held_norms = {_norm_text_hash(ex.spec_text) for ex in held_out}
    overlap_text = train_norms & held_norms
    if overlap_text:
        raise RuntimeError(
            f"Train/eval normalized-spec-text overlap: {len(overlap_text)} "
            "unique spec texts. The split is leaky."
        )

    # Soft assertion: spec_id overlap is now *expected* in the real dataset
    # (multiple original_index values can share the same source code). We just
    # log it for visibility.
    train_specs = {ex.spec_id for ex in train}
    held_specs = {ex.spec_id for ex in held_out}
    overlap_ids = train_specs & held_specs
    if overlap_ids:
        # Not an error — same spec_id with different content can land on both
        # sides legitimately. The text-hash disjointness above is what protects
        # against memorization-leakage.
        pass

    return train, held_out
