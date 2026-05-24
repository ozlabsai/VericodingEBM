"""Per-line energy head + LSE aggregator.

The head is a tiny MLP that maps each sentinel's final-layer hidden state to a
scalar energy. The aggregator combines per-line energies into a whole-impl
energy via temperature-annealed LogSumExp.

LSE is normalized so the result has units of "energy per line" rather than
"sum of line energies" — i.e. ``T * log(mean(exp(E_i / T)))``. This means LSE
collapses to mean as T→∞ and to max as T→0, regardless of how many lines the
impl has. Without the normalization, whole-impl energy scales with line count,
which would couple "longer impl" with "higher energy" and bias the L_spec
contrast against long impls.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class PerLineEnergyHead(nn.Module):
    """``hidden_state -> scalar energy`` per sentinel position.

    Unbounded (no sigmoid). Higher = more likely buggy.
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 256,
        dropout: float = 0.1,
        init_std: float = 0.02,
    ) -> None:
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(dropout)

        nn.init.normal_(self.fc1.weight, std=init_std)
        nn.init.zeros_(self.fc1.bias)
        nn.init.normal_(self.fc2.weight, std=init_std)
        nn.init.zeros_(self.fc2.bias)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """``(N, in_dim) -> (N,)`` energies."""
        x = F.gelu(self.fc1(hidden_states))
        x = self.dropout(x)
        x = self.fc2(x)
        return x.squeeze(-1)


class ScalarEnergyHead(nn.Module):
    """Direct whole-impl energy: attention-pool over [spec; impl] hidden states → scalar.

    Used by run #10 hybrid (Alt A+) to avoid the LSE-aggregator bias-drift
    pathology that broke run #9's AUROC. The scalar head is trained on impl-pair
    hinge so the energy is directly calibrated for cross-impl ranking, not
    inherited from per-line energies.
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 256,
        dropout: float = 0.1,
        init_std: float = 0.02,
    ) -> None:
        super().__init__()
        self.attn_q = nn.Parameter(torch.zeros(in_dim))
        self.fc1 = nn.Linear(in_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(dropout)
        nn.init.normal_(self.attn_q, std=init_std)
        nn.init.normal_(self.fc1.weight, std=init_std)
        nn.init.zeros_(self.fc1.bias)
        nn.init.normal_(self.fc2.weight, std=init_std)
        nn.init.zeros_(self.fc2.bias)

    def forward(
        self,
        hidden_states: torch.Tensor,        # (L, D)
        attention_mask: torch.Tensor,       # (L,) 1 = real token, 0 = pad
    ) -> torch.Tensor:
        # scores: (L,)
        scores = hidden_states @ self.attn_q
        scores = scores.masked_fill(attention_mask == 0, float("-inf"))
        weights = torch.softmax(scores, dim=-1)
        pooled = (weights.unsqueeze(-1) * hidden_states).sum(dim=0)  # (D,)
        x = F.gelu(self.fc1(pooled))
        x = self.dropout(x)
        x = self.fc2(x)
        return x.squeeze(-1)  # scalar


def normalized_lse(energies: torch.Tensor, temperature: float) -> torch.Tensor:
    """``T * log(mean(exp(E / T)))`` over the last dim.

    Args:
        energies: ``(..., N)`` per-line energies. Caller is responsible for
            masking out non-existent lines (padding) BEFORE calling — pass only
            the real per-line energies for this impl.
        temperature: positive scalar; high = mean-like (dense gradient), low =
            max-like (structural).

    Returns:
        ``(...,)`` aggregated energy. Returns 0 if energies is empty.
    """
    if energies.numel() == 0:
        return energies.new_zeros(())
    # T * logsumexp(E/T) - T * log(N)  ==  T * log(mean(exp(E/T)))
    n = energies.shape[-1]
    return temperature * (
        torch.logsumexp(energies / temperature, dim=-1) - torch.log(torch.tensor(float(n)))
    )


def lse_temperature_schedule(step: int, total_steps: int, t_start: float, t_end: float) -> float:
    """Linear interpolation of LSE temperature over training steps."""
    if total_steps <= 0:
        return t_end
    frac = max(0.0, min(1.0, step / total_steps))
    return t_start + (t_end - t_start) * frac
