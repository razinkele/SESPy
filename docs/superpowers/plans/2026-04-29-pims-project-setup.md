# PIMS Project Setup Implementation Plan

> **Status: Implemented** · 14 plan tasks shipped on `feat/pims-project-setup`, fast-forwarded to `main` 2026-04-30 (head `0c3d1a5`). Two post-merge fixes landed as `25cf45e` (project_io cleanup). The Task 6 plumbing (parallel `project_metadata` reactive) was **subsequently removed** in the Option-A refactor commit `af051c1` later the same day — `project_data` is now `reactive.Value[Project]`, the parallel reactive is gone, and PIMS reads/writes `project_data.get().metadata` directly. Task 6 in this plan is retained as historical context for what was actually built; the `event_bus.project_change` channel from Task 5 was also removed by the refactor.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the PROJECT SETUP sub-module of R's PIMS suite into SESPy as module #15 — a form-driven view that captures project-level context (DA site, focal issue, definition statement, temporal/spatial scale, system in focus) and persists it via the existing project save/load path.

**Architecture:** Adds 5 string fields to `ProjectMetadata`, a forward-compatible unknown-key filter on `Project.from_dict`, and an `event_bus.project_change` channel. Introduces a parallel `project_metadata: reactive.Value[ProjectMetadata]` reactive that lives alongside the existing `project_data: reactive.Value[IsaData]` — PIMS reads/writes only `project_metadata`; analysis modules continue to ignore metadata. Save/load/template/recent paths sync both reactives. Single new module file (`sespy/modules/pims_project.py`) with a two-column form UI; new `setup` stage at the front of the workflow stepper. No new dependencies.

**Tech Stack:** Shiny for Python, dataclasses, json, Playwright (e2e). Existing micromamba env `shiny`.

**Spec:** [`docs/superpowers/specs/2026-04-29-pims-project-setup-design.md`](../specs/2026-04-29-pims-project-setup-design.md) (committed at `c19f06c`).

**Notes on spec deviations discovered during plan-writing:**

1. The spec's §2 said the stepper stage list lives in `sespy/dashboard.py` and showed an imagined order (`setup → create → edit → analyze → export`). The actual stage list lives in `app.py` (`STEPPER` constant) with stages `start/create/visualize/analyze/report`. The plan inserts `setup` as a new stage at the front, before `start`, leaving the other four untouched.

2. The spec assumed `project_data: reactive.Value[Project]` (the full envelope with `.metadata`). Actual codebase has `project_data: reactive.Value[IsaData]` — metadata is discarded between load and save (synthesized fresh in `Project.from_isa(project_data.get())` at save time). Rather than refactor every module to wrap `Project` (Option A: ~3-4h of additional refactor across 14 modules), the plan introduces a parallel `project_metadata: reactive.Value[ProjectMetadata]` reactive (Option B). PIMS is the only module that uses it; `project_io`, `templates`, and `recent_projects` are minimally extended to keep both reactives in sync. Task 6 below is the dedicated plumbing task.

---

## Task 0: Verify environment and branch

- [ ] **Step 1: Confirm working tree is clean and on `main`**

```bash
git status --short
git branch --show-current
```
Expected: no output from `git status --short`; branch is `main`.

- [ ] **Step 2: Cut the feature branch**

```bash
git checkout -b feat/pims-project-setup
```
Expected: `Switched to a new branch 'feat/pims-project-setup'`.

- [ ] **Step 3: Confirm the spec exists and the BOT plan is the structural reference**

```bash
ls docs/superpowers/specs/2026-04-29-pims-project-setup-design.md
ls docs/superpowers/plans/2026-04-28-analysis-bot.md
```
Expected: both paths print without "No such file" errors.

- [ ] **Step 4: Verify the test suite is green at start**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py
```
Expected: `103 passed` (or higher — count drifts as tests are added).

- [ ] **Step 5: Create the `.tmp/wait_port.py` helper used in Tasks 8 and 13**

Background-started Shiny servers take a moment to bind their port; this helper polls until the port responds so the smoke-test step can proceed without a hard-coded sleep.

```bash
mkdir -p .tmp
```

Write `.tmp/wait_port.py` with this content (use the Write tool, since heredocs into Python through bash on Windows are fragile):

```python
import urllib.request, time, sys

for i in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000", timeout=1).read(1)
        print(f"ready after {i*0.5:.1f}s")
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
print("TIMEOUT")
sys.exit(1)
```

`.tmp/` is gitignored, so this helper does not need to be committed. It only exists for the duration of plan execution.

---

## Task 1: Schema additions to ProjectMetadata + unit tests

**Files:**
- Create: `tests/test_data_structure.py`
- Modify: `sespy/data_structure.py:16, 80-94`

Add the five new fields to `ProjectMetadata`, bump `PROJECT_SCHEMA_VERSION`, write unit tests covering round-trip behavior.

- [ ] **Step 1: Create `tests/test_data_structure.py` with three failing tests**

```python
"""Unit tests for sespy.data_structure — Project / ProjectMetadata schema."""
from __future__ import annotations

import json

from sespy.data_structure import (
    PROJECT_SCHEMA_VERSION,
    Project,
    ProjectMetadata,
    empty,
)


def test_schema_version_is_2():
    assert PROJECT_SCHEMA_VERSION == 2


def test_metadata_has_pims_fields_with_empty_defaults():
    meta = ProjectMetadata()
    assert meta.focal_issue == ""
    assert meta.definition_statement == ""
    assert meta.temporal_scale == ""
    assert meta.spatial_scale == ""
    assert meta.system_in_focus == ""


def test_round_trip_preserves_pims_fields():
    meta = ProjectMetadata(
        name="Test",
        da_site="Macaronesia",
        focal_issue="Plastic pollution in coastal habitats",
        definition_statement="A 5-year monitoring programme across three islands.",
        temporal_scale="Yearly",
        spatial_scale="Regional",
        system_in_focus="Intertidal zone",
    )
    project = Project(metadata=meta, isa_data=empty())
    payload = json.loads(project.to_json())
    restored = Project.from_dict(payload)
    assert restored.metadata.focal_issue == meta.focal_issue
    assert restored.metadata.definition_statement == meta.definition_statement
    assert restored.metadata.temporal_scale == meta.temporal_scale
    assert restored.metadata.spatial_scale == meta.spatial_scale
    assert restored.metadata.system_in_focus == meta.system_in_focus
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: 3 failures with `AssertionError` on `PROJECT_SCHEMA_VERSION == 2` (currently 1) and `AttributeError` on the new fields.

- [ ] **Step 3: Bump `PROJECT_SCHEMA_VERSION` and add the five fields**

In `sespy/data_structure.py`, change line 16:

```python
PROJECT_SCHEMA_VERSION = 2
```

Replace the `ProjectMetadata` dataclass body (lines 80-93) with:

```python
@dataclass
class ProjectMetadata:
    name: str = "Untitled Project"
    description: str = ""
    da_site: str = ""
    regional_sea: str = ""
    ecosystem_type: str = ""
    # PIMS Project Setup fields (added with schema v2).
    focal_issue: str = ""
    definition_statement: str = ""
    temporal_scale: str = ""
    spatial_scale: str = ""
    system_in_focus: str = ""
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = PROJECT_SCHEMA_VERSION

    @staticmethod
    def new(name: str = "Untitled Project") -> "ProjectMetadata":
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return ProjectMetadata(name=name, created_at=now, modified_at=now)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: `3 passed`.

- [ ] **Step 5: Run the broader unit suite to confirm no regressions**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py
```
Expected: same pass count as Task 0 step 4 plus the 3 new tests.

- [ ] **Step 6: Commit**

```bash
git add sespy/data_structure.py tests/test_data_structure.py
git commit -m "feat(schema): add 5 PIMS metadata fields, bump schema_version to 2"
```

---

