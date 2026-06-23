# Uncertainty-aware Leverage & Loop Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a D2D-faithful structural Monte Carlo that propagates edge `confidence` into leverage scores (as CIs) and feedback-loop classification (as existence/polarity probabilities with a "contested" flag), surfaced behind an off-by-default toggle in the Leverage and Loop Analysis modules.

**Architecture:** One new pure function `uncertainty_scores()` in `sespy/network.py` plus a private `_perturbed_connections()` generator. Each Monte Carlo draw independently drops and/or flips the polarity of every edge with probability `base·(5−conf)/4`. The existing point-estimate functions (`leverage_scores`, `classify_loops`, `feedback_loops`) are left untouched. Two Shiny modules gain an off-by-default toggle that calls the new function with a fixed seed for reproducible display.

**Tech Stack:** Python 3.11, NumPy (already a dep — see `dynamics.py`), NetworkX, Shiny for Python, pytest, Playwright (e2e).

## Global Constraints

- Existing point functions `leverage_scores`, `classify_loops`, `feedback_loops` MUST remain byte-for-byte unchanged.
- Confidence→probability map: `p(conf) = base · (5 − conf) / 4`, `base` default `0.5`, confidence clamped to `[1, 5]`. A confidence-5 edge has `p = 0`.
- All user-facing strings go through `t()` and MUST have entries for all 9 languages: `en, es, fr, de, lt, pt, it, no, el` (`tests/test_i18n.py::test_loader_handles_all_supported_languages` enforces this).
- CIs are 95% percentile intervals (2.5 / 97.5).
- Modules call `uncertainty_scores(..., seed=0)` for reproducible display.
- Run Python via the micromamba `shiny` env: `micromamba run -n shiny python -m pytest ...`.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Windows: never multi-line `python -c` (splits per line, creates stray files). Use a temp `.py` file or a single-line command.

---

### Task 1: Perturbation primitives (`_perturb_prob`, `_perturbed_connections`)

**Files:**
- Modify: `sespy/network.py` (add two functions near `_edge_weight`, ~line 330; add `from dataclasses import replace` to imports if absent)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `IsaData`, `Connection` from `sespy.data_structure`; `numpy`.
- Produces:
  - `_perturb_prob(confidence: int, base: float) -> float`
  - `_perturbed_connections(isa: IsaData, base: float, rng: "np.random.Generator") -> list[Connection]`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py`:

```python
import numpy as np
from sespy import network
from sespy.data_structure import IsaData, Element, Connection


def _isa(conns):
    """Build an IsaData whose elements are exactly the ids referenced by conns."""
    ids = sorted({c.source for c in conns} | {c.target for c in conns})
    els = [Element(id=i, label=i, type="pressure") for i in ids]
    return IsaData(elements=els, connections=conns)


def test_perturb_prob_endpoints():
    assert network._perturb_prob(5, 0.5) == 0.0
    assert network._perturb_prob(1, 0.5) == 0.5
    assert network._perturb_prob(3, 0.5) == 0.25
    # confidence clamps to [1, 5]
    assert network._perturb_prob(9, 0.5) == 0.0
    assert network._perturb_prob(0, 0.5) == 0.5


def test_perturbed_connections_certain_graph_never_changes():
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="-", confidence=5)]
    isa = _isa(conns)
    rng = np.random.default_rng(0)
    for _ in range(200):
        out = network._perturbed_connections(isa, 0.5, rng)
        assert {(c.source, c.target, c.polarity) for c in out} == {
            ("A", "B", "+"), ("B", "A", "-")}


def test_perturbed_connections_low_confidence_drops_and_flips():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "A", polarity="+", confidence=1)]
    isa = _isa(conns)
    rng = np.random.default_rng(0)
    saw_drop = saw_flip = False
    for _ in range(500):
        out = network._perturbed_connections(isa, 0.5, rng)
        if len(out) < 2:
            saw_drop = True
        if any(c.polarity == "-" for c in out):
            saw_flip = True
    assert saw_drop and saw_flip
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "perturb" -v`
Expected: FAIL with `AttributeError: module 'sespy.network' has no attribute '_perturb_prob'`

- [ ] **Step 3: Write minimal implementation**

In `sespy/network.py`, ensure the import block has:

```python
from dataclasses import replace
```

Add these functions (place them just above `_edge_weight`):

```python
def _perturb_prob(confidence: int, base: float) -> float:
    """Per-draw drop/flip probability for one edge: base*(5-conf)/4.

    confidence 5 -> 0 (certain edge never perturbed); confidence 1 -> base.
    Confidence is clamped to [1, 5]."""
    c = max(1, min(5, int(confidence)))
    return base * (5 - c) / 4.0


