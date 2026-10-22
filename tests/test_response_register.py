"""P1b — R response-register schema port (spec §4.2; Task 6).

Expected values are derived by hand from the pinned R v1.33.0 sources
(tests/parity/r_source/{constants.R,response_measures_schema.R}) and R's
testthat cases at 4017feb (tests/testthat/test-response-measures-schema.R),
never by running R. English texts come from the vendored translations
(sespy/translations/modules/*.json).
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from sespy.response_register import (
    EBM_MANAGEMENT_MEASURES,
    EBM_POLICY_INSTRUMENTS,
    EFFECTIVENESS_LEVELS,
    FEASIBILITY_LEVELS,
    IMPACT_COLUMNS,
    IMPACT_PROBLEM_TYPES,
    IMPACT_STRENGTHS,
    KIND_CODES,
    MILESTONE_COLUMNS,
    MILESTONE_STATUSES,
    RM_DISPLAY_COLUMNS,
    RM_REGISTER_COLUMNS,
    RM_STATUS_CODES,
    RM_TARGET_CODES,
    RM_TYPE_CODES,
    TENET_CODES,
    TIMEFRAMES,
    display_value,
    ebm_code_choices,
    ebm_picker_label,
    ef_points,
    normalize_impacts,
    normalize_measures,
    normalize_milestones,
    priority_rows,
    reverse_label_map,
    suggest_target,
)

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "sespy" / "translations" / "modules"
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")


def _vendored_all() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for p in sorted(VENDORED.glob("*.json")):
        out.update(json.loads(p.read_text(encoding="utf-8"))["translation"])
    return out


TRANS = _vendored_all()


def tr(key: str) -> str:
    """English translator over the vendored files (returns the key on a miss,
    as sespy.i18n.Translator.t does)."""
    return TRANS.get(key, {}).get("en") or key


def _rm(key: str, lang: str = "en") -> str:
    return TRANS[f"modules.response.measures.{key}"][lang]


# ---- constants ----------------------------------------------------------------

def test_columns():
    assert len(RM_REGISTER_COLUMNS) == 34 and RM_REGISTER_COLUMNS[0] == "ID"
    assert RM_REGISTER_COLUMNS[-1] == "TenetSource" and RM_REGISTER_COLUMNS[9] == "Cost"
    assert len(RM_DISPLAY_COLUMNS) == 15 and set(RM_DISPLAY_COLUMNS) <= set(RM_REGISTER_COLUMNS)
    assert len(TENET_CODES) == 11
    # data_structure.R:292-305
    assert IMPACT_COLUMNS == ("ResponseID", "ProblemType", "ProblemElementID",
                              "ImpactStrength", "Timeframe")
    assert MILESTONE_COLUMNS == ("ResponseID", "Milestone", "TargetDate", "Status", "Notes")


def test_ui_choice_lists():
    # response_module.R:91-102, 134-137, 207-224, 340 (v1.33.0)
    assert KIND_CODES == ("instrument", "measure")
    assert EFFECTIVENESS_LEVELS == ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
    assert FEASIBILITY_LEVELS == ("HIGH", "MEDIUM", "LOW")
    assert IMPACT_PROBLEM_TYPES == ("specific_pressure", "specific_activity",
                                    "specific_driver", "system_wide_issue")
    assert IMPACT_STRENGTHS == ("strong", "moderate", "weak")
    assert TIMEFRAMES == ("immediate", "short_term_1_3y", "medium_term_3_10y", "long_term_10y")
    assert MILESTONE_STATUSES == ("pending", "in_progress", "completed", "delayed")


def test_every_ui_code_has_a_label_in_all_languages():
    # The UI choice lists have no R fixture; their label keys must exist.
    keys = [f"modules.response.measures.{c.lower()}"
            for c in (*EFFECTIVENESS_LEVELS, *FEASIBILITY_LEVELS, *IMPACT_PROBLEM_TYPES,
                      *IMPACT_STRENGTHS, *TIMEFRAMES, *MILESTONE_STATUSES)]
    keys += [f"modules.response.governance.kind.{c}" for c in KIND_CODES]
    keys += [f"modules.response.measures.{s}" for s in (
        *RM_TYPE_CODES.values(), *RM_TARGET_CODES.values(), *RM_STATUS_CODES.values())]
    for k in keys:
        assert k in TRANS, k
        for lang in LANGS:
            assert (TRANS[k].get(lang) or "").strip(), (k, lang)


# ---- normalize_measures (response_measures_schema.R:49-107) ---------------------

def test_normalize_selects_and_orders_columns():
    out = normalize_measures([{"Name": "x", "ID": "RM001", "Bogus": "drop me"}])
    assert len(out) == 1
    row = out[0]
    assert list(row) == list(RM_REGISTER_COLUMNS)          # unknown key dropped, R's order
    assert row["ID"] == "RM001" and row["Name"] == "x"
    assert row["Cost"] is None                              # missing Cost -> NA_real_
    assert all(row[c] == "" for c in RM_REGISTER_COLUMNS if c not in ("ID", "Name", "Cost"))
    assert normalize_measures(None) == [] and normalize_measures([]) == []


@pytest.mark.parametrize("given,want", [
    ("7", 7.0), (7, 7.0), (2.5, 2.5), (" 3 ", 3.0), ("1e1", 10.0),
    ("cheap", None), (None, None), ("nan", None), ("inf", None), ("", None),
    (float("nan"), None), (["1", "2"], None), (True, None)])
def test_cost_coercion(given, want):
    # R: Cost -> as.numeric(paste(unlist(v), collapse=";")) (:59, :71); NaN/Inf -> None
    # (SESPy, so the JSON stays valid); a bool is pasted "TRUE" first -> NA, as R's list path.
    assert normalize_measures([{"ID": "RM001", "Cost": given}])[0]["Cost"] == want


def test_list_cell_joined():
    row = normalize_measures([{"ID": "RM001", "Stakeholders": ["a", "b"],
                               "ImplementingStakeholders": ["SH001", None, "SH002"]}])[0]
    assert row["Stakeholders"] == "a;b"
    assert row["ImplementingStakeholders"] == "SH001;SH002"   # R unlist() drops NULL


def test_scalar_cells_become_r_text():
    # R paste(): 5 -> "5", 5.5 -> "5.5"; None -> "".
    row = normalize_measures([{"ID": "RM001", "Name": 5, "Barriers": 5.5, "Mechanism": None}])[0]
    assert (row["Name"], row["Barriers"], row["Mechanism"]) == ("5", "5.5", "")


def test_pestle_cleaned(caplog):
    # testthat test-response-measures-schema.R:207-208 (4017feb)
    with caplog.at_level(logging.WARNING, logger="sespy.response_register"):
        row = normalize_measures([{"ID": "RM001", "PestleTag": "legal; political;bogus;legal"}])[0]
    assert row["PestleTag"] == "political;legal"
    assert any("bogus" in r.getMessage() for r in caplog.records)
    assert normalize_measures([{"ID": "R", "PestleTag": ["legal", "social"]}])[0]["PestleTag"] \
        == "social;legal"


def test_tenet_levels(caplog):
    # testthat :225-235 (4017feb); response_measures_schema.R:92-105
    with caplog.at_level(logging.WARNING, logger="sespy.response_register"):
        row = normalize_measures([{
            "ID": "RM001",
            "Tenet_ecol_effective": "Intermediate ",
            "Tenet_tech_feasible": "intermediate",       # only ecol_effective has it
            "Tenet_econ_viable": "FULL",
            "Tenet_communicable": "great",
            "Tenet_admin_achievable": " ",
        }])[0]
    assert row["Tenet_ecol_effective"] == "intermediate"
    assert row["Tenet_tech_feasible"] == ""
    assert row["Tenet_econ_viable"] == "full"
    assert row["Tenet_communicable"] == ""
    assert row["Tenet_admin_achievable"] == ""
    assert sum("Tenet_" in r.getMessage() for r in caplog.records) == 3


def test_reverse_map_all_languages():
    m = reverse_label_map()
    vocabs = {
        "type": {c: s for c, s in RM_TYPE_CODES.items()},
        "target": {c: s for c, s in RM_TARGET_CODES.items()},
        "status": {c: s for c, s in RM_STATUS_CODES.items()},
        "problem_type": {c: c for c in IMPACT_PROBLEM_TYPES},
        "strength": {c: c for c in IMPACT_STRENGTHS},
        "timeframe": {c: c for c in TIMEFRAMES},
        "milestone_status": {c: c for c in MILESTONE_STATUSES},
    }
    assert set(m) == set(vocabs)
    for vocab, codes in vocabs.items():
        for code, suffix in codes.items():
            for lang in LANGS:
                assert m[vocab][_rm(suffix, lang).strip()] == code, (vocab, code, lang)
    assert m["target"]["Activities:"] == "activities"


def test_label_to_code_on_normalise():
    # testthat :25-40 and :130-139 (4017feb): labels of any language map to codes.
    lt = _rm("implemented", "lt")
    row = normalize_measures([{"ID": "RM001", "Status": lt,
                               "Type": _rm("economic", "lt"),
                               "Target": _rm("pressures", "de")}])[0]
    assert (row["Status"], row["Type"], row["Target"]) == ("implemented", "economic", "pressures")


def test_lookup_is_untrimmed():
    # pending D12 / R .map_codes (:40-45): the stored value is looked up as is.
    assert normalize_measures([{"ID": "R", "Target": " Activities: "}])[0]["Target"] == " Activities: "
    assert normalize_measures([{"ID": "R", "Target": "Activities:"}])[0]["Target"] == "activities"


def test_handtyped_values_pass_through():
    row = normalize_measures([{"ID": "RM001", "Type": "something else",
                               "Effectiveness": "Very high", "Status": "hand typed"}])[0]
    assert (row["Type"], row["Effectiveness"], row["Status"]) == (
        "something else", "Very high", "hand typed")


def test_normalise_is_idempotent():
    rows = [{"ID": "RM001", "Name": "a", "Type": _rm("economic", "lt"), "Cost": "4",
             "PestleTag": "legal;political", "Tenet_econ_viable": " Full",
             "Stakeholders": ["x", "y"], "Extra": 1},
            {"ID": "RM002", "Cost": None, "Status": "planned"}]
    once = normalize_measures(rows)
    assert normalize_measures(once) == once


def test_malformed_measures_input(caplog):
    # pending D11: a JSON object -> empty register + warning (R Filter(is.list), :54);
    # a non-object row -> dropped + warning.
    with caplog.at_level(logging.WARNING, logger="sespy.response_register"):
        assert normalize_measures({"ID": "RM001"}) == []
        out = normalize_measures(["oops", {"ID": "RM002"}, ["a", "b"], 7])
    assert [r["ID"] for r in out] == ["RM002"]
    assert len(caplog.records) == 2


def test_normalize_impacts_and_milestones():
    imp = normalize_impacts([{"ResponseID": "RM001", "ProblemType": _rm("specific_pressure", "fr"),
                              "ImpactStrength": "Strong", "Timeframe": "short_term_1_3y",
                              "ProblemElementID": "P001", "Extra": "x"},
                             {"ResponseID": "RM002", "ProblemType": "hand typed"}])
    assert imp == [
        {"ResponseID": "RM001", "ProblemType": "specific_pressure", "ProblemElementID": "P001",
         "ImpactStrength": "strong", "Timeframe": "short_term_1_3y"},
        {"ResponseID": "RM002", "ProblemType": "hand typed", "ProblemElementID": "",
         "ImpactStrength": "", "Timeframe": ""}]
    ms = normalize_milestones([{"ResponseID": "RM001", "Milestone": "Consultation",
                                "TargetDate": "2027-10-22", "Status": _rm("in_progress", "de"),
                                "Notes": None}])
    assert ms == [{"ResponseID": "RM001", "Milestone": "Consultation", "TargetDate": "2027-10-22",
                   "Status": "in_progress", "Notes": ""}]
    assert normalize_impacts(None) == [] and normalize_milestones({"x": 1}) == []


# ---- EBM pickers (response_measures_schema.R:110-129) ----------------------------

def test_ebm_code_choices_and_suggest_target():
    inst = ebm_code_choices("instrument")
    assert len(inst) == 20 and "3.5" not in inst and not {"1", "2", "3", "4"} & set(inst)
    assert len(ebm_code_choices("measure")) == 12 and ebm_code_choices("") == []
    assert [suggest_target(c) for c in ("output", "spatial.seasonal", "restoration.habitat",
                                        "nbs.replace", "1.1", "")] == [
        "pressures", "multiple", "state", "activities", "", ""]
    assert len(EBM_POLICY_INSTRUMENTS) == 24 and len(EBM_MANAGEMENT_MEASURES) == 12


def test_ebm_picker_label():
    # response_measures_schema.R:120-124; wp5_vocabulary.R:53-67
    assert ebm_picker_label("instrument", "1.1", tr) == "1.1 " + tr("modules.wp5_vocabulary.instrument.1_1")
    assert ebm_picker_label("measure", "output", tr) == tr("modules.wp5_vocabulary.measure.output")
    assert ebm_picker_label("measure", "no.such", tr) == "no.such"       # missing key -> raw code
    assert ebm_picker_label("instrument", "9.9", tr) == "9.9 9.9"


# ---- prioritisation (response_module.R:705-722, 775-776, 801-814) ----------------

def _m(i, eff, feas, cost):
    return normalize_measures([{"ID": f"RM00{i}", "Name": f"m{i}", "Effectiveness": eff,
                                "Feasibility": feas, "Cost": cost}])[0]


def test_priority_rows_reproduce_r():
    ms = [_m(1, "HIGH", "LOW", 5), _m(2, "MEDIUM", "HIGH", 9), _m(3, "LOW", "MEDIUM", None),
          _m(4, "HIGH", "LOW", 5), _m(5, "", "UNKNOWN", 1)]
    rows = priority_rows(ms)
    assert [r["ID"] for r in rows] == ["RM001", "RM004", "RM002", "RM005", "RM003"]
    assert [r["Rank"] for r in rows] == [1, 2, 3, 4, 5]
    by = {r["ID"]: r for r in rows}
    # 0.4*3/3 + 0.3*1/3 + 0.3*(11-5)/10
    assert by["RM001"]["PriorityScore"] == pytest.approx(0.4 + 0.1 + 0.18, abs=1e-9)
    # 0.4*2/3 + 0.3*3/3 + 0.3*(11-9)/10
    assert by["RM002"]["PriorityScore"] == pytest.approx(0.8 / 3 + 0.3 + 0.06, abs=1e-9)
    # 0 + 0 + 0.3*(11-1)/10
    assert by["RM005"]["PriorityScore"] == pytest.approx(0.3, abs=1e-9)
    assert (by["RM001"]["EffScore"], by["RM001"]["FeasScore"]) == (3, 1)
    assert by["RM001"]["CostScore"] == pytest.approx(0.6, abs=1e-12)
    assert by["RM003"]["CostScore"] is None and by["RM003"]["PriorityScore"] is None
    assert (by["RM005"]["EffScore"], by["RM005"]["FeasScore"]) == (0, 0)
    w = priority_rows(ms, w_eff=1.0, w_feas=0.0, w_cost=0.0)
    assert [r["ID"] for r in w][:2] == ["RM001", "RM004"] and w[-1]["ID"] == "RM003"
    assert ms[0].get("PriorityScore") is None             # input rows untouched


def test_ef_points_skip_unrated():
    ms = [_m(1, "HIGH", "LOW", 5), _m(2, "UNKNOWN", "HIGH", 5), _m(3, "", "LOW", 5),
          _m(4, "Very high", "MEDIUM", 5), _m(5, "MEDIUM", "MEDIUM", 5)]
    assert ef_points(ms) == [("RM001", 1, 3), ("RM005", 2, 2)]
    assert ef_points([_m(1, "UNKNOWN", "", 5)]) == []


# ---- display (response_measures_schema.R:132-195) --------------------------------

def test_display_value():
    assert display_value("Kind", "instrument", tr) == "Policy instrument"
    assert display_value("GovernanceLevel", "regional_sea", tr) == "Regional sea"
    assert display_value("Tenet_econ_viable", "minimal", tr) == "Minimal compliance"
    assert display_value("Tenet_econ_viable", "", tr) == ""          # testthat :180
    assert display_value("Target", "activities", tr) == "Activities:"
    assert display_value("Target", "multiple", tr) == tr("modules.response.measures.multiple_levels")
    assert display_value("PestleTag", "political;legal", tr) == "Political, Legal"
    assert display_value("EbmCode", "output", tr) == tr("modules.wp5_vocabulary.measure.output")
    assert "output" not in display_value("EbmCode", "output", tr)
    assert display_value("EbmCode", "1.1", tr) == tr("modules.wp5_vocabulary.instrument.1_1")
    assert display_value("EbmCode", "zz", tr) == "zz"
    assert display_value("Timeframe", "short_term_1_3y", tr) == "Short-term (1-3y)"
    assert display_value("Cost", 5.0, tr) == "5" and display_value("Cost", 7.5, tr) == "7.5"
    assert display_value("Cost", None, tr) == ""
    assert display_value("PriorityScore", 0.123456, tr) == "0.123"
    assert display_value("Type", "something else", tr) == "something else"
    assert display_value("Effectiveness", "HIGH", tr) == "High"
    assert display_value("Effectiveness", "Very high", tr) == "Very high"
    assert display_value("Status", "partially_implemented", tr) == "Partially Implemented"
    assert display_value("Status", "in_progress", tr) == "In Progress"   # milestone status
    assert display_value("ProblemType", "system_wide_issue", tr) == "System-wide Issue"
    assert display_value("Name", "Quota", tr) == "Quota"
    assert display_value("Name", None, tr) == ""
    # a translator that returns the key (missing) or "" -> raw value
    assert display_value("Type", "regulatory", lambda k: k) == "regulatory"
    assert display_value("Type", "regulatory", lambda k: "") == "regulatory"


def test_response_register_imports_without_shiny():
    code = ("import sys, sespy.response_register; from sespy.data_structure import Project; "
            "p = Project.from_dict({'metadata': {'name': 'x'}, 'isa_data': {'elements': [], "
            "'connections': []}, 'response_measures': {'measures': [{'ID': 'RM001', 'Name': 'n'}], "
            "'counter': 1}}); sys.exit(1 if 'shiny' in sys.modules else 0)")
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0
