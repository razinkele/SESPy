"""K1 Task 6: R-exact knowledge-base lookup and context suggestions.

Every parity test compares against values captured from R v1.35.6 itself
(``tests/parity/r_fixtures/k1``) or, for edge cases the fixtures do not
cover, against literal R output recorded with Rscript at v1.35.6 (quoted in
the test). Nothing here "fixes" an R quirk.
"""
from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "parity"))

from k1_fixtures import load_k1_fixture  # noqa: E402

from sespy import kb_suggestions as ks  # noqa: E402
from sespy.r_kb import VENDORED  # noqa: E402

KB = VENDORED.kb()
GOV = VENDORED.governance()
CATEGORIES = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"]


def _lookup_row(sea, eco):
    m = ks.find_context(KB, sea, eco)
    if m is None:
        return {"key": None, "match": "fallback"}
    key, ctx, match = m
    assert ctx is KB["contexts"][key]
    return {"key": key, "match": match}


# ---------------------------------------------------------------------------
# Fixture-driven parity
# ---------------------------------------------------------------------------

def test_lookup_matches_r():
    rows = load_k1_fixture("lookup")["choices"]
    assert len(rows) == 69
    bad = [(r, _lookup_row(r["sea"], r["ecosystem"])) for r in rows
           if _lookup_row(r["sea"], r["ecosystem"]) != {"key": r["key"], "match": r["match"]}]
    assert not bad, f"{len(bad)} lookup mismatches, e.g. {bad[:5]}"


def test_free_text_ecosystems_match_r():
    """Review Focus 2: R-imported free-text types go through R's regex cascade."""
    rows = load_k1_fixture("lookup")["free_text"]
    assert [r["ecosystem"] for r in rows] == [
        "Coastal lagoon and delta", "Posidonia meadows", "Schären archipelago"]
    for r in rows:
        assert _lookup_row(r["sea"], r["ecosystem"]) == {"key": r["key"], "match": r["match"]}
    # and the R values themselves, so a fixture regression is visible here too
    assert [(r["key"], r["match"]) for r in rows] == [
        ("baltic_lagoon", "exact"), ("mediterranean_seagrass", "exact"),
        ("baltic_rocky_coast", "exact")]


def test_suggestions_grid_matches_r():
    """Every one of the 3,864 R cells: names AND sources, in order."""
    grid = load_k1_fixture("suggestions_grid")
    lists = grid["sources"]
    cells = grid["cells"]
    assert len(cells) == 3864
    compared = 0
    mismatches = []
    by_kind = Counter()
    for c in cells:
        expected = [tuple(p) for p in lists[c["items"]]]
        got = ks.get_context_suggestions(KB, GOV, c["category"], c["sea"], c["ecosystem"],
                                         c["issues"], c["countries"])
        compared += 1
        if got != expected:
            names_ok = [n for n, _ in got] == [n for n, _ in expected]
            by_kind[(c["category"], "sources" if names_ok else "names")] += 1
            mismatches.append((c, got, expected))
    assert compared == 3864
    if mismatches:
        c, got, exp = mismatches[0]
        pytest.fail(f"{len(mismatches)}/{compared} grid cells differ from R; by kind {dict(by_kind)}; "
                    f"first: {c}\n got={got}\n exp={exp}")


def test_habitat_specific_matches_r():
    rows = load_k1_fixture("habitat_specific")
    assert len(rows) == 483
    bad = [r for r in rows
           if ks.get_habitat_specific_suggestions(r["category"], r["sea"], r["ecosystem"]) != r["items"]]
    assert not bad, f"{len(bad)} habitat rows differ, e.g. {bad[:3]}"


def test_countries_for_sea_matches_r():
    data = load_k1_fixture("countries")
    assert len(data) == 11
    for sea, expected in data.items():
        assert ks.countries_for_sea(GOV, sea) == expected, sea


# ---------------------------------------------------------------------------
# Named quirks and Review Focus cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sea,eco,expected", [
    ("pacific", "Coral reef", ("pacific_island_atoll", "sea_only")),
    ("indian", "Island", ("indian_ocean_coral_reef", "sea_only")),
    ("atlantic", "Coastal upwelling", ("atlantic_open_coast", "exact")),
    ("irish_sea", "Open coast", None),
    ("north_sea", "Sandy beach", ("north_sea_offshore", "sea_only")),
])
def test_decision2_quirks_named(sea, eco, expected):
    m = ks.find_context(KB, sea, eco)
    assert (None if m is None else (m[0], m[2])) == expected


