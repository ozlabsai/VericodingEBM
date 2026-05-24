"""Parsers for the two raw data sources.

* ``parse_system_trajectory``: streams ``system_trajectory_843.jsonl`` and yields
  ``Example`` rows. Verifier-cited lines are NOT used as ``buggy_lines`` (per
  critique 1a); ``buggy_lines`` is always empty here. These rows contribute
  only to L_spec (whole-impl pass/fail contrast).

* ``parse_sft_safe``: streams ``sft_safe_25k.json``, identifies (broken, fixed)
  pairs, and yields one ``Example`` per side of each pair. For broken impls,
  ``buggy_lines`` = lines that changed in the broken→fixed diff. For fixed
  impls, ``buggy_lines`` = empty.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

import ijson

from ebm_verus.constants import DEFAULT_MAX_DIFF_LINES
from ebm_verus.data.line_policy import split_spec_impl
from ebm_verus.data.types import Example, Source, Status

# ---- system_trajectory_843 --------------------------------------------------


def _status_from_traj(status: str) -> Status:
    if status == "success":
        return Status.PASS
    if status in ("error", "timeout"):
        return Status.FAIL
    return Status.UNKNOWN


def _parse_original_item(raw: str | dict | None) -> dict:
    """``original_item`` is a JSON-encoded string in ``system_trajectory_843``.
    Returns an empty dict on parse failure.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def parse_system_trajectory(path: str | Path) -> Iterator[Example]:
    """Stream ``system_trajectory_843.jsonl`` -> Example.

    Schema observation (verified on real data, 2026-05-21):
      * PASS rows: ``verified_code`` holds the impl that passed Verus.
      * FAIL rows (error/timeout): ``verified_code`` and ``input_code`` are empty.
        The model's failing attempt lives inside ``original_item`` (a
        JSON-encoded *string*) at key ``output``; the original prompt with the
        spec is at ``original_item.input``.

    For uniformity we always pull (spec, impl) from these sources:
      * PASS impl   = ``verified_code``
      * FAIL impl   = ``original_item.output`` (extracted from the ```rust block)
      * Spec        = either ``verified_code`` (PASS, has full code) or
                      ``original_item.input`` (FAIL, has spec + holes).
    """
    path = Path(path)
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            status = _status_from_traj(row.get("status", ""))
            if status == Status.UNKNOWN:
                continue

            if status == Status.PASS:
                code = row.get("verified_code") or ""
            else:
                # FAIL: fish the failing attempt out of original_item.output.
                oi = _parse_original_item(row.get("original_item"))
                code = _extract_rust_code(oi.get("output") or "") or ""
                if not code:
                    # Some FAIL rows may have no usable output (timeout before
                    # any code was generated). Try the input as a last resort —
                    # it at least contains the spec, even if the impl part is
                    # empty placeholders.
                    code = _extract_rust_code(oi.get("input") or "") or ""

            if not code:
                continue

            spec_text, impl_text = split_spec_impl(code)
            if not impl_text.strip():
                continue  # parser couldn't find an impl body — skip

            spec_id = f"traj-{row.get('original_index', 'NA')}"
            impl_id = f"{spec_id}-rep{row.get('repetition', 'NA')}"

            yield Example(
                source=Source.SYSTEM_TRAJECTORY,
                spec_id=spec_id,
                impl_id=impl_id,
                spec_text=spec_text,
                impl_text=impl_text,
                status=status,
                # Per critique 1a: do NOT use verifier-cited lines as buggy_lines.
                buggy_lines=set(),
                rep_index=int(row.get("repetition", 0)) if row.get("repetition") is not None else None,
                verifier_log=row.get("log"),
            )


# ---- sft_safe_25k -----------------------------------------------------------

# Match a Rust code block in the input prompt: ```rust ... ```
_RUST_BLOCK_RE = re.compile(r"```rust\s*\n(.*?)```", re.DOTALL)
# Match the "The error messages are: ... ``` ... ```" tail.
_ERROR_BLOCK_RE = re.compile(
    r"The error messages are[^\n]*\n+\s*```(?:rust)?\s*\n(.*?)```", re.DOTALL
)


def _extract_rust_code(text: str) -> str | None:
    """Extract the first ```rust ... ``` block from a prompt string."""
    m = _RUST_BLOCK_RE.search(text)
    if not m:
        return None
    return m.group(1).rstrip()


def _extract_error_text(text: str) -> str | None:
    m = _ERROR_BLOCK_RE.search(text)
    if not m:
        return None
    return m.group(1).strip()


def _line_diff_changed_indices(broken_lines: list[str], fixed_lines: list[str]) -> set[int]:
    """Return indices (into ``broken_lines``) of lines that differ from fixed.

    Uses difflib.SequenceMatcher to identify 'replace' and 'delete' opcodes
    on the broken side. Insert-only on the fixed side doesn't generate
    broken-side line indices (you can't blame a line that doesn't exist).
    """
    sm = difflib.SequenceMatcher(a=broken_lines, b=fixed_lines, autojunk=False)
    changed: set[int] = set()
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            changed.update(range(i1, i2))
    return changed


