# Quadrant Median-Split Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Factor Quadrant split each axis at the mean (default) or the median, with a data-triggered skew warning, so hub-skewed graphs don't hide secondary leverage points.

**Architecture:** A shared `axis_threshold(values, split)` helper used by both the classifier (`influence_dependence`) and the plot's cross-hairs so they always agree; a `_axis_sums` refactor (one definition of per-node sums) feeding both `influence_dependence` and a new `influence_skew` flag; a sidebar mean/median radio and a skew caption in the quadrant module.

**Tech Stack:** Python 3.11+ (`statistics`), Shiny for Python, matplotlib, pandas; Playwright e2e. Env: micromamba `shiny` (`micromamba run -n shiny …`).

## Global Constraints

- No data-model / schema change. No `PROJECT_SCHEMA_VERSION` bump.
- Default `split="mean"` — every existing caller/test of `influence_dependence` stays green.
- The **degeneracy guard keeps using the mean** (`_variance` about the mean, `not weight_by_pair`); the split ONLY changes the classification cross-hair (`thr_inf`/`thr_dep`). Do NOT route the split into the variance guard.
- `_axis_sums` returns `(influence, dependence, weight_by_pair)` so `influence_dependence` keeps its exact `not weight_by_pair` check.
- Skew predicate is strict: `max(nz) > 3 · median(nz)` over non-zero influence; `False` if `<2` non-zero.
- Skew caption shows only when `influence_skew(isa)` AND `split == "mean"`.
- New i18n keys (`quadrant.split`, `quadrant.split_mean`, `quadrant.split_median`, `quadrant.skew_warning`) in all 9 languages (`tests/test_i18n.py` fails on English-only).
- UI text via module-level `t()`. e2e standalone asyncio gated via `python tests/run_e2e.py` (never `-k "not e2e"` / pytest on e2e scripts).
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Windows: never multi-line `python -c` (splits per line → stray files); never `>`/`>>` to create files; `git status` after runs.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `sespy/network.py` | refactor + add | `_axis_sums`, `axis_threshold`, `influence_dependence(split=)`, `influence_skew` |
| `tests/test_network.py` | append | unit tests (threshold, sample D001 pin, default==mean, skew) |
| `sespy/translations/core.json` | add | 4 i18n keys × 9 languages |
| `sespy/modules/analysis_quadrant.py` | edit | split radio, `rows()` split, plot `thr_*`, skew caption |
| `tests/test_quadrant_e2e.py` | extend | toggle median → D001 quadrant changes |

---

### Task 1: Pure layer — `_axis_sums`, `axis_threshold`, `influence_dependence(split=)`, `influence_skew`

**Files:**
- Modify: `sespy/network.py` (refactor `influence_dependence` ~194-250; add helpers)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Produces: `axis_threshold(values: list[float], split: str) -> float`;
  `influence_dependence(isa, *, split="mean") -> dict[str, dict]` (same return shape, new keyword);
  `influence_skew(isa, *, k=3.0) -> bool`;
  private `_axis_sums(isa) -> tuple[dict, dict, dict]`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py` (the `isa` fixture loads `data/sample_ses.json`):

```python
def test_axis_threshold():
    assert network.axis_threshold([1, 2, 3, 4], "mean") == 2.5
    assert network.axis_threshold([1, 2, 3, 4], "median") == 2.5
    assert network.axis_threshold([1, 2, 3, 100], "mean") == 26.5
    assert network.axis_threshold([1, 2, 3, 100], "median") == 2.5  # robust to outlier


def test_influence_dependence_default_is_mean(isa):
    assert network.influence_dependence(isa) == network.influence_dependence(isa, split="mean")


def test_influence_dependence_median_reclassifies_sample(isa):
    mean_q = network.influence_dependence(isa, split="mean")
    med_q = network.influence_dependence(isa, split="median")
    # Empirically verified on data/sample_ses.json (mean_inf 12.18, median_inf 12.0):
    assert mean_q["D001"]["quadrant"] == "buffering"
    assert med_q["D001"]["quadrant"] == "active"
    assert any(mean_q[k]["quadrant"] != med_q[k]["quadrant"] for k in mean_q)


