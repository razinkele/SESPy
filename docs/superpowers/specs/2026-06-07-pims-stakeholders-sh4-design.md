# PIMS Stakeholders SH4 — Communication Plan — Design

Date: 2026-06-07 (rev. 2 — after deep-review)
Status: **Draft** — design phase, not yet implemented.

**rev. 2 changes (from the review):** (a) the 4→5 schema bump touches **four** existing
assertions, not one — besides `test_data_structure.py::test_schema_version_is_4`, the
SH3 tests `test_from_dict_upgrades_schema_version_on_load`,
`test_save_path_roundtrip_preserves_engagements`, and
`test_migrated_v3_saves_as_schema_4_on_disk` all assert `4` and must move to `5`
(§8); (b) the e2e reads `#stakeholders-communication_table` **inline** (like SH3's
section 8), not via the stakeholder-table-hardcoded `_poll_table_contains` helper.

**Sub-project context:** SH4 of the PIMS Stakeholders port. SH1 (register), SH2
(Power-Interest grid), and SH3 (engagement-activity log) are all on `main`. SH4 adds
the **communication plan** as a fourth sub-tab of the existing Stakeholders panel:
a log of planned/tracked stakeholder communications (audience × type × frequency).
R source of truth: `../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_stakeholder_module.R`,
Tab 4 "Communication Plan" (UI ~217-272; server `add_communication` ~670-696,
`communication_table` ~698-703).

