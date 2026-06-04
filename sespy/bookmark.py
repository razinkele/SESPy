"""URL-bookmarking helpers (view-only). Pure — no Shiny imports."""
from __future__ import annotations

from urllib.parse import parse_qs


def parse_view(search: str | None, valid_views: set[str]) -> str | None:
    """Return the ?view value iff present AND in valid_views; else None.

    Tolerates a leading '?', None/empty input, missing/empty/repeated keys
    (first value wins). The client encodes when it sets the param, so there
    is no build_view counterpart — the server sends the raw view id.
    """
    if not search:
        return None
    values = parse_qs(search.lstrip("?")).get("view") or []
    view = values[0] if values else None
    return view if view in valid_views else None