## Task 2: Forward-compatible unknown-key filter

**Files:**
- Modify: `sespy/data_structure.py` — extend `Project.from_dict` and add `import` for `dataclasses.fields` and a logger.
- Modify: `tests/test_data_structure.py` — append two more tests.

Make the loader silently drop unknown metadata keys with a warning, so that future SESPy versions writing extra fields don't break older readers.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_data_structure.py`:

```python
def test_from_dict_drops_unknown_metadata_keys(caplog):
    payload = {
        "metadata": {
            "name": "Probe",
            "future_field": "hello",
            "another_unknown": 42,
        },
        "isa_data": {"elements": [], "connections": []},
    }
    import logging
    with caplog.at_level(logging.WARNING):
        project = Project.from_dict(payload)
    assert project.metadata.name == "Probe"
    assert not hasattr(project.metadata, "future_field")
    # Both unknown keys should appear in the warning message.
    assert any("future_field" in record.message and "another_unknown" in record.message
               for record in caplog.records)


def test_from_dict_loads_legacy_v1_files_silently():
    # A pre-v2 file lacks all PIMS fields; defaults must fill in.
    payload = {
        "metadata": {
            "name": "Legacy",
            "schema_version": 1,
        },
        "isa_data": {"elements": [], "connections": []},
    }
    project = Project.from_dict(payload)
    assert project.metadata.name == "Legacy"
    assert project.metadata.focal_issue == ""
    assert project.metadata.spatial_scale == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: `test_from_dict_drops_unknown_metadata_keys` FAILS with `TypeError: ProjectMetadata.__init__() got an unexpected keyword argument 'future_field'`.
The legacy-v1 test should already pass.

- [ ] **Step 3: Add `import logging` and `from dataclasses import fields` near the top**

In `sespy/data_structure.py`, change line 11 (currently `from dataclasses import asdict, dataclass, field`) to:

```python
import logging
from dataclasses import asdict, dataclass, field, fields
```

Add this immediately after the imports block (around line 15):

```python
_log = logging.getLogger(__name__)
```

- [ ] **Step 4: Update `Project.from_dict` to filter unknown keys**

Find `Project.from_dict` (currently at lines 114-118). Replace with:

```python
    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Project":
        meta_raw = raw.get("metadata", {}) or {}
        valid_keys = {f.name for f in fields(ProjectMetadata)}
        meta_filtered = {k: v for k, v in meta_raw.items() if k in valid_keys}
        dropped = sorted(set(meta_raw.keys()) - valid_keys)
        if dropped:
            _log.warning(
                "Project metadata had unknown keys (dropped): %s", dropped
            )
        meta = ProjectMetadata(**meta_filtered)
        isa = _isa_from_dict(raw.get("isa_data", raw))  # tolerate flat shapes
        return cls(metadata=meta, isa_data=isa)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add sespy/data_structure.py tests/test_data_structure.py
git commit -m "feat(schema): forward-compatible unknown-key filter on Project.from_dict"
```

---

## Task 3: Add PIMS constants

**Files:**
- Modify: `sespy/constants.py` — append three tuples.

Mirror the R values exactly (see `../SESToolbox/MarineSABRES_SES_Shiny/constants.R:528-532, 681-687`).

- [ ] **Step 1: Append the three tuples to `sespy/constants.py`**

Append at the end of the file:

```python


# ---------------------------------------------------------------------------
# PIMS (Process & Information Management System) — Project Setup constants.
# Mirrors ../SESToolbox/MarineSABRES_SES_Shiny/constants.R:528, 682.
# ---------------------------------------------------------------------------

DA_SITES: tuple[str, ...] = (
    "Tuscan Archipelago",
    "Arctic Northeast Atlantic",
    "Macaronesia",
)

SPATIAL_SCALES: tuple[str, ...] = (
    "Local",
    "Regional",
    "National",
    "International",
)

TEMPORAL_SCALES: tuple[str, ...] = (
    "Daily",
    "Monthly",
    "Yearly",
    "Decadal",
)
```

- [ ] **Step 2: Sanity-check the import**

```bash
micromamba run -n shiny python -c "from sespy.constants import DA_SITES, SPATIAL_SCALES, TEMPORAL_SCALES; print(len(DA_SITES), len(SPATIAL_SCALES), len(TEMPORAL_SCALES))"
```
Expected: `3 4 4`.

- [ ] **Step 3: Commit**

```bash
git add sespy/constants.py
git commit -m "feat(constants): add DA_SITES, SPATIAL_SCALES, TEMPORAL_SCALES for PIMS"
```

---

## Task 4: Add i18n keys for PIMS

**Files:**
- Modify: `sespy/translations/core.json`

Add 30 keys (1 nav + 1 stepper + 28 module-scoped). English first; the other 8 languages (es, fr, de, lt, pt, it, no, el) get the same English values as placeholders, mirroring the pattern used by Boolean+Simulation and BOT.

- [ ] **Step 1: Add `nav.pims` to the `nav.*` block**

Insert after the line containing `"nav.bot"`:

```json
    "nav.pims": {
        "en": "Project Setup",
        "es": "Project Setup",
        "fr": "Project Setup",
        "de": "Project Setup",
        "lt": "Project Setup",
        "pt": "Project Setup",
        "it": "Project Setup",
        "no": "Project Setup",
        "el": "Project Setup"
    },
```

- [ ] **Step 2: Add `stepper.setup` to the `stepper.*` block**

Insert after the existing `stepper.start` entry (search for `"stepper.start"`):

```json
    "stepper.setup": {
        "en": "Setup",
        "es": "Setup",
        "fr": "Setup",
        "de": "Setup",
        "lt": "Setup",
        "pt": "Setup",
        "it": "Setup",
        "no": "Setup",
        "el": "Setup"
    },
