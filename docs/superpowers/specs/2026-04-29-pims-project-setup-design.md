# PIMS Project Setup Module — Design

Date: 2026-04-29
Status: **Implemented** · merged to `main` 2026-04-30 at commit `0c3d1a5` (15 commits from `feat/pims-project-setup`, fast-forward). One Important post-review fix landed as `25cf45e` (drop redundant `with_modified_now()` in `save_project`, add missing `emit_project_saved`). The "parallel `project_metadata` reactive" architecture this design specified (§2 — chosen over Option A: promote `project_data` to wrap `Project`) was subsequently superseded by the Option A refactor in `af051c1` on the same day, which removed the `project_metadata` reactive and the `event_bus.project_change` channel. PIMS now reads/writes through `project_data.get().metadata` and emits `isa_change`. The §2 design and §3 reactive-flow diagrams are retained as historical context for the architectural reasoning at design time. Spec-vs-ship deltas inline-noted: `_load_form_values` subscribes only to `project_data` (not `isa_change`); `project_status_text` renderer was dropped before ship; the §2 i18n list was extended at implementation time with `pims.modified_at` and `pims.schema_version` to back the three-row `current_status` renderer (shipped count: 28 `pims.*` keys + `nav.pims` + `stepper.setup` = 30 total). **Post-implementation note**: i18n keys added to `core.json` MUST go inside the top-level `"translation"` wrapper object — `Translator._load_one` reads `raw.get("translation", {})`, so keys at the file root are silently invisible. This trap was discovered during PIMS implementation itself (fix commit `0c3d1a5` re-nested 30 keys); SP1/SP3/SP4 authors should be aware.
Source modules in R app:
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_module.R` lines 7-152 (PROJECT SETUP, ~145 LOC)
- `../SESToolbox/MarineSABRES_SES_Shiny/constants.R` lines 528-532 (`DA_SITES`), 681-687 (`SPATIAL_SCALES`)

## 1. Scope

Port the **Project Setup** sub-module of R's PIMS suite into SESPy as a new top-level module. PIMS = "Process & Information Management System"; Project Setup is its first sub-module and the only one with a non-placeholder R implementation worth porting in this round.

**In scope:**
- New module that captures project-level context: name, demonstration area, focal issue, definition statement, temporal scale, spatial scale, system in focus.
- Schema additions to `ProjectMetadata` for the five new fields (DA site already exists).
- Insertion of a new `setup` stage at the front of the workflow stepper.
- Live-update integration with the dashboard brand block when the project name changes.
- Round-trip persistence via the existing project save/load path; templates re-emitted with sensible domain-specific values.
- One e2e test covering the save-and-reload round trip.

**Out of scope (deferred to separate specs):**
- The other four PIMS sub-modules (Stakeholders, Resources & Risks, Data Management, Evaluation). Stakeholders is the obvious next port; the other three are placeholders even in R and will be deferred indefinitely unless the R app fills them in.
- The 840-LOC `pims_stakeholder_module.R` — its own future spec.
- Tests for migration of legacy on-disk project files written before this change (covered by the inbound unknown-key filter, which is itself unit-tested).

**Decisions baked in (from brainstorming):**

| Decision | Rationale |
|---|---|
| Project Setup before Stakeholders | Smallest schema-migration surface; exercises the pattern once on easy fields before applying it to a `list[Stakeholder]` collection later. |
| Drop the 3 R placeholders entirely | They're "Coming soon" stubs in R itself. Adding them as nav items would make SESPy worse. |
| Keep legacy `regional_sea` / `ecosystem_type` fields untouched | Already on `ProjectMetadata`; no UI exposes them; defaulted to `""`. Removing would force a churn migration for no benefit. |
| Bump `PROJECT_SCHEMA_VERSION` 1 → 2 | Signal to older SESPy versions that newer fields exist. New code reads old files via dataclass defaults; old code reading new files needs the unknown-key filter (added defensively in this change). |
| Single module file, no helper module | Module is form-driven (no numerics). Inline what's needed; promote to a helper only if logic grows beyond one screen. |

## 2. Architecture

### New files

- `sespy/modules/pims_project.py` — UI + server (~270–320 LOC). Pattern: `analysis_bot.py` style for state + persistence, with `@render.ui` for the form UI rather than the analysis modules' tabset shape.
- `tests/test_pims_project_e2e.py` — Playwright e2e (~90 LOC).

### Modified files

- `sespy/data_structure.py` — five new fields on `ProjectMetadata`; bump `PROJECT_SCHEMA_VERSION`; add unknown-key filter to `from_dict`.
- `sespy/constants.py` — three new tuples: `DA_SITES`, `SPATIAL_SCALES`, `TEMPORAL_SCALES`. Mirror the R values exactly.
- `sespy/event_bus.py` — add `project_change: reactive.Value[int]` and `emit_project_change()` method, alongside the existing `isa_change` pair. *[HISTORICAL — superseded by `af051c1`; `project_change` was never shipped. See §2 blockquote at the EventBus dataclass.]*
- `app.py` — add `setup` to the workflow stepper stage list (lines 101-108), ordered before `create`; register `pims` in `NAV` (top of list), `NAV_TO_STEP` (`"pims": "setup"`), `PANELS`, and the server-side registration block.
- `sespy/translations/core.json` — add ~22 new keys (see §2 i18n below).
- `sespy/templates/{coastal_tourism,minimal_demo,offshore_wind,small_scale_fisheries}.json` — re-emit with the five new metadata fields populated. One commit per template, or a single "templates: populate PIMS metadata" commit.
- `README.md` — bump module count 14 → 15; add a row to the modules table; bump test count by 1.
- `tests/test_data_structure.py` — extend with round-trip + unknown-key-filter tests for the new fields.

### Schema changes

Add five string fields to `ProjectMetadata` (data_structure.py:80):

```python
focal_issue: str = ""
definition_statement: str = ""
temporal_scale: str = ""    # one of "" or TEMPORAL_SCALES
spatial_scale: str = ""     # one of "" or SPATIAL_SCALES
system_in_focus: str = ""
```

`da_site` is already present (line 83) and stays — Project Setup binds the form's DA-site select to it.

Bump `PROJECT_SCHEMA_VERSION` from `1` to `2` (line 16).

Add an unknown-key filter to `Project.from_dict`:

```python
@classmethod
def from_dict(cls, raw: dict[str, Any]) -> "Project":
    meta_raw = raw.get("metadata", {})
    valid_keys = {f.name for f in fields(ProjectMetadata)}
    meta_filtered = {k: v for k, v in meta_raw.items() if k in valid_keys}
    dropped = set(meta_raw.keys()) - valid_keys
    if dropped:
        logger.warning("Project metadata had unknown keys (dropped): %s", sorted(dropped))
    meta = ProjectMetadata(**meta_filtered)
    isa = _isa_from_dict(raw.get("isa_data", raw))
    return cls(metadata=meta, isa_data=isa)
