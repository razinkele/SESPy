# PIMS Stakeholders SH1 — Stakeholder Register (data + CRUD + persistence) — Design

Date: 2026-06-04 (rev. 2 — after multi-agent + codebase review)
Status: **Draft** — design phase, not yet implemented.

**Sub-project context:** SH1 of 2 in the PIMS Stakeholders port (R source:
`modules/pims_stakeholder_module.R`, 908 LOC). SH1 = the stakeholder **register**
(data model + CRUD UI + persistence). SH2 (follow-up) adds the **Power×Interest
(Mendelow) grid** + per-quadrant engagement strategies. SH1 captures
`power`/`interest`/`attitude`/`engagement_level` now, so SH2 adds only the
visualization — no schema change between SH1 and SH2.

**rev. 2 changes (from the review):** the central fix is **envelope preservation** —
`Project` is reconstructed in ~8 places that would silently wipe a new `stakeholders`
field; SH1 must route them through a `Project.replace()` helper (§2.1). Also: a 12th
`created_at` field; canonical codes defined for all vocab fields; field-filtered
`from_dict`; name+type validation with a toast; the `render.data_frame` +
cell-selection CRUD pattern (not dynamic per-row buttons); `translator` in the server
signature; emit `isa_change` so autosave fires; round-trip test via the real
save path; the `test_schema_version_is_2` update.

## 1. Goal & scope

### 1.1 In scope
- A `Stakeholder` dataclass (11 data fields + `id`, mirroring R) on `Project`.
- **Envelope preservation** (§2.1): a `Project.replace()` helper + updating every
  site that reconstructs `Project` so stakeholders (and future fields) survive.
- Persistence: schema bump `PROJECT_SCHEMA_VERSION` 2→3; round-trip through the real
  Save path (`save_project_atomic` / `project_to_bytes`) + Recent Projects.
- A new **Stakeholders** nav item + a self-contained `pims_stakeholders` module: an
  add/edit form + a `render.data_frame` table with selection-based Edit/Remove.
- Pure, unit-tested list-mutation helpers (`sespy/stakeholders.py`).
- Unit + e2e tests.

### 1.2 Out of scope (SH2 / later)
- Power×Interest grid + engagement strategies (**SH2**).
- Linking stakeholders to SES elements; import/export beyond project save/load; PII
  handling on `contact`. **No R↔SESPy file interop:** R stored stakeholders as a
  data.frame under `pd$data$pims`, not in the elements/connections JSON SESPy loads —
  SH1's on-disk shape is greenfield; no round-trip with R files is expected.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| UI placement | New **Stakeholders** nav item + new `pims_stakeholders` module | Flat-nav pattern + R's separate module; isolates SH1 from the shipped `pims_project.py`. |
| Envelope edits | A `Project.replace(**changes)` helper; ALL envelope reconstructions go through it (or `dataclasses.replace`) | `Project` is rebuilt in `with_modified_now` + 7 module writers; a bare `Project(metadata=…, isa_data=…)` drops `stakeholders`. Centralizing prevents data loss now and for SH2+ fields. |
| Persistence test | Through `save_project_atomic`/`project_to_bytes`, not just `to_dict`/`from_dict` | `with_modified_now` (in the save path) is exactly where stakeholders were being dropped — the test must exercise it. |
| Vocab storage | Canonical CODE strings for ALL six controlled fields (§3) | Intentional, forward-looking divergence: R stores codes only for power/interest and the *translated label* for type/sector/attitude/engagement. Codes are i18n-stable. |
| CRUD widget | `ui.input_select` (not selectize); `render.data_frame` table; Edit/Remove via `input.<table>_cell_selection()` | Matches R's row-selection delete + the shipped `isa_data_entry` precedent; avoids the selectize `Shiny.setInputValue` e2e trap; gives a clean `page.select_option` driving path. |
| Edit flow | SESPy-only addition (R has Add + row-select delete only): per `editing_id` reactive, repopulate the single form | Reuses the `pims_project.py:195-207` repopulate pattern; one form serves add+edit. |
| Reactive state + autosave | Write `project_data.set(...)` then **`event_bus.emit_isa_change()`** | Autosave (`project_io.py:120-124`) is gated on `isa_change`; without the emit, stakeholder edits aren't autosaved. Mirrors `pims_project.py:174`. No *new* channel. |

