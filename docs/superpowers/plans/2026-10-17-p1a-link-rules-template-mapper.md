# P1a — Link rules, schema v7 and R template mapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SESPy v1.13.0: the R DAPSI(W)R(M) link-rule table (allow-and-warn, polarity prefill), project schema v7 (`Connection.description`, `Element.r_extra`, three metadata fields, `min_sespy_version` stamp), and a Shiny-free R template mapper that converts all 7 R v1.29.0 templates losslessly.

**Architecture:** The rule table lives as data in `sespy/constants.py`; `sespy/link_rules.py` (Shiny-free at import) classifies pairs, seeds polarity and logs off-rule links from `validate_project_payload` only. Schema v7 is serialised explicitly in `Project.to_dict()`, which also stamps `min_sespy_version`; tolerance lives in `_isa_from_dict` (MosaicSES path) and the one strict check in validation. `sespy/r_template_mapper.py` + `sespy/r_sync.py` work on sha256-pinned fixtures under `tests/parity/`, never shipped.

**Tech Stack:** Python 3.11+ (env Python 3.13), Shiny for Python 1.8.0 (`shiny.testserver.test_server` for in-memory module tests), pandas/openpyxl (Excel), `packaging` (version compare), pytest, Playwright (async standalone e2e scripts).

**Spec:** docs/superpowers/specs/2026-10-17-p1a-link-rules-template-mapper-design.md

## Global Constraints

- Python: always `micromamba run -n shiny python ...`. Never `pip install`, never a venv, never `python - <<EOF` (leaves spinning stdin orphans), never a multi-line `python -c "..."` on Windows (it splits per line and creates stray files) — use a `.py` file.
- Branch: cut `feat/p1a-link-rules` from the current HEAD of `docs/p1a-design` (commit `aadb874`, which carries the spec and has the v1.12.3 code). Local `main` is 10 behind `origin/main`; do not use it.
- Never `git commit -a` / `git add -A` / `git add .`: the user's `LITERATURE/proposed-issues.md` is modified and `LITERATURE/*.md` are untracked. Stage explicit paths only.
- Version: **1.13.0** in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` line 3 — first commit.
- `PROJECT_SCHEMA_VERSION = 7`; `SCHEMA_MIN_READER = {7: "1.13.0"}`.
- New dataclass fields are keyword-only with defaults (`field(..., kw_only=True)`) — MosaicSES constructs `Element`/`Connection`/`ProjectMetadata` positionally.
- R reference pin: MarineSABRES_SES_Shiny **v1.29.0 `e33faea`**, checkout at `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny`.
- Boolean: UI slider max and default stay **12** (server clamp `[4, 12]`); library ceiling `BOOLEAN_MAX_NODES_CEILING = 20`.
- CI unit command (every task must end green on it): `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q` (≈4 min; baseline 813 passed + 1 skipped; ≈1050 passed at the end).
- Every commit message ends with exactly these two trailer lines:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX`
- Commit messages are multi-line: use the **PowerShell tool** with a single-quoted here-string (`git commit -F -` is not needed; `git commit -m @'...'@` with `'@` at column 0). Never a PowerShell here-string in the Bash tool (it leaks a literal `@`).
- `tests/parity/` has no `__init__.py` (none in `tests/` either). Resolve the repo root with `Path(__file__).resolve().parents[2]`; never `from tests.x import ...` (a stray site-packages `tests` package shadows it).
- Logging: off-rule links log on logger `sespy.link_rules` only, only from `validate_project_payload`, only when the count is > 0. `data_structure` warns on `sespy.data_structure`. The mapper never logs.
- Expected at runtime after Task 3: the shipped gallery templates `minimal_demo.json` (4 off-rule links) and `offshore_wind.json` (2) log one `sespy.link_rules` WARNING each time they are validated (template listing). `data/sample_ses.json`, `coastal_tourism.json`, `small_scale_fisheries.json` log nothing. This is intended (allow-and-warn), not a regression.
- Nothing heavy runs alongside the e2e gate; port 8000 must be free before any e2e run; after any big run, sweep orphan `python` processes by creation date.
- Deploy steps (Task 15) need the user's explicit go-ahead.

## Review Focus

1. **`min_sespy_version` that is not a valid version string** (int `13`, float, `True`, `""`, `"not-a-version"`, `None`) reaching `Project.to_dict()` — `Version(13)` raises `TypeError`, not `InvalidVersion`; plus the `newer_build` reset branch and "never lowered" for an in-memory `"99.0.0"`. Owning task: **Task 2** (`test_unparsable_or_non_string_stamp_is_replaced`, `test_int_stamp_reaches_metadata_and_is_replaced`, `test_newer_build_stamp_is_reset_on_save`, `test_stamp_never_lowered_for_in_memory_project`, `test_older_format_copy_reloads_unflagged`).
2. **The load/validate split for the new fields**: `r_extra` that is `null` (silent `{}`) vs a string/list/int/bool (dropped with a `sespy.data_structure` warning, never fatal); `Connection.description` `None` → `""` and non-string coerced in `_isa_from_dict` but **rejected** by `validate_project_payload`; `Element.description` untouched. Owning task: **Task 2** (`test_non_object_r_extra_dropped_with_warning`, `test_null_or_absent_r_extra_is_silent`, `test_connection_description_coerced_on_load`, `test_validation_rejects_non_string_connection_description`, `test_validation_skips_null_description_and_loads_it_as_empty`, `test_element_description_none_is_untouched`).
3. **Excel polarity precedence with blank cells**: whitespace-only polarity cell + another alias column (`Sign`), blank polarity + Kumu `Label`, unstripped `" -"` Label, U+2212, numeric weight beating everything. Owning task: **Task 7** (`test_polarity_precedence_with_kumu_label`, 11 cases).
4. **Mapper edge inputs the 7 fixtures never exercise**: canonical + alias category both present (canonical wins), absent vs JSON-`null` fields, `bool`/`str`/`float` confidence, case-sensitive `"Strong"`, duplicate `(from_id, to_id)` with different attributes, `M→R` after folding (extension, not off-rule; no mismatch against pre-fold category). Owning task: **Task 5** (`test_canonical_key_wins_over_alias`, `test_absent_or_null_fields_take_r_defaults`, `test_failure_modes_raise_value_error`, `test_measure_to_response_link_becomes_extension_not_off_rule`).
5. **Untyped / unknown types and half-chosen pairs never flag**: `classify` with `""`, legacy `"Measures"`, `"Banana"` → `"untyped"`; entry pickers on the empty choice (only a source chosen, `new_target=""` set explicitly) seed nothing and show no note. Owning tasks: **Task 3** (`test_empty_or_unknown_types_are_untyped`, `test_clean_or_untyped_project_logs_nothing`) and **Task 9** (`test_only_a_source_seeds_nothing_and_shows_no_note`, `test_default_state_has_no_note`).

---

## File Structure

**Created**
| Path | Responsibility |
|---|---|
| `sespy/link_rules.py` | `classify`, `default_polarity`, `rule_id`, `seed_polarity`, `note_for`, `off_rule_message`, `log_off_rule_links`. Shiny-free at import. |
| `sespy/r_template_mapper.py` | `ConversionReport`, `convert_r_template`, `load_r_template`. Shiny-free, no clock, no logging. |
| `sespy/r_sync.py` | `sha256_norm(obj)`, `sha256_text_norm(text)` — the one hashing helper. |
| `tests/test_schema_v7.py` | Schema v7 fields, omission, load tolerance, validation, stamping. |
| `tests/test_link_rules.py` | Rule table rows, classification, helpers, logging; topology tests (Task 4). |
| `tests/parity/test_r_rules_parity.py` | Regex content parity of the rule table with the R `.R` fixture. |
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | R v1.29.0 rules fixture (copied). |
| `tests/parity/r_templates/{Aquaculture,Caribbean,ClimateChange,Fisheries,OffshoreWind,Pollution,Tourism}_SES_Template.json` | R v1.29.0 template fixtures (copied). |
| `tests/parity/r_sync.json` | Machine-readable pin `{r_tag, r_commit, files}`. |
| `tests/parity/test_r_sync.py` | Fixture hashes vs pin; `R_SYNC.md` vs pin; helper stability. |
| `docs/parity/R_SYNC.md` | Human record of the R pin and laguna verification. |
| `tests/test_r_template_mapper.py` | Done-when over 7 fixtures, folding, report, negative cases. |
| `tests/test_isa_entry_link_rules.py` | `test_server` tests: pickers, prefill, note, add-connection. |
| `tests/test_pims_project.py` | `test_server` test: Save project info keeps v7 metadata. |
| `tests/test_analysis_boolean_clamp.py` | `test_server` test: Boolean module clamps `max_nodes` to `[4, 12]`. |
| `tests/test_link_rules_e2e.py` | Playwright e2e for prefill + off-rule note. |

**Modified**
| Path | Change |
|---|---|
| `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` | Version 1.13.0 (Task 1); MANUAL link-rules text (Task 13). |
| `sespy/data_structure.py` | Schema v7 (Task 2); `_CONN_TYPES` 11 pairs + comment (Task 4). |
| `sespy/persistent_storage.py` | Description check (Task 2); `log_off_rule_links` call (Task 3). |
| `sespy/constants.py` | `RuleTarget`, `AdjacencyRule`, `DAPSIWRM_ADJACENCY_RULES` (Task 3). |
| `sespy/translations/core.json` | `entry.off_rule_link` (Task 3), `entry.choose_element` (Task 9). |
| `sespy/connection_scorer.py`, `sespy/claude_backend.py`, `sespy/wizard.py` | 11 pairs, R→S polarity branch, prompt (Task 4). |
| `sespy/excel_import.py` | Description, Kumu Label, type aliases, Measure (Task 7). |
| `sespy/modules/pims_project.py` | `dataclasses.replace` (Task 8). |
| `sespy/modules/isa_data_entry.py` | Empty first choice, prefill effect, off-rule note (Task 9). |
| `sespy/dynamics.py`, `sespy/modules/analysis_boolean.py` | Ceiling + clamp (Task 10). |
| `sespy/network.py` | `governance_gap` docstring (Task 11). |
| `tests/test_data_structure.py`, `tests/test_stakeholders.py`, `tests/test_schema_read_ahead.py` | Schema 6 → `PROJECT_SCHEMA_VERSION`, renames, cosmetic key (Task 2); `_CONN_TYPES` 11 (Task 4). |
| `tests/test_connection_scorer.py`, `tests/test_claude_backend.py` | Topology edits (Task 4). |
| `tests/test_i18n.py` | Key presence (Tasks 3, 9). |
| `tests/test_excel_import.py`, `tests/test_dynamics.py`, `tests/test_network.py` | New cases (Tasks 7, 10, 11). |
| `CHANGELOG.md`, `docs/screenshots/entry.png` | Release (Task 13). |

Commit groups (spec §4 "Commit order"): **C1** = Task 1; **C2** (schema v7 group, atomic) = Task 2; **C3** = Task 3; **C4** (topology group, atomic) = Task 4; **C5** ("the rest", any order, each its own green commit) = Tasks 5–12; release = Task 13; gates = Task 14; merge/tag/deploy = Task 15.

---

### Task 0: Branch

**Files:** none.

- [ ] **Step 1: Create the implementation branch from the spec branch**

```powershell
git switch docs/p1a-design
git log --oneline -1          # expect aadb874 docs(p1a): review round 8 minors (loop converged)
git switch -c feat/p1a-link-rules
git status --short            # expect only LITERATURE/ entries (user's, never staged)
```

- [ ] **Step 2: Confirm the baseline is green**

Run the CI unit command. Expected: `813 passed, 1 skipped` (numbers may differ by a few; zero failures).

---

### Task 1 (C1): Version bump to 1.13.0

**Files:**
- Modify: `sespy/__init__.py:3`, `pyproject.toml:3`, `docs/MANUAL.md:3`
- Test: `tests/test_manual.py::test_manual_version_line_matches_package` (existing)

**Interfaces:** Produces `sespy.__version__ == "1.13.0"` (Task 2's stamping round trips rely on it: a 1.12.3 build would flag its own `1.13.0` stamp as `newer_build`).

- [ ] **Step 1: Edit the three version lines**

`sespy/__init__.py`: `__version__ = "1.12.3"` → `__version__ = "1.13.0"`
`pyproject.toml`: `version = "1.12.3"` → `version = "1.13.0"`
`docs/MANUAL.md`: `**Version 1.12.3 · October 2026**` → `**Version 1.13.0 · October 2026**`

- [ ] **Step 2: Run the manual test**

`micromamba run -n shiny python -m pytest tests/test_manual.py -q` → `7 passed`.

- [ ] **Step 3: Run the CI unit command** → all green.

- [ ] **Step 4: Commit**

```powershell
git add sespy/__init__.py pyproject.toml docs/MANUAL.md
git commit -m @'
chore(release): bump version to 1.13.0 (P1a)

First P1a commit, so no branch round trip ever stamps min_sespy_version
1.13.0 while the build still reports 1.12.3.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 2 (C2, atomic): Schema v7

All of this is ONE commit: bumping the constant turns the schema-6 tests red, and the new fields need the stamping and load handling to round-trip.

**Files:**
- Modify: `sespy/data_structure.py` (line 10-11 imports; line 20 constant; `Element` 86-92; `Connection` 106-114; `_isa_from_dict` 141-159; `ProjectMetadata` 173-188; new `_min_reader_stamp` before `class Project` 311; `Project.to_dict` 333-343)
- Modify: `sespy/persistent_storage.py:115-120` (after the delay check)
- Modify: `tests/test_data_structure.py:17-18,217`; `tests/test_stakeholders.py:1-8,227,243,246,259,364,367,377`; `tests/test_schema_read_ahead.py:46`
- Create: `tests/test_schema_v7.py`

**Interfaces:**
- Consumes: `sespy.__version__ == "1.13.0"` (Task 1); `packaging.version.Version`, `InvalidVersion`.
- Produces:
  - `PROJECT_SCHEMA_VERSION: int = 7`; `SCHEMA_MIN_READER: dict[int, str] = {7: "1.13.0"}`
  - `Element(..., *, r_extra: dict[str, Any] = {})`; `Connection(..., *, description: str = "")`
  - `ProjectMetadata(..., *, origin: str = "", r_template_version: str = "", min_sespy_version: str = "")`
  - `_min_reader_stamp(current: Any, *, newer_build: bool) -> str`
  - `_element_to_dict(e: Element) -> dict[str, Any]`; `_connection_to_dict(c: Connection) -> dict[str, Any]`
  - `Project.to_dict()` — stamps `metadata.min_sespy_version`, omits empty `r_extra`/`description`, never mutates `self.metadata`.

- [ ] **Step 1: Grep for every hard-coded schema 6 before the bump**

Use the Grep tool: pattern `schema_version\D{1,6}6\b|schema_6` over `tests/` and `sespy/` (and `../MosaicSES/tests`). Expected hits only: `tests/test_data_structure.py:17,18,217`, `tests/test_stakeholders.py:227,243,246,259,364,367,377`. If anything else appears, switch it to `PROJECT_SCHEMA_VERSION` in this task too.

- [ ] **Step 2: Write the failing test file `tests/test_schema_v7.py`**

```python
"""P1a — schema v7: Connection.description, Element.r_extra, the three new
ProjectMetadata fields, and the min_sespy_version stamp (spec §4)."""
from __future__ import annotations

import copy
import json
import logging

import pytest

from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    SCHEMA_MIN_READER,
    Connection,
    Element,
    IsaData,
    Project,
    ProjectMetadata,
    _isa_from_dict,
)
from sespy.persistent_storage import project_to_bytes, validate_project_payload

FLOOR = SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]


def _isa() -> IsaData:
    return IsaData(
        elements=[
            Element("P1", "Nutrients", "Pressures",
                    r_extra={"r_type": "pressure", "category": ["a", 1]}),
            Element("M1", "Oxygen", "Marine Processes & Functioning"),
        ],
        connections=[Connection("P1", "M1", polarity="-",
                                description="Nutrients deplete oxygen")],
    )


def _payload(**meta) -> dict:
    return {
        "metadata": {"name": "P", **meta},
        "isa_data": {
            "elements": [
                {"id": "P1", "label": "p", "type": "Pressures"},
                {"id": "M1", "label": "m", "type": "Marine Processes & Functioning"},
            ],
            "connections": [{"source": "P1", "target": "M1", "polarity": "-"}],
        },
    }


# ---- constants -----------------------------------------------------------


def test_schema_min_reader_has_entry_for_current_schema():
    # A future bump without a table entry would make to_dict() raise KeyError.
    assert PROJECT_SCHEMA_VERSION in SCHEMA_MIN_READER
    assert SCHEMA_MIN_READER[7] == "1.13.0"


def test_new_fields_are_keyword_only_with_defaults():
    # MosaicSES constructs these positionally; the new fields must not shift.
    assert Element("A", "a", "Drivers", "d", 4).r_extra == {}
    c = Connection("A", "B", "-", "weak", 2, "short", [])
    assert c.description == ""
    m = ProjectMetadata("n")
    assert (m.origin, m.r_template_version, m.min_sespy_version) == ("", "", "")
    with pytest.raises(TypeError):
        Connection("A", "B", "-", "weak", 2, "short", [], "positional desc")


# ---- round trip ----------------------------------------------------------

def test_round_trip_keeps_description_and_r_extra():
    p = Project(ProjectMetadata(name="R", origin="r_template",
                                r_template_version="2.3"), _isa())
    back = Project.from_dict(json.loads(p.to_json()))
    assert back.isa_data == p.isa_data
    assert back.isa_data.connections[0].description == "Nutrients deplete oxygen"
    assert back.isa_data.elements[0].r_extra == {"r_type": "pressure",
                                                 "category": ["a", 1]}
    assert back.metadata.origin == "r_template"
    assert back.metadata.r_template_version == "2.3"
    assert back.metadata.min_sespy_version == FLOOR


def test_round_trip_through_the_real_upload_path():
    p = Project(ProjectMetadata(name="R"), _isa())
    res = validate_project_payload(json.loads(project_to_bytes(p)))
    assert res.valid, res.errors
    assert not res.project.newer_build     # needs the commit-1 bump to 1.13.0
    assert res.project.isa_data == p.isa_data


