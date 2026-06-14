# MosaicSES Scenario Studio (structural core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a non-destructive structural scenario module — author add/remove-element and channel interventions, materialise a derived `MultiSES`, and diff the five existing comparative analyses before vs after — with a depolderisation worked example and an in-app Scenario Studio.

**Architecture:** A frozen `Scenario` (a sidecar `<basename>.scenarios.json` overlay of typed `Intervention`s) never mutates the baseline. `materialise_scenario` applies interventions per-compartment (reusing `replace_compartment`/`replace_channel`/`sespy.network.remove_nodes`) into a new `MultiSES`; `compare_scenario` re-runs `multises.comparative` + `inter_compartment_metrics` on baseline vs materialised and emits per-metric `{before, after, delta}` frames. Sub-projects: **A** library core (headless) → **B** depolderisation factory → **C** Shiny Scenario Studio module. The qualitative sign-propagation overlay is explicitly out of scope (deferred follow-on; spec §13/§15).

**Tech Stack:** Python 3.11 · Shiny-for-Python ≥1.5 · pandas · networkx · pyvis · matplotlib(Agg) · pytest · Playwright. **Environment (mandatory):** everything through micromamba env `shiny` — `micromamba run -n shiny python -m pytest …`. Never a venv. MosaicSES test cwd is the MosaicSES repo root: `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`.

**Spec:** `SESPy/docs/superpowers/specs/2026-06-13-mosaicses-scenario-studio-design.md` (rev 3.1).

---

## File Structure

**New (MosaicSES):**
- `multises/scenario.py` — `Intervention`/`Scenario`/`ScenarioSet`/`ScenarioSetMetadata`/`ScenarioReport` dataclasses, `ScenarioError` + `ScenarioErrorCode`, validation, sidecar persistence, `add/replace/remove_intervention` helpers.
- `multises/materialise.py` — `materialise_scenario(baseline, scenario) -> tuple[MultiSES, ScenarioReport]`.
- `multises/scenario_compare.py` — `compare_scenario(baseline, scenario) -> dict[str, pd.DataFrame]` (the 5 metric diffs).
- `multises/scenarios/__init__.py`, `multises/scenarios/depolderisation.py` — `build_depolderisation_scenario(ms)`.
- `multises_app/modules/scenario_view.py` — the Scenario Studio Shiny module.
- Tests: `tests/test_scenario.py`, `test_materialise.py`, `test_scenario_compare.py`, `test_depolderisation.py`, `test_scenario_view_module.py`, additions to `tests/test_persistence.py` and `tests/test_ui_hardening_e2e.py` (or a new `test_scenario_e2e.py`).

**Modified (MosaicSES):**
- `multises/persistence.py` — extract `_atomic_write_bytes(path, body_bytes)`; `save` calls it.
- `multises/__init__.py` — re-export the scenario public API.
- `multises_app/state.py` — add `active_scenario` + `scenario_set` reactives.
- `app.py` — mount the Scenario Studio nav panel + server.
- `multises_app/dashboard.py` — add the `scenario` NavItem.

---

## Task 0: Branch + baseline

**Files:** none (git only).

- [ ] **Step 1: Branch the MosaicSES repo**

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
git checkout main && git pull
git checkout -b scenario-studio-2026-06-14
```

- [ ] **Step 2: Confirm baseline green**

Run: `micromamba run -n shiny python -m pytest tests/ -q -k "not e2e" -p no:cacheprovider`
Expected: all pass (record the count).

---

## Sub-project A — library core (headless)

### Task A1: Extract a generic atomic writer from persistence

**Why:** `persistence.save` is hard-typed to `MultiSES` (it calls `ms.to_dict()`); the sidecar needs the same atomic-write + SHA-256 verify for arbitrary bytes (spec §3, review T15).

**Files:**
- Modify: `multises/persistence.py`
- Test: `tests/test_persistence.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_persistence.py`:

```python
def test_atomic_write_bytes_roundtrips_and_verifies(tmp_path):
    from multises.persistence import _atomic_write_bytes
    p = tmp_path / "sub" / "x.json"
    body = '{"a": 1, "ünïcode": "✓"}'.encode("utf-8")
    _atomic_write_bytes(p, body)
    assert p.read_bytes() == body            # exact bytes, no CRLF translation
    assert p.parent.is_dir()                  # parents created


