"""P1a — DAPSI(W)R(M) link rules (spec §3.1-3.2, §3.5)."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from sespy.constants import DAPSIWRM_ADJACENCY_RULES, DAPSIWRM_ELEMENTS
from sespy.data_structure import Connection, Element, IsaData, Project, ProjectMetadata
from sespy.i18n import Translator, load_translations
from sespy.link_rules import (
    classify,
    default_polarity,
    log_off_rule_links,
    note_for,
    off_rule_message,
    rule_id,
    seed_polarity,
)

ROOT = Path(__file__).resolve().parents[1]
MPF = "Marine Processes & Functioning"

# Spec §3.1, one row per (from, to): (class, polarity, rule id).
SPEC_TABLE = [
    ("Drivers", "Activities", "canonical", "+", "1"),
    ("Drivers", "Pressures", "extension", "+", "ExUP"),
    ("Activities", "Pressures", "canonical", "+", "2"),
    ("Activities", "Activities", "extension", "+", "18"),
    ("Pressures", MPF, "canonical", "-", "3"),
    ("Pressures", "Pressures", "extension", "+", "17"),
    (MPF, "Ecosystem Services", "canonical", "+", "4"),
    (MPF, MPF, "extension", "+", "16"),
    ("Ecosystem Services", "Goods & Benefits", "canonical", "+", "5"),
    ("Goods & Benefits", "Drivers", "canonical", "+", "6-7"),
    ("Goods & Benefits", "Responses", "canonical", "+", "8"),
    ("Responses", "Drivers", "canonical", "-", "9"),
    ("Responses", "Activities", "canonical", "-", "10"),
    ("Responses", "Pressures", "canonical", "-", "11"),
    ("Responses", MPF, "canonical", "+", "12"),
    ("Responses", "Responses", "extension", "+", "14"),
]


@pytest.fixture(scope="module")
def tr() -> Translator:
    # A real translator: with no default registered, t() echoes the key, so
    # assertions would only prove the key name.
    return Translator(translations=load_translations(ROOT / "sespy" / "translations"))


@pytest.mark.parametrize("src,tgt,kind,pol,rid", SPEC_TABLE)
def test_every_spec_row(src, tgt, kind, pol, rid):
    assert classify(src, tgt) == kind
    assert default_polarity(src, tgt) == pol
    assert rule_id(src, tgt) == rid


def test_table_has_exactly_the_spec_rows():
    got = {(s, t.to_type) for s, r in DAPSIWRM_ADJACENCY_RULES.items()
           for t in (*r.targets, *r.extension_targets)}
    assert got == {(s, t) for s, t, *_ in SPEC_TABLE}
    assert set(DAPSIWRM_ADJACENCY_RULES) == set(DAPSIWRM_ELEMENTS)


def test_polarity_values_are_ascii():
    for r in DAPSIWRM_ADJACENCY_RULES.values():
        for t in (*r.targets, *r.extension_targets):
            assert t.polarity in ("+", "-")


def test_every_other_typed_pair_is_off_rule():
    listed = {(s, t) for s, t, *_ in SPEC_TABLE}
    for s in DAPSIWRM_ELEMENTS:
        for t in DAPSIWRM_ELEMENTS:
            if (s, t) not in listed:
                assert classify(s, t) == "off_rule", (s, t)
                assert rule_id(s, t) is None


def test_polarity_is_per_pair_not_per_source():
    assert default_polarity("Pressures", MPF) == "-"
    assert default_polarity("Pressures", "Pressures") == "+"
    assert default_polarity("Responses", MPF) == "+"
    assert default_polarity("Responses", "Responses") == "+"
    for t in ("Drivers", "Activities", "Pressures"):
        assert default_polarity("Responses", t) == "-"


@pytest.mark.parametrize("src,tgt", [("Pressures", "Drivers"),
                                     ("Responses", "Ecosystem Services"),
                                     ("Responses", "Goods & Benefits"),
                                     ("Drivers", "Goods & Benefits")])
def test_off_rule_pairs_seed_plus_like_r(src, tgt):
    assert classify(src, tgt) == "off_rule"
    assert default_polarity(src, tgt) == "+"


@pytest.mark.parametrize("src,tgt", [("", "Drivers"), ("Drivers", ""), ("", ""),
                                     ("Measures", "Drivers"),
                                     ("Goods & Benefits", "Measures"),
                                     ("Banana", "Drivers")])
def test_empty_or_unknown_types_are_untyped(src, tgt):
    assert classify(src, tgt) == "untyped"
    assert default_polarity(src, tgt) == "+"
    assert rule_id(src, tgt) is None


def test_no_measures_entry():
    assert "Measures" not in DAPSIWRM_ADJACENCY_RULES


# ---- seed_polarity / note_for (pure helpers behind the entry form) -------

D = Element("D001", "Tourism demand", "Drivers")
P = Element("P001", "Nutrients", "Pressures")
M = Element("MPF1", "Oxygen", MPF)
GB = Element("GB01", "Fish catch", "Goods & Benefits")
U = Element("T1", "Theme", "")


@pytest.mark.parametrize("src,tgt,want", [
    (None, M, None), (P, None, None), (None, None, None),
    (P, P, None),                       # same id
    (P, M, "-"),                        # canonical
    (D, GB, "+"),                       # off-rule seeds "+", as in R
    (U, GB, "+"), (D, U, "+"),          # untyped seeds "+"
])
def test_seed_polarity(src, tgt, want):
    assert seed_polarity(src, tgt) == want


@pytest.mark.parametrize("src,tgt", [
    (None, GB), (D, None), (D, D), (P, M), (D, U), (U, GB),
])
def test_note_for_is_none(src, tgt, tr):
    assert note_for(src, tgt, tr) is None


def test_note_for_off_rule_names_both_ends_with_raw_types(tr):
    msg = note_for(D, GB, tr)
    assert msg is not None and msg != "entry.off_rule_link"
    for s in ("Tourism demand", "Fish catch", "Drivers", "Goods & Benefits"):
        assert s in msg


def test_off_rule_message_uses_the_given_translator_language(tr):
    tr.set_language("de")
    try:
        msg = off_rule_message("a", "Drivers", "b", "Goods & Benefits", tr)
    finally:
        tr.set_language("en")
    assert msg == tr.translations["entry.off_rule_link"]["de"].format(
        source="a", target="b", source_type="Drivers",
        target_type="Goods & Benefits")


def test_off_rule_message_without_translator_falls_back_to_default_t(monkeypatch, tr):
    from sespy import i18n
    monkeypatch.setattr(i18n, "_default_translator", None)
    assert off_rule_message("a", "Drivers", "b", "Goods & Benefits",
                            None) == "entry.off_rule_link"      # no default: the key
    monkeypatch.setattr(i18n, "_default_translator", tr)
    assert off_rule_message("a", "Drivers", "b", "Goods & Benefits", None) == \
        off_rule_message("a", "Drivers", "b", "Goods & Benefits", tr)


def test_link_rules_imports_without_shiny():
    # A subprocess, so the shiny already imported by this test run cannot
    # mask an import of it.
    code = ("import sys, sespy.link_rules; "
            "sys.exit(1 if 'shiny' in sys.modules else 0)")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT)
    assert r.returncode == 0


# ---- log_off_rule_links ---------------------------------------------------

def _isa(*conns: Connection) -> IsaData:
    return IsaData([D, P, M, GB, U], list(conns))


def test_log_counts_and_warns_once(caplog):
    isa = _isa(Connection("D001", "GB01"), Connection("P001", "D001"),
               Connection("P001", "MPF1"))
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        n = log_off_rule_links(isa, context="test")
    assert n == 2
    recs = [r for r in caplog.records if r.name == "sespy.link_rules"]
    assert len(recs) == 1
    assert "D001->GB01" in recs[0].getMessage() and "2" in recs[0].getMessage()


def test_log_accepts_a_project(caplog):
    proj = Project(ProjectMetadata(), _isa(Connection("D001", "GB01")))
    assert log_off_rule_links(proj, context="test") == 1


def test_clean_or_untyped_project_logs_nothing(caplog):
    isa = _isa(Connection("P001", "MPF1"), Connection("T1", "GB01"))
    with caplog.at_level(logging.DEBUG, logger="sespy.link_rules"):
        assert log_off_rule_links(isa, context="test") == 0
    assert not [r for r in caplog.records if r.name == "sespy.link_rules"]


def test_validate_project_payload_logs_off_rule_links_once(caplog):
    from sespy.persistent_storage import validate_project_payload
    raw = {"metadata": {"name": "x"}, "isa_data": {
        "elements": [{"id": "D1", "label": "d", "type": "Drivers"},
                     {"id": "G1", "label": "g", "type": "Goods & Benefits"}],
        "connections": [{"source": "D1", "target": "G1"}]}}
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        res = validate_project_payload(raw)
    assert res.valid                    # accepted, never rejected
    recs = [r for r in caplog.records if r.name == "sespy.link_rules"]
    assert len(recs) == 1 and "D1->G1" in recs[0].getMessage()


def test_validate_project_payload_clean_project_is_silent(caplog):
    from sespy.persistent_storage import validate_project_payload
    raw = {"isa_data": {
        "elements": [{"id": "D1", "label": "d", "type": "Drivers"},
                     {"id": "A1", "label": "a", "type": "Activities"}],
        "connections": [{"source": "D1", "target": "A1"}]}}
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        assert validate_project_payload(raw).valid
    assert not [r for r in caplog.records if r.name == "sespy.link_rules"]


# ---- topology (commit 4: needs the 11-pair _CONN_TYPES) ------------------

def test_conn_types_set_equal_to_rule_table_canonical_targets():
    from sespy.data_structure import _CONN_TYPES, ELEMENT_TYPE_MAP
    got = {(ELEMENT_TYPE_MAP[f], ELEMENT_TYPE_MAP[t]) for f, t, _ in _CONN_TYPES}
    want = {(src, t.to_type) for src, r in DAPSIWRM_ADJACENCY_RULES.items()
            for t in r.targets}
    assert got == want


def test_rule_based_scorer_suggests_r_to_mpf():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[
        Element("R001", "Seagrass restoration", "Responses"),
        Element("MPF1", "Seagrass meadow extent", MPF),
    ])
    pairs = {(s.source, s.target) for s in suggest_connections(state)}
    assert ("R001", "MPF1") in pairs


def test_scorer_never_suggests_extension_pairs():
    from sespy.connection_scorer import suggest_connections
    from sespy.data_structure import WizardState
    state = WizardState(elements=[
        Element("R001", "Fishing quota", "Responses"),
        Element("R002", "Fishing licence", "Responses"),
        Element("P001", "Nutrient load", "Pressures"),
        Element("P002", "Nutrient runoff", "Pressures"),
    ])
    by_id = {e.id: e for e in state.elements}
    sugs = suggest_connections(state)
    assert sugs                       # R->P is canonical: something to check
    for s in sugs:
        assert classify(by_id[s.source].type, by_id[s.target].type) == "canonical"


def test_claude_backend_accepts_r_to_mpf():
    from sespy.claude_backend import _validate_and_coerce
    elements = [Element("R001", "Seagrass restoration", "Responses"),
                Element("MPF1", "Seagrass meadow extent", MPF)]
    sug = {"source": "R001", "target": "MPF1", "polarity": "+",
           "confidence": 0.7, "rationale": "restoration expands seagrass meadows"}
    out = _validate_and_coerce([sug], {"R001", "MPF1"}, elements)
    assert [(s.source, s.target) for s in out.suggestions] == [("R001", "MPF1")]
    assert out.drops_by_reason["invalid_pair"] == 0
