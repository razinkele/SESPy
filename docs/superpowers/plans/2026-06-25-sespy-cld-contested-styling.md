# CLD Contested-Edge Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Style CLD graph edges that are polarity-contested among raters — heavier width + a `⚠` label marker + hover-title detail + a legend line.

**Architecture:** In `_build_pyvis_network`'s edge loop, compute `connection_disagreement(c)` per edge and apply contested styling on the free `width` channel + a `⚠` label marker; one legend line; two i18n keys. No `network.py` change.

**Tech Stack:** Shiny for Python, pyvis, pytest.

## Global Constraints

- **Import fix (REQUIRED):** `cld_visualization.py` currently imports only `from ..network import delay_edge_kwargs`; extend to `from ..network import connection_disagreement, delay_edge_kwargs`.
- Edge loop: `kwargs = delay_edge_kwargs(c)` (fresh dict); `label = c.polarity`; `width = 2`; `if connection_disagreement(c)["polarity_contested"]:` → `label = f"{c.polarity} ⚠"`, `width = 6`, `kwargs["title"] = f'{kwargs["title"]} · ⚠ {t("cld.contested_sign")}'`; then `net.add_edge(source, target, label=label, color=EDGE_COLORS[...], arrows="to", width=width, **kwargs)`. Pass `width`/`label`/`color` explicitly and `title`/`dashes` only via `**kwargs` (no double-keyword collision).
- Legend: add `ui.tags.small(t("cld.contested_legend"), class_="text-muted")` next to the existing `cld.delay_legend` line.
- i18n: `cld.contested_legend` + `cld.contested_sign`, **each with all 9 languages** (en es fr de lt pt it no el) — the spec has the verbatim tables; `test_loader_handles_all_supported_languages` hard-fails on any missing language.
- `polarity_contested` is `False` for <2 ratings → single-author/imported models render unchanged (purely additive).
- pyvis edge dict keys (verified live): `from`, `to`, `label`, `width` (int), `title`, `dashes`, `color`, `arrows`. The `⚠` glyph survives in `label`.
- No `network.py` change. Run pytest/e2e via micromamba `shiny`. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Contested edge styling + legend + i18n + unit test

**Files:**
- Modify: `sespy/translations/core.json` (2 keys × 9 languages)
- Modify: `sespy/modules/cld_visualization.py` (import line ~41; edge loop ~231-240; legend ~135)
- Test: `tests/test_i18n.py` (presence test); `tests/test_cld.py` (contested-styling unit test)

**Interfaces:**
- Produces: contested CLD edge styling; i18n keys `cld.contested_legend`, `cld.contested_sign`.

- [ ] **Step 1: Write the failing i18n presence test**

In `tests/test_i18n.py` add (module-scoped `translations` fixture is the param):
```python
def test_cld_contested_keys_present(translations):
    assert "cld.contested_legend" in translations
    assert "cld.contested_sign" in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py::test_cld_contested_keys_present -v`
Expected: FAIL — keys not present.

- [ ] **Step 3: Add the i18n keys (all 9 languages)**

In `sespy/translations/core.json`, inside the `"translation"` object (next to the other `cld.*` keys), add (valid JSON — mind commas; UTF-8, keep accents/Greek/⚠ exactly):
```json
    "cld.contested_legend": {
      "en": "⚠ / thick edge = raters disagree on the sign",
      "es": "⚠ / arista gruesa = los evaluadores discrepan en el signo",
      "fr": "⚠ / arête épaisse = les évaluateurs sont en désaccord sur le signe",
      "de": "⚠ / dicke Kante = Bewerter sind sich beim Vorzeichen uneinig",
      "lt": "⚠ / stora briauna = vertintojai nesutaria dėl ženklo",
      "pt": "⚠ / aresta grossa = os avaliadores discordam no sinal",
      "it": "⚠ / arco spesso = i valutatori non concordano sul segno",
      "no": "⚠ / tykk kant = vurdererne er uenige om fortegnet",
      "el": "⚠ / παχιά ακμή = οι αξιολογητές διαφωνούν ως προς το πρόσημο"
    },
    "cld.contested_sign": {
      "en": "contested sign",
      "es": "signo en disputa",
      "fr": "signe contesté",
      "de": "umstrittenes Vorzeichen",
      "lt": "ginčijamas ženklas",
      "pt": "sinal contestado",
      "it": "segno conteso",
      "no": "omstridt fortegn",
      "el": "αμφισβητούμενο πρόσημο"
    }
```

