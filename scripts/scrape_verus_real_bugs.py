"""Scrape real Verus bug test cases from verus-lang/verus repository.

These are hand-authored Verus programs from the official test suite at
source/rust_verify_test/tests/*.rs. Each test file contains many
test_verify_one_file! { ... } blocks. Some are expected to succeed
(=> Ok(())) and some are expected to fail (=> Err(...)). Failing tests
contain a `// FAILS` comment on the line(s) that fail to verify.

This gives us a *labeled, hand-authored, non-mutator-generated* corpus
of Verus pass/fail pairs with line-level bug annotations -- exactly what
the mutator-fingerprint probe needs.

Output: JSONL with the same fields as our Example dataclass so the
existing eval pipeline can consume it directly.

Usage:
    uv run python scripts/scrape_verus_real_bugs.py \
        --out artifacts/real_bugs/records.jsonl \
        --max-files 50

Requires gh CLI authenticated (or unauthenticated if rate-limit OK).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


REPO = "verus-lang/verus"
TESTS_DIR = "source/rust_verify_test/tests"


def gh_api(path: str) -> dict | list:
    out = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def list_test_files() -> list[str]:
    """Return names of .rs files under the tests dir."""
    entries = gh_api(f"repos/{REPO}/contents/{TESTS_DIR}")
    return [e["name"] for e in entries if e.get("type") == "file" and e["name"].endswith(".rs")]


def fetch_file(name: str) -> str:
    """Fetch a single .rs test file's contents."""
    obj = gh_api(f"repos/{REPO}/contents/{TESTS_DIR}/{name}")
    content_b64 = obj["content"]
    return base64.b64decode(content_b64).decode("utf-8", errors="replace")


# Regex strategy:
# test_verify_one_file! {
#     #[test] <name> verus_code! { <body> } => <outcome>
# }
#
# The body can contain nested braces. We need a brace-matcher to find the end.