# R v1.35.6 (Rscript): get_context_suggestions(cat, "atlantis"|"", "Open coast",
# character(0), NULL, TRUE) -- generic_fallback elements, labelled knowledge_db.
_R_GENERIC = {
    "drivers": ["Climate change adaptation and resilience needs", "Food security from marine resources",
                "Economic development pressure", "Coastal protection needs",
                "Recreational and tourism demand"],
    "activities": ["Commercial fishing", "Coastal development", "Aquaculture",
                   "Tourism and recreation", "Shipping and transport"],
    "states": ["Fish stock biomass", "Water quality indicators", "Habitat condition",
               "Biodiversity levels"],
    "responses": ["Marine Protected Areas", "Fishing regulations", "Pollution control measures",
                  "Habitat restoration programmes"],
}


@pytest.mark.parametrize("sea", ["atlantis", ""])
def test_unknown_sea_slug_no_exception(sea):
    """Review Focus 1: no context, no countries_by_sea entry -> generic fallback, no error."""
    assert ks.find_context(KB, sea, "Open coast") is None
    assert ks.countries_for_sea(GOV, sea) == []
    assert ks.get_context_connections(KB, sea, "Open coast") == []
    for cat, names in _R_GENERIC.items():
        got = ks.get_context_suggestions(KB, GOV, cat, sea, "Open coast", [], [])
        assert got == [(n, "knowledge_db") for n in names], cat
    for cat in CATEGORIES:
        ks.get_context_suggestions(KB, GOV, cat, sea, "Open coast", ["Overfishing"], ["SE", "XX"])


def test_legacy_macaronesia_resolves_like_r():
    m = ks.find_context(KB, "macaronesia", "Open coast")
    assert (m[0], m[2]) == ("macaronesia_open_coast", "exact")
    m = ks.find_context(KB, "macaronesia", "Coral reef")
    assert (m[0], m[2]) == ("macaronesia_island", "sea_only")
    # R v1.35.6: get_context_suggestions("impacts", "macaronesia", "Coral reef",
    #            character(0), c("PT","ES"), TRUE)
    assert ks.get_context_suggestions(KB, GOV, "impacts", "macaronesia", "Coral reef", [], ["PT", "ES"]) == [
        ("Reduced artisanal fish catches", "knowledge_db"),
        ("Degraded diving and snorkeling site quality", "knowledge_db"),
        ("Loss of endemic marine species", "knowledge_db"),
        ("Altered nearshore food web structure", "knowledge_db"),
        ("Decline in coastal carbon sequestration", "knowledge_db"),
        ("Tourism revenue loss", "ecosystem"),
        ("Coastal protection loss", "ecosystem"),
        ("Fishery collapse", "ecosystem"),
    ]


def test_none_sea_or_ecosystem_like_r():
    assert ks.build_context_key(None, "Open coast") is None
    assert ks.build_context_key("baltic", None) is None
    assert ks.find_context(KB, None, "Open coast") is None
    assert ks.find_context(KB, "", None) is None
    assert ks.find_context(KB, None, None) is None
    m = ks.find_context(KB, "baltic", None)
    assert (m[0], m[2]) == ("baltic_lagoon", "sea_only")
    # R trims/lower-cases the sea for the lookup only
    m = ks.find_context(KB, " Baltic ", "Coastal lagoon")
    assert (m[0], m[2]) == ("baltic_lagoon", "exact")
    # R v1.35.6: get_context_suggestions("states", NULL, NULL, character(0), NULL, TRUE)
    assert ks.get_context_suggestions(KB, GOV, "states", None, None, [], []) == [
        (n, "knowledge_db") for n in _R_GENERIC["states"]]
    assert ks.get_habitat_specific_suggestions("states", None, "Estuary") == []
    assert ks.get_habitat_specific_suggestions("states", "baltic", None) == []


def test_raw_sea_used_for_regional_lists_like_r():
    # R v1.35.6: get_context_suggestions("pressures", "Baltic", "Coastal lagoon", ...)
    # resolves the KB (lower-cased) but skips the case-sensitive regional list.
    assert ks.get_context_suggestions(KB, GOV, "pressures", "Baltic", "Coastal lagoon", [], []) == [
        ("Nutrient enrichment from agricultural sources", "knowledge_db"),
        ("Cyanobacteria bloom formation", "knowledge_db"),
        ("Fishing mortality on pike-perch stock", "knowledge_db"),
        ("Reduced water exchange with open sea", "knowledge_db"),
        ("Sedimentation and lagoon infilling", "knowledge_db"),
        ("Microplastic accumulation in sediments", "knowledge_db"),
    ]


