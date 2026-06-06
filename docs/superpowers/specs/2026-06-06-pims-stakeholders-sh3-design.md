# PIMS Stakeholders SH3 — Engagement Activity Log — Design

Date: 2026-06-06
Status: **Draft** — design phase, not yet implemented.

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
- i18n keys (`stakeholders.engagement.*` + `stakeholders.tab_engagement`, 9 langs).
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
| Vocab storage | Canonical CODE strings for `method` + `status`; rendered via i18n | Mirrors SH1's all-codes choice (codes are i18n-stable); R stored translated labels. |
| Helper location | Append to `sespy/stakeholders.py` (not a new module) | Same domain; mirrors SH2 appending grid helpers there. Keeps the stakeholder domain in one pure, Shiny-free file. |
| ID scheme | `next_id([e.id for e in items], "ENG")` → `ENG001`… | Same `utils.next_id` convention as `SH###`; R used a separate `engagement_counter` + `ENG-` prefix — the id-derived counter is simpler and gap-tolerant. |
| Envelope preservation | **Nothing new needed** — every `Project` writer already routes through `.replace()` (SH1 fix), and `with_modified_now` uses `self.replace(metadata=…)` | Verified 2026-06-06: all writers in `ai_isa_wizard.py`, `isa_data_entry.py`, `pims_project.py`, `pims_stakeholders.py` use `.replace()`. Adding `engagements` to `Project` makes it survive automatically; only `to_dict`/`from_dict` need the new key. |
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
  `stakeholders` block:
  ```python
  eng_keys = {f.name for f in fields(Engagement)}
  engagements = [Engagement(**{k: v for k, v in e.items() if k in eng_keys})
                 for e in (raw.get("engagements") or [])]
  return cls(metadata=meta, isa_data=isa,
             stakeholders=stakeholders, engagements=engagements)
  ```
  A v3 project (no `engagements` key) and the 4 templates load with `[]`.

### 2.1 Envelope preservation — already handled
No new writer edits. `Project.replace()` (`dataclasses.replace`) and
`with_modified_now()` carry `engagements` automatically once the field exists. The
**only** persistence edits are `to_dict`/`from_dict` (above) and the schema bump.
`validate_project_payload` (`persistent_storage.py`) does not read `schema_version`,
so v4 is accepted unchanged (verified for v3 in SH1).

