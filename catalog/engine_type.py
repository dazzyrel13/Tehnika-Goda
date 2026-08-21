"""Detect and normalize vehicle engine / fuel type for filters."""

from __future__ import annotations

# Keep in sync with catalog.models.EngineType values.
PETROL = "petrol"
ELECTRIC = "electric"
HYBRID = "hybrid"

_ELECTRIC_MARKERS = (
    "электр",
    "electric",
    "bev",
    "pure electric",
)
_HYBRID_MARKERS = (
    "гибрид",
    "hybrid",
    "phev",
    "plug-in",
    "plugin",
    "hev",
)
_PETROL_MARKERS = (
    "бензин",
    "petrol",
    "gasoline",
)


def detect_engine_type(value: str) -> str:
    """Return engine type code or empty string if unknown."""
    text = " ".join((value or "").lower().replace("ё", "е").split())
    if not text:
        return ""

    # Hybrid before electric: "plug-in hybrid" / "гибридный электро".
    if any(marker in text for marker in _HYBRID_MARKERS):
        return HYBRID
    if any(marker in text for marker in _ELECTRIC_MARKERS):
        return ELECTRIC
    if any(marker in text for marker in _PETROL_MARKERS):
        return PETROL
    # Standalone "ev" as a token (avoid matching inside other words).
    tokens = set(text.replace("-", " ").split())
    if "ev" in tokens:
        return ELECTRIC
    return ""
