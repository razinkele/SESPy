# Leverage depth + Adjusted Loop Centrality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SESPy's Meadows realm classification loop-aware and add a polarity-signed Adjusted Loop Centrality beside the leverage composite, without changing `leverage_scores()`.

**Architecture:** Three pure additions to `sespy/network.py` — a `loop_gain()` helper lifted out of `loop_dominance`, `adjusted_loop_centrality()` built on it, and `leverage_realms()` layering one structural rule over the existing `leverage_realm()`. The Leverage module enumerates loops once and passes the same list to both. Nothing downstream changes signature.

**Tech Stack:** Python 3.13, networkx 3.6, numpy, Shiny for Python, pytest.

**Spec:** `docs/superpowers/specs/2026-09-03-leverage-depth-alc-design.md` — read it first. It records why this deviates from issue #23 as filed, and two measured hazards (ALC sign instability above the loop cap; the existing `loop_dominance` tests being a weak net for this refactor).

## Global Constraints

- Python runs ONLY as `micromamba run -n shiny <cmd>`. There is no other Python on this machine. Never create a venv.
- Unit gate: `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`. Baseline before this work: **559 passed**.
- Full e2e gate: `micromamba run -n shiny python tests/run_e2e.py` — expect **32/32**. Kill anything on port 8000 first. It takes ~10 minutes; launch it detached, never in a blocking foreground call that outlives your turn.
- `leverage_scores()` must not change — signature, formula, or return type. Its consumers are `sespy/modules/analysis_leverage.py:143`, `sespy/report.py:203`, `cascade_vulnerability` (`sespy/network.py:563`), `uncertainty_scores`' perturbation loop (`sespy/network.py:1254`), and MosaicSES.
- `leverage_realm(element_type)` must not change. It stays pure and type-only.
- **`build/` is git-ignored but present in the working tree with a stale copy of the package.** A bare `grep -rn X .` returns `build/lib/sespy/...` hits whose line numbers do not match the source. Scope every grep to `sespy/` and `tests/`.
- New i18n keys need all nine languages: en, es, fr, de, lt, pt, it, no, el.
- Do not bump the version and do not tag.

---

## File structure

| File | Responsibility | Tasks |
|---|---|---|
| `sespy/network.py` | `LOOP_ENUMERATION_CAP`, `loop_gain`, `adjusted_loop_centrality`, `alc_is_truncated`, `leverage_realms` | 1, 2, 3 |
| `tests/test_network.py` | unit tests for all four | 1, 2, 3 |
| `sespy/modules/analysis_leverage.py` | wires the three into the Leverage table + caption | 4 |
| `sespy/translations/core.json` | two new keys × 9 languages | 4 |
| `tests/test_leverage_module.py` | module-level assertions (**new file**) | 4 |

---

### Task 1: Extract `loop_gain` from `loop_dominance`

**Why first:** Tasks 2 and 3 both need it, and this task must prove the extraction is behaviour-preserving before anything builds on it.

**Files:**
- Modify: `sespy/network.py` — add `loop_gain` above `loop_dominance` (which begins at `:179`); replace the inline gain loop at `:226-231`
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `loop_gain(cycle: list[str], M, pos: dict[str, int]) -> float` — the **signed** product of matrix entries around the cycle. Tasks 2 and 3 call it with the matrix from `isa_to_numeric_matrix(isa)` and `pos = {n: i for i, n in enumerate(mat_ids)}`.

**Critical:** `loop_dominance` uses `isa_to_numeric_matrix` (`sespy/network.py:206`), **not** `isa_to_dynamics_matrix`. v1.4.0 fixed a direction bug in which the latter is the *transpose* of the former. Passing the wrong matrix silently changes every gain and the existing tests will mostly not notice — see Step 1's 3-cycle test, which is the guard.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def _three_cycle_isa():
    """A 3-cycle with one negative edge -> Balancing, and asymmetric enough
    that the numeric matrix and its transpose give DIFFERENT products.
    A 2-cycle cannot catch a transpose error; this can."""
    from sespy.data_structure import IsaData, Element, Connection
    els = [Element(id=n, label=n, type="Drivers") for n in ("A", "B", "C")]
    cons = [
        Connection(source="A", target="B", polarity="+", strength="strong"),
        Connection(source="B", target="C", polarity="+", strength="medium"),
        Connection(source="C", target="A", polarity="-", strength="weak"),
    ]
    return IsaData(elements=els, connections=cons)


