# Delay-Aware Loop Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Connection.delay` a first-class 3-level field (`immediate`/`short`/`long`) and surface it through the Loop Analysis module, flagging delayed balancing loops as "Oscillation-prone".

**Architecture:** Pure logic (`normalize_delay` in `constants.py`; `loop_has_delay` + extended `classify_loops` in `network.py`) is unit-tested without Shiny. The Loop Analysis module reads the new `delayed`/`behavior` fields (no new graph work). Capture is closed by a data-entry `delay` select, `normalize_delay` on Excel import, and one seeded delayed edge in the sample. No schema change.

**Tech Stack:** Python 3.11+, Shiny for Python, pyvis/vis.js, pandas; Playwright for e2e. Env: micromamba `shiny` (`micromamba run -n shiny …`).

## Global Constraints

- No data-model / schema change. `Connection.delay` is already a `str`; constrain values via UI vocabulary + `normalize_delay`. No `PROJECT_SCHEMA_VERSION` bump.
- `classify_loops` **retains** the existing `type` field and only *adds* `delayed`/`behavior` (backward compat: `test_loop_polarity_rule`, `test_report` depend on `type`).
- The sample seed **edits an existing edge's `delay`** — it must NOT add/remove a connection (`test_sample_loads` asserts `connection_count() == 20`, `element_count() == 17`).
- `behavior` ∈ `reinforcing` / `balancing` / `oscillating`, mutually exclusive, summing to `len(loops)`; **oscillating = Balancing AND delayed**.
- Oscillating UI wording is hedged: display "Oscillation-prone" + a structural-signature disclaimer (i18n). Internal key stays `oscillating`.
- `normalize_delay` is conservative: negation/zero sentinels → `immediate`; only genuine free-text → `short`.
- All new i18n keys MUST exist in all 9 catalog languages (en es fr de lt pt it no el) — `tests/test_i18n.py` fails on English-only.
- UI text via the module-level `t()` from `..i18n`.
- e2e tests are standalone `asyncio.run(main())` Playwright scripts (NOT pytest), gated via `python tests/run_e2e.py` — never `-k "not e2e"`, never `pytest` on the e2e scripts.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Windows: never multi-line `python -c` (splits per line → stray files; use single-line or a temp `.py`); never `>`/`>>` to create files; check `git status` for stray files after runs.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `sespy/constants.py` | append | `DELAY_LEVELS`, `_DELAY_IMMEDIATE_SENTINELS`, `normalize_delay` |
| `sespy/network.py` | append + edit | `loop_has_delay`, `_edge_delay_lookup`; extend `classify_loops` |
| `data/sample_ses.json` | edit one edge | seed `MPF2→ES02` `delay:"short"` → an oscillating loop |
| `sespy/translations/core.json` | add | 9 i18n keys × 9 languages |
| `sespy/modules/analysis_loops.py` | edit | summary / table / picker / narrative / dashed edges |
| `sespy/modules/isa_data_entry.py` | edit | delay select + table column |
| `sespy/excel_import.py` | edit one line | `normalize_delay` on import |
| `tests/test_network.py` | append | unit + done-criterion tests |
| `tests/test_loops_e2e.py` | create | oscillating + dashed-edge e2e |
| `tests/test_data_entry_e2e.py` | append | delay-select e2e |

---

### Task 1: `normalize_delay` + `DELAY_LEVELS` (constants)

**Files:**
- Modify: `sespy/constants.py` (append)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Produces: `DELAY_LEVELS: tuple[str,...] = ("immediate","short","long")`; `normalize_delay(raw: object) -> str` returning one of `DELAY_LEVELS`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_network.py`:

```python
def test_normalize_delay_table():
    from sespy.constants import normalize_delay
    cases = {
        "immediate": "immediate", "short": "short", "long": "long",
        "SHORT": "short", "Long": "long", "  short  ": "short",
        "": "immediate", "no": "immediate", "none": "immediate",
        "false": "immediate", "0": "immediate", "0.0": "immediate", "-": "immediate",
        "3": "short", "5y": "short", "lag": "short", "delayed": "short",
    }
    for raw, exp in cases.items():
        assert normalize_delay(raw) == exp, (raw, normalize_delay(raw))
    assert normalize_delay(None) == "immediate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py::test_normalize_delay_table -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_delay'`.

