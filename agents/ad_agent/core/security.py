"""Generic deterministic hashing helpers for Core contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize contract/security material deterministically.

    ``sort_keys`` plus compact separators gives equivalent JSON objects the
    same representation while avoiding Python's implementation-specific
    ``repr`` output. ``default=str`` is retained for legacy Tool inputs that
    contain UUID/date-like scalar values.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def normalize_field_name(value: Any) -> str:
    """Normalize a structured field name for generic contract comparisons."""
    return "".join(char for char in str(value or "").lower() if char.isalnum())
