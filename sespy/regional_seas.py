"""Regional seas knowledge base — replaces SP1's placeholder dict.

Loaded eagerly at module import via _load_kb(). The seas dict is
exposed via get_regional_seas() (matches SP1's contract shape). Since K1
the wizard's countries and EU membership come from R's governance data
(`sespy/data/r_kb/country_governance_db.json`, see
`kb_suggestions.countries_for_sea`), so this file no longer lists them.
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
    ecosystem_types, common_issues}}."""
    return _KB["regional_seas"]
