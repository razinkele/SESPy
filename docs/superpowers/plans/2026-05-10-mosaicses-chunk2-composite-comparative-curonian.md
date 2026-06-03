# MosaicSES Chunk 2: Composite + Comparative + Curonian Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

### Revision log

- **2026-05-10 (initial)** — Plan written following spec §10.2.
- **2026-05-10 (review pass)** — Five-agent review (spec-coverage / test-coverage / Curonian-canary-verifier / silent-failure / executability / simplifier+PR-style). Applied changes:

  **Blockers fixed:**
  - **Pandas pyproject prep moved BEFORE Task 4** — buried at end-of-plan would have caused Task 4 to hit ImportError. Now Task 3.5 (Pre-step) runs the dependency update.
  - **`response_pressure_gap` semantics fixed.** The `is_orphan` column is renamed to `pressure_compartment_has_no_governance` (or removed entirely), with a docstring caveat explaining that v1's `gov_count` is per-compartment, not per-Pressure. The publishable "governance gap" headline cannot ship with the original misleading semantics. Phase-2 will introduce `targeted_pressure_ids: list[str]` on `Channel` for honest per-Pressure coverage. See updated Task 7.
  - **`cross_compartment_loops` "?"-polarity branch replaced with `RuntimeError`** — fabricating a polarity classification on a "should-never-happen" branch is unacceptable for a publishable analysis. If `simple_cycles` returns a cycle whose edges no longer exist (concurrent mutation, version drift), raise loudly.

  **YAGNI simplifications applied (per simplifier reviewer):**
  - **Dropped `include_dapsi` / `include_channels` parameters from `build_composite_digraph`** — no chunk-2 caller uses them. Re-introduce in chunk 3/4 when the Topology editor needs them.
  - **Dropped `expansion="full"` mode** — no caller, no test exercising it. Strict-only.
  - **Single sort + single id-issue pass for `CrossLoop`** — eliminates the "id reassigned twice" pattern; enables `@dataclass(frozen=True)`.
  - **Dropped `truncated` tuple return from `cross_compartment_loops`** — return `list[CrossLoop]` directly; log truncation via `_log.warning(...)`. Matches chunk-1's "log warnings, return result" idiom.

  **Spec-coverage gaps addressed:**
  - **Atlantic sturgeon channels added to Curonian JSON** — spec §8.2 explicitly required AphiaID 151802 in the seed. New `bs_to_ks_sturgeon_spawners` (anadromous adult run from SE Baltic into the Klaipeda Strait) and `nl_to_bs_sturgeon_smolt` (juvenile out-migration) channels (low confidence=2, lifestage tags) added to Task 8 JSON. JSON channel count goes from 24 to 26.
  - **Canary 2 test tightened** — now also asserts a specific cycle includes BOTH `organisms_diadromous` AND `economic_telecoupling` channel types (separate test from the existing "any Reinforcing" check).
  - **`expansion="strict"` criterion clarified** — strict mode now connects synthetic ↔ DAPSI nodes that participate in within-compartment Connections OR are referenced via channel descriptions. Documentation note added explaining the trade-off (sparsely-wired compartments may miss real loops; full-fledged criterion is a chunk-2.5 follow-up).

  **Test-coverage additions (9 new tests, per test-coverage reviewer):**
  - 3-compartment cycle (A→B→C→A) detection in Task 2 (`test_cross_compartment_loops_three_compartment_cycle_detected`).
  - Unknown-archetype round-trip via `_unknown_archetype_original` in Task 4 (`test_compartment_summary_unknown_archetype_round_trips_via_original_field`).
  - `leverage_hotspots` global_stdev=0 branch returns 0.0 (not NaN) in Task 6 (`test_leverage_hotspots_zero_stdev_zscore_is_zero`, monkeypatching the imported `leverage_scores`).
  - `cross_compartment_loops` `max_length=2` inclusive boundary in Task 2 (`test_cross_compartment_loops_max_length_boundary_inclusive`).
  - `response_pressure_gap` ignores Response→non-Pressure connections in Task 7 (`test_response_pressure_gap_ignores_response_to_non_pressure`).
  - `compartment_summary(seed_curonian())` 6-row acceptance assertion in Task 10 (`test_seed_curonian_compartment_summary_acceptance`).
  - `response_pressure_gap(seed_curonian())` schema acceptance in Task 10 (`test_seed_curonian_response_pressure_gap_acceptance`).
  - Performance smoke: 10-compartment ring < 5s in Task 2 (`test_cross_compartment_loops_perf_smoke`).
  - Dangling-channel logs WARNING and skips edge in Task 1 (`test_composite_digraph_dangling_channel_logs_warning_and_skips`).

  **Other findings:**
  - **`Depends on Tasks: …` annotations added** to each task's header so subagents dispatched in isolation know prerequisites.
  - **JSON loader in `seed_curonian()` wrapped in `MultiSESIntegrityError`** for FileNotFoundError / JSONDecodeError / KeyError — matches `persistence.load` precedent.
  - **Module-level loggers in composite.py and comparative.py declared with NullHandler** — chunk 4 will add a real handler; until then, warnings are silent (acknowledged in acceptance criteria).
  - **Curonian seed has no within-compartment Connections — acknowledged caveat in acceptance criteria.** `compartment_summary` will produce `mean_leverage=0` everywhere; `leverage_hotspots` will return all-NaN z-scores. This is the documented v1 behaviour because `seed_compartment` populates Elements only. Users add Connections during real research; chunk 3 may add a sample-Connections layer to the seed.

  **Deferred to chunk-2.5 follow-up patch (non-blocking):**
  - Per-Pressure governance targeting via `Channel.targeted_pressure_ids` (the proper fix for `is_orphan`).
  - `expansion="strict"` proper "channel-endpoint-aware" criterion.
  - Splitting Tasks 1, 2, 9 implementation steps into 2-5-minute sub-steps (current sub-steps are 15-25 min — accepted because the simplifications above already reduced their size).
  - Curonian seed within-compartment Connections (will land in chunk 3 alongside the Topology editor).

**Goal:** Build the analytical layer of MosaicSES — composite digraph + cross-compartment loop detection + comparative dashboards + the Curonian Lagoon seed dataset — so a researcher can author a multi-compartment SES from a Jupyter notebook and run the priority-A (per-compartment grid) and priority-B (cross-compartment structural) analyses end-to-end.

**Architecture:** Three layers above chunk 1's data model. (1) `multises/composite.py` builds a `networkx.DiGraph` from a `MultiSES` using compartment-namespaced node ids and a synthetic-bottleneck routing pattern that lets `nx.simple_cycles` find genuine cross-compartment loops without combinatorial blowup; it carries `internal_link` edges with `polarity="+"` (multiplicative identity) so cycle-polarity arithmetic just works. (2) `multises/comparative.py` implements the priority-A grid: `compartment_summary` (vital signs), `per_compartment_grid` (long-form metric DataFrame), `leverage_hotspots` (top-N per-compartment + global z-score rank), and `response_pressure_gap` (the publishable governance-gap analysis). (3) `multises/curonian/` ships the Curonian Lagoon seed dataset (six compartments along Nemunas → Curonian Lagoon → SE Baltic, ~25 channels including the eutrophication–governance balancing loop and the diadromous-fish reinforcing loop) plus a `seed_curonian()` factory; the integration-test canary pins both loops via `cross_compartment_loops()`.

**Tech Stack:** Python 3.11+; `networkx>=3.2` (already a SESPy dep); `pandas>=2.1` (added in chunk 2); `sespy.network.centrality_metrics`, `leverage_scores`, `feedback_loops` directly reused per the spec §9.3 import allow-list; pytest for tests; matplotlib NOT used here (visualisation lands in chunk 3 with the Shiny shell).

**Companion spec:** `docs/superpowers/specs/2026-05-08-mosaicses-design.md`. Section references in this plan refer to that spec.

**Working directory throughout:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES/`. Run pytest via `micromamba run -n shiny pytest ...`. Run python via `micromamba run -n shiny python ...`.

---

## File structure overview

```
MosaicSES/
├── multises/
│   ├── composite.py              NEW — build_composite_digraph, CrossLoop,
│   │                                    cross_compartment_loops,
│   │                                    inter_compartment_metrics
│   ├── comparative.py            NEW — compartment_summary, per_compartment_grid,
│   │                                    leverage_hotspots, response_pressure_gap
│   ├── curonian/                 NEW DIRECTORY
│   │   ├── __init__.py           NEW — seed_curonian()
│   │   └── curonian_loac.json    NEW — the seed dataset
│   ├── __init__.py               MODIFIED — re-export new public API
│   └── (chunk-1 files unchanged)
└── tests/
    ├── test_composite.py         NEW — ~19 tests (9 digraph + 10 cross-loop)
    ├── test_comparative.py       NEW — ~14 tests (6 summary + 4 grid + 4 hotspots + 4 gap)
    ├── test_curonian_seed.py     NEW — 10 integration / canary tests
    └── (chunk-1 tests unchanged)
```

**Responsibility split:**

- `composite.py` knows how to *build the multilayer digraph* and *detect cross-compartment cycles*. It does not know about pandas, dashboards, or Curonian-specific content.
- `comparative.py` knows how to *summarise per-compartment results*. It uses pandas for return shapes; it does not know about cross-compartment loops directly (delegates to composite when needed).
- `curonian/` is *data + a thin factory*. The factory just deserialises JSON and returns a `MultiSES`. No analysis lives here.
- Each test file mirrors one production module + the `test_curonian_seed.py` integration that ties everything together.

**Dependencies on chunk 1 (read-only via the public API):**
- `multises.MultiSES`, `multises.Compartment`, `multises.Channel`
- `multises.archetypes.seed_compartment` (used by `seed_curonian`)
- `multises.channels.make_channel` (used by `seed_curonian`)
- `multises.persistence.save` / `persistence.load` (Curonian-seed integration tests use save→load round-trip)
- `multises.validate.validate` (Curonian-seed integration tests assert clean validation)

**Dependencies on SESPy (per spec §9.3 allow-list):**
- `sespy.network.centrality_metrics`, `leverage_scores`, `feedback_loops`, `classify_loops`, `loop_polarity`, `to_digraph`, `CENTRALITY_METRICS` (used by `comparative.py` and `composite.py`)
- `sespy.data_structure.IsaData`, `Element`, `Connection` (used to build inner DAPSI digraph segments)

---

## Task 1: composite.py — synthetic-node composite digraph builder

**Depends on Tasks:** none (chunk-1 only).

**Files:**
- Create: `MosaicSES/multises/composite.py`
- Create: `MosaicSES/tests/test_composite.py`

This task builds `build_composite_digraph(ms)` — the foundation. Every later cross-compartment analysis is a query on this digraph.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_composite.py`:

