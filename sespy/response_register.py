"""Response register — Shiny-free port of R's register schema (P1b, spec §4.2).

Ports, from MarineSABRES_SES_Shiny v1.33.0 (4017feb):
- the code lists of constants.R:780-846, 933 (fixture tests/parity/r_source/
  constants.R; checked by tests/parity/test_r_register_parity.py);
- normalize_response_measures, suggest_rm_target, ebm_code_choices,
  rm_display_label and rm_translate_for_display
  (functions/response_measures_schema.R:13-195);
- the register UI's choice lists and the prioritisation score
  (modules/response_module.R; no fixture, the lines are cited).

Rows are plain dicts keyed by R's column names. Stored values are codes;
labels exist only for display. Nothing here imports Shiny
(tests/test_response_register.py::test_response_register_imports_without_shiny).
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any, Callable, Iterable

from .data_structure import ResponseRegister
from .utils import safe_counter

_log = logging.getLogger(__name__)

# ---- code lists (constants.R v1.33.0) -----------------------------------------

# constants.R:831-840
RM_REGISTER_COLUMNS: tuple[str, ...] = (
    "ID", "Name", "Type", "Target", "Description", "Mechanism", "TargetElement",
    "Effectiveness", "Feasibility", "Cost", "Status", "Stakeholders", "Barriers", "DateAdded",
    "Kind", "EbmCode", "GovernanceLevel", "CompetentAuthority", "LegalBasis",
    "ImplementingStakeholders", "PairedWith", "PestleTag",
    "Tenet_ecol_effective", "Tenet_tech_feasible", "Tenet_econ_efficient",
    "Tenet_econ_viable", "Tenet_socially_desirable", "Tenet_ethically_defensible",
    "Tenet_culturally_inclusive", "Tenet_legally_permissible", "Tenet_admin_achievable",
    "Tenet_communicable", "Tenet_politically_expedient",
    "TenetSource",
)
# constants.R:844-846
RM_DISPLAY_COLUMNS: tuple[str, ...] = (
    "ID", "Name", "Type", "Target", "Kind", "EbmCode", "GovernanceLevel", "PestleTag",
    "CompetentAuthority", "LegalBasis", "Effectiveness", "Feasibility", "Cost",
    "Status", "DateAdded",
)
# EBM_TENETS$code, constants.R:804-810
TENET_CODES: tuple[str, ...] = (
    "ecol_effective", "tech_feasible", "econ_efficient",
    "econ_viable", "socially_desirable", "ethically_defensible", "culturally_inclusive",
    "legally_permissible", "admin_achievable", "communicable", "politically_expedient",
)
# code -> label-key suffix under modules.response.measures. (constants.R:821-827)
RM_TYPE_CODES: dict[str, str] = {
    "regulatory": "regulatory", "economic": "economic", "educational": "educational",
    "technical": "technical", "institutional": "institutional",
    "voluntary": "voluntary", "mixed": "mixed",
}
RM_TARGET_CODES: dict[str, str] = {
    "drivers": "drivers", "activities": "activities", "pressures": "pressures",
    "state": "state", "multiple": "multiple_levels",
}
RM_STATUS_CODES: dict[str, str] = {
    "proposed": "proposed", "planned": "planned", "implemented": "implemented",
    "partially_implemented": "partially_implemented", "abandoned": "abandoned",
}
# constants.R:828, :829 (intermediate: ecol_effective only), :933
GOVERNANCE_LEVELS: tuple[str, ...] = (
    "local", "island", "regional", "national", "eu", "regional_sea", "international")
TENET_LEVELS: tuple[str, ...] = ("minimal", "intermediate", "full")
PESTLE_CODES: tuple[str, ...] = (
    "political", "economic", "social", "technological", "legal", "environmental")
# (code, level) for all 24 rows, category rows included; no 3.5 (constants.R:780-790)
EBM_POLICY_INSTRUMENTS: tuple[tuple[str, str], ...] = (
    ("1", "category"), ("1.1", "type"), ("1.2", "type"), ("1.3", "type"),
    ("1.4", "type"), ("1.5", "type"), ("1.6", "type"),
    ("2", "category"), ("2.1", "type"), ("2.2", "type"), ("2.3", "type"),
    ("2.4", "type"), ("2.5", "type"),
    ("3", "category"), ("3.1", "type"), ("3.2", "type"), ("3.3", "type"),
    ("3.4", "type"), ("3.6", "type"), ("3.7", "type"),
    ("4", "category"), ("4.1", "type"), ("4.2", "type"), ("4.3", "type"),
)
# (code, category, dapsiwrm_target) (constants.R:793-801)
EBM_MANAGEMENT_MEASURES: tuple[tuple[str, str, str], ...] = (
    ("spatial.year_round", "spatial", "A|P|C"), ("spatial.seasonal", "spatial", "A|P|C"),
    ("input.capacity", "input", "A"), ("input.effort", "input", "A"),
    ("input.technical", "input", "A"), ("output", "output", "P"),
    ("remediation", "remediation", "P"), ("restoration.species", "restoration", "C"),
    ("restoration.habitat", "restoration", "C"), ("nbs.enhance", "nbs", "C"),
    ("nbs.multi_use", "nbs", "A"), ("nbs.replace", "nbs", "A"),
)

# ---- UI choice lists (modules/response_module.R v1.33.0; no fixture) ----------
KIND_CODES: tuple[str, ...] = ("instrument", "measure")                     # :134-137
EFFECTIVENESS_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")  # :91-95
FEASIBILITY_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")               # :98-102
# SESPy stores these codes where R stores the translated label (spec §4.2.2);
# each code is R's label-key suffix under modules.response.measures.
IMPACT_PROBLEM_TYPES: tuple[str, ...] = (                                     # :207-209
    "specific_pressure", "specific_activity", "specific_driver", "system_wide_issue")
IMPACT_STRENGTHS: tuple[str, ...] = ("strong", "moderate", "weak")           # :218-219
TIMEFRAMES: tuple[str, ...] = (                                               # :222-224
    "immediate", "short_term_1_3y", "medium_term_3_10y", "long_term_10y")
MILESTONE_STATUSES: tuple[str, ...] = (                                       # :339-340
    "pending", "in_progress", "completed", "delayed")
# functions/data_structure.R:292-305
IMPACT_COLUMNS: tuple[str, ...] = (
    "ResponseID", "ProblemType", "ProblemElementID", "ImpactStrength", "Timeframe")
MILESTONE_COLUMNS: tuple[str, ...] = (
    "ResponseID", "Milestone", "TargetDate", "Status", "Notes")

_RM_PREFIX = "modules.response.measures."
_GOV_PREFIX = "modules.response.governance."
_LEVEL_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
_TENET_COLUMNS = tuple(f"Tenet_{c}" for c in TENET_CODES)
_INSTRUMENT_CODES = frozenset(c for c, _ in EBM_POLICY_INSTRUMENTS)
_MEASURE_CODES = frozenset(c for c, _, _ in EBM_MANAGEMENT_MEASURES)
_VENDORED = Path(__file__).resolve().parent / "translations" / "modules" / "response_measures.json"

# vocab name -> {code: label-key suffix}
_VOCABS: dict[str, dict[str, str]] = {
    "type": RM_TYPE_CODES,
    "target": RM_TARGET_CODES,
    "status": RM_STATUS_CODES,
    "problem_type": {c: c for c in IMPACT_PROBLEM_TYPES},
    "strength": {c: c for c in IMPACT_STRENGTHS},
    "timeframe": {c: c for c in TIMEFRAMES},
    "milestone_status": {c: c for c in MILESTONE_STATUSES},
}


@cache
def reverse_label_map() -> dict[str, dict[str, str]]:
    """R rm_reverse_label_map (response_measures_schema.R:14-38), extended to
    the impact and milestone vocabularies (spec §4.2.2): vocab -> {label ->
    code} over every language of the vendored response_measures.json (the R
    keys live only there at v1.33.0). Labels are stripped and non-empty;
    the first occurrence wins. Reads the vendored file directly (never
    sespy.i18n, which imports Shiny)."""
    tr = json.loads(_VENDORED.read_text(encoding="utf-8"))["translation"]
    out: dict[str, dict[str, str]] = {}
    for vocab, codes in _VOCABS.items():
        m: dict[str, str] = {}
        for code, suffix in codes.items():
            entry = tr.get(_RM_PREFIX + suffix) or {}
            for text in entry.values():
                label = str(text).strip()
                if label and label not in m:
                    m[label] = code
        out[vocab] = m
    return out


def _map_code(value: str, vocab: str) -> str:
    """R .map_codes (:40-45): a value that is not a code but is a label maps
    to its code. The lookup uses the value as stored, untrimmed (pending D12)."""
    codes = _VOCABS[vocab]
    if value in codes:
        return value
    return reverse_label_map()[vocab].get(value, value)


def _r_text(v: Any) -> str | None:
    """One cell as R's paste(unlist(v), collapse = ";") gives it (:56-60);
    None for R's NA (nothing left after unlist)."""
    parts: list[str] = []

    def walk(x: Any) -> None:
        if x is None:
            return                                   # unlist() drops NULL
        if isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            for y in x.values():
                walk(y)
        elif isinstance(x, bool):
            parts.append("TRUE" if x else "FALSE")
        elif isinstance(x, float):
            if math.isnan(x):
                return
            parts.append(str(int(x)) if x.is_integer() else str(x))
        else:
            parts.append(str(x))

    walk(v)
    return ";".join(parts) if parts else None


