"""UI-side reference-data helpers (Shiny-dependent; the library `r_kb` is not).

`LAGUNA_R_DATA_DIR` is the app's default live override directory on the
laguna host. It is passed to `r_kb.configure(..., default_override_dir=...)`
by `app.py`; the library itself carries no deployment path.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from shiny import reactive

LAGUNA_R_DATA_DIR = "/srv/shiny-server/marinesabres/data"


def add_reads(reads: Any, names: Iterable[str]) -> None:
    """Record that this session read `names` from its snapshot.

    `reads` is the session's `reactive.Value[frozenset[str]]`, or None for a
    caller mounted without one (MosaicSES): then this is a no-op. The value
    is read under `isolate()` and set only when a name is new, so a render
    that calls this never invalidates itself (`Value.set` compares by
    identity, so an unconditional set of a fresh frozenset would loop).
    """
    if reads is None:
        return
    with reactive.isolate():
        current_reads = reads.get()
    new = frozenset(names) - current_reads
    if new:
        reads.set(current_reads | new)