def _skew_fixture():
    """isa where node 'A' has 4 strong out-edges (influence 12) and each of
    B,C,D,E has 1 weak out-edge (influence 1) → nz=[12,1,1,1,1], max 12 > 3·1."""
    from sespy.data_structure import Element, Connection, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("A", "B", "C", "D", "E")]
    conns = [Connection(source="A", target=t, strength="strong", confidence=1)
             for t in ("B", "C", "D", "E")]
    conns += [Connection(source=s, target="A", strength="weak", confidence=1)
              for s in ("B", "C", "D", "E")]
    return IsaData(elements=els, connections=conns)


def test_influence_skew_true_on_hub():
    assert network.influence_skew(_skew_fixture()) is True


def test_influence_skew_false_balanced():
    from sespy.data_structure import Element, Connection, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=1),
             Connection(source="B", target="C", strength="medium", confidence=1),
             Connection(source="C", target="A", strength="medium", confidence=1)]
    assert network.influence_skew(IsaData(elements=els, connections=conns)) is False


def test_influence_skew_false_boundary():
    # nz = [6, 2, 2, 2]: max 6 == 3*median 2 -> strict '>' is False.
    from sespy.data_structure import Element, Connection, IsaData
    els = [Element(id=i, label=i, type="Drivers") for i in ("H", "B", "C", "D", "S")]
    conns = [
        Connection(source="H", target="S", strength="strong", confidence=2),  # H influence 6
        Connection(source="B", target="S", strength="medium", confidence=1),  # B influence 2
        Connection(source="C", target="S", strength="medium", confidence=1),  # C influence 2
        Connection(source="D", target="S", strength="medium", confidence=1),  # D influence 2
    ]
    assert network.influence_skew(IsaData(elements=els, connections=conns)) is False


def test_influence_skew_false_empty():
    from sespy.data_structure import IsaData
    assert network.influence_skew(IsaData()) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "axis_threshold or influence_skew or median_reclassifies or default_is_mean" -v`
Expected: FAIL — `AttributeError: module 'sespy.network' has no attribute 'axis_threshold'` (and `influence_skew`), and the `split=` keyword is unknown.

- [ ] **Step 3: Refactor + implement** — in `sespy/network.py`, replace the body of `influence_dependence` and add the helpers. The full replacement (preserving the exact existing behaviour for `split="mean"`):

```python
def _axis_sums(isa: IsaData) -> tuple[dict[str, float], dict[str, float], dict[tuple[str, str], float]]:
    """Per-node Σ edge weights: (influence, dependence, weight_by_pair).
    Parallel (source,target) edges deduplicated (last-wins); self-loops and
    dangling refs skipped. Shared by influence_dependence and influence_skew."""
    influence = {el.id: 0.0 for el in isa.elements}
    dependence = {el.id: 0.0 for el in isa.elements}
    ids = set(influence)
    weight_by_pair: dict[tuple[str, str], float] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        weight_by_pair[(c.source, c.target)] = _edge_weight(c)
    for (src, tgt), w in weight_by_pair.items():
        influence[src] += w
        dependence[tgt] += w
    return influence, dependence, weight_by_pair


def axis_threshold(values: list[float], split: str) -> float:
    """Cross-hair statistic for one quadrant axis. 'median' -> median (robust to
    a hub); anything else -> arithmetic mean. Used by BOTH influence_dependence
    (classification) and the quadrant plot (cross-hair lines) so they agree.
    Assumes a non-empty list (callers guard the empty-graph case first)."""
    import statistics
    return statistics.median(values) if split == "median" else statistics.mean(values)