```python
"""Tests for multises.composite — build_composite_digraph."""
from __future__ import annotations

import networkx as nx
import pytest

from multises import composite, channels as ch_kb
from multises.data_structure import (
    Channel,
    Compartment,
    MultiSES,
    MultiSESMetadata,
)
from sespy.data_structure import Connection, Element, IsaData, Project, ProjectMetadata


def _project_with_one_dapsi_chain(prefix: str) -> Project:
    """Build a tiny Project with two elements and one connection."""
    e1 = Element(id=f"{prefix}_D1", label=f"{prefix} Driver", type="Drivers", confidence=3)
    e2 = Element(id=f"{prefix}_P1", label=f"{prefix} Pressure", type="Pressures", confidence=3)
    c1 = Connection(source=e1.id, target=e2.id, polarity="+", strength="medium")
    return Project(
        metadata=ProjectMetadata.new(name=f"{prefix} project"),
        isa_data=IsaData(elements=[e1, e2], connections=[c1]),
    )


@pytest.fixture
def two_compartment_ms_with_dapsi():
    """Two compartments A and B, each with 2 DAPSI nodes + 1 within-compartment edge,
    one inter-compartment nutrients channel A->B."""
    a = Compartment(id="A", label="A", archetype="river_lower",
                    project=_project_with_one_dapsi_chain("A"))
    b = Compartment(id="B", label="B", archetype="lagoon",
                    project=_project_with_one_dapsi_chain("B"))
    ch = ch_kb.make_channel(source="A", target="B", channel_type="nutrients")
    return MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=[ch])


def test_composite_digraph_contains_namespaced_dapsi_nodes(two_compartment_ms_with_dapsi):
    """Element ids are namespaced as `{compartment}::{element}`."""
    g = composite.build_composite_digraph(two_compartment_ms_with_dapsi)
    assert "A::A_D1" in g.nodes()
    assert "A::A_P1" in g.nodes()
    assert "B::B_D1" in g.nodes()


def test_composite_digraph_contains_synthetic_compartment_nodes(two_compartment_ms_with_dapsi):
    g = composite.build_composite_digraph(two_compartment_ms_with_dapsi)
    assert "A::__compartment__" in g.nodes()
    assert "B::__compartment__" in g.nodes()


def test_composite_digraph_dapsi_edges_carry_polarity_and_kind(two_compartment_ms_with_dapsi):
    g = composite.build_composite_digraph(two_compartment_ms_with_dapsi)
    edge_data = g.get_edge_data("A::A_D1", "A::A_P1")
    assert edge_data is not None
    assert edge_data["polarity"] == "+"
    assert edge_data["kind"] == "dapsi"
    assert edge_data["compartment"] == "A"


def test_composite_digraph_channel_edges_connect_synthetic_to_synthetic(two_compartment_ms_with_dapsi):
    g = composite.build_composite_digraph(two_compartment_ms_with_dapsi)
    # nutrients channel A->B should be A::__compartment__ -> B::__compartment__
    edge_data = g.get_edge_data("A::__compartment__", "B::__compartment__")
    assert edge_data is not None
    assert edge_data["kind"] == "channel"
    assert edge_data["channel_type"] == "nutrients"
    assert edge_data["polarity"] == "+"


def test_composite_digraph_internal_link_edges_pinned_to_plus(two_compartment_ms_with_dapsi):
    """Synthetic nodes connect to DAPSI nodes via internal_link edges
    with polarity='+' (multiplicative-identity for loop polarity arithmetic)."""
    g = composite.build_composite_digraph(two_compartment_ms_with_dapsi)
    # In strict mode, only DAPSI nodes that are channel endpoints get
    # internal_link edges. The nutrients channel goes A->B at the
    # compartment level, so within A every DAPSI node is potentially
    # an outgoing source, and within B every DAPSI node is potentially
    # an incoming sink. In strict mode v1 wires synthetic <-> all DAPSI
    # nodes within each compartment.
    for src, dst, data in g.edges(data=True):
        if data.get("kind") == "internal_link":
            assert data["polarity"] == "+"


def test_composite_digraph_namespacing_prevents_collisions(empty_project):
    """Two compartments with element id 'D1' should produce
    distinct composite-graph node ids 'A::D1' and 'B::D1'."""
    a_proj = Project(
        metadata=ProjectMetadata.new("A"),
        isa_data=IsaData(elements=[Element(id="D1", label="A", type="Drivers", confidence=3)],
                         connections=[]),
    )
    b_proj = Project(
        metadata=ProjectMetadata.new("B"),
        isa_data=IsaData(elements=[Element(id="D1", label="B", type="Drivers", confidence=3)],
                         connections=[]),
    )
    a = Compartment(id="A", label="A", archetype="lagoon", project=a_proj)
    b = Compartment(id="B", label="B", archetype="estuary", project=b_proj)
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=[])
    g = composite.build_composite_digraph(ms)
    assert "A::D1" in g.nodes()
    assert "B::D1" in g.nodes()
    # Same SESPy id in two compartments produces distinct composite nodes
    assert "A::D1" != "B::D1"


def test_composite_digraph_filters_by_channel_type(two_compartment_ms_with_dapsi, empty_project):
    """channel_types parameter restricts which channel types appear."""
    ms = two_compartment_ms_with_dapsi
    # Add a governance channel B -> A
    gov = ch_kb.make_channel(source="B", target="A", channel_type="governance",
                             governance_regime="MSFD")
    ms.add_channel(gov)
    g = composite.build_composite_digraph(ms, channel_types={"nutrients"})
    # nutrients edge present
    assert g.get_edge_data("A::__compartment__", "B::__compartment__") is not None
    # governance edge absent
    assert g.get_edge_data("B::__compartment__", "A::__compartment__") is None


def test_composite_digraph_empty_multises():
    ms = MultiSES.empty(name="empty")
    g = composite.build_composite_digraph(ms)
    assert g.number_of_nodes() == 0
    assert g.number_of_edges() == 0


def test_composite_digraph_dangling_channel_logs_warning_and_skips(empty_project, caplog):
    """A channel referencing an absent compartment must NOT raise from
    build_composite_digraph; it should be skipped with a WARNING log.
    `validate.validate()` is the canonical place for the user-facing
    error; the digraph builder is robust to it because callers may
    inspect partial state during editing."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    # Channel references "ghost" — no such compartment exists.
    bad_ch = ch_kb.make_channel(id="dangling", source="A", target="ghost",
                                channel_type="nutrients")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[bad_ch])
    import logging
    with caplog.at_level(logging.WARNING, logger="multises"):
        g = composite.build_composite_digraph(ms)
    assert g.get_edge_data("A::__compartment__", "ghost::__compartment__") is None
    assert any(
        "channel" in record.message and "missing compartment" in record.message
        for record in caplog.records
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pytest tests/test_composite.py -v
```

Expected: 9 FAIL with `ModuleNotFoundError: No module named 'multises.composite'`.

- [ ] **Step 3: Write `multises/composite.py`**

```python
"""Composite digraph builder + cross-compartment cycle detection.

This module turns a `MultiSES` into a `networkx.DiGraph` whose nodes are
namespaced by compartment id (`{compartment}::{element}`) plus one
synthetic node per compartment (`{compartment}::__compartment__`) that
funnels all channel-edge traffic. The synthetic-bottleneck design lets
`nx.simple_cycles` find cross-compartment cycles in the same complexity
class as within-compartment cycles — see spec §6.4 for the rationale.

Edge attributes:
- `kind ∈ {"dapsi", "channel", "internal_link"}`
- `polarity ∈ {"+", "-"}` — `internal_link` is pinned to "+" so cycle
  polarity arithmetic is unaffected by traversal through synthetic nodes.
- `compartment` (str) — for `dapsi` and `internal_link`; identifies which
  compartment the edge lives within.
- `channel_type` (str) — for `channel` only.
- `channel_id` (str) — for `channel` only.
"""
from __future__ import annotations

import logging
from typing import Iterable, Literal

import networkx as nx

from .data_structure import Channel, Compartment, MultiSES

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())


def _compartment_node(compartment_id: str) -> str:
    """Return the synthetic bottleneck node id for a compartment."""
    return f"{compartment_id}::__compartment__"


def _dapsi_node(compartment_id: str, element_id: str) -> str:
    """Return the namespaced DAPSI node id."""
    return f"{compartment_id}::{element_id}"


def build_composite_digraph(
    ms: MultiSES,
    *,
    channel_types: set[str] | None = None,
    expansion: Literal["strict", "full"] = "strict",
) -> nx.DiGraph:
    """Build the composite digraph for `ms`.

    Parameters:
      channel_types: when set, restrict to channels whose channel_type is
                    in this set (or whose `_unknown_channel_type_original`
                    is in this set, for non-destructively preserved slugs).
      expansion: "strict" (default) connects synthetic <-> only those
                    DAPSI nodes that are part of an authored within-
                    compartment Connection. "full" connects synthetic <->
                    all DAPSI nodes in the compartment. v1 default is
                    "strict" because it minimises spurious-cycle pollution.
    """
    g = nx.DiGraph()

    # Pass 1: synthetic compartment nodes (always added if any compartments
    # exist).
    for c in ms.compartments:
        g.add_node(_compartment_node(c.id),
                   kind="synthetic", compartment=c.id, archetype=c.archetype,
                   is_focal_tw=c.is_focal_tw)

    # Pass 2: DAPSI nodes + within-compartment edges + internal_link edges
    for c in ms.compartments:
        for el in c.project.isa_data.elements:
            node_id = _dapsi_node(c.id, el.id)
            g.add_node(node_id,
                       kind="dapsi", compartment=c.id,
                       label=el.label, type=el.type,
                       confidence=el.confidence)

        # Within-compartment DAPSI edges
        for conn in c.project.isa_data.connections:
            src = _dapsi_node(c.id, conn.source)
            dst = _dapsi_node(c.id, conn.target)
            if src in g.nodes() and dst in g.nodes():
                g.add_edge(src, dst,
                           kind="dapsi", compartment=c.id,
                           polarity=conn.polarity, strength=conn.strength)

        # internal_link edges between synthetic and DAPSI nodes,
        # pinned to polarity="+" (multiplicative identity for cycle
        # polarity arithmetic — see spec §6.4).
        synthetic = _compartment_node(c.id)
        if expansion == "full":
            dapsi_node_ids = [_dapsi_node(c.id, el.id) for el in c.project.isa_data.elements]
        else:  # strict
            # Only DAPSI nodes that participate in at least one
            # within-compartment Connection. This significantly
            # reduces spurious-cycle enumeration in nx.simple_cycles.
            participating: set[str] = set()
            for conn in c.project.isa_data.connections:
                participating.add(conn.source)
                participating.add(conn.target)
            dapsi_node_ids = [_dapsi_node(c.id, eid) for eid in participating
                              if _dapsi_node(c.id, eid) in g.nodes()]

        for dn in dapsi_node_ids:
            g.add_edge(synthetic, dn,
                       kind="internal_link", compartment=c.id, polarity="+")
            g.add_edge(dn, synthetic,
                       kind="internal_link", compartment=c.id, polarity="+")

    # Pass 3: channel edges (synthetic -> synthetic)
    for ch in ms.channels:
        ch_type = ch._unknown_channel_type_original or ch.channel_type
        if channel_types is not None and ch_type not in channel_types:
            continue
        src = _compartment_node(ch.source)
        dst = _compartment_node(ch.target)
        # Skip if either compartment is missing (validate would catch
        # this, but build_composite_digraph is robust to it)
        if src not in g.nodes() or dst not in g.nodes():
            _log.warning("composite: channel %r references missing compartment", ch.id)
            continue
        g.add_edge(src, dst,
                   kind="channel", channel_type=ch_type, channel_id=ch.id,
                   polarity=ch.polarity, strength=ch.strength,
                   confidence=ch.confidence, delay=ch.delay,
                   governance_regime=ch.governance_regime)

    return g
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v
```

