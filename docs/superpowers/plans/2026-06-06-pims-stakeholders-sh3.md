# PIMS Stakeholders SH3 — Engagement Activity Log — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-stakeholder **engagement-activity log** as a third sub-tab of the Stakeholders panel: an `Engagement` child entity (persisted, schema 3→4), pure helpers, an add-form + log table, i18n, and tests.

**Architecture:** `Engagement` references a `Stakeholder` by id (no denormalized name). Persistence rides the existing `Project.replace()` envelope infra (no new writer edits); only `to_dict`/`from_dict` + the schema bump change. Pure helpers (`add_engagement`, `remove_engagement`, `engagement_rows`) go in `sespy/stakeholders.py` (Shiny-free). The module gains a 3rd `nav_panel` in the existing `navset_tab` (`id="stakeholder_tabs"`), a dropdown-populate effect, an add handler, and a `@render.data_frame` log. **No `app.py`, SH1-model, or SH2-grid change.**

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, pandas, pytest, Playwright. Run via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-06-pims-stakeholders-sh3-design.md` (rev. 2, post-deep-review).

**Plan rev. 2 (from multi-agent plan deep-review):** (a) dropdown-populate effect uses the canonical `reactive.isolate()` + `input["eng_stakeholder"].is_set()` read (a direct read of an unset input raises `SilentException`); (b) `eng_status` choices precomputed into `status_choices` to stay under flake8's 100-char limit; (c) added a **migrated-v3-saves-as-schema-4-on-disk** test that inspects the raw JSON (the load-based test alone is masked by upgrade-on-load); (d) e2e polls for the `SH###` option before selecting and also asserts the **resolved stakeholder name** in the log; (e) `project_to_bytes` exists — clarified it's simply not the tool for a file round-trip.

