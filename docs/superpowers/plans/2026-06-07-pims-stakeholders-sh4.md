# PIMS Stakeholders SH4 — Communication Plan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a **communication plan** log as a fourth sub-tab of the Stakeholders panel: a `Communication` child entity (persisted, schema 4→5), pure helpers, an add-form + log table, i18n, and tests.

**Architecture:** A `Communication` is a project-level child record (like SH3's `Engagement`) but with **no stakeholder FK** — `audience` is a category code — so there is **no dropdown-populate effect and no FK validation**. Persistence rides the existing `Project.replace()` + upgrade-on-load infra (only `to_dict`/`from_dict` + schema bump change). Pure helpers (`add_communication`, `remove_communication`, `communication_rows`) go in `sespy/stakeholders.py`; the existing `_label` helper is generalized to take a key prefix (SH3 call sites updated, SH3 tests stay green). The module gains a 4th `nav_panel` + an add handler + a `@render.data_frame` log. **No `app.py`, SH1/SH2/SH3-feature change** (apart from the internal `_label` refactor).

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, pandas, pytest, Playwright. Run via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-07-pims-stakeholders-sh4-design.md` (rev. 2).

**Plan rev. 2 (from deep-review):** split the `from_dict` `return cls(...)` across lines (the one-line form exceeded flake8's 100-char limit). Review verified everything else — the `_label` refactor keeps SH3 tests green, all four 4→5 schema assertions are covered, snippets run, and the i18n key set is complete.

**Conventions verified against live code (2026-06-07, post-SH3):**
- Data model (`data_structure.py`): `PROJECT_SCHEMA_VERSION = 4` (:19); `to_dict` emits `metadata`/`isa_data`/`stakeholders`/`engagements`; `from_dict` parses each entity field-filtered and runs `meta.schema_version = PROJECT_SCHEMA_VERSION` (upgrade-on-load) before `return cls(...)`; `fields` already imported from `dataclasses`.
- Pure helpers (`stakeholders.py`): SH3 added `_label(code, known, translate, group)` → `translate(f"stakeholders.activity.{group}.{code}")`, called as `_label(e.method, ENGAGEMENT_METHODS, translate, "method")` and `_label(e.status, ENGAGEMENT_STATUSES, translate, "status")`; `add_engagement`/`remove_engagement`/`engagement_rows`; `ENGAGEMENT_METHODS`/`ENGAGEMENT_STATUSES` tuples; `next_id` + `Engagement`/`Stakeholder` imported.
- Module (`pims_stakeholders.py`): `_choices(codes, group, translate)` → `{"": "—", code: translate(f"stakeholders.{group}.{code}")}`; plain `_register_panel`/`_grid_panel`/`_engagement_panel` (un-decorated); `navset_tab(..., id="stakeholder_tabs")` now has 3 panels; server has `tr`/`_t`/`_items()`/`_engagements()`/`event_bus.emit_isa_change()`; SH3 add handler uses `@reactive.effect`+`@reactive.event(input.add_engagement, ignore_init=True)`, guarded `d.isoformat() if d else ""`, `ui.update_text_area(..., value="")`; the log render is `render.DataGrid(pd.DataFrame(rows or stub), height="320px")`.
- i18n (`core.json`): top-level `"translation"`; SH3's `stakeholders.activity.*` + `stakeholders.tab_activity` have 9-lang objects (langs: de, el, en, es, fr, it, lt, no, pt); JSON round-trips identically with `json.dumps(d, indent=2, ensure_ascii=False) + "\n"`; **no existing `stakeholders.comm*` keys** (verified).
- Tests: `tests/test_stakeholders.py` uses `_proj_with`/`_proj_with_eng` factories + `save_project_atomic`/`load_project`; the SH3 schema assertions at `4` are in `test_from_dict_upgrades_schema_version_on_load`, `test_save_path_roundtrip_preserves_engagements`, `test_migrated_v3_saves_as_schema_4_on_disk` (+ `test_data_structure.py::test_schema_version_is_4`). `next_id(existing_ids, prefix)` → `f"{prefix}{n:03d}"`.
- e2e (`test_stakeholders_e2e.py`): SH3 section 8 switches tab via `a[data-value='Engagement Planning']` and reads `#stakeholders-engagement_table` **inline** in a poll loop (NOT the `_poll_table_contains` helper, which is hardcoded to `#stakeholders-stakeholder_table`); `_set_select(page, id, value)` drives a native `<select>`.

---

## Task 1: Data model + persistence (`Communication`, schema 4→5)

**Files:**
- Modify: `sespy/data_structure.py`, `tests/test_stakeholders.py`, `tests/test_data_structure.py`

- [x] **Step 1: Write the failing tests**

  Extend the `from sespy.data_structure import (...)` block in `tests/test_stakeholders.py` to add `Communication`. Add a factory + tests:
  ```python
  def _proj_with_comm(communications):
      return Project(
          metadata=ProjectMetadata.new("T"),
          isa_data=IsaData(),
          communications=communications,
      )


  def test_communication_defaults():
      c = Communication(id="COMM001")
      assert c.audience == "" and c.comm_type == "" and c.message == ""
      assert c.frequency == "one_time"
      assert c.created_at == ""


  def test_project_roundtrip_preserves_communications():
      c = Communication(id="COMM001", audience="key_players", comm_type="report",
                        date="2026-06-07", frequency="monthly", message="status",
                        responsible="A. B.", created_at="2026-06-07")
      proj = _proj_with_comm([c])
      back = Project.from_dict(proj.to_dict())
      assert back.communications == [c]


  def test_from_dict_missing_communications_key_yields_empty_list():
      raw = {"metadata": {"name": "v4"}, "isa_data": {"elements": [], "connections": []}}
      assert Project.from_dict(raw).communications == []


  def test_from_dict_tolerates_unknown_communication_key():
      raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
             "communications": [{"id": "COMM001", "audience": "ngos", "future_field": 1}]}
      assert Project.from_dict(raw).communications == [
          Communication(id="COMM001", audience="ngos")]


  def test_with_modified_now_preserves_communications():
      c = Communication(id="COMM001", audience="government")
      proj = _proj_with_comm([c])
      assert proj.with_modified_now().communications == [c]


  def test_save_path_roundtrip_preserves_communications(tmp_path):
      c = Communication(id="COMM001", comm_type="newsletter")
      proj = _proj_with_comm([c])
      p = tmp_path / "proj.json"
      save_project_atomic(proj, p)
      back = load_project(p)
      assert back.communications == [c]
      assert back.metadata.schema_version == 5


  def test_migrated_v4_saves_as_schema_5_on_disk(tmp_path):
      import json
      old = Project.from_dict({
          "metadata": {"name": "old", "schema_version": 4},
          "isa_data": {"elements": [], "connections": []},
          "communications": [{"id": "COMM001", "audience": "ngos"}],
      })
      p = tmp_path / "old.json"
      save_project_atomic(old, p)
      raw = json.loads(p.read_text(encoding="utf-8"))
      assert raw["metadata"]["schema_version"] == 5
      assert raw["communications"][0]["id"] == "COMM001"
  ```
  **Update the existing SH3 schema assertions (4→5)** in the same file:
  - `test_from_dict_upgrades_schema_version_on_load`: `== 4` → `== 5`.
  - `test_save_path_roundtrip_preserves_engagements`: `back.metadata.schema_version == 4` → `== 5`.
  - rename `test_migrated_v3_saves_as_schema_4_on_disk` → `test_migrated_v3_saves_as_schema_5_on_disk` and its `raw[...]["schema_version"] == 4` → `== 5`.

  In `tests/test_data_structure.py` rename `test_schema_version_is_4` → `test_schema_version_is_5` (assert `== 5`).

- [x] **Step 2: Run; verify fail**
  `micromamba run -n shiny python -m pytest tests/test_stakeholders.py tests/test_data_structure.py -q` → ImportError (no `Communication`) / version-5 assertion failures.

- [x] **Step 3: Implement** in `sespy/data_structure.py`:
  1. `PROJECT_SCHEMA_VERSION = 5`.
  2. Add the dataclass after `Engagement` (before `Project`):
     ```python
     @dataclass
     class Communication:
         """A planned/tracked stakeholder communication item.
         Ported from pims_stakeholder_module.R Tab 4 (add_communication ~677-686)."""
         id: str
         audience: str = ""
         comm_type: str = ""
         date: str = ""
         frequency: str = "one_time"
         message: str = ""
         responsible: str = ""
         created_at: str = ""
     ```
  3. `Project`: add `communications: list["Communication"] = field(default_factory=list)`.
  4. `to_dict`: add `"communications": [asdict(c) for c in self.communications]`.
  5. `from_dict`: after the `engagements` block (and before `meta.schema_version = …`):
     ```python
     comm_keys = {f.name for f in fields(Communication)}
     communications = [
         Communication(**{k: v for k, v in c.items() if k in comm_keys})
         for c in (raw.get("communications") or [])
     ]
     ```
     and extend the return (split across lines to stay under flake8's 100-char limit):
     ```python
     return cls(
         metadata=meta,
         isa_data=isa,
         stakeholders=stakeholders,
         engagements=engagements,
         communications=communications,
     )
     ```

- [x] **Step 4: Run; verify pass** — `micromamba run -n shiny python -m pytest tests/test_stakeholders.py tests/test_data_structure.py -q` → green.

- [x] **Step 5: flake8 + commit**
  `micromamba run -n shiny python -m flake8 sespy/data_structure.py tests/test_stakeholders.py --max-line-length=100` (note: `tests/test_data_structure.py` has PRE-EXISTING E402/F401 at ~line 124 unrelated to SH4 — do not fix).
  ```bash
  git add sespy/data_structure.py tests/test_stakeholders.py tests/test_data_structure.py
  git commit -m "feat(data): Communication model + Project.communications, schema 4->5"
  ```

---

## Task 2: Pure helpers (`add_communication`, `remove_communication`, `communication_rows`) + `_label` refactor

**Files:**
- Modify: `sespy/stakeholders.py`, `tests/test_stakeholders.py`

- [x] **Step 1: Write the failing tests** — extend the `from sespy.stakeholders import (...)` block with `add_communication`, `communication_rows`, `remove_communication`. Append:
  ```python
  def test_add_communication_assigns_id_and_created_at():
      out = add_communication([], {"audience": "key_players", "comm_type": "report"},
                              today="2026-06-07")
      assert len(out) == 1 and out[0].id == "COMM001"
      assert out[0].created_at == "2026-06-07"


  def test_remove_communication_drops_by_id():
      items = [Communication(id="COMM001"), Communication(id="COMM002")]
      assert [c.id for c in remove_communication(items, "COMM001")] == ["COMM002"]


  def test_communication_rows_maps_known_codes_to_labels():
      c = [Communication(id="COMM001", audience="key_players", comm_type="report",
                         frequency="monthly", date="2026-06-07", message="m",
                         responsible="r")]
      rows = communication_rows(c, translate=_ident)
      assert rows[0]["audience"] == "stakeholders.comm.audience.key_players"
      assert rows[0]["type"] == "stakeholders.comm.type.report"
      assert rows[0]["frequency"] == "stakeholders.comm.frequency.monthly"
      assert rows[0]["date"] == "2026-06-07"
      assert rows[0]["message"] == "m" and rows[0]["responsible"] == "r"


  def test_communication_rows_unknown_code_passes_through_verbatim():
      c = [Communication(id="COMM001", audience="aliens", comm_type="smoke_signal",
                         frequency="hourly")]
      rows = communication_rows(c, translate=_ident)
      assert rows[0]["audience"] == "aliens"
      assert rows[0]["type"] == "smoke_signal"
      assert rows[0]["frequency"] == "hourly"
  ```
  (`Communication` is imported into the test file in Task 1; `_ident` was added in SH3's tests.)

- [x] **Step 2: Run; verify fail** — ImportError on the new helper names.

- [x] **Step 3: Implement** in `sespy/stakeholders.py`:
  - Add `Communication` to the `from sespy.data_structure import ...` line.
  - **Generalize `_label`** to take a full prefix, and update the two SH3 call sites:
    ```python
    def _label(code: str, known: tuple[str, ...], translate, prefix: str) -> str:
        # Translate only KNOWN codes (Translator.t() returns the key on a miss);
        # an unknown or blank code is passed through verbatim.
        if code and code in known:
            return translate(f"{prefix}.{code}")
        return code
    ```
    In `engagement_rows`:
    `"method": _label(e.method, ENGAGEMENT_METHODS, translate, "stakeholders.activity.method")`,
    `"status": _label(e.status, ENGAGEMENT_STATUSES, translate, "stakeholders.activity.status")`.
  - Append the constants + helpers:
    ```python
    COMMUNICATION_AUDIENCES = ("all_stakeholders", "key_players", "government",
                               "industry", "ngos", "local_communities",
                               "scientific_community", "specific_stakeholder")
    COMMUNICATION_TYPES = ("report", "newsletter", "presentation", "website_update",
                           "press_release", "social_media", "email", "meeting_notes",
                           "other")
    COMMUNICATION_FREQUENCIES = ("one_time", "weekly", "monthly", "quarterly",
                                 "annual", "as_needed")


    def add_communication(
        items: list[Communication], fields_: dict, *, today: str
    ) -> list[Communication]:
        cid = next_id([c.id for c in items], "COMM")
        return [*items, Communication(id=cid, created_at=today, **fields_)]


    def remove_communication(items: list[Communication], cid: str) -> list[Communication]:
        return [c for c in items if c.id != cid]


    def communication_rows(communications: list[Communication], *, translate) -> list[dict]:
        """Display rows for the communication log: map audience/type/frequency codes ->
        labels (known codes only), in input order."""
        return [
            {
                "audience": _label(c.audience, COMMUNICATION_AUDIENCES, translate,
                                   "stakeholders.comm.audience"),
                "type": _label(c.comm_type, COMMUNICATION_TYPES, translate,
                               "stakeholders.comm.type"),
                "date": c.date,
                "frequency": _label(c.frequency, COMMUNICATION_FREQUENCIES, translate,
                                    "stakeholders.comm.frequency"),
                "message": c.message,
                "responsible": c.responsible,
            }
            for c in communications
        ]
    ```

- [x] **Step 4: Run + flake8** — `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q` (incl. the unchanged SH3 engagement_rows tests) + `flake8 sespy/stakeholders.py tests/test_stakeholders.py --max-line-length=100` → green/clean.

- [x] **Step 5: Commit**
  ```bash
  git add sespy/stakeholders.py tests/test_stakeholders.py
  git commit -m "feat(stakeholders): pure communication helpers + generalize _label"
  ```

---

## Task 3: i18n keys (`stakeholders.comm.*` + `stakeholders.tab_comm`)

**Files:** Modify `sespy/translations/core.json`

- [x] **Step 1: Add the keys (programmatic)** — a temp script that loads the JSON, reuses the 9-lang set from `stakeholders.tab_activity`, adds each key as `{lang: english_value}`, dumps with `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`, then is deleted. Keys + English:
  - `stakeholders.tab_comm` → **"Communication Plan"**
  - `stakeholders.comm.add_heading` → "Add communication item"
  - `stakeholders.comm.audience` → "Target audience"
  - `stakeholders.comm.type` → "Communication type"
  - `stakeholders.comm.date` → "Date"
  - `stakeholders.comm.frequency` → "Frequency"
  - `stakeholders.comm.message` → "Key message / content"
  - `stakeholders.comm.responsible` → "Responsible person"
  - `stakeholders.comm.add` → "Add communication"
  - `stakeholders.comm.required` → "Select a target audience and a communication type first."
  - `stakeholders.comm.empty` → "No communications yet - add one above."
  - `stakeholders.comm.log_heading` → "Communications log"
  - `stakeholders.comm.audience.<code>` (8): all_stakeholders→"All stakeholders", key_players→"Key players", government→"Government", industry→"Industry", ngos→"NGOs", local_communities→"Local communities", scientific_community→"Scientific community", specific_stakeholder→"Specific stakeholder"
  - `stakeholders.comm.type.<code>` (9): report→"Report", newsletter→"Newsletter", presentation→"Presentation", website_update→"Website update", press_release→"Press release", social_media→"Social media", email→"Email", meeting_notes→"Meeting notes", other→"Other"
  - `stakeholders.comm.frequency.<code>` (6): one_time→"One-time", weekly→"Weekly", monthly→"Monthly", quarterly→"Quarterly", annual→"Annual", as_needed→"As needed"

- [x] **Step 2: Validate**
  ```
  micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation']; ks=['stakeholders.tab_comm','stakeholders.comm.audience.key_players','stakeholders.comm.type.report','stakeholders.comm.frequency.one_time','stakeholders.comm.required']; [print(k, sorted(d[k].keys())==sorted(d['stakeholders.tab_activity'].keys()), repr(d[k]['en'])) for k in ks]"
  ```
  Expect each key present, language set identical to `tab_activity`'s; `git diff --stat` shows only insertions.

- [x] **Step 3: Commit**
  ```bash
  git add sespy/translations/core.json
  git commit -m "i18n: stakeholders.comm.* + tab_comm (9 langs)"
  ```

---

## Task 4: Module — Communication Plan sub-tab

**Files:** Modify `sespy/modules/pims_stakeholders.py`

- [x] **Step 1: Imports + panel** — extend the `from sespy.stakeholders import (...)` block with `COMMUNICATION_AUDIENCES`, `COMMUNICATION_TYPES`, `COMMUNICATION_FREQUENCIES`, `add_communication`, `communication_rows`. Add a plain panel next to `_engagement_panel`:
  ```python
  def _communication_panel() -> ui.Tag:
      """Communication Plan tab — add-form + communications log. Plain (un-decorated)."""
      freq_choices = {
          c: _t(f"stakeholders.comm.frequency.{c}")
          for c in COMMUNICATION_FREQUENCIES
      }
      return ui.div(
          ui.h5(_t("stakeholders.comm.add_heading")),
          ui.layout_columns(
              ui.card(
                  ui.input_select("comm_audience", _t("stakeholders.comm.audience"),
                                  _choices(list(COMMUNICATION_AUDIENCES), "comm.audience", _t)),
                  ui.input_select("comm_type", _t("stakeholders.comm.type"),
                                  _choices(list(COMMUNICATION_TYPES), "comm.type", _t)),
                  ui.input_date("comm_date", _t("stakeholders.comm.date")),
                  ui.input_select("comm_frequency", _t("stakeholders.comm.frequency"),
                                  freq_choices, selected="one_time"),
                  ui.input_text_area("comm_message", _t("stakeholders.comm.message")),
                  ui.input_text("comm_responsible", _t("stakeholders.comm.responsible")),
                  ui.input_action_button("add_communication", _t("stakeholders.comm.add"),
                                         class_="btn-success"),
              ),
              ui.card(
                  ui.h5(_t("stakeholders.comm.log_heading")),
                  ui.output_data_frame("communication_table"),
              ),
              col_widths=[5, 7],
          ),
      )
  ```
  Add the 4th nav panel (after the `tab_activity` panel):
  ```python
  ui.nav_panel(_t("stakeholders.tab_comm"), _communication_panel()),
  ```

- [x] **Step 2: Server logic** — add an accessor near `_engagements()`:
  ```python
      def _communications():
          return project_data.get().communications
  ```
  Add handler + render after the SH3 engagement renders:
  ```python
      @reactive.effect
      @reactive.event(input.add_communication, ignore_init=True)
      def _add_communication():
          audience = input.comm_audience()
          comm_type = input.comm_type()
          if not audience or not comm_type:
              ui.notification_show(tr("stakeholders.comm.required"),
                                   type="warning", duration=3)
              return
          d = input.comm_date()
          fields_ = {
              "audience": audience,
              "comm_type": comm_type,
              "date": d.isoformat() if d else "",
              "frequency": input.comm_frequency(),
              "message": input.comm_message().strip(),
              "responsible": input.comm_responsible().strip(),
          }
          new_list = add_communication(_communications(), fields_,
                                       today=date.today().isoformat())
          project_data.set(project_data.get().replace(communications=new_list))
          event_bus.emit_isa_change()
          ui.update_text_area("comm_message", value="")
          ui.update_text("comm_responsible", value="")

      @output
      @render.data_frame
      def communication_table():
          rows = communication_rows(_communications(), translate=tr)
          stub = [{"audience": tr("stakeholders.comm.empty"), "type": "", "date": "",
                   "frequency": "", "message": "", "responsible": ""}]
          return render.DataGrid(pd.DataFrame(rows or stub), height="320px")
  ```

- [x] **Step 3: Verify**
  ```
  micromamba run -n shiny python -c "from sespy.modules.pims_stakeholders import pims_stakeholders_ui, pims_stakeholders_server; pims_stakeholders_ui('stakeholders'); print('ui ok')"
  micromamba run -n shiny python -m flake8 sespy/modules/pims_stakeholders.py --max-line-length=100
  micromamba run -n shiny python -c "import app; print('app ok')"
  ```
  **SH1 input-preservation guard** — the 10 `sh_*` register inputs must still exist (count → 10):
  `(Select-String -Path sespy\modules\pims_stakeholders.py -Pattern 'sh_(name|type|sector|contact|interests|role|power|interest|attitude|engagement_level)' -AllMatches | ForEach-Object { $_.Matches.Value }) | Sort-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count`
  Then the unit suite: `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` → green.

- [x] **Step 4: Commit**
  ```bash
  git add sespy/modules/pims_stakeholders.py
  git commit -m "feat(stakeholders): Communication Plan sub-tab (form + communications log)"
  ```

---

## Task 5: e2e — communication add + log

**Files:** Modify `tests/test_stakeholders_e2e.py` (extend; sections 1–8 UNCHANGED)

- [x] **Step 1: Develop selectors against the live app** — `micromamba run -n shiny shiny run app.py --port 8000` (background). Probe: nav `#sespy_nav_stakeholders`, switch to the comm tab via `#stakeholders-stakeholder_tabs a[data-value='Communication Plan']`, `_set_select` `comm_audience`=`key_players` + `comm_type`=`report`, click `#stakeholders-add_communication`, confirm "Report" (and/or "Key players") shows in `#stakeholders-communication_table`. Delete the probe.

- [x] **Step 2: Extend the e2e script** — after section 8, add section 9 (mirror SH3's inline-read pattern, NOT `_poll_table_contains`):
  ```python
  # 9. COMMUNICATION — add a communication item; assert it shows in the log
  await page.click(
      "#stakeholders-stakeholder_tabs a[data-value='Communication Plan']"
  )
  await page.wait_for_timeout(800)
  await _set_select(page, "stakeholders-comm_audience", "key_players")
  await _set_select(page, "stakeholders-comm_type", "report")
  await page.click("#stakeholders-add_communication")
  comm_txt = ""
  for _ in range(16):
      comm_txt = await page.inner_text("#stakeholders-communication_table")
      if "Report" in comm_txt and "Key players" in comm_txt:
          break
      await page.wait_for_timeout(500)
  assert "Report" in comm_txt and "Key players" in comm_txt, "communication not in log"
  print("9. communication: item added + shown in log — PASS")
  ```
  (Insert before the screenshot block.)

- [x] **Step 3: Run** — with the app on :8000: `micromamba run -n shiny python tests/test_stakeholders_e2e.py` → exit 0 (re-run once if the section-7 grid img flakes; `run_e2e.py` has retry-once). Stop the server.

- [x] **Step 4: Commit**
  ```bash
  git add tests/test_stakeholders_e2e.py
  git commit -m "test(stakeholders): e2e — communication item add + log"
  ```

---

## Final verification
- [x] `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — green.
- [x] `micromamba run -n shiny python tests/run_e2e.py` — all scripts pass (incl. the extended stakeholders e2e).
- [x] Then invoke **superpowers:finishing-a-development-branch** (merge no-ff into `main`, delete the branch).

## Sequencing notes
- TDD order: data model (1) → pure helpers + `_label` refactor (2) → i18n (3) → module (4) → e2e (5). Branch `feat/pims-stakeholders-sh4` is already cut from `main`.
- The `_label` refactor in Task 2 touches SH3 code; Task 2 Step 4 re-runs the SH3 engagement_rows tests to prove they stay green.
