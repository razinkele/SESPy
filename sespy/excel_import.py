"""Excel import — port of the R app's universal_excel_loader.R + the column-
name fallback constants from constants.R (FROM_COL_NAMES / TO_COL_NAMES).

Accepts an .xlsx with two sheets:
  * `Elements` (or `elements`) — columns: id, label, type, [description, confidence]
  * `Connections` (or `connections`) — columns: source/from, target/to, [polarity, strength, confidence]

Returns a `Project` ready to feed `project_data.set(...)`. Validation reuses
the same `validate_project_payload` the load_project handler uses, so
schema errors from upload look identical to schema errors from JSON load.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .data_structure import Connection, Element, IsaData, Project, ProjectMetadata
from .persistent_storage import ValidationResult, validate_project_payload

# Column-name fallbacks (case-insensitive, port of constants.R)
ELEMENT_ID_COLS    = ("id", "ID", "Id", "node", "Node")
ELEMENT_LABEL_COLS = ("label", "Label", "name", "Name")
ELEMENT_TYPE_COLS  = ("type", "Type", "group", "Group", "category", "Category")
ELEMENT_DESC_COLS  = ("description", "Description", "indicator", "Indicator")
ELEMENT_CONF_COLS  = ("confidence", "Confidence")

CONN_SOURCE_COLS   = ("source", "from", "from_node", "node1", "start",
                      "Source", "From")
CONN_TARGET_COLS   = ("target", "to", "to_node", "node2", "end",
                      "Target", "To")
CONN_POLARITY_COLS = ("polarity", "Polarity", "sign", "Sign")
CONN_STRENGTH_COLS = ("strength", "Strength", "weight", "Weight")
CONN_CONF_COLS     = ("confidence", "Confidence")
CONN_DELAY_COLS    = ("delay", "Delay", "lag", "Lag")

ELEMENTS_SHEET_NAMES    = ("Elements", "elements", "Nodes", "nodes")
CONNECTIONS_SHEET_NAMES = ("Connections", "connections", "Edges", "edges", "Links", "links")


def _pick(row: pd.Series, candidates: Sequence[str], default: Any = "") -> Any:
    """Return the first candidate column value found in `row`, or `default`."""
    for name in candidates:
        if name in row.index:
            v = row[name]
            if pd.notna(v):
                return v
    return default


def _resolve_sheet(workbook: pd.ExcelFile, candidates: Sequence[str]) -> str | None:
    """Find the first matching sheet name (case-insensitive)."""
    sheet_lower = {name.lower(): name for name in workbook.sheet_names}
    for c in candidates:
        if c.lower() in sheet_lower:
            return sheet_lower[c.lower()]
    return None


def parse_excel(path: Path | str) -> ValidationResult:
    """Parse an .xlsx into a `Project`. Returns `ValidationResult`:
    * `result.valid` — schema check passed
    * `result.project` — populated Project (only if valid)
    * `result.errors` — list of string errors (e.g. missing sheets, bad refs)
    """
    path = Path(path)
    if not path.exists():
        return ValidationResult(False, [f"File not found: {path.name}"])

    try:
        workbook = pd.ExcelFile(path, engine="openpyxl")
    except Exception as e:
        return ValidationResult(False, [f"Cannot open Excel file: {e}"])

    elements_sheet = _resolve_sheet(workbook, ELEMENTS_SHEET_NAMES)
    connections_sheet = _resolve_sheet(workbook, CONNECTIONS_SHEET_NAMES)

    errors: list[str] = []
    if elements_sheet is None:
        errors.append(
            f"No elements sheet found. Expected one of: {ELEMENTS_SHEET_NAMES}"
        )
    if connections_sheet is None:
        errors.append(
            f"No connections sheet found. Expected one of: {CONNECTIONS_SHEET_NAMES}"
        )
    if errors:
        return ValidationResult(False, errors)

    elements_df = pd.read_excel(workbook, sheet_name=elements_sheet)
    connections_df = pd.read_excel(workbook, sheet_name=connections_sheet)

    elements: list[Element] = []
    for i, row in elements_df.iterrows():
        eid = _pick(row, ELEMENT_ID_COLS)
        if eid == "":
            errors.append(f"Elements row {i + 2}: missing id")
            continue
        elements.append(Element(
            id=str(eid),
            label=str(_pick(row, ELEMENT_LABEL_COLS, default=eid)),
            type=str(_pick(row, ELEMENT_TYPE_COLS, default="")),
            description=str(_pick(row, ELEMENT_DESC_COLS, default="")),
            confidence=int(_pick(row, ELEMENT_CONF_COLS, default=3) or 3),
        ))

    connections: list[Connection] = []
    for i, row in connections_df.iterrows():
        src = _pick(row, CONN_SOURCE_COLS)
        tgt = _pick(row, CONN_TARGET_COLS)
        if src == "" or tgt == "":
            errors.append(f"Connections row {i + 2}: missing source/target")
            continue
        connections.append(Connection(
            source=str(src),
            target=str(tgt),
            polarity=str(_pick(row, CONN_POLARITY_COLS, default="+")) or "+",
            strength=str(_pick(row, CONN_STRENGTH_COLS, default="medium")) or "medium",
            confidence=int(_pick(row, CONN_CONF_COLS, default=3) or 3),
            delay=str(_pick(row, CONN_DELAY_COLS, default="immediate")) or "immediate",
        ))

    if errors:
        return ValidationResult(False, errors)

    # Build the same dict shape the JSON loader uses, then run it through
    # the shared validator so a bad Excel file fails the same way a bad
    # JSON file does (dangling refs, duplicate ids, etc.)
    payload = {
        "metadata": {
            "name": path.stem,
            "description": f"Imported from {path.name}",
        },
        "isa_data": {
            "elements":    [e.__dict__ for e in elements],
            "connections": [c.__dict__ for c in connections],
        },
    }
    return validate_project_payload(payload)