- [ ] **Step 4: Smoke-check JSON, then run i18n tests**

`micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('json ok')"` → `json ok`.
Then `micromamba run -n shiny python -m pytest tests/test_i18n.py -v` → PASS (presence + per-language completeness).

- [ ] **Step 5: Write the failing unit test**

In `tests/test_cld.py`, add `Rating` to the data_structure import:
```python
from sespy.data_structure import Element, Connection, IsaData, Rating
```
Then add:
```python
def test_contested_edge_is_styled():
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    contested = Connection(
        source="A", target="B", polarity="+", delay="immediate",
        ratings=[Rating(rater_id="r1", strength="medium", confidence=3, polarity="+", delay="immediate"),
                 Rating(rater_id="r2", strength="medium", confidence=3, polarity="-", delay="immediate")],
    )
    plain = Connection(source="B", target="A", polarity="-", delay="immediate")  # <2 ratings
    isa = IsaData(elements=els, connections=[contested, plain])
    net = _build_pyvis_network(isa, layout_kind="physics", direction="UD",
                               level_sep=150, node_sp=120, size_scale=1.0, font_scale=1.0)
    _, edges, *_ = net.get_network_data()
    by = {(e["from"], e["to"]): e for e in edges}
    ce = by[("A", "B")]
    assert ce["width"] > 2 and "⚠" in ce["label"], f"contested edge not styled: {ce}"
    pe = by[("B", "A")]
    assert pe["width"] == 2 and "⚠" not in pe["label"], f"plain edge wrongly styled: {pe}"
```

Note: the test asserts on `width` and `label` only — NOT the hover `title`. Outside a
Shiny session `t()` returns the key string (verified: `t("cld.delay_legend")` →
`"cld.delay_legend"`), so the title would contain `cld.contested_sign` rather than the
translation; that is irrelevant here because the `⚠` marker lives in `label`
(`f"{c.polarity} ⚠"`, no `t()`) and `width` is a plain int. `t()` returning the key does
NOT raise, so `_build_pyvis_network` runs fine in the unit test.

- [ ] **Step 6: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_cld.py::test_contested_edge_is_styled -v`
Expected: FAIL — the contested edge is rendered with `width == 2` and no `⚠` (current behavior).

- [ ] **Step 7: Implement the styling**

In `sespy/modules/cld_visualization.py`:

a) Extend the network import (line ~41):
```python
from ..network import connection_disagreement, delay_edge_kwargs
```

b) Replace the edge loop (currently ~231-240):
```python
    for c in isa.connections:
        net.add_edge(
            c.source,
            c.target,
            label=c.polarity,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=2,
            **delay_edge_kwargs(c),
        )
```
with:
```python
    for c in isa.connections:
        kwargs = delay_edge_kwargs(c)          # fresh dict per call: {"title": .., "dashes": ..}
        label = c.polarity
        width = 2
        if connection_disagreement(c)["polarity_contested"]:
            label = f"{c.polarity} ⚠"
            width = 6
            kwargs["title"] = f'{kwargs["title"]} · ⚠ {t("cld.contested_sign")}'
        net.add_edge(
            c.source,
            c.target,
            label=label,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=width,
            **kwargs,
        )
```

c) Add the legend line. After the existing `ui.tags.small(t("cld.delay_legend"), class_="text-muted"),` (~line 135), add:
```python
            ui.tags.small(t("cld.contested_legend"), class_="text-muted"),
```

- [ ] **Step 8: Run the unit + i18n tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_cld.py tests/test_i18n.py -v`
Expected: PASS — `test_contested_edge_is_styled` + the pre-existing dash test + i18n.
Then `micromamba run -n shiny python -c "import app; print('ok')"` → `ok`.

- [ ] **Step 9: Commit**

```bash
git add sespy/translations/core.json sespy/modules/cld_visualization.py tests/test_i18n.py tests/test_cld.py
git commit -m "feat(cld): style contested edges (width + ⚠ marker) (#8)"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  (incl. the new presence test, the per-language completeness test, and `test_contested_edge_is_styled`).
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`. `test_cld_e2e.py` must stay green (default rendering unchanged for non-contested models — the sample project has no multi-rater ratings, so no edge changes width).
- [ ] Manual sanity (optional): with two stakeholders rating one connection with opposite polarity, the CLD shows that edge thick + `⚠`.
