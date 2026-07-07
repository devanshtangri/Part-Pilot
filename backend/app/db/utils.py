from __future__ import annotations

import re
import unicodedata
from typing import Any


_WHITESPACE_RE = re.compile(r"\s+")
_SLUG_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")


def clean_text(value: str | None) -> str | None:
    """Trim repeated whitespace. Return None for empty text."""
    if value is None:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def normalize_lookup_text(value: str | None) -> str:
    """Normalize text for case-insensitive lookup/autocomplete keys."""
    cleaned = clean_text(value)
    if cleaned is None:
        return ""
    normalized = unicodedata.normalize("NFKC", cleaned).casefold()
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def slugify(value: str) -> str:
    """Create a stable ASCII slug for built-in/template names."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_SEPARATOR_RE.sub("-", ascii_value.lower()).strip("-")
    return slug or "item"


def normalize_location_name(value: str) -> str:
    """Normalize a location name for uniqueness while preserving flexible user labels."""
    return normalize_lookup_text(value)


def display_part_title(part_number: str | None, name: str | None) -> str:
    """Part display rule: part number first, fallback to name."""
    return clean_text(part_number) or clean_text(name) or "Untitled part"


def available_quantity(total_quantity: int, reserved_quantity: int) -> int:
    """Compute available quantity from stored total and reserved counts."""
    return int(total_quantity) - int(reserved_quantity)


def is_out_of_stock(total_quantity: int) -> bool:
    return int(total_quantity) <= 0


def parse_setting_value(value_json: Any, value_text: str | None = None, default: Any = None) -> Any:
    """Return JSON-backed setting value with a text fallback."""
    if value_json is not None:
        return value_json
    if value_text is not None:
        return value_text
    return default
