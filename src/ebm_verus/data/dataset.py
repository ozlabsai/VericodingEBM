"""PyTorch Dataset + collator + mixed sampler.

The sampler enforces per-batch source mixing so InfoNCE in-batch negatives are
not catastrophically correlated (per critique #4):

    each batch contains
      >= batch_min_traj_triples complete system-trajectory triples
      >= batch_min_safe_pairs   sft_safe (broken, fixed) pairs

This gives both losses non-empty signal every step and prevents the failure
mode where the contrastive loss has zero gradient because the batch is all
sft_safe pairs (which don't form within-spec triples) or all traj triples
(which have no within-impl line labels).
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

import torch
from torch.utils.data import Dataset, IterableDataset
from transformers import PreTrainedTokenizerBase

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data.marker_augment import MarkerAugmenter
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status, TokenizedExample


class ExampleDataset(Dataset):
    """Static-list dataset of ``Example`` rows. Tokenization is lazy."""

    def __init__(
        self,
        examples: list[Example],
        tokenizer: PreTrainedTokenizerBase,
        *,
        max_length: int,
        sentinel_token: str = SENTINEL_TOKEN,
    ) -> None:
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.sentinel_token = sentinel_token

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> TokenizedExample | None:
        return tokenize_example(
            self.examples[idx],
            self.tokenizer,
            max_length=self.max_length,
            sentinel_token=self.sentinel_token,
        )


# ---- batch structure --------------------------------------------------------


@dataclass
class Batch:
    """A model-ready batch.

    ``input_ids`` / ``attention_mask`` are standard padded tensors.

    Per-example index lists (variable length) are kept as Python lists of
    tensors; the model uses them to gather sentinel positions during the
    forward pass.

    Group metadata used by the losses:
      * ``traj_triples``: list of lists of batch-indices; each inner list is a
        complete (≥2) within-spec triple from system_trajectory. The first
        element is the index of a PASSING impl (positive); the rest are
        FAILING (negatives). Empty inner lists are not produced — only triples
        with mixed labels are added.
      * ``safe_broken_indices``: batch-indices of FAIL-labeled sft_safe impls
        (each has buggy_line_indices set).
    """

    input_ids: torch.Tensor                 # (B, L)
    attention_mask: torch.Tensor            # (B, L)
    sentinel_positions: list[torch.Tensor]  # length B, each (n_lines_i,)
    buggy_line_indices: list[torch.Tensor]  # length B, each (n_buggy_i,), values in [0, n_lines_i)
    statuses: list[Status]                  # length B
    sources: list[Source]                   # length B
    spec_ids: list[str]                     # length B

    traj_triples: list[list[int]]
    safe_broken_indices: list[int]


def _collate(
    items: list[TokenizedExample],
    pad_token_id: int,
) -> Batch:
    # Drop Nones (tokenization failures).
    items = [it for it in items if it is not None]
    if not items:
        raise RuntimeError("Empty batch after dropping None items")

    max_len = max(len(it.input_ids) for it in items)
    B = len(items)
    input_ids = torch.full((B, max_len), pad_token_id, dtype=torch.long)
    attention_mask = torch.zeros((B, max_len), dtype=torch.long)

    sentinel_positions: list[torch.Tensor] = []
    buggy_line_indices: list[torch.Tensor] = []
    statuses: list[Status] = []
    sources: list[Source] = []
    spec_ids: list[str] = []

    for i, it in enumerate(items):
        L = len(it.input_ids)
        input_ids[i, :L] = torch.tensor(it.input_ids, dtype=torch.long)
        attention_mask[i, :L] = 1
        sentinel_positions.append(torch.tensor(it.sentinel_positions, dtype=torch.long))
        buggy_line_indices.append(
            torch.tensor(sorted(it.buggy_line_indices), dtype=torch.long)
        )
        statuses.append(it.example.status)
        sources.append(it.example.source)
        spec_ids.append(it.example.spec_id)

    # Build group metadata.
    by_spec_traj: dict[str, list[int]] = defaultdict(list)
    safe_broken_indices: list[int] = []
    for i, it in enumerate(items):
        ex = it.example
        if ex.source == Source.SYSTEM_TRAJECTORY:
            by_spec_traj[ex.spec_id].append(i)
        elif ex.source == Source.SFT_SAFE and ex.status == Status.FAIL:
            if len(it.buggy_line_indices) > 0:
                safe_broken_indices.append(i)

    traj_triples: list[list[int]] = []
    for _spec, idxs in by_spec_traj.items():
        # Need at least one PASS and one FAIL in the group for a useful contrast.
        pass_idxs = [i for i in idxs if statuses[i] == Status.PASS]
        fail_idxs = [i for i in idxs if statuses[i] == Status.FAIL]
        if pass_idxs and fail_idxs:
            # Use first PASS as anchor; all FAIL as negatives in the local group.
            traj_triples.append([pass_idxs[0], *fail_idxs])

    return Batch(
        input_ids=input_ids,
        attention_mask=attention_mask,
        sentinel_positions=sentinel_positions,
        buggy_line_indices=buggy_line_indices,
        statuses=statuses,
        sources=sources,
        spec_ids=spec_ids,
        traj_triples=traj_triples,
        safe_broken_indices=safe_broken_indices,
    )


# ---- mixed sampler ----------------------------------------------------------


class MixedSourceIterableDataset(IterableDataset):
    """Yields batches with enforced per-batch source composition.

    Each batch contains:
      * ``min_traj_triples`` system-trajectory triples (each contributing all 3
        impls — typically 2-3 examples per triple after dedup)
      * ``min_safe_pairs`` sft_safe (broken, fixed) pairs (2 examples each)
      * filled out to ``batch_size`` examples with random extras from either pool

    This is an IterableDataset rather than a Sampler because the unit of
    sampling is a *triple/pair group*, not an individual example, which the
    standard PyTorch Sampler API doesn't express cleanly.
    """

    def __init__(
        self,
        train_examples: list[Example],
        tokenizer: PreTrainedTokenizerBase,
        *,
        batch_size: int,
        min_traj_triples: int,
        min_safe_pairs: int,
        max_length: int,
        seed: int,
        epoch: int = 0,
        verbose: bool = True,
        marker_aug_k: int = 1,
        marker_aug_prob: float = 0.5,
        marker_aug_positive_prob: float = 0.3,
        marker_aug_mode: str = "v6",
    ) -> None:
        self.tokenizer = tokenizer
        self.batch_size = batch_size
        self.min_traj_triples = min_traj_triples
        self.min_safe_pairs = min_safe_pairs
        self.max_length = max_length
        self.seed = seed
        self.epoch = epoch
        self.marker_aug_k = marker_aug_k

        # ---- Marker augmenter (counterfactual, per V6 research) ----
        # marker_aug_k=1 disables augmentation (just the original example).
        # k>1 pre-materializes (k-1) marker-perturbed copies per example. The
        # sampler picks uniformly among the k copies per epoch, giving the
        # LoRA varied marker placements without re-tokenizing per epoch.
        augmenter = (MarkerAugmenter(
            marker_prob=marker_aug_prob,
            positive_prob=marker_aug_positive_prob,
            seed=seed,
            mode=marker_aug_mode,
        ) if marker_aug_k > 1 else None)

        def _expand(ex: Example) -> list[Example]:
            if augmenter is None:
                return [ex]
            return augmenter.augment_example(ex, k=marker_aug_k)

        # ---- Pre-tokenize every example once, drop tokenization failures.
        # Cache results keyed by impl_id so __iter__ doesn't re-tokenize.
        # With marker_aug_k>1 we tokenize K copies per Example, each with a
        # different marker placement; the sampler later picks uniformly.
        traj_tokenized: dict[str, list[TokenizedExample]] = defaultdict(list)
        safe_tokenized: dict[str, list[TokenizedExample]] = defaultdict(list)
        n_traj_in = 0
        n_traj_kept = 0
        n_safe_in = 0
        n_safe_kept = 0
        for ex in train_examples:
            for variant in _expand(ex):
                if variant.source == Source.SYSTEM_TRAJECTORY:
                    n_traj_in += 1
                    t = tokenize_example(variant, tokenizer, max_length=max_length)
                    if t is not None:
                        traj_tokenized[variant.spec_id].append(t)
                        n_traj_kept += 1
                elif variant.source == Source.SFT_SAFE:
                    n_safe_in += 1
                    t = tokenize_example(variant, tokenizer, max_length=max_length)
                    if t is not None:
                        # For sft_safe FAIL examples, also require non-empty
                        # buggy_line_indices — otherwise L_line gets no signal.
                        if variant.status == Status.FAIL and not t.buggy_line_indices:
                            continue
                        safe_tokenized[variant.spec_id].append(t)
                        n_safe_kept += 1

        # ---- Filter spec groups: only keep specs viable for contrastive use.
        # Mixed-label traj specs must have BOTH ≥1 PASS and ≥1 FAIL surviving.
        viable_traj_spec_ids: list[str] = []
        for spec_id, items in traj_tokenized.items():
            has_pass = any(t.example.status == Status.PASS for t in items)
            has_fail = any(t.example.status == Status.FAIL for t in items)
            if has_pass and has_fail:
                viable_traj_spec_ids.append(spec_id)
        # sft_safe pairs need ≥1 FAIL impl with buggy_lines (L_line signal).
        viable_safe_spec_ids: list[str] = []
        for spec_id, items in safe_tokenized.items():
            has_broken_with_labels = any(
                t.example.status == Status.FAIL and t.buggy_line_indices
                for t in items
            )
            if has_broken_with_labels:
                viable_safe_spec_ids.append(spec_id)

        self.traj_tokenized = traj_tokenized
        self.safe_tokenized = safe_tokenized
        self.viable_traj_spec_ids = viable_traj_spec_ids
        self.viable_safe_spec_ids = viable_safe_spec_ids

        if verbose:
            print(
                f"  [sampler] traj examples: {n_traj_kept}/{n_traj_in} kept "
                f"after tokenization. "
                f"viable mixed-label traj specs: {len(viable_traj_spec_ids)}",
                flush=True,
            )
            print(
                f"  [sampler] safe examples: {n_safe_kept}/{n_safe_in} kept. "
                f"viable safe specs (with broken+buggy_lines): "
                f"{len(viable_safe_spec_ids)}",
                flush=True,
            )

        if not viable_traj_spec_ids:
            raise RuntimeError(
                "No viable mixed-label traj specs survived tokenization filter. "
                f"max_length={max_length} may be too low."
            )
        if not viable_safe_spec_ids:
            raise RuntimeError(
                "No viable sft_safe specs survived tokenization filter."
            )

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __iter__(self):
        rng = random.Random(self.seed + 1000 * self.epoch)
        traj_pool = list(self.viable_traj_spec_ids)
        safe_pool = list(self.viable_safe_spec_ids)
        rng.shuffle(traj_pool)
        rng.shuffle(safe_pool)

        ti = 0
        si = 0
        while True:
            # Wrap pools.
            if ti + self.min_traj_triples > len(traj_pool):
                rng.shuffle(traj_pool)
                ti = 0
            if si + self.min_safe_pairs > len(safe_pool):
                rng.shuffle(safe_pool)
                si = 0

            tokenized: list[TokenizedExample] = []

            # Pick triples — every viable traj spec has both PASS and FAIL.
            for _ in range(self.min_traj_triples):
                spec = traj_pool[ti]
                ti += 1
                tokenized.extend(self.traj_tokenized[spec])

            # Pick safe pairs — every viable safe spec has at least one FAIL
            # with buggy_lines.
            for _ in range(self.min_safe_pairs):
                spec = safe_pool[si]
                si += 1
                tokenized.extend(self.safe_tokenized[spec])

            # Truncate to batch_size if we overshot.
            tokenized = tokenized[: self.batch_size]

            yield tokenized


def make_collate_fn(pad_token_id: int):
    def _fn(items: list[TokenizedExample]) -> Batch:
        return _collate(items, pad_token_id=pad_token_id)
    return _fn
