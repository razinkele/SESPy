# PIMS Stakeholders SH1 — Stakeholder Register (data + CRUD + persistence) — Design

Date: 2026-06-04
Status: **Draft** — design phase, not yet implemented.

**Sub-project context:** SH1 of 2 in the PIMS Stakeholders port (R source:
`modules/pims_stakeholder_module.R`, 908 LOC). SH1 = the stakeholder **register**
(data model + CRUD UI + persistence). SH2 (follow-up) adds the **Power×Interest
(Mendelow) grid** visualization + per-quadrant engagement strategies. SH1 captures
the `power`/`interest`/`attitude`/`engagement_level` fields now, so SH2 only adds the
visualization — no schema change between SH1 and SH2.

## 1. Goal & scope

### 1.1 In scope
- A `Stakeholder` dataclass (10 fields, mirroring the R form) on `Project`.
- Persistence: schema bump `PROJECT_SCHEMA_VERSION` 2→3; round-trip via the existing
  Save/Load + Recent Projects (no changes to those modules).
- A new **Stakeholders** nav item + a self-contained `pims_stakeholders` module: an
  add/edit form + a stakeholders table with per-row Edit/Remove.
- Pure, unit-tested list-mutation helpers (add / update / remove).
- Unit tests + one e2e (add → table → edit → remove → persists across save/load).

### 1.2 Out of scope (SH2 / later)
- The Power×Interest (Mendelow) grid visualization + per-quadrant engagement
  strategies (Manage Closely / Keep Satisfied / Keep Informed / Monitor) — **SH2**.
- Linking stakeholders to SES elements; import/export beyond project save/load;
  PII handling on `contact` (stays plain text).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| UI placement | New top-level **Stakeholders** nav item + new `pims_stakeholders` module | Matches the current flat-nav pattern and R's separate-module structure; keeps SH1 isolated from the shipped `pims_project.py`. |
| Data home | `Project.stakeholders: list[Stakeholder]` | Persists with the project via the existing `Project.to_dict`/`from_dict`; Save/Load/Recent need no change. |
| Schema | bump `PROJECT_SCHEMA_VERSION` 2→3; `from_dict` defaults `stakeholders` to `[]` | Backward-compatible — v2 projects + the 4 templates load with an empty list (same tolerance as the v1→v2 bump). |
| Field set | All 10 R fields, full fidelity | SH1 owns the complete record so SH2 adds only the grid viz (no later schema change). |
| Edit UX | Per-row Edit repopulates the single add/edit form (`editing_id` reactive); Cancel returns to add-mode | Simpler than a modal; one form serves add + edit (mirrors the data-entry pattern). |
| Reactive state | `project_data: reactive.Value[Project]` (existing) | Canonical state; autosave already observes it. No new event channel — analysis modules don't consume stakeholders. |

## 2. Data model (`sespy/data_structure.py`)

New dataclass:
```python
@dataclass
class Stakeholder:
    id: str
    name: str
    stakeholder_type: str = ""   # controlled vocab (see §3) or ""
    sector: str = ""             # controlled vocab or ""
    contact: str = ""            # free text (name / email / phone)
    interests: str = ""          # free text (key interests / concerns)
    role: str = ""               # free text (role in system)
    power: str = ""              # "HIGH" | "MEDIUM" | "LOW" | ""
    interest: str = ""           # "HIGH" | "MEDIUM" | "LOW" | ""
    attitude: str = ""           # controlled vocab or ""
    engagement_level: str = ""   # controlled vocab or ""
```
- Add `stakeholders: list[Stakeholder] = field(default_factory=list)` to `Project`.
- `PROJECT_SCHEMA_VERSION = 3`.
- `Project.to_dict`: include `"stakeholders": [asdict(s) for s in self.stakeholders]`.
- `Project.from_dict`: `stakeholders=[Stakeholder(**s) for s in raw.get("stakeholders", [])]`
  — wrapped to tolerate unknown keys (filter to dataclass fields) so a future SH2/SH3
  field added on disk doesn't break older loaders, matching the existing
  unknown-key-tolerant pattern.
- IDs via `sespy/utils.py::next_id` (gap-filling) with prefix `SH` → `SH1`, `SH2`, …

## 3. Controlled vocabularies (mirror R; module-level constants)
Stored as canonical codes; rendered via i18n labels.
- **type:** Resource users · Industry/business · Government/regulators · NGO/civil society · Scientific/academic · Local communities · Indigenous groups · Other
- **sector:** Fisheries · Aquaculture · Tourism · Shipping · Energy · Conservation · Research · Policy/management · Multiple · Other
- **power / interest:** HIGH · MEDIUM · LOW
- **attitude:** Supportive · Neutral · Resistant · Unknown
- **engagement_level (IAP2):** Inform · Consult · Involve · Collaborate · Empower

Unknown codes encountered on load are kept as-is and displayed (forward-tolerant).

