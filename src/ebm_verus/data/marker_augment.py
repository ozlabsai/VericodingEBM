"""Counterfactual marker augmentation: decorrelate Qwen's pretraining-prior
`// FAIL/FIXME/TODO -> buggy line` from the actual buggy-line label.

Per V6 research (Kaushik 2020, Veitch 2021, Rabin 2021), the right fix for a
spurious feature whose prior survives PEFT fine-tuning is *counterfactual
data augmentation*: inject the feature at training time uncorrelated with
the label, so the LoRA learns to ignore it.

We support two modes:
  - 'augment': for each Example, create K augmented copies where marker
    comments are randomly placed (on buggy/non-buggy lines, with positive
    distractors). Cached at sampler init; sampler picks uniformly among
    the K copies per epoch.
  - 'strip': remove any existing marker comments at load time (no-op for
    our training data, but defensive).

Markers used:
    Negative-priming: // FAILS, // FIXME, // TODO, // BUG, // XXX, // HACK,
                      // broken, // wrong
    Positive distractors: // ok, // verified, // passes

Usage:
    aug = MarkerAugmenter(seed=42)
    copies = aug.augment_example(example, k=4)  # list of Example with varied markers
"""
from __future__ import annotations

import random
from dataclasses import replace
from ebm_verus.data.types import Example, Status

NEGATIVE_MARKERS = [
    "// FAILS",
    "// FIXME",
    "// TODO",
    "// BUG",
    "// XXX",
    "// HACK",
    "// broken",
    "// wrong",
]
POSITIVE_MARKERS = [
    "// ok",
    "// verified",
    "// passes",
]
ALL_MARKERS = NEGATIVE_MARKERS + POSITIVE_MARKERS

# Regex-stripping (used for inference-time defense + dataset cleanup).
import re
_MARKER_RE = re.compile(
    r"\s*//\s*(?:FAILS?|FIXME|TODO|BUG|XXX|HACK|broken|wrong|ok|verified|passes)\b.*?$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_markers(text: str) -> str:
    """Remove any marker comments from text. Used at eval and as a defensive
    transform at training time."""
    return _MARKER_RE.sub("", text)


def _inject_marker(line: str, marker: str) -> str:
    """Append a marker as a trailing comment. If the line already has a `//`
    comment, append the marker after it; otherwise create a new comment."""
    stripped = line.rstrip()
    if "//" in stripped:
        return stripped + " " + marker
    return stripped + "  " + marker


class MarkerAugmenter:
    """Deterministic-per-(impl_id, copy_idx) marker injection.

    The augmentation policy (V6):
      - With prob `marker_prob`, inject ONE marker on ONE line per impl.
      - When injecting, pick marker uniformly from ALL_MARKERS (mix of negative
        and positive — both must be random wrt label to decorrelate).
      - Line choice: uniform over scorable lines. Crucially we do NOT condition
        on the buggy_line_indices; placement is random wrt label.
      - Independently, with prob `positive_prob`, also inject a positive marker
        on a different random line (extra distractor).
    """

    def __init__(
        self,
        *,
        marker_prob: float = 0.5,
        positive_prob: float = 0.3,
        seed: int = 0,
        mode: str = "v6",
    ) -> None:
        """``mode='v6'`` is the run-#8 policy (mixed-marker, possibly on bug line).
        ``mode='adversarial'`` is the run-#9 policy: with prob ``marker_prob``, inject
        a NEGATIVE marker on a uniformly-random NON-buggy line. No positive markers,
        no placement on bug lines. Ensures the marker is anti-correlated with the
        label without creating within-class noise.
        """
        self.marker_prob = marker_prob
        self.positive_prob = positive_prob
        self.seed = seed
        self.mode = mode

    def _rng_for(self, impl_id: str, copy_idx: int) -> random.Random:
        return random.Random(f"{self.seed}-{impl_id}-{copy_idx}")

    def augment_example(self, ex: Example, k: int = 4) -> list[Example]:
        """Return k augmented copies of ``ex`` (each with possibly different
        marker placement). The first copy is the original (unaugmented).
        """
        copies: list[Example] = [ex]
        for i in range(1, k):
            copies.append(self._augment_one(ex, copy_idx=i))
        return copies

    def _augment_one(self, ex: Example, copy_idx: int) -> Example:
        rng = self._rng_for(ex.impl_id, copy_idx)
        lines = ex.impl_text.splitlines()
        n_lines = len(lines)
        if n_lines == 0:
            return ex

        if self.mode == "adversarial":
            # Run #9: NEGATIVE marker on a uniformly-random NON-buggy line.
            # No positive markers, no placement on labeled bug lines. This installs
            # a marker→non-bug anti-correlation without within-class noise.
            if rng.random() < self.marker_prob:
                non_bug = [i for i in range(n_lines) if i not in ex.buggy_lines]
                if non_bug:
                    i = rng.choice(non_bug)
                    marker = rng.choice(NEGATIVE_MARKERS)
                    lines[i] = _inject_marker(lines[i], marker)
        else:
            # v6: original mixed-marker policy (kept for run #8 reproducibility).
            if rng.random() < self.marker_prob:
                i = rng.randrange(n_lines)
                marker = rng.choice(ALL_MARKERS)
                lines[i] = _inject_marker(lines[i], marker)
            if rng.random() < self.positive_prob:
                j = rng.randrange(n_lines)
                marker = rng.choice(POSITIVE_MARKERS)
                lines[j] = _inject_marker(lines[j], marker)

        new_text = "\n".join(lines)
        # Replace creates a new Example with the same impl_id (sentinel positions
        # will shift but buggy_line_indices are in source-line space which is
        # invariant under appending to lines, so labels remain correct).
        return replace(ex, impl_text=new_text)
