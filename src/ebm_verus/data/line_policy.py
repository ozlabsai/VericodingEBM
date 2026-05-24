"""Line-level decisions: which source lines are scorable, where the spec ends.

Decisions baked into this module (see ``ebm_verus.constants`` docstring):

* Scorable lines: any non-empty, non-comment-only source line. Closing-brace-only
  lines ARE scorable (Verus often reports invariant failures there).
* Spec block: ``fn`` signature plus the contiguous ``requires`` / ``ensures``
  clauses immediately following it. ``invariant`` / ``decreases`` inside loops
  are IMPL, not spec.
"""

from __future__ import annotations

import re

from ebm_verus.constants import COMMENT_PREFIXES, FN_SIGNATURE_TOKENS, SPEC_CLAUSE_KEYWORDS


def is_scorable_line(line: str) -> bool:
    """Should this source line receive a sentinel + per-line energy?"""
    stripped = line.strip()
    if not stripped:
        return False
    # comment-only
    if stripped.startswith(COMMENT_PREFIXES):
        return False
    # everything else is scored, including bare braces
    return True


_FN_MAIN_RE = re.compile(r"^\s*(?:pub\s+)?fn\s+main\s*\(")


def find_fn_signature_line(lines: list[str], *, skip_main: bool = True) -> int | None:
    """Index of the first interesting function-signature line, or ``None``.

    ``skip_main=True``: skips ``fn main()`` stubs (very common in these
    datasets — the file has ``fn main() {}`` followed by the *real* spec
    inside ``verus! { ... }``). Without this skip, we'd hash on ``main``'s
    signature and collide thousands of distinct specs.
    """
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if skip_main and _FN_MAIN_RE.match(line):
            continue
        for marker in FN_SIGNATURE_TOKENS:
            if stripped.startswith(marker):
                return i
    return None


_SIG_OPEN_BRACE = re.compile(r"\{\s*$")
_SPEC_CLAUSE_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(k) for k in SPEC_CLAUSE_KEYWORDS) + r")\b"
)


def split_spec_impl(text: str) -> tuple[str, str]:
    """Split a Verus function source into (spec_text, impl_text).

    Heuristic:
      1. Find the ``fn`` signature line.
      2. **spec_text** = the fn signature line + its trailing ``requires`` /
         ``ensures`` clauses (up to but not including the body's opening ``{``).
         Boilerplate *before* the fn (use-statements, ``verus! {``, struct
         declarations, etc.) is DELIBERATELY EXCLUDED — those don't carry the
         spec content and they cause hash-collisions across records that share
         only the wrapper code.
      3. **impl_text** = everything inside the body ``{ ... }``.

    If we cannot find a function signature, fall back to a heuristic split at
    the first top-level ``{`` — degraded but won't crash.
    """
    lines = text.splitlines()
    sig_idx = find_fn_signature_line(lines)

    if sig_idx is None:
        # Fallback: split at first '{' on its own line or trailing.
        for i, line in enumerate(lines):
            if "{" in line:
                spec = "\n".join(lines[: i + 1])
                impl = "\n".join(lines[i + 1 :])
                return spec, impl
        return text, ""  # all spec, no impl

    # Walk forward from sig_idx to find where the function body opens.
    spec_end = sig_idx
    for i in range(sig_idx, len(lines)):
        line = lines[i]
        # If this line ends with '{' and is not a spec clause continuation,
        # it opens the body. The signature line itself may end with '{'.
        if i > sig_idx and not _SPEC_CLAUSE_RE.match(line) and _SIG_OPEN_BRACE.search(line):
            spec_end = i
            break
        if _SIG_OPEN_BRACE.search(line):
            spec_end = i
            break
        spec_end = i

    # spec = fn signature line + requires/ensures, NO preamble
    spec_lines = lines[sig_idx : spec_end + 1]
    impl_lines = lines[spec_end + 1 :]

    return "\n".join(spec_lines), "\n".join(impl_lines)


def scorable_line_indices(impl_text: str) -> list[int]:
    """Indices (into ``impl_text.splitlines()``) of lines that should be scored."""
    return [i for i, line in enumerate(impl_text.splitlines()) if is_scorable_line(line)]
