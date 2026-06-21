# Influence × Dependence Quadrant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Vester Influence × Dependence factor-classification map (QSEM Phase-1 parity) as a standalone SESPy analysis module, computed automatically from the signed/weighted diagram.

**Architecture:** One new pure function `influence_dependence(isa)` in `sespy/network.py` (weighted by the existing `_edge_weight`, sign-agnostic, parallel-edge-deduplicated, self-loops skipped, mean-split into active/critical/reactive/buffering with an `undetermined` degeneracy state). A thin Shiny module `sespy/modules/analysis_quadrant.py` presents it as a matplotlib scatter + classification table, mirroring `analysis_leverage.py`. Wired into `app.py` via the `NAV`/`NAV_TO_STEP`/`PANELS`/server quartet.

**Tech Stack:** Python 3.11+, Shiny for Python, matplotlib, pandas, networkx (already deps); Playwright for e2e. Env: micromamba `shiny` (`micromamba run -n shiny …`).

## Global Constraints

- No data-model / schema change. `Connection` and `Element` are read-only here; no `PROJECT_SCHEMA_VERSION` bump.
- Reuse `_edge_weight` (`network.py:216`) as the single edge-weight definition; do not invent a second.
- Sign-agnostic: `polarity` is **not** consumed by `influence_dependence`.
- UI text uses the module-level `t()` from `..i18n` (never translator-bound calls); the `translator` server param exists only for signature parity with sibling modules.
- matplotlib plots: `fig, ax = plt.subplots(...)` then `return fig`; never `plt.close`/`plt.show` (`@render.plot` owns the lifecycle).
- e2e tests are standalone `asyncio.run(main())` Playwright scripts, NOT pytest tests. Gate the full e2e suite with `python tests/run_e2e.py` — never `-k "not e2e"`, never `pytest tests/ -q` on the e2e scripts.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Windows shell trap: never multi-line `python -c "…"` (use a single line or a `.py` file); never `>`/`>>` to create files. Check `git status` for stray files after runs.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `sespy/network.py` | Modify (append) | `influence_dependence()` pure function |
| `tests/test_network.py` | Modify (append) | Unit tests for the function |
| `sespy/translations/core.json` | Modify | 13 new i18n keys × 9 languages |
| `sespy/modules/analysis_quadrant.py` | Create | Shiny UI + server module |
| `app.py` | Modify | Import + `NAV` + `NAV_TO_STEP` + `PANELS` + server call |
| `tests/test_quadrant_e2e.py` | Create | Standalone Playwright e2e |

---

### Task 1: `influence_dependence` pure function + unit tests

**Files:**
- Modify: `sespy/network.py` (append after `leverage_scores`, ~line 174)
- Test: `tests/test_network.py` (append)

**Interfaces:**
- Consumes: `IsaData`, `Element`, `Connection` (`sespy/data_structure.py`); `_edge_weight` (`sespy/network.py:216`).
- Produces: `influence_dependence(isa: IsaData) -> dict[str, dict]` returning, per element id, `{"influence": float, "dependence": float, "quadrant": str}` where `quadrant ∈ {"active","critical","reactive","buffering","undetermined"}`. Returns `{}` for an empty graph.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_network.py` (it already imports from `sespy`; match its existing import style — `from sespy.data_structure import Element, Connection, IsaData` and `from sespy import network`):

```python
def _quadrant_fixture():
    # Four nodes hitting all four quadrants; confidence=1 so weight == strength rank.
    els = [
        Element(id="D", label="Driver", type="Driver"),
        Element(id="H", label="Hub", type="Pressure"),
        Element(id="S", label="Sink", type="State"),
        Element(id="I", label="Inert", type="Welfare"),
    ]
    conns = [
        Connection(source="D", target="H", strength="strong", confidence=1),  # w=3
        Connection(source="D", target="S", strength="strong", confidence=1),  # w=3
        Connection(source="H", target="S", strength="strong", confidence=1),  # w=3
        Connection(source="H", target="I", strength="weak",   confidence=1),  # w=1
        Connection(source="S", target="H", strength="weak",   confidence=1),  # w=1
    ]
    return IsaData(elements=els, connections=conns)


