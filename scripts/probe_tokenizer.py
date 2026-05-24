"""Quick probe: confirm <|fim_pad|> is a single token in Qwen2.5-Coder tokenizer.

Also verifies basic Verus snippet tokenization matches the numbers from the
research run (~173 tokens for the canonical probe snippet).
"""

from transformers import AutoTokenizer

from ebm_verus.constants import SENTINEL_TOKEN

MODEL = "Qwen/Qwen2.5-Coder-1.5B"

VERUS_SNIPPET = """use vstd::prelude::*;
verus! {
spec fn sum_to(n: nat) -> nat
    decreases n
{
    if n == 0 { 0 } else { n + sum_to((n - 1) as nat) }
}

fn compute_sum(n: u32) -> (result: u32)
    requires n <= 1000,
    ensures result as nat == sum_to(n as nat),
{
    let mut result: u32 = 0;
    let mut i: u32 = 0;
    while i < n
        invariant
            i <= n,
            result as nat == sum_to(i as nat),
        decreases n - i,
    {
        i = i + 1;
        result = result + i;
    }
    result
}
}
"""


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL)

    # Sentinel must be a single token under Qwen's existing vocab.
    sentinel_ids = tok.encode(SENTINEL_TOKEN, add_special_tokens=False)
    print(f"sentinel token: {SENTINEL_TOKEN!r}")
    print(f"sentinel ids: {sentinel_ids}")
    assert len(sentinel_ids) == 1, f"sentinel must be single token; got {sentinel_ids}"
    print(f"sentinel id (single token): {sentinel_ids[0]}")

    # Snippet tokenization sanity check.
    snippet_ids = tok.encode(VERUS_SNIPPET, add_special_tokens=False)
    print(f"\nVerus snippet tokens: {len(snippet_ids)} (research baseline ~173)")

    # Inline sentinel + decode roundtrip.
    sample = "let x = 0;\n" + SENTINEL_TOKEN + "let y = 1;\n" + SENTINEL_TOKEN
    sample_ids = tok.encode(sample, add_special_tokens=False)
    decoded = tok.decode(sample_ids)
    print(f"\ninline sentinel roundtrip:")
    print(f"  input:  {sample!r}")
    print(f"  ids:    {sample_ids}")
    print(f"  decoded:{decoded!r}")

    # Where are the sentinels in the id list?
    sid = sentinel_ids[0]
    positions = [i for i, t in enumerate(sample_ids) if t == sid]
    print(f"  sentinel positions: {positions}")


if __name__ == "__main__":
    main()