def test_empty_description_and_r_extra_are_omitted():
    isa = IsaData([Element("A", "a", "Drivers"), Element("B", "b", "Activities")],
                  [Connection("A", "B")])
    d = Project(ProjectMetadata(), isa).to_dict()
    for el in d["isa_data"]["elements"]:
        assert "r_extra" not in el
        assert list(el) == ["id", "label", "type", "description", "confidence"]
    conn = d["isa_data"]["connections"][0]
    assert "description" not in conn
    assert list(conn) == ["source", "target", "polarity", "strength",
                          "confidence", "delay", "ratings"]


def test_new_metadata_fields_always_serialised():
    meta = Project(ProjectMetadata(), IsaData()).to_dict()["metadata"]
    assert meta["origin"] == "" and meta["r_template_version"] == ""
    assert meta["schema_version"] == PROJECT_SCHEMA_VERSION


def test_v6_file_loads():
    raw = _payload(schema_version=6)
    p = Project.from_dict(raw)
    assert p.newer_build == {}
    assert p.metadata.schema_version == PROJECT_SCHEMA_VERSION
    assert p.isa_data.connections[0].description == ""
    assert p.isa_data.elements[0].r_extra == {}
    assert validate_project_payload(raw).valid


def test_replace_keeps_description_and_r_extra():
    p = Project(ProjectMetadata(), _isa())
    q = p.replace(stakeholders=[]).with_modified_now()
    assert q.isa_data.connections[0].description == "Nutrients deplete oxygen"
    assert q.isa_data.elements[0].r_extra["r_type"] == "pressure"


def test_with_modified_now_keeps_new_metadata_fields():
    p = Project(ProjectMetadata(origin="r_template", r_template_version="2.1",
                                min_sespy_version="1.13.0"), IsaData())
    m = p.with_modified_now().metadata
    assert (m.origin, m.r_template_version, m.min_sespy_version) == \
        ("r_template", "2.1", "1.13.0")


# ---- load tolerance (_isa_from_dict) ------------------------------------

@pytest.mark.parametrize("bad", ["x", 3, ["a"], True])
def test_non_object_r_extra_dropped_with_warning(bad, caplog):
    raw = _payload()["isa_data"]
    raw["elements"][0]["r_extra"] = bad
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        isa = _isa_from_dict(raw)
    assert isa.elements[0].r_extra == {}
    assert any("r_extra" in r.getMessage() for r in caplog.records)


def test_null_or_absent_r_extra_is_silent(caplog):
    raw = _payload()["isa_data"]
    raw["elements"][0]["r_extra"] = None
    with caplog.at_level(logging.WARNING, logger="sespy.data_structure"):
        isa = _isa_from_dict(raw)
    assert [e.r_extra for e in isa.elements] == [{}, {}]
    assert not [r for r in caplog.records if "r_extra" in r.getMessage()]


@pytest.mark.parametrize("given,want", [(None, ""), (7, "7"), (1.5, "1.5"),
                                        ("ok", "ok")])
def test_connection_description_coerced_on_load(given, want):
    raw = _payload()["isa_data"]
    raw["connections"][0]["description"] = given
    assert _isa_from_dict(raw).connections[0].description == want


def test_element_description_none_is_untouched():
    # P1a does not touch Element.description: None still loads as None.
    raw = _payload()["isa_data"]
    raw["elements"][0]["description"] = None
    assert _isa_from_dict(raw).elements[0].description is None


# ---- validation (SESPy upload path) -------------------------------------

@pytest.mark.parametrize("bad", [7, ["x"], {"a": 1}, True])
def test_validation_rejects_non_string_connection_description(bad):
    raw = _payload()
    raw["isa_data"]["connections"][0]["description"] = bad
    res = validate_project_payload(raw)
    assert not res.valid
    assert any("description" in e for e in res.errors)


def test_validation_skips_null_description_and_loads_it_as_empty():
    raw = _payload()
    raw["isa_data"]["connections"][0]["description"] = None
    res = validate_project_payload(raw)
    assert res.valid, res.errors
    assert res.project.isa_data.connections[0].description == ""


def test_validation_does_not_check_element_description():
    raw = _payload()
    raw["isa_data"]["elements"][0]["description"] = 42
    assert validate_project_payload(raw).valid


def test_validation_drops_bad_r_extra_but_loads():
    raw = _payload()
    raw["isa_data"]["elements"][0]["r_extra"] = "oops"
    res = validate_project_payload(raw)
    assert res.valid
    assert res.project.isa_data.elements[0].r_extra == {}


# ---- stamping --------------------------------------------------------------

def test_fresh_project_is_stamped_with_floor():
    d = Project.from_isa(IsaData()).to_dict()
    assert d["metadata"]["min_sespy_version"] == FLOOR


def test_stamp_never_lowered_for_in_memory_project():
    # Built in memory: a LOADED stamp above the running version would set
    # newer_build and take the reset branch instead.
    p = Project(ProjectMetadata(min_sespy_version="99.0.0"), IsaData())
    assert not p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == "99.0.0"


def test_stamp_equal_to_floor_is_kept():
    p = Project(ProjectMetadata(min_sespy_version="1.13.0"), IsaData())
    assert p.to_dict()["metadata"]["min_sespy_version"] == "1.13.0"


def test_older_stamp_is_raised_to_floor():
    p = Project(ProjectMetadata(min_sespy_version="1.0.0"), IsaData())
    assert p.to_dict()["metadata"]["min_sespy_version"] == "1.13.0"


@pytest.mark.parametrize("bad", [13, 13.0, None, True, "", "not-a-version"])
def test_unparsable_or_non_string_stamp_is_replaced(bad):
    p = Project.from_dict(_payload(min_sespy_version=bad))
    assert not p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


def test_int_stamp_reaches_metadata_and_is_replaced():
    # Version(13) raises TypeError, not InvalidVersion: the isinstance guard
    # must run first.
    p = Project.from_dict(_payload(min_sespy_version=13))
    assert p.metadata.min_sespy_version == 13
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR


def test_newer_build_stamp_is_reset_on_save():
    p = Project.from_dict(_payload(schema_version=PROJECT_SCHEMA_VERSION + 1,
                                   min_sespy_version="99.0.0"))
    assert p.newer_build
    assert p.to_dict()["metadata"]["min_sespy_version"] == FLOOR
    assert p.metadata.min_sespy_version == "99.0.0"   # raw stamp kept


def test_older_format_copy_reloads_unflagged():
    flagged = Project.from_dict(_payload(min_sespy_version="99.0.0"))
    assert flagged.newer_build
    res = validate_project_payload(json.loads(project_to_bytes(flagged)))
    assert res.valid
    assert res.project.newer_build == {}


def test_to_dict_does_not_mutate_metadata():
    p = Project(ProjectMetadata(min_sespy_version=""), IsaData())
    before = copy.deepcopy(p.metadata)
    p.to_dict()
    assert p.metadata == before


def test_p0b_still_flags_a_v8_file():
    p = Project.from_dict(_payload(schema_version=8))
    assert p.newer_build == {"schema": 8, "schema_max": 7}
```

- [ ] **Step 3: Edit the existing schema-6 tests**

`tests/test_data_structure.py` lines 17-18 (the one test that pins the constant):
```python
def test_schema_version_is_7():
    assert PROJECT_SCHEMA_VERSION == 7
```
`tests/test_data_structure.py:217` (in `test_v5_project_loads_without_ratings`):
```python
    assert restored.metadata.schema_version == PROJECT_SCHEMA_VERSION
```
`tests/test_stakeholders.py` lines 1-8 — add the import:
```python
from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    Communication,
    Engagement,
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)
```
`tests/test_stakeholders.py`: replace `== 6` with `== PROJECT_SCHEMA_VERSION` at lines 227 (`Project.from_dict(raw).metadata.schema_version`), 243 and 364 (`back.metadata.schema_version`), 259 and 377 (`raw["metadata"]["schema_version"]`). Rename line 246 `def test_migrated_v3_saves_as_schema_6_on_disk(tmp_path):` → `def test_migrated_v3_saves_as_current_schema_on_disk(tmp_path):` and line 367 `def test_migrated_v4_saves_as_schema_6_on_disk(tmp_path):` → `def test_migrated_v4_saves_as_current_schema_on_disk(tmp_path):`.

`tests/test_schema_read_ahead.py:46` (cosmetic: `r_extra` is now a known key, so the "unknown key" example changes):
```python
    raw["isa_data"]["elements"][0]["future_field"] = {"category": "x"}
```

- [ ] **Step 4: Run the new tests to see them fail**

`micromamba run -n shiny python -m pytest tests/test_schema_v7.py -q`
Expected: collection ERROR `ImportError: cannot import name 'SCHEMA_MIN_READER' from 'sespy.data_structure'`.

- [ ] **Step 5: Implement in `sespy/data_structure.py`**

Imports (lines 10-11): add `import copy` before `import json`:
```python
import copy
import json
import logging
```

Line 20, replace `PROJECT_SCHEMA_VERSION = 6` with:
```python
PROJECT_SCHEMA_VERSION = 7

# Oldest SESPy release that reads each schema without dropping data.
# Project.to_dict() stamps metadata.min_sespy_version from this table, so a
# schema bump must add an entry (guarded by tests/test_schema_v7.py).
SCHEMA_MIN_READER: dict[int, str] = {7: "1.13.0"}
```

`Element` (after `confidence: int = 3`):
```python
    confidence: int = 3
    # Opaque passthrough for fields SESPy has no column for (R template
    # extras, r_type, r_kind). Serialised only when non-empty (schema v7).
    r_extra: dict[str, Any] = field(default_factory=dict, kw_only=True)
```

`Connection` (after `ratings`):
```python
    ratings: list["Rating"] = field(default_factory=list)
    # Free-text rationale (R template connection descriptions, Excel
    # description/rationale columns). Serialised only when non-empty (v7).
    description: str = field(default="", kw_only=True)
```

Replace the whole `_isa_from_dict` (lines 141-159) and add the two serialisers right after it:
```python
def _isa_from_dict(raw: dict[str, Any]) -> IsaData:
    # Unknown element keys (fields a newer SESPy adds) are dropped, as for
    # connections below, instead of raising TypeError in Element(**e).
    el_keys = {f.name for f in fields(Element)} - {"r_extra"}
    elements = []
    for e in raw.get("elements", []):
        el_fields = {k: v for k, v in e.items() if k in el_keys}
        r_extra = e.get("r_extra")
        if r_extra is None:                 # absent or null: silently {}
            r_extra = {}
        elif not isinstance(r_extra, dict):
            # Opaque passthrough data: never fatal, but say it was lost.
            _log.warning(
                "element %r: r_extra is %s, not an object; dropped",
                e.get("id"), type(r_extra).__name__,
            )
            r_extra = {}
        elements.append(Element(**el_fields, r_extra=dict(r_extra)))
    conn_keys = {f.name for f in fields(Connection)} - {"ratings", "description"}
    rating_keys = {f.name for f in fields(Rating)}
    connections = []
    for c in raw.get("connections", []):
        ratings = [
            Rating(**{k: v for k, v in r.items() if k in rating_keys})
            for r in (c.get("ratings") or [])
        ]
        conn_fields = {k: v for k, v in c.items() if k in conn_keys}
        desc = c.get("description")
        if desc is None:
            desc = ""
        elif not isinstance(desc, str):
            desc = str(desc)
        connections.append(
            Connection(ratings=ratings, description=desc, **conn_fields))
    return IsaData(elements=elements, connections=connections)


def _element_to_dict(e: Element) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": e.id, "label": e.label, "type": e.type,
        "description": e.description, "confidence": e.confidence,
    }
    if e.r_extra:                       # omitted when empty: v6 element shape
        d["r_extra"] = copy.deepcopy(e.r_extra)
    return d


def _connection_to_dict(c: Connection) -> dict[str, Any]:
    d: dict[str, Any] = {
        "source": c.source, "target": c.target, "polarity": c.polarity,
        "strength": c.strength, "confidence": c.confidence, "delay": c.delay,
        "ratings": [asdict(r) for r in c.ratings],
    }
    if c.description:                   # omitted when empty: v6 connection shape
        d["description"] = c.description
    return d
```

`ProjectMetadata` (after `schema_version: int = PROJECT_SCHEMA_VERSION`, before `@staticmethod`):
```python
    schema_version: int = PROJECT_SCHEMA_VERSION
    # Schema v7, always serialised. origin: e.g. "r_template".
    # r_template_version: R's metadata.version. min_sespy_version: stamped
    # by Project.to_dict() (see _min_reader_stamp), never by hand.
    origin: str = field(default="", kw_only=True)
    r_template_version: str = field(default="", kw_only=True)
    min_sespy_version: str = field(default="", kw_only=True)
```

Immediately before `@dataclass` / `class Project:` (line 311), insert:
```python
def _min_reader_stamp(current: Any, *, newer_build: bool) -> str:
    """The `min_sespy_version` that `Project.to_dict()` writes.

    Normally the higher of `current` and SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]
    (compared with packaging.version), so it is never lowered. A stamp that
    is not a string or not a valid version is replaced by the floor. When the
    project came from a newer build (`newer_build`), that build's data is
    already gone, so the stamp is RESET to the floor: otherwise the
    "-older-format" copy would be flagged again on every load.
    """
    # packaging is a declared hard dependency (pyproject.toml); imported
    # here, not at module top, so data_structure stays stdlib-only at import.
    from packaging.version import InvalidVersion, Version

    floor = SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]
    if newer_build or not isinstance(current, str):
        return floor
    try:
        return current if Version(current) >= Version(floor) else floor
    except InvalidVersion:
        return floor
```

In `Project.to_dict` replace the head (lines 333-339) so the method reads:
```python
    def to_dict(self) -> dict[str, Any]:
        # Stamping changes only the output dict, never self.metadata:
        # Project equality includes metadata, and a newer-build object must
        # keep its raw stamp.
        meta = asdict(self.metadata)
        meta["origin"] = self.metadata.origin
        meta["r_template_version"] = self.metadata.r_template_version
        meta["min_sespy_version"] = _min_reader_stamp(
            self.metadata.min_sespy_version, newer_build=bool(self.newer_build))
        return {
            "metadata": meta,
            "isa_data": {
                "elements": [_element_to_dict(e) for e in self.isa_data.elements],
                "connections": [
                    _connection_to_dict(c) for c in self.isa_data.connections
                ],
            },
            "stakeholders": [asdict(s) for s in self.stakeholders],
            "engagements": [asdict(e) for e in self.engagements],
            "communications": [asdict(c) for c in self.communications],
        }
```
(`with_modified_now` and `from_dict` need no change: `ProjectMetadata(**asdict(...))` carries the kw-only fields, and `from_dict` already passes declared metadata keys through.)

- [ ] **Step 6: Implement the description check in `sespy/persistent_storage.py`**

Right after the `delay` check block (after line 120, before `if len(errors) >= 10:`):
```python
            # Schema v7. None/absent is skipped like every optional field;
            # _isa_from_dict turns it into "". Element.description is not
            # validated (it never was), so old files keep loading.
            desc = c.get("description")
            if desc is not None and not isinstance(desc, str):
                errors.append(
                    f"connection[{i}] has invalid description {desc!r} "
                    f"(expected a string)"
                )
```

- [ ] **Step 7: Run the schema tests**

`micromamba run -n shiny python -m pytest tests/test_schema_v7.py tests/test_data_structure.py tests/test_stakeholders.py tests/test_schema_read_ahead.py tests/test_autosave.py tests/test_persistent_storage.py tests/test_recent_projects.py tests/test_templates.py tests/test_qsem_import.py tests/test_excel_import.py -q`
Expected: all pass (≈196 passed, 1 skipped).

- [ ] **Step 8: Run the CI unit command** → green.

- [ ] **Step 9: Commit**

```powershell
git add sespy/data_structure.py sespy/persistent_storage.py tests/test_schema_v7.py tests/test_data_structure.py tests/test_stakeholders.py tests/test_schema_read_ahead.py
git commit -m @'
feat(schema): project schema v7 with min_sespy_version stamp (P1a)

Connection.description and Element.r_extra (keyword-only, serialised only
when non-empty, so native projects keep the v6 shape), ProjectMetadata
origin / r_template_version / min_sespy_version. Project.to_dict() stamps
min_sespy_version from SCHEMA_MIN_READER, never lowering it, and resets it
for a newer-build project's older-format copy. _isa_from_dict tolerates a
bad r_extra or description; validation rejects a non-string connection
description.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 3 (C3): Rule table, `link_rules`, validation logging, R rules fixture, parity test, `entry.off_rule_link`

**Files:**
- Modify: `sespy/constants.py` (imports line 8; append after line 191)
- Create: `sespy/link_rules.py`, `tests/test_link_rules.py`, `tests/parity/test_r_rules_parity.py`, `tests/parity/r_rules/dapsiwrm_connection_rules.R` (copy)
- Modify: `sespy/persistent_storage.py` (imports line 18; return at lines 124-126)
- Modify: `sespy/translations/core.json` (after the `"entry.remove_connection"` block, ≈ line 915)
- Modify: `tests/test_i18n.py` (before `def test_causal_paths_keys_present`, line 205)

**Interfaces:**
- Produces (constants): `RuleTarget(to_type: str, polarity: str, rule_id: str)` (frozen); `AdjacencyRule(targets: tuple[RuleTarget, ...], extension_targets: tuple[RuleTarget, ...])` (frozen); `DAPSIWRM_ADJACENCY_RULES: dict[str, AdjacencyRule]`.
- Produces (link_rules):
  - `classify(from_type: str, to_type: str) -> Literal["canonical","extension","off_rule","untyped"]`
  - `default_polarity(from_type: str, to_type: str) -> str` (`"+"`/`"-"`)
  - `rule_id(from_type: str, to_type: str) -> str | None`
  - `seed_polarity(src_el: Element | None, tgt_el: Element | None) -> str | None`
  - `off_rule_message(from_label: str, from_type: str, to_label: str, to_type: str, translator: Translator | None) -> str`
  - `note_for(src_el: Element | None, tgt_el: Element | None, translator: Translator | None) -> str | None`
  - `log_off_rule_links(project_or_isa: Project | IsaData, *, context: str) -> int`
