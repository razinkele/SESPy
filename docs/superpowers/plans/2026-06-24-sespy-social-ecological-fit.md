# Social-ecological Fit Metric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-level social↔ecological coupling ("fit") diagnostic and surface it in the Network Metrics module.

**Architecture:** One pure `network.social_ecological_fit(isa) -> dict` (with a `network.subsystem(type)` partition helper); the Network Metrics module gains a `fit_summary` block above the top-N table. No schema/data-entry change.

**Tech Stack:** Python 3.11, Shiny for Python, pytest, Playwright.

## Global Constraints

- Partition (single source of truth, `_SUBSYSTEM` dict; keys MUST match `constants.DAPSIWRM_ELEMENTS` exactly): social = Drivers, Activities, Responses, Goods & Benefits; ecological = Pressures, Marine Processes & Functioning, Ecosystem Services.
- `social_ecological_fit` is PURE; `fit = cross_edges / total_edges` where `total_edges = within_social + within_ecological + cross` (0.0 when total is 0). Returns `{n_social, n_ecological, n_other, within_social_edges, within_ecological_edges, cross_edges, total_edges, fit}`.
- Skip self-loops (`source == target`) and dangling refs (endpoint not an element id). Edges touching an unclassified node (`""` subsystem, e.g. `Measures`) are excluded from every tally. (Duplicate `(source,target)` edges are forbidden by the data-entry layer, so no dedup is needed — count each valid connection.)
- UI uses the qualified `ui.output_ui("fit_summary")` (the module imports `ui`, `t`, `net_analysis`). Server adds an `@output @render.ui def fit_summary()` depending on `event_bus.isa_change`.
- `metrics.fit_none` text = "no classifiable cross-boundary edges to assess" (accurate for both the empty-graph and pure-unclassified paths).
- Golden sample value: `social_ecological_fit(load_sample("data/sample_ses.json"))` → `fit == 0.40` (cross_edges=8, within_social_edges=6, within_ecological_edges=6, total_edges=20, n_other=0).
- 3 new i18n keys × 9 languages; `test_i18n` only checks completeness so add a presence test.
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `network.subsystem` + `network.social_ecological_fit`

**Files:**
- Modify: `sespy/network.py` (add near `leverage_realm`/`_DAPSIWRM_REALM`)
- Test: `tests/test_network.py`

**Interfaces:**
- Produces: `subsystem(element_type: str) -> str` (`"social"|"ecological"|""`); `social_ecological_fit(isa) -> dict`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py` (uses the top-level `from sespy import network`; add `from pathlib import Path` if absent):

```python
def test_subsystem_classifies_all_types():
    assert network.subsystem("Drivers") == "social"
    assert network.subsystem("Activities") == "social"
    assert network.subsystem("Responses") == "social"
    assert network.subsystem("Goods & Benefits") == "social"
    assert network.subsystem("Pressures") == "ecological"
    assert network.subsystem("Marine Processes & Functioning") == "ecological"
    assert network.subsystem("Ecosystem Services") == "ecological"
    assert network.subsystem("Measures") == ""
    assert network.subsystem("Bogus") == ""


def test_fit_fully_crossed():
    from sespy.data_structure import IsaData, Element, Connection
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="P", label="p", type="Pressures")],
        connections=[Connection(source="D", target="P")],
    )
    r = network.social_ecological_fit(isa)
    assert r["cross_edges"] == 1 and r["total_edges"] == 1 and r["fit"] == 1.0
    assert r["n_social"] == 1 and r["n_ecological"] == 1 and r["n_other"] == 0


def test_fit_siloed_both_subsystems():
    from sespy.data_structure import IsaData, Element, Connection
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="A", label="a", type="Activities"),
                  Element(id="P", label="p", type="Pressures"),
                  Element(id="ES", label="e", type="Ecosystem Services")],
        connections=[Connection(source="D", target="A"),
                     Connection(source="P", target="ES")],
    )
    r = network.social_ecological_fit(isa)
    assert r == {"n_social": 2, "n_ecological": 2, "n_other": 0,
                 "within_social_edges": 1, "within_ecological_edges": 1,
                 "cross_edges": 0, "total_edges": 2, "fit": 0.0}


def test_fit_empty_graph():
    from sespy.data_structure import IsaData
    r = network.social_ecological_fit(IsaData())
    assert r["total_edges"] == 0 and r["fit"] == 0.0


def test_fit_excludes_measures_self_loop_and_dangling():
    from sespy.data_structure import IsaData, Element, Connection
    isa = IsaData(
        elements=[Element(id="D", label="d", type="Drivers"),
                  Element(id="M", label="m", type="Measures")],
        connections=[Connection(source="D", target="M"),   # touches unclassified → excluded
                     Connection(source="D", target="D"),   # self-loop → skipped
                     Connection(source="D", target="X")],  # dangling → skipped
    )
    r = network.social_ecological_fit(isa)
    assert r["n_other"] == 1
    assert r["total_edges"] == 0 and r["fit"] == 0.0


