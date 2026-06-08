# PIMS Stakeholders SH3 — Engagement Activity Log — Design

Date: 2026-06-06 (rev. 3 — status update after implementation)
Status: **Implemented** ✓ (shipped on `main`; engagement activity log sub-tab live).

**rev. 2 changes (from the review):** (a) i18n keys moved to a fresh
`stakeholders.activity.*` namespace + `stakeholders.tab_activity` — the obvious
`stakeholders.engagement.*` namespace is **already taken** by SH1's IAP2
engagement-*level* labels (`…engagement.inform/consult/involve/collaborate/empower`),
so reusing it would overload that namespace; (b) `from_dict` now **upgrades**
`schema_version` to the current value on load (a loaded v3 project must not save back
out claiming v3); (c) the stakeholder dropdown gets a leading blank option, is read
under `reactive.isolate()`, and the add handler validates the FK is a live
stakeholder; (d) `engagement_rows` only translates **known** codes (`Translator.t()`
returns the key itself on a miss, so a raw/unknown code must be passed through
verbatim); (e) guarded date conversion (`d.isoformat() if d else ""`); (f) the
"every writer uses `.replace()`" claim narrowed to *partial* mutators; (g) extra
edge-case tests.

**Sub-project context:** SH3 of the PIMS Stakeholders port. SH1 (the stakeholder
**register** — data + CRUD + persistence, schema v3) and SH2 (the **Power-Interest
(Mendelow) grid** + per-quadrant strategies, a read-only sub-tab) are both on `main`.
SH3 adds the **per-stakeholder engagement-activity log** as a third sub-tab of the
existing Stakeholders panel. R source of truth:
`../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_stakeholder_module.R`, Tab 3
"Engagement Planning" (UI ~151-215; server `add_engagement` ~630-661,
`engagement_table` ~663-668).

**Deferred to later increments (out of scope here, §1.2):** R's Tab 4
"Communication Plan" (`comm_*` / `add_communication` / `communication_table`),
Tab 5 "Analysis & Reports" (the statistics text + the three `downloadButton`s:
Excel report / Power-Interest PNG / summary PDF), and the Tab-2 click-to-inspect
handler (`plot_click` → `clicked_stakeholder`). Each is independently shippable;
SH3 is intentionally just the engagement log — the first child entity hanging off
a stakeholder.

## 1. Goal & scope

### 1.1 In scope
- An `Engagement` dataclass (a child record referencing a `Stakeholder` by id) on
  `Project`, plus persistence (schema bump `PROJECT_SCHEMA_VERSION` 3→4).
- A new **Engagement Planning** sub-tab inside the existing Stakeholders
  `navset_tab`: an "add engagement activity" form + a `render.data_frame` log table.
- Pure, unit-tested list-mutation helpers (`add_engagement`, `remove_engagement`,
  `engagement_rows`) appended to `sespy/stakeholders.py` (no Shiny imports).
- i18n keys (`stakeholders.activity.*` + `stakeholders.tab_activity`, 9 langs).
- Unit + e2e tests.

### 1.2 Out of scope (SH4 / later)
- **Communication Plan** (R Tab 4): a sibling child entity with its own form/table;
  same shape as SH3, deferred to keep the increment tight.
- **Analysis & Reports** (R Tab 5): the statistics summary text and the three
  file **downloads** (Excel / PNG / PDF). `@render.download` has no Playwright
  precedent in this repo and the PNG/PDF builders are non-trivial; a separate
  increment.
- **Click-to-inspect** a plotted grid point (R `plot_click` → `clicked_stakeholder`).
  Shiny-for-Python's `@render.plot` is a **static PNG** (no `plot_click` coords);
  faithfully porting this needs a different rendering path (e.g. plotly or a custom
  click layer). Deferred — unchanged from the SH2 decision.
- Any change to the SH1 `Stakeholder` model, the SH2 grid, or `app.py`. SH3 is
  internal to `pims_stakeholders_ui`/`_server`.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Entity link | `Engagement.stakeholder_id` only — **no denormalized name** | R stored `StakeholderName` in the row (R:642), which goes stale on rename. SESPy resolves the name at render time from the live stakeholder list. Intentional divergence. |