def _cost(text: str | None) -> float | None:
    """R as.numeric on the pasted text (:71); NaN and +-inf -> None (SESPy:
    JSON has no NaN/Infinity)."""
    if text is None:
        return None
    try:
        f = float(text)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _rows(rows: Any, what: str) -> list[dict[str, Any]]:
    """The dict rows of `rows`. R keeps only list items (Filter(is.list), :54);
    a JSON object instead of a list, or a non-object row, is dropped with one
    warning (pending D11)."""
    if rows is None:
        return []
    if not isinstance(rows, list):
        _log.warning("%s: expected a list of rows, got %s; ignored", what, type(rows).__name__)
        return []
    keep = [r for r in rows if isinstance(r, dict)]
    if len(keep) != len(rows):
        _log.warning("%s: dropped %d non-row item(s)", what, len(rows) - len(keep))
    return keep


def normalize_measures(rows: Any) -> list[dict[str, Any]]:
    """R normalize_response_measures (response_measures_schema.R:49-107),
    step for step: exactly RM_REGISTER_COLUMNS in order (unknown keys
    dropped, missing -> "" / None); Cost -> finite float or None; list cells
    ;-joined; Type/Target/Status labels (any of 9 languages) -> codes, other
    values pass through; PestleTag split/trim/drop-unknown (one warning) and
    re-ordered as PESTLE_CODES; tenet levels lower().strip(), blanked when
    not allowed (one warning per column). Idempotent."""
    out: list[dict[str, Any]] = []
    for r in _rows(rows, "normalize_measures"):
        row: dict[str, Any] = {}
        for col in RM_REGISTER_COLUMNS:
            text = _r_text(r.get(col))
            row[col] = _cost(text) if col == "Cost" else (text or "")
        row["Type"] = _map_code(row["Type"], "type")
        row["Target"] = _map_code(row["Target"], "target")
        row["Status"] = _map_code(row["Status"], "status")
        out.append(row)
    for row in out:
        tags = [t.strip() for t in row["PestleTag"].split(";")]
        bad = [t for t in tags if t and t not in PESTLE_CODES]
        if bad:
            _log.warning("normalize_measures: dropped unknown PESTLE code(s): %s", ", ".join(bad))
        row["PestleTag"] = ";".join(c for c in PESTLE_CODES if c in tags)
    for code, col in zip(TENET_CODES, _TENET_COLUMNS):
        ok = TENET_LEVELS if code == "ecol_effective" else ("minimal", "full")
        bad = []
        for row in out:
            tidy = row[col].strip().lower()
            if tidy in ok:
                row[col] = tidy
            elif row[col]:
                bad.append(row[col])
                row[col] = ""
        if bad:
            _log.warning("normalize_measures: blanked invalid %s value(s): %s",
                         col, ", ".join(dict.fromkeys(bad)))
    return out


