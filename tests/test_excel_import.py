"""Unit tests for the Excel import parser."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sespy.excel_import import _try_float, fcm_weight_to_fields, parse_excel


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


def test_fcm_weight_to_fields_magnitude_bins():
    assert fcm_weight_to_fields(0.2) == ("+", "weak")
    assert fcm_weight_to_fields(0.5) == ("+", "medium")
    assert fcm_weight_to_fields(0.7) == ("+", "strong")
    assert fcm_weight_to_fields(0.0) == ("+", "weak")


def test_fcm_weight_to_fields_sign():
    assert fcm_weight_to_fields(-0.2) == ("-", "weak")
    assert fcm_weight_to_fields(-0.5) == ("-", "medium")
    assert fcm_weight_to_fields(-0.7) == ("-", "strong")


def test_fcm_weight_to_fields_clamps_out_of_range():
    assert fcm_weight_to_fields(1.5) == ("+", "strong")
    assert fcm_weight_to_fields(-1.5) == ("-", "strong")


def test_fcm_weight_to_fields_boundaries():
    assert fcm_weight_to_fields(1/3) == ("+", "weak")     # inclusive upper
    assert fcm_weight_to_fields(0.34) == ("+", "medium")
    assert fcm_weight_to_fields(2/3) == ("+", "medium")   # inclusive upper
    assert fcm_weight_to_fields(0.7) == ("+", "strong")


def test_try_float_detects_numbers_only():
    assert _try_float(0.5) == 0.5
    assert _try_float(-0.7) == -0.7
    assert _try_float("0.5") == 0.5
    assert _try_float("") is None
    assert _try_float("strong") is None
    assert _try_float(None) is None
    assert _try_float(float("nan")) is None
    assert _try_float(float("inf")) is None


def test_parse_excel_fcm_numeric_weights(tmp_path):
    # All source/target ids must exist in Elements or validation fails on a
    # dangling ref BEFORE the FCM mapping is reached.
    f = _write_workbook(
        tmp_path,
        elements=VALID_ELEMENTS,  # D001, A001, P001
        connections=[
            {"source": "D001", "target": "A001", "weight": -0.7},   # FCM: -/strong
            {"source": "A001", "target": "P001", "weight": 0.2},    # FCM: +/weak
            {"source": "D001", "target": "P001",
             "polarity": "+", "strength": "medium"},                # categorical: unchanged
            {"source": "P001", "target": "A001",
             "weight": 0.5, "polarity": "-"},                       # numeric weight wins → +
        ],
    )
    result = parse_excel(f)
    assert result.valid, result.errors
    conns = {(c.source, c.target): c for c in result.project.isa_data.connections}

    fcm_neg = conns[("D001", "A001")]
    assert fcm_neg.polarity == "-" and fcm_neg.strength == "strong"

    fcm_pos = conns[("A001", "P001")]
    assert fcm_pos.polarity == "+" and fcm_pos.strength == "weak"

    cat = conns[("D001", "P001")]
    assert cat.polarity == "+" and cat.strength == "medium"

    wins = conns[("P001", "A001")]
    assert wins.polarity == "+" and wins.strength == "medium"  # weight sign (+0.5) overrides polarity "-"

    # downstream sanity: an FCM strong lands as a real strength rank, not a degraded default.
    from sespy import network
    assert network._STRENGTH_RANK[fcm_neg.strength] == 3


def test_parse_excel_categorical_weight_back_compat(tmp_path):
    # A text "weight" cell stays categorical (regression guard for KUMU sheets).
    f = _write_workbook(
        tmp_path,
        elements=VALID_ELEMENTS,
        connections=[{"source": "D001", "target": "A001",
                      "Polarity": "-", "Weight": "weak"}],
    )
    result = parse_excel(f)
    assert result.valid, result.errors
    c = result.project.isa_data.connections[0]
    assert c.polarity == "-" and c.strength == "weak"


# ---------------------------------------------------------------------------
# P1a (spec §8): connection description, Kumu Label polarity, type aliases
# ---------------------------------------------------------------------------

TWO = [{"id": "D001", "label": "Tourism demand", "type": "Drivers"},
       {"id": "A001", "label": "Boating", "type": "Activities"}]


def _one_conn(tmp_path, conn: dict, elements=TWO):
    res = parse_excel(_write_workbook(tmp_path, elements=elements, connections=[conn]))
    assert res.valid, res.errors
    return res.project.isa_data.connections[0]


@pytest.mark.parametrize("col", ["description", "Description", "rationale", "Rationale"])
def test_connection_description_columns(tmp_path, col):
    c = _one_conn(tmp_path, {"source": "D001", "target": "A001", col: "demand drives boating"})
    assert c.description == "demand drives boating"


def test_connection_description_empty_or_numeric_cell(tmp_path):
    f = _write_workbook(tmp_path, elements=TWO, connections=[
        {"source": "D001", "target": "A001", "description": None},
        {"source": "A001", "target": "D001", "description": 42}])
    res = parse_excel(f)
    assert res.valid, res.errors
    # pandas reads a column holding NaN and 42 as float: str() gives "42.0".
    assert [c.description for c in res.project.isa_data.connections] == ["", "42.0"]


BASE = {"source": "D001", "target": "A001", "strength": "medium"}


@pytest.mark.parametrize("conn,want", [
    ({**BASE, "polarity": None, "Label": "-"}, "-"),        # blank polarity cell
    ({**BASE, "polarity": "   ", "Label": "-"}, "-"),       # whitespace-only polarity cell
    ({**BASE, "Label": " -"}, "+"),                          # Label is not stripped (as R)
    ({**BASE, "Label": "\u2212"}, "-"),                      # U+2212 (SESPy divergence)
    ({**BASE, "label": "--"}, "-"),                          # lowercase column, starts with -
    ({**BASE, "Label": "increases"}, "+"),
    ({**BASE}, "+"),                                         # nothing at all
    ({**BASE, "polarity": "+", "Label": "-"}, "+"),         # polarity beats Label
    ({**BASE, "polarity": " -"}, "-"),                       # polarity cell is stripped
    ({**BASE, "polarity": "  ", "Sign": "-", "Label": "+"}, "-"),  # next alias column first
    ({"source": "D001", "target": "A001", "strength": -0.8, "Label": "+"}, "-"),  # weight wins
])
def test_polarity_precedence_with_kumu_label(tmp_path, conn, want):
    assert _one_conn(tmp_path, conn).polarity == want


@pytest.mark.parametrize("cell,want", [
    ("Driver", "Drivers"), ("driver", "Drivers"), ("  Activity ", "Activities"),
    ("Pressure", "Pressures"),
    ("Marine Process and Function", "Marine Processes & Functioning"),
    ("Marine Process and Functioning", "Marine Processes & Functioning"),
    ("State", "Marine Processes & Functioning"),
    ("state change", "Marine Processes & Functioning"),
    ("Ecosystem Service", "Ecosystem Services"), ("IMPACT", "Ecosystem Services"),
    ("Good and Benefit", "Goods & Benefits"), ("Goods and Benefits", "Goods & Benefits"),
    ("Welfare", "Goods & Benefits"), ("Response", "Responses"),
    ("drivers", "Drivers"), ("goods & benefits", "Goods & Benefits"),
])
def test_element_type_aliases(tmp_path, cell, want):
    els = [{"id": "X1", "label": "x", "type": cell},
           {"id": "D001", "label": "d", "type": "Drivers"}]
    res = parse_excel(_write_workbook(tmp_path, elements=els, connections=[
        {"source": "X1", "target": "D001"}]))
    assert res.valid, res.errors
    x = res.project.isa_data.elements[0]
    assert x.type == want and x.r_extra == {}


def test_measure_becomes_response_with_r_kind(tmp_path):
    els = [{"id": "M1", "label": "Gear ban", "type": "Measure"},
           {"id": "R1", "label": "Quota", "type": "response"}]
    res = parse_excel(_write_workbook(tmp_path, elements=els, connections=[
        {"source": "M1", "target": "R1"}]))
    assert res.valid, res.errors
    m, r = res.project.isa_data.elements
    assert (m.type, m.r_extra) == ("Responses", {"r_kind": "measure"})
    assert (r.type, r.r_extra) == ("Responses", {})


def test_unknown_type_still_rejected(tmp_path):
    els = [{"id": "X1", "label": "x", "type": "Banana"},
           {"id": "D001", "label": "d", "type": "Drivers"}]
    res = parse_excel(_write_workbook(tmp_path, elements=els, connections=[
        {"source": "X1", "target": "D001"}]))
    assert not res.valid
    assert any("Banana" in e for e in res.errors)


def _elements_with(tmp_path, extra_cols: dict) -> list:
    els = [{"ID": "S1", "Name": "Coral", "Type": "Marine Processes & Functioning", **extra_cols},
           {"ID": "D1", "Name": "Demand", "Type": "Drivers"}]
    res = parse_excel(_write_workbook(tmp_path, elements=els, connections=[
        {"source": "D1", "target": "S1"}]))
    assert res.valid, res.errors
    return res.project.isa_data.elements


def test_excel_indicator_column_fills_the_field_not_description(tmp_path):
    # P1b spec §5(c): from 1.15.0 "Indicator" no longer feeds the description.
    s1, d1 = _elements_with(tmp_path, {"Indicator": "Coral cover", "Indicator_Unit": "%"})
    assert s1.description == ""
    assert (s1.indicator, s1.indicator_unit) == ("Coral cover", "%")
    assert d1.indicator == "" and d1.description == ""


@pytest.mark.parametrize("cols", [
    {"Indicator": "i", "Indicator_Unit": "u", "Data_Source": "s", "Registry_Id": "r",
     "Registry_Version": "v", "Policy_Target": "eu_nrr"},
    {"indicator": "i", "indicator_unit": "u", "data_source": "s", "registry_id": "r",
     "registry_version": "v", "policy_target": "eu_nrr"},
    # spec §5(c): any case
    {"Indicator": "i", "indicator_unit": "u", "DATA_SOURCE": "s", "Registry_id": "r",
     "REGISTRY_VERSION": "v", "Policy_target": "eu_nrr"},
])
def test_excel_reads_all_six_indicator_columns(tmp_path, cols):
    from sespy.excel_import import ELEMENT_INDICATOR_COLS
    assert ELEMENT_INDICATOR_COLS == {
        "indicator": "Indicator", "indicator_unit": "Indicator_Unit", "data_source": "Data_Source",
        "registry_id": "Registry_Id", "registry_version": "Registry_Version",
        "policy_target": "Policy_Target"}
    s1 = _elements_with(tmp_path, cols)[0]
    assert (s1.indicator, s1.indicator_unit, s1.data_source, s1.registry_id,
            s1.registry_version, s1.policy_target) == ("i", "u", "s", "r", "v", "eu_nrr")


def test_excel_numeric_registry_version(tmp_path):
    # A numeric column with a blank reads back as float (2.0, NaN): indicator_text gives "2", "".
    s1, d1 = _elements_with(tmp_path, {"Registry_Version": 2})
    assert (s1.registry_version, d1.registry_version) == ("2", "")


@pytest.mark.parametrize("col", ["description", "Description"])
def test_excel_description_still_read(tmp_path, col):
    s1 = _elements_with(tmp_path, {col: "Live coral", "Indicator": "Coral cover"})[0]
    assert (s1.description, s1.indicator) == ("Live coral", "Coral cover")


def test_off_rule_link_imports_with_a_logged_warning(tmp_path, caplog):
    import logging
    els = [{"id": "D001", "label": "d", "type": "Drivers"},
           {"id": "G1", "label": "g", "type": "Goods & Benefits"}]
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        res = parse_excel(_write_workbook(tmp_path, elements=els, connections=[
            {"source": "D001", "target": "G1"}]))
    assert res.valid
    assert any("D001->G1" in r.getMessage() for r in caplog.records
               if r.name == "sespy.link_rules")
