"""Shared types for the data pipeline.

A training example is a single (spec, impl) pair with metadata. The two source
datasets (system_trajectory_843, sft_safe_25k) are normalized into the same
``Example`` shape so downstream code only ever sees one structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Source(str, Enum):
    """Which raw dataset this example came from."""

    SYSTEM_TRAJECTORY = "system_trajectory"
    SFT_SAFE = "sft_safe"


class Status(str, Enum):
    """Verifier verdict on this impl."""

    PASS = "pass"     # Verus accepts impl against spec
    FAIL = "fail"     # Verus rejects (error or timeout)
    UNKNOWN = "unknown"  # missing / unparsed; should be rare and dropped


@dataclass
class Example:
    """A single (spec, impl) row with all derived fields needed for training.

    ``spec_text`` and ``impl_text`` are *source text*, not tokens. Sentinel
    insertion + tokenization happen later (in the collator).

    ``buggy_lines`` is in *impl source-line indices*, 0-indexed. Empty set for
    passing impls and for failing impls where we have no localization signal
    (e.g., system_trajectory rows — verifier-cited lines are NOT used per
    critique 1a).
    """

    source: Source
    spec_id: str               # groups impls that share a spec (for spec-level split + L_spec)
    impl_id: str               # unique per row
    spec_text: str
    impl_text: str
    status: Status
    buggy_lines: set[int] = field(default_factory=set)

    # Optional metadata, currently unused in training but kept for analysis / debug.
    rep_index: int | None = None       # 0/1/2 for system_trajectory; None for sft_safe
    verifier_log: str | None = None    # raw log text if available
    sibling_impl_id: str | None = None # for sft_safe: id of the paired (broken,fixed) twin

    def __post_init__(self) -> None:
        if not isinstance(self.buggy_lines, set):
            self.buggy_lines = set(self.buggy_lines)


@dataclass
class TokenizedExample:
    """An ``Example`` after sentinel insertion + tokenization.

    ``sentinel_positions`` are 0-indexed positions in ``input_ids`` where the
    sentinel token id appears. There is one sentinel per *scorable* impl source
    line, in source order. ``buggy_line_indices`` indexes into
    ``sentinel_positions`` (NOT into raw impl line numbers) — i.e., it points at
    which sentinels correspond to buggy lines after non-scorable lines have been
    dropped.
    """

    example: Example
    input_ids: list[int]
    sentinel_positions: list[int]
    buggy_line_indices: set[int]
    spec_token_count: int      # how many tokens at the start are spec (vs impl)