def _normalize_table(rows: Any, columns: tuple[str, ...], coded: dict[str, str],
                     what: str) -> list[dict[str, str]]:
    out = []
    for r in _rows(rows, what):
        row = {c: _r_text(r.get(c)) or "" for c in columns}
        for col, vocab in coded.items():
            row[col] = _map_code(row[col], vocab)
        out.append(row)
    return out


def normalize_impacts(rows: Any) -> list[dict[str, str]]:
    """Exactly IMPACT_COLUMNS; ProblemType/ImpactStrength/Timeframe labels ->
    codes (spec §4.2.2); unknown values pass through."""
    return _normalize_table(rows, IMPACT_COLUMNS,
                            {"ProblemType": "problem_type", "ImpactStrength": "strength",
                             "Timeframe": "timeframe"}, "normalize_impacts")


def normalize_milestones(rows: Any) -> list[dict[str, str]]:
    """Exactly MILESTONE_COLUMNS; Status labels -> codes (spec §4.2.2);
    unknown values pass through."""
    return _normalize_table(rows, MILESTONE_COLUMNS, {"Status": "milestone_status"},
                            "normalize_milestones")


# ---- EBM pickers (response_measures_schema.R:110-129) --------------------------

def ebm_code_choices(kind: str) -> list[str]:
    """Instruments: the 20 "type"-level codes; measures: all 12; else []
    (:118-129; the UI adds the blank first choice)."""
    if kind == "instrument":
        return [c for c, level in EBM_POLICY_INSTRUMENTS if level == "type"]
    if kind == "measure":
        return [c for c, _, _ in EBM_MANAGEMENT_MEASURES]
    return []


