# SES Hypermodule Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect cohesive multi-tier SES subsystems (hypermodules) across the ecological/social/governance tiers and surface them as a button-gated block on the Network Metrics card, closing issue #24.

**Architecture:** One pure function `hypermodules(isa)` in `sespy/network.py` — three undirected bipartite tier projections, deterministic greedy-modularity communities, a size-aware hinge-merge into a module graph, multi-tier components merged to a node partition. One UI block cloned from the cascade block's shape, plus eight i18n keys × nine languages.

**Tech Stack:** Python 3.13, networkx 3.6 (`greedy_modularity_communities`), Shiny for Python, pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-hypermodules-design.md` — read it first. It records the owner's three decisions, every departure from issue #24, and two measured hazards: the flat ≥2 hinge threshold returns zero hypermodules on the shipped sample (and structurally cannot fire on chain-shaped models), and a node's projection modules can straddle two components (hence the merge-to-partition rule).

## Global Constraints

- Python runs ONLY as `micromamba run -n shiny <cmd>`. There is no other Python on this machine. Never create a venv.
- Unit gate: `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`. Baseline before this work: **576 passed**.
- Full e2e gate: `micromamba run -n shiny python tests/run_e2e.py` — expect **32/32**. Kill anything on port 8000 first; launch detached; ~10 minutes.
- `_SUBSYSTEM`, `subsystem()`, `social_ecological_fit` and `governance_gap` must not change.
- Determinism is a hard requirement: no RNG, no seed, and construction-order independence (build every node/edge list in sorted order before networkx sees it).
- **`build/` is git-ignored but present in the working tree with a STALE copy of the package.** A bare `grep -rn X .` returns `build/lib/sespy/...` hits whose line numbers do not match the source. Scope every grep to `sespy/` and `tests/`.
- New i18n keys need all nine languages: en, es, fr, de, lt, pt, it, no, el.
- Do not bump the version and do not tag.

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `sespy/network.py` | `_TIER`, `hypermodules()` | 1 |
| `tests/test_network.py` | ten algorithm tests | 1 |
| `sespy/modules/analysis_metrics.py` | the "SES Subsystem Modules" block | 2 |
| `sespy/translations/core.json` | eight keys × 9 languages | 2 |
| `tests/test_metrics_hypermodules.py` | module-level assertions (**new file**) | 2 |

---

### Task 1: `_TIER` and `hypermodules()`

**Files:**
- Modify: `sespy/network.py` — add `_TIER` directly above `_SUBSYSTEM` (locate by symbol: `grep -n "^_SUBSYSTEM" sespy/network.py`, currently `:784`), and `hypermodules()` directly after `governance_gap()` (locate by symbol; it currently starts at `:852` — find its end by the next top-level `def`)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Consumes: nothing new (networkx `community.greedy_modularity_communities`, stdlib)
- Produces: `hypermodules(isa: IsaData) -> dict` with keys `rows` (list of `{"node": str, "tier": str, "hypermodule_id": int | None, "n_congruent": int}`), `hypermodularity: float`, `n_hypermodules: int`, `n_untyped: int`, `note: str` (`"" | "no_coupling" | "single_projection" | "no_congruence"`); and `_TIER: dict[str, str]`. Task 2 consumes both.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
# ---- hypermodules (#24) ----


def _hm_isa(specs):
    """Build an IsaData from (id, type) node specs plus (source, target) edges."""
    from sespy.data_structure import IsaData, Element, Connection
    nodes, edges = specs
    els = [Element(id=n, label=n, type=t) for n, t in nodes]
    cons = [Connection(source=s, target=t, polarity="+", strength="strong")
            for s, t in edges]
    return IsaData(elements=els, connections=cons)


def _planted_two_clusters():
    """Two separate dense clusters, each with 2 ecological hinge nodes plus
    social and governance nodes, one weak inter-cluster link."""
    nodes = [("E1", "Pressures"), ("E2", "Pressures"),
             ("S1", "Activities"), ("S2", "Activities"), ("G1", "Responses"),
             ("E3", "Pressures"), ("E4", "Pressures"),
             ("S3", "Activities"), ("S4", "Activities"), ("G2", "Responses")]
    edges = [
        # cluster 1: E1,E2 wired to both socials and the governance node
        ("S1", "E1"), ("S1", "E2"), ("S2", "E1"), ("S2", "E2"),
        ("G1", "E1"), ("G1", "E2"), ("G1", "S1"), ("G1", "S2"),
        # cluster 2, same shape
        ("S3", "E3"), ("S3", "E4"), ("S4", "E3"), ("S4", "E4"),
        ("G2", "E3"), ("G2", "E4"), ("G2", "S3"), ("G2", "S4"),
        # one weak bridge
        ("S2", "E3"),
    ]
    return _hm_isa((nodes, edges))


def test_hypermodules_planted_two_clusters():
    """The headline behaviour: two dense three-tier clusters -> exactly two
    hypermodules with the planted membership. Fails against the vacuous
    pairwise congruence rule (which returns zero always) — the guard against
    reintroducing that reading."""
    from sespy.network import hypermodules

    r = hypermodules(_planted_two_clusters())
    assert r["n_hypermodules"] == 2
    assert r["note"] == ""
    by_hm = {}
    for row in r["rows"]:
        if row["hypermodule_id"] is not None:
            by_hm.setdefault(row["hypermodule_id"], set()).add(row["node"])
    members = sorted(sorted(m) for m in by_hm.values())
    assert members == [["E1", "E2", "G1", "S1", "S2"],
                       ["E3", "E4", "G2", "S3", "S4"]]
    tiers_per_hm = [
        {row["tier"] for row in r["rows"] if row["hypermodule_id"] == h}
        for h in by_hm
    ]
    assert all(t == {"ecological", "social", "governance"} for t in tiers_per_hm)


def test_hypermodules_fire_on_a_chain_model():
    """The size-aware hinge threshold exists for exactly this shape: one
    activity -> one pressure chains make every eco-social module a size-2
    pair, and a flat >=2-shared-hinge rule can never fire (measured: zero on
    the shipped sample). One shared hinge suffices when a module only HAS
    one hinge node."""
    from sespy.network import hypermodules

    isa = _hm_isa((
        [("A1", "Activities"), ("A2", "Activities"),
         ("P1", "Pressures"), ("P2", "Pressures"), ("R1", "Responses")],
        [("A1", "P1"), ("A2", "P2"), ("R1", "P1"), ("R1", "P2")],
    ))
    r = hypermodules(isa)
    assert r["n_hypermodules"] >= 1, "chain models must not be structurally excluded"
    assert r["note"] == ""


def test_hypermodules_membership_is_a_partition():
    """A node's projection modules can straddle two module-graph components
    (the review constructed this); hypermodules sharing any node must merge
    to a fixed point, so every node has exactly one id."""
    from sespy.network import hypermodules

    # X is an ecological node pulled toward two otherwise-separate groups.
    nodes = [("X", "Pressures"), ("E2", "Pressures"), ("E3", "Pressures"),
             ("E4", "Pressures"), ("S1", "Activities"), ("S2", "Activities"),
             ("S5", "Activities"), ("S6", "Activities"),
             ("G1", "Responses"), ("G2", "Responses"), ("G9", "Responses")]
    edges = [
        ("S1", "X"), ("S1", "E2"), ("S2", "X"), ("S2", "E2"),
        ("G9", "S1"), ("G9", "S2"),
        ("S5", "E3"), ("S5", "E4"), ("S6", "E3"), ("S6", "E4"),
        ("G1", "X"), ("G1", "E3"), ("G1", "E4"),
        ("G2", "X"), ("G2", "E3"), ("G2", "E4"),
    ]
    r = hypermodules(_hm_isa((nodes, edges)))
    ids = {}
    for row in r["rows"]:
        assert row["node"] not in ids, "one row per node"
        ids[row["node"]] = row["hypermodule_id"]
    assigned = [n for n, h in ids.items() if h is not None]
    assert len(assigned) == len({(n, ids[n]) for n in assigned}), "scalar ids"
    # X bridges the two candidate hypermodules -> they merge into one.
    x_id = ids["X"]
    assert x_id is not None
    assert ids["S1"] == x_id and ids["G1"] == x_id, (
        "hypermodules sharing X must have merged")


def test_hypermodules_single_module_component_is_not_a_hypermodule():
    """One bipartite module spans two tiers by itself; only components with
    >= 2 modules count."""
    from sespy.network import hypermodules

    isa = _hm_isa((
        [("A1", "Activities"), ("A2", "Activities"),
         ("P1", "Pressures"), ("P2", "Pressures")],
        [("A1", "P1"), ("A1", "P2"), ("A2", "P1"), ("A2", "P2")],
    ))
    r = hypermodules(isa)
    assert r["n_hypermodules"] == 0
    assert r["note"] == "single_projection"


def test_hypermodules_deterministic_and_order_independent():
    from sespy.network import hypermodules

    nodes, edges = ([("E1", "Pressures"), ("E2", "Pressures"),
                     ("S1", "Activities"), ("S2", "Activities"),
                     ("G1", "Responses")],
                    [("S1", "E1"), ("S1", "E2"), ("S2", "E1"), ("S2", "E2"),
                     ("G1", "E1"), ("G1", "E2")])
    a = hypermodules(_hm_isa((nodes, edges)))
    b = hypermodules(_hm_isa((nodes, edges)))
    assert a == b, "two calls must agree exactly"
    c = hypermodules(_hm_isa((list(reversed(nodes)), list(reversed(edges)))))
    assert a["n_hypermodules"] == c["n_hypermodules"]
    assert sorted((r["node"], r["hypermodule_id"]) for r in a["rows"]) == \
           sorted((r["node"], r["hypermodule_id"]) for r in c["rows"]), (
        "construction order must not leak into the result")


def test_hypermodules_note_no_coupling_and_empty_isa():
    from sespy.data_structure import IsaData
    from sespy.network import hypermodules

    r = hypermodules(IsaData(elements=[], connections=[]))
    assert r == {"rows": [], "hypermodularity": 0.0, "n_hypermodules": 0,
                 "n_untyped": 0, "note": "no_coupling"}

    # nodes in all tiers but only within-tier edges -> no projection wired
    isa = _hm_isa((
        [("A1", "Activities"), ("A2", "Activities"),
         ("P1", "Pressures"), ("R1", "Responses")],
        [("A1", "A2")],
    ))
    r2 = hypermodules(isa)
    assert r2["note"] == "no_coupling"
    assert r2["n_hypermodules"] == 0
    assert len(r2["rows"]) == 4


def test_hypermodules_note_single_projection_both_routes():
    """The note keys on wired PROJECTIONS, not tier presence: a missing tier
    and a present-but-unwired tier land in the same state."""
    from sespy.network import hypermodules

    # route 1: governance tier entirely absent
    r = hypermodules(_hm_isa((
        [("A1", "Activities"), ("P1", "Pressures")],
        [("A1", "P1")],
    )))
    assert r["note"] == "single_projection"
    # route 2: governance nodes exist but are unwired
    r2 = hypermodules(_hm_isa((
        [("A1", "Activities"), ("P1", "Pressures"), ("R1", "Responses")],
        [("A1", "P1")],
    )))
    assert r2["note"] == "single_projection"
    assert any(row["tier"] == "governance" for row in r2["rows"])


def test_hypermodules_note_no_congruence():
    """Two projections wired, but their modules share no hinge nodes at all
    -> no link, zero hypermodules, and the note that explains it."""
    from sespy.network import hypermodules

    isa = _hm_isa((
        [("A1", "Activities"), ("P1", "Pressures"),
         ("P2", "Pressures"), ("R1", "Responses")],
        [("A1", "P1"), ("R1", "P2")],
    ))
    r = hypermodules(isa)
    assert r["n_hypermodules"] == 0
    assert r["note"] == "no_congruence"


def test_hypermodules_untyped_and_score_denominator():
    """Unknown types are excluded from the score's denominator and counted;
    an all-unknown ISA gives 0.0, not 0/0."""
    from sespy.data_structure import IsaData, Element
    from sespy.network import hypermodules

    els = [Element(id="U1", label="U1", type="Weird"),
           Element(id="U2", label="U2", type="Weirder")]
    r = hypermodules(IsaData(elements=els, connections=[]))
    assert r["n_untyped"] == 2
    assert r["rows"] == []
    assert r["hypermodularity"] == 0.0


def test_hypermodules_sample_project_golden():
    """Pinned under the size-aware hinge rule; the flat >=2 rule measures
    0/17 on this same data (the mean_leverage failure shape). If the tier
    map or the hinge rule legitimately changes, re-derive by running
    hypermodules() on the sample and updating BOTH numbers and the members —
    an unexplained move is a regression."""
    from pathlib import Path
    from sespy.data_structure import load_sample
    from sespy.network import hypermodules

    isa = load_sample(
        Path(__file__).resolve().parents[1] / "data" / "sample_ses.json")
    r = hypermodules(isa)
    assert r["n_hypermodules"] == 2
    assert abs(r["hypermodularity"] - 9 / 17) < 1e-9
    members = sorted(sorted(row["node"] for row in r["rows"]
                            if row["hypermodule_id"] == h)
                     for h in range(r["n_hypermodules"]))
    assert members == [["A001", "ES01", "ES03", "GB01", "P001", "R002"],
                       ["A002", "P002", "R001"]]
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "hypermodules"
```