def test_fit_sample_golden():
    from sespy.data_structure import load_sample
    root = Path(__file__).resolve().parents[1]
    r = network.social_ecological_fit(load_sample(root / "data" / "sample_ses.json"))
    assert r["cross_edges"] == 8
    assert r["within_social_edges"] == 6
    assert r["within_ecological_edges"] == 6
    assert r["total_edges"] == 20
    assert r["n_other"] == 0
    assert round(r["fit"], 2) == 0.40
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "subsystem or fit_" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'subsystem'`.

- [ ] **Step 3: Implement**

Add to `sespy/network.py` near `_DAPSIWRM_REALM`:

```python
_SUBSYSTEM: dict[str, str] = {
    "Drivers": "social",
    "Activities": "social",
    "Responses": "social",
    "Goods & Benefits": "social",
    "Pressures": "ecological",
    "Marine Processes & Functioning": "ecological",
    "Ecosystem Services": "ecological",
}


def subsystem(element_type: str) -> str:
    """'social' | 'ecological' | '' (unknown type, e.g. 'Measures'). Pure."""
    return _SUBSYSTEM.get(element_type, "")


def social_ecological_fit(isa) -> dict:
    """Graph-level social↔ecological coupling. fit = cross / total edges.

    Each element classified via subsystem(); over connections (self-loops and
    dangling refs skipped, edges touching an unclassified node excluded), count
    edges within-social, within-ecological, and crossing the boundary. Pure.
    Duplicate (source,target) edges are forbidden by the data-entry layer, so
    each valid connection is counted once. n_other distinguishes a pure-
    unclassified graph (total 0, but has connections) from a genuinely empty one.
    """
    sub_by_id: dict[str, str] = {}
    n_social = n_ecological = n_other = 0
    for el in isa.elements:
        s = subsystem(el.type)
        sub_by_id[el.id] = s
        if s == "social":
            n_social += 1
        elif s == "ecological":
            n_ecological += 1
        else:
            n_other += 1

    within_social = within_ecological = cross = 0
    for c in isa.connections:
        if c.source == c.target or c.source not in sub_by_id or c.target not in sub_by_id:
            continue
        a, b = sub_by_id[c.source], sub_by_id[c.target]
        if a == "" or b == "":
            continue
        if a != b:
            cross += 1
        elif a == "social":
            within_social += 1
        else:
            within_ecological += 1

    total = within_social + within_ecological + cross
    return {
        "n_social": n_social,
        "n_ecological": n_ecological,
        "n_other": n_other,
        "within_social_edges": within_social,
        "within_ecological_edges": within_ecological,
        "cross_edges": cross,
        "total_edges": total,
        "fit": (cross / total) if total else 0.0,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "subsystem or fit_" -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): social_ecological_fit + subsystem partition"
```

---

### Task 2: i18n keys + presence test

**Files:**
- Modify: `sespy/translations/core.json`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces keys consumed by Task 3: `metrics.fit`, `metrics.fit_caption`, `metrics.fit_none`.

- [ ] **Step 1: Write the failing presence test**

Add to `tests/test_i18n.py` (module-scoped `translations` fixture exists):

```python
def test_metrics_fit_keys_present(translations):
    for key in ("metrics.fit", "metrics.fit_caption", "metrics.fit_none"):
        assert key in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -k "metrics_fit_keys_present" -v`
Expected: FAIL — keys not in `core.json` yet.

- [ ] **Step 3: Add the 3 keys**

Insert into the `"translation"` object in `sespy/translations/core.json` (valid JSON, UTF-8, non-ASCII as-is). `metrics.fit_caption` MUST keep the literal `{cross}` and `{total}` placeholders in every language:

```json
"metrics.fit": {"en": "Social-ecological fit", "es": "Ajuste socioecológico", "fr": "Adéquation socio-écologique", "de": "Sozial-ökologische Passung", "lt": "Socioekologinė dermė", "pt": "Ajuste socioecológico", "it": "Adeguatezza socio-ecologica", "no": "Sosial-økologisk tilpasning", "el": "Κοινωνικο-οικολογική προσαρμογή"},
"metrics.fit_caption": {"en": "{cross} of {total} edges cross the social–ecological boundary", "es": "{cross} de {total} conexiones cruzan la frontera socioecológica", "fr": "{cross} liens sur {total} franchissent la frontière socio-écologique", "de": "{cross} von {total} Verbindungen überschreiten die sozial-ökologische Grenze", "lt": "{cross} iš {total} ryšių kerta socioekologinę ribą", "pt": "{cross} de {total} conexões cruzam a fronteira socioecológica", "it": "{cross} di {total} connessioni attraversano il confine socio-ecologico", "no": "{cross} av {total} koblinger krysser den sosial-økologiske grensen", "el": "{cross} από {total} συνδέσεις διασχίζουν το κοινωνικο-οικολογικό όριο"},
"metrics.fit_none": {"en": "no classifiable cross-boundary edges to assess", "es": "no hay conexiones transfronterizas clasificables para evaluar", "fr": "aucun lien transfrontalier classifiable à évaluer", "de": "keine klassifizierbaren grenzüberschreitenden Verbindungen zu bewerten", "lt": "nėra klasifikuojamų ribą kertančių ryšių vertinti", "pt": "não há conexões transfronteiriças classificáveis para avaliar", "it": "nessuna connessione transfrontaliera classificabile da valutare", "no": "ingen klassifiserbare grensekryssende koblinger å vurdere", "el": "δεν υπάρχουν ταξινομήσιμες διασυνοριακές συνδέσεις προς αξιολόγηση"}
```

- [ ] **Step 4: Run the i18n suite**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS — incl. `test_metrics_fit_keys_present` and `test_loader_handles_all_supported_languages`.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(metrics): social-ecological fit keys (3 keys, 9 languages)"
```