def _vocab_label(kind: str, code: str, tr: Callable[[str], str]) -> str:
    """R wp5_vocab_label (wp5_vocabulary.R:53-67): the label, or the raw code
    when the key is missing (the translator returns the key) or empty."""
    key = f"modules.wp5_vocabulary.{kind}.{code.replace('.', '_')}"
    label = tr(key)
    return code if not label or label == key else label


def ebm_picker_label(kind: str, code: str, tr: Callable[[str], str]) -> str:
    """Picker label: an instrument shows "<code> <label>", a measure "<label>" (:120-124)."""
    label = _vocab_label(kind, code, tr)
    return f"{code} {label}" if kind == "instrument" else label


def suggest_target(ebm_measure_code: str) -> str:
    """R suggest_rm_target (:110-115): a measure's dapsiwrm_target A ->
    activities, P -> pressures, C -> state, A|P|C -> multiple; else ""."""
    for code, _, target in EBM_MANAGEMENT_MEASURES:
        if code == ebm_measure_code:
            return {"A": "activities", "P": "pressures", "C": "state",
                    "A|P|C": "multiple"}.get(target, "")
    return ""


# ---- prioritisation (response_module.R:705-722, 775-776, 801-814) ---------------

def priority_rows(measures: list[dict], w_eff: float = 0.4, w_feas: float = 0.3,
                  w_cost: float = 0.3) -> list[dict[str, Any]]:
    """Each measure plus EffScore, FeasScore (HIGH 3 / MEDIUM 2 / LOW 1 /
    else 0), CostScore = (11 - Cost) / 10 and PriorityScore = w_eff*Eff/3 +
    w_feas*Feas/3 + w_cost*CostScore; a None Cost gives None scores (R NA).
    Sorted by PriorityScore descending, stable, None last (R order()), with
    Rank 1..n. Input rows are not modified."""
    rows = []
    for m in measures:
        eff = _LEVEL_SCORE.get(m.get("Effectiveness"), 0)
        feas = _LEVEL_SCORE.get(m.get("Feasibility"), 0)
        cost = m.get("Cost")
        cost_score = None if cost is None else (11 - cost) / 10
        score = None if cost_score is None else (
            (w_eff * eff / 3) + (w_feas * feas / 3) + (w_cost * cost_score))
        rows.append({**m, "EffScore": eff, "FeasScore": feas,
                     "CostScore": cost_score, "PriorityScore": score})
    rows.sort(key=lambda r: (r["PriorityScore"] is None, -(r["PriorityScore"] or 0.0)))
    for rank, r in enumerate(rows, start=1):
        r["Rank"] = rank
    return rows


