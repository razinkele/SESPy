from __future__ import annotations

from typing import Any


def safe_int(value: Any, default: int) -> int:
    """Return `value` as int, or `default` when it is missing/empty/invalid.

    This intentionally preserves valid falsy ints such as 0, unlike `int(x or default)`.
    """
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float) -> float:
    """Return `value` as float, or `default` when it is missing/empty/invalid."""
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
