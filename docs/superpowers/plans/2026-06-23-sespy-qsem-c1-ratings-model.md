# QSEM-C1 Ratings Model + Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-connection multi-rater `ratings` list with a derived (materialized) consensus, plus the pure functions that compute the consensus and per-connection disagreement — with zero behaviour change for existing single-author projects.

**Architecture:** `Connection` gains a `ratings: list[Rating]` field; the existing scalar `strength`/`confidence`/`polarity`/`delay` stay as a *materialized consensus* whose sole writer is `network.recompute_consensus()`. Old projects load with `ratings=[]` and untouched scalars (no auto-lift). Two pure functions live in `network.py`: `recompute_consensus` (aggregation) and `connection_disagreement` (spread/contested). No UI in this chunk.

**Tech Stack:** Python 3.11, dataclasses, pytest.

## Global Constraints

- Materialized-consensus cache: scalar `strength`/`confidence`/`polarity`/`delay` on `Connection` remain the consensus; `recompute_consensus` is their ONLY writer.
- Migration is additive, NO auto-lift: a connection with empty `ratings` keeps its authored scalars; `recompute_consensus` is a no-op on empty ratings.
- `PROJECT_SCHEMA_VERSION`: 5 → 6.
- Aggregation rule: confidence = mean rounded, clamped [1,5]; strength = confidence-weighted mean of ranks (`weak/medium/strong = 1/2/3`, reuse `network._STRENGTH_RANK`), rounded, mapped back (plain mean if total weight 0); polarity = majority, exact tie → `"+"`; delay = mode, ties by first occurrence.
- Existing analysis readers (`_edge_weight`, `influence_dependence`, `leverage_scores`, metrics, simplify, loops, `uncertainty_scores`) MUST stay byte-for-byte unchanged.
- Valid delay values: `immediate | short | long` (`constants.DELAY_LEVELS`).
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `Rating` dataclass + `Connection.ratings` + migration

**Files:**
- Modify: `sespy/data_structure.py` (add `Rating` before `Connection` ~line 94; add `ratings` field to `Connection`; bump `PROJECT_SCHEMA_VERSION` line 19; update `_isa_from_dict` ~line 128)
- Test: `tests/test_data_structure.py`

**Interfaces:**
- Produces:
  - `Rating(rater_id: str, strength="medium", confidence=3, polarity="+", delay="immediate")`
  - `Connection(..., ratings: list[Rating] = [])` (field appended last)
  - `PROJECT_SCHEMA_VERSION == 6`

- [ ] **Step 1: Update the existing version test and write new failing tests**

In `tests/test_data_structure.py`, change the existing `test_schema_version_is_5`:

```python
def test_schema_version_is_6():
    assert PROJECT_SCHEMA_VERSION == 6
```

Add to the imports at the top of the file: `Connection`, `IsaData`, `Rating` from `sespy.data_structure` (extend the existing import block). Then add:

```python
def test_connection_ratings_round_trip():
    conn = Connection(
        source="A", target="B", polarity="+", strength="strong", confidence=4,
        ratings=[
            Rating(rater_id="s1", strength="strong", confidence=5, polarity="+"),
            Rating(rater_id="s2", strength="weak", confidence=2, polarity="-"),
        ],
    )
    project = Project(metadata=ProjectMetadata(name="R"), isa_data=IsaData(connections=[conn]))
    restored = Project.from_dict(json.loads(project.to_json()))
    rc = restored.isa_data.connections[0]
    assert len(rc.ratings) == 2
    assert all(isinstance(r, Rating) for r in rc.ratings)
    assert rc.ratings[0].rater_id == "s1"
    assert rc.ratings[1].polarity == "-"


def test_v5_project_loads_without_ratings():
    payload = {
        "metadata": {"name": "Legacy", "schema_version": 5},
        "isa_data": {
            "elements": [],
            "connections": [{"source": "A", "target": "B", "polarity": "-",
                             "strength": "weak", "confidence": 2, "delay": "short"}],
        },
    }
    restored = Project.from_dict(payload)
    c = restored.isa_data.connections[0]
    assert c.ratings == []
    assert (c.polarity, c.strength, c.confidence, c.delay) == ("-", "weak", 2, "short")
    assert restored.metadata.schema_version == 6


def test_connection_unknown_keys_filtered():
    payload = {
        "isa_data": {"elements": [], "connections": [
            {"source": "A", "target": "B", "future_field": 99,
             "ratings": [{"rater_id": "s1", "confidence": 3, "junk": 1}]}
        ]},
    }
    restored = Project.from_dict(payload)
    c = restored.isa_data.connections[0]
    assert c.source == "A" and c.target == "B"
    assert len(c.ratings) == 1 and c.ratings[0].rater_id == "s1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_data_structure.py -k "ratings or schema_version_is_6 or v5_project or unknown_keys" -v`