def test_main_issue_does_not_change_output():
    """R ignores main_issue from v1.35.0 (the grid fixture's two issue sets agree)."""
    for sea, eco in [("baltic", "Coastal lagoon"), ("irish_sea", "Estuary"), ("caribbean", "Coral reef")]:
        for cat in CATEGORIES:
            base = ks.get_context_suggestions(KB, GOV, cat, sea, eco, [], ["SE"])
            for issues in (["Overfishing"], ["Eutrophication", "Marine litter", "Tourism", "Climate change"]):
                assert ks.get_context_suggestions(KB, GOV, cat, sea, eco, issues, ["SE"]) == base


def test_null_relevance_is_half():
    kb = {"contexts": {"x_lagoon": {"drivers": [
        {"name": "A", "relevance": 0.4},
        {"name": "B", "relevance": None},
        {"name": "C"},
        {"name": "D", "relevance": 0.9},
        {"name": None, "relevance": 1.0},
        {"name": "E", "relevance": 0.5},
    ]}}}
    # stable descending: 0.9, then the 0.5 ties in file order
    assert ks.get_context_elements(kb, "x", "Coastal lagoon", "drivers") == ["D", "B", "C", "E", "A"]
    assert ks.get_context_elements(kb, "x", "Coastal lagoon", "drivers", min_relevance=0.5) == ["D", "B", "C", "E"]
    assert ks.get_context_elements(kb, "x", "Coastal lagoon", "drivers", min_relevance=0.51) == ["D"]


def test_vendored_kb_missing_relevance_element_is_half():
    """The vendored KB has an element with no relevance at all; it counts as 0.5."""
    found = []
    for key, ctx in KB["contexts"].items():
        for cat in CATEGORIES:
            for e in ctx.get(cat) or []:
                if e.get("relevance") is None:
                    found.append((key, cat, e["name"]))
    assert found, "expected an element without relevance in the vendored KB"
    for key, cat, name in found:
        ctx = copy.deepcopy(KB["contexts"][key])
        kb = {"contexts": {"x_lagoon": ctx}}
        assert name in ks.get_context_elements(kb, "x", "Lagoon", cat, 0.5)
        assert name not in ks.get_context_elements(kb, "x", "Lagoon", cat, 0.51)


def test_generic_fallback_when_no_context():
    kb = {"contexts": {"y_lagoon": {}}, "generic_fallback": {"states": [{"name": "G", "relevance": 0.7}]}}
    assert ks.get_context_elements(kb, "x", "Coastal lagoon", "states") == ["G"]
    assert ks.get_context_elements(kb, "x", "Coastal lagoon", "drivers") == []
    assert ks.get_context_elements({"contexts": {}}, "x", "Lagoon", "states") == []
    assert ks.get_context_elements(None, "x", "Lagoon", "states") == []


def test_context_connections():
    assert len(ks.get_context_connections(KB, "baltic", "Coastal lagoon")) == len(
        KB["contexts"]["baltic_lagoon"]["connections"])
    assert ks.get_context_connections(KB, "baltic", "Coastal lagoon") == KB["contexts"]["baltic_lagoon"]["connections"]
    # no generic fallback for connections
    assert ks.get_context_connections(KB, "irish_sea", "Open coast") == []
    assert ks.get_context_connections(None, "baltic", "Lagoon") == []


