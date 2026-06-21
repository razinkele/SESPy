# Graph-View Delay Styling (B2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render delayed connections as dashed edges (with a delay tooltip) consistently across every node-link graph view, via one shared helper.

**Architecture:** A pure `delay_edge_kwargs(c)` helper in `network.py` returns the vis.js edge kwargs (`dashes` + `title`) encoding a connection's delay; it is spread into the `add_edge(...)` call at all five full-graph builders (CLD, Leverage, Metrics, Simplify, Intervention), giving the delay cue one drift-proof definition. A one-line CLD-canvas caption teaches the cue. Reuses B's `normalize_delay`; no schema change.

**Tech Stack:** Python 3.11+, Shiny for Python, pyvis/vis.js, pandas; Playwright for e2e. Env: micromamba `shiny` (`micromamba run -n shiny …`).

## Global Constraints

- No data-model / schema change. Reads existing `Connection.delay`/`.polarity`. No `PROJECT_SCHEMA_VERSION` bump.
- ONE definition of the delay cue: `delay_edge_kwargs(c)` in `network.py`; spread `**…` into all five builders. Do NOT inline a second copy.
- `dashes` via the `add_edge(..., **kwargs)` keyword path (NOT `EdgeOptions`/`options=`) so `e.dashes` reaches the vis.js DataSet (proven in B).
- The Loop Analysis loop network is NOT touched (B already dashed it; different edge-construction context).
- New i18n key `cld.delay_legend` in all 9 languages (en es fr de lt pt it no el) — `tests/test_i18n.py` fails on English-only. The edge *tooltip* uses the raw delay level (no key).
- UI text via module-level `t()`. e2e are standalone `asyncio.run(main())` scripts gated via `python tests/run_e2e.py` (never `-k "not e2e"` / `pytest` on e2e scripts).
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Windows: never multi-line `python -c` (splits per line → stray files); never `>`/`>>` to create files; `git status` after runs for stray files.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `sespy/network.py` | append | `delay_edge_kwargs(c)` helper |
| `tests/test_network.py` | append | helper unit tests + sample delayed-edge guard |
| `sespy/translations/core.json` | add | `cld.delay_legend` × 9 languages |
| `sespy/modules/cld_visualization.py` | edit | spread helper into edge add; add import; legend caption |
| `sespy/modules/analysis_leverage.py` | edit | spread helper into edge add |
| `sespy/modules/analysis_metrics.py` | edit | spread helper into edge add |
| `sespy/modules/analysis_simplify.py` | edit | spread helper into edge add |
| `sespy/modules/analysis_intervention.py` | edit | spread helper into edge add |
| `tests/test_cld.py` | create | every-builder-applies-it unit test |
| `tests/test_cld_e2e.py` | create | CLD dashed-edge e2e |

---

### Task 1: `delay_edge_kwargs` helper + sample guard

**Files:**
- Modify: `sespy/network.py` (append)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Consumes: `normalize_delay` (`sespy/constants.py`, from B).
- Produces: `delay_edge_kwargs(c) -> dict` returning `{"title": f"{c.polarity} · {delay}", "dashes": <bool>}` where `delay = normalize_delay(c.delay)`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py` (note the `·` is U+00B7 MIDDLE DOT):

```python
def test_delay_edge_kwargs():
    from sespy.data_structure import Connection
    from sespy.network import delay_edge_kwargs
    short = delay_edge_kwargs(Connection(source="A", target="B", polarity="+", delay="short"))
    assert short["dashes"] is True
    assert short["title"] == "+ · short"
    imm = delay_edge_kwargs(Connection(source="A", target="B", polarity="+", delay="immediate"))
    assert imm["dashes"] is False
    assert imm["title"] == "+ · immediate"
    neg = delay_edge_kwargs(Connection(source="A", target="B", polarity="-", delay="long"))
    assert neg["dashes"] is True
    assert neg["title"] == "- · long"


def test_sample_has_a_delayed_connection(isa):
    from sespy.constants import normalize_delay
    delayed = sum(1 for c in isa.connections if normalize_delay(c.delay) != "immediate")
    assert delayed >= 1, "sample lost its seeded delayed edge"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "delay_edge_kwargs or sample_has_a_delayed" -v`
Expected: FAIL — `ImportError: cannot import name 'delay_edge_kwargs'` (the sample-guard test may already pass since the seed exists; the helper test must fail).

- [ ] **Step 3: Implement** — append to `sespy/network.py`:

```python
def delay_edge_kwargs(c) -> dict:
    """vis.js edge kwargs encoding a connection's delay as a dashed line + a
    delay tooltip. Spread into add_edge(...) at every full-graph edge builder
    (CLD, Leverage, Metrics, Simplify, Intervention) so the delay cue is one
    definition, identical across views. `dashes` is an orthogonal channel — it
    composes with the width/opacity cues some of those views overload."""
    from .constants import normalize_delay
    delay = normalize_delay(c.delay)
    return {"title": f"{c.polarity} · {delay}", "dashes": delay != "immediate"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "delay_edge_kwargs or sample_has_a_delayed" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): delay_edge_kwargs() shared edge-styling helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `cld.delay_legend` i18n key

