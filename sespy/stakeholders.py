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
