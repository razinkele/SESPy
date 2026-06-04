# PIMS Stakeholders SH1 — Stakeholder Register Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stakeholder register (data model + CRUD UI + persistence) to SESPy, ported from R's `pims_stakeholder_module.R`.

**Architecture:** A `Stakeholder` dataclass on `Project`; a `Project.replace()` helper so every envelope-reconstruction site preserves the new field; pure list-mutation helpers in `sespy/stakeholders.py`; a self-contained `pims_stakeholders` Shiny module (form + `render.data_frame` table with selection-based Edit/Remove) wired into the flat nav. Schema bumps 2→3 (backward-compatible load).

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, pandas (table), pytest, Playwright (e2e). Run everything via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-04-pims-stakeholders-sh1-design.md` (rev. 2).

**Conventions verified against live code (2026-06-04):**
- `data_structure.py`: `Project` is a plain `@dataclass` (metadata + isa_data); `from_dict` already field-filters `ProjectMetadata` (lines 186-198); `with_modified_now` at 208-213 rebuilds `Project(...)`. `from dataclasses import asdict, dataclass, field, fields` already present (line 12).
- Envelope writers to fix: `data_structure.py:213`, `pims_project.py:172`, `isa_data_entry.py:177`, `ai_isa_wizard.py:466/577/583/651/935`. `ai_isa_wizard.py:18` already imports `replace`.
- Table CRUD precedent: `isa_data_entry.py:136-150` (`@output`/`@render.data_frame` → `render.DataGrid(pd.DataFrame(rows or [stub]), selection_mode="row", height=...)`) and `:202-208` (`sel = elements_table.cell_selection(); sel["rows"]` is **row indices**, resolved against the source list).
- Repopulate precedent: `pims_project.py:195-207` (`@reactive.effect` tracking `project_data` only, never inputs).
- `event_bus.emit_isa_change()` exists (`event_bus.py:39`).
- i18n: `sespy/translations/core.json` has top-level `{"languages":[9], "translation": {key: {en,es,fr,de,lt,pt,it,no,el}}}`. 9 languages.
- nav/wiring: `app.py` `NAV` list (74-91), `PANELS` (120-135), `NAV_TO_STEP` (106+), module servers wired as `name_server("id", project_data=…, event_bus=…, translator=T)` (172-196). `setup` is a real STEPPER id (97).
- `utils.next_id(existing_ids, prefix)` → zero-padded `f"{prefix}{n:03d}"` → `SH001`.

---

## Task 1: `Stakeholder` dataclass, `Project.stakeholders`, serialization, schema 3

**Files:**
- Modify: `sespy/data_structure.py` (`PROJECT_SCHEMA_VERSION`, new `Stakeholder`, `Project` field + `to_dict`/`from_dict`)
- Test: `tests/test_stakeholders.py` (new)
- Test: `tests/test_data_structure.py` (update `test_schema_version_is_2`)

- [ ] **Step 1: Write the failing serialization round-trip test**

Create `tests/test_stakeholders.py`:

```python
from dataclasses import fields

from sespy.data_structure import (
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)


def _proj_with(stakeholders):
    return Project(
        metadata=ProjectMetadata.new("T"),
        isa_data=IsaData(),
        stakeholders=stakeholders,
    )


# NOTE: the schema-version assertion lives only in test_data_structure.py
# (Step 4) — it's a global concern, not duplicated here.


def test_stakeholder_defaults():
    s = Stakeholder(id="SH001", name="Port Authority")
    assert s.stakeholder_type == ""
    assert s.power == ""
    assert s.created_at == ""


def test_project_roundtrip_preserves_stakeholders():
    s = Stakeholder(
        id="SH001", name="Port Authority", stakeholder_type="government",
        sector="shipping", contact="port@x.eu", interests="navigation",
        role="regulator", power="HIGH", interest="MEDIUM",
        attitude="neutral", engagement_level="consult", created_at="2026-06-04",
    )
    proj = _proj_with([s])
    back = Project.from_dict(proj.to_dict())
    assert back.stakeholders == [s]


def test_from_dict_missing_key_yields_empty_list():
    raw = {"metadata": {"name": "Legacy v2"}, "isa_data": {"elements": [], "connections": []}}
    assert Project.from_dict(raw).stakeholders == []


