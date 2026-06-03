# AI-ISA Wizard SP1 Implementation Plan

> **Status: Implemented** · 16 plan tasks shipped on `feat/ai-isa-wizard-sp1`, fast-forwarded to `main` 2026-05-01 (head `dfedd28`). The branch tip `dfedd28` is a follow-up commit that strengthened e2e coverage gaps flagged in final review (added before the fast-forward, so it appears as both the merge tip and the named follow-up). Subsequent post-SP1 cleanup commit `d14960e` (2026-05-02) renamed `REGIONAL_SEAS_PLACEHOLDER` → `REGIONAL_SEAS` (a tech-debt cleanup the SP2 spec deferred to "the start of SP3" but landed sooner as a focused PR). The plan's 9 references to `REGIONAL_SEAS_PLACEHOLDER` are stale post-rename, but the plan is a frozen operational artifact and was correct at execution time.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the wizard scaffolding sub-project of R's AI-Assisted SES Creation feature into SESPy as module #16 — a 12-step guided wizard that builds a DAPSI(W)R(M) framework with live writes to `project_data` per step, a confirmation modal that protects existing SES data, and a stub `suggest_connections()` ready for SP2-SP4 to fill in.

**Architecture:** Two new files: `sespy/wizard.py` (pure data — 12-step flow + element-type map + suggest_connections stub) and `sespy/modules/ai_isa_wizard.py` (Shiny module — UI dispatch by step archetype + state machine + confirmation modal). Two new dataclasses in `sespy/data_structure.py` (`WizardState`, `ConnectionSuggestion`). One new shared helper `sespy/utils.py::next_id` (promoted from a private copy in `isa_data_entry.py`). The module reads/writes a single `project_data: reactive.Value[Project]` reactive (post-2026-04-30 refactor); no parallel reactives.

**Tech Stack:** Python 3.11, Shiny for Python, dataclasses, json, Playwright (e2e). Existing micromamba env `shiny`. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-01-ai-isa-wizard-sp1-design.md`](../specs/2026-05-01-ai-isa-wizard-sp1-design.md) (committed at `0d06900`; 514 LOC after 6 review rounds).

**Sub-project context.** This is **SP1 of 4**. SP2 ports the regional-seas knowledge base (replacing SP1's placeholder dict). SP3 implements TF-IDF + rule-based connection scoring (replacing the `[]` stub). SP4 adds an optional Claude API backend behind a settings switch. Each sub-project gets its own spec/plan/branch. SP1 ships a useful feature on its own (guided manual entry — connection-review step renders an empty table with a "no suggestions yet" placeholder).

---

## Task 0: Verify environment and branch

- [ ] **Step 1: Confirm working tree is clean and on `main`**

```bash
git status --short
git branch --show-current
```
Expected: no output from `git status --short` (or only `?? .claude/`, `?? .tmp/`); branch is `main`.

- [ ] **Step 2: Cut the feature branch**

```bash
git checkout -b feat/ai-isa-wizard-sp1
```
Expected: `Switched to a new branch 'feat/ai-isa-wizard-sp1'`.

- [ ] **Step 3: Confirm spec and reference plan exist**

```bash
ls docs/superpowers/specs/2026-05-01-ai-isa-wizard-sp1-design.md
ls docs/superpowers/plans/2026-04-29-pims-project-setup.md
```
Expected: both paths print without "No such file" errors.

- [ ] **Step 4: Verify the test suite is green at start**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py
```
Expected: `108 passed` (or higher — count drifts as tests are added).

- [ ] **Step 5: Verify the wait-for-port helper exists**

```bash
ls .tmp/wait_port.py
```
Expected: file exists. If missing, create it with this content (gitignored, used in Tasks 7, 15):

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

---

## Task 1: Promote `_next_id` to a public shared helper

**Files:**
- Create: `sespy/utils.py`
- Create: `tests/test_utils.py`
- Modify: `sespy/modules/isa_data_entry.py:31-39` (delete private `_next_id`); modify line ~201 (replace call site)

The wizard module and the existing `isa_data_entry` module both need next-id generation. Today only `isa_data_entry` has it as a private `_next_id`. Promote to a single public location, delete the duplicate, update the existing call site. **Three implementations cannot diverge if there is only one.**

- [ ] **Step 1: Create `tests/test_utils.py` with four failing tests**

```python
"""Unit tests for sespy.utils — small shared helpers."""
from __future__ import annotations

from sespy.utils import next_id


def test_next_id_empty_list_returns_001():
    assert next_id([], "D") == "D001"


def test_next_id_fills_lowest_gap():
    """Gap-filling semantics — matches the existing _next_id behavior in
    isa_data_entry.py. ["D001","D003"] → "D002" (fills the gap),
    NOT "D004" (max-plus-one). Preserves stable ids across deletions."""
    assert next_id(["D001", "D003"], "D") == "D002"


def test_next_id_appends_when_contiguous():
    assert next_id(["D001", "D002", "D003"], "D") == "D004"


def test_next_id_ignores_other_prefixes():
    assert next_id(["D001", "P002", "A005"], "D") == "D002"
    assert next_id(["D001", "P002", "A005"], "P") == "P003"
    assert next_id(["D001", "P002", "A005"], "MPF") == "MPF001"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_utils.py -v
```
Expected: 4 failures with `ModuleNotFoundError: No module named 'sespy.utils'`.

- [ ] **Step 3: Create `sespy/utils.py`**

```python
"""Shared utilities — pure-Python helpers used across multiple modules.

This module has no Shiny imports and no other intra-project dependencies
beyond the standard library. Anything that's a useful pure-data helper
shared by 2+ modules can land here.
"""
from __future__ import annotations


def next_id(existing_ids: list[str], prefix: str) -> str:
    """Return the next available id for a given DAPSIWRM type prefix.

    Uses gap-filling semantics: scans `existing_ids` for matching
    `<prefix><N>` ids, then returns `<prefix><N>` for the lowest N
    starting from 1 that's not in use, padded to 3 digits. This
    preserves stable id reuse after deletions and matches the
    behavior of the original `_next_id` in `isa_data_entry.py`.

    Examples:
        >>> next_id([], "D")
        'D001'
        >>> next_id(["D001", "D003"], "D")  # gap at D002
        'D002'
        >>> next_id(["D001", "D002", "D003"], "D")
        'D004'
        >>> next_id(["P001"], "D")
        'D001'
    """
    used = {
        int(eid[len(prefix):])
        for eid in existing_ids
        if eid.startswith(prefix) and eid[len(prefix):].isdigit()
    }
    n = 1
    while n in used:
        n += 1
    return f"{prefix}{n:03d}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_utils.py -v
```
Expected: `4 passed`.

- [ ] **Step 5: Delete the private `_next_id` from `isa_data_entry.py`**

In `sespy/modules/isa_data_entry.py`, locate the entire `_next_id` function definition (around lines 31-39 — find by name, the body uses gap-filling semantics with a `used = {...}` set followed by `while n in used: n += 1`). Delete the whole function from `def _next_id(...)` through its `return` statement.

In its place, add an import at the top of the file (just below the existing `from ..data_structure import ...` line):

```python
from ..utils import next_id
```

- [ ] **Step 6: Update the call site in `isa_data_entry.py`**

Find the single existing call to `_next_id(...)` (around line 201). Change it from:

```python
id=_next_id(existing, _prefix_for(el_type)),
```

to:

```python
id=next_id(existing, _prefix_for(el_type)),
```

- [ ] **Step 7: Run the existing tests to confirm no regression**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py tests/test_persistent_storage.py tests/test_utils.py -v
```
Expected: 5 (data_structure) + N (persistent_storage) + 4 (utils) tests pass.

- [ ] **Step 8: Boot the app and click into Edit Data to confirm `next_id` still works at runtime**

```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
(Run with `run_in_background=True`.) Open `http://127.0.0.1:8000`, navigate to Edit Data, click "Add Element" with a label like "Test driver" and type Drivers. Confirm a new element appears in the table with id `D00<N+1>`. Stop the server.

- [ ] **Step 9: Commit**

```bash
git add sespy/utils.py sespy/modules/isa_data_entry.py tests/test_utils.py
git commit -m "refactor(utils): promote _next_id to public sespy.utils.next_id"
```

---

## Task 2: Add `WizardState` and `ConnectionSuggestion` dataclasses + tests

**Files:**
- Modify: `sespy/data_structure.py` — append two new dataclasses
- Modify: `tests/test_data_structure.py` — append three new tests

These are the contract types between the wizard module (SP1) and the future scoring backends (SP3 TF-IDF, SP4 Claude API). SP1 only constructs and reads them; doesn't mutate.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_data_structure.py`:

```python
def test_wizard_state_defaults():
    from sespy.data_structure import WizardState
    state = WizardState()
    assert state.regional_sea == ""
    assert state.ecosystem_type == ""
    assert state.countries == []
    assert state.main_issue == []
    assert state.elements == []


def test_wizard_state_construction():
    from sespy.data_structure import WizardState, Element
    elements = [Element(id="D001", label="Tourism", type="Drivers")]
    state = WizardState(
        regional_sea="baltic",
        ecosystem_type="open_coast",
        countries=["Lithuania", "Poland"],
        main_issue=["Eutrophication"],
        elements=elements,
    )
    assert state.regional_sea == "baltic"
    assert len(state.elements) == 1
    assert state.elements[0].id == "D001"


def test_connection_suggestion_construction():
    from sespy.data_structure import ConnectionSuggestion
    s = ConnectionSuggestion(
        source="D001", target="P001", polarity="+",
        confidence=0.7, rationale="Tourism drives anchor damage."
    )
    assert s.source == "D001"
    assert s.target == "P001"
    assert s.polarity == "+"
    assert s.confidence == 0.7
    assert "anchor" in s.rationale.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: 3 new failures with `ImportError: cannot import name 'WizardState' from 'sespy.data_structure'` (and similar for `ConnectionSuggestion`).

- [ ] **Step 3: Append the two dataclasses to `sespy/data_structure.py`**

Append at the END of `sespy/data_structure.py` (after the existing `filter_elements` function):

```python


# ---------------------------------------------------------------------------
# AI-ISA Wizard contract types (added with SP1).
#
# WizardState is constructed at step-11 entry from wizard_answers + the
# current project_data and passed to suggest_connections(). SP3 (TF-IDF)
# and SP4 (Claude API) consume it as a frozen snapshot.
#
# ConnectionSuggestion is what suggest_connections() returns. It mirrors
# Connection's source/target/polarity but adds confidence (float 0..1) and
# rationale (free-text). SP3/SP4 must define the float→int confidence
# mapping when converting accepted suggestions to Connection objects (see
# spec §9).
# ---------------------------------------------------------------------------


@dataclass
class WizardState:
    """Snapshot of the wizard's accumulated context at the moment
    suggest_connections() is invoked. Holds the current SES element list
    plus the wizard-only ephemeral fields (countries, main_issue) that
    don't persist to the project file."""
    regional_sea: str = ""
    ecosystem_type: str = ""
    countries: list[str] = field(default_factory=list)
    main_issue: list[str] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)


@dataclass
class ConnectionSuggestion:
    """One suggested connection from a scoring backend (SP3 or SP4).
    SP1 returns an empty list of these from the stub."""
    source: str  # element id
    target: str  # element id
    polarity: str  # "+" reinforcing, "-" opposing
    confidence: float  # 0..1
    rationale: str  # short string explaining the suggestion
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_data_structure.py -v
```
Expected: `8 passed` (5 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add sespy/data_structure.py tests/test_data_structure.py
git commit -m "feat(schema): add WizardState and ConnectionSuggestion dataclasses"
```