```

- [ ] **Step 3: Add the 28 `pims.*` keys**

Insert this block after the last `bot.*` key (locate `"bot.stale_warning"` and place this after its closing `}`):

```json
    "pims.title": {
        "en": "Project Setup",
        "es": "Project Setup", "fr": "Project Setup", "de": "Project Setup",
        "lt": "Project Setup", "pt": "Project Setup", "it": "Project Setup",
        "no": "Project Setup", "el": "Project Setup"
    },
    "pims.subtitle": {
        "en": "Define the project's context, demonstration area, and scope.",
        "es": "Define the project's context, demonstration area, and scope.",
        "fr": "Define the project's context, demonstration area, and scope.",
        "de": "Define the project's context, demonstration area, and scope.",
        "lt": "Define the project's context, demonstration area, and scope.",
        "pt": "Define the project's context, demonstration area, and scope.",
        "it": "Define the project's context, demonstration area, and scope.",
        "no": "Define the project's context, demonstration area, and scope.",
        "el": "Define the project's context, demonstration area, and scope."
    },
    "pims.project_information": {
        "en": "Project information",
        "es": "Project information", "fr": "Project information", "de": "Project information",
        "lt": "Project information", "pt": "Project information", "it": "Project information",
        "no": "Project information", "el": "Project information"
    },
    "pims.project_name": {
        "en": "Project name",
        "es": "Project name", "fr": "Project name", "de": "Project name",
        "lt": "Project name", "pt": "Project name", "it": "Project name",
        "no": "Project name", "el": "Project name"
    },
    "pims.project_name_placeholder": {
        "en": "e.g. Madeira coastal monitoring 2026",
        "es": "e.g. Madeira coastal monitoring 2026", "fr": "e.g. Madeira coastal monitoring 2026", "de": "e.g. Madeira coastal monitoring 2026",
        "lt": "e.g. Madeira coastal monitoring 2026", "pt": "e.g. Madeira coastal monitoring 2026", "it": "e.g. Madeira coastal monitoring 2026",
        "no": "e.g. Madeira coastal monitoring 2026", "el": "e.g. Madeira coastal monitoring 2026"
    },
    "pims.demonstration_area": {
        "en": "Demonstration area",
        "es": "Demonstration area", "fr": "Demonstration area", "de": "Demonstration area",
        "lt": "Demonstration area", "pt": "Demonstration area", "it": "Demonstration area",
        "no": "Demonstration area", "el": "Demonstration area"
    },
    "pims.focal_issue": {
        "en": "Focal issue",
        "es": "Focal issue", "fr": "Focal issue", "de": "Focal issue",
        "lt": "Focal issue", "pt": "Focal issue", "it": "Focal issue",
        "no": "Focal issue", "el": "Focal issue"
    },
    "pims.focal_issue_placeholder": {
        "en": "What problem is this project investigating?",
        "es": "What problem is this project investigating?", "fr": "What problem is this project investigating?", "de": "What problem is this project investigating?",
        "lt": "What problem is this project investigating?", "pt": "What problem is this project investigating?", "it": "What problem is this project investigating?",
        "no": "What problem is this project investigating?", "el": "What problem is this project investigating?"
    },
    "pims.definition_statement": {
        "en": "Definition statement",
        "es": "Definition statement", "fr": "Definition statement", "de": "Definition statement",
        "lt": "Definition statement", "pt": "Definition statement", "it": "Definition statement",
        "no": "Definition statement", "el": "Definition statement"
    },
    "pims.definition_statement_placeholder": {
        "en": "A short paragraph defining the system, its boundary, and the project's goal.",
        "es": "A short paragraph defining the system, its boundary, and the project's goal.",
        "fr": "A short paragraph defining the system, its boundary, and the project's goal.",
        "de": "A short paragraph defining the system, its boundary, and the project's goal.",
        "lt": "A short paragraph defining the system, its boundary, and the project's goal.",
        "pt": "A short paragraph defining the system, its boundary, and the project's goal.",
        "it": "A short paragraph defining the system, its boundary, and the project's goal.",
        "no": "A short paragraph defining the system, its boundary, and the project's goal.",
        "el": "A short paragraph defining the system, its boundary, and the project's goal."
    },
    "pims.system_scope": {
        "en": "System scope",
        "es": "System scope", "fr": "System scope", "de": "System scope",
        "lt": "System scope", "pt": "System scope", "it": "System scope",
        "no": "System scope", "el": "System scope"
    },
    "pims.temporal_scale": {
        "en": "Temporal scale",
        "es": "Temporal scale", "fr": "Temporal scale", "de": "Temporal scale",
        "lt": "Temporal scale", "pt": "Temporal scale", "it": "Temporal scale",
        "no": "Temporal scale", "el": "Temporal scale"
    },
    "pims.temporal_daily": {
        "en": "Daily",
        "es": "Daily", "fr": "Daily", "de": "Daily",
        "lt": "Daily", "pt": "Daily", "it": "Daily",
        "no": "Daily", "el": "Daily"
    },
    "pims.temporal_monthly": {
        "en": "Monthly",
        "es": "Monthly", "fr": "Monthly", "de": "Monthly",
        "lt": "Monthly", "pt": "Monthly", "it": "Monthly",
        "no": "Monthly", "el": "Monthly"
    },
    "pims.temporal_yearly": {
        "en": "Yearly",
        "es": "Yearly", "fr": "Yearly", "de": "Yearly",
        "lt": "Yearly", "pt": "Yearly", "it": "Yearly",
        "no": "Yearly", "el": "Yearly"
    },
    "pims.temporal_decadal": {
        "en": "Decadal",
        "es": "Decadal", "fr": "Decadal", "de": "Decadal",
        "lt": "Decadal", "pt": "Decadal", "it": "Decadal",
        "no": "Decadal", "el": "Decadal"
    },
    "pims.spatial_scale": {
        "en": "Spatial scale",
        "es": "Spatial scale", "fr": "Spatial scale", "de": "Spatial scale",
        "lt": "Spatial scale", "pt": "Spatial scale", "it": "Spatial scale",
        "no": "Spatial scale", "el": "Spatial scale"
    },
    "pims.spatial_local": {
        "en": "Local",
        "es": "Local", "fr": "Local", "de": "Local",
        "lt": "Local", "pt": "Local", "it": "Local",
        "no": "Local", "el": "Local"
    },
    "pims.spatial_regional": {
        "en": "Regional",
        "es": "Regional", "fr": "Regional", "de": "Regional",
        "lt": "Regional", "pt": "Regional", "it": "Regional",
        "no": "Regional", "el": "Regional"
    },
    "pims.spatial_national": {
        "en": "National",
        "es": "National", "fr": "National", "de": "National",
        "lt": "National", "pt": "National", "it": "National",
        "no": "National", "el": "National"
    },
    "pims.spatial_international": {
        "en": "International",
        "es": "International", "fr": "International", "de": "International",
        "lt": "International", "pt": "International", "it": "International",
        "no": "International", "el": "International"
    },
    "pims.system_in_focus": {
        "en": "System in focus",
        "es": "System in focus", "fr": "System in focus", "de": "System in focus",
        "lt": "System in focus", "pt": "System in focus", "it": "System in focus",
        "no": "System in focus", "el": "System in focus"
    },
    "pims.system_in_focus_placeholder": {
        "en": "Describe the part of the social-ecological system this project examines.",
        "es": "Describe the part of the social-ecological system this project examines.",
        "fr": "Describe the part of the social-ecological system this project examines.",
        "de": "Describe the part of the social-ecological system this project examines.",
        "lt": "Describe the part of the social-ecological system this project examines.",
        "pt": "Describe the part of the social-ecological system this project examines.",
        "it": "Describe the part of the social-ecological system this project examines.",
        "no": "Describe the part of the social-ecological system this project examines.",
        "el": "Describe the part of the social-ecological system this project examines."
    },
    "pims.save": {
        "en": "Save project information",
        "es": "Save project information", "fr": "Save project information", "de": "Save project information",
        "lt": "Save project information", "pt": "Save project information", "it": "Save project information",
        "no": "Save project information", "el": "Save project information"
    },
    "pims.saved_at": {
        "en": "Last saved at",
        "es": "Last saved at", "fr": "Last saved at", "de": "Last saved at",
        "lt": "Last saved at", "pt": "Last saved at", "it": "Last saved at",
        "no": "Last saved at", "el": "Last saved at"
    },
    "pims.no_save_yet": {
        "en": "Not saved this session.",
        "es": "Not saved this session.", "fr": "Not saved this session.", "de": "Not saved this session.",
        "lt": "Not saved this session.", "pt": "Not saved this session.", "it": "Not saved this session.",
        "no": "Not saved this session.", "el": "Not saved this session."
    },
    "pims.modified_at": {
        "en": "Modified at",
        "es": "Modified at", "fr": "Modified at", "de": "Modified at",
        "lt": "Modified at", "pt": "Modified at", "it": "Modified at",
        "no": "Modified at", "el": "Modified at"
    },
    "pims.schema_version": {
        "en": "Schema version",
        "es": "Schema version", "fr": "Schema version", "de": "Schema version",
        "lt": "Schema version", "pt": "Schema version", "it": "Schema version",
        "no": "Schema version", "el": "Schema version"
    },
