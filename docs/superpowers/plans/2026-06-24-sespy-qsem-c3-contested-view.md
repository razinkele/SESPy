# QSEM-C3 Contested-Edges View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface multi-rater disagreement in the Rate Connections table — a `disagreement` column, a "contested only" filter, and an "{n} contested edges" caption — built on the shipped `connection_disagreement`.

**Architecture:** One pure formatter `network.disagreement_cell(d, *, contested_label)`; the rest is wiring in the shipped `sespy/modules/rate_connections.py`. A `displayed_connections()` reactive.calc returns `(true_idx, conn)` pairs (full when the filter is off, only `polarity_contested` rows when on); `_selected()` is refactored to resolve the cached displayed-row `sel_idx` through that calc to the TRUE full-list index — closing a silent wrong-connection corruption path under the filter.

**Tech Stack:** Python 3.11, Shiny for Python, pandas (DataGrid), pytest, Playwright.

## Global Constraints

- **Index contract (REQUIRED — prevents silent wrong-connection corruption):** `sel_idx` is a row index into the *displayed* list. `_selected()` MUST resolve it via `displayed_connections()` to the TRUE index into `project_data.get().isa_data.connections`; the existing raw `return idx, conns[idx]` MUST be removed and no other lookup path may remain. FORBIDDEN: any value/identity scan (`.index(conn)`) — `Connection` is a value dataclass.
- `connections_table` render and `_selected()` MUST iterate the SAME `displayed_connections()` list.
- `_save`/`_remove` need NO change: `_selected()` hands them the true full-list index they already use.
- Reset `sel_idx` to `None` on BOTH `input.rater` (already shipped) AND `input.contested_only` change.
- The contested-count caption counts the FULL list (`polarity_contested`), not the filtered one.
- `disagreement_cell` is pure (no `t()` inside); the module passes `contested_label=t("rate.contested")`.
- Filter and count read `d["polarity_contested"]` directly, not through the formatter.
- All user-facing strings via `t()` (the legend footnote is a fixed ASCII string — no new key). New i18n keys ×9 languages (`en,es,fr,de,lt,pt,it,no,el`), enforced by `tests/test_i18n.py::test_loader_handles_all_supported_languages`.
- `t(key, n=…)` interpolation is supported (see `tests/test_i18n.py::test_translator_format_interpolation`).
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `network.disagreement_cell`

**Files:**
- Modify: `sespy/network.py` (add after `disagreement` helpers near `connection_disagreement`)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: nothing (pure dict → str).
- Produces: `disagreement_cell(d: dict, *, contested_label: str) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py`:

```python
def test_disagreement_cell_contested():
    d = {"polarity_contested": True, "strength_spread": 2.0, "confidence_spread": 3.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "⚠ Contested"


def test_disagreement_cell_spread():
    d = {"polarity_contested": False, "strength_spread": 2.0, "confidence_spread": 3.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "~ 2/3"


def test_disagreement_cell_spread_confidence_only():
    d = {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 4.0}
    assert network.disagreement_cell(d, contested_label="X") == "~ 0/4"


def test_disagreement_cell_none():
    d = {"polarity_contested": False, "strength_spread": 0.0, "confidence_spread": 0.0}
    assert network.disagreement_cell(d, contested_label="Contested") == "—"


def test_disagreement_cell_from_real_connection_disagreement():
    from sespy.data_structure import Connection, Rating
    # +/- split → contested
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", polarity="+"), Rating(rater_id="s2", polarity="-")])
    assert network.disagreement_cell(network.connection_disagreement(c),
                                     contested_label="Contested") == "⚠ Contested"
    # same sign, weak vs strong → spread (strength rank 1 vs 3 → 2; confidence 3/3 → 0)
    c2 = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", polarity="+", strength="weak"),
        Rating(rater_id="s2", polarity="+", strength="strong")])
    assert network.disagreement_cell(network.connection_disagreement(c2),
                                     contested_label="X") == "~ 2/0"
    # single rating → none
    c3 = Connection(source="A", target="B", ratings=[Rating(rater_id="s1")])
    assert network.disagreement_cell(network.connection_disagreement(c3),
                                     contested_label="X") == "—"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "disagreement_cell" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'disagreement_cell'`.

- [ ] **Step 3: Implement**

Add to `sespy/network.py` right after `connection_disagreement`:

```python
def disagreement_cell(d: dict, *, contested_label: str) -> str:
    """Column cell text for a connection's disagreement, from a
    connection_disagreement() result + a pre-translated contested label. Pure
    (no t() inside) so every branch — including the spread numbers — is
    unit-testable directly."""
    if d["polarity_contested"]:
        return f"⚠ {contested_label}"
    if d["strength_spread"] > 0 or d["confidence_spread"] > 0:
        return f"~ {d['strength_spread']:.0f}/{d['confidence_spread']:.0f}"
    return "—"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "disagreement_cell" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): disagreement_cell — contested/spread/none column text"
```