def test_influence_dependence_sums_and_quadrants():
    res = network.influence_dependence(_quadrant_fixture())
    # influence (out): D=6, H=4, S=1, I=0 ; dependence (in): D=0, H=4, S=6, I=1
    assert res["D"]["influence"] == 6.0 and res["D"]["dependence"] == 0.0
    assert res["H"]["influence"] == 4.0 and res["H"]["dependence"] == 4.0
    assert res["S"]["influence"] == 1.0 and res["S"]["dependence"] == 6.0
    assert res["I"]["influence"] == 0.0 and res["I"]["dependence"] == 1.0
    # means are 2.75 / 2.75
    assert res["D"]["quadrant"] == "active"
    assert res["H"]["quadrant"] == "critical"
    assert res["S"]["quadrant"] == "reactive"
    assert res["I"]["quadrant"] == "buffering"


def test_influence_dependence_empty_graph():
    assert network.influence_dependence(IsaData()) == {}


def test_influence_dependence_all_isolated_is_undetermined():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    res = network.influence_dependence(IsaData(elements=els, connections=[]))
    assert {r["quadrant"] for r in res.values()} == {"undetermined"}
    assert res["A"]["influence"] == 0.0 and res["A"]["dependence"] == 0.0


def test_influence_dependence_uniform_ring_is_undetermined():
    els = [Element(id=n, label=n, type="Driver") for n in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=3),
             Connection(source="B", target="C", strength="medium", confidence=3),
             Connection(source="C", target="A", strength="medium", confidence=3)]
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert {r["quadrant"] for r in res.values()} == {"undetermined"}


def test_influence_dependence_skips_self_loops():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="A", strength="strong", confidence=1),  # ignored
             Connection(source="A", target="B", strength="medium", confidence=1)]  # w=2
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 2.0      # self-loop not added
    assert res["A"]["dependence"] == 0.0     # self-loop not added to dependence either


def test_influence_dependence_dedups_parallel_edges():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", strength="medium", confidence=1),  # w=2
             Connection(source="A", target="B", strength="strong", confidence=1)]  # w=3 (last wins)
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 3.0      # counted once, last-wins weight, not 5.0


def test_influence_dependence_is_sign_agnostic():
    els = [Element(id="A", label="A", type="Driver"),
           Element(id="B", label="B", type="State")]
    conns = [Connection(source="A", target="B", polarity="-", strength="strong", confidence=1)]
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["A"]["influence"] == 3.0      # negative polarity still positive magnitude