```

- [ ] **Step 4: Validate the JSON parses**

```bash
micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('parse: OK')"
```
Expected: `parse: OK`. If a `JSONDecodeError`, fix the trailing-comma or brace mismatch and re-run.

- [ ] **Step 5: Verify all 30 keys are present**

```bash
micromamba run -n shiny python -c "
import json
trans = json.load(open('sespy/translations/core.json', encoding='utf-8'))
keys = ['nav.pims', 'stepper.setup'] + [
    'pims.title', 'pims.subtitle', 'pims.project_information', 'pims.project_name',
    'pims.project_name_placeholder', 'pims.demonstration_area', 'pims.focal_issue',
    'pims.focal_issue_placeholder', 'pims.definition_statement', 'pims.definition_statement_placeholder',
    'pims.system_scope', 'pims.temporal_scale', 'pims.temporal_daily', 'pims.temporal_monthly',
    'pims.temporal_yearly', 'pims.temporal_decadal', 'pims.spatial_scale', 'pims.spatial_local',
    'pims.spatial_regional', 'pims.spatial_national', 'pims.spatial_international',
    'pims.system_in_focus', 'pims.system_in_focus_placeholder', 'pims.save', 'pims.saved_at',
    'pims.no_save_yet', 'pims.modified_at', 'pims.schema_version'
]
missing = [k for k in keys if k not in trans]
assert not missing, f'missing: {missing}'
print(f'{len(keys)} keys present')
"
```
Expected: `30 keys present`.

- [ ] **Step 6: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(pims): add 30 translation keys for PIMS Project Setup"
```

---

## Task 5: Event-bus extension — `project_change` channel

**Files:**
- Modify: `sespy/event_bus.py`

Add a new counter for metadata-only edits, separate from `isa_change`. Analysis modules subscribe only to `isa_change` and so will not see metadata-only edits as stale-data events.

- [ ] **Step 1: Add the field to the `EventBus` dataclass**

In `sespy/event_bus.py`, locate the `isa_change` field (line 30) and add a new field directly below it (before `cld_update`):

```python
    isa_change: reactive.Value[int]
    project_change: reactive.Value[int]
    cld_update: reactive.Value[int]
```

- [ ] **Step 2: Add the emit method**

Add a new method directly after `emit_isa_change` (lines 39-41):

```python
    def emit_isa_change(self) -> None:
        with reactive.isolate():
            self.isa_change.set(self.isa_change.get() + 1)

    def emit_project_change(self) -> None:
        with reactive.isolate():
            self.project_change.set(self.project_change.get() + 1)
```

- [ ] **Step 3: Update `create_event_bus` to initialize the new value**

Insert the new line after `isa_change=reactive.value(0),` in `create_event_bus`:

```python
def create_event_bus() -> EventBus:
    return EventBus(
        isa_change=reactive.value(0),
        project_change=reactive.value(0),
        cld_update=reactive.value(0),
        analysis_request=reactive.value(0),
        template_loaded=reactive.value(0),
        project_loaded=reactive.value(0),
        project_saved=reactive.value(0),
        navigation_request=reactive.value(0),
        language_changed=reactive.value(0),
    )
```

- [ ] **Step 4: Sanity-check via import**

```bash
micromamba run -n shiny python -c "from sespy.event_bus import create_event_bus; b = create_event_bus(); b.emit_project_change(); print('ok, counter at', b.project_change.get())"
```
Expected: `ok, counter at 1`.

- [ ] **Step 5: Commit**

```bash
git add sespy/event_bus.py
git commit -m "feat(event_bus): add project_change channel for metadata-only edits"
```

---

## Task 6: Plumb `project_metadata` reactive through save/load/template/recent paths

**Files:**
- Modify: `app.py:141-152` (server function — create the new reactive, pass to consumers)
- Modify: `sespy/modules/project_io.py` — extend `quick_actions_server` signature; update save (`save_project`), load (`_on_upload`), restore (`_do_restore`), new (`_on_new`), and `_autosave_on_change` to read/write both reactives.
- Modify: `sespy/modules/templates.py` — extend `templates_server` signature; on template load, set both `project_data` and `project_metadata`.
- Modify: `sespy/modules/recent_projects.py` — extend `recent_projects_server` signature; on recent-project load, set both reactives.

This is the architectural prep that makes PIMS possible. PIMS edits `project_metadata` directly (Task 10); other modules continue to read only `project_data` (IsaData) and ignore metadata.

- [ ] **Step 1: Update `app.py` to create `project_metadata` and import the new dataclass**

In `app.py`, find the import block (lines 19-20) — the line `from sespy import data_structure`. Below it, add an import for `ProjectMetadata`:

```python
from sespy import data_structure
from sespy.data_structure import ProjectMetadata
```

In the server function (line 141), insert `project_metadata` after the `project_data` line:

```python
def server(input: Inputs, output: Outputs, session: Session) -> None:
    project_data = reactive.value(data_structure.load_sample(SAMPLE))
    project_metadata = reactive.value(ProjectMetadata.new())
    event_bus = create_event_bus()
```

- [ ] **Step 2: Update the `quick_actions_server` call in `app.py` to pass `project_metadata`**

Find the existing call (around line 153). Add `project_metadata=project_metadata`:

```python
    quick_actions_server(
        input, output, session,
        project_data=project_data,
        project_metadata=project_metadata,
        event_bus=event_bus,
        sample_path=SAMPLE,
        translator=T,
    )
```

- [ ] **Step 3: Update the `templates_server` call in `app.py`**

Find the existing call (around line 161). Add the new kwarg:

```python
    templates_server(
        "templates",
        project_data=project_data,
        project_metadata=project_metadata,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 4: Update the `recent_projects_server` call in `app.py`**

Find the existing call (around line 223). Add the new kwarg:

```python
    recent_projects_server(
        "recent",
        project_data=project_data,
        project_metadata=project_metadata,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 5: Extend `quick_actions_server` signature in `project_io.py`**

In `sespy/modules/project_io.py`, find `def quick_actions_server(...)`. Add `project_metadata` after `project_data`:

```python
def quick_actions_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[ds.IsaData],
    project_metadata: reactive.Value[ds.ProjectMetadata],
    event_bus: EventBus,
    sample_path: Path,
    translator: Translator | None = None,
) -> None:
```

- [ ] **Step 6: Update `_autosave_on_change` to wrap both reactives**

In `project_io.py`, find `_autosave_on_change` (around line 119-130). It currently calls `write_autosave(project_data.get())`, which goes through `Project.from_isa` internally — meaning metadata is synthesized fresh and any user edits are dropped. Replace the function with an explicit Project construction that includes `project_metadata`:

```python
    @reactive.effect
    def _autosave_on_change():
        # Subscribe to ISA changes so editor activity is autosaved.
        event_bus.isa_change.get()
        # Also subscribe to project_change so metadata-only edits land in the autosave.
        event_bus.project_change.get()
        try:
            project = ds.Project(
                metadata=project_metadata.get(),
                isa_data=project_data.get(),
            )
            write_autosave(project)
            from datetime import datetime as _dt
            autosave_time.set(_dt.now().strftime("%H:%M:%S"))
        except Exception:
            pass
```

`autosave_time` is the existing `reactive.value(...)` defined a few lines above this effect — keep it as-is and let this replacement use it.

- [ ] **Step 7: Update `save_project` to use both reactives**

Find `def save_project()` (around line 186). Replace `proj = ds.Project.from_isa(...)` with explicit construction:

```python
    @render.download(
        filename=lambda: f"sespy-project-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    def save_project():
        proj = ds.Project(
            metadata=project_metadata.get(),
            isa_data=project_data.get(),
        ).with_modified_now()
        try:
            clear_autosave()
        except Exception:
            pass
        yield project_to_bytes(proj)
```

- [ ] **Step 8: Update `_do_restore` to set both reactives**

Find `_do_restore` (around line 200). After `project_data.set(recovered.isa_data)`, add the metadata sync:

```python
    @reactive.effect
    @reactive.event(input["__sespy_restore_autosave__"], ignore_init=True)
    def _do_restore():
        recovered = read_autosave()
        if recovered is None:
            ui.notification_remove("autosave-recovery")
            return
        project_data.set(recovered.isa_data)
        project_metadata.set(recovered.metadata)
        event_bus.emit_isa_change()
        event_bus.emit_project_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        ui.notification_remove("autosave-recovery")
        ui.notification_show(
            t("ui.quickactions.restored", "Recovered work restored."),
            type="message",
            duration=4,
        )
```

- [ ] **Step 9: Update `_on_upload` to set both reactives**

Find `_on_upload` (around line 220). After `project_data.set(proj.isa_data)`, add metadata sync:

```python
    @reactive.effect
    @reactive.event(input.load_project, ignore_init=True)
    def _on_upload():
        files = input.load_project()
        if not files:
            return
        upload = files[0]
        try:
            proj = load_project(Path(upload["datapath"]))
        except ValueError as e:
            ui.notification_show(str(e), type="warning", duration=8)
            return
        project_data.set(proj.isa_data)
        project_metadata.set(proj.metadata)
        event_bus.emit_isa_change()
        event_bus.emit_project_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
        try:
            add_recent(
                path=upload["datapath"],
                name=proj.metadata.name,
                element_count=proj.isa_data.element_count(),
                connection_count=proj.isa_data.connection_count(),
            )
        except Exception:
            pass
        ui.notification_show(
            t("ui.quickactions.loaded", "Project loaded.")
            + f"  ({proj.metadata.name})",
            type="message",
            duration=4,
        )
```

- [ ] **Step 10: Update `_on_new` to reset both reactives**

Find `_on_new` (around line 257). Add metadata reset:

```python
    @reactive.effect
    @reactive.event(input.new_project, ignore_init=True)
    def _on_new():
        project_data.set(ds.load_sample(sample_path))
        project_metadata.set(ds.ProjectMetadata.new())
        event_bus.emit_isa_change()
        event_bus.emit_project_change()
        event_bus.emit_cld_update()
        ui.notification_show(
            t("ui.quickactions.reset", "Project reset to sample."),
            type="message",
            duration=3,
        )
```

- [ ] **Step 11: Extend `templates_server` to set both reactives on load**

In `sespy/modules/templates.py`, change line 16 from:

```python
from ..data_structure import IsaData
```

to:

```python
from ..data_structure import IsaData, ProjectMetadata
```

Then find `def templates_server(...)` and add `project_metadata` to the signature:

```python
def templates_server(
    id: str,
    *,
    project_data: reactive.Value[IsaData],
    project_metadata: reactive.Value[ProjectMetadata],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
```

Find the line `project_data.set(project.isa_data)` (around line 98). Add metadata sync immediately after:

```python
        project_data.set(project.isa_data)
        project_metadata.set(project.metadata)
        event_bus.emit_isa_change()
        event_bus.emit_project_change()
        event_bus.emit_cld_update()
        event_bus.emit_template_loaded()
```

- [ ] **Step 12: Extend `recent_projects_server` to set both reactives on load**

In `sespy/modules/recent_projects.py`, two functions need the new parameter — the public `recent_projects_server` (around line 98) and the internal `_wire_load` helper (around line 153). Both currently take `project_data: reactive.Value[IsaData]`.

First, change the data-structure import on line 16 from:

```python
from ..data_structure import IsaData
```

to:

```python
from ..data_structure import IsaData, ProjectMetadata
```

Update `recent_projects_server`'s signature (around line 98-103). Add `project_metadata` immediately after `project_data`:

```python
def recent_projects_server(
    id: str,
    *,
    project_data: reactive.Value[IsaData],
    project_metadata: reactive.Value[ProjectMetadata],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
```

Inside `recent_projects_server`, find every call to `_wire_load(...)` and add `project_metadata=project_metadata` to the kwargs.

Update the `_wire_load` helper signature (around line 153). Add `project_metadata`:

```python
def _wire_load(
    input: Inputs,
    idx: int,
    project_data: reactive.Value[IsaData],
    project_metadata: reactive.Value[ProjectMetadata],
    event_bus: EventBus,
    entries_calc,
    refresh: reactive.Value[int],
) -> None:
```

Update the load handler body (around lines 174-177). Replace:

```python
        project_data.set(proj.isa_data)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
```

with:

```python
        project_data.set(proj.isa_data)
        project_metadata.set(proj.metadata)
        event_bus.emit_isa_change()
        event_bus.emit_project_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()
```

- [ ] **Step 13: Sanity-check that imports still work**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`. If `TypeError: <fn>() got an unexpected keyword argument 'project_metadata'`, you missed updating one of the three servers in app.py (`quick_actions_server`, `templates_server`, `recent_projects_server`) to pass the new kwarg, OR a server signature is missing the kwarg.

- [ ] **Step 14: Re-run the unit suite**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py
```
Expected: `108 passed`. (Same as before — no regressions.)

- [ ] **Step 15: Smoke-test in the browser**

Boot the app on port 8000 (`run_in_background`). Open `http://127.0.0.1:8000`, load a template via Templates (e.g. Coastal Tourism), then save the project via Quick Actions → Save. Open the saved JSON and verify `metadata.name`, `metadata.description`, `metadata.da_site` etc. are NOT the synthesized "Untitled Project" defaults — they reflect the loaded template's real metadata. (If they're synthesized defaults, `templates_server` step 11 didn't take.)

- [ ] **Step 16: Commit**

```bash
git add app.py sespy/modules/project_io.py sespy/modules/templates.py sespy/modules/recent_projects.py
git commit -m "feat(app): add parallel project_metadata reactive across save/load/template paths"
```

---

## Task 7: PIMS module skeleton (UI shell, no functionality yet)

**Files:**
- Create: `sespy/modules/pims_project.py`

Build the module file with empty placeholders. Adding functionality is split across Tasks 9–11. The module operates on `project_metadata` only — it does not need `project_data` (IsaData).

- [ ] **Step 1: Create `sespy/modules/pims_project.py` with the skeleton**

```python
"""PIMS Project Setup module.

Mirrors `modules/pims_module.R` lines 7-152 (PROJECT SETUP MODULE).
Captures project-level context (name, DA site, focal issue, definition
statement, temporal/spatial scale, system in focus) in a two-column form
view that updates the parallel `project_metadata` reactive on Save.

Pattern matches `analysis_intervention.py` for static form-style UI.
"""
from __future__ import annotations

from datetime import datetime, timezone

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import DA_SITES, SPATIAL_SCALES, TEMPORAL_SCALES
from ..data_structure import ProjectMetadata
from ..event_bus import EventBus
from ..i18n import Translator, t


_TEMPORAL_LABEL_KEYS = {
    "Daily": "pims.temporal_daily",
    "Monthly": "pims.temporal_monthly",
    "Yearly": "pims.temporal_yearly",
    "Decadal": "pims.temporal_decadal",
}

_SPATIAL_LABEL_KEYS = {
    "Local": "pims.spatial_local",
    "Regional": "pims.spatial_regional",
    "National": "pims.spatial_national",
    "International": "pims.spatial_international",
}


def _temporal_choices() -> dict[str, str]:
    """Map raw values to localized labels for the temporal-scale select.

    Iterating TEMPORAL_SCALES guarantees the form stays in lock-step with
    the canonical constants — adding a new scale to the constants list
    forces a missing-label-key KeyError here, fast-failing rather than
    silently producing an incomplete dropdown.
    """
    return {"": "—", **{v: t(_TEMPORAL_LABEL_KEYS[v]) for v in TEMPORAL_SCALES}}


def _spatial_choices() -> dict[str, str]:
    return {"": "—", **{v: t(_SPATIAL_LABEL_KEYS[v]) for v in SPATIAL_SCALES}}


def _da_site_choices() -> dict[str, str]:
    return {"": "—", **{s: s for s in DA_SITES}}


@module.ui
def pims_project_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("pims.title")),
        ui.div(
            ui.tags.p(t("pims.subtitle"), class_="text-muted"),
            ui.layout_columns(
                ui.tags.div(),  # placeholder for left column (Task 9)
                ui.tags.div(),  # placeholder for right column (Task 9)
                col_widths=(6, 6),
            ),
            style="padding: 16px;",
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def pims_project_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_metadata: reactive.Value[ProjectMetadata],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    # Session-only indicator: HH:MM:SS string set on the most recent Save
    # click in this session. None until first save.
    pims_save_status: reactive.Value[str | None] = reactive.value(None)

    # Placeholder — full save handler in Task 10.
    @reactive.effect
    @reactive.event(input.save_project_info, ignore_init=True)
    def _handle_save() -> None:
        pass

    # Placeholder — full load-form-values in Task 11.
    @reactive.effect
    def _load_form_values() -> None:
        # Subscribe so the placeholder still tracks; intentionally a no-op.
        project_metadata.get()
```

- [ ] **Step 2: Verify the file imports cleanly**

```bash
micromamba run -n shiny python -c "from sespy.modules.pims_project import pims_project_ui, pims_project_server; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/pims_project.py
git commit -m "feat(pims): module skeleton with empty placeholders"
```

---

## Task 8: Wire PIMS into app.py + add `setup` workflow stage

**Files:**
- Modify: `app.py`

Insert PIMS at the top of NAV. Add a new `setup` STEPPER stage at the front. Map `pims → setup`. Add the panel and the server registration. Pass `project_metadata` (created in Task 6) to the new server.

- [ ] **Step 1: Add the import**

In `app.py`, between the `analysis_simulation` and `cld_visualization` imports (around line 50), insert:

```python
from sespy.modules.pims_project import pims_project_server, pims_project_ui
```

- [ ] **Step 2: Insert the NAV entry at the top of the list**

Find `NAV: list[NavItem] = [` (line 72). Insert as the FIRST item:

```python
    NavItem(id="pims",     icon="clipboard-list",  label="Project Setup",     label_key="nav.pims"),
```

- [ ] **Step 3: Insert the `setup` stepper stage**

Find `STEPPER: list[StepperItem] = [` (line 92). Insert as the FIRST item:

```python
    StepperItem(id="setup",     label="Setup",       label_key="stepper.setup"),
```

- [ ] **Step 4: Add the NAV_TO_STEP mapping**

Find `NAV_TO_STEP = {` (line 101). Insert at the top of the dict:

```python
    "pims": "setup",
```

- [ ] **Step 5: Add the panel**

Find `PANELS = (` (line 112). Insert as the FIRST tuple element:

```python
    ui.nav_panel("Project Setup",     pims_project_ui("pims"),                     value="pims"),
```

- [ ] **Step 6: Add the server registration**

Find `templates_server(...)` (around line 161, now updated by Task 6 to take `project_metadata`). Add a `pims_project_server` call directly above it:

```python
    pims_project_server(
        "pims",
        project_metadata=project_metadata,
        event_bus=event_bus,
        translator=T,
    )

    templates_server(
        "templates",
        project_data=project_data,
        project_metadata=project_metadata,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 7: Smoke-test the import and start the app**

```bash
micromamba run -n shiny python -c "import app; print('imports ok')"
```
Expected: `imports ok`.

Boot the app:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
(Run with `run_in_background=True`.)

Wait for the server:
```bash
micromamba run -n shiny python .tmp/wait_port.py
```
Expected: `ready after <N>s`.

Open `http://127.0.0.1:8000` — verify "Project Setup" appears as the **first** nav item, the workflow stepper shows a **Setup** stage to the left of "Get Started", and clicking Project Setup lands on a card titled "Project Setup" with the placeholder subtitle. Stop the server when done.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat(app): wire PIMS module + setup stepper stage"
```

---

## Task 9: Form UI render

**Files:**
- Modify: `sespy/modules/pims_project.py` — replace the placeholder `layout_columns` body in `pims_project_ui`.

Build the two-column form. Inputs are bound to namespaced ids (`pims-project_name` etc.); the server-side load and save tasks read these values directly.

- [ ] **Step 1: Replace the body of `pims_project_ui`**

In `sespy/modules/pims_project.py`, replace the `pims_project_ui` function body with:

```python
@module.ui
def pims_project_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("pims.title")),
        ui.div(
            ui.tags.p(t("pims.subtitle"), class_="text-muted"),
            ui.layout_columns(
                # Left column: project information.
                ui.div(
                    ui.h4(t("pims.project_information")),
                    ui.input_text(
                        "project_name",
                        t("pims.project_name"),
                        placeholder=t("pims.project_name_placeholder"),
                    ),
                    ui.input_select(
                        "da_site",
                        t("pims.demonstration_area"),
                        choices=_da_site_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "focal_issue",
                        t("pims.focal_issue"),
                        placeholder=t("pims.focal_issue_placeholder"),
                        rows=4,
                        width="100%",
                    ),
                    ui.input_text_area(
                        "definition_statement",
                        t("pims.definition_statement"),
                        placeholder=t("pims.definition_statement_placeholder"),
                        rows=6,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "save_project_info",
                        t("pims.save"),
                        class_="btn btn-primary",
                        style="margin-top: 8px;",
                    ),
                ),
                # Right column: system scope + status.
                ui.div(
                    ui.h4(t("pims.system_scope")),
                    ui.input_select(
                        "temporal_scale",
                        t("pims.temporal_scale"),
                        choices=_temporal_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "spatial_scale",
                        t("pims.spatial_scale"),
                        choices=_spatial_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "system_in_focus",
                        t("pims.system_in_focus"),
                        placeholder=t("pims.system_in_focus_placeholder"),
                        rows=4,
                        width="100%",
                    ),
                    ui.tags.hr(),
                    ui.output_ui("current_status"),
                ),
                col_widths=(6, 6),
            ),
            style="padding: 16px;",
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )
```

- [ ] **Step 2: Add the `current_status` renderer**

In `pims_project_server`, after the placeholder `_handle_save`, add:

```python
    @output
    @render.ui
    def current_status():
        meta = project_metadata.get()
        saved_text = pims_save_status.get() or t("pims.no_save_yet")
        return ui.tags.dl(
            ui.tags.dt(t("pims.saved_at")),
            ui.tags.dd(saved_text),
            ui.tags.dt(t("pims.modified_at")),
            ui.tags.dd(meta.modified_at or "—"),
            ui.tags.dt(t("pims.schema_version")),
            ui.tags.dd(str(meta.schema_version)),
        )