_BLOCK_HEADER_RE = re.compile(
    r"test_verify_one_file!\s*\{\s*"
    r"(?:#\[(?:test|cfg|ignore)[^\]]*\]\s*)*"
    r"(?:#\[test\]\s*)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"verus_code!\s*\{",
    re.DOTALL,
)


def _match_braces(text: str, start: int) -> int | None:
    """Given that text[start-1] is '{', return index of the matching '}' (exclusive),
    or None if unbalanced. Naive: ignores braces inside strings/comments. Good
    enough for verus_code! bodies which don't normally contain literal `}` in strings.
    """
    depth = 1
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _trailing_outcome(text: str, after_body: int) -> tuple[str, int]:
    """Read past `} => <outcome> }` and return the outcome string and the
    position after the outer closing brace. Outcome is one of:
      - "Ok(())"
      - "Err(...)" (we treat all Err variants as FAIL)
      - "" (unrecognized; skip)
    """
    # Find " => " after position
    arrow_match = re.search(r"=>\s*", text[after_body:after_body + 400])
    if not arrow_match:
        return "", after_body
    arrow_end = after_body + arrow_match.end()
    # Outcome runs until the next `}` at top level of the outer block. Heuristic:
    # just check if the next non-whitespace token starts with "Ok" or "Err".
    rest = text[arrow_end:].lstrip()
    if rest.startswith("Ok"):
        return "Ok", arrow_end
    if rest.startswith("Err"):
        return "Err", arrow_end
    return "", arrow_end


def parse_blocks(text: str) -> list[dict]:
    """Return list of {name, body, outcome} dicts for a single test file."""
    blocks = []
    for m in _BLOCK_HEADER_RE.finditer(text):
        name = m.group("name")
        body_start = m.end()
        body_end = _match_braces(text, body_start)
        if body_end is None:
            continue
        body = text[body_start:body_end]
        outcome, _ = _trailing_outcome(text, body_end + 1)
        if not outcome:
            continue
        blocks.append({"name": name, "body": body, "outcome": outcome})
    return blocks


def split_spec_impl_heuristic(body: str) -> tuple[str, str]:
    """For our Example shape we need (spec_text, impl_text). The verus_code!
    body contains free-floating top-level fns + spec fns + use statements.

    Approximation: spec = everything before the first non-spec fn signature;
    impl = everything from that fn signature onwards. For our purposes the
    *split* matters less than line indexing being correct -- the model takes
    spec+impl jointly via sentinel tokenization.

    Concrete rule:
      - lines starting with "use ", "uninterp ", "spec ", "proof ", "broadcast "
        and lines like "fn <name>(...) -> ... { ... requires ... ensures }"
        are spec-ish.
      - First non-spec body fn (a regular fn with executable body) starts impl.
    """
    lines = body.splitlines()
    impl_start = None
    in_braces = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        # If we see a regular `fn name(...)` whose body comes immediately, treat as impl.
        if s.startswith("fn ") and "{" in s:
            impl_start = i
            break
        in_braces += s.count("{") - s.count("}")
    if impl_start is None:
        # No exec fn — whole thing is "spec". Return body as impl too (won't be useful).
        return body, body
    spec_text = "\n".join(lines[:impl_start])
    impl_text = "\n".join(lines[impl_start:])
    return spec_text, impl_text


def find_fails_lines(impl_text: str) -> list[int]:
    """Return 0-indexed line numbers (in impl_text) of lines marked `// FAILS`.

    Returned indices are source-line space, not sentinel space. The downstream
    pipeline (split_spec_impl + scorable_line_indices) maps them.
    """
    out = []
    for i, line in enumerate(impl_text.splitlines()):
        if "// FAILS" in line:
            out.append(i)
    return out


def pair_blocks(blocks: list[dict]) -> list[dict]:
    """Pair Err blocks with their nearest Ok sibling (same base name minus `_fails`).

    If no sibling exists, the Err block is kept as a "FAIL without paired PASS"
    record (still useful for top-k recall; just no within-spec contrast).
    """
    by_base: dict[str, dict] = {}
    for b in blocks:
        name = b["name"]
        if name.endswith("_fails"):
            base = name[: -len("_fails")]
        elif name.endswith("_fail"):
            base = name[: -len("_fail")]
        elif name.endswith("_FAILS"):
            base = name[: -len("_FAILS")]
        else:
            base = name
        by_base.setdefault(base, {})[name] = b
    return list(by_base.values())


def emit_records(file_name: str, blocks: list[dict]) -> list[dict]:
    """Build Example-shaped JSONL records from parsed blocks.

    For a paired (pass, fail) sibling set we emit BOTH sides: the FAIL side
    gets buggy_lines populated, the PASS side gets buggy_lines empty.
    """
    pair_counter = 0
    records: list[dict] = []
    pairs = pair_blocks(blocks)
    for group in pairs:
        # Pick canonical fail and pass blocks if multiples exist
        fail_block = None
        pass_block = None
        for name, b in group.items():
            if b["outcome"] == "Err":
                fail_block = fail_block or b
            elif b["outcome"] == "Ok":
                pass_block = pass_block or b
        # Need at least one labeled fail to be useful as a per-line eval example
        if fail_block is None:
            continue
        fail_body = fail_block["body"]
        spec_text, impl_text = split_spec_impl_heuristic(fail_body)
        buggy_lines = find_fails_lines(impl_text)
        if not buggy_lines and not impl_text.strip():
            continue
        # Stable spec_id: hash of normalized spec text
        norm = "".join(spec_text.split())
        spec_hash = hashlib.sha1(norm.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        spec_id = f"verus-real-{file_name[:-3]}-{spec_hash}"
        fail_id = f"{spec_id}-fail-{fail_block['name']}-{pair_counter}"
        records.append({
            "source": "verus_real",
            "source_file": file_name,
            "test_name": fail_block["name"],
            "spec_id": spec_id,
            "impl_id": fail_id,
            "spec_text": spec_text,
            "impl_text": impl_text,
            "status": "FAIL",
            "buggy_lines": buggy_lines,
            "outcome": "Err",
        })
        if pass_block is not None:
            pass_body = pass_block["body"]
            pass_spec, pass_impl = split_spec_impl_heuristic(pass_body)
            pass_id = f"{spec_id}-pass-{pass_block['name']}-{pair_counter}"
            records.append({
                "source": "verus_real",
                "source_file": file_name,
                "test_name": pass_block["name"],
                "spec_id": spec_id,
                "impl_id": pass_id,
                "spec_text": pass_spec,
                "impl_text": pass_impl,
                "status": "PASS",
                "buggy_lines": [],
                "outcome": "Ok",
            })
        pair_counter += 1
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path,
                    help="Output JSONL path")
    ap.add_argument("--max-files", type=int, default=None,
                    help="Cap on number of test files scanned (for quick smoke runs)")
    ap.add_argument("--max-records", type=int, default=None,
                    help="Cap on output records")
    args = ap.parse_args()

    print(f"listing test files in {REPO}:{TESTS_DIR} ...", flush=True)
    files = list_test_files()
    print(f"  found {len(files)} .rs files", flush=True)
    if args.max_files:
        files = files[: args.max_files]
        print(f"  limited to first {len(files)}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_out = 0
    n_fail_with_marker = 0
    n_files_scanned = 0
    with args.out.open("w") as f_out:
        for i, name in enumerate(files):
            if args.max_records and n_out >= args.max_records:
                break
            try:
                src = fetch_file(name)
            except subprocess.CalledProcessError as e:
                print(f"  [skip] {name}: {e}", flush=True)
                continue
            blocks = parse_blocks(src)
            n_files_scanned += 1
            recs = emit_records(name, blocks)
            n_fail_with_marker += sum(
                1 for r in recs
                if r["status"] == "FAIL" and r["buggy_lines"]
            )
            for r in recs:
                if args.max_records and n_out >= args.max_records:
                    break
                f_out.write(json.dumps(r) + "\n")
                n_out += 1
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(files)} files; {n_out} records, "
                      f"{n_fail_with_marker} fails with // FAILS markers",
                      flush=True)
    print(f"DONE. wrote {n_out} records "
          f"({n_fail_with_marker} FAIL-with-buggy-lines) to {args.out} "
          f"(scanned {n_files_scanned}/{len(files)} files)",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
