"""Project-wide constants. Tokenization / line policy decisions live here.

Decision log (Thu 2026-05-21 — baked in, not revisited):

- Sentinel token: ``<|fim_pad|>`` from Qwen's reserved FIM tokens. Never appears
  in normal training so its embedding is effectively free for LoRA to adapt. No
  embedding-matrix resize required.

- Line scoring policy (one sentinel after each *scorable* source line):
  * Empty lines: skipped (no sentinel)
  * Comment-only lines (``//`` or ``/* ... */`` exclusively): skipped
  * Multi-statement lines (``let x = 0; let y = 1;``): one sentinel — source-line
    is the user's mental model and the granularity our diffs / verifier reports use.
  * Multi-line statements (``requires (\n  x > 0,\n  y < 100\n)``): one sentinel
    per *source line*, not per logical statement.
  * Closing-brace-only lines (``}``): SCORED. Verus often reports invariant
    failures at loop-closing braces; the brace is a real localization unit.

- Spec / impl boundary:
  * Spec = ``fn`` signature + top-level ``requires`` / ``ensures`` block (function-level pre/post).
  * Impl = function body, INCLUDING ``invariant`` / ``decreases`` clauses inside
    loops. Wrong invariants are a real LLM bug class and we want to flag them.
"""

from __future__ import annotations

# ---- Sentinel ---------------------------------------------------------------

SENTINEL_TOKEN: str = "<|fim_pad|>"
"""Token inserted between scorable impl lines. See module docstring."""

# ---- Line classification ----------------------------------------------------

# Lines starting with these (after stripping leading whitespace) are comments.
COMMENT_PREFIXES: tuple[str, ...] = ("//", "/*", "*/", "*", "///")

# Lines matching this regex (entirely) are considered "block delimiter only"
# — kept SCORED, since Verus can point at them for invariant/post-condition
# failures. Listed here only for clarity; not used as a skip rule.
SCORABLE_BRACE_ONLY: tuple[str, ...] = ("}", "{", "})", "});", "};")

# ---- Spec / impl parsing ----------------------------------------------------

# Top-level spec clause keywords that, when on their own line at function scope,
# belong to the spec block (not impl). ``invariant`` / ``decreases`` are
# DELIBERATELY EXCLUDED — they appear inside loop bodies and are scored as impl.
SPEC_CLAUSE_KEYWORDS: tuple[str, ...] = ("requires", "ensures")

# Verus / Rust function-signature start markers.
FN_SIGNATURE_TOKENS: tuple[str, ...] = ("fn ", "pub fn ", "spec fn ", "proof fn ", "exec fn ")

# ---- Data filtering ---------------------------------------------------------

# sft_safe_25k debugging pairs whose diff spans more lines than this are
# treated as whole-function rewrites and dropped from L_line supervision.
DEFAULT_MAX_DIFF_LINES: int = 3