---

### Task 2: i18n keys

**Files:**
- Modify: `sespy/translations/core.json`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces keys consumed by Task 3: `rate.contested`, `rate.contested_only`, `rate.contested_count`.

- [ ] **Step 1: Add the 3 keys**

Insert into the `"translation"` object in `sespy/translations/core.json` (valid JSON, UTF-8, non-ASCII kept as-is):

```json
"rate.contested": {"en": "Contested", "es": "Disputado", "fr": "Contesté", "de": "Umstritten", "lt": "Ginčytinas", "pt": "Contestado", "it": "Conteso", "no": "Omstridt", "el": "Αμφισβητούμενο"},
"rate.contested_only": {"en": "Show contested only", "es": "Mostrar solo disputados", "fr": "Afficher uniquement les contestés", "de": "Nur umstrittene anzeigen", "lt": "Rodyti tik ginčytinus", "pt": "Mostrar apenas contestados", "it": "Mostra solo contesi", "no": "Vis kun omstridte", "el": "Εμφάνιση μόνο αμφισβητούμενων"},
"rate.contested_count": {"en": "{n} contested edges", "es": "{n} conexiones disputadas", "fr": "{n} liens contestés", "de": "{n} umstrittene Verbindungen", "lt": "{n} ginčytini ryšiai", "pt": "{n} conexões contestadas", "it": "{n} connessioni contese", "no": "{n} omstridte koblinger", "el": "{n} αμφισβητούμενες συνδέσεις"}
```

- [ ] **Step 2: Verify**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS (incl. `test_loader_handles_all_supported_languages`).

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(rate): contested view keys (3 keys, 9 languages)"
```

---

### Task 3: Contested view in `rate_connections.py` + e2e

**Files:**
- Modify: `sespy/modules/rate_connections.py`
- Test: `tests/test_rate_connections_e2e.py` (extend)

**Interfaces:**
- Consumes: `network.connection_disagreement` (shipped), `network.disagreement_cell` (Task 1), keys from Task 2.

- [ ] **Step 1: Add the UI controls (sidebar checkbox, count caption, legend)**

In `rate_connections_ui()`, replace the `ui.layout_sidebar(...)` block with:

```python
        ui.layout_sidebar(
            ui.sidebar(
                ui.output_ui("rater_picker"),
                ui.tags.hr(),
                ui.input_checkbox("contested_only", t("rate.contested_only"), value=False),
                width=260,
            ),
            ui.div(
                ui.output_ui("contested_count"),
                ui.output_data_frame("connections_table"),
                ui.tags.small("⚠ contested sign · ~ strength/confidence spread (0–2 / 0–4)",
                              class_="text-muted"),
                ui.tags.hr(),
                ui.output_ui("rating_editor"),
                ui.tags.hr(),
                ui.h5(t("rate.current_ratings")),
                ui.output_ui("current_ratings"),
            ),
        ),
```

- [ ] **Step 2: Add `displayed_connections()` and refactor `connections_table` + `_selected()`**

In `rate_connections_server`, immediately after `sel_idx = reactive.value(None)` add:

```python
    @reactive.calc
    def displayed_connections():
        """(true_idx, connection) pairs for the table — full list, or only
        polarity-contested rows when the filter is on. true_idx is the index
        into the FULL isa_data.connections list (for persistence)."""
        event_bus.isa_change.get()
        conns = project_data.get().isa_data.connections
        try:
            only = input.contested_only()
        except Exception:
            only = False
        if not only:
            return list(enumerate(conns))
        return [(i, c) for i, c in enumerate(conns)
                if network.connection_disagreement(c)["polarity_contested"]]
```

Replace the entire `connections_table` render function with:

```python
    @output
    @render.data_frame
    def connections_table():
        import pandas as pd
        try:
            rater = input.rater()
        except Exception:
            rater = None
        isa = project_data.get().isa_data
        by_id = {el.id: el.label for el in isa.elements}
        contested_label = t("rate.contested")
        cols = ["source", "target", "polarity", "strength", "confidence", "delay",
                "#ratings", "mine", "disagreement"]
        rows = []
        for _true_idx, c in displayed_connections():
            d = network.connection_disagreement(c)
            rows.append({
                "source": f"{c.source} · {by_id.get(c.source, '?')}",
                "target": f"{c.target} · {by_id.get(c.target, '?')}",
                "polarity": c.polarity,
                "strength": c.strength,
                "confidence": c.confidence,
                "delay": c.delay,
                "#ratings": len(c.ratings),
                "mine": "✓" if rater and any(r.rater_id == rater for r in c.ratings) else "—",
                "disagreement": network.disagreement_cell(d, contested_label=contested_label),
            })
        return render.DataGrid(
            pd.DataFrame(rows or [{k: "" for k in cols}]),
            selection_mode="row", height="260px",
        )