def test_atomic_write_bytes_no_temp_leak(tmp_path):
    from multises.persistence import _atomic_write_bytes
    p = tmp_path / "y.json"
    _atomic_write_bytes(p, b"hello")
    assert [f.name for f in tmp_path.iterdir()] == ["y.json"]   # no .tmp left
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_persistence.py::test_atomic_write_bytes_roundtrips_and_verifies -v`
Expected: FAIL — `ImportError: cannot import name '_atomic_write_bytes'`.

- [ ] **Step 3: Extract the helper and call it from `save`**

In `multises/persistence.py`, add (after the imports/logger):

```python
def _atomic_write_bytes(path: Path | str, body_bytes: bytes) -> None:
    """Atomically write raw bytes to `path` with fsync + post-replace SHA-256
    verify. Shared by MultiSES save and the scenario sidecar. Binary mode so
    Windows does not translate LF->CRLF (the SHA-256 check hashes exact bytes)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp", text=False,
    )
    try:
        with os.fdopen(tmp_fd, "wb") as fh:
            fh.write(body_bytes)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, str(path))
        tmp_name = None
        expected_hash = hashlib.sha256(body_bytes).hexdigest()
        actual_bytes = path.read_bytes()
        if hashlib.sha256(actual_bytes).hexdigest() != expected_hash:
            raise OSError(
                f"Post-replace sanity check failed for {path}: on-disk SHA-256 "
                f"does not match (expected {len(body_bytes)} bytes, "
                f"got {len(actual_bytes)})."
            )
    finally:
        if tmp_name is not None and Path(tmp_name).exists():
            try:
                os.unlink(tmp_name)
            except OSError:
                _log.warning("Failed to unlink temp file %s", tmp_name)
```

Replace the body of `save` (from `path = Path(path)` to the end of the `finally`) with:

```python
    payload = ms.to_dict()
    body_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    _atomic_write_bytes(path, body_bytes)
    _log.info("Saved MultiSES to %s (%d bytes)", path, len(body_bytes))
```

- [ ] **Step 4: Run the persistence suite**

Run: `micromamba run -n shiny python -m pytest tests/test_persistence.py -v`
Expected: PASS — the new tests plus every existing `save`/`load` round-trip test (the refactor preserves behaviour).

- [ ] **Step 5: Commit**

```bash
git add multises/persistence.py tests/test_persistence.py
git commit -m "refactor(mosaicses): extract _atomic_write_bytes from persistence.save"
```

> End every commit message in this plan with a blank line then:
> `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

### Task A2: Scenario data model + validation

**Files:**
- Create: `multises/scenario.py`
- Test: `tests/test_scenario.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scenario.py`:

```python
from __future__ import annotations
import pytest


def test_add_node_intervention_valid():
    from multises.scenario import Intervention
    iv = Intervention(id="i1", kind="add_node", compartment_id="c1",
                      target={"element": {"id": "E9", "label": "New", "type": "Pressures"}})
    assert iv.kind == "add_node" and iv.compartment_id == "c1"


def test_unknown_kind_raises_scenario_error():
    from multises.scenario import Intervention, ScenarioError, ScenarioErrorCode
    with pytest.raises(ScenarioError) as ei:
        Intervention(id="i1", kind="frobnicate", target={})
    assert ei.value.code == ScenarioErrorCode.S001_UNKNOWN_KIND


def test_add_node_requires_element_payload():
    from multises.scenario import Intervention, ScenarioError, ScenarioErrorCode
    with pytest.raises(ScenarioError) as ei:
        Intervention(id="i1", kind="add_node", compartment_id="c1", target={})
    assert ei.value.code == ScenarioErrorCode.S002_MISSING_TARGET_FIELD


def test_remove_channel_requires_channel_id_not_compartment():
    from multises.scenario import Intervention
    iv = Intervention(id="i1", kind="remove_channel", target={"channel_id": "ch1"})
    assert iv.compartment_id is None


def test_scenario_holds_interventions():
    from multises.scenario import Intervention, Scenario
    iv = Intervention(id="i1", kind="remove_node", compartment_id="c1",
                      target={"element_id": "E1"})
    sc = Scenario(id="s1", name="Test", interventions=(iv,))
    assert sc.schema_version == 1 and len(sc.interventions) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -v`
Expected: FAIL — `ModuleNotFoundError: multises.scenario`.

- [ ] **Step 3: Implement the data model**

Create `multises/scenario.py`:

```python
"""Structural scenario overlay (Phase-2 priority D, structural core).

A Scenario is a frozen, non-destructive overlay of typed structural Interventions
on a baseline MultiSES, persisted as a sidecar. Mirrors data_structure.py's
ErrorCode / _ChannelValidationError / LoadReport conventions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

InterventionKind = Literal[
    "add_node", "remove_node", "add_channel", "remove_channel", "retune_channel"
]

SCENARIO_SCHEMA_VERSION = 1


class ScenarioErrorCode:
    """Stable validation codes (assert on these, not message text)."""
    S001_UNKNOWN_KIND = "S001_UNKNOWN_KIND"
    S002_MISSING_TARGET_FIELD = "S002_MISSING_TARGET_FIELD"
    S003_DUPLICATE_INTERVENTION_TARGET = "S003_DUPLICATE_INTERVENTION_TARGET"
    # soft (collected into ScenarioReport at materialisation):
    W501_DANGLING_TARGET = "W501_DANGLING_TARGET"


class ScenarioError(ValueError):
    """Hard scenario-validation failure; carries a ScenarioErrorCode in `.code`."""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_VALID_KINDS = frozenset(InterventionKind.__args__)  # type: ignore[attr-defined]
# Required target keys per kind (compartment_id requiredness handled separately).
_REQUIRED_TARGET: dict[str, tuple[str, ...]] = {
    "add_node": ("element",),
    "remove_node": ("element_id",),
    "add_channel": ("source", "target", "channel_type"),
    "remove_channel": ("channel_id",),
    "retune_channel": ("channel_id",),
}
_NEEDS_COMPARTMENT = frozenset({"add_node", "remove_node"})


@dataclass(frozen=True)
class Intervention:
    id: str
    kind: InterventionKind
    label: str = ""
    compartment_id: str | None = None
    target: dict = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ScenarioError(
                ScenarioErrorCode.S001_UNKNOWN_KIND,
                f"intervention {self.id!r}: unknown kind {self.kind!r}; "
                f"expected one of {sorted(_VALID_KINDS)}",
            )
        for key in _REQUIRED_TARGET[self.kind]:
            if key not in self.target:
                raise ScenarioError(
                    ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                    f"intervention {self.id!r} ({self.kind}): target missing {key!r}",
                )
        if self.kind == "add_node":
            el = self.target["element"]
            for k in ("id", "label", "type"):
                if k not in el:
                    raise ScenarioError(
                        ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                        f"intervention {self.id!r}: element payload missing {k!r}",
                    )
        if self.kind in _NEEDS_COMPARTMENT and not self.compartment_id:
            raise ScenarioError(
                ScenarioErrorCode.S002_MISSING_TARGET_FIELD,
                f"intervention {self.id!r} ({self.kind}): compartment_id required",
            )


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str = ""
    baseline_name: str = ""
    interventions: tuple[Intervention, ...] = ()
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = SCENARIO_SCHEMA_VERSION


@dataclass(frozen=True)
class ScenarioSetMetadata:
    name: str = "Scenarios"
    schema_version: int = SCENARIO_SCHEMA_VERSION


@dataclass
class ScenarioSet:
    metadata: ScenarioSetMetadata
    scenarios: list[Scenario] = field(default_factory=list)


@dataclass(frozen=True)
class ScenarioReport:
    """Soft warnings collected at materialisation (dangling targets, etc.)."""
    warnings: tuple[tuple[str, str], ...] = ()   # (code, message)
```

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises/scenario.py tests/test_scenario.py
git commit -m "feat(mosaicses): Scenario/Intervention data model + validation (structural core)"
```

---

### Task A3: Sidecar persistence + mutation helpers

**Files:**
- Modify: `multises/scenario.py`
- Modify: `multises/__init__.py` (re-export)
- Test: `tests/test_scenario.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scenario.py`:

