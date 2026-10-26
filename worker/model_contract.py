"""Pure validation helpers shared by the Modal worker and local tests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


MODEL_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class ModelContractError(ValueError):
    """Raised when an uploaded voice model violates the runtime contract."""


def validate_model_slug(value: str) -> str:
    slug = value.strip().lower()
    if not MODEL_SLUG.fullmatch(slug):
        raise ModelContractError("model_slug must contain only lowercase letters, numbers, and hyphens")
    return slug


def resolve_model_files(volume_root: Path, model_slug: str) -> tuple[Path, Path]:
    """Return the single checkpoint/index pair for a model without path traversal."""
    slug = validate_model_slug(model_slug)
    model_dir = volume_root / "models" / slug
    if not model_dir.is_dir():
        raise ModelContractError(f"Model directory not found: models/{slug}")

    checkpoints = sorted(model_dir.glob("*.pth"))
    indexes = sorted(model_dir.glob("*.index"))
    if len(checkpoints) != 1:
        raise ModelContractError(f"Expected exactly one .pth file; found {len(checkpoints)}")
    if len(indexes) != 1:
        raise ModelContractError(f"Expected exactly one .index file; found {len(indexes)}")
    return checkpoints[0], indexes[0]


def summarize_checkpoint(checkpoint: Any) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        raise ModelContractError("Checkpoint root must be a dictionary")

    weights = checkpoint.get("weight") or checkpoint.get("model")
    if not isinstance(weights, dict) or not weights:
        raise ModelContractError("Checkpoint does not contain a non-empty weight/model dictionary")

    config = checkpoint.get("config")
    if config is not None and not isinstance(config, (list, tuple)):
        raise ModelContractError("Checkpoint config has an unexpected format")

    version = str(checkpoint.get("version") or "unknown")
    sample_rate = checkpoint.get("sr")
    if sample_rate is None and config:
        sample_rate = config[-1]

    return {
        "version": version,
        "sample_rate": str(sample_rate or "unknown"),
        "f0": checkpoint.get("f0"),
        "weight_tensors": len(weights),
    }