| Vocab storage | Canonical CODE strings for `method` + `status`; rendered via i18n **only when the code is known** | Mirrors SH1's all-codes choice (codes are i18n-stable); R stored translated labels. `Translator.t()` returns the *key* on a miss, so `engagement_rows` falls back to the raw code for unknown values (§4). |
| Helper location | Append to `sespy/stakeholders.py` (not a new module) | Same domain; mirrors SH2 appending grid helpers there. Keeps the stakeholder domain in one pure, Shiny-free file. |
| ID scheme | `next_id([e.id for e in items], "ENG")` → `ENG001`… | Same `utils.next_id` convention (`f"{prefix}{n:03d}"`, verified `utils.py:10,29-37`) as `SH###`; R used a separate `engagement_counter` + prefix — the id-derived counter is simpler and gap-tolerant. SESPy ids are greenfield (no R file interop). |
| Envelope preservation | **Nothing new needed for partial writers** — every *partial* `Project` mutator already routes through `.replace()` (SH1 fix), and `with_modified_now` uses `self.replace(metadata=…)`. Whole-project load/import/template/reset paths `set()` a complete `Project` straight from `from_dict`/a fresh build, so they carry `engagements` (or default `[]`) automatically | Verified 2026-06-06: partial writers in `ai_isa_wizard.py` (`:466,574,580,648,932`), `isa_data_entry.py:175`, `pims_project.py:172`, `pims_stakeholders.py:189,244` all use `.replace()`; whole-project setters (`import_data.py:147`, `recent_projects.py:174`, `templates.py:98`, `project_io.py:200/228/253`) set a full project. Adding `engagements` to `Project` survives all of them; only `to_dict`/`from_dict` need the new key. |
| UI placement | A 3rd `ui.nav_panel` in the **existing** `navset_tab` (`id="stakeholder_tabs"`) | SH2 already restructured the panel into Register \| Power-Interest Grid; SH3 appends Engagement Planning. Register stays first → default-active → SH1/SH2 e2e unaffected. |
| Reactive state + autosave | `project_data.set(current.replace(engagements=new_list))` then `event_bus.emit_isa_change()` | Identical to SH1's save path; autosave (`project_io.py`) is gated on `isa_change`. |
| Empty-state guard | `add_engagement` requires a selected stakeholder **and** a method; else a warning toast, no mutation | Mirrors R's `req(input$eng_stakeholder, input$eng_method)` (R:632) and SH1's name+type validation. |

## 2. Data model (`sespy/data_structure.py`)

```python
@dataclass
class Engagement:
    """A single planned/completed engagement activity for one stakeholder.
    Ported from pims_stakeholder_module.R Tab 3 (add_engagement ~639-650)."""
    id: str                  # "ENG001"…  (next_id(..., "ENG"))
    stakeholder_id: str      # FK -> Stakeholder.id (no denormalized name)
    method: str = ""         # canonical code (§3) or ""
    date: str = ""           # ISO date "YYYY-MM-DD" (planned/completed date)
    objectives: str = ""     # free text
    outcomes: str = ""       # free text
    status: str = "planned"  # canonical code (§3)
    facilitator: str = ""    # free text
    created_at: str = ""     # ISO date, set on add
```
- Add `engagements: list[Engagement] = field(default_factory=list)` to `Project`.
- `PROJECT_SCHEMA_VERSION = 4` (on `ProjectMetadata.schema_version`).
- `to_dict`: add `"engagements": [asdict(e) for e in self.engagements]`.
- `from_dict`: **field-filtered, unknown-key-tolerant**, exactly like the SH1
  `stakeholders` block, **and now upgrades the schema version on load** so an older
  project re-saved after an edit declares the current version (rev. 2 fix):
  ```python
  eng_keys = {f.name for f in fields(Engagement)}
  engagements = [Engagement(**{k: v for k, v in e.items() if k in eng_keys})
                 for e in (raw.get("engagements") or [])]
  meta.schema_version = PROJECT_SCHEMA_VERSION   # upgrade-on-load (no down-convert)
  return cls(metadata=meta, isa_data=isa,
             stakeholders=stakeholders, engagements=engagements)
  ```
  A v3 project (no `engagements` key) and the 4 templates load with `[]`. The
  `meta.schema_version = …` line is set after `meta` is built from the filtered dict;
  it converts a loaded v1/v2/v3 file to v4 in memory (we never write an older shape).
  NOTE: this also fixes a latent pre-SH3 gap (a loaded v2/v3 project previously
  re-saved keeping its old version). A migration test covers it (§8).