- [ ] **Step 3: Implement** — append to `sespy/constants.py`:

```python
# --- Connection delay vocabulary (QSEM time-delay surfacing) -----------------
DELAY_LEVELS: tuple[str, ...] = ("immediate", "short", "long")

# Values that mean "no delay" — guarded so a negated/zero cell is not
# mislabelled as delayed.
_DELAY_IMMEDIATE_SENTINELS = frozenset({
    "", "none", "immediate", "instant", "now", "no", "n/a", "na", "false", "f", "-",
})


def normalize_delay(raw: object) -> str:
    """Map any stored/imported delay value to DELAY_LEVELS, conservatively.

    Order (case-insensitive, stripped): exact short/long/immediate; an
    immediate/negation sentinel -> 'immediate'; numeric 0 -> 'immediate',
    > 0 -> 'short'; any remaining non-empty free-text -> 'short'. 'long' is
    only produced by an exact match (never auto-promoted).
    """
    s = ("" if raw is None else str(raw)).strip().lower()
    if s in ("short", "long", "immediate"):
        return s
    if s in _DELAY_IMMEDIATE_SENTINELS:
        return "immediate"
    try:
        return "immediate" if float(s) == 0 else "short"
    except ValueError:
        return "short" if s else "immediate"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py::test_normalize_delay_table -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sespy/constants.py tests/test_network.py
git commit -m "feat(constants): DELAY_LEVELS + conservative normalize_delay

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `loop_has_delay` + `classify_loops` behavior/delayed (network)

**Files:**
- Modify: `sespy/network.py` (append helper; edit `classify_loops`)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Consumes: `normalize_delay` (Task 1); existing `loop_polarity`, `feedback_loops`, `classify_loops` in `network.py`.
- Produces: `loop_has_delay(cycle, isa) -> bool`; `classify_loops(cycles, isa)` rows now also carry `delayed: bool` and `behavior: str` (`reinforcing`/`balancing`/`oscillating`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py`:

```python
def _delay_fixture(ab_polarity, ab_delay, ba_polarity="+", ba_delay="immediate"):
    from sespy.data_structure import Element, Connection, IsaData
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity=ab_polarity, delay=ab_delay),
             Connection(source="B", target="A", polarity=ba_polarity, delay=ba_delay)]
    return IsaData(elements=els, connections=conns)


def test_classify_loops_oscillating_when_balancing_and_delayed():
    isa = _delay_fixture(ab_polarity="-", ab_delay="short")  # 1 negative -> Balancing
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    assert rows, "expected >=1 loop"
    r = rows[0]
    assert r["type"] == "Balancing"
    assert r["delayed"] is True
    assert r["behavior"] == "oscillating"


def test_classify_loops_delayed_reinforcing_stays_reinforcing():
    isa = _delay_fixture(ab_polarity="+", ab_delay="short")  # 0 negatives -> Reinforcing
    r = network.classify_loops(network.feedback_loops(isa), isa)[0]
    assert r["type"] == "Reinforcing"
    assert r["delayed"] is True
    assert r["behavior"] == "reinforcing"


def test_classify_loops_immediate_balancing_not_oscillating():
    isa = _delay_fixture(ab_polarity="-", ab_delay="immediate")
    r = network.classify_loops(network.feedback_loops(isa), isa)[0]
    assert r["type"] == "Balancing"
    assert r["delayed"] is False
    assert r["behavior"] == "balancing"


def test_classify_loops_behavior_buckets_sum_to_total(isa):
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    counts = {b: sum(1 for r in rows if r["behavior"] == b)
              for b in ("reinforcing", "balancing", "oscillating")}
    assert sum(counts.values()) == len(rows)


def test_loop_has_delay_parallel_edges_last_wins():
    from sespy.data_structure import Element, Connection, IsaData
    els = [Element(id="A", label="A", type="Drivers"),
           Element(id="B", label="B", type="State")]
    # Two A->B edges; last one wins the (source,target) lookup.
    isa_delayed = IsaData(elements=els, connections=[
        Connection(source="A", target="B", delay="immediate"),
        Connection(source="A", target="B", delay="short"),     # last -> delayed
        Connection(source="B", target="A", delay="immediate"),
    ])
    assert network.loop_has_delay(["A", "B"], isa_delayed) is True
    isa_immediate = IsaData(elements=els, connections=[
        Connection(source="A", target="B", delay="short"),
        Connection(source="A", target="B", delay="immediate"),  # last -> immediate
        Connection(source="B", target="A", delay="immediate"),
    ])
    assert network.loop_has_delay(["A", "B"], isa_immediate) is False
```