Expected: FAIL — `ImportError`/`cannot import name 'Rating'` (and the version assertion).

- [ ] **Step 3: Implement the schema changes**

In `sespy/data_structure.py`:

(a) Bump the version (line 19):
```python
PROJECT_SCHEMA_VERSION = 6
```

(b) Add `Rating` immediately before the `Connection` dataclass:
```python
@dataclass
class Rating:
    """One stakeholder's rating of a connection. `rater_id` keys to a
    Stakeholder.id (free-form for now)."""
    rater_id: str
    strength: str = "medium"     # weak | medium | strong
    confidence: int = 3
    polarity: str = "+"          # "+" | "-"
    delay: str = "immediate"     # immediate | short | long
```

(c) Append the `ratings` field to `Connection` (after `delay`):
```python
@dataclass
class Connection:
    source: str
    target: str
    polarity: str = "+"
    strength: str = "medium"
    confidence: int = 3
    delay: str = "immediate"
    ratings: list["Rating"] = field(default_factory=list)
```

(d) Replace `_isa_from_dict` so it hydrates nested ratings and filters unknown connection keys:
```python
def _isa_from_dict(raw: dict[str, Any]) -> IsaData:
    elements = [Element(**e) for e in raw.get("elements", [])]
    conn_keys = {f.name for f in fields(Connection)} - {"ratings"}
    rating_keys = {f.name for f in fields(Rating)}
    connections = []
    for c in raw.get("connections", []):
        ratings = [
            Rating(**{k: v for k, v in r.items() if k in rating_keys})
            for r in (c.get("ratings") or [])
        ]
        conn_fields = {k: v for k, v in c.items() if k in conn_keys}
        connections.append(Connection(ratings=ratings, **conn_fields))
    return IsaData(elements=elements, connections=connections)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_data_structure.py -v`
Expected: PASS (the whole file, including the renamed version test).

- [ ] **Step 5: Commit**

```bash
git add sespy/data_structure.py tests/test_data_structure.py
git commit -m "feat(schema): Connection.ratings + Rating model + migration (schema v6)"
```

---

### Task 2: `recompute_consensus`

**Files:**
- Modify: `sespy/network.py` (add `recompute_consensus` near `_edge_weight`/`_STRENGTH_RANK`, ~line 330)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `Connection`, `Rating` (from `sespy.data_structure`); `network._STRENGTH_RANK`; `dataclasses.replace` (already imported in network.py).
- Produces: `recompute_consensus(connection: Connection) -> Connection` (pure; copy with consensus scalars; no-op on empty ratings).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py` (the `Rating` import may need adding to the existing `from sespy.data_structure import ...` line):

```python
def test_recompute_consensus_empty_is_noop():
    from sespy.data_structure import Connection
    c = Connection(source="A", target="B", polarity="-", strength="strong", confidence=5, delay="long")
    out = network.recompute_consensus(c)
    assert (out.polarity, out.strength, out.confidence, out.delay) == ("-", "strong", 5, "long")
    assert out is not c  # returns a copy


def test_recompute_consensus_confidence_weighted_strength():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", strength="weak", confidence=5, polarity="+"),
        Rating(rater_id="s2", strength="strong", confidence=1, polarity="+"),
    ])
    out = network.recompute_consensus(c)
    # weighted rank = (1*5 + 3*1)/6 = 1.33 -> rank 1 -> "weak"; conf = round((5+1)/2)=3
    assert out.strength == "weak"
    assert out.confidence == 3
    assert out.polarity == "+"


def test_recompute_consensus_majority_and_tie_polarity():
    from sespy.data_structure import Connection, Rating
    maj = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="+"),
        Rating(rater_id="c", polarity="-"),
    ]))
    assert maj.polarity == "+"
    tie = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="-"),
    ]))
    assert tie.polarity == "+"  # exact tie -> "+"


def test_recompute_consensus_delay_mode():
    from sespy.data_structure import Connection, Rating
    out = network.recompute_consensus(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", delay="short"), Rating(rater_id="b", delay="short"),
        Rating(rater_id="c", delay="immediate"),
    ]))
    assert out.delay == "short"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "recompute_consensus" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'recompute_consensus'`.

- [ ] **Step 3: Implement `recompute_consensus`**

Add to `sespy/network.py` (near `_edge_weight`; `replace` is already imported, add `from collections import Counter` at the top of the file if absent):

```python
_RANK_TO_STRENGTH = {1: "weak", 2: "medium", 3: "strong"}


