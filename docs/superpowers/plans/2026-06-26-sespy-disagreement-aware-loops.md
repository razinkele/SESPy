# Disagreement-Aware Loop Flagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag loops whose Reinforcing/Balancing classification hinges on a rater-polarity-contested edge — append `⚠` to the behavior label in the loops table.

**Architecture:** A pure `network.loop_polarity_contested(cycle, isa)` helper (mirrors `loop_polarity`'s directed wrap-around edges) + a one-line change in `loops_table`'s `base_row` to append `⚠` + a legend + one i18n key. Loops only (leverage is structural, quadrant is magnitude-based — out of scope).

**Tech Stack:** Python 3.11, Shiny for Python, pytest.

## Global Constraints

- `loop_polarity_contested(cycle: list[str], isa: IsaData) -> bool`: `conn_by_pair = {(c.source, c.target): c for c in isa.connections}`; for `i in range(len(cycle))` check `conn_by_pair.get((cycle[i], cycle[(i+1) % n]))` and `connection_disagreement(c)["polarity_contested"]`; True if any. Mirrors `loop_polarity`'s edge set exactly (verified: `_edge_polarity_lookup` is keyed directed `(source, target)`). `connection_disagreement` is in `network.py` (no import).
- `analysis_loops.py` imports network as **`net_analysis`** (NOT `network`) — call `net_analysis.loop_polarity_contested`.
- In `loops_table`: bind `isa = project_data.get().isa_data` after the `if not rows` guard; in the nested `base_row(r)` set `behavior = t(_BEHAVIOR_KEY[r["behavior"]])`, then `if net_analysis.loop_polarity_contested(r["nodes"], isa): behavior = f"{behavior} ⚠"`, and use `behavior` in the `"behavior"` cell. `base_row` is used in BOTH render branches → `⚠` shows regardless of the uncertainty toggle.
- Legend: `ui.tags.small(t("loops.disagreement_legend"), class_="text-muted")` after `ui.output_data_frame("loops_table")` (~line 142).
- i18n: `loops.disagreement_legend`, **all 9 languages** (spec has the verbatim table) — `test_loader_handles_all_supported_languages` hard-fails on any missing.
- Out of scope: quadrant/leverage flagging; weighting; merging with the #4 uncertainty MC signal.
- No new network.py import. Run pytest via micromamba `shiny`. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `loop_polarity_contested` helper + loops-table ⚠ + legend + i18n

**Files:**
- Modify: `sespy/network.py` (new helper after `loop_polarity`, ~line 95)
- Modify: `sespy/modules/analysis_loops.py` (`loops_table` `base_row` ~285-293; legend ~142)
- Modify: `sespy/translations/core.json` (1 key × 9 languages)
- Test: `tests/test_network.py` (helper unit test); `tests/test_i18n.py` (presence test)

**Interfaces:**
- Produces: `network.loop_polarity_contested(cycle: list[str], isa: IsaData) -> bool`; i18n key `loops.disagreement_legend`.

- [ ] **Step 1: Write the failing helper unit test**

In `tests/test_network.py` add:
```python
def test_loop_polarity_contested():
    from sespy.data_structure import Element, Connection, Rating, IsaData
    from sespy import network

    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="Pressures")]

    def rating(pol):
        return Rating(rater_id=f"r{pol}", strength="medium", confidence=3,
                      polarity=pol, delay="immediate")

    # A→B carries two sign-disagreeing ratings → the loop A→B→A is contested.
    contested = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+"), rating("-")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], contested) is True

    # Unanimous ratings → not contested.
    unanimous = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+"), rating("+")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], unanimous) is False

    # <2 ratings → not contested.
    one = IsaData(elements=els, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[rating("+")]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
    ])
    assert network.loop_polarity_contested(["A", "B"], one) is False

    # A contested edge that is NOT on the loop path → not contested.
    els3 = els + [Element(id="C", label="C", type="Pressures")]
    offpath = IsaData(elements=els3, connections=[
        Connection(source="A", target="B", polarity="+", ratings=[]),
        Connection(source="B", target="A", polarity="+", ratings=[]),
        Connection(source="A", target="C", polarity="+", ratings=[rating("+"), rating("-")]),
    ])
    assert network.loop_polarity_contested(["A", "B"], offpath) is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py::test_loop_polarity_contested -v`
Expected: FAIL — `AttributeError: module 'sespy.network' has no attribute 'loop_polarity_contested'`.

- [ ] **Step 3: Implement the helper**

In `sespy/network.py`, immediately after `loop_polarity` (ends ~line 94), add:
```python
def loop_polarity_contested(cycle: list[str], isa: IsaData) -> bool:
    """True if any directed edge of the cycle is rater-polarity-contested.

    Mirrors loop_polarity's edge iteration (consecutive pairs, wrap-around), so
    the flagged edges are exactly those that determine the loop classification.
    Pure; False for loops whose edges have <2 ratings."""
    conn_by_pair = {(c.source, c.target): c for c in isa.connections}
    n = len(cycle)
    for i in range(n):
        c = conn_by_pair.get((cycle[i], cycle[(i + 1) % n]))
        if c is not None and connection_disagreement(c)["polarity_contested"]:
            return True
    return False
```

- [ ] **Step 4: Run it to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py::test_loop_polarity_contested -v`
Expected: PASS.

- [ ] **Step 5: Write the failing i18n presence test**

In `tests/test_i18n.py` add (module-scoped `translations` fixture is the param):
```python
def test_disagreement_legend_key_present(translations):
    assert "loops.disagreement_legend" in translations
```
Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py::test_disagreement_legend_key_present -v` → FAIL (key not present).

- [ ] **Step 6: Add the i18n key (all 9 languages)**

In `sespy/translations/core.json`, inside `"translation"` (next to the other `loops.*` keys), add (valid JSON — mind commas; UTF-8, keep accents/Greek/⚠ exactly):
```json
    "loops.disagreement_legend": {
      "en": "⚠ = a loop edge has raters disagreeing on its sign (classification disputed)",
      "es": "⚠ = un enlace del bucle tiene evaluadores que discrepan en su signo (clasificación en disputa)",
      "fr": "⚠ = un lien de la boucle a des évaluateurs en désaccord sur son signe (classification contestée)",
      "de": "⚠ = eine Schleifenkante hat Bewerter, die sich beim Vorzeichen uneinig sind (Klassifizierung strittig)",
      "lt": "⚠ = kilpos ryšio ženklą vertintojai vertina nevienodai (klasifikacija ginčytina)",
      "pt": "⚠ = uma aresta do ciclo tem avaliadores em desacordo sobre o seu sinal (classificação contestada)",
      "it": "⚠ = un arco del ciclo ha valutatori in disaccordo sul segno (classificazione contestata)",
      "no": "⚠ = en sløyfekant har vurderere som er uenige om fortegnet (klassifisering omstridt)",
      "el": "⚠ = μια ακμή του κύκλου έχει αξιολογητές που διαφωνούν ως προς το πρόσημό της (αμφισβητούμενη ταξινόμηση)"
    }
```

- [ ] **Step 7: Smoke-check JSON, then run i18n tests**

`micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('json ok')"` → `json ok`.
Then `micromamba run -n shiny python -m pytest tests/test_i18n.py -v` → PASS (presence + per-language completeness).

- [ ] **Step 8: Wire the ⚠ into the loops table + add the legend**

In `sespy/modules/analysis_loops.py`:

a) In `loops_table` (~276), after `if not rows: return pd.DataFrame(columns=cols)` and before `unc = uncertainty_loops()`, bind:
```python
        isa = project_data.get().isa_data
```
and change `base_row` (~285-293) from:
```python
        def base_row(r):
            return {
                "id": r["id"],
                "behavior": t(_BEHAVIOR_KEY[r["behavior"]]),
                "delayed": "✓" if r["delayed"] else "—",
                "type": r["type"],
                "length": r["length"],
                "path": r["path"],
            }
```
to:
```python
        def base_row(r):
            behavior = t(_BEHAVIOR_KEY[r["behavior"]])
            if net_analysis.loop_polarity_contested(r["nodes"], isa):
                behavior = f"{behavior} ⚠"
            return {
                "id": r["id"],
                "behavior": behavior,
                "delayed": "✓" if r["delayed"] else "—",
                "type": r["type"],
                "length": r["length"],
                "path": r["path"],
            }
```

b) Add the legend after `ui.output_data_frame("loops_table"),` (~line 142):
```python
            ui.output_data_frame("loops_table"),
            ui.tags.small(t("loops.disagreement_legend"), class_="text-muted"),
            ui.tags.hr(),
```

- [ ] **Step 9: Verify the app builds + unit suite**

`micromamba run -n shiny python -c "import app; print('ok')"` → `ok`.
`micromamba run -n shiny python -m pytest tests/test_network.py tests/test_i18n.py -q` → all pass.

- [ ] **Step 10: Commit**

```bash
git add sespy/network.py sespy/modules/analysis_loops.py sespy/translations/core.json tests/test_network.py tests/test_i18n.py
git commit -m "feat(loops): flag loops whose classification hinges on a rater-contested edge (#9)"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  (incl. `test_loop_polarity_contested`, the presence test, and the per-language completeness test).
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`. `test_loops_e2e.py` stays green: its behavior selector is a substring match (`"scill" in b.lower()`) and the bundled templates carry no multi-rater ratings, so no `⚠` is appended.
- [ ] Manual sanity (optional): with two stakeholders rating an edge on a loop with opposite polarity, that loop's behavior cell shows `… ⚠`.