(The `isa` fixture already exists in `tests/test_network.py` — it loads the sample.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "classify_loops or loop_has_delay" -v`
Expected: FAIL — `AttributeError: module 'sespy.network' has no attribute 'loop_has_delay'` / `KeyError: 'behavior'`.

- [ ] **Step 3: Implement** — in `sespy/network.py`:

(a) Append the lookup + predicate (next to `_edge_polarity_lookup`):

```python
def _edge_delay_lookup(isa: IsaData) -> dict[tuple[str, str], str]:
    from .constants import normalize_delay
    return {(c.source, c.target): normalize_delay(c.delay) for c in isa.connections}


def loop_has_delay(cycle: list[str], isa: IsaData) -> bool:
    """True if any edge traversed by `cycle` is delayed
    (normalize_delay(delay) != 'immediate'). Walks (cycle[i], cycle[(i+1)%n])
    like loop_polarity; last-wins on parallel (source,target) edges (the UI
    blocks duplicate edges; only Excel / hand-edited JSON can create them)."""
    lookup = _edge_delay_lookup(isa)
    n = len(cycle)
    return any(
        lookup.get((cycle[i], cycle[(i + 1) % n]), "immediate") != "immediate"
        for i in range(n)
    )
```

(b) Edit `classify_loops` so each row computes `type` once and adds `delayed`/`behavior` (keep `id`, `length`, `type`, `nodes`, `path`):

```python
def classify_loops(cycles: list[list[str]], isa: IsaData) -> list[dict]:
    """Annotate each cycle with id, length, type, delayed, behavior, and a
    human-readable path."""
    label_by_id = {el.id: el.label for el in isa.elements}
    out: list[dict] = []
    for idx, cycle in enumerate(cycles, start=1):
        loop_type = loop_polarity(cycle, isa)
        delayed = loop_has_delay(cycle, isa)
        if loop_type == "Balancing" and delayed:
            behavior = "oscillating"
        elif loop_type == "Balancing":
            behavior = "balancing"
        else:                       # Reinforcing (and any unexpected value)
            behavior = "reinforcing"
        out.append({
            "id": f"L{idx:03d}",
            "length": len(cycle),
            "type": loop_type,
            "delayed": delayed,
            "behavior": behavior,
            "nodes": cycle,
            "path": " → ".join(label_by_id.get(n, n) for n in cycle)
            + f" → {label_by_id.get(cycle[0], cycle[0])}",
        })
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "classify_loops or loop_has_delay" -v`
Expected: PASS (5 new). Also run the existing loop test to confirm no regression: `micromamba run -n shiny python -m pytest tests/test_network.py::test_loop_polarity_rule -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): loop_has_delay + classify_loops behavior/delayed

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Seed the sample + done-criterion test

**Files:**
- Modify: `data/sample_ses.json` (edit one existing connection)
- Test: `tests/test_network.py` (append)

**Interfaces:** Consumes Task 2's `classify_loops`/`feedback_loops`. No new symbols.

- [ ] **Step 1: Write the failing test** — append to `tests/test_network.py`:

```python
def test_sample_has_oscillating_loop(isa):
    rows = network.classify_loops(network.feedback_loops(isa), isa)
    osc = [r for r in rows if r["behavior"] == "oscillating"]
    assert len(osc) >= 1, "sample seed missing — expected >=1 oscillating loop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py::test_sample_has_oscillating_loop -v`
Expected: FAIL (no edge is delayed yet → 0 oscillating).

- [ ] **Step 3: Seed the sample.** In `data/sample_ses.json`, find the connection whose `source` is `"MPF2"` and `target` is `"ES02"` (it lies on a Balancing loop) and add/set `"delay": "short"` on that one connection object. **Do not add or remove any connection** — only edit this one. (Verified: this produces exactly 1 oscillating loop and keeps `connection_count() == 20`.)

