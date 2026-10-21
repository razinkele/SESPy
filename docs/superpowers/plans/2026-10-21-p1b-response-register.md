# P1b — Response register, indicator fields, stakeholder roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SESPy v1.15.0 (project schema 8): R's Response register as a new page and a `Project.response_measures` block, six indicator fields on elements, a connection-description editor, D5.4 stakeholder roles with R's stakeholder ID counter, R re-pinned to v1.33.0.

**Architecture:** A Shiny-free helper module `sespy/response_register.py` ports R's register schema (code lists, normaliser, 9-language reverse label map, prioritisation score, display labels); R's `safe_counter` lives in `sespy/utils.py` and serves both measure and stakeholder IDs. `ResponseRegister` is a dataclass in `sespy/data_structure.py` that `Project` serialises only when non-empty. The UI is a new module `sespy/modules/response_register.py` (4 tabs) plus edit panels added to `isa_data_entry.py` and a roles field in `pims_stakeholders.py`. R strings are vendored, with R's keys, from pinned R fixtures by the existing sync (`sespy/r_template_catalogue.py`), extended with a translation-subset step.

**Tech Stack:** Python 3.13 (env `shiny`), Shiny for Python **1.8.0** (the env's version; `shiny.testserver.test_server` for module tests), pandas, matplotlib (`render.plot`), openpyxl, pytest, Playwright (standalone async e2e scripts run by `tests/run_e2e.py`).

**Spec:** `docs/superpowers/specs/2026-10-21-p1b-response-register-indicators-design.md` (approved 2026-10-21; amended in plan review round 1). Section numbers below (§) refer to it.

## Global Constraints

- Python: always `micromamba run -n shiny python ...`, never bare `pytest`. Never `pip install`, never a venv, never `python - <<EOF` or a bare `python -`, never a multi-line `python -c` (Windows splits it per line); use a `.py` file in the scratchpad.
- Work happens in the worktree `C:/Users/arturas.baziukas/AppData/Local/sespy-p1b` (written `<W>`) on branch `feat/p1b-response-register`, cut from the tip of `docs/p1b-design`. The env's editable `sespy` points at the main checkout `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy` (`<S>`, on `docs/p2-design`, **v1.13.0 code**). `python -m ...` and `python -c ...` import `<W>`'s package only when run **from `<W>` as cwd** (`Push-Location <W>` … `Pop-Location`, or `-WorkingDirectory`). A scratch `.py` file does not: Python puts the script's own directory first on `sys.path`, so the editable install wins (measured in the round-1 dry run). Run every scratch script and every detached process with `$env:PYTHONPATH = '<W>'`. Never edit the main checkout.
- Never `git commit -a` / `git add -A` / `git add .`; stage explicit paths. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Multi-line messages: the PowerShell tool with a single-quoted here-string (`'@` at column 0); never a PowerShell here-string in the Bash tool.
- Shell state does not persist between tool calls and the cwd resets: each block defines its variables and paths. PowerShell native commands do not throw: print or test `$LASTEXITCODE` after each one that matters.
- CI unit command (every task ends green on it; run from `<W>`): `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`. Baseline on `c7fde7f`: **1230 passed, 1 skipped** (measured 2026-10-21). It takes ≈ 8 min on this machine: pass `timeout: 600000`, or run it detached and poll.
- Lint: `micromamba run -n shiny python -m ruff check sespy tests app.py --statistics` must not total more than the baseline, **54** on `c7fde7f` (50 I001, 2 E741, 1 E501, 1 F821); every file this plan creates is clean (`ruff check <file>` → `All checks passed!`).
- Edits are placed by quoted anchor, never by line number (CRLF working copy). Line numbers in this plan locate code; re-read before editing.
- Version **1.15.0** in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` line 3; `PROJECT_SCHEMA_VERSION = 8`; `SCHEMA_MIN_READER = {7: "1.13.0", 8: "1.15.0"}`; all four in the first commit (Task 1).
- R reference: MarineSABRES_SES_Shiny **v1.33.0 = `4017feb`**, app dir `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny` (`<R>`). R also has a newer `v1.34.0`; the pin stays v1.33.0, the version laguna runs. **Read-only**: `git show`, `rev-parse`, `diff`, `log`, `grep`, `ls-tree` only, always at a tag. `git -C <R> show v1.33.0:MarineSABRES_SES_Shiny/<path>` takes a path from the repo root; pathspecs of `ls-tree`/`grep`/`diff` are relative to the app dir (`git -C <R> grep -n <pattern> v1.33.0 -- translations/modules`).
- Every R value ported (column names, codes, scores, normaliser and display behaviour) cites its R `file:line` at v1.33.0 in a code comment or test docstring; expected test values are derived by hand from the pinned R source and R's testthat files (§11; testthat citations name `4017feb`), never by running R.
- Serialisation rule (spec §4): new Element fields, the `response_measures` block and `stakeholder_counter` are written **only when non-empty / non-zero**; `Stakeholder` keeps `asdict` (its two new keys are always written).
- Nothing heavy runs alongside an e2e run; port 8000 must be free before any e2e run (`Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue` prints nothing); sweep orphan `python` processes after big runs.
- Shiny: read `references/modules-core.md`, `reactivity.md`, `data-frames.md`, `testing.md` under `micromamba run -n shiny shiny skills path shiny-for-python` before Tasks 9–12. Module labels resolve through `session.root_scope()` translators (v1.14.1). `test_server` mechanics (verified by probes in plan review round 1):
  - A `reactive.event(..., ignore_init=True)` button needs `set_inputs(x=0)` then `set_inputs(x=1)` (then 2, 3, … for later clicks).
  - Selecting row *i* of a data grid needs **both** inputs: `scope.set_inputs(**{"<id>_cell_selection": {"type": "row", "rows": [i]}, "<id>_data_view_rows": list(range(n))})` (`n` = rows in the grid). The selection alone is silently ignored (shiny `render/_data_frame.py:503-514`). Several rows: `"rows": [0, 2]`.
  - `ui.update_*` and `ui.notification_show` calls are not reflected back into inputs. Record them by monkeypatching `shiny.ui.<function>` (as `tests/test_isa_entry_link_rules.py:37-42`), or assert on an `output_ui`'s HTML (`scope.get_output(<id>).value["html"]`).
  - A "not clobbered" test changes `project_data` and asserts the editor's HTML or the recorded update calls did **not** change. Every "no write" test also performs a valid write in the same test (positive control).
- Merge, tag, push, deploy (Task 16) each need the user's explicit go-ahead.

## Review Focus

1. **Stored values outside a select's choices** — a hand-typed `Type`, an unvalidated `Effectiveness` ("Very high"), a dangling `PairedWith` (RM099) or `ImplementingStakeholders` (SH404), a free-text `policy_target`: opening the record in Edit and saving must not rewrite them (Shiny drops a `selected` value that is not a choice). Owning tasks: **Task 9** (`test_free_text_policy_target_kept`), **Task 11** (`test_edit_keeps_dangling_and_pass_through_values`).
2. **Hand-edited or legacy register data** — measures as a JSON object instead of a list, a row that is a string, `Cost` `"cheap"`, `PestleTag` as a JSON array, a Lithuanian Status label, `counter` `"7"` or `null`: load never fails; the value is normalised or defaulted with one log line. Owning task: **Task 7** (`test_from_dict_tolerates_malformed_register`, seven cases).
3. **IDs after delete and on loaded projects** — measures: delete RM003 of RM001–RM003 then add → RM004; a file with `counter` 0 and IDs up to RM012 keeps counter 0 on load and adds RM013. Stakeholders: delete SH002 of SH001–SH002 then add → SH003, never SH002 again. Owning tasks: **Task 3** (`test_safe_counter_cases`, `test_add_stakeholder_uses_the_counter`), **Task 7** (`test_loaded_counter_is_kept_not_raised`), **Task 10** (`test_deleted_id_is_not_reused`).
4. **Files from older builds** — a project saved from the v1.14.x Caribbean template keeps `r_extra["indicator"]` and must show it in the new Indicator field; a Responses element carrying indicator fields keeps them; a v7 file loads with empty defaults; a v1.14 reader refuses to overwrite a v8 file. Owning tasks: **Task 2** (`test_saved_r_extra_indicator_is_hoisted_on_load`, `test_indicator_fields_on_responses_survive_round_trip`), **Task 7** (`test_v7_file_loads_with_new_defaults`), **Task 1** (`test_v8_file_is_newer_build_for_a_1_14_reader`).
5. **Language switch while the register is open** — stored values are codes, so switching the UI language re-labels the table without changing data; labels typed in another language on import map back to codes. Owning tasks: **Task 6** (`test_reverse_map_all_languages`), **Task 11** (`test_language_switch_relabels_not_rewrites`).

---

## File Structure

**Created**
| Path | Responsibility |
|---|---|
| `sespy/response_register.py` | R register port: code lists, `normalize_measures/impacts/milestones`, `reverse_label_map`, add/update/delete helpers, `references_to`, `priority_rows`, `ef_points`, `display_value`, `ebm_code_choices`, `ebm_picker_label`, `suggest_target`. Shiny-free. |
| `sespy/response_reports.py` | `build_response_workbook()` → xlsx bytes (3 sheets). |
| `sespy/modules/response_register.py` | Response Register page (4 tabs). |
| `sespy/translations/modules/{response_measures,response_governance,wp5_vocabulary,wp5_scenarios,wp5_governance,indicator_registry}.json` | Vendored R key subsets (generated by the sync). |
| `tests/parity/r_source/{constants.R,response_measures_schema.R,stakeholder_schema.R}`, `tests/parity/r_translations/*.json` (6) | R v1.33.0 fixtures (generated by the sync). |
| `tests/test_schema_v8.py` | v8 bump, Element fields, register block, stakeholder fields and counter. |
| `tests/test_response_register.py` | Helper unit tests. |
| `tests/parity/test_r_register_parity.py` | Python constants vs the R fixtures. |
| `tests/test_response_register_module.py`, `tests/test_isa_entry_edit.py`, `tests/test_stakeholders_module.py` | `test_server` module tests. |
| `tests/test_response_register_e2e.py`, `tests/test_isa_edit_e2e.py` | Playwright e2e. |

**Modified**: `sespy/data_structure.py`, `sespy/__init__.py`, `pyproject.toml`, `sespy/utils.py`, `sespy/constants.py` (`POLICY_TARGET_CODES`), `sespy/stakeholders.py`, `sespy/r_template_mapper.py`, `sespy/excel_import.py`, `sespy/r_template_catalogue.py`, `sespy/modules/isa_data_entry.py`, `sespy/modules/pims_stakeholders.py`, `sespy/translations/core.json`, `app.py`, `sespy/templates/marinesabres/*.json` (regenerated), `tests/parity/r_sync.json`, `docs/parity/R_SYNC.md`, `docs/MANUAL.md`, `CHANGELOG.md`, `README.md`, and the existing tests each task names.

Commit order: Task 1 first (version + schema). Tasks 2–8 are data and sync; 9–12 UI; 13 e2e; 14 docs; 15 gates; 16 release. **Every commit leaves the CI unit command green.**

---

### Task 0: Branch and baseline

**Files:** none.

- [ ] **Step 1: Branch** (the upstream makes the post-release `git branch -d` work; it is the only delete form the auto-mode classifier allows)

```powershell
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -C $W switch docs/p1b-design
git -C $W log --oneline -1          # the newest docs(p1b) commit (this plan)
git -C $W switch -c feat/p1b-response-register
git -C $W branch --set-upstream-to=origin/main feat/p1b-response-register
git -C $W status -sb                # "## feat/p1b-response-register...origin/main [ahead N]", nothing else
```

- [ ] **Step 2: Baselines.** Run the CI unit command and the lint statistics from `<W>`; write both numbers into the ledger (expected 1230 passed, 1 skipped; 54). Confirm `git -C <R> rev-parse --short=7 'v1.33.0^{commit}'` prints `4017feb`.

---

### Task 1: Version 1.15.0 and schema 8

**Files:**
- Modify: `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` (line 3), `sespy/data_structure.py` (`PROJECT_SCHEMA_VERSION`, `SCHEMA_MIN_READER`)
- Modify tests:
  - `tests/test_data_structure.py`: `test_schema_version_is_7` → `test_schema_version_is_8`.
  - `tests/test_schema_v7.py`: `test_p0b_still_flags_a_v8_file` → `test_p0b_still_flags_a_newer_file` with `_payload(schema_version=PROJECT_SCHEMA_VERSION + 1)` and `{"schema": PROJECT_SCHEMA_VERSION + 1, "schema_max": PROJECT_SCHEMA_VERSION}`; `test_stamp_equal_to_floor_is_kept` (`:231-233`) builds with `min_sespy_version=FLOOR` and expects `FLOOR`; `test_older_stamp_is_raised_to_floor` (`:236-238`) expects `FLOOR`. Keep `:57`.
  - `tests/test_r_template_catalogue.py:202`: `== "1.13.0"` → `== SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]` (import both from `sespy.data_structure`).
- Regenerate: `sespy/templates/marinesabres/*_SES_Template.json` (7), with the sync's fixture mode.
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

- [ ] **Step 2:** From `<W>`: `micromamba run -n shiny python -m pytest tests/test_schema_v8.py -q` → 3 failed.
- [ ] **Step 3:** Edit the three version lines (`1.14.2` → `1.15.0`) and the two constants; update the pinned tests listed above.
- [ ] **Step 4: Restamp the shipped templates** (the 7 R fixtures are unchanged, so fixture mode rewrites the projects at schema 8 / 1.15.0 without touching the pin):

```powershell
Push-Location 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
try {
  micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures
  "sync exit: $LASTEXITCODE"            # 0, eight "wrote ..." lines
  micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check
  "check exit: $LASTEXITCODE"           # 0, no other output
  git status --short sespy/templates    # exactly the 7 *_SES_Template.json files
} finally { Pop-Location }
```
- [ ] **Step 5:** `micromamba run -n shiny python -m pytest tests/test_schema_v8.py tests/test_schema_v7.py tests/test_data_structure.py tests/test_manual.py tests/test_schema_read_ahead.py tests/test_r_template_catalogue.py -q` → all pass. Then the CI unit command → green, no exceptions.
- [ ] **Step 6: Commit** `feat(schema): v1.15.0 and project schema 8 (P1b)`, staging the files above and `sespy/templates/marinesabres`.

---

### Task 2: Element indicator fields

**Files:**
- Modify: `sespy/data_structure.py` (`Element`, `_isa_from_dict`, `_element_to_dict`), `sespy/constants.py`
- Modify test: `tests/test_schema_read_ahead.py:43-49` (`indicator` is no longer an unknown key)
- Test: `tests/test_schema_v8.py`

**Interfaces:**
- Produces `data_structure.INDICATOR_FIELDS: tuple[str, ...] = ("indicator", "indicator_unit", "data_source", "registry_id", "registry_version", "policy_target")` (R `ISA_INDICATOR_COLUMNS`, `constants.R:855`, lowercased as R's loader does, `data_structure.R:947-949`).
- `Element` gains these six as `str = field(default="", kw_only=True)`, declared after `r_extra`.
- `constants.POLICY_TARGET_CODES: tuple[str, ...] = ("kmgbf_30x30", "eu_nrr", "msfd_ges_d1", "msfd_ges_d6", "national_mpa_pct")` (`constants.R:940`).
- `_isa_from_dict`: each indicator value `None` → `""` silently (as `Connection.description`, `data_structure.py:185-189`); a non-str → `str(v)` with one `_log.warning` naming the element id and the field. **Hoist (spec §4.3):** when an element's `indicator` is empty and `r_extra.get("indicator")` is a non-empty `str`, move it into `indicator` and drop the key from `r_extra`; one `_log.info` per project with the count. `_element_to_dict` writes each non-empty field after `confidence` and before `r_extra`, in `INDICATOR_FIELDS` order.

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

def test_indicator_field_coercion(caplog):
    d = Project.from_isa(IsaData(elements=[Element(id="D1", label="x", type="Drivers")])).to_dict()
    d["isa_data"]["elements"][0].update(indicator=12, indicator_unit=None)
    with caplog.at_level(logging.WARNING):
        el = Project.from_dict(d).isa_data.elements[0]
    assert (el.indicator, el.indicator_unit) == ("12", "")
    assert sum("indicator" in r.getMessage() for r in caplog.records) == 1   # the int warns, None is silent

def test_indicator_fields_on_responses_survive_round_trip():
    r = Element(id="R1", label="Quota", type="Responses", indicator="TAC")
    assert Project.from_dict(Project.from_isa(IsaData(elements=[r])).to_dict()).isa_data.elements[0].indicator == "TAC"

def test_new_element_fields_are_keyword_only():
    Element("D1", "x", "Drivers", "d", 3)                      # positional shape unchanged
    with pytest.raises(TypeError):
        Element("D1", "x", "Drivers", "d", 3, {}, "Coral cover")

def test_saved_r_extra_indicator_is_hoisted_on_load():
    raw = {"metadata": {"name": "P", "schema_version": 7}, "isa_data": {"elements": [
        {"id": "S1", "label": "Sargassum", "type": "Marine Processes & Functioning",
         "r_extra": {"indicator": "Volume (t/yr)", "baseline": "Minimal pre-2011"}},
        {"id": "S2", "label": "Reef", "type": "Marine Processes & Functioning",
         "indicator": "kept", "r_extra": {"indicator": "left alone"}}], "connections": []}}
    s1, s2 = Project.from_dict(raw).isa_data.elements
    assert s1.indicator == "Volume (t/yr)" and s1.r_extra == {"baseline": "Minimal pre-2011"}
    assert s2.indicator == "kept" and s2.r_extra == {"indicator": "left alone"}
```
Modify `tests/test_schema_read_ahead.py:43-49` → `test_unknown_element_keys_are_dropped_known_ones_load`: keep both keys in the payload; assert `not hasattr(el, "future_field")` and `el.indicator == "SST"`.

- [ ] **Step 2:** run → fail. **Step 3:** implement as Interfaces say.
- [ ] **Step 4:** tests + CI unit command → green. **Step 5: Commit** `feat(schema): indicator fields on elements (P1b)`.

---

### Task 3: Stakeholder roles and R's stakeholder ID counter

**Files:**
- Modify: `sespy/utils.py`, `sespy/data_structure.py` (`Stakeholder`, `Project`, `to_dict`, `from_dict`), `sespy/stakeholders.py`
- Test: `tests/test_utils.py`, `tests/test_schema_v8.py`, `tests/test_stakeholders.py`

**Interfaces:**
- `utils.safe_counter(counter: Any, ids: Iterable[str], prefix: str) -> int` — R `data_structure.R:25-33`: the counter as a finite number (an int, a float, a numeric string; `bool`, `None`, non-numeric, NaN/inf → 0), the integer suffixes of the `str` ids that start with `prefix` (non-numeric suffixes ignored), result `int(max(counter, *suffixes))`. Task 6/7 import it from here.
- `Stakeholder.ne_roles: str = field(default="", kw_only=True)`, `Stakeholder.source_id: str = field(default="", kw_only=True)`.
- `stakeholders.STAKEHOLDER_ROLES: tuple[str, ...] = ("Inputters", "Extractors", "Regulators", "Affectees", "Beneficiaries", "Influencers")` (R's `STAKEHOLDER_TYPES`, `constants.R:564-571`; renamed because SESPy already has an unrelated `stakeholder_type`).
- `stakeholders.normalize_ne_roles(value: str | Sequence[str] | None) -> str` — a str splits on `;`, a list or tuple (what a selectize returns) is taken item by item; strip, drop unknown values (one `logging` warning listing them), dedupe, order as `STAKEHOLDER_ROLES`, join with `;` (`stakeholder_schema.R:30-37`).
- `Project.stakeholder_counter: int = field(default=0, kw_only=True)` (R `pims$stakeholder_counter`, `data_structure.R:222`), declared before `newer_build`. `to_dict` writes a top-level `"stakeholder_counter"` only when > 0. `from_dict` reads it through a private `_coerce_counter(value, where: str) -> int` (also used by Task 7): an `int` (not `bool`) as is, a numeric string or finite float → `int(float(v))`, anything else → 0 with one warning.
- `from_dict` normalises each loaded stakeholder's `ne_roles` and coerces `source_id` (`None` → "" silently, non-str → `str()` with a warning). It imports `sespy.stakeholders` **inside the function**: `stakeholders.py` imports `data_structure` at module level, so a top-level import would be a cycle.
- `stakeholders.add_stakeholder(items, fields_, *, today, counter: int = 0) -> list[Stakeholder]` — the new ID is `f"SH{safe_counter(counter, [s.id for s in items], 'SH') + 1:03d}"` (R `pims_stakeholder_module.R:458-460`), no longer `next_id`; `fields_["ne_roles"]`, when present, goes through `normalize_ne_roles`. `update_stakeholder` normalises `ne_roles` the same way. The caller stores the new counter as `safe_counter(counter, [s.id for s in new_list], "SH")` (Task 10). Engagement and communication IDs keep `next_id`.

- [ ] **Step 1: Failing tests**

```python
def test_safe_counter_cases():            # tests/test_utils.py; R data_structure.R:25-33
    assert safe_counter(0, ["RM001", "RM012", "RMabc", "SH099"], "RM") == 12
    assert safe_counter(None, [], "RM") == 0
    assert safe_counter("5", ["RM002"], "RM") == 5
    assert safe_counter(3.0, ["SH001"], "SH") == 3
    assert safe_counter(True, ["SH002"], "SH") == 2      # a bool is not a count
    assert safe_counter("x", ["SH007", None], "SH") == 7

@pytest.mark.parametrize("raw,expected", [
    ("Regulators;Inputters", "Inputters;Regulators"),
    (["Influencers", "Influencers", " Affectees "], "Affectees;Influencers"),
    (("Regulators", "Inputters"), "Inputters;Regulators"),     # a selectize returns a tuple
    ("regulators;Bogus", ""),            # codes are case-sensitive, as R
    (None, ""), ("", ""),
])
def test_normalize_ne_roles(raw, expected): ...

def test_stakeholder_roles_round_trip():   # ne_roles + source_id survive to_dict/from_dict; both keys always present
def test_stakeholder_counter_round_trip():  # 4 -> "stakeholder_counter": 4; 0 -> key absent; "4" loads as 4; "x" loads as 0 with a warning
def test_add_stakeholder_uses_the_counter():
    items = add_stakeholder([], {"name": "A"}, today="2026-10-21")
    items = add_stakeholder(items, {"name": "B"}, today="2026-10-21", counter=1)
    items = remove_stakeholder(items, "SH002")
    assert add_stakeholder(items, {"name": "C"}, today="2026-10-21", counter=2)[-1].id == "SH003"
    assert add_stakeholder([Stakeholder(id="SH007", name="X")], {"name": "Y"}, today="d")[-1].id == "SH008"
def test_add_stakeholder_normalises_roles():  # {"name": "A", "ne_roles": ("Regulators", "Inputters")} -> "Inputters;Regulators"
```
The existing `tests/test_stakeholders.py:127-153` tests stay as they are (`SH001`, `SH002` still hold).

- [ ] **Steps 2–5:** fail → implement → pass + CI unit → commit `feat(stakeholders): D5.4 roles, source id and R's stakeholder id counter (P1b)`.

---

### Task 4: Mapper `indicator` hoist and Excel indicator columns

**Files:**
- Modify: `sespy/r_template_mapper.py` (the generic extras loop, `:110-117`), `sespy/excel_import.py` (`ELEMENT_DESC_COLS`, element construction `:184-191`)
- Modify tests: `tests/test_r_template_mapper.py::test_every_r_element_field_is_kept` (`:105-120`)
- Test: `tests/test_r_template_mapper.py`, `tests/test_excel_import.py`
- Regenerate: `sespy/templates/marinesabres/Caribbean_SES_Template.json`

**Interfaces:** Consumes `INDICATOR_FIELDS` (Task 2). Produces `excel_import.ELEMENT_INDICATOR_COLS: dict[str, str]` = field → R header (`"indicator": "Indicator", "indicator_unit": "Indicator_Unit", "data_source": "Data_Source", "registry_id": "Registry_Id", "registry_version": "Registry_Version", "policy_target": "Policy_Target"`), matched **case-insensitively** by a new `_pick_casefold(row, name, default="")` (the first column whose `str(col).casefold() == name.casefold()` and whose value is not NA). `ELEMENT_DESC_COLS = ("description", "Description")`: an Indicator column no longer feeds the description.

- [ ] **Step 1: Failing tests**

```python
def test_caribbean_indicator_moves_to_the_field():
    project, report = convert_r_template(_fixture("Caribbean"), key="Caribbean")
    s1 = next(e for e in project.isa_data.elements if e.id == "S1")   # the mapper keeps R ids (:105)
    assert s1.indicator == "Volume of Sargassum biomass on beaches (tons/year)"
    assert "indicator" not in s1.r_extra and s1.r_extra["baseline"] == "Minimal pre-2011"
    assert "indicator" not in report.extra_fields
    assert sum(1 for e in project.isa_data.elements if e.indicator) == 10

def test_excel_indicator_columns_fill_the_fields_not_description(tmp_path):
    els = [{"id": "D001", "label": "Demand", "type": "Drivers", "Indicator": "Visitors",
            "indicator_unit": "per year", "DATA_SOURCE": "Stats office", "Policy_target": "eu_nrr"},
           *VALID_ELEMENTS[1:]]
    el = parse_excel(_write_workbook(tmp_path, elements=els, connections=VALID_CONNECTIONS)).project.isa_data.elements[0]
    assert el.description == ""
    assert (el.indicator, el.indicator_unit, el.data_source, el.policy_target) == (
        "Visitors", "per year", "Stats office", "eu_nrr")

def test_excel_description_still_read(tmp_path):   # a "Description" column -> description; indicator fields ""
```
Modify `test_every_r_element_field_is_kept`: inside the loop, `if f == "indicator": assert el.indicator == v; continue` before the `r_extra` assert (so `names` never holds `indicator` and `set(report.extra_fields) == names | {"type"}` still holds).

- [ ] **Step 2:** fail. **Step 3:** mapper: the R key `indicator` goes to `Element(indicator=str(v))` instead of `r_extra`; all other extras unchanged. Excel as Interfaces say.
- [ ] **Step 4: Regenerate Caribbean** — the Task 1 Step 4 block again: `sync exit: 0`, `check exit: 0`, and `git status --short sespy/templates` lists only `Caribbean_SES_Template.json`.
- [ ] **Step 5:** tests + CI unit → green. **Step 6: Commit** `feat(import): R indicator into Element.indicator; Excel indicator columns (P1b)`.

---

### Task 5: Re-pin R to v1.33.0, new fixtures, vendored translations

**Files:**
- Modify `sespy/r_template_catalogue.py`: `INPUTS`, new `TRANSLATION_SUBSETS`, new `build_vendored_translations()`, `sync()` (both modes read the translation inputs); the module docstring's "(v1.31.0)" → "(v1.33.0)". Also `sespy/r_template_mapper.py:9` docstring → v1.33.0.
- Modify `pyproject.toml`: `[tool.setuptools.package-data] sespy` gains `"translations/modules/*.json"` (setuptools globs do not cross `/`).
- Modify tests:
  - `tests/test_r_template_catalogue.py`:
    - `_fake_r` (`:60-78`) also commits `constants.R` (at the app root), `functions/response_measures_schema.R` and `functions/stakeholder_schema.R` as one-line stubs, and `translations/modules/<stem>.json` for the 6 stems from a new helper `_fake_translation(stem) -> bytes`: a 9-language file with one key under each prefix of `TRANSLATION_SUBSETS[stem]` (one key for a whole-file stem) plus one key outside every prefix;
    - `test_real_run_writes_everything_then_checks_clean` (`:396`): `len(pin["files"]) == 18`, and each of the 6 vendored files holds exactly the in-subset keys of its fake fixture;
    - `test_fixture_mode_writes_projects_and_catalogue_only` → `test_fixture_mode_writes_projects_catalogue_and_translations`: the changed set gains the 6 `sespy/translations/modules/<stem>.json`, and `wrote` lines 8 → 14;
    - `test_check_reports_missing_outputs` (`:312-314`): 8 → 14;
    - `test_shipped_catalogue_equals_a_fresh_build` (`:642`): `("v1.31.0", "4b53b7d")` → `("v1.33.0", "4017feb")`.
    - `test_build_is_deterministic_lf_and_newline_terminated` (`:184`) stays unchanged: `build_outputs()` is not touched.
  - `tests/parity/test_r_sync.py::test_pin_shape` (`:27`): `len(paths) == 18`; add `sum(p.startswith("tests/parity/r_translations/") for p in paths) == 6` and that the 3 new `tests/parity/r_source/` paths are present.
- Generated by the sync: `tests/parity/r_sync.json`, `tests/parity/r_source/{constants.R,response_measures_schema.R,stakeholder_schema.R}`, `tests/parity/r_translations/*.json` (6), `sespy/translations/modules/*.json` (6), the generated block of `docs/parity/R_SYNC.md`, `sespy/templates/marinesabres/catalogue.json` (its `r_tag`/`r_commit` move to v1.33.0 / `4017feb`; the 7 templates are byte-identical, the R files being unchanged)
- Write by hand: `docs/parity/R_SYNC.md` prose and triage (Step 5)

**Interfaces:**
- `INPUTS` gains `"constants.R": "tests/parity/r_source/constants.R"` (it sits at the app root), `"functions/response_measures_schema.R"` and `"functions/stakeholder_schema.R"` → `tests/parity/r_source/<name>`, and `f"translations/modules/{s}.json"` → `f"tests/parity/r_translations/{s}.json"` for the 6 stems.
- `TRANSLATION_SUBSETS: dict[str, tuple[str, ...]]` — file stem → key prefixes (empty tuple = whole file):
  `response_measures: ()`, `response_governance: ()`,
  `wp5_vocabulary: ("modules.wp5_vocabulary.instrument.", "modules.wp5_vocabulary.measure.", "modules.wp5_vocabulary.tenet.")`,
  `wp5_scenarios: ("modules.wp5_scenarios.pestle.",)`,
  `wp5_governance: ("modules.wp5_governance.role.", "modules.wp5_governance.ne_roles")`,
  `indicator_registry: ("modules.indicator_registry.policy_target", "modules.indicator_registry.field_")`.
  Measured while planning at v1.33.0: 142, 26, 47, 6, 8, 10 keys = **239**, all 9 languages complete, no clash with `core.json`.
- `build_vendored_translations(raw_by_stem: dict[str, bytes]) -> dict[str, bytes]` (pure): for each stem, parse the R file (`utf-8-sig`), select keys in R's order, return `{f"sespy/translations/modules/{stem}.json": (json.dumps({"languages": <R's list>, "translation": {...}}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")}`. A file without a `translation` object raises `ValueError` (`sync()` already turns that into exit 1 with nothing written).
- `sync()`: git mode reads the translation inputs with `git show` like the others; fixture mode reads them from `tests/parity/r_translations/` (extend the `if r_path.startswith("data/")` loop to `translations/`). `outputs.update(build_vendored_translations(...))` right after `build_outputs()`; translation inputs never enter `raw_by_file`. So `--from-fixtures` writes and checks 14 outputs (7 templates, catalogue, 6 vendored files), and `--check` reports vendored drift in either mode.

- [ ] **Step 1: Failing tests** (in `tests/test_r_template_catalogue.py`, plus the modifications above):

```python
def test_vendored_translations_match_fixture_subsets():
    # for each stem: vendored keys == keys of tests/parity/r_translations/<stem>.json selected by
    # TRANSLATION_SUBSETS, in the fixture's order; every text equal; 9 languages each
def test_vendored_translation_key_counts():
    assert {s: len(_vendored(s)) for s in C.TRANSLATION_SUBSETS} == {
        "response_measures": 142, "response_governance": 26, "wp5_vocabulary": 47,
        "wp5_scenarios": 6, "wp5_governance": 8, "indicator_registry": 10}
def test_build_vendored_translations_is_pure_and_lf():    # a fake input -> the exact expected bytes; no "\r"
def test_package_data_ships_vendored_translations():      # as tests/test_templates.py:207-214
    # tomllib.load(pyproject) -> "translations/modules/*.json" in tool.setuptools.package-data.sespy
```

- [ ] **Step 2:** fail. **Step 3:** implement.
- [ ] **Step 4: Run the real sync** (no `--accept-warnings`: the 7 templates are byte-identical v1.31.0 → v1.33.0, so the pinned accepted warnings still match; any `warning (unaccepted)` line is a stop)

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
Push-Location 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
try {
  micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --rev v1.33.0
  "sync exit: $LASTEXITCODE"                  # 0
  micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --check
  "r-root check exit: $LASTEXITCODE"          # 0, no other output
  micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check
  "fixtures check exit: $LASTEXITCODE"        # 0, no other output
  git status --short
} finally { Pop-Location }
```
Expected: `hash ...: (none) -> <hash>` for the 9 new inputs, no hash line for the 9 old ones, and `git status --short` shows exactly the generated paths in Files plus this task's hand edits.
- [ ] **Step 5: R_SYNC.md prose** (outside the generated block; no 64-hex string anywhere in the prose, `tests/parity/test_r_sync.py:52-54` compares every one with the pin):
  - Update the prose that names v1.31.0 as the current pin: adopted in 1.15.0 (P1b), previous pin v1.31.0; the 9 previously pinned files are identical v1.31.0 → v1.33.0; P1b adds 3 R sources and 6 translation files (vendored subsets in `sespy/translations/modules/`).
  - Add `## R changes v1.31.0 → v1.33.0 (triaged <date>)`: one row per path of `git -C <R> diff --name-status v1.31.0 v1.33.0` (71 paths, prefix omitted), columns `# | Status | Path | Change | Owner`, as the v1.29.0 → v1.31.0 table. Owners follow spec §9's summary table; read each path's diff (or R's CHANGELOG 1.32.0–1.33.0 entries) for the Change column; every row has an owner or "not relevant". Then the line "Load DA actor list: P4 (user decision 2026-10-21)." (The `33ddd96` check item is closed in Task 10, once its test exists.)
- [ ] **Step 6:** CI unit command → green. Lint gate. **Commit** `chore(r-sync): pin R v1.33.0; register fixtures and vendored translations (P1b)`.

---

### Task 6: Register helpers (`sespy/response_register.py`)

**Files:**
- Create: `sespy/response_register.py`, `tests/test_response_register.py`, `tests/parity/test_r_register_parity.py`

**Interfaces (Produces; all pure, no Shiny; `safe_counter` comes from `sespy.utils`):**
- Constants (values from spec §4.2.1–4.2.2, each citing its R line):
  - `RM_REGISTER_COLUMNS` (34-tuple, `constants.R:831-840`), `RM_DISPLAY_COLUMNS` (15-tuple, `:844-846`), `TENET_CODES` (R `EBM_TENETS$code`, 11, `:804-810`).
  - `RM_TYPE_CODES`, `RM_TARGET_CODES`, `RM_STATUS_CODES`: `dict[str, str]` code → label-key suffix, R's named vectors (`:821-827`; only `"multiple": "multiple_levels"` differs from its code).
  - `GOVERNANCE_LEVELS` (`:828`), `TENET_LEVELS` (`:829`), `PESTLE_CODES` (`:933`).
  - `EBM_POLICY_INSTRUMENTS: tuple[tuple[str, str], ...]` — all 24 rows (code, level), category rows included (`:780-790`); `EBM_MANAGEMENT_MEASURES: tuple[tuple[str, str, str], ...]` (code, category, dapsiwrm_target) (`:793-801`).
  - UI choice lists from `response_module.R` (not a fixture; cite the lines): `KIND_CODES = ("instrument", "measure")`, `EFFECTIVENESS_LEVELS = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")`, `FEASIBILITY_LEVELS = ("HIGH", "MEDIUM", "LOW")` (`:91-102`), `IMPACT_PROBLEM_TYPES = ("specific_pressure", "specific_activity", "specific_driver", "system_wide_issue")`, `IMPACT_STRENGTHS = ("strong", "moderate", "weak")`, `TIMEFRAMES = ("immediate", "short_term_1_3y", "medium_term_3_10y", "long_term_10y")` (`:207-224`), `MILESTONE_STATUSES = ("pending", "in_progress", "completed", "delayed")` (`:340`); `IMPACT_COLUMNS`, `MILESTONE_COLUMNS` (`data_structure.R:292-305`).
- `reverse_label_map() -> dict[str, dict[str, str]]` — vocab name (`type, target, status, problem_type, strength, timeframe, milestone_status`) → {label (stripped, every language of the vendored `sespy/translations/modules/response_measures.json`) → code}; first occurrence wins; `functools.cache`. Reads the vendored file, never the fixture.
- `normalize_measures(rows: Any) -> list[dict[str, Any]]` — R `normalize_response_measures` (`response_measures_schema.R:49-107`) step for step (spec §4.2.1). `Cost` → a finite float, else `None` (`"cheap"`, `"nan"`, `"inf"` → `None`, so the JSON stays valid).
- `normalize_impacts(rows: Any) -> list[dict[str, str]]`, `normalize_milestones(rows: Any) -> list[dict[str, str]]` — exactly the 5 columns; labels → codes for ProblemType/ImpactStrength/Timeframe/Status; unknown values pass through.
- `ebm_code_choices(kind: str) -> list[str]` — instruments: the 20 codes with level `"type"`; measures: all 12; else `[]` (`response_measures_schema.R:118-129`).
- `ebm_picker_label(kind: str, code: str, tr: Callable[[str], str]) -> str` — an instrument shows `"<code> <label>"`, a measure `"<label>"` (`:120-124`); label = `tr("modules.wp5_vocabulary.<kind>.<code with . → _>")`, the raw code when the key is missing (`wp5_vocabulary.R:53-67`).
- `suggest_target(ebm_measure_code: str) -> str` — A → activities, P → pressures, C → state, `A|P|C` → multiple, else "" (`response_measures_schema.R:110-115`).
- `priority_rows(measures: list[dict], w_eff: float = 0.4, w_feas: float = 0.3, w_cost: float = 0.3) -> list[dict[str, Any]]` — each measure plus `EffScore`, `FeasScore`, `CostScore`, `PriorityScore`, `Rank` (`response_module.R:705-722, 775-776`). A `None` Cost gives `CostScore = None` and `PriorityScore = None` (R's NA). Sort by `PriorityScore` descending, stable, `None` after every number (R `order()` puts NA last); `Rank` 1..n over the sorted list.
- `ef_points(measures: list[dict]) -> list[tuple[str, int, int]]` — (ID, feasibility 1–3, effectiveness 1–3) for the measures whose Effectiveness and Feasibility are both HIGH/MEDIUM/LOW, in input order (`response_module.R:801-814`).
- `display_value(column: str, value: Any, tr: Callable[[str], str]) -> str` — R `rm_translate_for_display` + `rm_display_label` (`response_measures_schema.R:132-195`): a blank or `None` value → `""` in every column; Effectiveness/Feasibility → `modules.response.measures.<lower>` for HIGH/MEDIUM/LOW/UNKNOWN; Type/Target/Status (measure or milestone status) → `modules.response.measures.<suffix>`; Kind → `modules.response.governance.kind.<code>`; GovernanceLevel → `.level.<code>`; `Tenet_*` → `.tenet_level.<code>`; EbmCode → the vocabulary label with **no code prefix**, measure codes checked before instrument codes, the raw code on a miss; PestleTag → `;`-split, each `modules.wp5_scenarios.pestle.<code>`, joined with `", "`; ProblemType/ImpactStrength/Timeframe → `modules.response.measures.<code>` (SESPy stores codes, §4.2.2); `Cost` → an integral float as an int (`5.0` → `"5"`), otherwise `str(v)`; `PriorityScore` → 3 decimals (R `formatRound(…, 3)`). An unknown value, or a key the translator returns unchanged or empty, → the raw value.

- [ ] **Step 1: Failing tests** (`tests/test_response_register.py`), expected values cited to R; English texts are taken from the vendored files:

```python
def test_columns():
    assert len(RM_REGISTER_COLUMNS) == 34 and RM_REGISTER_COLUMNS[0] == "ID"
    assert RM_REGISTER_COLUMNS[-1] == "TenetSource" and RM_REGISTER_COLUMNS[9] == "Cost"

def test_normalize_selects_and_orders_columns():      # unknown key dropped; missing -> "" / Cost None
def test_cost_coercion():                              # "7" -> 7.0; "cheap", None, "nan", "inf" -> None
def test_list_cell_joined():                           # Stakeholders ["a","b"] -> "a;b"
def test_pestle_cleaned():                             # "legal; political;bogus;legal" -> "political;legal"
def test_tenet_levels():                               # Tenet_ecol_effective "Intermediate " -> "intermediate";
                                                       # Tenet_tech_feasible "intermediate" -> "" ; "FULL" -> "full"
def test_reverse_map_all_languages():                  # for each code of type/target/status/problem_type/strength/
                                                       # timeframe/milestone_status and each of 9 languages,
                                                       # map[label] == code; "Activities:" -> "activities"
def test_label_to_code_on_normalise():                 # Status = the lt label of "implemented" (from the vendored file) -> "implemented"
def test_handtyped_values_pass_through():              # Type "something else" stays
def test_normalise_is_idempotent():
def test_ebm_code_choices_and_suggest_target():
    inst = ebm_code_choices("instrument")
    assert len(inst) == 20 and "3.5" not in inst and not {"1", "2", "3", "4"} & set(inst)
    assert len(ebm_code_choices("measure")) == 12 and ebm_code_choices("") == []
    assert [suggest_target(c) for c in ("output", "spatial.seasonal", "restoration.habitat",
                                        "nbs.replace", "1.1", "")] == [
        "pressures", "multiple", "state", "activities", "", ""]
def test_ebm_picker_label():                           # instrument "1.1" -> "1.1 " + label; measure "output" -> label only
def test_priority_rows_reproduce_r():                  # 3 measures, hand-computed scores to 1e-9, ties keep input
                                                       # order, a None Cost -> None scores, ranked last
def test_ef_points_skip_unrated():                     # UNKNOWN / "" / hand-typed levels left out; [] when none rated
def test_display_value():                              # English: Kind "instrument" -> "Policy instrument";
    # GovernanceLevel "regional_sea" -> "Regional sea"; Tenet "minimal" -> "Minimal compliance"; a blank tenet -> "";
    # Target "activities" -> "Activities:"; PestleTag "political;legal" -> "Political, Legal";
    # EbmCode "output" -> its label without "output"; Timeframe "short_term_1_3y" -> "Short-term (1-3y)";
    # Cost 5.0 -> "5", 7.5 -> "7.5"; PriorityScore 0.123456 -> "0.123"; Type "something else" -> "something else"
def test_response_register_imports_without_shiny():   # subprocess, cwd <W>: import sespy.response_register,
    # run Project.from_dict on a payload with a register, exit 1 if "shiny" in sys.modules (as tests/parity/test_r_sync.py:78-82)
```

`tests/parity/test_r_register_parity.py` reads `tests/parity/r_source/constants.R` (CRLF → LF) through a small R-literal parser: balanced parentheses, string literals with escapes, `name = "value"` pairs (→ dict), `rep("x", n)`, `paste0("p", c(...))`, `c(...)`, `list(...)` and `data.frame(col = c(...), ...)` (→ dict of columns); anything else raises. It asserts, order included:
- `RM_TYPE_CODES`, `RM_TARGET_CODES`, `RM_STATUS_CODES` (names → values);
- `GOVERNANCE_LEVELS`, `TENET_LEVELS`, `PESTLE_CODES`, `RM_REGISTER_COLUMNS`, `RM_DISPLAY_COLUMNS`;
- `EBM_TENETS$code` ↔ `TENET_CODES`; `EBM_POLICY_INSTRUMENTS` (code, level); `EBM_MANAGEMENT_MEASURES` (code, category, dapsiwrm_target);
- `STAKEHOLDER_TYPES` ↔ `stakeholders.STAKEHOLDER_ROLES`; `WP5_POLICY_TARGETS` ↔ `constants.POLICY_TARGET_CODES`; lowercased `ISA_INDICATOR_COLUMNS` ↔ `data_structure.INDICATOR_FIELDS`; `ELEMENT_ID_PREFIX$measures == "RM"` and `PIMS_ID_PREFIX$stakeholder == "SH"`;
- by string presence: `response_measures_schema.R` still contains `"intermediate"` and `setdiff(TENET_LEVELS`, and `stakeholder_schema.R` contains `STAKEHOLDER_TYPES[STAKEHOLDER_TYPES %in% t]`, so an R change surfaces at re-pin.

The UI choice lists have no fixture. A test checks instead that every code has its label key in all 9 languages of the vendored files: `modules.response.measures.<code>` (levels lowercased) and `modules.response.governance.kind.<code>`.

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(register): R response-register schema port (P1b)`.

---

### Task 7: `Project.response_measures`

**Files:**
- Modify: `sespy/data_structure.py`, `sespy/response_register.py` (register-level helpers), `tests/test_newer_build_e2e.py:35-39` (its "unknown" block and field are now known: rename them `future_block` and `future_field` so the script still exercises unknown data)
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
  `from_dict` imports `sespy.response_register` inside the function and runs the three normalisers; a non-dict `raw` → empty + one warning; `counter` → `_coerce_counter` (Task 3) and is then **kept as loaded** (R `response_module.R:494-501`); `safe_counter` applies only in `add_measure`.
- `Project.response_measures: ResponseRegister = field(default_factory=ResponseRegister, kw_only=True)` (before `newer_build`). `to_dict` adds `"response_measures"` only when `not is_empty()`; `from_dict` reads it when present.
- In `sespy/response_register.py` (register-level; all return new objects, never mutate):
  - `add_measure(reg: ResponseRegister, fields: dict[str, Any], *, today: str) -> tuple[ResponseRegister, str]` — `n = safe_counter(reg.counter, ids, "RM") + 1`, ID `f"RM{n:03d}"`, `counter = n`, `DateAdded = today`, row normalised (spec §4.2.3, `response_module.R:507-509`).
  - `update_measure(reg, measure_id: str, fields: dict[str, Any]) -> tuple[ResponseRegister, bool]` — R `update` (`response_module.R:515-525`): never changes `ID` or `DateAdded`; columns absent from `fields` are kept; the row is re-normalised; `False` and unchanged when the ID is absent.
  - `delete_measures(reg, ids: Iterable[str]) -> tuple[ResponseRegister, int]` — counter unchanged; the int counts impact + milestone rows whose `ResponseID` is in `ids` (they are kept).
  - `add_impact(reg, fields) -> ResponseRegister`, `delete_impact(reg, index: int) -> ResponseRegister`, `add_milestone(reg, fields) -> ResponseRegister`, `delete_milestone(reg, index: int) -> ResponseRegister`; an out-of-range index returns `reg` unchanged.
  - `references_to(reg, element_id: str) -> list[str]` — sorted unique IDs of the measures whose `TargetElement` (`;`-split, exact match) contains `element_id`, plus the `ResponseID` of impact rows whose `ProblemElementID` equals it (used by Task 9's delete warning).

- [ ] **Step 1: Failing tests**

```python
def test_round_trip_all_features():              # spec §1 done-when 1: one fully filled measure (34 columns) +
    # impact + milestone + Element indicator fields + a connection description + a stakeholder with roles and
    # source_id + stakeholder_counter 1, through project_to_bytes -> json.loads -> validate_project_payload(...).valid
    # -> res.project; every value equal, field by field
def test_v7_file_loads_with_new_defaults():      # a schema-7 payload: empty register, stakeholder_counter 0,
    # ne_roles == source_id == "", indicator fields "", newer_build == {}
def test_empty_register_is_omitted():            # "response_measures" not in to_dict()
def test_counter_alone_is_kept():                # counter 3, no rows -> serialised
@pytest.mark.parametrize("bad", [
    {"measures": {"ID": "RM001"}}, {"measures": ["oops"]}, {"measures": [{"ID": "RM001", "Cost": "cheap"}]},
    {"measures": [{"ID": "RM001", "PestleTag": ["legal", "social"]}]},
    {"measures": [{"ID": "RM001", "Status": "<lt label of implemented>"}]},
    {"counter": "7"}, {"counter": None}])
def test_from_dict_tolerates_malformed_register(bad): ...   # loads; values normalised/defaulted
def test_loaded_counter_is_kept_not_raised():    # counter 0 + RM012 -> loads 0, re-serialises 0; add_measure -> RM013
def test_counter_coercion():                     # 3.0 -> 3; True -> 0 with a warning
def test_replace_carries_register():             # project.replace(metadata=...) keeps response_measures
def test_add_update_delete_cycle():              # RM001, RM002; update keeps ID/DateAdded; delete RM001 -> refs count;
                                                 # add -> RM003
def test_references_to():                        # TargetElement "P001;P002" and an impact on P002 -> ["RM001", "RM002"]
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit → commit `feat(schema): response register block (P1b)`.

---

### Task 8: SESPy-only i18n keys

**Files:** Modify `sespy/translations/core.json`, `tests/test_i18n.py`.

**Interfaces.** Strings with a vendored R key use it (spec §7); `core.json` gets only these keys, in all 9 languages (keep `{n}`, `{id}`, `{measures}`, `{version}` placeholders identical across languages):
- **Text copied from R's `translations/common/labels.json` at v1.33.0** (all 9 languages, via `git -C <R> show v1.33.0:MarineSABRES_SES_Shiny/translations/common/labels.json`): `responses.name` ← `common.labels.response_name`, `responses.type` ← `common.labels.response_type`, `responses.status` ← `common.labels.implementation_status`, `responses.description` ← `common.labels.description`, `responses.target_date` ← `common.labels.target_date`, `responses.milestone_status` ← `common.labels.status`.
- **SESPy text** (translate the English):
  - `nav.responses` "Response Register" (navigation keys stay in `nav.*`);
  - `responses.edit_selected` "Edit selected", `responses.cancel` "Cancel", `responses.save` "Save measure";
  - `responses.select_first` "Select a row first.", `responses.select_one` "Select exactly one row to edit.", `responses.name_type_required` "Name and type are required.";
  - `responses.deleted_with_refs` "{n} impact or milestone rows still refer to the deleted measures.";
  - `responses.tenet_source` "Tenet ratings source", `responses.target_element_hint` "Pick elements from this project; IDs not in the project are kept.";
  - `responses.element_still_referenced` "{id} is still referenced by the response register ({measures}). The reference is kept; an element added later may reuse this ID.";
  - `entry.edit_selected` "Edit selected", `entry.save_changes` "Save changes", `entry.cancel_edit` "Cancel", `entry.description` "Description", `entry.registry` "WP5 registry: {id} (revision {version})", `entry.connection_description` "Connection description".
- **R keys used directly** (already vendored; listed so module code and tests agree):
  - tabs: `modules.response.measures.response_register`, `impact_assessment`, `prioritization`, `implementation_plan`;
  - buttons: `modules.response.measures.delete_selected`, `download_response_data_excel`;
  - toasts: `modules.response.measures.deleted_response_measures`, `impact_linkage_added`, `milestone_added`;
  - plot: `add_effectiveness_and_feasibility_ratings`, `response_measure_prioritization_matrix`, `feasibility`, `effectiveness`, `low`, `medium`, `high`, `high_priorityneffective_feasible`, `effective_butndifficult`, `easy_butnlimited_impact`, `low_priority` (all `modules.response.measures.*`);
  - the governance section: `modules.response.governance.section_title` and the field labels `kind`, `ebm_code`, `level`, `competent_authority`, `legal_basis`, `paired_with`, `implementing_stakeholders`, `pestle`, `tenets_title`, the hints `ebm_code_hint`, `pestle_hint`, `no_stakeholders_hint`, and `tenet_level.not_assessed` for each tenet select's empty choice;
  - the other register, impact and milestone labels: the `modules.response.measures.*` key R uses at `response_module.R:28-190, 196-232, 318-345`;
  - ISA panel: `modules.indicator_registry.field_indicator`, `field_unit`, `field_data_source`, `field_policy_target`, help `policy_target_help`, choice labels `modules.indicator_registry.policy_target.<code>`;
  - roles: `modules.wp5_governance.ne_roles` (label), `ne_roles_hint` (help), `role.<lower code>` (choices).
- Table headers are R's column names, untranslated (spec §7).

- [ ] **Step 1:** failing `test_p1b_keys_present(translations)`: every `core.json` key above and every R key above present with all 9 languages non-empty. `test_p1b_placeholders_match_across_languages`: as `test_bbn_evidence_placeholders_match_across_languages`, for the keys with placeholders. **Steps 2–5:** fail → add keys → pass + CI unit → commit `feat(i18n): P1b UI strings (P1b)`.

---

### Task 9: ISA entry edit panels

**Files:**
- Modify: `sespy/modules/isa_data_entry.py`
- Create: `tests/test_isa_entry_edit.py` (fixture as `tests/test_isa_entry_link_rules.py:32-52`: `test_server`, the sample project, recorded `notification_show`)

**Interfaces:** Consumes `INDICATOR_FIELDS`, `POLICY_TARGET_CODES`, `references_to` (Task 7). New ids (module namespace `entry`):
- Elements: button `edit_element` (under `elements_table`) sets `editing_element: reactive.Value[str | None]` from the selected row with the module's own idiom (`isa.elements[elements_table.cell_selection()["rows"][0]].id`, as `_remove_element`, `:251-268`; py-shiny applies a row selection to the source data before sorting). `output_ui("element_editor")` renders under `@reactive.event(editing_element)` only (never re-rendered by `project_data` writes) and shows, while editing: `el_label`, `el_description` (text area), and for non-Responses `el_indicator`, `el_indicator_unit`, `el_data_source`, `el_policy_target` (`input_selectize`, choices `""` + `POLICY_TARGET_CODES` labelled `modules.indicator_registry.policy_target.<code>`, **plus the stored value when it is not one of them, shown raw**, `options={"create": True}`), labels from `modules.indicator_registry.field_*`, a read-only `entry.registry` line when `registry_id` is set, buttons `save_element`, `cancel_element`.
- Connections: button `edit_connection`, `output_ui("connection_editor")` (same gating) with `conn_description` (text area), `save_connection`, `cancel_connection`; `editing_connection: reactive.Value[tuple[str, str] | None]` keyed by (source, target).
- Save goes through `_replace(...)` with `dataclasses.replace(element, ...)`, so `r_extra`, the registry fields and every untouched field survive; for a Responses element only label and description are written. An empty label → warning toast, no write; then `editing_*` resets to `None`.
- `_remove_element`, after the removal: when `references_to(project.response_measures, target_id)` is non-empty, a warning toast `tr("responses.element_still_referenced", id=target_id, measures=", ".join(refs))`. The references are kept (spec §6.1).

- [ ] **Step 1: Failing `test_server` tests** (Global Constraints: selection needs both inputs; assert on the editor HTML):

```python
def test_edit_element_saves_indicator_fields():   # select MPF1's row, edit_element 0/1, set el_*, save_element 0/1
                                                  # -> indicator/unit/data_source/policy_target set; r_extra kept
def test_indicator_inputs_hidden_for_responses():  # editor HTML for R001 has entry-el_label, no entry-el_indicator
def test_free_text_policy_target_kept():          # MPF1 stored with policy_target "My national 25% target": the editor
                                                  # HTML has '<option value="My national 25% target" selected'; saving
                                                  # with that input leaves the value unchanged
def test_edit_connection_description():
def test_editor_not_clobbered_by_project_writes(): # while editing MPF1 (HTML shows indicator "A"), project_data.set(a
    # project where MPF1.indicator == "B") -> HTML still shows "A"; positive control: cancel, edit again -> shows "B"
def test_delete_referenced_element_warns():       # register measure with TargetElement "P001": remove P001's row ->
                                                  # one toast containing "P001" and "RM001"; the measure keeps "P001"
```

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(entry): edit element indicators and connection descriptions (P1b)`.

---

### Task 10: Stakeholder roles UI, counter wiring and export

**Files:** Modify `sespy/modules/pims_stakeholders.py` (`_register_panel`, `_form_fields`, `_clear_form`, `_repopulate`, `_save`, `stakeholder_table`), `docs/parity/R_SYNC.md` (the check item, `:145-151`, gets its outcome below it: "**Outcome (P1b, v1.15.0):** the stakeholders page adds one row per click (`tests/test_stakeholders_module.py::test_add_adds_exactly_one_row`) and allocates ids from R's persisted counter (`Project.stakeholder_counter`); response-measure ids use `safe_counter` (`add_measure`)." — no 64-hex string); Test: `tests/test_stakeholders_module.py` (new, `test_server`), `tests/test_stakeholder_reports.py`.

**Interfaces:**
- Input `sh_ne_roles`: `input_selectize`, multiple, choices `STAKEHOLDER_ROLES` labelled `modules.wp5_governance.role.<lower>`, label `modules.wp5_governance.ne_roles`, help text `modules.wp5_governance.ne_roles_hint`. Roles are normalised codes, so every stored value is a choice.
- `_form_fields` adds `"ne_roles": normalize_ne_roles(input.sh_ne_roles())`; `_clear_form` sends `ui.update_selectize("sh_ne_roles", selected=[])`; `_repopulate` sends `selected=match.ne_roles.split(";")` (or `[]`).
- `_save`, add branch: `add_stakeholder(items, f, today=..., counter=project.stakeholder_counter)` and `project.replace(stakeholders=new_list, stakeholder_counter=safe_counter(project.stakeholder_counter, [s.id for s in new_list], "SH"))`; the edit branch leaves the counter alone. `source_id` is never shown or edited, and an edit keeps it (`update_stakeholder` replaces only the form's fields).
- Table column `roles`: translated labels, `", "`-joined.
- Workbook: `build_stakeholder_workbook` already writes one column per `Stakeholder` field, so the Stakeholders sheet gains `ne_roles` (codes, `;`-joined) and `source_id`; no code change (spec §6.3).

- [ ] **Step 1: Failing tests**

```python
def test_add_with_two_roles_stores_canonical_order():  # sh_ne_roles ("Regulators", "Inputters") -> "Inputters;Regulators"
def test_add_adds_exactly_one_row():                   # R 33ddd96: one save click -> +1 row; a second -> SH001, SH002
def test_deleted_id_is_not_reused():                   # add A, B; select B and remove; add C -> C.id == "SH003",
                                                       # project.stakeholder_counter == 3
def test_edit_repopulates_roles_and_keeps_source_id(): # stored ne_roles "Regulators", source_id "d54:x": edit ->
    # recorded update_selectize("sh_ne_roles", selected=["Regulators"]); save a new name -> source_id still "d54:x"
def test_workbook_headers_are_the_stakeholder_fields():  # tests/test_stakeholder_reports.py: header row ==
    # [f.name for f in fields(Stakeholder)]; a stakeholder with ne_roles "Inputters;Regulators" carries it
```
**Steps 2–5:** fail → implement → pass + CI unit → commit `feat(stakeholders): D5.4 roles field and counter-based ids (P1b)`.

---

### Task 11: Response Register page — Register tab, wiring, manual section

**Files:**
- Create: `sespy/modules/response_register.py`, `tests/test_response_register_module.py`
- Modify: `app.py` (`NAV` after `entry`: `NavItem(id="responses", icon="list-check", label="Response Register", label_key="nav.responses")`; `PANELS` after Edit Data: `ui.nav_panel("Response Register", response_register_ui("responses"), value="responses")`; `NAV_TO_STEP["responses"] = "create"`; `response_register_server("responses", project_data=..., event_bus=..., translator=translator)`), `docs/MANUAL.md`, `README.md` (`:10`, `:50`, `:61`, `:121`), `tests/test_manual.py`

**Interfaces:** `response_register_ui()` / `response_register_server(input, output, session, *, project_data, event_bus, translator=None)` mirroring `pims_stakeholders`. Tabs `navset_tab(id="response_tabs")` with values `register`, `impacts`, `priority`, `milestones`, titled by the four R tab keys (Task 8).
- Register tab ids and choices, as R `response_module.R:28-190` (blank first choice `""` where R has one): `rm_name`, `rm_type` (`""` + the 7 codes), `rm_target` (`""` + the 5 codes), `rm_status` (the 5 codes, **no blank choice, default `proposed`**, `:68-70`), `rm_description`, `rm_mechanism`, `rm_target_element` (selectize multiple: project element IDs except Responses, plus any stored IDs not in the project; stored `;`-joined; R has a text input, spec §6.1), `rm_effectiveness` (`""` + HIGH/MEDIUM/LOW/UNKNOWN), `rm_feasibility` (`""` + HIGH/MEDIUM/LOW), `rm_cost` (numeric 1–10, default 5), `rm_stakeholders`, `rm_barriers` (text areas); inside `ui.tags.details` (summary `modules.response.governance.section_title`): `rm_kind` (`""` + instrument/measure), `rm_ebm_code` (choices `{"": " "}` + `{c: ebm_picker_label(kind, c, tr)}` over `ebm_code_choices(kind)`; a measure code calls `suggest_target` and, when it returns non-empty, `ui.update_select("rm_target", selected=...)`), `rm_gov_level` (`""` + the 7 levels), `rm_competent_authority`, `rm_legal_basis`, `rm_paired_with` (`""` + `"<ID> - <Name>"` with R's hyphen, `response_module.R:554`, excluding the measure being edited), `rm_impl_stakeholders` (selectize multiple, `"<Name> (<ID>)"`, stored `;`-joined IDs; hint `modules.response.governance.no_stakeholders_hint` when the project has none), `rm_pestle` (multiple), `rm_tenet_<code>` ×11 (labelled `modules.wp5_vocabulary.tenet.<code>`; choices `""` labelled `tenet_level.not_assessed`, `minimal`, `intermediate` only for `ecol_effective`, `full`); `output_ui("tenet_source")` read-only when set. Buttons `save_measure`, `cancel_measure`, `edit_measure`, `delete_measures`; table `measures_table` (`RM_DISPLAY_COLUMNS` as headers, values through `display_value`, `selection_mode="rows"`, built in register order).
- **Edit** takes the selected row (none → `responses.select_first`; more than one → `responses.select_one`), sets `editing_measure: reactive.Value[str | None]`, and repopulates the form with `ui.update_*` from `@reactive.event(editing_measure)` only (the `pims_stakeholders._repopulate` pattern). **Every select or selectize it repopulates gets the stored value(s) added to its choices, shown raw, when they are not known codes or IDs**: `rm_type`, `rm_target`, `rm_status`, `rm_effectiveness`, `rm_feasibility`, `rm_kind`, `rm_ebm_code`, `rm_gov_level`, `rm_paired_with` (a dangling ID), `rm_impl_stakeholders` (dangling IDs), `rm_target_element` (foreign IDs). The update dict never contains `ID`, `DateAdded` or `TenetSource`.
- **Save** (`save_measure`): name and type required (`responses.name_type_required`, no write); `add_measure` or `update_measure`; then the form is cleared as R does after an add (`response_module.R:589-599`: the text fields, stakeholders, PESTLE and tenets; not type, target, status, cost or the other selects) and `editing_measure` resets.
- **Delete** (`delete_measures`, multi-row): `delete_measures(reg, ids)`, then **one** toast: `tr("modules.response.measures.deleted_response_measures")`, followed by `" " + tr("responses.deleted_with_refs", n=n)` when `n > 0`.
- Every write: `project_data.set(project.replace(response_measures=...))` + `event_bus.emit_isa_change()`.
- **MANUAL:** a new `## 10. Response Register` after `## 9. Edit Data` (a one-paragraph stub, finished in Task 14). Renumber with a one-off scratch script `<scratchpad>\renumber_manual.py` (not committed; it only rewrites text, so the import rule does not matter): every number N ≥ 10 becomes N + 1 in (a) headings `^## (\d+)\. `, (b) the Contents lines (`docs/MANUAL.md:11-33`, items `N. Title` separated by ` · `), (c) prose `\bsections? (\d+)` and the second number of `sections (\d+) and (\d+)` (30 references today). Numbers < 10 and appendix letters stay. Then insert `10. Response Register · ` into the Contents line after `9. Edit Data · `. `docs/MANUAL.md:56` "all nineteen panels" → "all twenty panels". README: `:10` "**19 modules**" → "**20 modules**", `:50` and `:61` "See manual sections 19 and 43" → "20 and 44", `:121` "all 19 panels" → "all 20 panels".

- [ ] **Step 1: Failing tests** (`tests/test_response_register_module.py`; recorded `ui.update_*` and toasts, Global Constraints):

```python
def test_add_two_measures_ids():                   # RM001, RM002; DateAdded today; Type stored as the code
def test_add_requires_name_and_type():             # a valid add first (+1 row), then a blank name -> toast, no new row
def test_edit_repopulates_and_updates_in_place():  # recorded update calls carry the stored values; save -> ID,
                                                   # DateAdded and counter unchanged
def test_edit_keeps_dangling_and_pass_through_values():  # PairedWith "RM099", ImplementingStakeholders "SH404",
    # Type "something else", Effectiveness "Very high": the recorded updates for rm_paired_with, rm_impl_stakeholders,
    # rm_type and rm_effectiveness each include the raw value in choices and selected; saving with those inputs leaves
    # the row unchanged
def test_edit_with_two_rows_selected_asks_for_one():
def test_delete_reports_references():              # 1 impact + 1 milestone on RM002: delete RM002 -> the toast equals
    # tr(deleted_response_measures) + " " + tr("responses.deleted_with_refs", n=2)
def test_measure_code_suggests_target():           # rm_kind "measure", rm_ebm_code "output" -> recorded
                                                   # update_select("rm_target", selected="pressures")
def test_language_switch_relabels_not_rewrites():  # TR.set_language("de"): measures_table shows the German Type label;
                                                   # the stored row is unchanged
def test_section_references_resolve():             # tests/test_manual.py: every "section N" / "sections N and M" names an
    # existing "## N." heading; the Contents numbers in order equal the heading numbers in order; spot checks:
    # "Rate Connections (section 11)", "**Recent Projects** (section 23)", "**Help** (section 25)"
```
Also run, unchanged: `tests/test_help_offcanvas.py` and `tests/test_manual.py` (every nav panel still has a manual section).

- [ ] **Steps 2–5:** fail → implement → pass + CI unit + lint → commit `feat(responses): Response Register page, register tab (P1b)`.

---

### Task 12: Impacts, prioritisation, milestones, Excel export

**Files:** Modify `sespy/modules/response_register.py`; Create `sespy/response_reports.py`; Test `tests/test_response_register_module.py`, `tests/test_response_register.py`.

**Interfaces:**
- Impacts tab ids: `impact_response` (select `""` + `"<ID>: <Name>"`, `response_module.R:663-666`), `impact_problem` (`IMPACT_PROBLEM_TYPES`), `impact_element` (select, as `rm_target_element` but single), `impact_strength`, `impact_timeframe`, `add_impact` (requires response and problem; toast `impact_linkage_added`), `impacts_table` (values through `display_value`), `delete_impact`.
- Priority tab: sliders `weight_effectiveness` 0.4, `weight_feasibility` 0.3, `weight_cost` 0.3 (0–1, step 0.1); `priority_table` from `priority_rows` with R's visible columns minus BanditSuggestion (`Rank, ID, Name, Type, Target, Kind, EbmCode, GovernanceLevel, Effectiveness, Feasibility, Cost, PriorityScore, Status`, `response_module.R:782-784`), values through `display_value`; `ef_plot` (`render.plot`, matplotlib) as R `response_module.R:796-837`: the points of `ef_points`, x = feasibility, y = effectiveness, limits 0.5–3.5, ticks 1–3 labelled `low`/`medium`/`high`, dashed grey lines at 2, title `response_measure_prioritization_matrix`, the four quadrant labels at (2.5, 2.5), (1.25, 2.5), (2.5, 1.25), (1.25, 1.25), points labelled by ID; with no point, empty axes titled `add_effectiveness_and_feasibility_ratings`.
- Milestones tab: `impl_response`, `impl_milestone`, `impl_date` (default today + 365 days), `impl_status` (`MILESTONE_STATUSES`), `impl_notes`, `add_milestone` (requires response and milestone; clears milestone and notes; toast `milestone_added`), `milestones_table` (values through `display_value`), `delete_milestone`, `download_response_xlsx`.
- `response_reports.build_response_workbook(reg: ResponseRegister, tr: Callable[[str], str]) -> bytes` (R `build_response_excel`, `response_module.R:1178-1192`): sheets `Response_Measures` (header `RM_REGISTER_COLUMNS`; the columns R translates go through `display_value`, `Cost` stays a number, blank when `None`), `Impact_Matrix` (header `IMPACT_COLUMNS`; ProblemType, ImpactStrength, Timeframe through `display_value`), `Implementation` (header `MILESTONE_COLUMNS`; Status through `display_value`). Lazy `openpyxl` import, as `stakeholder_reports.py`.

- [ ] Tests: impact add/delete (with the required-field toast); milestone add with the default date; `priority_table` rows match `priority_rows`; the workbook's sheet names and header rows, a coded Type rendered as `tr("modules.response.measures.regulatory")`, a Timeframe `short_term_1_3y` as "Short-term (1-3y)", `Cost` as a number. **Steps:** fail → implement → pass + CI unit + lint → commit `feat(responses): impacts, prioritisation, milestones, Excel (P1b)`.

---

### Task 13: e2e scripts

**Files:** Create `tests/test_response_register_e2e.py`, `tests/test_isa_edit_e2e.py`; Modify `tests/test_stakeholders_e2e.py` (a roles step).

Copy the skeleton and idioms of `tests/test_stakeholders_e2e.py`: a standalone `async def main()` + `asyncio.run(main())` against `http://127.0.0.1:8000`; `wait_for_selector("#sespy_nav_<id>", timeout=60000)`, click, then the active-pane `wait_for_function` on `.tab-content > .tab-pane[data-value='<id>']`; `_poll_table_contains` / `_poll_table_lacks`; downloads saved and checked by magic bytes (`.xlsx` → `b"PK\x03\x04"`). Rules:
- namespaced ids only (`#responses-…`, `#entry-…`, `#stakeholders-…`), never a bare `text=` (every panel is in one DOM);
- a toast is matched by **its own text** inside `#shiny-notification-panel .shiny-notification`, never by presence (a recovery banner can be up);
- a button rendered inside an `output_ui` is clicked only after `wait_for_selector("#<id>.shiny-bound-input", state="attached")`;
- a selectize input: wait for its hidden `<select>` with `state="attached"`, then set it with `Shiny.setInputValue("<id>", [...])` (the proven pattern; plain selects use `page.select_option`).
Each new session starts on `data/sample_ses.json` (17 elements: MPF1 "Posidonia meadows" is Marine Processes & Functioning, R001 "MPA enforcement" is Responses, a connection D001 → A001; no register).

- `test_response_register_e2e.py`:
  1. nav `responses`; `#responses-measures_table` visible.
  2. add "No-take zone" (`rm_type` `regulatory`) and "Mooring buoys" (`rm_type` `technical`) → the table shows `RM001` and `RM002`.
  3. select RM001, `edit_measure`, `rm_status` → `implemented`, save → the RM001 row shows "Implemented" and is still `RM001`.
  4. tab `impacts`: an impact for RM002 (`impact_problem` `specific_pressure`) → one row in `#responses-impacts_table`; tab `milestones`: milestone "Consultation" for RM002 → one row.
  5. tab `register`: select RM002, `delete_measures` → a toast whose own text contains "Deleted response measure(s)" and "2 impact or milestone rows still refer"; the table lacks `RM002`.
  6. add "Seasonal closure" → `RM003` (IDs are not reused).
  7. tab `milestones`: `download_response_xlsx` → name ends `.xlsx`, magic bytes `PK\x03\x04`.
  Last line: `response register e2e: all assertions passed`.
- `test_isa_edit_e2e.py`:
  1. nav `entry`; select the `MPF1` row of `#entry-elements_table` (the first `td` of the `tbody tr` whose first cell is `MPF1`), `edit_element`; set `el_indicator` "Shoot density" and `el_indicator_unit` "shoots/m2"; `save_element`; select MPF1 again and edit → both inputs hold the saved values.
  2. select `R001`, `edit_element` → `#entry-el_label` attached and `#entry-el_indicator` absent (`query_selector` → `None`).
  3. select the D001 → A001 row of `#entry-connections_table`, `edit_connection`, `conn_description` "Visitors bring boats", save; edit again → the text area holds it.
  Last line: `isa edit e2e: all assertions passed`.
- `test_stakeholders_e2e.py`: in step 2, before saving "Port Authority", set `stakeholders-sh_ne_roles` to `["Regulators", "Inputters"]`; after the row appears, the table text contains both English role labels (`modules.wp5_governance.role.inputters` / `.regulators` in the vendored file). Every later step stays unchanged.

- [ ] **Step 1:** from `<W>`: `micromamba run -n shiny python -m py_compile tests/test_response_register_e2e.py tests/test_isa_edit_e2e.py tests/test_stakeholders_e2e.py` → exit 0.
- [ ] **Step 2: Run the three solo against a fresh server.** `run_e2e.py` has no single-script option, so write `<scratchpad>\e2e_solo.py` (it loads the runner by path; a `from tests.run_e2e` import would hit the stray site-packages `tests`):

```python
"""Run named e2e scripts solo, exactly as tests/run_e2e.py runs them.
Usage (from the repo root): python -I e2e_solo.py tests/test_a_e2e.py [...]"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_e2e", Path("tests/run_e2e.py").resolve())
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
url = "http://127.0.0.1:8000/"
if E.port_busy(url):
    sys.exit("port 8000 is busy: kill it first")
proc = E.start_server(8000, {})
code = 0
try:
    if not E.wait_ready(url):
        sys.exit("server never answered")
    E.warm_session(url)
    for s in sys.argv[1:]:
        r = E.run_script(E.ROOT / s)
        print(f"{'PASS' if r.returncode == 0 else 'FAIL'} {s}\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        code |= r.returncode != 0
finally:
    E.stop_server(proc)
sys.exit(code)
```
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
Push-Location 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
try { micromamba run -n shiny python -I '<scratchpad>\e2e_solo.py' tests/test_response_register_e2e.py tests/test_isa_edit_e2e.py tests/test_stakeholders_e2e.py; "solo exit: $LASTEXITCODE" } finally { Pop-Location }
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing again
```
`-I` is safe: the runner is loaded by absolute path, its `ROOT` is `<W>` (`tests/run_e2e.py:32`), and the server and scripts run as children with `PYTHONPATH=<W>` (`:59`). Expected: three `PASS` lines whose last lines are the two above and `stakeholders e2e assertions pass`, then `solo exit: 0`. If port 8000 is still held afterwards, stop it **by port**.
- [ ] **Step 3:** CI unit command → green. **Step 4: Commit** `test(e2e): response register, ISA edit, stakeholder roles (P1b)`.

---

### Task 14: Docs and roadmap

**Files:**
- `docs/MANUAL.md`: §10 Response Register (what each tab does, IDs never reused, deletes do not cascade and what the toast says, values outside a list kept on Edit, Excel export); §9 Edit Data (the edit panels, the six indicator fields, Responses excluded, the referenced-element warning); §6 Stakeholders (roles; IDs never reused); `:130` "converted from R release v1.31.0" → v1.33.0.
- `CHANGELOG.md`: `## [1.15.0] — <date>`, intro "Roadmap P1b …; ports R …, against R v1.33.0 (`4017feb`)", then Added / Changed: schema 8 with the "an older SESPy refuses to overwrite a v1.15 file" note; the Excel "Indicator column now fills the Indicator field, not the description" change; stakeholder IDs now follow R's counter (a deleted ID is not reused); saved Caribbean projects get their indicators in the new field; deferred: the indicator registry picker and "Load DA actor list" → P4, Word exports → P6c/P14, the workshop → proposed P15, `r_min_app_version` → P1c.
- `README.md`: the feature line (unit and e2e counts are Task 15's).
- `tests/make_docs_screenshots.py`: docstring "the 19 nav panels" → "the 20 nav panels"; `NAV_ORDER` gains `("responses", ("sel", "#responses-measures_table"))` after `entry` (the default sample has no register, so the shot shows the empty form; the script keeps its "never mutate the project" rule). Shoot with port 8000 free (`shiny run --port 8000 app.py` from `<W>` with `$env:PYTHONPATH = '<W>'`), commit only `responses.png`, `entry.png` and `stakeholders.png`.
- **Roadmap** (spec §2, §8; branch `docs/r-parity-roadmap`, edited in a scratchpad worktree so no checkout is switched: `git -C <S> fetch origin`; check `git -C <S> rev-parse docs/r-parity-roadmap origin/docs/r-parity-roadmap` prints one SHA twice; `git -c core.longpaths=true -C <S> worktree add <scratchpad>\p1b-roadmap docs/r-parity-roadmap`; commit there; pushed in Task 16 Step 6). Edit `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md` so that:
  - the header names baseline R v1.33.0 (`4017feb`, re-pinned by P1b) and SESPy v1.15.0 (P0, P1a, P2, P1b shipped);
  - node M says shipped in MosaicSES 0.4.0 (live 0.4.1), with spec §2's line refs;
  - P1b: R sources gain 1.32.0 (`TenetSource`, tenet validation); decisions (a) and (b) as spec §5 records them, with the load-time hoist; "Load DA actor list" → P4; the `33ddd96` check closed (stakeholder counter); the "two version stamps" bullet moves to P1c;
  - P4: gains "Load DA actor list" with `wp5_governance_profiles.json`; its page bullet becomes "WP5 mechanism and D5.4 governance-context tabs on the Response Register page shipped by P1b (v1.15.0)"; "five indicator fields" → "six indicator fields incl. `Policy_Target`";
  - P1c: maps R `NERoles`/`SourceId`/`pims.stakeholder_counter` to `ne_roles`/`source_id`/`stakeholder_counter`; imports registers through `normalize_measures`; owns `r_min_app_version`;
  - §3 sync tracking: baseline v1.33.0; §3 testing: "P1b = v1.15.0";
  - the dependency graph and §5 gain P15 (WS-10 workshop elicitation, after P4).

- [ ] `micromamba run -n shiny python -m pytest tests/test_manual.py tests/test_help_offcanvas.py -q` green; commit `docs: P1b manual, changelog, screenshots (P1b)` on the feature branch and `docs(roadmap): P1b amendments` on the roadmap branch (explicit paths, trailer, each).

---

### Task 15: Gates — CI unit, sync checks + lint, code review, full e2e, README counts, MosaicSES

Every block runs from `<W>` (`Push-Location` / `-WorkingDirectory`).

- [ ] **Step 1: CI unit command** → green; record the `passed` count.
- [ ] **Step 2: Sync checks at the pin, then lint**

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
Push-Location 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
try {
  micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --check
  "r-root check exit: $LASTEXITCODE"          # 0, and no other output
  micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check
  "fixtures check exit: $LASTEXITCODE"        # 0, and no other output
  micromamba run -n shiny python -m ruff check sespy tests app.py --statistics
} finally { Pop-Location }
```
Lint: the total is at most 54, and `ruff check` on each file this plan created prints `All checks passed!`.
- [ ] **Step 3: Implementation review loop — before the slow gates**, so every review fix still goes through e2e and MosaicSES. superpowers:requesting-code-review with BASE_SHA = `git -C <W> merge-base docs/p1b-design HEAD` and HEAD_SHA = `git -C <W> rev-parse HEAD` (the implementation commits only; diffing against the `docs/p1b-design` tip would show later plan commits as a fake revert). Repeat until a round finds no Critical or Important issue; each fix is its own commit followed by the CI unit command, both checks of Step 2 and the lint gate. A fix needed after Steps 4–6 ran (including one found at Task 16 Step 1) is committed on `feat/p1b-response-register` like any other; unless it touches docs only, Steps 4–6 run again.
- [ ] **Step 4: Full e2e gate, detached** (the Bash tool kills anything past 10 min, even backgrounded). Port 8000 free, nothing heavy running:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
$log = '<scratchpad>\e2e-p1b.log'
$env:PYTHONPATH = $W
Start-Process micromamba.exe -ArgumentList "run -n shiny python -u tests/run_e2e.py" -WorkingDirectory $W -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden
```
Poll in bounded PowerShell calls, `Start-Sleep -Seconds 240; Get-Content '<scratchpad>\e2e-p1b.log' -Tail 15` (literal path; `$log` is gone in a new call), until the summary prints; never park on a background monitor. Expected: the Phase 1 line reads `35 scripts + wizard no-key`, the summary `37/37 e2e scripts passed, 0 failed`, and no `PASS (retry)`. A red script or a retry: rerun that script solo (Task 13 Step 2) before believing it; green solo = a load flake (record it), red solo = a regression (a new i18n label colliding with another module's selector: scope the selector). Afterwards: port 8000 free, `git -C <W> status --short` empty, and sweep orphans:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CreationDate -gt (Get-Date).AddHours(-2) } | Select-Object ProcessId, CreationDate, CommandLine
```
- [ ] **Step 5: README counts from the gates' own output.** The runner never prints the script count: its `=== Phase 1 (no key): K scripts + wizard no-key ===` line leaves out the wizard, and its final `P/T e2e scripts passed` counts runs (the wizard runs twice). So N (scripts) = K + 1 and M (runs) = T; expected N = 36 and M = 37 (README today: 34 scripts, 35 runs, 1227 unit tests). Update `README.md`: the `# Full Playwright e2e — one command boots the server, runs all N browser` comment (≈`:468`); the `<unit> unit tests + N standalone Playwright scripts (M runs` paragraph (≈`:480`); the "Tests" section's `**<unit> unit tests**` header (≈`:551`), both unit counts set to the latest CI `passed`; the `**N end-to-end test scripts**` list (≈`:567`): add `response-register` and `isa-edit`, and set the bold count to N. If anything changed, commit `docs(readme): test counts after P1b` (explicit `git add README.md`, trailer).
- [ ] **Step 6: MosaicSES gate — full suite including e2e**, never `-k "not e2e"`. MosaicSES imports `sespy`, and the env's editable install points at the main checkout, so `PYTHONPATH` must name `<W>` (MosaicSES's own `tests` still wins: `-m pytest` puts its cwd first on `sys.path`). First grep MosaicSES `tests/` for `[id$=`, `[id^=` and `[id*=` and confirm no pattern matches a new `entry-*` id (spec §10; none did on 2026-10-21). Then:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$env:PYTHONPATH = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
$mlog = '<scratchpad>\mosaicses-p1b.log'
Start-Process micromamba.exe -ArgumentList "run -n shiny python -m pytest tests -q -p no:cacheprovider" -WorkingDirectory 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES' -RedirectStandardOutput $mlog -RedirectStandardError "$mlog.err" -WindowStyle Hidden
```
Poll with bounded `Start-Sleep -Seconds 240; Get-Content '<scratchpad>\mosaicses-p1b.log' -Tail 5` calls. Expected: all green (≈ 590 passed at v1.14.2). Before believing a green, prove the import: with the same `PYTHONPATH` and the MosaicSES dir as cwd, `micromamba run -n shiny python -c "import sespy; print(sespy.__file__, sespy.__version__)"` → `...sespy-p1b\sespy\__init__.py 1.15.0`. Then a compartment round trip as a scratch script `<scratchpad>\mosaic_rt.py`, run the same way: a SESPy `Project` with one measure (`add_measure`), one impact, one milestone, an `Element(indicator=...)` and a stakeholder from `add_stakeholder(..., {"name": "Port authority", "ne_roles": "Regulators"}, ...)`, put in `multises.data_structure.Compartment(id="c1", label="C1", archetype="lagoon", project=...)` inside `MultiSES(metadata=MultiSESMetadata(), compartments=[...])`; `MultiSES.to_dict()` (`multises/data_structure.py:601`, which calls `Project.to_dict`) → `json.dumps` → `json.loads` → `MultiSES.from_dict(...)` (`:642`, a `LoadResult`; take `.multises`); assert the five values survive on `compartments[0].project`. A MosaicSES test for this is a MosaicSES commit: only with the user's go-ahead.

---

### Task 16: Release v1.15.0 — **each step needs the user's go-ahead**

The release runs from the implementation worktree itself (no separate release worktree): `feat/p1b-response-register` comes from `origin/main` plus the P1b commits, so when `origin/main` has not moved it is pushed as a fast-forward, exactly like v1.14.1/v1.14.2. Steps may span sessions, so every block names its paths absolutely and uses `git -C`; `<scratchpad>` is substituted literally. Long foreground blocks need `timeout: 600000`.

- [ ] **Step 1 (user go-ahead): Bring in `origin/main`, guard the schema number, date the CHANGELOG**

```powershell
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -C $W status --short                                  # must print nothing
git -c core.longpaths=true -C $W fetch origin
if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
git -C $W show origin/main:sespy/data_structure.py | Select-String '^PROJECT_SCHEMA_VERSION = '
                                                          # must print "= 7": "= 8" or more means another sub-project
                                                          # (K1) took schema 8 first: stop and renumber per roadmap §3
git -c core.longpaths=true -C $W merge-base --is-ancestor origin/main HEAD
"ancestor exit: $LASTEXITCODE"                            # 0 = fast-forward possible
```
If `ancestor exit: 1` (`origin/main` gets weekly `docs(literature)` commits), merge it, then re-run Task 15 Steps 1, 4 and 6 (CI unit, full e2e, MosaicSES) before going on:
```powershell
git -c core.longpaths=true -C 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b' merge --no-ff origin/main -m @'
Merge origin/main into feat/p1b-response-register

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
"merge exit: $LASTEXITCODE"                               # non-zero: resolve keeping both sides, git add <file>, git commit --no-edit
```
If the `## [1.15.0]` date written in Task 14 is not the release day, fix it with the Edit tool and commit `docs(changelog): 1.15.0 release date` (explicit `git add CHANGELOG.md`, trailer).

- [ ] **Step 2 (user go-ahead): Push and tag — only if `origin/main` has not moved**

```powershell
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -c core.longpaths=true -C $W fetch origin
if ($LASTEXITCODE -ne 0) { throw 'fetch failed' }
git -c core.longpaths=true -C $W merge-base --is-ancestor origin/main HEAD
if ($LASTEXITCODE -ne 0) { throw 'origin/main moved since Step 1: repeat Step 1' }
git -c core.longpaths=true -C $W push origin feat/p1b-response-register:main
if ($LASTEXITCODE -ne 0) { throw 'push rejected: nothing was tagged' }
git -c core.longpaths=true -C $W tag -a v1.15.0 -m "v1.15.0 - P1b: response register, indicator fields, stakeholder roles (schema 8)"
if ($LASTEXITCODE -ne 0) { throw 'tag failed' }
git -c core.longpaths=true -C $W push origin v1.15.0
if ($LASTEXITCODE -ne 0) { throw 'tag push failed: main is pushed but v1.15.0 is only local; retry the tag push' }
git -c core.longpaths=true -C $W ls-remote --tags origin v1.15.0     # must print one line
```

- [ ] **Step 3 (user go-ahead): Deploy from the worktree.** First confirm node M is live (roadmap: it must precede the first schema bump after P1a; MosaicSES 0.4.0 shipped it, live 0.4.1 since 2026-10-18): `Push-Location 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES'; try { micromamba run -n shiny python deploy/verify_live.py; "verify exit: $LASTEXITCODE" } finally { Pop-Location }` → all checks pass, `verify exit: 0`. Then:

```powershell
$S = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy'
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -c core.longpaths=true -C $W describe --tags --exact-match HEAD
if ($LASTEXITCODE -ne 0) { throw 'HEAD is untagged: run Step 2 first' }
Copy-Item "$S\deploy\config.env" "$W/deploy/config.env"   # gitignored, so absent from the worktree
bash "$W/deploy/deploy.sh"
```
Expected: `v1.15.0`, then `==> Deploying SESPy v1.15.0 to ...` and `==> Done.`. `deploy.sh` copies the whole `sespy/` tree, so `sespy/translations/modules/` and the regenerated templates ship; the deployed `sespy/` is symlinked into the live MosaicSES, so MosaicSES changes immediately.

- [ ] **Step 4 (user go-ahead): Verify on laguna with the worker's Python** (`-s`: user site disabled). Write `<scratchpad>\verify_p1b.py`:

```python
"""Run on laguna from the SESPy app dir:
/opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_p1b.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import sespy  # noqa: E402
from sespy.data_structure import (  # noqa: E402
    PROJECT_SCHEMA_VERSION, Element, IsaData, Project, ResponseRegister)
from sespy.i18n import load_translations  # noqa: E402
from sespy.persistent_storage import project_to_bytes, validate_project_payload  # noqa: E402
from sespy.response_register import add_impact, add_measure, add_milestone  # noqa: E402
from sespy.stakeholders import add_stakeholder  # noqa: E402
from sespy.templates import list_catalogue, load_template  # noqa: E402

assert sespy.__version__ == "1.15.0", sespy.__version__
assert PROJECT_SCHEMA_VERSION == 8
reg, mid = add_measure(ResponseRegister(), {"Name": "No-take zone", "Type": "regulatory"}, today="2026-10-22")
assert mid == "RM001"
reg = add_impact(reg, {"ResponseID": mid, "ProblemType": "specific_pressure"})
reg = add_milestone(reg, {"ResponseID": mid, "Milestone": "Consultation", "Status": "pending"})
sh = add_stakeholder([], {"name": "Port authority", "ne_roles": "Regulators"}, today="2026-10-22", counter=4)
assert sh[0].id == "SH005", sh[0].id
el = Element(id="MPF1", label="Reef", type="Marine Processes & Functioning", indicator="Coral cover")
p = Project.from_isa(IsaData(elements=[el])).replace(
    response_measures=reg, stakeholders=sh, stakeholder_counter=5)
raw = json.loads(project_to_bytes(p))
assert raw["metadata"]["schema_version"] == 8 and raw["metadata"]["min_sespy_version"] == "1.15.0"
assert raw["stakeholder_counter"] == 5
res = validate_project_payload(raw)
assert res.valid, res.errors
back = Project.from_dict(raw)
assert back.response_measures.measures[0]["ID"] == "RM001"
assert len(back.response_measures.impacts) == 1 and len(back.response_measures.milestones) == 1
assert back.isa_data.elements[0].indicator == "Coral cover"
assert back.stakeholders[0].ne_roles == "Regulators" and back.stakeholder_counter == 5
carib = next(r for r in list_catalogue() if r.name.startswith("Caribbean"))
cp = load_template(carib.file)
assert sum(1 for e in cp.isa_data.elements if e.indicator) == 10
tr = load_translations(Path("sespy/translations"))
assert tr["modules.response.measures.activities"]["en"] == "Activities:"
print("P1b OK:", sespy.__file__)
```
Run it in **one** Bash tool call (config.env is bash syntax; forward-slash scratchpad path; `\$?` escaped so the remote shell expands it and `rm` cannot mask a failure):
```bash
cd "C:/Users/arturas.baziukas/AppData/Local/sespy-p1b" && source deploy/config.env && \
scp "<scratchpad>/verify_p1b.py" "$DEPLOY_SERVER:/tmp/verify_p1b.py" && \
ssh "$DEPLOY_SERVER" "cd '$DEPLOY_DIR' && /opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_p1b.py; s=\$?; rm -f /tmp/verify_p1b.py; exit \$s"
echo "verify exit: $?"
```
Expected: `P1b OK: <DEPLOY_DIR>/sespy/__init__.py` and `verify exit: 0` (pre-existing `off-rule link` warnings on stderr are not errors). Then, in a browser (the user), the live app shows the Response Register nav item, and adding a measure shows RM001.

- [ ] **Step 5 (user go-ahead; read-only): Recheck the live MosaicSES** — the `verify_live.py` call of Step 3 again → all checks pass.

- [ ] **Step 6 (user go-ahead): Push the roadmap branch** (Task 14's commit): `git -C 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy' push origin docs/r-parity-roadmap`; then `git -c core.longpaths=true -C <S> worktree remove <scratchpad>\p1b-roadmap`.

- [ ] **Step 7 (user go-ahead): Clean up** (safe forms only: they refuse rather than discard)

```powershell
$S = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy'
$W = 'C:/Users/arturas.baziukas/AppData/Local/sespy-p1b'
git -C $S fetch origin
$left = git -C $S log --oneline origin/main..feat/p1b-response-register
if ($left) { throw "feat/p1b-response-register has commits not on origin/main: $left" }
Remove-Item "$W/deploy/config.env" -ErrorAction SilentlyContinue   # untracked copy from Step 3, else worktree remove refuses
git -c core.longpaths=true -C $S worktree remove $W                # 'Permission denied' on .git/worktrees/... = harmless OneDrive lock
git -C $S worktree prune
git -C $S branch -d feat/p1b-response-register                      # -d: its upstream origin/main (Task 0) contains it
git -C $S fetch origin main:main                                    # fast-forward only
```
`docs/p1b-design` stays (its spec and plan commits are on `main` via the feature branch); delete it with `branch -d` only if `git branch --merged origin/main` lists it. Then update `.remember/remember.md` and the memory index (P1b shipped as v1.15.0, schema 8, R pin v1.33.0 `4017feb`; stakeholder IDs follow R's counter; deferred: indicator registry picker + Load DA actor list → P4, Word exports → P6c/P14, workshop → proposed P15, `r_min_app_version` → P1c).
