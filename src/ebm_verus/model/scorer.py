"""End-to-end scorer: Qwen + LoRA + per-line head.

Forward pass:
  1. Run backbone on (B, L) input_ids → hidden_states (B, L, D)
  2. For each batch element b, gather hidden_states[b, sentinel_positions[b], :]
  3. Apply per-line head → per-line energies (variable length per impl)
  4. Aggregate via normalized LSE at the current temperature → whole-impl energy

We return both per-line and whole-impl energies so losses can use either.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

from ebm_verus.model.head import PerLineEnergyHead, ScalarEnergyHead, normalized_lse


@dataclass
class ScorerOutput:
    """Output of the energy scorer for a batch.

    ``per_line_energies`` is a list of length B, each (n_lines_b,) — variable
    length, NOT a padded tensor, because losses iterate per-impl anyway.

    ``whole_impl_energies`` is a (B,) tensor. In legacy mode (LSE) this is the
    LSE-aggregated per-line energies. In hybrid mode (Alt A+ / run #10) this is
    the direct scalar-head output trained on impl-pair hinge, NOT an aggregation.
    """

    per_line_energies: list[torch.Tensor]
    whole_impl_energies: torch.Tensor


class EnergyScorer(nn.Module):
    """Causal LM backbone with LoRA + a per-line energy head.

    The backbone weights are frozen; only LoRA adapters + the head are trained.
    """

    def __init__(
        self,
        backbone_name: str,
        *,
        lora_rank: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.05,
        lora_target_modules: tuple[str, ...] = (
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ),
        embed_lora_rank: int = 8,
        head_hidden_dim: int = 256,
        head_dropout: float = 0.1,
        head_init_std: float = 0.02,
        torch_dtype: torch.dtype = torch.bfloat16,
        gradient_checkpointing: bool = True,
        scalar_head: bool = False,
    ) -> None:
        super().__init__()

        base = AutoModelForCausalLM.from_pretrained(
            backbone_name,
            torch_dtype=torch_dtype,
        )
        # We never use the LM head; drop it to save memory and avoid touching it
        # accidentally. We only need hidden_states from the encoder stack.
        # Keep the head intact for now (PEFT may inspect it), but mark it as
        # non-trainable.
        for p in base.parameters():
            p.requires_grad = False

        # All-linear LoRA on the transformer body, plus a separate low-rank LoRA
        # on the embedding layer for lexical adaptation to Verus syntax.
        lora_cfg = LoraConfig(
            r=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=list(lora_target_modules) + (
                ["embed_tokens"] if embed_lora_rank > 0 else []
            ),
            # Per-module rank pattern: lower rank on embed_tokens.
            rank_pattern={"embed_tokens": embed_lora_rank} if embed_lora_rank > 0 else {},
            bias="none",
            task_type="FEATURE_EXTRACTION",  # we use hidden_states, not LM logits
        )
        self.backbone = get_peft_model(base, lora_cfg)

        if gradient_checkpointing:
            self.backbone.gradient_checkpointing_enable(
                gradient_checkpointing_kwargs={"use_reentrant": False}
            )
            # Required for grad-checkpointing to actually save memory.
            self.backbone.enable_input_require_grads()

        hidden_size = base.config.hidden_size
        self.head = PerLineEnergyHead(
            in_dim=hidden_size,
            hidden_dim=head_hidden_dim,
            dropout=head_dropout,
            init_std=head_init_std,
        )
        # Optional scalar head for the run-#10 hybrid (Alt A+): direct whole-impl
        # energy via attention-pool, trained on impl-pair hinge. Avoids the
        # LSE-aggregator bias-drift that inverted run #9's AUROC.
        self.use_scalar_head = scalar_head
        if scalar_head:
            self.scalar_head = ScalarEnergyHead(
                in_dim=hidden_size,
                hidden_dim=head_hidden_dim,
                dropout=head_dropout,
                init_std=head_init_std,
            )
        else:
            self.scalar_head = None

    @property
    def hidden_size(self) -> int:
        return self.backbone.config.hidden_size

    def _hidden_states(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Final-layer hidden states ``(B, L, D)``."""
        out = self.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True,
            use_cache=False,
            return_dict=True,
        )
        return out.hidden_states[-1]

    def forward(
        self,
        input_ids: torch.Tensor,             # (B, L)
        attention_mask: torch.Tensor,        # (B, L)
        sentinel_positions: list[torch.Tensor],  # list of (n_lines_b,)
        *,
        lse_temperature: float,
    ) -> ScorerOutput:
        hidden = self._hidden_states(input_ids, attention_mask)  # (B, L, D)

        per_line: list[torch.Tensor] = []
        whole_impl: list[torch.Tensor] = []
        for b, sent_pos in enumerate(sentinel_positions):
            if sent_pos.numel() == 0:
                per_line.append(hidden.new_zeros((0,)))
                whole_impl.append(hidden.new_zeros(()))
                continue
            sent_pos = sent_pos.to(hidden.device)
            h_lines = hidden[b].index_select(0, sent_pos)
            e_lines = self.head(h_lines.float())
            per_line.append(e_lines)
            if self.use_scalar_head:
                e_scalar = self.scalar_head(
                    hidden[b].float(),
                    attention_mask[b],
                )
                whole_impl.append(e_scalar)
            else:
                whole_impl.append(normalized_lse(e_lines, lse_temperature))

        whole_impl_t = torch.stack(whole_impl)  # (B,)
        return ScorerOutput(
            per_line_energies=per_line,
            whole_impl_energies=whole_impl_t,
        )

    # ---- introspection helpers ----------------------------------------------

    def trainable_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def total_parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    # ---- checkpoint I/O -----------------------------------------------------
    # We only persist the *trainable* parts: LoRA adapters + the per-line head.
    # The frozen backbone is reconstructable from the HF name + LoRA config.

    def save_trainable(self, ckpt_dir: str | "os.PathLike") -> None:  # type: ignore[name-defined]
        """Save LoRA adapters + head state to ``ckpt_dir``.

        Layout:
          ckpt_dir/adapter/   (PEFT save_pretrained: adapter_config.json + .safetensors)
          ckpt_dir/head.pt    (head state_dict)
        """
        import os
        from pathlib import Path
        d = Path(ckpt_dir)
        d.mkdir(parents=True, exist_ok=True)
        self.backbone.save_pretrained(str(d / "adapter"))
        import torch as _torch
        _torch.save(self.head.state_dict(), str(d / "head.pt"))
        if self.scalar_head is not None:
            _torch.save(self.scalar_head.state_dict(), str(d / "scalar_head.pt"))

    def load_trainable(self, ckpt_dir: str | "os.PathLike") -> None:  # type: ignore[name-defined]
        """Inverse of ``save_trainable``. Loads LoRA adapter weights + head.

        PEFT's ``load_adapter`` interprets relative paths as HF repo ids, so we
        resolve to an absolute path (which it then treats as a local dir).
        """
        from pathlib import Path
        import torch as _torch
        d = Path(ckpt_dir).resolve()
        adapter_dir = str(d / "adapter")
        # load_adapter REPLACES the existing 'default' adapter with the saved
        # weights. is_trainable=True keeps it as a LoRA so the saved adapter
        # config matches our trainable LoRA structure.
        # The path must be absolute, otherwise PEFT treats it as an HF repo_id.
        from peft import PeftModel  # noqa: F401
        # peft 0.x exposes load_adapter on the PeftModel object directly.
        # If the adapter named "default" already exists (it does — set up in
        # __init__), load_adapter complains. Trick: use set_peft_model_state_dict
        # instead, loading the safetensors manually.
        from peft.utils.save_and_load import load_peft_weights, set_peft_model_state_dict
        weights = load_peft_weights(adapter_dir, device="cpu")
        set_peft_model_state_dict(self.backbone, weights, adapter_name="default")
        self.head.load_state_dict(_torch.load(str(d / "head.pt"), map_location="cpu"))
        if self.scalar_head is not None:
            sh_path = d / "scalar_head.pt"
            if sh_path.exists():
                self.scalar_head.load_state_dict(_torch.load(str(sh_path), map_location="cpu"))