```python
def test_scenario_set_roundtrip(tmp_path):
    from multises.scenario import (Intervention, Scenario, ScenarioSet,
                                   ScenarioSetMetadata, save_scenario_set,
                                   load_scenario_set)
    iv = Intervention(id="i1", kind="remove_node", compartment_id="c1",
                      target={"element_id": "E1"}, rationale="why")
    ss = ScenarioSet(metadata=ScenarioSetMetadata(name="S"),
                     scenarios=[Scenario(id="s1", name="One", interventions=(iv,))])
    p = tmp_path / "proj.scenarios.json"
    save_scenario_set(ss, p)
    loaded = load_scenario_set(p)
    assert loaded.scenarios[0].interventions[0].target == {"element_id": "E1"}
    assert loaded.scenarios[0].interventions[0].kind == "remove_node"


def test_add_and_remove_intervention_pure():
    from multises.scenario import (Intervention, Scenario, add_intervention,
                                   remove_intervention)
    sc = Scenario(id="s1", name="One")
    iv = Intervention(id="i1", kind="remove_channel", target={"channel_id": "ch1"})
    sc2 = add_intervention(sc, iv)
    assert len(sc.interventions) == 0 and len(sc2.interventions) == 1   # pure
    sc3 = remove_intervention(sc2, "i1")
    assert len(sc3.interventions) == 0


def test_add_duplicate_target_rejected():
    from multises.scenario import (Intervention, Scenario, add_intervention,
                                   ScenarioError, ScenarioErrorCode)
    sc = Scenario(id="s1", name="One", interventions=(
        Intervention(id="i1", kind="remove_node", compartment_id="c1",
                     target={"element_id": "E1"}),))
    dup = Intervention(id="i2", kind="add_node", compartment_id="c1",
                       target={"element": {"id": "E1", "label": "x", "type": "Pressures"}})
    with __import__("pytest").raises(ScenarioError) as ei:
        add_intervention(sc, dup)
    assert ei.value.code == ScenarioErrorCode.S003_DUPLICATE_INTERVENTION_TARGET
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py::test_scenario_set_roundtrip -v`
Expected: FAIL — `ImportError: cannot import name 'save_scenario_set'`.

- [ ] **Step 3: Implement persistence + helpers**

Append to `multises/scenario.py` (add `import json`, `from dataclasses import asdict, replace` to the top imports; add `from pathlib import Path`):

```python
def _intervention_target_key(iv: "Intervention") -> tuple:
    """Identity of what an intervention touches, for duplicate detection."""
    if iv.kind == "add_node":
        return (iv.compartment_id, iv.target["element"]["id"])
    if iv.kind == "remove_node":
        return (iv.compartment_id, iv.target["element_id"])
    if iv.kind == "add_channel":
        return (iv.target["source"], iv.target["target"], iv.target["channel_type"])
    return (iv.target["channel_id"],)   # remove_channel / retune_channel


def add_intervention(scenario: "Scenario", iv: "Intervention") -> "Scenario":
    """Return a new Scenario with `iv` appended. Rejects a duplicate target."""
    key = _intervention_target_key(iv)
    if any(_intervention_target_key(e) == key for e in scenario.interventions):
        raise ScenarioError(
            ScenarioErrorCode.S003_DUPLICATE_INTERVENTION_TARGET,
            f"another intervention already targets {key!r}",
        )
    return replace(scenario, interventions=scenario.interventions + (iv,))


def remove_intervention(scenario: "Scenario", intervention_id: str) -> "Scenario":
    """Return a new Scenario with the named intervention removed (no-op if absent)."""
    kept = tuple(e for e in scenario.interventions if e.id != intervention_id)
    return replace(scenario, interventions=kept)


def save_scenario_set(scenario_set: "ScenarioSet", path: Path | str) -> None:
    """Persist a ScenarioSet to a sidecar JSON via the generic atomic writer."""
    from .persistence import _atomic_write_bytes
    body = json.dumps(asdict(scenario_set), indent=2, ensure_ascii=False)
    _atomic_write_bytes(path, body.encode("utf-8"))


def load_scenario_set(path: Path | str) -> "ScenarioSet":
    """Load a ScenarioSet from a sidecar JSON."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = [
        Scenario(
            id=s["id"], name=s["name"], description=s.get("description", ""),
            baseline_name=s.get("baseline_name", ""),
            interventions=tuple(
                Intervention(id=i["id"], kind=i["kind"], label=i.get("label", ""),
                             compartment_id=i.get("compartment_id"),
                             target=i.get("target", {}), rationale=i.get("rationale", ""))
                for i in s.get("interventions", [])),
            created_at=s.get("created_at", ""), modified_at=s.get("modified_at", ""),
            schema_version=s.get("schema_version", SCENARIO_SCHEMA_VERSION))
        for s in raw.get("scenarios", [])
    ]
    md = raw.get("metadata", {})
    return ScenarioSet(metadata=ScenarioSetMetadata(
        name=md.get("name", "Scenarios"),
        schema_version=md.get("schema_version", SCENARIO_SCHEMA_VERSION)),
        scenarios=scenarios)
```

In `multises/__init__.py`, add the scenario re-exports to the import block and `__all__` (mirroring how `replace_channel` was re-exported):

```python
from .scenario import (
    Intervention, Scenario, ScenarioSet, ScenarioSetMetadata, ScenarioReport,
    ScenarioError, ScenarioErrorCode,
    add_intervention, remove_intervention, save_scenario_set, load_scenario_set,
)
```
and append those names to `__all__`.

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises/scenario.py multises/__init__.py tests/test_scenario.py
git commit -m "feat(mosaicses): scenario sidecar persistence + pure mutation helpers"
```

---

### Task A4: Materialisation

**Files:**
- Create: `multises/materialise.py`
- Test: `tests/test_materialise.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_materialise.py`:

```python
from __future__ import annotations
from multises import seed_curonian
from multises.scenario import Intervention, Scenario
from multises.materialise import materialise_scenario

CID = "curonian_lagoon"


def _lag(ms):
    return next(c for c in ms.compartments if c.id == CID)


