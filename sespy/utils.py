"""Shared utilities — pure-Python helpers used across multiple modules.

This module has no Shiny imports and no other intra-project dependencies
beyond the standard library. Anything that's a useful pure-data helper
shared by 2+ modules can land here.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


def _finite_number(v: Any) -> float | None:
    """R `as.numeric` on one scalar, finite values only: an int, a float or a
    numeric string (surrounding whitespace allowed) -> float; a bool, None, a
    non-numeric value, NaN or +-inf -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    elif isinstance(v, str):
        try:
            f = float(v)
        except ValueError:
            return None
    else:
        return None
    return f if math.isfinite(f) else None


def safe_counter(counter: Any, ids: Iterable[Any], prefix: str) -> int:
    """R `safe_counter` (functions/data_structure.R:25-33, v1.33.0): the
    larger of the stored counter and the largest numeric suffix of the str
    ids that start with `prefix`.

    The counter counts only as a finite number (`_finite_number`; anything
    else is 0). Suffixes are read like R's `as.numeric` (pending D4):
    "RM1e2" -> 100, "RM 7" -> 7, "RM12.5" -> 12.5; non-numeric and
    non-finite suffixes are ignored. Result `int(max(...))`, so the next ID
    is `prefix + f"{safe_counter(...) + 1:03d}"` (R next_element_id).
    """
    nums = [_finite_number(counter) or 0.0]
    for i in ids:
        if isinstance(i, str) and i.startswith(prefix):
            n = _finite_number(i[len(prefix):])
            if n is not None:
                nums.append(n)
    return int(max(nums))


def next_id(existing_ids: list[str], prefix: str) -> str:
    """Return the next available id for a given DAPSIWRM type prefix.

    Uses gap-filling semantics: scans `existing_ids` for matching
    `<prefix><N>` ids, then returns `<prefix><N>` for the lowest N
    starting from 1 that's not in use, padded to 3 digits. This
    preserves stable id reuse after deletions and matches the
    behavior of the original `_next_id` in `isa_data_entry.py`.

    Examples:
        >>> next_id([], "D")
        'D001'
        >>> next_id(["D001", "D003"], "D")  # gap at D002
        'D002'
        >>> next_id(["D001", "D002", "D003"], "D")
        'D004'
        >>> next_id(["P001"], "D")
        'D001'
    """
    used = {
        int(eid[len(prefix):])
        for eid in existing_ids
        if eid.startswith(prefix) and eid[len(prefix):].isdigit()
    }
    n = 1
    while n in used:
        n += 1
    return f"{prefix}{n:03d}"