## 3. Controlled vocabularies — canonical codes (module-level constants)
Stored as the **code**; rendered via i18n labels (`stakeholders.engagement.method.*`,
`stakeholders.engagement.status.*`). A leading `""` ("—") option is offered so a
field can be left blank (matching SH1's selects), except `status` which defaults to
`planned`.
- **method:** `workshop`, `interview`, `survey`, `focus_group`, `public_meeting`,
  `advisory_committee`, `email_newsletter`, `one_on_one`, `site_visit`, `other`
- **status:** `planned`, `completed`, `cancelled`, `ongoing`

Unknown codes on load are kept as-is and displayed (forward-tolerant).

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
    # live stakeholder list (unknown id -> "" ), map method/status codes -> labels via
    # `translate`. Returns [{stakeholder, method, date, objectives, outcomes,
    # status, facilitator}] in input order.
```
`add_engagement`/`remove_engagement` are mechanical (mirror `add_stakeholder`/
`remove_stakeholder`). `engagement_rows` is the one with logic worth unit-testing:
name resolution + code→label mapping + stable order. `today` is injected (no
`datetime.now()` inside) to keep these pure. Validation (a stakeholder + method are
present) lives in the caller.

## 5. Module — Engagement Planning sub-tab (`sespy/modules/pims_stakeholders.py`)

**UI** — add a 3rd panel to the existing `navset_tab` and a `_engagement_panel()`
plain module-level function (NO `@module.ui` decorator — same rule as
`_register_panel`/`_grid_panel`, so ids get the single `stakeholders` namespace):
```python
ui.navset_tab(
    ui.nav_panel(_t("stakeholders.tab_register"), _register_panel()),
    ui.nav_panel(_t("stakeholders.tab_grid"), _grid_panel()),
    ui.nav_panel(_t("stakeholders.tab_engagement"), _engagement_panel()),
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
  that calls `ui.update_select("eng_stakeholder", choices={s.id: s.name for s in _items()})`
  so newly-added stakeholders appear as engagement targets (mirrors R's
  `updateSelectInput(..., "eng_stakeholder", …)` at R:512).
- **Add handler** (`@reactive.event(input.add_engagement)`): if no `eng_stakeholder`
  or no `eng_method` → `ui.notification_show(tr("stakeholders.engagement.required"),
  type="warning", duration=3)` and return. Else build `fields_`
  (`stakeholder_id`, `method`, `date` as `input.eng_date().isoformat()`, `objectives`,
  `outcomes`, `status`, `facilitator`), then
  `project_data.set(project_data.get().replace(engagements=add_engagement(_engagements(),
  fields_, today=date.today().isoformat())))`, `event_bus.emit_isa_change()`, and clear
  the free-text inputs (objectives/outcomes/facilitator) per R:656-658.
- **Log table** (`@render.data_frame`): `render.DataGrid(pd.DataFrame(rows or stub))`
  where `rows = engagement_rows(_engagements(), _items(), translate=tr)`; empty stub
  is one row of `tr("stakeholders.engagement.empty")`. (Selection-based removal can be
  added later; R has no per-row delete for engagements, so SH3 omits it to stay
  faithful + small.)
- `_engagements()` — a small accessor: `project_data.get().engagements`.

No `app.py` change; the nav item/panel/server wiring from SH1 already mounts this module.

## 6. i18n (`sespy/translations/core.json`)
Fresh `stakeholders.engagement.*` keys + `stakeholders.tab_engagement`, **inside the
top-level `"translation"` wrapper**. Do NOT reuse R's `modules.pims.stakeholder.*`
keys. Keys needed: `tab_engagement`; `engagement.heading`, `engagement.add_heading`,
`engagement.stakeholder`, `engagement.method`, `engagement.date`,
`engagement.objectives`, `engagement.outcomes`, `engagement.status`,
`engagement.facilitator`, `engagement.add`, `engagement.required`,
`engagement.empty`, `engagement.log_heading`; the 10 `engagement.method.<code>`
labels and 4 `engagement.status.<code>` labels (§3). English values as placeholders
for all 9 languages (per SP4).

## 7. Persistence & migration
- Schema bump 3→4; v3 projects and the 4 templates load with `engagements=[]`.
- Save/Load + Recent Projects round-trip automatically once §2 lands (writers use
  `.replace()`; `with_modified_now` carries the field). No `project_io.py`,
  `recent_projects.py`, or `persistent_storage.py` change.

## 8. Testing
- **Unit — `tests/test_stakeholders.py`** (append): `Engagement` dataclass round-trip;
  `Project` v4 `to_dict`/`from_dict` round-trip **and a full save-path round-trip via
  `save_project_atomic`/`project_to_bytes`** (proves `with_modified_now` preserves
  engagements alongside stakeholders); v3 dict (no `engagements` key) → `[]`; on-disk
  record with an unknown extra key → tolerated; `add_engagement` assigns `ENG001` +
  `created_at`; `remove_engagement` drops by id; **`engagement_rows`**: resolves
  stakeholder name from the live list, maps method/status codes → labels, preserves
  order, and yields `""` for a dangling `stakeholder_id`.
- **Unit — `tests/test_data_structure.py`:** rename `test_schema_version_is_3` →
  `test_schema_version_is_4` and assert `== 4` (grep confirms it is the only
  `schema_version == 3` fixture).
- **e2e — `tests/test_stakeholders_e2e.py`** (extend; the CRUD + grid sections stay
  UNCHANGED): add an engagement section — ensure a stakeholder exists (reuse one, or
  add `KEY_NAME`), switch to the Engagement Planning sub-tab via
  `#stakeholders-stakeholder_tabs a[data-value='Engagement Planning']` (the verified
  SH2 `data-value` selector pattern — NOT `:has-text`), drive `eng_stakeholder` +
  `eng_method` via the `el.value`+dispatch `_set_select` helper, click
  `#stakeholders-add_engagement`, and assert the method/stakeholder text appears in
  `#stakeholders-engagement_table`. Optionally assert it persists across a nav
  away/back (the in-session `project_data` round-trip).

## 9. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit | `Engagement` dataclass; `Project.engagements`; `to_dict`/`from_dict` (field-filtered); schema 3→4 |
| `sespy/stakeholders.py` | edit | append pure `add_engagement`/`remove_engagement`/`engagement_rows` (no Shiny) |
| `sespy/modules/pims_stakeholders.py` | edit | 3rd `nav_panel`; `_engagement_panel()`; dropdown-populate effect; add handler; `engagement_table` render |
| `sespy/translations/core.json` | edit | `stakeholders.engagement.*` + `stakeholders.tab_engagement` (inside `"translation"`, 9 langs) |
| `tests/test_stakeholders.py` | edit | Engagement model + helpers + v4 save-path round-trip unit tests |
| `tests/test_data_structure.py` | edit | `test_schema_version_is_3` → `_is_4` (assert 4) |
| `tests/test_stakeholders_e2e.py` | edit | add engagement add+log e2e section (data-value tab selector) |

No changes to `app.py`, `project_io.py`, `recent_projects.py`, or
`persistent_storage.py`; the SH1 `Stakeholder` model and SH2 grid are untouched.