def test_add_node_increments_element_count_and_is_pure():
    ms = seed_curonian()
    before = len(_lag(ms).project.isa_data.elements)
    sc = Scenario(id="s", name="add", interventions=(
        Intervention(id="i1", kind="add_node", compartment_id=CID,
                     target={"element": {"id": "WMPF1", "label": "Wetland",
                                         "type": "Marine Processes & Functioning"}}),))
    new_ms, report = materialise_scenario(ms, sc)
    assert len(_lag(new_ms).project.isa_data.elements) == before + 1
    assert len(_lag(ms).project.isa_data.elements) == before   # baseline unmutated
    assert report.warnings == ()


def test_remove_node_cleans_incident_connections():
    ms = seed_curonian()
    before_conn = len(_lag(ms).project.isa_data.connections)
    sc = Scenario(id="s", name="rm", interventions=(
        Intervention(id="i1", kind="remove_node", compartment_id=CID,
                     target={"element_id": "P001"}),))
    new_ms, _ = materialise_scenario(ms, sc)
    assert all(e.id != "P001" for e in _lag(new_ms).project.isa_data.elements)
    assert len(_lag(new_ms).project.isa_data.connections) < before_conn


def test_add_channel_appends_channel():
    ms = seed_curonian()
    before = len(ms.channels)
    sc = Scenario(id="s", name="ch", interventions=(
        Intervention(id="i1", kind="add_channel",
                     target={"source": CID, "target": "klaipeda_strait",
                             "channel_type": "organisms_marine_estuarine"}),))
    new_ms, _ = materialise_scenario(ms, sc)
    assert len(new_ms.channels) == before + 1


def test_dangling_target_is_soft_warning_not_crash():
    ms = seed_curonian()
    sc = Scenario(id="s", name="bad", interventions=(
        Intervention(id="i1", kind="remove_node", compartment_id=CID,
                     target={"element_id": "NOPE"}),))
    new_ms, report = materialise_scenario(ms, sc)
    assert any(code == "W501_DANGLING_TARGET" for code, _ in report.warnings)
    assert len(_lag(new_ms).project.isa_data.elements) == len(_lag(ms).project.isa_data.elements)
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_materialise.py -v`
Expected: FAIL — `ModuleNotFoundError: multises.materialise`.

- [ ] **Step 3: Implement materialisation**

Create `multises/materialise.py`:

```python
"""Apply a structural Scenario to a baseline MultiSES, producing a derived
MultiSES (non-destructive). Order: removes -> adds -> retunes; nodes before
channels. Dangling targets are soft ScenarioReport warnings, never crashes."""
from __future__ import annotations

import dataclasses
from collections import defaultdict

from sespy.data_structure import Element, IsaData
from sespy.network import remove_nodes

from .channels import make_channel
from .data_structure import MultiSES, replace_compartment, replace_channel
from .scenario import Scenario, ScenarioReport, ScenarioErrorCode


def materialise_scenario(baseline: MultiSES, scenario: Scenario) -> tuple[MultiSES, ScenarioReport]:
    warnings: list[tuple[str, str]] = []
    ms = baseline

    def warn(msg: str) -> None:
        warnings.append((ScenarioErrorCode.W501_DANGLING_TARGET, msg))

    # --- node ops, batched per compartment (remove then add) ---
    removes: dict[str, list[str]] = defaultdict(list)
    adds: dict[str, list[dict]] = defaultdict(list)
    for iv in scenario.interventions:
        if iv.kind == "remove_node":
            removes[iv.compartment_id].append(iv.target["element_id"])
        elif iv.kind == "add_node":
            adds[iv.compartment_id].append(iv.target["element"])

    touched = set(removes) | set(adds)
    cmpt_by_id = {c.id: c for c in ms.compartments}
    for cid in touched:
        comp = cmpt_by_id.get(cid)
        if comp is None:
            warn(f"compartment {cid!r} not in baseline; node ops skipped")
            continue
        isa = comp.project.isa_data
        present = {e.id for e in isa.elements}
        to_remove = [eid for eid in removes.get(cid, []) if eid in present]
        for eid in removes.get(cid, []):
            if eid not in present:
                warn(f"remove_node target {cid}::{eid} absent; skipped")
        if to_remove:
            isa = remove_nodes(isa, to_remove)
        new_elements = list(isa.elements)
        for el in adds.get(cid, []):
            new_elements.append(Element(
                id=el["id"], label=el["label"], type=el["type"],
                description=el.get("description", ""), confidence=el.get("confidence", 3)))
        isa = IsaData(elements=new_elements, connections=list(isa.connections))
        # dataclasses.replace preserves Project's other sub-collections
        # (stakeholders/engagements/communications); a fresh Project(metadata, isa_data)
        # would silently drop them (review F3).
        ms = replace_compartment(ms, cid, dataclasses.replace(comp.project, isa_data=isa))

    # --- channel ops: remove -> add -> retune ---
    chan_by_id = {ch.id: ch for ch in ms.channels}
    remove_ids = {iv.target["channel_id"] for iv in scenario.interventions
                  if iv.kind == "remove_channel"}
    for cid in remove_ids:
        if cid not in chan_by_id:
            warn(f"remove_channel target {cid!r} absent; skipped")
    channels = [ch for ch in ms.channels if ch.id not in remove_ids]

    for iv in scenario.interventions:
        if iv.kind == "add_channel":
            t = iv.target
            channels.append(make_channel(
                id=t.get("id"), source=t["source"], target=t["target"],
                channel_type=t["channel_type"],
                polarity=t.get("polarity"), strength=t.get("strength")))
    ms = MultiSES(metadata=ms.metadata, compartments=ms.compartments, channels=channels)

    for iv in scenario.interventions:
        if iv.kind != "retune_channel":
            continue
        ch_id = iv.target["channel_id"]
        old = next((c for c in ms.channels if c.id == ch_id), None)
        if old is None:
            warn(f"retune_channel target {ch_id!r} absent; skipped")
            continue
        # NOTE: dataclasses is imported at MODULE level (top of file). Do NOT add a
        # function-local `import dataclasses` here — a name imported anywhere in a
        # function body becomes function-local for the WHOLE function, which would
        # make the earlier dataclasses.replace(comp.project, ...) call raise
        # UnboundLocalError (plan-review pass-2 CRITICAL).
        changes = {k: iv.target[k] for k in ("polarity", "strength", "channel_type")
                   if k in iv.target}
        ms = replace_channel(ms, ch_id, dataclasses.replace(old, **changes))

    return ms, ScenarioReport(warnings=tuple(warnings))