```

Replace the entire `_selected()` function with the index-contract version:

```python
    def _selected():
        """(true_idx, connection) for the cached displayed-row selection, or
        (None, None). SOLE lookup path: resolves sel_idx (a DISPLAYED-row index)
        through displayed_connections() to the TRUE full-list index. Never index
        isa_data.connections by the raw sel_idx (would corrupt under the filter)."""
        idx = sel_idx.get()
        if idx is None:
            return None, None
        pairs = displayed_connections()
        if idx >= len(pairs):
            return None, None
        return pairs[idx]   # (true_idx, conn)
```

- [ ] **Step 3: Add the filter-reset effect and the count caption**

After the existing `_reset_selection_on_rater` effect, add:

```python
    @reactive.effect
    @reactive.event(input.contested_only)
    def _reset_selection_on_filter():
        sel_idx.set(None)
```

After the `current_ratings` render function, add:

```python
    @output
    @render.ui
    def contested_count():
        event_bus.isa_change.get()
        conns = project_data.get().isa_data.connections
        n = sum(1 for c in conns
                if network.connection_disagreement(c)["polarity_contested"])
        return ui.tags.p(t("rate.contested_count", n=n),
                         class_="text-muted", style="margin-bottom:4px;")
```

(No change to `_save`/`_remove`: `_selected()` now returns the true full-list index they already use via `conns[idx] = …`.)

- [ ] **Step 4: Smoke-test import + app build**

Run: `micromamba run -n shiny python -c "import app; print('ok')"`
Expected: prints `ok`.

Run: `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_i18n.py -q`
Expected: all pass (sanity that Task 1/2 symbols/keys resolve as used).

- [ ] **Step 5: Extend the e2e with the contested flow**

In `tests/test_rate_connections_e2e.py`, insert this block in `main()` immediately **before** `await browser.close()` (it continues from the C2 flow, where stakeholder "Port Authority" already rated the first connection `+`):

```python
        # --- C3: make the first connection CONTESTED with a 2nd rater ---
        # 1. Add a second stakeholder.
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_selector("#stakeholders-sh_name", timeout=30000)
        await page.fill("#stakeholders-sh_name", "Coastal NGO")
        await _set_select(page, "stakeholders-sh_type", "government")  # any valid code; reuse C2's proven one
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # 2. Back to Rate Connections; switch the rater to the 2nd option.
        await page.click("#sespy_nav_rate")
        await page.wait_for_selector("#rate-connections_table table tbody tr", timeout=30000)
        await page.evaluate(
            "() => { const s=document.getElementById('rate-rater');"
            " if(s){ s.selectedIndex=1; s.dispatchEvent(new Event('change',{bubbles:true})); } }"
        )
        await page.wait_for_timeout(500)

        # 3. Switching rater reset sel_idx — RE-CLICK the first row (TD), required.
        await page.click(RATE_ROW)
        await page.wait_for_selector("#rate-save_rating", timeout=30000)

        # 4. Rate it with OPPOSITE polarity ("-"), then save.
        await page.evaluate(
            "() => { const r=document.querySelector(\"#rate-ed_polarity input[value='-']\");"
            " if(r){ r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); } }"
        )
        await page.click("#rate-save_rating")

        # 5. Poll until the first row's disagreement cell shows the contested marker.
        contested = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if any("⚠" in c for c in cells):
                contested = True
                break
        assert contested, f"first connection not marked contested: {cells}"

        # 6. Count caption reads 1.
        count_txt = await page.evaluate(
            "() => { const e=document.getElementById('rate-contested_count');"
            " return e ? e.textContent : ''; }"
        )
        assert "1" in count_txt, f"contested count caption wrong: {count_txt!r}"

        # 7. Filter narrows the table to exactly one row.
        await page.check("#rate-contested_only")
        narrowed = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            n = await page.evaluate(
                "() => document.querySelectorAll('#rate-connections_table table tbody tr').length"
            )
            if n == 1:
                narrowed = True
                break
        assert narrowed, f"contested-only filter did not narrow to 1 row (got {n})"
        print("rate connections contested view: OK")
```

- [ ] **Step 6: Run the e2e**

Start a server and run the script directly (as the C2 task did):
```
# background: micromamba run -n shiny shiny run --port 8000 app.py
# then:       micromamba run -n shiny python tests/test_rate_connections_e2e.py
```
Expected: prints both `rate connections save: OK` and `rate connections contested view: OK`. If it can't run for an infra reason (not a code defect), report DONE_WITH_CONCERNS with detail and still commit.

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/rate_connections.py tests/test_rate_connections_e2e.py
git commit -m "feat(rate): contested-edges view — disagreement column, filter, count"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: prior baseline + 5 new `disagreement_cell` tests, all passing.
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`; `test_rate_connections_e2e.py` passes (both the C2 save flow and the C3 contested flow).
- [ ] Index contract honored: `_selected()` resolves only through `displayed_connections()`; no raw `conns[idx]` against the full list remains; no `.index(conn)` scan.
