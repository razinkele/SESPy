# AI-ISA Wizard SP3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SP1's stub `def suggest_connections(state) -> []` (sespy/wizard.py:92) with a deterministic, offline, rule-based connection-scoring backend ported from R's `connection_generator.R` (1009 LOC), so the wizard's step-11 connection_review surfaces real suggestions without any change to the SP1 renderer.

**Architecture:** Two new files mirror SP2's pattern: `sespy/connection_keywords.json` (10 keyword lists + 4 polarity word sets) holds all data, and `sespy/connection_scorer.py` (~450 LOC) holds the algorithm — eager-loaded at module import. A 5-line relocation moves `ELEMENT_TYPE_MAP` from `sespy/wizard.py` to `sespy/data_structure.py` to break a would-be import cycle. SP1's stub `suggest_connections` is replaced with a one-line top-level-import delegation. A `pyproject.toml` packaging fix (~10 LOC) ensures both SP2's and SP3's JSON files ship in installed wheels.

**Tech Stack:** Python 3.11, micromamba env `shiny`, stdlib only (`json`, `re`, `logging`, `pathlib`, `dataclasses`), pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-03-ai-isa-wizard-sp3-design.md` (HEAD `c793001` on main; 5 multi-agent review rounds, ~50 findings caught and fixed). When in doubt, the spec is authoritative.

**Working directory:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy`. All shell commands assume this is the cwd. Use forward slashes.