Use your editor; locate the object with `"source": "MPF2", "target": "ES02"` and insert `"delay": "short"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "oscillating or test_sample_loads" -v`
Expected: PASS — `test_sample_has_oscillating_loop` AND `test_sample_loads` (still 20 connections / 17 elements).

- [ ] **Step 5: Commit**

```bash
git add data/sample_ses.json tests/test_network.py
git commit -m "feat(data): seed sample with a delayed edge -> 1 oscillating loop

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: i18n keys (9 keys × 9 languages)

**Files:**
- Modify: `sespy/translations/core.json`

**Interfaces:** Produces i18n keys consumed by Tasks 5 & 6: `entry.delay`; `delay.immediate`/`.short`/`.long`; `loops.behavior.reinforcing`/`.balancing`/`.oscillating`; `loops.oscillating_disclaimer`; `loops.delay_chip`. (Table column *headers* stay untranslated English, matching the existing `loops_table` headers `id`/`type`/`length`/`path` — so no `loops.col_*` keys; only the cell *values* are translated. The spec §6 also listed `loops.oscillating_count` — **intentionally dropped**: the summary count line (Task 5 Step 1) reuses `loops.behavior.oscillating` as its label rather than a separate count key.)

- [ ] **Step 1: Add the keys.** Create a temp `add_delay_i18n.py` at the repo root, run it once, then delete it (avoids the Windows multi-line `-c` trap):

```python
import json, pathlib
PATH = pathlib.Path("sespy/translations/core.json")
data = json.loads(PATH.read_text(encoding="utf-8"))
tr = data["translation"]
KEYS = {
  "entry.delay": {"en":"Delay","es":"Retardo","fr":"Délai","de":"Verzögerung","lt":"Vėlavimas","pt":"Atraso","it":"Ritardo","no":"Forsinkelse","el":"Καθυστέρηση"},
  "delay.immediate": {"en":"Immediate","es":"Inmediato","fr":"Immédiat","de":"Sofort","lt":"Betarpiškas","pt":"Imediato","it":"Immediato","no":"Umiddelbar","el":"Άμεσο"},
  "delay.short": {"en":"Short","es":"Corto","fr":"Court","de":"Kurz","lt":"Trumpas","pt":"Curto","it":"Breve","no":"Kort","el":"Σύντομο"},
  "delay.long": {"en":"Long","es":"Largo","fr":"Long","de":"Lang","lt":"Ilgas","pt":"Longo","it":"Lungo","no":"Lang","el":"Μακρύ"},
  "loops.behavior.reinforcing": {"en":"Reinforcing","es":"Reforzador","fr":"Renforçant","de":"Verstärkend","lt":"Stiprinantis","pt":"Reforçador","it":"Rinforzante","no":"Forsterkende","el":"Ενισχυτικός"},
  "loops.behavior.balancing": {"en":"Balancing","es":"Equilibrador","fr":"Équilibrant","de":"Ausgleichend","lt":"Balansuojantis","pt":"Equilibrador","it":"Bilanciante","no":"Balanserende","el":"Εξισορροπητικός"},
  "loops.behavior.oscillating": {"en":"Oscillation-prone","es":"Propenso a oscilar","fr":"Sujet aux oscillations","de":"Schwingungsanfällig","lt":"Linkęs svyruoti","pt":"Propenso a oscilar","it":"Soggetto a oscillazioni","no":"Svingningsutsatt","el":"Επιρρεπής σε ταλαντώσεις"},
  "loops.oscillating_disclaimer": {"en":"Structural signature only — delayed balancing loops are prone to overshoot/oscillation; actual behaviour depends on gains and delay magnitude, not simulated here.","es":"Solo firma estructural — los bucles equilibradores con retardo son propensos a sobrepasos/oscilaciones; el comportamiento real depende de las ganancias y la magnitud del retardo, no simulado aquí.","fr":"Signature structurelle uniquement — les boucles d'équilibrage retardées sont sujettes au dépassement/oscillation ; le comportement réel dépend des gains et de l'ampleur du délai, non simulé ici.","de":"Nur strukturelle Signatur — verzögerte ausgleichende Schleifen neigen zu Überschwingen/Schwingung; das tatsächliche Verhalten hängt von Verstärkungen und Verzögerungsgröße ab, hier nicht simuliert.","lt":"Tik struktūrinis požymis — vėluojančios balansuojančios kilpos linkusios peršokti/svyruoti; tikrasis elgesys priklauso nuo stiprinimų ir vėlavimo dydžio, čia nemodeliuojama.","pt":"Apenas assinatura estrutural — ciclos equilibradores com atraso são propensos a sobre-elevação/oscilação; o comportamento real depende dos ganhos e da magnitude do atraso, não simulado aqui.","it":"Solo firma strutturale — i cicli bilancianti ritardati sono soggetti a sovraelongazione/oscillazione; il comportamento reale dipende dai guadagni e dall'entità del ritardo, non simulato qui.","no":"Kun strukturell signatur — forsinkede balanserende sløyfer er utsatt for oversving/svingning; faktisk atferd avhenger av forsterkninger og forsinkelsens størrelse, ikke simulert her.","el":"Μόνο δομική υπογραφή — οι καθυστερημένοι εξισορροπητικοί βρόχοι είναι επιρρεπείς σε υπερύψωση/ταλάντωση· η πραγματική συμπεριφορά εξαρτάται από τα κέρδη και το μέγεθος της καθυστέρησης, δεν προσομοιώνεται εδώ."},
  "loops.delay_chip": {"en":"delay","es":"retardo","fr":"délai","de":"Verzög.","lt":"vėlavimas","pt":"atraso","it":"ritardo","no":"forsink.","el":"καθυστ."},
}
for k, v in KEYS.items():
    tr[k] = v
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("added", len(KEYS), "keys")
```

Run: `micromamba run -n shiny python add_delay_i18n.py` then `rm add_delay_i18n.py`.

- [ ] **Step 2: Verify keys + 9 languages + drift test**

Run: `micromamba run -n shiny python -c "import json;d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation'];ks=[k for k in d if k=='entry.delay' or k.startswith('delay.') or k.startswith('loops.behavior') or k in ('loops.oscillating_disclaimer','loops.delay_chip')];print(len(ks),'keys',all(len(d[k])==9 for k in ks))"`
Expected: `9 keys True`.

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`
Expected: PASS (drift test green).