---

## Task 3: Create `sespy/wizard.py` — pure-data step flow + stub

**Files:**
- Create: `sespy/wizard.py`
- Create: `tests/test_wizard.py`

`sespy/wizard.py` is a pure-Python file (no Shiny imports). It holds the 12-step flow as data, the element-type mapping, the placeholder regional-seas KB (small SP1 mock — SP2 will replace), and the `suggest_connections()` stub. The module file in Task 5 imports from this.

- [ ] **Step 1: Create `tests/test_wizard.py` with failing tests**

```python
"""Unit tests for sespy.wizard — pure-data wizard flow."""
from __future__ import annotations

from sespy.wizard import (
    WIZARD_STEPS,
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS_PLACEHOLDER,
    suggest_connections,
)
from sespy.data_structure import WizardState


def test_wizard_steps_count_is_12():
    assert len(WIZARD_STEPS) == 12


def test_wizard_steps_indices_are_0_to_11():
    indices = [s["step"] for s in WIZARD_STEPS]
    assert indices == list(range(12))


def test_wizard_steps_targets_match_spec():
    targets = [s["target"] for s in WIZARD_STEPS]
    assert targets == [
        "regional_sea", "ecosystem_type", "countries", "main_issue",
        "drivers", "activities", "pressures", "states",
        "impacts", "welfare", "responses", "connections",
    ]


def test_wizard_steps_archetypes():
    archetypes = [s["archetype"] for s in WIZARD_STEPS]
    assert archetypes == [
        "choice_one", "choice_one", "choice_many", "choice_many",
        "freeform_multiple", "freeform_multiple", "freeform_multiple",
        "freeform_multiple", "freeform_multiple", "freeform_multiple",
        "freeform_multiple", "connection_review",
    ]


def test_element_type_map_matches_constants():
    """The mapping must match constants.ELEMENT_ID_PREFIX semantics —
    impacts→Ecosystem Services, welfare→Goods & Benefits."""
    assert ELEMENT_TYPE_MAP["drivers"] == "Drivers"
    assert ELEMENT_TYPE_MAP["activities"] == "Activities"
    assert ELEMENT_TYPE_MAP["pressures"] == "Pressures"
    assert ELEMENT_TYPE_MAP["states"] == "Marine Processes & Functioning"
    assert ELEMENT_TYPE_MAP["impacts"] == "Ecosystem Services"
    assert ELEMENT_TYPE_MAP["welfare"] == "Goods & Benefits"
    assert ELEMENT_TYPE_MAP["responses"] == "Responses"


def test_regional_seas_placeholder_has_at_least_baltic():
    assert "baltic" in REGIONAL_SEAS_PLACEHOLDER
    baltic = REGIONAL_SEAS_PLACEHOLDER["baltic"]
    assert "name" in baltic
    assert "ecosystem_types" in baltic
    assert "countries" in baltic
    assert "common_issues" in baltic


def test_suggest_connections_stub_returns_empty():
    state = WizardState(regional_sea="baltic", ecosystem_type="open_coast")
    assert suggest_connections(state) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_wizard.py -v
```
Expected: 7 failures with `ModuleNotFoundError: No module named 'sespy.wizard'`.

- [ ] **Step 3: Create `sespy/wizard.py`**

```python
"""Pure-data definition of the AI-ISA wizard flow.

This module has NO Shiny imports — it's a flat data file plus the
suggest_connections() stub. The Shiny module at
`sespy/modules/ai_isa_wizard.py` imports from here; SP3 and SP4 will
later replace `suggest_connections` with real scoring backends.

The 12 steps mirror R's `ai_isa_assistant_module.R` question_flow.R
1:1 by step index and target. The 6 distinct R step types collapse to
4 widget archetypes (choice_one, choice_many, freeform_multiple,
connection_review).

Element-type mapping for steps 4-10 (the freeform_multiple steps that
write Element objects to project_data.isa_data.elements):
- impacts → Ecosystem Services (the impact ON ecosystem services)
- welfare → Goods & Benefits (welfare derived from goods & benefits)
This matches `constants.ELEMENT_ID_PREFIX` (impacts→ES, welfare→GB).
"""
from __future__ import annotations

from typing import Any

from .data_structure import WizardState, ConnectionSuggestion


# ---------------------------------------------------------------------------
# Wizard step flow — 12 steps as a list of dicts. Each dict has:
#   step:       int (0-11)
#   title_key:  str — i18n key suffix (resolved as wizard.step_<key>_title)
#   archetype:  str — one of choice_one, choice_many, freeform_multiple, connection_review
#   target:     str — key in wizard_answers + element-type mapping (for steps 4-10)
# ---------------------------------------------------------------------------

WIZARD_STEPS: list[dict[str, Any]] = [
    {"step": 0,  "title_key": "regional_sea",       "archetype": "choice_one",         "target": "regional_sea"},
    {"step": 1,  "title_key": "ecosystem",          "archetype": "choice_one",         "target": "ecosystem_type"},
    {"step": 2,  "title_key": "countries",          "archetype": "choice_many",        "target": "countries"},
    {"step": 3,  "title_key": "main_issue",         "archetype": "choice_many",        "target": "main_issue"},
    {"step": 4,  "title_key": "drivers",            "archetype": "freeform_multiple",  "target": "drivers"},
    {"step": 5,  "title_key": "activities",         "archetype": "freeform_multiple",  "target": "activities"},
    {"step": 6,  "title_key": "pressures",          "archetype": "freeform_multiple",  "target": "pressures"},
    {"step": 7,  "title_key": "states",             "archetype": "freeform_multiple",  "target": "states"},
    {"step": 8,  "title_key": "impacts",            "archetype": "freeform_multiple",  "target": "impacts"},
    {"step": 9,  "title_key": "welfare",            "archetype": "freeform_multiple",  "target": "welfare"},
    {"step": 10, "title_key": "responses",          "archetype": "freeform_multiple",  "target": "responses"},
    {"step": 11, "title_key": "connection_review",  "archetype": "connection_review",  "target": "connections"},
]


# ---------------------------------------------------------------------------
# Wizard target → SESPy Element.type mapping for steps 4-10.
#
# Authoritative source: sespy/constants.py::ELEMENT_ID_PREFIX. The id
# prefixes there encode the relationship (impacts→ES→Ecosystem Services,
# welfare→GB→Goods & Benefits). This dict makes the mapping explicit at
# the call site.
# ---------------------------------------------------------------------------

ELEMENT_TYPE_MAP: dict[str, str] = {
    "drivers": "Drivers",
    "activities": "Activities",
    "pressures": "Pressures",
    "states": "Marine Processes & Functioning",
    "impacts": "Ecosystem Services",
    "welfare": "Goods & Benefits",
    "responses": "Responses",
}


# ---------------------------------------------------------------------------
# Regional-seas placeholder (SP1 mock; SP2 ports the real KB).
#
# Shape:
#   {
#     "<slug>": {
#       "name": "<display name>",
#       "ecosystem_types": [...],
#       "countries": [...],
#       "common_issues": [...],
#     },
#     ...
#   }
#
# SP2 must produce data with this same shape to satisfy SP1's renderer.
# Shape is the SP1→SP2 contract (see spec §9).
# ---------------------------------------------------------------------------

REGIONAL_SEAS_PLACEHOLDER: dict[str, dict[str, Any]] = {
    "baltic": {
        "name": "Baltic Sea",
        "ecosystem_types": ["Open coast", "Archipelago", "Estuary", "Coastal lagoon", "Offshore waters"],
        "countries": ["Denmark", "Estonia", "Finland", "Germany", "Latvia", "Lithuania", "Poland", "Russia", "Sweden"],
        "common_issues": ["Eutrophication", "Overfishing", "Pollution", "Invasive species", "Climate change"],
    },
    "mediterranean": {
        "name": "Mediterranean Sea",
        "ecosystem_types": ["Open coast", "Island", "Coastal lagoon", "Rocky shore", "Sandy beach", "Seagrass meadow"],
        "countries": ["Italy", "Spain", "France", "Greece", "Croatia", "Tunisia", "Egypt"],
        "common_issues": ["Overfishing", "Coastal development", "Tourism pressure", "Marine litter", "Invasive species"],
    },
    "north_sea": {
        "name": "North Sea",
        "ecosystem_types": ["Open coast", "Estuary", "Tidal flat", "Offshore waters", "Sandy beach"],
        "countries": ["United Kingdom", "Norway", "Denmark", "Germany", "Netherlands", "Belgium", "France"],
        "common_issues": ["Overfishing", "Oil and gas extraction", "Shipping", "Wind energy development", "Eutrophication"],
    },
    "irish_sea": {
        "name": "Irish Sea",
        "ecosystem_types": ["Open coast", "Estuary", "Coastal lagoon", "Rocky shore", "Sandy beach"],
        "countries": ["Ireland", "United Kingdom"],
        "common_issues": ["Overfishing", "Coastal development", "Shipping", "Marine litter", "Eutrophication"],
    },
    "macaronesia": {
        "name": "Macaronesia",
        "ecosystem_types": ["Open coast", "Volcanic island", "Rocky shore", "Offshore waters"],
        "countries": ["Portugal", "Spain"],
        "common_issues": ["Tourism pressure", "Overfishing", "Coastal development", "Climate change"],
    },
}


# ---------------------------------------------------------------------------
# suggest_connections — SP1 stub.
#
# SP3 (TF-IDF + rules) and SP4 (Claude API) replace this with real
# implementations. The signature is the contract: a WizardState in,
# a list of ConnectionSuggestion out. SP1 always returns [].
# ---------------------------------------------------------------------------

def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """Return suggested connections for the wizard's connection-review step.

    SP1 stub: returns []. SP3 fills via TF-IDF + polarity rules; SP4 fills
    via Claude API. SP1's connection-review renderer surfaces an empty
    table with a placeholder message ("No suggestions yet — install SP3
    or SP4 backend to enable AI-assisted connection generation").
    """
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_wizard.py -v
```
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add sespy/wizard.py tests/test_wizard.py
git commit -m "feat(wizard): pure-data step flow, element-type map, KB placeholder, stub"
```

---

## Task 4: Add ~50 i18n keys for the wizard

**Files:**
- Modify: `sespy/translations/core.json`

Add the wizard's i18n keys INSIDE the `"translation"` wrapper (the PIMS gotcha — keys at top level are silently invisible to `t()`). English values first; the other 8 languages get the same English value as a placeholder, mirroring the BOT/PIMS pattern.

- [ ] **Step 1: Insert `nav.wizard` after `"nav.pims"` (or near it)**

Find the line containing `"nav.pims"` in `sespy/translations/core.json`. Insert immediately after its closing `}`:

```json
    "nav.wizard": {
        "en": "SES Wizard",
        "es": "SES Wizard", "fr": "SES Wizard", "de": "SES Wizard",
        "lt": "SES Wizard", "pt": "SES Wizard", "it": "SES Wizard",
        "no": "SES Wizard", "el": "SES Wizard"
    },