def influence_dependence(isa: IsaData, *, split: str = "mean") -> dict[str, dict]:
    """Vester influence × dependence per node — weighted, sign-agnostic.

    influence  = Σ _edge_weight over a node's outgoing edges (to OTHERS)
    dependence = Σ _edge_weight over a node's incoming edges (from OTHERS)
    quadrant   = active | critical | reactive | buffering, split at the mean
                 (default) or median of each axis (>= threshold = high side);
                 or 'undetermined' when the system has no structural
                 differentiation. `split` ('mean'|'median') only changes the
                 classification cross-hair, never the degeneracy guard.

    Parallel (source, target) edges are deduplicated (last-wins); self-loops are
    skipped. Returns {} for an empty graph; never raises.
    """
    elements = isa.elements
    if not elements:
        return {}

    influence, dependence, weight_by_pair = _axis_sums(isa)
    n = len(elements)

    # Degeneracy guard: ALWAYS about the mean (split-independent by design).
    mean_inf = sum(influence.values()) / n
    mean_dep = sum(dependence.values()) / n

    def _variance(values: dict[str, float], mean: float) -> float:
        return sum((v - mean) ** 2 for v in values.values()) / n

    if not weight_by_pair or (
        _variance(influence, mean_inf) < 1e-12
        and _variance(dependence, mean_dep) < 1e-12
    ):
        return {
            el.id: {"influence": influence[el.id], "dependence": dependence[el.id],
                    "quadrant": "undetermined"}
            for el in elements
        }

    # Classification cross-hair follows the chosen split.
    thr_inf = axis_threshold(list(influence.values()), split)
    thr_dep = axis_threshold(list(dependence.values()), split)

    out: dict[str, dict] = {}
    for el in elements:
        i, d = influence[el.id], dependence[el.id]
        hi_i, hi_d = i >= thr_inf, d >= thr_dep
        if hi_i and not hi_d:
            quadrant = "active"
        elif hi_i and hi_d:
            quadrant = "critical"
        elif hi_d:
            quadrant = "reactive"
        else:
            quadrant = "buffering"
        out[el.id] = {"influence": i, "dependence": d, "quadrant": quadrant}
    return out


def influence_skew(isa: IsaData, *, k: float = 3.0) -> bool:
    """True when the influence distribution is hub-skewed: max(v) > k * median(v)
    over the non-zero influence values. False when <2 non-zero values. Pure."""
    import statistics
    influence, _, _ = _axis_sums(isa)
    nz = [v for v in influence.values() if v > 0]
    if len(nz) < 2:
        return False
    return max(nz) > k * statistics.median(nz)
