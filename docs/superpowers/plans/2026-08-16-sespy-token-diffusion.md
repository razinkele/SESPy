# Stochastic Token Diffusion (issue #17) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `token_diffusion()` to `sespy/dynamics.py` — vectorised stochastic random-walk propagation from an intervention node — and surface it as a second block ("Intervention Simulation") in the existing Intervention card.

**Architecture:** A pure numpy function compiles the signed digraph to CSR-style arrays once, then walks all tokens in lockstep (one vectorised op per step, not per token). The UI reuses the button-gated `reactive.value` pattern from the cascade/paths blocks, inside `analysis_intervention.py`'s existing sidebar+main card. Spec: `docs/superpowers/specs/2026-08-16-token-diffusion-design.md`.

**Tech Stack:** Python, numpy, matplotlib, Shiny for Python, pytest, Playwright e2e.

## Global Constraints

- Python ONLY via `micromamba run -n shiny python …` (no global python, no pip/venv).
- Unit suite (CI parity): `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` (518 green on main, 5 pre-existing warnings).
- e2e: ALWAYS the full suite `micromamba run -n shiny python tests/run_e2e.py` (32 script-runs); kill port 8000 first; exceeds the ~600s tool cap — the controller runs it detached LAST on an IDLE machine (a contention flake burned a prior run); implementers must NOT attempt it.
- Every i18n key needs all 9 languages (en es fr de lt pt it no el), one line per key in `sespy/translations/core.json`.
- `sespy/dynamics.py` is numpy + TypedDict and **pandas-free** — return dicts, never DataFrames (module layer may build one).
- Degenerate inputs return the empty shape, never raise. Results must be reproducible for a fixed seed.
- Playwright selectors scoped to ids (`#intervention-diffusion_summary`, `#intervention-run_diffusion`, `#intervention-diffusion_chart`), never bare `text=`.
- Renderers subscribe `event_bus.isa_change.get()` first; button effects use `@reactive.event(..., ignore_init=True)`.
- Commit style: conventional. Branch `feat/token-diffusion` off `main`.

**Golden values** (computed against the real repo with a reference implementation of the exact algorithm below, 2026-08-16 — these hold only if the implementation draws RNG exactly as written: one `rng.random(k)` per step over the LIVE tokens only):

- **Manual-trace chain** A→B→C→D with B→C negative, `n_steps=5, n_tokens=100, seed=0`: three rows, each `tokens_received=100`; B `"+"` first step 1; C `"-"` first step 2; D `"-"` first step 3. (Deterministic — single route; validates counts, the negative flip persisting downstream, and arrival steps.)
- **Sink behaviour** A→B→T (T has no out-edges), `n_steps=6, n_tokens=50, seed=0`: exactly two rows, B 50 tokens step 1, T 50 tokens step 2 — T is NOT credited again on steps 3-6 because its tokens stopped.
- **Sink source** (source has no out-edges): empty shape, `n_reached=0`.
- **Contested `~`** on A→X(+)→T, A→Y(−)→T with `n_steps=3, n_tokens=1000, seed=1`: T `tokens_received=1000`, `net_sign="~"` (507/493 split, 1.4 % ≤ 5 %), first step 2; X 507 `"+"`, Y 493 `"-"`, both first step 1. (With `seed=0` the split is 473/527 = 5.4 % → `"-"`, so the seed matters here.)
- **Sample** `data/sample_ses.json`, source `D001`, defaults (`n_steps=10, n_tokens=1000`), `seed=0`: `n_reached=7`; rows in order — P001 2000 `"+"` step 2; MPF1 2000 `"-"` step 3; GB01 1501 `"-"` step 5; A001 1499 `"+"` step 1; ES03 1002 `"-"` step 4; ES01 998 `"-"` step 4; R002 501 `"-"` step 6. Source D001 absent from rows. Same seed reproduces exactly; `seed=1` differs.

---

### Task 0: Branch

- [ ] **Step 1:**

```bash
git checkout -b feat/token-diffusion
```

---

### Task 1: `token_diffusion()` in `sespy/dynamics.py`

