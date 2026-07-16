"""UUID normalization helpers shared across SQL boundaries."""

from __future__ import annotations

from uuid import UUID


def normalize_uuid(value):
    """Return a canonical UUID string or None for invalid values."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(UUID(text))
    except Exception:
        return None


def is_valid_uuid(value) -> bool:
    return normalize_uuid(value) is not None


def filter_valid_uuids(values):
    """Return deduplicated canonical UUID strings from an iterable."""
    if values is None:
        return []
    seen = set()
    result = []
    for value in values:
        normalized = normalize_uuid(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
