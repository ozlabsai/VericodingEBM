"""Build the corruption-style examples for the static demo.

We pick real (FAIL, PASS) sibling pairs from the dev-test corpus where the
model strongly discriminates (delta_e >> 0), then for each example we precompute
energies for ~3 variants:
  - the original FAIL impl (with // FAILS marker intact)
  - the sibling PASS impl
  - the FAIL with the // FAILS marker stripped (demonstrates marker-aversion)

Each variant is scored against the live backend at startup time so the static
demo can show energies instantly without a model load.

Output: demo/frontend/public/data/corruption_examples.json
"""
from __future__ import annotations
import json
import re
import time
from collections import defaultdict
from pathlib import Path
import urllib.request

import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = "http://127.0.0.1:8765"

# Curated by hand from the top-delta sibling pairs (see build_corruption_examples
# pre-step output). Picked for: short, readable, FAIL/PASS differ by 1-2 lines.
CURATED_SPEC_IDS = [
    "verus-real-adts_generics-39d41db00801",     # >= 1 vs >= 0  ("1-char corruption")
    "verus-real-match-38d4dd210af4",              # assert(z) vs assert(!z)
    "verus-real-return-637895b687d2",             # wrong ensures (false vs true)
    "verus-real-quantifiers-5417c12c4ee6",        # missing trigger hint
    "verus-real-ext_equal-f53fcd66fb8a",          # missing auto_ext_equal attribute
    "verus-real-traits-47a2060aa419",             # wrong assertion + missing decomp
]

# Friendly labels for each spec
LABELS = {
    "verus-real-adts_generics-39d41db00801": {
        "name": "adts_generics_offByOne",
        "label": "ADT field: off-by-one assertion",
        "blurb": "The FAIL impl asserts `id(p2).a >= 1` for a struct with field value 2; should be `>= 0` (or any smaller bound). The fix is a single-digit change in the assertion. Model should flag the failing assertion line.",
    },
    "verus-real-match-38d4dd210af4": {
        "name": "match_assertOnBool",
        "label": "Destructured bool — wrong assertion",
        "blurb": "Pattern-binds `b: false` to `z`, then asserts `z` (which is false). The fix is to assert `!z`. Tiny code, obvious bug — perfect to corrupt either way.",
    },
    "verus-real-return-637895b687d2": {
        "name": "return_falseEnsures",
        "label": "Early return with `ensures false`",
        "blurb": "The spec claims `ensures false` (which is impossible for any non-diverging function), so the early `return;` fails. The PASS variant uses `ensures true`.",
    },
    "verus-real-quantifiers-5417c12c4ee6": {
        "name": "quantifiers_missingTrigger",
        "label": "Existential without instantiation hint",
        "blurb": "The FAIL impl asks Verus to prove an existential without giving it a witness; the PASS variant provides one via an explicit `assert(tr::<nat>(300))`. Classic SMT-trigger problem.",
    },
    "verus-real-ext_equal-f53fcd66fb8a": {
        "name": "ext_equal_missingAttr",
        "label": "Extensional equality — missing attribute",
        "blurb": "Verus needs `#[verifier::auto_ext_equal()]` to compare two `spec_fn`s for extensional equality. The FAIL drops the attribute (and the matching assume).",
    },
    "verus-real-traits-47a2060aa419": {
        "name": "traits_typeBoundedEq",
        "label": "Trait dispatch: type-bounded equality",
        "blurb": "`S::f(1u8)` and `S::f(1u16)` are dispatched to two different trait impls (true vs false), so `==` on them fails. PASS variant decomposes the comparison into individual assertions.",
    },
}