def _perturbed_connections(isa: IsaData, base: float, rng) -> list["Connection"]:
    """One Monte Carlo draw of structural uncertainty.

    Each connection independently: drops out with _perturb_prob (omitted from
    the result), or — if kept — flips polarity with the same probability.
    Pure: `isa` is never mutated; returns a fresh connection list."""
    out: list[Connection] = []
    for c in isa.connections:
        p = _perturb_prob(c.confidence, base)
        if rng.random() < p:
            continue  # dropped
        if rng.random() < p:
            flipped = "-" if c.polarity == "+" else "+"
            out.append(replace(c, polarity=flipped))
        else:
            out.append(c)
    return out
```

(If `Connection` is not already imported in `network.py`, add it to the
`from sespy.data_structure import ...` line.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "perturb" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): edge drop+flip perturbation primitives (D2D MC)"
```

---

### Task 2: `uncertainty_scores` aggregation

**Files:**
- Modify: `sespy/network.py` (add `uncertainty_scores` after `classify_loops`, ~line 463)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `_perturbed_connections` (Task 1), `feedback_loops`, `leverage_scores`, `loop_polarity` (existing), `numpy`.
- Produces:
  ```python
  def uncertainty_scores(
      isa: IsaData, *, cycles: list[list[str]] | None = None,
      n_samples: int = 500, seed: int | None = None, base: float = 0.5,
      max_length: int = 6, max_loops: int = 50,
      contested_band: tuple[float, float] = (0.2, 0.8),
  ) -> dict
  ```
  Returns `{"n_samples": int, "leverage": {id: {"mean","ci_low","ci_high","std"}}, "loops": [{"id","nodes","path","existence_prob","reinforcing_prob","balancing_prob","contested"}]}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py` (reuses the `_isa` helper from Task 1):

```python
def test_uncertainty_regression_anchor_certain_graph():
    # All confidence-5 -> p=0 -> every draw equals the point estimate.
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "C", polarity="-", confidence=5),
             Connection("C", "A", polarity="+", confidence=5)]
    isa = _isa(conns)
    point = network.leverage_scores(isa)
    res = network.uncertainty_scores(isa, n_samples=50, seed=1)
    for nid, lev in res["leverage"].items():
        assert lev["std"] == 0.0
        assert lev["mean"] == point[nid]
        assert lev["ci_low"] == lev["ci_high"] == point[nid]
    assert len(res["loops"]) == 1
    loop = res["loops"][0]
    assert loop["existence_prob"] == 1.0
    # A->B(+), B->C(-), C->A(+): one negative edge -> Balancing.
    assert loop["balancing_prob"] == 1.0
    assert loop["reinforcing_prob"] == 0.0
    assert loop["contested"] is False


def test_uncertainty_empty_graph():
    res = network.uncertainty_scores(IsaData(), n_samples=10, seed=0)
    assert res == {"n_samples": 10, "leverage": {}, "loops": []}


def test_uncertainty_no_cycles():
    conns = [Connection("A", "B", polarity="+", confidence=3)]
    res = network.uncertainty_scores(_isa(conns), n_samples=20, seed=0)
    assert res["loops"] == []
    assert set(res["leverage"]) == {"A", "B"}


def test_uncertainty_deterministic_seed():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "A", polarity="+", confidence=1)]
    isa = _isa(conns)
    a = network.uncertainty_scores(isa, n_samples=100, seed=7)
    b = network.uncertainty_scores(isa, n_samples=100, seed=7)
    c = network.uncertainty_scores(isa, n_samples=100, seed=8)
    assert a == b
    assert a != c


def test_uncertainty_low_confidence_widens_and_lowers_existence():
    conns = [Connection("A", "B", polarity="+", confidence=1),
             Connection("B", "C", polarity="+", confidence=1),
             Connection("C", "A", polarity="+", confidence=1)]
    res = network.uncertainty_scores(_isa(conns), n_samples=500, seed=0)
    assert any(lev["std"] > 0 for lev in res["leverage"].values())
    assert res["loops"][0]["existence_prob"] < 1.0


def test_uncertainty_contested_loop():
    # A->B certain (+); B->A uncertain (+, conf 1). When the uncertain edge
    # survives it flips ~50% -> loop polarity ~50/50 -> contested.
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="+", confidence=1)]
    res = network.uncertainty_scores(_isa(conns), n_samples=3000, seed=1)
    assert len(res["loops"]) == 1
    lp = res["loops"][0]
    assert lp["contested"] is True
    assert 0.2 <= lp["reinforcing_prob"] <= 0.8


def test_uncertainty_respects_supplied_cycles():
    conns = [Connection("A", "B", polarity="+", confidence=5),
             Connection("B", "A", polarity="+", confidence=5)]
    isa = _isa(conns)
    res = network.uncertainty_scores(isa, cycles=[["A", "B"]], n_samples=10, seed=0)
    assert [lp["nodes"] for lp in res["loops"]] == [["A", "B"]]
    assert res["loops"][0]["id"] == "L001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "uncertainty" -v`