```

This makes the schema forward-compatible: a SESPy reading a future project file with extra fields will warn but still load, instead of raising `TypeError: ProjectMetadata.__init__() got an unexpected keyword argument`.

### Event bus extension

> **HISTORICAL — superseded by `af051c1` (2026-04-30).** The `project_change` channel described in this section was implemented as designed but removed the same day during the Option A refactor that promoted `project_data: reactive.Value[IsaData]` to `reactive.Value[Project]`. The shipped PIMS module instead emits `event_bus.emit_isa_change()` on save (see `sespy/modules/pims_project.py:174`), and metadata changes flow through `project_data.set(Project(metadata=new_meta, isa_data=current.isa_data))`. The `EventBus` dataclass below is preserved as historical context for the architectural reasoning at design time; it does not match the shipped `sespy/event_bus.py`. Stale prose: §3 listener bullets ("Dashboard brand block", "Autosave", "Recent Projects") and §3's `_handle_save` step 7, plus §3's data-flow diagram arrows referencing `emit_project_change` are all part of the same superseded design.

Mirror the existing `isa_change` pair:

```python
@dataclass(frozen=True)
class EventBus:
    isa_change: reactive.Value[int]
    project_change: reactive.Value[int]   # NEW
    ...

    def emit_project_change(self) -> None:
        with reactive.isolate():
            self.project_change.set(self.project_change.get() + 1)