def score(spec: str, impl: str) -> dict:
    """Call the live backend to get per-line energies and 2D projection."""
    req = urllib.request.Request(
        f"{BACKEND}/api/score-line",
        data=json.dumps({"spec_text": spec, "impl_text": impl}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def strip_fails_marker(text: str) -> str:
    """Strip `// FAILS`, `// FIXME`, `// fails-with-...` markers from each line."""
    out_lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s*//\s*(FAILS|FIXME|fails[-_].*|expected[-_]fail.*)\b.*$", "", line, flags=re.IGNORECASE)
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def main() -> None:
    impls = pq.read_table(REPO / "demo/backend/data/impl_manifold.parquet").to_pylist()
    by_spec = defaultdict(list)
    for impl in impls:
        by_spec[impl["spec_id"]].append(impl)

    out_examples = []
    for spec_id in CURATED_SPEC_IDS:
        meta = LABELS[spec_id]
        group = by_spec[spec_id]
        fails = [i for i in group if i["status"] == "fail"]
        passes = [i for i in group if i["status"] == "pass"]
        if not fails or not passes:
            print(f"  SKIP {spec_id}: missing pair")
            continue
        # Shortest of each
        f = min(fails, key=lambda i: i["n_lines"])
        p = min(passes, key=lambda i: i["n_lines"])
        spec_text = f["spec_text"]

        print(f"\n=== {meta['name']} ({spec_id}) ===")
        variants = []

        # Variant 1: original FAIL (markers intact)
        print("  scoring: original FAIL")
        s = score(spec_text, f["impl_text"])
        variants.append({
            "label": "Original FAIL (with `// FAILS` marker)",
            "kind": "fail_original",
            "note": "The failing implementation, as it appears in the corpus.",
            "impl": f["impl_text"],
            "per_line_energies": s["per_line_energies"],
            "line_xys": s["line_xys"],
            "whole_impl_energy": s["whole_impl_energy"],
            "whole_impl_xy": s["whole_impl_xy"],
        })
        print(f"    whole-impl E = {s['whole_impl_energy']:+.3f}")
        time.sleep(0.1)

        # Variant 2: FAIL with marker stripped (demonstrates marker-aversion: energy should NOT collapse)
        stripped = strip_fails_marker(f["impl_text"])
        if stripped != f["impl_text"]:
            print("  scoring: FAIL with `// FAILS` marker stripped")
            s = score(spec_text, stripped)
            variants.append({
                "label": "FAIL with the `// FAILS` marker stripped",
                "kind": "fail_marker_stripped",
                "note": "Same buggy code, but the marker token Qwen pretrained on is gone. Hybrid-Averse should still flag the bug.",
                "impl": stripped,
                "per_line_energies": s["per_line_energies"],
                "line_xys": s["line_xys"],
                "whole_impl_energy": s["whole_impl_energy"],
                "whole_impl_xy": s["whole_impl_xy"],
            })
            print(f"    whole-impl E = {s['whole_impl_energy']:+.3f}")
            time.sleep(0.1)

        # Variant 3: the sibling PASS impl
        print("  scoring: sibling PASS")
        s = score(spec_text, p["impl_text"])
        variants.append({
            "label": "Sibling PASS (the corrected version)",
            "kind": "pass_sibling",
            "note": "A different implementation that actually verifies. Model energies should drop visibly across the board.",
            "impl": p["impl_text"],
            "per_line_energies": s["per_line_energies"],
            "line_xys": s["line_xys"],
            "whole_impl_energy": s["whole_impl_energy"],
            "whole_impl_xy": s["whole_impl_xy"],
        })
        print(f"    whole-impl E = {s['whole_impl_energy']:+.3f}")
        time.sleep(0.1)

        out_examples.append({
            "name": meta["name"],
            "spec_id": spec_id,
            "label": meta["label"],
            "blurb": meta["blurb"],
            "spec": spec_text,
            "variants": variants,
        })

    out_path = REPO / "demo/frontend/public/data/corruption_examples.json"
    out_path.write_text(json.dumps(out_examples, indent=2))
    print(f"\nwrote {out_path} ({len(out_examples)} examples)")


if __name__ == "__main__":
    main()