```

Note: this is the exact existing classification logic; only `_axis_sums` is extracted, `split` is added, and `thr_*` replaces `mean_*` in the `>=` comparison (with `mean_*` retained for the guard).

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "axis_threshold or influence_skew or median_reclassifies or default_is_mean" -v`
Expected: PASS (8 passed).
Then the full file (no regression — the existing 8 `influence_dependence`/quadrant tests must stay green): `micromamba run -n shiny python -m pytest tests/test_network.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): mean|median split + influence_skew for the quadrant

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: i18n keys

**Files:**
- Modify: `sespy/translations/core.json`

**Interfaces:** Produces `quadrant.split`, `quadrant.split_mean`, `quadrant.split_median`, `quadrant.skew_warning` (consumed by Task 3).

- [ ] **Step 1: Add the keys.** Create a temp `add_split_i18n.py` at the repo root, run it once, then delete it:

```python
import json, pathlib
PATH = pathlib.Path("sespy/translations/core.json")
data = json.loads(PATH.read_text(encoding="utf-8"))
tr = data["translation"]
KEYS = {
  "quadrant.split": {"en":"Cross-hair split","es":"División de ejes","fr":"Séparation des axes","de":"Achsen-Trennung","lt":"Ašių skirstymas","pt":"Divisão dos eixos","it":"Divisione assi","no":"Aksedeling","el":"Διαχωρισμός αξόνων"},
  "quadrant.split_mean": {"en":"Mean","es":"Media","fr":"Moyenne","de":"Mittelwert","lt":"Vidurkis","pt":"Média","it":"Media","no":"Gjennomsnitt","el":"Μέσος όρος"},
  "quadrant.split_median": {"en":"Median","es":"Mediana","fr":"Médiane","de":"Median","lt":"Mediana","pt":"Mediana","it":"Mediana","no":"Median","el":"Διάμεσος"},
  "quadrant.skew_warning": {"en":"Distribution is hub-skewed — consider the median split","es":"La distribución está sesgada por un nodo dominante — considere la división por mediana","fr":"La distribution est asymétrique (nœud dominant) — envisagez la séparation par médiane","de":"Verteilung ist durch einen Hub verzerrt — erwägen Sie die Median-Trennung","lt":"Pasiskirstymas iškreiptas dominuojančio mazgo — apsvarstykite medianos skirstymą","pt":"A distribuição está enviesada por um nó dominante — considere a divisão por mediana","it":"La distribuzione è sbilanciata da un nodo dominante — valuta la divisione per mediana","no":"Fordelingen er nav-skjev — vurder median-deling","el":"Η κατανομή είναι στρεβλωμένη από έναν κόμβο — εξετάστε τη διάμεσο διαίρεση"},
}
for k, v in KEYS.items():
    tr[k] = v
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("added", len(KEYS), "keys")
```

Run: `micromamba run -n shiny python add_split_i18n.py` then `rm add_split_i18n.py`.

- [ ] **Step 2: Verify + drift test**

Run: `micromamba run -n shiny python -c "import json;d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation'];ks=[k for k in d if k.startswith('quadrant.split') or k=='quadrant.skew_warning'];print(len(ks),'keys',all(len(d[k])==9 for k in ks))"`
Expected: `4 keys True`.
Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q` → PASS.

- [ ] **Step 3: Confirm no stray files, commit**

Run: `git status --short` (expect only `sespy/translations/core.json`; NO `add_split_i18n.py`).

```bash
git add sespy/translations/core.json
git commit -m "i18n(quadrant): add split/skew keys (4 keys, 9 languages)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Quadrant module — split radio, plot cross-hairs, skew caption

**Files:**
- Modify: `sespy/modules/analysis_quadrant.py`

**Interfaces:**
- Consumes: `axis_threshold`, `influence_dependence(split=)`, `influence_skew` (Task 1); i18n keys (Task 2).
- Produces: no new public symbols; adds `#quadrant-split` input and `#quadrant-skew_caption` output.

- [ ] **Step 1: Add the split radio to the sidebar.** In `analysis_quadrant_ui`, add to the `ui.sidebar(...)` (after the About `ui.p(...)`, before `width=260`):

```python
                ui.tags.hr(),
                ui.input_radio_buttons(
                    "split", t("quadrant.split"),
                    {"mean": t("quadrant.split_mean"), "median": t("quadrant.split_median")},
                    selected="mean", inline=True,
                ),
```

- [ ] **Step 2: Add the skew-caption slot.** In the main `ui.div(...)`, insert between `ui.output_plot("quadrant_plot", height="460px")` and the `ui.tags.hr()`:

```python
                ui.output_ui("skew_caption"),
```

- [ ] **Step 3: Thread the split into `rows()`.** In `analysis_quadrant_server`, change the `rows()` calc:

```python
    @reactive.calc
    def rows() -> dict[str, dict]:
        event_bus.isa_change.get()
        return net_analysis.influence_dependence(project_data.get().isa_data,
                                                 split=input.split())
```

- [ ] **Step 4: Make the plot cross-hairs follow the split.** In `quadrant_plot`, replace the inline mean computation (lines ~99-100) and the `axvline`/`axhline` (lines ~116-117):