Expected: FAIL with `AttributeError: module 'sespy.network' has no attribute 'uncertainty_scores'`

- [ ] **Step 3: Write minimal implementation**

Add to `sespy/network.py` after `classify_loops`:

```python
def uncertainty_scores(
    isa: IsaData,
    *,
    cycles: list[list[str]] | None = None,
    n_samples: int = 500,
    seed: int | None = None,
    base: float = 0.5,
    max_length: int = 6,
    max_loops: int = 50,
    contested_band: tuple[float, float] = (0.2, 0.8),
) -> dict:
    """Monte-Carlo leverage & loop uncertainty under edge drop + sign-flip.

    Each of `n_samples` draws perturbs the graph via `_perturbed_connections`
    (drop and/or flip per edge, probability decreasing in confidence), then
    recomputes leverage and checks each baseline loop's survival + polarity.

    Returns per-node leverage {mean, ci_low, ci_high, std} (95% percentile CI)
    and per-baseline-loop existence/polarity probabilities with a `contested`
    flag (polarity probability inside `contested_band`). With every edge at
    confidence 5 (or base=0) the result collapses to the point estimate.
    """
    import numpy as np

    node_ids = [el.id for el in isa.elements]
    if not node_ids:
        return {"n_samples": n_samples, "leverage": {}, "loops": []}

    if cycles is None:
        cycles = feedback_loops(isa, max_length=max_length, max_loops=max_loops)

    rng = np.random.default_rng(seed)
    lev_samples: dict[str, list[float]] = {nid: [] for nid in node_ids}
    survived = [0] * len(cycles)
    reinforcing = [0] * len(cycles)

    for _ in range(n_samples):
        pert = IsaData(
            elements=isa.elements,
            connections=_perturbed_connections(isa, base, rng),
        )
        lev = leverage_scores(pert)
        for nid in node_ids:
            lev_samples[nid].append(lev.get(nid, 0.0))
        present = {(c.source, c.target) for c in pert.connections}
        for i, cyc in enumerate(cycles):
            n = len(cyc)
            if all((cyc[k], cyc[(k + 1) % n]) in present for k in range(n)):
                survived[i] += 1
                if loop_polarity(cyc, pert) == "Reinforcing":
                    reinforcing[i] += 1

    leverage_out: dict[str, dict] = {}
    for nid in node_ids:
        arr = np.asarray(lev_samples[nid], dtype=float)
        leverage_out[nid] = {
            "mean": float(arr.mean()),
            "ci_low": float(np.percentile(arr, 2.5)),
            "ci_high": float(np.percentile(arr, 97.5)),
            "std": float(arr.std()),
        }

    label_by_id = {el.id: el.label for el in isa.elements}
    lo, hi = contested_band
    loops_out: list[dict] = []
    for i, cyc in enumerate(cycles):
        exist_p = survived[i] / n_samples
        if survived[i] > 0:
            rein_p = reinforcing[i] / survived[i]
            bal_p = 1.0 - rein_p
            contested = lo <= rein_p <= hi
        else:
            rein_p = bal_p = 0.0
            contested = False
        loops_out.append({
            "id": f"L{i + 1:03d}",
            "nodes": cyc,
            "path": " → ".join(label_by_id.get(x, x) for x in cyc)
            + f" → {label_by_id.get(cyc[0], cyc[0])}",
            "existence_prob": exist_p,
            "reinforcing_prob": rein_p,
            "balancing_prob": bal_p,
            "contested": contested,
        })

    return {"n_samples": n_samples, "leverage": leverage_out, "loops": loops_out}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "uncertainty" -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full network test file (no regressions)**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): uncertainty_scores — MC leverage CIs + loop existence/polarity probs"
```

