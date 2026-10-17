"""The one hashing helper for R-sourced files (P1a).

tests/parity/test_r_sync.py, P2's template sync script, K1's live drift
check (tests/parity/check_live.py) and K1's provenance all hash through
these two functions, so their hashes always agree. Shiny-free, stdlib only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_norm(obj: Any) -> str:
    """Hash parsed JSON. Key order, whitespace, CRLF and a BOM in the source
    file never reach the hash, because `obj` is already parsed."""
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_text_norm(text: str) -> str:
    """Hash a non-JSON text file (R source) with CRLF normalised to LF."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