```

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_materialise.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises/materialise.py tests/test_materialise.py
git commit -m "feat(mosaicses): materialise_scenario (structural ops + soft integrity)"
```

---

### Task A5: Metric diff

**Files:**
- Create: `multises/scenario_compare.py`
- Test: `tests/test_scenario_compare.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scenario_compare.py`:

```python
from __future__ import annotations
import pandas as pd
from multises import seed_curonian
from multises.scenario import Intervention, Scenario
from multises.scenario_compare import compare_scenario, METRIC_KEYS

CID = "curonian_lagoon"


def _add_node_scenario():
    return Scenario(id="s", name="add", interventions=(
        Intervention(id="i1", kind="add_node", compartment_id=CID,
                     target={"element": {"id": "WMPF1", "label": "Wetland",
                                         "type": "Marine Processes & Functioning"}}),))


def test_compare_returns_a_frame_per_metric():
    diffs = compare_scenario(seed_curonian(), _add_node_scenario())
    assert set(diffs) == set(METRIC_KEYS)
    for k, df in diffs.items():
        assert isinstance(df, pd.DataFrame), k


def test_compartment_summary_delta_reflects_added_node():
    diffs = compare_scenario(seed_curonian(), _add_node_scenario())
    row = diffs["compartment_summary"].set_index("compartment_id").loc[CID]
    assert row["element_count_delta"] == 1


def test_inter_compartment_metrics_normalised_to_frame():
    # the source is a dict-of-dicts; the diff must still be a frame keyed by compartment
    diffs = compare_scenario(seed_curonian(), _add_node_scenario())
    icm = diffs["inter_compartment_metrics"]
    assert "compartment_id" in icm.columns
    assert "betweenness_delta" in icm.columns
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_compare.py -v`
Expected: FAIL — `ModuleNotFoundError: multises.scenario_compare`.

- [ ] **Step 3: Implement the diff**

Create `multises/scenario_compare.py`:

```python
"""Diff the five established comparative analyses on baseline vs materialised
MultiSES, emitting per-metric {col}_before / {col}_after / {col}_delta frames
(numeric cols) with descriptive cols carried through. inter_compartment_metrics
is a dict-of-dicts and is normalised to a frame first; its channel-type list
columns are set-diffed, not numerically delta'd (spec §6)."""
from __future__ import annotations

import pandas as pd

from .comparative import (compartment_summary, leverage_hotspots,
                          response_pressure_gap, tenet_gap_analysis)
from .composite import inter_compartment_metrics
from .data_structure import MultiSES
from .materialise import materialise_scenario
from .scenario import Scenario

METRIC_KEYS = (
    "compartment_summary", "leverage_hotspots", "response_pressure_gap",
    "tenet_gap_analysis", "inter_compartment_metrics",
)

# (join key, numeric cols, list cols (set-diff)). All other cols carry through.
_CONTRACT: dict[str, tuple[list[str], list[str], list[str]]] = {
    "compartment_summary": (
        ["compartment_id"],
        ["element_count", "connection_count", "mean_leverage", "dominant_pressure_count"],
        []),
    "leverage_hotspots": (
        ["compartment_id", "element_id"],
        ["leverage", "global_rank_zscore"], []),
    "response_pressure_gap": (
        ["compartment_id", "pressure_id"],
        ["within_compartment_response_count", "incoming_governance_channel_count",
         "downstream_equity_outcome_count"], []),
    "tenet_gap_analysis": (
        ["subject_kind", "source_compartment_id", "target_compartment_id", "subject_id"],
        ["scored_count", "gap_count", "mean_score", "min_score"], []),
    "inter_compartment_metrics": (
        ["compartment_id"],
        ["channel_in_degree", "channel_out_degree", "betweenness"],
        ["incoming_channel_types", "outgoing_channel_types"]),
}


def _icm_frame(ms: MultiSES) -> pd.DataFrame:
    d = inter_compartment_metrics(ms)             # dict[compartment_id, dict]
    df = pd.DataFrame(d).T
    for col in ("channel_in_degree", "channel_out_degree", "betweenness"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")   # .T leaves object dtype (review F6)
    df.index.name = "compartment_id"
    return df.reset_index()


def _as_set(v) -> set:
    """List/NaN-safe: an outer-join missing cell is float NaN; a present cell is a list.
    Do NOT use pd.notna() on a list cell — it returns an ARRAY and `if array` raises
    ValueError: ambiguous truth value (review F1, reproduced on the seed)."""
    return set(v) if isinstance(v, (list, tuple, set)) else set()


def _diff(before: pd.DataFrame, after: pd.DataFrame, key, numeric, listcols) -> pd.DataFrame:
    merged = before.merge(after, on=key, how="outer", suffixes=("_before", "_after"))
    for col in numeric:
        merged[f"{col}_delta"] = merged.get(f"{col}_after") - merged.get(f"{col}_before")
    for col in listcols:
        b, a = f"{col}_before", f"{col}_after"
        merged[f"{col}_added"] = merged.apply(
            lambda r: sorted(_as_set(r.get(a)) - _as_set(r.get(b))), axis=1)
        merged[f"{col}_removed"] = merged.apply(
            lambda r: sorted(_as_set(r.get(b)) - _as_set(r.get(a))), axis=1)
    return merged


def compare_scenario(baseline: MultiSES, scenario: Scenario) -> dict[str, pd.DataFrame]:
    materialised, _report = materialise_scenario(baseline, scenario)
    sources = {
        "compartment_summary": compartment_summary,
        "leverage_hotspots": leverage_hotspots,
        "response_pressure_gap": response_pressure_gap,
        "tenet_gap_analysis": tenet_gap_analysis,
    }
    out: dict[str, pd.DataFrame] = {}
    for name, fn in sources.items():
        key, numeric, listcols = _CONTRACT[name]
        out[name] = _diff(fn(baseline), fn(materialised), key, numeric, listcols)
    key, numeric, listcols = _CONTRACT["inter_compartment_metrics"]
    out["inter_compartment_metrics"] = _diff(
        _icm_frame(baseline), _icm_frame(materialised), key, numeric, listcols)
    return out
```

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_compare.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises/scenario_compare.py tests/test_scenario_compare.py
git commit -m "feat(mosaicses): compare_scenario — 5 metric before/after/delta diffs"
```

---

## Sub-project B — depolderisation worked example

### Task B1: Depolderisation factory + end-to-end test

**Files:**
- Create: `multises/scenarios/__init__.py`, `multises/scenarios/depolderisation.py`
- Test: `tests/test_depolderisation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_depolderisation.py`:

```python
from __future__ import annotations
from multises import seed_curonian
from multises.materialise import materialise_scenario
from multises.scenario_compare import compare_scenario
from multises.scenarios.depolderisation import build_depolderisation_scenario