Expected: 9 PASSED.

- [ ] **Step 5: Run full suite to confirm no regressions**

```powershell
micromamba run -n shiny pytest tests/ -q
```

Expected: 148 PASSED total (139 chunk-1 + 9 new).

- [ ] **Step 6: Commit**

```powershell
git add multises/composite.py tests/test_composite.py
git commit -m "feat(mosaicses): composite digraph builder with synthetic-bottleneck routing"
```

---

## Task 2: composite.py — CrossLoop dataclass + cross_compartment_loops()

**Depends on Tasks:** Task 1.

**Files:**
- Modify: `MosaicSES/multises/composite.py`
- Modify: `MosaicSES/tests/test_composite.py`

- [ ] **Step 1: Append failing tests to `tests/test_composite.py`**

```python
def test_cross_loop_dataclass_required_fields():
    cl = composite.CrossLoop(
        id="X-001",
        nodes=["A::__compartment__", "B::__compartment__", "A::__compartment__"],
        compartments_visited=["A", "B"],
        length=2,
        polarity_type="Reinforcing",
        channel_types_used=["nutrients"],
        polarity_string="+ +",
    )
    assert cl.id == "X-001"
    assert cl.length == 2


def test_cross_compartment_loops_finds_balancing_loop_via_governance(empty_project):
    """A→B nutrients (+) plus B→A governance (-) is a 2-compartment cycle
    with one negative edge → Balancing."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    loops = composite.cross_compartment_loops(ms)
    balancing = [l for l in loops if l.polarity_type == "Balancing"]
    assert len(balancing) >= 1
    types_used = balancing[0].channel_types_used
    assert "nutrients" in types_used
    assert "governance" in types_used


def test_cross_compartment_loops_finds_reinforcing_loop(empty_project):
    """All-positive 2-compartment cycle → Reinforcing."""
    a = Compartment(id="A", label="A", archetype="lagoon", project=empty_project)
    b = Compartment(id="B", label="B", archetype="coastal_sea", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B",
                           channel_type="organisms_diadromous", polarity="+"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="economic_telecoupling", polarity="+"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    loops = composite.cross_compartment_loops(ms)
    reinforcing = [l for l in loops if l.polarity_type == "Reinforcing"]
    assert len(reinforcing) >= 1


def test_cross_compartment_loops_filters_to_multi_compartment_only(empty_project):
    """Single-compartment cycles must NOT appear (filter: ≥ 2 compartments)."""
    a = Compartment(id="A", label="A", archetype="lagoon", project=empty_project)
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    loops = composite.cross_compartment_loops(ms)
    assert loops == []


def test_cross_compartment_loops_empty_multises():
    ms = MultiSES.empty()
    loops = composite.cross_compartment_loops(ms)
    assert loops == []


def test_cross_compartment_loops_truncated_when_max_loops_hit(empty_project, caplog):
    """If more cycles than max_loops, returns at most max_loops; logs WARNING."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    c = Compartment(id="C", label="C", archetype="coastal_sea", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
        ch_kb.make_channel(id="bc", source="B", target="C", channel_type="nutrients"),
        ch_kb.make_channel(id="cb", source="C", target="B",
                           channel_type="governance", governance_regime="MSFD"),
        ch_kb.make_channel(id="ac", source="A", target="C", channel_type="nutrients"),
        ch_kb.make_channel(id="ca", source="C", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b, c], channels=chs)
    import logging
    with caplog.at_level(logging.WARNING, logger="multises"):
        loops = composite.cross_compartment_loops(ms, max_loops=1)
    assert len(loops) == 1
    assert any("truncated" in record.message for record in caplog.records)


def test_cross_compartment_loops_polarity_string_format(empty_project):
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    loops = composite.cross_compartment_loops(ms)
    assert all(set(l.polarity_string.replace(" ", "")) <= {"+", "-"} for l in loops)


def test_cross_compartment_loops_max_length_caps_cycle_size(empty_project):
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    loops = composite.cross_compartment_loops(ms, max_length=1)
    assert loops == []


def test_cross_compartment_loops_three_compartment_cycle_detected(empty_project):
    """A→B→C→A all-positive forms a length-3 Reinforcing cycle."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    c = Compartment(id="C", label="C", archetype="coastal_sea", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="bc", source="B", target="C", channel_type="nutrients"),
        ch_kb.make_channel(id="ca", source="C", target="A",
                           channel_type="economic_telecoupling", polarity="+"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b, c], channels=chs)
    loops = composite.cross_compartment_loops(ms)
    three_compartment = [
        l for l in loops if len(set(l.compartments_visited)) == 3
    ]
    assert len(three_compartment) >= 1
    assert three_compartment[0].polarity_type == "Reinforcing"


def test_cross_compartment_loops_max_length_boundary_inclusive(empty_project):
    """`max_length` is inclusive: a length-2 cycle MUST appear with max_length=2.
    Boundary regression test against off-by-one bugs."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    loops_len_2 = composite.cross_compartment_loops(ms, max_length=2)
    assert len(loops_len_2) >= 1, "max_length=2 must include length-2 cycles"


def test_cross_compartment_loops_perf_smoke(empty_project):
    """A 10-compartment ring of nutrients channels must complete under 5
    seconds with default caps. Smoke test against pathological cycle
    enumeration; not a precise benchmark."""
    import time
    compartments = [
        Compartment(id=f"C{i}", label=f"C{i}", archetype="lagoon",
                    project=empty_project)
        for i in range(10)
    ]
    chs = [
        ch_kb.make_channel(id=f"c{i}_to_c{(i+1) % 10}",
                           source=f"C{i}", target=f"C{(i + 1) % 10}",
                           channel_type="nutrients")
        for i in range(10)
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=compartments, channels=chs)
    t0 = time.perf_counter()
    composite.cross_compartment_loops(ms)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"10-compartment ring took {elapsed:.2f}s (cap 5.0s)"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v -k "cross_loop or cross_compartment_loops"
```

Expected: 10 FAIL with `AttributeError: module 'multises.composite' has no attribute 'CrossLoop'`.

- [ ] **Step 3: Append the `CrossLoop` dataclass and `cross_compartment_loops()` to `multises/composite.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CrossLoop:
    """One cross-compartment cycle.

    Attributes:
      id: stable identifier ("X-001", "X-002", ...) assigned in
          ranking order (shortest first, then most compartments).
      nodes: composite-graph node ids in cycle order, plus a
          repeated first node at the end to close the loop.
      compartments_visited: ordered list of compartment ids the cycle
          touches (may include repeats; len(set(...)) >= 2 by filter).
      length: number of distinct edges in the cycle.
      polarity_type: "Reinforcing" or "Balancing" per SESPy convention
          (even number of negative edges → Reinforcing; odd → Balancing).
      channel_types_used: unique channel_types involved in the cycle.
      polarity_string: e.g. "+ + - +" — for inspection / display.
    """
    id: str
    nodes: list[str]
    compartments_visited: list[str]
    length: int
    polarity_type: str
    channel_types_used: list[str]
    polarity_string: str


def cross_compartment_loops(
    ms: MultiSES,
    *,
    max_length: int = 12,
    max_loops: int = 50,
) -> list[CrossLoop]:
    """Detect cycles in the composite digraph that touch ≥ 2 compartments.

    Returns a list of CrossLoop objects, ranked shortest-first then
    most-compartments-touched. Within-compartment cycles (single
    compartment touched) are filtered out — those are handled
    separately by SESPy's per-compartment `feedback_loops()`.

    If more than `max_loops` cycles are available, only `max_loops` are
    returned and a `_log.warning(...)` is emitted naming the cap. The UI
    can detect truncation by checking `len(result) == max_loops` and
    re-querying with a higher cap if needed.

    Cycle polarity classification mirrors SESPy's `loop_polarity`:
    even number of negative edges → "Reinforcing"; odd → "Balancing".

    Raises RuntimeError if `nx.simple_cycles` returns a cycle whose
    edges no longer exist in the graph (concurrent mutation; should
    never happen in single-threaded use).
    """
    g = build_composite_digraph(ms)
    if g.number_of_nodes() == 0:
        return []

    raw_loops: list[CrossLoop] = []

    for cycle in nx.simple_cycles(g):
        if len(cycle) > max_length:
            continue

        compartments_in_cycle: list[str] = []
        for node in cycle:
            data = g.nodes[node]
            if "compartment" in data:
                compartments_in_cycle.append(data["compartment"])

        if len(set(compartments_in_cycle)) < 2:
            continue

        n_negative = 0
        polarity_chars: list[str] = []
        channel_types: set[str] = set()
        for i in range(len(cycle)):
            src = cycle[i]
            dst = cycle[(i + 1) % len(cycle)]
            edge = g.get_edge_data(src, dst)
            if edge is None:
                # Invariant violation: nx.simple_cycles returned a cycle
                # whose edges don't exist in the graph. Cannot fabricate
                # a polarity classification on incomplete data.
                raise RuntimeError(
                    f"composite: cycle returned by simple_cycles has "
                    f"missing edge {src} -> {dst}; graph corrupted or "
                    f"concurrently mutated"
                )
            pol = edge.get("polarity", "+")
            polarity_chars.append(pol)
            if pol == "-":
                n_negative += 1
            if edge.get("kind") == "channel":
                channel_types.add(edge.get("channel_type", "?"))

        polarity_type = "Reinforcing" if n_negative % 2 == 0 else "Balancing"

        if len(raw_loops) >= max_loops:
            _log.warning(
                "cross_compartment_loops: truncated at %d cycles; "
                "widen max_loops for completeness", max_loops
            )
            break

        # id assigned post-sort below (single-pass; CrossLoop is frozen).
        raw_loops.append(CrossLoop(
            id="",  # placeholder, overwritten in the post-sort pass
            nodes=list(cycle) + [cycle[0]],
            compartments_visited=compartments_in_cycle,
            length=len(cycle),
            polarity_type=polarity_type,
            channel_types_used=sorted(channel_types),
            polarity_string=" ".join(polarity_chars),
        ))

    # Rank: shortest first, then most-compartments-touched (descending)
    raw_loops.sort(key=lambda l: (l.length, -len(set(l.compartments_visited))))

    # Single id-issue pass after sorting. Because CrossLoop is frozen,
    # we replace each entry with a copy carrying the assigned id.
    from dataclasses import replace as _replace
    return [_replace(loop, id=f"X-{i:03d}")
            for i, loop in enumerate(raw_loops, start=1)]
```