```

The PIMS module emits `project_change` after Save. Listeners:
- **Dashboard brand block** — re-renders the project name.
- **Autosave** — already listens to `isa_change`; subscribe to both via a combined effect.
- **Recent Projects** — refresh-on-change so the saved name is fresh in the picker.

`emit_project_change` does NOT trigger `emit_isa_change`. Element/connection edits are conceptually different from metadata edits; analysis modules should not see metadata-only edits as "data changed — rerun" events.

### Workflow stepper "setup" stage

`sespy/dashboard.py` defines stage names. Add `"setup"` to the front of the stepper list. The stepper accepts arbitrary stage strings; only the i18n key `stepper.setup` and the `NAV_TO_STEP` mapping need updating.

Final stepper order: `setup → create → edit → analyze → export`.

### Dependencies

None. `dataclasses.fields` (used by the unknown-key filter) is stdlib.

### Persistence

The new fields are part of the same `metadata` block in the project JSON. No new top-level keys, no companion files, no autosave-format change beyond the schema-version bump.

### i18n keys (~27, all under `pims.*` plus one `nav.*` and one `stepper.*`)

```
nav.pims
stepper.setup

pims.title
pims.subtitle
pims.project_information
pims.project_name
pims.project_name_placeholder
pims.demonstration_area
pims.focal_issue
pims.focal_issue_placeholder
pims.definition_statement
pims.definition_statement_placeholder
pims.system_scope
pims.temporal_scale
pims.temporal_daily
pims.temporal_monthly
pims.temporal_yearly
pims.temporal_decadal
pims.spatial_scale
pims.spatial_local
pims.spatial_regional
pims.spatial_national
pims.spatial_international
pims.system_in_focus
pims.system_in_focus_placeholder
pims.save
pims.saved_at
pims.no_save_yet
pims.modified_at
pims.schema_version
```

*Post-impl note: the `pims.modified_at` and `pims.schema_version` keys were added during implementation to support the `current_status` renderer's three-row display (Last saved / Modified at / Schema version) described in §3. Shipped key counts: 28 `pims.*` + `nav.pims` + `stepper.setup` = 30 total in `core.json`. The "~27" figure in the section header above reflects the design-time estimate; the §3 renderer description is what actually drove the shipped count.*

English first; the other 8 languages get the same keys with English placeholder values, mirroring the established pattern. Mirror the R i18n keys (`modules.pims.*`) where they exist; renamed-with-prefix-stripped from R's longer hierarchy.

## 3. Components & Data Flow

### Reactive stores (module-local)

- `pims_save_status: reactive.value[str | None]` — last save timestamp as a friendly string ("2026-04-29 14:32"); `None` when no save yet this session. Drives the right-column status block.

The form fields are bound to `input.*` values from Shiny inputs directly; no separate intermediate store. The persistent state is `project_data.get().metadata`.

### Effects (write to project_data)

- **`_handle_save`** — `@reactive.event(input.save_project_info, ignore_init=True)`.
  1. Read every `input.*` value (project_name, da_site, focal_issue, definition_statement, temporal_scale, spatial_scale, system_in_focus).
  2. Apply name fallback: `name = (input.project_name() or "").strip() or "Untitled Project"`. The field accepts empty input but the saved value never is.
  3. Build a new `ProjectMetadata` by copying `project_data.get().metadata` and overriding the seven fields.
  4. Build a new `Project(metadata=..., isa_data=...)` keeping the existing isa_data unchanged.
  5. Call `project_data.set(new_project.with_modified_now())` (updates `modified_at`).
  6. Set `pims_save_status` to the current local-time HH:MM:SS.
  7. Call `event_bus.emit_project_change()`. *[HISTORICAL — `project_change` was removed in `af051c1`; shipped code calls `event_bus.emit_isa_change()` instead. See §2 blockquote.]*

### Effects (read project_data)

- **`_load_form_values`** — `@reactive.effect`. Subscribes to `project_data` only (covers project loads via `Load` button or `Recent Projects` click; spec originally also said `event_bus.isa_change` but the shipped code at `pims_project.py:196` reads only `project_data`, which is sufficient because all load paths route through `project_data.set()`). Updates each input via `ui.update_text`/`ui.update_select`/`ui.update_text_area` to reflect the loaded metadata. Inside `with reactive.isolate():` wrt the inputs themselves to avoid re-firing on user typing.

### Renderers

- **`@render.ui current_status`** — dl block showing `Last saved`, `Modified at`, `Schema version`. Falls back to "Not saved this session" on first open.
- **`@render.ui project_status_text`** — header with the current project name (lifted from `project_data.get().metadata.name`); updates live as the input changes. *Status: dropped before ship — the shipped module exposes only `current_status` (the save-state status line), not a separate live project-name header. A future PR could add this if a reviewer wants the brand-style header back.*

### Data flow

```
User types in fields    →  input.* (Shiny built-in reactivity)
                                                │