## 2. Data model (`sespy/data_structure.py`)

```python
@dataclass
class Stakeholder:
    id: str
    name: str
    stakeholder_type: str = ""   # canonical code (§3) or ""
    sector: str = ""             # canonical code or ""
    contact: str = ""            # free text (name / email / phone)
    interests: str = ""          # free text
    role: str = ""               # free text
    power: str = ""              # "HIGH" | "MEDIUM" | "LOW" | ""
    interest: str = ""           # "HIGH" | "MEDIUM" | "LOW" | ""
    attitude: str = ""           # canonical code or ""
    engagement_level: str = ""   # canonical code or ""
    created_at: str = ""         # ISO date, set on add (mirrors R DateAdded; R:384,466)
```
- Add `stakeholders: list[Stakeholder] = field(default_factory=list)` to `Project`.
- `PROJECT_SCHEMA_VERSION = 3` (lives on `ProjectMetadata.schema_version`, not `Project`).
- `to_dict`: add `"stakeholders": [asdict(s) for s in self.stakeholders]`.
- `from_dict`: **field-filtered, unknown-key-tolerant** (the literal `[Stakeholder(**s)…]`
  would raise on a future SH2 field — only `ProjectMetadata.from_dict`'s field-filter is
  tolerant; `_isa_from_dict` is not the model here):
  ```python
  sh_keys = {f.name for f in fields(Stakeholder)}
  stakeholders = [Stakeholder(**{k: v for k, v in s.items() if k in sh_keys})
                  for s in raw.get("stakeholders", [])]
  return cls(metadata=meta, isa_data=isa, stakeholders=stakeholders)
  ```
  A v2 project (no `stakeholders` key) and the 4 templates load with `[]`.
- IDs via `next_id([s.id for s in items], "SH")` → zero-padded `SH001`, `SH002`
  (`utils.next_id(existing_ids, prefix)` takes ids first and pads to 3 digits).

### 2.1 Envelope preservation (the critical fix)
`Project` is reconstructed in these sites; each currently does
`Project(metadata=…, isa_data=…)` and would drop `stakeholders`:
- `data_structure.py:208-213` `with_modified_now` (in the Save/autosave path).
- `modules/pims_project.py:172` (project-name/metadata save).
- `modules/isa_data_entry.py:177` (element/connection edits).
- `modules/ai_isa_wizard.py:466, 577, 583, 651, 935` (wizard step writes).

Fix: add a helper and route all of them through it:
```python
# data_structure.py
def replace(self, **changes) -> "Project":
    return dataclasses.replace(self, **changes)
```
- `with_modified_now` → `return self.replace(metadata=meta)` (preserves `stakeholders`
  and isa_data automatically).
- The 7 module writers → `current.replace(metadata=new_meta)` /
  `current.replace(isa_data=new_isa)` instead of `Project(metadata=…, isa_data=…)`
  (the wizard already imports `dataclasses.replace`). This makes every partial edit
  field-complete and immune to future field additions.

## 3. Controlled vocabularies — canonical codes (module-level constants)
Stored as the **code** (left); rendered via i18n labels. Storing codes for all six is
an intentional divergence from R (which stores translated labels for type/sector/
attitude/engagement). Codes:
- **stakeholder_type:** `resource_users`, `industry`, `government`, `ngo`, `academic`, `local_community`, `indigenous`, `other`
- **sector:** `fisheries`, `aquaculture`, `tourism`, `shipping`, `energy`, `conservation`, `research`, `policy`, `multiple`, `other`
- **power / interest:** `HIGH`, `MEDIUM`, `LOW`
- **attitude:** `supportive`, `neutral`, `resistant`, `unknown`
- **engagement_level (IAP2):** `inform`, `consult`, `involve`, `collaborate`, `empower`

