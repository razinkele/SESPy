"""Async reader for Shiny 1.7.0 test-mode snapshots.

The shipped controller (shiny.playwright.controller.AppTestValues) is built on
playwright.sync_api; SESPy's e2e scripts use the async API, so this mirrors its
_fetch(): discover the snapshot URL from the Shiny client, GET it, parse JSON.
Requires the server to run with SHINY_TESTMODE=1 (tests/run_e2e.py sets it).
"""
from __future__ import annotations

from typing import Any

_DISCOVER = ("() => window.Shiny?.shinyapp?.getTestSnapshotBaseUrl?."
             "({ fullUrl: true }) ?? false")


async def snapshot(page, timeout_ms: int = 15000) -> dict[str, Any]:
    handle = await page.wait_for_function(_DISCOVER, timeout=timeout_ms)
    url = str(await handle.json_value())
    response = await page.request.get(url)
    if not response.ok:
        raise RuntimeError(
            f"test-mode snapshot {url} returned HTTP {response.status}; "
            "is the server running with SHINY_TESTMODE=1?")
    return await response.json()


def export_value(snap: dict[str, Any], key: str) -> Any:
    """The `export` entry `key`, or a KeyError naming it."""
    exports = snap.get("export") or {}
    if key not in exports:
        raise KeyError(f"{key!r} not in snapshot export block: {sorted(exports)}")
    return exports[key]