def recompute_consensus(connection):
    """Return a copy of `connection` with scalar strength/confidence/polarity/
    delay rewritten as the consensus of its `ratings`. No-op (equivalent copy)
    when there are no ratings. The SOLE writer of the consensus scalars.

    confidence = mean rounded, clamped [1,5]; strength = confidence-weighted
    mean of ranks (plain mean if total weight 0); polarity = majority, tie -> '+';
    delay = mode (ties by first occurrence)."""
    ratings = connection.ratings
    if not ratings:
        return replace(connection)

    confs = [max(1, min(5, int(r.confidence))) for r in ratings]
    confidence = max(1, min(5, round(sum(confs) / len(confs))))

    ranks = [_STRENGTH_RANK.get(r.strength, 2) for r in ratings]
    wsum = sum(confs)
    avg = (sum(rk * c for rk, c in zip(ranks, confs)) / wsum) if wsum > 0 \
        else (sum(ranks) / len(ranks))
    strength = _RANK_TO_STRENGTH[max(1, min(3, round(avg)))]

    n_plus = sum(1 for r in ratings if r.polarity == "+")
    polarity = "+" if n_plus >= (len(ratings) - n_plus) else "-"

    counts = Counter(r.delay for r in ratings)
    top = max(counts.values())
    delay = next(r.delay for r in ratings if counts[r.delay] == top)

    return replace(connection, strength=strength, confidence=confidence,
                   polarity=polarity, delay=delay)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "recompute_consensus" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): recompute_consensus — materialized rating consensus"
```

---

### Task 3: `connection_disagreement`

**Files:**
- Modify: `sespy/network.py` (add `connection_disagreement` after `recompute_consensus`)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `Connection`, `Rating`; `network._STRENGTH_RANK`.
- Produces: `connection_disagreement(connection: Connection) -> dict` with keys `polarity_contested: bool`, `strength_spread: float`, `confidence_spread: float`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py`:

```python
def test_disagreement_polarity_split_is_contested():
    from sespy.data_structure import Connection, Rating
    d = network.connection_disagreement(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", strength="weak", confidence=2, polarity="+"),
        Rating(rater_id="b", strength="strong", confidence=5, polarity="-"),
    ]))
    assert d["polarity_contested"] is True
    assert d["strength_spread"] == 2.0   # rank 3 - rank 1
    assert d["confidence_spread"] == 3.0  # 5 - 2


def test_disagreement_unanimous_not_contested():
    from sespy.data_structure import Connection, Rating
    d = network.connection_disagreement(Connection(source="A", target="B", ratings=[
        Rating(rater_id="a", polarity="+"), Rating(rater_id="b", polarity="+"),
    ]))
    assert d["polarity_contested"] is False


def test_disagreement_under_two_ratings_is_zero():
    from sespy.data_structure import Connection, Rating
    one = network.connection_disagreement(Connection(source="A", target="B",
        ratings=[Rating(rater_id="a", polarity="-")]))
    assert one == {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}
    none = network.connection_disagreement(Connection(source="A", target="B"))
    assert none == {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "disagreement" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'connection_disagreement'`.

- [ ] **Step 3: Implement `connection_disagreement`**

Add to `sespy/network.py` after `recompute_consensus`:

```python
def connection_disagreement(connection) -> dict:
    """Per-connection rater divergence (pure; computed on demand, not stored).

    polarity_contested: ratings not unanimous in sign (False for <2 ratings).
    strength_spread / confidence_spread: max-min over rating ranks / confidences
    (0.0 for <2 ratings)."""
    ratings = connection.ratings
    if len(ratings) < 2:
        return {"polarity_contested": False, "strength_spread": 0.0,
                "confidence_spread": 0.0}
    ranks = [_STRENGTH_RANK.get(r.strength, 2) for r in ratings]
    confs = [max(1, min(5, int(r.confidence))) for r in ratings]
    return {
        "polarity_contested": len({r.polarity for r in ratings}) > 1,
        "strength_spread": float(max(ranks) - min(ranks)),
        "confidence_spread": float(max(confs) - min(confs)),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "disagreement" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): connection_disagreement — per-connection rater divergence"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: previous baseline (352 passed, 1 skipped) + the new schema/network tests, all passing; the renamed `test_schema_version_is_6` passes.
- [ ] No behaviour change for existing data: `_edge_weight`, `influence_dependence`, `leverage_scores` produce identical results on single-author fixtures (covered by the existing network/quadrant tests staying green, since empty `ratings` leaves scalars untouched).
- [ ] e2e unaffected (data-layer-only change, no UI): a spot-run of `tests/test_data_entry_e2e.py` + `tests/test_import_e2e.py` still passes (these exercise connection persistence). Full e2e not required for a no-UI change, but run these two as a guard.
- [ ] `recompute_consensus` is the only writer of the consensus scalars (nothing in C1 calls it automatically; grep confirms no other assignment to `connection.strength/.confidence/.polarity/.delay`).