def test_from_dict_tolerates_unknown_stakeholder_key():
    raw = {
        "metadata": {"name": "T"},
        "isa_data": {"elements": [], "connections": []},
        "stakeholders": [{"id": "SH001", "name": "X", "future_field": 42}],
    }
    out = Project.from_dict(raw).stakeholders
    assert out == [Stakeholder(id="SH001", name="X")]
```

- [ ] **Step 2: Run it; verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q`
Expected: FAIL — `ImportError: cannot import name 'Stakeholder'`.

- [ ] **Step 3: Implement the data model**

In `sespy/data_structure.py`: bump the constant (line 19):

```python
PROJECT_SCHEMA_VERSION = 3
```

Add the dataclass just above `class Project` (after `ProjectMetadata`):

```python
@dataclass
class Stakeholder:
    """A single PIMS stakeholder. Ported from pims_stakeholder_module.R.

    Controlled-vocabulary fields store canonical CODE strings (see
    sespy/modules/pims_stakeholders.py for the code->label maps), not the
    translated label — codes are i18n-stable. `created_at` mirrors R's
    DateAdded.
    """
    id: str
    name: str
    stakeholder_type: str = ""
    sector: str = ""
    contact: str = ""
    interests: str = ""
    role: str = ""
    power: str = ""            # "HIGH" | "MEDIUM" | "LOW" | ""
    interest: str = ""         # "HIGH" | "MEDIUM" | "LOW" | ""
    attitude: str = ""
    engagement_level: str = ""
    created_at: str = ""
```

Add the field to `Project` (after `isa_data`):

```python
    stakeholders: list["Stakeholder"] = field(default_factory=list)
```

Extend `to_dict` (inside the returned dict, after `"isa_data": {...}`):

```python
            "stakeholders": [asdict(s) for s in self.stakeholders],
```

Extend `from_dict` — replace the final `return` (currently line 198) with:

```python
        sh_keys = {f.name for f in fields(Stakeholder)}
        stakeholders = [
            Stakeholder(**{k: v for k, v in s.items() if k in sh_keys})
            for s in (raw.get("stakeholders") or [])
        ]
        return cls(metadata=meta, isa_data=isa, stakeholders=stakeholders)
```

- [ ] **Step 4: Update the stale schema-version test**

In `tests/test_data_structure.py`, rename/retarget `test_schema_version_is_2`:

```python
def test_schema_version_is_3():
    assert PROJECT_SCHEMA_VERSION == 3
```

Run: `grep -rn "== *2" sespy/ tests/ | grep -i schema` — the ONLY expected match is `tests/test_data_structure.py:14` (the test being retargeted). Fix any other straggler that pins `schema_version == 2`. Then `micromamba run -n shiny python -m pytest tests/ -q -k "schema_version"`.

- [ ] **Step 5: Run tests; verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py tests/test_data_structure.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sespy/data_structure.py tests/test_stakeholders.py tests/test_data_structure.py
git commit -m "feat(data): Stakeholder model + Project.stakeholders, schema 2->3"
```

---

## Task 2: `Project.replace()` + envelope preservation across all 8 writers

**Files:**
- Modify: `sespy/data_structure.py` (add `replace`; fix `with_modified_now`)
- Modify: `sespy/modules/pims_project.py:172`, `sespy/modules/isa_data_entry.py:177`, `sespy/modules/ai_isa_wizard.py:466,577,583,651,935`
- Test: `tests/test_stakeholders.py` (append)

- [ ] **Step 1: Write the failing envelope/save-path tests**

Append to `tests/test_stakeholders.py`. The save-path test uses the REAL
on-disk helpers — verified to exist in `sespy/persistent_storage.py`:
`save_project_atomic(project, path)` (project first; runs `with_modified_now()`
internally at line 93) and `load_project(path)` (which goes through
`validate_project_payload` → `Project.from_dict` at line 81). There is NO
`project_from_bytes`; do not import one.

```python
from sespy.persistent_storage import load_project, save_project_atomic


def test_with_modified_now_preserves_stakeholders():
    s = Stakeholder(id="SH001", name="X")
    proj = _proj_with([s])
    assert proj.with_modified_now().stakeholders == [s]


def test_replace_preserves_other_fields():
    s = Stakeholder(id="SH001", name="X")
    proj = _proj_with([s])
    new_meta = ProjectMetadata.new("Renamed")
    out = proj.replace(metadata=new_meta)
    assert out.metadata.name == "Renamed"
    assert out.stakeholders == [s]
    assert out.isa_data is proj.isa_data