- [ ] **Step 3: Confirm no stray files, commit**

Run: `git status --short` (expect only `sespy/translations/core.json`; NO `add_delay_i18n.py`).

```bash
git add sespy/translations/core.json
git commit -m "i18n(loops): add delay/behavior keys (9 keys, 9 languages)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Loop Analysis surfacing (`analysis_loops.py`)

**Files:**
- Modify: `sespy/modules/analysis_loops.py`

**Interfaces:**
- Consumes: `classify_loops` rows with `behavior`/`delayed` (Task 2); i18n keys (Task 4); existing `EDGE_COLORS`.
- Produces: no new public symbols; updates the rendered summary, table, picker, narrative, and loop network.

Behavior→display label + colour helpers — add near the top of the module body (module scope, after imports):

```python
_BEHAVIOR_KEY = {
    "reinforcing": "loops.behavior.reinforcing",
    "balancing": "loops.behavior.balancing",
    "oscillating": "loops.behavior.oscillating",
}
_BEHAVIOR_COLOR = {
    "reinforcing": EDGE_COLORS["reinforcing"],
    "balancing": EDGE_COLORS["opposing"],
    "oscillating": "#e8a33d",   # amber — distinct from R/B
}
```

- [ ] **Step 1: Classification summary — three buckets + disclaimer.** Replace the body of `classification_summary` so it counts by `behavior` and renders three coloured counts plus the disclaimer footnote:

```python
    @output
    @render.ui
    def classification_summary():
        rows = classified()
        if not rows:
            return ui.tags.p("No loops detected yet — click the button.", class_="text-muted")
        counts = {b: sum(1 for r in rows if r["behavior"] == b)
                  for b in ("reinforcing", "balancing", "oscillating")}

        def line(b):
            return ui.tags.div(
                ui.tags.strong(str(counts[b])), " ", t(_BEHAVIOR_KEY[b]),
                style=f"color: {_BEHAVIOR_COLOR[b]}; margin-bottom: 4px;",
            )
        return ui.div(
            line("reinforcing"), line("balancing"), line("oscillating"),
            ui.tags.div(t("loops.oscillating_disclaimer"),
                        class_="text-muted", style="font-size: 0.72rem; margin-top: 6px;"),
        )