```

- [ ] **Step 2: Insert all `wizard.*` keys after the last `pims.*` key**

Find `"pims.schema_version"` — it's the LAST key inside the `"translation"` wrapper, so the closing `}` of its value is followed by no comma (the next line closes the wrapper). To insert new keys after it without breaking JSON syntax:

1. **Add a trailing comma** to the closing `}` of `pims.schema_version`'s value object — change `}` (last char on its line) to `},`.
2. Insert the `wizard.*` block below, FOLLOWED BY the 24 step-title/question keys produced from the table at the end of this step.
3. The very LAST key in the entire combined insertion (which will be `wizard.step_11_question` once the step keys are appended) MUST have its closing `}` with NO trailing comma — otherwise JSON parse fails ("Expecting property name enclosed in double quotes").
4. Within the block below, every key ends with `},` (including the final `wizard.accept` — the step keys come after it via the table prose).
5. Step 3 below validates this with `python -c "import json; json.load(open(...))"`.

Insert this block after the now-comma-terminated `pims.schema_version` entry:

```json
    "wizard.title": {
        "en": "AI-Assisted SES Creation Wizard",
        "es": "AI-Assisted SES Creation Wizard", "fr": "AI-Assisted SES Creation Wizard", "de": "AI-Assisted SES Creation Wizard",
        "lt": "AI-Assisted SES Creation Wizard", "pt": "AI-Assisted SES Creation Wizard", "it": "AI-Assisted SES Creation Wizard",
        "no": "AI-Assisted SES Creation Wizard", "el": "AI-Assisted SES Creation Wizard"
    },
    "wizard.start": {
        "en": "Start Wizard",
        "es": "Start Wizard", "fr": "Start Wizard", "de": "Start Wizard",
        "lt": "Start Wizard", "pt": "Start Wizard", "it": "Start Wizard",
        "no": "Start Wizard", "el": "Start Wizard"
    },
    "wizard.back": {
        "en": "Back",
        "es": "Back", "fr": "Back", "de": "Back",
        "lt": "Back", "pt": "Back", "it": "Back",
        "no": "Back", "el": "Back"
    },
    "wizard.next": {
        "en": "Next",
        "es": "Next", "fr": "Next", "de": "Next",
        "lt": "Next", "pt": "Next", "it": "Next",
        "no": "Next", "el": "Next"
    },
    "wizard.finish": {
        "en": "Finish",
        "es": "Finish", "fr": "Finish", "de": "Finish",
        "lt": "Finish", "pt": "Finish", "it": "Finish",
        "no": "Finish", "el": "Finish"
    },
    "wizard.cancel": {
        "en": "Cancel",
        "es": "Cancel", "fr": "Cancel", "de": "Cancel",
        "lt": "Cancel", "pt": "Cancel", "it": "Cancel",
        "no": "Cancel", "el": "Cancel"
    },
    "wizard.replace": {
        "en": "Continue, replace it",
        "es": "Continue, replace it", "fr": "Continue, replace it", "de": "Continue, replace it",
        "lt": "Continue, replace it", "pt": "Continue, replace it", "it": "Continue, replace it",
        "no": "Continue, replace it", "el": "Continue, replace it"
    },
    "wizard.modal_title": {
        "en": "Replace existing SES?",
        "es": "Replace existing SES?", "fr": "Replace existing SES?", "de": "Replace existing SES?",
        "lt": "Replace existing SES?", "pt": "Replace existing SES?", "it": "Replace existing SES?",
        "no": "Replace existing SES?", "el": "Replace existing SES?"
    },
    "wizard.modal_body": {
        "en": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "es": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "fr": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "de": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "lt": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "pt": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "it": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "no": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard.",
        "el": "The wizard will replace your current SES. Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard."
    },
    "wizard.no_suggestions": {
        "en": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "es": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "fr": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "de": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "lt": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "pt": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "it": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "no": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation.",
        "el": "No connection suggestions yet — install the SP3 or SP4 scoring backend to enable AI-assisted connection generation."
    },
    "wizard.add_another": {
        "en": "Add another",
        "es": "Add another", "fr": "Add another", "de": "Add another",
        "lt": "Add another", "pt": "Add another", "it": "Add another",
        "no": "Add another", "el": "Add another"
    },
    "wizard.remove": {
        "en": "Remove",
        "es": "Remove", "fr": "Remove", "de": "Remove",
        "lt": "Remove", "pt": "Remove", "it": "Remove",
        "no": "Remove", "el": "Remove"
    },
    "wizard.validation_error": {
        "en": "Please provide at least one valid entry before continuing.",
        "es": "Please provide at least one valid entry before continuing.",
        "fr": "Please provide at least one valid entry before continuing.",
        "de": "Please provide at least one valid entry before continuing.",
        "lt": "Please provide at least one valid entry before continuing.",
        "pt": "Please provide at least one valid entry before continuing.",
        "it": "Please provide at least one valid entry before continuing.",
        "no": "Please provide at least one valid entry before continuing.",
        "el": "Please provide at least one valid entry before continuing."
    },
    "wizard.duplicate_error": {
        "en": "Duplicate entries — please make each value unique within this step.",
        "es": "Duplicate entries — please make each value unique within this step.",
        "fr": "Duplicate entries — please make each value unique within this step.",
        "de": "Duplicate entries — please make each value unique within this step.",
        "lt": "Duplicate entries — please make each value unique within this step.",
        "pt": "Duplicate entries — please make each value unique within this step.",
        "it": "Duplicate entries — please make each value unique within this step.",
        "no": "Duplicate entries — please make each value unique within this step.",
        "el": "Duplicate entries — please make each value unique within this step."
    },
    "wizard.regional_sea_label": {
        "en": "Which regional sea is your project focused on?",
        "es": "Which regional sea is your project focused on?", "fr": "Which regional sea is your project focused on?", "de": "Which regional sea is your project focused on?",
        "lt": "Which regional sea is your project focused on?", "pt": "Which regional sea is your project focused on?", "it": "Which regional sea is your project focused on?",
        "no": "Which regional sea is your project focused on?", "el": "Which regional sea is your project focused on?"
    },
    "wizard.ecosystem_type_label": {
        "en": "Which ecosystem type best describes your study area?",
        "es": "Which ecosystem type best describes your study area?", "fr": "Which ecosystem type best describes your study area?", "de": "Which ecosystem type best describes your study area?",
        "lt": "Which ecosystem type best describes your study area?", "pt": "Which ecosystem type best describes your study area?", "it": "Which ecosystem type best describes your study area?",
        "no": "Which ecosystem type best describes your study area?", "el": "Which ecosystem type best describes your study area?"
    },
    "wizard.countries_label": {
        "en": "Which countries are involved?",
        "es": "Which countries are involved?", "fr": "Which countries are involved?", "de": "Which countries are involved?",
        "lt": "Which countries are involved?", "pt": "Which countries are involved?", "it": "Which countries are involved?",
        "no": "Which countries are involved?", "el": "Which countries are involved?"
    },
    "wizard.main_issue_label": {
        "en": "What are the main issues your project addresses?",
        "es": "What are the main issues your project addresses?", "fr": "What are the main issues your project addresses?", "de": "What are the main issues your project addresses?",
        "lt": "What are the main issues your project addresses?", "pt": "What are the main issues your project addresses?", "it": "What are the main issues your project addresses?",
        "no": "What are the main issues your project addresses?", "el": "What are the main issues your project addresses?"
    },
    "wizard.placeholder_drivers": {
        "en": "List the drivers (e.g. tourism demand, fishing pressure)",
        "es": "List the drivers (e.g. tourism demand, fishing pressure)", "fr": "List the drivers (e.g. tourism demand, fishing pressure)", "de": "List the drivers (e.g. tourism demand, fishing pressure)",
        "lt": "List the drivers (e.g. tourism demand, fishing pressure)", "pt": "List the drivers (e.g. tourism demand, fishing pressure)", "it": "List the drivers (e.g. tourism demand, fishing pressure)",
        "no": "List the drivers (e.g. tourism demand, fishing pressure)", "el": "List the drivers (e.g. tourism demand, fishing pressure)"
    },
    "wizard.placeholder_activities": {
        "en": "List the human activities driving the system",
        "es": "List the human activities driving the system", "fr": "List the human activities driving the system", "de": "List the human activities driving the system",
        "lt": "List the human activities driving the system", "pt": "List the human activities driving the system", "it": "List the human activities driving the system",
        "no": "List the human activities driving the system", "el": "List the human activities driving the system"
    },
    "wizard.placeholder_pressures": {
        "en": "List the pressures the activities create",
        "es": "List the pressures the activities create", "fr": "List the pressures the activities create", "de": "List the pressures the activities create",
        "lt": "List the pressures the activities create", "pt": "List the pressures the activities create", "it": "List the pressures the activities create",
        "no": "List the pressures the activities create", "el": "List the pressures the activities create"
    },
    "wizard.placeholder_states": {
        "en": "List the marine processes and ecosystem states",
        "es": "List the marine processes and ecosystem states", "fr": "List the marine processes and ecosystem states", "de": "List the marine processes and ecosystem states",
        "lt": "List the marine processes and ecosystem states", "pt": "List the marine processes and ecosystem states", "it": "List the marine processes and ecosystem states",
        "no": "List the marine processes and ecosystem states", "el": "List the marine processes and ecosystem states"
    },
    "wizard.placeholder_impacts": {
        "en": "List the ecosystem services impacted",
        "es": "List the ecosystem services impacted", "fr": "List the ecosystem services impacted", "de": "List the ecosystem services impacted",
        "lt": "List the ecosystem services impacted", "pt": "List the ecosystem services impacted", "it": "List the ecosystem services impacted",
        "no": "List the ecosystem services impacted", "el": "List the ecosystem services impacted"
    },
    "wizard.placeholder_welfare": {
        "en": "List the goods and benefits people derive",
        "es": "List the goods and benefits people derive", "fr": "List the goods and benefits people derive", "de": "List the goods and benefits people derive",
        "lt": "List the goods and benefits people derive", "pt": "List the goods and benefits people derive", "it": "List the goods and benefits people derive",
        "no": "List the goods and benefits people derive", "el": "List the goods and benefits people derive"
    },
    "wizard.placeholder_responses": {
        "en": "List the responses (policies, measures, interventions)",
        "es": "List the responses (policies, measures, interventions)", "fr": "List the responses (policies, measures, interventions)", "de": "List the responses (policies, measures, interventions)",
        "lt": "List the responses (policies, measures, interventions)", "pt": "List the responses (policies, measures, interventions)", "it": "List the responses (policies, measures, interventions)",
        "no": "List the responses (policies, measures, interventions)", "el": "List the responses (policies, measures, interventions)"
    },
    "wizard.connection_suggestions_table": {
        "en": "Suggested connections",
        "es": "Suggested connections", "fr": "Suggested connections", "de": "Suggested connections",
        "lt": "Suggested connections", "pt": "Suggested connections", "it": "Suggested connections",
        "no": "Suggested connections", "el": "Suggested connections"
    },
    "wizard.confidence": {
        "en": "Confidence",
        "es": "Confidence", "fr": "Confidence", "de": "Confidence",
        "lt": "Confidence", "pt": "Confidence", "it": "Confidence",
        "no": "Confidence", "el": "Confidence"
    },
    "wizard.rationale": {
        "en": "Rationale",
        "es": "Rationale", "fr": "Rationale", "de": "Rationale",
        "lt": "Rationale", "pt": "Rationale", "it": "Rationale",
        "no": "Rationale", "el": "Rationale"
    },
    "wizard.accept": {
        "en": "Accept",
        "es": "Accept", "fr": "Accept", "de": "Accept",
        "lt": "Accept", "pt": "Accept", "it": "Accept",
        "no": "Accept", "el": "Accept"
    },