def test_save_path_roundtrip_preserves_stakeholders(tmp_path):
    # Real persistence round-trip: save_project_atomic runs with_modified_now()
    # (the drop-site) and writes on-disk JSON; load_project re-validates and
    # rebuilds via Project.from_dict. Proves stakeholders survive a true save.
    s = Stakeholder(id="SH001", name="Coastal NGO", stakeholder_type="ngo")
    proj = _proj_with([s])
    p = tmp_path / "proj.json"
    save_project_atomic(proj, p)
    back = load_project(p)
    assert back.stakeholders == [s]
```

> The save-path test depends on Task 1's `from_dict` change (it carries
> stakeholders) AND Task 2's `with_modified_now` fix. If it fails on the
> `from_dict` side, Task 1 is incomplete; if on `with_modified_now`, Task 2 is.

- [ ] **Step 2: Run; verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q -k "modified_now or replace or save_path"`
Expected: FAIL — `with_modified_now` drops stakeholders / `replace` AttributeError.

- [ ] **Step 3: Add `Project.replace` and fix `with_modified_now`**

In `sespy/data_structure.py`, add a method on `Project` (needs `import dataclasses` or reuse — `dataclasses.replace` isn't imported yet; add `from dataclasses import replace as _dc_replace` to the existing import line, or `import dataclasses`). Prefer extending the existing import:

Change line 12 to:
```python
from dataclasses import asdict, dataclass, field, fields, replace as _dc_replace
```

Add method to `Project`:
```python
    def replace(self, **changes: Any) -> "Project":
        """Return a copy with `changes` applied, preserving all other fields
        (incl. stakeholders). Use this for every partial Project edit instead
        of `Project(metadata=…, isa_data=…)`, which silently drops new fields."""
        return _dc_replace(self, **changes)
```

Rewrite `with_modified_now` body's final return (line 213):
```python
        return self.replace(metadata=meta)
```

- [ ] **Step 4: Route the 7 sibling writers through `.replace()`**

Edit each site to preserve the full envelope. Exact replacements:

`sespy/modules/pims_project.py:172`:
```python
        project_data.set(current_project.replace(metadata=new_meta))
```

`sespy/modules/isa_data_entry.py:177`:
```python
        project_data.set(current.replace(isa_data=isa))
```

`sespy/modules/ai_isa_wizard.py` — five sites:
- `:466-469` (multi-line clear — the wizard "start fresh" reset):
  ```python
          project_data.set(current.replace(isa_data=IsaData()))
  ```
  DECISION: this **intentionally preserves stakeholders**. Restarting the SES
  wizard clears the ISA element/connection graph, but the stakeholder register
  is project-level data independent of that graph — wiping it on a wizard
  restart would be data loss. `.replace(isa_data=IsaData())` is therefore the
  correct behavior, not merely a mechanical substitution. (If a future "New
  blank project" action is added, that — not this wizard reset — is where
  stakeholders should be cleared.)
- `:577`: `new_proj = current.replace(metadata=new_meta)`
- `:583`: `new_proj = current.replace(metadata=new_meta)`
- `:651`: `new_proj = current.replace(isa_data=new_isa)`
- `:935`: `new_proj = current.replace(isa_data=new_isa)`

Each of these already has a `current = project_data.get()` in scope (verify by reading 5 lines above each). If a site lacks `current`, add it. Leave the `IsaData()` import usage at :468 intact (it's the value passed to `.replace`).

- [ ] **Step 5: Run focused + full suite**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q`
Then: `micromamba run -n shiny python -m pytest tests/ -q`
Expected: PASS (full suite green — the wizard/pims/data-entry tests still pass because `.replace()` is behavior-preserving for the fields they set).

- [ ] **Step 6: Commit**

```bash
git add sespy/data_structure.py sespy/modules/pims_project.py sespy/modules/isa_data_entry.py sespy/modules/ai_isa_wizard.py tests/test_stakeholders.py
git commit -m "fix(data): Project.replace() — preserve envelope (stakeholders) across all 8 writers"
```

---

## Task 3: Pure list-mutation helpers (`sespy/stakeholders.py`)

**Files:**
- Create: `sespy/stakeholders.py`
- Test: `tests/test_stakeholders.py` (append)

- [ ] **Step 1: Write failing helper tests**

Append to `tests/test_stakeholders.py`:

```python
from sespy.stakeholders import add_stakeholder, remove_stakeholder, update_stakeholder


def test_add_assigns_padded_id_and_created_at():
    out = add_stakeholder([], {"name": "A", "stakeholder_type": "ngo"}, today="2026-06-04")
    assert len(out) == 1
    assert out[0].id == "SH001"
    assert out[0].name == "A"
    assert out[0].created_at == "2026-06-04"


def test_add_is_pure_and_increments_id():
    first = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    second = add_stakeholder(first, {"name": "B"}, today="2026-06-05")
    assert [s.id for s in second] == ["SH001", "SH002"]
    assert len(first) == 1  # original list untouched


def test_update_replaces_by_id_preserving_id_and_created_at():
    items = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    out = update_stakeholder(items, "SH001", {"name": "A2", "power": "HIGH"})
    assert out[0].id == "SH001"
    assert out[0].name == "A2"
    assert out[0].power == "HIGH"
    assert out[0].created_at == "2026-06-04"


def test_remove_drops_by_id():
    items = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    assert remove_stakeholder(items, "SH001") == []
```

- [ ] **Step 2: Run; verify fail**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q -k "add or update or remove"`
Expected: FAIL — `ModuleNotFoundError: sespy.stakeholders`.

- [ ] **Step 3: Implement the helpers**

Create `sespy/stakeholders.py`:

```python
"""Pure list-mutation helpers for the stakeholder register.

No Shiny imports — every function takes a list and returns a NEW list, so the
reactive module layer stays a thin wrapper and these stay trivially testable.
The caller injects `today` (keeps these pure / no datetime.now inside) and is
responsible for name+type validation before calling add/update.
"""

from __future__ import annotations

from dataclasses import replace

from sespy.data_structure import Stakeholder
from sespy.utils import next_id


def add_stakeholder(
    items: list[Stakeholder], fields_: dict, *, today: str
) -> list[Stakeholder]:
    # INVARIANT: `fields_` contains only valid Stakeholder field names and
    # NEVER `id` or `created_at` (those are assigned here). The module layer
    # builds it from exactly the form inputs, so this holds.
    sid = next_id([s.id for s in items], "SH")
    return [*items, Stakeholder(id=sid, created_at=today, **fields_)]


def update_stakeholder(
    items: list[Stakeholder], sid: str, fields_: dict
) -> list[Stakeholder]:
    return [replace(s, **fields_) if s.id == sid else s for s in items]


def remove_stakeholder(items: list[Stakeholder], sid: str) -> list[Stakeholder]:
    return [s for s in items if s.id != sid]
```

> `Stakeholder(id=sid, created_at=today, **fields_)` requires `fields_` to contain only valid Stakeholder field names and NOT `id`/`created_at`. The module layer (Task 5) builds `fields_` from exactly the form inputs, so this holds.

- [ ] **Step 4: Run; verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sespy/stakeholders.py tests/test_stakeholders.py
git commit -m "feat(stakeholders): pure add/update/remove helpers"
```

---

## Task 4: i18n keys (`sespy/translations/core.json`)

**Files:**
- Modify: `sespy/translations/core.json`

- [ ] **Step 1: Add keys (no test — verified by app load in Task 6)**

Inside the top-level `"translation"` object, add these keys. Each value is an object with all 9 language codes (`en,es,fr,de,lt,pt,it,no,el`); use the English string as the placeholder value for every language (matches the SP4 precedent — real translations come later). Use clean English labels (do NOT copy R's buggy `Industrybusiness`/`Ngocivil Society`).

Keys to add:
- `nav.stakeholders` → "Stakeholders"
- `stakeholders.title` → "Stakeholder Register"
- `stakeholders.add_heading` → "Add / edit stakeholder"
- `stakeholders.name` → "Name"
- `stakeholders.type` → "Type"
- `stakeholders.sector` → "Sector"
- `stakeholders.contact` → "Contact"
- `stakeholders.interests` → "Interests"
- `stakeholders.role` → "Role"
- `stakeholders.power` → "Power"
- `stakeholders.interest` → "Interest"
- `stakeholders.attitude` → "Attitude"
- `stakeholders.engagement_level` → "Engagement level"
- `stakeholders.save` → "Save stakeholder"
- `stakeholders.cancel` → "Cancel"
- `stakeholders.edit_selected` → "Edit selected"
- `stakeholders.remove_selected` → "Remove selected"
- `stakeholders.name_type_required` → "Name and type are required."
- `stakeholders.select_first` → "Select a stakeholder first."
- `stakeholders.empty` → "No stakeholders yet — add one above."

Also add the controlled-vocabulary label keys (code → label), e.g. `stakeholders.type.government` → "Government", `stakeholders.sector.shipping` → "Shipping & ports", `stakeholders.power.HIGH` → "High", `stakeholders.attitude.neutral` → "Neutral", `stakeholders.engagement.consult` → "Consult", etc. — one per code listed in spec §3.

- [ ] **Step 2: Validate JSON parses + keys present**

Run:
```bash
micromamba run -n shiny python -c "import json;d=json.load(open('sespy/translations/core.json',encoding='utf-8'));t=d['translation'];assert 'nav.stakeholders' in t and len(t['nav.stakeholders'])==9 and 'stakeholders.name_type_required' in t;print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n: stakeholders.* + nav.stakeholders keys (9 langs)"
```

---

## Task 5: `pims_stakeholders` module (UI + server)

**Files:**
- Create: `sespy/modules/pims_stakeholders.py`
- Test: covered by Task 6 (app import) + Task 7 (e2e). Add one server-less import smoke check here.

- [ ] **Step 1: Implement the module**

Create `sespy/modules/pims_stakeholders.py`. Use `ui.input_select` (NOT selectize) for every controlled field so e2e can drive via `page.select_option` with the code value.

```python
"""PIMS Stakeholders — register UI + CRUD server. Port of pims_stakeholder_module.R.

A self-contained Shiny module: an add/edit form on the left, a render.data_frame
table on the right with selection-based Edit/Remove. All envelope writes go
through Project.replace() and emit isa_change so autosave fires.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from sespy.data_structure import Project, Stakeholder
from sespy.event_bus import EventBus
from sespy.i18n import Translator, t as _t
from sespy.stakeholders import add_stakeholder, remove_stakeholder, update_stakeholder

# code -> i18n label-key suffix maps (codes are stored; labels are rendered)
_TYPE_CODES = ["resource_users", "industry", "government", "ngo", "academic",
               "local_community", "indigenous", "other"]
_SECTOR_CODES = ["fisheries", "aquaculture", "tourism", "shipping", "energy",
                 "conservation", "research", "policy", "multiple", "other"]
_LEVEL_CODES = ["HIGH", "MEDIUM", "LOW"]
_ATTITUDE_CODES = ["supportive", "neutral", "resistant", "unknown"]
_ENGAGE_CODES = ["inform", "consult", "involve", "collaborate", "empower"]

_FORM_INPUTS = ["sh_name", "sh_type", "sh_sector", "sh_contact", "sh_interests",
                "sh_role", "sh_power", "sh_interest", "sh_attitude",
                "sh_engagement_level"]


def _choices(codes: list[str], group: str, translate) -> dict[str, str]:
    # "" front option so a field can be left blank; label via i18n key.
    out = {"": "—"}
    for c in codes:
        out[c] = translate(f"stakeholders.{group}.{c}")
    return out


@module.ui
def pims_stakeholders_ui() -> ui.Tag:
    # Static labels resolved via the module-level default translator (`_t`),
    # matching pims_project_ui's pattern.
    return ui.div(
        ui.h3(_t("stakeholders.title")),
        ui.layout_columns(
            ui.card(
                ui.card_header(_t("stakeholders.add_heading")),
                ui.input_text("sh_name", _t("stakeholders.name")),
                ui.input_select("sh_type", _t("stakeholders.type"),
                                _choices(_TYPE_CODES, "type", _t)),
                ui.input_select("sh_sector", _t("stakeholders.sector"),
                                _choices(_SECTOR_CODES, "sector", _t)),
                ui.input_text("sh_contact", _t("stakeholders.contact")),
                ui.input_text_area("sh_interests", _t("stakeholders.interests")),
                ui.input_text_area("sh_role", _t("stakeholders.role")),
                ui.input_select("sh_power", _t("stakeholders.power"),
                                _choices(_LEVEL_CODES, "power", _t)),
                ui.input_select("sh_interest", _t("stakeholders.interest"),
                                _choices(_LEVEL_CODES, "interest", _t)),
                ui.input_select("sh_attitude", _t("stakeholders.attitude"),
                                _choices(_ATTITUDE_CODES, "attitude", _t)),
                ui.input_select("sh_engagement_level", _t("stakeholders.engagement_level"),
                                _choices(_ENGAGE_CODES, "engagement", _t)),
                ui.input_action_button("save_stakeholder", _t("stakeholders.save"),
                                       class_="btn-primary"),
                ui.input_action_button("cancel_edit", _t("stakeholders.cancel")),
            ),
            ui.card(
                ui.card_header(_t("stakeholders.title")),
                ui.output_data_frame("stakeholder_table"),
                ui.div(
                    ui.input_action_button("edit_selected", _t("stakeholders.edit_selected")),
                    ui.input_action_button("remove_selected", _t("stakeholders.remove_selected")),
                ),
            ),
            col_widths=[5, 7],
        ),
        class_="sespy-card",
    )


@module.server
def pims_stakeholders_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    T = translator
    tr = (lambda k: T.t(k)) if T is not None else _t

    editing_id: reactive.Value[str | None] = reactive.value(None)

    def _items() -> list[Stakeholder]:
        return project_data.get().stakeholders

    @output
    @render.data_frame
    def stakeholder_table():
        rows = [
            {"name": s.name, "type": s.stakeholder_type, "sector": s.sector,
             "power": s.power, "interest": s.interest,
             "attitude": s.attitude, "engagement": s.engagement_level}
            for s in _items()
        ]
        stub = [{"name": tr("stakeholders.empty"), "type": "", "sector": "",
                 "power": "", "interest": "", "attitude": "", "engagement": ""}]
        return render.DataGrid(pd.DataFrame(rows or stub),
                               selection_mode="row", height="320px")

    def _form_fields() -> dict:
        return {
            "name": input.sh_name().strip(),
            "stakeholder_type": input.sh_type(),
            "sector": input.sh_sector(),
            "contact": input.sh_contact().strip(),
            "interests": input.sh_interests().strip(),
            "role": input.sh_role().strip(),
            "power": input.sh_power(),
            "interest": input.sh_interest(),
            "attitude": input.sh_attitude(),
            "engagement_level": input.sh_engagement_level(),
        }

    def _clear_form() -> None:
        ui.update_text("sh_name", value="")
        ui.update_select("sh_type", selected="")
        ui.update_select("sh_sector", selected="")
        ui.update_text("sh_contact", value="")
        ui.update_text_area("sh_interests", value="")
        ui.update_text_area("sh_role", value="")
        ui.update_select("sh_power", selected="")
        ui.update_select("sh_interest", selected="")
        ui.update_select("sh_attitude", selected="")
        ui.update_select("sh_engagement_level", selected="")

    @reactive.effect
    @reactive.event(input.save_stakeholder, ignore_init=True)
    def _save():
        f = _form_fields()
        if not f["name"] or not f["stakeholder_type"]:
            ui.notification_show(tr("stakeholders.name_type_required"),
                                 type="warning", duration=3)
            return
        eid = editing_id.get()
        if eid is None:
            new_list = add_stakeholder(_items(), f, today=date.today().isoformat())
        else:
            new_list = update_stakeholder(_items(), eid, f)
        # Reset editing_id BEFORE project_data.set so the _repopulate effect
        # (it subscribes to project_data via _items()) re-runs with editing_id
        # == None and exits early, rather than re-filling the cleared form.
        editing_id.set(None)
        project_data.set(project_data.get().replace(stakeholders=new_list))
        event_bus.emit_isa_change()
        _clear_form()

    @reactive.effect
    @reactive.event(input.edit_selected, ignore_init=True)
    def _edit():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        editing_id.set(items[sel["rows"][0]].id)

    # Repopulate the form ONLY when editing_id changes — never subscribe to the
    # sh_* inputs here (that would clobber typing). Mirrors pims_project.py:195.
    @reactive.effect
    def _repopulate():
        eid = editing_id.get()
        if eid is None:
            return
        match = next((s for s in _items() if s.id == eid), None)
        if match is None:
            return
        ui.update_text("sh_name", value=match.name)
        ui.update_select("sh_type", selected=match.stakeholder_type)
        ui.update_select("sh_sector", selected=match.sector)
        ui.update_text("sh_contact", value=match.contact)
        ui.update_text_area("sh_interests", value=match.interests)
        ui.update_text_area("sh_role", value=match.role)
        ui.update_select("sh_power", selected=match.power)
        ui.update_select("sh_interest", selected=match.interest)
        ui.update_select("sh_attitude", selected=match.attitude)
        ui.update_select("sh_engagement_level", selected=match.engagement_level)

    @reactive.effect
    @reactive.event(input.cancel_edit, ignore_init=True)
    def _cancel():
        editing_id.set(None)
        _clear_form()

    @reactive.effect
    @reactive.event(input.remove_selected, ignore_init=True)
    def _remove():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        sid = items[sel["rows"][0]].id
        project_data.set(project_data.get().replace(
            stakeholders=remove_stakeholder(items, sid)))
        event_bus.emit_isa_change()
        if editing_id.get() == sid:
            editing_id.set(None)
            _clear_form()
```

> Implementer: verify the `output_data_frame`/`render.data_frame`/`render.DataGrid` and `Translator`/`t` import names against `isa_data_entry.py` and `pims_project.py` before finalizing — match whatever those files import. If the repo uses `@output` above `@render.data_frame`, mirror it (it does — `isa_data_entry.py:136`).

- [ ] **Step 2: Import smoke check**

Run: `micromamba run -n shiny python -c "from sespy.modules.pims_stakeholders import pims_stakeholders_ui, pims_stakeholders_server; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/pims_stakeholders.py
git commit -m "feat(stakeholders): register module (form + data_frame CRUD, validation, edit)"
```

---

## Task 6: Wire into the app (`app.py`)

**Files:**
- Modify: `app.py` (import, `NAV`, `PANELS`, `NAV_TO_STEP`, `server`)

- [ ] **Step 1: Add the import** (next to the other module imports, ~line 52):

```python
from sespy.modules.pims_stakeholders import (
    pims_stakeholders_server,
    pims_stakeholders_ui,
)
```

- [ ] **Step 2: Add the nav item** (in `NAV`, immediately after the `pims` item, line 75):

```python
    NavItem(id="stakeholders", icon="users", label="Stakeholders", label_key="nav.stakeholders"),
```

- [ ] **Step 3: Add the panel** (in `PANELS`, after the `pims` nav_panel, line 120):

```python
    ui.nav_panel("Stakeholders", pims_stakeholders_ui("stakeholders"), value="stakeholders"),
```

- [ ] **Step 4: Map nav→step** (in `NAV_TO_STEP`, add):

```python
    "stakeholders": "setup",
```

- [ ] **Step 5: Wire the server** (in `server()`, after the `pims_project_server(...)` block, ~line 177):

```python
    pims_stakeholders_server(
        "stakeholders",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 6: Verify the app imports and the full suite passes**

Run: `micromamba run -n shiny python -c "import app; print('app import ok')"`
Then: `micromamba run -n shiny python -m pytest tests/ -q`
Expected: app imports; suite green.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat(stakeholders): wire Stakeholders nav item, panel, and server"
```

---

## Task 7: End-to-end test (`tests/test_stakeholders_e2e.py`)

**Files:**
- Create: `tests/test_stakeholders_e2e.py` (auto-discovered by `tests/run_e2e.py`)

- [ ] **Step 1: Write the e2e script**

Harness contract (verified against `tests/run_e2e.py` + `tests/test_data_entry_e2e.py`):
the file is a **standalone script** ending in `asyncio.run(main())`; `run_e2e.py`
auto-discovers `tests/test_*_e2e.py`, boots `shiny run` on port 8000, and runs each
as a subprocess (non-zero exit = fail). It must:
- `async with async_playwright() as p: browser = await p.chromium.launch()`, new context/page, `await page.goto("http://127.0.0.1:8000", wait_until="networkidle")`, then `await page.wait_for_timeout(1500)`.
- Nav via `#sespy_nav_<id>` (e.g. `#sespy_nav_stakeholders`, `#sespy_nav_pims`).
- Module inputs via `#<module>-<input>` (e.g. `#stakeholders-sh_name`).
- **Drive `<select>` the repo's proven way** — NOT `page.select_option`. Use the
  `el.value = code; dispatchEvent('change')` pattern from `test_data_entry_e2e.py:35-38`:
  ```python
  await page.evaluate("""(v) => {
    const el = document.getElementById('stakeholders-sh_type');
    if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); }
  }""", "government")
  await page.wait_for_timeout(400)
  ```
- Use `wait_for_timeout` + short polling loops (the repo's idiom — fixed waits are
  acceptable here), and end with a `tests/screenshots/stakeholders.png` + a `print("... assertions pass")`.

Behaviour to assert (each via text presence in `#stakeholders-stakeholder_table`):
1. Click `#sespy_nav_stakeholders`; `wait_for_timeout(1500)`; assert `#stakeholders-sh_name` is present.
2. **Add**: fill `#stakeholders-sh_name` = "Port Authority"; set `sh_type` = `government` via the evaluate/dispatch snippet; click `#stakeholders-save_stakeholder`; poll until the table text contains "Port Authority".
3. **Validation**: clear `#stakeholders-sh_name` (`fill ""`); click Save; assert a `.shiny-notification` toast appears AND the table still shows exactly one data row (no new row).
4. **Edit**: select the row (see selector note); click `#stakeholders-edit_selected`; `wait_for_timeout`; change `#stakeholders-sh_name` = "Port Authority (gov)"; Save; poll until the table text contains "Port Authority (gov)".
5. **Remove**: select the row; click `#stakeholders-remove_selected`; poll until the table text shows the empty-stub label (`stakeholders.empty` English value) and no longer contains the name.
6. **Persistence (in-session)**: add a stakeholder; click `#sespy_nav_pims`; `wait_for_timeout`; click `#sespy_nav_stakeholders`; assert the row text is still present (proves the `project_data` round-trip across nav).

> **HIGH-RISK SELECTOR — row selection.** No existing e2e selects a
> `render.data_frame` row (`test_data_entry_e2e.py` only adds via the form and
> verifies via pyvis node counts; it never clicks a row). Shiny for Python's
> `render.data_frame` renders a custom React grid, NOT a native table — so the
> selection click target is unproven. The implementer MUST develop this selector
> interactively against the running app (`micromamba run -n shiny shiny run app.py`
> + the Playwright MCP `browser_snapshot` to read the live DOM) before finalizing.
> Likely target: click the cell text, e.g. `await page.click("#stakeholders-stakeholder_table td:has-text('Port Authority')")`, then `wait_for_timeout(500)` for `cell_selection()` to propagate. Confirm via a screenshot that the row shows selected before clicking Edit/Remove. Do not assume `tbody tr` — verify the actual rendered markup.

- [ ] **Step 2: Run it locally**

During development, iterate fast against a manually-started server (the script
hardcodes port 8000): in one shell `micromamba run -n shiny shiny run app.py --port 8000`,
then `micromamba run -n shiny python tests/test_stakeholders_e2e.py`.
Final check — the full battery (boots its own server): `micromamba run -n shiny python tests/run_e2e.py`.
Expected: the new stakeholders e2e passes; the runner's discovered-script count is the previous count + 1.

- [ ] **Step 3: Commit**

```bash
git add tests/test_stakeholders_e2e.py
git commit -m "test(stakeholders): e2e — add/validate/edit/remove/persist CRUD"
```

---

## Final verification (after all tasks)

- [ ] `micromamba run -n shiny python -m pytest tests/ -q` — full unit suite green.
- [ ] `micromamba run -n shiny python tests/run_e2e.py` — full e2e battery green.
- [ ] `git log --oneline` shows 7 focused commits.
- [ ] Then invoke **superpowers:finishing-a-development-branch**.

## Self-review (against spec rev.2)

**Spec coverage:** §2 model → Task 1; §2.1 envelope (replace + 8 sites) → Task 2; §3 codes → Task 5 (`_*_CODES`); §4 helpers → Task 3; §5 module/nav → Tasks 5–6; §6 i18n → Task 4; §7 persistence → Task 2 save-path test; §8 tests → Tasks 1–3, 7 + schema-test update (Task 1 Step 4); §9 files → all tasks. Covered.

**Placeholder scan:** every code step has concrete code. After the plan deep-review, the previously-soft spots are now grounded against live code: Task 2's save-path test uses the real `save_project_atomic`/`load_project` (verified to exist; `project_from_bytes` does not and was removed), and Task 7 carries the exact verified harness contract (port 8000, `asyncio.run(main())`, `el.value`+dispatch for selects). The ONE remaining unprovable item — the `render.data_frame` row-selection selector — is explicitly flagged HIGH-RISK with instructions to develop it against the live DOM, because no existing e2e selects a grid row and the markup can only be read at runtime.

**Type consistency:** `Stakeholder` field names identical across Tasks 1/3/5; `Project.replace(**changes)` signature identical in Tasks 2/5; helper names `add_stakeholder`/`update_stakeholder`/`remove_stakeholder` consistent Tasks 3/5; table renderer `stakeholder_table` + `.cell_selection()["rows"]` consistent Tasks 5/7; i18n keys in Task 4 match `tr(...)` calls in Task 5.