```python
        infl = [r["influence"] for r in data.values()]
        dep = [r["dependence"] for r in data.values()]
        thr_inf = net_analysis.axis_threshold(infl, input.split())
        thr_dep = net_analysis.axis_threshold(dep, input.split())
```
and:
```python
        ax.axvline(thr_dep, color="#aaa", linestyle="--", linewidth=1, zorder=1)
        ax.axhline(thr_inf, color="#aaa", linestyle="--", linewidth=1, zorder=1)
```
(Replace every later use of `mean_dep`/`mean_inf` in the plot with `thr_dep`/`thr_inf` — check the quadrant-caption corner positions if they referenced the means.)

- [ ] **Step 5: Add the skew-caption render function.** In `analysis_quadrant_server`, add:

```python
    @output
    @render.ui
    def skew_caption():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if input.split() == "mean" and net_analysis.influence_skew(isa):
            return ui.tags.small(t("quadrant.skew_warning"), class_="text-muted")
        return ui.TagList()
```

- [ ] **Step 6: Verify the module imports + app boots**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_quadrant as m; print(hasattr(m,'analysis_quadrant_server'))"` → `True`.
Run: `micromamba run -n shiny python -c "import app; print('app ok')"` → `app ok`.

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/analysis_quadrant.py
git commit -m "feat(quadrant): mean/median split radio + cross-hairs + skew caption

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: e2e — toggle median reclassifies D001 + full gate

**Files:**
- Modify: `tests/test_quadrant_e2e.py` (extend `main()` before the final screenshot/close)

**Interfaces:** Consumes the running app (`#quadrant-split` radio, the `quadrant_table`).

- [ ] **Step 1: Extend the e2e.** In `tests/test_quadrant_e2e.py`, insert before `await page.screenshot(...)` (after the existing distinct-quadrants assertion):

```python
        # --- mean/median split toggle: D001 reclassifies (verified on the sample) ---
        async def quadrant_by_id():
            return await page.evaluate(
                "() => Object.fromEntries(Array.from(document.querySelectorAll("
                "'#quadrant-quadrant_table table tbody tr')).map(tr => ["
                "tr.querySelector('td:nth-child(2)')?.textContent?.trim(),"
                "tr.querySelector('td:last-child')?.textContent?.trim()]))"
            )

        before = await quadrant_by_id()
        # Toggle the split radio to "median"
        ok = await page.evaluate(
            "() => { const r = document.querySelector("
            "'#quadrant-split input[value=\"median\"]');"
            " if (!r) return false; r.click();"
            " r.dispatchEvent(new Event('change', {bubbles: true})); return true; }"
        )
        assert ok, "#quadrant-split median radio not found"
        await page.wait_for_timeout(2000)  # table re-renders
        after = await quadrant_by_id()
        print(f"D001 mean={before.get('D001')} median={after.get('D001')}")
        assert before.get("D001") and after.get("D001"), "D001 row not found"
        assert before["D001"] != after["D001"], \
            f"D001 quadrant did not change on median split: {before.get('D001')}"
```

- [ ] **Step 2: Run the FULL e2e gate**

Run: `micromamba run -n shiny python tests/run_e2e.py` (generous timeout up to 600000ms).
Expected: all green incl. the extended `test_quadrant_e2e.py`, EXCEPT the known pre-existing `test_report_e2e.py` WeasyPrint red (`tinycss2.color5`) — do not fix that.

- [ ] **Step 3: Run unit + i18n**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_i18n.py -q` → PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_quadrant_e2e.py
git commit -m "test(e2e): quadrant median toggle reclassifies D001

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria
- `axis_threshold`, `influence_dependence(split=)`, `influence_skew` unit tests green; default==mean (no regression); D001 buffering→active under median.
- 4 i18n keys × 9 languages; `test_i18n.py` green.
- Quadrant sidebar has a mean/median radio; the plot cross-hairs follow the split; the skew caption shows only on mean+skewed.
- Full e2e green via `python tests/run_e2e.py` (except the known WeasyPrint red); the e2e asserts D001 reclassifies.
- Four commits, repo clean, no stray files.