**Files:**
- Modify: `sespy/dynamics.py` (append at end of file)
- Test: `tests/test_dynamics.py` (append; the file already imports `numpy as np`, `pytest`, `dynamics`, and `Connection`/`Element`/`IsaData`, and defines the `_isa(elements, connections)` helper — reuse them)

**Interfaces:**
- Consumes: `IsaData`, `np` (both already imported in `dynamics.py`).
- Produces: `token_diffusion(isa: IsaData, source: str, *, n_steps: int = 10, n_tokens: int = 1000, seed: int | None = None) -> dict` returning `{"rows": [{"id", "label", "tokens_received", "net_sign", "first_arrival_step"}], "source": str, "n_tokens": int, "n_steps": int, "n_reached": int}`. Task 3's renderer consumes exactly this shape.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_dynamics.py`:

```python
# ============================================================
# token_diffusion (issue #17)
# ============================================================


def _chain_isa():
    """A -> B -(-)-> C -> D: a single route, so every token's itinerary is
    known in advance and the whole result is hand-checkable."""
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in "ABCD"]
    conns = [Connection(source="A", target="B", polarity="+"),
             Connection(source="B", target="C", polarity="-"),
             Connection(source="C", target="D", polarity="+")]
    return _isa(els, conns)


def test_token_diffusion_matches_manual_trace():
    r = dynamics.token_diffusion(_chain_isa(), "A",
                                 n_steps=5, n_tokens=100, seed=0)
    assert r["source"] == "A" and r["n_reached"] == 3
    assert r["rows"] == [
        {"id": "B", "label": "b", "tokens_received": 100,
         "net_sign": "+", "first_arrival_step": 1},
        {"id": "C", "label": "c", "tokens_received": 100,
         "net_sign": "-", "first_arrival_step": 2},
        {"id": "D", "label": "d", "tokens_received": 100,
         "net_sign": "-", "first_arrival_step": 3},
    ]


def test_token_diffusion_sink_tokens_stop():
    # T has no outgoing edges: its 50 tokens arrive once at step 2 and are
    # NOT re-counted on steps 3-6. A regression that keeps sinks "live"
    # would credit T four more times.
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in ("A", "B", "T")]
    conns = [Connection(source="A", target="B", polarity="+"),
             Connection(source="B", target="T", polarity="+")]
    r = dynamics.token_diffusion(_isa(els, conns), "A",
                                 n_steps=6, n_tokens=50, seed=0)
    assert [(x["id"], x["tokens_received"], x["first_arrival_step"])
            for x in r["rows"]] == [("B", 50, 1), ("T", 50, 2)]


def test_token_diffusion_contested_sign():
    # Equal-probability +/- routes converge on T: the split lands inside
    # the 5% margin at this seed, so T is contested rather than signed.
    els = [Element(id=i, label=i.lower(), type="Drivers")
           for i in ("A", "X", "Y", "T")]
    conns = [Connection(source="A", target="X", polarity="+"),
             Connection(source="A", target="Y", polarity="-"),
             Connection(source="X", target="T", polarity="+"),
             Connection(source="Y", target="T", polarity="+")]
    r = dynamics.token_diffusion(_isa(els, conns), "A",
                                 n_steps=3, n_tokens=1000, seed=1)
    by_id = {x["id"]: x for x in r["rows"]}
    assert by_id["T"]["net_sign"] == "~"
    assert by_id["T"]["tokens_received"] == 1000
    assert by_id["X"]["net_sign"] == "+" and by_id["Y"]["net_sign"] == "-"
    assert by_id["X"]["tokens_received"] + by_id["Y"]["tokens_received"] == 1000


def test_token_diffusion_seed_reproducible_and_distinct():
    isa = _isa([Element(id=i, label=i.lower(), type="Drivers")
                for i in ("A", "X", "Y", "T")],
               [Connection(source="A", target="X"),
                Connection(source="A", target="Y"),
                Connection(source="X", target="T"),
                Connection(source="Y", target="T")])
    a = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=3)
    b = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=3)
    c = dynamics.token_diffusion(isa, "A", n_tokens=500, seed=4)
    assert a == b
    assert a != c


def test_token_diffusion_sample_golden():
    from pathlib import Path

    from sespy.data_structure import load_sample

    root = Path(__file__).resolve().parents[1]
    r = dynamics.token_diffusion(load_sample(root / "data" / "sample_ses.json"),
                                 "D001", seed=0)
    assert r["n_reached"] == 7
    assert r["n_steps"] == 10 and r["n_tokens"] == 1000
    assert [(x["id"], x["tokens_received"], x["net_sign"],
             x["first_arrival_step"]) for x in r["rows"]] == [
        ("P001", 2000, "+", 2),
        ("MPF1", 2000, "-", 3),
        ("GB01", 1501, "-", 5),
        ("A001", 1499, "+", 1),
        ("ES03", 1002, "-", 4),
        ("ES01", 998, "-", 4),
        ("R002", 501, "-", 6),
    ]
    assert all(x["id"] != "D001" for x in r["rows"])  # source excluded


def test_token_diffusion_degenerate_shapes():
    chain = _chain_isa()
    for kwargs in ({"n_tokens": 0}, {"n_steps": 0}):
        r = dynamics.token_diffusion(chain, "A", seed=0, **kwargs)
        assert r["rows"] == [] and r["n_reached"] == 0
    # unknown source
    assert dynamics.token_diffusion(chain, "NOPE", seed=0)["rows"] == []
    # empty model
    assert dynamics.token_diffusion(IsaData(), "A", seed=0)["rows"] == []
    # sink SOURCE: nothing can leave, so nothing is ever received
    els = [Element(id=i, label=i.lower(), type="Drivers") for i in ("A", "B")]
    r = dynamics.token_diffusion(_isa(els, [Connection(source="B", target="A")]),
                                 "A", n_steps=5, n_tokens=10, seed=0)
    assert r == {"rows": [], "source": "A", "n_tokens": 10,
                 "n_steps": 5, "n_reached": 0}
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_dynamics.py -q -k token_diffusion`
Expected: 6 errors, `AttributeError: module 'sespy.dynamics' has no attribute 'token_diffusion'`.

