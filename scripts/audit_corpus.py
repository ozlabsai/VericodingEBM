"""Audit #4: measure publicly-available Verus source corpus size.

Decides PLAN.md §5.5 (continued pretraining) go/no-go:
  - corpus < 2MB   → skip CPT entirely (too little signal)
  - corpus 2-20MB  → skip unless Friday data pipeline finishes by 14:00
  - corpus > 20MB  → run CPT per §5.5

Strategy: shallow-clone the main Verus repos into /tmp, find `.rs` files
containing the `verus!` macro, sum their bytes.

Usage:
    bash scripts/audit_corpus.sh
"""
print("This is a placeholder — see scripts/audit_corpus.sh for the actual work.")
