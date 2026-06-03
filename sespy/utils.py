"""Shared utilities — pure-Python helpers used across multiple modules.

This module has no Shiny imports and no other intra-project dependencies
beyond the standard library. Anything that's a useful pure-data helper
shared by 2+ modules can land here.
"""
from __future__ import annotations


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