def test_loop_gain_sign_matches_loop_polarity():
    """The sign IS the polarity. Scoped to fixtures with no parallel edges:
    the numeric matrix SUMS connections sharing a (source, target) pair while
    loop_polarity reads a last-wins dict, so the two can disagree there."""
    from sespy.dynamics import isa_to_numeric_matrix
    from sespy.network import loop_gain, loop_polarity, feedback_loops

    for isa in (_two_loop_isa(), _three_cycle_isa()):
        M, mat_ids = isa_to_numeric_matrix(isa)
        pos = {n: i for i, n in enumerate(mat_ids)}
        cycles = feedback_loops(isa)
        assert cycles, "fixture must have loops"
        for c in cycles:
            g = loop_gain(c, M, pos)
            assert g != 0.0
            expected = "Reinforcing" if g > 0 else "Balancing"
            assert loop_polarity(c, isa) == expected, (c, g)


def test_loop_gain_is_orientation_sensitive_on_a_three_cycle():
    """Guards the transpose hazard: loop_gain must use isa_to_numeric_matrix.
    On a 2-cycle both orientations give the same product, so only a 3-cycle
    can detect the error."""
    from sespy.dynamics import isa_to_numeric_matrix
    from sespy.network import loop_gain, feedback_loops

    isa = _three_cycle_isa()
    M, mat_ids = isa_to_numeric_matrix(isa)
    pos = {n: i for i, n in enumerate(mat_ids)}
    c = feedback_loops(isa)[0]
    forward = loop_gain(c, M, pos)
    transposed = loop_gain(c, M.T, pos)
    assert forward != transposed, (
        "fixture is transpose-invariant and cannot guard the orientation")
    assert forward < 0, "one negative edge -> Balancing -> negative product"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "loop_gain"
