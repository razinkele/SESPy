# P1b — Response register, indicator fields, stakeholder roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SESPy v1.15.0 (project schema 8): R's Response register as a new page and a `Project.response_measures` block, six indicator fields on elements, a connection-description editor, D5.4 stakeholder roles, R re-pinned to v1.33.0.

**Architecture:** A Shiny-free helper module `sespy/response_register.py` ports R's register schema (code lists, normaliser, 9-language reverse label map, `safe_counter` IDs, prioritisation score, display labels); `ResponseRegister` is a dataclass in `sespy/data_structure.py` that `Project` serialises only when non-empty. The UI is a new module `sespy/modules/response_register.py` (4 tabs) plus edit panels added to `isa_data_entry.py` and a roles field in `pims_stakeholders.py`. R strings are vendored, with R's keys, from pinned R fixtures by the existing sync (`sespy/r_template_catalogue.py`), extended with a translation-subset step.

**Tech Stack:** Python 3.13 (env `shiny`), Shiny for Python 1.7 (`shiny.testserver.test_server` for module tests), pandas, matplotlib (`render.plot`), openpyxl, pytest, Playwright (standalone async e2e scripts run by `tests/run_e2e.py`).

**Spec:** `docs/superpowers/specs/2026-10-21-p1b-response-register-indicators-design.md` (approved 2026-10-21). Section numbers below (§) refer to it.

## Global Constraints