---

### Task 3: i18n keys (9 languages)

**Files:**
- Modify: `sespy/translations/core.json` (add 8 keys to the `"translation"` object)
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces translation keys: `uncertainty.toggle`, `uncertainty.n_samples`, `uncertainty.ci`, `uncertainty.unstable`, `loops.existence_pct`, `loops.reinforcing_pct`, `loops.balancing_pct`, `loops.contested`.

- [ ] **Step 1: Add the keys**

Insert these 8 entries into the `"translation"` object in `sespy/translations/core.json` (any position inside the object; preserve valid JSON and trailing commas):

```json
"uncertainty.toggle": {"en": "Show uncertainty (Monte Carlo)", "es": "Mostrar incertidumbre (Monte Carlo)", "fr": "Afficher l'incertitude (Monte-Carlo)", "de": "Unsicherheit anzeigen (Monte-Carlo)", "lt": "Rodyti neapibrežtį (Monte Karlo)", "pt": "Mostrar incerteza (Monte Carlo)", "it": "Mostra incertezza (Monte Carlo)", "no": "Vis usikkerhet (Monte Carlo)", "el": "Εμφάνιση αβεβαιότητας (Monte Carlo)"},
"uncertainty.n_samples": {"en": "Monte Carlo samples", "es": "Muestras de Monte Carlo", "fr": "Échantillons Monte-Carlo", "de": "Monte-Carlo-Stichproben", "lt": "Monte Karlo imtys", "pt": "Amostras de Monte Carlo", "it": "Campioni Monte Carlo", "no": "Monte Carlo-prøver", "el": "Δείγματα Monte Carlo"},
"uncertainty.ci": {"en": "95% CI", "es": "IC 95%", "fr": "IC 95 %", "de": "95%-KI", "lt": "95% PI", "pt": "IC 95%", "it": "IC 95%", "no": "95% KI", "el": "95% ΔΕ"},
"uncertainty.unstable": {"en": "unstable", "es": "inestable", "fr": "instable", "de": "instabil", "lt": "nestabilus", "pt": "instável", "it": "instabile", "no": "ustabil", "el": "ασταθές"},
"loops.existence_pct": {"en": "Existence %", "es": "Existencia %", "fr": "Existence %", "de": "Existenz %", "lt": "Egzistavimas %", "pt": "Existência %", "it": "Esistenza %", "no": "Eksistens %", "el": "Ύπαρξη %"},
"loops.reinforcing_pct": {"en": "Reinforcing %", "es": "Reforzador %", "fr": "Renforçant %", "de": "Verstärkend %", "lt": "Stiprinanti %", "pt": "Reforço %", "it": "Rinforzante %", "no": "Forsterkende %", "el": "Ενισχυτικό %"},
"loops.balancing_pct": {"en": "Balancing %", "es": "Equilibrador %", "fr": "Équilibrant %", "de": "Ausgleichend %", "lt": "Balansuojanti %", "pt": "Equilíbrio %", "it": "Bilanciante %", "no": "Balanserende %", "el": "Εξισορροπητικό %"},
"loops.contested": {"en": "Contested", "es": "Disputado", "fr": "Contesté", "de": "Umstritten", "lt": "Ginčytinas", "pt": "Contestado", "it": "Conteso", "no": "Omstridt", "el": "Αμφισβητούμενο"}
```