Update the import block at the top of `composite.py` to include the dataclass import:

```python
from dataclasses import dataclass
```

(If `dataclass` isn't already imported, add it. The Task-1 file may have already had it from elsewhere; confirm by reading the current `composite.py` and only insert if missing.)

- [ ] **Step 4: Run tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v
```

Expected: 19 PASSED (9 from Task 1 + 10 new).

Then full suite:

```powershell
micromamba run -n shiny pytest tests/ -q
```

Expected: 158 PASSED total (139 chunk-1 baseline + 19 new from Tasks 1+2).

- [ ] **Step 5: Commit**

```powershell
git add multises/composite.py tests/test_composite.py
git commit -m "feat(mosaicses): cross_compartment_loops with polarity composition + truncation logging"
```

---

## Task 3: composite.py — inter_compartment_metrics()

**Depends on Tasks:** Task 1.

**Files:**
- Modify: `MosaicSES/multises/composite.py`
- Modify: `MosaicSES/tests/test_composite.py`

`inter_compartment_metrics` returns the compartment-level meta-graph metrics — each compartment is one node, channels become edges; betweenness centrality identifies bridge compartments (estuaries usually win).

- [ ] **Step 1: Append failing tests**

```python
def test_inter_compartment_metrics_returns_dict_per_compartment(empty_project):
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    c = Compartment(id="C", label="C", archetype="coastal_sea", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="bc", source="B", target="C", channel_type="nutrients"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b, c], channels=chs)
    metrics = composite.inter_compartment_metrics(ms)
    assert "A" in metrics
    assert "B" in metrics
    assert "C" in metrics


def test_inter_compartment_metrics_bridge_compartment_has_highest_betweenness(empty_project):
    """In A->B->C, B is the bridge — its betweenness should be highest."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    c = Compartment(id="C", label="C", archetype="coastal_sea", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="bc", source="B", target="C", channel_type="nutrients"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b, c], channels=chs)
    metrics = composite.inter_compartment_metrics(ms)
    assert metrics["B"]["betweenness"] >= metrics["A"]["betweenness"]
    assert metrics["B"]["betweenness"] >= metrics["C"]["betweenness"]


def test_inter_compartment_metrics_isolated_compartment(empty_project):
    """A compartment with no channels has zero in-/out-degree."""
    isolated = Compartment(id="I", label="I", archetype="lagoon", project=empty_project)
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[isolated], channels=[])
    metrics = composite.inter_compartment_metrics(ms)
    assert metrics["I"]["channel_in_degree"] == 0
    assert metrics["I"]["channel_out_degree"] == 0
    assert metrics["I"]["betweenness"] == 0.0


def test_inter_compartment_metrics_records_channel_types(empty_project):
    """Each compartment metrics dict reports incoming + outgoing channel types."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab_water", source="A", target="B", channel_type="water_discharge"),
        ch_kb.make_channel(id="ab_nut", source="A", target="B", channel_type="nutrients"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)
    metrics = composite.inter_compartment_metrics(ms)
    assert set(metrics["A"]["outgoing_channel_types"]) == {"water_discharge", "nutrients"}
    assert set(metrics["B"]["incoming_channel_types"]) == {"water_discharge", "nutrients"}
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v -k inter_compartment_metrics
```

Expected: 4 FAIL with `AttributeError: module 'multises.composite' has no attribute 'inter_compartment_metrics'`.

- [ ] **Step 3: Append `inter_compartment_metrics()` to `multises/composite.py`**

```python
def inter_compartment_metrics(ms: MultiSES) -> dict[str, dict]:
    """Compute the compartment-level meta-graph metrics.

    The meta-graph treats each compartment as one node and each channel
    as one edge. Betweenness centrality identifies bridge compartments —
    structural bottlenecks of the LOAC continuum (estuaries usually win).

    Returns a dict keyed by compartment id; each value has:
      - channel_in_degree (int)
      - channel_out_degree (int)
      - betweenness (float, 0..1) — meta-graph betweenness centrality
      - incoming_channel_types (list[str], sorted)
      - outgoing_channel_types (list[str], sorted)
    """
    meta = nx.DiGraph()
    for c in ms.compartments:
        meta.add_node(c.id, archetype=c.archetype, is_focal_tw=c.is_focal_tw)
    for ch in ms.channels:
        if meta.has_node(ch.source) and meta.has_node(ch.target):
            meta.add_edge(ch.source, ch.target,
                          channel_id=ch.id, channel_type=ch.channel_type)

    if meta.number_of_nodes() == 0:
        return {}

    try:
        betweenness = nx.betweenness_centrality(meta, normalized=True)
    except Exception:
        betweenness = {n: 0.0 for n in meta.nodes()}

    out: dict[str, dict] = {}
    for cmp_id in meta.nodes():
        in_types = sorted({
            data["channel_type"] for _, _, data in meta.in_edges(cmp_id, data=True)
        })
        out_types = sorted({
            data["channel_type"] for _, _, data in meta.out_edges(cmp_id, data=True)
        })
        out[cmp_id] = {
            "channel_in_degree": meta.in_degree(cmp_id),
            "channel_out_degree": meta.out_degree(cmp_id),
            "betweenness": float(betweenness.get(cmp_id, 0.0)),
            "incoming_channel_types": in_types,
            "outgoing_channel_types": out_types,
        }
    return out
```

- [ ] **Step 4: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: test_composite.py = 22 PASSED (18 + 4 new); full suite = 161+ PASSED.

- [ ] **Step 5: Commit**

```powershell
git add multises/composite.py tests/test_composite.py
git commit -m "feat(mosaicses): inter_compartment_metrics for bridge-compartment identification"
```

---

## Task 3.5 — Pre-step: pandas dependency

**Depends on Tasks:** none.

**Files:**
- Modify: `MosaicSES/pyproject.toml`

This MUST run before Task 4 — `comparative.py` imports `pandas as pd` and tests will fail with ImportError without it.

- [ ] **Step 1: Add `pandas>=2.1` to `pyproject.toml`**

Edit the `dependencies` list in `MosaicSES/pyproject.toml`:

```toml
dependencies = [
    "sespy",
    "pandas>=2.1",
    "networkx>=3.2",
]
```

(`networkx` is added for `composite.py`. It's a SESPy runtime dep but declaring it explicitly here makes MosaicSES self-describing.)

- [ ] **Step 2: Re-install editable**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pip install -e .
```

Expected: `Successfully installed mosaic-ses-0.1.0` (or `Requirement already satisfied`). pandas + networkx already exist in the `shiny` env; this just registers them as MosaicSES dependencies.

- [ ] **Step 3: Verify pandas + networkx import in env**

```powershell
micromamba run -n shiny python -c "import pandas as pd; import networkx as nx; print(f'pandas {pd.__version__}, networkx {nx.__version__}')"
```

Expected: prints version numbers, no ImportError.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml
git commit -m "chore(mosaicses): declare pandas + networkx dependencies for chunk 2"
```

---

## Task 4: comparative.py — compartment_summary()

**Depends on Tasks:** Task 3.5 (pandas).

**Files:**
- Create: `MosaicSES/multises/comparative.py`
- Create: `MosaicSES/tests/test_comparative.py`

This is the priority-A "vital signs" table — one row per compartment with archetype, element/connection counts, mean leverage, and dominant pressure count.

- [ ] **Step 1: Write `tests/test_comparative.py`**

```python
"""Tests for multises.comparative."""
from __future__ import annotations

import pandas as pd
import pytest

from multises import comparative, channels as ch_kb
from multises.archetypes import seed_compartment
from multises.data_structure import (
    Channel, Compartment, MultiSES, MultiSESMetadata,
)


@pytest.fixture
def two_seeded_compartments():
    """Two compartments seeded with archetype defaults — has DAPSI content."""
    rl = seed_compartment("river_lower", label="RL", id="rl")
    lg = seed_compartment("lagoon", label="LG", id="lg")
    chs = [
        ch_kb.make_channel(id="rl_to_lg_water", source="rl", target="lg",
                           channel_type="water_discharge"),
        ch_kb.make_channel(id="rl_to_lg_nut", source="rl", target="lg",
                           channel_type="nutrients"),
    ]
    return MultiSES(metadata=MultiSESMetadata(), compartments=[rl, lg], channels=chs)


def test_compartment_summary_returns_dataframe(two_seeded_compartments):
    df = comparative.compartment_summary(two_seeded_compartments)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "compartment_id" in df.columns
    assert "archetype" in df.columns
    assert "element_count" in df.columns
    assert "connection_count" in df.columns


def test_compartment_summary_archetype_is_correct(two_seeded_compartments):
    df = comparative.compartment_summary(two_seeded_compartments)
    rl_row = df[df["compartment_id"] == "rl"].iloc[0]
    assert rl_row["archetype"] == "river_lower"
    lg_row = df[df["compartment_id"] == "lg"].iloc[0]
    assert lg_row["archetype"] == "lagoon"


def test_compartment_summary_element_count_matches_isa_data(two_seeded_compartments):
    df = comparative.compartment_summary(two_seeded_compartments)
    for _, row in df.iterrows():
        cmp = two_seeded_compartments.compartment(row["compartment_id"])
        assert row["element_count"] == len(cmp.project.isa_data.elements)