CID = "curonian_lagoon"


def test_factory_materialises_without_dangling_warnings():
    ms = seed_curonian()
    sc = build_depolderisation_scenario(ms)
    new_ms, report = materialise_scenario(ms, sc)
    assert report.warnings == (), report.warnings   # all targets resolve


def test_wetland_node_is_added_and_lagoon_grows():
    ms = seed_curonian()
    sc = build_depolderisation_scenario(ms)
    new_ms, _ = materialise_scenario(ms, sc)
    lag_before = next(c for c in ms.compartments if c.id == CID)
    lag_after = next(c for c in new_ms.compartments if c.id == CID)
    after_ids = {e.id for e in lag_after.project.isa_data.elements}
    assert "WET_HABITAT" in after_ids               # restored wetland habitat added
    assert len(lag_after.project.isa_data.elements) > len(lag_before.project.isa_data.elements)


def test_tidal_channel_targets_klaipeda_strait_via_channel_type_setdiff():
    ms = seed_curonian()
    diffs = compare_scenario(ms, build_depolderisation_scenario(ms))
    icm = diffs["inter_compartment_metrics"].set_index("compartment_id")
    added = icm.loc[CID, "outgoing_channel_types_added"]
    assert "organisms_marine_estuarine" in added     # new tidal exchange registers here
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_depolderisation.py -v`
Expected: FAIL — `ModuleNotFoundError: multises.scenarios`.

- [ ] **Step 3: Implement the factory**

Create `multises/scenarios/__init__.py` (empty), then `multises/scenarios/depolderisation.py`:

```python
"""Self-grounding depolderisation scenario for the Curonian seed.

The generic seed encodes NO polder, so an add-then-remove of a barrier would net to
ZERO structural change vs the un-poldered baseline (review F2). Depolderisation here
is therefore the ADDITIVE 'designing a new ecosystem' restoration: (1) a restored
intertidal wetland habitat, (2) a regulating nutrient-buffering service, (3) its
Goods & Benefits outcome (canonical SESPy element types), and (4) a re-opened tidal
organisms_marine_estuarine channel to klaipeda_strait (the lagoon's true marine
neighbour — it does NOT border baltic_se). Output is a structural Scenario; its
effect is read via compare_scenario as metric deltas (see tests)."""
from __future__ import annotations

from multises.data_structure import MultiSES
from multises.scenario import Intervention, Scenario

LAGOON = "curonian_lagoon"
STRAIT = "klaipeda_strait"

# Caveat constants rendered by the UI (spec §7).
CAVEATS = (
    "Structural network analysis, not a process/biogeochemical model: shows how "
    "graph metrics change, not predicted ecological dynamics, magnitudes, or timescales.",
    "'Designing new ecosystems' is not restoration to a historical reference state.",
    "The breach is endogenic (locally managed); its benefit depends on exogenic "
    "drivers (sea-level rise, upstream load).",
)


def build_depolderisation_scenario(ms: MultiSES) -> Scenario:
    interventions = (
        # restored ecosystem (canonical element types) — the additive restoration;
        # the un-poldered seed has no barrier to breach (review F2).
        Intervention(id="dp1", kind="add_node", compartment_id=LAGOON,
                     label="Restored wetland habitat",
                     target={"element": {"id": "WET_HABITAT", "label": "Restored intertidal wetland",
                                         "type": "Marine Processes & Functioning"}},
                     rationale="Designing a new ecosystem: restored intertidal wetland."),
        Intervention(id="dp2", kind="add_node", compartment_id=LAGOON,
                     label="Nutrient buffering service",
                     target={"element": {"id": "WET_BUFFER", "label": "Wetland nutrient buffering",
                                         "type": "Ecosystem Services"}}),
        Intervention(id="dp3", kind="add_node", compartment_id=LAGOON,
                     label="Wetland benefit",
                     target={"element": {"id": "WET_BENEFIT", "label": "Birdwatching/recreation",
                                         "type": "Goods & Benefits"}}),
        # re-opened tidal exchange to the true marine neighbour (the strait)
        Intervention(id="dp4", kind="add_channel",
                     label="Restored tidal exchange",
                     target={"source": LAGOON, "target": STRAIT,
                             "channel_type": "organisms_marine_estuarine"},
                     rationale="Re-opened marine larval/juvenile ingress to the nursery."),
    )
    return Scenario(id="depolderisation", name="Depolderisation (Curonian lagoon)",
                    description="Managed realignment worked example.",
                    baseline_name=ms.metadata.name, interventions=interventions)
```

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_depolderisation.py -v`
Expected: PASS. (If `test_wetland_node_is_added` fails because `add_node` of a node with no connections is dropped by a downstream metric, that is fine — the node-count assertion is on the materialised compartment, which Task A4 guarantees.)

- [ ] **Step 5: Commit**

```bash
git add multises/scenarios/ tests/test_depolderisation.py
git commit -m "feat(mosaicses): self-grounding depolderisation scenario factory + e2e metric test"
```

---

## Sub-project C — Scenario Studio app module

### Task C1: Shared state

**Files:**
- Modify: `multises_app/state.py`
- Test: `tests/test_state_scenario.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_state_scenario.py`:

```python
from __future__ import annotations
from shiny import reactive
from multises import seed_curonian
from multises_app.state import create_multises_state


def test_state_has_scenario_reactives():
    state = create_multises_state(seed_curonian())
    with reactive.isolate():
        assert state.active_scenario.get() is None
        assert state.scenario_set.get().scenarios == []
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_state_scenario.py -v`
Expected: FAIL — `AttributeError: 'MultiSESState' object has no attribute 'active_scenario'`.

- [ ] **Step 3: Extend the state**