- [ ] **Step 2: Verify JSON validity and key coverage**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS — in particular `test_loader_handles_all_supported_languages` (every key has all 9 languages) and `test_loader_finds_keys`.

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(uncertainty): add toggle/CI/loop-prob keys (8 keys, 9 languages)"
```

---

### Task 4: Leverage module — uncertainty toggle + CI columns

**Files:**
- Modify: `sespy/modules/analysis_leverage.py` (UI sidebar ~line 92; server ~line 152)
- Test: `tests/test_leverage_e2e.py`

**Interfaces:**
- Consumes: `net_analysis.uncertainty_scores` (Task 2), keys `uncertainty.toggle/n_samples/ci/unstable` (Task 3).
- Produces: inputs `show_uncertainty` (checkbox), `n_samples` (numeric) in the `leverage` module namespace; extra `leverage_table` columns when toggled on.

- [ ] **Step 1: Add the UI inputs**

In `analysis_leverage_ui()`, immediately after the `top_n` `ui.input_slider(...)` block (before `width=240,`), add:

```python
                ui.tags.hr(),
                ui.input_checkbox("show_uncertainty", t("uncertainty.toggle"), value=False),
                ui.input_numeric("n_samples", t("uncertainty.n_samples"),
                                 value=500, min=50, max=5000, step=50),
```

- [ ] **Step 2: Add the uncertainty reactive + extend the table**

In `analysis_leverage_server`, add a reactive after the `ranked()` calc:

```python
    @reactive.calc
    def uncertainty() -> dict | None:
        if not input.show_uncertainty():
            return None
        event_bus.isa_change.get()
        return net_analysis.uncertainty_scores(
            project_data.get().isa_data,
            n_samples=int(input.n_samples() or 500),
            seed=0,
        )
```

Replace the `leverage_table` render function body with:

```python
    @output
    @render.data_frame
    def leverage_table():
        import pandas as pd

        rows = ranked()
        base_cols = ["rank", "id", "label", "type", "leverage"]
        if not rows:
            return pd.DataFrame(columns=base_cols)

        unc = uncertainty()
        if unc is None:
            return pd.DataFrame(rows, columns=base_cols)

        lev = unc["leverage"]
        enriched = []
        for r in rows:
            u = lev.get(r["id"])
            ci = f"[{u['ci_low']:.2f}, {u['ci_high']:.2f}]" if u else ""
            unstable = (t("uncertainty.unstable")
                        if u and u["ci_low"] < 0 < u["ci_high"] else "")
            enriched.append({**r, t("uncertainty.ci"): ci,
                             t("uncertainty.unstable"): unstable})
        cols = base_cols + [t("uncertainty.ci"), t("uncertainty.unstable")]
        return pd.DataFrame(enriched, columns=cols)
```

- [ ] **Step 3: Smoke-test the module imports**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_leverage as m; print('ok')"`
Expected: prints `ok` (no syntax/import error).

- [ ] **Step 4: Add the e2e assertion**

Append to `tests/test_leverage_e2e.py` (mirror the existing nav + table-wait pattern; if the file already has a `main()`, add the new assertions inside it after the table loads, otherwise add this block). The check: enabling the toggle adds the "95% CI" column header.

```python
        # --- Uncertainty toggle adds the 95% CI column ---
        await page.click("#sespy_nav_leverage")
        await page.wait_for_selector("#leverage-leverage_table table tbody tr", timeout=30000)
        await page.check("#leverage-show_uncertainty")
        # Table re-renders; poll for the new header.
        found_ci = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#leverage-leverage_table table thead th')).map(th => th.textContent.trim())"
            )
            if any("CI" in h for h in headers):
                found_ci = True
                break
        assert found_ci, f"95% CI column not added after toggling uncertainty: {headers}"
        print("leverage uncertainty CI column: OK")
```

- [ ] **Step 5: Run the e2e**