```

- [ ] **Step 3: Smoke-test in the browser**

Boot the app on port 8000. Navigate to Project Setup. Verify:
- Left column shows: Project name (text), Demonstration area (select with 4 options including blank), Focal issue (textarea, 4 rows), Definition statement (textarea, 6 rows), Save button.
- Right column shows: Temporal scale (select), Spatial scale (select), System in focus (textarea, 4 rows), separator, status block listing "Last saved at: Not saved this session", "Modified at: <a timestamp from `ProjectMetadata.new()`>", "Schema version: 2".
- Save button does nothing yet (placeholder).

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/pims_project.py
git commit -m "feat(pims): form UI with two-column layout and status block"
```

---

## Task 10: Save handler

**Files:**
- Modify: `sespy/modules/pims_project.py` — replace the placeholder `_handle_save`.

On Save click: read all form inputs, apply the empty-name fallback, build a fresh `ProjectMetadata`, call `project_metadata.set` and `event_bus.emit_project_change`.

- [ ] **Step 1: Replace `_handle_save`**

In `sespy/modules/pims_project.py`, replace the placeholder `_handle_save` (currently `pass`-only) with:

```python
    @reactive.effect
    @reactive.event(input.save_project_info, ignore_init=True)
    def _handle_save() -> None:
        # Empty-name fallback: never persist a literally-empty project name.
        name = (input.project_name() or "").strip() or "Untitled Project"
        current = project_metadata.get()
        new_meta = ProjectMetadata(
            name=name,
            description=current.description,
            da_site=(input.da_site() or "").strip(),
            regional_sea=current.regional_sea,
            ecosystem_type=current.ecosystem_type,
            focal_issue=(input.focal_issue() or "").strip(),
            definition_statement=(input.definition_statement() or "").strip(),
            temporal_scale=(input.temporal_scale() or "").strip(),
            spatial_scale=(input.spatial_scale() or "").strip(),
            system_in_focus=(input.system_in_focus() or "").strip(),
            created_at=current.created_at,
            modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            schema_version=current.schema_version,
        )
        project_metadata.set(new_meta)
        pims_save_status.set(datetime.now().strftime("%H:%M:%S"))
        event_bus.emit_project_change()
        ui.notification_show(
            f"{t('pims.save')} ✓",
            duration=3,
            type="message",
        )
```