def test_influence_dependence_tie_boundary_and_nonuniform_cycle():
    # Non-uniform cycle: influence {A:1, B:2, C:3} mean 2 ; dependence {A:3, B:1, C:2} mean 2.
    # Both axes VARY (var=0.667) so the AND-both-axes degeneracy guard must NOT fire —
    # this pins AND-not-OR semantics. B sits EXACTLY at mean influence (2.0), so the
    # `>= mean` tie rule must place it on the HIGH influence side: a `>` implementation
    # would misclassify B as buffering and fail this test.
    els = [Element(id=n, label=n, type="Driver") for n in ("A", "B", "C")]
    conns = [Connection(source="A", target="B", strength="weak",   confidence=1),  # w=1
             Connection(source="B", target="C", strength="medium", confidence=1),  # w=2
             Connection(source="C", target="A", strength="strong", confidence=1)]  # w=3
    res = network.influence_dependence(IsaData(elements=els, connections=conns))
    assert res["B"]["influence"] == 2.0          # exactly mean_inf
    assert res["B"]["quadrant"] == "active"      # tie -> high side (fails under '>')
    assert res["A"]["quadrant"] == "reactive"
    assert res["C"]["quadrant"] == "critical"
    # Differentiated graph -> distinct quadrants, NOT all 'undetermined'.
    assert len({r["quadrant"] for r in res.values()}) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k influence_dependence -v`
Expected: FAIL — `AttributeError: module 'sespy.network' has no attribute 'influence_dependence'`.

- [ ] **Step 3: Write the implementation**

Append to `sespy/network.py` (after `leverage_scores`):

```python
def influence_dependence(isa: IsaData) -> dict[str, dict]:
    """Vester influence × dependence per node — weighted, sign-agnostic.

    influence  = Σ _edge_weight over a node's outgoing edges (to OTHERS)
    dependence = Σ _edge_weight over a node's incoming edges (from OTHERS)
    quadrant   = active | critical | reactive | buffering, split at the mean
                 of each axis (>= mean = high side); or 'undetermined' when the
                 system has no structural differentiation.

    Parallel (source, target) edges are deduplicated (last-wins), matching
    to_digraph; self-loops are skipped. Returns {} for an empty graph; never
    raises. Mirrors the zeros-never-raise posture of the other metrics here.
    """
    elements = isa.elements
    if not elements:
        return {}

    influence = {el.id: 0.0 for el in elements}
    dependence = {el.id: 0.0 for el in elements}
    ids = set(influence)

    # Deduplicate parallel edges (last-wins) and drop self-loops / dangling refs.
    weight_by_pair: dict[tuple[str, str], float] = {}
    for c in isa.connections:
        if c.source == c.target:
            continue
        if c.source not in ids or c.target not in ids:
            continue
        weight_by_pair[(c.source, c.target)] = _edge_weight(c)

    for (src, tgt), w in weight_by_pair.items():
        influence[src] += w
        dependence[tgt] += w

    n = len(elements)
    mean_inf = sum(influence.values()) / n
    mean_dep = sum(dependence.values()) / n

    def _variance(values: dict[str, float], mean: float) -> float:
        return sum((v - mean) ** 2 for v in values.values()) / n

    # Degeneracy guard: no edges, or zero variance on both axes (uniform graph).
    if not weight_by_pair or (
        _variance(influence, mean_inf) < 1e-12
        and _variance(dependence, mean_dep) < 1e-12
    ):
        return {
            el.id: {
                "influence": influence[el.id],
                "dependence": dependence[el.id],
                "quadrant": "undetermined",
            }
            for el in elements
        }

    out: dict[str, dict] = {}
    for el in elements:
        i, d = influence[el.id], dependence[el.id]
        hi_i, hi_d = i >= mean_inf, d >= mean_dep
        if hi_i and not hi_d:
            quadrant = "active"
        elif hi_i and hi_d:
            quadrant = "critical"
        elif hi_d:  # not hi_i and hi_d
            quadrant = "reactive"
        else:
            quadrant = "buffering"
        out[el.id] = {"influence": i, "dependence": d, "quadrant": quadrant}
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k influence_dependence -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): influence_dependence() Vester quadrant scorer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: i18n keys

**Files:**
- Modify: `sespy/translations/core.json` (the single catalog; shape `{"languages":[...], "translation": {key: {lang: text}}}`, 9 languages: en es fr de lt pt it no el)
- Test: none (covered by the e2e in Task 5; Task 4 adds a one-off `import app` sanity check, not a test layer)

**Interfaces:**
- Produces: i18n keys `card.quadrant`, `nav.quadrant`, `quadrant.about`, `quadrant.about_text`, `quadrant.map`, `quadrant.classification`, `quadrant.axis_influence`, `quadrant.axis_dependence`, `quadrant.active`, `quadrant.critical`, `quadrant.reactive`, `quadrant.buffering`, `quadrant.undetermined` — each consumed by Tasks 3 and 4.

- [ ] **Step 1: Add the keys**

Create a one-off script `add_quadrant_i18n.py` at the repo root (delete it after running) and run it once. (Using a script, not `python -c`, avoids the Windows multi-line trap.) Missing languages fall back to English at runtime (`i18n.py:100`), so English values are authoritative; translations below mirror `leverage.*` coverage.