Run: `micromamba run -n shiny python tests/run_e2e.py test_leverage_e2e.py`
(or the project's standard single-e2e invocation)
Expected: PASS, prints `leverage uncertainty CI column: OK`.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/analysis_leverage.py tests/test_leverage_e2e.py
git commit -m "feat(leverage): off-by-default MC uncertainty toggle + 95% CI columns"
```

---

### Task 5: Loop Analysis module — uncertainty toggle + probability columns

**Files:**
- Modify: `sespy/modules/analysis_loops.py` (UI `_loops_body()` ~line 116; server `loops_table` ~line 212)
- Test: `tests/test_loops_e2e.py`

**Interfaces:**
- Consumes: `net_analysis.uncertainty_scores` (Task 2), keys `uncertainty.toggle/n_samples`, `loops.existence_pct/reinforcing_pct/balancing_pct/contested` (Task 3); `detected` reactive + `classified()` calc (existing — both derived from the same `detected` cycles so loop ids align with `uncertainty_scores(..., cycles=detected.get())`).
- Produces: inputs `show_uncertainty`, `n_samples` in the `loops` module namespace; extra `loops_table` columns when toggled on.

- [ ] **Step 1: Add the UI inputs**

In `_loops_body()`, in the sidebar after the `detect` button line (after `ui.input_action_button("detect", ...)`), add:

```python
            ui.tags.hr(),
            ui.input_checkbox("show_uncertainty", t("uncertainty.toggle"), value=False),
            ui.input_numeric("n_samples", t("uncertainty.n_samples"),
                             value=500, min=50, max=5000, step=50),
```

- [ ] **Step 2: Add the uncertainty reactive + extend the table**

In `analysis_loops_server`, add after the `classified()` calc:

```python
    @reactive.calc
    def uncertainty_loops() -> dict[str, dict]:
        if not input.show_uncertainty():
            return {}
        cycles = detected.get()
        if not cycles:
            return {}
        res = net_analysis.uncertainty_scores(
            project_data.get().isa_data,
            cycles=cycles,
            n_samples=int(input.n_samples() or 500),
            seed=0,
        )
        return {lp["id"]: lp for lp in res["loops"]}
```

Replace the `loops_table` render function body with:

```python
    @output
    @render.data_frame
    def loops_table():
        import pandas as pd
        rows = classified()
        cols = ["id", "behavior", "delayed", "type", "length", "path"]
        if not rows:
            return pd.DataFrame(columns=cols)

        unc = uncertainty_loops()

        def base_row(r):
            return {
                "id": r["id"],
                "behavior": t(_BEHAVIOR_KEY[r["behavior"]]),
                "delayed": "✓" if r["delayed"] else "—",
                "type": r["type"],
                "length": r["length"],
                "path": r["path"],
            }

        if not unc:
            return pd.DataFrame([base_row(r) for r in rows], columns=cols)

        ext_cols = cols + [t("loops.existence_pct"), t("loops.reinforcing_pct"),
                           t("loops.balancing_pct"), t("loops.contested")]
        out = []
        for r in rows:
            row = base_row(r)
            u = unc.get(r["id"])
            if u:
                row[t("loops.existence_pct")] = f"{u['existence_prob'] * 100:.0f}%"
                row[t("loops.reinforcing_pct")] = f"{u['reinforcing_prob'] * 100:.0f}%"
                row[t("loops.balancing_pct")] = f"{u['balancing_prob'] * 100:.0f}%"
                row[t("loops.contested")] = t("loops.contested") if u["contested"] else ""
            else:
                row[t("loops.existence_pct")] = ""
                row[t("loops.reinforcing_pct")] = ""
                row[t("loops.balancing_pct")] = ""
                row[t("loops.contested")] = ""
            out.append(row)
        return pd.DataFrame(out, columns=ext_cols)
```

- [ ] **Step 3: Smoke-test the module imports**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_loops as m; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Add the e2e assertion**

Append to `tests/test_loops_e2e.py` inside `main()`, after loop detection populates the table (after the existing `wait_for_selector("#loops-loops_table table tbody tr", ...)`). It enables the toggle and asserts the existence-% column header appears:

```python
        # --- Uncertainty toggle adds loop probability columns ---
        await page.check("#loops-show_uncertainty")
        found_exist = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#loops-loops_table table thead th')).map(th => th.textContent.trim())"
            )
            if any("%" in h for h in headers):
                found_exist = True
                break
        assert found_exist, f"loop probability columns not added: {headers}"
        print("loops uncertainty probability columns: OK")
```

- [ ] **Step 5: Run the e2e**

Run: `micromamba run -n shiny python tests/run_e2e.py test_loops_e2e.py`
Expected: PASS, prints `loops uncertainty probability columns: OK`.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/analysis_loops.py tests/test_loops_e2e.py
git commit -m "feat(loops): off-by-default MC uncertainty toggle + existence/polarity columns"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: previous baseline (342 passed, 1 skipped) + the new network tests, all passing.
- [ ] e2e green: `micromamba run -n shiny python tests/run_e2e.py`
  Expected: green except `test_report_e2e.py` (pre-existing WeasyPrint env break — not a regression).
- [ ] Existing `leverage_scores` / `classify_loops` / `feedback_loops` unchanged (git diff shows no edits to their bodies).
- [ ] Toggles default OFF: default leverage/loops render is the cheap point estimate.