- [ ] **Step 2: Smoke-test in the browser**

Boot the app. Navigate to Project Setup. Type a project name, pick a DA site, fill focal issue and definition statement, pick temporal=Yearly, spatial=Regional, fill system in focus. Click Save. Verify:
- A toast appears confirming save.
- "Last saved at" updates to the current HH:MM:SS.
- "Modified at" updates to the current ISO timestamp.

Now switch to a different module and back; the form will go blank (Task 11 fixes this — for now it's expected behaviour).

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/pims_project.py
git commit -m "feat(pims): save handler with empty-name fallback and project_change emission"
```

---

## Task 11: Load-form-values effect

**Files:**
- Modify: `sespy/modules/pims_project.py` — replace the placeholder `_load_form_values`.

When `project_metadata` changes (template load, Recent Projects pick, Save round-trip), populate the form with the loaded values. Reads only `project_metadata` to avoid feedback loops with `_handle_save` writes.

- [ ] **Step 1: Replace `_load_form_values`**

In `sespy/modules/pims_project.py`, replace the placeholder `_load_form_values` with:

```python
    @reactive.effect
    def _load_form_values() -> None:
        # Track project_metadata changes only. Do NOT subscribe to inputs
        # here — that would cause this effect to re-fire on every keystroke
        # and undo the user's typing.
        meta = project_metadata.get()
        ui.update_text("project_name", value=meta.name or "")
        ui.update_select("da_site", selected=meta.da_site or "")
        ui.update_text_area("focal_issue", value=meta.focal_issue or "")
        ui.update_text_area("definition_statement", value=meta.definition_statement or "")
        ui.update_select("temporal_scale", selected=meta.temporal_scale or "")
        ui.update_select("spatial_scale", selected=meta.spatial_scale or "")
        ui.update_text_area("system_in_focus", value=meta.system_in_focus or "")
```

- [ ] **Step 2: Smoke-test the round trip in the browser**

Boot the app. Navigate to Project Setup. Fill the form and click Save. Switch to Edit Data, switch back to Project Setup — every field should have the values you saved. Now navigate to Templates and load a different template (e.g. Coastal Tourism). Switch to Project Setup — the form should reflect the loaded template's metadata (it'll be empty if the template wasn't migrated yet; Task 12 handles that).

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/pims_project.py
git commit -m "feat(pims): load-form-values effect populates form on project_metadata changes"
```

---

## Task 12: Re-emit the four built-in templates with PIMS metadata

**Files:**
- Modify: `sespy/templates/coastal_tourism.json`
- Modify: `sespy/templates/minimal_demo.json`
- Modify: `sespy/templates/offshore_wind.json`
- Modify: `sespy/templates/small_scale_fisheries.json`

Each template's `metadata` block needs the five new fields populated with sensible domain-specific values, plus a `schema_version: 2` bump.

- [ ] **Step 1: Update `coastal_tourism.json`**

Open `sespy/templates/coastal_tourism.json`. Find the `metadata` object. Add (or update if any are present) these fields, leaving existing fields like `name`/`description`/`created_at` unchanged:

```json
        "da_site": "Tuscan Archipelago",
        "focal_issue": "Pressure on coastal habitats from increasing tourism activity and the trade-offs between economic development and environmental protection.",
        "definition_statement": "A multi-stakeholder analysis of how seasonal tourism flows interact with marine and coastal ecosystems on the Tuscan Archipelago, scoped to a five-year planning horizon.",
        "temporal_scale": "Yearly",
        "spatial_scale": "Local",
        "system_in_focus": "Coastal tourism economy and adjacent marine and intertidal habitats.",
        "schema_version": 2
```

- [ ] **Step 2: Update `minimal_demo.json`**

```json
        "da_site": "",
        "focal_issue": "Demonstration template for SESPy onboarding.",
        "definition_statement": "A small synthetic SES used to walk first-time users through the create / visualize / analyze / report workflow.",
        "temporal_scale": "Yearly",
        "spatial_scale": "Local",
        "system_in_focus": "Generic demonstration system.",
        "schema_version": 2
```

- [ ] **Step 3: Update `offshore_wind.json`**

```json
        "da_site": "Macaronesia",
        "focal_issue": "Spatial conflict between offshore renewable-energy development and marine biodiversity in EU coastal waters.",
        "definition_statement": "An analysis of how offshore wind farm siting decisions interact with seabird, cetacean, and benthic ecosystem services in the Macaronesia demonstration area.",
        "temporal_scale": "Yearly",
        "spatial_scale": "Regional",
        "system_in_focus": "Offshore wind farms and adjacent marine ecosystems.",
        "schema_version": 2
```

- [ ] **Step 4: Update `small_scale_fisheries.json`**

```json
        "da_site": "Arctic Northeast Atlantic",
        "focal_issue": "Sustainability of small-scale coastal fisheries under climate-change and overfishing pressures.",
        "definition_statement": "An exploration of how local fishing communities, fish stocks, and policy levers interact in the Arctic Northeast Atlantic demonstration area, scoped to the next decade.",
        "temporal_scale": "Decadal",
        "spatial_scale": "Local",
        "system_in_focus": "Small-scale coastal fisheries, target species, and dependent livelihoods.",
        "schema_version": 2
```

- [ ] **Step 5: Validate the templates load**

```bash
micromamba run -n shiny python -c "
from sespy.templates import list_templates
from sespy.persistent_storage import load_project
infos = list_templates()
for info in infos:
    p = load_project(info.file)
    assert p.metadata.schema_version == 2, info.file
    assert p.metadata.focal_issue, f'{info.file} has empty focal_issue'
print(f'{len(infos)} templates load with schema 2 + non-empty focal_issue')
"
```
Expected: `4 templates load with schema 2 + non-empty focal_issue`.

- [ ] **Step 6: Browser-smoke the round-trip**

Boot the app. Load each template via Templates → click Load. Navigate to Project Setup. Verify all five PIMS fields are populated with the per-domain values from the JSON.

- [ ] **Step 7: Commit**

```bash
git add sespy/templates/coastal_tourism.json sespy/templates/minimal_demo.json sespy/templates/offshore_wind.json sespy/templates/small_scale_fisheries.json
git commit -m "templates: populate PIMS metadata fields, bump schema_version to 2"
```

---

## Task 13: E2e test suite

**Files:**
- Create: `tests/test_pims_project_e2e.py`

Two scenarios, mirroring the script style of `test_bot_e2e.py`. Boot the app on port 8000, run the script.

- [ ] **Step 1: Create `tests/test_pims_project_e2e.py`**

```python
"""E2E for the PIMS Project Setup module.

Two cases:
  1. Save and round-trip — fill all 5 PIMS fields, click Save, switch
     modules, switch back, assert form values persisted + status block
     shows a recent save timestamp.
  2. Template load populates PIMS form — load Coastal Tourism, navigate
     to PIMS, assert template's metadata fields populate the form.
"""
import asyncio
from playwright.async_api import async_playwright


async def _open_pims(page):
    await page.wait_for_selector("#sespy_nav_pims", timeout=15000)
    await page.click("#sespy_nav_pims")
    await page.wait_for_timeout(1500)


async def case_save_and_round_trip(page):
    print("\n=== case 1: PIMS save and round-trip ===")
    await _open_pims(page)

    # Fill the form.
    await page.fill("#pims-project_name", "E2E Test Project")
    await page.select_option("#pims-da_site", "Macaronesia")
    await page.fill("#pims-focal_issue", "E2E focal issue text.")
    await page.fill("#pims-definition_statement", "E2E definition statement.")
    await page.select_option("#pims-temporal_scale", "Yearly")
    await page.select_option("#pims-spatial_scale", "Regional")
    await page.fill("#pims-system_in_focus", "E2E system in focus.")
    await page.wait_for_timeout(400)

    # Click Save.
    await page.click("#pims-save_project_info")
    await page.wait_for_timeout(1000)

    # The "Last saved at" block should now show a non-empty timestamp.
    saved_text = await page.evaluate(
        "() => {"
        " const dts = document.querySelectorAll('#pims-current_status dt');"
        " for (let i=0; i<dts.length; ++i) {"
        "   if (dts[i].textContent.trim().toLowerCase().includes('last saved'))"
        "     return dts[i].nextElementSibling.textContent.trim();"
        " }"
        " return null;"
        "}"
    )
    assert saved_text and "Not saved" not in saved_text, (
        f"expected non-empty last-saved timestamp, got {saved_text!r}"
    )

    # Switch to Edit Data and back.
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(800)
    await page.click("#sespy_nav_pims")
    await page.wait_for_timeout(1500)

    # Form values should still be present.
    name = await page.evaluate("() => document.querySelector('#pims-project_name').value")
    assert name == "E2E Test Project", f"name lost on round-trip: {name!r}"

    da = await page.evaluate("() => document.querySelector('#pims-da_site').value")
    assert da == "Macaronesia", f"da_site lost: {da!r}"

    focal = await page.evaluate("() => document.querySelector('#pims-focal_issue').value")
    assert focal == "E2E focal issue text.", f"focal_issue lost: {focal!r}"

    temporal = await page.evaluate("() => document.querySelector('#pims-temporal_scale').value")
    assert temporal == "Yearly", f"temporal_scale lost: {temporal!r}"

    spatial = await page.evaluate("() => document.querySelector('#pims-spatial_scale').value")
    assert spatial == "Regional", f"spatial_scale lost: {spatial!r}"

    print(f"  ok (last saved: {saved_text})")


async def case_template_loads_pims_metadata(page):
    print("\n=== case 2: template load populates PIMS form ===")
    # Load the Coastal Tourism template via the Templates picker.
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    assert "Coastal Tourism" in cards, f"Coastal Tourism missing: {cards}"
    idx = cards.index("Coastal Tourism")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)

    await _open_pims(page)
    da = await page.evaluate("() => document.querySelector('#pims-da_site').value")
    assert da == "Tuscan Archipelago", f"expected Tuscan Archipelago, got {da!r}"
    focal = await page.evaluate("() => document.querySelector('#pims-focal_issue').value")
    assert focal and "tourism" in focal.lower(), f"focal_issue not populated: {focal!r}"
    print(f"  ok (da={da})")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_save_and_round_trip(page)
        await case_template_loads_pims_metadata(page)

        await page.screenshot(path="tests/screenshots/pims_project_e2e.png")
        print("\npims project setup e2e: 2 cases passed")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the e2e against a running app**

Boot the app:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
(Run with `run_in_background=True`.)

Wait for it:
```bash
micromamba run -n shiny python .tmp/wait_port.py
```

Run the test:
```bash
micromamba run -n shiny python tests/test_pims_project_e2e.py
```
Expected: `pims project setup e2e: 2 cases passed`.

If failures: common causes are timing flakes (bump `wait_for_timeout` values), nav id mismatches (`#sespy_nav_pims` requires Task 8 to be done correctly), empty-form values if Task 11 isn't loading metadata back (or Task 6 didn't wire `templates_server` to call `project_metadata.set`), or `page.select_option` not driving the select as expected if Shiny renders it with a selectize wrapper instead of a plain `<select>`. If the last is the case, swap to the selectize-style click pattern from `tests/test_bot_e2e.py`:

```python
await page.click("#pims-da_site + .selectize-control")
await page.wait_for_timeout(300)
await page.click(".selectize-dropdown-content [data-value='Macaronesia']")
```

- [ ] **Step 3: Stop the background server and commit**

```bash
git add tests/test_pims_project_e2e.py
git commit -m "test(pims): e2e coverage for save round-trip + template load"
```

---

## Task 14: README update + final verification

**Files:**
- Modify: `README.md`

Bump the module count and table; bump test counts.

- [ ] **Step 1: Bump module count from 14 to 15**

In `README.md`, replace the only occurrence of `**14 modules**` with `**15 modules**`. Also replace `### Modules (14)` with `### Modules (15)`.

- [ ] **Step 2: Add a row to the modules table**

Insert this row at the TOP of the modules table (immediately after the header row separator):

```markdown
| **PIMS Project Setup** (`sespy/modules/pims_project.py`) | `modules/pims_module.R` (PROJECT SETUP) | Two-column form for project context: name, demonstration area, focal issue, definition statement, temporal/spatial scale, system in focus. Persists to project metadata via a parallel `project_metadata` reactive. |
```

- [ ] **Step 3: Bump test counts**

Find the line `103 unit tests + 16 e2e scripts.` and change it to:

```
108 unit tests + 17 e2e scripts.
```

(103 + 5 new unit tests in `test_data_structure.py` = 108; 16 + 1 new e2e = 17.)

- [ ] **Step 4: Run the unit suite to confirm no regressions**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py
```
Expected: `108 passed`.

- [ ] **Step 5: Verify the app imports cleanly**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): note PIMS Project Setup — now 15 modules"
```

- [ ] **Step 7: Final branch summary**

```bash
git log --oneline main..feat/pims-project-setup
```
Expected: 14 commits — one per task across Tasks 1–14 (Task 0 is read-only and does not commit). Each commit message should be self-descriptive.

---

## Definition of done

- All 14 tasks complete.
- `feat/pims-project-setup` branch contains 14 commits (one per task; Task 0 is read-only).
- E2e suite (`tests/test_pims_project_e2e.py`) prints `2 cases passed`.
- App boots cleanly; "Project Setup" appears as the **first** nav item; the workflow stepper shows **Setup** as the first stage; clicking Project Setup renders the two-column form.
- Save round-trip works: filling fields + click Save updates `project_metadata`; switching modules and back preserves form values.
- All four templates load with their PIMS metadata populating the form.
- Saving a project file via Quick Actions includes the PIMS metadata in the JSON; reloading that file rehydrates the PIMS form.
- Autosave includes PIMS metadata; on session restart the recovery toast restores it.
- README reflects 15 modules, 108 unit tests, 17 e2e scripts.
- Existing unit-test suite still passes (no regressions).

## Out of scope (deferred to future work)

- Spec §3 mentions a `@render.ui project_status_text` renderer that would echo the saved project name as a separate header. Dropped from this plan as YAGNI: the form's `project_name` text input already shows the live name and the card header already shows "Project Setup".
- Promoting `project_data` to wrap full `Project` envelope (Option A from the architectural decision in this plan's header). Deferred — would simplify a `project_metadata` lookup to `project_data.get().metadata` everywhere but requires touching every analysis module's `project_data.get()` callsite. Worth doing as its own focused refactor PR after PIMS ships.
- Stakeholders sub-module (`pims_stakeholder_module.R`) — its own future spec/plan, ~1 week of work.
- The 3 placeholder PIMS sub-modules (Resources & Risks, Data Management, Evaluation) — explicitly omitted; they're "Coming soon" stubs in R itself.
- Dashboard brand block live-update on project name change — listed as a §9 risk in the spec; if the brand block needs explicit subscription to `event_bus.project_change` or `project_metadata`, defer to a follow-up commit on `main`.
