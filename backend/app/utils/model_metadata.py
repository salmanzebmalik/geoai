from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.segmentation import ModelVariant


MODEL_VARIANTS: tuple[ModelVariant, ...] = (
    "sam2.1_hiera_large",
    "sam2.1_hiera_tiny",
)


def stored_model_variant(
    stored_result: Mapping[str, Any] | None,
) -> ModelVariant | None:
    """Return an explicit variant or recover it from legacy model names."""
    stored_result = stored_result or {}
    explicit = stored_result.get("model_variant")
    if explicit in MODEL_VARIANTS:
        return explicit

    model_name = str(stored_result.get("model_name") or "")
    prefix = "lang-sam-"
    inferred = model_name[len(prefix):] if model_name.startswith(prefix) else None
    if inferred in MODEL_VARIANTS:
        return inferred
    return None