def test_habitat_branch_used_when_kb_empty():
    """The grid never reaches the habitat fallback (generic_fallback always feeds it)."""
    # R v1.35.6 (Rscript) with .ses_kb_env$db <- list(contexts = list(
    #   baltic_estuary = list(activities = list()))), no generic_fallback.
    kb = {"contexts": {"baltic_estuary": {"activities": []}}}
    assert ks.get_context_suggestions(kb, GOV, "activities", "baltic", "Estuary", [], []) == [
        ("Commercial fishing", "generic"), ("Aquaculture", "generic"), ("Shipping", "generic"),
        ("Coastal development", "generic"), ("Environmental monitoring", "generic"),
        ("Wind farm development", "regional"), ("Dredging", "regional"),
        ("Oil and gas extraction", "regional"), ("Trawl fishing", "regional"),
        ("Marine aggregate extraction", "regional"),
        ("Industrial discharge", "habitat"), ("Commercial trawling", "habitat"),
        ("Recreational boating", "habitat"), ("Coastal flood defense construction", "habitat"),
        ("Mussel and oyster harvesting", "habitat"), ("Shellfish water quality monitoring", "habitat"),
    ]
    assert ks.get_context_suggestions(kb, GOV, "states", "caribbean", "Mangrove", [], []) == [
        ("Water quality decline", "generic"), ("Biodiversity loss", "generic"),
        ("Habitat degradation", "generic"), ("Species population changes", "generic"),
        ("Oxygen depletion", "generic"), ("Coral bleaching", "regional"),
        ("Seagrass loss", "regional"), ("Reef degradation", "regional"),
        ("Mangrove forest area loss", "ecosystem"), ("Carbon storage reduction", "ecosystem"),
        ("Nursery habitat loss", "ecosystem"), ("Mangrove forest extent", "habitat"),
        ("Root system integrity", "habitat"), ("Sediment trapping capacity", "habitat"),
        ("Nursery habitat quality", "habitat"), ("Carbon burial rates", "habitat"),
    ]
    assert ks.get_context_suggestions(kb, GOV, "drivers", "north_sea", "Offshore waters", [], []) == [
        (n, "generic") for n in ["Food security", "Economic development", "Recreation and tourism",
                                 "Energy needs", "Coastal protection", "Cultural heritage",
                                 "Employment", "Trade and commerce"]
    ] + [(n, "habitat") for n in ["Wind energy demand", "Oil and gas extraction",
                                  "Sand and gravel extraction", "Cable and pipeline corridors"]]
    # KB with no contexts at all is "unavailable" in R: generic_fallback is ignored too
    kb2 = {"contexts": {}, "generic_fallback": {"activities": [{"name": "Z", "relevance": 1}]}}
    assert "Z" not in dict(ks.get_context_suggestions(kb2, GOV, "activities", "baltic", "Estuary", [], []))


# R v1.35.6 (Rscript) results for get_habitat_specific_suggestions
@pytest.mark.parametrize("cat,sea,eco,expected", [
    ("activities", "arctic", "Fjord", ["Arctic aquaculture", "Cruise tourism", "Mining discharge",
                                       "Small-scale fishing", "Fjord monitoring"]),
    ("pressures", "black_sea", "Estuary", ["Eutrophication from Danube inputs", "Hydrogen sulfide zones",
                                           "Invasive jellyfish (Mnemiopsis)", "Overfishing of anchovy and sprat"]),
    ("drivers", "", "Estuary", ["Urban expansion", "Flood management", "Agricultural demand", "Port development"]),
    ("responses", "atlantis", "Deep sea mud flat", []),
    ("welfare", "baltic", "Kelp forest", []),
])
def test_habitat_specific_edge_cases_like_r(cat, sea, eco, expected):
    assert ks.get_habitat_specific_suggestions(cat, sea, eco) == expected


# R v1.35.6 (Rscript) results for deduplicate_suggestions
@pytest.mark.parametrize("items,protected,expected", [
    (["Trawl fishing", "Trawling fishing gear", "fishing"], ["Trawling fishing gear"], ["Trawling fishing gear"]),
    (["Seagrass loss", "seagrass losses"], ["seagrass loss"], ["Seagrass loss", "seagrass losses"]),
    (["Seagrass loss", "Seagrass losses"], ["Seagrass loss", "Seagrass losses"], ["Seagrass loss", "Seagrass losses"]),
    (["Fish", "Fish stock decline", "Fishing"], ["Fishing"], ["Fishing"]),
    ([" Fish  stock", "fish stocks ", "a b c d e", "a b c d x"], [], ["fish stocks ", "a b c d e"]),
    (["Fish stock", "Fish stocks"], ["fish stocks"], ["Fish stock"]),          # case-sensitive protection
    (["Fish stock", "Fish stocks"], ["Fish stocks"], ["Fish stocks"]),
    (["Fish stock decline", "Fish stocks"], ["Fish stock decline"], ["Fish stock decline"]),
    (["Fish stocks", "Fish stock decline"], ["Fish stock decline"], ["Fish stock decline"]),
    (["Fish stocks", "Fish stock decline"], [], ["Fish stocks"]),
    (["Landings", "Lands"], [], ["Landings", "Lands"]),             # single-pass strip: landing != land
    (["Fishing fleets", "fish fleet"], [], ["Fishing fleets"]),
    ([], [], []),
    (["only"], [], ["only"]),
])
def test_deduplicate_like_r(items, protected, expected):
    assert ks.deduplicate_suggestions(items, protected) == expected