## 4. Pure list-mutation helpers (testable without Shiny)
In a new pure module **`sespy/stakeholders.py`** (no Shiny imports — same pattern as
`sespy/bookmark.py`; imports `Stakeholder` from `data_structure`):
```python
def add_stakeholder(items: list[Stakeholder], fields: dict) -> list[Stakeholder]
    # name required (caller validates); assigns next_id(SH); returns a NEW list
def update_stakeholder(items: list[Stakeholder], sid: str, fields: dict) -> list[Stakeholder]
    # replaces the record with id==sid; returns a NEW list
def remove_stakeholder(items: list[Stakeholder], sid: str) -> list[Stakeholder]
    # drops id==sid; returns a NEW list
```
All return new lists (never mutate in place) so reactive writes are clean.

## 5. Module + nav

`sespy/modules/pims_stakeholders.py`:
- `@module.ui pims_stakeholders_ui` → a `sespy-card` with: an "Add new stakeholder"
  form (the 10 fields, using `ui.input_text` / `ui.input_text_area` /
  `ui.input_select`) + a `@render.ui` stakeholders table (columns: name, type,
  sector, power, interest, attitude, engagement + Edit/Remove buttons per row).
- `@module.server pims_stakeholders_server(input, output, session, *, project_data, event_bus)`:
  - `editing_id: reactive.Value[str | None]` (None = add-mode).
  - Add/Save handler: validate `name` non-empty; in add-mode call `add_stakeholder`,
    in edit-mode call `update_stakeholder`; write
    `project_data.set(Project(metadata=cur.metadata, isa_data=cur.isa_data,
    stakeholders=new_list))`; reset `editing_id` + clear/refresh the form.
  - Per-row Edit: set `editing_id`; repopulate the form (via `ui.update_*`) from the
    selected record. Per-row Remove: `remove_stakeholder` → `project_data.set(...)`.
  - Empty-state: friendly "No stakeholders yet" message in the table area.

`app.py`:
- `NAV`: add `NavItem(id="stakeholders", icon="users", label="Stakeholders", label_key="nav.stakeholders")` after the `pims` item.
- Panel set: add `ui.nav_panel("Stakeholders", pims_stakeholders_ui("stakeholders"), value="stakeholders")`.
- `server`: call `pims_stakeholders_server("stakeholders", project_data=project_data, event_bus=event_bus)`.
- `NAV_TO_STEP`: map `stakeholders` → `setup` (PIMS is the setup phase).

## 6. i18n (`sespy/translations/core.json`)
Add keys under a `stakeholders.*` namespace **inside the top-level `"translation"`
wrapper** (the `raw.get("translation", {})` trap): `nav.stakeholders`, the form field
labels + placeholders, the type/sector/power/interest/attitude/engagement choice
labels, table headers, and the Add/Save/Cancel/Edit/Remove buttons. English values
across all 9 languages (matching SP4's approach; real translations later).

## 7. Persistence & migration
- `project_io` (Save/Load) and `recent_projects` use `Project.to_dict`/`from_dict`, so
  they round-trip stakeholders automatically once §2 lands — **no changes to those
  modules.**
- A v2 project on disk (no `stakeholders` key) loads with `stakeholders=[]`. The 4
  built-in templates (v2) are unaffected. `persistent_storage` validation must accept
  `schema_version` 3 (verify it doesn't hard-pin 2).

## 8. Testing
- **Unit — `tests/test_stakeholders.py`:** `Stakeholder` `asdict`/`from_dict` round-trip;
  `Project` v3 to_dict/from_dict round-trip with stakeholders; a v2 dict (no
  `stakeholders`) → `[]`; an on-disk record with an unknown extra key → tolerated; the
  three pure helpers (add assigns gap-filling `SH` id; update replaces by id; remove
  drops by id; name-required is enforced by the caller path — test the helper contract).
- **e2e — `tests/test_stakeholders_e2e.py`** (auto-discovered by `run_e2e.py`; uses
  `wait_for_selector`/`wait_for_function`, never fixed sleeps): nav to Stakeholders →
  fill the form + Add → the row appears in the table; click Edit → change a field →
  Save → the row updates; click Remove → the row is gone; **persistence** — add a
  stakeholder, trigger Save (download) / reload from the sample, and assert it survives
  a `Project.from_dict(to_dict)` round-trip (DOM or a focused reactive check, per the
  project's e2e conventions).

## 9. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit | `Stakeholder` dataclass; `Project.stakeholders`; schema 2→3; to/from_dict |
| `sespy/stakeholders.py` | new | pure `add`/`update`/`remove` list-mutation helpers (no Shiny) |
| `sespy/modules/pims_stakeholders.py` | new | the `@module.ui`/`@module.server` register UI (imports the helpers) |
| `app.py` | edit | NAV item, nav_panel, server wiring, NAV_TO_STEP mapping |
| `sespy/translations/core.json` | edit | `stakeholders.*` + `nav.stakeholders` keys (inside `"translation"`) |
| `tests/test_stakeholders.py` | new | data-model + helper unit tests |
| `tests/test_stakeholders_e2e.py` | new | CRUD + persistence e2e |

No changes to `project_io.py`, `recent_projects.py`, `persistent_storage.py` (beyond
confirming v3 is accepted), or any analysis module.