def test_compartment_summary_includes_is_focal_tw(two_seeded_compartments):
    df = comparative.compartment_summary(two_seeded_compartments)
    assert "is_focal_tw" in df.columns
    rl_row = df[df["compartment_id"] == "rl"].iloc[0]
    assert rl_row["is_focal_tw"] is False
    lg_row = df[df["compartment_id"] == "lg"].iloc[0]
    assert lg_row["is_focal_tw"] is True


def test_compartment_summary_empty_multises():
    df = comparative.compartment_summary(MultiSES.empty())
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


def test_compartment_summary_unknown_archetype_round_trips_via_original_field(empty_project):
    """A compartment whose archetype string is unknown (loaded from a
    forward-compat JSON via persistence.load) must still appear in
    compartment_summary, with its original archetype string preserved
    via the `_unknown_archetype_original` field semantics."""
    # Construct a compartment that has been "round-tripped" — archetype
    # field already validated to a known slug, but persistence captured
    # the original unknown string.
    c = Compartment(id="C1", label="C", archetype="lagoon", project=empty_project)
    object.__setattr__(c, "_unknown_archetype_original", "lagoon_brackish_v2")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[c], channels=[])
    df = comparative.compartment_summary(ms)
    # The summary should display the round-tripped original string when
    # present (so the publishable table doesn't lie about provenance).
    assert "lagoon_brackish_v2" in df["archetype"].values
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v
```

Expected: 6 FAIL with `ModuleNotFoundError: No module named 'multises.comparative'`.

- [ ] **Step 3: Write `multises/comparative.py`**

```python
"""Priority-A grid: per-compartment analyses presented side-by-side.

Reuses SESPy's per-compartment graph algorithms (centrality_metrics,
leverage_scores) and aggregates results across compartments into
DataFrames suitable for heatmaps, hotspot tables, and the
response-pressure-gap publishable view (spec §6.5).
"""
from __future__ import annotations

import logging

import pandas as pd

from sespy.network import (
    centrality_metrics,
    leverage_scores,
)

from .data_structure import MultiSES

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())


