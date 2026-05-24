"""Strip-FAILS re-evaluation: highest-EV falsification per research V4.

Hypothesis: maybe the model is leaking through `// FAILS` markers being
visible in sentinel positions. Re-tokenize the real corpus with the
markers entirely removed (not just masked at loss), re-score, compare top-3.

If top-3 stays >= 0.90, marker-leak hypothesis is ruled out.
If top-3 drops below the length-baseline 0.73, marker-leak is the bulk of the signal.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import torch, yaml

from ebm_verus.constants import SENTINEL_TOKEN  # noqa: F401
from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer


def _resolve_dtype(p):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[p]


def _status_from_str(s):
    s = s.upper()
    if s.endswith("PASS") or s.endswith("OK"): return Status.PASS
    if s.endswith("FAIL") or s.endswith("ERR"): return Status.FAIL
    return Status.UNKNOWN


def _strip_fails(impl_text: str) -> str:
    """Remove `// FAILS` (and any trailing whitespace/text after it on the same line)."""
    new_lines = []
    for line in impl_text.splitlines():
        if "// FAILS" in line:
            line = line.split("// FAILS", 1)[0].rstrip()
        new_lines.append(line)
    return "\n".join(new_lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--ckpt-dir", required=True, type=Path)
    ap.add_argument("--in", dest="in_path", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    with args.config.open() as f:
        cfg = yaml.safe_load(f)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}", flush=True)

    raw = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if not line: continue
            raw.append(json.loads(line))
    print(f"loaded {len(raw)} input records", flush=True)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
    if tok.pad_token_id is None:
        tok.pad_token_id = tok.eos_token_id

    lora = cfg["model"]["lora"]
    scalar_head = (args.ckpt_dir / "scalar_head.pt").exists() if args.ckpt_dir else False
    if scalar_head:
        print(f"  detected scalar_head.pt → building hybrid scorer", flush=True)
    model = EnergyScorer(
        backbone_name=cfg["model"]["backbone"],
        lora_rank=int(lora["rank"]),
        lora_alpha=int(lora["alpha"]),
        lora_dropout=float(lora["dropout"]),
        lora_target_modules=tuple(lora["target_modules"]),
        embed_lora_rank=int(lora["embed_lora_rank"]),
        head_hidden_dim=int(cfg["model"]["head"]["hidden_dim"]),
        head_dropout=float(cfg["model"]["head"]["dropout"]),
        head_init_std=float(cfg["model"]["head"]["init_std"]),
        torch_dtype=_resolve_dtype(cfg["train"]["precision"]),
        gradient_checkpointing=False,
        scalar_head=scalar_head,
    ).to(device)
    print(f"loading ckpt: {args.ckpt_dir}", flush=True)
    model.load_trainable(args.ckpt_dir)
    model.eval()

    max_len = int(cfg["data"]["max_seq_len"])
    lse_t = float(cfg["model"]["lse"]["temp_end"])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    n_written, n_skipped = 0, 0
    n_stripped = 0
    with args.out.open("w") as f_out:
        for r in raw:
            impl_text_orig = r.get("impl_text", "")
            impl_text = _strip_fails(impl_text_orig)
            if impl_text != impl_text_orig:
                n_stripped += 1
            spec_text = r.get("spec_text", "")
            if not impl_text.strip():
                n_skipped += 1
                continue
            buggy_source_lines = set(int(i) for i in r.get("buggy_lines", []))
            ex = Example(
                source=Source.SFT_SAFE,
                spec_id=r["spec_id"], impl_id=r["impl_id"],
                spec_text=spec_text, impl_text=impl_text,
                status=_status_from_str(r.get("status","")),
                buggy_lines=buggy_source_lines,
            )
            t = tokenize_example(ex, tok, max_length=max_len)
            if t is None or not t.sentinel_positions:
                n_skipped += 1
                continue
            input_ids = torch.tensor([t.input_ids], device=device)
            attn = torch.ones_like(input_ids)
            sent_pos = [torch.tensor(t.sentinel_positions, device=device)]
            with torch.no_grad():
                out = model(input_ids, attn, sent_pos, lse_temperature=lse_t)
            per_line = out.per_line_energies[0].float().cpu().tolist()
            whole = float(out.whole_impl_energies[0].float().cpu().item())
            all_lines = impl_text.splitlines()
            scorable = scorable_line_indices(impl_text)
            scorable_texts = [all_lines[i] for i in scorable][: len(per_line)]
            src_to_sent = {s: i for i, s in enumerate(scorable)}
            buggy_sent = sorted({src_to_sent[s] for s in buggy_source_lines
                                  if s in src_to_sent and src_to_sent[s] < len(per_line)})
            f_out.write(json.dumps({
                "impl_id": ex.impl_id, "spec_id": ex.spec_id,
                "source": "verus_real_stripped",
                "status": ex.status.value,
                "whole_impl_energy": whole,
                "per_line_energies": per_line,
                "buggy_line_indices": buggy_sent,
                "scorable_line_texts": scorable_texts,
            }) + "\n")
            n_written += 1
            if n_written % 100 == 0:
                print(f"  {n_written} done", flush=True)
    print(f"DONE: wrote {n_written}, skipped {n_skipped}, "
          f"{n_stripped} impls had at least one `// FAILS` line stripped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