```

- [ ] **Step 2: Loops table — add behavior + delayed columns.** Update `loops_table` to include them (keep existing columns):

```python
    @output
    @render.data_frame
    def loops_table():
        import pandas as pd
        rows = classified()
        cols = ["id", "behavior", "delayed", "type", "length", "path"]
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([{
            "id": r["id"],
            "behavior": t(_BEHAVIOR_KEY[r["behavior"]]),
            "delayed": "✓" if r["delayed"] else "—",
            "type": r["type"],
            "length": r["length"],
            "path": r["path"],
        } for r in rows], columns=cols)
```

- [ ] **Step 3: Loop picker — behavior in the label.** Update `loop_picker` choices:

```python
        choices = {r["id"]: f"{r['id']} · {t(_BEHAVIOR_KEY[r['behavior']])} · len {r['length']}"
                   for r in rows}
```

- [ ] **Step 4: Loop narrative — behavior badge + delay chip.** Update `loop_narrative` to colour the badge by behavior and append a delay chip when delayed-but-not-oscillating. (Note: the seeded sample produces an oscillating loop, not a delayed-*reinforcing* one, so the chip branch is covered by reading the code/logic only — not exercised by the e2e. That's acceptable; a second seed to exercise it is out of scope.)

```python
    @output
    @render.ui
    def loop_narrative():
        row = selected_row()
        if row is None:
            return ui.tags.p("Detect loops first.", class_="text-muted")
        color = _BEHAVIOR_COLOR[row["behavior"]]
        parts = [
            ui.tags.span(
                t(_BEHAVIOR_KEY[row["behavior"]]),
                style=(f"display:inline-block; padding:2px 10px; background:{color}; "
                       "color:#fff; border-radius:12px; font-size:12px; margin-right:8px;"),
            ),
        ]
        if row["delayed"] and row["behavior"] != "oscillating":
            parts.append(ui.tags.span(
                t("loops.delay_chip"),
                style=("display:inline-block; padding:2px 8px; background:#e8a33d; "
                       "color:#fff; border-radius:12px; font-size:11px; margin-right:8px;"),
            ))
        parts.append(ui.tags.span(f"length {row['length']}", style="color:#777; margin-right:8px;"))
        parts.append(ui.tags.span(row["path"]))
        return ui.div(*parts, style="margin: 8px 0 12px 0;")
```

- [ ] **Step 5: Dashed delayed edges in the loop network.** In `_build_loop_network`, compute a delay lookup and set `dashes` + tooltip per edge via the **`net.add_edge(..., dashes=...)` keyword path** (do NOT route edges through a typed `EdgeOptions`/`options=` object — pyvis passes legacy kwargs through verbatim to the vis.js edge so `e.dashes` is exposed to the e2e; a typed options object would drop the unmodeled field). Add near the top of the function (beside `polarity_by_edge`):

```python
    from ..constants import normalize_delay
    delay_by_edge = {(c.source, c.target): normalize_delay(c.delay) for c in isa.connections}
```

and replace the `net.add_edge(...)` call in the loop with:

```python
        delay = delay_by_edge.get((src, tgt), "immediate")
        is_delayed = delay != "immediate"
        net.add_edge(
            src,
            tgt,
            label=polarity,
            title=f"{polarity} · {delay}",
            color=EDGE_COLORS["reinforcing" if polarity == "+" else "opposing"],
            arrows="to",
            width=3,
            dashes=is_delayed,
        )
```

- [ ] **Step 6: Verify the module imports**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_loops as m; print(hasattr(m,'analysis_loops_ui'), hasattr(m,'analysis_loops_server'))"`
Expected: `True True`.

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/analysis_loops.py
git commit -m "feat(loops): surface behavior/delayed (oscillation-prone + dashed edges)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Data-entry delay input + table column + Excel normalize