def ef_points(measures: list[dict]) -> list[tuple[str, int, int]]:
    """(ID, feasibility 1-3, effectiveness 1-3) of the measures whose
    Effectiveness and Feasibility are both HIGH/MEDIUM/LOW, in input order
    (response_module.R:801-814)."""
    return [(m.get("ID", ""), _LEVEL_SCORE[m["Feasibility"]], _LEVEL_SCORE[m["Effectiveness"]])
            for m in measures
            if m.get("Effectiveness") in _LEVEL_SCORE and m.get("Feasibility") in _LEVEL_SCORE]


# ---- display (response_measures_schema.R:132-195) --------------------------------

def _translate(key: str | None, raw: str, tr: Callable[[str], str]) -> str:
    if key is None:
        return raw
    label = tr(key)
    return raw if not label or label == key else label


def _display_key(column: str, code: str) -> str | None:
    if column in ("Effectiveness", "Feasibility"):
        return _RM_PREFIX + code.lower() if code in EFFECTIVENESS_LEVELS else None
    if column == "Type":
        return _RM_PREFIX + RM_TYPE_CODES[code] if code in RM_TYPE_CODES else None
    if column == "Target":
        return _RM_PREFIX + RM_TARGET_CODES[code] if code in RM_TARGET_CODES else None
    if column == "Status":                    # measure or milestone status (no overlap)
        if code in RM_STATUS_CODES:
            return _RM_PREFIX + RM_STATUS_CODES[code]
        return _RM_PREFIX + code if code in MILESTONE_STATUSES else None
    if column == "Kind":
        return f"{_GOV_PREFIX}kind.{code}" if code in KIND_CODES else None
    if column == "GovernanceLevel":
        return f"{_GOV_PREFIX}level.{code}" if code in GOVERNANCE_LEVELS else None
    if column.startswith("Tenet_") and column != "TenetSource":
        return f"{_GOV_PREFIX}tenet_level.{code}" if code in TENET_LEVELS else None
    if column == "ProblemType":
        return _RM_PREFIX + code if code in IMPACT_PROBLEM_TYPES else None
    if column == "ImpactStrength":
        return _RM_PREFIX + code if code in IMPACT_STRENGTHS else None
    if column == "Timeframe":
        return _RM_PREFIX + code if code in TIMEFRAMES else None
    return None


def display_value(column: str, value: Any, tr: Callable[[str], str]) -> str:
    """One cell for display (tables, Excel export): R rm_translate_for_display
    + rm_display_label (:132-195), extended to the impact and milestone codes
    SESPy stores (spec §4.2.2). A blank or None value is "" in every column;
    an unknown value, or a key the translator returns unchanged or empty,
    shows the raw value. EbmCode shows the vocabulary label without the code
    (measure codes first, then instrument codes). Cost: an integral float as
    an int; PriorityScore: 3 decimals (R formatRound(..., 3))."""
    if value is None or (isinstance(value, str) and not value):
        return ""
    if column == "Cost" and isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if column == "PriorityScore" and isinstance(value, (int, float)):
        return f"{value:.3f}"
    raw = str(value)
    if column == "EbmCode":
        if raw in _MEASURE_CODES:
            return _vocab_label("measure", raw, tr)
        if raw in _INSTRUMENT_CODES:
            return _vocab_label("instrument", raw, tr)
        return raw
    if column == "PestleTag":
        key = "modules.wp5_scenarios.pestle."
        return ", ".join(_translate(key + t if t in PESTLE_CODES else None, t, tr)
                         for t in raw.split(";"))
    return _translate(_display_key(column, raw), raw, tr)