def _hash_spec(spec_text: str) -> str:
    return hashlib.sha1(spec_text.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def parse_sft_safe(
    path: str | Path,
    *,
    max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
) -> Iterator[Example]:
    """Stream ``sft_safe_25k.json`` -> Example pairs (broken + fixed).

    The file is a JSON array; we use ijson to stream items so we don't load
    1+ GB into memory.

    For each (input, output) row whose ``input`` contains both a rust code block
    and an error message, we:
      1. Parse the broken impl from the rust block in ``input``.
      2. Parse the fixed impl from ``output`` (which should be raw rust, possibly
         wrapped in a ```rust block).
      3. Split each into (spec, impl). Spec should match between the two.
      4. Compute line-diff on impl_text; if it exceeds ``max_diff_lines``, skip
         (likely whole-function rewrite, not a localizable bug).
      5. Yield two Examples (broken/FAIL with buggy_lines, fixed/PASS without).
    """
    path = Path(path)
    pair_counter = 0
    with path.open("rb") as f:
        items = ijson.items(f, "item")
        while True:
            # Tolerate truncated files (e.g. the cached 20MB partial in /tmp):
            # stop cleanly at IncompleteJSONError instead of crashing the loader.
            try:
                item = next(items)
            except StopIteration:
                break
            except ijson.common.IncompleteJSONError:
                break
            input_text = item.get("input") or ""
            output_text = item.get("output") or ""

            broken_code = _extract_rust_code(input_text)
            if not broken_code:
                continue
            # output is sometimes wrapped in a code block, sometimes raw
            fixed_code = _extract_rust_code(output_text) or output_text.strip()
            if not fixed_code:
                continue

            broken_spec, broken_impl = split_spec_impl(broken_code)
            _, fixed_impl = split_spec_impl(fixed_code)

            if not broken_impl.strip() or not fixed_impl.strip():
                continue

            broken_lines = broken_impl.splitlines()
            fixed_lines = fixed_impl.splitlines()
            changed = _line_diff_changed_indices(broken_lines, fixed_lines)
            if not changed:
                # No diff on impl body — could be all changes were in spec, skip.
                continue
            if len(changed) > max_diff_lines:
                continue

            spec_hash = _hash_spec(broken_spec)
            spec_id = f"safe-{spec_hash}"
            broken_id = f"{spec_id}-broken-{pair_counter}"
            fixed_id = f"{spec_id}-fixed-{pair_counter}"

            broken_ex = Example(
                source=Source.SFT_SAFE,
                spec_id=spec_id,
                impl_id=broken_id,
                spec_text=broken_spec,
                impl_text=broken_impl,
                status=Status.FAIL,
                buggy_lines=changed,
                verifier_log=_extract_error_text(input_text),
                sibling_impl_id=fixed_id,
            )
            fixed_ex = Example(
                source=Source.SFT_SAFE,
                spec_id=spec_id,
                impl_id=fixed_id,
                spec_text=broken_spec,  # same spec
                impl_text=fixed_impl,
                status=Status.PASS,
                buggy_lines=set(),
                sibling_impl_id=broken_id,
            )
            pair_counter += 1
            yield broken_ex
            yield fixed_ex


# ---- combined loader --------------------------------------------------------


def load_all(
    system_trajectory_path: str | Path,
    sft_safe_path: str | Path,
    *,
    max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
    extra_trajectory_paths: list[str | Path] | None = None,
    extra_sft_paths: list[str | Path] | None = None,
) -> list[Example]:
    """Load all configured sources into memory as a flat list of Examples.

    ``extra_trajectory_paths`` are parsed with the same parser as
    ``system_trajectory_path`` (e.g. ``algorithmic_trajectory_9040.jsonl``).
    ``extra_sft_paths`` are parsed like ``sft_safe_path`` (e.g.
    ``sft_part2_4557.json``); records without a valid broken/fixed diff are
    auto-skipped, so proof-generation-only records won't poison L_line.
    """
    out: list[Example] = []
    out.extend(parse_system_trajectory(system_trajectory_path))
    for p in extra_trajectory_paths or []:
        out.extend(parse_system_trajectory(p))
    out.extend(parse_sft_safe(sft_safe_path, max_diff_lines=max_diff_lines))
    for p in extra_sft_paths or []:
        out.extend(parse_sft_safe(p, max_diff_lines=max_diff_lines))
    return out


def iter_all(
    system_trajectory_path: str | Path,
    sft_safe_path: str | Path,
    *,
    max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
) -> Iterable[Example]:
    """Streaming version of ``load_all`` — useful for stats/audit scripts."""
    yield from parse_system_trajectory(system_trajectory_path)
    yield from parse_sft_safe(sft_safe_path, max_diff_lines=max_diff_lines)