```

(The `accept_suggestion_<i>` checkbox uses the default unchecked state to mean "reject"; no separate `wizard.reject` key is needed.)

(Plus 12 step-title keys + 12 step-question keys appended in the same block — `wizard.step_0_title`, `wizard.step_0_question`, ... `wizard.step_11_title`, `wizard.step_11_question` — each with the standard 9-language structure with English placeholder for non-English. Use these English values:

| key | value |
|---|---|
| `wizard.step_0_title` / `_question` | `Regional Sea` / `Pick the regional sea your project covers.` |
| `wizard.step_1_title` / `_question` | `Ecosystem Type` / `Pick the ecosystem type that best fits.` |
| `wizard.step_2_title` / `_question` | `Countries` / `Which countries are involved?` |
| `wizard.step_3_title` / `_question` | `Main Issue` / `What are the main issues to address?` |
| `wizard.step_4_title` / `_question` | `Drivers` / `What human or natural drivers shape the system?` |
| `wizard.step_5_title` / `_question` | `Activities` / `What activities arise from those drivers?` |
| `wizard.step_6_title` / `_question` | `Pressures` / `What pressures do those activities create?` |
| `wizard.step_7_title` / `_question` | `States` / `What marine processes and states result?` |
| `wizard.step_8_title` / `_question` | `Impacts` / `What ecosystem services are impacted?` |
| `wizard.step_9_title` / `_question` | `Welfare` / `What goods and benefits do people derive?` |
| `wizard.step_10_title` / `_question` | `Responses` / `What responses (policies, measures) address the pressures?` |
| `wizard.step_11_title` / `_question` | `Review Connections` / `Review and accept the suggested connections.` |

Use the same 9-language placeholder pattern.)

- [ ] **Step 3: Validate JSON parses**

```bash
micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('parse: OK')"
```
Expected: `parse: OK`.

- [ ] **Step 4: Verify all wizard keys present**

```bash
micromamba run -n shiny python -c "
import json
# Read the 'translation' wrapper, NOT the top-level dict — keys at the
# top level are silently invisible to t() (the PIMS gotcha).
raw = json.load(open('sespy/translations/core.json', encoding='utf-8'))
trans = raw.get('translation', {})
required = ['nav.wizard', 'wizard.title', 'wizard.start', 'wizard.back', 'wizard.next', 'wizard.finish', 'wizard.cancel', 'wizard.replace', 'wizard.modal_title', 'wizard.modal_body', 'wizard.no_suggestions', 'wizard.add_another', 'wizard.remove', 'wizard.validation_error', 'wizard.duplicate_error', 'wizard.regional_sea_label', 'wizard.ecosystem_type_label', 'wizard.countries_label', 'wizard.main_issue_label', 'wizard.connection_suggestions_table', 'wizard.confidence', 'wizard.rationale', 'wizard.accept']
required += [f'wizard.placeholder_{tgt}' for tgt in ('drivers','activities','pressures','states','impacts','welfare','responses')]
required += [f'wizard.step_{i}_title' for i in range(12)] + [f'wizard.step_{i}_question' for i in range(12)]
missing = [k for k in required if k not in trans]
assert not missing, f'missing: {missing}'
print(f'{len(required)} keys present')
"
```
Expected: `54 keys present` (23 single + 7 placeholders + 24 step keys = 54). The variable `tgt` is used inside the comprehension to avoid shadowing the `t` translator function.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(wizard): add ~54 translation keys for SES Wizard"
```

---

## Task 5: Module skeleton (UI shell + empty effects)

**Files:**
- Create: `sespy/modules/ai_isa_wizard.py`

Build the module file with empty placeholders. The Shiny module receives `project_data` and `event_bus`. Tasks 8-14 fill in the effects and renderers. The skeleton is enough to import and register.

- [ ] **Step 1: Create `sespy/modules/ai_isa_wizard.py`**

```python
"""AI-Assisted SES Creation Wizard module.

12-step guided wizard for building a DAPSI(W)R(M) framework. Writes
elements to project_data.isa_data per step (live writes), with a
confirmation modal protecting existing SES data.

Pattern: matches `analysis_intervention.py` for static form-style UI
plus a state machine driven by reactive values.

Pure-data flow definition lives in `sespy/wizard.py` so SP2/SP3/SP4
can swap in their own backends without touching this module.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import ELEMENT_ID_PREFIX
from ..data_structure import (
    Connection,
    ConnectionSuggestion,
    Element,
    IsaData,
    Project,
    WizardState,
)
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..utils import next_id
from ..wizard import (
    ELEMENT_TYPE_MAP,
    REGIONAL_SEAS_PLACEHOLDER,
    WIZARD_STEPS,
    suggest_connections,
)


@module.ui
def ai_isa_wizard_ui() -> ui.Tag:
    """Static UI: card with breadcrumb output + step-render output. The
    nav buttons (Start / Back / Next / Finish) are rendered CONDITIONALLY
    inside `wizard_step_render` so we don't need inline JS to toggle
    visibility (which would require <script>-tags in @render.ui output —
    browsers don't execute innerHTML-inserted <script> tags reliably,
    and Shiny for Python's update pipeline doesn't work around that).

    Each conditionally-rendered button keeps the SAME input id across
    renders (`wizard_start`, `wizard_back`, etc.) so the @reactive.event
    handlers registered at server-init time fire whenever the button
    exists and gets clicked.
    """
    return ui.card(
        ui.card_header(t("wizard.title")),
        ui.div(
            ui.output_ui("wizard_breadcrumb"),    # step pills
            ui.output_ui("wizard_step_render"),   # Start OR step widget + nav buttons
            style="padding: 16px;",
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def ai_isa_wizard_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    # Wizard state — three module-local reactives.
    wizard_step: reactive.Value[int] = reactive.value(0)
    wizard_answers: reactive.Value[dict[str, Any]] = reactive.value({})
    wizard_active: reactive.Value[bool] = reactive.value(False)
    wizard_suggestions: reactive.Value[list[ConnectionSuggestion]] = reactive.value([])
    # Per-target counts for the freeform_multiple archetype's dynamic UI.
    freeform_counts: reactive.Value[dict[str, int]] = reactive.value({})

    # ---- Placeholders — Tasks 8-14 fill these in ----------------------------

    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        pass  # Task 8

    @reactive.effect
    @reactive.event(input.wizard_replace, ignore_init=True)
    def _on_modal_replace() -> None:
        pass  # Task 8

    @reactive.effect
    @reactive.event(input.wizard_cancel_modal, ignore_init=True)
    def _on_modal_cancel() -> None:
        pass  # Task 8

    @reactive.effect
    @reactive.event(input.wizard_next, ignore_init=True)
    def _on_next() -> None:
        pass  # Task 12

    @reactive.effect
    @reactive.event(input.wizard_back, ignore_init=True)
    def _on_back() -> None:
        pass  # Task 13

    @reactive.effect
    @reactive.event(input.wizard_finish, ignore_init=True)
    def _on_finish() -> None:
        pass  # Task 13

    @output
    @render.ui
    def wizard_breadcrumb() -> ui.Tag:
        """Pill row showing all 12 steps. Inactive state returns empty;
        active state highlights the current step + marks completed."""
        if not wizard_active.get():
            return ui.tags.div()
        current = wizard_step.get()
        pills = []
        for s in WIZARD_STEPS:
            idx = s["step"]
            label = t(f"wizard.step_{idx}_title")
            if idx < current:
                cls = "badge bg-success"  # completed
            elif idx == current:
                cls = "badge bg-primary"  # active
            else:
                cls = "badge bg-secondary"  # future
            pills.append(
                ui.tags.span(
                    f"{idx + 1}. {label}",
                    class_=cls,
                    style="margin: 2px; padding: 4px 8px;",
                )
            )
        return ui.tags.div(
            *pills,
            class_="wizard-breadcrumb",
            style="margin-bottom: 16px; display: flex; flex-wrap: wrap;",
        )

    @output
    @render.ui
    def wizard_step_render() -> ui.Tag:
        # Placeholder — Tasks 9-11 fill the per-archetype widgets.
        # Buttons are rendered conditionally inside this output (not in
        # the static UI) to avoid depending on inline <script> execution.
        if not wizard_active.get():
            return ui.tags.div(
                ui.tags.p("Click Start Wizard to begin.", class_="text-muted"),
                ui.input_action_button(
                    "wizard_start", t("wizard.start"),
                    class_="btn btn-primary",
                ),
            )
        return ui.tags.div("Step content goes here (Tasks 9-11)")
```

- [ ] **Step 2: Verify the file imports cleanly**

```bash
micromamba run -n shiny python -c "from sespy.modules.ai_isa_wizard import ai_isa_wizard_ui, ai_isa_wizard_server; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): module skeleton with empty placeholders"
```

---

## Task 6: Wire PIMS-style into app.py

**Files:**
- Modify: `app.py` — import, NAV, STEPPER (no new stage; wizard goes in `create`), NAV_TO_STEP, PANELS, server registration

PIMS lives in `setup` stage; templates/entry/import live in `create`. Wizard is a creation tool — it goes in `create`, after `templates`.

- [ ] **Step 1: Add the import**

In `app.py`, between the `analysis_simulation` and `cld_visualization` imports (around line 50), insert:

```python
from sespy.modules.ai_isa_wizard import ai_isa_wizard_server, ai_isa_wizard_ui
```

- [ ] **Step 2: Insert the NAV entry after `templates`**

Find `NavItem(id="templates", ...)` in `NAV: list[NavItem] = [`. Insert IMMEDIATELY AFTER it:

```python
    NavItem(id="wizard",   icon="wand-magic-sparkles", label="SES Wizard",  label_key="nav.wizard"),
```

- [ ] **Step 3: Add the NAV_TO_STEP mapping**

Find `NAV_TO_STEP = {`. Insert (anywhere in the dict, alphabetical after `templates` is fine):

```python
    "wizard": "create",
```

- [ ] **Step 4: Add the panel after the Templates panel**

Find `ui.nav_panel("Templates", ...)`. Insert IMMEDIATELY AFTER:

```python
    ui.nav_panel("SES Wizard",        ai_isa_wizard_ui("wizard"),                 value="wizard"),
```

- [ ] **Step 5: Add the server registration**

Find the `templates_server(...)` call. Insert IMMEDIATELY AFTER it:

```python
    ai_isa_wizard_server(
        "wizard",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 6: Smoke-test the import**

```bash
micromamba run -n shiny python -c "import app; print('imports ok')"
```
Expected: `imports ok`.

- [ ] **Step 7: Boot and click the SES Wizard nav button**

Boot the app:
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
(Background; wait_port; open `http://127.0.0.1:8000`.)

Confirm: "SES Wizard" appears in the sidebar, between Templates and Edit Data. Clicking it lands on a card titled "AI-Assisted SES Creation Wizard" with a placeholder text and a Start button (rendered conditionally by `wizard_step_render` when `wizard_active=False`; once the wizard activates, this whole inactive view is replaced rather than hidden).

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat(app): wire SES Wizard module + nav + panel"
```

---

## Task 7: Modal namespace spike

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (temporary — reverted at end of task)

**Goal:** verify whether `ui.input_action_button` ids inside `ui.modal_show()` content auto-namespace to the module prefix when called from `@module.server`. This is a 10-15 minute exploratory spike before writing the real modal flow in Task 8 — a half-day of debugging-saved if it turns out wrong.

- [ ] **Step 1: Add a temporary spike modal to `_on_start`**

In `sespy/modules/ai_isa_wizard.py`, replace the `_on_start` placeholder body with:

```python
    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        # SPIKE: open a minimal modal and observe DOM
        ui.modal_show(
            ui.modal(
                ui.tags.p("Spike: testing namespace behavior."),
                ui.input_action_button("spike_button", "Spike"),
                title="Namespace Spike",
                easy_close=True,
            )
        )

    @reactive.effect
    @reactive.event(input.spike_button, ignore_init=True)
    def _on_spike_button() -> None:
        ui.notification_show(
            "spike_button input fired — namespace works!",
            duration=5, type="message",
        )