Unknown codes on load are kept as-is and displayed (forward-tolerant).

## 4. Pure list-mutation helpers (`sespy/stakeholders.py`, no Shiny imports)
```python
def add_stakeholder(items: list[Stakeholder], fields_: dict, *, today: str) -> list[Stakeholder]
    # assign next_id([s.id for s in items], "SH") + created_at=today; return a NEW list
def update_stakeholder(items: list[Stakeholder], sid: str, fields_: dict) -> list[Stakeholder]
    # replace the record with id==sid (preserving id + created_at); NEW list
def remove_stakeholder(items: list[Stakeholder], sid: str) -> list[Stakeholder]
    # drop id==sid; NEW list
```
All return new lists. `today` is injected (caller passes the date) so the helper stays
pure/unit-testable (no `datetime.now()` inside). Name+type validation lives in the
caller (the helper assumes valid input).

## 5. Module + nav (`sespy/modules/pims_stakeholders.py`, `app.py`)

`pims_stakeholders_ui()` (`@module.ui`) → a `sespy-card`:
- An "Add new stakeholder" form: `ui.input_text("sh_name")`, `ui.input_select`
  (`sh_type`, `sh_sector`, `sh_power`, `sh_interest`, `sh_attitude`,
  `sh_engagement_level` — choices = `{code: label}`), `ui.input_text("sh_contact")`,
  `ui.input_text_area("sh_interests")`, `ui.input_text_area("sh_role")`, an
  Add/Save `ui.input_action_button("save_stakeholder")`, and a Cancel
  (`cancel_edit`, shown only in edit-mode).
- A `@render.data_frame` table (`stakeholder_table`) of columns name/type/sector/
  power/interest/attitude/engagement, with **row-selection enabled**, plus
  `edit_selected` / `remove_selected` action buttons that operate on
  `input.stakeholder_table_cell_selection()` (the `isa_data_entry` precedent). Empty
  state: a friendly "No stakeholders yet" message.

`pims_stakeholders_server(input, output, session, *, project_data, event_bus, translator=None)`:
- `editing_id: reactive.Value[str | None] = reactive.value(None)`.
- **Save handler** (`@reactive.event(input.save_stakeholder)`): read the form; if
  `name` or `type` empty → `ui.notification_show(t("stakeholders.name_type_required"),
  type="warning", duration=3)` and return without mutating. Else build `fields_` dict;
  in add-mode `add_stakeholder(..., today=date.today().isoformat())`, in edit-mode
  `update_stakeholder(items, editing_id.get(), fields_)`; then
  `project_data.set(current.replace(stakeholders=new_list))`,
  `event_bus.emit_isa_change()`, reset `editing_id` to None, clear the form.
- **Edit** (`@reactive.event(input.edit_selected)`): set `editing_id` from the selected
  row's id. A separate `@reactive.effect` that depends **only on `editing_id`** (NOT on
  the form inputs — avoids the keystroke-clobber trap) calls `ui.update_text` /
  `ui.update_select` on each `sh_*` input to repopulate, exactly per
  `pims_project.py:195-207`.
- **Remove** (`@reactive.event(input.remove_selected)`):
  `project_data.set(current.replace(stakeholders=remove_stakeholder(items, sid)))` +
  `emit_isa_change()` + reset `editing_id` if it pointed at the removed row.

`app.py`:
- `NAV`: add `NavItem(id="stakeholders", icon="users", label="Stakeholders", label_key="nav.stakeholders")` after `pims`.
- Panels: add `ui.nav_panel("Stakeholders", pims_stakeholders_ui("stakeholders"), value="stakeholders")`.
- `server`: `pims_stakeholders_server("stakeholders", project_data=project_data, event_bus=event_bus, translator=T)`.
- `NAV_TO_STEP`: map `stakeholders` → `setup` (confirm `setup` is a real `STEPPER` id).