User clicks Save        →  _handle_save  ──────►  project_data.set(...)
                                          │            │
                                          ├────────────► project file (when user clicks Save in project_io)
                                          │
                                          └──► event_bus.emit_project_change()  [HISTORICAL — shipped: emit_isa_change()]
                                                       │
                                          ┌────────────┴────────────┐
                                          ▼                         ▼
                              dashboard brand block       autosave & recent_projects
                              re-renders project_name     refresh listeners
```

Note: Save-in-PIMS does NOT directly write a `.sespy` file. It updates the in-memory project. The user separately uses the global `Save` action in the project IO panel to flush to disk. This matches every other module's pattern.

## 4. Error Handling

### Validation rules

| Condition | Behavior |
|---|---|
| Empty/whitespace `project_name` on Save | `_handle_save` applies a fallback: empty/whitespace becomes `"Untitled Project"`. Matches `ProjectMetadata.new` default. |
| Free-text fields (focal_issue, definition_statement, system_in_focus) | No validation — any string accepted, including empty. |
| Select fields with empty value | Treated as "not set"; saved as empty string. |
| Selects with values not in the canonical lists | Should be impossible from the UI, but `from_dict` accepts them (the schema is `str`, not `Literal[...]`). No validation enforcement on read either; the UI simply won't pre-select them. |

### No fatal paths

The only failure surface is `project_data.set(...)` itself, which doesn't raise in normal operation. No `try/except` is needed in `_handle_save`. Schema-version mismatch on inbound load is handled in `Project.from_dict` via the unknown-key filter — it logs a warning and proceeds.

### Out of scope

- Recovery from corrupt project JSON — handled upstream by `project_io.py`.
- Network/disk errors — neither this module nor the event bus touches I/O.
- Migration of project files written by future SESPy versions back to schema 2 — not a real scenario; readers handle forward compatibility, writers always emit current schema.

## 5. Testing

### Unit tests (extend `tests/test_data_structure.py`)

About 6 new tests:

- **Round-trip with all new fields populated** — `Project → to_json → from_json` preserves focal_issue, definition_statement, temporal_scale, spatial_scale, system_in_focus.
- **Round-trip with new fields empty** — empty strings round-trip as empty strings.
- **Schema version bump** — `PROJECT_SCHEMA_VERSION == 2`; old-version files (`schema_version: 1`) load without error and have empty new fields.
- **Unknown-key filter (forward compatibility)** — a project JSON with `metadata.future_field: "value"` loads with a warning and `future_field` is dropped.
- **Empty project file (no metadata block)** — `Project.from_dict({})` returns a `Project` with default `ProjectMetadata`.
- **Templates load with new fields populated** — load each of the 4 built-in templates and assert all five new fields are non-empty (the seed data is meaningful).

### E2e (`tests/test_pims_project_e2e.py`)

One scenario, ~90 LOC:

- App starts, navigates to PIMS via `#sespy_nav_pims`.
- Asserts default form values match the loaded sample/template.
- Fills the five new form fields.
- Clicks Save.
- Switches to a different module (e.g., Edit Data) and back to PIMS.
- Asserts the form fields persisted (the `_load_form_values` effect re-populates).
- Asserts the `current_status` block shows a non-empty "Last saved" value.