**Environment:** `micromamba run -n shiny <cmd>` for everything Python. Do NOT `pip install` packages (except in Task 11's throwaway-env wheel-install verification, which is the *only* sanctioned `pip install` in this plan). Do NOT use `python -m venv` — global CLAUDE.md forbids it on this machine.

**Git:** SESPy is a git repository (initialized 2026-04-27 during the boolean+sim plan execution). All "Commit" steps run real `git add`/`git commit` commands; do not `git init`.

**R source-of-truth:** `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R` (1009 LOC). Tasks 1 and 2 read specific R line ranges; verify accessibility in Task 0 before continuing.

**Branch:** `feat/ai-isa-wizard-sp3` cut from main at HEAD `c793001`.

**Expected commits:** 12 (one per implementation task — Tasks 0 and 12 are read-only verification with no commit). The spec §8's "~6 commits" estimate aggregated multiple sub-steps into "Task 2"; this plan splits that into 6-7 atomic per-function commits for clean history and granular review.

**Total estimate:** ~4.5–5.5 hours focused work.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `sespy/connection_keywords.json` | KB data: 10 connection-type keyword lists + 4 polarity-signal word sets | NEW (Task 1) |
| `sespy/connection_scorer.py` | Pure-Python algorithm: 3 public functions (`calculate_relevance`, `detect_polarity`, `suggest_connections`) + 4 private (`_load_keywords`, `_analyze_polarity_phrase`, `_select_verb`, `_generate_smart_connections`); eager `_KW = _load_keywords()` at import; module-level `_REVERSAL_COMPOUNDS` and `_NEGATION_PATTERNS` regex constants | NEW (Tasks 3-9) |
| `tests/test_connection_scorer.py` | 33 unit tests in 5 groups: schema (G1=5), relevance (G2=6), polarity (G3=7), smart_connections (G4=6), suggest_connections (G5=9) | NEW (Tasks 3-9 incrementally) |
| `sespy/data_structure.py` | New home for `ELEMENT_TYPE_MAP` (relocated from wizard.py) | MODIFIED (Task 2) |
| `sespy/wizard.py` | (a) Re-export `ELEMENT_TYPE_MAP` from data_structure for SP1 caller compat; (b) replace stub `suggest_connections` at line 92 with delegation to `connection_scorer` | MODIFIED (Tasks 2, 10) |
| `tests/test_wizard.py` | Rename `test_suggest_connections_stub_returns_empty` → `test_suggest_connections_empty_state_returns_empty` | MODIFIED (Task 10) |
| `pyproject.toml` | Add `[build-system]`, `[tool.setuptools.packages.find]`, `[tool.setuptools.package-data]` so JSON files ship in wheels | MODIFIED (Task 11) |
| `README.md` | Bump unit test count `134 → 180` at both occurrences | MODIFIED (Task 13) |

---

## Task 0: Verify environment, R source access, and cut branch

**Files:** none (read-only sanity check)

- [ ] **Step 1: Verify `shiny` env imports the stack**

Run:
```bash
micromamba run -n shiny python -c "import json, re, logging, pathlib; from sespy.data_structure import WizardState, ConnectionSuggestion, Element; from sespy.wizard import ELEMENT_TYPE_MAP; print('ok')"
```
Expected: prints `ok`.

If it fails, stop and ask the user to fix the environment. Do not proceed.

- [ ] **Step 2: Verify the existing test suite is green at baseline**

The `pytest tests/ -k "not e2e"` form fails at collection time on this codebase because `*_e2e.py` files import Playwright fixtures that touch the network at collection time. Use the explicit unit-test file list (the same set SP2's plan used at HEAD `1822595`):

```bash
micromamba run -n shiny python -m pytest \
  tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py \
  tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py \
  tests/test_report.py tests/test_templates.py tests/test_network.py \
  tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py \
  tests/test_regional_seas.py -q
```
Expected: `134 passed` (or whatever the current main HEAD baseline is — confirm with `git log --oneline -1` shows `c793001` or later).

**Save this command** — it is the canonical "run all unit tests without picking up e2e collection" form, used in every Step-N verification gate below.

- [ ] **Step 3: Verify spec exists and is at the expected commit**

Run:
```bash
ls docs/superpowers/specs/2026-05-03-ai-isa-wizard-sp3-design.md && git log -1 --oneline -- docs/superpowers/specs/2026-05-03-ai-isa-wizard-sp3-design.md
```
Expected: file exists; most-recent commit is `c793001` (or later if SP3 spec gets further fixes before plan execution).

- [ ] **Step 4: Verify R source-of-truth is accessible**

Run:
```bash
ls "../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R" && wc -l "../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R"
```
Expected: file exists; `wc -l` reports `1009 ± 5` lines (the spec was written against 1009 LOC; small drift from cosmetic R-side edits is OK as long as the line ranges cited in spec §1 remain approximately correct).

If R source is missing, stop. Tasks 1 and 2 cannot proceed without it. The spec's §8 Task 0 declares R-access as a hard prerequisite.

- [ ] **Step 5: Spot-check key R line ranges referenced by the plan**

Run:
```bash
sed -n '343,370p' "../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R" | head -5
```
Expected: shows `connection_keywords <- list(` and the start of `drivers_activities = c("fish", ...)`.

Run:
```bash
sed -n '513,529p' "../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R"
```
Expected: shows the verb-selection `if/else if` chain (`drivers` → `"drives"`, `activities` → `"increases"`/`"causes"`, etc.).

- [ ] **Step 6: Check current branch and clean working tree**

Run:
```bash
git status && git rev-parse --abbrev-ref HEAD
```
Expected: `On branch main` and either `nothing to commit, working tree clean` OR `nothing added to commit but untracked files present` (the `.tmp/` and `.claude/` directories are NOT in `.gitignore` — they're untracked but harmless; ignore-listed only via not being added). Final line of the chained command should print `main`.

**STOP if branch is not main:** the plan was authored against `c793001` on main. If the working tree is on another branch (e.g., `feat/analysis-bot`) or has tracked-file modifications, the SP3 branch will be cut from the wrong parent and contain unrelated changes. In that case, before continuing:
1. Either complete and merge the in-flight branch to main, OR stash its changes (`git stash push -u -m "SP3 plan parking"`).
2. Switch to main: `git checkout main && git pull` (skip the pull if no remote configured).
3. Verify the HEAD: `git log --oneline -1` should show `c793001` or a later commit on main.
4. Re-run Step 6.

- [ ] **Step 7: Cut the SP3 branch**

Run:
```bash
git checkout -b feat/ai-isa-wizard-sp3
git status && git log --oneline -1
```
Expected: `On branch feat/ai-isa-wizard-sp3`; HEAD is `c793001` (or whatever main HEAD was at branch-cut time).

(No commit — Task 0 is read-only verification + branch creation.)

---

## Task 1: Create `sespy/connection_keywords.json` with 10 type-keyword lists + 4 polarity word sets

**Files:**
- Create: `sespy/connection_keywords.json`

The JSON ports R's content verbatim from these line ranges (verified in Task 0 Step 5):
- R lines 87–91: `negative_keywords` (24 stems)
- R lines 94–98: `positive_keywords` (18 stems)
- R lines 101–105: `mitigation_keywords` (17 stems)
- R lines 343–370: `connection_keywords` list of 9 keys (note: R has 9, not 10 — `welfare_drivers` is the SP3 hand-curated 10th list per spec §3)
- R lines 440–444: `loss_keywords` (19 stems)

The `welfare_drivers` 8-stem list is **hand-curated by SP3** because R omits it (would otherwise fall through to R's `0.5` default at line 376). Spec §3 chose `concern, demand, advocacy, campaign, lobby, policy, legislation, awareness` and explicitly dropped `"pressure"` to avoid substring-collision with the framework's own `pressures` element type.

- [ ] **Step 1: Write the JSON file**

Use the `Write` tool to create `sespy/connection_keywords.json` with this exact content (1-to-1 port of R, no truncations):

```json
{
  "connection_types": {
    "drivers_activities": [
      "fish", "food", "econom", "livelihood", "subsistence",
      "commerc", "industr", "recreat", "tourism", "develop",
      "demand", "need", "cultural", "spiritual"
    ],
    "activities_pressures": [
      "fish", "extract", "harvest", "develop", "construct",
      "pollut", "discharge", "emission", "waste", "noise",
      "disturb", "remov", "introduc", "invasive"
    ],
    "pressures_states": [
      "pollut", "nutrient", "contamin", "extract", "remov",
      "habitat", "species", "abundance", "diversity", "structure",
      "function", "ecosystem", "chemical", "physical", "biological"
    ],
    "states_impacts": [
      "decline", "loss", "degrad", "change", "abundance",
      "diversity", "habitat", "ecosystem", "service", "provision",
      "regulat", "cultural", "support"
    ],
    "impacts_welfare": [
      "food", "protein", "nutrition", "income", "livelihood",
      "employ", "health", "wellbeing", "recreation", "cultural",
      "spiritual", "aesthetic", "economic", "social"
    ],
    "responses_pressures": [
      "regulat", "protect", "conserv", "restor", "manag",
      "monitor", "enforc", "limit", "restrict", "ban",
      "quota", "closure", "zone", "designation"
    ],
    "responses_drivers": [
      "policy", "awareness", "education", "incentiv", "subsid",
      "tax", "regulation", "enforcement", "behavior", "demand"
    ],
    "responses_activities": [
      "limit", "restrict", "ban", "regulat", "control",
      "manage", "permit", "license", "quota", "closure",
      "zone"
    ],
    "welfare_drivers": [
      "concern", "demand", "advocacy", "campaign", "lobby",
      "policy", "legislation", "awareness"
    ],
    "welfare_responses": [
      "concern", "awareness", "demand", "advocacy", "pressure",
      "policy", "legislation", "management", "action",
      "intervention"
    ]
  },
  "polarity_signals": {
    "negative_keywords": [
      "declin", "degrad", "loss", "reduc", "damag", "destruct", "pollut",
      "eutrophic", "overfish", "bycatch", "invasive", "extinct", "harm",
      "contaminat", "erosion", "acidific", "hypox", "dead zone", "bleach",
      "disease", "mortality", "collapse", "fragment", "depletion"
    ],
    "positive_keywords": [
      "increas", "growth", "restor", "recover", "improv", "enhanc", "protect",
      "conserv", "benefit", "health", "sustain", "resilient", "biodiver",
      "abundance", "productiv", "regenerat", "rehabilit", "rebui"
    ],
    "mitigation_keywords": [
      "ban", "prohibit", "restrict", "limit", "regulat", "control", "manag",
      "reduce", "prevent", "mitigat", "protect", "enforce", "monitor",
      "stop", "remov", "clean", "treat"
    ],
    "loss_keywords": [
      "loss", "decline", "declin", "degrad", "reduc", "damag", "destruct",
      "decreas", "diminish", "deplet", "erosion", "collapse", "extinct",
      "mortality", "death", "disappear", "absent", "lack", "scarcity"
    ]
  }
}
```

- [ ] **Step 2: Verify JSON parses and has the expected structure**

Run:
```bash
micromamba run -n shiny python -c "import json; d = json.load(open('sespy/connection_keywords.json')); print('connection_types keys:', sorted(d['connection_types'].keys())); print('polarity_signals keys:', sorted(d['polarity_signals'].keys())); print('negative count:', len(d['polarity_signals']['negative_keywords'])); print('positive count:', len(d['polarity_signals']['positive_keywords'])); print('mitigation count:', len(d['polarity_signals']['mitigation_keywords'])); print('loss count:', len(d['polarity_signals']['loss_keywords']))"
```
Expected output (literal):
```
connection_types keys: ['activities_pressures', 'drivers_activities', 'impacts_welfare', 'pressures_states', 'responses_activities', 'responses_drivers', 'responses_pressures', 'states_impacts', 'welfare_drivers', 'welfare_responses']
polarity_signals keys: ['loss_keywords', 'mitigation_keywords', 'negative_keywords', 'positive_keywords']
negative count: 24
positive count: 18
mitigation count: 17
loss count: 19
```

- [ ] **Step 3: Commit**

```bash
git add sespy/connection_keywords.json
git commit -m "$(cat <<'EOF'
feat(connection_scorer): keyword JSON ported from R generator

10 connection-type keyword lists (9 verbatim from R lines 343-370 +
welfare_drivers SP3 hand-curated 8-stem list per spec §3) plus 4
polarity-signal word sets (negative=24, positive=18, mitigation=17,
loss=19 stems verbatim from R lines 87-91, 94-98, 101-105, 441-444).

The welfare_drivers stems mirror welfare_responses semantically
(both encode 'welfare drives behavior'); 'pressure' is omitted
since SP3 hand-curates this list rather than mirroring R verbatim
(R has no welfare_drivers list at all — see spec §3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Relocate `ELEMENT_TYPE_MAP` from `wizard.py` to `data_structure.py` (prerequisite for Tasks 3-9)

**Files:**
- Modify: `sespy/data_structure.py` (add ELEMENT_TYPE_MAP)
- Modify: `sespy/wizard.py` (remove local ELEMENT_TYPE_MAP, re-export from data_structure)

This 5-line refactor must run BEFORE Task 3 (scorer skeleton) because Task 3's `connection_scorer.py` imports `ELEMENT_TYPE_MAP` from `data_structure` at module top. Without this relocation, Tasks 3-9 would fail on cold import. Doing it here also breaks the would-be circular import: `connection_scorer.py` imports from `data_structure` (its post-relocation home); `wizard.py` re-exports `ELEMENT_TYPE_MAP` so SP1 callers (`tests/test_wizard.py:5-6`, `sespy/modules/ai_isa_wizard.py`) keep working unchanged.

- [ ] **Step 1: Inspect `sespy/data_structure.py` to find the right insertion point**

Run:
```bash
micromamba run -n shiny python -c "import ast; src = open('sespy/data_structure.py').read(); tree = ast.parse(src); print('\\n'.join(f'{n.lineno}: {type(n).__name__} {getattr(n, \"name\", \"\")}' for n in tree.body))"
```
Expected: a list of top-level statements showing where imports end and dataclasses begin. Use that to pick the insertion point — ideally just before the first `@dataclass` block (line ~22 historically, but verify).

- [ ] **Step 2: Insert ELEMENT_TYPE_MAP into data_structure.py**

Use the `Edit` tool to insert the constant just before the `Element` dataclass. The anchor `@dataclass\nclass Element:` is unique in this file (other dataclasses are Connection, IsaData, ProjectMetadata, Project, WizardState, ConnectionSuggestion).

**Concrete `Edit` parameters** (verified against `sespy/data_structure.py` lines 19-23 at HEAD `c793001`):

`old_string` (5 lines, including 2 blank lines that already separate `PROJECT_SCHEMA_VERSION` from `@dataclass`):

```
PROJECT_SCHEMA_VERSION = 2


@dataclass
class Element:
```

`new_string` (the entire 5-line `old_string` with the `ELEMENT_TYPE_MAP` block inserted between `PROJECT_SCHEMA_VERSION = 2` and `@dataclass`; preserves the 2 blank lines that already exist before `@dataclass`):

```
PROJECT_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Wizard target → SESPy Element.type mapping for steps 4-10.
#
# Authoritative source for the wizard-target → element-type relationship.
# The id prefixes in sespy/constants.py::ELEMENT_ID_PREFIX encode the same
# relationship via the id prefix (impacts→ES→Ecosystem Services,
# welfare→GB→Goods & Benefits).
#
# Lives in data_structure.py (not wizard.py) so sespy/connection_scorer.py
# can import it without creating a cycle: wizard.py imports
# connection_scorer.py for suggest_connections, and connection_scorer.py
# needs the element-type → slug mapping. Anchoring the constant here
# (alongside the Element.type strings it references) gives a linear
# import graph: data_structure → (stdlib only); wizard → data_structure,
# regional_seas, connection_scorer; connection_scorer → data_structure.
#
# Re-exported from sespy/wizard.py for SP1 caller compatibility.
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


@dataclass
class Element:
```

(The new_string starts and ends with the same boundary lines as `old_string`; only the middle is new content — keeps blank-line spacing PEP-8 compliant.)

- [ ] **Step 3: Verify ELEMENT_TYPE_MAP loads from data_structure.py**

Run:
```bash
micromamba run -n shiny python -c "from sespy.data_structure import ELEMENT_TYPE_MAP; print(ELEMENT_TYPE_MAP['states'])"
```
Expected: `Marine Processes & Functioning`.

- [ ] **Step 4: Remove ELEMENT_TYPE_MAP from wizard.py and re-export from data_structure**

Read the current state of `sespy/wizard.py` at the import block and the current `ELEMENT_TYPE_MAP` definition (currently around line 60-68 per spec §6):

```bash
sed -n '1,30p' sespy/wizard.py && echo "---ELEMENT_TYPE_MAP block---" && sed -n '55,75p' sespy/wizard.py
```

Use `Edit` (one or two operations):
1. Update the existing `from .data_structure import WizardState, ConnectionSuggestion` line (or whatever its current form) to add `ELEMENT_TYPE_MAP` to the imported names.
2. Delete the local `ELEMENT_TYPE_MAP: dict[str, str] = { ... }` block (the 7-line dict literal plus its leading docstring/comment block).

After editing, the wizard.py `from .data_structure` import should look like:

```python
from .data_structure import WizardState, ConnectionSuggestion, ELEMENT_TYPE_MAP
```

(Or whichever exact form matches the existing wizard.py imports; preserve PEP-8 and project style.)

- [ ] **Step 5: Verify wizard.py still has ELEMENT_TYPE_MAP accessible (re-export works)**

Run:
```bash
micromamba run -n shiny python -c "from sespy.wizard import ELEMENT_TYPE_MAP; print(ELEMENT_TYPE_MAP['states'])"
```
Expected: `Marine Processes & Functioning`.

This proves SP1 callers (`tests/test_wizard.py:5-6` and `sespy/modules/ai_isa_wizard.py`) keep working unchanged — they import `ELEMENT_TYPE_MAP` from `sespy.wizard` and the re-export forwards to its new home in `data_structure`.

- [ ] **Step 6: Run all existing SP1 wizard tests to verify no regression**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_wizard.py -v
```
Expected: All wizard tests pass (the renamed test in Task 10 hasn't run yet, so the SP1 stub-empty test still has its original name and still passes).

- [ ] **Step 7: Commit**

```bash
git add sespy/data_structure.py sespy/wizard.py
git commit -m "$(cat <<'EOF'
refactor(data_structure): move ELEMENT_TYPE_MAP to break SP3 import cycle

Relocate ELEMENT_TYPE_MAP from sespy/wizard.py to sespy/data_structure
.py (its conceptual home alongside the Element.type strings it
references). wizard.py re-exports via 'from .data_structure import
ELEMENT_TYPE_MAP' so SP1 callers (tests/test_wizard.py:5-6, sespy/
modules/ai_isa_wizard.py) keep working unchanged.

Post-relocation dependency graph is linear:
  data_structure → (stdlib only)
  wizard → data_structure, regional_seas, connection_scorer
  connection_scorer → data_structure (NOT wizard)

This unblocks Task 3's (and subsequent tasks') top-level import of
ELEMENT_TYPE_MAP from data_structure — the would-be import cycle is
broken at the architecture level instead of papered over with a lazy
import.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create `sespy/connection_scorer.py` skeleton (loader + module-level constants) + Group 1 schema tests

**Files:**
- Create: `sespy/connection_scorer.py`
- Create: `tests/test_connection_scorer.py`

This task creates the module skeleton with the loader, module-level constants, and the 5 Group-1 schema tests. Subsequent tasks (4-9) add one function at a time.

- [ ] **Step 1: Write the failing schema tests first (TDD red)**

Use the `Write` tool to create `tests/test_connection_scorer.py` with this initial content (Group 1 only):

```python
"""Unit tests for sespy.connection_scorer — connection-scoring backend.

Test groups (per spec §7):
  G1 (this file's first 5 tests): JSON schema / loader
  G2: calculate_relevance (added in Task 4)
  G3: detect_polarity (added in Tasks 5-6)
  G4: _select_verb + _generate_smart_connections (added in Tasks 7-8)
  G5: suggest_connections — the SP3 contract (added in Task 9)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Group 1: JSON schema / loader (5 tests)
# ---------------------------------------------------------------------------

def test_keywords_json_loads():
    """File loads via _load_keywords() without error."""
    from sespy.connection_scorer import _load_keywords
    kw = _load_keywords()
    assert isinstance(kw, dict)
    assert "connection_types" in kw
    assert "polarity_signals" in kw


def test_all_10_connection_types_present():
    """Set-equality on connection_types keys against the 10 expected slugs."""
    from sespy.connection_scorer import _KW
    expected = {
        "drivers_activities", "activities_pressures", "pressures_states",
        "states_impacts", "impacts_welfare",
        "responses_pressures", "responses_drivers", "responses_activities",
        "welfare_drivers", "welfare_responses",
    }
    assert set(_KW["connection_types"].keys()) == expected


def test_polarity_signals_keys_present():
    """Set-equality on the 4 polarity-signal keys."""
    from sespy.connection_scorer import _KW
    expected = {"negative_keywords", "positive_keywords",
                "mitigation_keywords", "loss_keywords"}
    assert set(_KW["polarity_signals"].keys()) == expected


def test_every_keyword_list_non_empty():
    """All connection_types lists and all polarity_signals lists have len >= 1.

    Includes welfare_drivers — the SP3 hand-curated addition. Pinning
    non-emptiness here protects against a future 'minimize JSON' pass
    silently dropping the curated list.
    """
    from sespy.connection_scorer import _KW
    for slug, kws in _KW["connection_types"].items():
        assert len(kws) >= 1, f"{slug}: connection_types list is empty"
    for name, kws in _KW["polarity_signals"].items():
        assert len(kws) >= 1, f"{name}: polarity_signals list is empty"


def test_keywords_are_lowercase_and_stripped():
    """Canonicalization invariant: every keyword == kw.lower().strip()."""
    from sespy.connection_scorer import _KW
    for slug, kws in _KW["connection_types"].items():
        for kw in kws:
            assert kw == kw.lower().strip(), (
                f"{slug}: keyword {kw!r} is not lowercase/stripped"
            )
    for name, kws in _KW["polarity_signals"].items():
        for kw in kws:
            assert kw == kw.lower().strip(), (
                f"{name}: keyword {kw!r} is not lowercase/stripped"
            )
```

- [ ] **Step 2: Run the tests to verify they fail (no module yet)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: 5 errors / failures with `ModuleNotFoundError: No module named 'sespy.connection_scorer'` or similar.

- [ ] **Step 3: Write the minimal scorer skeleton (loader + constants)**

Use the `Write` tool to create `sespy/connection_scorer.py` with this content:

```python
"""Connection scoring backend for the AI-ISA wizard (SP3).

Pure-Python rule-based scoring across all 10 DAPSI(W)R(M) connection
types. Loads a keyword JSON eagerly at module import; exposes
suggest_connections(state) as the SP3 contract — same signature as
SP1's stub, replacing it via sespy/wizard.py.

R source-of-truth: ../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/
connection_generator.R (1009 LOC; SP3 ports lines 62-187, 198-226,
264-323, 338-387, 436-574, 755-1001 with KB-lookup and ML branches
dropped per scope).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .data_structure import (
    WizardState,
    ConnectionSuggestion,
    Element,
    ELEMENT_TYPE_MAP,  # post-Task-2 home (data_structure.py)
)


_KW_PATH = Path(__file__).parent / "connection_keywords.json"
_logger = logging.getLogger(__name__)


def _load_keywords() -> dict[str, Any]:
    """Read and parse the keyword JSON. Called once at module import."""
    with _KW_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_KW = _load_keywords()
_TYPE_TO_SLUG = {v: k for k, v in ELEMENT_TYPE_MAP.items()}
# {"Drivers": "drivers", "Activities": "activities", ...,
#  "Marine Processes & Functioning": "states", "Ecosystem Services": "impacts",
#  "Goods & Benefits": "welfare", "Responses": "responses"}

_MAX_PER_TYPE = 15
_MIN_RELEVANCE = 0.3

# 10 connection types as (from_slug, to_slug, conn_type_key) tuples.
# Iteration order matches R's natural DAPSI(W)R(M) layer flow at
# connection_generator.R:755+. The conn_type_key is f"{from_slug}_{to_slug}"
# matching R's paste(from_type, to_type, sep="_") at line 373.
_CONN_TYPES: list[tuple[str, str, str]] = [
    ("drivers", "activities", "drivers_activities"),
    ("activities", "pressures", "activities_pressures"),
    ("pressures", "states", "pressures_states"),
    ("states", "impacts", "states_impacts"),
    ("impacts", "welfare", "impacts_welfare"),
    ("responses", "pressures", "responses_pressures"),
    ("responses", "drivers", "responses_drivers"),
    ("responses", "activities", "responses_activities"),
    ("welfare", "drivers", "welfare_drivers"),
    ("welfare", "responses", "welfare_responses"),
]

# Reversal-compounds used by _analyze_polarity_phrase to detect
# "negative-of-negative" phrases (e.g., "pollution reduction" → positive).
# Bare X.*Y stems with no \b boundaries — matches R lines 216-218 verbatim.
# Algorithm-shape (regex), kept inline rather than in JSON.
_REVERSAL_COMPOUNDS: list[str] = [
    r"pollut.*reduc",  r"emission.*reduc",  r"pressure.*reduc",
    r"litter.*reduc",  r"waste.*reduc",     r"noise.*reduc",
    r"overfish.*prevent",  r"erosion.*control",
]

# Negation-regex patterns with \b word boundaries — matches R lines 209-211
# verbatim. Algorithm-shape (regex), kept inline rather than in JSON.
_NEGATION_PATTERNS: list[str] = [
    r"\bno\b",       r"\bnot\b",       r"\bnon[- ]",     r"\bwithout\b",
    r"\bprevent",    r"\bban\b",       r"\breduc",       r"\bremov",
    r"\bcontrol",    r"\blimit",       r"\brestrict",
]
```

(The 4 functions and 2 helpers are added in Tasks 4-9 — leave the file ending at `_NEGATION_PATTERNS`. Tests only need the module-level loader + `_KW` dict at this point.)

- [ ] **Step 4: Run the schema tests to verify they pass**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: `5 passed`.

If any test fails, re-read the JSON content from Task 1 — the most likely cause is a typo in the keyword stems or the connection-type slug names.

- [ ] **Step 5: Verify the scorer module imports cleanly end-to-end**

Run:
```bash
micromamba run -n shiny python -c "from sespy.connection_scorer import _KW, _TYPE_TO_SLUG, _CONN_TYPES, _MAX_PER_TYPE, _MIN_RELEVANCE, _REVERSAL_COMPOUNDS, _NEGATION_PATTERNS; print('module loads; conn types:', len(_CONN_TYPES))"
```
Expected: `module loads; conn types: 10`. (This works because Task 2 already moved `ELEMENT_TYPE_MAP` to `data_structure.py`; the import graph is linear at this point.)

- [ ] **Step 6: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): loader module with module-level constants and 5 schema tests

Eager _KW = _load_keywords() at module import (mirrors SP2's
regional_seas.py pattern). Defines _MAX_PER_TYPE=15, _MIN_RELEVANCE=
0.3, the 10-tuple _CONN_TYPES list, and module-level _REVERSAL_
COMPOUNDS (8 patterns) and _NEGATION_PATTERNS (11 patterns) regex
constants. The 5 Group-1 schema tests pin set-equality of
connection_types and polarity_signals keys, non-emptiness, and the
lowercase/stripped canonicalization invariant.

The ELEMENT_TYPE_MAP import is from sespy.data_structure (post-Task-2
home; the relocation in Task 2 broke the would-be circular import
ahead of this commit so the module loads cleanly on cold import).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Implement `calculate_relevance` + Group 2 tests (6 tests)

**Files:**
- Modify: `sespy/connection_scorer.py` (append function)
- Modify: `tests/test_connection_scorer.py` (append Group 2 section)

`calculate_relevance` is a direct port of R's `.calculate_basic_relevance` at `connection_generator.R:338-387`. Substring match (`re.search(re.escape(kw), name_lower)`) — NOT token-exact match. Score thresholds: `0 → 0.3`, `1 → 0.6`, `2+ → 0.9`. Default `0.5` for unknown type-pair (R line 376; defensive — schema test pins all 10 keys present).

- [ ] **Step 1: Write the 6 failing Group-2 tests first (TDD red)**

Append to `tests/test_connection_scorer.py`:

```python


# ---------------------------------------------------------------------------
# Group 2: calculate_relevance (6 tests)
# ---------------------------------------------------------------------------

def test_zero_matches_returns_03():
    """Names with no keyword substring match → 0.3 (R's Low relevance floor)."""
    from sespy.connection_scorer import calculate_relevance
    # "Tractor" / "Bicycle" share no keyword stems with drivers_activities
    # (which has "fish", "food", "econom", "livelihood", ...).
    assert calculate_relevance("Tractor", "Bicycle", "drivers", "activities") == 0.3


def test_one_match_returns_06():
    """Exactly one keyword substring match across both names → 0.6."""
    from sespy.connection_scorer import calculate_relevance
    # "Fishing" matches "fish" stem (1 match in from_name); "Bicycle" matches
    # nothing → total_matches = 1 → 0.6.
    assert calculate_relevance("Fishing", "Bicycle", "drivers", "activities") == 0.6


def test_two_plus_matches_returns_09():
    """Two or more keyword substring matches → 0.9."""
    from sespy.connection_scorer import calculate_relevance
    # "Fishing" matches "fish"; "Tourism" matches "tourism" → total_matches = 2 → 0.9.
    assert calculate_relevance("Fishing", "Tourism", "drivers", "activities") == 0.9


def test_relevance_uses_substring_match():
    """'Fishing' matches keyword stem 'fish' (substring, not token-exact).

    Pinned because the substring-vs-token semantics is load-bearing —
    token-exact match would miss most real labels (R uses grepl, not
    word-boundary match).
    """
    from sespy.connection_scorer import calculate_relevance
    # If the implementation used token-exact match (e.g., 'fish' in name.split()),
    # 'Fishing' would NOT match 'fish' and this would return 0.3 (no matches).
    # With substring match, it matches and returns 0.6 (1 match in from_name).
    assert calculate_relevance("Fishing", "XYZ", "drivers", "activities") == 0.6


def test_relevance_is_case_insensitive():
    """'FISHING' matches keyword 'fish' (input lowercased before matching)."""
    from sespy.connection_scorer import calculate_relevance
    assert calculate_relevance("FISHING", "XYZ", "drivers", "activities") == 0.6


def test_relevance_unknown_pair_returns_05():
    """Unknown (from_slug, to_slug) pair → 0.5 (R's defensive default at line 376).

    Pins the defensive path so a future removal is a deliberate decision.
    Schema test guarantees all 10 valid pairs are present, so this only
    fires on coding errors.
    """
    from sespy.connection_scorer import calculate_relevance
    # "garbage_bogus" is not a valid slug pair; the lookup falls through to 0.5.
    assert calculate_relevance("X", "Y", "garbage", "bogus") == 0.5
```

- [ ] **Step 2: Run the new tests to verify they fail (TDD red)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v -k "test_zero_matches or test_one_match or test_two_plus or test_relevance"
```
Expected: 6 failures with `ImportError: cannot import name 'calculate_relevance'` or `AttributeError`.

- [ ] **Step 3: Implement `calculate_relevance` (TDD green)**

Append to `sespy/connection_scorer.py` (after the `_NEGATION_PATTERNS` constant):

```python


def calculate_relevance(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> float:
    """Return one of {0.3, 0.6, 0.9} based on keyword-substring-match
    count across both names (0 matches → 0.3 floor, 1 → 0.6, 2+ → 0.9).
    Returns 0.5 if the (from_slug, to_slug) pair is missing from the
    keyword JSON (defensive default at R line 376; schema test pins all
    10 pairs present so 0.5 doesn't fire in normal operation).

    Slug params are lowercase (e.g., "drivers", "states"), NOT human
    Element.type strings.

    Direct port of R's .calculate_basic_relevance at
    connection_generator.R:338-387.
    """
    key = f"{from_slug}_{to_slug}"
    keywords = _KW["connection_types"].get(key)
    if keywords is None:
        return 0.5

    from_lower = from_name.lower()
    to_lower = to_name.lower()
    from_matches = sum(
        1 for kw in keywords if re.search(re.escape(kw), from_lower)
    )
    to_matches = sum(
        1 for kw in keywords if re.search(re.escape(kw), to_lower)
    )
    total_matches = from_matches + to_matches

    if total_matches == 0:
        return 0.3
    if total_matches == 1:
        return 0.6
    return 0.9
```

- [ ] **Step 4: Run the Group-2 tests to verify they pass**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: `11 passed` (5 Group-1 + 6 Group-2).

- [ ] **Step 5: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): calculate_relevance with substring matching + 6 tests

Direct port of R's .calculate_basic_relevance at connection_generator
.R:338-387. Substring match via re.search(re.escape(kw), name_lower)
mirrors R's grepl byte-for-byte (no token-exact match, no Python
word-boundaries). Score thresholds: 0 matches → 0.3, 1 → 0.6, 2+ →
0.9; defensive 0.5 for unknown type-pair at R line 376.

Group 2 (6 tests): pins the 0/1/2+ → 0.3/0.6/0.9 mapping, substring-
vs-token semantics, case-insensitivity, and the defensive 0.5 path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Implement `_analyze_polarity_phrase` + 1 Group-3 test (the helper-specific one)

**Files:**
- Modify: `sespy/connection_scorer.py` (append helper)
- Modify: `tests/test_connection_scorer.py` (append Group 3 first test)

`_analyze_polarity_phrase` is the per-name polarity helper consumed by `detect_polarity` (Task 5). It runs two regex checks against the lowercased name; reversal-compounds take precedence over negation-patterns in the return. Returns one of three tuples: `("positive", True)`, `("neutral", True)`, or `("neutral", False)`. Never returns `("negative", *)` — R's helper has no path emitting that string. R's third return field `base_sentiment` is dropped (unused by R's `detect_polarity`).

- [ ] **Step 1: Write the failing test (TDD red)**

Append to `tests/test_connection_scorer.py`:

```python


# ---------------------------------------------------------------------------
# Group 3: detect_polarity (7 tests)
# ---------------------------------------------------------------------------

def test_analyze_polarity_phrase_reversal_compound():
    """The helper detects 'negative-of-negative' phrases as ('positive', True)
    via the 8-pattern reversal-compounds list (R lines 216-218).

    Falsifiable invariant for the load-bearing reversal-compound list:
    'pollution reduction' returns ('positive', True), 'emission reduction'
    likewise, an unrelated phrase returns ('neutral', False), a phrase
    matching only a negation pattern returns ('neutral', True).
    """
    from sespy.connection_scorer import _analyze_polarity_phrase

    # Reversal-compound matches → ("positive", True)
    assert _analyze_polarity_phrase("pollution reduction") == ("positive", True)
    assert _analyze_polarity_phrase("emission reduction") == ("positive", True)
    assert _analyze_polarity_phrase("overfish prevention") == ("positive", True)

    # No reversal, no negation → ("neutral", False)
    assert _analyze_polarity_phrase("fishing activity") == ("neutral", False)

    # Negation only (no reversal-compound match) → ("neutral", True)
    # "no biodiversity" matches \bno\b but not any reversal compound.
    assert _analyze_polarity_phrase("no biodiversity") == ("neutral", True)
```

- [ ] **Step 2: Run the test to verify it fails (TDD red)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py::test_analyze_polarity_phrase_reversal_compound -v
```
Expected: failure with `ImportError: cannot import name '_analyze_polarity_phrase'` or `AttributeError`.

- [ ] **Step 3: Implement `_analyze_polarity_phrase` (TDD green)**

Append to `sespy/connection_scorer.py` (after `calculate_relevance`):

```python


def _analyze_polarity_phrase(name_lower: str) -> tuple[str, bool]:
    """Return (sentiment, negated) for a single name. Two-check scheme;
    reversal takes precedence in the return.

    Returns only ("positive", True), ("neutral", True), or
    ("neutral", False) — never ("negative", *). R's helper has no path
    emitting "negative" sentiment; the negative semantic is captured
    separately by the from_is_negative / to_is_negative substring flags
    computed in detect_polarity Step A (see §5 of the spec).

    Direct port of R's .analyze_polarity_phrase at
    connection_generator.R:198-226. R's third return field
    base_sentiment is dropped — R's detect_polarity (R 117-186) reads
    only sentiment and negated.

    Implementation notes:
    - name_lower is assumed already lowercased by the caller (matches
      R's code path where tolower() runs before this helper).
    - Reversal-compounds are checked first to give them return-priority.
      In R, both checks compute their flags before the early return on
      reversal; either order produces the same observable behaviour.
    - Pattern lists _REVERSAL_COMPOUNDS and _NEGATION_PATTERNS are
      module-level (algorithm-shape, not data; see §5).
    """
    # Phase 1: reversal-compounds (precedence in return).
    for pattern in _REVERSAL_COMPOUNDS:
        if re.search(pattern, name_lower):
            return ("positive", True)

    # Phase 2: negation regex with \b boundaries.
    for pattern in _NEGATION_PATTERNS:
        if re.search(pattern, name_lower):
            return ("neutral", True)

    return ("neutral", False)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py::test_analyze_polarity_phrase_reversal_compound -v
```
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): _analyze_polarity_phrase with reversal compounds

Direct port of R's .analyze_polarity_phrase at connection_generator
.R:198-226 (KB-aware fallback at lines 199-207 dropped per scope).
Two-check scheme: 8 reversal-compound regexes (R 216-218) take
precedence over 11 negation regex patterns with \\b word boundaries
(R 209-211). Returns only ('positive', True), ('neutral', True), or
('neutral', False) — never ('negative', *). R's third base_sentiment
field is dropped because detect_polarity never reads it.

The helper's negation-detection is the gateway for the
('activities', 'pressures') mitigation-by-reversal branch — without
it, 'Pollution reduction' would not be detected as a positive-
sentiment activity that reduces pressure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Implement `detect_polarity` + remaining 6 Group-3 tests

**Files:**
- Modify: `sespy/connection_scorer.py` (append function)
- Modify: `tests/test_connection_scorer.py` (append 6 Group-3 tests)

`detect_polarity` is a per-pair dispatch over `(from_slug, to_slug)`. R's structure is precomputed-per-name signals + per-pair branches with embedded conditional logic (NOT a 3-layer fall-through). Spec §5 has the full dispatch table; this task implements all branches.

- [ ] **Step 1: Write the 6 failing Group-3 tests (TDD red)**

Append to `tests/test_connection_scorer.py` (after the helper test from Task 4):

```python


def test_responses_to_pressures_is_minus():
    """Always '-' regardless of names (R line 117 invariant)."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Foo", "Bar", "responses", "pressures") == "-"
    assert detect_polarity("Marine policy", "Pollution",
                          "responses", "pressures") == "-"


def test_activities_to_pressures_mitigation_is_minus():
    """'Pollution reduction' from activities → '-' via the reversal-compound
    path: _analyze_polarity_phrase returns ('positive', True), then dispatch
    checks from_analysis.sentiment == 'positive' (R lines 133-138)."""
    from sespy.connection_scorer import detect_polarity
    assert detect_polarity("Pollution reduction", "Eutrophication",
                          "activities", "pressures") == "-"


def test_activities_to_pressures_default_is_plus():
    """Neutral names → '+' (default for activities → pressures)."""
    from sespy.connection_scorer import detect_polarity
    # "Tourism" has no mitigation_keywords match, no reversal-compound match.
    # → from_is_mitigation=False, from_analysis.sentiment="neutral" → default "+".
    assert detect_polarity("Tourism", "Noise", "activities", "pressures") == "+"


def test_pressures_to_states_branches():
    """All three pressures→states branches (R lines 144-150):
    - to_is_negative=True → "+" (pressure increases negative state)
    - to_is_positive=True → "-" (pressure decreases positive state)
    - neutral → default "-"

    The to_is_positive branch is observationally identical to the
    default in the current implementation (both return "-") but is
    pinned here so a future refactor that distinguishes them would
    break the test instead of silently changing behavior.
    """
    from sespy.connection_scorer import detect_polarity
    # to_is_negative path: "Fish stocks decline" has "declin" → "+"
    assert detect_polarity("Eutrophication", "Fish stocks decline",
                           "pressures", "states") == "+"
    # to_is_positive path: "Healthy biodiversity" has "health", "biodiver" → "-"
    assert detect_polarity("Eutrophication", "Healthy biodiversity",
                           "pressures", "states") == "-"
    # neutral default path: "Open coastal waters" has no positive/negative
    # keyword → "-"
    assert detect_polarity("Eutrophication", "Open coastal waters",
                           "pressures", "states") == "-"


def test_states_to_impacts_negation_flip():
    """The negation flip (R line 158) zeroes from_is_negative when
    from_analysis.negated AND from_is_negative both hold. This test pins
    the flip behavior with a label whose POST-FLIP polarity output
    differs from its NO-FLIP output — i.e., a label where the flip
    is observable, not a silent no-op.

    Test pair design:
      from_name = "Loss reduction" → matches BOTH a loss_keyword ("loss")
        AND a negation pattern (\\breduc). Without flip:
          from_is_negative=True, from_analysis=("neutral", True).
          Matrix on (states, impacts) with from_is_negative=True and
          to_is_positive=True (e.g., to_name="Cultural service") gives
          opposite-sign → "-".
        With flip (R-faithful): from_is_negative=False, from_is_positive
        is also False (no positive_keyword in "loss reduction"), and
        to_is_positive=True → falls through to default "-".

    Both pre-flip and post-flip happen to give "-" for this pair, so
    we need a different fixture to OBSERVE the flip. Use:
      from_name = "Reduced biodiversity" — has from_is_negative=True
        (matches "reduc") AND from_is_positive=True (matches "biodiver"),
        with from_analysis=("neutral", True) from the negation-pattern
        path. Without flip: matrix would see from_is_negative=True AND
        from_is_positive=True (ambiguous) — neither both-negative nor
        both-positive matches; opposite-sign also doesn't match cleanly;
        falls to default "-".
        With flip (R-faithful): from_is_negative=False (the flip),
        from_is_positive=True (NOT flipped per R line 158-159). With
        to_is_positive=True (e.g., to_name="Healthy ecosystem services"),
        matrix detects (from_is_positive AND to_is_positive) →
        same-sign reinforcement → "+".

    So expected output "+" can ONLY be produced if the negation flip
    correctly zeroed from_is_negative — proving the flip ran. Without
    the flip, both flags stay True and the matrix returns "-".
    """
    from sespy.connection_scorer import detect_polarity
    # Positive expected output proves the flip ran.
    assert detect_polarity(
        "Reduced biodiversity", "Healthy ecosystem services",
        "states", "impacts",
    ) == "+"
    # Negative control: a from_name with no negation flag should NOT
    # trigger the flip; matrix sees from_is_negative=True AND
    # to_is_positive=True → opposite-sign → "-".
    assert detect_polarity(
        "Pollution",  # negative_keyword "pollut" but no negation pattern
        "Healthy ecosystem services",
        "states", "impacts",
    ) == "-"


def test_default_fallback_for_unspecified_pair():
    """(drivers, activities) and other pairs without a named branch return
    '+' per R line 186 (default fallback).
    """
    from sespy.connection_scorer import detect_polarity
    # No named branch for (drivers, activities) — falls through to "+".
    assert detect_polarity("Tourism demand", "Coastal development",
                           "drivers", "activities") == "+"
    # Same for the other 4 default-fallback pairs.
    assert detect_polarity("Marine policy", "Tourism demand",
                           "responses", "drivers") == "+"
    assert detect_polarity("Marine policy", "Coastal development",
                           "responses", "activities") == "+"
    assert detect_polarity("Public concern", "Tourism demand",
                           "welfare", "drivers") == "+"
    assert detect_polarity("Public concern", "Marine policy",
                           "welfare", "responses") == "+"
```

- [ ] **Step 2: Run to verify they fail (TDD red)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v -k "test_responses_to_pressures or test_activities_to_pressures or test_pressures_to_states or test_states_to_impacts or test_default_fallback"
```
Expected: 6 failures with `ImportError: cannot import name 'detect_polarity'` or `AttributeError`.

- [ ] **Step 3: Implement `detect_polarity` (TDD green)**

Append to `sespy/connection_scorer.py` (after `_analyze_polarity_phrase`):

```python


def detect_polarity(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> str:
    """Return '+' or '-' via per-pair dispatch with precomputed per-name
    signals. Faithful to R's structure at connection_generator.R:62-187
    (KB-lookup branch at R 63-75 dropped per scope).

    Slug params are lowercase, NOT human Element.type strings.

    Step A: Precompute per-name signals (R lines 86-112):
      - Lowercase both names.
      - Substring-match polarity_signals keyword sets against each name.
      - Call _analyze_polarity_phrase twice (once per name).

    Step B: Per-pair dispatch over (from_slug, to_slug):
      - ("responses", "pressures"): always "-" (R line 117).
      - ("activities", "pressures"): mitigation-aware (R 133-138).
      - ("pressures", "states"): to-flag-aware (R 143-150).
      - ("states", "impacts"): negation-flip + matrix (R 153-167).
      - ("impacts", "welfare"): negation-flip + simple fall-through (R 170-183).
      - All other pairs: default "+" (R line 186).

    R's KB-lookup branch (R 63-75) and ML-scoring branch are not
    ported per the rule-based-only scope decision. R also has an
    11th branch ("responses", "states") at R 122-130 that SP3 does
    NOT port: _CONN_TYPES (Task 3) only generates 10 type-pairs and
    "responses" → "states" is not among them, so the branch would
    be unreachable dead code. SP4 can re-add it with a test if
    needed (see spec §5 dispatch-table prose).
    """
    from_lower = from_name.lower()
    to_lower = to_name.lower()

    # --- Step A: Precompute per-name signals (universal hoist) -----
    polarity = _KW["polarity_signals"]
    negative_keywords = polarity["negative_keywords"]
    positive_keywords = polarity["positive_keywords"]
    mitigation_keywords = polarity["mitigation_keywords"]

    def _has_any(text: str, kws: list[str]) -> bool:
        return any(re.search(re.escape(kw), text) for kw in kws)

    from_is_negative = _has_any(from_lower, negative_keywords)
    from_is_positive = _has_any(from_lower, positive_keywords)
    to_is_negative = _has_any(to_lower, negative_keywords)
    to_is_positive = _has_any(to_lower, positive_keywords)
    from_is_mitigation = _has_any(from_lower, mitigation_keywords)

    from_analysis = _analyze_polarity_phrase(from_lower)
    to_analysis = _analyze_polarity_phrase(to_lower)

    # --- Step B: Per-pair dispatch ---------------------------------
    # ("responses", "pressures") — R line 117: always "-".
    if from_slug == "responses" and to_slug == "pressures":
        return "-"

    # ("activities", "pressures") — R lines 133-138.
    if from_slug == "activities" and to_slug == "pressures":
        if from_is_mitigation or from_analysis[0] == "positive":
            return "-"
        return "+"

    # ("pressures", "states") — R lines 143-150.
    if from_slug == "pressures" and to_slug == "states":
        if to_is_negative:
            return "+"  # pressure increases negative state
        if to_is_positive:
            return "-"
        return "-"  # default

    # ("states", "impacts") — R lines 153-167.
    if from_slug == "states" and to_slug == "impacts":
        # Negation flip: only negative flags flip; positive flags NEVER flip.
        if from_analysis[1] and from_is_negative:  # from_analysis.negated
            from_is_negative = False
        if to_analysis[1] and to_is_negative:
            to_is_negative = False
        # Matrix:
        if (from_is_negative and to_is_negative) or (
            from_is_positive and to_is_positive
        ):
            return "+"  # same-sign reinforcement
        if (from_is_negative and to_is_positive) or (
            from_is_positive and to_is_negative
        ):
            return "-"  # opposite-sign opposition
        return "-"  # default for ambiguous/neutral pairs

    # ("impacts", "welfare") — R lines 170-183.
    if from_slug == "impacts" and to_slug == "welfare":
        # Only from-side flags are read (R reads only from_*); to_is_*
        # were precomputed in Step A but UNUSED in this branch.
        if from_analysis[1] and from_is_negative:  # from_analysis.negated
            from_is_negative = False
        if from_is_negative:
            return "-"
        if from_is_positive:
            return "+"
        return "-"  # default: impacts reduce welfare

    # All other pairs (D→A, R→D, R→A, W→D, W→R) — R line 186 default.
    return "+"
```

- [ ] **Step 4: Run all Group-3 tests to verify they pass**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: `18 passed` (5 G1 + 6 G2 + 7 G3).

- [ ] **Step 5: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): detect_polarity per-pair dispatch + 6 tests

Direct port of R's detect_polarity at connection_generator.R:62-187.
Per-pair dispatch with precomputed per-name signals (NOT a 3-layer
fall-through):
- ('responses', 'pressures') always '-' (R 117)
- ('activities', 'pressures') mitigation-aware (R 133-138)
- ('pressures', 'states') to-flag-aware (R 143-150)
- ('states', 'impacts') negation-flip + 4-cell matrix (R 153-167);
  flips only negative flags, never positive flags
- ('impacts', 'welfare') negation-flip + from-only fall-through (R 170-183)
- All other pairs (D→A, R→{D,A}, W→{D,R}) default '+' (R line 186)

KB-lookup and ML branches dropped per rule-based-only scope.

Group 3 (6 tests in this commit + the _analyze_polarity_phrase test
from the previous commit = 7 total): pins each named branch's
behavior plus the default fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Implement `_select_verb` + Group-4 verb test (1 test)

**Files:**
- Modify: `sespy/connection_scorer.py` (append helper)
- Modify: `tests/test_connection_scorer.py` (append Group 4 first test — the parameterized verb test)

`_select_verb` is a polarity-aware verb-table lookup used to build the rationale string in `_generate_smart_connections`. Half the from-slugs are polarity-insensitive (drivers always "drives", states always "impacts"); the other half have `+`/`-` variants. Direct port of R lines 513-529.

- [ ] **Step 1: Write the failing parameterized test (TDD red)**

Append to `tests/test_connection_scorer.py`:

```python


# ---------------------------------------------------------------------------
# Group 4: _generate_smart_connections (6 tests)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_slug,polarity,expected_verb",
    [
        # drivers and states are polarity-insensitive (R 514-515, 519-520) —
        # both polarities yield the same verb. The parameterization runs them
        # twice anyway to catch a regression where polarity is accidentally
        # consulted.
        ("drivers", "+", "drives"),
        ("drivers", "-", "drives"),
        ("activities", "+", "increases"),
        ("activities", "-", "causes"),
        ("pressures", "+", "increases"),
        ("pressures", "-", "decreases"),
        ("states", "+", "impacts"),
        ("states", "-", "impacts"),
        ("impacts", "+", "increases"),
        ("impacts", "-", "reduces"),
        ("responses", "+", "enables"),
        ("responses", "-", "restricts"),
        ("welfare", "+", "motivates"),
        ("welfare", "-", "reduces"),
    ],
)
def test_verb_selection_per_from_slug_polarity_pair(from_slug, polarity, expected_verb):
    """Pin the 7 from-slugs × 2 polarities = 14-case verb table verbatim
    (matches R lines 513-529).

    Critical because the verb table lives only in _select_verb's
    docstring + this test. A typo in either drift would ship silently
    without this parameterized coverage.
    """
    from sespy.connection_scorer import _select_verb
    assert _select_verb(from_slug, polarity) == expected_verb
```

- [ ] **Step 2: Run to verify they fail (14 cases × 1 = 14 failures)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py::test_verb_selection_per_from_slug_polarity_pair -v
```
Expected: 14 errors with `ImportError: cannot import name '_select_verb'`.

- [ ] **Step 3: Implement `_select_verb` (TDD green)**

Append to `sespy/connection_scorer.py` (after `detect_polarity`):

```python


def _select_verb(from_slug: str, polarity: str) -> str:
    """Verb for the rationale string, polarity-aware for some types.
    Matches R's verb selection at connection_generator.R:513-529.

        drivers     → "drives"                (polarity-insensitive)
        activities  → "increases" (+) | "causes" (-)
        pressures   → "increases" (+) | "decreases" (-)
        states      → "impacts"               (polarity-insensitive)
        impacts     → "increases" (+) | "reduces" (-)
        responses   → "enables" (+)   | "restricts" (-)
        welfare     → "motivates" (+) | "reduces" (-)
        default     → "affects positively" (+) | "affects negatively" (-)

    The default branch is unreachable from _CONN_TYPES' 7 from-slugs
    (the test parameterization runs only the 7×2=14 valid cases) but
    is included for forward-compat with future Element-type additions.
    """
    if from_slug == "drivers":
        return "drives"
    if from_slug == "activities":
        return "increases" if polarity == "+" else "causes"
    if from_slug == "pressures":
        return "increases" if polarity == "+" else "decreases"
    if from_slug == "states":
        return "impacts"
    if from_slug == "impacts":
        return "increases" if polarity == "+" else "reduces"
    if from_slug == "responses":
        return "enables" if polarity == "+" else "restricts"
    if from_slug == "welfare":
        return "motivates" if polarity == "+" else "reduces"
    # Default fallback for forward-compat
    return "affects positively" if polarity == "+" else "affects negatively"
```

- [ ] **Step 4: Run all 14 verb cases to verify they pass**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py::test_verb_selection_per_from_slug_polarity_pair -v
```
Expected: `14 passed`.

- [ ] **Step 5: Run the full test suite to confirm no regression**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: `32 passed` (5 G1 + 6 G2 + 7 G3 + 14 verb cases — pytest counts each `parametrize` case as a separate test for the test-count purposes here, so the running total looks higher than the spec's 33; the spec counts the parameterized test as 1 logical test which would be 19 passed, but pytest reports each case → `32 passed`).

(The spec's "33 tests" count is logical-test count. pytest's reported count up through Task 7 will be higher than the logical count because Task 7's verb-test parametrize expands into 14 items. By end of Task 9, pytest will report 46 individual test runs across the 33 logical tests.)

- [ ] **Step 6: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): _select_verb with polarity-aware verbs + 14-case test

Direct port of R's verb-selection chain at connection_generator.R:
513-529. Half the from-slugs are polarity-insensitive (drivers,
states); the other 5 have +/- variants. The default branch
('affects positively/negatively') is unreachable from _CONN_TYPES'
7 from-slugs but kept for forward-compat with future Element-type
additions.

The 14-case parameterized test (7 from-slugs × 2 polarities) pins
the verb table verbatim — catches both 'drift between docstring
and implementation' and 'polarity accidentally consulted for an
insensitive slug' regressions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Implement `_generate_smart_connections` + remaining 5 Group-4 tests

**Files:**
- Modify: `sespy/connection_scorer.py` (append function)
- Modify: `tests/test_connection_scorer.py` (append remaining Group-4 tests)

`_generate_smart_connections` is the per-type pair generator: cross-product, threshold filter (vacuous in practice given R's 0.3 floor; pinned for forward-compat), double-negative filter using `loss_keywords` (NOT `negative_keywords`), polarity computation, sort by confidence desc, cap at `max_count`. R lines 436-574.

- [ ] **Step 1: Write the 5 remaining Group-4 tests (TDD red)**

Append to `tests/test_connection_scorer.py`:

```python


def _make_element(eid: str, label: str, etype: str):
    """Helper: build a minimal Element for testing without going through
    the wizard's id-prefix machinery."""
    from sespy.data_structure import Element
    return Element(id=eid, label=label, type=etype)


def test_cross_product_pair_generation():
    """2 from-elements × 3 to-elements → ≤ 6 candidates pre-filter
    (some may drop via double-negative filter).
    """
    from sespy.connection_scorer import _generate_smart_connections
    from_els = [_make_element("D001", "Tourism", "Drivers"),
                _make_element("D002", "Fishing", "Drivers")]
    to_els = [_make_element("A001", "Recreation", "Activities"),
              _make_element("A002", "Commercial fishing", "Activities"),
              _make_element("A003", "Aquaculture", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    # Cross-product is 2×3=6; double-negative filter doesn't apply (no
    # loss_keywords in any name). All 6 pairs survive the threshold
    # because R's 0.3 floor admits everything.
    assert len(result) == 6


def test_double_negative_filter_uses_loss_keywords():
    """Both names contain loss_keywords substring → suggestion dropped.
    Names with negative_keywords that are NOT loss_keywords (e.g.,
    'Pollution') survive.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # Both labels have "loss" / "decline" → loss_keywords match → dropped.
    from_els = [_make_element("S001", "Loss of biodiversity",
                              "Marine Processes & Functioning")]
    to_els = [_make_element("I001", "Decline in fishery yield",
                            "Ecosystem Services")]
    result = _generate_smart_connections(
        from_els, to_els, "states", "impacts"
    )
    assert result == []  # Filtered out

    # Now: one name has only negative_keywords (not loss_keywords).
    # "Pollution" matches negative_keywords but NOT loss_keywords (loss list
    # has decline/declin/degrad/reduc/damag/destruct/decreas/diminish/
    # deplet/erosion/collapse/extinct/mortality/death/disappear/absent/
    # lack/scarcity — no 'pollut'). Pair survives.
    from_els = [_make_element("S002", "Pollution",
                              "Marine Processes & Functioning")]
    to_els = [_make_element("I002", "Loss of habitat",
                            "Ecosystem Services")]
    result = _generate_smart_connections(
        from_els, to_els, "states", "impacts"
    )
    assert len(result) == 1


def test_results_sorted_by_confidence_desc():
    """Output is sorted by confidence descending (stable sort).

    Use a to-element with NO keyword matches ('XYZ') so the from-element
    keyword count solely determines confidence. Otherwise the to-element
    contribution masks the gradient and the test still passes via
    sortedness coincidence rather than the property under test.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # to-name "XYZ" has 0 keyword matches in drivers_activities;
    # from-name match counts: "Tourism fishing"=2, "Tourism"=1, "Bicycle"=0.
    # → confidences {0.9, 0.6, 0.3}.
    from_els = [
        _make_element("D001", "Tourism fishing", "Drivers"),  # 2 stems → 0.9
        _make_element("D002", "Tourism", "Drivers"),          # 1 stem → 0.6
        _make_element("D003", "Bicycle", "Drivers"),          # 0 stems → 0.3
    ]
    to_els = [_make_element("A001", "XYZ", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    confidences = [s.confidence for s in result]
    assert confidences == [0.9, 0.6, 0.3]
    assert confidences == sorted(confidences, reverse=True)


def test_max_count_cap_honored():
    """> 15 candidates → exactly 15 returned."""
    from sespy.connection_scorer import _generate_smart_connections
    # 4 × 5 = 20 candidates; cap at max_count=15.
    from_els = [_make_element(f"D{i:03d}", f"Tourism{i}", "Drivers")
                for i in range(1, 5)]
    to_els = [_make_element(f"A{i:03d}", f"Recreation{i}", "Activities")
              for i in range(1, 6)]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities",
        max_count=15
    )
    assert len(result) == 15


def test_pair_with_relevance_exactly_03_survives():
    """Pin R's >= threshold semantics at the floor: a pair with
    relevance == 0.3 IS emitted (the gate is vacuous given R's floor).
    Future change to min_relevance > 0.3 (or strict >) would change
    this; the test forces a deliberate decision.
    """
    from sespy.connection_scorer import _generate_smart_connections
    # No keyword matches → relevance = 0.3 exactly.
    from_els = [_make_element("D001", "Bicycle", "Drivers")]
    to_els = [_make_element("A001", "Letter", "Activities")]
    result = _generate_smart_connections(
        from_els, to_els, "drivers", "activities"
    )
    assert len(result) == 1
    assert result[0].confidence == 0.3
```

- [ ] **Step 2: Run to verify they fail (TDD red)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v -k "test_cross_product or test_double_negative or test_results_sorted or test_max_count or test_pair_with_relevance"
```
Expected: 5 errors with `ImportError: cannot import name '_generate_smart_connections'`.

- [ ] **Step 3: Implement `_generate_smart_connections` (TDD green)**

Append to `sespy/connection_scorer.py` (after `_select_verb`):

```python


def _generate_smart_connections(
    from_elements: list[Element],
    to_elements: list[Element],
    from_slug: str,
    to_slug: str,
    max_count: int = _MAX_PER_TYPE,
    min_relevance: float = _MIN_RELEVANCE,
) -> list[ConnectionSuggestion]:
    """Per-type pair generator. Cross-product, threshold filter,
    double-negative filter, sort desc by confidence, cap at max_count.

    Direct port of R's generate_smart_connections at
    connection_generator.R:436-574 (KB and ML branches dropped per
    scope). Verb is derived per-pair via _select_verb(from_slug,
    polarity) — NOT a parameter, because verb is polarity-aware and
    polarity varies per pair.

    Note: the conn_type_key (f"{from_slug}_{to_slug}") is reproducible
    from from_slug+to_slug and is used internally by calculate_relevance
    via the same construction. Not passed as a separate parameter.

    The double-negative filter uses _KW["polarity_signals"]
    ["loss_keywords"] (specific decline/loss vocabulary), NOT
    "negative_keywords" (broader, includes pollutants like 'pollut',
    'contaminat'). The two sets overlap but are distinct in R.
    """
    loss_keywords = _KW["polarity_signals"]["loss_keywords"]
    candidates: list[ConnectionSuggestion] = []

    for from_el in from_elements:
        for to_el in to_elements:
            relevance = calculate_relevance(
                from_el.label, to_el.label, from_slug, to_slug
            )
            # Threshold gate (R uses >= at line 452; vacuous given 0.3 floor
            # but pinned by test_pair_with_relevance_exactly_03_survives).
            if relevance < min_relevance:
                continue

            # Double-negative filter (R lines 440-463).
            from_lower = from_el.label.lower()
            to_lower = to_el.label.lower()
            from_is_loss = any(
                re.search(re.escape(kw), from_lower) for kw in loss_keywords
            )
            to_is_loss = any(
                re.search(re.escape(kw), to_lower) for kw in loss_keywords
            )
            if from_is_loss and to_is_loss:
                continue

            polarity = detect_polarity(
                from_el.label, to_el.label, from_slug, to_slug
            )
            verb = _select_verb(from_slug, polarity)
            candidates.append(ConnectionSuggestion(
                source=from_el.id,
                target=to_el.id,
                polarity=polarity,
                confidence=relevance,
                rationale=f"{from_el.label} {verb} {to_el.label}",
            ))

    # Sort desc by confidence (stable — preserves cross-product order on ties).
    candidates.sort(key=lambda s: s.confidence, reverse=True)
    return candidates[:max_count]
```

- [ ] **Step 4: Run all Group-4 tests to verify they pass**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: 5+6+7+14+5 = 37 individual test runs, all passing. (parametrize cases inflate the count from "33 logical tests" to ~37+ at this point.)

- [ ] **Step 5: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): _generate_smart_connections with double-negative filter + 5 tests

Direct port of R's generate_smart_connections at connection_generator
.R:436-574 (KB and ML branches dropped per rule-based-only scope).

Per-pair flow:
1. calculate_relevance (filter at >= MIN_RELEVANCE; vacuous at floor)
2. Double-negative filter using loss_keywords (specific decline
   vocabulary, NOT the broader negative_keywords)
3. detect_polarity per-pair dispatch
4. _select_verb(from_slug, polarity) — polarity-aware
5. ConnectionSuggestion build with f-string rationale
6. Sort desc by confidence (stable), cap at max_count=15

Group 4 (5 tests in this commit + the 14-case verb test from the
previous commit = 6 logical tests / 19 pytest items): pins cross-
product, double-negative filter using loss_keywords vocabulary,
sort order, max_count cap, and the >= threshold semantics at the
floor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Implement `suggest_connections` + Group-5 tests (9 tests, the SP3 contract)

**Files:**
- Modify: `sespy/connection_scorer.py` (append function)
- Modify: `tests/test_connection_scorer.py` (append Group 5)

`suggest_connections` is the SP3 contract — same signature as SP1's stub. Top-level orchestrator (R lines 755-1001): groups elements by type, iterates the 10 connection-type pairs, concatenates results.

- [ ] **Step 1: Write the 9 failing Group-5 tests (TDD red)**

Append to `tests/test_connection_scorer.py`:

```python


# ---------------------------------------------------------------------------
# Group 5: suggest_connections (the SP3 contract) (9 tests)
# ---------------------------------------------------------------------------


def test_empty_state_returns_empty():
    """state.elements = [] → []."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState()
    assert suggest_connections(state) == []


def test_single_element_state_returns_empty():
    """Only one element → no possible cross-product → []."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(
        elements=[_make_element("D001", "Tourism", "Drivers")]
    )
    assert suggest_connections(state) == []


def test_full_state_returns_typed_suggestions():
    """Multi-type state → all items are ConnectionSuggestion, all
    confidence ∈ {0.3, 0.6, 0.9}, all polarity ∈ {'+', '-'}.
    """
    from sespy.data_structure import WizardState, ConnectionSuggestion
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
        _make_element("P001", "Pollution", "Pressures"),
    ])
    result = suggest_connections(state)
    assert len(result) > 0
    for s in result:
        assert isinstance(s, ConnectionSuggestion)
        assert s.confidence in {0.3, 0.6, 0.9}
        assert s.polarity in {"+", "-"}


def test_per_type_cap_honored_end_to_end():
    """State designed to overflow D→A → ≤ 15 D→A suggestions in output."""
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    # 5 × 5 = 25 D→A candidates; cap at 15.
    drivers = [_make_element(f"D{i:03d}", f"Tourism{i}", "Drivers")
               for i in range(1, 6)]
    activities = [_make_element(f"A{i:03d}", f"Recreation{i}", "Activities")
                  for i in range(1, 6)]
    state = WizardState(elements=drivers + activities)
    result = suggest_connections(state)
    da_count = sum(
        1 for s in result
        if s.source.startswith("D") and s.target.startswith("A")
    )
    assert da_count == 15


def test_all_10_types_yield_high_confidence_suggestions():
    """Designed-to-overlap reference fixture: ≥2 elements per type with
    keyword-rich labels. Assert that for each of the 10 connection types,
    at least one suggestion has confidence >= 0.6 (i.e., ≥ 1 keyword match
    across both names).

    NOTE: A weaker form ("≥1 suggestion per type") would pass trivially
    because R's 0.3 floor admits every cross-product pair. This stronger
    form actually verifies the keyword JSON has overlap-rich coverage —
    if a future JSON edit drops too many stems, this test fails.
    """
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections, _CONN_TYPES
    # Build 2 elements per type with overlap-rich labels designed to hit
    # ≥1 keyword in each connection_types list.
    # IMPORTANT: at least one element per S/I/W group MUST have a label
    # WITHOUT loss_keywords (loss/decline/declin/degrad/reduc/damag/...)
    # because the double-negative filter at _generate_smart_connections
    # drops pairs where BOTH labels match loss_keywords. With every S, I,
    # and W element loss-flagged, all S→I and I→W pairs would be filtered
    # out and the test would fail at those two connection types.
    state = WizardState(elements=[
        _make_element("D001", "Tourism demand", "Drivers"),
        _make_element("D002", "Fishing economy", "Drivers"),
        _make_element("A001", "Recreational fishing", "Activities"),
        _make_element("A002", "Commercial fishing", "Activities"),
        _make_element("P001", "Pollution from waste", "Pressures"),
        _make_element("P002", "Habitat removal", "Pressures"),
        # S001 has loss_keyword "decline"; S002 does NOT — at least one
        # must avoid loss_keywords so S→I pairs survive the filter.
        _make_element("S001", "Decline in biodiversity",
                      "Marine Processes & Functioning"),
        _make_element("S002", "Habitat structure",
                      "Marine Processes & Functioning"),
        # I001 has loss_keyword "loss"; I002 does NOT.
        _make_element("I001", "Loss of fish abundance",
                      "Ecosystem Services"),
        _make_element("I002", "Cultural service provision",
                      "Ecosystem Services"),
        # W001 has loss_keyword "reduc"; W002 does NOT.
        _make_element("W001", "Reduced food security",
                      "Goods & Benefits"),
        _make_element("W002", "Cultural wellbeing",
                      "Goods & Benefits"),
        _make_element("R001", "Marine policy intervention", "Responses"),
        _make_element("R002", "Fishing quota regulation", "Responses"),
    ])
    result = suggest_connections(state)
    # Deduce the type-pair from element ids' prefixes.
    # Map: drivers→D, activities→A, pressures→P, states→S,
    # impacts→I, welfare→W, responses→R.
    high_conf_seen = set()
    for s in result:
        if s.confidence < 0.6:
            continue
        for from_slug, to_slug, key in _CONN_TYPES:
            from_prefix = from_slug[0].upper()
            to_prefix = to_slug[0].upper()
            if s.source.startswith(from_prefix) and s.target.startswith(to_prefix):
                high_conf_seen.add(key)
                break
    expected = {key for _, _, key in _CONN_TYPES}
    missing = expected - high_conf_seen
    assert not missing, (
        f"Missing high-confidence (≥0.6) suggestions for: {sorted(missing)}. "
        f"This may indicate the keyword JSON has insufficient overlap "
        f"with the fixture labels for those connection types."
    )


def test_unknown_element_type_skipped(caplog):
    """Element with .type = 'Foo' (not in _TYPE_TO_SLUG) is skipped without
    raising; one logging.warning per unknown-typed element with element
    id and type in the message for diagnostics.
    """
    import logging
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("X001", "Mystery thing", "Foo"),  # unknown type
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
    ])
    with caplog.at_level(logging.WARNING, logger="sespy.connection_scorer"):
        result = suggest_connections(state)
    # Suggestions still produced for the valid (D, A) pair:
    assert len(result) >= 1
    # Warning emitted with id + type:
    assert any("X001" in rec.message and "Foo" in rec.message
               for rec in caplog.records)


def test_type_slug_map_is_inverse_of_wizard_map():
    """_TYPE_TO_SLUG exactly inverts ELEMENT_TYPE_MAP.

    Set-equality + per-key roundtrip. If ELEMENT_TYPE_MAP ever gains
    a duplicate value (silent inversion loss), this fails.
    """
    from sespy.data_structure import ELEMENT_TYPE_MAP
    from sespy.connection_scorer import _TYPE_TO_SLUG
    # Inverse property:
    for slug, type_str in ELEMENT_TYPE_MAP.items():
        assert _TYPE_TO_SLUG[type_str] == slug
    # Set equality (no duplicates lost):
    assert len(_TYPE_TO_SLUG) == len(ELEMENT_TYPE_MAP)


def test_polarity_default_fallback_returns_positive():
    """Pair of (drivers, activities) — one of the 5 type-pairs without
    a named branch — returns '+' regardless of name content (R line 186
    fallback). Distinct from test_default_fallback_for_unspecified_pair
    in Group 3 by being end-to-end through suggest_connections.
    """
    from sespy.data_structure import WizardState
    from sespy.connection_scorer import suggest_connections
    state = WizardState(elements=[
        _make_element("D001", "Tourism", "Drivers"),
        _make_element("A001", "Recreation", "Activities"),
    ])
    result = suggest_connections(state)
    da_polarities = {
        s.polarity for s in result
        if s.source.startswith("D") and s.target.startswith("A")
    }
    assert da_polarities == {"+"}


def test_no_wizard_import_in_connection_scorer():
    """Defensive: parse sespy/connection_scorer.py via AST and assert
    no top-level OR lazy (function-body) wizard import exists.

    Pins the §6 import-graph linearity post-ELEMENT_TYPE_MAP-relocation.
    If a future refactor accidentally re-introduces a wizard import
    (top-level OR inside a function body — both forms re-create the
    cycle when wizard.py later imports connection_scorer top-level),
    this test fails. AST-based scan immune to docstring/comment
    mentions of "from .wizard import".

    Path is anchored to this file's location (Path(__file__)) so
    the test works regardless of pytest's cwd.
    """
    import ast
    from pathlib import Path
    src_path = (
        Path(__file__).resolve().parent.parent
        / "sespy" / "connection_scorer.py"
    )
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # Catches `from .wizard import X` (relative) and
            # `from sespy.wizard import X` (absolute).
            if node.module == "wizard" and node.level == 1:
                pytest.fail(
                    f"connection_scorer.py:{node.lineno} imports from "
                    f".wizard — re-introduces the import cycle that "
                    f"ELEMENT_TYPE_MAP relocation broke; see spec §6"
                )
            if node.module == "sespy.wizard":
                pytest.fail(
                    f"connection_scorer.py:{node.lineno} imports from "
                    f"sespy.wizard — re-introduces the import cycle"
                )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("sespy.wizard", "wizard"):
                    pytest.fail(
                        f"connection_scorer.py:{node.lineno} imports "
                        f"sespy.wizard — re-introduces the import cycle"
                    )
```

- [ ] **Step 2: Run to verify the new tests fail (TDD red)**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v -k "test_empty_state or test_single_element or test_full_state or test_per_type_cap_honored_end or test_all_10_types or test_unknown_element or test_type_slug_map or test_polarity_default_fallback or test_no_wizard_import"
```
Expected: **7 failures + 2 passes**. The 7 failures are `ImportError: cannot import name 'suggest_connections'` or `AttributeError` for the tests that exercise the impl. The 2 passes are:
1. `test_no_wizard_import_in_connection_scorer` — reads the source file via AST and asserts no wizard import is present (Task 3 created the scorer with a `data_structure` import; Task 2 had already moved `ELEMENT_TYPE_MAP` there).
2. `test_type_slug_map_is_inverse_of_wizard_map` — verifies `_TYPE_TO_SLUG` (created at module top in Task 3) inverts `ELEMENT_TYPE_MAP` (relocated in Task 2). Doesn't depend on `suggest_connections`.

Both passing-during-red are expected, NOT TDD failures: they pin invariants of the module-level scaffolding established in earlier tasks. (An earlier draft of this plan said "8 failures + 1 pass" — that prediction was off by one; the corrected expectation is 7+2.)

- [ ] **Step 3: Implement `suggest_connections` (TDD green)**

Append to `sespy/connection_scorer.py` (after `_generate_smart_connections`):

```python


def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    Same signature as SP1's stub at sespy/wizard.py:92.

    Top-level orchestrator (R lines 755-1001; constants MAX_PER_TYPE=15
    and MIN_RELEVANCE=0.3 at R 757-758). KB-seed and ML-scoring
    branches dropped per rule-based-only scope.

    Returns a flat list of ≤150 (10 types × 15 cap) ConnectionSuggestions
    sorted globally by source group order (per _CONN_TYPES iteration)
    and within each group by confidence descending.
    """
    # 1. Group state.elements by type using _TYPE_TO_SLUG.
    grouped: dict[str, list[Element]] = {
        slug: [] for slug in _TYPE_TO_SLUG.values()
    }
    for el in state.elements:
        slug = _TYPE_TO_SLUG.get(el.type)
        if slug is None:
            _logger.warning(
                "unknown Element.type %r for id %r; skipping",
                el.type, el.id,
            )
            continue
        grouped[slug].append(el)

    # 2. For each of the 10 connection-type pairs, generate suggestions.
    # _CONN_TYPES is a 3-tuple list (from_slug, to_slug, conn_type_key);
    # we destructure the 3rd field but don't pass it — calculate_relevance
    # rebuilds the conn_type_key from (from_slug, to_slug) internally.
    out: list[ConnectionSuggestion] = []
    for from_slug, to_slug, _conn_type_key in _CONN_TYPES:
        from_list = grouped[from_slug]
        to_list = grouped[to_slug]
        if not from_list or not to_list:
            continue  # cross-product would be empty anyway
        out.extend(_generate_smart_connections(
            from_list, to_list, from_slug, to_slug
        ))

    return out
```

- [ ] **Step 4: Run the full test suite to verify everything passes**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -v
```
Expected: All Group 1-5 tests pass — 33 logical tests, ~46 pytest items (parametrize expansions). No failures.

- [ ] **Step 5: Verify the module imports cleanly end-to-end**

Run:
```bash
micromamba run -n shiny python -c "from sespy.connection_scorer import suggest_connections, calculate_relevance, detect_polarity; print('module loads end-to-end')"
```
Expected: `module loads end-to-end`. (Works because Task 2 already moved `ELEMENT_TYPE_MAP` to `data_structure.py`; the import graph is linear.)

- [ ] **Step 6: Commit**

```bash
git add sespy/connection_scorer.py tests/test_connection_scorer.py
git commit -m "$(cat <<'EOF'
feat(connection_scorer): suggest_connections SP3 contract + 9 Group-5 tests

Top-level orchestrator (R lines 755-1001; KB-seed and ML branches
dropped per rule-based-only scope). Groups state.elements by type
via _TYPE_TO_SLUG, iterates the 10 _CONN_TYPES pairs, calls
_generate_smart_connections for each non-empty pair, concatenates.

Element with type not in _TYPE_TO_SLUG is skipped silently with a
single logging.warning per occurrence (caplog-asserted) carrying
the element id and type for diagnostics.

Group 5 (9 tests): empty/single-element/full-state behavior, per-
type cap end-to-end, all-10-types-produce-suggestions for a
reference fixture, unknown-type skip behavior, _TYPE_TO_SLUG
inverse-of-ELEMENT_TYPE_MAP invariant, default-fallback polarity,
and the no-wizard-import defensive check that pins import-graph
linearity post-ELEMENT_TYPE_MAP-relocation.

Total: 33 logical tests across G1-G5 (5+6+7+6+9), ~46 pytest items
when parametrize expansions are counted.

The connection_scorer module imports ELEMENT_TYPE_MAP from
data_structure (its post-Task-2 home); cold-import works because the
relocation in Task 2 broke the would-be circular import ahead of
this commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire `sespy/wizard.py` stub to delegate to `connection_scorer`

**Files:**
- Modify: `sespy/wizard.py:92` (replace stub body with delegation)
- Modify: `tests/test_wizard.py:62` (rename test)

The SP1 stub `def suggest_connections(state) -> []` at `sespy/wizard.py:92` is replaced with a one-line delegation to `connection_scorer.suggest_connections`. The SP1 test that pinned the empty-stub return is renamed to reflect its new narrower meaning.

- [ ] **Step 1: Read current wizard.py stub**

Run:
```bash
sed -n '85,105p' sespy/wizard.py
```
Expected: the SP1 stub block including the docstring `"""SP1 stub: returns []. SP3 fills via TF-IDF + polarity rules; ..."""` and `return []`.

- [ ] **Step 2: Add the top-level import to wizard.py**

Find the existing imports section in wizard.py. Use `Edit` to add the connection_scorer import alongside the others.

Locate the existing `from .data_structure import ...` line. Add immediately after it:

```python
from .connection_scorer import suggest_connections as _suggest_impl
```

Now wizard.py imports the SP3 backend at module-load time. This is safe because the import graph is linear (Task 2 fixed the cycle).

- [ ] **Step 3: Replace the stub body**

Use `Edit` to replace the SP1 stub at line 92. The exact `old_string` (verified against `sespy/wizard.py:92-100` at HEAD `c793001` — note the docstring's first line "Return suggested connections..." which is easy to miss):

```python
def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """Return suggested connections for the wizard's connection-review step.

    SP1 stub: returns []. SP3 fills via TF-IDF + polarity rules; SP4 fills
    via Claude API. SP1's connection-review renderer surfaces an empty
    table with a placeholder message ("No suggestions yet — install SP3
    or SP4 backend to enable AI-assisted connection generation").
    """
    return []
```

Replace with:

```python
def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    Delegates to sespy.connection_scorer.suggest_connections (imported
    as _suggest_impl at module top).

    SP4 (Claude API) will replace the implementation behind a settings
    switch; the signature is the contract.
    """
    return _suggest_impl(state)
```

- [ ] **Step 4: Verify wizard.py loads and delegation works**

Run:
```bash
micromamba run -n shiny python -c "from sespy.wizard import suggest_connections; from sespy.data_structure import WizardState; print(suggest_connections(WizardState()))"
```
Expected: `[]` (empty WizardState → empty result, but now via the SP3 backend).

Run:
```bash
micromamba run -n shiny python -c "
from sespy.wizard import suggest_connections
from sespy.data_structure import WizardState, Element
state = WizardState(elements=[
    Element(id='D001', label='Tourism', type='Drivers'),
    Element(id='A001', label='Recreation', type='Activities'),
])
result = suggest_connections(state)
print(f'count={len(result)}')
print(f'first: source={result[0].source} target={result[0].target} polarity={result[0].polarity} confidence={result[0].confidence}')
"
```
Expected: `count=1`, first suggestion is `source=D001 target=A001 polarity=+ confidence=0.9`. Confidence math: drivers_activities keywords include `"tourism"` (matches "Tourism") AND `"recreat"` (matches "Recreation") → total_matches=2 → 0.9. Polarity is `"+"` because (drivers, activities) has no named branch in detect_polarity → falls through to R line 186 default.

- [ ] **Step 5: Rename the SP1 stub-empty test**

Read `tests/test_wizard.py:60-65` to find the existing test:

Run:
```bash
sed -n '55,70p' tests/test_wizard.py
```
Expected: shows `def test_suggest_connections_stub_returns_empty():` and its assertions.

Use `Edit` to rename the function. The `old_string`:

```python
def test_suggest_connections_stub_returns_empty():
    state = WizardState(regional_sea="baltic", ecosystem_type="open_coast")
    assert suggest_connections(state) == []
```

Replace with:

```python
def test_suggest_connections_empty_state_returns_empty():
    """SP3-renamed from test_suggest_connections_stub_returns_empty.

    The wizard-level test smokes the import-graph and delegation after
    Task 2's ELEMENT_TYPE_MAP relocation. The richer behavioral pinning
    moved to tests/test_connection_scorer.py Group 5 (which has 9 tests
    including its own test_empty_state_returns_empty for the impl path).
    """
    state = WizardState(regional_sea="baltic", ecosystem_type="open_coast")
    assert suggest_connections(state) == []
```

- [ ] **Step 6: Run tests to verify everything still passes**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_wizard.py tests/test_connection_scorer.py -v
```
Expected: All pass — including the renamed wizard test and all 33 connection_scorer tests.

Run the full suite:
```bash
micromamba run -n shiny python -m pytest \
  tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py \
  tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py \
  tests/test_report.py tests/test_templates.py tests/test_network.py \
  tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py \
  tests/test_regional_seas.py tests/test_connection_scorer.py -q
```
Expected: `180 passed` (134 baseline + 46 pytest items, where the parametrize expansion in Group 4's verb test inflates 33 logical tests → 46 pytest items; see Task 7 Step 5 note).

- [ ] **Step 7: Commit**

```bash
git add sespy/wizard.py tests/test_wizard.py
git commit -m "$(cat <<'EOF'
feat(wizard): SP3 backend swap — replace stub with connection_scorer

Replace the SP1 stub at sespy/wizard.py:92 with a one-line delegation
to connection_scorer.suggest_connections (imported top-level as
_suggest_impl per the post-Task-2 linear import graph). The wizard
module's connection_review renderer is untouched per spec scope —
SP3 is a pure backend swap.

Rename test_suggest_connections_stub_returns_empty (line 62) to
test_suggest_connections_empty_state_returns_empty in tests/
test_wizard.py — narrower name reflecting that the wizard-level
test now smokes the delegation, while the richer behavioral
pinning moved to tests/test_connection_scorer.py Group 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Add `pyproject.toml` package-data + verify wheel install

**Files:**
- Modify: `pyproject.toml` (add 3 sections)

The current `pyproject.toml` has no `[build-system]` table at all — `pip install` falls back to setuptools' legacy behavior under PEP 517 and silently omits the JSON files. SP2's `regional_seas.json` is already affected; SP3 inherits the hazard. A coordinated ~10-LOC change fixes both in one commit.

The verification uses a throwaway micromamba env (NOT `python -m venv`, per CLAUDE.md global instructions).

- [ ] **Step 1: Read current pyproject.toml**

Run:
```bash
cat pyproject.toml
```
Expected: shows `[project]`, `[project.optional-dependencies]`, and `[tool.pytest.ini_options]` only. No `[build-system]`, no `[tool.setuptools.*]`.

- [ ] **Step 2: Append the 3 packaging sections**

Use `Edit` to append at the end of `pyproject.toml`. The `old_string` should be the last meaningful line (likely `pythonpath = ["."]` from the pytest section); `new_string` is that same line followed by the new sections.

Concretely, the last lines of pyproject.toml currently look like:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

After the edit, the file should end with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["sespy*"]

[tool.setuptools.package-data]
sespy = ["*.json"]
```

(setuptools `>=68` is chosen over `>=61` to avoid known historical edge cases with `package-data` honoring under PEP 517 builds. The `[tool.setuptools.packages.find]` block uses implicit `where = ["."]` because SESPy uses a flat layout — `sespy/` lives at the repo root.)

- [ ] **Step 3: Verify pyproject.toml parses as TOML**

Run:
```bash
micromamba run -n shiny python -c "import tomllib; d = tomllib.loads(open('pyproject.toml').read()); print('build-system requires:', d['build-system']['requires']); print('package-data:', d['tool']['setuptools']['package-data'])"
```
Expected: prints the build-system requires + the package-data dict.

- [ ] **Step 4: Verify pytest still works after the edit**

Run:
```bash
micromamba run -n shiny python -m pytest tests/test_connection_scorer.py -q
```
Expected: `46 passed` (33 logical tests, but Group 4's `test_verb_selection_per_from_slug_polarity_pair` parametrize expands to 14 items → 5+6+7+19+9 = 46). The pytest config under `[tool.pytest.ini_options]` is unchanged; the new pyproject sections don't interfere.

- [ ] **Step 5: Verify the wheel-install hazard is fixed (throwaway micromamba env)**

This is the one-shot CI/manual verification (NOT a pytest test — see spec §8 Task 5). Uses a throwaway micromamba env per CLAUDE.md global instructions ("Do NOT create virtual environments").

Run with `set -e` (abort on first failure), idempotent pre-cleanup, and unconditional trap-based post-cleanup so the env is fresh per run AND doesn't leak on any failure path:
```bash
set -e  # abort on any non-zero exit so partial-success states don't masquerade as success
# Idempotent pre-cleanup: removes any leftover env from a prior aborted run.
micromamba env remove -n sespy-wheel-test -y 2>/dev/null || true
# Fresh create + trap-based post-cleanup.
micromamba create -n sespy-wheel-test python=3.11 -y
trap 'micromamba env remove -n sespy-wheel-test -y' EXIT
micromamba run -n sespy-wheel-test pip install .
micromamba run -n sespy-wheel-test python -c "import sespy.connection_scorer, sespy.regional_seas; print('json files load from installed wheel: ok')"
```
Expected: `json files load from installed wheel: ok`. The pre-cleanup ensures a fresh state even if a prior aborted run left a stale env. `set -e` ensures any failed command (e.g., `pip install` returns non-zero) aborts the script before false-success output. The trap fires on EXIT regardless of cause, so the env is removed even on failure.

**Specify `timeout: 600000` (10 min)** on the Bash tool call — fresh-env creation + dependency install can exceed the default 2-minute timeout, especially on first run. Run all 5 lines in a single Bash invocation (the `trap` only fires on shell exit).

If the import line fails with `FileNotFoundError: ... regional_seas.json` or `... connection_keywords.json`, the package-data declaration didn't take effect — re-check the `pyproject.toml` block syntax (TOML is strict on bracket placement and quoting).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "$(cat <<'EOF'
fix(packaging): include package data in wheel for SP2/SP3 JSON files

Add [build-system], [tool.setuptools.packages.find], and [tool.
setuptools.package-data] sections to pyproject.toml so sespy/*.json
files (SP2's regional_seas.json and SP3's connection_keywords.json)
ship in installed wheels.

Latent SP2 hazard fixed in passing: today's pyproject.toml has no
[build-system] table at all — pip falls back to setuptools' PEP 517
legacy behavior and omits non-Python files. SP2's eager _load_kb()
already fails on 'pip install .' in a clean env; SP3's eager
_load_keywords() would extend the breakage. A single coordinated
config change covers both.

Verified via throwaway-micromamba-env wheel install (with trap-based
unconditional cleanup so a failed install doesn't leave a dangling
env behind).

setuptools>=68 is chosen over >=61 to avoid known historical edge
cases with package-data honoring under PEP 517 builds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: SP1 e2e verification (canonical) + Coastal Tourism UAT (optional)

**Files:** none (verification only — no commit unless a fix is needed)

This task verifies that the SP3 backend swap doesn't break SP1's e2e suite. Spec DoD §11 requires "All 6 SP1 e2e cases pass; case 1 (full run) shows ≥1 connection suggestion at step 11" — case_full_run does the empty-project 12-step walk and SP3 makes step 11 produce real suggestions for the user-filled elements. The Coastal Tourism UAT (Step 2 below) is OPTIONAL bonus verification for non-trivial template content; it's manual-only because it requires a human to drive the browser, and agentic execution can skip it without affecting DoD coverage.

- [ ] **Step 1: Run SP1 e2e suite (canonical DoD verification)**

**Use `Bash` with `run_in_background: true` + the environment's background-shell-termination tool** (the SP2 Task 4 pattern). On this machine the `pkill` binary is **NOT available** in Git Bash (verified `which pkill` returns "not found"), so subshell+trap fallbacks that rely on `pkill` will silently fail to kill the server — the port stays bound and subsequent runs collide. The background-shell pattern avoids `pkill` entirely.

The exact name of the cleanup tool depends on the agentic harness running this plan. **Verify the available tool name before starting Task 12** — common variants include `KillShell`, `KillBash`, or `TaskStop` depending on the harness. If unsure, use the harness's tool-search facility (e.g., `ToolSearch` in Claude Code) to find the deferred tool that takes a Bash shell ID and terminates the process tree.

Concrete pattern (3 separate tool calls):

**Call 1** (start server, capture shell ID — `Bash` tool with `run_in_background: true`):
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```
Save the returned shell ID (e.g., `bash_abc123`) for Call 3.

**Call 2** (wait for port, run e2e — foreground `Bash`, with `timeout: 600000`):
```bash
micromamba run -n shiny python .tmp/wait_port.py && \
micromamba run -n shiny python tests/test_wizard_e2e.py
```
Expected output ends with `wizard e2e: 6 cases passed`. If `wait_port.py` times out (port never bound — e.g., `app.py` crashed during import), `&&` short-circuits and the e2e doesn't run. In that case, read the background shell's stdout for the server-side traceback before terminating it.

**Call 3** (kill the background server with the harness's cleanup tool, passing the shell ID from Call 1):
The cleanup tool reliably terminates the process tree on Windows where `kill $!` and `pkill` are both fragile.

If `run_in_background` is genuinely unavailable in your tooling environment (rare), use this Linux/macOS-only fallback (will leak the server on Windows because `pkill` is missing — manual cleanup needed):

```bash
(
  micromamba run -n shiny shiny run --port 8000 app.py &
  SHINY_PID=$!
  trap 'kill $SHINY_PID 2>/dev/null; kill -- -$$ 2>/dev/null' EXIT
  micromamba run -n shiny python .tmp/wait_port.py
  micromamba run -n shiny python tests/test_wizard_e2e.py
)
```
With `timeout: 600000`. Note: `kill -- -$$` is a process-group kill (Linux/macOS); on Windows Git Bash it has no effect. The orphan `shiny run` (python.exe) may persist; check `netstat -ano | grep :8000` and `taskkill //F //PID <pid>` manually if needed.

If any e2e case fails, the output indicates which step. Common failure modes:
- Case 1 (full 12-step run): check that step 11 (connection_review) renders without error. SP3 may have introduced a runtime error in the renderer if `_assemble_wizard_state` returns malformed data. Inspect the screenshot at `tests/screenshots/wizard_e2e.png` (auto-saved at run end).
- Case 4 (mid-wizard nav): unrelated to SP3 — should still pass.

**For agentic execution (subagent-driven-development / executing-plans):** if Step 1 passes, the DoD verification for "case 1 shows ≥1 connection suggestion at step 11" is satisfied — case_full_run fills in elements during steps 4-10 and SP3 produces suggestions at step 11. No further browser smoke is required. Skip Step 2 entirely and proceed to Task 13.

- [ ] **Step 2: Coastal Tourism UAT (optional, human-only)**

This is OPTIONAL human-driven verification beyond the spec DoD. Skip if executing agentically — Step 1 already covers the DoD. Run only if a human is available to drive the browser and you want bonus confidence on a non-trivial template.

Start the server (foreground, in a fresh terminal):
```bash
micromamba run -n shiny shiny run --port 8000 app.py
```

Then in a browser:
1. Navigate to `http://127.0.0.1:8000`.
2. Load the Coastal Tourism template (Templates → Coastal Tourism → Apply).
3. Click the SES Wizard nav.
4. Click Start Wizard. Modal appears (Coastal Tourism has elements).
5. Click Continue, replace it (resets ISA but keeps metadata).
6. Click Next 11 times (steps 0-10), filling in valid answers using existing template defaults where possible. Step 11 is connection_review.
7. **Assert: the connection_review table shows ≥1 suggestion row.** Each row should have source, target, polarity (+/-), confidence (0.3-0.9), and a rationale string like "Tourism drives Recreation".

If the table is empty (only the placeholder "No suggestions yet"), SP3 isn't returning suggestions for the wizard's WizardState. Debug by:
- Inspecting the wizard's `_assemble_wizard_state()` return value (use `print()` or a debug breakpoint).
- Verifying `state.elements` is non-empty at step 11 entry.
- Calling `suggest_connections(state)` directly and checking the return value.

If it fails, the issue is real and needs a `fix(...)` commit.

- [ ] **Step 3: Stop the Shiny server (only if Step 2 ran)**

If Step 2 was executed, stop the server with Ctrl+C in the foreground terminal. On Windows Git Bash where `pkill` is unavailable, find the process ID via:
```bash
netstat -ano | grep ":8000.*LISTENING"
```
Then `taskkill //F //PID <pid>` (Windows) or `kill <pid>` (Linux/macOS). If you used `Bash` with `run_in_background: true` and have the shell ID, prefer your harness's background-shell cleanup tool (Step 1 above identifies it) — it terminates the process tree reliably across platforms.

- [ ] **Step 4: Verify no regressions in unit tests**

Run:
```bash
micromamba run -n shiny python -m pytest \
  tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py \
  tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py \
  tests/test_report.py tests/test_templates.py tests/test_network.py \
  tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py \
  tests/test_regional_seas.py tests/test_connection_scorer.py -q
```
Expected: `180 passed` (134 baseline + 46 pytest items, where the parametrize expansion in Group 4's verb test inflates 33 logical tests → 46 pytest items; see Task 7 Step 5 note).

(No commit — Task 12 is verification. If a fix was needed in Step 4, that fix gets its own commit with message `fix(connection_scorer): <specific issue>`.)

---

## Task 13: Update README.md unit-test count

**Files:**
- Modify: `README.md` (bump `134` to `180` at both occurrences)

The SP3 baseline shifts from 134 → 180 unit-test pytest items (+46 new pytest items, where Group 4's verb test parametrize expands 1 logical test into 14 items). The README phrase "134 unit tests" refers to pytest items (matches `pytest -q` output), so the SP3 update preserves that semantic: "180 unit tests" matches `pytest -q` output post-SP3.

- [ ] **Step 1: Find the test-count occurrences**

Run:
```bash
grep -cn "134 unit" README.md && grep -n "134" README.md
```
Expected: count is exactly `2` and grep reports the 2 lines — one in the headline test-count (e.g., "134 unit tests + 21 e2e scripts") and one in the per-module list section.

**STOP and reconcile if the count is 0, 1, or 3+:** README may have been updated since the plan was written. Use `git log -p README.md` to find the latest test-count change and align this task's edits to current state. The count is verifiable via `grep -c "134 unit" README.md`; this plan was authored against the post-SP2 README at HEAD `3c18fd8` which has exactly 2 occurrences.

- [ ] **Step 2: Replace both occurrences with `180`**

Use `Edit` with `replace_all: true` for the exact phrase. If the test count appears as `134 unit tests`, replace `134 unit tests` → `180 unit tests`.

If the two occurrences have slightly different surrounding context (e.g., one says "134 unit + 21 e2e" and the other "134 unit tests"), use two separate `Edit` calls — one per occurrence with unique surrounding context.

- [ ] **Step 3: Verify both occurrences updated**

Run:
```bash
grep -n "134\|180" README.md
```
Expected: only `180` references remain — no `134` lines (unless `134` appears in unrelated context like a year or commit hash, in which case those are fine).

- [ ] **Step 4: Sanity-check the readme is well-formed (stdlib-only, no extra deps)**

Run:
```bash
micromamba run -n shiny python -c "
text = open('README.md', encoding='utf-8').read()
assert len(text) > 100, 'readme too short'
assert '180' in text, 'expected 180 to appear in readme post-bump'
assert '134' not in text or 'commit' in text.lower(), 'unexpected 134 (test-count) reference'
print('readme sanity ok')
"
```
Expected: `readme sanity ok`. Stdlib-only — does NOT require the `markdown` package (which isn't in the `shiny` env).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): bump unit test count to 180 after SP3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done

After Task 13, the SP3 branch `feat/ai-isa-wizard-sp3` is ready for fast-forward merge to main. Expected commit count: 12 (Tasks 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13 each produce one commit; Tasks 0 and 12 are read-only).

Final verification before merge:

```bash
micromamba run -n shiny python -m pytest \
  tests/test_dynamics.py tests/test_i18n.py tests/test_persistent_storage.py \
  tests/test_excel_import.py tests/test_autosave.py tests/test_recent_projects.py \
  tests/test_report.py tests/test_templates.py tests/test_network.py \
  tests/test_data_structure.py tests/test_utils.py tests/test_wizard.py \
  tests/test_regional_seas.py tests/test_connection_scorer.py -q
```
Expected: `180 passed` (134 baseline + 46 pytest items, where the parametrize expansion in Group 4's verb test inflates 33 logical tests → 46 pytest items; see Task 7 Step 5 note).

```bash
git log --oneline main..feat/ai-isa-wizard-sp3
```
Expected: ~12 commits matching the per-task commit messages above.

Then proceed to merge per project convention (fast-forward to main).

---

## Spec coverage check (self-review)

| Spec section | Covered by |
|---|---|
| §1 Goal & scope | Plan goal/architecture; Tasks 1-9 (data + algorithm); Task 10 (wizard wire); Task 11 (packaging); Task 13 (readme) |
| §1 Decisions table (8 decisions) | Decisions are baked into Tasks 1-9 (rule-based only, all 10 types, file location, thresholds, confidence passthrough, JSON+loader pattern, slug naming) — none are re-litigated |
| §2 File organization | Plan File Structure table covers all 4 new files and 4 modified files |
| §3 Data shape | Task 1 produces the full JSON verbatim |
| §4 Loader API | Tasks 3-9 produce each function signature + body |
| §5 Components (the 4 functions + 2 helpers) | Task 4 (calculate_relevance), Task 5 (_analyze_polarity_phrase), Task 6 (detect_polarity), Task 7 (_select_verb), Task 8 (_generate_smart_connections), Task 9 (suggest_connections) |
| §6 Migration of wizard.py | Task 2 (relocation, prerequisite for Tasks 3-9) + Task 10 (delegation) |
| §7 Testing (33 logical tests in 5 groups; 46 pytest items after parametrize expansion) | Group 1 in Task 3; Group 2 in Task 4; Group 3 in Tasks 5-6; Group 4 in Tasks 7-8; Group 5 in Task 9 |
| §8 Build sequence (8 spec-tasks) | Plan's 14 tasks split spec Task 2 into 6 atomic per-function tasks (one commit per function) AND moves spec Task 3 (relocation) to plan Task 2 (prerequisite for the scorer-creation tasks); the other 6 spec-tasks map 1:1 |
| §9 Risks & mitigations | All 10 risks have at least one pinning test in Tasks 3-9; the package-data hazard is fixed in Task 11 |
| §10 Out of scope | Plan does not implement any out-of-scope feature (Feature B governance/socioeconomic, KB lookup, ML scoring, Claude API, hot-reload) |
| §11 Definition of done | Final verification block above maps to each DoD bullet |

**Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details", "Add appropriate error handling", or "Similar to Task N" in the plan body. All steps show the actual code or commands needed.

**Type consistency:**
- `calculate_relevance(from_name, to_name, from_slug, to_slug) -> float` — same signature in Tasks 4, 6, 8.
- `detect_polarity(from_name, to_name, from_slug, to_slug) -> str` — same in Tasks 6, 8.
- `_select_verb(from_slug, polarity) -> str` — same in Tasks 7, 8.
- `_generate_smart_connections(from_elements, to_elements, from_slug, to_slug, max_count, min_relevance) -> list[ConnectionSuggestion]` — same in Tasks 8, 9. Note: `conn_type_key` was dropped post-round-4 review (parameter was dead — calculate_relevance reconstructs it internally from from_slug+to_slug).
- `suggest_connections(state) -> list[ConnectionSuggestion]` — same in Tasks 9, 10.
- `_analyze_polarity_phrase(name_lower) -> tuple[str, bool]` — same in Tasks 5, 6.
- `Element(id, label, type)` — used consistently in tests (Tasks 8, 9) via `_make_element` helper.

All function signatures consistent. No type drift detected.