## 6. i18n (`sespy/translations/core.json`)
Fresh `stakeholders.*` keys + `nav.stakeholders`, **inside the top-level `"translation"`
wrapper** (the `raw.get("translation", {})` trap). Do NOT reuse R's
`modules.pims.stakeholder.*` keys (their English labels are buggy — `Industrybusiness`,
`Ngocivil Society`) — define clean labels; this is an intentional correction. Provide
an entry for all 9 languages (English values as placeholders, per SP4).

## 7. Persistence & migration
- Save/Load (`project_io`) and `recent_projects` use the Project (de)serialization +
  `with_modified_now` — so once §2 + §2.1 land, they round-trip stakeholders. **The
  earlier "no changes to persistent_storage" claim was wrong**: `with_modified_now`
  must carry stakeholders (§2.1). `validate_project_payload` does **not** read
  `schema_version` (verified — `persistent_storage.py:27-81` only checks isa_data
  structure + id/ref integrity), so v3 is accepted; no validator change needed.
- v2 projects + the 4 templates load with `stakeholders=[]`.

## 8. Testing
- **Unit — `tests/test_stakeholders.py`:** `Stakeholder` round-trip; `Project` v3
  to_dict/from_dict round-trip **and a full save-path round-trip via
  `save_project_atomic`/`project_to_bytes`** (proves `with_modified_now` preserves
  stakeholders); v2 dict (no key) → `[]`; on-disk record with an unknown extra key →
  tolerated (field-filtered); the 3 pure helpers (`add` assigns `SH001` + `created_at`;
  `update` replaces by id preserving id+created_at; `remove` drops by id);
  **`Project.replace`/envelope tests**: `with_modified_now()` and each writer pattern
  preserve a non-empty `stakeholders`. **Update `test_data_structure.py::test_schema_version_is_2`
  → assert `== 3`** (and grep for other `schema_version == 2` fixtures).
- **e2e — `tests/test_stakeholders_e2e.py`** (auto-discovered by `run_e2e.py`; follow
  the repo convention — `wait_for_selector` + a short settle, the runner's retry-once
  covers timing): nav `#sespy_nav_stakeholders` → fill the form (drive selects via
  `page.select_option('#stakeholders-sh_type', '<code>')` with the **code** value) →
  Save → row appears in `#stakeholders-stakeholder_table`; **validation** — Save with
  empty name → assert the warning toast appears and the table did not grow; select row
  + Edit → change a field → Save → row updates; select row + Remove → row gone;
  **persistence** — add a stakeholder, navigate away (`#sespy_nav_pims`) and back, and
  assert the row text is still present (the in-session `project_data` round-trip;
  `@render.download` save has no Playwright precedent, so don't drive the file path).

## 9. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit | `Stakeholder` dataclass; `Project.stakeholders`; `Project.replace()`; fix `with_modified_now`; `to_dict`/`from_dict` (field-filtered); schema 2→3 |
| `sespy/modules/pims_project.py` | edit | route its `Project(...)` write (`:172`) through `.replace()` |
| `sespy/modules/isa_data_entry.py` | edit | route its `Project(...)` write (`:177`) through `.replace()` |
| `sespy/modules/ai_isa_wizard.py` | edit | route its 5 `Project(...)` writes (`:466,577,583,651,935`) through `.replace()` |
| `sespy/stakeholders.py` | new | pure `add`/`update`/`remove` helpers (no Shiny) |
| `sespy/modules/pims_stakeholders.py` | new | `@module.ui`/`@module.server` register UI |
| `app.py` | edit | NAV item, nav_panel, server wiring (`translator=T`), `NAV_TO_STEP` |
| `sespy/translations/core.json` | edit | clean `stakeholders.*` + `nav.stakeholders` keys (inside `"translation"`) |
| `tests/test_stakeholders.py` | new | data-model + helper + envelope/save-path unit tests |
| `tests/test_data_structure.py` | edit | `test_schema_version_is_2` → assert 3 (+ any sibling fixtures) |
| `tests/test_stakeholders_e2e.py` | new | CRUD + validation + persistence e2e |

No changes to `project_io.py`, `recent_projects.py`, or `persistent_storage.py` (v3
accepted as-is); analysis modules untouched.