**Files:**
- Modify: `sespy/translations/core.json`

**Interfaces:** Produces i18n key `cld.delay_legend`, consumed by Task 3.

- [ ] **Step 1: Add the key.** Create a temp `add_cld_legend_i18n.py` at the repo root, run it once, then delete it:

```python
import json, pathlib
PATH = pathlib.Path("sespy/translations/core.json")
data = json.loads(PATH.read_text(encoding="utf-8"))
data["translation"]["cld.delay_legend"] = {
    "en": "Dashed edges = delayed links",
    "es": "Aristas discontinuas = enlaces con retardo",
    "fr": "Arêtes en pointillés = liens retardés",
    "de": "Gestrichelte Kanten = verzögerte Verbindungen",
    "lt": "Brūkšninės briaunos = vėluojantys ryšiai",
    "pt": "Arestas tracejadas = ligações com atraso",
    "it": "Archi tratteggiati = collegamenti ritardati",
    "no": "Stiplede kanter = forsinkede koblinger",
    "el": "Διακεκομμένες ακμές = καθυστερημένες συνδέσεις",
}
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("added cld.delay_legend")
```

Run: `micromamba run -n shiny python add_cld_legend_i18n.py` then `rm add_cld_legend_i18n.py`.

- [ ] **Step 2: Verify + drift test**

Run: `micromamba run -n shiny python -c "import json;d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation'];print(len(d['cld.delay_legend'])==9)"`
Expected: `True`.

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`
Expected: PASS.

- [ ] **Step 3: Confirm no stray files, commit**

Run: `git status --short` (expect only `sespy/translations/core.json`; NO `add_cld_legend_i18n.py`).

```bash
git add sespy/translations/core.json
git commit -m "i18n(cld): add cld.delay_legend key (9 languages)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Spread the helper into all five builders + CLD legend caption

**Files:**
- Modify: `sespy/modules/cld_visualization.py` (import + edge add + legend caption)
- Modify: `sespy/modules/analysis_leverage.py`, `analysis_metrics.py`, `analysis_simplify.py`, `analysis_intervention.py` (edge add)
- Test: `tests/test_cld.py` (create)

**Interfaces:**
- Consumes: `delay_edge_kwargs` (Task 1); `cld.delay_legend` (Task 2).
- Produces: dashed delayed edges in all five builders; the CLD legend caption.

- [ ] **Step 1: Write the failing test** — create `tests/test_cld.py`:

```python
"""Every full-graph edge builder applies the shared delay cue (dashes)."""
from sespy.data_structure import Element, Connection, IsaData
from sespy.modules.cld_visualization import _build_pyvis_network
from sespy.modules.analysis_leverage import _build_leverage_network
from sespy.modules.analysis_metrics import _build_metrics_network
from sespy.modules.analysis_simplify import _build_simplified_network
from sespy.modules.analysis_intervention import _build_intervention_network


def _fixture():
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity="+", delay="short"),      # delayed
             Connection(source="B", target="A", polarity="-", delay="immediate")]  # not
    return IsaData(elements=els, connections=conns)


def _dashes_by_edge(net):
    nodes, edges, *_ = net.get_network_data()
    return {(e["from"], e["to"]): e.get("dashes") for e in edges}


def test_every_builder_dashes_the_delayed_edge():
    isa = _fixture()
    builders = [
        _build_pyvis_network(isa, layout_kind="physics", direction="UD",
                             level_sep=150, node_sp=120, size_scale=1.0, font_scale=1.0),
        _build_leverage_network(isa, {"A": 1.0, "B": 0.5}),
        _build_metrics_network(isa, "degree", {"A": 2.0, "B": 1.0}),
        _build_simplified_network(isa),
        # intervention reads info['before']/['after']/['delta'] per surviving
        # node, so pass a complete impact dict (removed_ids empty = nothing ablated).
        _build_intervention_network(
            isa,
            {"A": {"before": 0.0, "after": 0.0, "delta": 0.0},
             "B": {"before": 0.0, "after": 0.0, "delta": 0.0}},
            [],
        ),
    ]
    for net in builders:
        d = _dashes_by_edge(net)
        assert d[("A", "B")] is True, f"delayed edge not dashed in {net}"
        assert d[("B", "A")] is False, f"immediate edge wrongly dashed in {net}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_cld.py -v`
Expected: FAIL — `KeyError`/`AssertionError` (`dashes` is `None`, not `True`, because no builder spreads the helper yet).