# ---- register-level helpers (return new objects, never mutate) ------------------

def add_measure(reg: ResponseRegister, fields: dict[str, Any], *,
                today: str) -> tuple[ResponseRegister, str]:
    """R register add (response_module.R:507-511, 562-585): n = safe_counter(
    counter, ids, "RM") + 1, ID "RM%03d", counter = n, DateAdded = today; the
    row goes through normalize_measures. Returns (new register, new ID)."""
    n = safe_counter(reg.counter, [m.get("ID") for m in reg.measures], "RM") + 1
    new_id = f"RM{n:03d}"
    row = normalize_measures([{**fields, "ID": new_id, "DateAdded": today}])[0]
    return replace(reg, measures=[*reg.measures, row], counter=n), new_id


def update_measure(reg: ResponseRegister, measure_id: str,
                   fields: dict[str, Any]) -> tuple[ResponseRegister, bool]:
    """R register update (response_module.R:515-525): the first row with
    `measure_id` gets the known columns of `fields` (R skips only ID; SESPy
    also keeps DateAdded); other columns are kept; the row is re-normalised.
    (unchanged register, False) when the ID is absent."""
    for i, m in enumerate(reg.measures):
        if m.get("ID") == measure_id:
            changes = {k: v for k, v in fields.items()
                       if k in RM_REGISTER_COLUMNS and k not in ("ID", "DateAdded")}
            row = normalize_measures([{**m, **changes}])[0]
            measures = [*reg.measures[:i], row, *reg.measures[i + 1:]]
            return replace(reg, measures=measures), True
    return reg, False


def delete_measures(reg: ResponseRegister,
                    ids: Iterable[str]) -> tuple[ResponseRegister, int]:
    """R delete (response_module.R:650-657): only the measure rows go; the
    counter is unchanged and impacts/milestones are kept (no cascade, spec
    §6.1). The int counts the impact + milestone rows whose ResponseID is in
    `ids`."""
    gone = set(ids)
    measures = [m for m in reg.measures if m.get("ID") not in gone]
    refs = sum(1 for r in (*reg.impacts, *reg.milestones) if r.get("ResponseID") in gone)
    return replace(reg, measures=measures), refs


def add_impact(reg: ResponseRegister, fields: dict[str, Any]) -> ResponseRegister:
    return replace(reg, impacts=[*reg.impacts, *normalize_impacts([fields])])


def delete_impact(reg: ResponseRegister, index: int) -> ResponseRegister:
    if not 0 <= index < len(reg.impacts):
        return reg
    return replace(reg, impacts=[r for i, r in enumerate(reg.impacts) if i != index])


def add_milestone(reg: ResponseRegister, fields: dict[str, Any]) -> ResponseRegister:
    return replace(reg, milestones=[*reg.milestones, *normalize_milestones([fields])])


def delete_milestone(reg: ResponseRegister, index: int) -> ResponseRegister:
    if not 0 <= index < len(reg.milestones):
        return reg
    return replace(reg, milestones=[r for i, r in enumerate(reg.milestones) if i != index])


def split_ids(value: str) -> list[str]:
    """IDs in a TargetElement cell. R's field is free text, usually
    comma-separated (placeholder `modules.response.measures.placeholder_element_ids`,
    "e.g., A001, D002"); SESPy writes ";"-joined IDs. Both separators are read;
    parts are stripped and empty ones dropped."""
    return [p.strip() for p in re.split(r"[;,]", value or "") if p.strip()]


def references_to(reg: ResponseRegister, element_id: str) -> list[str]:
    """Sorted unique IDs of the measures whose TargetElement (split_ids, exact
    match) contains `element_id`, plus the ResponseID of impact rows whose
    ProblemElementID equals it (the ISA page's delete warning, spec §6.1)."""
    if not element_id:
        return []
    hits = {m.get("ID", "") for m in reg.measures
            if element_id in split_ids(m.get("TargetElement", ""))}
    hits |= {r.get("ResponseID", "") for r in reg.impacts
             if r.get("ProblemElementID") == element_id}
    return sorted(h for h in hits if h)