Expected: FAIL with `ImportError: cannot import name 'hypermodules' from 'sespy.network'`.

- [ ] **Step 3: Add `_TIER`**

In `sespy/network.py`, directly above `_SUBSYSTEM` (locate by symbol):

```python
#: Three-tier partition for hypermodule detection (#24). Governance matches
#: governance_gap()'s layer exactly; the split of the remaining types is
#: _SUBSYSTEM's. _SUBSYSTEM itself is NOT changed — it answers a different,
#: two-tier question and other shipped metrics depend on it. Note Measures
#: is genuinely mapped here, unlike leverage_realm where it is an accepted
#: gap, because governance_gap already treats it as governance.
_TIER: dict[str, str] = {
    "Pressures": "ecological",
    "Marine Processes & Functioning": "ecological",
    "Ecosystem Services": "ecological",
    "Drivers": "social",
    "Activities": "social",
    "Goods & Benefits": "social",
    "Responses": "governance",
    "Measures": "governance",
}
```

- [ ] **Step 4: Add `hypermodules()`**

In `sespy/network.py`, directly after the end of `governance_gap()` (locate by symbol; find its end at the next top-level `def`):

```python
def hypermodules(isa: IsaData) -> dict:
    """Cohesive multi-tier SES subsystems via module congruence (#24).

    Three undirected bipartite projections (eco-social, eco-governance,
    social-governance), deterministic greedy-modularity communities per
    projection, then a module graph: modules from different projections link
    when they share min(2, hinge_capacity) hinge-tier nodes, where
    hinge_capacity is the smaller module's node count in the tier the two
    projections share. Two shared hinge nodes normally; one suffices exactly
    when either module only HAS one hinge-tier node, so chain-shaped models
    (one activity -> one pressure) are not structurally excluded — a flat
    >=2 rule measures ZERO hypermodules on data/sample_ses.json.

    A hypermodule is the node union of a module-graph component containing
    at least two modules; hypermodules sharing any node are then merged to
    a fixed point, so membership is a partition (a node's modules from
    different projections need not land in one component otherwise).

    RECONSTRUCTION NOTE: the HyperMod paper (doi:10.1098/rspb.2026.1348)
    was not reachable when this was designed; the hinge threshold and the
    merge rule are documented assumptions — check against the paper when
    available. Same caveat class as #22's ALC and #23's depth scheme.
    """
    from networkx.algorithms import community

    tier = {el.id: _TIER.get(el.type, "") for el in isa.elements}
    tiered = sorted(nid for nid, t in tier.items() if t)
    n_untyped = sum(1 for t in tier.values() if not t)

    pairs = [("ecological", "social"), ("ecological", "governance"),
             ("social", "governance")]
    hinge_of = {(0, 1): "ecological", (0, 2): "social", (1, 2): "governance"}

    modules: list[tuple[int, frozenset]] = []
    n_wired = 0
    for pi, (a, b) in enumerate(pairs):
        g = nx.Graph()
        for c in sorted(isa.connections, key=lambda c: (c.source, c.target)):
            if {tier.get(c.source, ""), tier.get(c.target, "")} == {a, b}:
                g.add_edge(c.source, c.target)
        if g.number_of_edges() == 0:
            continue
        n_wired += 1
        for m in community.greedy_modularity_communities(g):
            modules.append((pi, frozenset(m)))

    def _result(hms: list[list[str]], note: str) -> dict:
        node_hm: dict[str, int] = {}
        for hid, members in enumerate(hms):
            for n in members:
                node_hm[n] = hid
        # n_congruent: other nodes of the same hypermodule sharing at least
        # one projection module with this node.
        mod_sets = [set(m) for _, m in modules]
        rows = []
        for nid in tiered:
            hid = node_hm.get(nid)
            n_cong = 0
            if hid is not None:
                partners = set()
                for ms in mod_sets:
                    if nid in ms:
                        partners |= (ms & set(hms[hid]))
                partners.discard(nid)
                n_cong = len(partners)
            rows.append({"node": nid, "tier": tier[nid],
                         "hypermodule_id": hid, "n_congruent": n_cong})
        rows.sort(key=lambda r: (r["hypermodule_id"] is None,
                                 r["hypermodule_id"]
                                 if r["hypermodule_id"] is not None else -1,
                                 r["node"]))
        score = (sum(1 for r in rows if r["hypermodule_id"] is not None)
                 / len(tiered)) if tiered else 0.0
        return {"rows": rows, "hypermodularity": score,
                "n_hypermodules": len(hms), "n_untyped": n_untyped,
                "note": note}

    if n_wired == 0:
        return _result([], "no_coupling")
    if n_wired == 1:
        return _result([], "single_projection")

    # Module graph: size-aware hinge linking.
    mg = nx.Graph()
    mg.add_nodes_from(range(len(modules)))
    for i in range(len(modules)):
        for j in range(i + 1, len(modules)):
            pi, mi = modules[i]
            pj, mj = modules[j]
            if pi == pj:
                continue
            h = hinge_of[(min(pi, pj), max(pi, pj))]
            cap = min(sum(1 for n in mi if tier[n] == h),
                      sum(1 for n in mj if tier[n] == h))
            need = min(2, cap)
            if need >= 1 and len(mi & mj) >= need:
                mg.add_edge(i, j)

    candidates = []
    for comp in nx.connected_components(mg):
        if len(comp) < 2:
            continue        # a single bipartite module is not a hypermodule
        candidates.append(set().union(*(modules[i][1] for i in comp)))

    # Merge candidates sharing any node, to a fixed point -> a partition.
    merged = True
    while merged:
        merged = False
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                if candidates[i] & candidates[j]:
                    candidates[i] |= candidates[j]
                    del candidates[j]
                    merged = True
                    break
            if merged:
                break

    hms = sorted((sorted(c) for c in candidates))
    return _result(hms, "" if hms else "no_congruence")
```