**Files:**
- Modify: `sespy/modules/isa_data_entry.py`
- Modify: `sespy/excel_import.py`

**Interfaces:** Consumes `DELAY_LEVELS`/`normalize_delay` (Task 1), i18n keys (Task 4). No new public symbols.

- [ ] **Step 1: Add the delay select to the connection form.** In `isa_data_entry.py`, the connection-add `ui.layout_columns(...)` currently holds source_picker, target_picker, `new_polarity` radio, `add_connection` button with `col_widths=(3, 3, 3, 3)`. Insert a delay select before the add button and refit widths to `(3, 3, 2, 2, 2)`:

```python
            ui.layout_columns(
                ui.output_ui("source_picker"),
                ui.output_ui("target_picker"),
                ui.input_radio_buttons(
                    "new_polarity", t("entry.polarity"),
                    CONNECTION_POLARITY_LABELS,
                    selected="+",
                    inline=True,
                ),
                ui.input_select(
                    "new_delay", t("entry.delay"),
                    {lvl: t(f"delay.{lvl}") for lvl in DELAY_LEVELS},
                    selected="immediate",
                ),
                ui.input_action_button("add_connection", t("entry.add_connection"),
                                       class_="btn btn-primary",
                                       style="align-self: end;"),
                col_widths=(3, 3, 2, 2, 2),
            ),
```

Add the import at the top of the file: `from ..constants import DELAY_LEVELS` (merge into the existing `..constants` import if present).

- [ ] **Step 2: Pass delay into the new Connection.** In the add-connection handler, change the `Connection(...)` construction:

```python
        new = Connection(source=src, target=tgt,
                         polarity=input.new_polarity() or "+",
                         delay=input.new_delay() or "immediate")
```

- [ ] **Step 3: Add a delay column to the connections table.** In `connections_table`, add `"delay"` to each row dict and to the empty placeholder:

```python
        rows = [
            {
                "source": f"{c.source} · {by_id.get(c.source, '?')}",
                "target": f"{c.target} · {by_id.get(c.target, '?')}",
                "polarity": c.polarity,
                "strength": c.strength,
                "delay": c.delay,
            }
            for c in project_data.get().isa_data.connections
        ]
        return render.DataGrid(
            pd.DataFrame(rows or [{"source": "", "target": "", "polarity": "", "strength": "", "delay": ""}]),
            selection_mode="row",
            height="240px",
        )
```

- [ ] **Step 4: Normalize delay on Excel import.** In `sespy/excel_import.py`, add `from .constants import normalize_delay` (merge with existing constants import if any) and wrap the delay read at the `Connection(...)` build:

```python
            delay=normalize_delay(_pick(row, CONN_DELAY_COLS, default="immediate")),
```

- [ ] **Step 5: Verify imports + a normalize round-trip**

Run: `micromamba run -n shiny python -c "import sespy.modules.isa_data_entry, sespy.excel_import; from sespy.constants import normalize_delay; print('ok', normalize_delay('Lag'), normalize_delay('no'))"`
Expected: `ok short immediate`.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/isa_data_entry.py sespy/excel_import.py
git commit -m "feat(entry): delay select + table column; normalize_delay on import

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: e2e + full gate

**Files:**
- Create: `tests/test_loops_e2e.py`
- Modify: `tests/test_data_entry_e2e.py` (append assertions)

**Interfaces:** Consumes the running app (`#sespy_nav_loops`, `#sespy_nav_entry`, the seeded oscillating loop, the `new_delay` select).

- [ ] **Step 1: Write the loops e2e.** Create `tests/test_loops_e2e.py` (standalone asyncio, modelled on `tests/test_leverage_e2e.py`):