```python
import json, pathlib

PATH = pathlib.Path("sespy/translations/core.json")
data = json.loads(PATH.read_text(encoding="utf-8"))
tr = data["translation"]

KEYS = {
    "card.quadrant": {"en": "Factor Quadrant", "es": "Cuadrante de Factores", "fr": "Quadrant des Facteurs", "de": "Faktor-Quadrant", "lt": "Veiksnių Kvadrantas", "pt": "Quadrante de Fatores", "it": "Quadrante dei Fattori", "no": "Faktorkvadrant", "el": "Τεταρτημόριο Παραγόντων"},
    "nav.quadrant": {"en": "Factor Quadrant", "es": "Cuadrante de Factores", "fr": "Quadrant des Facteurs", "de": "Faktor-Quadrant", "lt": "Veiksnių Kvadrantas", "pt": "Quadrante de Fatores", "it": "Quadrante dei Fattori", "no": "Faktorkvadrant", "el": "Τεταρτημόριο Παραγόντων"},
    "quadrant.about": {"en": "About", "es": "Acerca de", "fr": "À propos", "de": "Über", "lt": "Apie", "pt": "Sobre", "it": "Informazioni", "no": "Om", "el": "Σχετικά"},
    "quadrant.about_text": {"en": "Factors are placed by influence (how much they drive others) against dependence (how much they are driven). Magnitude only — reinforcing and opposing links both count; read net direction from the diagram. Active = best leverage; Critical = powerful but feeds back; Reactive = outcomes/indicators; Buffering = low priority.", "es": "Los factores se ubican por influencia (cuánto impulsan a otros) frente a dependencia (cuánto son impulsados). Solo magnitud — los vínculos reforzadores y opuestos cuentan igual; lea la dirección neta en el diagrama. Activo = mejor palanca; Crítico = potente pero retroalimenta; Reactivo = resultados/indicadores; Amortiguador = baja prioridad.", "fr": "Les facteurs sont placés selon l'influence (combien ils agissent sur les autres) face à la dépendance (combien ils subissent). Magnitude seule — les liens renforçants et opposés comptent ; lisez la direction nette sur le diagramme. Actif = meilleur levier ; Critique = puissant mais en rétroaction ; Réactif = résultats/indicateurs ; Tampon = faible priorité.", "de": "Faktoren werden nach Einfluss (wie stark sie andere antreiben) gegen Abhängigkeit (wie stark sie angetrieben werden) eingeordnet. Nur Betrag — verstärkende und gegenläufige Verbindungen zählen gleich; die Nettorichtung aus dem Diagramm ablesen. Aktiv = bester Hebel; Kritisch = stark, aber rückgekoppelt; Reaktiv = Ergebnisse/Indikatoren; Puffernd = geringe Priorität.", "lt": "Veiksniai išdėstomi pagal įtaką (kiek jie veikia kitus) ir priklausomybę (kiek jie yra veikiami). Tik dydis — stiprinančios ir priešingos jungtys skaičiuojamos vienodai; grynąją kryptį žiūrėkite diagramoje. Aktyvus = geriausia svertis; Kritinis = galingas, bet su grįžtamuoju ryšiu; Reaktyvus = rezultatai/rodikliai; Buferinis = žemas prioritetas.", "pt": "Os fatores são posicionados pela influência (quanto impulsionam outros) face à dependência (quanto são impulsionados). Apenas magnitude — ligações reforçadoras e opostas contam igual; leia a direção líquida no diagrama. Ativo = melhor alavanca; Crítico = potente mas realimenta; Reativo = resultados/indicadores; Amortecedor = baixa prioridade.", "it": "I fattori sono collocati per influenza (quanto guidano gli altri) rispetto alla dipendenza (quanto sono guidati). Solo magnitudine — i legami rinforzanti e opposti contano allo stesso modo; leggere la direzione netta dal diagramma. Attivo = leva migliore; Critico = potente ma con retroazione; Reattivo = esiti/indicatori; Cuscinetto = bassa priorità.", "no": "Faktorer plasseres etter innflytelse (hvor mye de driver andre) mot avhengighet (hvor mye de drives). Kun størrelse — forsterkende og motvirkende koblinger teller likt; les netto retning fra diagrammet. Aktiv = best innflytelse; Kritisk = kraftig men gir tilbakekobling; Reaktiv = utfall/indikatorer; Bufrende = lav prioritet.", "el": "Οι παράγοντες τοποθετούνται κατά επιρροή (πόσο επηρεάζουν άλλους) έναντι εξάρτησης (πόσο επηρεάζονται). Μόνο μέγεθος — ενισχυτικοί και αντίθετοι δεσμοί μετρούν εξίσου· διαβάστε την καθαρή κατεύθυνση από το διάγραμμα. Ενεργός = καλύτερος μοχλός· Κρίσιμος = ισχυρός αλλά ανατροφοδοτεί· Αντιδραστικός = αποτελέσματα/δείκτες· Ρυθμιστικός = χαμηλή προτεραιότητα."},
    "quadrant.map": {"en": "Influence × Dependence map", "es": "Mapa de Influencia × Dependencia", "fr": "Carte Influence × Dépendance", "de": "Einfluss-×-Abhängigkeits-Karte", "lt": "Įtakos × Priklausomybės žemėlapis", "pt": "Mapa de Influência × Dependência", "it": "Mappa Influenza × Dipendenza", "no": "Innflytelse × Avhengighet-kart", "el": "Χάρτης Επιρροής × Εξάρτησης"},
    "quadrant.classification": {"en": "Factor classification", "es": "Clasificación de factores", "fr": "Classification des facteurs", "de": "Faktorklassifizierung", "lt": "Veiksnių klasifikacija", "pt": "Classificação de fatores", "it": "Classificazione dei fattori", "no": "Faktorklassifisering", "el": "Ταξινόμηση παραγόντων"},
    "quadrant.axis_influence": {"en": "Influence (drives others)", "es": "Influencia (impulsa a otros)", "fr": "Influence (agit sur les autres)", "de": "Einfluss (treibt andere)", "lt": "Įtaka (veikia kitus)", "pt": "Influência (impulsiona outros)", "it": "Influenza (guida gli altri)", "no": "Innflytelse (driver andre)", "el": "Επιρροή (επηρεάζει άλλους)"},
    "quadrant.axis_dependence": {"en": "Dependence (driven by others)", "es": "Dependencia (impulsado por otros)", "fr": "Dépendance (subit les autres)", "de": "Abhängigkeit (von anderen getrieben)", "lt": "Priklausomybė (veikiama kitų)", "pt": "Dependência (impulsionado por outros)", "it": "Dipendenza (guidato dagli altri)", "no": "Avhengighet (drevet av andre)", "el": "Εξάρτηση (επηρεάζεται από άλλους)"},
    "quadrant.active": {"en": "Active / Driving", "es": "Activo / Impulsor", "fr": "Actif / Moteur", "de": "Aktiv / Treibend", "lt": "Aktyvus / Varomasis", "pt": "Ativo / Impulsionador", "it": "Attivo / Trainante", "no": "Aktiv / Drivende", "el": "Ενεργός / Κινητήριος"},
    "quadrant.critical": {"en": "Critical / Ambivalent", "es": "Crítico / Ambivalente", "fr": "Critique / Ambivalent", "de": "Kritisch / Ambivalent", "lt": "Kritinis / Ambivalentiškas", "pt": "Crítico / Ambivalente", "it": "Critico / Ambivalente", "no": "Kritisk / Ambivalent", "el": "Κρίσιμος / Αμφίσημος"},
    "quadrant.reactive": {"en": "Reactive / Dependent", "es": "Reactivo / Dependiente", "fr": "Réactif / Dépendant", "de": "Reaktiv / Abhängig", "lt": "Reaktyvus / Priklausomas", "pt": "Reativo / Dependente", "it": "Reattivo / Dipendente", "no": "Reaktiv / Avhengig", "el": "Αντιδραστικός / Εξαρτημένος"},
    "quadrant.buffering": {"en": "Buffering / Inert", "es": "Amortiguador / Inerte", "fr": "Tampon / Inerte", "de": "Puffernd / Inert", "lt": "Buferinis / Inertiškas", "pt": "Amortecedor / Inerte", "it": "Cuscinetto / Inerte", "no": "Bufrende / Inert", "el": "Ρυθμιστικός / Αδρανής"},
    "quadrant.undetermined": {"en": "Undetermined (no differentiation)", "es": "Indeterminado (sin diferenciación)", "fr": "Indéterminé (sans différenciation)", "de": "Unbestimmt (keine Differenzierung)", "lt": "Neapibrėžta (nėra diferenciacijos)", "pt": "Indeterminado (sem diferenciação)", "it": "Indeterminato (nessuna differenziazione)", "no": "Ubestemt (ingen differensiering)", "el": "Απροσδιόριστο (χωρίς διαφοροποίηση)"},
}

for key, langs in KEYS.items():
    tr[key] = langs

PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("added", len(KEYS), "keys")
```