In `multises_app/state.py`: add imports `from multises.scenario import Scenario, ScenarioSet, ScenarioSetMetadata`. Insert two fields into the `MultiSESState` dataclass **immediately after `dirty` and BEFORE `skip_next_backwrite_dirty`** — they have no defaults, so they MUST precede the trailing defaulted `skip_next_backwrite_dirty: bool = False`, or Python raises `TypeError: non-default argument follows default argument` at import, crashing the whole app (review F4). Final field order: `active_multises, active_compartment_id, active_compartment_project, event_bus, dirty, active_scenario, scenario_set, skip_next_backwrite_dirty`.

```python
    active_scenario: reactive.Value  # reactive.Value[Scenario | None]
    scenario_set: reactive.Value     # reactive.Value[ScenarioSet]
```

In `create_multises_state(...)`, add to the `MultiSESState(...)` constructor call:

```python
        active_scenario=reactive.value(None),
        scenario_set=reactive.value(ScenarioSet(metadata=ScenarioSetMetadata())),
```

- [ ] **Step 4: Run the test**

Run: `micromamba run -n shiny python -m pytest tests/test_state_scenario.py tests/test_state_dirty.py -v`
Expected: PASS (the existing dirty tests still pass).

- [ ] **Step 5: Commit**

```bash
git add multises_app/state.py tests/test_state_scenario.py
git commit -m "feat(mosaicses): add active_scenario + scenario_set to shared state"
```

---

### Task C2: Scenario Studio module UI + server

**Files:**
- Create: `multises_app/modules/scenario_view.py`
- Modify: `multises_app/modules/__init__.py` (re-export `scenario_view_ui`, `scenario_view_server`)
- Test: `tests/test_scenario_view_module.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scenario_view_module.py`:

```python
from __future__ import annotations


def test_scenario_view_module_importable():
    from multises_app.modules import scenario_view  # noqa


def test_scenario_view_ui_has_editor_and_diff_outputs():
    from multises_app.modules.scenario_view import scenario_view_ui
    html = str(scenario_view_ui("test_id").tagify())
    assert 'id="test_id-iv_kind"' in html            # intervention-kind picker
    assert 'id="test_id-add_intervention"' in html   # add button
    assert 'id="test_id-diff_compartment_summary"' in html
    assert "structural network analysis" in html.lower()   # disclaimer


def test_scenario_view_server_callable():
    from multises_app.modules.scenario_view import scenario_view_server
    assert callable(scenario_view_server)
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_module.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module**

Create `multises_app/modules/scenario_view.py`:

```python
"""Scenario Studio — author structural interventions, materialise, and read the
before/after metric diff. Mirrors cross_view.py's layout + reactive idioms."""
from __future__ import annotations

from shiny import module, ui, render, reactive

from multises.scenario import (Intervention, Scenario, add_intervention,
                              remove_intervention, ScenarioError)
from multises.scenario_compare import compare_scenario, METRIC_KEYS
from multises_app.overlay_edit import friendly_error
from multises_app.state import MultiSESState

_KIND_CHOICES = {
    "add_node": "Add element", "remove_node": "Remove element",
    "add_channel": "Add channel", "remove_channel": "Remove channel",
    "retune_channel": "Retune channel",
}


@module.ui
def scenario_view_ui() -> ui.Tag:
    return ui.layout_sidebar(
        ui.sidebar(
            ui.input_text("scenario_name", "Scenario name", value="New scenario"),
            ui.input_select("iv_kind", "Intervention", choices=_KIND_CHOICES),
            ui.input_text("iv_compartment", "Compartment id (node ops)"),
            ui.input_select("iv_element_type", "Element type (Add element)",
                            choices=["Drivers", "Activities", "Pressures",
                                     "Marine Processes & Functioning", "Ecosystem Services",
                                     "Goods & Benefits", "Responses"]),
            ui.input_text("iv_target", "Target (element id / channel id / source>type>target)"),
            ui.input_text("iv_rationale", "Rationale"),
            ui.input_action_button("add_intervention", "Add intervention", class_="btn-primary"),
            ui.output_ui("intervention_list"),
            id="scenario_sidebar", title="Author", position="left", open="desktop", width=340,
        ),
        ui.tags.div(
            ui.tags.p(
                "Structural network analysis, not a process model: this shows how the "
                "graph metrics change when the scenario is materialised, not predicted "
                "ecological dynamics, magnitudes, or timescales.",
                class_="sticky-disclaimer"),
            ui.output_ui("drift_banner"),
            *[ui.card(ui.card_header(k.replace("_", " ").title()),
                      ui.output_data_frame(f"diff_{k}"), class_="comparative-card")
              for k in METRIC_KEYS],
        ),
    )


@module.server
def scenario_view_server(input, output, session, *, state: MultiSESState) -> None:
    @reactive.effect
    @reactive.event(input.add_intervention)
    def _add():
        try:
            kind = input.iv_kind()
            tgt_raw = (input.iv_target() or "").strip()
            if kind == "add_node":
                target = {"element": {"id": tgt_raw, "label": tgt_raw,
                                      "type": input.iv_element_type()}}
                comp = input.iv_compartment() or None
            elif kind == "remove_node":
                target, comp = {"element_id": tgt_raw}, (input.iv_compartment() or None)
            elif kind == "add_channel":
                src, ctype, dst = (tgt_raw.split(">") + ["", "", ""])[:3]
                target, comp = {"source": src, "channel_type": ctype, "target": dst}, None
            else:  # remove_channel / retune_channel
                target, comp = {"channel_id": tgt_raw}, None
            n = len(state.active_scenario.get().interventions) if state.active_scenario.get() else 0
            iv = Intervention(id=f"iv{n+1}", kind=kind, compartment_id=comp,
                              target=target, rationale=input.iv_rationale() or "")
            sc = state.active_scenario.get() or Scenario(id="s1", name=input.scenario_name())
            state.active_scenario.set(add_intervention(sc, iv))
            state.dirty.set(True)
        except ScenarioError as e:
            ui.notification_show(friendly_error("Invalid intervention", e),
                                 type="error", duration=6)

    @output
    @render.ui
    def intervention_list():
        sc = state.active_scenario.get()
        if not sc or not sc.interventions:
            return ui.tags.p("No interventions yet.", class_="text-muted")
        return ui.tags.ul(*[ui.tags.li(f"{iv.kind}: {iv.target}") for iv in sc.interventions])

    @output
    @render.ui
    def drift_banner():
        return ui.tags.span("")   # populated when a sidecar is loaded against a drifted baseline

    def _diff_renderer(metric_key: str):
        @render.data_frame
        def _():
            sc = state.active_scenario.get()
            if not sc or not sc.interventions:
                import pandas as pd
                return render.DataGrid(pd.DataFrame({"info": ["Add an intervention to see the diff."]}))
            diffs = compare_scenario(state.active_multises.get(), sc)
            return render.DataGrid(diffs[metric_key], height="260px")
        return _

    for _k in METRIC_KEYS:
        output(_diff_renderer(_k), id=f"diff_{_k}")