### 2.1 Envelope preservation — already handled (partial writers)
No new writer edits. `Project.replace()` (`dataclasses.replace`) and
`with_modified_now()` carry `engagements` automatically once the field exists; every
*partial* mutator already uses `.replace()`. Whole-project load/import/template/reset
paths `project_data.set(...)` a complete `Project` produced by `from_dict` or a fresh
build, so they too carry `engagements` (or the `[]` default). The **only** persistence
edits are `to_dict`/`from_dict` (above, incl. the schema-upgrade line) and the schema
bump. `validate_project_payload` (`persistent_storage.py`) does not read
`schema_version`, so v4 is accepted unchanged.

## 3. Controlled vocabularies — canonical codes (module-level constants)
Stored as the **code**; rendered via i18n labels under the **`stakeholders.activity.*`
namespace** (`stakeholders.activity.method.*`, `stakeholders.activity.status.*`).
**Do NOT use `stakeholders.engagement.*`** — that namespace already holds SH1's IAP2
engagement-*level* labels (`…engagement.inform/consult/involve/collaborate/empower`,
`core.json:3743-3797`) for the `Stakeholder.engagement_level` field; overloading it
is confusing. A leading `""` ("—") option is offered so a field can be left blank
(matching SH1's selects), except `status` which defaults to `planned`.
- **method:** `workshop`, `interview`, `survey`, `focus_group`, `public_meeting`,
  `advisory_committee`, `email_newsletter`, `one_on_one`, `site_visit`, `other`
- **status:** `planned`, `completed`, `cancelled`, `ongoing`

Unknown codes on load are kept as-is and **displayed verbatim** (forward-tolerant) —
see the `engagement_rows` fallback in §4.

## 4. Pure list-mutation helpers (`sespy/stakeholders.py`, no Shiny imports)
```python
def add_engagement(items: list[Engagement], fields_: dict, *, today: str) -> list[Engagement]
    # assign next_id([e.id for e in items], "ENG") + created_at=today; NEW list.
    # INVARIANT: fields_ has only valid Engagement field names, never id/created_at.
def remove_engagement(items: list[Engagement], eid: str) -> list[Engagement]
    # drop id==eid; NEW list.
def engagement_rows(
    engagements: list[Engagement], stakeholders: list[Stakeholder], *, translate
) -> list[dict]
    # Build display rows for the log table: resolve stakeholder_id -> name from the
    # live stakeholder list (unknown/dangling id -> ""), map method/status codes ->
    # labels via `translate` ONLY for codes in the known vocab (_METHOD_CODES /
    # _STATUS_CODES); an unknown code is passed through VERBATIM (Translator.t()
    # returns the key on a miss, so a blind translate would render the full key
    # string). Blank code -> "". Returns [{stakeholder, method, date, objectives,
    # outcomes, status, facilitator}] in input order.
```
`add_engagement`/`remove_engagement` are mechanical (mirror `add_stakeholder`/
`remove_stakeholder`). `engagement_rows` is the one with logic worth unit-testing:
name resolution (incl. dangling FK → `""`), **known-code-only** label mapping with
verbatim fallback for unknown codes, and stable order. The set of known codes is
passed in or imported as module constants so the helper stays Shiny-free. `today` is
injected (no `datetime.now()` inside) to keep these pure. Validation (a stakeholder +
method are present, and the stakeholder id is live) lives in the caller.

## 5. Module — Engagement Planning sub-tab (`sespy/modules/pims_stakeholders.py`)

**UI** — add a 3rd panel to the existing `navset_tab` and a `_engagement_panel()`
plain module-level function (NO `@module.ui` decorator — same rule as
`_register_panel`/`_grid_panel`, so ids get the single `stakeholders` namespace):
```python
ui.navset_tab(
    ui.nav_panel(_t("stakeholders.tab_register"), _register_panel()),
    ui.nav_panel(_t("stakeholders.tab_grid"), _grid_panel()),
    ui.nav_panel(_t("stakeholders.tab_activity"), _engagement_panel()),
    id="stakeholder_tabs",
)
```
`_engagement_panel()` builds:
- A form card: `ui.input_select("eng_stakeholder", …, choices={})` (populated in the
  server), `ui.input_select("eng_method", …)`, `ui.input_date("eng_date")`,
  `ui.input_text_area("eng_objectives")`, `ui.input_text_area("eng_outcomes")`,
  `ui.input_select("eng_status", …, selected="planned")`,
  `ui.input_text("eng_facilitator")`, and an `ui.input_action_button("add_engagement")`.

  **Note — `ui.input_date` is the one new widget type** (not used elsewhere in
  `sespy/modules/`). It is a standard Shiny-for-Python widget that **returns a
  `datetime.date`** (hence `input.eng_date().isoformat()` for the stored string) and
  defaults to today when `value` is omitted. The e2e leaves it at its default (it
  drives only stakeholder + method), so no Playwright date-picker handling is needed.
- A `ui.output_data_frame("engagement_table")` log below.

**Server** — add to `pims_stakeholders_server` (alongside the SH1/SH2 renders):
- **Populate the stakeholder dropdown** — a `@reactive.effect` depending on `_items()`
  that calls `ui.update_select("eng_stakeholder", choices={"": "—", **{s.id: s.name
  for s in _items()}})` (a leading blank option, mirroring R's `c("", …)` at R:162-163,
  so "no stakeholder selected" is a real, default-able state). Read the **current
  selection inside `reactive.isolate()`** (so the effect subscribes only to `_items()`,
  not to `input.eng_stakeholder()` — avoids a re-run loop) and pass `selected=` to keep
  a still-valid selection, else fall back to `""`. This also drops a stale selection
  when the chosen stakeholder is edited away or removed. Mirrors R's
  `updateSelectInput(..., "eng_stakeholder", …)` at R:512.
- **Add handler** (`@reactive.event(input.add_engagement)`): read `sid =
  input.eng_stakeholder()` and `method = input.eng_method()`. Validate: if `sid` is
  blank, `method` is blank, **or `sid not in {s.id for s in _items()}`** (FK no longer
  live) → `ui.notification_show(tr("stakeholders.activity.required"), type="warning",
  duration=3)` and return without mutating. Else build `fields_` (`stakeholder_id=sid`,
  `method`, `date` via the **guarded** `d = input.eng_date(); date=d.isoformat() if d
  else ""`, `objectives`, `outcomes`, `status`, `facilitator`), then
  `project_data.set(project_data.get().replace(engagements=add_engagement(_engagements(),
  fields_, today=date.today().isoformat())))`, `event_bus.emit_isa_change()`, and clear
  the free-text inputs (objectives/outcomes/facilitator) per R:656-658.
- **Log table** (`@render.data_frame`): `render.DataGrid(pd.DataFrame(rows or stub))`
  where `rows = engagement_rows(_engagements(), _items(), translate=tr)`; empty stub
  is one row of `tr("stakeholders.activity.empty")`. (Selection-based removal can be
  added later; R has no per-row delete for engagements, so SH3 omits it to stay
  faithful + small.)
- `_engagements()` — a small accessor: `project_data.get().engagements`.

No `app.py` change; the nav item/panel/server wiring from SH1 already mounts this module.

## 6. i18n (`sespy/translations/core.json`)
Fresh `stakeholders.activity.*` keys + `stakeholders.tab_activity`, **inside the
top-level `"translation"` wrapper**. **Do NOT reuse `stakeholders.engagement.*`** (SH1's
IAP2 engagement-*level* labels, `core.json:3743-3797`) nor R's
`modules.pims.stakeholder.*` keys. Keys needed: `tab_activity` (English value
**"Engagement Planning"** — this exact string becomes the tab's rendered `data-value`,
which the e2e selects on); `activity.heading`, `activity.add_heading`,
`activity.stakeholder`, `activity.method`, `activity.date`, `activity.objectives`,
`activity.outcomes`, `activity.status`, `activity.facilitator`, `activity.add`,
`activity.required`, `activity.empty`, `activity.log_heading`; the 10
`activity.method.<code>` labels and 4 `activity.status.<code>` labels (§3). English
values as placeholders for all 9 languages (per SP4).

## 7. Persistence & migration
- Schema bump 3→4; v3 projects and the 4 templates load with `engagements=[]`, and
  `from_dict` upgrades their `schema_version` to 4 in memory (§2) so a re-save is
  self-consistent.
- Save/Load + Recent Projects round-trip automatically once §2 lands (partial writers
  use `.replace()`; whole-project loaders set a full `from_dict` project;
  `with_modified_now` carries the field). No `project_io.py`, `recent_projects.py`, or
  `persistent_storage.py` change.

## 8. Testing
- **Unit — `tests/test_stakeholders.py`** (append): `Engagement` dataclass round-trip;
  `Project` v4 `to_dict`/`from_dict` round-trip **and a full save-path round-trip via
  `save_project_atomic`/`project_to_bytes`** (proves `with_modified_now` preserves
  engagements alongside stakeholders); v3 dict (no `engagements` key) → `[]`; on-disk
  record with an unknown extra key → tolerated; `add_engagement` assigns `ENG001` +
  `created_at`; `remove_engagement` drops by id; **`engagement_rows`**: resolves
  stakeholder name from the live list, maps method/status codes → labels, preserves
  order, yields `""` for a dangling `stakeholder_id`, and **renders an unknown
  method/status code verbatim** (not the i18n key).
- **Migration test** (rev. 2): load a **v3** dict (with an engagement entry) →
  `from_dict` → assert `metadata.schema_version == 4`; round-trip through
  `project_to_bytes`/`save_project_atomic` and re-load → assert the saved bytes
  declare schema 4 and the engagement survived.
- **Unit — `tests/test_data_structure.py`:** rename `test_schema_version_is_3` →
  `test_schema_version_is_4` and assert `== 4`. (The only other hard-coded `3` is the
  generated artifact `tests/screenshots/_save_test.json`, regenerated by
  `test_quick_actions_e2e.py` and **not** asserted as an exact version — no change
  needed; noted so it isn't mistaken for a fixture.)
- **e2e — `tests/test_stakeholders_e2e.py`** (extend; the CRUD + grid sections stay
  UNCHANGED): add an engagement section — ensure a stakeholder exists (reuse one, or
  add `KEY_NAME`), switch to the Engagement Planning sub-tab via
  `#stakeholders-stakeholder_tabs a[data-value='Engagement Planning']` (the verified
  SH2 `data-value` selector pattern — NOT `:has-text`), drive `eng_stakeholder` (to a
  real stakeholder id) + `eng_method` via the `el.value`+dispatch `_set_select` helper,
  click `#stakeholders-add_engagement`, and assert the method/stakeholder text appears
  in `#stakeholders-engagement_table`. Optionally assert it persists across a nav
  away/back (the in-session `project_data` round-trip).

## 9. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit | `Engagement` dataclass; `Project.engagements`; `to_dict`/`from_dict` (field-filtered + schema upgrade-on-load); schema 3→4 |
| `sespy/stakeholders.py` | edit | append pure `add_engagement`/`remove_engagement`/`engagement_rows` (no Shiny) |
| `sespy/modules/pims_stakeholders.py` | edit | 3rd `nav_panel`; `_engagement_panel()`; dropdown-populate effect (blank option + isolate); add handler (FK validation); `engagement_table` render |
| `sespy/translations/core.json` | edit | `stakeholders.activity.*` + `stakeholders.tab_activity` (inside `"translation"`, 9 langs) |
| `tests/test_stakeholders.py` | edit | Engagement model + helpers + v4 save-path round-trip + migration + unknown-code-fallback unit tests |
| `tests/test_data_structure.py` | edit | `test_schema_version_is_3` → `_is_4` (assert 4) |
| `tests/test_stakeholders_e2e.py` | edit | add engagement add+log e2e section (data-value tab selector) |

No changes to `app.py`, `project_io.py`, `recent_projects.py`, or
`persistent_storage.py`; the SH1 `Stakeholder` model and SH2 grid are untouched.
