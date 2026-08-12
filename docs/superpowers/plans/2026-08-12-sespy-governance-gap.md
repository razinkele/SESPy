# Governance Gap Detection (issue #13, amended) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `governance_gap()` to `sespy/network.py` — a SENA governance-coverage diagnostic — and surface it as a second summary block on the Network Metrics card.

**Architecture:** A pure graph function beside `social_ecological_fit` computes **directed** governance→ecological coverage over the DAPSI(W)R(M) cascade, with a **Pressures-only headline denominator** and path-based orphan detection. A pure state helper picks one of four degenerate UI states; the Shiny renderer is a second `output_ui` block inside the existing metrics card. This implements the design **as amended by the 2026-08-12 five-agent review** (`docs/superpowers/plans/2026-08-12-sespy-governance-gap-review.json`) — NOT issue #13's original text, which specified undirected 1-hop coverage and a NaN sentinel, both overturned.

**Tech Stack:** Python (stdlib only in `network.py` — no networkx needed), Shiny for Python, pytest, Playwright e2e.

## Global Constraints

- Python env: `micromamba run -n shiny python …` — never create venvs, never bare `python` (no global Python on PATH).
- Unit suite: `micromamba run -n shiny python -m pytest tests -q` (475 tests green on main).
- e2e suite: `micromamba run -n shiny python tests/run_e2e.py` — ALWAYS the full suite, never `-k "not e2e"`. Before running, kill any orphaned server by port: `powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"`.
- Every i18n key must exist in ALL 9 languages (`en es fr de lt pt it no el`) — `tests/test_i18n.py::test_loader_handles_all_supported_languages` enforces this. Keys live in `sespy/translations/core.json`, ONE line per key.
- No NaN anywhere in return values — degenerate denominators return `0.0` (repo precedent: `social_ecological_fit`, `network.py:302`).
- Playwright selectors must be scoped to element ids (`#metrics-governance_gap_summary`), never bare `text=`.
- Commit style: conventional (`feat(metrics): …`, `test(e2e): …`, `docs(changelog): …`).
- Work on branch `feat/governance-gap` off `main`.

## Design decisions locked by the review (do not re-litigate)

