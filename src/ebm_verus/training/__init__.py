"""Training: losses + loop + config."""

from ebm_verus.training.loop import StopPointTriggered, TrainConfig, train
from ebm_verus.training.losses import (
    LossOutput,
    compute_loss,
    l_line_hinge,
    l_spec_infonce,
)

__all__ = [
    "LossOutput",
    "StopPointTriggered",
    "TrainConfig",
    "compute_loss",
    "l_line_hinge",
    "l_spec_infonce",
    "train",
]