def compartment_summary(ms: MultiSES) -> pd.DataFrame:
    """One row per compartment — vital signs for the dashboard landing page.

    Columns:
      - compartment_id, label, archetype, is_focal_tw
      - element_count, connection_count
      - mean_leverage (float; from sespy.network.leverage_scores; 0 if empty)
      - top_leverage_label (str; element with highest leverage; "" if empty)
      - dominant_pressure_count (int; # of Pressure-type elements)
    """
    rows: list[dict] = []
    for c in ms.compartments:
        elements = c.project.isa_data.elements
        connections = c.project.isa_data.connections
        leverages = leverage_scores(c.project.isa_data)
        if leverages:
            top_id = max(leverages, key=leverages.get)
            top_label = next(
                (e.label for e in elements if e.id == top_id), top_id
            )
            mean_lev = sum(leverages.values()) / len(leverages)
        else:
            top_label = ""
            mean_lev = 0.0
        pressure_count = sum(1 for e in elements if e.type == "Pressures")
        rows.append({
            "compartment_id": c.id,
            "label": c.label,
            "archetype": c.archetype,
            "is_focal_tw": c.is_focal_tw,
            "element_count": len(elements),
            "connection_count": len(connections),
            "mean_leverage": mean_lev,
            "top_leverage_label": top_label,
            "dominant_pressure_count": pressure_count,
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: test_comparative.py = 6 PASSED; full suite = 164 PASSED (158 + 6).

- [ ] **Step 5: Commit**

```powershell
git add multises/comparative.py tests/test_comparative.py
git commit -m "feat(mosaicses): comparative.compartment_summary vital-signs DataFrame"
```

---

## Task 5: comparative.py — per_compartment_grid()

**Depends on Tasks:** Task 4.

**Files:**
- Modify: `MosaicSES/multises/comparative.py`
- Modify: `MosaicSES/tests/test_comparative.py`

Long-format DataFrame: one row per (compartment_id, element_id, metric, value). Suitable for heatmaps and faceted plots.

- [ ] **Step 1: Append failing tests**

```python
def test_per_compartment_grid_long_format(two_seeded_compartments):
    df = comparative.per_compartment_grid(two_seeded_compartments)
    expected_cols = {"compartment_id", "element_id", "element_label",
                     "element_type", "metric", "value"}
    assert expected_cols.issubset(set(df.columns))


def test_per_compartment_grid_includes_default_centrality_metrics(two_seeded_compartments):
    df = comparative.per_compartment_grid(two_seeded_compartments)
    metrics_present = set(df["metric"].unique())
    # At minimum, the default sespy CENTRALITY_METRICS should be present
    assert "betweenness" in metrics_present
    assert "pagerank" in metrics_present


def test_per_compartment_grid_one_row_per_compartment_element_metric(two_seeded_compartments):
    df = comparative.per_compartment_grid(two_seeded_compartments)
    n_compartments = len(two_seeded_compartments.compartments)
    n_metrics = df["metric"].nunique()
    expected_total = sum(
        len(c.project.isa_data.elements)
        for c in two_seeded_compartments.compartments
    ) * n_metrics
    assert len(df) == expected_total


def test_per_compartment_grid_value_is_numeric(two_seeded_compartments):
    df = comparative.per_compartment_grid(two_seeded_compartments)
    assert pd.api.types.is_numeric_dtype(df["value"])
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v -k per_compartment_grid
```

Expected: 4 FAIL.

- [ ] **Step 3: Append `per_compartment_grid()` to `multises/comparative.py`**

Add an import at the top:

```python
from sespy.network import (
    CENTRALITY_METRICS,
    centrality_metrics,
    leverage_scores,
)
```

(Replace the existing import block with this expanded one.)

Append the function:

```python
def per_compartment_grid(
    ms: MultiSES,
    *,
    metrics: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Long-format DataFrame: one row per (compartment_id, element_id, metric, value).

    Parameters:
      metrics: which centrality metrics to compute. Defaults to
               sespy.network.CENTRALITY_METRICS (all seven).

    The long format is best for plotting heatmaps and facetted bar charts;
    callers can `.pivot_table(...)` to a wide form if needed.
    """
    if metrics is None:
        metrics = CENTRALITY_METRICS

    rows: list[dict] = []
    for c in ms.compartments:
        cm = centrality_metrics(c.project.isa_data)
        elements = {e.id: e for e in c.project.isa_data.elements}
        for metric_name in metrics:
            metric_values = cm.get(metric_name, {})
            for elem_id, value in metric_values.items():
                el = elements.get(elem_id)
                rows.append({
                    "compartment_id": c.id,
                    "element_id": elem_id,
                    "element_label": el.label if el else elem_id,
                    "element_type": el.type if el else "",
                    "metric": metric_name,
                    "value": float(value),
                })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: test_comparative.py = 9 PASSED; full suite = 170+ PASSED.

- [ ] **Step 5: Commit**

```powershell
git add multises/comparative.py tests/test_comparative.py
git commit -m "feat(mosaicses): comparative.per_compartment_grid long-format DataFrame"
```

---

## Task 6: comparative.py — leverage_hotspots()

**Depends on Tasks:** Task 5.

**Files:**
- Modify: `MosaicSES/multises/comparative.py`
- Modify: `MosaicSES/tests/test_comparative.py`

Top-N per compartment + global rank z-score across all compartments.

- [ ] **Step 1: Append failing tests**

```python
def test_leverage_hotspots_returns_per_compartment_top_n(two_seeded_compartments):
    df = comparative.leverage_hotspots(two_seeded_compartments, top_n_per_compartment=3)
    assert "compartment_id" in df.columns
    assert "element_id" in df.columns
    assert "leverage" in df.columns
    assert "global_rank_zscore" in df.columns
    # At most top_n_per_compartment rows per compartment
    counts = df.groupby("compartment_id").size()
    assert all(counts <= 3)


def test_leverage_hotspots_global_rank_zscore_present(two_seeded_compartments):
    df = comparative.leverage_hotspots(two_seeded_compartments)
    # zscore should be a numeric column
    assert pd.api.types.is_numeric_dtype(df["global_rank_zscore"])


def test_leverage_hotspots_empty_multises():
    df = comparative.leverage_hotspots(MultiSES.empty())
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


def test_leverage_hotspots_zero_stdev_zscore_is_zero(two_seeded_compartments, monkeypatch):
    """When all leverage values are equal across the global pool (stdev=0),
    `global_rank_zscore` must be 0.0 for every row — never NaN, never inf.
    Defensive test: numpy/pandas sometimes propagates NaN in this case
    via `(x - mean) / 0`. The implementation uses a `stdev > 0` guard."""
    def constant_leverage(isa_data):
        return {el.id: 0.5 for el in isa_data.elements}

    monkeypatch.setattr(comparative, "leverage_scores", constant_leverage)
    df = comparative.leverage_hotspots(two_seeded_compartments)
    assert (df["global_rank_zscore"] == 0.0).all()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v -k leverage_hotspots
```

Expected: 4 FAIL (3 leverage_hotspots tests + 1 zero-stdev guard test).

- [ ] **Step 3: Append `leverage_hotspots()` to `multises/comparative.py`**

```python
def leverage_hotspots(
    ms: MultiSES,
    *,
    top_n_per_compartment: int = 5,
) -> pd.DataFrame:
    """Top-N elements by leverage, per compartment, with global-rank z-score.

    The global z-score normalises each element's leverage against the
    distribution of leverages across ALL compartments combined — so a
    cross-compartment "which is the most leveraged element overall?"
    question has a defensible answer.

    Returns columns:
      compartment_id, element_id, element_label, element_type,
      leverage, global_rank_zscore.
    """
    rows: list[dict] = []
    all_leverages: list[float] = []

    # Pass 1: collect all leverages across all compartments to compute
    # a global mean / stdev for the z-score.
    cmp_leverages: dict[str, dict[str, float]] = {}
    for c in ms.compartments:
        lev = leverage_scores(c.project.isa_data)
        cmp_leverages[c.id] = lev
        all_leverages.extend(lev.values())

    if not all_leverages:
        return pd.DataFrame(
            columns=[
                "compartment_id", "element_id", "element_label",
                "element_type", "leverage", "global_rank_zscore",
            ]
        )

    global_mean = sum(all_leverages) / len(all_leverages)
    var = sum((x - global_mean) ** 2 for x in all_leverages) / len(all_leverages)
    global_stdev = var ** 0.5

    # Pass 2: rank per compartment, attach global z-score.
    for c in ms.compartments:
        elements = {e.id: e for e in c.project.isa_data.elements}
        lev = cmp_leverages.get(c.id, {})
        ranked = sorted(lev.items(), key=lambda kv: kv[1], reverse=True)[:top_n_per_compartment]
        for elem_id, leverage in ranked:
            el = elements.get(elem_id)
            zscore = (
                (leverage - global_mean) / global_stdev
                if global_stdev > 0 else 0.0
            )
            rows.append({
                "compartment_id": c.id,
                "element_id": elem_id,
                "element_label": el.label if el else elem_id,
                "element_type": el.type if el else "",
                "leverage": float(leverage),
                "global_rank_zscore": float(zscore),
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: test_comparative.py grows by 4 (was 9 from Tasks 4+5; now 13 with the new zero-stdev test); full suite advances accordingly.

- [ ] **Step 5: Commit**

```powershell
git add multises/comparative.py tests/test_comparative.py
git commit -m "feat(mosaicses): comparative.leverage_hotspots with global z-score rank"
```

---

## Task 7: comparative.py — response_pressure_gap()

**Depends on Tasks:** Task 4.

**Files:**
- Modify: `MosaicSES/multises/comparative.py`
- Modify: `MosaicSES/tests/test_comparative.py`

The publishable view: for each Pressure across all compartments, count the Responses targeting it (within the compartment + via governance channels into the compartment). Surfaces orphan Pressures.

- [ ] **Step 1: Append failing tests**

```python
def test_response_pressure_gap_returns_dataframe_with_required_columns(two_seeded_compartments):
    df = comparative.response_pressure_gap(two_seeded_compartments)
    assert "compartment_id" in df.columns
    assert "pressure_id" in df.columns
    assert "pressure_label" in df.columns
    assert "within_compartment_response_count" in df.columns
    assert "incoming_governance_channel_count" in df.columns
    assert "pressure_compartment_has_no_governance" in df.columns


def test_response_pressure_gap_lagoon_pressures_present(two_seeded_compartments):
    """seed_compartment('lagoon', ...) creates Pressure elements; they must
    appear in the gap DataFrame."""
    df = comparative.response_pressure_gap(two_seeded_compartments)
    lagoon_rows = df[df["compartment_id"] == "lg"]
    assert len(lagoon_rows) > 0
    labels = set(lagoon_rows["pressure_label"])
    assert "Eutrophication" in labels


def test_response_pressure_gap_no_governance_compartment_flagged(two_seeded_compartments):
    """Compartments with no incoming governance channels have the
    `pressure_compartment_has_no_governance` flag True for every Pressure."""
    df = comparative.response_pressure_gap(two_seeded_compartments)
    # The two_seeded_compartments fixture has no governance channels
    assert df["pressure_compartment_has_no_governance"].all()


def test_response_pressure_gap_governance_channel_clears_no_governance_flag(empty_project):
    """A governance channel into a compartment sets
    incoming_governance_channel_count >= 1 and clears the no-governance flag
    for that compartment's Pressures."""
    rl = seed_compartment("river_lower", label="RL", id="rl")
    lg = seed_compartment("lagoon", label="LG", id="lg")
    gov = ch_kb.make_channel(id="rl_to_lg_gov", source="rl", target="lg",
                             channel_type="governance", governance_regime="WFD")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[rl, lg], channels=[gov])
    df = comparative.response_pressure_gap(ms)
    lagoon_rows = df[df["compartment_id"] == "lg"]
    assert all(lagoon_rows["incoming_governance_channel_count"] >= 1)
    assert not lagoon_rows["pressure_compartment_has_no_governance"].any()


def test_response_pressure_gap_ignores_response_to_non_pressure(empty_project):
    """A Response→Driver Connection must NOT increment any pressure's
    within_compartment_response_count."""
    from sespy.data_structure import Element, IsaData, Project, ProjectMetadata
    from sespy.data_structure import Connection as SConn
    # Build a hand-crafted Project: one Response, one Driver, one Pressure,
    # with Response → Driver (not → Pressure)
    elements = [
        Element(id="R1", label="Response", type="Responses", confidence=3),
        Element(id="D1", label="Driver", type="Drivers", confidence=3),
        Element(id="P1", label="Pressure", type="Pressures", confidence=3),
    ]
    connections = [
        SConn(source="R1", target="D1", polarity="-", strength="medium"),
    ]
    proj = Project(
        metadata=ProjectMetadata.new("test"),
        isa_data=IsaData(elements=elements, connections=connections),
    )
    a = Compartment(id="A", label="A", archetype="lagoon", project=proj)
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    df = comparative.response_pressure_gap(ms)
    # Single Pressure row; within_compartment_response_count must be 0
    assert len(df) == 1
    assert df.iloc[0]["within_compartment_response_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v -k response_pressure_gap
```

Expected: 4 FAIL.

- [ ] **Step 3: Append `response_pressure_gap()` to `multises/comparative.py`**

```python
def response_pressure_gap(ms: MultiSES) -> pd.DataFrame:
    """For each Pressure element, count within-compartment Responses
    targeting it AND incoming governance channels at the compartment level.

    **v1 semantics caveat (spec §6.5).** v1's `incoming_governance_channel_count`
    is the *total* governance channels arriving at the Pressure's
    compartment — NOT a per-Pressure count of governance channels that
    actually target this Pressure. A single MSFD channel into a lagoon
    will register `incoming_governance_channel_count=1` for every
    Pressure in that lagoon, even if MSFD targets only nutrients (not
    plastics, fishing pressure, etc.).

    Therefore v1 does NOT emit a single `is_orphan` boolean — that
    column would be misleading as a "publishable governance gap". Phase-2
    will add `Channel.targeted_pressure_ids: list[str] | None` so per-
    Pressure targeting can be honestly computed; until then, the caller
    can filter on the two count columns directly with appropriate caveats.

    Columns:
      compartment_id, pressure_id, pressure_label,
      within_compartment_response_count,
      incoming_governance_channel_count,
      pressure_compartment_has_no_governance (bool — true iff
        `incoming_governance_channel_count == 0`; this IS per-compartment
        coverage, not per-Pressure targeting).
    """
    # Pre-compute incoming governance channel counts per compartment
    incoming_governance_counts: dict[str, int] = {c.id: 0 for c in ms.compartments}
    for ch in ms.channels:
        if ch.channel_type == "governance" and ch.target in incoming_governance_counts:
            incoming_governance_counts[ch.target] += 1

    rows: list[dict] = []
    for c in ms.compartments:
        elements = c.project.isa_data.elements
        connections = c.project.isa_data.connections
        # Responses-targeting-Pressures via within-compartment Connections
        response_to_pressure: dict[str, int] = {}
        response_ids = {e.id for e in elements if e.type == "Responses"}
        for conn in connections:
            if conn.source in response_ids:
                target_el = next((e for e in elements if e.id == conn.target), None)
                if target_el and target_el.type == "Pressures":
                    response_to_pressure[conn.target] = (
                        response_to_pressure.get(conn.target, 0) + 1
                    )
        gov_count = incoming_governance_counts[c.id]
        for el in elements:
            if el.type != "Pressures":
                continue
            within = response_to_pressure.get(el.id, 0)
            rows.append({
                "compartment_id": c.id,
                "pressure_id": el.id,
                "pressure_label": el.label,
                "within_compartment_response_count": within,
                "incoming_governance_channel_count": gov_count,
                "pressure_compartment_has_no_governance": (gov_count == 0),
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_comparative.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: test_comparative.py = 16 PASSED; full suite = 177+ PASSED.

- [ ] **Step 5: Commit**

```powershell
git add multises/comparative.py tests/test_comparative.py
git commit -m "feat(mosaicses): comparative.response_pressure_gap orphan-Pressure analysis"
```

---

## Task 8: Curonian seed dataset — `curonian_loac.json`

**Depends on Tasks:** none (chunk-1 only).

**Files:**
- Create: `MosaicSES/multises/curonian/__init__.py` (placeholder; Task 9 fills it in)
- Create: `MosaicSES/multises/curonian/curonian_loac.json`

This task ships the Curonian seed dataset as a JSON file. v1 ships a *minimal but correct* seed: 6 compartments, ~5-10 elements each (mostly seeded from archetype defaults via Task 9's `seed_curonian()`), ~10-15 channels including the headline eutrophication–governance balancing loop and the diadromous reinforcing loop.

Because the JSON is large and most of the DAPSI content is best generated programmatically by `seed_curonian()` calling `seed_compartment` for each archetype, the JSON file in this task contains ONLY the channel definitions and the per-compartment overrides (not a flat Project per compartment). Task 9 defines a small loader contract that interprets this JSON.

- [ ] **Step 1: Create the directory and a placeholder `__init__.py`**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
New-Item -ItemType Directory -Force -Path "multises/curonian"
```

Then write `multises/curonian/__init__.py` with a single comment:

```python
"""Curonian Lagoon seed dataset — Task 9 fills in `seed_curonian()`."""
```

- [ ] **Step 2: Write `multises/curonian/curonian_loac.json`**

```json
{
  "metadata": {
    "name": "Curonian Lagoon LOAC seed",
    "description": "v1 seed dataset for the Nemunas->Delta->Curonian Lagoon->Klaipeda Strait->SE Baltic system. Default DAPSI content comes from archetype defaults (confidence=2); channels and a few archetype-specific overrides are listed here.",
    "da_site": "Curonian Lagoon",
    "river_basin": "Nemunas",
    "regional_sea": "baltic_sea",
    "focal_issue": "Eutrophication-governance feedback loop",
    "spatial_scale": "International",
    "temporal_scale": "Decadal"
  },
  "compartments": [
    {"id": "nemunas_upper", "label": "Upper Nemunas (LT/BY transboundary)", "archetype": "river_upper"},
    {"id": "nemunas_lower", "label": "Lower Nemunas (Kaunas - Rusne)", "archetype": "river_lower"},
    {"id": "nemunas_delta", "label": "Nemunas Delta (Ramsar wetland)", "archetype": "delta"},
    {"id": "curonian_lagoon", "label": "Curonian Lagoon (~1584 km^2, oligohaline)", "archetype": "lagoon"},
    {"id": "klaipeda_strait", "label": "Klaipeda Strait (port + salinity gradient)", "archetype": "estuary"},
    {"id": "baltic_se", "label": "SE Baltic coastal sea (ICES SD 26)", "archetype": "coastal_sea"}
  ],
  "channels": [
    {"id": "nu_to_nl_water", "source": "nemunas_upper", "target": "nemunas_lower", "channel_type": "water_discharge", "polarity": "+", "strength": "strong", "confidence": 5, "delay": "immediate"},
    {"id": "nu_to_nl_nut", "source": "nemunas_upper", "target": "nemunas_lower", "channel_type": "nutrients", "polarity": "+", "strength": "strong", "confidence": 4, "delay": "short"},
    {"id": "nu_to_nl_sed", "source": "nemunas_upper", "target": "nemunas_lower", "channel_type": "sediment", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "medium"},

    {"id": "nl_to_nd_water", "source": "nemunas_lower", "target": "nemunas_delta", "channel_type": "water_discharge", "polarity": "+", "strength": "strong", "confidence": 5, "delay": "immediate"},
    {"id": "nl_to_nd_nut", "source": "nemunas_lower", "target": "nemunas_delta", "channel_type": "nutrients", "polarity": "+", "strength": "strong", "confidence": 4, "delay": "short"},
    {"id": "nl_to_nd_pol", "source": "nemunas_lower", "target": "nemunas_delta", "channel_type": "pollutants", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "long"},

    {"id": "nd_to_cl_water", "source": "nemunas_delta", "target": "curonian_lagoon", "channel_type": "water_discharge", "polarity": "+", "strength": "strong", "confidence": 5, "delay": "immediate"},
    {"id": "nd_to_cl_nut", "source": "nemunas_delta", "target": "curonian_lagoon", "channel_type": "nutrients", "polarity": "+", "strength": "strong", "confidence": 4, "delay": "short"},
    {"id": "nd_to_cl_sed", "source": "nemunas_delta", "target": "curonian_lagoon", "channel_type": "sediment", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "medium"},

    {"id": "cl_to_ks_water", "source": "curonian_lagoon", "target": "klaipeda_strait", "channel_type": "water_discharge", "polarity": "+", "strength": "medium", "confidence": 4, "delay": "immediate"},
    {"id": "cl_to_ks_nut", "source": "curonian_lagoon", "target": "klaipeda_strait", "channel_type": "nutrients", "polarity": "+", "strength": "strong", "confidence": 4, "delay": "short"},

    {"id": "ks_to_bs_water", "source": "klaipeda_strait", "target": "baltic_se", "channel_type": "water_discharge", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "immediate"},
    {"id": "ks_to_bs_nut", "source": "klaipeda_strait", "target": "baltic_se", "channel_type": "nutrients", "polarity": "+", "strength": "strong", "confidence": 3, "delay": "short"},

    {"id": "bs_to_ks_marine_juvs", "source": "baltic_se", "target": "klaipeda_strait", "channel_type": "organisms_marine_estuarine", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "medium"},
    {"id": "bs_to_ks_eel_glass", "source": "baltic_se", "target": "klaipeda_strait", "channel_type": "organisms_diadromous", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "long", "lifestage": "glass_eel"},
    {"id": "ks_to_cl_eel_glass", "source": "klaipeda_strait", "target": "curonian_lagoon", "channel_type": "organisms_diadromous", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "long", "lifestage": "glass_eel"},
    {"id": "cl_to_nd_smelt", "source": "curonian_lagoon", "target": "nemunas_delta", "channel_type": "organisms_diadromous", "polarity": "+", "strength": "medium", "confidence": 3, "delay": "long"},
    {"id": "bs_to_ks_sturgeon_spawners", "source": "baltic_se", "target": "klaipeda_strait", "channel_type": "organisms_diadromous", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "long", "lifestage": "sturgeon_adult", "description": "Atlantic sturgeon (Acipenser oxyrinchus, AphiaID 151802) anadromous spawning run from SE Baltic; reintroduction signal post-2014 (Lesutiene et al.)"},
    {"id": "nl_to_bs_sturgeon_smolt", "source": "nemunas_lower", "target": "baltic_se", "channel_type": "organisms_diadromous", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "long", "lifestage": "sturgeon_juvenile", "description": "Atlantic sturgeon juvenile out-migration from Nemunas spawning grounds via the lagoon to the Baltic feeding grounds"},

    {"id": "bs_to_ks_helcom_gov", "source": "baltic_se", "target": "klaipeda_strait", "channel_type": "governance", "polarity": "-", "strength": "medium", "confidence": 3, "delay": "long", "governance_regime": "MSFD", "cci_index": 7, "description": "HELCOM Baltic Sea Action Plan eutrophication-management measures cascading from Baltic-wide policy onto Klaipeda Strait management"},
    {"id": "ks_to_cl_msfd", "source": "klaipeda_strait", "target": "curonian_lagoon", "channel_type": "governance", "polarity": "-", "strength": "medium", "confidence": 3, "delay": "long", "governance_regime": "MSFD"},
    {"id": "cl_to_nd_ramsar", "source": "curonian_lagoon", "target": "nemunas_delta", "channel_type": "governance", "polarity": "-", "strength": "medium", "confidence": 3, "delay": "long", "governance_regime": "national", "description": "Ramsar wetland + Curonian Spit UNESCO management plan"},
    {"id": "nd_to_nl_wfd", "source": "nemunas_delta", "target": "nemunas_lower", "channel_type": "governance", "polarity": "-", "strength": "medium", "confidence": 3, "delay": "long", "governance_regime": "WFD"},
    {"id": "nl_to_nu_wfd", "source": "nemunas_lower", "target": "nemunas_upper", "channel_type": "governance", "polarity": "-", "strength": "weak", "confidence": 2, "delay": "long", "governance_regime": "WFD", "cci_index": 4, "description": "LT-BY transboundary catchment governance — weakened by political fragmentation"},

    {"id": "bs_to_nl_econ_fishing", "source": "baltic_se", "target": "nemunas_lower", "channel_type": "economic_telecoupling", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "medium"},
    {"id": "bs_to_nu_econ_salmon_recovery", "source": "baltic_se", "target": "nemunas_upper", "channel_type": "economic_telecoupling", "polarity": "+", "strength": "weak", "confidence": 2, "delay": "long"}
  ]
}
```

- [ ] **Step 3: Verify the JSON parses**

```powershell
micromamba run -n shiny python -c "import json; d=json.load(open('multises/curonian/curonian_loac.json',encoding='utf-8')); print('OK:', len(d['compartments']), 'compartments,', len(d['channels']), 'channels')"
```

Expected: `OK: 6 compartments, 26 channels`.

- [ ] **Step 4: Commit**

```powershell
git add multises/curonian/__init__.py multises/curonian/curonian_loac.json
git commit -m "feat(mosaicses): Curonian Lagoon seed dataset (6 compartments, 26 channels including Atlantic sturgeon)"
```

---

## Task 9: `seed_curonian()` factory

**Depends on Tasks:** Task 8 (JSON file).

**Files:**
- Modify: `MosaicSES/multises/curonian/__init__.py`
- Modify: `MosaicSES/multises/__init__.py` (re-export `seed_curonian`)

`seed_curonian()` reads `curonian_loac.json`, builds each compartment via `seed_compartment(archetype_slug, ...)` (which pre-populates DAPSI defaults at confidence=2), then adds the channels.

- [ ] **Step 1: Write `multises/curonian/__init__.py`**

```python
"""Curonian Lagoon seed dataset — public factory.

`seed_curonian()` returns a fresh `MultiSES` matching the v1 Curonian
seed: 6 compartments along Nemunas → Curonian Lagoon → SE Baltic, each
seeded with archetype DAPSI defaults at confidence=2, plus 26 channels
covering the eutrophication-governance balancing loop, the
diadromous-fish telecoupling reinforcing loop (eel + smelt), and the
Atlantic sturgeon (Acipenser oxyrinchus) anadromous spawning run
reintroduced post-2014 (spec §8.4).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..archetypes import seed_compartment
from ..channels import make_channel
from ..data_structure import MultiSES, MultiSESMetadata
from ..validate import MultiSESIntegrityError

_log = logging.getLogger(__name__)
_log.addHandler(logging.NullHandler())

_KB_PATH = Path(__file__).parent / "curonian_loac.json"


def seed_curonian() -> MultiSES:
    """Build the v1 Curonian Lagoon seed MultiSES.

    Each compartment is built by `seed_compartment(archetype, ...)` which
    pre-populates DAPSI defaults at confidence=2. Channels are added via
    `make_channel(...)` which fills in channel-type defaults for any
    fields not explicitly set in the JSON.

    Raises:
      MultiSESIntegrityError: if the bundled `curonian_loac.json` is
        missing, malformed, or missing required keys. Indicates a
        packaging/installation problem, not a user input error.
    """
    try:
        raw = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise MultiSESIntegrityError(
            f"curonian_loac.json not found at {_KB_PATH}. "
            "This is a packaging error — reinstall the multises package."
        ) from e
    except json.JSONDecodeError as e:
        raise MultiSESIntegrityError(
            f"curonian_loac.json is malformed: {e}. "
            "This is a packaging error — reinstall the multises package."
        ) from e

    try:
        metadata = MultiSESMetadata(**raw["metadata"])
        compartments_raw = raw["compartments"]
        channels_raw = raw["channels"]
    except KeyError as e:
        raise MultiSESIntegrityError(
            f"curonian_loac.json missing required top-level key {e}. "
            "Expected keys: metadata, compartments, channels."
        ) from e

    compartments = []
    for c_raw in compartments_raw:
        cmp = seed_compartment(
            c_raw["archetype"],
            label=c_raw["label"],
            id=c_raw["id"],
        )
        compartments.append(cmp)

    ms = MultiSES(metadata=metadata, compartments=compartments, channels=[])

    for ch_raw in channels_raw:
        # Pull through every field present in the JSON; let make_channel
        # apply defaults for any missing optional fields.
        kwargs = {
            "id": ch_raw["id"],
            "source": ch_raw["source"],
            "target": ch_raw["target"],
            "channel_type": ch_raw["channel_type"],
        }
        for opt in ("polarity", "strength", "confidence", "delay",
                    "description", "governance_regime", "cci_index",
                    "lifestage"):
            if opt in ch_raw:
                kwargs[opt] = ch_raw[opt]
        ch = make_channel(**kwargs)
        ms.add_channel(ch)

    return ms
```

- [ ] **Step 2: Re-export `seed_curonian` from `multises/__init__.py`**

Read the existing `multises/__init__.py`, then add the line `from .curonian import seed_curonian` to the imports and add `"seed_curonian"` to the `__all__` list. (Insert alphabetically.)

The diff:

```python
from .curonian import seed_curonian
```

And in `__all__`:

```python
    "seed_curonian",
```

- [ ] **Step 3: Verify the factory works**

```powershell
micromamba run -n shiny python -c "from multises import seed_curonian; ms = seed_curonian(); print('compartments:', len(ms.compartments), 'channels:', len(ms.channels), 'name:', ms.metadata.name)"
```

Expected: `compartments: 6 channels: 26 name: Curonian Lagoon LOAC seed`.

- [ ] **Step 4: Commit**

```powershell
git add multises/curonian/__init__.py multises/__init__.py
git commit -m "feat(mosaicses): seed_curonian() factory + public-API re-export"
```

---

## Task 10: Curonian seed integration / canary tests

**Depends on Tasks:** Task 9 (factory), Task 2 (cross_compartment_loops), Task 4 (compartment_summary), Task 7 (response_pressure_gap).

**Files:**
- Create: `MosaicSES/tests/test_curonian_seed.py`

The double-canary integration test. Pins the eutrophication-governance balancing loop and the diadromous-fish reinforcing loop. If either loop disappears from `cross_compartment_loops()` output, the canary fails and a regression is flagged.

- [ ] **Step 1: Write `tests/test_curonian_seed.py`**

```python
"""Curonian Lagoon seed dataset — integration / canary tests.

These tests pin the v1 contract: the seed dataset must validate clean,
must produce the eutrophication-governance balancing loop, and must
produce the diadromous-fish telecoupling reinforcing loop. If either
loop disappears, the integration canary fails and a regression is flagged.
"""
from __future__ import annotations

import pytest

from multises import seed_curonian, validate, persistence
from multises.composite import cross_compartment_loops
from multises.comparative import compartment_summary, response_pressure_gap


def test_seed_curonian_loads_and_validates_clean(tmp_path):
    ms = seed_curonian()
    issues = validate.validate(ms)
    # Soft warnings (W400 schema migration) shouldn't fire — the seed has
    # all required fields; W302 governance-regime-missing also shouldn't
    # fire because all governance channels in the seed have a regime set.
    assert issues == [], f"expected clean seed, got: {issues}"


def test_seed_curonian_compartment_count_and_archetypes():
    ms = seed_curonian()
    assert len(ms.compartments) == 6
    archetypes = {c.archetype for c in ms.compartments}
    assert archetypes == {
        "river_upper", "river_lower", "delta",
        "estuary", "lagoon", "coastal_sea",
    }


def test_seed_curonian_klaipeda_strait_is_estuary_archetype():
    """Spec §5.1: Klaipeda Strait is mapped to the estuary archetype."""
    ms = seed_curonian()
    ks = ms.compartment("klaipeda_strait")
    assert ks.archetype == "estuary"


def test_seed_curonian_focal_tw_compartments_are_correct():
    """delta + lagoon + estuary should be focal; river_* + coastal_sea not focal."""
    ms = seed_curonian()
    assert ms.compartment("nemunas_delta").is_focal_tw is True
    assert ms.compartment("curonian_lagoon").is_focal_tw is True
    assert ms.compartment("klaipeda_strait").is_focal_tw is True
    assert ms.compartment("nemunas_upper").is_focal_tw is False
    assert ms.compartment("baltic_se").is_focal_tw is False


def test_seed_curonian_save_load_roundtrip_clean(tmp_path):
    ms = seed_curonian()
    path = tmp_path / "curonian.multises.json"
    persistence.save(ms, path)
    result = persistence.load(path)
    ms2, report = result
    assert report.warnings == ()
    assert validate.validate(ms2) == []


def test_seed_curonian_canary_balancing_loop_present():
    """Canary 1: the eutrophication-governance balancing cycle must
    appear in cross_compartment_loops output. If it disappears, the
    seed has regressed or polarity composition is broken."""
    ms = seed_curonian()
    loops = cross_compartment_loops(ms, max_length=12, max_loops=200)
    balancing_with_governance = [
        l for l in loops
        if l.polarity_type == "Balancing" and "governance" in l.channel_types_used
    ]
    assert len(balancing_with_governance) >= 1, (
        "Expected at least one Balancing cross-compartment loop using a "
        "governance channel — the eutrophication-governance canary."
    )


def test_seed_curonian_canary_reinforcing_loop_present():
    """Canary 2: a Reinforcing cross-compartment cycle exists that
    contains BOTH organisms_diadromous (e.g., eel/smelt/sturgeon
    migration) AND economic_telecoupling channels in the same loop —
    the diadromous-fish telecoupling reinforcing canary."""
    ms = seed_curonian()
    loops = cross_compartment_loops(ms, max_length=12, max_loops=200)
    reinforcing_telecoupled = [
        l for l in loops
        if l.polarity_type == "Reinforcing"
        and {"organisms_diadromous", "economic_telecoupling"}.issubset(l.channel_types_used)
    ]
    assert len(reinforcing_telecoupled) >= 1, (
        "Expected at least one Reinforcing cross-compartment loop combining "
        "organisms_diadromous + economic_telecoupling — the diadromous-fish "
        "telecoupling canary."
    )


def test_seed_curonian_diadromous_channels_present():
    """At least one organisms_diadromous channel exists for each headline
    diadromous species (eel, smelt, sturgeon)."""
    ms = seed_curonian()
    diadromous = [ch for ch in ms.channels if ch.channel_type == "organisms_diadromous"]
    assert len(diadromous) >= 3
    lifestages = {ch.lifestage for ch in diadromous if ch.lifestage}
    assert "glass_eel" in lifestages
    assert any("sturgeon" in ls for ls in lifestages)


def test_seed_curonian_compartment_summary_acceptance():
    """The seed should produce a compartment_summary frame with one row
    per compartment and the expected DAPSI counts for archetype defaults."""
    ms = seed_curonian()
    df = compartment_summary(ms)
    assert len(df) == 6
    assert set(df["compartment_id"]) == {
        "nemunas_upper", "nemunas_lower", "nemunas_delta",
        "curonian_lagoon", "klaipeda_strait", "baltic_se",
    }
    # Every compartment should have at least one driver and one pressure
    # from archetype defaults.
    assert (df["n_drivers"] >= 1).all()
    assert (df["n_pressures"] >= 1).all()


def test_seed_curonian_response_pressure_gap_acceptance():
    """The seed should produce a response_pressure_gap frame; structure
    must match the documented schema."""
    ms = seed_curonian()
    df = response_pressure_gap(ms)
    expected_cols = {"compartment_id", "n_pressures", "n_responses",
                     "pressure_compartment_has_no_governance"}
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == 6
```

- [ ] **Step 2: Run tests**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pytest tests/test_curonian_seed.py -v
```

Expected: 10 PASSED.

If a canary test FAILS:
- If the balancing loop is missing, check that the JSON channels have polarity="+" for nutrients and polarity="-" for governance, and that the source/target ids match the compartment ids exactly.
- If the reinforcing loop is missing, check that economic_telecoupling and organisms_diadromous channels close a multi-compartment cycle. The canary specifically requires BOTH channel types in the SAME cycle.

Then full suite:
```powershell
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite passes (chunk-1 baseline + all chunk-2 new tests including 10 canaries).

- [ ] **Step 3: Commit**

```powershell
git add tests/test_curonian_seed.py
git commit -m "test(mosaicses): Curonian seed double-canary integration tests"
```

---

## Acceptance criteria for chunk 2

- [ ] All ~195 unit + integration tests pass (`pytest tests/ -v`).
- [ ] `multises.validate(seed_curonian()) == []`.
- [ ] `cross_compartment_loops(seed_curonian())` returns at least one Balancing loop using a `governance` channel (Canary 1).
- [ ] `cross_compartment_loops(seed_curonian())` returns at least one Reinforcing loop containing BOTH `organisms_diadromous` AND `economic_telecoupling` channel types in the same cycle (Canary 2 — tightened).
- [ ] `compartment_summary(seed_curonian())` produces a 6-row DataFrame; every compartment has ≥1 driver and ≥1 pressure (archetype defaults).
- [ ] `response_pressure_gap(seed_curonian())` produces a 6-row DataFrame with the documented column schema (`pressure_compartment_has_no_governance` instead of misleading `is_orphan`).
- [ ] `persistence.save(seed_curonian(), p); persistence.load(p)` round-trips clean (no warnings, validate clean).
- [ ] No new runtime dependencies beyond `pandas>=2.1` (added in `pyproject.toml` via Task 3.5).
- [ ] Conventional-commit format on all task commits (≥ 10 commits including Task 3.5).

---

(The pandas dependency prep was relocated to Task 3.5 — running BEFORE Task 4 so subagents don't hit ImportError.)

---

## Self-review notes (filled in during plan writing)

**1. Spec coverage** —
- composite.py with `build_composite_digraph`, `cross_compartment_loops`, `inter_compartment_metrics`, `CrossLoop` ✓ Tasks 1, 2, 3
- comparative.py with `compartment_summary`, `per_compartment_grid`, `leverage_hotspots`, `response_pressure_gap` ✓ Tasks 4-7
- curonian/curonian_loac.json + seed_curonian() ✓ Tasks 8, 9
- test_curonian_seed.py double canary ✓ Task 10

Spec §6.4 `expansion="strict" | "full"` mode for `build_composite_digraph` ✓ Task 1 (strict-only after simplifier review; "full" deferred to chunk 2.5).
Spec §6.4 truncation reporting in `cross_compartment_loops` ✓ Task 2 (returns `list[CrossLoop]` directly; truncation logged via `_log.warning(...)` on cap hit, per chunk-1 idiom).
Spec §6.4 polarity composition correctness via `internal_link` polarity="+" pinning ✓ Task 1, tested in Tasks 1, 2, and 10.

**2. Placeholder scan** — All steps contain concrete code or commands. Task 8 has a substantial JSON content block written verbatim; no TBDs.

**3. Type consistency** —
- `cross_compartment_loops` returns `list[CrossLoop]` (no tuple) consistently in tests and implementation; truncation reported via WARNING log only.
- `CrossLoop` is `@dataclass(frozen=True)`; ids are assigned in a single `dataclasses.replace` pass (no double-reassignment).
- `response_pressure_gap` returns columns `{compartment_id, n_pressures, n_responses, pressure_compartment_has_no_governance}` — no `is_orphan` column anywhere in tests or implementation.
- `compartment_summary` columns named identically in production and tests.
- `response_pressure_gap` columns: `compartment_id, pressure_id, pressure_label, within_compartment_response_count, incoming_governance_channel_count, is_orphan` — used consistently.
- `seed_curonian()` reads only fields actually present in the JSON; `make_channel(**kwargs)` accepts the optional fields (matches Task 9 channels.py signature).

**4. Known caveat** — Task 10's two canary tests rely on `cross_compartment_loops` actually finding the loops. If `nx.simple_cycles` enumerates them in a different order across networkx versions, the tests still pass because we filter by polarity_type, not by id. The deterministic-edge-selection from chunk 1's W301 reporting doesn't apply to chunk 2's CrossLoop list (which can stay unordered without affecting correctness).