Optional second scenario if time permits: switch language to a non-English option, verify the labels swap correctly. Skip if the page-reload pattern (modules don't update labels live) makes this tedious.

### Coverage targets

- `sespy/data_structure.py` — already has good coverage; new tests bring the new fields under it.
- `sespy/modules/pims_project.py` — covered only by the e2e (form widgets + Shiny inputs are not unit-testable without mocking the entire reactive runtime).

## 6. Architectural conventions to reuse

These are pinned in `sespy_port_context.md` memory and apply directly to PIMS:

- **i18n:** `from ..i18n import t`; call `t("pims.<key>")` directly. UI labels constructed at `@module.ui` time capture the current language; the page-reload pattern for label switching is acceptable.
- **Reactive self-write discipline:** if `_load_form_values` ever needs to read a form input it might also write to, wrap the read in `with reactive.isolate():`. Simplest avoidance: `_load_form_values` only reads `project_data`, never inputs.
- **Action buttons:** `@reactive.event(input.save_project_info, ignore_init=True)` — required since action buttons start at 0, not None.
- **Defensive input reads:** `(input.project_name() or "").strip()` and similar — Shiny inputs return `None` when fields are cleared.
- **Stale-data warnings:** N/A here — Project Setup doesn't compute results that go stale on edits.

## 7. Roll-out plan

1. Branch: `feat/pims-project-setup` (off `main`).
2. Implementation order: schema additions + tests → constants + i18n → event_bus extension → module file → wire-up (app.py + dashboard.py) → template re-emit → e2e → README.
3. Local Playwright run before pushing.
4. Merge to `main` via fast-forward (linear history convention).

## 8. Estimated effort

~5 hours of clock time including reviews:

| Task | Time |
|---|---|
| Schema + unknown-key filter + 6 unit tests | 45 min |
| Constants + i18n batch (R-mining + 9 languages) | 30 min |
| Event_bus extension + listener wiring | 30 min |
| Module skeleton + UI | 1 h |
| Server logic (save, load-form-values) | 45 min |
| Workflow stepper "setup" stage + nav placement | 20 min |
| Template migrations × 4 | 30 min |
| E2e test | 45 min |
| README + memory updates | 20 min |

## 9. Risks / known unknowns

- **Project name in dashboard brand block:** the brand block currently renders a static label. Wiring it to `project_data.get().metadata.name` requires verifying the brand renderer is in fact reactive (it should be — bslib `page_sidebar`'s title accepts a string each render). Worst case: deferred to a follow-up commit if the brand block turns out to be statically baked.
- **DA_SITES list churn:** R version is just 3 sites ("Tuscan Archipelago", "Arctic Northeast Atlantic", "Macaronesia"). If the R app expands this in the future, SESPy's list will drift. Mitigation: leave a comment in `constants.py` pointing at the R source.
- **`pims_save_status` is session-only:** intentional — captures "did the user save in this session?" not "is there a save somewhere on disk?". The persistent timestamp is `metadata.modified_at`, which round-trips with the project. The session indicator helps the user distinguish "I just saved this" from "this is a previously-loaded project".
- **`event_bus.project_change` listener count:** add carefully — every new listener is a place where a missed `reactive.isolate()` could cause a feedback loop. The dashboard brand block in particular is a prime suspect since it renders inside a `@render.ui` that may also update on project loads. *[HISTORICAL — `project_change` was removed in `af051c1`; this risk no longer applies. The reactive-isolate discipline still applies generally to any listener on `isa_change`.]*

## 10. Non-goals

- Refactoring `sespy/data_structure.py` beyond the additions listed.
- Porting any other PIMS sub-module.
- Changing the project JSON top-level structure.
- Plotting library changes.
- Multi-user session-isolation work.