- [ ] **Step 5: Run the tests**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "hypermodules"
```

Expected: all 10 PASS. **If the sample golden fails, do not adjust the
expected numbers** — the derivation was measured against this exact
algorithm; a mismatch means the implementation diverged (check the hinge
capacity is counted on hinge-tier nodes, not module size, and that
construction is sorted). Then run the whole file:

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q
```

Expected: no pre-existing test moves.

- [ ] **Step 6: Run the full unit gate**

```bash
micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' \
  --ignore=tests/test_burger.py --ignore=tests/test_stepper.py \
  --ignore=tests/test_stepper_click.py
```

Expected: **586 passed** (576 + 10).

- [ ] **Step 7: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): SES hypermodule detection (#24)

Deterministic module congruence across the three tier projections, with a
size-aware hinge threshold: a flat >=2 rule measures zero hypermodules on
the shipped sample and cannot fire on chain-shaped models. Membership is a
partition (candidates sharing a node merge to a fixed point)."
```

---

### Task 2: The "SES Subsystem Modules" block

**Files:**
- Modify: `sespy/modules/analysis_metrics.py` — UI slot after `paths_summary` (locate: `grep -n "paths_summary" sespy/modules/analysis_metrics.py`, UI at `:160`, server block ends near `:470`); server block appended after the paths block
- Modify: `sespy/translations/core.json` — eight keys after `metrics.paths_truncated` (currently `:5530`)
- Create: `tests/test_metrics_hypermodules.py` — it does NOT exist; only `tests/test_metrics_e2e.py` does

**Interfaces:**
- Consumes: `hypermodules(isa)` and its return contract from Task 1
- Produces: nothing later tasks rely on

- [ ] **Step 1: Write the failing tests**

Create `tests/test_metrics_hypermodules.py`:

```python
"""Module-level pins for the SES Subsystem Modules block (#24).

Source-text assertions pin the FEATURE, not just call names — the lesson
from #23, where grep-for-the-function tests passed with the column absent.
"""


def test_metrics_module_wires_hypermodules():
    from sespy.modules import analysis_metrics

    text = open(analysis_metrics.__file__, encoding="utf-8").read()
    assert "net_analysis.hypermodules(" in text, "must call the library fn"
    assert '"run_hypermodules"' in text, "the run button"
    assert 'ui.output_ui("hypermodules_summary")' in text, "the UI slot"
    assert "_hypermodules_result" in text, "the reactive result value"
    # The reset-on-isa-change effect must cover the new result value.
    assert text.count("_hypermodules_result.set(None)") == 1


def test_hypermodules_translation_keys_resolve():
    """Through the PRODUCTION loader, per the repo convention."""
    from pathlib import Path
    from sespy.i18n import load_translations

    tr = load_translations(
        Path(__file__).resolve().parents[1] / "sespy" / "translations")
    langs = {"en", "es", "fr", "de", "lt", "pt", "it", "no", "el"}
    for key in ("metrics.hypermodules", "metrics.hypermodules_run",
                "metrics.hypermodules_hint", "metrics.hypermodules_score",
                "metrics.hypermodules_no_coupling",
                "metrics.hypermodules_single_projection",
                "metrics.hypermodules_no_congruence",
                "metrics.hypermodules_caption"):
        assert key in tr, f"{key} does not resolve"
        assert langs.issubset(set(tr[key])), f"{key} missing languages"
        assert all(tr[key][l].strip() for l in langs), f"{key} empty value"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_metrics_hypermodules.py -q
```

Expected: FAIL — `assert "net_analysis.hypermodules(" in text` first.

- [ ] **Step 3: Add the UI slot**

In `analysis_metrics.py`, in the `ui.div(...)` that stacks the summaries
(currently `:151-161`), directly after the `paths_summary` pair:

```python
                ui.output_ui("paths_summary"),
                ui.tags.hr(),
                ui.output_ui("hypermodules_summary"),
                ui.tags.hr(),
```

(The first two lines exist; add the second two after them.)

- [ ] **Step 4: Add the server block**

Append after the paths server block (its renderer `paths_summary` starts
near `:405`; add after that function ends), following the cascade block's
shape exactly:

```python
    _hypermodules_result = reactive.value(None)

    @reactive.effect
    def _reset_hypermodules():
        # Any model change invalidates a computed result — a stale table
        # must never masquerade as current. (Same contract as the cascade.)
        event_bus.isa_change.get()
        _hypermodules_result.set(None)

    @reactive.effect
    @reactive.event(input.run_hypermodules, ignore_init=True)
    def _compute_hypermodules():
        _hypermodules_result.set(
            net_analysis.hypermodules(project_data.get().isa_data))

    @output
    @render.ui
    def hypermodules_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 3:
            # gov_gap_none is the card's shared too-small message — the
            # cascade and paths blocks use the same key for this guard.
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        button = ui.input_action_button(
            "run_hypermodules", t("metrics.hypermodules_run"),
            class_="btn-sm btn-outline-primary")
        r = _hypermodules_result.get()
        if r is None:
            return ui.div(
                ui.h5(t("metrics.hypermodules")),
                button,
                ui.p(t("metrics.hypermodules_hint"), class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        if r["note"]:
            return ui.div(
                ui.h5(t("metrics.hypermodules")),
                button,
                ui.p(t(f"metrics.hypermodules_{r['note']}"),
                     class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        by_id = {el.id: el for el in isa.elements}
        groups: dict[int, list[dict]] = {}
        for row in r["rows"]:
            if row["hypermodule_id"] is not None:
                groups.setdefault(row["hypermodule_id"], []).append(row)
        lines = []
        for hid in sorted(groups):
            rows = groups[hid]
            tiers = {}
            for row in rows:
                tiers[row["tier"]] = tiers.get(row["tier"], 0) + 1
            comp = " · ".join(f"{n} {tname}" for tname, n in sorted(tiers.items()))
            labels = ", ".join(
                (by_id[row["node"]].label if row["node"] in by_id
                 else row["node"])
                for row in rows)
            lines.append(ui.tags.li(
                f"HM{hid} ({len(rows)}): {comp} — {labels}"))
        return ui.div(
            ui.h5(t("metrics.hypermodules")),
            button,
            ui.p(ui.tags.strong(
                t("metrics.hypermodules_score",
                  n=r["n_hypermodules"],
                  score=f"{r['hypermodularity']:.2f}")),
                style="margin-top: 0.5rem;"),
            ui.tags.ul(*lines),
            ui.p(t("metrics.hypermodules_caption"),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )
```

- [ ] **Step 5: Add the eight i18n keys**

In `sespy/translations/core.json`, directly after the
`"metrics.paths_truncated"` line (currently `:5530`), insert:

```json
    "metrics.hypermodules": {"en": "SES subsystem modules", "es": "Módulos de subsistemas SES", "fr": "Modules de sous-systèmes SES", "de": "SES-Teilsystem-Module", "lt": "SES posistemių moduliai", "pt": "Módulos de subsistemas SES", "it": "Moduli di sottosistemi SES", "no": "SES-delsystemmoduler", "el": "Ενότητες υποσυστημάτων SES"},
    "metrics.hypermodules_run": {"en": "Detect subsystem modules", "es": "Detectar módulos de subsistemas", "fr": "Détecter les modules de sous-systèmes", "de": "Teilsystem-Module erkennen", "lt": "Aptikti posistemių modulius", "pt": "Detetar módulos de subsistemas", "it": "Rileva moduli di sottosistemi", "no": "Detekter delsystemmoduler", "el": "Εντοπισμός ενοτήτων υποσυστημάτων"},
    "metrics.hypermodules_hint": {"en": "not computed for the current model — run to compute", "es": "no calculado para el modelo actual: ejecute para calcular", "fr": "non calculé pour le modèle actuel — lancez le calcul", "de": "für das aktuelle Modell nicht berechnet — zum Berechnen ausführen", "lt": "dabartiniam modeliui neapskaičiuota — paleiskite skaičiavimą", "pt": "não calculado para o modelo atual — execute para calcular", "it": "non calcolato per il modello attuale — eseguire per calcolare", "no": "ikke beregnet for gjeldende modell — kjør for å beregne", "el": "δεν έχει υπολογιστεί για το τρέχον μοντέλο — εκτελέστε για υπολογισμό"},
    "metrics.hypermodules_score": {"en": "{n} subsystem module(s); {score} of typed elements belong to one", "es": "{n} módulo(s) de subsistema; {score} de los elementos tipados pertenecen a uno", "fr": "{n} module(s) de sous-système ; {score} des éléments typés en font partie", "de": "{n} Teilsystem-Modul(e); {score} der typisierten Elemente gehören zu einem", "lt": "{n} posistemio modulis(-iai); {score} tipizuotų elementų priklauso vienam", "pt": "{n} módulo(s) de subsistema; {score} dos elementos tipados pertencem a um", "it": "{n} modulo(i) di sottosistema; {score} degli elementi tipizzati vi appartiene", "no": "{n} delsystemmodul(er); {score} av typede elementer tilhører en", "el": "{n} ενότητα(-ες) υποσυστήματος· {score} των τυποποιημένων στοιχείων ανήκουν σε μία"},
    "metrics.hypermodules_no_coupling": {"en": "no cross-tier connections — subsystem modules need links between the ecological, social and governance tiers", "es": "sin conexiones entre niveles: los módulos de subsistemas requieren enlaces entre los niveles ecológico, social y de gobernanza", "fr": "aucune connexion inter-niveaux — les modules de sous-systèmes nécessitent des liens entre les niveaux écologique, social et de gouvernance", "de": "keine ebenenübergreifenden Verbindungen — Teilsystem-Module benötigen Verknüpfungen zwischen ökologischer, sozialer und Governance-Ebene", "lt": "nėra ryšių tarp pakopų — posistemių moduliams reikia sąsajų tarp ekologinės, socialinės ir valdymo pakopų", "pt": "sem conexões entre níveis — os módulos de subsistemas requerem ligações entre os níveis ecológico, social e de governação", "it": "nessuna connessione tra livelli — i moduli di sottosistemi richiedono collegamenti tra i livelli ecologico, sociale e di governance", "no": "ingen forbindelser på tvers av nivåer — delsystemmoduler krever koblinger mellom økologisk, sosialt og styringsnivå", "el": "δεν υπάρχουν συνδέσεις μεταξύ βαθμίδων — οι ενότητες υποσυστημάτων απαιτούν συνδέσμους μεταξύ οικολογικής, κοινωνικής και διακυβερνητικής βαθμίδας"},
    "metrics.hypermodules_single_projection": {"en": "only one tier pair is connected — congruence needs at least two (wire the third tier in, or this metric cannot fire)", "es": "solo un par de niveles está conectado: la congruencia requiere al menos dos (conecte el tercer nivel o esta métrica no puede activarse)", "fr": "une seule paire de niveaux est connectée — la congruence en exige au moins deux (reliez le troisième niveau, sinon cette métrique ne peut rien détecter)", "de": "nur ein Ebenenpaar ist verbunden — Kongruenz benötigt mindestens zwei (dritte Ebene anbinden, sonst kann diese Metrik nicht anschlagen)", "lt": "sujungta tik viena pakopų pora — kongruencijai reikia bent dviejų (prijunkite trečią pakopą, kitaip ši metrika neveiks)", "pt": "apenas um par de níveis está ligado — a congruência requer pelo menos dois (ligue o terceiro nível, caso contrário esta métrica não pode disparar)", "it": "è connessa una sola coppia di livelli — la congruenza ne richiede almeno due (collegare il terzo livello, altrimenti la metrica non può attivarsi)", "no": "bare ett nivåpar er koblet — kongruens krever minst to (koble inn det tredje nivået, ellers kan ikke denne metrikken slå ut)", "el": "μόνο ένα ζεύγος βαθμίδων είναι συνδεδεμένο — η συμφωνία απαιτεί τουλάχιστον δύο (συνδέστε την τρίτη βαθμίδα, αλλιώς ο δείκτης δεν μπορεί να ενεργοποιηθεί)"},
    "metrics.hypermodules_no_congruence": {"en": "tiers are connected but no modules co-cluster across projections — no multi-tier subsystem detected in this model", "es": "los niveles están conectados pero ningún módulo se agrupa a través de las proyecciones: no se detectó ningún subsistema multinivel en este modelo", "fr": "les niveaux sont connectés mais aucun module ne co-clusterise entre projections — aucun sous-système multi-niveaux détecté dans ce modèle", "de": "die Ebenen sind verbunden, aber keine Module clustern über Projektionen hinweg — kein mehrstufiges Teilsystem in diesem Modell erkannt", "lt": "pakopos sujungtos, bet moduliai nesigrupuoja per projekcijas — šiame modelyje daugiapakopis posistemis neaptiktas", "pt": "os níveis estão ligados mas nenhum módulo se coagrupa entre projeções — nenhum subsistema multinível detetado neste modelo", "it": "i livelli sono connessi ma nessun modulo si co-raggruppa tra le proiezioni — nessun sottosistema multilivello rilevato in questo modello", "no": "nivåene er koblet, men ingen moduler samklynger seg på tvers av projeksjoner — ingen flernivå-delsystem oppdaget i denne modellen", "el": "οι βαθμίδες συνδέονται αλλά καμία ενότητα δεν συνομαδοποιείται μεταξύ προβολών — δεν εντοπίστηκε πολυβαθμιδωτό υποσύστημα σε αυτό το μοντέλο"},
    "metrics.hypermodules_caption": {"en": "Subsystem modules group elements that community detection co-clusters across at least two tier pairings (Pinheiro et al. 2026, hypermodules). Structural, undirected, and computed on the detected modules only — a reconstruction of the published method; see the spec.", "es": "Los módulos de subsistemas agrupan elementos que la detección de comunidades coagrupa en al menos dos pares de niveles (Pinheiro et al. 2026, hipermódulos). Estructural, no dirigido y calculado solo sobre los módulos detectados: una reconstrucción del método publicado; véase la especificación.", "fr": "Les modules de sous-systèmes regroupent les éléments que la détection de communautés co-clusterise dans au moins deux paires de niveaux (Pinheiro et al. 2026, hypermodules). Structurel, non dirigé, calculé sur les seuls modules détectés — une reconstruction de la méthode publiée ; voir la spécification.", "de": "Teilsystem-Module gruppieren Elemente, die die Community-Erkennung in mindestens zwei Ebenenpaaren gemeinsam clustert (Pinheiro et al. 2026, Hypermodule). Strukturell, ungerichtet und nur auf den erkannten Modulen berechnet — eine Rekonstruktion der publizierten Methode; siehe Spezifikation.", "lt": "Posistemių moduliai grupuoja elementus, kuriuos bendruomenių aptikimas sugrupuoja bent dviejose pakopų porose (Pinheiro et al. 2026, hipermoduliai). Struktūrinis, nekryptinis, skaičiuojamas tik pagal aptiktus modulius — publikuoto metodo rekonstrukcija; žr. specifikaciją.", "pt": "Os módulos de subsistemas agrupam elementos que a deteção de comunidades coagrupa em pelo menos dois pares de níveis (Pinheiro et al. 2026, hipermódulos). Estrutural, não direcionado e calculado apenas sobre os módulos detetados — uma reconstrução do método publicado; ver a especificação.", "it": "I moduli di sottosistemi raggruppano elementi che il rilevamento di comunità co-raggruppa in almeno due coppie di livelli (Pinheiro et al. 2026, ipermoduli). Strutturale, non orientato e calcolato solo sui moduli rilevati — una ricostruzione del metodo pubblicato; vedere la specifica.", "no": "Delsystemmoduler grupperer elementer som fellesskapsdeteksjon samklynger i minst to nivåpar (Pinheiro et al. 2026, hypermoduler). Strukturelt, urettet og beregnet kun på de detekterte modulene — en rekonstruksjon av den publiserte metoden; se spesifikasjonen.", "el": "Οι ενότητες υποσυστημάτων ομαδοποιούν στοιχεία που η ανίχνευση κοινοτήτων συνομαδοποιεί σε τουλάχιστον δύο ζεύγη βαθμίδων (Pinheiro et al. 2026, υπερενότητες). Δομικός, μη κατευθυνόμενος, υπολογιζόμενος μόνο στις εντοπισμένες ενότητες — ανακατασκευή της δημοσιευμένης μεθόδου· βλ. την προδιαγραφή."},
```

- [ ] **Step 6: Run the module tests, then the full unit gate**

```bash
micromamba run -n shiny python -m pytest tests/test_metrics_hypermodules.py -q
micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' \
  --ignore=tests/test_burger.py --ignore=tests/test_stepper.py \
  --ignore=tests/test_stepper_click.py
```

Expected: 2 PASS; suite total **588 passed** (576 + 10 from Task 1 + 2 here).

- [ ] **Step 7: Extend the metrics e2e (renders + fires, cascade-style)**

The cascade precedent is e2e-driven (`tests/test_metrics_e2e.py:134` clicks
`#metrics-run_cascade`); "the block renders" gets the same automated
coverage, not only the manual look. In `tests/test_metrics_e2e.py`, directly
after the cascade section (its `print(f"cascade vulnerability block: OK` line)
and BEFORE the "Causal pathways" section, insert — matching the file's async
idiom exactly:

```python
        # --- SES subsystem modules: idle hint, then button-triggered list ---
        hm_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            hm_text = (await page.inner_text("#metrics-hypermodules_summary")).strip()
            if hm_text:
                break
        assert "SES subsystem modules" in hm_text, f"expected heading, got: {hm_text!r}"
        assert "not computed" in hm_text, f"expected idle hint, got: {hm_text!r}"
        await page.click("#metrics-run_hypermodules")
        for _ in range(30):
            await page.wait_for_timeout(500)
            hm_text = (await page.inner_text("#metrics-hypermodules_summary")).strip()
            if "HM0" in hm_text:
                break
        # Sample golden: 2 hypermodules, score 0.53 (see the unit golden).
        assert "2 subsystem module" in hm_text, f"expected count line, got: {hm_text!r}"
        assert "0.53" in hm_text, f"expected score, got: {hm_text!r}"
        assert "HM0" in hm_text and "HM1" in hm_text, f"expected both modules, got: {hm_text!r}"
        print(f"hypermodules block: OK ({hm_text[:120]!r})")
```

Add `tests/test_metrics_e2e.py` to Step 8's `git add`. The e2e count stays
32/32 — this extends an existing script.

- [ ] **Step 8: Look at the panel**

The unit tests cannot see a broken block. Start the server DETACHED — a
foreground `shiny run` never returns and ending your turn ends your
participation:

```powershell
Start-Process -FilePath "cmd.exe" -ArgumentList "/c","micromamba run -n shiny shiny run --port 8000 app.py" -WindowStyle Hidden
```

Wait ~20s, open http://127.0.0.1:8000 → **Network Metrics**, click
**Detect subsystem modules**, and confirm: the block appears below Causal
pathways; two hypermodule lines render with tier compositions and labels;
the score line reads "2 subsystem module(s); 0.53 …". Then stop it:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

- [ ] **Step 9: Commit**

```bash
git add sespy/modules/analysis_metrics.py sespy/translations/core.json tests/test_metrics_hypermodules.py tests/test_metrics_e2e.py
git commit -m "feat(metrics): SES subsystem modules block (#24)

Button-gated per the card's convention; every degenerate note has a
translated explanation, so a zero result is never a bare empty table."
```

---

## Final gate — before merging

Run in order, never concurrently:

1. Unit (CI ignore-set): expect **588 passed**.
2. Kill anything on port 8000, then `micromamba run -n shiny python tests/run_e2e.py` — expect **32/32** (the Network Metrics card changes shape; `tests/test_metrics_e2e.py` drives it). Launch detached, ~10 minutes.
3. MosaicSES: `cd ../MosaicSES && micromamba run -n shiny python -m pytest tests/ -q` — expect **526 passed** (it does not import `hypermodules`; cheap insurance). Never `-k "not e2e"`.

## Done means

- Clicking one button on the Network Metrics card lists the model's multi-tier subsystems with tier composition and member labels, or explains in the user's language exactly why there are none.
- On the shipped sample: 2 hypermodules, score 0.53 — not the zero the flat threshold measures.
- The result is bit-identical across runs, processes, and ISA construction order.
- 588 unit, 32/32 e2e, MosaicSES 526.

## Explicitly out of scope

Everything the spec's Out of scope lists: strength-weighted modularity, Louvain/`algorithm=`, changes to `_SUBSYSTEM`/`subsystem()`/`social_ecological_fit`/`governance_gap`, pyvis visualisation, MosaicSES surfacing, verifying the reconstruction against the paper, enriching `data/sample_ses.json`.