```

Expected: FAIL with `ImportError: cannot import name 'loop_gain' from 'sespy.network'`.

- [ ] **Step 3: Add the helper**

In `sespy/network.py`, directly above `def loop_dominance(` (`:179`):

```python
def loop_gain(cycle: list[str], M, pos: dict[str, int]) -> float:
    """Signed product of the edge weights around `cycle`.

    The SIGN is the polarity: an even number of negative edges gives a
    positive product, which is the rule loop_polarity() applies. That
    correspondence holds only where no two connections share a
    (source, target) pair — the matrix SUMS parallel edges while
    loop_polarity() reads a last-wins dict — and a zero product (cancelling
    parallel edges) carries no polarity at all.

    Takes the PREPARED matrix and its id->index mapping rather than an
    IsaData, so one matrix is shared across every cycle at a call site.

    `M` must come from isa_to_numeric_matrix, NOT isa_to_dynamics_matrix:
    v1.4.0 established that the latter is its transpose, and passing it here
    would silently change every gain.
    """
    g = 1.0
    for i in range(len(cycle)):
        g *= float(M[pos[cycle[i]], pos[cycle[(i + 1) % len(cycle)]]])
    return g
```

- [ ] **Step 4: Use it in `loop_dominance`**

In `sespy/network.py`, replace this block (currently `:225-231`):

```python
    mpos = {n: i for i, n in enumerate(mat_ids)}
    structural: list[float] = []
    for c in cyc:
        g = 1.0
        for i in range(len(c)):
            g *= float(M[mpos[c[i]], mpos[c[(i + 1) % len(c)]]])
        structural.append(abs(g))
```

with:

```python
    mpos = {n: i for i, n in enumerate(mat_ids)}
    # abs(): loop_dominance ranks by magnitude. The sign is the polarity and
    # is what adjusted_loop_centrality uses instead.
    structural: list[float] = [abs(loop_gain(c, M, mpos)) for c in cyc]
```

- [ ] **Step 5: Run the new tests, then every `loop_dominance` test**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "loop_gain or loop_dominance"
```

Expected: the two new tests PASS, and all 11 existing `loop_dominance` tests still pass unchanged. **If any `loop_dominance` test moves, the extraction is wrong — do not re-baseline it.** Note those tests are assertions, not goldens, and no RNG is involved.

- [ ] **Step 6: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "refactor(network): extract loop_gain, keeping the sign

loop_dominance discarded the sign via abs(); adjusted_loop_centrality needs
it. One definition, two views."
```

---

### Task 2: `adjusted_loop_centrality` and `alc_is_truncated`

**Files:**
- Modify: `sespy/network.py` — add `LOOP_ENUMERATION_CAP` near `feedback_loops` (`:44`); add both functions after `loop_gain`
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `loop_gain(cycle, M, pos)` from Task 1
- Produces:
  - `adjusted_loop_centrality(isa: IsaData, *, cycles: list[list[str]] | None = None) -> dict[str, float]` — every element id present; `0.0` when the node is in no detected loop or its gains cancel
  - `alc_is_truncated(isa: IsaData, *, cycles: list[list[str]] | None = None) -> bool`
  - `LOOP_ENUMERATION_CAP: int = 50`

**Why the cap is extracted into a constant:** `alc_is_truncated` must compare against exactly the number `feedback_loops` uses as its `max_loops` default. Two independent literals would drift silently, and the failure mode is an ALC column shown with an unstable sign.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def _reinforcing_and_balancing_isa():
    """X is in a Reinforcing 2-cycle; Y is in a Balancing 2-cycle; Z is in
    neither."""
    from sespy.data_structure import IsaData, Element, Connection
    els = [Element(id=n, label=n, type="Drivers")
           for n in ("X1", "X2", "Y1", "Y2", "Z")]
    cons = [
        Connection(source="X1", target="X2", polarity="+", strength="strong"),
        Connection(source="X2", target="X1", polarity="+", strength="strong"),
        Connection(source="Y1", target="Y2", polarity="+", strength="strong"),
        Connection(source="Y2", target="Y1", polarity="-", strength="strong"),
    ]
    return IsaData(elements=els, connections=cons)


def test_alc_signs_follow_loop_polarity():
    from sespy.network import adjusted_loop_centrality

    alc = adjusted_loop_centrality(_reinforcing_and_balancing_isa())
    assert alc["X1"] > 0 and alc["X2"] > 0, "reinforcing -> positive"
    assert alc["Y1"] < 0 and alc["Y2"] < 0, "balancing -> negative"
    assert alc["Z"] == 0.0, "in no loop -> exactly zero"


def test_alc_covers_every_element_and_handles_no_loops():
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import adjusted_loop_centrality

    els = [Element(id=n, label=n, type="Drivers") for n in ("A", "B")]
    isa = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", strength="strong")])
    alc = adjusted_loop_centrality(isa)
    assert set(alc) == {"A", "B"}
    assert all(v == 0.0 for v in alc.values())
    assert adjusted_loop_centrality(IsaData(elements=[], connections=[])) == {}


def test_alc_sums_over_every_loop_a_node_is_in():
    """A node in two reinforcing loops scores more than in one."""
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import adjusted_loop_centrality

    els = [Element(id=n, label=n, type="Drivers") for n in ("H", "P", "Q")]
    isa = IsaData(elements=els, connections=[
        Connection(source="H", target="P", polarity="+", strength="strong"),
        Connection(source="P", target="H", polarity="+", strength="strong"),
        Connection(source="H", target="Q", polarity="+", strength="strong"),
        Connection(source="Q", target="H", polarity="+", strength="strong"),
    ])
    alc = adjusted_loop_centrality(isa)
    assert alc["H"] > alc["P"] > 0
    assert alc["P"] == alc["Q"]


def test_alc_truncation_flag_tracks_the_enumeration_cap():
    """Above the cap the detected subset varies between processes, so the ALC
    sign is not reproducible. The flag is what suppresses the column."""
    from sespy.network import alc_is_truncated, LOOP_ENUMERATION_CAP
    from sespy.data_structure import IsaData

    isa = IsaData(elements=[], connections=[])
    assert alc_is_truncated(isa, cycles=[]) is False
    under = [["A", "B"]] * (LOOP_ENUMERATION_CAP - 1)
    assert alc_is_truncated(isa, cycles=under) is False
    at_cap = [["A", "B"]] * LOOP_ENUMERATION_CAP
    assert alc_is_truncated(isa, cycles=at_cap) is True


def test_loop_enumeration_cap_matches_feedback_loops_default():
    """Two literals would drift, and the failure mode is a wrongly-signed
    column shown to the user."""
    import inspect
    from sespy.network import feedback_loops, LOOP_ENUMERATION_CAP

    default = inspect.signature(feedback_loops).parameters["max_loops"].default
    assert default == LOOP_ENUMERATION_CAP
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "alc or loop_enumeration_cap"
```

Expected: FAIL with `ImportError: cannot import name 'adjusted_loop_centrality' from 'sespy.network'`.

- [ ] **Step 3: Extract the cap constant**

In `sespy/network.py`, immediately above `def feedback_loops(` (`:44`):

```python
#: Ceiling on enumerated cycles. Above it the detected subset is not
#: reproducible across processes (see _canonical_cycles' note on hash
#: seeding), which is why adjusted_loop_centrality reports truncation.
LOOP_ENUMERATION_CAP = 50
```

Then change `feedback_loops`' signature to use it, so the two cannot drift:

```python
def feedback_loops(
    isa: IsaData, *, max_length: int = 6, max_loops: int = LOOP_ENUMERATION_CAP
) -> list[list[str]]:
```

- [ ] **Step 4: Add both functions**

In `sespy/network.py`, after `loop_gain`:

```python
def adjusted_loop_centrality(
    isa: IsaData, *, cycles: list[list[str]] | None = None
) -> dict[str, float]:
    """Per-node sum of the SIGNED gains of every detected loop it is in.

    Positive: the node sits in amplifying structure. Negative: damping.
    0.0: in no detected loop, OR its loop gains cancel.

    Only meaningful when the loop set is complete — see alc_is_truncated().
    """
    from .dynamics import isa_to_numeric_matrix  # local: dynamics imports network

    alc: dict[str, float] = {el.id: 0.0 for el in isa.elements}
    cyc = _canonical_cycles(
        cycles if cycles is not None else feedback_loops(isa))
    if not cyc or not alc:
        return alc

    M, mat_ids = isa_to_numeric_matrix(isa)
    pos = {n: i for i, n in enumerate(mat_ids)}
    for c in cyc:
        if any(n not in pos for n in c):
            continue        # a caller-injected cycle naming unknown nodes
        g = loop_gain(c, M, pos)
        for n in set(c):    # set(): never count a node twice for one loop
            if n in alc:
                alc[n] += g
    return alc


def alc_is_truncated(
    isa: IsaData, *, cycles: list[list[str]] | None = None
) -> bool:
    """True when loop enumeration hit LOOP_ENUMERATION_CAP, so an ALC sum over
    the detected subset is not reproducible across processes and must not be
    shown as a signed number."""
    cyc = cycles if cycles is not None else feedback_loops(isa)
    return len(cyc) >= LOOP_ENUMERATION_CAP
```

- [ ] **Step 5: Run the new tests, then the whole network suite**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q
```

Expected: the five new tests PASS and nothing else moves.

- [ ] **Step 6: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): adjusted loop centrality, signed by loop polarity

Sums the signed gain of every detected loop a node is in. Ships with
alc_is_truncated: above the enumeration cap the detected subset varies
between processes and the sign is not reproducible."
```

---

### Task 3: `leverage_realms` — the one structural rule

**Files:**
- Modify: `sespy/network.py` — add after `leverage_realm` (`:684`)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `feedback_loops`, `_canonical_cycles`, `leverage_realm`
- Produces: `leverage_realms(isa: IsaData, *, cycles: list[list[str]] | None = None) -> dict[str, str]` — realm token per element id; `""` for unknown types, exactly as `leverage_realm` returns today

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py`:

```python
def test_leverage_realms_promotes_an_activity_inside_a_loop():
    """The one structural rule: an Activity in a detected loop acts at the
    feedback level, not the design level."""
    from sespy.data_structure import IsaData, Element, Connection
    from sespy.network import leverage_realms, leverage_realm

    els = [Element(id="ACT", label="ACT", type="Activities"),
           Element(id="PR", label="PR", type="Pressures")]
    looped = IsaData(elements=els, connections=[
        Connection(source="ACT", target="PR", polarity="+", strength="strong"),
        Connection(source="PR", target="ACT", polarity="+", strength="strong"),
    ])
    assert leverage_realms(looped)["ACT"] == "feedbacks"

    # Same Activity, loop broken -> falls back to the type-based mapping.
    unlooped = IsaData(elements=els, connections=[
        Connection(source="ACT", target="PR", polarity="+", strength="strong"),
    ])
    assert leverage_realms(unlooped)["ACT"] == "design"
    assert leverage_realm("Activities") == "design", "the pure fn is untouched"


def test_leverage_realms_agrees_with_leverage_realm_for_every_other_type():
    from sespy.network import leverage_realms, leverage_realm
    from sespy.data_structure import load_sample
    from pathlib import Path

    isa = load_sample(Path(__file__).resolve().parents[1] / "data" / "sample_ses.json")
    realms = leverage_realms(isa)
    by_id = {el.id: el for el in isa.elements}
    assert set(realms) == set(by_id)
    for nid, realm in realms.items():
        if by_id[nid].type != "Activities":
            assert realm == leverage_realm(by_id[nid].type), nid


def test_leverage_realms_handles_no_loops_and_unknown_types():
    from sespy.data_structure import IsaData, Element
    from sespy.network import leverage_realms

    isa = IsaData(elements=[Element(id="M", label="M", type="Measures")],
                  connections=[])
    assert leverage_realms(isa) == {"M": ""}
    assert leverage_realms(IsaData(elements=[], connections=[])) == {}
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q -k "leverage_realms"
```

Expected: FAIL with `ImportError: cannot import name 'leverage_realms' from 'sespy.network'`.

- [ ] **Step 3: Add the function**

In `sespy/network.py`, directly after `leverage_realm` (`:684-688`):

```python
def leverage_realms(
    isa: IsaData, *, cycles: list[list[str]] | None = None
) -> dict[str, str]:
    """Meadows realm per element id, with ONE structural refinement over the
    type-only leverage_realm(): an Activity that participates in a detected
    feedback loop reports 'feedbacks' instead of 'design'.

    Everything else — every other type, and an Activity in no loop — is
    exactly leverage_realm(el.type).

    "Detected" is bounded by feedback_loops(): an Activity in a loop longer
    than max_length, or beyond LOOP_ENUMERATION_CAP, is not promoted. The
    realm is therefore a statement about the detected structure, not about
    the graph in the abstract.
    """
    cyc = _canonical_cycles(
        cycles if cycles is not None else feedback_loops(isa))
    in_loop = {n for c in cyc for n in c}
    return {
        el.id: ("feedbacks"
                if el.type == "Activities" and el.id in in_loop
                else leverage_realm(el.type))
        for el in isa.elements
    }
```

- [ ] **Step 4: Run the tests**

```bash
micromamba run -n shiny python -m pytest tests/test_network.py -q
```

Expected: the three new tests PASS, nothing else moves.

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): loop-aware leverage realms

An Activity inside a detected feedback loop acts at the feedback level.
leverage_realm() stays pure and type-only."
```

---

### Task 4: Wire it into the Leverage module

**Files:**
- Modify: `sespy/modules/analysis_leverage.py` — `ranked()` (`:146-163`), `leverage_table` (`:203-227`), and the UI block around `:110`
- Modify: `sespy/translations/core.json` — two new keys beside the realm keys (`:5500-5503`)
- Create: `tests/test_leverage_module.py` — it does NOT exist yet; only
  `tests/test_leverage_e2e.py` does

**Interfaces:**
- Consumes: `leverage_realms(isa, cycles=…)`, `adjusted_loop_centrality(isa, cycles=…)`, `alc_is_truncated(isa, cycles=…)` from Tasks 2-3
- Produces: nothing other tasks depend on

**Note on the i18n count:** the spec says "one new key". The truncation resolution needs a second (the suppression note), so this task adds **two** keys × 9 languages. That is a deliberate consequence of the blocking finding, not scope creep.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_leverage_module.py` containing exactly these three tests (each imports what it needs inline, so the file needs no header):

```python
def test_leverage_rows_carry_realm_and_alc():
    """ranked() must expose both new fields, and the realm must be the
    loop-aware one."""
    from sespy.modules import analysis_leverage
    src = analysis_leverage.__file__
    text = open(src, encoding="utf-8").read()
    assert "leverage_realms(" in text, "must use the loop-aware realms"
    assert "adjusted_loop_centrality(" in text
    assert "alc_is_truncated(" in text
    assert "leverage_realm(" not in text.replace("leverage_realms(", ""), (
        "the per-row type-only call must be gone")


def test_leverage_enumerates_loops_once():
    """Both new calls must receive the SAME cycles list; re-enumerating per
    call would run feedback_loops three times per render."""
    from sespy.modules import analysis_leverage
    text = open(analysis_leverage.__file__, encoding="utf-8").read()
    assert text.count("feedback_loops(") == 1
    assert text.count("cycles=cycles") == 3


def test_alc_translation_keys_exist_in_every_language():
    import json
    from pathlib import Path

    core = json.loads(
        (Path(__file__).resolve().parents[1]
         / "sespy" / "translations" / "core.json").read_text(encoding="utf-8"))

    def find(node, key):
        if isinstance(node, dict):
            if key in node:
                return node[key]
            for v in node.values():
                got = find(v, key)
                if got is not None:
                    return got
        return None

    langs = {"en", "es", "fr", "de", "lt", "pt", "it", "no", "el"}
    for key in ("leverage.caption", "leverage.alc_truncated"):
        entry = find(core, key)
        assert entry is not None, f"{key} missing"
        assert langs.issubset(set(entry)), f"{key} missing languages"
        assert all(entry[l].strip() for l in langs), f"{key} has an empty value"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_leverage_module.py -q
```

Expected: FAIL — `assert "leverage_realms(" in text` fails first.

- [ ] **Step 3: Rewrite `ranked()`**

In `sespy/modules/analysis_leverage.py`, replace the whole of `ranked()` (`:146-163`) with:

```python
    def ranked() -> list[dict]:
        isa = project_data.get().isa_data
        s = scores()
        # ONE enumeration shared by both consumers: feedback_loops is bounded
        # but not free, and a per-row call would re-run it for every element.
        cycles = net_analysis.feedback_loops(isa)
        realms = net_analysis.leverage_realms(isa, cycles=cycles)
        alc = net_analysis.adjusted_loop_centrality(isa, cycles=cycles)
        truncated = net_analysis.alc_is_truncated(isa, cycles=cycles)
        by_id = {el.id: el for el in isa.elements}
        rows = sorted(s.items(), key=lambda kv: kv[1], reverse=True)
        out: list[dict] = []
        for rank, (nid, value) in enumerate(rows, start=1):
            el = by_id.get(nid)
            token = realms.get(nid, "")
            row = {
                "rank": rank,
                "id": nid,
                "label": el.label if el else nid,
                "type":  el.type if el else "",
                "realm": t(f"leverage.realm.{token}") if token else "—",
                "leverage": round(value, 3),
            }
            # Suppressed entirely when truncated: above the cap the SIGN is
            # not reproducible across processes, and the sign is the meaning.
            if not truncated:
                row["alc"] = round(alc.get(nid, 0.0), 3)
            out.append(row)
        return out[: int(input.top_n() or 8)]
```

- [ ] **Step 4: Add a truncation reactive and use it in the table**

Directly below `ranked()`, add:

```python
    @reactive.calc
    def alc_truncated() -> bool:
        isa = project_data.get().isa_data
        return net_analysis.alc_is_truncated(isa)
```

Then in `leverage_table` (`:203`), replace the `base_cols` line (`:208`):

```python
        base_cols = ["rank", "id", "label", "type", "realm", "leverage"]
```

with:

```python
        base_cols = ["rank", "id", "label", "type", "realm", "leverage"]
        if not alc_truncated():
            base_cols.insert(5, "alc")
```

- [ ] **Step 5: Add the caption output**

In the UI block, immediately after `ui.output_data_frame("leverage_table")` (`:111`):

```python
                ui.output_ui("leverage_caption"),
```

and in the server, after `leverage_table`:

```python
    @output
    @render.ui
    def leverage_caption():
        parts = [ui.p(t("leverage.caption"), class_="text-muted",
                      style="font-size: 0.85rem;")]
        if alc_truncated():
            parts.append(ui.p(t("leverage.alc_truncated"), class_="text-muted",
                              style="font-size: 0.85rem;"))
        return ui.div(*parts)
```

- [ ] **Step 6: Add the two i18n keys**

In `sespy/translations/core.json`, directly after the `leverage.realm.intent` line (`:5503`), add these two lines:

```json
    "leverage.caption": {"en": "Realm is the Meadows level an intervention would act at; an Activity inside a detected feedback loop is shown as Feedbacks rather than Design, so two Activities can differ. ALC sums the signed strength of every loop a node sits in — positive is amplifying, negative is damping, zero means no loop. It is not comparable with the leverage score beside it.", "es": "El ámbito es el nivel de Meadows en el que actuaría una intervención; una Actividad dentro de un bucle de retroalimentación detectado se muestra como Retroalimentaciones en lugar de Diseño, por lo que dos Actividades pueden diferir. ALC suma la fuerza con signo de cada bucle en el que se encuentra un nodo: positivo amplifica, negativo amortigua, cero significa ningún bucle. No es comparable con la puntuación de apalancamiento contigua.", "fr": "Le domaine est le niveau de Meadows auquel une intervention agirait ; une Activité située dans une boucle de rétroaction détectée s'affiche comme Rétroactions plutôt que Conception, deux Activités peuvent donc différer. L'ALC additionne la force signée de chaque boucle où se trouve un nœud : positif amplifie, négatif amortit, zéro signifie aucune boucle. Il n'est pas comparable au score de levier voisin.", "de": "Der Bereich ist die Meadows-Ebene, auf der ein Eingriff wirken würde; eine Aktivität innerhalb einer erkannten Rückkopplungsschleife wird als Rückkopplungen statt Gestaltung angezeigt, sodass zwei Aktivitäten abweichen können. ALC summiert die vorzeichenbehaftete Stärke jeder Schleife, in der ein Knoten liegt: positiv verstärkt, negativ dämpft, null bedeutet keine Schleife. Er ist nicht mit dem daneben stehenden Hebelwert vergleichbar.", "lt": "Sritis nurodo Meadows lygmenį, kuriame veiktų intervencija; Veikla, esanti aptiktoje grįžtamojo ryšio kilpoje, rodoma kaip Grįžtamieji ryšiai, o ne Struktūra, todėl dvi Veiklos gali skirtis. ALC sudeda kiekvienos kilpos, kuriai priklauso mazgas, ženklu pažymėtą stiprumą: teigiamas stiprina, neigiamas slopina, nulis reiškia, kad kilpos nėra. Jis nepalyginamas su šalia esančiu sverto įverčiu.", "pt": "O domínio é o nível de Meadows em que uma intervenção atuaria; uma Atividade dentro de um ciclo de retroalimentação detetado aparece como Retroalimentações em vez de Conceção, pelo que duas Atividades podem diferir. O ALC soma a força com sinal de cada ciclo em que um nó se encontra: positivo amplifica, negativo amortece, zero significa nenhum ciclo. Não é comparável com a pontuação de alavancagem ao lado.", "it": "L'ambito è il livello di Meadows su cui agirebbe un intervento; un'Attività all'interno di un anello di retroazione rilevato è mostrata come Retroazioni anziché Progettazione, quindi due Attività possono differire. L'ALC somma la forza con segno di ogni anello in cui si trova un nodo: positivo amplifica, negativo smorza, zero significa nessun anello. Non è confrontabile con il punteggio di leva accanto.", "no": "Område er Meadows-nivået et tiltak ville virke på; en Aktivitet inne i en oppdaget tilbakekoblingsløkke vises som Tilbakekoblinger i stedet for Utforming, så to Aktiviteter kan avvike. ALC summerer den fortegnssatte styrken til hver løkke en node ligger i: positiv forsterker, negativ demper, null betyr ingen løkke. Den kan ikke sammenlignes med brekkstangskåren ved siden av.", "el": "Ο τομέας είναι το επίπεδο Meadows στο οποίο θα δρούσε μια παρέμβαση· μια Δραστηριότητα εντός εντοπισμένου βρόχου ανατροφοδότησης εμφανίζεται ως Ανατροφοδοτήσεις αντί για Σχεδιασμός, οπότε δύο Δραστηριότητες μπορεί να διαφέρουν. Το ALC αθροίζει την προσημασμένη ισχύ κάθε βρόχου στον οποίο ανήκει ένας κόμβος: θετικό ενισχύει, αρνητικό αποσβένει, μηδέν σημαίνει κανένας βρόχος. Δεν είναι συγκρίσιμο με τη διπλανή βαθμολογία μόχλευσης."},
    "leverage.alc_truncated": {"en": "ALC is hidden: this model has more feedback loops than the detection limit, and a score summed over a partial loop set is not reproducible.", "es": "ALC está oculto: este modelo tiene más bucles de retroalimentación que el límite de detección, y una puntuación sumada sobre un conjunto parcial de bucles no es reproducible.", "fr": "L'ALC est masqué : ce modèle comporte plus de boucles de rétroaction que la limite de détection, et un score cumulé sur un ensemble partiel de boucles n'est pas reproductible.", "de": "ALC ist ausgeblendet: Dieses Modell hat mehr Rückkopplungsschleifen als das Erkennungslimit, und ein über eine unvollständige Schleifenmenge summierter Wert ist nicht reproduzierbar.", "lt": "ALC paslėptas: šiame modelyje grįžtamojo ryšio kilpų yra daugiau nei aptikimo riba, o įvertis, sudėtas iš dalinio kilpų rinkinio, nėra atkuriamas.", "pt": "O ALC está oculto: este modelo tem mais ciclos de retroalimentação do que o limite de deteção, e uma pontuação somada sobre um conjunto parcial de ciclos não é reproduzível.", "it": "L'ALC è nascosto: questo modello ha più anelli di retroazione del limite di rilevamento e un punteggio sommato su un insieme parziale di anelli non è riproducibile.", "no": "ALC er skjult: denne modellen har flere tilbakekoblingsløkker enn deteksjonsgrensen, og en skår summert over et delvis løkkesett er ikke reproduserbar.", "el": "Το ALC είναι κρυμμένο: αυτό το μοντέλο έχει περισσότερους βρόχους ανατροφοδότησης από το όριο εντοπισμού και μια βαθμολογία αθροισμένη σε μερικό σύνολο βρόχων δεν είναι αναπαραγώγιμη."},
```

- [ ] **Step 7: Run the module tests, then the full unit suite**

```bash
micromamba run -n shiny python -m pytest tests/test_leverage_module.py -q
micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' \
  --ignore=tests/test_burger.py --ignore=tests/test_stepper.py \
  --ignore=tests/test_stepper_click.py
```

Expected: the three module tests PASS; suite total **572 passed**
(559 baseline + 2 in Task 1 + 5 in Task 2 + 3 in Task 3 + 3 here = 13 new).

- [ ] **Step 8: Look at the panel**

The unit tests cannot see a broken table. Start the server detached — a foreground `shiny run` never returns:

```bash
# PowerShell, from the SESPy root:
Start-Process -FilePath "cmd.exe" -ArgumentList "/c","micromamba run -n shiny shiny run --port 8000 app.py" -WindowStyle Hidden
```

Wait ~20s, open http://127.0.0.1:8000, go to **Leverage Points**, and confirm: the `alc` column is present with signed values; the Realm column still reads normally; the caption appears below the table. Then stop it:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

- [ ] **Step 9: Commit**

```bash
git add sespy/modules/analysis_leverage.py sespy/translations/core.json tests/test_leverage_module.py
git commit -m "feat(leverage): loop-aware realm and an ALC column

Enumerates loops once per render and shares the list. ALC is suppressed
with a note when the model exceeds the loop-detection cap, because the
sign is not reproducible over a partial loop set."
```

---

## Final gate — before merging

Run in this order, never concurrently:

1. `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — expect **572 passed** (559 + 13).
2. Kill anything on port 8000, then `micromamba run -n shiny python tests/run_e2e.py` — expect **32/32**. Launch it detached; it takes ~10 minutes. `tests/test_leverage_e2e.py` already drives this panel, so a regression in the table shows up here.
3. MosaicSES must be unaffected — it consumes `leverage_scores()`, which this plan does not touch:
   ```bash
   cd ../MosaicSES && micromamba run -n shiny python -m pytest tests/ -q
   ```
   Expect **526 passed**. Never `-k "not e2e"` there.

## Done means

- The Leverage table shows a Realm that distinguishes an Activity inside a feedback loop from one outside it, and an ALC column whose sign says whether a node sits in amplifying or damping structure.
- On a model past the loop-detection cap the ALC column is absent and a note says why, rather than a number whose sign changes between restarts.
- `leverage_scores()` and `leverage_realm()` are byte-for-byte unchanged.
- 572 unit, 32/32 e2e, MosaicSES 526.

## Explicitly out of scope

- Changing `leverage_scores()`, the composite formula, or `governance_actor_influence`'s golden equality with it.
- Making `_DAPSIWRM_REALM` runtime-configurable (#23 asks; the spec declines under YAGNI).
- A bespoke sort control for the realm column (#23's "allow sorting by it").
- Re-classifying `Measures`, which has no `_DAPSIWRM_REALM` entry and still returns `""`.
- Modelling whether a node *initiates* versus *reinforces* a loop — ALC implements strength and polarity only.
- #24 (cross-tier hypermodule detection).