**Conventions verified against live code (2026-06-06):**
- Data model (`data_structure.py`): `PROJECT_SCHEMA_VERSION = 3` (:19); `Stakeholder` (:169-188); `Project` (:192) with `to_dict` (:198-206, emits `metadata`/`isa_data`/`stakeholders`), `from_dict` (:211-228, field-filtered per-entity), `replace` (:238-242 → `_dc_replace`), `with_modified_now` (:244-249 → `self.replace(metadata=…)`).
- Envelope: every **partial** writer already uses `.replace()` (`ai_isa_wizard.py:466,574,580,648,932`, `isa_data_entry.py:175`, `pims_project.py:172`, `pims_stakeholders.py:189,244`); whole-project loaders `set()` a full `from_dict` project (`import_data.py:147`, `recent_projects.py:174`, `templates.py:98`, `project_io.py:200/228/253`). Adding a field survives all of them.
- Pure helpers (`stakeholders.py`): `add_stakeholder`/`update_stakeholder`/`remove_stakeholder` (new lists, injected `today`); SH2's `QUADRANTS`/`level_num`/`summarize_quadrants` were appended there.
- Module (`pims_stakeholders.py`): code-list constants `_TYPE_CODES`…`_ENGAGE_CODES` (:28-34); `_choices(codes, group, translate)` builds `{"": "—", code: translate(f"stakeholders.{group}.{code}")}` (:37-42); plain `_register_panel`/`_grid_panel` (un-decorated, :45/:87); `navset_tab(..., id="stakeholder_tabs")` (:105-108); server has `T`/`tr`/`_t` (:124-125), `_items()` (:129-130), `render.DataGrid(pd.DataFrame(rows or stub))` (:143-144), `event_bus.emit_isa_change()` (:190,246), and the `_clear_form` `ui.update_select(..., selected="")` idiom (:162-170).
- i18n (`core.json`): top-level `"translation"`; per-key 9-lang objects; SH1's `stakeholders.engagement.inform/consult/involve/collaborate/empower` (:3743-3797) are the **engagement-level** labels — SH3 uses a separate `stakeholders.activity.*` namespace.
- Tests: `tests/test_stakeholders.py` imports `save_project_atomic`/`load_project` from `sespy.persistent_storage` and uses a `_proj_with(...)` factory; the **save-path round-trip pattern is `save_project_atomic(proj, p)` → `load_project(p)`** (`project_to_bytes` exists at `persistent_storage.py:123` but isn't the tool for a file round-trip). `tests/test_data_structure.py::test_schema_version_is_3` (:14-15) is the only exact-version assertion; `test_from_dict_loads_legacy_v1_files_silently` (:66-78) does **not** assert version preservation (so upgrade-on-load is safe). `utils.next_id(existing_ids, prefix)` → `f"{prefix}{n:03d}"`.
- e2e (`test_stakeholders_e2e.py`): the SH2 grid tab switches via `#stakeholders-stakeholder_tabs a[data-value='Power-Interest Grid']`; `_set_select(page, id, value)` drives a native `<select>` via `el.value`+`dispatchEvent('change')`; `_poll_table_contains` polls a table's inner text. A `nav_panel`'s `data-value` equals its label string.

---

## Task 1: Data model + persistence (`Engagement`, schema 3→4)

**Files:**
- Modify: `sespy/data_structure.py` (add `Engagement`; `Project.engagements`; `to_dict`/`from_dict` + schema upgrade-on-load; `PROJECT_SCHEMA_VERSION` 3→4)
- Test: `tests/test_stakeholders.py` (append), `tests/test_data_structure.py` (rename schema test)

- [ ] **Step 1: Write the failing tests**

  Append to `tests/test_stakeholders.py`. Extend the top import to add `Engagement`:
  ```python
  from sespy.data_structure import (
      Engagement,
      IsaData,
      Project,
      ProjectMetadata,
      Stakeholder,
  )
  ```
  Add a factory next to `_proj_with` and the tests:
  ```python
  def _proj_with_eng(stakeholders, engagements):
      return Project(
          metadata=ProjectMetadata.new("T"),
          isa_data=IsaData(),
          stakeholders=stakeholders,
          engagements=engagements,
      )


  def test_engagement_defaults():
      e = Engagement(id="ENG001", stakeholder_id="SH001")
      assert e.method == "" and e.outcomes == ""
      assert e.status == "planned"
      assert e.created_at == ""


  def test_project_roundtrip_preserves_engagements():
      e = Engagement(id="ENG001", stakeholder_id="SH001", method="workshop",
                     date="2026-06-06", objectives="align", outcomes="agreed",
                     status="completed", facilitator="A. B.", created_at="2026-06-06")
      proj = _proj_with_eng([Stakeholder(id="SH001", name="X")], [e])
      back = Project.from_dict(proj.to_dict())
      assert back.engagements == [e]


  def test_from_dict_missing_engagements_key_yields_empty_list():
      raw = {"metadata": {"name": "v3"}, "isa_data": {"elements": [], "connections": []},
             "stakeholders": [{"id": "SH001", "name": "X"}]}
      assert Project.from_dict(raw).engagements == []


  def test_from_dict_tolerates_unknown_engagement_key():
      raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
             "engagements": [{"id": "ENG001", "stakeholder_id": "SH001", "future_field": 1}]}
      assert Project.from_dict(raw).engagements == [
          Engagement(id="ENG001", stakeholder_id="SH001")]


  def test_from_dict_upgrades_schema_version_on_load():
      raw = {"metadata": {"name": "old", "schema_version": 3},
             "isa_data": {"elements": [], "connections": []},
             "engagements": [{"id": "ENG001", "stakeholder_id": "SH001"}]}
      assert Project.from_dict(raw).metadata.schema_version == 4


  def test_with_modified_now_preserves_engagements():
      e = Engagement(id="ENG001", stakeholder_id="SH001")
      proj = _proj_with_eng([], [e])
      assert proj.with_modified_now().engagements == [e]


  def test_save_path_roundtrip_preserves_engagements(tmp_path):
      e = Engagement(id="ENG001", stakeholder_id="SH001", method="survey")
      proj = _proj_with_eng([Stakeholder(id="SH001", name="X")], [e])
      p = tmp_path / "proj.json"
      save_project_atomic(proj, p)
      back = load_project(p)
      assert back.engagements == [e]
      assert back.metadata.schema_version == 4


  def test_migrated_v3_saves_as_schema_4_on_disk(tmp_path):
      # Start from a RAW v3 payload (not a fresh v4 project): load → save →
      # inspect the RAW JSON so the on-disk version isn't masked by from_dict's
      # upgrade-on-load.
      import json
      old = Project.from_dict({
          "metadata": {"name": "old", "schema_version": 3},
          "isa_data": {"elements": [], "connections": []},
          "engagements": [{"id": "ENG001", "stakeholder_id": "SH001"}],
      })
      p = tmp_path / "old.json"
      save_project_atomic(old, p)
      raw = json.loads(p.read_text(encoding="utf-8"))
      assert raw["metadata"]["schema_version"] == 4
      assert raw["engagements"][0]["id"] == "ENG001"
  ```
  In `tests/test_data_structure.py` rename the schema test:
  ```python
  def test_schema_version_is_4():
      assert PROJECT_SCHEMA_VERSION == 4
  ```

- [ ] **Step 2: Run; verify fail**
  `micromamba run -n shiny python -m pytest tests/test_stakeholders.py tests/test_data_structure.py -q` → ImportError / assertion failures (no `Engagement`, version is 3).

- [ ] **Step 3: Implement**

  In `sespy/data_structure.py`:
  1. `PROJECT_SCHEMA_VERSION = 4` (:19).
  2. Add the dataclass (after `Stakeholder`, before `Project`):
     ```python
     @dataclass
     class Engagement:
         """A planned/completed engagement activity for one stakeholder.
         Ported from pims_stakeholder_module.R Tab 3 (add_engagement ~639-650)."""
         id: str
         stakeholder_id: str
         method: str = ""
         date: str = ""
         objectives: str = ""
         outcomes: str = ""
         status: str = "planned"
         facilitator: str = ""
         created_at: str = ""
     ```
  3. `Project`: add `engagements: list["Engagement"] = field(default_factory=list)`.
  4. `to_dict`: add `"engagements": [asdict(e) for e in self.engagements]`.
  5. `from_dict`: after the `stakeholders` block, add (and upgrade the version):
     ```python
     eng_keys = {f.name for f in fields(Engagement)}
     engagements = [Engagement(**{k: v for k, v in e.items() if k in eng_keys})
                    for e in (raw.get("engagements") or [])]
     meta.schema_version = PROJECT_SCHEMA_VERSION   # upgrade-on-load (no down-convert)
     return cls(metadata=meta, isa_data=isa,
                stakeholders=stakeholders, engagements=engagements)
     ```

- [ ] **Step 4: Run; verify pass**
  `micromamba run -n shiny python -m pytest tests/test_stakeholders.py tests/test_data_structure.py -q` → green.

- [ ] **Step 5: flake8 + commit**
  `micromamba run -n shiny python -m flake8 sespy/data_structure.py tests/test_stakeholders.py tests/test_data_structure.py --max-line-length=100`
  ```bash
  git add sespy/data_structure.py tests/test_stakeholders.py tests/test_data_structure.py
  git commit -m "feat(data): Engagement model + Project.engagements, schema 3->4"
  ```

---

## Task 2: Pure helpers (`add_engagement`, `remove_engagement`, `engagement_rows`)

**Files:**
- Modify: `sespy/stakeholders.py` (append helpers + `ENGAGEMENT_METHODS`/`ENGAGEMENT_STATUSES` constants)
- Test: `tests/test_stakeholders.py` (append)

- [ ] **Step 1: Write the failing tests**

  Extend the top import:
  ```python
  from sespy.stakeholders import (
      add_engagement,
      add_stakeholder,
      classify_quadrant,
      engagement_rows,
      level_num,
      remove_engagement,
      remove_stakeholder,
      summarize_quadrants,
      update_stakeholder,
  )
  ```
  Tests (append). The `translate` fake returns the key (proves known-vs-unknown handling):
  ```python
  def _ident(key):  # mimic Translator.t() returning the key on a miss
      return key


  def test_add_engagement_assigns_id_and_created_at():
      out = add_engagement([], {"stakeholder_id": "SH001", "method": "workshop"},
                           today="2026-06-06")
      assert len(out) == 1 and out[0].id == "ENG001"
      assert out[0].created_at == "2026-06-06"
      assert out[0].stakeholder_id == "SH001"


  def test_remove_engagement_drops_by_id():
      items = [Engagement(id="ENG001", stakeholder_id="SH001"),
               Engagement(id="ENG002", stakeholder_id="SH002")]
      out = remove_engagement(items, "ENG001")
      assert [e.id for e in out] == ["ENG002"]


  def test_engagement_rows_resolves_name_and_labels():
      sh = [Stakeholder(id="SH001", name="Port Authority")]
      eng = [Engagement(id="ENG001", stakeholder_id="SH001", method="workshop",
                        status="completed", date="2026-06-06")]
      rows = engagement_rows(eng, sh, translate=_ident)
      assert rows[0]["stakeholder"] == "Port Authority"
      assert rows[0]["method"] == "stakeholders.activity.method.workshop"
      assert rows[0]["status"] == "stakeholders.activity.status.completed"
      assert rows[0]["date"] == "2026-06-06"


  def test_engagement_rows_dangling_fk_yields_blank_name():
      eng = [Engagement(id="ENG001", stakeholder_id="GONE")]
      rows = engagement_rows(eng, [], translate=_ident)
      assert rows[0]["stakeholder"] == ""


  def test_engagement_rows_unknown_code_passes_through_verbatim():
      eng = [Engagement(id="ENG001", stakeholder_id="SH001",
                        method="telepathy", status="vibes")]
      rows = engagement_rows(eng, [Stakeholder(id="SH001", name="X")], translate=_ident)
      assert rows[0]["method"] == "telepathy"     # NOT the i18n key
      assert rows[0]["status"] == "vibes"


  def test_engagement_rows_blank_code_is_blank():
      eng = [Engagement(id="ENG001", stakeholder_id="SH001")]  # method="" status="planned"
      rows = engagement_rows(eng, [Stakeholder(id="SH001", name="X")], translate=_ident)
      assert rows[0]["method"] == ""
      assert rows[0]["status"] == "stakeholders.activity.status.planned"
  ```
  (Add `Engagement` to the `from sespy.data_structure import (...)` block if not already present from Task 1.)

- [ ] **Step 2: Run; verify fail** — ImportError on the new helper names.

- [ ] **Step 3: Implement** — append to `sespy/stakeholders.py` (add `Engagement` to its import from `data_structure`):
  ```python
  # --- SH3: engagement activity log (pure) -----------------------------------
  ENGAGEMENT_METHODS = ("workshop", "interview", "survey", "focus_group",
                        "public_meeting", "advisory_committee", "email_newsletter",
                        "one_on_one", "site_visit", "other")
  ENGAGEMENT_STATUSES = ("planned", "completed", "cancelled", "ongoing")


  def add_engagement(items, fields_, *, today):
      eid = next_id([e.id for e in items], "ENG")
      return [*items, Engagement(id=eid, created_at=today, **fields_)]


  def remove_engagement(items, eid):
      return [e for e in items if e.id != eid]


  def _label(code, known, translate, group):
      # Translate only KNOWN codes (Translator.t() returns the key on a miss);
      # pass an unknown/blank code through verbatim.
      if code and code in known:
          return translate(f"stakeholders.activity.{group}.{code}")
      return code


  def engagement_rows(engagements, stakeholders, *, translate):
      names = {s.id: s.name for s in stakeholders}
      return [
          {
              "stakeholder": names.get(e.stakeholder_id, ""),
              "method": _label(e.method, ENGAGEMENT_METHODS, translate, "method"),
              "date": e.date,
              "objectives": e.objectives,
              "outcomes": e.outcomes,
              "status": _label(e.status, ENGAGEMENT_STATUSES, translate, "status"),
              "facilitator": e.facilitator,
          }
          for e in engagements
      ]
  ```
  Type hints mirror the existing helpers' style (`list[Engagement]`, etc.); add them to match `add_stakeholder`'s signature form.

- [ ] **Step 4: Run; verify pass** — `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q` green.

- [ ] **Step 5: flake8 + commit**
  ```bash
  git add sespy/stakeholders.py tests/test_stakeholders.py
  git commit -m "feat(stakeholders): pure engagement add/remove/rows helpers"
  ```

---

## Task 3: i18n keys (`stakeholders.activity.*` + `stakeholders.tab_activity`)

**Files:**
- Modify: `sespy/translations/core.json`

- [ ] **Step 1: Add the keys (programmatic, lowest-risk)**

  Use a script (mirrors how SH1/SH2 added keys) so all 9 languages get the same English placeholder and the `"translation"` wrapper is respected. Keys + English values:
  - `stakeholders.tab_activity` → **"Engagement Planning"** (this exact value becomes the tab's rendered `data-value`).
  - `stakeholders.activity.heading` → "Stakeholder engagement strategy"
  - `stakeholders.activity.add_heading` → "Define engagement activities"
  - `stakeholders.activity.stakeholder` → "Stakeholder"
  - `stakeholders.activity.method` → "Engagement method"
  - `stakeholders.activity.date` → "Planned / completed date"
  - `stakeholders.activity.objectives` → "Engagement objectives"
  - `stakeholders.activity.outcomes` → "Outcomes / notes"
  - `stakeholders.activity.status` → "Status"
  - `stakeholders.activity.facilitator` → "Facilitator / contact"
  - `stakeholders.activity.add` → "Add activity"
  - `stakeholders.activity.required` → "Select a stakeholder and a method first."
  - `stakeholders.activity.empty` → "No engagement activities yet — add one above."
  - `stakeholders.activity.log_heading` → "Engagement activities log"
  - `stakeholders.activity.method.<code>` (10): workshop→"Workshop", interview→"Interview", survey→"Survey", focus_group→"Focus group", public_meeting→"Public meeting", advisory_committee→"Advisory committee", email_newsletter→"Email / newsletter", one_on_one→"One-on-one meeting", site_visit→"Site visit", other→"Other"
  - `stakeholders.activity.status.<code>` (4): planned→"Planned", completed→"Completed", cancelled→"Cancelled", ongoing→"Ongoing"

  The 9 language codes are whatever the existing `stakeholders.tab_grid` entry uses — read that key's object and reuse its key set (English string for every language, per SP4).

- [ ] **Step 2: Validate**
  ```
  micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation']; ks=['stakeholders.tab_activity','stakeholders.activity.method.workshop','stakeholders.activity.status.planned','stakeholders.activity.required','stakeholders.activity.empty']; [print(k, sorted(d[k].keys())==sorted(d['stakeholders.tab_grid'].keys()), d[k]['en']) for k in ks]"
  ```
  Expect each key present, language-set identical to `tab_grid`'s, English values as above. Confirm valid JSON (the load itself proves it).

- [ ] **Step 3: Commit**
  ```bash
  git add sespy/translations/core.json
  git commit -m "i18n: stakeholders.activity.* + tab_activity (9 langs)"
  ```

---

## Task 4: Module — Engagement Planning sub-tab

**Files:**
- Modify: `sespy/modules/pims_stakeholders.py`

- [ ] **Step 1: Add code-list constants + the engagement panel**

  Import the canonical code tuples from the pure module (single source of truth) and add module-level method/status code lists for `_choices`:
  ```python
  from sespy.stakeholders import (
      ENGAGEMENT_METHODS,
      ENGAGEMENT_STATUSES,
      add_engagement,
      add_stakeholder,
      engagement_rows,
      level_num,
      remove_stakeholder,
      summarize_quadrants,
      update_stakeholder,
  )
  ```
  Add `Engagement` is NOT needed in the module (only the list type via `project_data`). Add a plain panel function (NO `@module.ui`), next to `_grid_panel`:
  ```python
  def _engagement_panel() -> ui.Tag:
      """Engagement Planning tab — add-form + activity log. Plain (un-decorated)."""
      status_choices = {
          c: _t(f"stakeholders.activity.status.{c}")
          for c in ENGAGEMENT_STATUSES
      }
      return ui.div(
          ui.h5(_t("stakeholders.activity.add_heading")),
          ui.layout_columns(
              ui.card(
                  ui.input_select("eng_stakeholder", _t("stakeholders.activity.stakeholder"), {}),
                  ui.input_select("eng_method", _t("stakeholders.activity.method"),
                                  _choices(list(ENGAGEMENT_METHODS), "activity.method", _t)),
                  ui.input_date("eng_date", _t("stakeholders.activity.date")),
                  ui.input_text_area("eng_objectives", _t("stakeholders.activity.objectives")),
                  ui.input_text_area("eng_outcomes", _t("stakeholders.activity.outcomes")),
                  ui.input_select("eng_status", _t("stakeholders.activity.status"),
                                  status_choices, selected="planned"),
                  ui.input_text("eng_facilitator", _t("stakeholders.activity.facilitator")),
                  ui.input_action_button("add_engagement", _t("stakeholders.activity.add"),
                                         class_="btn-success"),
              ),
              ui.card(
                  ui.h5(_t("stakeholders.activity.log_heading")),
                  ui.output_data_frame("engagement_table"),
              ),
              col_widths=[5, 7],
          ),
      )
  ```
  Add the 3rd nav panel to `pims_stakeholders_ui`:
  ```python
  ui.nav_panel(_t("stakeholders.tab_activity"), _engagement_panel()),
  ```
  (immediately after the `tab_grid` panel, before `id="stakeholder_tabs"`).
  Note: `eng_status` uses a code→label dict WITHOUT a blank option (status always set, defaults `planned`); `eng_method` uses `_choices(...)` which DOES prepend `""`.

- [ ] **Step 2: Add the server logic**

  In `pims_stakeholders_server`, add an accessor near `_items()`:
  ```python
      def _engagements():
          return project_data.get().engagements
  ```
  Dropdown-populate effect (subscribe only to `_items()`; read the current
  selection dependency-free via `reactive.isolate()` + `is_set()`, tolerating the
  input being unset on first render — a direct read of an unset input raises
  `SilentException`):
  ```python
      @reactive.effect
      def _populate_eng_stakeholders():
          choices = {"": "—", **{s.id: s.name for s in _items()}}
          with reactive.isolate():
              val = input["eng_stakeholder"]
              current = (val() or "") if val.is_set() else ""
          selected = current if current in choices else ""
          ui.update_select("eng_stakeholder", choices=choices, selected=selected)
  ```
  (`reactive.isolate()` suppresses the dependency that reading the input — or
  `is_set()` — would otherwise create, so the effect re-runs only when `_items()`
  changes, never in a loop.)

  Add handler:
  ```python
      @reactive.effect
      @reactive.event(input.add_engagement)
      def _add_engagement():
          sid = input.eng_stakeholder()
          method = input.eng_method()
          if not sid or not method or sid not in {s.id for s in _items()}:
              ui.notification_show(tr("stakeholders.activity.required"),
                                   type="warning", duration=3)
              return
          d = input.eng_date()
          fields_ = {
              "stakeholder_id": sid,
              "method": method,
              "date": d.isoformat() if d else "",
              "objectives": input.eng_objectives().strip(),
              "outcomes": input.eng_outcomes().strip(),
              "status": input.eng_status(),
              "facilitator": input.eng_facilitator().strip(),
          }
          new_list = add_engagement(_engagements(), fields_, today=date.today().isoformat())
          project_data.set(project_data.get().replace(engagements=new_list))
          event_bus.emit_isa_change()
          ui.update_text_area("eng_objectives", value="")
          ui.update_text_area("eng_outcomes", value="")
          ui.update_text("eng_facilitator", value="")
  ```
  Log table render:
  ```python
      @output
      @render.data_frame
      def engagement_table():
          rows = engagement_rows(_engagements(), _items(), translate=tr)
          stub = [{"stakeholder": tr("stakeholders.activity.empty"), "method": "",
                   "date": "", "objectives": "", "outcomes": "", "status": "",
                   "facilitator": ""}]
          return render.DataGrid(pd.DataFrame(rows or stub), height="320px")
  ```

- [ ] **Step 3: Verify**
  ```
  micromamba run -n shiny python -c "from sespy.modules.pims_stakeholders import pims_stakeholders_ui, pims_stakeholders_server; pims_stakeholders_ui('stakeholders'); print('ok')"
  micromamba run -n shiny python -m flake8 sespy/modules/pims_stakeholders.py --max-line-length=100
  micromamba run -n shiny python -c "import app; print('app ok')"
  ```
  **Input-preservation guard** — the 10 SH1 register inputs must still exist:
  `(Select-String -Path sespy\modules\pims_stakeholders.py -Pattern 'sh_(name|type|sector|contact|interests|role|power|interest|attitude|engagement_level)' | ForEach-Object { ($_.Line | Select-String -Pattern 'sh_\w+' -AllMatches).Matches.Value } | Sort-Object -Unique).Count` → must be **10**.
  Then the unit suite: `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` → green.

- [ ] **Step 4: Commit**
  ```bash
  git add sespy/modules/pims_stakeholders.py
  git commit -m "feat(stakeholders): Engagement Planning sub-tab (form + activity log)"
  ```

---

## Task 5: e2e — engagement add + log

**Files:**
- Modify: `tests/test_stakeholders_e2e.py` (extend; CRUD + grid sections stay UNCHANGED)

- [ ] **Step 1: Develop the selectors against the live app**

  Launch `micromamba run -n shiny shiny run app.py --port 8000` (background). Using a throwaway Playwright probe: nav `#sespy_nav_stakeholders`, ensure a stakeholder exists, switch to the activity tab via `#stakeholders-stakeholder_tabs a[data-value='Engagement Planning']` (the verified SH2 `data-value` pattern — NOT `:has-text`), set `#stakeholders-eng_stakeholder` (to a real `SH###` id) and `#stakeholders-eng_method` via the `el.value`+dispatch helper, click `#stakeholders-add_engagement`, and confirm a row text appears in `#stakeholders-engagement_table`. **Record the stakeholder id** the dropdown actually exposes (it is `SH001`-style; the e2e must select that option value, not the name). Delete the probe afterward.

- [ ] **Step 2: Extend the e2e script**

  After the grid section (section 7), add a section 8. Reuse the SH2 `_set_select` and `_poll_table_contains`-style helpers (add a small `_poll_eng_table_contains` or generalize). Pseudocode:
  ```python
  # 8. ENGAGEMENT — add an activity for an existing stakeholder, assert in the log
  await page.click("#stakeholders-stakeholder_tabs a[data-value='Engagement Planning']")
  await page.wait_for_timeout(800)
  # the dropdown is populated from existing stakeholders (an update-select message
  # that may lag) — POLL until a real SH### option exists before selecting it.
  sid = None
  for _ in range(16):
      sid = await page.eval_on_selector(
          "#stakeholders-eng_stakeholder",
          "el => Array.from(el.options).map(o => o.value).find(v => v.startsWith('SH'))")
      if sid:
          break
      await page.wait_for_timeout(500)
  assert sid, "engagement stakeholder dropdown has no SH### option"
  await _set_select(page, "stakeholders-eng_stakeholder", sid)
  # capture the selected stakeholder's display name to assert name-resolution
  sh_label = await page.eval_on_selector(
      "#stakeholders-eng_stakeholder",
      "el => el.options[el.selectedIndex].text")
  await _set_select(page, "stakeholders-eng_method", "workshop")
  await page.click("#stakeholders-add_engagement")
  # the log table shows the method label "Workshop" AND the resolved stakeholder name
  txt = ""
  for _ in range(16):
      txt = await page.inner_text("#stakeholders-engagement_table")
      if "Workshop" in txt and sh_label in txt:
          break
      await page.wait_for_timeout(500)
  assert "Workshop" in txt and sh_label in txt, "engagement not in log"
  print("8. engagement: activity added + name-resolved in log — PASS")
  ```
  (A stakeholder exists by this point — section 6 added "Coastal NGO".)

- [ ] **Step 3: Run**
  With the app on :8000: `micromamba run -n shiny python tests/test_stakeholders_e2e.py` → exit 0. Stop the background server.

- [ ] **Step 4: Commit**
  ```bash
  git add tests/test_stakeholders_e2e.py
  git commit -m "test(stakeholders): e2e — engagement activity add + log"
  ```

---

## Final verification

- [ ] `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — green.
- [ ] `micromamba run -n shiny python tests/run_e2e.py` — all scripts pass (incl. the extended stakeholders e2e).
- [ ] Then invoke **superpowers:finishing-a-development-branch**.

## Sequencing notes
- Tasks are ordered for TDD: data model (1) → pure helpers (2) → i18n (3) → module (4) → e2e (5). Tasks 1–3 are independent of the live app; Task 4 wires them; Task 5 exercises the running app.
- Branch: cut `feat/pims-stakeholders-sh3` from `main` before Task 1.
