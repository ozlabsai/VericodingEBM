"""Sanity tests for the data pipeline.

Runs in CPU-only environment. Loads the real Qwen tokenizer (downloaded
once, then cached locally by HF).
"""

from __future__ import annotations

import pytest
from transformers import AutoTokenizer

from ebm_verus.constants import SENTINEL_TOKEN
from ebm_verus.data import (
    Example,
    Source,
    Status,
    insert_sentinels,
    is_scorable_line,
    split_examples,
    split_spec_impl,
    tokenize_example,
)


VERUS_SNIPPET = """use vstd::prelude::*;
verus! {

fn compute_sum(n: u32) -> (result: u32)
    requires n <= 1000,
    ensures result as nat == sum_to(n as nat),
{
    let mut result: u32 = 0;
    // initialize counter
    let mut i: u32 = 0;
    while i < n
        invariant
            i <= n,
        decreases n - i,
    {
        i = i + 1;
        result = result + i;
    }
    result
}

}
"""


# ---- line policy ------------------------------------------------------------


class TestLinePolicy:
    def test_empty_line_not_scorable(self) -> None:
        assert not is_scorable_line("")
        assert not is_scorable_line("   ")
        assert not is_scorable_line("\t")

    def test_comment_line_not_scorable(self) -> None:
        assert not is_scorable_line("// this is a comment")
        assert not is_scorable_line("    // indented comment")
        assert not is_scorable_line("/// doc comment")
        assert not is_scorable_line("/* block start")

    def test_code_line_scorable(self) -> None:
        assert is_scorable_line("let x = 0;")
        assert is_scorable_line("    invariant i <= n,")

    def test_brace_only_scorable(self) -> None:
        # Closing brace is scored — Verus often reports invariant failures here.
        assert is_scorable_line("}")
        assert is_scorable_line("    }")
        assert is_scorable_line("{")


class TestSplitSpecImpl:
    def test_basic_split(self) -> None:
        spec, impl = split_spec_impl(VERUS_SNIPPET)
        assert "fn compute_sum" in spec
        assert "requires" in spec
        assert "ensures" in spec
        assert "let mut result" in impl
        assert "while i < n" in impl
        # invariant/decreases belong to IMPL (per critique 3b decision)
        assert "invariant" in impl
        assert "decreases" in impl


class TestSentinelInsertion:
    def test_sentinels_only_after_scorable_lines(self) -> None:
        impl = "let x = 0;\n\n// a comment\nlet y = 1;\n"
        with_sent, src_indices = insert_sentinels(impl)
        # Lines: ['let x = 0;', '', '// a comment', 'let y = 1;']
        # Scorable: [0, 3]
        assert src_indices == [0, 3]
        # Two sentinels should appear
        assert with_sent.count(SENTINEL_TOKEN) == 2


# ---- tokenization roundtrip -------------------------------------------------


@pytest.fixture(scope="module")
def tokenizer():
    return AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B")


class TestTokenize:
    def test_sentinel_is_single_token(self, tokenizer) -> None:
        ids = tokenizer.encode(SENTINEL_TOKEN, add_special_tokens=False)
        assert len(ids) == 1

    def test_tokenize_example_basic(self, tokenizer) -> None:
        spec, impl = split_spec_impl(VERUS_SNIPPET)
        ex = Example(
            source=Source.SYSTEM_TRAJECTORY,
            spec_id="test-1",
            impl_id="test-1-rep0",
            spec_text=spec,
            impl_text=impl,
            status=Status.PASS,
            buggy_lines=set(),
        )
        out = tokenize_example(ex, tokenizer, max_length=4096)
        assert out is not None
        assert len(out.sentinel_positions) > 0
        sid = tokenizer.encode(SENTINEL_TOKEN, add_special_tokens=False)[0]
        # All claimed sentinel positions must actually be sentinel tokens.
        for pos in out.sentinel_positions:
            assert out.input_ids[pos] == sid
        # spec_token_count points before any sentinel.
        first_sentinel = out.sentinel_positions[0]
        assert out.spec_token_count <= first_sentinel

    def test_buggy_line_index_mapping(self, tokenizer) -> None:
        # impl with 4 source lines, scorable at indices [0, 2, 3]
        # (line 1 is blank, line 3 is a comment-only? Let's make sure)
        spec = "fn f() ensures true,\n{"
        impl = "let a = 1;\n\nlet b = 2;\nlet c = 3;\n"
        # source lines: ['let a = 1;', '', 'let b = 2;', 'let c = 3;']
        # scorable: [0, 2, 3]
        ex = Example(
            source=Source.SFT_SAFE,
            spec_id="t",
            impl_id="t1",
            spec_text=spec,
            impl_text=impl,
            status=Status.FAIL,
            buggy_lines={2},  # source line 2 -> 'let b = 2;'
        )
        out = tokenize_example(ex, tokenizer, max_length=4096)
        assert out is not None
        # source line 2 is the *second* scorable line (sentinel index 1).
        assert out.buggy_line_indices == {1}


# ---- split ------------------------------------------------------------------


class TestSplit:
    def test_spec_disjoint(self) -> None:
        # 5 traj specs x 3 impls + 10 safe specs x 2 examples. Each spec gets
        # distinct spec_text so the normalized-text disjointness assertion holds.
        examples: list[Example] = []
        for s in range(5):
            for r in range(3):
                examples.append(
                    Example(
                        source=Source.SYSTEM_TRAJECTORY,
                        spec_id=f"traj-{s}",
                        impl_id=f"traj-{s}-rep{r}",
                        spec_text=f"spec for traj {s}",
                        impl_text="let x = 0;",
                        status=Status.PASS if r == 0 else Status.FAIL,
                    )
                )
        for s in range(10):
            for r in range(2):
                examples.append(
                    Example(
                        source=Source.SFT_SAFE,
                        spec_id=f"safe-{s}",
                        impl_id=f"safe-{s}-{r}",
                        spec_text=f"spec for safe {s}",
                        impl_text="let y = 0;",
                        status=Status.FAIL if r == 0 else Status.PASS,
                    )
                )
        train, held = split_examples(
            examples, n_eval_traj_specs=2, sft_eval_frac=0.2, seed=42
        )
        train_specs = {e.spec_id for e in train}
        held_specs = {e.spec_id for e in held}
        assert not (train_specs & held_specs)
        # Held-out should have exactly 2 traj specs and ~2 safe specs (hash-based).
        assert sum(1 for s in held_specs if s.startswith("traj-")) == 2