**Structurally a simpler clone of SH3.** A `Communication` is a child record of the
project (like SH3's `Engagement`), BUT — unlike `Engagement` — it does **not**
reference a `Stakeholder` by id: its `audience` is a *category* code
(All stakeholders / Key players / Government / …), not a foreign key. So SH4 needs
**no dropdown-populate effect and no FK validation** — it is SH3 minus those two
pieces.

**Deferred to later increments (out of scope here, §1.2):** R's Tab 5 "Analysis &
Reports" (the statistics summary + Excel/PNG/PDF `downloadButton`s) and the Tab-2
click-to-inspect handler (`plot_click` → `clicked_stakeholder`). Unchanged from
SH3's deferral.

## 1. Goal & scope

### 1.1 In scope
- A `Communication` dataclass (a project-level child record) on `Project`, plus
  persistence (schema bump `PROJECT_SCHEMA_VERSION` 4→5).
- A new **Communication Plan** sub-tab inside the existing Stakeholders
  `navset_tab`: an "add communication item" form + a `render.data_frame` log table.
- Pure, unit-tested helpers (`add_communication`, `remove_communication`,
  `communication_rows`) appended to `sespy/stakeholders.py` (no Shiny imports).
- i18n keys (`stakeholders.comm.*` + `stakeholders.tab_comm`, 9 langs).
- Unit + e2e tests.

### 1.2 Out of scope (SH5 / later)
- **Analysis & Reports** (R Tab 5): statistics text + Excel/PNG/PDF downloads.
  `@render.download` has no Playwright precedent and the builders are non-trivial.
- **Click-to-inspect** a plotted grid point (static-PNG limitation; see SH2/SH3).
- Any change to the SH1 `Stakeholder` model, SH2 grid, or SH3 engagement log, or to
  `app.py`. SH4 is internal to `pims_stakeholders_ui`/`_server`.
- Linking a communication to a specific stakeholder id (R's `specific_stakeholder`
  audience is just a category label, not an FK — SH4 keeps it a plain code).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Entity link | **None** — `audience` is a category code, not a `Stakeholder` FK | Faithful to R (Tab 4 stores `Audience` as a text category, R:679); avoids SH3's dropdown/FK machinery entirely. |
| Field name for "type" | `comm_type` (not bare `type`) | Mirrors SH1's `stakeholder_type` choice — avoid shadowing the `type` builtin; JSON key is `comm_type`, matching the form input id. |
| Vocab storage | Canonical CODE strings for `audience`/`comm_type`/`frequency`; rendered via i18n **only when the code is known** | Same as SH1–SH3; `Translator.t()` returns the key on a miss, so `communication_rows` falls back to the raw code for unknown values (§4). |
| Helper location | Append to `sespy/stakeholders.py` | Same domain; mirrors SH2/SH3. Generalizes the existing `_label` helper (§4) to take a key prefix. |
| ID scheme | `next_id([c.id for c in items], "COMM")` → `COMM001`… | Same `utils.next_id` convention as `SH###`/`ENG###`. |
| Envelope preservation | **Nothing new needed** — partial writers use `.replace()`, whole-project loaders set a full `from_dict` project; `from_dict` already upgrades `schema_version` on load (added in SH3) | Verified in SH3; adding `communications` to `Project` survives all writers. Only `to_dict`/`from_dict` change. |
| UI placement | A 4th `ui.nav_panel` in the existing `navset_tab` (`id="stakeholder_tabs"`) | Register \| Power-Interest Grid \| Engagement Planning \| **Communication Plan**. Register stays first → default-active → SH1–SH3 e2e unaffected. |
| Reactive state + autosave | `project_data.set(current.replace(communications=new_list))` then `event_bus.emit_isa_change()` | Identical to SH1/SH3. |
| Empty-state guard | `add_communication` requires `audience` **and** `comm_type`; else a warning toast, no mutation | Mirrors R's `req(input$comm_audience, input$comm_type)` (R:672). |

## 2. Data model (`sespy/data_structure.py`)

```python
@dataclass
class Communication:
    """A planned/tracked stakeholder communication item.
    Ported from pims_stakeholder_module.R Tab 4 (add_communication ~677-686)."""
    id: str                  # "COMM001"…  (next_id(..., "COMM"))
    audience: str = ""       # canonical code (§3) or ""
    comm_type: str = ""      # canonical code (§3) or ""  (R "Type")
    date: str = ""           # ISO date "YYYY-MM-DD"
    frequency: str = "one_time"  # canonical code (§3)
    message: str = ""        # free text
    responsible: str = ""    # free text
    created_at: str = ""     # ISO date, set on add
```
- Add `communications: list[Communication] = field(default_factory=list)` to `Project`.
- `PROJECT_SCHEMA_VERSION = 5`.
- `to_dict`: add `"communications": [asdict(c) for c in self.communications]`.
- `from_dict`: after the `engagements` block, add the field-filtered, unknown-key-
  tolerant parse (identical pattern); the existing `meta.schema_version =
  PROJECT_SCHEMA_VERSION` upgrade-on-load line already covers v5:
  ```python
  comm_keys = {f.name for f in fields(Communication)}
  communications = [Communication(**{k: v for k, v in c.items() if k in comm_keys})
                    for c in (raw.get("communications") or [])]
  ...
  return cls(metadata=meta, isa_data=isa, stakeholders=stakeholders,
             engagements=engagements, communications=communications)
  ```
  A v4 project (no `communications` key) and the 4 templates load with `[]`.

### 2.1 Envelope preservation — already handled
No new writer edits (verified in SH3). `Project.replace()` and `with_modified_now()`
carry `communications` automatically; whole-project loaders set a full `from_dict`
project. The only persistence edits are `to_dict`/`from_dict` and the schema bump.

## 3. Controlled vocabularies — canonical codes (module-level constants)
Stored as the **code**; rendered via i18n under the **`stakeholders.comm.*`
namespace** (no collision — verified no existing `stakeholders.comm*` keys). A
leading `""` ("—") option is offered for `audience` and `comm_type`; `frequency`
defaults to `one_time` (no blank, matching R:244).
- **audience:** `all_stakeholders`, `key_players`, `government`, `industry`, `ngos`,
  `local_communities`, `scientific_community`, `specific_stakeholder`
- **comm_type:** `report`, `newsletter`, `presentation`, `website_update`,
  `press_release`, `social_media`, `email`, `meeting_notes`, `other`
- **frequency:** `one_time`, `weekly`, `monthly`, `quarterly`, `annual`, `as_needed`

Unknown codes on load are kept as-is and **displayed verbatim** (forward-tolerant) —
see the `communication_rows` fallback in §4.

## 4. Pure helpers (`sespy/stakeholders.py`, no Shiny imports)
```python
def add_communication(items, fields_, *, today) -> list[Communication]
    # next_id([c.id for c in items], "COMM") + created_at=today; NEW list.
def remove_communication(items, cid) -> list[Communication]
    # drop id==cid; NEW list.
def communication_rows(communications, *, translate) -> list[dict]
    # map audience/comm_type/frequency codes -> labels (KNOWN codes only; unknown
    # passed through verbatim). Returns [{audience, type, date, frequency, message,
    # responsible}] in input order. No stakeholder-name resolution (no FK).
```
**Refactor `_label`** (added in SH3) to take a full key **prefix** instead of a
`group` suffix, so both engagement and communication rows can reuse it:
```python
def _label(code, known, translate, prefix):
    if code and code in known:
        return translate(f"{prefix}.{code}")
    return code
```
Update SH3's two call sites accordingly:
`_label(e.method, ENGAGEMENT_METHODS, translate, "stakeholders.activity.method")`
and `_label(e.status, ENGAGEMENT_STATUSES, translate, "stakeholders.activity.status")`.
`communication_rows` then calls e.g.
`_label(c.audience, COMMUNICATION_AUDIENCES, translate, "stakeholders.comm.audience")`.
The existing SH3 `engagement_rows` tests must continue to pass unchanged (they assert
the same full keys, e.g. `stakeholders.activity.method.workshop`).

Constants: `COMMUNICATION_AUDIENCES`, `COMMUNICATION_TYPES`,
`COMMUNICATION_FREQUENCIES` (tuples, §3).

## 5. Module — Communication Plan sub-tab (`sespy/modules/pims_stakeholders.py`)

**UI** — add a 4th panel + a plain `_communication_panel()` (NO `@module.ui`):
```python
ui.nav_panel(_t("stakeholders.tab_comm"), _communication_panel()),
```
`_communication_panel()` builds a form card —
`ui.input_select("comm_audience", …, _choices(list(COMMUNICATION_AUDIENCES), "comm.audience", _t))`,
`ui.input_select("comm_type", …, _choices(list(COMMUNICATION_TYPES), "comm.type", _t))`,
`ui.input_date("comm_date")`, `ui.input_select("comm_frequency", …, freq_choices,
selected="one_time")` (freq_choices precomputed, no blank), `ui.input_text_area(
"comm_message")`, `ui.input_text("comm_responsible")`,
`ui.input_action_button("add_communication", …, class_="btn-success")` — and a
`ui.output_data_frame("communication_table")` log.

**Server** — add (no dropdown effect; `audience` is not an FK):
- `_communications()` accessor: `project_data.get().communications`.
- **Add handler** (`@reactive.event(input.add_communication, ignore_init=True)`):
  read `audience = input.comm_audience()`, `comm_type = input.comm_type()`; if either
  blank → `ui.notification_show(tr("stakeholders.comm.required"), type="warning",
  duration=3)` and return. Else build `fields_` (`audience`, `comm_type`, `date` via
  guarded `d = input.comm_date(); d.isoformat() if d else ""`, `frequency`, `message`,
  `responsible`), then `project_data.set(project_data.get().replace(communications=
  add_communication(_communications(), fields_, today=date.today().isoformat())))`,
  `event_bus.emit_isa_change()`, and clear the free-text inputs (message/responsible).
- **Log table** (`@render.data_frame`): `render.DataGrid(pd.DataFrame(rows or stub))`
  where `rows = communication_rows(_communications(), translate=tr)`; empty stub is one
  row of `tr("stakeholders.comm.empty")`.

No `app.py` change.

## 6. i18n (`sespy/translations/core.json`)
Fresh `stakeholders.comm.*` keys + `stakeholders.tab_comm`, **inside the top-level
`"translation"` wrapper**, 9 langs (English placeholder per SP4). Keys: `tab_comm`
(English value **"Communication Plan"** — becomes the tab's `data-value` for the
e2e); `comm.add_heading`, `comm.audience`, `comm.type`, `comm.date`, `comm.frequency`,
`comm.message`, `comm.responsible`, `comm.add`, `comm.required`, `comm.empty`,
`comm.log_heading`; the 8 `comm.audience.<code>`, 9 `comm.type.<code>`, and 6
`comm.frequency.<code>` labels (§3).

## 7. Persistence & migration
- Schema bump 4→5; v4 projects + the 4 templates load with `communications=[]`, and
  `from_dict`'s existing upgrade-on-load stamps them v5 in memory.
- Save/Load + Recent Projects round-trip automatically. No `project_io.py`,
  `recent_projects.py`, or `persistent_storage.py` change.

## 8. Testing
- **Unit — `tests/test_stakeholders.py`** (append): `Communication` round-trip;
  `Project` v5 `to_dict`/`from_dict` round-trip + a full save-path round-trip via
  `save_project_atomic`/`load_project`; v4 dict (no `communications`) → `[]`; unknown
  extra key tolerated; `add_communication` assigns `COMM001` + `created_at`;
  `remove_communication` drops by id; **`communication_rows`** maps known codes →
  labels, passes unknown codes verbatim, preserves order. **Migration:** raw-v4 →
  `from_dict` → save → inspect raw JSON declares schema 5 and the communication
  survived. Keep the SH3 `engagement_rows` tests green after the `_label` refactor.
- **Unit — `tests/test_data_structure.py`:** rename `test_schema_version_is_4` →
  `test_schema_version_is_5` and assert `== 5`.
- **Unit — update existing SH3 schema assertions (4→5)** — these were added in SH3 and
  track "the current version", so the bump requires editing them (do NOT leave at 4):
  `test_from_dict_upgrades_schema_version_on_load` (assert `== 5`),
  `test_save_path_roundtrip_preserves_engagements` (assert `== 5`), and rename
  `test_migrated_v3_saves_as_schema_4_on_disk` → `…_schema_5_on_disk` (assert raw
  JSON `== 5`). Grep for `schema_version == 4` / `"schema_version"] == 4` to catch all.
- **e2e — `tests/test_stakeholders_e2e.py`** (extend; sections 1–8 UNCHANGED): add a
  section 9 — switch to the Communication Plan sub-tab via
  `#stakeholders-stakeholder_tabs a[data-value='Communication Plan']`, drive
  `comm_audience` + `comm_type` via the `el.value`+dispatch `_set_select` helper, click
  `#stakeholders-add_communication`, and assert the type/audience label appears by
  reading `#stakeholders-communication_table` **inline** in a poll loop (as SH3's
  section 8 does for `engagement_table` — NOT the `_poll_table_contains` helper, which
  is hardcoded to `#stakeholders-stakeholder_table`).

## 9. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/data_structure.py` | edit | `Communication` dataclass; `Project.communications`; `to_dict`/`from_dict`; schema 4→5 |
| `sespy/stakeholders.py` | edit | append `add_communication`/`remove_communication`/`communication_rows` + constants; generalize `_label` (+ update 2 SH3 call sites) |
| `sespy/modules/pims_stakeholders.py` | edit | 4th `nav_panel`; `_communication_panel()`; add handler; `communication_table` render |
| `sespy/translations/core.json` | edit | `stakeholders.comm.*` + `stakeholders.tab_comm` (inside `"translation"`, 9 langs) |
| `tests/test_stakeholders.py` | edit | Communication model + helpers + v5 save-path + migration + unknown-code unit tests |
| `tests/test_data_structure.py` | edit | `test_schema_version_is_4` → `_is_5` (assert 5) |
| `tests/test_stakeholders_e2e.py` | edit | add communication add+log e2e section (data-value tab selector) |

No changes to `app.py`, `project_io.py`, `recent_projects.py`, or
`persistent_storage.py`; the SH1–SH3 features are untouched (apart from the internal
`_label` refactor, which keeps SH3 tests green).