---

### Task 3: Fit summary in the Network Metrics module + e2e

**Files:**
- Modify: `sespy/modules/analysis_metrics.py` (UI `ui.div` at ~line 129; server after the existing calcs ~line 180)
- Test: `tests/test_metrics_e2e.py`

**Interfaces:**
- Consumes: `net_analysis.social_ecological_fit` (Task 1), the 3 i18n keys (Task 2). `ui`, `t`, `net_analysis`, `project_data`, `event_bus` already in scope.

- [ ] **Step 1: Add the UI output**

In `analysis_metrics_ui()`, at the TOP of the main `ui.div(...)` (immediately after `ui.div(` and before `ui.h4(t("metrics.top_ranked"))`), add:

```python
                ui.output_ui("fit_summary"),
                ui.tags.hr(),
```

- [ ] **Step 2: Add the server render function**

In `analysis_metrics_server`, after the existing `@reactive.calc`/render functions (anywhere in the server body, e.g. after `top_rows`), add:

```python
    @output
    @render.ui
    def fit_summary():
        event_bus.isa_change.get()
        r = net_analysis.social_ecological_fit(project_data.get().isa_data)
        if r["total_edges"] == 0:
            return ui.p(t("metrics.fit_none"), class_="text-muted")
        return ui.div(
            ui.h5(t("metrics.fit")),
            ui.tags.strong(f"{r['fit']:.2f}"),
            ui.p(t("metrics.fit_caption", cross=r["cross_edges"], total=r["total_edges"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )
```

- [ ] **Step 3: Smoke-test import + app build**

Run: `micromamba run -n shiny python -c "import app; print('ok')"`
Expected: prints `ok`.

Run: `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_i18n.py -q`
Expected: all pass (sanity that Task 1/2 symbols/keys resolve).

- [ ] **Step 4: Extend the e2e**

`tests/test_metrics_e2e.py` is a standalone `asyncio.run(main())` script (no pytest-asyncio). Add this block at the END of the existing `main()` coroutine, immediately before `await browser.close()`:

```python
        # --- Social-ecological fit summary renders with the golden value ---
        await page.click("#sespy_nav_metrics")
        await page.wait_for_selector("#metrics-fit_summary", timeout=30000)
        fit_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            fit_text = (await page.inner_text("#metrics-fit_summary")).strip()
            if fit_text:
                break
        # Sample (data/sample_ses.json) has 8 cross of 20 edges → fit 0.40 (golden).
        assert "0.40" in fit_text, f"expected fit 0.40 in summary, got: {fit_text!r}"
        print(f"metrics fit summary: OK ({fit_text!r})")
```

- [ ] **Step 5: Run the e2e**

Start a server and run the script directly:
```
# background: micromamba run -n shiny shiny run --port 8000 app.py
# then:       micromamba run -n shiny python tests/test_metrics_e2e.py
```
Expected: prints `metrics fit summary: OK (...)` containing `0.40`, and the existing assertions still pass. If it can't run for an infra reason (not a code defect), report DONE_WITH_CONCERNS with detail and still commit.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/analysis_metrics.py tests/test_metrics_e2e.py
git commit -m "feat(metrics): social-ecological fit summary in the Network Metrics module"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: prior baseline + the new `subsystem`/`fit_*`/`metrics_fit_keys_present` tests, all passing.
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`; `test_metrics_e2e.py` passes (fit summary `0.40` + existing checks).
- [ ] `social_ecological_fit` is pure; partition keys match `DAPSIWRM_ELEMENTS`; "Measures"/unknown excluded (n_other), self-loops/dangling skipped.
