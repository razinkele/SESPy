# MosaicSES Phase-2 #20 — Emerald Justice Equity Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Emerald Justice equity overlay on MosaicSES outcome elements (Impact + Welfare), an equity-exposure lens on `response_pressure_gap`, a read-only "Emerald Justice exposure" comparative card, and a demonstrative Curonian seed.

**Architecture:** Evaluative overlay on the MosaicSES `Compartment` keyed by outcome element id (SESPy `Element` untouched, no schema bump), mirroring the shipped #19 tenets increment. Reachability uses the cycle-safe `sespy.network.to_digraph` + `networkx.descendants`. Read-only display only.

**Tech Stack:** Python 3, dataclasses, pandas, networkx, Shiny for Python; tests via pytest. Run everything through micromamba env `shiny`.

**Repos:** Code + tests live in the **MosaicSES** repo: `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`. This plan and its spec live in the **SESPy** repo `docs/superpowers/`. **All commits in this plan are made in the MosaicSES repo.** Work and run commands from the MosaicSES directory.

**Spec:** `SESPy/docs/superpowers/specs/2026-06-13-mosaicses-phase2-emerald-justice-design.md`

**Test command (unit):** `micromamba run -n shiny python -m pytest tests/<file> -q` (run from the MosaicSES repo root).

---

### Task 1: Equity vocabulary + re-exports

**Files:**
- Modify: `multises/data_structure.py` (add `EQUITY_DIMENSIONS`/`EQUITY_SLUGS` after the existing `TENET_*` block)
- Modify: `multises/__init__.py` (re-export in both the import block and `__all__`)
- Test: `tests/test_equity.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_equity.py`:

```python
"""Tests for the Emerald Justice equity overlay (Phase-2 #20)."""
from __future__ import annotations

import pytest

from multises import data_structure as ds
from multises.archetypes import seed_compartment
from multises.data_structure import (
    Compartment,
    MultiSES,
    MultiSESMetadata,
    EQUITY_DIMENSIONS,
    EQUITY_SLUGS,
    OUTCOME_ELEMENT_TYPES,
    MULTISES_SCHEMA_VERSION,
    ErrorCode,
)


def test_equity_vocab_shape():
    assert len(EQUITY_DIMENSIONS) == 6
    assert len(EQUITY_SLUGS) == 6
    assert len(set(EQUITY_SLUGS)) == 6                 # unique
    assert EQUITY_SLUGS[0] == "ocean_grabbing"         # canonical order is load-bearing
    assert EQUITY_SLUGS[-1] == "cultural_heritage"     # the provisional 6th
    # every entry is (slug, label)
    assert all(isinstance(s, str) and isinstance(lbl, str)
               for s, lbl in EQUITY_DIMENSIONS)
    # single source of truth for the outcome-element predicate (design §2.2)
    assert OUTCOME_ELEMENT_TYPES == ("Ecosystem Services", "Goods & Benefits")


def test_equity_vocab_reexported_from_package():
    import multises
    assert multises.EQUITY_SLUGS == EQUITY_SLUGS
    assert multises.OUTCOME_ELEMENT_TYPES == OUTCOME_ELEMENT_TYPES
    assert "EQUITY_DIMENSIONS" in multises.__all__
    assert "EQUITY_SLUGS" in multises.__all__
    assert "OUTCOME_ELEMENT_TYPES" in multises.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -q`
Expected: FAIL with `ImportError: cannot import name 'EQUITY_DIMENSIONS'`.

- [ ] **Step 3: Add the vocabulary to `multises/data_structure.py`**

Find the existing tenet vocabulary block (search for `TENET_SCORE_MAX: int = 5`). Immediately after that block, add:

```python

# Emerald Justice equity dimensions (Nyka & group; EG monograph; spec §11 #20).
# Order is load-bearing: it is the canonical display order. Slugs are stable
# ids; labels are display strings. The first five are Nyka's canonical set
# (parent §11 #20); `cultural_heritage` is added in Phase-2 #20 (provisional,
# pending Nyka's ratification — see design §3.1).
EQUITY_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("ocean_grabbing",          "Ocean grabbing"),
    ("livelihood_displacement", "Livelihood displacement"),
    ("gender_inequity",         "Gender inequity"),
    ("indigenous_rights",       "Indigenous rights"),
    ("decision_exclusion",      "Exclusion from decision-making"),
    ("cultural_heritage",       "Cultural heritage loss"),
)
EQUITY_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in EQUITY_DIMENSIONS)

# Outcome element types an equity dimension may attach to (design §2.2):
# Impact ("Ecosystem Services") and Welfare ("Goods & Benefits"). This is the
# SINGLE source of truth for the outcome predicate — imported by validate()
# and comparative.py so the fragile string pair is written exactly once.
OUTCOME_ELEMENT_TYPES: tuple[str, ...] = ("Ecosystem Services", "Goods & Benefits")
```

- [ ] **Step 4: Re-export from `multises/__init__.py`**

In the `from .data_structure import (` block, add these three lines in alphabetical position (before `ErrorCode,`):

```python
    EQUITY_DIMENSIONS,
    EQUITY_SLUGS,
    OUTCOME_ELEMENT_TYPES,
```

In the `__all__` list, add (before `"ErrorCode",`):

```python
    "EQUITY_DIMENSIONS",
    "EQUITY_SLUGS",
    "OUTCOME_ELEMENT_TYPES",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add multises/data_structure.py multises/__init__.py tests/test_equity.py
git commit -m "feat(mosaicses): EQUITY_DIMENSIONS vocab + re-exports (phase-2 #20)"
```

---

### Task 2: `Compartment.outcome_equity_dimensions` field + validation + round-trip

**Files:**
- Modify: `multises/data_structure.py` (`ErrorCode.M207`; `_validate_equity_dimensions` helper; `Compartment` field + `__post_init__` loop; `from_dict` kwarg)
- Test: `tests/test_equity.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_equity.py`:

```python
# --- Task 2: field + M207 validation + round-trip --------------------------

def _lagoon_with_overlay(overlay):
    """A lagoon compartment carrying an outcome_equity_dimensions overlay."""
    proj = seed_compartment("lagoon", label="seed", id="seed").project
    return Compartment(id="a", label="A", archetype="lagoon", project=proj,
                       outcome_equity_dimensions=overlay)


def test_outcome_equity_dimensions_valid_and_empty_list():
    c = _lagoon_with_overlay({"GB001": ["livelihood_displacement"], "ES001": []})
    assert c.outcome_equity_dimensions["GB001"] == ["livelihood_displacement"]
    assert c.outcome_equity_dimensions["ES001"] == []   # empty list allowed


@pytest.mark.parametrize("bad", [
    {"GB001": ["not_a_dimension"]},                       # unknown slug
    {"GB001": "livelihood_displacement"},                 # not a list
    {"GB001": ["gender_inequity", "gender_inequity"]},    # duplicate
])
def test_outcome_equity_dimensions_invalid_raise_m207(bad):
    with pytest.raises(ds._ChannelValidationError) as e:
        _lagoon_with_overlay(bad)
    assert e.value.code == ErrorCode.M207_INVALID_EQUITY_DIMENSION


def test_outcome_equity_dimensions_round_trip():
    a = seed_compartment("lagoon", label="A", id="a")
    a.outcome_equity_dimensions = {"GB001": ["livelihood_displacement", "cultural_heritage"]}
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    res = MultiSES.from_json(ms.to_json())
    assert res.multises.compartments[0].outcome_equity_dimensions == {
        "GB001": ["livelihood_displacement", "cultural_heritage"]}


def test_outcome_equity_dimensions_absent_loads_none_no_w400():
    a = seed_compartment("lagoon", label="A", id="a")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    res = MultiSES.from_json(ms.to_json())
    assert res.multises.compartments[0].outcome_equity_dimensions is None
    assert MULTISES_SCHEMA_VERSION == 1
    assert all(i.code != ErrorCode.W400_SCHEMA_VERSION_MIGRATED
               for i in res.report.warnings)
```

