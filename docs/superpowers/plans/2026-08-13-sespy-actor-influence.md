# Governance Actor Influence (issue #14) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `governance_actor_influence()` to `sespy/network.py` and surface it as a ranked table — the third block on the Network Metrics card.

**Architecture:** A pure function reuses `centrality_metrics` + `_zscore` + `_GOVERNANCE` to return per-governance-actor rows whose `influence` composite equals `leverage_scores()` by construction. The renderer is a third `output_ui` block rendering a plain HTML table (NOT `render.data_frame` — shadow DOM would blind the e2e's text assertions). Spec: `docs/superpowers/specs/2026-08-13-governance-actor-influence-design.md`.

**Tech Stack:** Python, networkx (via existing helpers), Shiny for Python, pytest, Playwright e2e.

## Global Constraints

- Python runs ONLY via `micromamba run -n shiny python …` (no global python, no pip/venv).
- Unit suite (CI parity — bare `pytest tests` collects e2e scripts that execute at import): `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` (491 green on main, 5 pre-existing warnings).
- e2e: ALWAYS the full suite `micromamba run -n shiny python tests/run_e2e.py` (32 script-runs), never a subset. Kill any orphaned server first: `powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"`. NOTE: the run takes >10 min and backgrounded Bash dies at ~600s — the controller runs it detached (Start-Process + Monitor); implementers must not attempt it via backgrounded Bash.
- Every i18n key needs all 9 languages (en es fr de lt pt it no el), one line per key in `sespy/translations/core.json`.
- No NaN/inf in return values (inherited from `_safe_floats`/`_zscore`; tests assert finiteness).
- Playwright selectors scoped to `#metrics-actor_influence_summary`, never bare `text=`.
- Metric names in UI (column headers) stay untranslated lowercase ("betweenness", "eigenvector", "pagerank", "influence") — the module's existing convention (radio buttons, histogram axis).
- Commit style: conventional. Work on branch `feat/actor-influence` off `main`.

**Golden values** (computed on `data/sample_ses.json` against the real repo, 2026-08-13): governance rows sort to `["R002", "R001"]` — R002 "Mooring buoy program" (betweenness 0.0833, eigenvector 0.3393, pagerank 0.0592, influence 0.1965), R001 "MPA enforcement" (0.0, 0.0, 0.0088, influence −4.0938). `influence` must equal `leverage_scores()[id]` exactly (same computation). Note: `centrality_metrics` logs an eigenvector numpy→iterative fallback warning on this sample (pre-existing, AmbiguousSolution) — not a defect of this feature.

---

### Task 0: Branch

- [ ] **Step 1:**

```bash
git checkout -b feat/actor-influence
```

---

### Task 1: `governance_actor_influence()` in `sespy/network.py`

**Files:**
- Modify: `sespy/network.py` (insert after `leverage_scores`, which ends ~line 220)
- Test: `tests/test_network.py` (append; reuse the file's existing imports — `network`, `IsaData`, `Element`, `Connection`, `load_sample`, `Path`; check whether `pytest` and `math` are already imported before adding them)

**Interfaces:**
- Consumes: `centrality_metrics(isa)`, `_zscore(values)`, `_GOVERNANCE` frozenset, `leverage_scores(isa)` (parity target) — all already in `sespy/network.py`.
- Produces: `governance_actor_influence(isa: IsaData) -> list[dict]`, rows `{"id", "label", "type", "betweenness", "eigenvector", "pagerank", "influence"}` sorted by `influence` desc, ties in `isa.elements` order. Task 3's renderer consumes exactly this shape.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py`:

```python
# ---------------------------------------------------------------------------
# governance_actor_influence (issue #14)
# ---------------------------------------------------------------------------


def test_actor_influence_sample_golden():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    rows = network.governance_actor_influence(isa)
    # R002 dominates; R001 is peripheral (zero betweenness/eigenvector) —
    # the power-asymmetry pattern the source paper diagnoses.
    assert [r["id"] for r in rows] == ["R002", "R001"]
    assert rows[0]["label"] == "Mooring buoy program"
    assert set(rows[0]) == {"id", "label", "type", "betweenness",
                            "eigenvector", "pagerank", "influence"}
    lv = network.leverage_scores(isa)
    for r in rows:
        assert r["influence"] == lv[r["id"]]  # equal by construction
        assert r["type"] == "Responses"
    assert round(rows[0]["betweenness"], 4) == 0.0833
    assert round(rows[1]["influence"], 4) == -4.0938


def test_actor_influence_no_governance_returns_empty():
    isa = IsaData(
        elements=[Element(id="P1", label="p", type="Pressures"),
                  Element(id="D1", label="d", type="Drivers")],
        connections=[Connection(source="D1", target="P1")],
    )
    assert network.governance_actor_influence(isa) == []


def test_actor_influence_empty_graph():
    assert network.governance_actor_influence(IsaData()) == []


def test_actor_influence_measures_forward_compat():
    # Synthetic-IsaData precedent for the unreachable "Measures" type
    # (see test_governance_gap_measures_is_governance_forward_compat).
    isa = IsaData(
        elements=[Element(id="M1", label="m", type="Measures"),
                  Element(id="P1", label="p", type="Pressures")],
        connections=[Connection(source="M1", target="P1")],
    )
    rows = network.governance_actor_influence(isa)
    assert [r["id"] for r in rows] == ["M1"]
    assert rows[0]["type"] == "Measures"


def test_actor_influence_tie_order_deterministic():
    # Two structurally identical Responses: equal influence, so the sort
    # must fall back to isa.elements order (R2 listed first wins).
    els = [Element(id="R2", label="b", type="Responses"),
           Element(id="R1", label="a", type="Responses"),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R2", target="P1"),
             Connection(source="R1", target="P1")]
    rows = network.governance_actor_influence(
        IsaData(elements=els, connections=conns))
    assert [r["id"] for r in rows] == ["R2", "R1"]


def test_actor_influence_disconnected_graph_is_finite():
    import math
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="P1", label="p", type="Pressures"),
           Element(id="D1", label="d", type="Drivers")]
    rows = network.governance_actor_influence(
        IsaData(elements=els,
                connections=[Connection(source="D1", target="P1")]))
    assert len(rows) == 1
    assert all(math.isfinite(v) for v in rows[0].values()
               if isinstance(v, float))
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k actor_influence`
Expected: 6 errors, `AttributeError: module 'sespy.network' has no attribute 'governance_actor_influence'`.

- [ ] **Step 3: Implement** — insert into `sespy/network.py` after `leverage_scores`:

```python
def governance_actor_influence(isa: IsaData) -> list[dict]:
    """Per-governance-actor influence within the WHOLE network — the
    power-asymmetry diagnostic of Maritime Studies 2026
    (doi:10.1007/s40152-026-00501-z): dominant vs. peripheral governance
    actors in co-management.

    One row per element whose type is in _GOVERNANCE ("Measures" is
    forward-looking — unreachable through today's ingresses). Rows carry the
    RAW betweenness/eigenvector/pagerank centralities (readable values) plus
    `influence`, the whole-network z-score composite — equal by construction
    to leverage_scores() for the same node: one definition, two views.
    Centralities are computed on the full graph so cross-boundary influence
    counts; z-scores are standardised over ALL nodes so an actor's score
    reads "influence relative to the whole system" and is stable under
    changes to the governance subset. Sorted by influence descending, ties
    in isa.elements order (list.sort is stable). Degenerate inputs return
    []; values are finite (inherited _safe_floats/_zscore guards). Pure.
    """
    governance = [el for el in isa.elements if el.type in _GOVERNANCE]
    if not governance:
        return []
    m = centrality_metrics(isa)
    bz = _zscore(m["betweenness"])
    ez = _zscore(m["eigenvector"])
    pz = _zscore(m["pagerank"])
    rows = [
        {
            "id": el.id,
            "label": el.label,
            "type": el.type,
            "betweenness": m["betweenness"].get(el.id, 0.0),
            "eigenvector": m["eigenvector"].get(el.id, 0.0),
            "pagerank": m["pagerank"].get(el.id, 0.0),
            "influence": (bz.get(el.id, 0.0) + ez.get(el.id, 0.0)
                          + pz.get(el.id, 0.0)),
        }
        for el in governance
    ]
    rows.sort(key=lambda r: -r["influence"])
    return rows
```

- [ ] **Step 4: Run the new tests, then the full unit suite (Global Constraints command)** — expect 6 passed, then 497 passed / 5 pre-existing warnings.

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): governance_actor_influence() - whole-network actor ranking (#14)"
```

---

### Task 2: i18n (2 keys × 9 languages) + presence test

**Files:**
- Modify: `sespy/translations/core.json` (insert after the `"metrics.gov_gap_no_press"` line, one line per key)
- Test: `tests/test_i18n.py` (append after `test_governance_gap_keys_present`)

**Interfaces:**
- Produces: keys `metrics.actor_influence`, `metrics.actor_influence_caption` (no params). Task 3 uses exactly these.

- [ ] **Step 1: Write the failing test** — append to `tests/test_i18n.py`:

```python
def test_actor_influence_keys_present(translations):
    assert "metrics.actor_influence" in translations
    assert "metrics.actor_influence_caption" in translations
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q -k actor_influence` → FAIL.

- [ ] **Step 3: Insert the keys VERBATIM** (then verify the file is still valid JSON with `micromamba run -n shiny python -c "import json;json.load(open('sespy/translations/core.json',encoding='utf-8'))"`):

```json
    "metrics.actor_influence": {"en": "Governance actor influence", "es": "Influencia de los actores de gobernanza", "fr": "Influence des acteurs de gouvernance", "de": "Einfluss der Governance-Akteure", "lt": "Valdysenos veikėjų įtaka", "pt": "Influência dos atores de governança", "it": "Influenza degli attori di governance", "no": "Innflytelse til styringsaktører", "el": "Επιρροή των φορέων διακυβέρνησης"},
    "metrics.actor_influence_caption": {"en": "influence = z-score sum of betweenness, eigenvector and PageRank over the whole network", "es": "influencia = suma de puntuaciones z de intermediación, vector propio y PageRank sobre toda la red", "fr": "influence = somme des scores z d'intermédiarité, de vecteur propre et de PageRank sur l'ensemble du réseau", "de": "Einfluss = Summe der z-Werte von Betweenness, Eigenvektor und PageRank über das gesamte Netzwerk", "lt": "įtaka = tarpiškumo, tikrinio vektoriaus ir PageRank z-įverčių suma visame tinkle", "pt": "influência = soma dos escores z de intermediação, autovetor e PageRank em toda a rede", "it": "influenza = somma dei punteggi z di betweenness, autovettore e PageRank sull'intera rete", "no": "innflytelse = sum av z-skårer for mellomleddssentralitet, egenvektor og PageRank over hele nettverket", "el": "επιρροή = άθροισμα z-τιμών ενδιαμεσότητας, ιδιοδιανύσματος και PageRank σε ολόκληρο το δίκτυο"},
```

- [ ] **Step 4: Run `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`** — all pass including the 9-language drift test.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(metrics): actor-influence keys in all nine languages (#14)"
```

---

### Task 3: UI block + e2e

**Files:**
- Modify: `sespy/modules/analysis_metrics.py` — one line pair in `analysis_metrics_ui` after the governance-gap pair; renderer after `governance_gap_summary` in the server.
- Modify: `tests/test_metrics_e2e.py` — append after the governance-gap block, before `await browser.close()`.

**Interfaces:**
- Consumes: `governance_actor_influence(isa)` rows (Task 1 shape), `governance_gap(isa)["n_edges_considered"]` (existing), i18n keys (Task 2), existing keys `metrics.gov_gap_none` / `metrics.gov_gap_no_gov`.
- Produces: DOM node `#metrics-actor_influence_summary`.

- [ ] **Step 1: UI slot** — in `analysis_metrics_ui`, directly after the `governance_gap_summary` output_ui + hr pair:

```python
                ui.output_ui("actor_influence_summary"),
                ui.tags.hr(),
```

- [ ] **Step 2: Renderer** — in `analysis_metrics_server`, after the `governance_gap_summary` renderer:

```python
    @output
    @render.ui
    def actor_influence_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if net_analysis.governance_gap(isa)["n_edges_considered"] == 0:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        rows = net_analysis.governance_actor_influence(isa)
        if not rows:
            return ui.p(t("metrics.gov_gap_no_gov"), class_="text-muted")
        header = ui.tags.tr(
            ui.tags.th(""),
            ui.tags.th("betweenness"), ui.tags.th("eigenvector"),
            ui.tags.th("pagerank"), ui.tags.th("influence"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(f"{r['id']} · {r['label']}"),
                ui.tags.td(f"{r['betweenness']:.2f}"),
                ui.tags.td(f"{r['eigenvector']:.2f}"),
                ui.tags.td(f"{r['pagerank']:.2f}"),
                ui.tags.td(ui.tags.strong(f"{r['influence']:.2f}")),
            )
            for r in rows
        ]
        return ui.div(
            ui.h5(t("metrics.actor_influence")),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("metrics.actor_influence_caption"),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )
```

- [ ] **Step 3: e2e block** — insert into `tests/test_metrics_e2e.py` after the governance-gap assertions:

```python
        # --- Governance actor influence table renders both actors, ranked ---
        ai_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            ai_text = (await page.inner_text("#metrics-actor_influence_summary")).strip()
            if ai_text:
                break
        assert "Governance actor influence" in ai_text, f"expected heading, got: {ai_text!r}"
        assert "R002" in ai_text and "R001" in ai_text, f"expected both actors, got: {ai_text!r}"
        # R002 (dominant) must rank above R001 (peripheral).
        assert ai_text.index("R002") < ai_text.index("R001"), f"expected R002 first, got: {ai_text!r}"
        print(f"actor influence table: OK")
```

- [ ] **Step 4: Run unit tests (full CI-parity suite)**, then the FULL e2e suite (controller runs it detached per Global Constraints; implementer stops after unit suite and requests the e2e run).

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/analysis_metrics.py tests/test_metrics_e2e.py
git commit -m "feat(metrics): governance actor influence table on the metrics card (#14)"
```

---

### Task 4: Changelog, merge, close issue #14

- [ ] **Step 1: Changelog** — first bullet under `## [Unreleased]` in `CHANGELOG.md`:

```markdown
- New "Governance actor influence" table on the Network Metrics card (#14):
  whole-network centrality ranking (betweenness, eigenvector, PageRank, and a
  z-score composite equal to the leverage score) restricted to governance
  elements, revealing dominant vs. peripheral actors (Maritime Studies 2026,
  doi:10.1007/s40152-026-00501-z).
```

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): actor-influence table under Unreleased (#14)"
```

- [ ] **Step 2: Merge and push** (after the final branch review is clean and the full e2e is green):

```bash
git checkout main
git merge --no-ff feat/actor-influence -m "feat: governance actor influence (#14)"
git push
```

- [ ] **Step 3: Close issue #14** noting the two deviations from its text: returns a list of row-dicts, not a DataFrame (network.py is pandas-free by convention), and raw centralities are shown with the z-score composite (named `influence`, computed whole-network) rather than a separate `influence_rank` column.

---

## Self-review notes

- Spec coverage: function/rows/sort (Task 1), whole-network z-scores + leverage parity (Task 1 test), Measures forward-compat (Task 1 test), 2 i18n keys + presence test (Task 2), third block + plain HTML table + degenerate guards reusing gov_gap keys (Task 3), scoped e2e with rank-order assertion (Task 3), changelog + issue close with deviations (Task 4).
- Type consistency: row keys identical across Tasks 1 and 3; `#metrics-actor_influence_summary` identical across Tasks 3's renderer and e2e.
- Golden values computed against the real repo on 2026-08-13, not assumed.