```python
"""E2E for delay-aware Loop Analysis: detect loops, confirm an oscillation-prone
loop is reported and its delayed edge renders dashed in the loop network."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        await page.click("#sespy_nav_loops")
        await page.wait_for_timeout(1500)
        # Run detection
        await page.click("#loops-detect")
        # Poll until the loops table populates (data_frame <tbody> late-mounts)
        await page.wait_for_selector("#loops-loops_table table tbody tr", timeout=30000)
        # The picker is a separate output_ui-rendered <select> that flushes as its
        # own Shiny message — wait for it too before reading/setting selectedIndex.
        await page.wait_for_selector("#loops-selected_loop", timeout=30000)

        # Behaviour is column 2; find the index of the oscillation-prone row.
        # The picker (#loops-selected_loop) options are in the SAME order as the
        # table rows (both come from classify_loops), so the row index == option index.
        behaviors = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#loops-loops_table table tbody tr')).map("
            "tr => (tr.querySelector('td:nth-child(2)')?.textContent || '').trim())"
        )
        print("behaviors:", behaviors)
        osc_idx = next((i for i, b in enumerate(behaviors) if "scill" in b.lower()), -1)
        assert osc_idx >= 0, f"no oscillation-prone loop reported: {behaviors}"

        # Deterministically select the oscillation-prone loop in the picker.
        ok = await page.evaluate(
            "(i) => { const el=document.getElementById('loops-selected_loop');"
            " if(!el) return false;"
            " el.selectedIndex=i; el.dispatchEvent(new Event('change',{bubbles:true})); return true; }",
            osc_idx,
        )
        assert ok, "#loops-selected_loop not mounted"

        # Read the rendered loop network's edge `dashes` flags: the delayed edge
        # must be dashed AND at least one edge must be solid. Poll for the re-render.
        dashes = None
        for _ in range(16):
            await page.wait_for_timeout(500)
            dashes = await page.evaluate(
                "() => { const s=window.pyvisNetworks && window.pyvisNetworks['loops-loop_network'];"
                " return s && s.edges ? s.edges.get().map(e => e.dashes === true) : null; }"
            )
            if dashes:
                break
        print("dashes:", dashes)
        assert dashes, "loop network edges not readable"
        assert any(dashes), "no dashed (delayed) edge in the oscillation-prone loop"
        assert not all(dashes), "expected at least one solid (immediate) edge too"

        await page.screenshot(path="tests/screenshots/loops.png")
        print("\nloops e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Extend the data-entry e2e.** Append to `tests/test_data_entry_e2e.py` (before `browser.close()` / inside `main`), after the existing element-add assertions: navigate to Edit Data, assert the delay select exists with three options.

```python
        # --- delay select on the connection form (delay-aware Loop Analysis) ---
        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(1200)
        delay_opts = await page.evaluate(
            "() => { const el=document.getElementById('entry-new_delay');"
            " return el ? Array.from(el.options).map(o => o.value) : null; }"
        )
        print("delay options:", delay_opts)
        assert delay_opts == ["immediate", "short", "long"], f"unexpected: {delay_opts}"
```

(Place this before the existing `await page.screenshot(...)` / `print(... )` / `browser.close()` tail so the script still ends cleanly with a single `asyncio.run(main())`.)

- [ ] **Step 3: Run the FULL e2e gate**

Run: `micromamba run -n shiny python tests/run_e2e.py` (generous timeout, up to 600000ms — boots `shiny run app.py` and runs every `test_*_e2e.py` as a subprocess).
Expected: all e2e green including the new `test_loops_e2e.py` and the extended `test_data_entry_e2e.py`. (Known pre-existing failure: `test_report_e2e.py` PDF step fails due to a broken WeasyPrint in this env — unrelated to this branch; do not block on it.)

- [ ] **Step 4: Run the unit + i18n suites**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py tests/test_i18n.py -q`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add tests/test_loops_e2e.py tests/test_data_entry_e2e.py
git commit -m "test(e2e): oscillation-prone loop + dashed edge + delay select

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria
- `normalize_delay` + `loop_has_delay` + `classify_loops` behavior/delayed unit tests green.
- Sample yields ≥1 oscillating loop; `test_sample_loads` still 20/17.
- 9 i18n keys × 9 languages; `test_i18n.py` green.
- Loop Analysis shows a 3-bucket summary (with disclaimer), behavior/delayed columns, behavior badge + delay chip, dashed delayed edges.
- Delay settable in the data-entry form; Excel import normalized.
- Full e2e suite green via `python tests/run_e2e.py` (except the known pre-existing WeasyPrint `test_report_e2e` red).
- Seven commits, repo clean, no stray files.