- [ ] **Step 3: Add the import + spread in CLD.** In `sespy/modules/cld_visualization.py`, add to the imports (top of file, after the existing `from ..` lines):

```python
from ..network import delay_edge_kwargs
```

Then replace the edge loop (lines 229-237):

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

- [ ] **Step 4: Spread in the four analysis builders.** Each already imports `from .. import network as net_analysis`. Add `**net_analysis.delay_edge_kwargs(c),` as the last arg of each `net.add_edge(...)`:

`analysis_leverage.py` (line ~68):
```python
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=1.5,
            **net_analysis.delay_edge_kwargs(c),
        )
```

`analysis_metrics.py` (line ~98): identical shape (width=1.5) — add `**net_analysis.delay_edge_kwargs(c),` as the last arg.

`analysis_simplify.py` (line ~60): keep its `width=1.5 + 0.5 * net_analysis._STRENGTH_RANK.get(c.strength, 2)` and add `**net_analysis.delay_edge_kwargs(c),` as the last arg.

`analysis_intervention.py` (line ~104): keep its `color={...opacity...}` dict and `width=1.5`, add `**net_analysis.delay_edge_kwargs(c),` as the last arg.

- [ ] **Step 5: Add the CLD legend caption.** In `cld_viz_ui` (`cld_visualization.py`), inside the `ui.div(...)` that wraps `output_pyvis_network("network", ...)`, add a caption immediately after the `output_pyvis_network(...)` call:

```python
            ui.tags.small(t("cld.delay_legend"), class_="text-muted"),
```

- [ ] **Step 6: Run the test + import check**

Run: `micromamba run -n shiny python -m pytest tests/test_cld.py -v`
Expected: PASS.
Run: `micromamba run -n shiny python -c "import app; print('app ok')"`
Expected: `app ok` (all five modules import cleanly).

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/cld_visualization.py sespy/modules/analysis_leverage.py sespy/modules/analysis_metrics.py sespy/modules/analysis_simplify.py sespy/modules/analysis_intervention.py tests/test_cld.py
git commit -m "feat(graph): dash delayed edges across all 5 graph views + CLD legend

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: CLD e2e + full gate

**Files:**
- Create: `tests/test_cld_e2e.py`

**Interfaces:** Consumes the running app (default CLD tab, `cld-network`, the seeded delayed edge).

- [ ] **Step 1: Write the e2e** — create `tests/test_cld_e2e.py` (standalone asyncio, poll pattern from `tests/test_loops_e2e.py`):

```python
"""E2E: the main CLD network dashes the seeded delayed edge."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        # CLD is the default tab; wait for its network container to mount so a
        # "tab never rendered" failure is distinct from an "edges empty" timeout.
        await page.wait_for_selector("#cld-network", timeout=30000)
        # Poll until the network DataSet has edges.
        dashes = None
        for _ in range(16):
            res = await page.evaluate(
                "() => { const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s || !s.edges) return null;"
                " const es = s.edges.get();"
                " return { n: es.length, dashes: es.map(e => e.dashes === true) }; }"
            )
            if res and res["n"]:
                dashes = res
                break
            await page.wait_for_timeout(500)
        print("cld edges:", dashes)
        assert dashes is not None, "cld-network edges not readable"
        assert dashes["n"] == 20, f"expected 20 edges (default, unfiltered), got {dashes['n']}"
        flags = dashes["dashes"]
        assert any(flags), "no dashed (delayed) edge in the CLD"
        assert not all(flags), "expected at least one solid (immediate) edge too"

        await page.screenshot(path="tests/screenshots/cld.png")
        print("\ncld e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the FULL e2e gate**

Run: `micromamba run -n shiny python tests/run_e2e.py` (generous timeout up to 600000ms).
Expected: all green including the new `test_cld_e2e.py`, EXCEPT the known pre-existing `test_report_e2e.py` WeasyPrint red (`tinycss2.color5`) — do not try to fix that one.

- [ ] **Step 3: Run unit + i18n**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_cld.py tests/test_i18n.py -q`
Expected: PASS.

- [ ] **Step 4: Confirm no stray files, commit**

Run: `git status --short` (expect only `tests/test_cld_e2e.py`; `tests/screenshots/` is git-ignored — do not commit the screenshot).

```bash
git add tests/test_cld_e2e.py
git commit -m "test(e2e): CLD dashes the seeded delayed edge (20 edges, some dashed)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria
- `delay_edge_kwargs` unit tests green; sample delayed-edge guard green.
- `cld.delay_legend` in all 9 languages; `test_i18n.py` green.
- All five builders dash the delayed edge (`tests/test_cld.py` green); CLD shows the legend caption.
- Full e2e green via `python tests/run_e2e.py` (except the known WeasyPrint red).
- Four commits, repo clean, no stray files.