def test_governance_and_socioeconomic():
    # unmapped category -> [] (R: .map_category error -> hardcoded fallback -> character(0))
    assert ks.get_governance_elements(GOV, ["SE"], "activities") == []
    assert ks.get_socioeconomic_elements(GOV, ["SE"], "pressures") == []
    assert ks.get_socioeconomic_elements(GOV, ["SE"], "responses") == []
    assert ks.get_governance_elements(GOV, [], "responses") == []
    assert ks.get_governance_elements(GOV, ["XX"], "responses") == []
    # codes are trimmed and upper-cased (R: get_governance_elements(c(" se", "fi"), "responses"))
    got = ks.get_governance_elements(GOV, [" se", "fi"], "responses")
    assert got == ks.get_governance_elements(GOV, ["SE", "FI"], "responses")
    assert got[0] == "Marine Strategy Framework Directive (MSFD) implementation"
    assert got[-1] == "Nordic knowledge exchange on ecosystem-based management"
    assert len(got) == 28 and len(set(got)) == 28
    assert ks.get_governance_elements(None, ["SE"], "responses") == []


def test_hardcoded_governance_when_gov_unavailable():
    """R falls back to the hardcoded tables when the governance DB is not loaded.

    Expected values: R v1.35.6 (Rscript) with .country_gov_env$loaded <- FALSE.
    """
    assert ks.get_context_suggestions(KB, None, "responses", "baltic", "Coastal lagoon", [], ["SE"]) == [
        ("HELCOM nutrient reduction targets for lagoon catchments", "knowledge_db"),
        ("Pike-perch minimum landing size regulations", "knowledge_db"),
        ("Agricultural buffer zone requirements", "knowledge_db"),
        ("Reed bed restoration programmes", "knowledge_db"),
        ("Natura 2000 lagoon habitat protection", "knowledge_db"),
        ("Oxygen restoration", "regional"), ("Fish stock recovery plans", "regional"),
        ("EU Marine Strategy Framework Directive (MSFD)", "governance"),
        ("EU Common Fisheries Policy (CFP)", "governance"),
        ("EU Water Framework Directive", "governance"), ("Natura 2000 marine sites", "governance"),
        ("EU Biodiversity Strategy 2030", "governance"), ("EU Blue Economy Strategy", "governance"),
        ("HELCOM Baltic Sea Action Plan", "governance"), ("OSPAR Convention", "governance"),
        ("Arctic Council frameworks", "governance"),
    ]
    assert ks.get_context_suggestions(KB, {}, "drivers", "baltic", "Coastal lagoon", [], ["NO"]) == [
        ("Agricultural production demand in catchment", "knowledge_db"),
        ("Food security from local fisheries", "knowledge_db"),
        ("Recreational demand for nature tourism", "knowledge_db"),
        ("Cultural heritage of traditional fishing", "knowledge_db"),
        ("Urban wastewater management needs", "knowledge_db"),
        ("Industrial fisheries demand", "socioeconomic"), ("Seafood export economy", "socioeconomic"),
        ("Fish processing industry", "socioeconomic"), ("Maritime transport demand", "socioeconomic"),
        ("Port infrastructure development", "socioeconomic"),
    ]
    # hardcoded tables match raw codes: "jm" is not JM
    assert ks.get_context_suggestions(KB, None, "welfare", "caribbean", "Coral reef", [], ["BZ", "jm"]) == [
        ("Tourism-dependent community livelihoods", "knowledge_db"),
        ("Food security from reef protein sources", "knowledge_db"),
        ("Coastal property protection value", "knowledge_db"),
        ("Cultural and spiritual connection to reefs", "knowledge_db"),
        ("Tourism revenue vulnerability", "socioeconomic"),
        ("Coastal community displacement risk", "socioeconomic"),
        ("Food security from marine resources", "socioeconomic"),
    ]


def test_does_not_mutate_inputs():
    kb = copy.deepcopy(KB)
    gov = copy.deepcopy(GOV)
    countries = ["se", "FI"]
    for cat in CATEGORIES:
        ks.get_context_suggestions(kb, gov, cat, "baltic", "Coastal lagoon", ["Overfishing"], countries)
    assert kb == KB and gov == GOV and countries == ["se", "FI"]
