"""Unit tests for the Excel import parser."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sespy.excel_import import parse_excel


def _write_workbook(
    tmp_path: Path,
    *,
    elements: list[dict],
    connections: list[dict],
    elements_sheet: str = "Elements",
    connections_sheet: str = "Connections",
    name: str = "test.xlsx",
) -> Path:
    out = tmp_path / name
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        pd.DataFrame(elements).to_excel(xl, sheet_name=elements_sheet, index=False)
        pd.DataFrame(connections).to_excel(xl, sheet_name=connections_sheet, index=False)
    return out


VALID_ELEMENTS = [
    {"id": "D001", "label": "Tourism demand", "type": "Drivers"},
    {"id": "A001", "label": "Recreational boating", "type": "Activities"},
    {"id": "P001", "label": "Anchor damage", "type": "Pressures"},
]
VALID_CONNECTIONS = [
    {"source": "D001", "target": "A001", "polarity": "+", "strength": "strong"},
    {"source": "A001", "target": "P001", "polarity": "+", "strength": "medium"},
]


def test_parse_excel_happy_path(tmp_path):
    f = _write_workbook(tmp_path, elements=VALID_ELEMENTS, connections=VALID_CONNECTIONS)
    result = parse_excel(f)
    assert result.valid, result.errors
    proj = result.project
    assert proj is not None
    assert proj.isa_data.element_count() == 3
    assert proj.isa_data.connection_count() == 2
    assert proj.metadata.name == "test"


def test_parse_excel_case_insensitive_sheet_names(tmp_path):
    """`elements`/`connections` (lowercase), `Nodes`/`Edges`, etc. all work."""
    for el_name, conn_name in [
        ("elements", "connections"),
        ("Nodes", "Edges"),
        ("NODES", "LINKS"),
    ]:
        f = _write_workbook(
            tmp_path,
            elements=VALID_ELEMENTS,
            connections=VALID_CONNECTIONS,
            elements_sheet=el_name,
            connections_sheet=conn_name,
            name=f"{el_name}_{conn_name}.xlsx",
        )
        result = parse_excel(f)
        assert result.valid, f"failed for {el_name}/{conn_name}: {result.errors}"


def test_parse_excel_alternative_column_names(tmp_path):
    """`from`/`to` instead of `source`/`target`, `Name` instead of `label`."""
    f = _write_workbook(
        tmp_path,
        elements=[
            {"ID": "X", "Name": "X-element", "Type": "Drivers"},
            {"ID": "Y", "Name": "Y-element", "Type": "Activities"},
        ],
        connections=[
            {"from": "X", "to": "Y", "Polarity": "-", "Weight": "weak"},
        ],
    )
    result = parse_excel(f)
    assert result.valid, result.errors
    proj = result.project
    assert proj is not None
    elements = proj.isa_data.elements
    assert {e.id for e in elements} == {"X", "Y"}
    assert elements[0].label == "X-element"
    conn = proj.isa_data.connections[0]
    assert conn.source == "X" and conn.target == "Y"
    assert conn.polarity == "-"


def test_parse_excel_missing_sheet_returns_validation_error(tmp_path):
    out = tmp_path / "lonely.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        pd.DataFrame(VALID_ELEMENTS).to_excel(xl, sheet_name="Elements", index=False)
    result = parse_excel(out)
    assert not result.valid
    assert any("connections" in e.lower() for e in result.errors)


def test_parse_excel_dangling_reference_caught(tmp_path):
    f = _write_workbook(
        tmp_path,
        elements=VALID_ELEMENTS,
        connections=[
            {"source": "D001", "target": "GHOST", "polarity": "+"},  # GHOST doesn't exist
        ],
    )
    result = parse_excel(f)
    assert not result.valid
    assert any("GHOST" in e for e in result.errors)


def test_parse_excel_missing_id_per_row(tmp_path):
    f = _write_workbook(
        tmp_path,
        elements=[
            {"id": "A", "label": "Alpha", "type": "Drivers"},
            {"id": "", "label": "no-id", "type": "Activities"},  # blank id
        ],
        connections=[],
    )
    result = parse_excel(f)
    assert not result.valid
    assert any("missing id" in e for e in result.errors)


def test_parse_excel_file_not_found(tmp_path):
    result = parse_excel(tmp_path / "nope.xlsx")
    assert not result.valid
    assert "not found" in result.errors[0].lower()
