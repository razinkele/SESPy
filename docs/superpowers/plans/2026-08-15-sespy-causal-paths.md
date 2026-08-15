# Causal Path Tracer (issue #16) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `causal_paths()` to `sespy/network.py` — directed simple-path enumeration with compound-polarity sign arithmetic — surfaced as a button-gated fifth block (source/target selectors) on the Network Metrics card.

**Architecture:** A pure function enumerates `nx.all_simple_paths` (cutoff counts edges) over a last-wins-polarity adjacency, with an honest `max_paths` truncation flag and deterministic `(length, path)` ordering. The UI reuses the cascade block's gating machinery: `reactive.value` + reset-on-`isa_change` + compute-on-button. Spec: `docs/superpowers/specs/2026-08-15-causal-paths-design.md`.

**Tech Stack:** Python, networkx, Shiny for Python, pytest, Playwright e2e.

## Global Constraints

- Python ONLY via `micromamba run -n shiny python …` (no global python, no pip/venv).
- Unit suite (CI parity): `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` (506 green on main, 5 pre-existing warnings).
- e2e: ALWAYS the full suite `micromamba run -n shiny python tests/run_e2e.py` (32 script-runs); kill orphans on port 8000 first; the run exceeds the ~600s tool cap — the controller runs it detached on a QUIET machine (no concurrent dispatches); implementers must NOT attempt it.
- Every i18n key needs all 9 languages (en es fr de lt pt it no el), one line per key in `sespy/translations/core.json`.
- Degenerate inputs return the empty shape, never raise; no NaN; no pandas in `network.py`.
- Playwright selectors scoped to ids (`#metrics-paths_summary`, `#metrics-trace_paths`, `#metrics-paths_source`, `#metrics-paths_target`), never bare `text=`.
- Renderers subscribe `event_bus.isa_change.get()` first; button effects use `@reactive.event(..., ignore_init=True)`.
- Commit style: conventional. Branch `feat/causal-paths` off `main`.

**Golden values** (computed against the real repo, 2026-08-15): `D001→P001` → exactly one path `["D001","A001","P001"]`, length 2, polarity `"+"`. `ES02→D001` → exactly two length-8 paths, both `"-"`: `["ES02","GB02","D002","A003","P003","MPF1","ES01","GB01","D001"]` sorted before `["ES02","GB02","D002","A003","P003","MPF1","ES03","GB01","D001"]`; with `max_paths=1` → 1 row and `truncated=True`. `D001→ES02` → empty shape (no directed route). Labels: D001 "Tourism demand", ES02 "Food provisioning".

---

### Task 0: Branch

- [ ] **Step 1:**

```bash
git checkout -b feat/causal-paths
```

---

### Task 1: `causal_paths()` in `sespy/network.py`

**Files:**
- Modify: `sespy/network.py` (insert after `cascade_vulnerability`)
- Test: `tests/test_network.py` (append; reuse existing imports — `network`, `IsaData`, `Element`, `Connection`, `load_sample`, `Path`)

**Interfaces:**
- Consumes: `nx` (imported in the module).
- Produces: `causal_paths(isa: IsaData, source: str, target: str, *, max_length: int = 8, max_paths: int = 100) -> dict` returning `{"paths": [{"path": [ids], "length": int, "polarity": "+"|"-"|"0"}], "counts": {"+": int, "-": int, "0": int}, "truncated": bool}`. Task 3's renderer consumes exactly this shape.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py`:

```python
# ---------------------------------------------------------------------------
# causal_paths (issue #16)
# ---------------------------------------------------------------------------

_EMPTY_PATHS = {"paths": [], "counts": {"+": 0, "-": 0, "0": 0}, "truncated": False}


def test_causal_paths_sample_single_positive():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "D001", "P001")
    assert r["paths"] == [{"path": ["D001", "A001", "P001"],
                           "length": 2, "polarity": "+"}]
    assert r["counts"] == {"+": 1, "-": 0, "0": 0}
    assert r["truncated"] is False


def test_causal_paths_sample_two_negative_sorted():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "ES02", "D001")
    assert [p["path"] for p in r["paths"]] == [
        ["ES02", "GB02", "D002", "A003", "P003", "MPF1", "ES01", "GB01", "D001"],
        ["ES02", "GB02", "D002", "A003", "P003", "MPF1", "ES03", "GB01", "D001"],
    ]
    assert all(p["polarity"] == "-" and p["length"] == 8 for p in r["paths"])
    assert r["counts"] == {"+": 0, "-": 2, "0": 0}


def test_causal_paths_sample_no_route():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "D001", "ES02") == _EMPTY_PATHS


def test_causal_paths_truncation_is_honest():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    r = network.causal_paths(isa, "ES02", "D001", max_paths=1)
    assert len(r["paths"]) == 1
    assert r["truncated"] is True


def test_causal_paths_diamond_polarity():
    # A->B->D (one negative hop) and A->C->D (all positive): the compound
    # sign differs per route, and counts reflect both.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABCD"]
    conns = [Connection(source="A", target="B", polarity="-"),
             Connection(source="B", target="D", polarity="+"),
             Connection(source="A", target="C", polarity="+"),
             Connection(source="C", target="D", polarity="+")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "D")
    by_route = {tuple(p["path"]): p["polarity"] for p in r["paths"]}
    assert by_route == {("A", "B", "D"): "-", ("A", "C", "D"): "+"}
    assert r["counts"] == {"+": 1, "-": 1, "0": 0}


def test_causal_paths_even_negatives_are_positive():
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B", polarity="-"),
             Connection(source="B", target="C", polarity="-")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert r["paths"][0]["polarity"] == "+"  # two negatives multiply out


def test_causal_paths_unsigned_hop_is_ambiguous():
    # Forward-looking: no current ingress emits a polarity outside {+,-},
    # but the sign arithmetic must not silently misread one.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B", polarity=""),
             Connection(source="B", target="C", polarity="-")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert r["paths"][0]["polarity"] == "0"
    assert r["counts"] == {"+": 0, "-": 0, "0": 1}


def test_causal_paths_degenerate_inputs():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "NOPE", "D001") == _EMPTY_PATHS
    assert network.causal_paths(isa, "D001", "NOPE") == _EMPTY_PATHS
    assert network.causal_paths(isa, "D001", "D001") == _EMPTY_PATHS
    assert network.causal_paths(IsaData(), "A", "B") == _EMPTY_PATHS


def test_causal_paths_cycles_yield_simple_paths_only():
    # A->B->A cycle plus B->C: only the simple path A->B->C may appear.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABC"]
    conns = [Connection(source="A", target="B"),
             Connection(source="B", target="A"),
             Connection(source="B", target="C")]
    r = network.causal_paths(IsaData(elements=els, connections=conns), "A", "C")
    assert [p["path"] for p in r["paths"]] == [["A", "B", "C"]]


def test_causal_paths_deterministic():
    root = Path(__file__).resolve().parents[1]
    isa = load_sample(root / "data" / "sample_ses.json")
    assert network.causal_paths(isa, "ES02", "D001") == \
        network.causal_paths(isa, "ES02", "D001")
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k causal_paths`
Expected: 10 errors, `AttributeError: module 'sespy.network' has no attribute 'causal_paths'`.

- [ ] **Step 3: Implement** — insert into `sespy/network.py` after `cascade_vulnerability`:

```python
def causal_paths(
    isa: IsaData, source: str, target: str,
    *, max_length: int = 8, max_paths: int = 100,
) -> dict:
    """Directed causal-chain enumeration with compound-polarity sign
    arithmetic — the static explainability layer of Applied Soft Computing
    2026 (doi:10.1016/j.asoc.2026.115925): "how does A influence B?".

    Enumerates simple directed paths source→target (nx.all_simple_paths;
    cutoff counts EDGES, so max_length bounds path length and prevents
    combinatorial explosion on dense CLDs). Each row carries the node-id
    path, its edge count, and the compound polarity: "-" for an odd number
    of "-" hops, "+" otherwise, and "0" when any hop's polarity is neither
    "+" nor "-" (forward-looking — every current ingress emits only +/-).
    Parallel (source, target) edges deduplicate last-wins, matching
    _axis_sums; self-loops and dangling refs are skipped. Collection stops
    at max_paths with an honest truncated flag (never a silent cap). Rows
    sort (length, path) — deterministic. Unknown endpoints, source ==
    target, or no route return the empty shape; never raises. Pure.
    """
    empty = {"paths": [], "counts": {"+": 0, "-": 0, "0": 0},
             "truncated": False}
    ids = {el.id for el in isa.elements}
    if source not in ids or target not in ids or source == target:
        return empty

    pol: dict[tuple[str, str], str] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        pol[(c.source, c.target)] = c.polarity
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    g.add_edges_from(pol)

    rows: list[dict] = []
    truncated = False
    for p in nx.all_simple_paths(g, source, target, cutoff=max_length):
        if len(rows) >= max_paths:
            truncated = True
            break
        negatives = 0
        ambiguous = False
        for a, b in zip(p, p[1:]):
            sign = pol[(a, b)]
            if sign == "-":
                negatives += 1
            elif sign != "+":
                ambiguous = True
        rows.append({
            "path": list(p),
            "length": len(p) - 1,
            "polarity": "0" if ambiguous else ("-" if negatives % 2 else "+"),
        })
    rows.sort(key=lambda r: (r["length"], r["path"]))

    counts = {"+": 0, "-": 0, "0": 0}
    for r in rows:
        counts[r["polarity"]] += 1
    return {"paths": rows, "counts": counts, "truncated": truncated}
```