- [ ] **Step 3: Implement** — append to `sespy/dynamics.py`:

```python
def token_diffusion(
    isa: IsaData, source: str, *,
    n_steps: int = 10, n_tokens: int = 1000, seed: int | None = None,
) -> dict:
    """Stochastic token diffusion from an intervention node — step 2 of the
    Donlan et al. 2026 participatory framework (doi:10.21203/rs.3.rs-10397797/v1).

    n_tokens positive tokens start at `source`. Each step, every token whose
    node has outgoing edges hops to ONE uniformly-random out-neighbour;
    traversing a "-" edge flips the token's polarity. Tokens reaching a sink
    stay there and stop contributing arrivals. Per node (excluding the
    source) we accumulate arrivals across all steps, the polarity split on
    arrival, and the 1-based step of first arrival — a reach-and-speed
    profile that ranks which parts of the system an intervention at `source`
    actually touches, how fast, and with what net sign.

    net_sign is "+"/"-" by majority, or "~" when the split is within 5%
    (contested). Nodes never reached are omitted. Rows sort by
    tokens_received descending, ties in isa.elements order. Parallel edges
    deduplicate last-wins (the _axis_sums convention); self-loops and
    dangling refs are skipped; only "-" flips a token.

    Vectorised: one rng draw per STEP over the live tokens, not per token,
    so 5000 tokens x 30 steps is 30 numpy ops. Identical (isa, source,
    n_steps, n_tokens, seed) reproduce exactly. Unknown source, empty model,
    non-positive n_steps/n_tokens, or a source with no outgoing edges return
    the empty shape; never raises. Pure apart from the seeded RNG.
    """
    empty = {"rows": [], "source": source, "n_tokens": n_tokens,
             "n_steps": n_steps, "n_reached": 0}
    order = {el.id: i for i, el in enumerate(isa.elements)}
    if source not in order or n_tokens <= 0 or n_steps <= 0:
        return empty

    n = len(isa.elements)
    pairs: dict[tuple[str, str], str] = {}
    for c in isa.connections:
        if c.source == c.target or c.source not in order or c.target not in order:
            continue
        pairs[(c.source, c.target)] = c.polarity
    neighbours: list[list[tuple[int, bool]]] = [[] for _ in range(n)]
    for (src, tgt), polarity in pairs.items():
        neighbours[order[src]].append((order[tgt], polarity == "-"))

    indptr = np.zeros(n + 1, dtype=np.int64)
    for i, lst in enumerate(neighbours):
        indptr[i + 1] = indptr[i] + len(lst)
    flat = [x for lst in neighbours for x in lst]
    indices = np.array([t for t, _ in flat], dtype=np.int64) if flat \
        else np.zeros(0, dtype=np.int64)
    flips = np.array([f for _, f in flat], dtype=bool) if flat \
        else np.zeros(0, dtype=bool)
    outdeg = np.diff(indptr)
    if outdeg[order[source]] == 0:
        return empty

    rng = np.random.default_rng(seed)
    pos = np.full(n_tokens, order[source], dtype=np.int64)
    sign = np.ones(n_tokens, dtype=np.int8)
    pos_count = np.zeros(n, dtype=np.int64)
    neg_count = np.zeros(n, dtype=np.int64)
    first = np.full(n, -1, dtype=np.int64)

    for step in range(1, n_steps + 1):
        live = np.nonzero(outdeg[pos] > 0)[0]
        if live.size == 0:
            break
        here = pos[live]
        slot = indptr[here] + (rng.random(live.size) * outdeg[here]).astype(np.int64)
        pos[live] = indices[slot]
        sign[live] = sign[live] * np.where(flips[slot], -1, 1).astype(np.int8)
        landed, landed_sign = pos[live], sign[live]
        np.add.at(pos_count, landed[landed_sign > 0], 1)
        np.add.at(neg_count, landed[landed_sign < 0], 1)
        arrived = np.unique(landed)
        first[arrived[first[arrived] < 0]] = step

    rows: list[dict] = []
    src_index = order[source]
    for el in isa.elements:
        i = order[el.id]
        if i == src_index:
            continue
        pos_i, neg_i = int(pos_count[i]), int(neg_count[i])
        total = pos_i + neg_i
        if total == 0:
            continue
        if abs(pos_i - neg_i) / total <= 0.05:
            net = "~"
        else:
            net = "+" if pos_i > neg_i else "-"
        rows.append({"id": el.id, "label": el.label, "tokens_received": total,
                     "net_sign": net, "first_arrival_step": int(first[i])})
    rows.sort(key=lambda r: -r["tokens_received"])
    return {"rows": rows, "source": source, "n_tokens": n_tokens,
            "n_steps": n_steps, "n_reached": len(rows)}
```