Run: `micromamba run -n shiny python add_quadrant_i18n.py` then delete it: `rm add_quadrant_i18n.py`.

- [ ] **Step 2: Verify the keys load and every key has 9 languages**

Run (single-line, no multi-line `-c`):
`micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation']; ks=[k for k in d if k=='nav.quadrant' or k.startswith('quadrant.') or k=='card.quadrant']; print(len(ks),'keys'); print(all(len(d[k])==9 for k in ks))"`
Expected: `13 keys` and `True`.

- [ ] **Step 3: Confirm no stray files / valid JSON, then commit**

Run: `git status --short` (expect only `sespy/translations/core.json` modified; NO `add_quadrant_i18n.py`).

```bash
git add sespy/translations/core.json
git commit -m "i18n(quadrant): add 13 Factor Quadrant keys (9 languages)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `analysis_quadrant.py` module

**Files:**
- Create: `sespy/modules/analysis_quadrant.py`
- Test: none directly (Task 4 `import app` sanity check; e2e in Task 5)

**Interfaces:**
- Consumes: `influence_dependence` (Task 1); `Project` (`data_structure`); `EventBus`; `ELEMENT_COLORS`, `DEFAULT_GROUP_COLOR` (`constants`); `t`, `Translator` (`i18n`); i18n keys (Task 2).
- Produces: `analysis_quadrant_ui(id) -> ui.Tag` and `analysis_quadrant_server(id, *, project_data, event_bus, translator=None)` — consumed by Task 4.

- [ ] **Step 1: Write the module**

Create `sespy/modules/analysis_quadrant.py`:

```python
"""Influence × Dependence Quadrant — QSEM Phase-1 parity.

Plots every factor by its influence (Σ outgoing edge weight) against its
dependence (Σ incoming edge weight), split at the mean of each axis into the
four Vester quadrants (active / critical / reactive / buffering), with an
'undetermined' state for systems with no structural differentiation. The
scoring lives in `sespy/network.py::influence_dependence`; this module is a thin
presenter mirroring `analysis_leverage.py`.
"""