- [ ] **Step 4: Run the new tests, then the full unit suite** (Global Constraints command) — expect 10 passed, then 516 passed / 5 pre-existing warnings.

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): causal_paths() - signed simple-path enumeration (#16)"
```

---

### Task 2: i18n (7 keys × 9 languages) + presence test

**Files:**
- Modify: `sespy/translations/core.json` (insert after the `"metrics.cascade_caption"` line, one line per key)
- Test: `tests/test_i18n.py` (append after `test_cascade_keys_present`)

**Interfaces:**
- Produces: keys `metrics.paths`, `metrics.paths_trace`, `metrics.paths_source`, `metrics.paths_target`, `metrics.paths_summary` (params `{n}`, `{pos}`, `{neg}`, `{amb}`), `metrics.paths_none`, `metrics.paths_truncated` (param `{max}`). Task 3 uses exactly these (idle hint reuses the existing `metrics.cascade_hint`).

- [ ] **Step 1: Write the failing test** — append to `tests/test_i18n.py`:

```python
def test_causal_paths_keys_present(translations):
    for key in ("metrics.paths", "metrics.paths_trace", "metrics.paths_source",
                "metrics.paths_target", "metrics.paths_summary",
                "metrics.paths_none", "metrics.paths_truncated"):
        assert key in translations
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q -k causal_paths` → FAIL.

- [ ] **Step 3: Insert the keys VERBATIM** (verify JSON validity afterwards with `micromamba run -n shiny python -c "import json;json.load(open('sespy/translations/core.json',encoding='utf-8'))"`):

```json
    "metrics.paths": {"en": "Causal pathways", "es": "Vías causales", "fr": "Chemins causaux", "de": "Kausalpfade", "lt": "Priežastiniai keliai", "pt": "Vias causais", "it": "Percorsi causali", "no": "Kausale stier", "el": "Αιτιώδεις διαδρομές"},
    "metrics.paths_trace": {"en": "Trace paths", "es": "Trazar vías", "fr": "Tracer les chemins", "de": "Pfade verfolgen", "lt": "Sekti kelius", "pt": "Traçar vias", "it": "Traccia percorsi", "no": "Spor stier", "el": "Ανίχνευση διαδρομών"},
    "metrics.paths_source": {"en": "From", "es": "Desde", "fr": "De", "de": "Von", "lt": "Iš", "pt": "De", "it": "Da", "no": "Fra", "el": "Από"},
    "metrics.paths_target": {"en": "To", "es": "Hasta", "fr": "Vers", "de": "Nach", "lt": "Į", "pt": "Para", "it": "A", "no": "Til", "el": "Προς"},
    "metrics.paths_summary": {"en": "{n} paths: {pos} positive, {neg} negative, {amb} ambiguous", "es": "{n} vías: {pos} positivas, {neg} negativas, {amb} ambiguas", "fr": "{n} chemins : {pos} positifs, {neg} négatifs, {amb} ambigus", "de": "{n} Pfade: {pos} positiv, {neg} negativ, {amb} mehrdeutig", "lt": "{n} keliai: {pos} teigiami, {neg} neigiami, {amb} neaiškūs", "pt": "{n} vias: {pos} positivas, {neg} negativas, {amb} ambíguas", "it": "{n} percorsi: {pos} positivi, {neg} negativi, {amb} ambigui", "no": "{n} stier: {pos} positive, {neg} negative, {amb} tvetydige", "el": "{n} διαδρομές: {pos} θετικές, {neg} αρνητικές, {amb} ασαφείς"},
    "metrics.paths_none": {"en": "no directed path between the selected elements", "es": "no hay vía dirigida entre los elementos seleccionados", "fr": "aucun chemin dirigé entre les éléments sélectionnés", "de": "kein gerichteter Pfad zwischen den ausgewählten Elementen", "lt": "tarp pasirinktų elementų nėra kryptinio kelio", "pt": "não há via direcionada entre os elementos selecionados", "it": "nessun percorso diretto tra gli elementi selezionati", "no": "ingen rettet sti mellom de valgte elementene", "el": "δεν υπάρχει κατευθυνόμενη διαδρομή μεταξύ των επιλεγμένων στοιχείων"},
    "metrics.paths_truncated": {"en": "showing the first {max} paths — narrow the pair or lower the depth", "es": "se muestran las primeras {max} vías: acote el par o reduzca la profundidad", "fr": "affichage des {max} premiers chemins — restreignez la paire ou réduisez la profondeur", "de": "die ersten {max} Pfade werden angezeigt — Paar eingrenzen oder Tiefe verringern", "lt": "rodomi pirmieji {max} keliai — susiaurinkite porą arba sumažinkite gylį", "pt": "mostrando as primeiras {max} vias — restrinja o par ou reduza a profundidade", "it": "vengono mostrati i primi {max} percorsi — restringere la coppia o ridurre la profondità", "no": "viser de første {max} stiene — begrens paret eller reduser dybden", "el": "εμφανίζονται οι πρώτες {max} διαδρομές — περιορίστε το ζεύγος ή μειώστε το βάθος"},
```

- [ ] **Step 4: Run `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`** — all pass including the drift test.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(metrics): causal-paths keys in all nine languages (#16)"
```

---

### Task 3: Button-gated UI block + e2e

**Files:**
- Modify: `sespy/modules/analysis_metrics.py` — one line pair in `analysis_metrics_ui` after the cascade pair; state + effects + renderer after the cascade block in the server.
- Modify: `tests/test_metrics_e2e.py` — append after the cascade block, before `await browser.close()`.

**Interfaces:**
- Consumes: `causal_paths(isa, source, target)` (Task 1 shape), i18n keys (Task 2), existing keys `metrics.gov_gap_none` / `metrics.cascade_hint`.
- Produces: DOM nodes `#metrics-paths_summary`, `#metrics-paths_source`, `#metrics-paths_target`, `#metrics-trace_paths`.

- [ ] **Step 1: UI slot** — in `analysis_metrics_ui`, directly after the `cascade_summary` output_ui + hr pair:

```python
                ui.output_ui("paths_summary"),
                ui.tags.hr(),
```

- [ ] **Step 2: Server state + effects + renderer** — in `analysis_metrics_server`, after the cascade block:

```python
    _paths_result = reactive.value(None)

    @reactive.effect
    def _reset_paths():
        # A model change invalidates a previously traced result.
        event_bus.isa_change.get()
        _paths_result.set(None)

    @reactive.effect
    @reactive.event(input.trace_paths, ignore_init=True)
    def _compute_paths():
        _paths_result.set(net_analysis.causal_paths(
            project_data.get().isa_data,
            input.paths_source(), input.paths_target()))

    @output
    @render.ui
    def paths_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 2:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        choices = {el.id: f"{el.id} · {el.label}" for el in isa.elements}
        controls = ui.div(
            ui.input_select("paths_source", t("metrics.paths_source"),
                            choices, selected=isa.elements[0].id),
            ui.input_select("paths_target", t("metrics.paths_target"),
                            choices, selected=isa.elements[-1].id),
            ui.input_action_button("trace_paths", t("metrics.paths_trace"),
                                   class_="btn-sm btn-outline-primary"),
        )
        r = _paths_result.get()
        if r is None:
            return ui.div(
                ui.h5(t("metrics.paths")), controls,
                ui.p(t("metrics.cascade_hint"), class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        if not r["paths"]:
            return ui.div(
                ui.h5(t("metrics.paths")), controls,
                ui.p(t("metrics.paths_none"), class_="text-muted",
                     style="margin-top: 0.5rem;"),
            )
        labels = {el.id: el.label for el in isa.elements}
        header = ui.tags.tr(
            ui.tags.th(""), ui.tags.th("length"), ui.tags.th("polarity"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(" → ".join(labels.get(n, n) for n in row["path"])),
                ui.tags.td(str(row["length"])),
                ui.tags.td(ui.tags.strong(row["polarity"])),
            )
            for row in r["paths"]
        ]
        c = r["counts"]
        trunc_line = None
        if r["truncated"]:
            trunc_line = ui.p(t("metrics.paths_truncated", max=len(r["paths"])),
                              class_="text-muted", style="font-size: 0.85rem;")
        return ui.div(
            ui.h5(t("metrics.paths")), controls,
            ui.p(ui.tags.strong(
                t("metrics.paths_summary", n=len(r["paths"]),
                  pos=c["+"], neg=c["-"], amb=c["0"])),
                style="margin-top: 0.5rem;"),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            trunc_line,
        )
```

- [ ] **Step 3: e2e block** — insert into `tests/test_metrics_e2e.py` after the cascade assertions:

```python
        # --- Causal pathways: select ES02 -> D001, trace, assert goldens ---
        pt_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            pt_text = (await page.inner_text("#metrics-paths_summary")).strip()
            if pt_text:
                break
        assert "Causal pathways" in pt_text, f"expected heading, got: {pt_text!r}"
        await page.select_option("#metrics-paths_source", "ES02")
        await page.select_option("#metrics-paths_target", "D001")
        await page.click("#metrics-trace_paths")
        for _ in range(30):
            await page.wait_for_timeout(500)
            pt_text = (await page.inner_text("#metrics-paths_summary")).strip()
            if "2 paths" in pt_text:
                break
        # Sample golden: ES02 -> D001 has exactly two length-8 negative paths.
        assert "2 paths: 0 positive, 2 negative, 0 ambiguous" in pt_text, \
            f"expected summary, got: {pt_text!r}"
        assert "Food provisioning" in pt_text and "Tourism demand" in pt_text, \
            f"expected label chain endpoints, got: {pt_text!r}"
        print(f"causal pathways block: OK ({pt_text[:120]!r})")
```

- [ ] **Step 4: Sanity-import** (`micromamba run -n shiny python -c "import sespy.modules.analysis_metrics"`), then the full CI-parity unit suite once (expect 517 passed: 516 + Task 2's presence test). Do NOT run the e2e suite.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/analysis_metrics.py tests/test_metrics_e2e.py
git commit -m "feat(metrics): button-gated causal-pathways block with source/target selectors (#16)"
```

---

### Task 4: Changelog, merge, close issue #16

- [ ] **Step 1: Changelog** — first bullet under `## [Unreleased]` in `CHANGELOG.md`:

```markdown
- New button-gated "Causal pathways" block on the Network Metrics card (#16):
  enumerate the directed simple paths between any two elements with compound
  polarity (odd negatives flip the sign), honest truncation, and a
  positive/negative/ambiguous summary (Applied Soft Computing 2026,
  doi:10.1016/j.asoc.2026.115925 — static layer only).
```

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): causal-pathways block under Unreleased (#16)"
```

- [ ] **Step 2: Merge and push** (after the final branch review is clean AND the detached full e2e is green):

```bash
git checkout main
git merge --no-ff feat/causal-paths -m "feat: causal path tracer (#16)"
git push
```

- [ ] **Step 3: Close issue #16** noting deviations: dict of row-dicts + counts + truncated flag, not a DataFrame (`network.py` pandas-free); signature takes `isa`, not `g`; a `max_paths` cap (default 100) with an honest truncated flag was added beyond the issue's depth-only cap; UI is button-gated (cascade precedent) rather than merely collapsed; `'0'`/ambiguous polarity is implemented but unreachable through current ingresses (documented as forward-looking).

---

## Self-review notes

- Spec coverage: function + empty shapes + sign arithmetic incl. `'0'` (Task 1), edges-cutoff semantics documented (Task 1 docstring), honest `max_paths` (Task 1 + test), 7 i18n keys + presence (Task 2), selectors + button gating + summary line + truncation note (Task 3), scoped e2e with the two-negative-paths golden (Task 3), changelog + issue close with deviations (Task 4).
- Type consistency: result keys identical across Tasks 1 and 3; DOM ids identical across Task 3's renderer and e2e; i18n params match `t()` kwargs.
- Golden values computed against the real repo on 2026-08-15 via a reference implementation of this exact spec.