> Note: `res.report.warnings` follows the `LoadResult` shape used in the existing tests; if the attribute name differs in this codebase, mirror whatever `tests/test_tenets.py` / the seed tests use to read load warnings. (`MultiSES.from_json` returns a `LoadResult` with `.multises` and `.report`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'outcome_equity_dimensions'` (and `AttributeError: M207_INVALID_EQUITY_DIMENSION`).

- [ ] **Step 3: Add the `M207` error code**

In `multises/data_structure.py`, in the `ErrorCode` class, directly after the line `M206_INVALID_TENET_SCORES = "M206_INVALID_TENET_SCORES"` add:

```python
    M207_INVALID_EQUITY_DIMENSION = "M207_INVALID_EQUITY_DIMENSION"
```

- [ ] **Step 4: Add the `_validate_equity_dimensions` helper**

In `multises/data_structure.py`, immediately after the `_validate_tenet_scores` function (it ends with its last `raise _ChannelValidationError(...)` block), add:

```python
def _validate_equity_dimensions(dims, *, where: str) -> None:
    """Raise _ChannelValidationError(M207) unless `dims` is a list of slugs
    drawn from EQUITY_SLUGS with no duplicates. An empty list is allowed (an
    explicitly-flagged-but-empty outcome contributes nothing). Shared by
    Compartment.outcome_equity_dimensions entries (design §3.2)."""
    if not isinstance(dims, list):
        raise _ChannelValidationError(
            ErrorCode.M207_INVALID_EQUITY_DIMENSION,
            f"{where}: equity dimensions must be a list (got {type(dims).__name__})",
        )
    seen: set[str] = set()
    for slug in dims:
        if slug not in EQUITY_SLUGS:
            raise _ChannelValidationError(
                ErrorCode.M207_INVALID_EQUITY_DIMENSION,
                f"{where}: unknown equity dimension {slug!r}; "
                f"expected one of {EQUITY_SLUGS}",
            )
        if slug in seen:
            raise _ChannelValidationError(
                ErrorCode.M207_INVALID_EQUITY_DIMENSION,
                f"{where}: duplicate equity dimension {slug!r}",
            )
        seen.add(slug)
```

- [ ] **Step 5: Add the `Compartment` field**

In `multises/data_structure.py`, in the `Compartment` dataclass, directly after the `response_tenet_scores: dict[str, dict[str, int]] | None = None` line, add:

```python

    # Phase-2 evaluative overlay (Emerald Justice, #20): outcome element id ->
    # [equity slugs]. Keys are sespy outcome element ids — type "Ecosystem
    # Services" (Impact) or "Goods & Benefits" (Welfare) — within this
    # compartment's project. Keys are unique within this compartment; global
    # element-id uniqueness is never assumed. None = no outcomes flagged.
    # SESPy Element is deliberately NOT modified (evaluative layer; design §2).
    # Referential integrity (id resolves to a real outcome element) is a soft
    # W305 check in validate(), not here.
    outcome_equity_dimensions: dict[str, list[str]] | None = None
```

- [ ] **Step 6: Add the `__post_init__` validation loop**

In `Compartment.__post_init__`, directly after the existing `response_tenet_scores` validation loop (which ends with the `_validate_tenet_scores(scores, where=...)` call), add:

```python
        if self.outcome_equity_dimensions is not None:
            for eid, dims in self.outcome_equity_dimensions.items():
                _validate_equity_dimensions(
                    dims, where=f"Compartment {self.id!r} outcome {eid!r}")
```

- [ ] **Step 7: Wire `from_dict`**

In `multises/data_structure.py`, in `MultiSES.from_dict`, in the `Compartment(` constructor call, directly after the `response_tenet_scores=c_raw.get("response_tenet_scores"),` line add:

```python
                outcome_equity_dimensions=c_raw.get("outcome_equity_dimensions"),
```

(`to_dict` needs no change — `dataclasses.asdict` emits the new field as `null` when unset, since `_COMPARTMENT_EXCLUDE` only drops `project` and `_unknown_archetype_original`.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -q`
Expected: PASS (all Task 1 + Task 2 tests green).

- [ ] **Step 9: Commit**

```bash
git add multises/data_structure.py tests/test_equity.py
git commit -m "feat(mosaicses): Compartment.outcome_equity_dimensions + M207 validation + round-trip (phase-2 #20)"
```

---

### Task 3: `W305` referential soft-check in `validate()`

**Files:**
- Modify: `multises/data_structure.py` (`ErrorCode.W305`)
- Modify: `multises/validate.py` (`_check_equity_element_refs` + wire into `validate`)
- Test: `tests/test_equity.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_equity.py`:

```python
# --- Task 3: referential-integrity soft check (W305) -----------------------

def _ms_with_overlay_on(elem_id, dims=("cultural_heritage",)):
    from multises.validate import validate
    cmp = seed_compartment("lagoon", label="A", id="a")
    cmp.outcome_equity_dimensions = {elem_id: list(dims)}
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[cmp], channels=[])
    return ms, validate


def test_validate_no_warn_when_id_resolves_to_impact():
    # ES001 is an "Ecosystem Services" (Impact) element in the lagoon archetype.
    ms, validate = _ms_with_overlay_on("ES001")
    codes = {i.code for i in validate(ms)}
    assert ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT not in codes


def test_validate_no_warn_when_id_resolves_to_welfare():
    # GB001 is a "Goods & Benefits" (Welfare) element in the lagoon archetype.
    ms, validate = _ms_with_overlay_on("GB001")
    codes = {i.code for i in validate(ms)}
    assert ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT not in codes


def test_validate_warns_when_id_resolves_to_non_outcome():
    # P001 is a Pressure (not an outcome element) -> must warn.
    ms, validate = _ms_with_overlay_on("P001")
    codes = {i.code for i in validate(ms)}
    assert ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT in codes


def test_validate_warns_on_unknown_outcome_id():
    ms, validate = _ms_with_overlay_on("ghost_outcome")
    codes = {i.code for i in validate(ms)}
    assert ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT in codes


def test_w305_not_emitted_on_load():
    a = seed_compartment("lagoon", label="A", id="a")
    a.outcome_equity_dimensions = {"ghost_outcome": ["cultural_heritage"]}
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    res = MultiSES.from_json(ms.to_json())   # from_json does NOT run validate()
    assert all(i.code != ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT
               for i in res.report.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -k "w305 or resolves or non_outcome or unknown_outcome" -q`
Expected: FAIL — `AttributeError: W305_EQUITY_DIM_UNKNOWN_ELEMENT`.

- [ ] **Step 3: Add the `W305` error code**

In `multises/data_structure.py`, in the `ErrorCode` class, directly after `W304_TENET_SCORE_UNKNOWN_RESPONSE = "W304_TENET_SCORE_UNKNOWN_RESPONSE"` add:

```python
    W305_EQUITY_DIM_UNKNOWN_ELEMENT = "W305_EQUITY_DIM_UNKNOWN_ELEMENT"
```

- [ ] **Step 4: Add the referential check in `multises/validate.py`**

First, import the centralized outcome-type constant: in `multises/validate.py`, in the existing `from .data_structure import (` block, add `OUTCOME_ELEMENT_TYPES,` (alphabetical position, before `ValidationIssue,`).

Then, directly after the `_check_tenet_response_refs` function (ends at its final `path=...` line + closing `))`), add:

```python
def _check_equity_element_refs(ms: MultiSES) -> Iterable[ValidationIssue]:
    """Soft W305: every key in a compartment's outcome_equity_dimensions must
    resolve to an outcome element id (type "Ecosystem Services" = Impact, or
    "Goods & Benefits" = Welfare) in that compartment's project. An orphaned or
    wrong-typed id warns rather than fails, so the evaluative overlay survives
    structural edits to the underlying SES."""
    for i, c in enumerate(ms.compartments):
        if not c.outcome_equity_dimensions:
            continue
        outcome_ids = {
            el.id for el in c.project.isa_data.elements
            if el.type in OUTCOME_ELEMENT_TYPES
        }
        for eid in c.outcome_equity_dimensions:
            if eid not in outcome_ids:
                yield _emit(ValidationIssue(
                    severity="warning",
                    code=ErrorCode.W305_EQUITY_DIM_UNKNOWN_ELEMENT,
                    message=(
                        f"outcome_equity_dimensions references {eid!r}, which is "
                        f"not an outcome element (Impact/Welfare) in "
                        f"compartment {c.id!r}."
                    ),
                    path=f"compartments[{i}].outcome_equity_dimensions.{eid}",
                ))
```

- [ ] **Step 5: Wire it into `validate()`**

In `multises/validate.py`, in the `validate` function, directly after `issues.extend(_check_tenet_response_refs(ms))` add:

```python
    issues.extend(_check_equity_element_refs(ms))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py -q`
Expected: PASS (all equity tests green).

- [ ] **Step 7: Commit**

```bash
git add multises/data_structure.py multises/validate.py tests/test_equity.py
git commit -m "feat(mosaicses): W305 equity-element referential soft-check in validate() (phase-2 #20)"
```

---

### Task 4: Preserve the overlay through `replace_compartment`

**Files:**
- Modify: `multises/data_structure.py` (`replace_compartment` reconstruction + docstring)
- Test: `tests/test_equity.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_equity.py`:

```python
# --- Task 4: replace_compartment preserves overlays ------------------------

def test_replace_compartment_preserves_overlays():
    from multises.data_structure import replace_compartment
    a = seed_compartment("lagoon", label="A", id="a")
    a.outcome_equity_dimensions = {"GB001": ["livelihood_displacement"]}
    a.response_tenet_scores = {"R1": {"ecological": 4}}
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    new_project = seed_compartment("lagoon", label="A", id="a").project
    # replace_compartment is PURE — it returns a NEW MultiSES; assert on the
    # returned object (asserting on the original `ms` would pass trivially).
    ms2 = replace_compartment(ms, "a", new_project)
    c = ms2.compartments[0]
    assert c.outcome_equity_dimensions == {"GB001": ["livelihood_displacement"]}
    assert c.response_tenet_scores == {"R1": {"ecological": 4}}   # pre-existing gap, now fixed
```

> `replace_compartment` is a pure function returning a new `MultiSES` (signature `replace_compartment(ms, compartment_id, new_project)`); capture the return value — asserting on the original `ms` is a false-negative trap.

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py::test_replace_compartment_preserves_overlays -q`
Expected: FAIL — `outcome_equity_dimensions` is `None` after replace (and `response_tenet_scores` is `None`).

- [ ] **Step 3: Preserve both overlays in `replace_compartment`**

In `multises/data_structure.py`, in `replace_compartment`, in the `new = Compartment(` reconstruction, add two kwargs after `is_focal_tw=old.is_focal_tw,`:

```python
        response_tenet_scores=old.response_tenet_scores,
        outcome_equity_dimensions=old.outcome_equity_dimensions,
```

Then update the docstring line that enumerates preserved fields (`... 'is_focal_tw', and '_unknown_archetype_original'.`) to also mention the overlays:

```python
    `is_focal_tw`, `response_tenet_scores`, `outcome_equity_dimensions`, and
    `_unknown_archetype_original`. This is the backwrite contract — UI editing
    within a compartment must NEVER silently drop compartment-level metadata.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py::test_replace_compartment_preserves_overlays -q`
Expected: PASS.

- [ ] **Step 5: Run the full equity suite + the tenets suite (no regressions)**

Run: `micromamba run -n shiny python -m pytest tests/test_equity.py tests/test_tenets.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multises/data_structure.py tests/test_equity.py
git commit -m "fix(mosaicses): replace_compartment preserves evaluative overlays (phase-2 #20)"
```

---

### Task 5: `_downstream_outcome_ids` helper + augment `response_pressure_gap`

**Files:**
- Modify: `multises/comparative.py` (import `OUTCOME_ELEMENT_TYPES` + `to_digraph` + `networkx`; `_downstream_outcome_ids`; augment `response_pressure_gap`)
- Test: `tests/test_comparative.py` (extend — the file holding `response_pressure_gap` coverage)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_comparative.py` (a new section). These build a one-compartment MultiSES directly so the graph is fully controlled:

```python
# --- Phase-2 #20: equity exposure columns on response_pressure_gap ---------

def _equity_compartment(*, elements, connections, overlay, cid="a"):
    """Build a one-compartment MultiSES with explicit elements/connections."""
    from multises.archetypes import seed_compartment
    from multises.data_structure import Compartment, MultiSES, MultiSESMetadata
    from sespy.data_structure import Element, Connection, IsaData, Project
    # Start from a real lagoon project, then replace its isa_data with ours so
    # the element/connection set is exactly what the test specifies.
    base = seed_compartment("lagoon", label="A", id=cid)
    base.project.isa_data.elements[:] = elements
    base.project.isa_data.connections[:] = connections
    base.outcome_equity_dimensions = overlay
    return MultiSES(metadata=MultiSESMetadata(), compartments=[base], channels=[])


def _E(eid, etype, label=None):
    from sespy.data_structure import Element
    return Element(id=eid, label=label or eid, type=etype)


def _C(src, tgt):
    from sespy.data_structure import Connection
    return Connection(source=src, target=tgt, polarity="+", strength="medium", confidence=2)


def _gap(ms):
    from multises.comparative import response_pressure_gap
    return response_pressure_gap(ms)


def test_equity_orphan_with_equity():
    # P1 (no Response) -> S1 -> GB1 (Welfare, flagged). Orphan + equity.
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("S1", "Marine Processes & Functioning"),
                  _E("GB1", "Goods & Benefits")],
        connections=[_C("P1", "S1"), _C("S1", "GB1")],
        overlay={"GB1": ["livelihood_displacement", "decision_exclusion"]})
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 1
    assert row.affected_equity_dimensions == "decision_exclusion,livelihood_displacement"
    assert bool(row.is_equity_relevant_orphan) is True


def test_equity_governed_with_equity_is_not_orphan():
    # R1 -> P1 (P1 governed) ; P1 -> GB1 (flagged). Equity yes, orphan no.
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("R1", "Responses"),
                  _E("GB1", "Goods & Benefits")],
        connections=[_C("R1", "P1"), _C("P1", "GB1")],
        overlay={"GB1": ["gender_inequity"]})
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 1
    assert bool(row.is_equity_relevant_orphan) is False


def test_equity_reachable_but_unflagged_and_empty_list_do_not_count():
    # P1 reaches ES1 (no overlay) and GB1 (overlay = []). Both unflagged.
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("ES1", "Ecosystem Services"),
                  _E("GB1", "Goods & Benefits")],
        connections=[_C("P1", "ES1"), _C("P1", "GB1")],
        overlay={"GB1": []})   # empty list = unflagged
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 0
    assert row.affected_equity_dimensions == ""
    assert bool(row.is_equity_relevant_orphan) is False


def test_equity_multi_outcome_dedupe_and_both_node_types():
    # P1 -> ES1 (Impact, cultural_heritage) and -> GB1 (Welfare, cultural_heritage+livelihood).
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("ES1", "Ecosystem Services"),
                  _E("GB1", "Goods & Benefits")],
        connections=[_C("P1", "ES1"), _C("P1", "GB1")],
        overlay={"ES1": ["cultural_heritage"],
                 "GB1": ["cultural_heritage", "livelihood_displacement"]})
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 2          # both nodes counted
    assert row.affected_equity_dimensions == "cultural_heritage,livelihood_displacement"  # deduped+sorted


def test_equity_reachability_is_cycle_safe():
    # P1 -> A -> B -> P1 (cycle) and P1 -> GB1 (flagged). Must terminate.
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("A", "Activities"),
                  _E("B", "Drivers"), _E("GB1", "Goods & Benefits")],
        connections=[_C("P1", "A"), _C("A", "B"), _C("B", "P1"),
                     _C("P1", "GB1"), _C("P1", "P1")],   # includes a self-loop
        overlay={"GB1": ["ocean_grabbing"]})
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 1
    assert bool(row.is_equity_relevant_orphan) is True


def test_equity_reachability_does_not_cross_compartments():
    from multises.archetypes import seed_compartment
    from multises.data_structure import MultiSES, MultiSESMetadata
    a = seed_compartment("lagoon", label="A", id="a")
    a.project.isa_data.elements[:] = [_E("P1", "Pressures")]
    a.project.isa_data.connections[:] = []
    b = seed_compartment("lagoon", label="B", id="b")
    b.project.isa_data.elements[:] = [_E("GB1", "Goods & Benefits")]
    b.project.isa_data.connections[:] = []
    b.outcome_equity_dimensions = {"GB1": ["ocean_grabbing"]}
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=[])
    row = _gap(ms).set_index("pressure_id").loc["P1"]
    assert row.downstream_equity_outcome_count == 0          # B's flag is not reachable from A


def test_equity_columns_present_appended():
    ms = _equity_compartment(
        elements=[_E("P1", "Pressures"), _E("GB1", "Goods & Benefits")],
        connections=[_C("P1", "GB1")],
        overlay={"GB1": ["ocean_grabbing"]})
    cols = list(_gap(ms).columns)
    for c in ("downstream_equity_outcome_count", "affected_equity_dimensions",
              "is_equity_relevant_orphan"):
        assert c in cols
    # existing columns still present (append, not replace)
    assert "within_compartment_response_count" in cols
    assert "pressure_compartment_has_no_governance" in cols
```

> If `IsaData`/`Project`/`Element`/`Connection` import paths differ, mirror the exact imports the existing `tests/test_comparative.py` already uses to build a project. The `_equity_compartment` helper deliberately mutates `isa_data.elements`/`.connections` in place (`[:] =`) so the project object stays valid.

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative.py -k equity -q`
Expected: FAIL — `AttributeError: 'Series' object has no attribute 'downstream_equity_outcome_count'` (columns not present yet).

- [ ] **Step 3: Add imports + `_downstream_outcome_ids` helper to `multises/comparative.py`**

At the top of `multises/comparative.py`, change the `sespy.network` import to also bring in `to_digraph`, and add `networkx`:

```python
import networkx as nx

from sespy.network import (
    CENTRALITY_METRICS,
    centrality_metrics,
    leverage_scores,
    to_digraph,
)
```

Also import the centralized outcome-type constant: in the existing `from .data_structure import (...)` block in `multises/comparative.py` (which currently imports `MultiSES`, `TENETS`, `TENET_SLUGS`), add `OUTCOME_ELEMENT_TYPES,`.

Then, directly above the `response_pressure_gap` function, add:

```python
def _downstream_outcome_ids(isa_data, start_id: str) -> set[str]:
    """Element ids reachable downstream from `start_id` whose type is an outcome
    type (OUTCOME_ELEMENT_TYPES). Cycle-safe (nx.descendants terminates on the
    DAPSI feedback cycles); the start node is never included. Reachability is
    confined to this one project's connection graph — cross-compartment Channels
    are not part of isa_data, so the walk never leaves the compartment (§4.2)."""
    g = to_digraph(isa_data)
    if start_id not in g:
        return set()
    reachable = nx.descendants(g, start_id)
    types = {e.id: e.type for e in isa_data.elements}
    return {eid for eid in reachable if types.get(eid) in OUTCOME_ELEMENT_TYPES}
```

- [ ] **Step 4: Augment `response_pressure_gap`**

In `response_pressure_gap`, inside the `for c in ms.compartments:` loop, after the existing `response_to_pressure` is built and before the `for el in elements:` loop, add the per-compartment overlay lookup:

```python
        equity_map = c.outcome_equity_dimensions or {}
        isa = c.project.isa_data
```

Then, inside `for el in elements:` after `within = response_to_pressure.get(el.id, 0)`, compute the equity exposure and add the three columns to the appended dict. Replace the existing `rows.append({...})` for Pressure rows with:

```python
            within = response_to_pressure.get(el.id, 0)
            flagged_dims: set[str] = set()
            n_flagged = 0
            for oid in _downstream_outcome_ids(isa, el.id):
                dims = equity_map.get(oid)
                if dims:                       # non-empty list only
                    n_flagged += 1
                    flagged_dims.update(dims)
            rows.append({
                "compartment_id": c.id,
                "pressure_id": el.id,
                "pressure_label": el.label,
                "within_compartment_response_count": within,
                "incoming_governance_channel_count": gov_count,
                "pressure_compartment_has_no_governance": (gov_count == 0),
                "downstream_equity_outcome_count": n_flagged,
                "affected_equity_dimensions": ",".join(sorted(flagged_dims)),
                "is_equity_relevant_orphan": (within == 0 and n_flagged > 0),
            })
```

(Keep the existing six keys exactly as they were; only the last three keys are new. `gov_count` is the existing per-compartment governance count already in scope.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative.py -k equity -q`
Expected: PASS (8 equity tests).

- [ ] **Step 6: Run the full comparative suite (no regressions in existing `response_pressure_gap` tests)**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative.py -q`
Expected: PASS (existing column checks use `in df.columns`, so appended columns do not break them).

- [ ] **Step 7: Commit**

```bash
git add multises/comparative.py tests/test_comparative.py
git commit -m "feat(mosaicses): equity-exposure columns on response_pressure_gap (cycle-safe reachability) (phase-2 #20)"
```

---

### Task 6: "Emerald Justice exposure" comparative card

**Files:**
- Modify: `multises_app/modules/comparative.py` (add card to `comparative_ui`; add `equity_disclaimer` + `equity_table` renders; update module docstring "6-card" → "7-card")
- Test: `tests/test_comparative_module.py` (extend + bump card-count assertions)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_comparative_module.py` (mirror the existing tenet-card test in that file):

```python
def test_comparative_ui_has_equity_card():
    # comparative_ui is a @module.ui function — it REQUIRES a module-id argument
    # (existing tests call it as comparative_ui("test_id") and assert namespaced
    # ids). Calling comparative_ui() raises TypeError — do not do that.
    html = str(comparative_ui("test_id"))
    assert "Emerald Justice exposure" in html
    assert 'id="test_id-equity_disclaimer"' in html
    assert 'id="test_id-equity_table"' in html
```

Then update the two existing `comparative-card` count assertions in this file (the test reviewer located them at lines 19 and 142) from `== 6` to `== 7`. Find each assertion that counts `comparative-card` occurrences and change the expected count to 7. (Leave the `>= 5` smoke assertion at line 11 unchanged — it stays valid at 7. Also update the stale "six cards total now" comment in `test_comparative_graph_cards_are_full_screen` near line 142 to "seven"; the `bslib-full-screen-enter == 2` assertions stay valid because the new card is not full-screen.)

> Use the same rendering/counting idiom already present in `tests/test_comparative_module.py` for the existing cards — do not invent a new one.

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py -q`
Expected: FAIL — "Emerald Justice exposure" not found; card count is 6 not 7.

- [ ] **Step 3: Add the card to `comparative_ui`**

In `multises_app/modules/comparative.py`, in `comparative_ui`, directly after the "Tenet readiness" card (the `ui.card(ui.card_header("Tenet readiness"), ...)` block) and before the "Compartment meta-graph" card, add:

```python
        ui.card(ui.card_header("Emerald Justice exposure"),
                ui.output_ui("equity_disclaimer"),
                ui.output_data_frame("equity_table"),
                class_="comparative-card"),
```

- [ ] **Step 4: Add the server renders**

In `comparative_server`, directly after the `tenet_table` render function, add the two equity outputs. They map slugs to display labels in canonical order and filter to the equity-relevant slice:

```python
    @output
    @render.ui
    def equity_disclaimer():
        df = response_pressure_gap(state.active_multises.get())
        has_rows = (not df.empty
                    and "downstream_equity_outcome_count" in df.columns
                    and bool((df["downstream_equity_outcome_count"] > 0).any()))
        caveat = ui.help_text(
            "Screening signal only: a row means a Pressure has a directed "
            "graph-path to an equity-flagged outcome (an Impact or "
            "Goods-&-Benefits element); it does not establish that the Pressure "
            "causes that inequity. Reachability ignores edge polarity/type. "
            "'Equity-relevant orphan' = a Pressure with no within-compartment "
            "Response that nonetheless reaches an equity-flagged outcome."
        )
        if not has_rows:   # spec §5 empty-state hint
            return ui.div(
                ui.em("No equity-flagged outcomes reached in this MultiSES yet."),
                caveat)
        return caveat

    @output
    @render.data_frame
    def equity_table():
        from multises.data_structure import EQUITY_DIMENSIONS
        label_by_slug = dict(EQUITY_DIMENSIONS)
        order = {slug: i for i, (slug, _) in enumerate(EQUITY_DIMENSIONS)}

        def _labels(cell: str):
            if not cell:
                return ""
            slugs = sorted(cell.split(","), key=lambda s: order.get(s, 99))
            return ", ".join(label_by_slug.get(s, s) for s in slugs)

        df = response_pressure_gap(state.active_multises.get())
        if df.empty or "downstream_equity_outcome_count" not in df.columns:
            df = df.iloc[0:0]
        else:
            df = df[df["downstream_equity_outcome_count"] > 0].copy()
            df["affected_equity_dimensions"] = df["affected_equity_dimensions"].map(_labels)
            df = df.sort_values(
                ["is_equity_relevant_orphan", "compartment_id", "pressure_label"],
                ascending=[False, True, True])
            df = df[["compartment_id", "pressure_label",
                     "within_compartment_response_count",
                     "downstream_equity_outcome_count",
                     "affected_equity_dimensions", "is_equity_relevant_orphan"]]
        return render.DataGrid(df, height="320px")
```

(`response_pressure_gap` is already imported at the top of this module.)

- [ ] **Step 5: Update the module docstring**

At the top of `multises_app/modules/comparative.py`, update the docstring: change "6-card analytical grid" to "7-card analytical grid" and add a line to the numbered card list:

```python
  6. Emerald Justice exposure     — equity-flagged Pressures table + disclaimer (phase-2 #20)
  7. Compartment meta-graph       — pyvis canvas via render_pyvis_network
```

(Renumber the existing meta-graph entry from 6 to 7.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_module.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): Emerald Justice exposure card in Comparative dashboard (phase-2 #20)"
```

---

### Task 7: Curonian seed — demonstrative equity dimensions

**Files:**
- Modify: `multises/curonian/__init__.py` (read `outcome_equity_dimensions` from each compartment's JSON)
- Modify: `multises/curonian/curonian_loac.json` (flag `GB001` + `ES003` in `curonian_lagoon`; add the `MPF003→ES003` edge)
- Test: `tests/test_curonian_seed.py` (extend)

**Grounding:** In the lagoon, `GB001` = "Lagoon fishery (smelt, perch, pikeperch)" (Welfare) and `ES003` = "Bird habitat (Ramsar value)" (Impact). `P003` = "Algal blooms" is an ungoverned Pressure (no `Response→P003` edge) reaching `GB001` via the existing `P003→MPF003→GB001`. Adding `MPF003→ES003` makes `ES003` reachable too. So `P003` becomes an equity-relevant orphan exposing both nodes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_curonian_seed.py`:

```python
def test_seed_curonian_equity_exposure():
    from multises.curonian import seed_curonian
    from multises.comparative import response_pressure_gap
    df = response_pressure_gap(seed_curonian())
    # at least one Pressure reaches an equity-flagged outcome
    assert (df["downstream_equity_outcome_count"] > 0).any()
    # at least one equity-relevant orphan (ungoverned Pressure -> flagged outcome)
    assert df["is_equity_relevant_orphan"].any()
    # the lagoon's "Algal blooms" Pressure is the demonstrative orphan
    lagoon = df[df["compartment_id"] == "curonian_lagoon"]
    algal = lagoon[lagoon["pressure_label"] == "Algal blooms"].iloc[0]
    assert bool(algal["is_equity_relevant_orphan"]) is True
    assert "cultural_heritage" in algal["affected_equity_dimensions"]
    assert "livelihood_displacement" in algal["affected_equity_dimensions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_curonian_seed.py::test_seed_curonian_equity_exposure -q`
Expected: FAIL — `KeyError`/`AttributeError` or empty selection (the seed carries no equity dims yet, and `seed_curonian` does not read the field).

- [ ] **Step 3: Make `seed_curonian` read the overlay**

In `multises/curonian/__init__.py`, in the per-compartment loop, directly after the `connections` try/except block and before `compartments.append(cmp)`, add:

```python
        oed = c_raw.get("outcome_equity_dimensions")
        if oed is not None:
            if not isinstance(oed, dict):
                raise MultiSESIntegrityError(
                    f"curonian_loac.json: compartment {c_raw.get('id')!r} "
                    f"field 'outcome_equity_dimensions' must be an object, "
                    f"got {type(oed).__name__!r}."
                )
            cmp.outcome_equity_dimensions = oed
```

- [ ] **Step 4: Edit the Curonian lagoon seed JSON**

In `multises/curonian/curonian_loac.json`, **replace the entire `curonian_lagoon` compartment object** (the one with `"archetype": "lagoon"`) with the block below. Two things change versus the current file: one new connection `MPF003→ES003` is appended to `connections`, and a new `outcome_equity_dimensions` key is added. (Replacing the whole object avoids fiddly in-array insertions.) The demonstrative equity tags are illustrative, grounded in the LT/RU small-scale-fishery + Curonian heritage narrative; `cultural_heritage` is provisional pending Nyka's ratification.

```json
    {
      "id": "curonian_lagoon",
      "label": "Curonian Lagoon (~1584 km^2, oligohaline)",
      "archetype": "lagoon",
      "elements_extra": [
        {"id": "R001", "label": "National eutrophication management programme (BSAP-derived)", "type": "Responses", "confidence": 2}
      ],
      "connections": [
        {"source": "P001", "target": "P003", "polarity": "+", "strength": "strong", "confidence": 4},
        {"source": "P003", "target": "MPF003", "polarity": "-", "strength": "strong", "confidence": 4},
        {"source": "MPF003", "target": "GB001", "polarity": "+", "strength": "medium", "confidence": 3},
        {"source": "MPF003", "target": "ES003", "polarity": "-", "strength": "medium", "confidence": 2},
        {"source": "GB001", "target": "R001", "polarity": "-", "strength": "weak", "confidence": 2},
        {"source": "R001", "target": "P001", "polarity": "-", "strength": "weak", "confidence": 2}
      ],
      "outcome_equity_dimensions": {
        "GB001": ["livelihood_displacement", "decision_exclusion"],
        "ES003": ["cultural_heritage"]
      }
    },
```

- [ ] **Step 4b: Bump the pinned lagoon connection-count assertion**

The new `MPF003→ES003` edge takes the lagoon from 5 to 6 within-compartment connections. An existing test hard-pins this. In `tests/test_curonian_seed.py` (around line 228), change:

```python
    assert len(lg2.project.isa_data.connections) == 5, (
        f"Lagoon must have 5 within-compartment connections after "
```

to:

```python
    assert len(lg2.project.isa_data.connections) == 6, (
        f"Lagoon must have 6 within-compartment connections after "
```

(Update the `5`→`6` in the assertion and the f-string message; the rest of that test — the `R001→P001` polarity check — is unaffected.)

- [ ] **Step 5: Run test to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_curonian_seed.py::test_seed_curonian_equity_exposure -q`
Expected: PASS.

- [ ] **Step 6: Run the full seed suite (no regressions)**

Run: `micromamba run -n shiny python -m pytest tests/test_curonian_seed.py -q`
Expected: PASS. The connection-count assertion was bumped 5→6 in Step 4b; the new `MPF003→ES003` edge adds no `Response→Pressure` edge, so the response/governance gap assertions and the `R001→P001` balancing-loop checks are unaffected.

- [ ] **Step 7: Commit**

```bash
git add multises/curonian/__init__.py multises/curonian/curonian_loac.json tests/test_curonian_seed.py
git commit -m "feat(mosaicses): demonstrative Emerald Justice scores on Curonian lagoon outcomes (phase-2 #20)"
```

---

### Task 8: Comparative e2e — card visible + count sync

**Files:**
- Modify: `tests/test_comparative_e2e.py` (bump `comparative-card` count 6 → 7; assert the equity panel + disclaimer)

- [ ] **Step 1: Update the e2e assertions**

In `tests/test_comparative_e2e.py`, change the card-count assertion (the test reviewer located it at line 34: `cards.count() == 6`) to `== 7`.

Then add equity-panel coverage mirroring however the existing test asserts the "Tenet readiness" card. After the seed is loaded and the comparative page is shown, assert the equity card header and a data row are visible, e.g.:

```python
    # Emerald Justice exposure card present with the seed's demonstrative scores
    page.wait_for_selector("text=Emerald Justice exposure")
    page.wait_for_selector("text=Screening signal only")
    # the disclaimer text confirms the card rendered; the seed guarantees >=1 row
```

> Match the existing e2e idiom in this file (Playwright `page` fixture, selectors, and how it loads the Curonian seed). Do not introduce a new harness.

- [ ] **Step 2: Run the comparative e2e**

Run: `micromamba run -n shiny python -m pytest tests/test_comparative_e2e.py -q`
Expected: PASS (card count 7; equity panel visible).

> If `test_comparative_e2e.py` self-runs on import (boots its own server) rather than being a standard pytest module, run it via whatever entrypoint the repo uses for e2e (check `tests/` for an e2e runner); the assertions to change are the same.

- [ ] **Step 3: Commit**

```bash
git add tests/test_comparative_e2e.py
git commit -m "test(mosaicses): comparative e2e — Emerald Justice card visible + card count 7 (phase-2 #20)"
```

---

### Task 9: Full-suite verification + mark spec implemented

**Files:**
- Modify (in SESPy repo): `docs/superpowers/specs/2026-06-13-mosaicses-phase2-emerald-justice-design.md` (flip `Status:` to Implemented)
- Modify (in SESPy repo): `docs/superpowers/specs/2026-05-08-mosaicses-design.md` (§11 #20 back-pointer)
- Modify (in SESPy repo): `docs/superpowers/specs/2026-05-09-mosaicses-scientific-basis.md` (§8a alignment-matrix row)

- [ ] **Step 1: Run the full MosaicSES unit suite**

Run (from MosaicSES root): `micromamba run -n shiny python -m pytest tests/ -q`
Expected: PASS (all prior tests + the new `test_equity.py`, augmented `test_comparative.py`, `test_comparative_module.py`, `test_curonian_seed.py`). If any e2e file aborts collection by self-running, exclude it the same way the repo's documented unit-run does and run the e2e separately.

- [ ] **Step 2: Manual smoke (optional but recommended)**

Boot the app and open the Comparative dashboard; confirm the "Emerald Justice exposure" card shows the lagoon's "Algal blooms" Pressure as an equity-relevant orphan with human-readable dimension labels (Livelihood displacement, Exclusion from decision-making, Cultural heritage loss), orphans first.

- [ ] **Step 3: Mark the spec implemented (SESPy repo)**

In the SESPy repo, make three doc updates (mirroring the #19 precedent — commit `a875a97` marked tenets implemented across the parent + this-spec):

(a) `docs/superpowers/specs/2026-06-13-mosaicses-phase2-emerald-justice-design.md` — change the `**Status:**` line to:

```markdown
**Status:** **Implemented** ✓ — shipped in MosaicSES `main` (Phase-2 #20); unit suite green + comparative e2e green.
```

(b) `docs/superpowers/specs/2026-05-08-mosaicses-design.md` — in the §11 backlog item **#20**, append a back-pointer sentence (mirroring how #19 points to its design):

```markdown
    **→ Designed + implemented in [`2026-06-13-mosaicses-phase2-emerald-justice-design.md`](2026-06-13-mosaicses-phase2-emerald-justice-design.md) (Phase-2 #20); that spec refines "field on Element (Impact type)" to a MosaicSES overlay (`Compartment.outcome_equity_dimensions`) attached to BOTH outcome nodes (Impact + Welfare), keeping SESPy's `Element` unchanged, and adds a provisional 6th dimension `cultural_heritage`.**
```

(c) `docs/superpowers/specs/2026-05-09-mosaicses-scientific-basis.md` — in the §8a alignment matrix, change the **Emerald Justice equity dimensions** row's v1-status cell from `✗ deferred` to `✓ implemented (Phase-2 #20)` and update the coverage-summary tally line accordingly.

- [ ] **Step 4: Commit the spec status (SESPy repo)**

```bash
git add docs/superpowers/specs/2026-06-13-mosaicses-phase2-emerald-justice-design.md docs/superpowers/specs/2026-05-08-mosaicses-design.md docs/superpowers/specs/2026-05-09-mosaicses-scientific-basis.md
git commit -m "docs(spec): mark Phase-2 #20 Emerald Justice as implemented (shipped to MosaicSES)"
```

---

## Self-Review

**Spec coverage check (every spec section → task):**
- §2.2 outcome predicate (Impact + Welfare) → centralized as `OUTCOME_ELEMENT_TYPES` in Task 1, imported by Tasks 3 & 5 (single source of truth) ✓
- §3.1 vocab → Task 1 ✓
- §3.2 field + M207 + empty-list + from_dict/to_dict round-trip + no-bump → Task 2 ✓
- §3.3 W305 soft check (validate-only, both ES+GB resolve, non-outcome warns) → Task 3 ✓
- §3.5 replace_compartment preservation → Task 4 ✓
- §4 augmented `response_pressure_gap` + cycle-safe `_downstream_outcome_ids` + all reachability branches (orphan/governed/unflagged/empty-list/dedupe/both-node/cycle/cross-compartment/append) → Task 5 ✓
- §5 UI card + slug→label mapping + slice/filter/sort + **empty-state hint** + 6→7 → Task 6 ✓
- §6 seed (tags + connecting edge + seed_curonian reader + connection-count bump) producing ≥1 equity + ≥1 orphan row → Task 7 ✓
- §7 e2e card visible + count → Task 8 ✓
- §10 DoD full-suite green + status flip + parent §11 #20 back-pointer + §8a matrix flip → Task 9 ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The only "match the existing idiom" notes are for test-harness rendering/selectors that are house-specific (module HTML rendering, e2e Playwright selectors) — these point at concrete existing tests to copy, not vague instructions. (Post-review: the one literal mistake — `comparative_ui()` missing its module id — is corrected to `comparative_ui("test_id")` in Task 6.)

**DRY:** the fragile outcome-type pair `("Ecosystem Services", "Goods & Benefits")` — which the spec §2.2 calls "the single fact most likely to be mis-coded" — is defined exactly **once** as `data_structure.OUTCOME_ELEMENT_TYPES` and imported by `validate.py` (Task 3) and `comparative.py` (Task 5).

**Type/name consistency:** `outcome_equity_dimensions` (field), `EQUITY_DIMENSIONS`/`EQUITY_SLUGS`/`OUTCOME_ELEMENT_TYPES` (vocab/predicate), `M207_INVALID_EQUITY_DIMENSION`, `W305_EQUITY_DIM_UNKNOWN_ELEMENT`, `_validate_equity_dimensions`, `_downstream_outcome_ids`, and columns `downstream_equity_outcome_count`/`affected_equity_dimensions`/`is_equity_relevant_orphan` are used identically across every task and match the spec.

**Post-review corrections applied (2nd loop):** comparative_ui arity BLOCKER fixed (Task 6); pinned lagoon connection-count test bumped 5→6 (Task 7 Step 4b); JSON edit reframed as whole-object replacement (Task 7); spec'd empty-state disclaimer added (Task 6); parent + scientific-basis doc updates added (Task 9); outcome-type predicate centralized (Tasks 1/3/5).