- Consumes: `DAPSIWRM_ELEMENTS`; `sespy.i18n.t` (function-local only).

- [ ] **Step 1: Copy the R rules fixture**

```powershell
$R = "C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny"
git -C $R rev-parse --short HEAD                 # must print e33faea
git -C $R describe --tags                        # must print v1.29.0
New-Item -ItemType Directory -Force tests\parity\r_rules | Out-Null
Copy-Item "$R\functions\dapsiwrm_connection_rules.R" tests\parity\r_rules\
```

- [ ] **Step 2: Write the failing tests**

`tests/test_link_rules.py`:
```python
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
```

`tests/parity/test_r_rules_parity.py`:
```python
"""P1a — content parity of DAPSIWRM_ADJACENCY_RULES with R's
functions/dapsiwrm_connection_rules.R (v1.29.0 fixture copy).

A hash pin alone would let a hand-copy error pass, so this parses the R
table's `targets`, `extension_targets` and `target_polarities` vectors with
regexes and compares them with the Python table. Rule ids are not in R;
they stay pinned by tests/test_link_rules.py against the spec.
"""
from __future__ import annotations

import re
from pathlib import Path

from sespy.constants import DAPSIWRM_ADJACENCY_RULES

ROOT = Path(__file__).resolve().parents[2]
R_RULES = ROOT / "tests" / "parity" / "r_rules" / "dapsiwrm_connection_rules.R"

# One source block: `  Drivers = list(` or `  "Goods & Benefits" = list(`
# at two-space indent, inside `DAPSIWRM_ADJACENCY_RULES <- list(`.
_BLOCK = re.compile(r'^  (?:"([^"]+)"|(\w+)) = list\($', re.M)


def _vector(body: str, key: str) -> list[str]:
    m = re.search(rf"^\s*{key} = (c\((.*?)\)|character\(0\))", body, re.M | re.S)
    assert m, f"{key} not found"
    return re.findall(r'"([^"]+)"', m.group(2) or "")


def parse_r_rules(text: str) -> dict[str, tuple[dict[str, str], dict[str, str]]]:
    start = text.index("DAPSIWRM_ADJACENCY_RULES <- list(")
    end = text.index("\nget_allowed_targets <- function", start)
    table = text[start:end]
    heads = list(_BLOCK.finditer(table))
    out = {}
    for i, h in enumerate(heads):
        body = table[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(table)]
        # target_polarities may span two lines (the Responses block).
        pol_src = re.search(r"target_polarities = c\((.*?)\),\s*\n", body, re.S).group(1)
        pol = dict(re.findall(r'"([^"]+)"\s*=\s*"([+-])"', pol_src))
        targets = _vector(body, "targets")
        ext = _vector(body, "extension_targets")
        out[h.group(1) or h.group(2)] = ({t: pol[t] for t in targets},
                                         {t: pol[t] for t in ext})
    return out


def _python_table():
    return {src: ({t.to_type: t.polarity for t in r.targets},
                  {t.to_type: t.polarity for t in r.extension_targets})
            for src, r in DAPSIWRM_ADJACENCY_RULES.items()}


def test_parser_sees_all_seven_sources_and_the_two_line_responses_block():
    parsed = parse_r_rules(R_RULES.read_text(encoding="utf-8"))
    assert len(parsed) == 7
    assert parsed["Responses"][0]["Marine Processes & Functioning"] == "+"
    assert parsed["Responses"][1] == {"Responses": "+"}
    assert parsed["Ecosystem Services"][1] == {}


def test_rule_table_matches_r():
    assert _python_table() == parse_r_rules(R_RULES.read_text(encoding="utf-8"))
```

`tests/test_i18n.py` — insert before `def test_causal_paths_keys_present(translations):`:
```python
def test_link_rules_keys_present(translations):
    for key in ("entry.off_rule_link",):
        assert key in translations, key
        for lang in SUPPORTED_LANGUAGES:
            text = translations[key][lang]
            for ph in ("{source}", "{target}", "{source_type}", "{target_type}"):
                assert ph in text, (key, lang, ph)


```

- [ ] **Step 3: Run them to see them fail**

`micromamba run -n shiny python -m pytest tests/test_link_rules.py tests/parity/test_r_rules_parity.py tests/test_i18n.py -q`
Expected: collection ERRORs `ModuleNotFoundError: No module named 'sespy.link_rules'` and `ImportError: cannot import name 'DAPSIWRM_ADJACENCY_RULES' from 'sespy.constants'`; `test_link_rules_keys_present` FAILED (`AssertionError: entry.off_rule_link`).

- [ ] **Step 4: Implement the rule table in `sespy/constants.py`**

After `from __future__ import annotations` (line 8) add:
```python

from dataclasses import dataclass
```
Append at the end of the file (after `normalize_delay`):
```python


# ---------------------------------------------------------------------------
# DAPSI(W)R(M) link rules (P1a). Ported from R v1.29.0
# functions/dapsiwrm_connection_rules.R:26-341 (targets, extension_targets,
# per-pair target_polarities). R's table has no rule ids: they come from R's
# DAPSIWRM_FRAMEWORK_RULES.md ("6-7" = the collapsed GB->D rules, "ExUP" =
# the D->P exogenic-unmanaged-pressure exception). R's per-source
# default_polarity is unreachable (every listed target has its own
# polarity), so it is not ported. There is no Measures entry: Measures fold
# into Responses (M->R is covered by R->R, Rule 14).
# tests/parity/test_r_rules_parity.py pins this table to the R file.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleTarget:
    to_type: str
    polarity: str      # "+" | "-"
    rule_id: str


@dataclass(frozen=True)
class AdjacencyRule:
    targets: tuple[RuleTarget, ...]              # canonical: offered as suggestions
    extension_targets: tuple[RuleTarget, ...]    # valid, never suggested


_MPF = "Marine Processes & Functioning"

DAPSIWRM_ADJACENCY_RULES: dict[str, AdjacencyRule] = {
    "Drivers": AdjacencyRule(
        targets=(RuleTarget("Activities", "+", "1"),),
        extension_targets=(RuleTarget("Pressures", "+", "ExUP"),),
    ),
    "Activities": AdjacencyRule(
        targets=(RuleTarget("Pressures", "+", "2"),),
        extension_targets=(RuleTarget("Activities", "+", "18"),),
    ),
    "Pressures": AdjacencyRule(
        targets=(RuleTarget(_MPF, "-", "3"),),
        extension_targets=(RuleTarget("Pressures", "+", "17"),),
    ),
    _MPF: AdjacencyRule(
        targets=(RuleTarget("Ecosystem Services", "+", "4"),),
        extension_targets=(RuleTarget(_MPF, "+", "16"),),
    ),
    "Ecosystem Services": AdjacencyRule(
        targets=(RuleTarget("Goods & Benefits", "+", "5"),),
        extension_targets=(),
    ),
    "Goods & Benefits": AdjacencyRule(
        targets=(RuleTarget("Drivers", "+", "6-7"),
                 RuleTarget("Responses", "+", "8")),
        extension_targets=(),
    ),
    "Responses": AdjacencyRule(
        targets=(RuleTarget("Drivers", "-", "9"),
                 RuleTarget("Activities", "-", "10"),
                 RuleTarget("Pressures", "-", "11"),
                 RuleTarget(_MPF, "+", "12")),
        extension_targets=(RuleTarget("Responses", "+", "14"),),
    ),
}
```

- [ ] **Step 5: Create `sespy/link_rules.py`**

```python
"""DAPSI(W)R(M) link rules (P1a): classify a (from_type, to_type) pair, seed
its default polarity, and describe off-rule links.

Off-rule links are allowed and warned about, as R does
(`validate_connection(strict = FALSE)`): ISA entry shows a note, and
`persistent_storage.validate_project_payload` logs them through
`log_off_rule_links`. Nothing is ever rejected.

Shiny-free at import: `sespy.i18n` imports `shiny.reactive`, so it is only
imported inside `off_rule_message` when no translator is passed.
`persistent_storage`, the R template mapper and P2's sync script import this
module. tests/test_link_rules.py checks that in a subprocess.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from .constants import DAPSIWRM_ADJACENCY_RULES, DAPSIWRM_ELEMENTS

if TYPE_CHECKING:
    from .data_structure import Element
    from .i18n import Translator

logger = logging.getLogger(__name__)

LinkClass = Literal["canonical", "extension", "off_rule", "untyped"]

_KNOWN_TYPES = frozenset(DAPSIWRM_ELEMENTS)
_LOG_PAIRS = 5     # how many off-rule pairs one log line names


def _target(from_type: str, to_type: str):
    rule = DAPSIWRM_ADJACENCY_RULES.get(from_type)
    if rule is None:
        return None, None
    for kind, targets in (("canonical", rule.targets),
                          ("extension", rule.extension_targets)):
        for t in targets:
            if t.to_type == to_type:
                return kind, t
    return None, None


def classify(from_type: str, to_type: str) -> LinkClass:
    """"untyped" when either type is "" or not one of the 7
    DAPSIWRM_ELEMENTS (QSEM themes, a legacy "Measures"); untyped pairs are
    never flagged. Otherwise canonical, extension or off_rule."""
    if from_type not in _KNOWN_TYPES or to_type not in _KNOWN_TYPES:
        return "untyped"
    kind, _ = _target(from_type, to_type)
    return kind or "off_rule"


def default_polarity(from_type: str, to_type: str) -> str:
    """The pair's rule polarity, else "+" (what R's
    get_rule_default_polarity returns in practice)."""
    _, t = _target(from_type, to_type)
    return t.polarity if t is not None else "+"


def rule_id(from_type: str, to_type: str) -> str | None:
    _, t = _target(from_type, to_type)
    return t.rule_id if t is not None else None


def seed_polarity(src_el: Element | None, tgt_el: Element | None) -> str | None:
    """Polarity the ISA entry form pre-fills: None while either endpoint is
    missing or both are the same element, else default_polarity()."""
    if src_el is None or tgt_el is None or src_el.id == tgt_el.id:
        return None
    return default_polarity(src_el.type, tgt_el.type)


def off_rule_message(from_label: str, from_type: str, to_label: str,
                     to_type: str, translator: Translator | None) -> str:
    """The `entry.off_rule_link` text. Type placeholders take the raw
    canonical type names (as the entry form's type dropdown shows them)."""
    fmt = dict(source=from_label, target=to_label,
               source_type=from_type, target_type=to_type)
    if translator is not None:
        return translator.t("entry.off_rule_link", **fmt)
    from .i18n import t      # function-local: keeps this module Shiny-free
    return t("entry.off_rule_link", **fmt)


def note_for(src_el: Element | None, tgt_el: Element | None,
             translator: Translator | None) -> str | None:
    """The ISA entry warning for the chosen pair, or None (missing endpoint,
    same element, or a pair that is not off-rule)."""
    if src_el is None or tgt_el is None or src_el.id == tgt_el.id:
        return None
    if classify(src_el.type, tgt_el.type) != "off_rule":
        return None
    return off_rule_message(src_el.label, src_el.type, tgt_el.label,
                            tgt_el.type, translator)


def log_off_rule_links(project_or_isa: Any, *, context: str) -> int:
    """Count the off-rule links of a Project or IsaData. Logs one WARNING on
    `sespy.link_rules` only when the count is above 0 (a clean project logs
    nothing). Returns the count."""
    isa = getattr(project_or_isa, "isa_data", project_or_isa)
    types = {el.id: el.type for el in isa.elements}
    off: list[str] = []
    for c in isa.connections:
        ft, tt = types.get(c.source, ""), types.get(c.target, "")
        if classify(ft, tt) == "off_rule":
            off.append(f"{c.source}->{c.target} ({ft} -> {tt})")
    if off:
        more = f" (+{len(off) - _LOG_PAIRS} more)" if len(off) > _LOG_PAIRS else ""
        logger.warning("%s: %d off-rule link(s): %s%s", context, len(off),
                       "; ".join(off[:_LOG_PAIRS]), more)
    return len(off)
```

- [ ] **Step 6: Wire logging into `sespy/persistent_storage.py`**

Imports (line 18):
```python
from .data_structure import Project
from .link_rules import log_off_rule_links
```
Replace the last three lines of `validate_project_payload` (124-126):
```python
    if errors:
        return ValidationResult(False, errors)
    project = Project.from_dict(raw)
    # Off-rule links are accepted (as R's validate_connection(strict=FALSE))
    # and logged once per validation call. Not in Project.from_dict, which
    # MosaicSES calls once per compartment.
    log_off_rule_links(project, context="validate_project_payload")
    return ValidationResult(True, [], project)
```

- [ ] **Step 7: Add `entry.off_rule_link` to `sespy/translations/core.json`**

Use the Edit tool with this exact anchor (the end of the `"entry.remove_connection"` block, unique):
```
      "el": "Αφαίρεση επιλεγμένης σύνδεσης"
    },
```
Replace with:
```
      "el": "Αφαίρεση επιλεγμένης σύνδεσης"
    },
    "entry.off_rule_link": {
      "en": "{source} ({source_type}) → {target} ({target_type}) is not a standard DAPSI(W)R(M) link. You can still add it.",
      "es": "{source} ({source_type}) → {target} ({target_type}) no es una conexión DAPSI(W)R(M) estándar. Aun así, puede añadirla.",
      "fr": "{source} ({source_type}) → {target} ({target_type}) n'est pas une connexion DAPSI(W)R(M) standard. Vous pouvez quand même l'ajouter.",
      "de": "{source} ({source_type}) → {target} ({target_type}) ist keine Standardverbindung in DAPSI(W)R(M). Sie können sie trotzdem hinzufügen.",
      "lt": "{source} ({source_type}) → {target} ({target_type}) nėra standartinis DAPSI(W)R(M) ryšys. Vis tiek galite jį pridėti.",
      "pt": "{source} ({source_type}) → {target} ({target_type}) não é uma conexão DAPSI(W)R(M) padrão. Ainda assim, pode adicioná-la.",
      "it": "{source} ({source_type}) → {target} ({target_type}) non è una connessione DAPSI(W)R(M) standard. Puoi comunque aggiungerla.",
      "no": "{source} ({source_type}) → {target} ({target_type}) er ikke en standard DAPSI(W)R(M)-forbindelse. Du kan likevel legge den til.",
      "el": "Η σύνδεση {source} ({source_type}) → {target} ({target_type}) δεν είναι τυπική σύνδεση DAPSI(W)R(M). Μπορείτε να την προσθέσετε παρ' όλα αυτά."
    },
```
Do NOT reformat the file with `json.dump` (its mixed one-line/multi-line layout would turn into a huge diff).

- [ ] **Step 8: Run the tests**

`micromamba run -n shiny python -m pytest tests/test_link_rules.py tests/parity/test_r_rules_parity.py tests/test_i18n.py tests/test_schema_v7.py tests/test_persistent_storage.py -q` → all pass (≈143).

- [ ] **Step 9: Run the CI unit command** → green. (You will see `sespy.link_rules` WARNING lines for `minimal_demo.json`/`offshore_wind.json` in captured logs from template tests — expected.)

- [ ] **Step 10: Commit**

```powershell
git add sespy/constants.py sespy/link_rules.py sespy/persistent_storage.py sespy/translations/core.json tests/test_link_rules.py tests/test_i18n.py tests/parity/test_r_rules_parity.py tests/parity/r_rules/dapsiwrm_connection_rules.R
git commit -m @'
feat(rules): DAPSI(W)R(M) link-rule table and link_rules module (P1a)

Port of R v1.29.0 dapsiwrm_connection_rules.R: canonical and extension
targets with per-pair polarity and the framework rule ids. link_rules
classifies pairs (untyped never flagged), seeds polarity, words the
off-rule note (entry.off_rule_link, 9 languages) and logs off-rule links
once per validate_project_payload call. Allow-and-warn, as R. The .R file
is a test fixture; a regex content-parity test pins the table to it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 4 (C4, atomic): Topology group — `_CONN_TYPES` 11 pairs, Claude prompt, scorer R→S branch

ONE commit: `test_all_10_types_yield_high_confidence_suggestions` derives its expected set from `_CONN_TYPES`, so splitting this group turns the gate red.

**Files:**
- Modify: `sespy/data_structure.py:64-77`; `sespy/connection_scorer.py` (docstring line 3; 70-75; 155-169; after 195; 349, 356, 374); `sespy/wizard.py:74`; `sespy/claude_backend.py:144-146,224`
- Modify: `tests/test_data_structure.py:148,159-173,184`; `tests/test_connection_scorer.py:29-38,124-133,476-529`; `tests/test_claude_backend.py:86-90,331`
- Modify: `tests/test_link_rules.py` (append), `tests/test_connection_scorer.py` (append)

**Interfaces:**
- Consumes: `DAPSIWRM_ADJACENCY_RULES` (Task 3), `classify`.
- Produces: `_CONN_TYPES` with `("responses", "states", "responses_states")` at index 8; `_VALID_TYPE_PAIRS` of size 11; `detect_polarity(from_name, to_name, "responses", "states") -> "+"|"-"`; `_SYSTEM_PROMPT` containing `(11 valid)` and `R->S`. `connection_keywords.json` is **not** changed (no `responses_states` key).

- [ ] **Step 1: Grep every "10 types" reference**

Grep tool, pattern `\b10\b` in `sespy/connection_scorer.py sespy/wizard.py sespy/data_structure.py sespy/claude_backend.py`, and `all_10|10 valid|10 type|10 connection|the 10` in `tests/`. Expected code hits: `connection_scorer.py:3,74,166,349,356,374`, `wizard.py:74`, `data_structure.py:64`, `claude_backend.py:144,224` (`:174` is "30/30/30/10", unrelated; `wizard.py:13,33,47` and `data_structure.py:24` are wizard *steps* 4-10, unrelated; `connection_scorer.py:258` is about the 7 from-slugs and stays). Test hits: `test_data_structure.py:148,159,184`, `test_connection_scorer.py:29-30,131,476,478`, `test_claude_backend.py:86-87,331`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_link_rules.py`:
```python


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
```

Append to `tests/test_connection_scorer.py`:
```python


# ---------------------------------------------------------------------------
# P1a: responses_states (R->MPF) — flat relevance + ported polarity branch
# ---------------------------------------------------------------------------

def test_r_to_mpf_relevance_is_flat_05():
    """R has no relevance keywords for R->MPF and scores it at a flat 0.5
    (connection_generator.R:375); SESPy invents none."""
    from sespy.connection_scorer import _KW, calculate_relevance
    assert "responses_states" not in _KW["connection_types"]
    assert calculate_relevance("Seagrass restoration", "Seagrass meadow extent",
                               "responses", "states") == 0.5


@pytest.mark.parametrize("to_label,want", [
    ("Hypoxia extent", "-"),          # negative-sounding target: reduces a bad state
    ("Fish stock recovery", "+"),     # positive-sounding target: increases a good state
    ("Seabed sediment", "+"),         # neither: default "+"
])
def test_detect_polarity_responses_to_states(to_label, want):
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Marine protected area", to_label,
                           "responses", "states") == want
```

Edit existing tests:

`tests/test_data_structure.py:148`: `assert len(_CONN_TYPES) == 10` → `assert len(_CONN_TYPES) == 11`.
`tests/test_data_structure.py:159-173` (`test_conn_types_exact_entries`): docstring becomes
```python
    """The 11 type-pairs are the canonical DAPSI(W)R(M) directed edges,
    in a fixed order (R->S was appended after R->A in P1a)."""
```
and in `expected`, after `("responses", "activities", "responses_activities"),` insert `("responses", "states", "responses_states"),`.
`tests/test_data_structure.py:184`: `assert len(_VALID_TYPE_PAIRS) == 10` → `== 11`.

`tests/test_connection_scorer.py:29-30`: rename + new docstring (set stays at 10 keys):
```python
def test_keyword_json_has_10_keys_for_the_11_pairs():
    """Set-equality on connection_types keys against the 10 keyword slugs.

    Stays at 10 although _CONN_TYPES has 11 pairs: R has no relevance
    keywords for responses_states (R->MPF) and scores it at a flat 0.5
    (connection_generator.R:375), so SESPy invents none (spec §3.3)."""
```
`tests/test_connection_scorer.py:129-131` (docstring of `test_relevance_unknown_pair_returns_05`) — replace the sentences "Pins the defensive path ... fires on coding errors." with:
```python
    Pins the defensive path so a future removal is a deliberate decision.
    It is also the normal path for responses_states (R->MPF), which has no
    keywords by design (see test_r_to_mpf_relevance_is_flat_05).
```
`tests/test_connection_scorer.py:476-479`: rename and fix the docstring head:
```python
def test_every_keyword_type_yields_high_confidence_suggestions():
    """Designed-to-overlap reference fixture: ≥2 elements per type with
    keyword-rich labels. Assert that for each of the 10 keyword-scored
    connection types (all _CONN_TYPES except responses_states, which R
    scores at a flat 0.5 and so can never reach 0.6),
```
(the rest of the docstring — "at least one suggestion has confidence >= 0.6 ..." — is unchanged)
and at line 528:
```python
    # responses_states: no keywords, flat 0.5 relevance (R parity).
    expected = {key for _, _, key in _CONN_TYPES} - {"responses_states"}
```

`tests/test_claude_backend.py:86-90`:
```python
def test_system_prompt_lists_all_11_directions():
    """Rule 1 lists the 11 valid type-pair directions verbatim."""
    for direction in ["D->A", "A->P", "P->S", "S->I", "I->W",
                      "R->P", "R->D", "R->A", "R->S", "W->D", "W->R"]:
        assert direction in _SYSTEM_PROMPT
    assert "(11 valid)" in _SYSTEM_PROMPT
```
`tests/test_claude_backend.py:331`: `"""States -> Drivers is not in the 10 valid type-pair directions."""` → `... the 11 valid ...`.

- [ ] **Step 3: Run to see them fail**

`micromamba run -n shiny python -m pytest tests/test_link_rules.py tests/test_connection_scorer.py tests/test_claude_backend.py tests/test_data_structure.py -q`
Expected FAILs: `test_conn_types_set_equal_to_rule_table_canonical_targets` (set missing `('Responses', 'Marine Processes & Functioning')`), `test_rule_based_scorer_suggests_r_to_mpf`, `test_claude_backend_accepts_r_to_mpf` (`invalid_pair` == 1), `test_detect_polarity_responses_to_states[Hypoxia extent--]` (`'+' == '-'`), `test_system_prompt_lists_all_11_directions`, the three `test_data_structure` length/order tests.

- [ ] **Step 4: Implement**

`sespy/data_structure.py:64-65` comment, replace:
```python
# 10 type-pairs as (from_slug, to_slug, conn_type_key) 3-tuples.
# Iteration order matches DAPSI(W)R(M) layer flow.
```
with:
```python
# 11 type-pairs as (from_slug, to_slug, conn_type_key) 3-tuples: the
# canonical targets of constants.DAPSIWRM_ADJACENCY_RULES (the single source
# of truth; tests/test_link_rules.py asserts set equality). Kept as an
# explicit literal so the order (which the scorer's output follows) is fixed
# and readable. responses_states (R->MPF, Rule 12) was added in P1a after
# responses_activities, so the existing pairs keep their order.
```
and in the list, after `("responses", "activities", "responses_activities"),` add:
```python
    ("responses", "states", "responses_states"),
```

`sespy/connection_scorer.py`:
- line 3: `Pure-Python rule-based scoring across all 10 DAPSI(W)R(M) connection` → `... all 11 DAPSI(W)R(M) connection`
- lines 72-74 (in `calculate_relevance` docstring) replace
```
    Returns 0.5 if the (from_slug, to_slug) pair is missing from the
    keyword JSON (defensive default at R line 376; schema test pins all
    10 pairs present so 0.5 doesn't fire in normal operation).
```
with
```
    Returns 0.5 if the (from_slug, to_slug) pair is missing from the
    keyword JSON (R line 376). That is the normal path for responses_states
    (R->MPF): R has no keywords for it and scores it at a flat 0.5, so the
    keyword JSON deliberately has no responses_states key (10 keys for the
    11 pairs).
```
- in `detect_polarity` docstring, after `      - ("responses", "pressures"): always "-" (R line 117).` add `      - ("responses", "states"): to-flag-aware, default "+" (R 122-130).`; and replace lines 163-169 (`R's KB-lookup branch ... dispatch-table prose).`) with:
```
    R's KB-lookup branch (R 63-75) and ML-scoring branch are not
    ported per the rule-based-only scope decision. The
    ("responses", "states") branch (R 122-130) is ported since P1a made
    R->MPF a canonical pair in _CONN_TYPES.
```
- after the `("responses", "pressures")` branch (`return "-"`, line 195) insert:
```python

    # ("responses", "states") — R lines 122-130.
    if from_slug == "responses" and to_slug == "states":
        if to_is_negative:
            return "-"  # reduces a bad state
        if to_is_positive:
            return "+"  # increases a good state
        return "+"  # default: responses improve states
```
- line 349: `"""SP3 contract: rule-based scoring across all 10 connection types.` → `... all 11 connection types.`
- line 356: `Returns a flat list of <=150 (10 types x 15 cap) ConnectionSuggestions` → `Returns a flat list of <=165 (11 types x 15 cap) ConnectionSuggestions`
- line 374: `# 2. For each of the 10 connection-type pairs, generate suggestions.` → `# 2. For each of the 11 connection-type pairs, generate suggestions.`

`sespy/wizard.py:74`: `"""SP3 contract: rule-based scoring across all 10 connection types.` → `... all 11 connection types.`

`sespy/claude_backend.py:144-146`:
```
1. Allowed type-pair directions (11 valid):
   D->A, A->P, P->S, S->I, I->W,
   R->P, R->D, R->A, R->S, W->D, W->R.
```
`sespy/claude_backend.py:224`: `  - {"source": "a1", "target": "d1", ...} - A->D is not in the 10` → `... is not in the 11`. (The tool schema's `maxItems: 150` is a separate limit — unchanged.)

- [ ] **Step 5: Run the tests**

`micromamba run -n shiny python -m pytest tests/test_link_rules.py tests/test_connection_scorer.py tests/test_claude_backend.py tests/test_data_structure.py tests/test_wizard.py -q` → all pass (≈204).

- [ ] **Step 6: Run the CI unit command** → green.

- [ ] **Step 7: Commit**

```powershell
git add sespy/data_structure.py sespy/connection_scorer.py sespy/wizard.py sespy/claude_backend.py tests/test_data_structure.py tests/test_connection_scorer.py tests/test_claude_backend.py tests/test_link_rules.py
git commit -m @'
feat(rules): Responses -> MPF is a canonical pair (11 topology pairs) (P1a)

_CONN_TYPES gains responses_states after responses_activities and is pinned
set-equal to the rule table's canonical targets. Both suggestion backends
now propose R->MPF: the Claude prompt lists 11 directions, and the scorer
ports R's R->S polarity branch and, like R, scores the pair at a flat 0.5
relevance (no keywords invented). Extension pairs are never suggested.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 5 (C5): R template mapper + the 7 template fixtures

**Files:**
- Create: `sespy/r_template_mapper.py`, `tests/test_r_template_mapper.py`, `tests/parity/r_templates/*_SES_Template.json` (7 copies)

**Interfaces:**
- Consumes: `Element`, `Connection`, `IsaData`, `Project`, `ProjectMetadata` with v7 fields (Task 2); `classify` (Task 3).
- Produces:
  - `@dataclass(frozen=True) class ConversionReport: key: str; counts_by_type: dict[str, int]; link_count: int; folded_measures: tuple[str, ...]; off_rule_links: tuple[tuple[str, str], ...]; type_mismatches: tuple[str, ...]; extra_fields: tuple[str, ...]; template_meta: dict[str, Any]`
  - `convert_r_template(raw: dict, *, key: str) -> tuple[Project, ConversionReport]`
  - `load_r_template(path: Path | str) -> dict`

- [ ] **Step 1: Copy the 7 fixtures (not the `_backup` file)**

```powershell
$R = "C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny"
git -C $R rev-parse --short HEAD                 # e33faea
New-Item -ItemType Directory -Force tests\parity\r_templates | Out-Null
foreach ($k in "Aquaculture","Caribbean","ClimateChange","Fisheries","OffshoreWind","Pollution","Tourism") {
    Copy-Item "$R\data\${k}_SES_Template.json" tests\parity\r_templates\
}
(Get-ChildItem tests\parity\r_templates).Count   # 7
```

- [ ] **Step 2: Write the failing test file `tests/test_r_template_mapper.py`**

```python
"""P1a — R template mapper (spec §1 done-when, §5, §6)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sespy.constants import DAPSIWRM_ELEMENTS
from sespy.persistent_storage import project_to_bytes, validate_project_payload
from sespy.r_template_mapper import (
    ConversionReport,
    convert_r_template,
    load_r_template,
)

FIXTURES = Path(__file__).resolve().parent / "parity" / "r_templates"
KEYS = ["Aquaculture", "Caribbean", "ClimateChange", "Fisheries",
        "OffshoreWind", "Pollution", "Tourism"]


def _fixture(key: str) -> dict:
    return load_r_template(FIXTURES / f"{key}_SES_Template.json")


def _edge(c) -> tuple:
    return (c.source, c.target, c.polarity, c.strength, c.confidence, c.description)


# ---- done-when (spec §1) -------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_r_template_survives_real_save_load(key):
    raw = _fixture(key)
    project, report = convert_r_template(raw, key=key)

    res = validate_project_payload(json.loads(project_to_bytes(project)))
    assert res.valid, res.errors
    loaded = res.project
    assert not loaded.newer_build

    expected = [(c["from_id"], c["to_id"], c["polarity"], c["strength"],
                 c["confidence"], c["description"]) for c in raw["connections"]]
    got = [_edge(c) for c in loaded.isa_data.connections]
    assert len(got) == len(expected)              # nothing dropped or merged
    assert set(got) == set(expected)
    assert report.link_count == len(expected)

    fw = raw["dapsiwrm_framework"]
    assert len(loaded.isa_data.elements) == sum(len(v) for v in fw.values())
    n_resp = len(fw.get("responses", [])) + len(fw.get("measures", []))
    assert sum(e.type == "Responses" for e in loaded.isa_data.elements) == n_resp
    assert report.counts_by_type.get("Responses", 0) == n_resp

    assert report.off_rule_links == ()
    assert report.type_mismatches == ()
    assert loaded.metadata.origin == "r_template"
    assert loaded.metadata.r_template_version == raw["metadata"]["version"]


def test_fixture_link_total_is_read_from_the_files():
    # The spec quotes 320 at v1.29.0; the done-when test never hard-codes it.
    assert sum(len(_fixture(k)["connections"]) for k in KEYS) == 320


# ---- folding, r_type, extras ----------------------------------------------

def test_measures_fold_into_responses_with_r_kind():
    raw = _fixture("Fisheries")
    project, report = convert_r_template(raw, key="Fisheries")
    measure_ids = [m["id"] for m in raw["dapsiwrm_framework"]["measures"]]
    assert measure_ids and report.folded_measures == tuple(measure_ids)
    by_id = {e.id: e for e in project.isa_data.elements}
    for mid in measure_ids:
        assert by_id[mid].type == "Responses"
        assert by_id[mid].r_extra["r_kind"] == "measure"
    for r in raw["dapsiwrm_framework"]["responses"]:
        assert "r_kind" not in by_id[r["id"]].r_extra
    assert "Measures" not in {e.type for e in project.isa_data.elements}


def test_r_type_kept_only_when_the_element_has_one():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    for cat, items in raw["dapsiwrm_framework"].items():
        for item in items:
            el = by_id[item["id"]]
            if "type" in item:
                assert el.r_extra["r_type"] == item["type"]
            else:
                assert "r_type" not in el.r_extra
    assert "type" in report.extra_fields and "r_type" not in report.extra_fields


def test_type_comes_from_the_category_never_the_element():
    raw = _fixture("Caribbean")
    project, _ = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    for p in raw["dapsiwrm_framework"]["pressures"]:
        assert by_id[p["id"]].type == "Pressures"


def test_every_r_element_field_is_kept():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    by_id = {e.id: e for e in project.isa_data.elements}
    names = set()
    for items in raw["dapsiwrm_framework"].values():
        for item in items:
            el = by_id[item["id"]]
            assert el.label == item["name"] and el.confidence == 3
            assert el.description == item.get("description", "")
            for f, v in item.items():
                if f not in ("id", "name", "description", "type"):
                    assert el.r_extra[f] == v
                    names.add(f)
    assert set(report.extra_fields) == names | {"type"}
    assert list(report.extra_fields) == sorted(report.extra_fields)


# ---- report and metadata --------------------------------------------------

def test_report_contents_fisheries():
    raw = _fixture("Fisheries")
    _, report = convert_r_template(raw, key="Fisheries")
    assert isinstance(report, ConversionReport)
    assert report.key == "Fisheries"
    assert set(report.counts_by_type) <= set(DAPSIWRM_ELEMENTS)
    assert all(v > 0 for v in report.counts_by_type.values())
    assert sum(report.counts_by_type.values()) == sum(
        len(v) for v in raw["dapsiwrm_framework"].values())
    assert report.extra_fields == ("type",)
    meta = raw["metadata"]
    assert report.template_meta == {
        "complexity": raw["complexity"],
        "version": meta["version"], "created_date": meta["created_date"],
        "source": meta["source"], "applicable_regions": meta["applicable_regions"],
        "regional_context": raw["regional_context"],
    }


def test_metadata_from_the_r_file_and_no_clock():
    raw = _fixture("Fisheries")
    p1, _ = convert_r_template(raw, key="Fisheries")
    p2, _ = convert_r_template(copy.deepcopy(raw), key="Fisheries")
    m = p1.metadata
    assert m.name == raw["template_name"]
    assert m.description == raw["template_description"]
    assert m.regional_sea == raw["regional_context"]["regional_sea"]
    assert m.created_at == m.modified_at == raw["metadata"]["created_date"]
    assert p1.to_dict() == p2.to_dict()          # deterministic


def test_caribbean_has_no_regional_sea_and_keeps_usage_notes():
    raw = _fixture("Caribbean")
    project, report = convert_r_template(raw, key="Caribbean")
    assert project.metadata.regional_sea == ""
    assert report.template_meta["usage_notes"] == raw["usage_notes"]
    assert "regional_sea" not in report.template_meta["regional_context"]


def test_connection_fields_and_delay():
    raw = _fixture("Aquaculture")
    project, _ = convert_r_template(raw, key="Aquaculture")
    assert {c.delay for c in project.isa_data.connections} == {"immediate"}


# ---- synthetic inputs: aliases, defaults, mismatches, failure modes ---------

def _tiny() -> dict:
    return {
        "template_name": "Tiny", "template_description": "d",
        "metadata": {"version": "1.0"},
        "dapsiwrm_framework": {
            "pressures": [{"id": "P1", "name": "p", "description": "", "type": "pressure"}],
            "marine_processes": [{"id": "S1", "name": "s", "description": ""}],
            "responses": [{"id": "R1", "name": "r"}],
            "measures": [{"id": "M1", "name": "m"}],
        },
        "connections": [{
            "from_id": "P1", "to_id": "S1", "from_type": "pressure",
            "to_type": "state", "polarity": "-", "strength": "strong",
            "confidence": 4, "description": "x",
        }],
    }


def test_legacy_category_aliases_are_accepted():
    t = _tiny()
    fw = t["dapsiwrm_framework"]
    fw["states"] = fw.pop("marine_processes")
    fw["impacts"] = [{"id": "E1", "name": "e"}]
    fw["welfare"] = [{"id": "G1", "name": "g"}]
    project, report = convert_r_template(t, key="Tiny")
    types = {e.id: e.type for e in project.isa_data.elements}
    assert types["S1"] == "Marine Processes & Functioning"
    assert types["E1"] == "Ecosystem Services"
    assert types["G1"] == "Goods & Benefits"


def test_canonical_key_wins_over_alias():
    t = _tiny()
    t["dapsiwrm_framework"]["states"] = [{"id": "X9", "name": "ignored"}]
    project, _ = convert_r_template(t, key="Tiny")
    assert "X9" not in {e.id for e in project.isa_data.elements}


@pytest.mark.parametrize("missing", ["polarity", "strength", "confidence", "description"])
@pytest.mark.parametrize("how", ["absent", "null"])
def test_absent_or_null_fields_take_r_defaults(missing, how):
    t = _tiny()
    if how == "absent":
        del t["connections"][0][missing]
    else:
        t["connections"][0][missing] = None
    c = convert_r_template(t, key="Tiny")[0].isa_data.connections[0]
    want = {"polarity": "+", "strength": "medium", "confidence": 3, "description": ""}
    assert getattr(c, missing) == want[missing]


@pytest.mark.parametrize("given,want", [(0, 1), (9, 5), (2, 2)])
def test_confidence_is_clamped(given, want):
    t = _tiny()
    t["connections"][0]["confidence"] = given
    assert convert_r_template(t, key="Tiny")[0].isa_data.connections[0].confidence == want


def test_measure_to_response_link_becomes_extension_not_off_rule():
    t = _tiny()
    t["connections"].append({"from_id": "M1", "to_id": "R1",
                             "from_type": "measure", "to_type": "response"})
    _, report = convert_r_template(t, key="Tiny")
    assert report.off_rule_links == ()
    assert report.type_mismatches == ()        # 'measure' matches the pre-fold category


def test_off_rule_links_are_reported_not_raised():
    t = _tiny()
    t["connections"].append({"from_id": "S1", "to_id": "P1"})   # MPF -> P
    project, report = convert_r_template(t, key="Tiny")
    assert report.off_rule_links == (("S1", "P1"),)
    assert len(project.isa_data.connections) == 2


def test_type_mismatch_is_reported_not_raised():
    t = _tiny()
    t["connections"][0]["to_type"] = "impact"
    _, report = convert_r_template(t, key="Tiny")
    assert report.type_mismatches == (
        "connections[0] P1->S1: to_type 'impact' vs category 'marine_processes'",)


@pytest.mark.parametrize("mutate,match", [
    (lambda t: t["connections"][0].update(to_id="NOPE"), r"Tiny.*NOPE"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"id": "P1", "name": "dup"}),
     r"Tiny.*duplicate element id 'P1'"),
    (lambda t: t["connections"].append(dict(t["connections"][0], polarity="+")),
     r"Tiny.*P1->S1.*duplicate link"),
    (lambda t: t["connections"][0].update(to_id="P1"), r"Tiny.*self-loop"),
    (lambda t: t["connections"][0].update(polarity="positive"), r"Tiny.*'positive'"),
    (lambda t: t["connections"][0].update(strength="very strong"), r"Tiny.*'very strong'"),
    (lambda t: t["connections"][0].update(strength="Strong"), r"Tiny.*'Strong'"),
    (lambda t: t["connections"][0].update(confidence="4"), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(confidence=4.5), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(confidence=True), r"Tiny.*confidence"),
    (lambda t: t["connections"][0].update(description=7), r"Tiny.*description"),
    (lambda t: t["dapsiwrm_framework"].update(drivers={"id": "D1"}), r"Tiny.*'drivers' is not a list"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"name": "no id"}), r"Tiny.*no id or name"),
    (lambda t: t["dapsiwrm_framework"]["responses"].append({"id": "R9"}), r"Tiny.*no id or name"),
])
def test_failure_modes_raise_value_error(mutate, match):
    t = _tiny()
    mutate(t)
    with pytest.raises(ValueError, match=match):
        convert_r_template(t, key="Tiny")


def test_legacy_format_is_rejected():
    with pytest.raises(ValueError, match="unsupported legacy R template format"):
        convert_r_template({"template_info": {}, "elements": []}, key="Old")


def test_load_r_template_tolerates_bom_and_crlf(tmp_path):
    p = tmp_path / "t.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(_tiny(), indent=2).replace("\n", "\r\n").encode("utf-8"))
    assert load_r_template(p) == _tiny()


def test_mapper_imports_without_shiny():
    import subprocess
    import sys
    code = ("import sys, sespy.r_template_mapper; "
            "sys.exit(1 if 'shiny' in sys.modules else 0)")
    root = Path(__file__).resolve().parents[1]
    assert subprocess.run([sys.executable, "-c", code], cwd=root).returncode == 0
```

- [ ] **Step 3: Run to see it fail**

`micromamba run -n shiny python -m pytest tests/test_r_template_mapper.py -q` → collection ERROR `ModuleNotFoundError: No module named 'sespy.r_template_mapper'`.

- [ ] **Step 4: Create `sespy/r_template_mapper.py`**

```python
"""Convert an R MarineSABRES `*_SES_Template.json` into a SESPy Project (P1a).

A library function, not UI: P1a uses it on sha256-pinned test fixtures
(tests/parity/r_templates/), P2's sync script reuses it to build gallery
templates. Shiny-free, never uses the clock (converting a file twice gives
identical output), and never logs: everything worth reporting goes into the
ConversionReport and the caller decides what to log.

R reference: functions/template_loader.R (v1.29.0). Measures fold into
Responses as R does (template_loader.R:103,189-190), marked with
r_extra["r_kind"] = "measure". Element-level `type` labels and every field
without a SESPy column are kept in Element.r_extra (R drops them), and
connection descriptions are kept (R drops them on template load).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data_structure import Connection, Element, IsaData, Project, ProjectMetadata
from .link_rules import classify

# (canonical key, legacy alias, SESPy type). Order = DAPSI(W)R(M) flow.
_CATEGORIES: tuple[tuple[str, str | None, str], ...] = (
    ("drivers", None, "Drivers"),
    ("activities", None, "Activities"),
    ("pressures", None, "Pressures"),
    ("marine_processes", "states", "Marine Processes & Functioning"),
    ("ecosystem_services", "impacts", "Ecosystem Services"),
    ("goods_benefits", "welfare", "Goods & Benefits"),
    ("responses", None, "Responses"),
    ("measures", None, "Responses"),        # folded, r_kind = "measure"
)

# R's connection from_type/to_type labels -> the R category they name.
_LABEL_CATEGORY = {
    "driver": "drivers", "activity": "activities", "pressure": "pressures",
    "state": "marine_processes", "impact": "ecosystem_services",
    "welfare": "goods_benefits", "response": "responses", "measure": "measures",
}

_ELEMENT_COLUMNS = {"id", "name", "description"}   # `type` -> r_extra["r_type"]
_POLARITIES = ("+", "-")
_STRENGTHS = ("weak", "medium", "strong")
_META_KEYS = ("version", "created_date", "source", "applicable_regions")


@dataclass(frozen=True)
class ConversionReport:
    key: str
    counts_by_type: dict[str, int]
    link_count: int
    folded_measures: tuple[str, ...]              # element ids
    off_rule_links: tuple[tuple[str, str], ...]
    type_mismatches: tuple[str, ...]              # from_type/to_type vs category
    extra_fields: tuple[str, ...]                 # R field names moved into r_extra
    template_meta: dict[str, Any]


def load_r_template(path: Path | str) -> dict:
    """Read an R template file. utf-8-sig tolerates a BOM; CRLF is harmless
    to json.loads."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _optional(c: dict, field: str, default: Any) -> Any:
    v = c.get(field)
    return default if v is None else v      # absent or JSON null -> R default


def convert_r_template(raw: dict, *, key: str) -> tuple[Project, ConversionReport]:
    """Convert one parsed R template. Raises ValueError (naming `key` and the
    offending item) on: the legacy `elements` + `template_info` format, a
    category that is not a list, an element without id or name, a duplicate
    element id, a dangling connection endpoint, a self-loop, a duplicate
    (from_id, to_id) pair, or a present-but-invalid polarity, strength,
    confidence or description."""
    if "dapsiwrm_framework" not in raw and ("elements" in raw or "template_info" in raw):
        raise ValueError(f"{key}: unsupported legacy R template format")
    fw = raw.get("dapsiwrm_framework")
    if not isinstance(fw, dict):
        raise ValueError(f"{key}: dapsiwrm_framework must be an object")

    elements: list[Element] = []
    category_of: dict[str, str] = {}
    counts: dict[str, int] = {}
    folded: list[str] = []
    extras: set[str] = set()
    for cat, alias, sespy_type in _CATEGORIES:
        items = fw.get(cat)
        if items is None and alias is not None:
            items = fw.get(alias)          # canonical key wins, as R's %||%
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"{key}: category {cat!r} is not a list")
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
                raise ValueError(f"{key}: {cat}[{i}] has no id or name")
            eid = str(item["id"])
            if eid in category_of:
                raise ValueError(f"{key}: duplicate element id {eid!r}")
            r_extra: dict[str, Any] = {}
            if item.get("type") is not None:      # only when the element has one
                r_extra["r_type"] = item["type"]
                extras.add("type")
            for f, v in item.items():
                if f not in _ELEMENT_COLUMNS and f != "type":
                    r_extra[f] = v
                    extras.add(f)
            if cat == "measures":
                r_extra["r_kind"] = "measure"
                folded.append(eid)
            category_of[eid] = cat
            counts[sespy_type] = counts.get(sespy_type, 0) + 1
            desc = item.get("description")
            elements.append(Element(
                id=eid, label=str(item["name"]),
                type=sespy_type,
                description="" if desc is None else str(desc),
                confidence=3,
                r_extra=r_extra,
            ))

    type_of = {e.id: e.type for e in elements}
    connections: list[Connection] = []
    seen: set[tuple[str, str]] = set()
    off_rule: list[tuple[str, str]] = []
    mismatches: list[str] = []
    for i, c in enumerate(raw.get("connections") or []):
        src, tgt = c.get("from_id"), c.get("to_id")
        where = f"{key}: connections[{i}] {src}->{tgt}"
        for end in (src, tgt):
            if end not in category_of:
                raise ValueError(f"{where}: unknown element id {end!r}")
        if src == tgt:
            raise ValueError(f"{where}: self-loop")
        if (src, tgt) in seen:
            raise ValueError(f"{where}: duplicate link")
        seen.add((src, tgt))

        polarity = _optional(c, "polarity", "+")
        if polarity not in _POLARITIES:
            raise ValueError(f"{where}: invalid polarity {polarity!r}")
        strength = _optional(c, "strength", "medium")
        if strength not in _STRENGTHS:
            raise ValueError(f"{where}: invalid strength {strength!r}")
        confidence = _optional(c, "confidence", 3)
        if isinstance(confidence, bool) or not isinstance(confidence, int):
            raise ValueError(f"{where}: invalid confidence {confidence!r}")
        description = _optional(c, "description", "")
        if not isinstance(description, str):
            raise ValueError(f"{where}: invalid description {description!r}")

        for side, end in (("from_type", src), ("to_type", tgt)):
            label = c.get(side)
            if label is not None and _LABEL_CATEGORY.get(label) != category_of[end]:
                mismatches.append(
                    f"connections[{i}] {src}->{tgt}: {side} {label!r} "
                    f"vs category {category_of[end]!r}")
        if classify(type_of[src], type_of[tgt]) == "off_rule":
            off_rule.append((src, tgt))
        connections.append(Connection(
            source=src, target=tgt, polarity=polarity, strength=strength,
            confidence=min(5, max(1, confidence)), delay="immediate",
            description=description,
        ))

    meta_raw = raw.get("metadata") or {}
    regional = raw.get("regional_context")
    created = meta_raw.get("created_date") or ""
    regional_sea = ""
    if isinstance(regional, dict) and regional.get("regional_sea"):
        regional_sea = str(regional["regional_sea"])   # absent in Caribbean
    metadata = ProjectMetadata(
        name=raw.get("template_name") or key,
        description=raw.get("template_description") or "",
        regional_sea=regional_sea,
        created_at=created,
        modified_at=created,
        origin="r_template",
        r_template_version=str(meta_raw.get("version") or ""),
    )
    template_meta: dict[str, Any] = {}
    for k in ("complexity", "usage_notes"):
        if k in raw:
            template_meta[k] = raw[k]
    for k in _META_KEYS:
        if k in meta_raw:
            template_meta[k] = meta_raw[k]
    if regional is not None:
        template_meta["regional_context"] = regional

    report = ConversionReport(
        key=key,
        counts_by_type=counts,
        link_count=len(connections),
        folded_measures=tuple(folded),
        off_rule_links=tuple(off_rule),
        type_mismatches=tuple(mismatches),
        extra_fields=tuple(sorted(extras)),
        template_meta=template_meta,
    )
    return Project(metadata, IsaData(elements, connections)), report
```

- [ ] **Step 5: Run the mapper tests**

`micromamba run -n shiny python -m pytest tests/test_r_template_mapper.py -q` → `49 passed`.

- [ ] **Step 6: Run the CI unit command** → green.

- [ ] **Step 7: Commit**

```powershell
git add sespy/r_template_mapper.py tests/test_r_template_mapper.py tests/parity/r_templates
git commit -m @'
feat(mapper): R template mapper with the 7 v1.29.0 fixtures (P1a)

convert_r_template turns an R *_SES_Template.json into a Project: category
gives the type, Measures fold into Responses with r_kind, element extras
and r_type go to r_extra, connection descriptions are kept. A
ConversionReport lists counts, folded measures, off-rule links, type
mismatches, extra fields and gallery-only metadata. All 7 fixtures survive
the real save/load path with zero off-rule links and zero mismatches.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 6 (C5): `r_sync` hashing, `r_sync.json`, `R_SYNC.md`

**Files:**
- Create: `sespy/r_sync.py`, `tests/parity/r_sync.json`, `tests/parity/test_r_sync.py`, `docs/parity/R_SYNC.md`
- Scratch (not committed): `make_r_sync.py` in your scratchpad directory

**Interfaces:**
- Consumes: fixtures from Tasks 3 and 5.
- Produces: `sha256_norm(obj: Any) -> str`; `sha256_text_norm(text: str) -> str`; `r_sync.json` shape `{"r_tag": "v1.29.0", "r_commit": "e33faea", "files": {"tests/parity/...": "<64-hex>"}}` (8 entries, repo-root-relative forward-slash paths).

- [ ] **Step 1: Write the failing test `tests/parity/test_r_sync.py`**

```python
"""P1a — the R fixtures are pinned to MarineSABRES v1.29.0 (e33faea).

tests/parity/r_sync.json is the machine-readable pin; docs/parity/R_SYNC.md
is the human record and must list the same hashes. A new R release is
adopted by re-copying the fixtures and updating both in one commit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from sespy.r_sync import sha256_norm, sha256_text_norm

ROOT = Path(__file__).resolve().parents[2]
PIN = json.loads((ROOT / "tests" / "parity" / "r_sync.json").read_text(encoding="utf-8"))


def test_pin_shape():
    assert PIN["r_tag"] == "v1.29.0" and PIN["r_commit"] == "e33faea"
    paths = sorted(PIN["files"])
    assert len(paths) == 8
    assert "tests/parity/r_rules/dapsiwrm_connection_rules.R" in paths
    assert sum(p.startswith("tests/parity/r_templates/") for p in paths) == 7
    assert not any("backup" in p for p in paths)


@pytest.mark.parametrize("rel", sorted(PIN["files"]))
def test_fixture_hash_matches_pin(rel):
    data = (ROOT / rel).read_bytes().decode("utf-8-sig")
    got = sha256_norm(json.loads(data)) if rel.endswith(".json") else sha256_text_norm(data)
    assert got == PIN["files"][rel], f"{rel} drifted from the R pin"


def test_r_sync_md_lists_exactly_the_pinned_hashes():
    md = (ROOT / "docs" / "parity" / "R_SYNC.md").read_text(encoding="utf-8")
    assert set(re.findall(r"\b[0-9a-f]{64}\b", md)) == set(PIN["files"].values())


# ---- the helpers ------------------------------------------------------------

def test_sha256_norm_ignores_key_order_and_formatting():
    a = {"b": 1, "a": ["é", {"y": 2, "x": None}]}
    b = json.loads('{\r\n  "a": ["\\u00e9", {"x": null, "y": 2}],\r\n  "b": 1\r\n}')
    assert sha256_norm(a) == sha256_norm(b)


def test_sha256_norm_is_the_documented_encoding():
    import hashlib
    obj = {"k": "é"}
    want = hashlib.sha256('{"k":"é"}'.encode("utf-8")).hexdigest()
    assert sha256_norm(obj) == want          # ensure_ascii=False, compact separators


def test_sha256_text_norm_normalises_crlf(tmp_path):
    p = tmp_path / "x.R"
    p.write_bytes(b"a <- 1\r\nb <- 2\r\n")
    assert sha256_text_norm(p.read_bytes().decode("utf-8")) == sha256_text_norm("a <- 1\nb <- 2\n")


def test_r_sync_imports_without_shiny():
    import subprocess
    import sys
    code = "import sys, sespy.r_sync; sys.exit(1 if 'shiny' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0
```

- [ ] **Step 2: Run to see it fail**

`micromamba run -n shiny python -m pytest tests/parity/test_r_sync.py -q` → collection ERROR `ModuleNotFoundError: No module named 'sespy.r_sync'`.

- [ ] **Step 3: Create `sespy/r_sync.py`**

```python
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
```

- [ ] **Step 4: Generate `tests/parity/r_sync.json` with a scratch script**

Save as `<scratchpad>/make_r_sync.py` (NOT in the repo) and run it from the repo root: `micromamba run -n shiny python <scratchpad>/make_r_sync.py`
```python
"""Write tests/parity/r_sync.json from the fixture copies. Run from the repo
root:  micromamba run -n shiny python <scratch>/make_r_sync.py
Prints the Markdown hash table for docs/parity/R_SYNC.md."""
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))          # this working tree's sespy, not site-packages
from sespy.r_sync import sha256_norm, sha256_text_norm  # noqa: E402

R_TAG, R_COMMIT = "v1.29.0", "e33faea"
files = {}
for p in sorted((ROOT / "tests/parity/r_templates").glob("*_SES_Template.json")):
    obj = json.loads(p.read_bytes().decode("utf-8-sig"))
    files[p.relative_to(ROOT).as_posix()] = sha256_norm(obj)
rules = ROOT / "tests/parity/r_rules/dapsiwrm_connection_rules.R"
files[rules.relative_to(ROOT).as_posix()] = sha256_text_norm(rules.read_bytes().decode("utf-8"))
assert len(files) == 8, files

out = ROOT / "tests/parity/r_sync.json"
out.write_text(json.dumps({"r_tag": R_TAG, "r_commit": R_COMMIT, "files": files},
                          indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
print("| Fixture | Hash |\n|---|---|")
for path, h in files.items():
    print(f"| `{path}` | `{h}` |")
```
Expected `tests/parity/r_sync.json` (verified against the v1.29.0 checkout on 2026-10-17; these match the laguna-deployed R):
```json
{
  "r_tag": "v1.29.0",
  "r_commit": "e33faea",
  "files": {
    "tests/parity/r_templates/Aquaculture_SES_Template.json": "d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946",
    "tests/parity/r_templates/Caribbean_SES_Template.json": "7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961",
    "tests/parity/r_templates/ClimateChange_SES_Template.json": "ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3",
    "tests/parity/r_templates/Fisheries_SES_Template.json": "f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6",
    "tests/parity/r_templates/OffshoreWind_SES_Template.json": "a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf",
    "tests/parity/r_templates/Pollution_SES_Template.json": "d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56",
    "tests/parity/r_templates/Tourism_SES_Template.json": "1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e",
    "tests/parity/r_rules/dapsiwrm_connection_rules.R": "ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5"
  }
}
```
If any hash differs, STOP: the fixture copy is not v1.29.0 — recopy, do not edit the hash.

- [ ] **Step 5: Create `docs/parity/R_SYNC.md`** (the table must be the script's printed table)

```markdown
# R sync record

SESPy reads a few files from the R MarineSABRES SES Toolbox as **test
fixtures**. They never ship to the server. This page is the human record of
which R release they come from. The machine-readable pin is
[`tests/parity/r_sync.json`](../../tests/parity/r_sync.json), which
`tests/parity/test_r_sync.py` checks; it also checks that this page lists
exactly the same hashes. Update both in the same commit.

## Current pin

- **R release:** MarineSABRES_SES_Shiny **v1.29.0**, commit `e33faea`.
- **Adopted in:** SESPy 1.13.0 (P1a: link rules, schema v7, R template mapper).
- **Roadmap baseline:** moved from v1.28.0 (`e3c3b77`) to v1.29.0. The files
  below are unchanged between the two.

| Fixture | Hash |
|---|---|
| `tests/parity/r_templates/Aquaculture_SES_Template.json` | `d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946` |
| `tests/parity/r_templates/Caribbean_SES_Template.json` | `7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961` |
| `tests/parity/r_templates/ClimateChange_SES_Template.json` | `ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3` |
| `tests/parity/r_templates/Fisheries_SES_Template.json` | `f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6` |
| `tests/parity/r_templates/OffshoreWind_SES_Template.json` | `a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf` |
| `tests/parity/r_templates/Pollution_SES_Template.json` | `d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56` |
| `tests/parity/r_templates/Tourism_SES_Template.json` | `1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e` |
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | `ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5` |

The JSON templates are hashed with `sespy.r_sync.sha256_norm` (the parsed
JSON, so key order, CRLF and a BOM do not matter). The `.R` file is hashed
with `sespy.r_sync.sha256_text_norm` (text with CRLF normalised to LF).
`Caribbean_SES_Template_backup.json` is not a fixture.

## Laguna verification (2026-10-17)

The R app deployed on laguna (`/srv/shiny-server/marinesabres`) was
v1.29.0 on 2026-10-17. Its 7 templates and its
`functions/dapsiwrm_connection_rules.R` have the same hashes as the local
checkout, so the pin above matches what users run.

## Adopting a new R release

1. Copy the 7 `data/*_SES_Template.json` files to `tests/parity/r_templates/`
   and `functions/dapsiwrm_connection_rules.R` to `tests/parity/r_rules/`.
2. Regenerate `tests/parity/r_sync.json` and update the table above.
3. Run `tests/parity/` and `tests/test_r_template_mapper.py`; a red
   `test_r_rules_parity.py` means the rule table changed and
   `sespy/constants.py::DAPSIWRM_ADJACENCY_RULES` must follow.

Live drift against laguna (`tests/parity/check_live.py`) is owned by **K1**
in the R-parity roadmap; P1a uses these files only as test fixtures.
```

- [ ] **Step 6: Run the parity tests**

`micromamba run -n shiny python -m pytest tests/parity -q` → `16 passed`.

- [ ] **Step 7: Run the CI unit command** → green.

- [ ] **Step 8: Commit**

```powershell
git add sespy/r_sync.py tests/parity/r_sync.json tests/parity/test_r_sync.py docs/parity/R_SYNC.md
git commit -m @'
test(parity): pin the R fixtures to v1.29.0 with sha256_norm (P1a)

sespy.r_sync is the one hashing helper (parsed-JSON sha256_norm, CRLF-
normalised sha256_text_norm). tests/parity/r_sync.json pins the 7 templates
and the rules file; docs/parity/R_SYNC.md is the human record, including the
laguna verification, and a test keeps its hashes equal to the pin.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 7 (C5): Excel import — description, Kumu Label, type aliases, Measure

**Files:**
- Modify: `sespy/excel_import.py` (import line 21; constants after line 39; `_pick` 45-52 + two new helpers; element loop 124-131; polarity 142-146; connection construction 148-155)
- Modify: `tests/test_excel_import.py` (import `pytest` after `import pandas as pd`; append tests)

**Interfaces:**
- Consumes: `Element(..., r_extra=...)`, `Connection(..., description=...)` (Task 2); logging via validation (Task 3).
- Produces: `CONN_DESC_COLS`, `CONN_LABEL_COLS`; `_pick(row, candidates, default="", *, skip_blank: bool = False)`; `_resolve_type(raw: Any) -> tuple[str, dict[str, Any]]`; `_row_polarity(row: pd.Series) -> str`.

Decision (spec §8 says whitespace handling happens "per column inside `_pick`"): it is opt-in via `skip_blank=True`, used **only** for the polarity columns, so label/description/type picks are unchanged.

- [ ] **Step 1: Write the failing tests**

In `tests/test_excel_import.py`, change the imports to:
```python
import pandas as pd
import pytest
```
Append:
```python


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
```

- [ ] **Step 2: Run to see them fail**

`micromamba run -n shiny python -m pytest tests/test_excel_import.py -q` → `28 failed, 21 passed` (descriptions are `''`, aliases rejected by validation, `"Measure"` invalid type, Label ignored).

- [ ] **Step 3: Implement in `sespy/excel_import.py`**

Line 21:
```python
from .constants import DAPSIWRM_ELEMENTS, normalize_delay
```
After `CONN_DELAY_COLS    = ("delay", "Delay", "lag", "Lag")` (line 39):
```python
CONN_DESC_COLS     = ("description", "Description", "rationale", "Rationale")
# Kumu's edge Label: decides polarity only when the row has neither a numeric
# weight nor a non-empty polarity cell (R excel_import_helpers.R:432-437).
CONN_LABEL_COLS    = ("Label", "label")

_MPF = "Marine Processes & Functioning"
# R's Excel type aliases (excel_import_helpers.R:160-175), matched
# case-insensitively after stripping (R is case-sensitive: a divergence).
# The canonical SESPy names are accepted the same way.
_TYPE_ALIASES: dict[str, str] = {
    **{t.lower(): t for t in DAPSIWRM_ELEMENTS},
    "driver": "Drivers",
    "activity": "Activities",
    "pressure": "Pressures",
    "marine process and function": _MPF,
    "marine process and functioning": _MPF,
    "state": _MPF,
    "state change": _MPF,
    "ecosystem service": "Ecosystem Services",
    "impact": "Ecosystem Services",
    "good and benefit": "Goods & Benefits",
    "goods and benefits": "Goods & Benefits",
    "welfare": "Goods & Benefits",
    "response": "Responses",
    "measure": "Responses",
}
# Kumu label prefixes that mean "-": ASCII (as R) plus U+2212, the sign
# SESPy's own polarity labels use (a divergence).
_NEGATIVE_LABEL_PREFIXES = ("-", "\u2212")
```
Replace `_pick` (lines 45-52) with:
```python
def _pick(row: pd.Series, candidates: Sequence[str], default: Any = "",
          *, skip_blank: bool = False) -> Any:
    """Return the first candidate column value found in `row`, or `default`.
    With skip_blank, a whitespace-only string cell counts as empty, so the
    next candidate column is tried (used for the polarity columns only)."""
    for name in candidates:
        if name in row.index:
            v = row[name]
            if pd.notna(v):
                if skip_blank and isinstance(v, str) and not v.strip():
                    continue
                return v
    return default


def _resolve_type(raw: Any) -> tuple[str, dict[str, Any]]:
    """Map an Elements-sheet type cell to (SESPy type, r_extra). A Measure
    becomes Responses with r_extra["r_kind"] = "measure". An unrecognised
    string is returned stripped, and validation rejects it as before."""
    text = str(raw).strip()
    key = text.lower()
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key], ({"r_kind": "measure"} if key == "measure" else {})
    return text, {}


def _row_polarity(row: pd.Series) -> str:
    """Polarity for a row without a numeric FCM weight: the first non-empty
    polarity cell (stripped), else the Kumu Label cell (not stripped, as R:
    a value starting with "-" or U+2212 is negative), else "+"."""
    cell = _pick(row, CONN_POLARITY_COLS, default="", skip_blank=True)
    if cell != "":
        return str(cell).strip()
    label = _pick(row, CONN_LABEL_COLS, default="")
    return "-" if str(label).startswith(_NEGATIVE_LABEL_PREFIXES) else "+"
```
Element loop (lines 124-131):
```python
        el_conf = _pick(row, ELEMENT_CONF_COLS, default=3)
        # Resolved before the payload is built: validation would reject
        # "driver" or "Measure".
        el_type, r_extra = _resolve_type(_pick(row, ELEMENT_TYPE_COLS, default=""))
        elements.append(Element(
            id=str(eid),
            label=str(_pick(row, ELEMENT_LABEL_COLS, default=eid)),
            type=el_type,
            description=str(_pick(row, ELEMENT_DESC_COLS, default="")),
            confidence=int(el_conf if el_conf is not None and el_conf != "" else 3),
            r_extra=r_extra,
        ))
```
Polarity (lines 142-146):
```python
        if fcm is not None:                       # numeric → FCM weight decides the sign
            polarity, strength = fcm_weight_to_fields(fcm)
        else:                                     # polarity column, else Kumu Label
            polarity = _row_polarity(row)
            strength = str(raw_strength) or "medium"
```
Connection construction — after the `delay=...` line add:
```python
            delay=normalize_delay(_pick(row, CONN_DELAY_COLS, default="immediate")),
            # An empty/NaN cell is "" (as for element descriptions), so one
            # numeric cell never fails a whole workbook.
            description=str(_pick(row, CONN_DESC_COLS, default="")),
        ))
```
(The payload built with `e.__dict__` / `c.__dict__` now carries `r_extra` and `description`; validation and `_isa_from_dict` handle both.)

- [ ] **Step 4: Run** `micromamba run -n shiny python -m pytest tests/test_excel_import.py -q` → `49 passed`.

- [ ] **Step 5: Run the CI unit command** → green.

- [ ] **Step 6: Commit**

```powershell
git add sespy/excel_import.py tests/test_excel_import.py
git commit -m @'
feat(import): Excel connection descriptions, Kumu Label polarity, R type aliases (P1a)

Connection description/rationale columns fill Connection.description. With
no numeric weight and no non-empty polarity cell (whitespace counts as
empty, per column), Kumu's Label decides: a leading "-" (or U+2212) is
negative. R's element type aliases (Driver, State, Welfare, Measure, ...)
are matched case-insensitively; a Measure becomes a Response with
r_extra r_kind=measure.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 8 (C5): `pims_project` keeps v7 metadata on "Save project info"

**Files:**
- Modify: `sespy/modules/pims_project.py` (imports 10-17; handler 146-170)
- Create: `tests/test_pims_project.py`

**Interfaces:** Consumes `ProjectMetadata` v7 fields (Task 2). Produces no new API.

- [ ] **Step 1: Write the failing test `tests/test_pims_project.py`**

```python
"""P1a — "Save project info" keeps the schema-v7 metadata fields (spec §4).

pims_project_server used to rebuild ProjectMetadata field by field, which
would drop origin, r_template_version and min_sespy_version on every save.
"""
from __future__ import annotations

from shiny import reactive
from shiny.testserver import test_server

from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import create_event_bus
from sespy.modules.pims_project import pims_project_server

FORM = dict(project_name="Renamed", da_site="", focal_issue="Eutrophication",
            definition_statement="", temporal_scale="Yearly",
            spatial_scale="Regional", system_in_focus="Lagoon")


def test_save_project_info_keeps_v7_metadata_fields():
    start = Project(ProjectMetadata(
        name="R template", description="from R", regional_sea="Baltic Sea",
        created_at="2026-04-08", modified_at="2026-04-08",
        origin="r_template", r_template_version="2.3",
        min_sespy_version="1.13.0"), IsaData())
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(start)
        holder.append(pd)
        pims_project_server("pims", project_data=pd, event_bus=create_event_bus())

    with test_server(server) as ts:
        scope = ts.make_scope("pims")
        # Every form input must be set, or input.x() aborts the handler.
        # Action buttons ignore their initial value: set 0, then 1.
        scope.set_inputs(**FORM, save_project_info=0)
        scope.set_inputs(save_project_info=1)
        assert ts.is_ok, ts.error
        with reactive.isolate():
            meta = holder[0].get().metadata

    assert meta.name == "Renamed" and meta.focal_issue == "Eutrophication"
    assert (meta.origin, meta.r_template_version, meta.min_sespy_version) == \
        ("r_template", "2.3", "1.13.0")
    assert (meta.description, meta.regional_sea, meta.created_at) == \
        ("from R", "Baltic Sea", "2026-04-08")
    assert meta.modified_at != "2026-04-08"
```

- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_pims_project.py -q` → FAILED `AssertionError: assert ('', '', '') == ('r_template', '2.3', '1.13.0')`.

- [ ] **Step 3: Implement**

Imports:
```python
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
```
and `from ..data_structure import Project, ProjectMetadata` → `from ..data_structure import Project`.

Replace the comment above `_handle_save` (lines 146-148) with:
```python
    # Full save handler: read form inputs, apply empty-name fallback,
    # replace the form's fields on the current ProjectMetadata (every other
    # field, e.g. origin / r_template_version / min_sespy_version, is kept),
    # set project_data, emit isa_change, and show confirmation toast.
```
Replace the `new_meta = ProjectMetadata(...)` call (lines 156-170) with:
```python
        new_meta = dataclasses.replace(
            current,
            name=name,
            da_site=(input.da_site() or "").strip(),
            focal_issue=(input.focal_issue() or "").strip(),
            definition_statement=(input.definition_statement() or "").strip(),
            temporal_scale=(input.temporal_scale() or "").strip(),
            spatial_scale=(input.spatial_scale() or "").strip(),
            system_in_focus=(input.system_in_focus() or "").strip(),
            modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
```

- [ ] **Step 4: Run** `micromamba run -n shiny python -m pytest tests/test_pims_project.py -q` → `1 passed`.
- [ ] **Step 5: Run the CI unit command** → green.
- [ ] **Step 6: Commit**

```powershell
git add sespy/modules/pims_project.py tests/test_pims_project.py
git commit -m @'
fix(pims): Save project info keeps every other metadata field (P1a)

The handler rebuilt ProjectMetadata field by field and would drop origin,
r_template_version and min_sespy_version. It now uses dataclasses.replace
on the current metadata. First test_server test of pims_project_server.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 9 (C5): ISA entry — empty first choice, polarity prefill, off-rule note

**Files:**
- Modify: `sespy/modules/isa_data_entry.py` (imports 27-30; UI after the connections `layout_columns` 94-95; pickers 124-139)
- Modify: `sespy/translations/core.json` (before `"entry.off_rule_link"`)
- Modify: `tests/test_i18n.py` (before `def test_causal_paths_keys_present`)
- Create: `tests/test_isa_entry_link_rules.py`

**Interfaces:**
- Consumes: `seed_polarity`, `note_for` (Task 3); `Translator` from the server's `translator` param (in the app it is `_i18n.get_default()`, the session clone).
- Produces: UI ids `entry-off_rule_note` (output_ui) rendering `div.sespy-off-rule-note.alert.alert-warning`; pickers' first choice `""` labelled `t("entry.choose_element")` when elements exist (`{"": "(no elements yet)"}` unchanged when none).

- [ ] **Step 1: Write the failing tests**

`tests/test_isa_entry_link_rules.py`:
```python
"""P1a — ISA entry: empty first picker choice, polarity prefill and the
off-rule note, in memory with shiny.testserver (spec §3.4, §10).

update_radio_buttons only sends a client message that test_server does not
reflect back into inputs, so the tests record the calls instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n
from sespy.data_structure import Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.isa_data_entry import isa_data_entry_server

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))


def _sample() -> Project:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    return Project.from_dict(raw)


@pytest.fixture
def entry(monkeypatch):
    # The module labels its pickers with the module-level t(); give it the
    # real translations for this test only (restored by monkeypatch).
    monkeypatch.setattr(i18n, "_default_translator", TR)
    radio: list[dict] = []
    toasts: list[str] = []
    monkeypatch.setattr(shiny.ui, "update_radio_buttons",
                        lambda id, **kw: radio.append({"id": id, **kw}))
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(_sample())
        holder.append(pd)
        isa_data_entry_server("entry", project_data=pd, event_bus=create_event_bus(),
                              translator=TR)

    with test_server(server) as ts:
        yield ts, ts.make_scope("entry"), radio, toasts, holder


def _note(scope):
    out = scope.get_output("off_rule_note")
    return None if out.status != "ok" or not out.value else out.value["html"]


@pytest.mark.parametrize("picker", ["source_picker", "target_picker"])
def test_pickers_start_with_an_empty_selected_choice(entry, picker):
    _, scope, *_ = entry
    html = scope.get_output(picker).value["html"]
    assert '<option value="" selected' in html
    assert TR.t("entry.choose_element") in html
    assert html.index('value=""') < html.index('value="D001"')


def test_empty_project_keeps_the_no_elements_choice(monkeypatch):
    from sespy.data_structure import IsaData, ProjectMetadata

    def server(input, output, session):
        isa_data_entry_server("entry", project_data=reactive.value(
            Project(ProjectMetadata(), IsaData())), event_bus=create_event_bus())

    with test_server(server) as ts:
        html = ts.make_scope("entry").get_output("source_picker").value["html"]
    assert "(no elements yet)" in html and "choose" not in html


def test_pressure_to_mpf_seeds_minus(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    assert radio and radio[-1] == {"id": "new_polarity", "selected": "-"}


def test_off_rule_pair_seeds_plus_and_shows_the_note(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="D001", new_target="GB01")
    assert radio[-1] == {"id": "new_polarity", "selected": "+"}
    html = _note(scope)
    assert html and "sespy-off-rule-note" in html and "alert-warning" in html
    assert "Drivers" in html and "Goods &amp; Benefits" in html


def test_changing_an_endpoint_reseeds(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    scope.set_inputs(new_source="R001")            # R -> MPF is "+"
    assert [c["selected"] for c in radio[-2:]] == ["-", "+"]


def test_only_a_source_seeds_nothing_and_shows_no_note(entry):
    _, scope, radio, *_ = entry
    # new_target set explicitly to "": unset, the effect would never run and
    # the test would pass vacuously.
    scope.set_inputs(new_source="P001", new_target="")
    assert radio == []
    assert _note(scope) is None


def test_default_state_has_no_note(entry):
    _, scope, radio, *_ = entry
    scope.set_inputs(new_source="", new_target="")
    assert _note(scope) is None and radio == []


def test_canonical_pair_has_no_note(entry):
    _, scope, *_ = entry
    scope.set_inputs(new_source="P001", new_target="MPF2")
    assert _note(scope) is None


def test_add_connection_refuses_an_empty_endpoint(entry):
    """Characterisation: _add_connection already refuses an empty endpoint."""
    _, scope, _, toasts, holder = entry
    scope.set_inputs(new_source="", new_target="D001", new_polarity="+",
                     new_delay="immediate", add_connection=0)
    scope.set_inputs(add_connection=1)
    assert toasts and "Pick source and target" in toasts[-1]
    with reactive.isolate():
        assert holder[0].get().isa_data.connection_count() == 20


def test_off_rule_link_still_saves(entry):
    _, scope, _, toasts, holder = entry
    scope.set_inputs(new_source="D001", new_target="GB01", new_polarity="+",
                     new_delay="immediate", add_connection=0)
    scope.set_inputs(add_connection=1)
    with reactive.isolate():
        conns = holder[0].get().isa_data.connections
    assert ("D001", "GB01") in {(c.source, c.target) for c in conns}
    assert len(conns) == 21
```

`tests/test_i18n.py` — insert before `def test_causal_paths_keys_present(translations):`:
```python
def test_entry_choose_element_key_present(translations):
    assert "entry.choose_element" in translations
    assert translations["entry.choose_element"]["en"] == "— choose —"


```

- [ ] **Step 2: Run to see them fail**

`micromamba run -n shiny python -m pytest tests/test_isa_entry_link_rules.py tests/test_i18n.py -q`
Expected: `8 failed` in the entry file (`'<option value="" selected' in html` false; `radio` empty; `KeyError` for output `off_rule_note`), 3 passed (`test_empty_project_keeps_the_no_elements_choice`, and the two characterisation tests `test_add_connection_refuses_an_empty_endpoint`, `test_off_rule_link_still_saves`); `test_entry_choose_element_key_present` FAILED.

- [ ] **Step 3: Add `entry.choose_element` to `sespy/translations/core.json`**

Edit anchor `    "entry.off_rule_link": {` (unique, added in Task 3); replace with:
```
    "entry.choose_element": {
      "en": "— choose —",
      "es": "— elegir —",
      "fr": "— choisir —",
      "de": "— auswählen —",
      "lt": "— pasirinkite —",
      "pt": "— escolher —",
      "it": "— scegli —",
      "no": "— velg —",
      "el": "— επιλέξτε —"
    },
    "entry.off_rule_link": {
```

- [ ] **Step 4: Implement in `sespy/modules/isa_data_entry.py`**

Imports:
```python
from ..i18n import Translator, t
from ..link_rules import note_for, seed_polarity
from ..utils import next_id
```
UI — between the connections `layout_columns(...)` and the `connections_table` div:
```python
                col_widths=(3, 3, 2, 2, 2),
            ),
            # Off-rule warning for the chosen pair (link_rules.note_for);
            # empty for canonical/extension/untyped pairs. The link still saves.
            ui.output_ui("off_rule_note"),
            ui.tags.div(
                ui.output_data_frame("connections_table"),
```
Replace the picker block (lines 124-139) with:
```python
    # ---- Element-type-aware label pickers for connections ---------------
    # Both pickers re-render on every isa_change with no selected=, so they
    # fall back to their first choice. That choice is an empty "— choose —"
    # entry, so a half-chosen pair never seeds a polarity or shows a note.
    def _picker_choices() -> dict[str, str]:
        elements = project_data.get().isa_data.elements
        if not elements:
            return {"": "(no elements yet)"}
        return {"": t("entry.choose_element"),
                **{el.id: f"{el.id} · {el.label}" for el in elements}}

    @output
    @render.ui
    def source_picker():
        event_bus.isa_change.get()
        return ui.input_select("new_source", t("entry.source"), _picker_choices())

    @output
    @render.ui
    def target_picker():
        event_bus.isa_change.get()
        return ui.input_select("new_target", t("entry.target"), _picker_choices())

    def _element(eid: str | None) -> Element | None:
        if not eid:
            return None
        return next((el for el in project_data.get().isa_data.elements
                     if el.id == eid), None)

    # ---- Polarity prefill from the link rules (R default_polarity_for_matrix)
    @reactive.effect
    def _seed_polarity():
        src_id, tgt_id = input.new_source(), input.new_target()
        with reactive.isolate():
            src, tgt = _element(src_id), _element(tgt_id)
        polarity = seed_polarity(src, tgt)
        # Changing either endpoint re-seeds, overriding a manual choice (as R).
        if polarity is not None:
            ui.update_radio_buttons("new_polarity", selected=polarity)

    @output
    @render.ui
    def off_rule_note():
        src_id, tgt_id = input.new_source(), input.new_target()
        with reactive.isolate():
            src, tgt = _element(src_id), _element(tgt_id)
        text = note_for(src, tgt, translator)
        if text is None:
            return None
        return ui.div(text, class_="sespy-off-rule-note alert alert-warning")
```
(`_add_connection` is unchanged: it already refuses `""` endpoints and self-loops. `Connection.description` gets no UI in P1a — P1b owns it.)

- [ ] **Step 5: Run** `micromamba run -n shiny python -m pytest tests/test_isa_entry_link_rules.py tests/test_i18n.py -q` → all pass (11 + i18n).

- [ ] **Step 6: Run the CI unit command** → green.

- [ ] **Step 7: Commit**

```powershell
git add sespy/modules/isa_data_entry.py sespy/translations/core.json tests/test_i18n.py tests/test_isa_entry_link_rules.py
git commit -m @'
feat(entry): polarity prefill and off-rule note in Edit Data (P1a)

Source and target pickers start on an empty "— choose —" choice (9
languages), so nothing is seeded until both ends are chosen. Choosing a
pair pre-fills polarity from the rule table (overridable; re-seeds on each
change, as R), and an off-rule pair shows a warning note. The link still
saves.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 10 (C5): Boolean hardening

**Files:**
- Modify: `sespy/dynamics.py:228-264`; `sespy/modules/analysis_boolean.py:102`
- Modify: `tests/test_dynamics.py` (append; this file stays Shiny-free)
- Create: `tests/test_analysis_boolean_clamp.py`

**Interfaces:** Produces `BOOLEAN_MAX_NODES_CEILING: int = 20`; `clamp_max_nodes(value: int, *, lo: int, hi: int) -> int`; `boolean_attractors(rules, max_nodes: int = 12, *, ceiling: int = BOOLEAN_MAX_NODES_CEILING) -> dict` (too-large sentinel reports the clamped `max_nodes`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dynamics.py`:
```python


# ---- P1a: Boolean ceiling and clamp -----------------------------------------

def _isolated_rules(n: int) -> list[dict]:
    return [{"node_id": i, "activators": [], "inhibitors": [], "threshold": 0.0}
            for i in range(n)]


@pytest.mark.parametrize("value,lo,hi,want", [
    (12, 4, 12, 12), (50, 4, 12, 12), (1, 4, 12, 4), (-3, 4, 12, 4),
    (7, 4, 12, 7), (25, 1, 20, 20), (0, 1, 20, 1),
])
def test_clamp_max_nodes(value, lo, hi, want):
    from sespy.dynamics import clamp_max_nodes
    assert clamp_max_nodes(value, lo=lo, hi=hi) == want


def test_boolean_ceiling_is_20():
    from sespy.dynamics import BOOLEAN_MAX_NODES_CEILING
    assert BOOLEAN_MAX_NODES_CEILING == 20


def test_boolean_attractors_clamps_a_huge_cap_to_the_ceiling():
    from sespy.dynamics import boolean_attractors
    r = boolean_attractors(_isolated_rules(21), max_nodes=10_000)
    assert r["error"] == "too_large"
    assert r["n_nodes"] == 21
    assert r["max_nodes"] == 20            # the clamped value actually applied


def test_boolean_attractors_explicit_ceiling():
    from sespy.dynamics import boolean_attractors
    r = boolean_attractors(_isolated_rules(9), max_nodes=50, ceiling=8)
    assert r["error"] == "too_large" and r["max_nodes"] == 8


def test_boolean_attractors_zero_or_negative_cap_clamps_to_one():
    from sespy.dynamics import boolean_attractors
    r = boolean_attractors(_isolated_rules(2), max_nodes=0)
    assert r["error"] == "too_large" and r["max_nodes"] == 1
    assert "error" not in boolean_attractors(_isolated_rules(1), max_nodes=-5)


def test_boolean_attractors_default_cap_unchanged():
    from sespy.dynamics import boolean_attractors
    assert boolean_attractors(_isolated_rules(13))["max_nodes"] == 12
    assert "error" not in boolean_attractors(_isolated_rules(3))
```

`tests/test_analysis_boolean_clamp.py`:
```python
"""P1a — the Boolean module clamps max_nodes to its UI range on the server
(spec §7). tests/test_dynamics.py stays Shiny-free, so this lives here."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from shiny import reactive
from shiny.testserver import test_server

from sespy import dynamics
from sespy.data_structure import Project
from sespy.event_bus import create_event_bus
from sespy.modules.analysis_boolean import analysis_boolean_server

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_ses.json"


@pytest.mark.parametrize("ui_value,want", [(50, 12), (2, 4), (8, 8), ("junk", 12)])
def test_boolean_module_clamps_max_nodes_to_ui_range(monkeypatch, ui_value, want):
    seen: list[int] = []
    real = dynamics.boolean_attractors

    def spy(rules, max_nodes=12, **kw):
        seen.append(max_nodes)
        return real(rules, max_nodes=max_nodes, **kw)

    monkeypatch.setattr(dynamics, "boolean_attractors", spy)
    project = Project.from_dict(json.loads(SAMPLE.read_text(encoding="utf-8")))

    def server(input, output, session):
        analysis_boolean_server("boolean", project_data=reactive.value(project),
                                event_bus=create_event_bus())

    with test_server(server) as ts:
        scope = ts.make_scope("boolean")
        # Action buttons ignore their initial value: set 0, then 1.
        scope.set_inputs(direction="cols", max_nodes=ui_value, run_boolean=0)
        scope.set_inputs(run_boolean=1)
    assert seen == [want]
```

- [ ] **Step 2: Run** `micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_analysis_boolean_clamp.py -q -k "clamp or ceiling or boolean_attractors"` → FAILs: `ImportError: cannot import name 'clamp_max_nodes'`, `'BOOLEAN_MAX_NODES_CEILING'`, `assert 10000 == 20`, `TypeError: ... unexpected keyword argument 'ceiling'`, and `assert [50] == [12]` / `[2] == [4]`.

- [ ] **Step 3: Implement**

`sespy/dynamics.py` — replace the `boolean_attractors` signature (lines 228-231) with:
```python
# Server-side ceiling for library callers of boolean_attractors (R
# DYNAMICS_MAX_BOOLEAN_NODES). The UI keeps its own [4, 12] range
# (analysis_boolean.py): this pure-Python 2^N search runs synchronously, and
# raising the UI limit needs an ExtendedTask or a vectorised search (P7a).
BOOLEAN_MAX_NODES_CEILING = 20


def clamp_max_nodes(value: int, *, lo: int, hi: int) -> int:
    """Clamp a node cap to [lo, hi]. Shared by boolean_attractors (library
    ceiling) and the Boolean module (UI range)."""
    return max(lo, min(hi, int(value)))


def boolean_attractors(
    rules: list[dict[str, Any]],
    max_nodes: int = 12,
    *,
    ceiling: int = BOOLEAN_MAX_NODES_CEILING,
) -> dict[str, Any]:
```
In its docstring replace the `max_nodes` parameter entry with:
```
    max_nodes
        Hard cap on ``len(rules)``; networks above it return an error sentinel
        rather than running (2^N grows fast). Clamped to ``[1, ceiling]``
        first; the sentinel reports the clamped value.
    ceiling
        Upper bound for ``max_nodes`` (default BOOLEAN_MAX_NODES_CEILING = 20).
```
and make the body start:
```python
    max_nodes = clamp_max_nodes(max_nodes, lo=1, hi=ceiling)
    n = len(rules)
    if n > max_nodes:
```

`sespy/modules/analysis_boolean.py:102` — replace
```python
            attractors = dynamics.boolean_attractors(rules, max_nodes=safe_int(input.max_nodes(), 12))
```
with
```python
            # Server-side clamp to the slider's own range [4, 12]: a crafted
            # input must not run a 2^20 search on the shared worker.
            max_nodes = dynamics.clamp_max_nodes(
                safe_int(input.max_nodes(), 12), lo=4, hi=12)
            attractors = dynamics.boolean_attractors(rules, max_nodes=max_nodes)
```
The slider (`min=4, max=12, value=12`) is unchanged.

- [ ] **Step 4: Run** `micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_analysis_boolean_clamp.py -q` → all pass.
- [ ] **Step 5: Run the CI unit command** → green.
- [ ] **Step 6: Commit**

```powershell
git add sespy/dynamics.py sespy/modules/analysis_boolean.py tests/test_dynamics.py tests/test_analysis_boolean_clamp.py
git commit -m @'
fix(boolean): 20-node library ceiling and server-side UI clamp (P1a)

boolean_attractors clamps max_nodes to [1, ceiling] (default 20, R's
DYNAMICS_MAX_BOOLEAN_NODES) and reports the clamped cap. The Boolean module
clamps its input to the slider's own [4, 12] on the server; the UI limit
stays 12 until P7a makes the search non-blocking.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 11 (C5, after Task 4): `governance_gap` docstring + characterisation test

**Files:** Modify `sespy/network.py:966-972` (docstring only); append to `tests/test_network.py`.

**Interfaces:** none changed. `pressure_gap_fraction` keeps its Pressures-only denominator.

- [ ] **Step 1: Add the characterisation test** (green on today's code — it pins that the headline does not change). Append to `tests/test_network.py` (it already imports `Connection`, `Element`, `IsaData` from `sespy.data_structure`):
```python


def test_governance_gap_headline_unchanged_by_an_r_to_mpf_link():
    """P1a: R->MPF is canonical now, but pressure_gap_fraction keeps its
    Pressures-only denominator (characterisation; green before and after)."""
    from sespy.network import governance_gap
    els = [
        Element("R1", "r", "Responses"),
        Element("P1", "p", "Pressures"),
        Element("P2", "p2", "Pressures"),
        Element("M1", "m", "Marine Processes & Functioning"),
    ]
    base = IsaData(els, [Connection("R1", "P1", polarity="-")])
    plus = IsaData(els, [*base.connections, Connection("R1", "M1", polarity="+")])
    a, b = governance_gap(base), governance_gap(plus)
    assert a["pressure_gap_fraction"] == b["pressure_gap_fraction"] == 0.5
    assert b["gaps_by_type"]["Marine Processes & Functioning"]["uncovered"] == []
    # ecological_gap_fraction already pools MPF, so it does move.
    assert a["ecological_gap_fraction"] != b["ecological_gap_fraction"]
```
Run `micromamba run -n shiny python -m pytest tests/test_network.py -q -k governance` → passes (it is a characterisation test; there is no red step).

- [ ] **Step 2: Rewrite the docstring** — in `governance_gap`, replace:
```
    Coverage is DIRECTED: an ecological node counts as covered when at least
    one governance node has an out-edge to it. The headline
    ``pressure_gap_fraction`` uses Pressures alone as denominator — the only
    ecological layer the DAPSI(W)R(M) topology (``_CONN_TYPES``) routes a
    Response into; Marine Processes & Functioning and Ecosystem Services are
    unreachable at distance 1 by construction, so their coverage is reported
    per-type in ``gaps_by_type`` rather than pooled into the headline. A
```
with:
```
    Coverage is DIRECTED: an ecological node counts as covered when at least
    one governance node has an out-edge to it. The headline
    ``pressure_gap_fraction`` uses Pressures alone as denominator. Since P1a
    (v1.13.0) Responses -> Marine Processes & Functioning is also a canonical
    pair (Rule 12, ``_CONN_TYPES``), but the headline stays Pressures-only for
    continuity, so a published diagnostic does not change silently. MPF and
    Ecosystem Services coverage is reported per type in ``gaps_by_type``, and
    ``ecological_gap_fraction`` pools every ecological layer (so an R -> MPF
    link does move it). A
```
- [ ] **Step 3: Run** `micromamba run -n shiny python -m pytest tests/test_network.py -q -k governance` → `18 passed`. Then the CI unit command → green.
- [ ] **Step 4: Commit**

```powershell
git add sespy/network.py tests/test_network.py
git commit -m @'
docs(network): governance_gap rationale after R->MPF became canonical (P1a)

The headline pressure_gap_fraction keeps its Pressures-only denominator for
continuity; the docstring no longer claims MPF is unreachable, and says
ecological_gap_fraction pools MPF. A characterisation test pins both.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 12 (C5, after Task 9): e2e test `tests/test_link_rules_e2e.py`

**Files:** Create `tests/test_link_rules_e2e.py` (picked up by `tests/run_e2e.py` via `test_*_e2e.py`; excluded from the CI unit command by `--ignore-glob='*e2e*'`).

**Interfaces:** Consumes UI ids `#sespy_nav_entry`, `#entry-new_source`, `#entry-new_target`, `input[name="entry-new_polarity"]`, `#entry-add_connection`, `#entry-off_rule_note .sespy-off-rule-note`, `#entry-status_line`.

- [ ] **Step 1: Write the script**

```python
"""E2E for P1a link rules in ISA entry (Edit Data): the empty first picker
choice, the polarity prefill from the rule table, and the off-rule note.

Starts from the default sample project (data/sample_ses.json, loaded at
startup): 17 elements, 20 connections. Module id is "entry" (app.py:140), so
every selector is namespaced and scoped (no bare text= selectors).
"""
import asyncio

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"
SRC, TGT = "#entry-new_source", "#entry-new_target"
NOTE = "#entry-off_rule_note .sespy-off-rule-note"
MINUS = 'input[name="entry-new_polarity"][value="-"]:checked'
PLUS = 'input[name="entry-new_polarity"][value="+"]:checked'


async def wait_connections(page, n: int) -> None:
    # Pickers re-render to "" after Add, so the save is proved by the count.
    await page.wait_for_function(
        "n => (document.getElementById('entry-status_line')?.textContent || '')"
        ".includes(n + ' connections')", arg=n, timeout=30000)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        # The nav is server-rendered (cold server ~32 s idle; more under load).
        await page.wait_for_selector("#sespy_nav_entry", timeout=60000)
        await page.click("#sespy_nav_entry")
        await page.wait_for_selector(SRC, timeout=30000)
        await page.wait_for_selector(TGT, timeout=30000)
        await wait_connections(page, 20)

        # ---- default state: both pickers on the empty choice, no note ------
        assert await page.input_value(SRC) == "", "source picker not on the empty choice"
        assert await page.input_value(TGT) == "", "target picker not on the empty choice"
        assert await page.locator(NOTE).count() == 0, "note shown in the default state"
        print("default state: empty pickers, no note")

        # ---- only a source: no note --------------------------------------
        await page.select_option(SRC, "P001")
        await page.wait_for_timeout(1500)
        assert await page.locator(NOTE).count() == 0, "note shown with only a source"
        print("only a source: no note")

        # ---- P -> MPF on a free pair prefills "-" and saves ----------------
        # (P001->MPF1, P002->MPF2 and P003->MPF1 already exist in the sample.)
        await page.select_option(TGT, "MPF2")
        await page.wait_for_selector(MINUS, state="attached", timeout=15000)
        assert await page.locator(NOTE).count() == 0, "note shown for a canonical pair"
        await page.click("#entry-add_connection")
        await wait_connections(page, 21)
        print("P001 -> MPF2: polarity prefilled '-', saved (21 connections)")

        # ---- D -> GB is off-rule: note shown, still saves ------------------
        await page.wait_for_function(
            "() => document.getElementById('entry-new_source')?.value === ''",
            timeout=15000)
        await page.select_option(SRC, "D001")
        await page.select_option(TGT, "GB01")
        await page.wait_for_selector(NOTE, timeout=15000)
        text = (await page.locator(NOTE).text_content()) or ""
        assert "Drivers" in text and "Goods & Benefits" in text, text
        # The radio still shows "-" from the previous add until the seed lands.
        await page.wait_for_selector(PLUS, state="attached", timeout=15000)
        await page.click("#entry-add_connection")
        await wait_connections(page, 22)
        print("D001 -> GB01: off-rule note shown, polarity '+', saved (22 connections)")

        await browser.close()
        print("link-rules e2e: all assertions passed")


asyncio.run(main())
```

- [ ] **Step 2: Run it solo against a fresh server** (port 8000 must be free; nothing heavy alongside)

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$srv = Start-Process micromamba.exe -ArgumentList "run -n shiny python -m shiny run --port 8000 app.py" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 40          # cold server needs ~32 s before the nav renders
micromamba run -n shiny python tests/test_link_rules_e2e.py
```
Expected last line: `link-rules e2e: all assertions passed`. Then stop the server **by port** (the micromamba launcher is not the listener):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
```
(The red step for this behaviour is the in-memory `tests/test_isa_entry_link_rules.py` in Task 9; this script is the browser-level coverage. On pre-Task-9 code it would fail at `AssertionError: source picker not on the empty choice`.)

- [ ] **Step 3: Run the CI unit command** → green (the e2e file is ignored by it).

- [ ] **Step 4: Commit**

```powershell
git add tests/test_link_rules_e2e.py
git commit -m @'
test(e2e): link-rule prefill and off-rule note in Edit Data (P1a)

From the sample project: pickers start empty, only a source shows no note,
P001->MPF2 prefills "-" and saves, D001->GB01 shows the off-rule note,
seeds "+" and still saves. Saves are proved by the status-line count.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 13: Release docs — CHANGELOG, MANUAL, ISA-entry screenshot

**Files:** Modify `CHANGELOG.md` (under `## [Unreleased]`), `docs/MANUAL.md` (§9 Edit Data), `docs/screenshots/entry.png`.

- [ ] **Step 1: Check the version is still 1.13.0 everywhere**

Grep `1\.12\.3|1\.13\.0` in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` → only `1.13.0` hits; `micromamba run -n shiny python -m pytest tests/test_manual.py -q` → pass.

- [ ] **Step 2: CHANGELOG** — replace
```
## [Unreleased]

## [1.12.3] — 2026-10-17
```
with
```
## [Unreleased]

## [1.13.0] — 2026-10-17

Roadmap P1a (link rules, schema v7, R template mapper; R-parity roadmap §2
P1a). Ports R MarineSABRES 1.17.1, 1.18.0, 1.22.0 (N26/N61/N62) and 1.22.3,
against R v1.29.0 (`e33faea`).

### Added

- **DAPSI(W)R(M) link rules.** SESPy now knows R's rule table: which type
  pairs are canonical (offered as suggestions), which are valid extensions
  (A→A, P→P, MPF→MPF, R→R, D→P) and the default polarity of each pair.
- **Edit Data pre-fills polarity** when you pick a source and a target
  (for example Pressures → MPF is "−"). You can change it before adding the
  link; changing either end re-seeds it. Both pickers now start on
  "— choose —".
- **Off-rule links are allowed, with a warning.** Edit Data shows a note for
  a pair outside the framework (for example Drivers → Goods & Benefits); the
  link still saves. Loading a project, a template or an Excel/QSEM import
  accepts such links and logs them, as R does.
- **Responses → Marine Processes & Functioning** is a canonical pair
  (Rule 12). The rule-based and Claude suggestion backends now propose it.
- **Project schema v7.** Connections keep a free-text `description`, and
  elements keep fields SESPy has no column for in `r_extra`. Both are written
  only when non-empty. Project metadata gains `origin`, `r_template_version`
  and `min_sespy_version`, which every save stamps so an older SESPy warns
  before dropping data.
- **R template mapper** (`sespy.r_template_mapper`), a library function that
  converts R `*_SES_Template.json` files without loss. The 7 R templates are
  test fixtures pinned by hash (`docs/parity/R_SYNC.md`); adding them to the
  gallery is P2.
- **Excel import** reads connection `description`/`rationale` columns,
  Kumu's `Label` column for polarity, and R's element type names (Driver,
  State, Welfare, Measure, ...).

### Changed

- Boolean analysis clamps the node limit on the server to the slider's
  range (4–12), and library callers to at most 20 nodes.
- "Save project info" keeps every other project field.

### Deliberate differences from R

- SESPy keeps connection descriptions from templates (R drops them).
- SESPy keeps element `type` labels and extra fields in `r_extra` (R ignores
  them).
- The mapper rejects a duplicate link in a template (R keeps the last one).
- Excel import marks an imported Measure with `r_kind = "measure"`.
- Excel type names match case-insensitively, after trimming spaces.
- A Kumu `Label` starting with "−" (U+2212) also counts as negative.
- R's AI generator also suggests the extension pairs R→R, P→P and MPF→MPF;
  SESPy suggests canonical pairs only (extensions are planned for K1).
- The Boolean slider stays at 12 nodes (R allows 20) until P7a makes the
  search non-blocking.

### Compatibility

- SESPy 1.12.3 opens a 1.13.0 project with its "newer SESPy" warning and
  without autosave, because it would drop the new fields. A native project
  with no descriptions or `r_extra` still opens in 1.12.2.

## [1.12.3] — 2026-10-17
```

- [ ] **Step 3: MANUAL §9 Edit Data** — replace the Controls paragraph:
```
**Controls.** Under "Elements": "Label", "Type" (the seven DAPSI(W)R(M) types), "Add element", "Remove selected element". Under "Connections": "Source", "Target", "Polarity" (+ reinforcing or − opposing), "Delay" (Immediate, Short, Long), "Add connection", "Remove selected connection". Rows are selected by clicking them in the tables.
```
with:
```
**Controls.** Under "Elements": "Label", "Type" (the seven DAPSI(W)R(M) types), "Add element", "Remove selected element". Under "Connections": "Source" and "Target" (both start on "— choose —"), "Polarity" (+ reinforcing or − opposing), "Delay" (Immediate, Short, Long), "Add connection", "Remove selected connection". Rows are selected by clicking them in the tables.
```
and after the `**Reading it.** ...` paragraph insert a new paragraph:
```

**Link rules.** SESPy follows the DAPSI(W)R(M) framework rules used by the R toolbox. When both a source and a target are chosen, "Polarity" is pre-filled with the rule's default for that pair of types: for example Pressures → Marine Processes & Functioning is "−", and Responses → Drivers, Activities or Pressures is "−". You can change it before adding the link; choosing a different source or target pre-fills it again. If the pair is not a standard DAPSI(W)R(M) link (for example Drivers → Goods & Benefits), a yellow note says so. The link can still be added. Elements without a type are never flagged.
```

- [ ] **Step 4: Re-shoot only the ISA-entry screenshot**

`tests/make_docs_screenshots.py` has no per-panel option: it shoots every panel into `--out`. Shoot into a scratch dir and copy back only `entry.png`:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # nothing
$srv = Start-Process micromamba.exe -ArgumentList "run -n shiny python -m shiny run --port 8000 app.py" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 40
micromamba run -n shiny python tests/make_docs_screenshots.py --port 8000 --out <scratchpad>\shots
Copy-Item <scratchpad>\shots\entry.png docs\screenshots\entry.png
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Open `docs/screenshots/entry.png` (Read tool) and check the pickers show "— choose —". Run `attrib +P docs\screenshots\entry.png` (OneDrive: keep it local so the About→Manual image loads).

- [ ] **Step 5: Run** `micromamba run -n shiny python -m pytest tests/test_manual.py -q` and the CI unit command → green.

- [ ] **Step 6: Commit**

```powershell
git add CHANGELOG.md docs/MANUAL.md docs/screenshots/entry.png
git commit -m @'
docs(release): 1.13.0 changelog, manual link rules, Edit Data screenshot (P1a)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```

---

### Task 14: Gates — full e2e, MosaicSES, reviews (no commit)

- [ ] **Step 1: CI unit command** on the branch tip → green (≈1050 passed, 1 skipped).

- [ ] **Step 2: Full e2e gate, detached** (the Bash tool kills anything past 10 min even backgrounded). Port 8000 free, nothing heavy running, then:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$log = "<scratchpad>\e2e-p1a.log"
Start-Process micromamba.exe -ArgumentList "run -n shiny python -u tests/run_e2e.py" -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden
```
Poll in bounded PowerShell calls (e.g. `Start-Sleep -Seconds 240; Get-Content $log -Tail 15`) until the summary prints; do not park on a background monitor. Expected: every script PASS, including the new `test_link_rules_e2e.py` (one more script than the last green run). Any red: rerun that script **solo** (Task 12 Step 2 procedure) before believing it; a red that is green solo is load flake, a red that stays red is a regression. After the run: port 8000 free, `git status --short` shows only the user's `LITERATURE/` entries, and sweep orphans:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CreationDate -gt (Get-Date).AddHours(-2) } | Select-Object ProcessId, CreationDate, CommandLine
```

- [ ] **Step 3: MosaicSES gate** (it imports SESPy from this working tree):
```powershell
cd ..\MosaicSES
micromamba run -n shiny python -m pytest tests -q -p no:cacheprovider
cd ..\SESPy
```
Expected: all green (pre-checked while planning: MosaicSES's non-e2e suite, 544 passed + 1 skipped, against a full P1a implementation). MosaicSES must never be gated on `-k "not e2e"`. Triage: a red that compares an exact metadata dict is a MosaicSES fixture needing `origin`/`r_template_version`/`min_sespy_version` (fix in MosaicSES, separate commit there); anything else is a SESPy regression.

- [ ] **Step 4: Implementation review loop** — superpowers:requesting-code-review over `aadb874..HEAD`, repeated until a round finds no Critical or Important issues; each fix is its own commit followed by the CI unit command.

---

### Task 15: Merge, tag v1.13.0, deploy, verify — **each step needs the user's go-ahead**

- [ ] **Step 1 (user go-ahead): Merge onto `origin/main` in a temp worktree** (local `main` is behind and the untracked `LITERATURE/` files block a fast-forward in the main checkout):
```powershell
git fetch origin
git worktree add <scratchpad>\sespy-release origin/main
cd <scratchpad>\sespy-release
git switch -c release/1.13.0
git merge --no-ff feat/p1a-link-rules -m @'
Merge v1.13.0 (P1a: link rules, schema v7, R template mapper) into main

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Qp36XeWVVjTmQinjy7ZtUX
'@
```
Conflicts are possible only in `CHANGELOG.md`/`LITERATURE/` (origin/main has literature-alert commits); keep both sides. Then in the worktree run the CI unit command → green.

- [ ] **Step 2 (user go-ahead): Push and tag**
```powershell
git push origin release/1.13.0:main
git tag -a v1.13.0 -m "v1.13.0 — P1a: link rules, schema v7, R template mapper"
git push origin v1.13.0
```

- [ ] **Step 3 (user go-ahead): Deploy from the worktree**
```powershell
Copy-Item "C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy\deploy\config.env" deploy\config.env   # gitignored, not in the worktree
bash deploy/deploy.sh
```
Expected: `==> Deploying SESPy v1.13.0 to ...`. The deployed `sespy/` is symlinked into the live MosaicSES, so this deploy changes MosaicSES immediately.

- [ ] **Step 4: Verify on laguna with the worker's Python** (user site disabled: `-s`). Write `<scratchpad>\verify_v7.py`:
```python
"""Run on laguna from the SESPy app dir with the worker python:
/opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_v7.py"""
import json
import sys

sys.path.insert(0, ".")
import sespy  # noqa: E402
from sespy.data_structure import (  # noqa: E402
    PROJECT_SCHEMA_VERSION, Connection, Element, IsaData, Project, ProjectMetadata,
)
from sespy.persistent_storage import project_to_bytes, validate_project_payload  # noqa: E402

assert sespy.__version__ == "1.13.0", sespy.__version__
assert PROJECT_SCHEMA_VERSION == 7
p = Project(ProjectMetadata(name="v7 check", origin="r_template", r_template_version="2.3"),
            IsaData([Element("P1", "p", "Pressures", r_extra={"r_type": "pressure"}),
                     Element("M1", "m", "Marine Processes & Functioning")],
                    [Connection("P1", "M1", polarity="-", description="d")]))
raw = json.loads(project_to_bytes(p))
assert raw["metadata"]["min_sespy_version"] == "1.13.0"
assert raw["isa_data"]["elements"][0]["r_extra"] == {"r_type": "pressure"}
res = validate_project_payload(raw)
assert res.valid and not res.project.newer_build, res.errors
assert res.project.isa_data == p.isa_data
print("v7 round-trip OK:", sespy.__file__)
```
Then, in the **Bash tool** from the worktree (`config.env` is bash syntax; use the scratchpad path with forward slashes):
```bash
source deploy/config.env
scp "<scratchpad>/verify_v7.py" "$DEPLOY_SERVER:/tmp/verify_v7.py"
ssh "$DEPLOY_SERVER" "cd '$DEPLOY_DIR' && /opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_v7.py; rm -f /tmp/verify_v7.py"
```
Expected: `v7 round-trip OK: <DEPLOY_DIR>/sespy/__init__.py`. Also open the live SESPy app in a browser → Edit Data: the pickers show "— choose —" and Pressures → MPF prefills "−".

- [ ] **Step 5: Recheck the live MosaicSES**
```powershell
cd ..\MosaicSES
micromamba run -n shiny python deploy/verify_live.py
cd ..\SESPy
```
Expected: all checks pass (HTTP 200, nav renders, scenario authored, sibling apps answer).

- [ ] **Step 6: Clean up**
```powershell
git worktree remove <scratchpad>\sespy-release
git fetch origin
git log --oneline origin/main..feat/p1a-link-rules   # must print nothing (all merged)
git branch -D feat/p1a-link-rules                    # -D: local main never received the merge
git branch -f main origin/main                       # only if main is not checked out
```
Record the release in memory (P1a shipped, v1.13.0, deploy status; MosaicSES node M follow-up still open).
