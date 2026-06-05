"""Pure list-mutation helpers for the stakeholder register.

No Shiny imports — every function takes a list and returns a NEW list, so the
reactive module layer stays a thin wrapper and these stay trivially testable.
The caller injects `today` (keeps these pure / no datetime.now inside) and is
responsible for name+type validation before calling add/update.
"""

from __future__ import annotations

from dataclasses import replace

from sespy.data_structure import Stakeholder
from sespy.utils import next_id


def add_stakeholder(
    items: list[Stakeholder], fields_: dict, *, today: str
) -> list[Stakeholder]:
    # INVARIANT: `fields_` contains only valid Stakeholder field names and
    # NEVER `id` or `created_at` (those are assigned here). The module layer
    # builds it from exactly the form inputs, so this holds.
    sid = next_id([s.id for s in items], "SH")
    return [*items, Stakeholder(id=sid, created_at=today, **fields_)]


def update_stakeholder(
    items: list[Stakeholder], sid: str, fields_: dict
) -> list[Stakeholder]:
    return [replace(s, **fields_) if s.id == sid else s for s in items]


def remove_stakeholder(items: list[Stakeholder], sid: str) -> list[Stakeholder]:
    return [s for s in items if s.id != sid]


# --- SH2: Power-Interest grid classification (pure) -------------------------
_LEVEL_NUM = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
QUADRANTS = ("key_players", "keep_satisfied", "keep_informed", "monitor")


def level_num(level: str) -> int | None:
    """Map a power/interest code to its 1-3 axis position, or None if blank/unknown."""
    return _LEVEL_NUM.get(level)


def classify_quadrant(power: str, interest: str) -> str | None:
    """Mendelow quadrant for a (power, interest) pair, or None if either is unset.

    Binning: a value is "high" iff it is MEDIUM or HIGH (>= 2 on the 1-3 axis),
    matching the plot's colored regions. This classifies MEDIUM stakeholders
    (R dropped them from its summary entirely).
    """
    p, i = level_num(power), level_num(interest)
    if p is None or i is None:
        return None
    high_p, high_i = p >= 2, i >= 2
    if high_p and high_i:
        return "key_players"
    if high_p and not high_i:
        return "keep_satisfied"
    if not high_p and high_i:
        return "keep_informed"
    return "monitor"


def summarize_quadrants(items: list[Stakeholder]) -> dict[str, list[str]]:
    """Return {quadrant_key: [names]} for the 4 quadrants plus "unplotted"
    (stakeholders missing power or interest). All 5 keys always present."""
    out: dict[str, list[str]] = {q: [] for q in QUADRANTS}
    out["unplotted"] = []
    for s in items:
        q = classify_quadrant(s.power, s.interest)
        out[q if q is not None else "unplotted"].append(s.name)
    return out
