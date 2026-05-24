"""Sentinel insertion + tokenization.

Given an ``Example`` and a tokenizer, produce a ``TokenizedExample`` with:
  - input_ids = tokens(spec) + [sep newline] + tokens(impl with sentinels)
  - sentinel_positions = indices in input_ids where the sentinel id appears
  - buggy_line_indices = which sentinels correspond to buggy lines

Sentinel placement: one sentinel token is appended AFTER each scorable impl
source line (immediately after the trailing newline). Non-scorable lines (empty,
comment-only) are kept in the text (so the impl reads naturally) but receive no
sentinel.
"""

from __future__ import annotations

from transformers import PreTrainedTokenizerBase

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data.line_policy import is_scorable_line
from ebm_verus.data.types import Example, TokenizedExample


def insert_sentinels(impl_text: str, sentinel: str = SENTINEL_TOKEN) -> tuple[str, list[int]]:
    """Append a sentinel after each scorable source line.

    Returns ``(text_with_sentinels, scorable_line_source_indices)`` where
    ``scorable_line_source_indices[k]`` is the source-line index of the
    k-th sentinel.
    """
    lines = impl_text.splitlines()
    out_parts: list[str] = []
    scorable_src_indices: list[int] = []
    for i, line in enumerate(lines):
        out_parts.append(line)
        if is_scorable_line(line):
            # Sentinel appears on its own after the line content.
            out_parts.append(sentinel)
            scorable_src_indices.append(i)
    return "\n".join(out_parts), scorable_src_indices


def _spec_impl_join(spec_text: str, impl_with_sentinels: str) -> str:
    """Join spec + impl with a clear textual boundary."""
    spec = spec_text.rstrip()
    impl = impl_with_sentinels.lstrip("\n")
    return spec + "\n" + impl


def tokenize_example(
    ex: Example,
    tokenizer: PreTrainedTokenizerBase,
    *,
    max_length: int,
    sentinel_token: str = SENTINEL_TOKEN,
) -> TokenizedExample | None:
    """Tokenize an Example. Returns None if the result exceeds ``max_length``
    or has no scorable lines after sentinel insertion.
    """
    sentinel_id = tokenizer.encode(sentinel_token, add_special_tokens=False)
    if len(sentinel_id) != 1:
        raise ValueError(
            f"Sentinel {sentinel_token!r} must be a single token; got {sentinel_id}"
        )
    sid = sentinel_id[0]

    impl_with, scorable_src = insert_sentinels(ex.impl_text, sentinel_token)
    if not scorable_src:
        return None  # impl has no scorable lines (all blank/comments)

    # Tokenize spec and impl separately so we can record where the boundary is.
    spec_ids = tokenizer.encode(ex.spec_text.rstrip() + "\n", add_special_tokens=False)
    impl_ids = tokenizer.encode(impl_with.lstrip("\n"), add_special_tokens=False)

    input_ids = spec_ids + impl_ids
    if len(input_ids) > max_length:
        return None  # too long; caller can choose to truncate or drop

    sentinel_positions = [i for i, t in enumerate(input_ids) if t == sid]

    # Sanity: number of sentinel tokens in input_ids should equal scorable lines.
    # If not, the tokenizer fragmented something unexpectedly — drop the example
    # rather than silently corrupting labels.
    if len(sentinel_positions) != len(scorable_src):
        return None

    # Map ex.buggy_lines (source-line indices) into sentinel-index space.
    # buggy_line_indices[k] is True iff the k-th sentinel corresponds to a buggy line.
    src_to_sentinel = {src: k for k, src in enumerate(scorable_src)}
    buggy_line_indices = {
        src_to_sentinel[src] for src in ex.buggy_lines if src in src_to_sentinel
    }

    return TokenizedExample(
        example=ex,
        input_ids=input_ids,
        sentinel_positions=sentinel_positions,
        buggy_line_indices=buggy_line_indices,
        spec_token_count=len(spec_ids),
    )