from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import network as net_analysis
from ..constants import DEFAULT_GROUP_COLOR, ELEMENT_COLORS
from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t

_QUADRANT_KEYS = {
    "active": "quadrant.active",
    "critical": "quadrant.critical",
    "reactive": "quadrant.reactive",
    "buffering": "quadrant.buffering",
    "undetermined": "quadrant.undetermined",
}


@module.ui
def analysis_quadrant_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.quadrant")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("quadrant.about")),
                ui.p(
                    t("quadrant.about_text"),
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                width=260,
            ),
            ui.div(
                ui.h4(t("quadrant.map")),
                ui.output_plot("quadrant_plot", height="460px"),
                ui.tags.hr(),
                ui.h4(t("quadrant.classification")),
                ui.output_data_frame("quadrant_table"),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_quadrant_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def rows() -> dict[str, dict]:
        event_bus.isa_change.get()
        return net_analysis.influence_dependence(project_data.get().isa_data)

    @output
    @render.plot
    def quadrant_plot():
        import matplotlib.pyplot as plt

        data = rows()
        isa = project_data.get().isa_data
        type_by_id = {el.id: el.type for el in isa.elements}
        label_by_id = {el.id: el.label for el in isa.elements}

        fig, ax = plt.subplots(figsize=(7, 5))

        undetermined = bool(data) and all(
            r["quadrant"] == "undetermined" for r in data.values()
        )
        if not data or undetermined:
            msg = "No data — build a diagram first" if not data else \
                  "No differentiation — every factor scores alike"
            ax.text(0.5, 0.5, msg, ha="center", va="center",
                    transform=ax.transAxes, color="#777")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        infl = [r["influence"] for r in data.values()]
        dep = [r["dependence"] for r in data.values()]
        mean_inf = sum(infl) / len(infl)
        mean_dep = sum(dep) / len(dep)

        for nid, r in data.items():
            ax.scatter(
                r["dependence"], r["influence"],
                s=140, alpha=0.85, zorder=3,
                color=ELEMENT_COLORS.get(type_by_id.get(nid), DEFAULT_GROUP_COLOR),
                edgecolors="#2d5a7b", linewidths=0.8,
            )
            ax.annotate(
                label_by_id.get(nid, nid),
                (r["dependence"], r["influence"]),
                textcoords="offset points", xytext=(6, 4),
                fontsize=8, color="#2c3e50",
            )

        ax.axvline(mean_dep, color="#aaa", linestyle="--", linewidth=1, zorder=1)
        ax.axhline(mean_inf, color="#aaa", linestyle="--", linewidth=1, zorder=1)

        xhi = max(dep) * 1.05 + 0.5
        yhi = max(infl) * 1.05 + 0.5
        ax.set_xlim(-0.5, xhi)
        ax.set_ylim(-0.5, yhi)
        cap = dict(fontsize=8, color="#999", style="italic")
        ax.text(xhi, yhi, t("quadrant.critical"), ha="right", va="top", **cap)
        ax.text(-0.4, yhi, t("quadrant.active"), ha="left", va="top", **cap)
        ax.text(-0.4, -0.4, t("quadrant.buffering"), ha="left", va="bottom", **cap)
        ax.text(xhi, -0.4, t("quadrant.reactive"), ha="right", va="bottom", **cap)

        ax.set_xlabel(t("quadrant.axis_dependence"))
        ax.set_ylabel(t("quadrant.axis_influence"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.data_frame
    def quadrant_table():
        import pandas as pd

        cols = ["rank", "id", "label", "type", "influence", "dependence", "quadrant"]
        data = rows()
        if not data:
            return pd.DataFrame(columns=cols)
        isa = project_data.get().isa_data
        by_id = {el.id: el for el in isa.elements}
        ordered = sorted(data.items(), key=lambda kv: kv[1]["influence"], reverse=True)
        out = []
        for rank, (nid, r) in enumerate(ordered, start=1):
            el = by_id.get(nid)
            out.append({
                "rank": rank,
                "id": nid,
                "label": el.label if el else nid,
                "type": el.type if el else "",
                "influence": round(r["influence"], 3),
                "dependence": round(r["dependence"], 3),
                "quadrant": t(_QUADRANT_KEYS.get(r["quadrant"], r["quadrant"])),
            })
        return pd.DataFrame(out, columns=cols)
```

- [ ] **Step 2: Verify the module imports**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_quadrant as m; print(hasattr(m,'analysis_quadrant_ui'), hasattr(m,'analysis_quadrant_server'))"`
Expected: `True True`.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/analysis_quadrant.py
git commit -m "feat(module): Factor Quadrant analysis module (UI + server)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wire into `app.py`

**Files:**
- Modify: `app.py` (import block; `NAV` list ~78-96; `NAV_TO_STEP` ~111-123; `PANELS` ~128-143; server registration ~218-223)

**Interfaces:**
- Consumes: `analysis_quadrant_ui`, `analysis_quadrant_server` (Task 3); `NavItem` (already imported in `app.py`); `nav.quadrant` key (Task 2).
- Produces: a reachable "Factor Quadrant" panel with id/value `quadrant` and sidebar button `#sespy_nav_quadrant`.

- [ ] **Step 1: Add the import**

Next to the other module imports (after the `analysis_leverage` import at `app.py:41`):

```python
from sespy.modules.analysis_quadrant import analysis_quadrant_server, analysis_quadrant_ui
```

- [ ] **Step 2: Add the `NAV` entry**

In `NAV` (app.py:78-96), immediately after the `leverage` line:

```python
    NavItem(id="quadrant", icon="table-cells-large", label="Factor Quadrant", label_key="nav.quadrant"),
```

- [ ] **Step 3: Add the `NAV_TO_STEP` mapping**

In `NAV_TO_STEP` (app.py:111-123), add `quadrant` to the analyze group (e.g. alongside `leverage`):

```python
    "leverage": "analyze", "quadrant": "analyze", "boolean": "analyze", "simulation": "analyze",
```

- [ ] **Step 4: Add the panel + server call**

In `PANELS`, after the "Leverage Points" `nav_panel` (app.py:134):

```python
    ui.nav_panel("Factor Quadrant",   analysis_quadrant_ui("quadrant"),            value="quadrant"),
```

In the server body, after the `analysis_leverage_server(...)` call (app.py:218-223):

```python
    analysis_quadrant_server(
        "quadrant",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 5: Verify the app imports and the panel is registered**

Run: `micromamba run -n shiny python -c "import app; ids=[getattr(i,'id',None) for i in app.NAV]; print('quadrant' in ids, app.NAV_TO_STEP.get('quadrant'))"`
Expected: `True analyze`.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat(app): register Factor Quadrant panel (nav + step + panel + server)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: e2e test + full e2e gate

**Files:**
- Create: `tests/test_quadrant_e2e.py`

**Interfaces:**
- Consumes: the running app (`shiny run app.py` at `127.0.0.1:8000`, started by `tests/run_e2e.py`); the `#sespy_nav_quadrant` button (Task 4); the default project `data/sample_ses.json`.

- [ ] **Step 1: Write the e2e script**

Create `tests/test_quadrant_e2e.py` (modelled exactly on `tests/test_leverage_e2e.py`):

```python
"""E2E for the Factor Quadrant module."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Click "Factor Quadrant"
        await page.click("#sespy_nav_quadrant")
        await page.wait_for_timeout(2500)  # settle pad

        nav_active = await page.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        assert nav_active == ["sespy_nav_quadrant"], f"unexpected: {nav_active}"

        # Wait for the late-mounting data_frame <tbody> and the matplotlib <img>
        # rather than racing a fixed sleep (cold first render can exceed 2500ms;
        # mirrors test_simulation_e2e.py / test_boolean_e2e.py).
        await page.wait_for_selector("#quadrant-quadrant_table table tbody tr", timeout=30000)
        await page.wait_for_selector("#quadrant-quadrant_plot img", timeout=30000)

        # Classification table rendered rows
        row_count = await page.evaluate(
            "() => document.querySelectorAll("
            "'#quadrant-quadrant_table table tbody tr').length"
        )
        print(f"quadrant table rows: {row_count}")
        assert row_count > 0, "classification table is empty"

        # The 17-node sample must differentiate into >= 2 distinct quadrants —
        # guards against a degeneracy-guard misfire (all 'undetermined') or an
        # all-same-quadrant classifier bug rendering a caption-only plot yet
        # still passing row_count>0 / img>0. Mirrors test_leverage_e2e.py:34's
        # `assert min(sizes) < max(sizes)`.
        quadrants = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#quadrant-quadrant_table table tbody tr'))"
            ".map(tr => tr.querySelector('td:last-child')?.textContent?.trim())"
            ".filter(Boolean)"
        )
        distinct = set(quadrants)
        print(f"distinct quadrants: {distinct}")
        assert len(distinct) >= 2, f"factors not differentiated: {distinct}"

        # Scatter plot image rendered
        img = await page.evaluate(
            "() => { const i = document.querySelector('#quadrant-quadrant_plot img');"
            " return i ? i.naturalWidth : 0; }"
        )
        assert img > 0, "quadrant plot image did not render"

        await page.screenshot(path="tests/screenshots/quadrant.png")
        print("\nquadrant e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the FULL e2e suite (never `-k "not e2e"`)**

Run: `micromamba run -n shiny python tests/run_e2e.py`
Expected: all e2e scripts pass, including `test_quadrant_e2e.py` ("quadrant e2e assertions pass") and every pre-existing script (regression check — a shared CSS/selector change must not break siblings).

If the table/plot selector ids differ at runtime, inspect the rendered DOM (the module id is `quadrant`, output ids `quadrant_table` / `quadrant_plot`, so Shiny composes `#quadrant-quadrant_table` / `#quadrant-quadrant_plot`) and adjust the selectors — do not weaken the assertions.

- [ ] **Step 3: Run the unit suite too (no regressions)**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q`
Expected: PASS (existing + 7 new).

- [ ] **Step 4: Commit**

```bash
git add tests/test_quadrant_e2e.py
git commit -m "test(e2e): Factor Quadrant panel navigation + render

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria
- `influence_dependence` unit tests green (8 new).
- 13 i18n keys present in all 9 languages.
- "Factor Quadrant" panel reachable from the sidebar, plots + table render on the default sample.
- Full e2e suite green via `python tests/run_e2e.py` (new + all pre-existing).
- Five commits, repo clean, no stray files.
