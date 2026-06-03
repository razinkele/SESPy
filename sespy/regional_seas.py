"""Regional seas knowledge base — replaces SP1's placeholder dict.

Loaded eagerly at module import via _load_kb(). The seas dict is
exposed via get_regional_seas() (matches SP1's contract shape) and
EU membership is exposed via get_eu_member_codes() for SP3.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_KB_PATH = Path(__file__).parent / "regional_seas.json"


def _load_kb() -> dict[str, Any]:
    with _KB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_KB = _load_kb()


def get_regional_seas() -> dict[str, dict[str, Any]]:
    """Return the seas dict in SP1's contract shape: {slug: {name,
    ecosystem_types, common_issues, countries, country_codes}}."""
    return _KB["regional_seas"]


def get_eu_member_codes() -> set[str]:
    """Return ISO-2 codes of EU member states as a fresh `set` for fast
    membership tests. Used by SP3's governance suggestions. (A `set` is
    constructed each call rather than cached; it's microseconds for 22
    elements and avoids any caller mutating a shared object.)"""
    return set(_KB["eu_member_codes"])