- Python: always `micromamba run -n shiny python ...`. Never `pip install`, never a venv, never `python - <<EOF` or a bare `python -`, never a multi-line `python -c` (Windows splits it per line); use a `.py` file in the scratchpad.
- Work happens in the worktree `C:/Users/arturas.baziukas/AppData/Local/sespy-p1b` (written `<W>`) on branch `feat/p1b-response-register`, cut from the tip of `docs/p1b-design`. The env's editable `sespy` points at the main checkout (old code): every Python command imports this tree only because it runs **from `<W>` as cwd** (`Push-Location <W>` … `Pop-Location`, or `-WorkingDirectory`), and every detached run sets `$env:PYTHONPATH = '<W>'`. Never edit the main checkout.
- Never `git commit -a` / `git add -A` / `git add .`; stage explicit paths. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Multi-line messages: the PowerShell tool with a single-quoted here-string (`'@` at column 0); never a PowerShell here-string in the Bash tool.
- Shell state does not persist between tool calls and the cwd resets: each block defines its variables and paths.
- CI unit command (every task ends green on it; run from `<W>`, `timeout: 600000`): `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`. Baseline on `c7fde7f`: ≈1230 passed (record the exact number in Task 0).
- Lint: `micromamba run -n shiny python -m ruff check sespy tests app.py --statistics` must not total more than the Task 0 baseline; every file this plan creates is clean (`ruff check <file>` → `All checks passed!`).
- Edits are placed by quoted anchor, never by line number (CRLF working copy).
- Version **1.15.0** in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` line 3; `PROJECT_SCHEMA_VERSION = 8`; `SCHEMA_MIN_READER = {7: "1.13.0", 8: "1.15.0"}`; all four in the first commit (Task 1).
- R reference: MarineSABRES_SES_Shiny **v1.33.0 = `4017feb`**, app dir `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny` (`<R>`; git prefix `MarineSABRES_SES_Shiny/`). **Read-only**: `git show`, `rev-parse`, `diff`, `log`, `grep` only, always at a tag.
- Every R value ported (column names, codes, scores, normaliser behaviour) cites its R `file:line` at v1.33.0 in a code comment or test docstring; expected test values are derived by hand from the pinned R source and R's testthat files (§11), never by running R.
- Serialisation rule (spec §4): new Element fields and the `response_measures` block are written **only when non-empty**; `Stakeholder` keeps `asdict` (its two new keys are always written).
- Nothing heavy runs alongside an e2e run; port 8000 must be free before any e2e run (`Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue` prints nothing); sweep orphan `python` processes after big runs.
- Shiny: read `references/modules-core.md`, `reactivity.md`, `data-frames.md`, `testing.md` under `micromamba run -n shiny shiny skills path shiny-for-python` before Tasks 9–12. In `test_server`, a `reactive.event(..., ignore_init=True)` button needs `set_inputs(x=0)` then `set_inputs(x=1)`. Module labels resolve through `session.root_scope()` translators (v1.14.1).
- Merge, tag, push, deploy (Task 16) each need the user's explicit go-ahead.

## Review Focus

1. **A v1.14 reader opening a v8 file**: it must be refused-to-overwrite by the P0b guard (`min_sespy_version` 1.15.0 > running). Owning task: **Task 1** (`test_v8_file_is_newer_build_for_a_1_14_reader`, monkeypatching `_running_version` to `"1.14.2"`).
2. **Hand-edited or legacy register data** — measures as a JSON object instead of a list, a row that is a string, `Cost` `"cheap"`, `PestleTag` as a JSON array, a translated Status in Lithuanian, `counter` `"7"` or `null`: load never fails, the value is normalised or defaulted with one log line. Owning task: **Task 7** (`test_from_dict_tolerates_malformed_register` parametrised over those six inputs).
3. **IDs after delete and on loaded projects** — delete RM003 of RM001–RM003 then add → RM004; a loaded file with `counter` 0 and IDs up to RM012 → RM013; non-numeric `RMabc` ignored. Owning task: **Task 6** (`test_safe_counter_cases`).
4. **Responses elements** — the indicator fields are hidden in the edit panel for Responses, but a file that carries them on a Responses element keeps them through load → save. Owning tasks: **Task 2** (`test_indicator_fields_on_responses_survive_round_trip`), **Task 9** (`test_indicator_inputs_hidden_for_responses`).
5. **Language switch while the register is open** — stored values are codes, so switching UI language re-labels the table without changing data; labels typed in another language on import map back to codes. Owning tasks: **Task 6** (`test_reverse_map_all_languages`), **Task 11** (`test_language_switch_relabels_not_rewrites`).

---

## File Structure

**Created**
| Path | Responsibility |
|---|---|
| `sespy/response_register.py` | R register port: code lists, `normalize_measures/impacts/milestones`, `reverse_label_map`, `safe_counter`, add/update/delete helpers, `priority_rows`, `display_value`, `ebm_code_choices`, `suggest_target`. Shiny-free. |
| `sespy/response_reports.py` | `build_response_workbook()` → xlsx bytes (3 sheets). |
| `sespy/modules/response_register.py` | Response Register page (4 tabs). |
| `sespy/translations/modules/{response_measures,response_governance,wp5_vocabulary,wp5_scenarios,wp5_governance,indicator_registry}.json` | Vendored R key subsets (generated by the sync). |
| `tests/parity/r_source/{constants.R,response_measures_schema.R,stakeholder_schema.R}`, `tests/parity/r_translations/*.json` (6) | R v1.33.0 fixtures (generated by the sync). |
| `tests/test_schema_v8.py` | v8 bump, Element fields, register block, stakeholder fields. |
| `tests/test_response_register.py` | Helper unit tests. |
| `tests/parity/test_r_register_parity.py` | Python constants vs the R fixtures. |
| `tests/test_response_register_module.py`, `tests/test_isa_entry_edit.py` | `test_server` module tests. |
| `tests/test_response_register_e2e.py`, `tests/test_isa_edit_e2e.py` | Playwright e2e. |

**Modified**: `sespy/data_structure.py`, `sespy/__init__.py`, `pyproject.toml`, `sespy/constants.py` (`POLICY_TARGET_CODES`), `sespy/stakeholders.py`, `sespy/r_template_mapper.py`, `sespy/excel_import.py`, `sespy/r_template_catalogue.py`, `sespy/modules/isa_data_entry.py`, `sespy/modules/pims_stakeholders.py`, `sespy/stakeholder_reports.py`, `sespy/translations/core.json`, `app.py`, `sespy/templates/marinesabres/*.json` (regenerated), `tests/parity/r_sync.json`, `docs/parity/R_SYNC.md`, `docs/MANUAL.md`, `CHANGELOG.md`, `README.md`, existing tests named per task.

Commit order: Task 1 first (version + schema). Tasks 2–8 are data and sync; 9–12 UI; 13 e2e; 14 docs; 15 gates; 16 release.

---

### Task 0: Branch and baseline

**Files:** none.

- [ ] **Step 1: Branch**

```powershell
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -C $W switch docs/p1b-design
git -C $W log --oneline -1          # the newest docs(p1b) commit (this plan)
git -C $W switch -c feat/p1b-response-register
git -C $W status --short            # expect nothing
```

- [ ] **Step 2: Baselines.** Run the CI unit command and the lint statistics from `<W>`; write both numbers into the ledger. Confirm `git -C <R> rev-parse --short=7 'v1.33.0^{commit}'` prints `4017feb`.

---

### Task 1: Version 1.15.0 and schema 8

**Files:**
- Modify: `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` (line 3), `sespy/data_structure.py` (`PROJECT_SCHEMA_VERSION`, `SCHEMA_MIN_READER`)
- Modify tests: `tests/test_data_structure.py` (`test_schema_version_is_7` → `test_schema_version_is_8`), `tests/test_schema_v7.py` (`test_p0b_still_flags_a_v8_file`: use `PROJECT_SCHEMA_VERSION + 1`, `schema_max` = `PROJECT_SCHEMA_VERSION`; keep `:57`)
- Create: `tests/test_schema_v8.py`

**Interfaces:** Produces `sespy.__version__ == "1.15.0"`, `PROJECT_SCHEMA_VERSION == 8`, `SCHEMA_MIN_READER[8] == "1.15.0"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_schema_v8.py`:

```python
def test_schema_8_and_floor():
    assert PROJECT_SCHEMA_VERSION == 8
    assert SCHEMA_MIN_READER == {7: "1.13.0", 8: "1.15.0"}

def test_every_save_is_stamped_1_15_0():
    d = Project.from_isa(IsaData()).to_dict()
    assert d["metadata"]["schema_version"] == 8
    assert d["metadata"]["min_sespy_version"] == "1.15.0"

def test_v8_file_is_newer_build_for_a_1_14_reader(monkeypatch):
    raw = Project.from_isa(IsaData()).to_dict()
    monkeypatch.setattr(data_structure, "_running_version", lambda: "1.14.2")
    assert newer_build_info(raw) == {"min_version": "1.15.0", "running": "1.14.2"}
```

- [ ] **Step 2:** Run `pytest tests/test_schema_v8.py -q` → 3 failed.
- [ ] **Step 3:** Edit the three version lines (`1.14.2` → `1.15.0`) and the two constants; update the two pinned tests named above.
- [ ] **Step 4:** `pytest tests/test_schema_v8.py tests/test_schema_v7.py tests/test_data_structure.py tests/test_manual.py tests/test_schema_read_ahead.py -q` → all pass. Then the CI unit command. **Expected red:** `tests/test_r_template_catalogue.py` (shipped templates still carry 7/1.13.0, drift check) — it stays red until Task 5's sync; record the failing test names in the ledger, nothing else may fail.
- [ ] **Step 5: Commit** `feat(schema): v1.15.0 and project schema 8 (P1b)`.

---

### Task 2: Element indicator fields

**Files:**
- Modify: `sespy/data_structure.py` (`Element`, `_isa_from_dict`, `_element_to_dict`), `sespy/constants.py`
- Test: `tests/test_schema_v8.py`

**Interfaces:**
- Produces `data_structure.INDICATOR_FIELDS: tuple[str, ...] = ("indicator", "indicator_unit", "data_source", "registry_id", "registry_version", "policy_target")` (R `ISA_INDICATOR_COLUMNS`, `constants.R:855`, lowercased as R's loader does, `data_structure.R:947-949`).
- `Element` gains these six as `str = field(default="", kw_only=True)`, declared after `r_extra`.
- `constants.POLICY_TARGET_CODES: tuple[str, ...] = ("kmgbf_30x30", "eu_nrr", "msfd_ges_d1", "msfd_ges_d6", "national_mpa_pct")` (`constants.R:940`).

- [ ] **Step 1: Failing tests**

```python
def test_indicator_fields_round_trip_and_omit_when_empty():
    a = Element(id="MPF1", label="x", type="Marine Processes & Functioning",
                indicator="Coral cover", indicator_unit="%", policy_target="kmgbf_30x30")
    b = Element(id="D1", label="y", type="Drivers")
    d = Project.from_isa(IsaData(elements=[a, b])).to_dict()
    e0, e1 = d["isa_data"]["elements"]
    assert e0["indicator"] == "Coral cover" and e0["policy_target"] == "kmgbf_30x30"
    assert "data_source" not in e0                       # empty -> omitted
    assert not set(INDICATOR_FIELDS) & set(e1)           # v7 element shape
    back = Project.from_dict(json.loads(json.dumps(d))).isa_data.elements
    assert back[0] == a and back[1] == b

def test_indicator_field_non_str_is_coerced(caplog):  # 12 -> "12", None -> ""

def test_indicator_fields_on_responses_survive_round_trip():
    r = Element(id="R1", label="Quota", type="Responses", indicator="TAC")
    assert Project.from_dict(Project.from_isa(IsaData(elements=[r])).to_dict()).isa_data.elements[0].indicator == "TAC"

def test_new_element_fields_are_keyword_only():   # Element("D1","x","Drivers","d",3) still works; fields kw_only
```

- [ ] **Step 2:** run → fail. **Step 3:** implement. In `_isa_from_dict` coerce each indicator value: `None` → `""`, non-str → `str(v)` with one `_log.warning` naming element id and field. `_element_to_dict` adds each non-empty field after `confidence` and before `r_extra`, in `INDICATOR_FIELDS` order.
- [ ] **Step 4:** tests + CI unit command (Task 1's expected red only). **Step 5: Commit** `feat(schema): indicator fields on elements (P1b)`.

---

### Task 3: Stakeholder roles in the model

**Files:**
- Modify: `sespy/data_structure.py` (`Stakeholder`, `Project.from_dict`), `sespy/stakeholders.py`
- Test: `tests/test_schema_v8.py`, `tests/test_stakeholders.py`

**Interfaces:**
- `Stakeholder.ne_roles: str = field(default="", kw_only=True)`, `Stakeholder.source_id: str = field(default="", kw_only=True)`.
- `stakeholders.STAKEHOLDER_ROLES: tuple[str, ...] = ("Inputters", "Extractors", "Regulators", "Affectees", "Beneficiaries", "Influencers")` (`constants.R:563-571`).
- `stakeholders.normalize_ne_roles(value: str | list[str] | None) -> str` — split on `;`, strip, drop unknown (one `logging` warning listing them), dedupe, order as `STAKEHOLDER_ROLES`, join `;` (`stakeholder_schema.R:30-37`).
- `add_stakeholder` / `update_stakeholder` pass `ne_roles` through `normalize_ne_roles`; `Project.from_dict` normalises each loaded stakeholder's `ne_roles`.

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.parametrize("raw,expected", [
    ("Regulators;Inputters", "Inputters;Regulators"),
    (["Influencers", "Influencers", " Affectees "], "Affectees;Influencers"),
    ("regulators;Bogus", ""),            # codes are case-sensitive, as R
    (None, ""), ("", ""),
])
def test_normalize_ne_roles(raw, expected): ...

def test_stakeholder_roles_round_trip():   # ne_roles + source_id survive to_dict/from_dict; both keys always present
def test_add_stakeholder_normalises_roles():
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit → commit `feat(stakeholders): D5.4 roles and source id fields (P1b)`.

---

### Task 4: Mapper `indicator` hoist and Excel indicator columns

**Files:**
- Modify: `sespy/r_template_mapper.py` (the generic extras loop, `:110-117`), `sespy/excel_import.py` (`ELEMENT_DESC_COLS`, element construction near `:188`)
- Test: `tests/test_r_template_mapper.py`, `tests/test_excel_import.py`

**Interfaces:** Consumes `INDICATOR_FIELDS` (Task 2). Produces `excel_import.ELEMENT_INDICATOR_COLS: dict[str, tuple[str, ...]]` mapping each field to the column names it accepts: the R TitleCase name (`Indicator`, `Indicator_Unit`, `Data_Source`, `Registry_Id`, `Registry_Version`, `Policy_Target`) and its lowercase form.

- [ ] **Step 1: Failing tests**

```python
def test_caribbean_indicator_moves_to_the_field():
    project, report = convert_r_template(_load("Caribbean_SES_Template.json"))
    s1 = _element_for_r_id(project, "S1")   # small helper using the mapper's id rule (see existing mapper tests)
    assert s1.indicator == "Volume of Sargassum biomass on beaches (tons/year)"
    assert "indicator" not in s1.r_extra and s1.r_extra["baseline"] == "Minimal pre-2011"
    assert "indicator" not in report.extra_fields
    assert sum(1 for e in project.isa_data.elements if e.indicator) == 10

def test_excel_indicator_column_fills_the_field_not_description():
    # a sheet with Name, Type, Indicator, Indicator_Unit -> description "" and indicator/unit set
def test_excel_description_still_read():
```
(Find S1 by the mapper's actual id scheme; read it from `tests/test_r_template_mapper.py` before writing the test.)

- [ ] **Step 2:** fail. **Step 3:** mapper: the key `indicator` goes to `Element(indicator=str(v))` instead of `r_extra`; all other extras unchanged. Excel: `ELEMENT_DESC_COLS = ("description", "Description")`; read the six indicator columns via `_pick`.
- [ ] **Step 4:** tests + CI unit (Task 1's red only). **Step 5: Commit** `feat(import): R indicator into Element.indicator; Excel indicator columns (P1b)`.

---

### Task 5: Re-pin R to v1.33.0, new fixtures, vendored translations, regenerate templates

**Files:**
- Modify: `sespy/r_template_catalogue.py` (`INPUTS`; new `TRANSLATION_SUBSETS`; `sync()` writes the vendored files), `tests/test_r_template_catalogue.py` (counts of pinned files, the `:202` floor `"1.15.0"`), `tests/parity/test_r_sync.py` if it counts files, `docs/parity/R_SYNC.md` (prose + triage, generated block by the sync)
- Generated by the sync: `tests/parity/r_sync.json`, fixtures under `tests/parity/r_source/` and `tests/parity/r_translations/`, `sespy/translations/modules/*.json` (6), `sespy/templates/marinesabres/*.json`, `catalogue.json` if changed

**Interfaces:**
- `INPUTS` gains `constants.R`, `functions/response_measures_schema.R`, `functions/stakeholder_schema.R` → `tests/parity/r_source/<name>`, and `translations/modules/<f>.json` → `tests/parity/r_translations/<f>.json` for the 6 files.
- `TRANSLATION_SUBSETS: dict[str, tuple[str, ...]]` — file stem → key prefixes (empty tuple = whole file):
  `response_measures: ()`, `response_governance: ()`,
  `wp5_vocabulary: ("modules.wp5_vocabulary.instrument.", "modules.wp5_vocabulary.measure.", "modules.wp5_vocabulary.tenet.")`,
  `wp5_scenarios: ("modules.wp5_scenarios.pestle.",)`,
  `wp5_governance: ("modules.wp5_governance.role.", "modules.wp5_governance.ne_roles")`,
  `indicator_registry: ("modules.indicator_registry.policy_target", "modules.indicator_registry.field_")`.
  Measured while planning at v1.33.0: 142, 26, 47, 6, 8, 10 keys = **239**, all 9 languages complete, no clash with `core.json`.
- The sync writes `sespy/translations/modules/<f>.json` as `{"languages": [...], "translation": {<selected keys in R order>}}`, LF, `write_bytes`; `--check` reports drift in them like any other output.

- [ ] **Step 1: Failing tests** (in `tests/test_r_template_catalogue.py`):

```python
def test_vendored_translations_match_fixture_subsets():
    # for each stem: vendored keys == keys of the fixture selected by TRANSLATION_SUBSETS, texts equal, 9 languages
def test_vendored_translation_key_counts():
    assert {s: len(_vendored(s)) for s in TRANSLATION_SUBSETS} == {
        "response_measures": 142, "response_governance": 26, "wp5_vocabulary": 47,
        "wp5_scenarios": 6, "wp5_governance": 8, "indicator_registry": 10}
def test_shipped_templates_are_schema_8():   # every shipped template: schema_version 8, min_sespy_version "1.15.0"
```

- [ ] **Step 2:** fail. **Step 3:** implement the subset step. **Step 4: Run the real sync** from `<W>`: `micromamba run -n shiny python -m scripts.sync_r_templates --rev v1.33.0` then `... --check` → clean. Inspect `git -C <W> status --short`: expected changes are exactly the generated paths listed above. `git diff --stat sespy/templates/marinesabres` shows all 7 templates changed (schema stamp) and Caribbean additionally moves 10 indicators.
- [ ] **Step 5: R_SYNC.md prose** (outside the generated block): adopted in 1.15.0 (P1b), previous pin v1.31.0; the 9 old files identical v1.31.0 → v1.33.0; the triage table from spec §9 verbatim, plus the line "Load DA actor list: P4 (user decision 2026-10-21)".
- [ ] **Step 6:** CI unit command → fully green (Task 1's red is gone). Lint gate. **Commit** `chore(r-sync): pin R v1.33.0; register fixtures and vendored translations (P1b)`.

---

### Task 6: Register helpers (`sespy/response_register.py`)

**Files:**
- Create: `sespy/response_register.py`, `tests/test_response_register.py`, `tests/parity/test_r_register_parity.py`

**Interfaces (Produces; all pure, no Shiny):**
- Constants (values from spec §4.2.1–4.2.2, each with its `constants.R` line):
  `RM_REGISTER_COLUMNS` (34-tuple, R order), `RM_DISPLAY_COLUMNS` (15-tuple, `constants.R:844-846`), `TENET_CODES` (11), `RM_TYPE_CODES`, `RM_TARGET_CODES` (`dict[str, str]` code → label-key suffix; `"multiple": "multiple_levels"`, others identity), `RM_STATUS_CODES`, `GOVERNANCE_LEVELS`, `TENET_LEVELS`, `PESTLE_CODES`, `KIND_CODES = ("instrument", "measure")`, `EFFECTIVENESS_LEVELS = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")`, `FEASIBILITY_LEVELS = ("HIGH", "MEDIUM", "LOW")`, `EBM_POLICY_INSTRUMENTS: tuple[tuple[str, str], ...]` (code, level) and `EBM_MANAGEMENT_MEASURES: tuple[tuple[str, str, str], ...]` (code, category, dapsiwrm_target) (`constants.R:780-801`), `IMPACT_COLUMNS`, `MILESTONE_COLUMNS`, `IMPACT_PROBLEM_TYPES = ("specific_pressure", "specific_activity", "specific_driver", "system_wide_issue")`, `IMPACT_STRENGTHS = ("strong", "moderate", "weak")`, `TIMEFRAMES = ("immediate", "short_term_1_3y", "medium_term_3_10y", "long_term_10y")`, `MILESTONE_STATUSES = ("pending", "in_progress", "completed", "delayed")`.
- `reverse_label_map() -> dict[str, dict[str, str]]` — vocab name (`type, target, status, problem_type, strength, timeframe, milestone_status`) → {label (stripped, every language of the vendored `sespy/translations/modules/response_measures.json`) → code}; first occurrence wins; `functools.cache`. Reads the vendored file, never the fixture.
- `normalize_measures(rows: Any) -> list[dict[str, Any]]` — R `normalize_response_measures` (`response_measures_schema.R:49-107`) step for step (spec §4.2.1).
- `normalize_impacts(rows: Any) -> list[dict[str, str]]`, `normalize_milestones(rows: Any) -> list[dict[str, str]]` — exactly the 5 columns; labels → codes for ProblemType/ImpactStrength/Timeframe/Status; unknown values pass through.
- `safe_counter(counter: Any, ids: Iterable[str], prefix: str = "RM") -> int` (`data_structure.R:25-33`).
- `ebm_code_choices(kind: str) -> list[str]` — instruments: codes with level `"type"`; measures: all 12; else `[]` (`response_measures_schema.R:118-121`).
- `suggest_target(ebm_measure_code: str) -> str` — A → activities, P → pressures, C → state, `A|P|C` → multiple, else "" (`:110-115`).
- `priority_rows(measures: list[dict], w_eff: float = 0.4, w_feas: float = 0.3, w_cost: float = 0.3) -> list[dict[str, Any]]` — each measure plus `EffScore`, `FeasScore`, `CostScore`, `PriorityScore`, `Rank`; R's formula (spec §6.1 tab 3). A `None` Cost gives `CostScore = None` and `PriorityScore = None`, as R's NA. Sort by `PriorityScore` descending, stable, with `None` scores after all numeric ones (R `order()` puts NA last); `Rank` 1..n over the sorted list.
- `display_value(column: str, value: Any, tr: Callable[[str], str]) -> str` — labels per spec §6.1 (key families: `modules.response.measures.<suffix>` for Type/Target/Status and for Effectiveness/Feasibility lowercased; `modules.response.governance.kind.<code>`, `.level.<code>`, `.tenet_level.<level>` (blank → `.tenet_level.not_assessed`); `EbmCode` → `"<code> " + tr("modules.wp5_vocabulary.instrument|measure.<code with . → _>")`; `PestleTag` → `", "`-joined `modules.wp5_scenarios.pestle.<code>`; impact/milestone vocabularies via `modules.response.measures.<code>`); unknown values and missing keys return the raw value.

Task 6 is list-level only; the `ResponseRegister`-level helpers come in Task 7, in this same module.

- [ ] **Step 1: Failing tests** (`tests/test_response_register.py`), expected values cited to R:

```python
def test_columns():
    assert len(RM_REGISTER_COLUMNS) == 34 and RM_REGISTER_COLUMNS[0] == "ID"
    assert RM_REGISTER_COLUMNS[-1] == "TenetSource" and RM_REGISTER_COLUMNS[9] == "Cost"

def test_normalize_selects_and_orders_columns():      # unknown key dropped; missing -> "" / Cost None
def test_cost_coercion():                              # "7" -> 7.0, "cheap" -> None, None -> None
def test_list_cell_joined():                           # Stakeholders ["a","b"] -> "a;b"
def test_pestle_cleaned():                             # "legal; political;bogus;legal" -> "political;legal"
def test_tenet_levels():                               # Tenet_ecol_effective "Intermediate " -> "intermediate";
                                                       # Tenet_tech_feasible "intermediate" -> "" ; "FULL" -> "full"
def test_reverse_map_all_languages():                  # for each code of type/target/status/strength/timeframe/milestone
                                                       # and each of 9 languages, map[label] == code; "Activities:" -> "activities"
def test_label_to_code_on_normalise():                 # Status "Įgyvendinta"-style lt label -> "implemented" (take the real lt text from the vendored file)
def test_handtyped_values_pass_through():              # Type "something else" stays
def test_normalise_is_idempotent():
def test_safe_counter_cases():
    assert safe_counter(0, ["RM001", "RM012", "RMabc", "SH099"]) == 12
    assert safe_counter(None, []) == 0 and safe_counter("5", ["RM002"]) == 5
def test_ebm_code_choices_and_suggest_target():        # "3.5" absent; 23-? count from fixture; measure "output" -> "pressures"
def test_priority_rows_reproduce_r():                  # 3 measures, hand-computed scores to 1e-9, ties keep input order
def test_display_value():                              # English labels: "Policy instrument", "Regional sea",
                                                       # "Minimal compliance", "Not assessed", "Activities:", "Political, Legal"
```

`tests/parity/test_r_register_parity.py`: extract each R vector named above from `tests/parity/r_source/constants.R` (a small regex helper for `NAME <- c(...)`, CRLF → LF) and assert equality with the Python constant (order included); assert `RM_REGISTER_COLUMNS` equals R's; assert the normaliser step list in `response_measures_schema.R` still contains the tenet loop (string presence of `"intermediate"` and `setdiff(TENET_LEVELS`), so an R change surfaces at re-pin.

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(register): R response-register schema port (P1b)`.

---

### Task 7: `Project.response_measures`

**Files:**
- Modify: `sespy/data_structure.py`, `sespy/response_register.py` (register-level wrappers)
- Test: `tests/test_schema_v8.py`, `tests/test_response_register.py`

**Interfaces:**
- In `data_structure.py`:

```python
@dataclass
class ResponseRegister:
    measures: list[dict[str, Any]] = field(default_factory=list)
    impacts: list[dict[str, str]] = field(default_factory=list)
    milestones: list[dict[str, str]] = field(default_factory=list)
    counter: int = 0
    def is_empty(self) -> bool: ...          # no rows and counter == 0
    def to_dict(self) -> dict[str, Any]: ... # deep copies, row-wise
    @classmethod
    def from_dict(cls, raw: Any) -> "ResponseRegister": ...
```
  `from_dict` imports `sespy.response_register` lazily (inside the function) and runs the three normalisers; non-dict `raw` → empty + one warning; `counter` → `int` when it is an int or a numeric string, else 0 with a warning; then `counter = safe_counter(counter, measure IDs)`.
- `Project.response_measures: ResponseRegister = field(default_factory=ResponseRegister, kw_only=True)` (before `newer_build`). `to_dict` adds `"response_measures"` only when `not is_empty()`; `from_dict` reads it when present.
- In `sespy/response_register.py` (register-level, all return new objects, never mutate):
  - `add_measure(reg: ResponseRegister, fields: dict[str, Any], *, today: str) -> tuple[ResponseRegister, str]` — new ID per spec §4.2.3, `DateAdded = today`, row normalised; returns the new ID.
  - `update_measure(reg, measure_id: str, fields: dict[str, Any]) -> tuple[ResponseRegister, bool]` — R `update` (`response_module.R:515-525`): never changes `ID`; `False` and unchanged when the ID is absent.
  - `delete_measures(reg, ids: Iterable[str]) -> tuple[ResponseRegister, int]` — counter unchanged; the int counts impact + milestone rows whose `ResponseID` is in `ids` (they are kept).
  - `add_impact(reg, fields) -> ResponseRegister`, `delete_impact(reg, index: int) -> ResponseRegister`, `add_milestone(reg, fields) -> ResponseRegister`, `delete_milestone(reg, index: int) -> ResponseRegister`.

- [ ] **Step 1: Failing tests**

```python
def test_register_round_trip_all_34_columns():   # one fully filled measure + impact + milestone,
                                                 # through project_to_bytes -> json.loads -> validate_project_payload(...).valid -> Project.from_dict
def test_empty_register_is_omitted():            # "response_measures" not in to_dict()
def test_counter_alone_is_kept():                # counter 3, no rows -> serialised
@pytest.mark.parametrize("bad", [
    {"measures": {"ID": "RM001"}}, {"measures": ["oops"]}, {"measures": [{"ID": "RM001", "Cost": "cheap"}]},
    {"measures": [{"ID": "RM001", "PestleTag": ["legal", "social"]}]},
    {"measures": [{"ID": "RM001", "Status": "<lt label of implemented>"}]},
    {"counter": "7"}, {"counter": None}])
def test_from_dict_tolerates_malformed_register(bad): ...   # loads; values normalised/defaulted
def test_replace_carries_register():             # project.replace(metadata=...) keeps response_measures
def test_add_update_delete_cycle():              # RM001, RM002; delete RM001 -> refs count; add -> RM003
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit → commit `feat(schema): response register block (P1b)`.

---

### Task 8: SESPy-only i18n keys

**Files:** Modify `sespy/translations/core.json`, `tests/test_i18n.py`.

**Interfaces:** Produces these keys, all 9 languages (translate the English given; keep `{n}`, `{id}`, `{version}` placeholders identical across languages):
`nav.responses` "Response Register"; `responses.title` "Response register"; `responses.tab_register` "Register"; `responses.tab_impacts` "Impacts"; `responses.tab_priority` "Prioritisation"; `responses.tab_milestones` "Milestones and export"; `responses.edit_selected` "Edit selected"; `responses.delete_selected` "Delete selected"; `responses.cancel` "Cancel"; `responses.save` "Save measure"; `responses.select_first` "Select a row first."; `responses.name_type_required` "Name and type are required."; `responses.deleted_with_refs` "{n} impact or milestone rows still refer to the deleted measures."; `responses.tenet_source` "Tenet ratings source"; `responses.target_element_hint` "Pick elements from this project; IDs not in the project are kept."; `responses.download_xlsx` "Download Excel"; `entry.edit_selected` "Edit selected"; `entry.save_changes` "Save changes"; `entry.cancel_edit` "Cancel"; `entry.description` "Description"; `entry.indicators_heading` "Indicator"; `entry.registry` "WP5 registry: {id} (revision {version})"; `entry.connection_description` "Connection description".
Before adding a key, check whether R's vendored files already carry the same string (tab titles, "Delete selected", "Add response measure"); prefer the R key and drop the SESPy one from this list — record each such swap in the commit message.

- [ ] **Step 1:** failing `test_p1b_keys_present(translations)` listing every key above plus a sample of vendored R keys (`modules.response.measures.activities`, `modules.response.governance.kind.instrument`, `modules.wp5_governance.role.inputters`, `modules.indicator_registry.policy_target.eu_nrr`) → all 9 languages present and non-empty. **Steps 2–5:** fail → add keys → pass + CI unit → commit `feat(i18n): P1b UI strings (P1b)`.

---

### Task 9: ISA entry edit panels

**Files:**
- Modify: `sespy/modules/isa_data_entry.py`
- Create: `tests/test_isa_entry_edit.py`

**Interfaces:** Consumes `INDICATOR_FIELDS`, `POLICY_TARGET_CODES`. New ids (module namespace `entry`):
- Elements: button `edit_element` (under `elements_table`), `output_ui("element_editor")` rendering — while `editing_element: reactive.Value[str | None]` is set — inputs `el_label`, `el_description` (text area), and for non-Responses `el_indicator`, `el_indicator_unit`, `el_data_source`, `el_policy_target` (`input_selectize`, choices `""` + `POLICY_TARGET_CODES` labelled via `modules.indicator_registry.policy_target.<code>`, `options={"create": True}`), a read-only `entry.registry` line when `registry_id` is set, buttons `save_element`, `cancel_element`.
- Connections: button `edit_connection`, `output_ui("connection_editor")` with `conn_description` (text area), `save_connection`, `cancel_connection`; `editing_connection: reactive.Value[tuple[str, str] | None]` keyed by (source, target).
- The editor UI is rendered from `editing_*` only (`@reactive.event`-gated repopulation as `pims_stakeholders._repopulate`, never re-filled by `project_data` writes); save goes through `_replace(...)` with `dataclasses.replace(element, ...)` so `r_extra` and untouched fields survive; empty label → warning toast, no write.

- [ ] **Step 1: Failing `test_server` tests**

```python
def test_edit_element_saves_indicator_fields():   # select MPF row, edit_element 0/1, set el_* , save_element 0/1
                                                  # -> element.indicator/unit/data_source/policy_target set; r_extra kept
def test_indicator_inputs_hidden_for_responses():  # editor HTML for a Responses element has no el_indicator
def test_free_text_policy_target_kept():
def test_edit_connection_description():
def test_autosave_write_does_not_clobber_editor(): # project_data.set(...) while editing leaves el_* untouched
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(entry): edit element indicators and connection descriptions (P1b)`.

---

### Task 10: Stakeholder roles UI and export

**Files:** Modify `sespy/modules/pims_stakeholders.py` (`_register_panel`, `_form_fields`, `_clear_form`, `_repopulate`, `stakeholder_table`), `sespy/stakeholder_reports.py`; Test: `tests/test_stakeholders.py` (or a new `test_server` test file `tests/test_stakeholders_module.py`), `tests/test_stakeholder_reports.py`.

**Interfaces:** input `sh_ne_roles` (`input_selectize`, multiple, choices `STAKEHOLDER_ROLES` labelled `modules.wp5_governance.role.<lower>`, label `modules.wp5_governance.ne_roles`, help text `modules.wp5_governance.ne_roles_hint`); table column `roles` (translated, `", "`-joined); workbook stakeholder sheet gains a `Roles` column (codes `;`-joined, as stored). `source_id` is never shown or edited (and an edit keeps it).

- [ ] Tests: add with two roles → stored `"Inputters;Regulators"` in canonical order; edit repopulates the selectize; an edit keeps `source_id`; workbook has the `Roles` column. **Steps:** fail → implement → pass + CI unit → commit `feat(stakeholders): D5.4 roles field (P1b)`.

---

### Task 11: Response Register page — Register tab and wiring

**Files:**
- Create: `sespy/modules/response_register.py`, `tests/test_response_register_module.py`
- Modify: `app.py` (`NAV` after `entry`: `NavItem(id="responses", icon="list-check", label="Response Register", label_key="nav.responses")`; `PANELS` after Edit Data: `ui.nav_panel("Response Register", response_register_ui("responses"), value="responses")`; `NAV_TO_STEP["responses"] = "create"`; `response_register_server("responses", project_data=..., event_bus=..., translator=translator)`), `docs/MANUAL.md` (new `## 10. Response Register` after `## 9. Edit Data`, renumber 10–40 → 11–41 and the Contents list; one-paragraph stub, finished in Task 14), `tests/make_docs_screenshots.py` (add `responses` to its NAV-order probe table)

**Interfaces:** `response_register_ui()` / `response_register_server(input, output, session, *, project_data, event_bus, translator=None)` mirroring `pims_stakeholders`. Tabs `navset_tab(id="response_tabs")` with values `register`, `impacts`, `priority`, `milestones`. Register tab ids: `rm_name`, `rm_type`, `rm_target`, `rm_status`, `rm_description`, `rm_mechanism`, `rm_target_element` (selectize multiple: project element IDs except Responses, plus any stored IDs not in the project; stored `;`-joined), `rm_effectiveness`, `rm_feasibility`, `rm_cost` (numeric 1–10, default 5), `rm_stakeholders`, `rm_barriers`; inside `ui.tags.details` (summary `modules.response.governance.section_title`): `rm_kind`, `rm_ebm_code` (choices from `ebm_code_choices(kind)`; a measure code calls `suggest_target` and updates `rm_target` when it returns non-empty), `rm_gov_level`, `rm_competent_authority`, `rm_legal_basis`, `rm_paired_with` (`""` + `"ID – Name"`, excluding the measure being edited), `rm_impl_stakeholders` (selectize multiple, `"Name (ID)"`, stored `;`-joined IDs; hint `modules.response.governance.no_stakeholders_hint` when none), `rm_pestle` (multiple), `rm_tenet_<code>` ×11 (choices `""` not assessed, minimal, intermediate only for `ecol_effective`, full); `output_ui("tenet_source")` read-only when set. Buttons `save_measure`, `cancel_measure`, `edit_measure`, `delete_measures`; table `measures_table` (`RM_DISPLAY_COLUMNS`, `display_value`, `selection_mode="rows"`). Every write: `project_data.set(project.replace(response_measures=...))` + `event_bus.emit_isa_change()`.

- [ ] **Step 1: Failing `test_server` tests**

```python
def test_add_two_measures_ids():                  # RM001, RM002; DateAdded today; Type stored as code
def test_add_requires_name_and_type():            # warning toast, no write
def test_edit_repopulates_and_updates_in_place(): # ID unchanged, counter unchanged
def test_delete_reports_references():             # toast text contains the count from delete_measures
def test_measure_code_suggests_target():          # rm_kind "measure", rm_ebm_code "output" -> rm_target "pressures"
def test_language_switch_relabels_not_rewrites(): # switch to "de": table text changes, stored row unchanged
def test_every_nav_panel_still_has_a_manual_section():  # existing tests/test_help_offcanvas.py + tests/test_manual.py pass
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(responses): Response Register page, register tab (P1b)`.

---

### Task 12: Impacts, prioritisation, milestones, Excel export

**Files:** Modify `sespy/modules/response_register.py`; Create `sespy/response_reports.py`; Test `tests/test_response_register_module.py`, `tests/test_response_register.py`.

**Interfaces:**
- Impacts tab ids: `impact_response` (select `"ID: Name"`), `impact_problem`, `impact_element` (select, as `rm_target_element` but single), `impact_strength`, `impact_timeframe`, `add_impact` (requires response + problem), `impacts_table`, `delete_impact`.
- Priority tab: sliders `weight_effectiveness` 0.4, `weight_feasibility` 0.3, `weight_cost` 0.3 (0–1 step 0.1); `priority_table` from `priority_rows`; `ef_plot` (`render.plot`, matplotlib: effectiveness vs feasibility 3×3 grid with quadrant labels, points labelled by ID, unknown/blank levels plotted at 0).
- Milestones tab: `impl_response`, `impl_milestone`, `impl_date` (default today + 365 days), `impl_status`, `impl_notes`, `add_milestone` (requires response + milestone), `milestones_table`, `delete_milestone`, `download_response_xlsx`.
- `response_reports.build_response_workbook(reg: ResponseRegister, tr: Callable[[str], str]) -> bytes` — sheets `Response_Measures` (all 34 columns, values through `display_value`), `Impact_Matrix`, `Implementation` (`response_module.R` `build_response_excel`).

- [ ] Tests: impact add/delete; milestone add with the default date; `priority_table` rows match `priority_rows`; workbook sheet names, header row equals `RM_REGISTER_COLUMNS`, a coded Type rendered as its English label. **Steps:** fail → implement → pass + CI unit + lint → commit `feat(responses): impacts, prioritisation, milestones, Excel (P1b)`.

---

### Task 13: e2e scripts

**Files:** Create `tests/test_response_register_e2e.py`, `tests/test_isa_edit_e2e.py`; Modify `tests/test_stakeholders_e2e.py` (a roles step).

Selectors are namespaced ids only (`#responses-…`, `#entry-…`, `#stakeholders-…`), never bare `text=`; wait for `.shiny-bound-input` before clicking dynamically rendered buttons; `wait_for_function` on DOM state, no fixed sleeps beyond the existing idiom; nav via `#sespy_nav_responses`.

- `test_response_register_e2e.py`: add two measures (name + type) → table shows RM001, RM002; edit RM001's status → table updates; add an impact for RM002 and a milestone; delete RM001 → reference toast; download Excel → file name ends `.xlsx`, size > 0. Last line printed: `response register e2e: all assertions passed`.
- `test_isa_edit_e2e.py`: on the sample project select an element, edit indicator + unit, save; select a Responses element → no `#entry-el_indicator`; edit a connection description; reload-free check through the CLD tooltip is **not** required. Last line: `isa edit e2e: all assertions passed`.
- Stakeholders e2e: pick two roles on add → table Roles cell shows both labels.

- [ ] Run the three solo with `<scratchpad>\e2e_solo.py` (the runner-equivalent helper from the P2 session; loads `tests/run_e2e.py` by path and runs named scripts with SHINY_TESTMODE, PYTHONPATH and warm-up), port 8000 free before and after. Then commit `test(e2e): response register, ISA edit, stakeholder roles (P1b)`.

---

### Task 14: Docs

**Files:** `docs/MANUAL.md` (§10 Response Register: what each tab does, IDs never reused, deletes do not cascade, Excel export; §9 Edit Data: the edit panels and the six indicator fields, Responses excluded; §6 Stakeholders: roles; Contents), `CHANGELOG.md` (`## [1.15.0]` naming P1b, R v1.33.0, schema 8 with the "older SESPy will refuse to overwrite" note, the Excel "Indicator column" behaviour change, deferred items: indicator registry picker and Load DA actor list → P4, Word exports → P6c/P14, workshop → proposed P15), `README.md` (feature line; unit and e2e counts updated in Task 15 from the gate output), screenshots via `tests/make_docs_screenshots.py` for `responses`, `entry`, `stakeholders` (port 8000 free; commit only those PNGs).

Roadmap amendments (spec §2; separate branch `docs/r-parity-roadmap`, separate worktree, pushed only with the user's go-ahead): M shipped in MosaicSES 0.4.0 with fresh line refs; P1b section: "Load DA actor list" → P4; R baseline v1.33.0; WS-10 workshop as proposed P15 (after P4).

- [ ] `pytest tests/test_manual.py tests/test_help_offcanvas.py -q` green; commit `docs: P1b manual, changelog, screenshots (P1b)`.

---

### Task 15: Gates

- [ ] **Step 1:** CI unit command, lint gate, `micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check` → clean.
- [ ] **Step 2: Code review loop** (superpowers:requesting-code-review, BASE = `git merge-base docs/p1b-design HEAD`) until no Critical/Important; each fix its own commit + Step 1 again.
- [ ] **Step 3: Full e2e**, detached, nothing else running, port 8000 free:

```powershell
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
$log = '<scratchpad>\e2e-p1b.log'
$env:PYTHONPATH = $W
Start-Process micromamba.exe -ArgumentList "run -n shiny python -u tests/run_e2e.py" -WorkingDirectory $W -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden
```
Watch with `pwsh -File <scratchpad>\watch_log.ps1` (Monitor) or bounded polls. Expected: all scripts pass (37 = 35 + 2 new), 0 retries ideally; a retry is investigated, not waved through.
- [ ] **Step 4: MosaicSES gate** (unit + full e2e, never `-k "not e2e"`), with `$env:PYTHONPATH = $W` and `-WorkingDirectory` the MosaicSES repo, command `run -n shiny python -m pytest tests -q -p no:cacheprovider`, detached, port 8000 free. Also confirm by test that a MosaicSES compartment round-trips a project with a register and indicator fields (`multises` `MultiSES.to_dict`/`from_dict`), added to MosaicSES only if its suite lacks such a case — **that addition is a MosaicSES commit and needs the user's go-ahead**; otherwise just run it as a scratch script.
- [ ] **Step 5:** README counts from the gate output; commit.

---

### Task 16: Release v1.15.0 — **each step needs the user's go-ahead**

Same mechanics as v1.14.1/v1.14.2 (handoff notes): (1) fetch; `merge-base --is-ancestor origin/main HEAD` guard (rebase or merge if `main` moved, then re-run Task 15 Steps 1 and 3); CHANGELOG date; (2) push `feat/p1b-response-register:main`, throw on failure; (3) `git tag -a v1.15.0`, push the tag, check `ls-remote`; (4) `describe --exact-match`, copy `config.env`, `bash deploy/deploy.sh`; (5) laguna verify with the worker python `-s` (version 1.15.0; a v8 round trip of a project with one measure, one impact, one milestone, an indicator field and a stakeholder role; the 7 templates load, Caribbean S1 has its indicator); (6) MosaicSES `deploy/verify_live.py`; (7) guarded cleanup: worktree remove, `branch -d` (merged), `git fetch origin main:main`. Then update `.remember/remember.md` and memory.