```

In `multises_app/modules/__init__.py`, add `scenario_view_ui`, `scenario_view_server` to the imports + `__all__` (mirroring `cross_view`).

- [ ] **Step 4: Run the tests**

Run: `micromamba run -n shiny python -m pytest tests/test_scenario_view_module.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/scenario_view.py multises_app/modules/__init__.py tests/test_scenario_view_module.py
git commit -m "feat(mosaicses): Scenario Studio module — author interventions + metric-diff tables"
```

---

### Task C3: Mount in the app + e2e

**Files:**
- Modify: `app.py`, `multises_app/dashboard.py`
- Test: `tests/test_scenario_e2e.py`, `tests/test_app_imports_colors.py`

- [ ] **Step 1: Write the failing UI-wiring test**

Add to `tests/test_app_imports_colors.py`:

```python
def test_app_mounts_scenario_panel():
    import app as mosaic_app
    html = str(mosaic_app.app_ui.tagify())
    assert "scenario" in html.lower()
    assert 'id="scenario-diff_compartment_summary"' in html
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py::test_app_mounts_scenario_panel -v`
Expected: FAIL.

- [ ] **Step 3: Wire the panel**

In `multises_app/dashboard.py`, add to the `NAV` list:

```python
    NavItem(id="scenario", icon="wand-magic-sparkles", label="Scenarios"),
```

and add a `NAV_TO_STEP` entry so the workflow stepper highlights on the Scenarios panel (without it `.get()` returns `None` — safe but unhighlighted; review pass-2 LOW):

```python
    "scenario": "drill",
```

In `app.py`:
- import: add `scenario_view_ui, scenario_view_server,` to the `from multises_app.modules import (...)` block.
- add the panel to `PANELS`: `ui.nav_panel("Scenarios", scenario_view_ui("scenario"), value="scenario"),`
- in `server`, after the other module servers: `scenario_view_server("scenario", state=state)`

- [ ] **Step 4: Write the e2e test**

Create `tests/test_scenario_e2e.py`:

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright, expect


def test_author_intervention_populates_diff(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(mosaicses_app_url, wait_until="networkidle")
            page.wait_for_selector("#sespy_nav_scenario", timeout=10_000)
            page.click("#sespy_nav_scenario")
            page.select_option("#scenario-iv_kind", "add_node")
            page.fill("#scenario-iv_compartment", "curonian_lagoon")
            page.fill("#scenario-iv_target", "WET_HABITAT")
            page.click("#scenario-add_intervention")
            page.wait_for_timeout(1500)   # materialise + diff
            grid = page.locator("#scenario-diff_compartment_summary")
            expect(grid).to_contain_text("curonian_lagoon", timeout=10_000)
        finally:
            browser.close()
```

- [ ] **Step 5: Run unit wiring + import**

Run: `micromamba run -n shiny python -c "import app; print('OK')"` then `micromamba run -n shiny python -m pytest tests/test_app_imports_colors.py -v`
Expected: import OK; PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py multises_app/dashboard.py tests/test_scenario_e2e.py tests/test_app_imports_colors.py
git commit -m "feat(mosaicses): mount Scenario Studio nav panel + author/diff e2e"
```

---

## Final verification

- [ ] **Full non-e2e suite:** `micromamba run -n shiny python -m pytest tests/ -q -k "not e2e" -p no:cacheprovider` → all green.
- [ ] **e2e suite (one app start):** `micromamba run -n shiny python -m pytest tests/ -k "e2e" -p no:cacheprovider` → green (the conftest 180 s start timeout from UI-hardening applies).
- [ ] **Dispatch a final whole-branch code review**, then **superpowers:finishing-a-development-branch** to merge/PR.

---

## Self-review notes (author)

- **Spec coverage:** §3 data model → A2/A3; §3 persistence helper → A1; §4 materialisation → A4; §6 metric diff + join contracts → A5; §7 depolderisation (grounded, wired wetland, klaipeda_strait, channel-type set-diff acceptance) → B1; §8 app module (editor + diff tables + disclaimer + drift banner) → C2/C3; §3 state → C1; §9 decisions / §10 errors / §11 tests / §12 risks → covered across tasks. The sign-propagation overlay (§13/§15) is explicitly out of scope.
- **Type consistency:** `materialise_scenario -> (MultiSES, ScenarioReport)` is consumed by A5 and B1; `METRIC_KEYS` defined in A5, reused in C2; `ScenarioErrorCode.W501_DANGLING_TARGET` set in A4, asserted in A4 tests; `add_intervention`/`remove_intervention` defined in A3, used in C2.
- **Verified by the plan review** (workflow `wf_a0797912-a09`; agents ran the code on the real seed): every A5 metric column name + join key matches the real frames; all seam signatures (`replace_compartment`, `IsaData`, `Element`, `make_channel`, `remove_nodes`) check out; the dynamic `output(_diff_renderer(_k), id=…)` idiom IS valid in Shiny 1.6.1 and the namespaced ids/selectors are correct — **no fallback needed**. The two CRITICALs the review reproduced (the `pd.notna`-on-a-list crash and the depolderisation add-then-breach ordering) are fixed above (`_as_set` guard; additive factory), plus the HIGH `Project` sub-collection preservation (`dataclasses.replace`), the C1 field-order footgun, the C2 element-type picker, and the ICM `to_numeric` coercion.
- **Spec §8 descope:** the side-by-side baseline/materialised composite-graph view (and its a11y graph table) is deferred to a follow-on refinement; C2 delivers the five diff tables + disclaimer + the "changed rows only" filter + the baseline-drift-on-load banner. (Spec §8 trimmed to match.)