- [ ] **Step 4: Run the new tests, then the full unit suite** (Global Constraints command) — expect 6 passed, then 524 passed / 5 pre-existing warnings.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): token_diffusion() - vectorised stochastic intervention reach (#17)"
```

---

### Task 2: i18n (9 keys × 9 languages) + presence test

**Files:**
- Modify: `sespy/translations/core.json` (insert after the `"metrics.paths_truncated"` line, one line per key)
- Test: `tests/test_i18n.py` (append after `test_causal_paths_keys_present`)

**Interfaces:**
- Produces: `diffusion.title`, `diffusion.source`, `diffusion.steps`, `diffusion.tokens`, `diffusion.run`, `diffusion.hint`, `diffusion.none`, `diffusion.summary` (params `{reached}`, `{total}`, `{tokens}`, `{steps}`), `diffusion.caption`. Task 3 uses exactly these.

- [ ] **Step 1: Write the failing test** — append to `tests/test_i18n.py`:

```python
def test_token_diffusion_keys_present(translations):
    for key in ("diffusion.title", "diffusion.source", "diffusion.steps",
                "diffusion.tokens", "diffusion.run", "diffusion.hint",
                "diffusion.none", "diffusion.summary", "diffusion.caption"):
        assert key in translations
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q -k token_diffusion` → FAIL.

- [ ] **Step 3: Insert the keys VERBATIM** (then verify JSON validity with `micromamba run -n shiny python -c "import json;json.load(open('sespy/translations/core.json',encoding='utf-8'))"`):

```json
    "diffusion.title": {"en": "Intervention simulation", "es": "Simulación de intervención", "fr": "Simulation d'intervention", "de": "Interventionssimulation", "lt": "Intervencijos modeliavimas", "pt": "Simulação de intervenção", "it": "Simulazione di intervento", "no": "Intervensjonssimulering", "el": "Προσομοίωση παρέμβασης"},
    "diffusion.source": {"en": "Intervene at", "es": "Intervenir en", "fr": "Intervenir sur", "de": "Eingriff bei", "lt": "Įsikišti ties", "pt": "Intervir em", "it": "Intervenire su", "no": "Grip inn ved", "el": "Παρέμβαση στο"},
    "diffusion.steps": {"en": "Steps", "es": "Pasos", "fr": "Étapes", "de": "Schritte", "lt": "Žingsniai", "pt": "Passos", "it": "Passi", "no": "Trinn", "el": "Βήματα"},
    "diffusion.tokens": {"en": "Tokens", "es": "Fichas", "fr": "Jetons", "de": "Marken", "lt": "Žetonai", "pt": "Fichas", "it": "Gettoni", "no": "Brikker", "el": "Μονάδες"},
    "diffusion.run": {"en": "Run simulation", "es": "Ejecutar simulación", "fr": "Lancer la simulation", "de": "Simulation ausführen", "lt": "Vykdyti modeliavimą", "pt": "Executar simulação", "it": "Esegui simulazione", "no": "Kjør simulering", "el": "Εκτέλεση προσομοίωσης"},
    "diffusion.hint": {"en": "not simulated for the current model — run to compute", "es": "no simulado para el modelo actual: ejecute para calcular", "fr": "non simulé pour le modèle actuel — lancez le calcul", "de": "für das aktuelle Modell nicht simuliert — zum Berechnen ausführen", "lt": "dabartiniam modeliui nemodeliuota — paleiskite skaičiavimą", "pt": "não simulado para o modelo atual — execute para calcular", "it": "non simulato per il modello attuale — eseguire per calcolare", "no": "ikke simulert for gjeldende modell — kjør for å beregne", "el": "δεν έχει προσομοιωθεί για το τρέχον μοντέλο — εκτελέστε για υπολογισμό"},
    "diffusion.none": {"en": "no element is reached from here — the chosen element has no outgoing links", "es": "no se alcanza ningún elemento desde aquí: el elemento elegido no tiene enlaces salientes", "fr": "aucun élément n'est atteint depuis ici — l'élément choisi n'a aucun lien sortant", "de": "von hier wird kein Element erreicht — das gewählte Element hat keine ausgehenden Verbindungen", "lt": "iš čia nepasiekiamas nė vienas elementas — pasirinktas elementas neturi išeinančių ryšių", "pt": "nenhum elemento é alcançado a partir daqui — o elemento escolhido não tem ligações de saída", "it": "nessun elemento viene raggiunto da qui — l'elemento scelto non ha collegamenti in uscita", "no": "ingen elementer nås herfra — det valgte elementet har ingen utgående koblinger", "el": "κανένα στοιχείο δεν προσεγγίζεται από εδώ — το επιλεγμένο στοιχείο δεν έχει εξερχόμενους δεσμούς"},
    "diffusion.summary": {"en": "{reached} of {total} elements reached by {tokens} tokens in {steps} steps", "es": "{reached} de {total} elementos alcanzados por {tokens} fichas en {steps} pasos", "fr": "{reached} éléments sur {total} atteints par {tokens} jetons en {steps} étapes", "de": "{reached} von {total} Elementen von {tokens} Marken in {steps} Schritten erreicht", "lt": "{reached} iš {total} elementų pasiekti {tokens} žetonais per {steps} žingsnius", "pt": "{reached} de {total} elementos alcançados por {tokens} fichas em {steps} passos", "it": "{reached} di {total} elementi raggiunti da {tokens} gettoni in {steps} passi", "no": "{reached} av {total} elementer nådd av {tokens} brikker på {steps} trinn", "el": "{reached} από {total} στοιχεία προσεγγίστηκαν από {tokens} μονάδες σε {steps} βήματα"},
    "diffusion.caption": {"en": "tokens follow random outgoing links; negative links flip a token's sign. The random draw is fixed, so two intervention points differ by structure, not chance.", "es": "las fichas siguen enlaces salientes al azar; los enlaces negativos invierten su signo. El sorteo es fijo, así que dos puntos de intervención difieren por estructura, no por azar.", "fr": "les jetons suivent des liens sortants au hasard ; les liens négatifs inversent leur signe. Le tirage est fixe : deux points d'intervention diffèrent par la structure, non par hasard.", "de": "Marken folgen zufälligen ausgehenden Verbindungen; negative Verbindungen kehren ihr Vorzeichen um. Die Ziehung ist fest, sodass sich zwei Eingriffspunkte durch die Struktur unterscheiden, nicht durch Zufall.", "lt": "žetonai eina atsitiktiniais išeinančiais ryšiais; neigiami ryšiai apverčia jų ženklą. Atsitiktinis traukimas fiksuotas, todėl du intervencijos taškai skiriasi struktūra, o ne atsitiktinumu.", "pt": "as fichas seguem ligações de saída aleatórias; ligações negativas invertem o seu sinal. O sorteio é fixo, portanto dois pontos de intervenção diferem pela estrutura, não pelo acaso.", "it": "i gettoni seguono collegamenti in uscita casuali; i collegamenti negativi ne invertono il segno. L'estrazione è fissa, quindi due punti di intervento differiscono per struttura, non per caso.", "no": "brikker følger tilfeldige utgående koblinger; negative koblinger snur fortegnet. Trekningen er fast, så to inngrepspunkter skiller seg ved struktur, ikke tilfeldighet.", "el": "οι μονάδες ακολουθούν τυχαίους εξερχόμενους δεσμούς· οι αρνητικοί δεσμοί αντιστρέφουν το πρόσημο. Η τυχαία επιλογή είναι σταθερή, ώστε δύο σημεία παρέμβασης να διαφέρουν λόγω δομής, όχι τύχης."},
```

- [ ] **Step 4: Run `micromamba run -n shiny python -m pytest tests/test_i18n.py -q`** — all pass including the 9-language drift test.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(diffusion): intervention-simulation keys in all nine languages (#17)"
```

---

### Task 3: UI block in the Intervention card + e2e

**Files:**
- Modify: `sespy/modules/analysis_intervention.py` — sidebar controls, main-column outputs, and server state/effects/renderers.
- Modify: `tests/test_intervention_e2e.py` — append before the final `print(...)`/browser close.

**Interfaces:**
- Consumes: `token_diffusion(isa, source, n_steps=…, n_tokens=…, seed=0)` (Task 1 shape), i18n keys (Task 2), existing key `metrics.gov_gap_none`.
- Produces: DOM nodes `#intervention-diffusion_controls`, `#intervention-diffusion_summary`, `#intervention-diffusion_chart`, `#intervention-run_diffusion`, `#intervention-diffusion_source`.

- [ ] **Step 1: Import the dynamics module** — at the top of `sespy/modules/analysis_intervention.py`, beside the existing `from .. import network as net_analysis` import, add:

```python
from .. import dynamics as dyn
```

- [ ] **Step 2: Sidebar controls** — in `analysis_intervention_ui`, immediately after the existing `ui.input_action_button("reset", …)` block and before `width=280,`, insert:

```python
                ui.tags.hr(),
                ui.h5(t("diffusion.title")),
                ui.output_ui("diffusion_controls"),
                ui.input_slider("n_steps", t("diffusion.steps"),
                                min=3, max=30, value=10, step=1),
                ui.input_slider("n_tokens", t("diffusion.tokens"),
                                min=100, max=5000, value=1000, step=100),
                ui.input_action_button(
                    "run_diffusion", t("diffusion.run"),
                    class_="btn btn-sm btn-outline-primary",
                ),
```

- [ ] **Step 3: Main-column outputs** — in `analysis_intervention_ui`, immediately after the `output_pyvis_network(...)` call's closing `),` and before the closing `),` of the enclosing `ui.div(`, insert:

```python
                ui.tags.hr(),
                ui.h4(t("diffusion.title")),
                ui.output_ui("diffusion_summary"),
                ui.output_plot("diffusion_chart", height="260px"),
```

- [ ] **Step 4: Server state, effects and renderers** — in `analysis_intervention_server`, after the `_network()` renderer at the end of the function, append:

```python
    _diffusion_result = reactive.value(None)

    @output
    @render.ui
    def diffusion_controls():
        event_bus.isa_change.get()
        els = project_data.get().isa_data.elements
        if not els:
            return ui.div()
        choices = {el.id: f"{el.id} · {el.label}" for el in els}
        # Keep the user's pick across re-renders (isolate so choosing a
        # source doesn't itself re-render this block), falling back when
        # the model no longer has that element.
        with reactive.isolate():
            try:
                current = input.diffusion_source()
            except Exception:
                current = None
        return ui.input_select(
            "diffusion_source", t("diffusion.source"), choices,
            selected=current if current in choices else els[0].id,
        )

    @reactive.effect
    def _reset_diffusion():
        event_bus.isa_change.get()
        _diffusion_result.set(None)

    @reactive.effect
    @reactive.event(input.run_diffusion, ignore_init=True)
    def _run_diffusion():
        try:
            src = input.diffusion_source()
        except Exception:
            src = None
        if not src:
            return
        # Fixed seed: two intervention points then differ by structure
        # rather than by chance, which is the point of comparing them.
        _diffusion_result.set(dyn.token_diffusion(
            project_data.get().isa_data, src,
            n_steps=int(input.n_steps() or 10),
            n_tokens=int(input.n_tokens() or 1000),
            seed=0,
        ))

    @output
    @render.ui
    def diffusion_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 2:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        r = _diffusion_result.get()
        if r is None:
            return ui.p(t("diffusion.hint"), class_="text-muted",
                        style="font-size: 0.85rem;")
        if not r["rows"]:
            return ui.p(t("diffusion.none"), class_="text-muted")
        header = ui.tags.tr(
            ui.tags.th(""), ui.tags.th("tokens"),
            ui.tags.th("net sign"), ui.tags.th("first step"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(f"{row['id']} · {row['label']}"),
                ui.tags.td(str(row["tokens_received"])),
                ui.tags.td(ui.tags.strong(row["net_sign"])),
                ui.tags.td(str(row["first_arrival_step"])),
            )
            for row in r["rows"]
        ]
        return ui.div(
            ui.p(ui.tags.strong(t(
                "diffusion.summary", reached=r["n_reached"],
                total=len(isa.elements), tokens=r["n_tokens"],
                steps=r["n_steps"]))),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("diffusion.caption"), class_="text-muted",
                 style="font-size: 0.85rem;"),
        )

    @output
    @render.plot
    def diffusion_chart():
        import matplotlib.pyplot as plt

        r = _diffusion_result.get()
        rows = (r or {}).get("rows", [])[:12]
        fig, ax = plt.subplots(figsize=(8, 2.6))
        if rows:
            colours = {"+": "#2e7d32", "-": "#c62828", "~": "#757575"}
            ax.bar(
                range(len(rows)),
                [row["tokens_received"] for row in rows],
                color=[colours[row["net_sign"]] for row in rows],
            )
            ax.set_xticks(range(len(rows)))
            ax.set_xticklabels([row["label"] for row in rows],
                               rotation=30, ha="right", fontsize=8)
            ax.set_ylabel("tokens")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig
```

- [ ] **Step 5: e2e block** — in `tests/test_intervention_e2e.py`, insert immediately before the final `print("\nintervention e2e assertions pass")` line:

```python
        # --- Intervention simulation (token diffusion), fixed seed 0 ---
        await page.wait_for_selector("#intervention-diffusion_summary", timeout=15000)
        hint = (await page.inner_text("#intervention-diffusion_summary")).strip()
        assert "not simulated" in hint, f"expected idle hint, got: {hint!r}"
        await page.select_option("#intervention-diffusion_source", "D001")
        await page.click("#intervention-run_diffusion")
        diff_text = ""
        for _ in range(30):
            await page.wait_for_timeout(500)
            diff_text = (await page.inner_text("#intervention-diffusion_summary")).strip()
            if "elements reached" in diff_text:
                break
        # Sample golden at seed 0: D001 reaches 7 of 17 elements; the top
        # row is P001 with 2000 tokens.
        assert "7 of 17 elements reached by 1000 tokens in 10 steps" in diff_text, \
            f"expected summary, got: {diff_text!r}"
        assert "Anchor damage" in diff_text and "2000" in diff_text, \
            f"expected top row, got: {diff_text!r}"
        # The bar chart must render as an <img> once results exist.
        chart_ok = await page.evaluate(
            "() => { const el = document.getElementById('intervention-diffusion_chart');"
            " return !!el && !!el.querySelector('img'); }"
        )
        assert chart_ok, "diffusion chart did not render an image"
        print(f"intervention simulation: OK ({diff_text[:90]!r})")
```

- [ ] **Step 6: Sanity-import and run the unit suite**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_intervention"` → clean.
Run the full CI-parity unit suite once → expect 525 passed (524 + Task 2's presence test). Do NOT run the e2e suite (the controller runs it detached, last, on an idle machine).

- [ ] **Step 7: Commit**

```bash
git add sespy/modules/analysis_intervention.py tests/test_intervention_e2e.py
git commit -m "feat(intervention): button-gated token-diffusion simulation block (#17)"
```

---

### Task 4: Changelog, merge, close issue #17

- [ ] **Step 1: Changelog** — first bullet under `## [Unreleased]` in `CHANGELOG.md`:

```markdown
- New "Intervention simulation" block on the Intervention card (#17): seed
  tokens at any element and watch them diffuse along the causal links —
  negative links flip a token's sign — giving a ranked reach, net sign and
  first-arrival step per element, with a colour-coded chart. Lets two
  candidate intervention points be compared directly (Donlan et al. 2026,
  doi:10.21203/rs.3.rs-10397797/v1).
```

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): intervention-simulation block under Unreleased (#17)"
```

- [ ] **Step 2: Merge and push** (after the final branch review is clean AND the detached full e2e is green):

```bash
git checkout main
git merge --no-ff feat/token-diffusion -m "feat: stochastic token diffusion (#17)"
git push
```

- [ ] **Step 3: Close issue #17** noting deviations: dict-of-rows rather than a DataFrame (`dynamics.py` is numpy/TypedDict, pandas-free); signature takes `IsaData`, not a networkx graph, matching every other function in the module; unreached nodes are omitted from rows rather than listed with `first_arrival_step=None` (the counts convey the same, and `n_reached`/element count give the denominator); the UI fixes `seed=0` rather than exposing it, so two candidate interventions differ by structure rather than chance; the block lives in the Intervention card (not Network Metrics), where the ablation analysis already answers the neighbouring question.

---

## Self-review notes

- Spec coverage: vectorised CSR walk + sign flip + sink stop (Task 1), `~` contested margin (Task 1 + test), reproducible seed (Task 1 + test), manual-trace validation per the issue's acceptance criteria (Task 1 chain test), 9 i18n keys + presence (Task 2), sidebar controls + button gating + summary + table + colour-coded chart (Task 3), scoped e2e incl. chart render and idle→computed transition (Task 3), changelog + issue close with deviations (Task 4).
- Type consistency: result keys identical across Tasks 1 and 3; DOM ids identical across Task 3's renderer and e2e; i18n params match `t()` kwargs.
- Golden values computed against the real repo on 2026-08-16 with a reference implementation of the exact algorithm in Task 1 Step 3 (chain, sink, sink-source, contested-seed and sample fixtures all verified).