1. Coverage is **directed**: an ecological node is covered iff some governance node has an out-edge to it. (Undirected 1-hop made the metric direction-blind and structurally degenerate.)
2. Headline `pressure_gap_fraction` uses **Pressures only** — the sole ecological layer `_CONN_TYPES` (`sespy/data_structure.py:66-77`) routes a Response into (`responses→pressures`). MPF and Ecosystem Services are unreachable at distance 1 *by topology*, so pooling them makes the demo model read "75 % gap"; they are reported per-type instead.
3. **Orphan** = governance node with **no directed path** to any ecological node. A Response reaching ecology only via R→Drivers→Activities→Pressures (the highest-leverage "intent" realm per `_DAPSIWRM_REALM`) is NOT an orphan.
4. `n_edges_considered` = count of **unique directed (source, target) pairs** after dropping self-loops and dangling refs. Edges touching untyped nodes DO count (they are structure) — this deliberately differs from `social_ecological_fit`'s `total_edges`.
5. Four degenerate UI states with **untyped-domination checked BEFORE no-governance** (a raw `.qsem` import satisfies both; "map themes first" is the actionable message).
6. `"Measures"` stays in `_GOVERNANCE` but is **currently unreachable** (rejected by `persistent_storage.py:25`, offered by no UI) — forward-looking, documented as such, not a "live divergence".
7. Signature is `governance_gap(isa: IsaData) -> dict` (annotated). Rationale: every graph-level public entry point takes `IsaData`; `to_digraph` is lossy (collapses parallel edges, materialises dangling refs); deterministic id ordering needs `isa.elements` order. (NOT "the digraph lacks type" — it carries it, `network.py:24`.)
8. Paper semantics (verified against the OA PDF, CC-BY, edepot.wur.nl/716549): Fraga et al. 2026 (doi:10.1016/j.marpol.2026.107169) formalise a one-mode square adjacency matrix kept in BOTH an undirected/unsigned version (modularity, participation roles) and a directed/signed version (centrality, out-degree focus), and identify governance gaps *interpretively* from module composition and weak institutional linkage — no formal distance-1 coverage test. Our directed coverage test is an explicit operationalisation of their concept, and the docstring says so.
9. Out of scope: surfacing `n_other` on the existing fit card (review's open check #2 — separate follow-up), widening Measures into a real 8th element type, issue #14 (`governance_actor_influence`).

**Golden values** (measured on `data/sample_ses.json`, replicated identically by the review's verification and by this plan's probe): Pressures 3 nodes / 1 uncovered = `P003` ("Nutrient enrichment") → `pressure_gap_fraction 0.333…`; MPF 2/2 uncovered, ES 3/3 uncovered (by topology); 0 orphans; `n_ecological 8`, `n_governance 2`, `n_unclassified 0`, `n_edges_considered 20`. Do NOT pin the pooled 0.75 as a headline anywhere — it characterises the rejected design.

---

### Task 0: Branch + preserve the review record

**Files:**
- Create: `docs/superpowers/plans/2026-08-12-sespy-governance-gap-review.json` (already copied into the working tree from the workflow task output — just commit it)
- Create: `docs/superpowers/plans/2026-08-12-sespy-governance-gap.md` (this file)

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feat/governance-gap
```

- [ ] **Step 2: Commit the plan and the review synthesis**

```bash
git add docs/superpowers/plans/2026-08-12-sespy-governance-gap.md docs/superpowers/plans/2026-08-12-sespy-governance-gap-review.json
git commit -m "docs(plans): governance-gap plan + five-agent design-review record (#13)"
```

---

### Task 1: `governance_gap()` in `sespy/network.py`

**Files:**
- Modify: `sespy/network.py` (insert after `social_ecological_fit`, i.e. after line 303)
- Test: `tests/test_network.py` (append at end; the file already imports `network`, `IsaData`, `Element`, `Connection`, `load_sample`, `Path` — check its header and reuse, do not re-import)

**Interfaces:**
- Consumes: `subsystem(element_type) -> str` (`network.py:252`), `IsaData` dataclass.
- Produces: `governance_gap(isa: IsaData) -> dict` with keys `gaps_by_type` (`{eco_type: {"n": int, "uncovered": [id, …]}}`, ids in `isa.elements` order), `pressure_gap_fraction: float`, `ecological_gap_fraction: float`, `governance_orphans: [id, …]`, `n_ecological: int`, `n_governance: int`, `n_unclassified: int`, `n_edges_considered: int`. Also module-level `_GOVERNANCE: frozenset[str]` (kept private — issue #14 lands in the same module and can use it directly, per the `_axis_sums` precedent).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_network.py`:

```python
# ---------------------------------------------------------------------------
# governance_gap (issue #13, amended per the 2026-08-12 design review)
# ---------------------------------------------------------------------------


def _gg(elements, connections=()):
    return network.governance_gap(
        IsaData(elements=list(elements), connections=list(connections)))


def test_governance_gap_sample_golden():
    root = Path(__file__).resolve().parents[1]
    r = network.governance_gap(load_sample(root / "data" / "sample_ses.json"))
    assert r["gaps_by_type"]["Pressures"] == {"n": 3, "uncovered": ["P003"]}
    assert round(r["pressure_gap_fraction"], 3) == 0.333
    assert r["governance_orphans"] == []
    assert r["n_ecological"] == 8 and r["n_governance"] == 2
    assert r["n_unclassified"] == 0
    assert r["n_edges_considered"] == 20


def test_governance_gap_coverage_is_directed():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="P1", label="p", type="Pressures")]
    # An ecological -> governance edge alone does NOT cover the pressure...
    r = _gg(els, [Connection(source="P1", target="R1")])
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == ["P1"]
    assert r["pressure_gap_fraction"] == 1.0
    # ...adding the antiparallel governance -> ecological edge does, and the
    # pair stays two distinct directed edges (no undirected collapse).
    r = _gg(els, [Connection(source="P1", target="R1"),
                  Connection(source="R1", target="P1")])
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == []
    assert r["pressure_gap_fraction"] == 0.0
    assert r["n_edges_considered"] == 2


def test_governance_gap_intent_chain_is_not_orphan():
    # R -> Drivers -> Activities -> Pressures reaches ecology only through
    # the "intent" realm; the Response must NOT be an orphan (consistency
    # with leverage_realm), while P1 stays uncovered (no DIRECT edge).
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers"),
           Element(id="A1", label="a", type="Activities"),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R1", target="D1"),
             Connection(source="D1", target="A1"),
             Connection(source="A1", target="P1")]
    r = _gg(els, conns)
    assert r["governance_orphans"] == []
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == ["P1"]


def test_governance_gap_dead_end_response_is_orphan():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers"),
           Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="R1", target="D1")])
    assert r["governance_orphans"] == ["R1"]


def test_governance_gap_no_governance_shape():
    els = [Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="P1", target="P1")])  # self-loop only
    assert r["n_governance"] == 0
    assert r["n_edges_considered"] == 0
    assert r["pressure_gap_fraction"] == 1.0  # UI guards on n_governance
    assert r["governance_orphans"] == []


def test_governance_gap_no_ecological_still_reports_orphans():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers")]
    r = _gg(els, [Connection(source="R1", target="D1")])
    assert r["n_ecological"] == 0
    assert r["ecological_gap_fraction"] == 0.0  # never NaN
    assert r["pressure_gap_fraction"] == 0.0
    assert r["governance_orphans"] == ["R1"]


def test_governance_gap_empty_graph():
    r = network.governance_gap(IsaData())
    assert r == {
        "gaps_by_type": {},
        "pressure_gap_fraction": 0.0,
        "ecological_gap_fraction": 0.0,
        "governance_orphans": [],
        "n_ecological": 0,
        "n_governance": 0,
        "n_unclassified": 0,
        "n_edges_considered": 0,
    }


def test_governance_gap_edges_considered_definition():
    # n_edges_considered = unique directed (source, target) pairs after
    # dropping self-loops and dangling refs. Edges touching an UNTYPED node
    # still count (they are structure) — deliberately unlike
    # social_ecological_fit's total_edges, which classifies them away.
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="U1", label="u", type=""),
           Element(id="P1", label="p", type="Pressures")]
    conns = [Connection(source="R1", target="U1"),   # touches untyped: counts
             Connection(source="R1", target="U1"),   # duplicate: deduplicated
             Connection(source="U1", target="U1"),   # self-loop: skipped
             Connection(source="R1", target="X9"),   # dangling: skipped
             Connection(source="R1", target="P1")]   # counts
    r = _gg(els, conns)
    assert r["n_edges_considered"] == 2
    assert r["n_unclassified"] == 1


def test_governance_gap_measures_is_governance_forward_compat():
    # "Measures" is unreachable through every production ingress today
    # (persistent_storage.py:25 rejects it; no UI offers it). Synthetic-
    # IsaData precedent: test_fit_excludes_measures_self_loop_and_dangling.
    # Forward-compat: when the vocabulary widens, Measures must count as
    # governance, never as unclassified.
    els = [Element(id="M1", label="m", type="Measures"),
           Element(id="P1", label="p", type="Pressures")]
    r = _gg(els, [Connection(source="M1", target="P1")])
    assert r["n_governance"] == 1
    assert r["n_unclassified"] == 0
    assert r["gaps_by_type"]["Pressures"]["uncovered"] == []
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k governance_gap`
Expected: 9 failures/errors, `AttributeError: module 'sespy.network' has no attribute 'governance_gap'`.

- [ ] **Step 3: Implement** — insert into `sespy/network.py` directly after `social_ecological_fit` (after line 303):

```python
_GOVERNANCE: frozenset[str] = frozenset({"Responses", "Measures"})


def governance_gap(isa: IsaData) -> dict:
    """SENA governance-gap diagnostic — directed coverage of the ecological
    subsystem by governance elements.

    Coverage is DIRECTED: an ecological node counts as covered when at least
    one governance node has an out-edge to it. The headline
    ``pressure_gap_fraction`` uses Pressures alone as denominator — the only
    ecological layer the DAPSI(W)R(M) topology (``_CONN_TYPES``) routes a
    Response into; Marine Processes & Functioning and Ecosystem Services are
    unreachable at distance 1 by construction, so their coverage is reported
    per-type in ``gaps_by_type`` rather than pooled into the headline. A
    governance *orphan* is a governance node with no directed PATH to any
    ecological node, so a Response acting through Drivers/Activities (the
    highest-leverage "intent" realm per ``leverage_realm``) is not an orphan.

    Degenerate denominators return 0.0, never NaN; callers discriminate via
    the ``n_*`` counts (same contract as ``social_ecological_fit`` and
    ``total_edges``). ``n_edges_considered`` counts unique directed
    (source, target) pairs after dropping self-loops and dangling refs —
    edges touching untyped nodes included. "Measures" in the governance set
    is forward-looking: ``persistent_storage`` rejects it and no UI offers
    it today. Duplicate element ids (possible only via the validation-free
    ``load_sample``) can overcount — parity with ``social_ecological_fit``.

    Concept: Fraga et al. 2026, Marine Policy 191:107169
    (doi:10.1016/j.marpol.2026.107169) diagnose MPA governance gaps
    interpretively from modularity, participation roles and out-degree
    centrality on a one-mode network held in both undirected and directed
    forms; this function operationalises that concept as an explicit
    directed coverage test over the DAPSI(W)R(M) cascade. Pure.
    """
    ids = {el.id for el in isa.elements}
    out: dict[str, set[str]] = {el.id: set() for el in isa.elements}
    pairs: set[tuple[str, str]] = set()
    for c in isa.connections:
        if c.source == c.target or c.source not in ids or c.target not in ids:
            continue
        pairs.add((c.source, c.target))
        out[c.source].add(c.target)

    governance = [el for el in isa.elements if el.type in _GOVERNANCE]
    ecological = [el for el in isa.elements if subsystem(el.type) == "ecological"]
    n_unclassified = sum(
        1 for el in isa.elements
        if subsystem(el.type) == "" and el.type not in _GOVERNANCE
    )

    covered: set[str] = set()
    for g in governance:
        covered |= out[g.id]

    gaps_by_type: dict[str, dict] = {}
    for el in ecological:
        entry = gaps_by_type.setdefault(el.type, {"n": 0, "uncovered": []})
        entry["n"] += 1
        if el.id not in covered:
            entry["uncovered"].append(el.id)

    eco_ids = {el.id for el in ecological}
    orphans: list[str] = []
    for g in governance:
        seen: set[str] = set()
        stack = [g.id]
        found = False
        while stack and not found:
            for nxt in out[stack.pop()]:
                if nxt in eco_ids:
                    found = True
                    break
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if not found:
            orphans.append(g.id)

    press = gaps_by_type.get("Pressures", {"n": 0, "uncovered": []})
    n_eco = len(ecological)
    n_uncovered = sum(len(v["uncovered"]) for v in gaps_by_type.values())
    return {
        "gaps_by_type": gaps_by_type,
        "pressure_gap_fraction":
            (len(press["uncovered"]) / press["n"]) if press["n"] else 0.0,
        "ecological_gap_fraction": (n_uncovered / n_eco) if n_eco else 0.0,
        "governance_orphans": orphans,
        "n_ecological": n_eco,
        "n_governance": len(governance),
        "n_unclassified": n_unclassified,
        "n_edges_considered": len(pairs),
    }
```

- [ ] **Step 4: Run the new tests to verify they pass, then the whole unit suite**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -q -k governance_gap` → 9 passed.
Run: `micromamba run -n shiny python -m pytest tests -q` → all green (475 + 9).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): governance_gap() - directed SENA coverage with Pressures headline (#13)"
```

---

### Task 2: i18n keys (7 keys × 9 languages) + presence test

**Files:**
- Modify: `sespy/translations/core.json` — insert the 7 lines below immediately after the `"metrics.fit_none"` line (~line 5407), keeping the file's one-line-per-key style and trailing commas consistent with neighbours.
- Test: `tests/test_i18n.py` — append after `test_metrics_fit_keys_present` (line 93).

**Interfaces:**
- Produces: translation keys `metrics.gov_gap`, `metrics.gov_gap_caption` (params `{uncovered}`, `{n}`), `metrics.gov_gap_orphans` (params `{n}`, `{ids}`), `metrics.gov_gap_none`, `metrics.gov_gap_untyped`, `metrics.gov_gap_no_gov`, `metrics.gov_gap_no_eco`. Task 3's renderer uses exactly these names.

- [ ] **Step 1: Write the failing test** — append to `tests/test_i18n.py`:

```python
def test_governance_gap_keys_present(translations):
    for key in (
        "metrics.gov_gap", "metrics.gov_gap_caption", "metrics.gov_gap_orphans",
        "metrics.gov_gap_none", "metrics.gov_gap_untyped",
        "metrics.gov_gap_no_gov", "metrics.gov_gap_no_eco",
    ):
        assert key in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q -k governance_gap`
Expected: FAIL (`assert 'metrics.gov_gap' in translations`).

- [ ] **Step 3: Add the keys** — insert into `sespy/translations/core.json` after the `metrics.fit_none` line (all 9 languages per key; the drift test fails otherwise):

```json
    "metrics.gov_gap": {"en": "Governance gap", "es": "Brecha de gobernanza", "fr": "Lacune de gouvernance", "de": "Governance-Lücke", "lt": "Valdysenos spraga", "pt": "Lacuna de governança", "it": "Lacuna di governance", "no": "Styringsgap", "el": "Κενό διακυβέρνησης"},
    "metrics.gov_gap_caption": {"en": "{uncovered} of {n} pressure nodes lack a direct governance response", "es": "{uncovered} de {n} nodos de presión carecen de una respuesta de gobernanza directa", "fr": "{uncovered} nœuds de pression sur {n} sans réponse de gouvernance directe", "de": "{uncovered} von {n} Belastungsknoten ohne direkte Governance-Antwort", "lt": "{uncovered} iš {n} spaudimo mazgų be tiesioginio valdysenos atsako", "pt": "{uncovered} de {n} nós de pressão sem resposta direta de governança", "it": "{uncovered} di {n} nodi di pressione senza risposta diretta di governance", "no": "{uncovered} av {n} pressnoder mangler direkte styringsrespons", "el": "{uncovered} από {n} κόμβους πίεσης χωρίς άμεση απόκριση διακυβέρνησης"},
    "metrics.gov_gap_orphans": {"en": "{n} governance element(s) with no path to the ecological subsystem: {ids}", "es": "{n} elemento(s) de gobernanza sin ruta al subsistema ecológico: {ids}", "fr": "{n} élément(s) de gouvernance sans chemin vers le sous-système écologique : {ids}", "de": "{n} Governance-Element(e) ohne Pfad zum ökologischen Subsystem: {ids}", "lt": "{n} valdysenos elementas(-ai) be kelio į ekologinę posistemę: {ids}", "pt": "{n} elemento(s) de governança sem caminho para o subsistema ecológico: {ids}", "it": "{n} elemento/i di governance senza percorso verso il sottosistema ecologico: {ids}", "no": "{n} styringselement(er) uten sti til det økologiske delsystemet: {ids}", "el": "{n} στοιχείο(-α) διακυβέρνησης χωρίς διαδρομή προς το οικολογικό υποσύστημα: {ids}"},
    "metrics.gov_gap_none": {"en": "not enough structure to assess governance coverage", "es": "estructura insuficiente para evaluar la cobertura de gobernanza", "fr": "structure insuffisante pour évaluer la couverture de gouvernance", "de": "nicht genügend Struktur, um die Governance-Abdeckung zu bewerten", "lt": "nepakanka struktūros valdysenos aprėpčiai įvertinti", "pt": "estrutura insuficiente para avaliar a cobertura de governança", "it": "struttura insufficiente per valutare la copertura di governance", "no": "ikke nok struktur til å vurdere styringsdekningen", "el": "ανεπαρκής δομή για την αξιολόγηση της κάλυψης διακυβέρνησης"},
    "metrics.gov_gap_untyped": {"en": "model is largely untyped — map themes to DAPSI(W)R(M) first", "es": "el modelo carece mayormente de tipos: asigne primero los temas a DAPSI(W)R(M)", "fr": "le modèle est largement non typé — associez d'abord les thèmes à DAPSI(W)R(M)", "de": "Modell ist größtenteils untypisiert — ordnen Sie zuerst die Themen DAPSI(W)R(M) zu", "lt": "modelis daugiausia be tipų — pirmiausia priskirkite temas DAPSI(W)R(M)", "pt": "o modelo está em grande parte sem tipos — mapeie primeiro os temas para DAPSI(W)R(M)", "it": "il modello è in gran parte senza tipi — mappare prima i temi su DAPSI(W)R(M)", "no": "modellen er stort sett utypet — koble temaene til DAPSI(W)R(M) først", "el": "το μοντέλο είναι σε μεγάλο βαθμό χωρίς τύπους — αντιστοιχίστε πρώτα τα θέματα στο DAPSI(W)R(M)"},
    "metrics.gov_gap_no_gov": {"en": "no governance elements to assess against", "es": "no hay elementos de gobernanza contra los que evaluar", "fr": "aucun élément de gouvernance pour l'évaluation", "de": "keine Governance-Elemente für die Bewertung vorhanden", "lt": "nėra valdysenos elementų, pagal kuriuos vertinti", "pt": "não há elementos de governança para avaliar", "it": "nessun elemento di governance rispetto a cui valutare", "no": "ingen styringselementer å vurdere mot", "el": "δεν υπάρχουν στοιχεία διακυβέρνησης για αξιολόγηση"},
    "metrics.gov_gap_no_eco": {"en": "no ecological elements — showing governance orphans only", "es": "no hay elementos ecológicos: solo se muestran los huérfanos de gobernanza", "fr": "aucun élément écologique — seuls les orphelins de gouvernance sont affichés", "de": "keine ökologischen Elemente — nur Governance-Waisen werden angezeigt", "lt": "nėra ekologinių elementų — rodomi tik valdysenos našlaičiai", "pt": "não há elementos ecológicos — mostrando apenas órfãos de governança", "it": "nessun elemento ecologico — vengono mostrati solo gli orfani di governance", "no": "ingen økologiske elementer — viser kun styringsforeldreløse", "el": "δεν υπάρχουν οικολογικά στοιχεία — εμφανίζονται μόνο τα ορφανά διακυβέρνησης"},
```

- [ ] **Step 4: Run the i18n suite to verify it passes (drift test included)**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q` → all pass, including `test_loader_handles_all_supported_languages`.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(metrics): 7 governance-gap keys in all nine languages (#13)"
```

---

### Task 3: UI block on the Network Metrics card

**Files:**
- Modify: `sespy/modules/analysis_metrics.py` — (a) module-level pure helper `governance_gap_state`; (b) one line in `analysis_metrics_ui` (line 130-131 area); (c) renderer in `analysis_metrics_server` after `fit_summary` (line 221).
- Test: Create `tests/test_governance_gap_ui.py` (pure-helper unit tests — the renderer itself is covered by Task 4's e2e).

**Interfaces:**
- Consumes: `governance_gap(isa)` from Task 1 (via the module's existing `net_analysis` import); i18n keys from Task 2.
- Produces: `governance_gap_state(r: dict, n_elements: int) -> str` returning `"none" | "untyped" | "no_gov" | "no_eco" | ""` (empty string = render fully); DOM node `#metrics-governance_gap_summary` (Task 4's e2e selector).

- [ ] **Step 1: Write the failing tests** — create `tests/test_governance_gap_ui.py`:

```python
"""Unit tests for the governance-gap UI state helper (branch precedence).

The four degenerate states and their ORDER were fixed by the 2026-08-12
design review: untyped-domination must outrank no-governance because a raw
.qsem import (all elements untyped) satisfies both, and "map themes first"
is the actionable message there.
"""
from pathlib import Path

from sespy import network
from sespy.data_structure import Connection, Element, IsaData, load_sample
from sespy.modules.analysis_metrics import governance_gap_state


def _state(isa):
    return governance_gap_state(network.governance_gap(isa), len(isa.elements))


def test_state_zero_edges():
    isa = IsaData(elements=[Element(id="P1", label="p", type="Pressures")])
    assert _state(isa) == "none"


def test_state_untyped_outranks_no_gov():
    els = [Element(id=f"U{i}", label="u", type="") for i in range(3)]
    els.append(Element(id="P1", label="p", type="Pressures"))
    isa = IsaData(elements=els,
                  connections=[Connection(source="U0", target="U1")])
    assert _state(isa) == "untyped"


def test_state_no_gov():
    els = [Element(id="P1", label="p", type="Pressures"),
           Element(id="D1", label="d", type="Drivers")]
    isa = IsaData(elements=els,
                  connections=[Connection(source="D1", target="P1")])
    assert _state(isa) == "no_gov"


def test_state_no_eco():
    els = [Element(id="R1", label="r", type="Responses"),
           Element(id="D1", label="d", type="Drivers")]
    isa = IsaData(elements=els,
                  connections=[Connection(source="R1", target="D1")])
    assert _state(isa) == "no_eco"


def test_state_ok_on_sample():
    root = Path(__file__).resolve().parents[1]
    assert _state(load_sample(root / "data" / "sample_ses.json")) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_governance_gap_ui.py -q`
Expected: `ImportError: cannot import name 'governance_gap_state'`.

- [ ] **Step 3: Implement.** Three edits to `sespy/modules/analysis_metrics.py`:

(a) Module-level helper, placed after `_scaled_size` (line 56):

```python
def governance_gap_state(r: dict, n_elements: int) -> str:
    """Which degenerate UI state applies to a governance_gap() result —
    '' means render the full block. Order matters: untyped-domination
    outranks no-governance because "map your themes first" is the
    actionable message when both hold (e.g. a raw .qsem import where
    every element is untyped). Pure."""
    if r["n_edges_considered"] == 0:
        return "none"
    if n_elements and r["n_unclassified"] / n_elements > 0.5:
        return "untyped"
    if r["n_governance"] == 0:
        return "no_gov"
    if r["n_ecological"] == 0:
        return "no_eco"
    return ""
```

(b) In `analysis_metrics_ui`, insert one output slot + rule directly after the fit block (current lines 130-131), keeping fit first:

```python
                ui.output_ui("fit_summary"),
                ui.tags.hr(),
                ui.output_ui("governance_gap_summary"),
                ui.tags.hr(),
```

(c) In `analysis_metrics_server`, add the renderer directly after the `fit_summary` renderer (after line 221), mirroring its `event_bus.isa_change.get()` subscription and `:.2f` ratio format (NOT a percentage — the fit card renders `0.40`-style ratios and a `%` next to it would misread):

```python
    @output
    @render.ui
    def governance_gap_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        r = net_analysis.governance_gap(isa)
        state = governance_gap_state(r, len(isa.elements))
        if state in ("none", "untyped", "no_gov"):
            key = {"none": "metrics.gov_gap_none",
                   "untyped": "metrics.gov_gap_untyped",
                   "no_gov": "metrics.gov_gap_no_gov"}[state]
            return ui.p(t(key), class_="text-muted")
        orphan_line = None
        if r["governance_orphans"]:
            labels = {el.id: el.label for el in isa.elements}
            shown = ", ".join(f"{i} · {labels.get(i, i)}"
                              for i in r["governance_orphans"][:5])
            orphan_line = ui.p(
                t("metrics.gov_gap_orphans",
                  n=len(r["governance_orphans"]), ids=shown),
                class_="text-muted", style="font-size: 0.85rem;")
        if state == "no_eco":
            return ui.div(
                ui.h5(t("metrics.gov_gap")),
                ui.p(t("metrics.gov_gap_no_eco"), class_="text-muted"),
                orphan_line,
            )
        press = r["gaps_by_type"].get("Pressures", {"n": 0, "uncovered": []})
        return ui.div(
            ui.h5(t("metrics.gov_gap")),
            ui.tags.strong(f"{r['pressure_gap_fraction']:.2f}"),
            ui.p(t("metrics.gov_gap_caption",
                   uncovered=len(press["uncovered"]), n=press["n"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
            orphan_line,
        )
```

Notes for the implementer: `id · label` is the repo's element-rendering convention (`isa_data_entry.py:167-168`) — labels alone are NOT unique (three shipped `.qsem` files each contain five elements labelled "Number of jobs for locals"). This is a second `output_ui` block inside the existing card, NOT a second `ui.card` — `analysis_metrics_ui` returns exactly one card.

- [ ] **Step 4: Run the new tests, then the full unit suite**

Run: `micromamba run -n shiny python -m pytest tests/test_governance_gap_ui.py -q` → 5 passed.
Run: `micromamba run -n shiny python -m pytest tests -q` → all green.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/analysis_metrics.py tests/test_governance_gap_ui.py
git commit -m "feat(metrics): governance-gap summary block with four degenerate states (#13)"
```

---

### Task 4: e2e coverage + full-suite verification

**Files:**
- Modify: `tests/test_metrics_e2e.py` — append a scoped assertion block after the fit-summary block (after line 95, before `await browser.close()`).

**Interfaces:**
- Consumes: DOM node `#metrics-governance_gap_summary` (Task 3), English strings "Governance gap" / caption "1 of 3 pressure nodes …" (Task 2), golden `0.33` (Task 1).

- [ ] **Step 1: Add the e2e block** — insert into `tests/test_metrics_e2e.py` after the fit assertions (line 95):

```python
        # --- Governance gap summary renders with the golden values ---
        # Sample: directed coverage leaves 1 of 3 Pressures (P003) uncovered
        # -> 0.33; no orphans, so no orphan line. Selector is scoped to the
        # output id — bare text= selectors have shipped broken e2e before.
        gg_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            gg_text = (await page.inner_text("#metrics-governance_gap_summary")).strip()
            if gg_text:
                break
        assert "Governance gap" in gg_text, f"expected heading, got: {gg_text!r}"
        assert "0.33" in gg_text, f"expected 0.33, got: {gg_text!r}"
        assert "1 of 3" in gg_text, f"expected '1 of 3' caption, got: {gg_text!r}"
        print(f"governance gap summary: OK ({gg_text!r})")
```

- [ ] **Step 2: Kill any orphaned server, then run the FULL e2e suite**

Run first: `powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"`
Then: `micromamba run -n shiny python tests/run_e2e.py`
Expected: all scripts pass (33/33 including this extension). A red PDF-export/report script is a REAL regression (WeasyPrint false-red was resolved 2026-08-11), not noise.

- [ ] **Step 3: Run the full unit suite one final time**

Run: `micromamba run -n shiny python -m pytest tests -q` → all green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_metrics_e2e.py
git commit -m "test(e2e): assert governance-gap block renders the 0.33 golden (#13)"
```

---

### Task 5: Changelog, merge, close issue #13

**Files:**
- Modify: `CHANGELOG.md` (top of `## [Unreleased]`)

- [ ] **Step 1: Add the changelog entry** — first bullet under `## [Unreleased]`:

```markdown
- New "Governance gap" block on the Network Metrics card (#13): directed
  coverage of pressure nodes by governance elements (headline fraction),
  per-layer gap listing, and detection of governance elements with no path
  into the ecological subsystem. Operationalises the SENA governance-gap
  concept of Fraga et al. 2026 (Marine Policy, doi:10.1016/j.marpol.2026.107169).
```

- [ ] **Step 2: Commit, merge to main, push**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): governance-gap block under Unreleased (#13)"
git checkout main
git merge --no-ff feat/governance-gap -m "feat: governance gap detection (#13)"
git push
```

- [ ] **Step 3: Close issue #13 with a deviations comment** (the shipped design deliberately diverges from the issue's acceptance criteria; without this comment the close looks wrong):

```bash
gh issue close 13 --comment "Shipped in $(git rev-parse --short HEAD) with four deliberate deviations from the original acceptance criteria, per the five-agent design review recorded in docs/superpowers/plans/2026-08-12-sespy-governance-gap-review.json:

1. Coverage is DIRECTED (governance→ecological out-edges), not undirected — the DAPSI(W)R(M) topology makes undirected 1-hop direction-blind and inconsistent with leverage_realm.
2. The headline fraction is pressure_gap_fraction over Pressures only (renamed from gap_fraction). _CONN_TYPES routes Responses only into Pressures/Drivers/Activities, so an all-ecological denominator marks every MPF and Ecosystem Services node as a gap by construction (the healthy demo model scored 0.75). Per-layer coverage is still reported in gaps_by_type.
3. Degenerate denominators return 0.0, never NaN — NaN breaks JSON export, dict-equality tests, and the module's existing conventions (social_ecological_fit returns 0.0). Callers discriminate via the n_* counts.
4. governance_orphans uses directed reachability to the ecological subsystem, not 1-hop, so a Response acting through Drivers/Activities is not a false orphan.

Verified against the paper (OA PDF): Fraga et al. identify gaps interpretively from modularity/roles/out-degree on a one-mode network kept in both directed and undirected forms; the directed coverage test here is an explicit operationalisation of that concept."
```

---

## Self-review notes

- Spec coverage: all 9 review amendments have a task (1→Task 1 defs, 2→Task 1 orphan tests, 3→Task 1 return shape, 4→Task 1 no-NaN tests, 5→Tasks 2+3 four states, 6→Task 3 second-output_ui + `id · label` + `:.2f`, 7→Task 1 docstring, 8→Tasks 1/3/4 tests incl. golden 0.333/orphan/antiparallel/i18n presence/scoped e2e, 9→`_GOVERNANCE` stays private). Both review "open checks" resolved: paper semantics verified (locked decision 8); fit-card `n_other` explicitly out of scope (locked decision 9).
- Type consistency: `governance_gap(isa: IsaData) -> dict` and `governance_gap_state(r, n_elements) -> str` used identically across Tasks 1, 3, 4.
- Golden values in Tasks 1 and 4 were computed against the real repo on 2026-08-12, not copied from the review.