```

- [ ] **Step 2: Boot the app**

```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
(Background; `micromamba run -n shiny python .tmp/wait_port.py`.)

- [ ] **Step 3: Trigger the spike modal**

Open `http://127.0.0.1:8000`. Navigate to SES Wizard. The placeholder text shows but the Start button is hidden. Use browser devtools console to click it programmatically:

```javascript
document.getElementById('wizard-wizard_start').click()
```

The modal opens.

- [ ] **Step 4: Inspect the spike button's DOM id**

In the devtools console, find the spike button by scanning for buttons inside the modal:

```javascript
// Most reliable: look inside the open modal
Array.from(document.querySelectorAll('.modal button')).map(b => ({id: b.id, text: b.textContent.trim()}))
```

(Avoid `document.querySelector('button:not(...)')` patterns — there are many buttons in the page; you'd get a false answer.)

Look at the printed list for the Spike button. **Two possible outcomes**:

- **Outcome A: id is `wizard-spike_button`** → namespace auto-applies. Note this in your spike findings. Remove the spike code, write the real modal in Task 8 with confidence that `input.wizard_replace` will fire when the modal button is clicked.
- **Outcome B: id is just `spike_button` (unprefixed)** → namespace does NOT auto-apply. Document the workaround: construct the modal body via `session.ns(...)` to manually prefix ids, e.g. `ui.input_action_button(session.ns("wizard_replace"), ...)`. Task 8 must use this pattern.

- [ ] **Step 5: Click the Spike button and confirm server-side handler fires**

Click the Spike button in the modal. If a green toast notification appears saying "spike_button input fired — namespace works!", the server-side handler bound to `input.spike_button` is correctly receiving the click.

- **If the toast fires**: confirms outcome A.
- **If the toast does NOT fire**: confirms outcome B — the underlying input id was different from what the handler expected.

- [ ] **Step 6: Document the finding**

Append a short note to the spec or to `.tmp/modal_spike_finding.txt`:

```
Modal namespace spike — 2026-05-01
Outcome: <A: auto-namespacing works | B: requires session.ns()>
DOM id observed: <copy from devtools>
Toast handler fired: <yes/no>
Implication for Task 8: <use plain ids | use session.ns()>
```

- [ ] **Step 7: Stop the app and revert the spike code**

Stop the background app. In `sespy/modules/ai_isa_wizard.py`, restore `_on_start` to its placeholder form:

```python
    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        pass  # Task 8
```

Delete the entire `_on_spike_button` handler.

- [ ] **Step 8: Verify clean revert**

```bash
git diff sespy/modules/ai_isa_wizard.py
```
Expected: empty diff (the file is back to the Task 5 commit's state).

- [ ] **Step 9: NO commit**

This task is exploratory — no commit. Findings are recorded in `.tmp/modal_spike_finding.txt` (gitignored) and shape Task 8's implementation.

---

## Task 8: Confirmation modal flow

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `_on_start`, `_on_modal_replace`, `_on_modal_cancel` placeholders

Implements the two-button confirmation modal (Continue, replace it / Cancel) with tip text. Writes preserve the existing project metadata.

**Important: use the appropriate id-namespace pattern from Task 7's spike finding.** The code below assumes outcome A (auto-namespace works). If outcome B, wrap each button id with `session.ns(...)`.

- [ ] **Step 1: Replace `_on_start`**

Replace the `_on_start` placeholder with:

```python
    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start() -> None:
        if len(project_data.get().isa_data.elements) == 0:
            # Empty project — start directly without modal.
            wizard_answers.set({})
            wizard_step.set(0)
            wizard_active.set(True)
            return
        # Non-empty — open confirmation modal.
        ui.modal_show(
            ui.modal(
                ui.tags.p(t("wizard.modal_body")),
                ui.div(
                    ui.input_action_button(
                        "wizard_replace", t("wizard.replace"),
                        class_="btn btn-warning",
                    ),
                    ui.input_action_button(
                        "wizard_cancel_modal", t("wizard.cancel"),
                        class_="btn btn-secondary",
                    ),
                    style="display: flex; gap: 8px; margin-top: 12px;",
                ),
                title=t("wizard.modal_title"),
                easy_close=False,
                footer=None,
            )
        )
```

- [ ] **Step 2: Replace `_on_modal_replace`**

```python
    @reactive.effect
    @reactive.event(input.wizard_replace, ignore_init=True)
    def _on_modal_replace() -> None:
        # Pinned write order — same shape as the live writes in `_on_next`:
        #   build new project → project_data.set → emit signals →
        #   wizard_answers.set / freeform_counts.set → wizard_active /
        #   wizard_step (LAST so wizard_step_render fires once with all
        #   downstream state already settled).
        # Why this order matters: `wizard_active.set(True)` triggers
        # `wizard_step_render`, which depends on `wizard_answers` and
        # `freeform_counts`. Putting wizard_active before the clears
        # would render step 0 against stale answers from the previous
        # session. Putting wizard_active before the emits would let the
        # wizard breadcrumb appear before CLD/autosave see the cleared
        # isa_data, producing a single-frame inconsistent UI.
        current = project_data.get()
        project_data.set(Project(
            metadata=current.metadata,
            isa_data=IsaData(),
        ))
        # Emit BOTH so autosave + CLD see the clearance immediately.
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        wizard_answers.set({})
        freeform_counts.set({})
        wizard_active.set(True)
        wizard_step.set(0)
        ui.modal_remove()
```

- [ ] **Step 3: Replace `_on_modal_cancel`**

```python
    @reactive.effect
    @reactive.event(input.wizard_cancel_modal, ignore_init=True)
    def _on_modal_cancel() -> None:
        # wizard_active is False by construction (modal only opens when False).
        ui.modal_remove()
```

- [ ] **Step 4: Verify imports still work**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): confirmation modal flow with metadata-preserving replace"
```

---

## Task 9: `choice_one` and `choice_many` step renderers

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `wizard_step_render` placeholder, add helper functions

Steps 0-3 use `choice_one` (steps 0-1) and `choice_many` (steps 2-3). Render them with pre-population from `wizard_answers` so Back navigation shows prior selections.

- [ ] **Step 1: Replace `wizard_step_render`**

Replace the existing `wizard_step_render` body with:

```python
    @output
    @render.ui
    def wizard_step_render() -> ui.Tag:
        """Conditionally render: inactive state shows the Start button;
        active state shows the step widget + Back/Next or Back/Finish.
        Buttons are rendered (not hidden via CSS) so we don't depend on
        innerHTML-inserted <script> execution."""
        active = wizard_active.get()
        if not active:
            return ui.tags.div(
                ui.tags.p(
                    "Click Start Wizard to begin a guided 12-step "
                    "DAPSI(W)R(M) framework setup.",
                    class_="text-muted",
                    style="margin-bottom: 16px;",
                ),
                ui.input_action_button(
                    "wizard_start", t("wizard.start"),
                    class_="btn btn-primary",
                ),
            )
        # Active state — render the current step.
        step_idx = wizard_step.get()
        step = WIZARD_STEPS[step_idx]
        archetype = step["archetype"]
        widget: ui.Tag
        if archetype == "choice_one":
            widget = _render_choice_one(step, wizard_answers.get())
        elif archetype == "choice_many":
            widget = _render_choice_many(step, wizard_answers.get())
        elif archetype == "freeform_multiple":
            widget = _render_freeform_multiple(
                step, wizard_answers.get(), freeform_counts.get(), input,
            )
        elif archetype == "connection_review":
            widget = _render_connection_review(wizard_suggestions.get())
        else:
            widget = ui.tags.div(f"Unknown archetype: {archetype}")

        # Build nav buttons inline based on which step we're on.
        nav_buttons: list[ui.Tag] = []
        if step_idx > 0:
            nav_buttons.append(ui.input_action_button(
                "wizard_back", t("wizard.back"), class_="btn btn-secondary",
            ))
        if step_idx < 11:
            nav_buttons.append(ui.input_action_button(
                "wizard_next", t("wizard.next"), class_="btn btn-primary",
            ))
        else:  # step_idx == 11
            nav_buttons.append(ui.input_action_button(
                "wizard_finish", t("wizard.finish"), class_="btn btn-success",
            ))

        return ui.tags.div(
            ui.tags.h4(t(f"wizard.step_{step_idx}_title")),
            ui.tags.p(t(f"wizard.step_{step_idx}_question"), class_="text-muted"),
            widget,
            ui.div(
                *nav_buttons,
                style="margin-top: 16px; display: flex; gap: 8px;",
            ),
        )
```

- [ ] **Step 2: Add `_render_choice_one` helper at module-top scope**

Add at module scope (above `@module.ui` `ai_isa_wizard_ui`):

```python
def _render_choice_one(step: dict, answers: dict) -> ui.Tag:
    """Render a single-choice step (steps 0, 1)."""
    target = step["target"]
    selected = answers.get(target, "")
    if target == "regional_sea":
        choices = {"": "—"} | {
            slug: data["name"] for slug, data in REGIONAL_SEAS_PLACEHOLDER.items()
        }
        return ui.input_radio_buttons(
            f"answer_{target}", t("wizard.regional_sea_label"),
            choices=choices, selected=selected,
        )
    if target == "ecosystem_type":
        # Filter ecosystem types by previously-chosen regional sea.
        regional_sea = answers.get("regional_sea", "")
        eco_list = REGIONAL_SEAS_PLACEHOLDER.get(regional_sea, {}).get(
            "ecosystem_types", []
        )
        choices = {"": "—"} | {e: e for e in eco_list}
        return ui.input_radio_buttons(
            f"answer_{target}", t("wizard.ecosystem_type_label"),
            choices=choices, selected=selected,
        )
    return ui.tags.div(f"choice_one renderer doesn't know target {target!r}")
```

- [ ] **Step 3: Add `_render_choice_many` helper**

Add immediately after `_render_choice_one`:

```python
def _render_choice_many(step: dict, answers: dict) -> ui.Tag:
    """Render a multi-select step (steps 2, 3)."""
    target = step["target"]
    selected = answers.get(target, [])
    regional_sea = answers.get("regional_sea", "")
    sea_data = REGIONAL_SEAS_PLACEHOLDER.get(regional_sea, {})
    if target == "countries":
        choices = sea_data.get("countries", [])
        label = t("wizard.countries_label")
    elif target == "main_issue":
        choices = sea_data.get("common_issues", [])
        label = t("wizard.main_issue_label")
    else:
        choices = []
        label = ""
    return ui.input_selectize(
        f"answer_{target}", label,
        choices={c: c for c in choices},
        selected=selected,
        multiple=True,
        options={"plugins": ["remove_button"]},
    )
```

- [ ] **Step 4: Add stub `_render_freeform_multiple` and `_render_connection_review` for now**

Add immediately after `_render_choice_many`:

```python
def _render_freeform_multiple(
    step: dict, answers: dict, counts: dict, input,
) -> ui.Tag:
    """Stub — Task 10 fills this in. The trailing `input` parameter is
    used by the real implementation to snapshot live typing-in-progress
    via `reactive.isolate()`; the stub ignores it."""
    return ui.tags.p(f"freeform_multiple: {step['target']} (Task 10 TODO)")


def _render_connection_review(suggestions: list) -> ui.Tag:
    """Stub — Task 11 fills this in."""
    return ui.tags.p("connection_review (Task 11 TODO)")
```

- [ ] **Step 5: Smoke-test in browser**

Boot the app. Navigate to SES Wizard. Click Start. Step 0 (regional_sea) should render with 5 radio buttons (Baltic, Mediterranean, North Sea, Irish Sea, Macaronesia) plus a "—" option, plus visible Back (hidden on step 0) / Next buttons. Pick Baltic Sea, click Next... but Next won't advance yet (Task 12 wires it). Verify: step 0 widget renders correctly. Stop the server.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): choice_one and choice_many step renderers"
```

---

## Task 10: `freeform_multiple` step renderer

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `_render_freeform_multiple` stub, add Add/Remove handlers

The hardest archetype: dynamic list of `input_text` rows with Add/Remove buttons. Per the spec: indexed ids (`entry_{step.target}_{i}`), `freeform_counts` reactive tracks how many rows per target.

- [ ] **Step 1: Replace `_render_freeform_multiple` stub**

Replace the existing stub with:

```python
def _render_freeform_multiple(
    step: dict, answers: dict, counts: dict, input,
) -> ui.Tag:
    """Render a list of input_text rows + Add/Remove buttons.

    `counts[target]` is the number of rows currently visible. Pre-populates
    from `answers[target]` (a list[str]) when re-entering a step via Back —
    in that case we ALSO bump counts[target] up to match the saved length.

    `input` is passed in (rather than closure-captured) because this is a
    module-top-scope helper. We use it to snapshot live typing-in-progress
    so that clicking Add/Remove doesn't wipe what the user just typed.
    Without this snapshot, the renderer would re-emit `value=""` for any
    row that hasn't been saved yet, and Shiny would push that empty value
    back to the client, overwriting the typed text — exactly the spec §9
    risk. Reads are wrapped in `reactive.isolate()` so we don't subscribe
    to every entry input (which would cause the renderer to fire on every
    keystroke).
    """
    target = step["target"]
    saved = answers.get(target, [])
    n_rows = max(counts.get(target, 1), len(saved), 1)
    placeholder = t(f"wizard.placeholder_{target}")
    # Snapshot live input values so typing survives Add/Remove re-renders.
    current_values: list[str] = []
    with reactive.isolate():
        for i in range(n_rows):
            try:
                v = input[f"entry_{target}_{i}"]()
                current_values.append(v if v is not None else "")
            except Exception:
                # Input doesn't exist yet (first render) — empty default.
                current_values.append("")
    rows = []
    for i in range(n_rows):
        row_id = f"entry_{target}_{i}"
        # Priority: live typing > saved value > empty.
        value = current_values[i] or (saved[i] if i < len(saved) else "")
        rows.append(
            ui.div(
                ui.input_text(
                    row_id, "",
                    value=value,
                    placeholder=placeholder,
                    width="100%",
                ),
                style="margin-bottom: 4px;",
            )
        )
    rows.append(
        ui.div(
            ui.input_action_button(
                f"add_{target}", t("wizard.add_another"),
                class_="btn btn-sm btn-secondary",
            ),
            ui.input_action_button(
                f"remove_{target}", t("wizard.remove"),
                class_="btn btn-sm btn-secondary",
                style="margin-left: 8px;",
            ),
            style="margin-top: 8px;",
        )
    )
    return ui.div(*rows, id=f"freeform_{target}_container")
```

- [ ] **Step 2: Add Add/Remove handlers in the server**

In `ai_isa_wizard_server`, AFTER the `_on_modal_cancel` handler and BEFORE `_on_next`, add a small helper-effect-builder loop:

```python
    # Add/Remove handlers — one pair per freeform_multiple target.
    _freeform_targets = ["drivers", "activities", "pressures", "states",
                         "impacts", "welfare", "responses"]

    def _make_add_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"add_{target}"], ignore_init=True)
        def _():
            counts = dict(freeform_counts.get())
            counts[target] = counts.get(target, 1) + 1
            freeform_counts.set(counts)
        return _

    def _make_remove_handler(target: str):
        @reactive.effect
        @reactive.event(input[f"remove_{target}"], ignore_init=True)
        def _():
            counts = dict(freeform_counts.get())
            counts[target] = max(counts.get(target, 1) - 1, 1)
            freeform_counts.set(counts)
        return _

    _freeform_handlers = [
        (_make_add_handler(t_), _make_remove_handler(t_))
        for t_ in _freeform_targets
    ]
```

- [ ] **Step 3: Smoke-test (CRITICAL — verifies dynamic-subscript reactive event pattern)**

Boot the app. Start the wizard. Advance through steps 0-3 (selecting valid answers — but Next won't actually advance until Task 12 wires the handler; for now just confirm step rendering). Reach step 4 (drivers) — confirm one input_text row appears with the placeholder "List the drivers (e.g. tourism demand, fishing pressure)" and Add/Remove buttons.

**Critical assertion 1 (subscript-event pattern)**: Click Add — a second row MUST appear. Click Add again — a third row MUST appear. Click Remove — the third row MUST disappear.

This test is load-bearing: the `_make_add_handler` / `_make_remove_handler` closures register reactive effects via `@reactive.event(input[f"add_{target}"], ...)` — passing a *subscript-resolved* `InputItem` rather than the more common attribute-access form (`input.add_drivers`). If subscript-based input access doesn't act as a reactive event source in the installed Shiny for Python version, every click will silently do nothing and the row count will stay at 1.

**Critical assertion 2 (typing survives Add/Remove)**: Type "Tourism demand" into row 0. Click Add. Row 0 MUST still display "Tourism demand" — NOT empty. Type "Fishing pressure" into row 1. Click Add again. Both row 0 and row 1 MUST retain their typed values.

This test verifies the spec §9 risk: the renderer re-fires on every Add/Remove (because `freeform_counts` changed) and re-emits `value=...` for every row. Without the `reactive.isolate()` snapshot of live input values in `_render_freeform_multiple`, the `value` would default to `saved[i] if i < len(saved) else ""` — for rows the user just typed but hasn't saved (Next not clicked yet), `saved` is empty, so `value=""` would be pushed back to the client and the typed text would be wiped. If this assertion fails, verify `_render_freeform_multiple` reads `input[f"entry_{target}_{i}"]()` inside `with reactive.isolate():` and uses that value first, falling back to `saved[i]` only if no live value exists.

**If clicks silently do nothing**: fall back to attribute-access by hard-coding seven separate handlers (one per target) instead of the loop. Replace Step 2 with:

```python
    @reactive.effect
    @reactive.event(input.add_drivers, ignore_init=True)
    def _add_drivers():
        counts = dict(freeform_counts.get())
        counts["drivers"] = counts.get("drivers", 1) + 1
        freeform_counts.set(counts)

    # ... and six more (activities, pressures, states, impacts, welfare, responses)
    # mirroring the same shape, plus seven _remove_<target> handlers.
```

The factory pattern is preferred for DRY, but correctness wins. Document the fallback choice in the Task 10 commit message if used. Stop the server when verified.

(Stepping forward isn't possible yet because Task 12 wires `_on_next`. The test here is purely the renderer + Add/Remove dynamic UI.)

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): freeform_multiple renderer with Add/Remove dynamic UI"
```

---

## Task 11: `connection_review` step renderer

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `_render_connection_review` stub

Step 11 renders the suggestions table (empty in SP1) with accept/reject toggles per row. SP1's stub returns `[]` so the table renders the placeholder message.

- [ ] **Step 1: Replace `_render_connection_review` stub**

Replace the existing stub with:

```python
def _render_connection_review(suggestions: list) -> ui.Tag:
    """Render the connection-review step (step 11)."""
    if not suggestions:
        return ui.tags.div(
            ui.tags.p(t("wizard.no_suggestions"), class_="text-muted"),
            ui.tags.p(
                "Click Finish to complete the wizard. You can add "
                "connections manually via the Edit Data module.",
                class_="text-muted",
            ),
        )
    # Suggestions present — render an accept/reject table (SP3+ path).
    # Column 1 is the row number ("#"); the table label
    # `wizard.connection_suggestions_table` is rendered as a <caption>
    # above the rows, NOT as the first column header (which would
    # mis-label the row-number column).
    rows = [
        ui.tags.tr(
            ui.tags.th("#"),
            ui.tags.th("Source"),
            ui.tags.th("Target"),
            ui.tags.th(t("wizard.confidence")),
            ui.tags.th(t("wizard.rationale")),
            ui.tags.th(t("wizard.accept")),
        ),
    ]
    for i, s in enumerate(suggestions):
        rows.append(
            ui.tags.tr(
                ui.tags.td(f"{i+1}"),
                ui.tags.td(s.source),
                ui.tags.td(s.target),
                ui.tags.td(f"{s.confidence:.2f}"),
                ui.tags.td(s.rationale),
                ui.tags.td(
                    ui.input_checkbox(f"accept_suggestion_{i}", "", value=False),
                ),
            )
        )
    return ui.tags.table(
        ui.tags.caption(t("wizard.connection_suggestions_table")),
        *rows,
        class_="table table-sm",
    )
```

- [ ] **Step 2: Smoke-test**

Boot the app, start the wizard, advance to step 11 (still requires Task 12 to wire Next). For now confirm: the step 11 renderer shows the placeholder text "No connection suggestions yet — install the SP3 or SP4 scoring backend...". Stop server.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): connection_review renderer with empty-state message"
```

---

## Task 12: `_on_next` handler with pinned write order

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `_on_next` placeholder

The single largest server-side handler. Validates current step's answer, writes elements (steps 4-10) or metadata (steps 0-1) to `project_data` in the pinned order, increments `wizard_step`. Steps 2 and 3 are ephemeral (only update `wizard_answers`).

- [ ] **Step 1: Replace `_on_next`**

```python
    @reactive.effect
    @reactive.event(input.wizard_next, ignore_init=True)
    def _on_next() -> None:
        # Guard: on step 11 only Finish is rendered (no Next button), but a
        # stale click event could still arrive — bail before mutating state.
        if wizard_step.get() >= 11:
            return
        step_idx = wizard_step.get()
        step = WIZARD_STEPS[step_idx]
        target = step["target"]
        archetype = step["archetype"]

        # Read answer from inputs (defensive: input may be None).
        if archetype == "choice_one":
            value = (input[f"answer_{target}"]() or "").strip()
            if not value:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            answer: Any = value
        elif archetype == "choice_many":
            raw = input[f"answer_{target}"]()
            value_list = list(raw) if raw else []
            if not value_list:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            answer = value_list
        elif archetype == "freeform_multiple":
            # Read row count from BOTH freeform_counts (display state)
            # AND len(saved answers) — the renderer expands rows for
            # saved answers without writing back to freeform_counts, so
            # using freeform_counts alone misses Back-navigation rows.
            counts = freeform_counts.get()
            saved = wizard_answers.get().get(target, [])
            n = max(counts.get(target, 1), len(saved))
            raw_entries: list[str] = []
            for i in range(n):
                v = (input[f"entry_{target}_{i}"]() or "").strip()
                if v:
                    raw_entries.append(v)
            if not raw_entries:
                ui.notification_show(
                    t("wizard.validation_error"), type="warning", duration=3,
                )
                return
            # Duplicates are a validation failure per spec §4 — toast and bail.
            if len(raw_entries) != len(set(raw_entries)):
                ui.notification_show(
                    t("wizard.duplicate_error"), type="warning", duration=3,
                )
                return
            answer = raw_entries
        else:
            return  # connection_review reached via _on_finish, not _on_next

        # Write phase — pinned order.
        # Steps 0-1: write to metadata; steps 2-3: ephemeral (no project_data write);
        # steps 4-10: write Element objects to isa_data.
        current = project_data.get()
        if step_idx == 0:
            # regional_sea — metadata write
            new_meta = _replace_metadata(current.metadata, regional_sea=answer)
            new_proj = Project(metadata=new_meta, isa_data=current.isa_data)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        elif step_idx == 1:
            new_meta = _replace_metadata(current.metadata, ecosystem_type=answer)
            new_proj = Project(metadata=new_meta, isa_data=current.isa_data)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        elif step_idx in (2, 3):
            pass  # ephemeral; only wizard_answers gets updated below
        elif step_idx in (4, 5, 6, 7, 8, 9, 10):
            elem_type = ELEMENT_TYPE_MAP[target]
            prefix = ELEMENT_ID_PREFIX[target]

            # Idempotent re-write semantics. The R-style "Back doesn't undo
            # writes" rule (spec §4) means that on first Next from this
            # step, we wrote N Elements to isa_data. If the user goes Back
            # and clicks Next AGAIN — without this idempotency block —
            # _on_next would APPEND a fresh batch alongside the previous
            # one, leaving the project with duplicated labels (D001 and
            # D002 both = "Tourism"). To prevent that, before appending
            # we REMOVE this step's previous batch by matching
            # (type == elem_type AND label in prev_answer). Connections
            # referencing those removed ids are also pruned (no
            # dangling endpoints).
            prev_answer = wizard_answers.get().get(target, [])
            if prev_answer == answer:
                # No-change re-Next (user clicked Back, then Next without
                # edits). The existing elements already match what the
                # user wants — skip the rebuild entirely. Rewriting would
                # re-allocate element ids (gap-filling typically yields
                # the SAME id, but the rewrite still emits an
                # intermediate IsaData with the old elements removed) and
                # would prune any external connections (e.g. from PIMS
                # or Edit Data) that reference those ids. Forward-compat
                # for SP3/SP4: once `suggest_connections` returns real
                # suggestions and the user accepts some via Finish, those
                # connections live in `project_data.connections`. A user
                # re-running the wizard later (Replace flow) would clear
                # everything anyway, but a Back+Next mid-wizard with no
                # edits should be a true no-op.
                pass
            else:
                if prev_answer:
                    # Re-Next WITH changes: replace previous batch with
                    # current answer; prune connections to removed ids.
                    elements_to_keep = [
                        e for e in current.isa_data.elements
                        if not (e.type == elem_type and e.label in prev_answer)
                    ]
                    removed_ids = {
                        e.id for e in current.isa_data.elements
                    } - {e.id for e in elements_to_keep}
                    connections_to_keep = [
                        c for c in current.isa_data.connections
                        if c.source not in removed_ids and c.target not in removed_ids
                    ]
                else:
                    # First Next from this step: nothing to remove.
                    elements_to_keep = list(current.isa_data.elements)
                    connections_to_keep = list(current.isa_data.connections)

                existing_ids = [e.id for e in elements_to_keep]
                new_elements = list(elements_to_keep)
                for entry_label in answer:
                    new_id = next_id(existing_ids, prefix)
                    new_elements.append(Element(id=new_id, label=entry_label, type=elem_type))
                    existing_ids.append(new_id)
                new_isa = IsaData(
                    elements=new_elements,
                    connections=connections_to_keep,
                )
                new_proj = Project(metadata=current.metadata, isa_data=new_isa)
                project_data.set(new_proj)
                event_bus.emit_isa_change()
                event_bus.emit_cld_update()

        # Always: update answers, populate suggestions if next step is 11,
        # then advance the step LAST. Pinned order so wizard_step_render
        # fires once with all dependent reactives already at their new
        # values — otherwise setting wizard_step to 11 would re-render
        # _render_connection_review before wizard_suggestions has been
        # updated, showing the empty placeholder for one flush before
        # the real suggestions arrive.
        ans = dict(wizard_answers.get())
        ans[target] = answer
        wizard_answers.set(ans)

        if step_idx + 1 == 11:
            wizard_suggestions.set(suggest_connections(_assemble_wizard_state()))

        wizard_step.set(step_idx + 1)

    def _assemble_wizard_state() -> WizardState:
        """Build a WizardState snapshot from current reactive state."""
        ans = wizard_answers.get()
        isa = project_data.get().isa_data
        return WizardState(
            regional_sea=ans.get("regional_sea", ""),
            ecosystem_type=ans.get("ecosystem_type", ""),
            countries=ans.get("countries", []),
            main_issue=ans.get("main_issue", []),
            elements=list(isa.elements),
        )
```

- [ ] **Step 2: Add `_replace_metadata` helper at module-top scope**

Add immediately after the existing helper functions (above `@module.ui`):

```python
def _replace_metadata(meta, **overrides):
    """Build a new ProjectMetadata copying meta and overriding listed fields.
    `replace` is imported at module top alongside other stdlib imports."""
    return replace(meta, **overrides)
```

- [ ] **Step 3: Smoke-test**

Boot the app. Start the wizard. Advance through all 12 steps with valid answers. Confirm:
- Step 0 (regional_sea): pick Baltic, Next. Step 1 renders ecosystem types FROM Baltic.
- Step 1: pick Open coast, Next. Step 2 (countries) renders Baltic's countries.
- Steps 2-3: select 1+ entries each, Next.
- Steps 4-10: type 1+ entry each, Next. After each, check that the CLD module shows the new elements.
- Step 11: connection-review renders the placeholder message. No Finish action yet (Task 13).

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): _on_next handler with pinned write order and step guard"
```

---

## Task 13: `_on_back` and `_on_finish` handlers

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` — replace `_on_back` and `_on_finish` placeholders

`_on_back` simply decrements; doesn't undo writes (R behavior). `_on_finish` deactivates the wizard, optionally writing accepted connection suggestions.

- [ ] **Step 1: Replace `_on_back`**

```python
    @reactive.effect
    @reactive.event(input.wizard_back, ignore_init=True)
    def _on_back() -> None:
        if wizard_step.get() <= 0:
            return  # can't go before step 0
        new_step_idx = wizard_step.get() - 1
        # If returning to a freeform_multiple step, pre-seed
        # freeform_counts[target] = max(current, len(saved)) so that
        # subsequent Add/Remove clicks operate on the correct visible
        # row count. Without this, _render_freeform_multiple still shows
        # the right number of rows (via max(counts, len(saved), 1)),
        # but Add/Remove handlers mutate the stale `counts` value — a
        # 3-entry re-entry would show 3 rows but Remove would clamp
        # `counts[target]` from 1 to 1, leaving the visible 3 rows
        # unchanged from the user's perspective.
        new_step = WIZARD_STEPS[new_step_idx]
        if new_step["archetype"] == "freeform_multiple":
            target = new_step["target"]
            saved = wizard_answers.get().get(target, [])
            counts = dict(freeform_counts.get())
            counts[target] = max(counts.get(target, 1), len(saved), 1)
            freeform_counts.set(counts)
        wizard_step.set(new_step_idx)
```

- [ ] **Step 2: Replace `_on_finish`**

```python
    @reactive.effect
    @reactive.event(input.wizard_finish, ignore_init=True)
    def _on_finish() -> None:
        # Hard guard — Finish is only rendered on step 11, but a stale click
        # event could still arrive — bail before mutating state.
        if wizard_step.get() != 11:
            return
        # Collect accepted suggestions (if any). SP1 stub returns [], so the
        # accept_suggestion_<i> inputs may not exist; defensive read.
        accepted: list[ConnectionSuggestion] = []
        for i, s in enumerate(wizard_suggestions.get()):
            try:
                if input[f"accept_suggestion_{i}"]():
                    accepted.append(s)
            except Exception:
                pass
        if accepted:
            current = project_data.get()
            new_conns = list(current.isa_data.connections)
            for s in accepted:
                new_conns.append(Connection(
                    source=s.source, target=s.target, polarity=s.polarity,
                ))
            new_isa = IsaData(
                elements=list(current.isa_data.elements),
                connections=new_conns,
            )
            new_proj = Project(metadata=current.metadata, isa_data=new_isa)
            project_data.set(new_proj)
            event_bus.emit_isa_change()
            event_bus.emit_cld_update()
        # Deactivate.
        wizard_active.set(False)
        ui.notification_show(
            "Wizard complete — your SES is ready.",
            type="message", duration=4,
        )
```

- [ ] **Step 3: Smoke-test**

Boot the app. Run a complete wizard (start to step 11). Click Finish. Confirm: a "Wizard complete" toast appears, the wizard panel returns to the inactive state with the Start button visible again. project_data retains the elements written. Stop server.

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/ai_isa_wizard.py
git commit -m "feat(wizard): _on_back and _on_finish with step guards"
```

---

## Task 14: E2e test suite

**Files:**
- Create: `tests/test_wizard_e2e.py`

6 cases covering the state machine and the modal flow. Each case follows the standalone-asyncio-Playwright pattern from `tests/test_pims_project_e2e.py`.

- [ ] **Step 1: Create `tests/test_wizard_e2e.py`**

```python
"""E2E for the AI-ISA Wizard module (SP1).

Six cases:
  1. Empty project — full 12-step run, asserts elements written + Finish deactivates.
  2. Non-empty project — modal Cancel preserves state.
  3. Non-empty project — modal Replace clears isa_data, preserves metadata.
  4. Mid-wizard nav and resume.
  5. Back preserves writes.
  6. Validation failure on freeform step.

Boot the app on port 8000, then run this script.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def _open_wizard(page):
    await page.wait_for_selector("#sespy_nav_wizard", timeout=15000)
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)


async def _start_wizard_empty_via_replace(page):
    """Reset the page, then drive the wizard from boot state through
    Start → modal → Replace. End state: wizard active at step 0, with
    `isa_data` cleared to `IsaData()`.

    The page reload is the cleanest way to guarantee a fresh
    `wizard_active=False` baseline regardless of what previous cases
    left in session reactives — there is no UI affordance to
    deactivate the wizard except by clicking Finish on step 11, which
    is impractical to wire up just to reset between cases.

    Why not click `#new_project` instead of going through Replace?
    Because `#new_project` in `project_io.py` is wired to `_on_new`
    which calls `Project.from_isa(load_sample(SAMPLE))` — it RELOADS
    the sample, it does NOT produce an empty project. Start would
    still see a non-empty project and open the modal anyway. The
    modal-Replace flow is the only path to a truly empty wizard
    state, so we exercise it as the default empty-start helper.
    """
    await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
    await page.wait_for_selector("#sespy_nav_wizard", timeout=15000)
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    await page.click("#wizard-wizard_replace")
    await page.wait_for_timeout(1500)


async def case_full_run(page):
    print("\n=== case 1: empty project full 12-step run ===")
    # _start_wizard_empty_via_replace navigates and reloads; no need to
    # call _open_wizard separately.
    await _start_wizard_empty_via_replace(page)
    # Steps 0-10: pick a value, click Next.
    for step in range(11):
        # For choice_one and choice_many, set the answer via JS.
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic',"
                " {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast',"
                " {priority: 'event'})"
            )
        elif step in (2, 3):
            target = "countries" if step == 2 else "main_issue"
            value_js = "['Lithuania']" if step == 2 else "['Eutrophication']"
            await page.evaluate(
                f"() => Shiny.setInputValue('wizard-answer_{target}', {value_js},"
                " {priority: 'event'})"
            )
        else:
            target = ["drivers","activities","pressures","states","impacts","welfare","responses"][step-4]
            await page.fill(f"#wizard-entry_{target}_0", f"E2E {target} sample")
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # Step 11: click Finish.
    await page.click("#wizard-wizard_finish")
    await page.wait_for_timeout(1500)
    # Assert: Start button is back in the DOM (wizard_active=False causes
    # `wizard_step_render` to re-render the inactive view, which contains
    # the Start button). Under the conditional-render architecture the
    # button is *absent* from the DOM while the wizard is active, so we
    # check `!== null` rather than CSS visibility.
    present = await page.evaluate(
        "() => document.getElementById('wizard-wizard_start') !== null"
    )
    assert present, "Start button should be present in DOM after Finish"
    print("  ok (wizard deactivated)")


async def case_modal_cancel(page):
    print("\n=== case 2: non-empty project modal Cancel ===")
    # Load Coastal Tourism SES so project is non-empty.
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)
    # Open wizard, click Start — modal opens.
    await _open_wizard(page)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    # Modal Cancel.
    await page.click("#wizard-wizard_cancel_modal")
    await page.wait_for_timeout(800)
    # Assert: modal closed, wizard still inactive (Start button still in DOM).
    # Cancel does not flip `wizard_active`, so the inactive view never
    # re-rendered — but check DOM presence not CSS visibility, since the
    # active view would *remove* the button entirely.
    present = await page.evaluate(
        "() => document.getElementById('wizard-wizard_start') !== null"
    )
    assert present, "Start button should still be present after Cancel"
    print("  ok")


async def case_modal_replace(page):
    print("\n=== case 3: non-empty project modal Replace ===")
    # Load Coastal Tourism (sorted-first template) by name lookup, mirroring
    # case 2's pattern — robust if a future template sorts before it.
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)
    await _open_wizard(page)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    # Modal Continue, replace it.
    await page.click("#wizard-wizard_replace")
    await page.wait_for_timeout(1500)
    # Assert: wizard now active. Query the active pill (bg-primary class)
    # to verify which step is current — the breadcrumb renders all 12 pills
    # regardless of current step, so plain text-contains checks would be
    # vacuously true.
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("1."), (
        f"active pill should be '1. ...' for step 0, got {active_pill!r}"
    )
    # Assert: isa_data was actually cleared by Replace. Navigate to Edit
    # Data and verify the elements table has 0 rows. Without this, the
    # active-pill assertion alone passes even if Replace forgot to wipe
    # isa_data — the bug it's MEANT to catch (silent metadata-vs-isa-data
    # confusion was a recurring concern across review rounds).
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(2500)
    elements_count = await page.evaluate(
        "() => document.querySelectorAll("
        "'#entry-elements_table table tbody tr').length"
    )
    assert elements_count == 0, (
        f"isa_data not cleared by Replace — elements table shows "
        f"{elements_count} rows, expected 0"
    )
    # Navigate back to wizard so case 4's helper finds the wizard nav
    # consistently (no cleanup work needed since helper does page.goto).
    print(f"  ok (active pill: {active_pill[:50]}, elements: 0)")


async def case_mid_nav_resume(page):
    print("\n=== case 4: mid-wizard nav and resume ===")
    # Helper reloads to get a fresh `wizard_active=False` baseline,
    # then Start → modal → Replace into an empty active wizard.
    await _start_wizard_empty_via_replace(page)
    # Advance to step 3.
    for step in range(3):
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic', {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast', {priority: 'event'})"
            )
        elif step == 2:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_countries', ['Lithuania'], {priority: 'event'})"
            )
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # Navigate away to CLD.
    await page.click("#sespy_nav_cld")
    await page.wait_for_timeout(1000)
    # Navigate back.
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)
    # Assert active pill is "4. ..." (1-based label for step index 3).
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("4."), (
        f"active pill should be '4. ...' for step 3, got {active_pill!r}"
    )
    print(f"  ok (active: {active_pill[:50]})")


async def case_back_preserves(page):
    print("\n=== case 5: Back preserves writes ===")
    # Continue from case 4's state — wizard is on step 3 (main_issue).
    # First advance through step 3 so we land on step 4 (drivers).
    await page.evaluate(
        "() => Shiny.setInputValue('wizard-answer_main_issue', ['Eutrophication'],"
        " {priority: 'event'})"
    )
    await page.wait_for_timeout(300)
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(500)
    # Now on step 4 (drivers, freeform_multiple). Fill and click Next.
    await page.fill("#wizard-entry_drivers_0", "Tourism demand")
    await page.wait_for_timeout(300)
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(500)
    # Now on step 5. Click Back to return to step 4.
    await page.click("#wizard-wizard_back")
    await page.wait_for_timeout(800)
    # Step 4 renders as active pill "5. Drivers".
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("5."), (
        f"active pill should be '5. ...' for step index 4, got {active_pill!r}"
    )
    val = await page.evaluate(
        "() => document.getElementById('wizard-entry_drivers_0')?.value"
    )
    assert val == "Tourism demand", f"driver entry lost: {val!r}"
    print(f"  ok (entry preserved: {val!r})")


async def case_validation_failure(page):
    print("\n=== case 6: validation failure on freeform step ===")
    # Helper reloads to deactivate any prior wizard state, then Start
    # → modal → Replace into a fresh empty active wizard at step 0.
    await _start_wizard_empty_via_replace(page)
    for step in range(4):
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic', {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast', {priority: 'event'})"
            )
        elif step in (2, 3):
            target = "countries" if step == 2 else "main_issue"
            value_js = "['Lithuania']" if step == 2 else "['Eutrophication']"
            await page.evaluate(
                f"() => Shiny.setInputValue('wizard-answer_{target}', {value_js},"
                " {priority: 'event'})"
            )
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # On step 4 with empty driver — click Next.
    await page.fill("#wizard-entry_drivers_0", "   ")  # whitespace-only
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(1000)
    # Assert: validation toast appeared AND breadcrumb still shows step 4.
    notif = await page.evaluate(
        "() => document.querySelectorAll('#shiny-notification-panel .shiny-notification').length"
    )
    assert notif >= 1, "expected validation notification"
    # Validation failed → still on step 4, active pill is "5. Drivers".
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("5."), (
        f"should still be on step 4 (pill '5. ...'), got {active_pill!r}"
    )
    print("  ok (validation triggered, step did not advance)")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_full_run(page)
        await case_modal_cancel(page)
        await case_modal_replace(page)
        await case_mid_nav_resume(page)
        await case_back_preserves(page)
        await case_validation_failure(page)

        await page.screenshot(path="tests/screenshots/wizard_e2e.png")
        print("\nwizard e2e: 6 cases passed")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Verify it parses**

```bash
micromamba run -n shiny python -c "import ast; ast.parse(open('tests/test_wizard_e2e.py').read()); print('parse: OK')"
```
Expected: `parse: OK`.

- [ ] **Step 3: Run the e2e against a running app**

Boot the app, wait for port, run the script:

```bash
micromamba run -n shiny shiny run --port 8000 app.py  # background
micromamba run -n shiny python .tmp/wait_port.py
micromamba run -n shiny python tests/test_wizard_e2e.py
```
Expected: `wizard e2e: 6 cases passed`. Stop the background server.

If failures: common causes — Shiny.setInputValue might need a different format for selectize multi (use list); modal button ids may need namespace adjustment per Task 7's spike; freeform inputs may need a tick after Add to be present.

- [ ] **Step 4: Commit**

```bash
git add tests/test_wizard_e2e.py
git commit -m "test(wizard): e2e suite — 6 cases covering state machine + modal"
```

---

## Task 15: README update + final verification

**Files:**
- Modify: `README.md`

Bump module count, add a row to the modules table, reconcile e2e count to truth.

- [ ] **Step 1: Bump module count from 15 to 16**

In `README.md`, replace `**15 modules**` with `**16 modules**`. Replace `### Modules (15)` with `### Modules (16)`.

- [ ] **Step 2: Add a row to the modules table**

Find the row for `**Templates**` (the Templates module). Insert this row IMMEDIATELY AFTER it:

```markdown
| **SES Wizard** (`sespy/modules/ai_isa_wizard.py`) | `modules/ai_isa_assistant_module.R` (and `ai_isa/`) | 12-step DAPSI(W)R(M) wizard with confirmation modal, live writes per step, and a stub `suggest_connections()` ready for SP3/SP4 scoring backends. |
```

- [ ] **Step 3: Verify the actual e2e count and reconcile**

```bash
ls tests/test_*.py | wc -l
ls tests/test_*_e2e.py tests/test_burger.py tests/test_stepper*.py 2>/dev/null | wc -l
```
The second number is the e2e count after adding `test_wizard_e2e.py` (now 21). The README's stated number may have drifted from reality — **reconcile to the actual count**, don't just increment.

Find the line that says `108 unit tests + 20 e2e scripts.` and update to:

```
122 unit tests + 21 e2e scripts.
```

(108 baseline + 4 in `test_utils.py` from Task 1 + 3 in `test_data_structure.py` from Task 2 + 7 in `test_wizard.py` from Task 3 = 14 new = 122 total. Verify by running pytest and updating the number to whatever pytest actually reports — the README's stated 20 e2e count should also be reconciled to whatever `ls tests/test_*_e2e.py tests/test_burger.py tests/test_stepper*.py | wc -l` actually shows after adding `test_wizard_e2e.py`.)

- [ ] **Step 4: Verify the unit test count via pytest**

```bash
micromamba run -n shiny python -m pytest tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py tests/test_report.py tests/test_templates.py tests/test_network.py tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py 2>&1 | tail -3
```

Expected: `122 passed` (or close — adjust the README's count to match the actual number reported).

- [ ] **Step 5: Verify the app imports cleanly**

```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): note SES Wizard — now 16 modules"
```

- [ ] **Step 7: Final branch summary**

```bash
git log --oneline main..feat/ai-isa-wizard-sp1
```
Expected: 14 commits (Tasks 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15 — Task 0 is read-only and Task 7 is exploratory with no commit).

---

## Definition of done

- All 16 tasks complete (Task 0 + Task 7 don't commit; 14 commits on the branch).
- `feat/ai-isa-wizard-sp1` contains 14 commits with self-descriptive messages.
- E2e suite (`tests/test_wizard_e2e.py`) prints `wizard e2e: 6 cases passed`.
- App boots cleanly; "SES Wizard" appears in the nav between Templates and Edit Data; clicking it lands on the placeholder card with a Start button.
- Empty-project flow: click Start → modal does NOT appear → step 0 renders. Pick + Next round-trips through all 12 steps. Click Finish → wizard deactivates, project_data has expected elements.
- Non-empty-project flow: click Start → modal appears with Continue/Cancel buttons. Cancel preserves project. Replace clears isa_data, preserves metadata.
- Back preserves writes. Validation toasts on empty freeform steps.
- Module #16 in README; tests count updated to actual.
- All existing tests still pass.

## Out of scope (deferred to future sub-projects)

- SP2: regional-seas knowledge base (replaces `REGIONAL_SEAS_PLACEHOLDER` with the real KB).
- SP3: TF-IDF + rule-based connection scoring (fills `suggest_connections()`).
- SP4: optional Claude API connection scoring backend.
- The `connection_review_tabbed.R` (1292 LOC) extended editor — SP1's connection-review step is a simple table; the rich editor is a separate sub-project if ever needed.
- **The `Measures` element type** — SESPy has 8 DAPSIWRM types but the wizard's 12 R-mirrored steps only cover 7. R's "responses" maps to SESPy's `Responses`; SESPy's `Measures` (id prefix `RM`) is not produced by any wizard step. Users who want `Measures` elements add them via Edit Data. Aligns with R behavior.
- Animation, custom CSS, decorative help modals from `ai_isa_assistant_module.R`.
- Persistence of `countries` and `main_issue` answers across sessions.
- Mobile/responsive layout.
