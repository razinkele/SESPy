# QSEM DAPSIWRM Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user optionally assign DAPSIWRM types to imported QSEM nodes via an editable, heuristic-pre-filled per-theme mapping table, so imported models render as a coloured/levelled CLD.

**Architecture:** Pure data-layer functions in `qsem_import.py` (theme→type mapping, theme discovery, heuristic, project builder) drive an opt-in UI in the `import_data.py` Shiny module (static checkbox → `render.ui` mapping table → guarded commit re-map). All UI-glue that can be pure is extracted so it is unit-testable; the reactive wiring is covered by e2e.

**Tech Stack:** Python 3.13, `shiny` (Shiny for Python, `@module`), pytest, Playwright (standalone async e2e scripts), micromamba env `shiny`.

## Global Constraints

- Run everything in the micromamba env: prefix commands with `micromamba run -n shiny`.
- Do NOT create venvs. Do NOT `pip install`.
- `DAPSIWRM_ELEMENTS` (from `sespy/constants.py`) = `('Drivers', 'Activities', 'Pressures', 'Marine Processes & Functioning', 'Ecosystem Services', 'Goods & Benefits', 'Responses')`.
- `qsem_to_isa` and `qsem_themes` MUST use identical node guards (`isinstance(n, dict) and not n.get("isGhost")`) and theme normalization (`node.get("theme") or ""`).
- Backwards compatibility: `qsem_to_isa(data)` and `parse_qsem(path)` behaviour with no map must be byte-identical to today.
- i18n: every user-facing string added as a key in `sespy/translations/core.json` across all 9 languages (`en es fr de lt pt it no el`).
- Commit after each task. Keep the tree ruff-clean (`micromamba run -n shiny ruff check <files>`).

---

## File Structure

- `sespy/qsem_import.py` — MODIFY. Add `theme_map` param to `qsem_to_isa`; new `build_project`, `qsem_themes`, `suggest_dapsiwrm_map`, `resolve_theme_map`. Refactor `parse_qsem` to call `build_project`.
- `sespy/modules/import_data.py` — MODIFY. Static `assign_dapsiwrm` checkbox; `dapsiwrm_map` `render.ui`; `raw_qsem`/`themes`/`seq` reactives; commit re-map + reset.
- `sespy/translations/core.json` — MODIFY. New i18n keys ×9.
- `tests/test_qsem_dapsiwrm_map.py` — CREATE. Unit tests for the data layer + glue.
- `tests/test_qsem_map_e2e.py` — CREATE. e2e: map applies → CLD coloured.
- `tests/test_import_e2e.py` — MODIFY. Add an Excel-commit regression assertion.
- `CHANGELOG.md` — MODIFY. `[Unreleased]` entry.

---

### Task 1: Data — `theme_map` on `qsem_to_isa` + `build_project`

**Files:**
- Modify: `sespy/qsem_import.py`
- Test: `tests/test_qsem_dapsiwrm_map.py`

**Interfaces:**
- Produces: `qsem_to_isa(data: dict, theme_map: dict[str,str] | None = None) -> tuple[list[Element], list[Connection]]`; `build_project(data: dict, name: str, theme_map: dict[str,str] | None = None) -> ValidationResult`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qsem_dapsiwrm_map.py`:

```python
"""Unit tests for optional DAPSIWRM assignment on QSEM import."""
from pathlib import Path

from sespy.qsem_import import build_project, qsem_to_isa


def _canvas(nodes, links=None):
    return {"canvas": {"nodes": nodes, "links": links or []}}


def test_theme_map_none_is_unchanged():
    data = _canvas([{"id": "a", "label": "A", "theme": "Ecosystem Services"},
                    {"id": "b", "label": "B", "theme": "OWFs"}])
    els, _ = qsem_to_isa(data)  # no map
    by_label = {e.label: e for e in els}
    assert by_label["A"].type == "Ecosystem Services"   # exact DAPSIWRM match
    assert by_label["B"].type == ""                     # non-DAPSIWRM -> untyped
    assert by_label["B"].description == "Theme: OWFs"    # annotation retained


def test_theme_map_applies_and_description_keys_off_resolved_type():
    data = _canvas([{"id": "b", "label": "B", "theme": "OWFs"}])
    els, _ = qsem_to_isa(data, {"OWFs": "Activities"})
    assert els[0].type == "Activities"
    assert els[0].description == ""     # typed via map -> NO "Theme: OWFs"


def test_theme_map_untyped_value_and_coercion():
    data = _canvas([{"id": "b", "label": "B", "theme": "OWFs"},
                    {"id": "c", "label": "C", "theme": "LWB"}])
    els, _ = qsem_to_isa(data, {"OWFs": "", "LWB": "NotAType"})
    by_label = {e.label: e for e in els}
    assert by_label["B"].type == ""                    # "" -> untyped
    assert by_label["B"].description == "Theme: OWFs"   # untyped -> annotated
    assert by_label["C"].type == ""                    # bogus value coerced to ""


def test_build_project_names_and_validates():
    data = _canvas([{"id": "a", "label": "A", "theme": "OWFs"}])
    res = build_project(data, "MyModel", {"OWFs": "Activities"})
    assert res.valid and res.project is not None
    assert res.project.metadata.name == "MyModel"
    assert res.project.isa_data.elements[0].type == "Activities"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -q`
Expected: FAIL — `build_project` not importable / `qsem_to_isa` takes no `theme_map`.

- [ ] **Step 3: Implement in `sespy/qsem_import.py`**

Replace the `qsem_to_isa` node-typing loop so type/description derive from a resolved type, and add a `theme_map` param. Find the current element loop:

```python
    for i, node in enumerate(canonical, start=1):
        new_id = f"N{i:03d}"
        qid = node.get("id")
        if qid is not None:
            id_map[qid] = new_id
        theme = node.get("theme") or ""
        mapped = theme in DAPSIWRM_ELEMENTS
        elements.append(Element(
            id=new_id,
            label=str(node.get("label", "")),
            type=theme if mapped else "",
            description="" if (mapped or not theme) else f"Theme: {theme}",
            confidence=3,
        ))
```

Replace the loop body's typing with a resolved-type helper. Change the signature and loop to:

```python
def _resolve_type(theme: str, theme_map: dict[str, str] | None) -> str:
    """The final DAPSIWRM type for a node's theme. Membership-coerced (not
    truthiness) so None/stale/non-DAPSIWRM values become untyped."""
    if theme_map is None:
        return theme if theme in DAPSIWRM_ELEMENTS else ""
    rt = theme_map.get(theme, "")
    return rt if rt in DAPSIWRM_ELEMENTS else ""


def qsem_to_isa(
    data: dict, theme_map: dict[str, str] | None = None
) -> tuple[list[Element], list[Connection]]:
    # ... unchanged canvas/nodes/links/canonical/ghost setup ...
    for i, node in enumerate(canonical, start=1):
        new_id = f"N{i:03d}"
        qid = node.get("id")
        if qid is not None:
            id_map[qid] = new_id
        theme = node.get("theme") or ""
        rt = _resolve_type(theme, theme_map)
        elements.append(Element(
            id=new_id,
            label=str(node.get("label", "")),
            type=rt,
            description="" if (rt or not theme) else f"Theme: {theme}",
            confidence=3,
        ))
```

Keep the connections loop and the rest of `qsem_to_isa` unchanged. Then factor the payload build out of `parse_qsem` into `build_project`, and make `parse_qsem` call it:

```python
def build_project(
    data: dict, name: str, theme_map: dict[str, str] | None = None
) -> ValidationResult:
    """Map a QSEM dict -> validated Project named `name`. Shared by parse_qsem
    (theme_map=None) and the import module's DAPSIWRM re-map path, so both
    validate and name identically."""
    elements, connections = qsem_to_isa(data, theme_map)
    payload = {
        "metadata": {"name": name, "description": f"Imported from {name}"},
        "isa_data": {
            "elements": [e.__dict__ for e in elements],
            "connections": [c.__dict__ for c in connections],
        },
    }
    return validate_project_payload(payload)


def parse_qsem(path: Path | str) -> ValidationResult:
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return ValidationResult(False, [f"Not a valid QSEM/JSON file: {e}"])

    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    if not isinstance(canvas.get("nodes"), list):
        return ValidationResult(False, ["Not a QSEM file (missing canvas.nodes)"])
    if not canvas.get("nodes"):
        return ValidationResult(False, ["QSEM file has no nodes"])

    return build_project(data, path.stem)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Regression — existing QSEM tests still pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_models_load.py -q`
Expected: PASS (8 tests) — proves `theme_map=None` path unchanged.

- [ ] **Step 6: Commit**

```bash
git add sespy/qsem_import.py tests/test_qsem_dapsiwrm_map.py
git commit -m "feat(qsem): theme_map param on qsem_to_isa + build_project helper"
```

---

### Task 2: Data — `qsem_themes` with consistency invariant

**Files:**
- Modify: `sespy/qsem_import.py`
- Test: `tests/test_qsem_dapsiwrm_map.py`

**Interfaces:**
- Produces: `qsem_themes(data: dict) -> list[tuple[str, int]]` — canonical (non-ghost) themes with counts, sorted by count desc then theme asc; empty theme as `""`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_qsem_dapsiwrm_map.py`)

```python
import json

import pytest

from sespy.qsem_import import qsem_themes

_MODELS_DIR = Path(
    r"C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\NiD4OCEAN"
    r"\DST\social ecological system map\Social ecological systems map"
)


def test_qsem_themes_counts_and_untyped_and_ghosts():
    data = _canvas([
        {"id": "a", "label": "A", "theme": "OWFs"},
        {"id": "b", "label": "B", "theme": "OWFs"},
        {"id": "c", "label": "C"},                       # missing theme -> ""
        {"id": "d", "label": "D", "theme": None},        # None -> ""
        {"id": "g", "label": "G", "theme": "OWFs", "isGhost": True},  # excluded
        "not-a-dict",                                    # excluded
    ])
    themes = dict(qsem_themes(data))
    assert themes["OWFs"] == 2       # ghost + non-dict excluded
    assert themes[""] == 2           # missing + None collapse to ""


@pytest.mark.skipif(not _MODELS_DIR.is_dir(), reason="external models absent")
def test_qsem_themes_keyset_matches_qsem_to_isa():
    for f in _MODELS_DIR.glob("*.qsem"):
        data = json.loads(f.read_text(encoding="utf-8"))
        theme_keys = {t for t, _ in qsem_themes(data)}
        # themes qsem_to_isa actually normalizes from canonical nodes
        canon = [n for n in data["canvas"]["nodes"]
                 if isinstance(n, dict) and not n.get("isGhost")]
        seen = {(n.get("theme") or "") for n in canon}
        assert theme_keys == seen, f.name
```

- [ ] **Step 2: Run to verify fail**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k themes -q`
Expected: FAIL — `qsem_themes` not defined.

- [ ] **Step 3: Implement in `sespy/qsem_import.py`**

```python
from collections import Counter


def qsem_themes(data: dict) -> list[tuple[str, int]]:
    """Distinct themes of canonical (non-ghost) nodes with counts. Uses the
    SAME node guard and `theme or ""` normalization as qsem_to_isa so the keys
    line up exactly with what gets typed. Sorted by count desc, then name."""
    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    counts: Counter[str] = Counter(
        (n.get("theme") or "")
        for n in nodes
        if isinstance(n, dict) and not n.get("isGhost")
    )
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
```

- [ ] **Step 4: Run to verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k themes -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sespy/qsem_import.py tests/test_qsem_dapsiwrm_map.py
git commit -m "feat(qsem): qsem_themes with qsem_to_isa-consistent normalization"
```

---

### Task 3: Data — `suggest_dapsiwrm_map` heuristic

**Files:**
- Modify: `sespy/qsem_import.py`
- Test: `tests/test_qsem_dapsiwrm_map.py`

**Interfaces:**
- Produces: `suggest_dapsiwrm_map(themes: Iterable[str]) -> dict[str, str]`.

- [ ] **Step 1: Write the failing tests** (append)

```python
from sespy.qsem_import import suggest_dapsiwrm_map


def test_suggest_known_themes():
    m = suggest_dapsiwrm_map([
        "OWFs", "Environmental pressures", "Ecosystem components",
        "Policy", "Food web", "Ecosystem Services", "LWB", "NiD", "",
    ])
    assert m["OWFs"] == "Activities"
    assert m["Environmental pressures"] == "Pressures"
    assert m["Ecosystem components"] == "Marine Processes & Functioning"
    assert m["Policy"] == "Responses"
    assert m["Food web"] == "Marine Processes & Functioning"
    assert m["Ecosystem Services"] == "Ecosystem Services"  # exact match first
    assert m["NiD"] == "Responses"      # exact abbreviation lookup (user-confirmed)
    assert m["LWB"] == "" and m[""] == ""


def test_suggest_ordering_responses_before_goods():
    # "governance" must win over the broad "good"
    assert suggest_dapsiwrm_map(["Good governance"])["Good governance"] == "Responses"


def test_suggest_abbrev_is_exact_not_substring():
    # exact 'NiD' -> Responses, but a word merely CONTAINING 'nid' must not match
    m = suggest_dapsiwrm_map(["NiD", "Unidentified stressors"])
    assert m["NiD"] == "Responses"
    assert m["Unidentified stressors"] == ""   # no false substring hit
```

- [ ] **Step 2: Run to verify fail**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k suggest -q`
Expected: FAIL — not defined.

- [ ] **Step 3: Implement in `sespy/qsem_import.py`**

Add `from collections.abc import Iterable` to the imports, then:

```python
# (theme_keyword_substring, DAPSIWRM type) — first match wins; Responses before
# Goods & Benefits so "governance"/"management" aren't shadowed by "good".
_HEURISTIC_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("driver",), "Drivers"),
    (("pressure",), "Pressures"),
    (("activit", "fishing", "farm", "wind", "owf", "shipping", "aquacult", "tourism"), "Activities"),
    (("service",), "Ecosystem Services"),
    (("process", "function", "component", "habitat", "species", "food web", "ecolog"), "Marine Processes & Functioning"),
    (("policy", "response", "management", "measure", "governance", "regulation"), "Responses"),
    (("benefit", "good", "welfare", "value", "econom"), "Goods & Benefits"),
)


# NiD4OCEAN project abbreviations — EXACT (case-insensitive) match, so short
# codes cannot false-match as substrings (bare "nid" would hit "Unidentified").
# LWB deliberately omitted -> stays untyped (user-confirmed).
_ABBREV: dict[str, str] = {"nid": "Responses"}


def suggest_dapsiwrm_map(themes: Iterable[str]) -> dict[str, str]:
    """Heuristic best-guess theme -> DAPSIWRM type (or "" untyped). Precedence:
    exact DAPSIWRM match → exact project-abbreviation lookup → first
    keyword-substring rule (case-insensitive)."""
    out: dict[str, str] = {}
    for theme in themes:
        if theme in DAPSIWRM_ELEMENTS:
            out[theme] = theme
            continue
        low = theme.lower()
        if low in _ABBREV:
            out[theme] = _ABBREV[low]
            continue
        out[theme] = ""
        for keywords, dtype in _HEURISTIC_RULES:
            if any(k in low for k in keywords):
                out[theme] = dtype
                break
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k suggest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sespy/qsem_import.py tests/test_qsem_dapsiwrm_map.py
git commit -m "feat(qsem): suggest_dapsiwrm_map heuristic pre-fill"
```

---

### Task 4: Data — `resolve_theme_map` (pure commit-glue)

**Files:**
- Modify: `sespy/qsem_import.py`
- Test: `tests/test_qsem_dapsiwrm_map.py`

**Interfaces:**
- Produces: `resolve_theme_map(themes: list[str], suggested: dict[str,str], read: Callable[[int], str | None]) -> dict[str,str]` — builds the final map; when `read(i)` returns `None` (select not set yet), falls back to `suggested[theme]`. Pure, so the commit handler's core logic is unit-testable without Shiny.

- [ ] **Step 1: Write the failing tests** (append)

```python
from sespy.qsem_import import resolve_theme_map


def test_resolve_theme_map_uses_reads_and_falls_back():
    themes = ["OWFs", "Policy", "LWB"]
    suggested = {"OWFs": "Activities", "Policy": "Responses", "LWB": ""}
    reads = {0: "Drivers", 1: None, 2: "Pressures"}   # index 1 not set yet
    out = resolve_theme_map(themes, suggested, reads.get)
    assert out == {"OWFs": "Drivers",      # user override read
                   "Policy": "Responses",  # unset -> suggested fallback
                   "LWB": "Pressures"}     # user override read
```

- [ ] **Step 2: Run to verify fail**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k resolve -q`
Expected: FAIL — not defined.

- [ ] **Step 3: Implement in `sespy/qsem_import.py`**

Add `from collections.abc import Callable, Iterable` (extend the existing import), then:

```python
def resolve_theme_map(
    themes: list[str],
    suggested: dict[str, str],
    read: "Callable[[int], str | None]",
) -> dict[str, str]:
    """Build theme -> type from per-theme select reads. `read(i)` returns the
    select value for theme index i, or None if it isn't set yet (render not
    settled); then fall back to the heuristic `suggested` so commit is always
    well-defined. Coercion to valid types happens later in qsem_to_isa."""
    out: dict[str, str] = {}
    for i, theme in enumerate(themes):
        val = read(i)
        out[theme] = suggested.get(theme, "") if val is None else val
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py -k resolve -q`
Expected: PASS.

- [ ] **Step 5: Full data-layer suite + ruff**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py tests/test_qsem_models_load.py -q && micromamba run -n shiny ruff check sespy/qsem_import.py tests/test_qsem_dapsiwrm_map.py`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add sespy/qsem_import.py tests/test_qsem_dapsiwrm_map.py
git commit -m "feat(qsem): resolve_theme_map pure commit-glue helper"
```

---

### Task 5: i18n keys ×9 languages

**Files:**
- Modify: `sespy/translations/core.json`

**Interfaces:**
- Produces: keys `import.map_theme`, `import.map_count`, `import.map_type`, `import.leave_untyped`, `import.typed_summary`. (The checkbox label + helptext are hardcoded English in `import_data_ui()`, consistent with that module's other UI strings, which are not yet i18n'd — so no keys for them.)

- [ ] **Step 1: Add the keys**

In `sespy/translations/core.json`, inside the `"translation"` object (single-line style like the neighbouring keys), add:

```json
    "import.map_theme": {"en":"QSEM theme","es":"Tema QSEM","fr":"Thème QSEM","de":"QSEM-Thema","lt":"QSEM tema","pt":"Tema QSEM","it":"Tema QSEM","no":"QSEM-tema","el":"Θέμα QSEM"},
    "import.map_count": {"en":"Nodes","es":"Nodos","fr":"Nœuds","de":"Knoten","lt":"Mazgai","pt":"Nós","it":"Nodi","no":"Noder","el":"Κόμβοι"},
    "import.map_type": {"en":"DAPSIWRM type","es":"Tipo DAPSIWRM","fr":"Type DAPSIWRM","de":"DAPSIWRM-Typ","lt":"DAPSIWRM tipas","pt":"Tipo DAPSIWRM","it":"Tipo DAPSIWRM","no":"DAPSIWRM-type","el":"Τύπος DAPSIWRM"},
    "import.leave_untyped": {"en":"Leave untyped","es":"Dejar sin tipo","fr":"Laisser sans type","de":"Ohne Typ lassen","lt":"Palikti be tipo","pt":"Deixar sem tipo","it":"Lascia senza tipo","no":"La stå utypet","el":"Χωρίς τύπο"},
    "import.typed_summary": {"en":"Assigned DAPSIWRM types to {typed} of {total} elements.","es":"Se asignaron tipos DAPSIWRM a {typed} de {total} elementos.","fr":"Types DAPSIWRM attribués à {typed} sur {total} éléments.","de":"DAPSIWRM-Typen zu {typed} von {total} Elementen zugewiesen.","lt":"DAPSIWRM tipai priskirti {typed} iš {total} elementų.","pt":"Tipos DAPSIWRM atribuídos a {typed} de {total} elementos.","it":"Tipi DAPSIWRM assegnati a {typed} di {total} elementi.","no":"DAPSIWRM-typer tildelt {typed} av {total} elementer.","el":"Εκχωρήθηκαν τύποι DAPSIWRM σε {typed} από {total} στοιχεία."},
```

- [ ] **Step 2: Validate JSON + keys load**

Run: `micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8')); t=d['translation']; assert all(k in t for k in ['import.map_theme','import.map_count','import.map_type','import.leave_untyped','import.typed_summary']); assert all(len(t[k])==9 for k in t if k.startswith('import.')); print('i18n OK')"`
Expected: `i18n OK`.

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(import): keys for DAPSIWRM assignment UI x9 languages"
```

---

### Task 6: UI — static checkbox, mapping table, upload reactives

**Files:**
- Modify: `sespy/modules/import_data.py`

**Interfaces:**
- Consumes: `qsem_themes`, `suggest_dapsiwrm_map`, `parse_upload`, `DAPSIWRM_ELEMENTS`.
- Produces: a `raw_qsem` reactive, a `themes` reactive (`list[str]`), a `seq` reactive (`int`), an `assign_dapsiwrm` static checkbox, and a `dapsiwrm_map` `render.ui` — all consumed by Task 7's commit handler.

- [ ] **Step 1: Add imports + STATIC checkbox to the UI**

At the top of `sespy/modules/import_data.py`, extend imports:

```python
from ..constants import DAPSIWRM_ELEMENTS
from ..qsem_import import parse_qsem, qsem_themes, suggest_dapsiwrm_map
```

In `import_data_ui()`, insert a **static** checkbox (always in the DOM, so
`input.assign_dapsiwrm()` is ALWAYS set — never `SilentException`) plus a
dynamic map slot, between the `input_file(...)` and the `ui.tags.hr()` before
`output_ui("preview")`:

```python
            ui.input_file( ... ),  # unchanged
            ui.input_checkbox(
                "assign_dapsiwrm",
                "Assign DAPSIWRM types (QSEM only)",
                value=False,
            ),
            ui.tags.small(
                "Map each QSEM theme to a DAPSIWRM category so the diagram is "
                "coloured and levelled. Unmapped themes stay untyped.",
                class_="text-muted",
            ),
            ui.output_ui("dapsiwrm_map"),   # table renders only for QSEM + checked
            ui.tags.hr(),
            ui.output_ui("preview"),
```

Rationale (CRITICAL review finding): the checkbox stays static so reading it in
the shared `_on_commit` can never `SilentException`-break the Excel path. It is
shown for all uploads but is a **no-op** for non-QSEM (the commit gates on
`raw_qsem is not None`). Only the per-theme selects (inherently dynamic) need
guarded reads.

- [ ] **Step 2: Add the reactives + renderers in `import_data_server`**

Near the top of `import_data_server` (after the existing `parsed = reactive.value(None)`), add:

```python
    raw_qsem: reactive.Value[dict | None] = reactive.value(None)
    themes: reactive.Value[list[str]] = reactive.value([])
    seq: reactive.Value[int] = reactive.value(0)
```

In `_on_upload`, after computing `result = parse_upload(...)` and `parsed.set(result)`, add QSEM detection + raw storage:

```python
        suffix = Path(info["name"]).suffix.lower()
        if suffix in (".qsem", ".json") and result.valid:
            import json
            try:
                data = json.loads(Path(info["datapath"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
            raw_qsem.set(data)
            themes.set([t for t, _ in qsem_themes(data)] if data else [])
            seq.set(seq.get() + 1)   # generation stamp -> fresh select ids
        else:
            raw_qsem.set(None)
            themes.set([])
```

Add the map renderer (place beside the existing `preview` renderer). The checkbox
is static (Step 1); this only renders the table when a QSEM is loaded AND the box
is ticked:

```python
    @output
    @render.ui
    def dapsiwrm_map():
        if raw_qsem.get() is None or not input.assign_dapsiwrm():
            return None
        th = themes.get()
        suggested = suggest_dapsiwrm_map(th)
        choices = {"": _t("import.leave_untyped", "Leave untyped")}
        choices.update({d: d for d in DAPSIWRM_ELEMENTS})
        s = seq.get()
        counts = dict(qsem_themes(raw_qsem.get()))
        rows = [
            ui.tags.tr(
                ui.tags.td(t or _t("import.leave_untyped", "(untyped)")),
                ui.tags.td(str(counts.get(t, 0)), class_="text-nowrap"),
                ui.tags.td(ui.input_select(
                    f"map_{s}_{i}", None, choices=choices, selected=suggested.get(t, ""),
                    width="240px",
                )),
            )
            for i, t in enumerate(th)
        ]
        head = ui.tags.thead(ui.tags.tr(
            ui.tags.th(_t("import.map_theme", "QSEM theme")),
            ui.tags.th(_t("import.map_count", "Nodes")),
            ui.tags.th(_t("import.map_type", "DAPSIWRM type")),
        ))
        return ui.tags.table(head, ui.tags.tbody(*rows),
                             class_="table table-sm sespy-feedback-table mb-0")
```

Add a small `_t` helper at the top of `import_data_server` if not present (the module receives `translator`):

```python
    def _t(key: str, fallback: str) -> str:
        return translator.t(key) if translator else fallback
```

- [ ] **Step 3: Smoke-test the app builds**

Run: `micromamba run -n shiny python -c "import app; print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Ruff**

Run: `micromamba run -n shiny ruff check sespy/modules/import_data.py`
Expected: clean. (Move the `import json` to module top if ruff flags the inline import.)

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/import_data.py
git commit -m "feat(import): DAPSIWRM checkbox + per-theme mapping table (UI only)"
```

---

### Task 7: UI — commit re-map + state reset

**Files:**
- Modify: `sespy/modules/import_data.py`

**Interfaces:**
- Consumes: Task 6 reactives (`raw_qsem`, `themes`, `seq`, `assign_dapsiwrm`, `map_{seq}_{i}`), `resolve_theme_map`, `build_project`.

- [ ] **Step 1: Add imports**

```python
from ..qsem_import import build_project, parse_qsem, qsem_themes, resolve_theme_map, suggest_dapsiwrm_map
```

- [ ] **Step 2: Rewrite `_on_commit` to branch on the guarded checkbox**

Replace the current `_on_commit` body:

```python
    @reactive.effect
    @reactive.event(input.commit, ignore_init=True)
    def _on_commit():
        result = parsed.get()
        if result is None or not result.valid or result.project is None:
            return

        data = raw_qsem.get()
        # Checkbox is static (always in DOM) -> input.assign_dapsiwrm() is always
        # safe to read. Non-QSEM uploads have raw_qsem=None -> plain path.
        if data is not None and input.assign_dapsiwrm():
            th = themes.get()
            suggested = suggest_dapsiwrm_map(th)
            s = seq.get()

            def _read(i: int):
                # Per-theme selects ARE dynamic -> guard existence + set-ness,
                # falling back (in resolve_theme_map) to the heuristic guess.
                key = f"map_{s}_{i}"
                try:
                    return input[key]() if input[key].is_set() else None
                except Exception:
                    return None

            theme_map = resolve_theme_map(th, suggested, _read)
            remapped = build_project(data, result.project.metadata.name, theme_map)
            project = remapped.project if remapped.valid and remapped.project else result.project
        else:
            project = result.project

        project_data.set(project)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_project_loaded()

        typed = sum(1 for e in project.isa_data.elements if e.type)
        ui.notification_show(
            _t("import.typed_summary",
               "Assigned DAPSIWRM types to {typed} of {total} elements.").format(
                   typed=typed, total=project.isa_data.element_count()),
            type="message", duration=4,
        )

        # reset all state so the next upload starts clean
        parsed.set(None)
        raw_qsem.set(None)
        themes.set([])
        ui.update_action_button("commit", disabled=True)
        ui.update_checkbox("assign_dapsiwrm", value=False)
```

Note: the static checkbox needs no existence guard. For the dynamic per-theme
selects, `_read` wraps the access in `try/except` (covers both a not-yet-created
id and `SilentException` from an unset value) and returns `None`, which
`resolve_theme_map` turns into the heuristic fallback. Verify `input[key].is_set()`
exists in the installed Shiny; if not, rely on the `try/except` alone.

- [ ] **Step 3: Smoke-test build + existing import e2e**

Run: `micromamba run -n shiny python -c "import app; print('OK')"`
Then start a server and run the existing import e2e (regression):
```bash
micromamba run -n shiny python -m shiny run app.py --port 8000 --host 127.0.0.1 & \
until curl -s -o /dev/null http://127.0.0.1:8000/; do sleep 1; done; \
micromamba run -n shiny python tests/test_import_e2e.py; \
pkill -f "8000" 2>/dev/null
```
Expected: `import e2e assertions pass`. (If the server orphans, kill by port with PowerShell `Get-NetTCPConnection -LocalPort 8000`.)

- [ ] **Step 4: Ruff**

Run: `micromamba run -n shiny ruff check sespy/modules/import_data.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/import_data.py
git commit -m "feat(import): apply DAPSIWRM theme map on commit + reset state"
```

---

### Task 8: e2e — mapping applies, Excel regression

**Files:**
- Create: `tests/test_qsem_map_e2e.py`
- Modify: `tests/test_import_e2e.py`

- [ ] **Step 1: Write the QSEM-map e2e script**

Create `tests/test_qsem_map_e2e.py`. It copies a real model into the repo (Playwright-MCP-independent; plain Playwright can read any path, so use the absolute model path directly), uploads, ticks the box, commits, and asserts the CLD carries DAPSIWRM groups:

```python
"""E2E: QSEM import with DAPSIWRM assignment -> CLD gets typed (coloured) nodes."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

MODEL = Path(
    r"C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\NiD4OCEAN"
    r"\DST\social ecological system map\Social ecological systems map\Food_web_V_01.qsem"
)


async def main():
    if not MODEL.exists():
        print("model absent — skip")
        return
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.click("#sespy_nav_import")
        await pg.wait_for_timeout(1500)
        await pg.set_input_files("#import-xlsx", str(MODEL))
        await pg.wait_for_selector("#import-commit:not([disabled])", timeout=15000)
        # tick "Assign DAPSIWRM types"
        await pg.check("#import-assign_dapsiwrm")
        await pg.wait_for_selector("#import-dapsiwrm_map select", timeout=10000)
        await pg.click("#import-commit")
        # go to CLD, wait for the network, assert DAPSIWRM groups present
        await pg.click("#sespy_nav_cld")
        await pg.wait_for_selector("#cld-network", timeout=30000)
        groups = None
        for _ in range(30):
            groups = await pg.evaluate(
                "() => { const s=window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s||!s.nodes) return null;"
                " return Array.from(new Set(s.nodes.get().map(n => n.group))); }"
            )
            if groups and any(g and g != "" for g in groups):
                break
            await pg.wait_for_timeout(500)
        print("cld groups:", groups)
        assert groups is not None, "cld-network not readable"
        assert any(g in ("Activities", "Pressures", "Marine Processes & Functioning",
                         "Responses", "Ecosystem Services", "Goods & Benefits", "Drivers")
                   for g in groups), f"no DAPSIWRM groups after mapping: {groups}"
        print("qsem-map e2e assertions pass")
        await b.close()


asyncio.run(main())
```

- [ ] **Step 2: Add an Excel-commit regression to `tests/test_import_e2e.py`**

The existing script already uploads an Excel fixture and commits. Confirm it still asserts a successful commit AFTER the checkbox change (the static-checkbox guard must not break Excel). If the script lacks an explicit post-commit assertion, add after its commit click:

```python
        # Excel import still works with the DAPSIWRM checkbox present-but-unused
        await pg.wait_for_selector(".shiny-notification", timeout=10000)
```

- [ ] **Step 3: Run both e2e against a live server**

```bash
micromamba run -n shiny python -m shiny run app.py --port 8000 --host 127.0.0.1 & \
until curl -s -o /dev/null http://127.0.0.1:8000/; do sleep 1; done; \
micromamba run -n shiny python tests/test_import_e2e.py; \
micromamba run -n shiny python tests/test_qsem_map_e2e.py
```
Then kill the server by port (PowerShell `Get-NetTCPConnection -LocalPort 8000 | %{Stop-Process -Id $_.OwningProcess -Force}`).
Expected: both print `assertions pass`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_qsem_map_e2e.py tests/test_import_e2e.py
git commit -m "test(e2e): QSEM DAPSIWRM mapping applies to CLD + Excel regression"
```

---

### Task 9: CHANGELOG + full gate + ship

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add CHANGELOG entry**

Under `## [Unreleased]` add:

```markdown
- Import: optional "Assign DAPSIWRM types" for QSEM models — an editable,
  heuristic-pre-filled per-theme mapping table (opt-in, default off) so imported
  models render as a coloured, levelled CLD.
```

- [ ] **Step 2: Full unit suite + ruff**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_dapsiwrm_map.py tests/test_qsem_models_load.py tests/test_cld_filter.py -q && micromamba run -n shiny ruff check sespy/qsem_import.py sespy/modules/import_data.py tests/`
Expected: all PASS, ruff clean.

- [ ] **Step 3: Full e2e gate (clean 8000 first!)**

Ensure nothing squats on 8000 (`Get-NetTCPConnection -LocalPort 8000`), then:
Run: `micromamba run -n shiny python tests/run_e2e.py --port 8000`
Expected: 28/29 (or 29/30 with the new script) — only `test_report_e2e` (WeasyPrint) may fail.

- [ ] **Step 4: Commit + ship**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): QSEM DAPSIWRM assignment"
git push origin main
bash deploy/deploy.sh
```

- [ ] **Step 5: Verify live** (via `ssh -L 8899:127.0.0.1:3838 <server>` tunnel + a real import through the browser, or at minimum grep the deployed `suggest_dapsiwrm_map`/`qsem_themes` on the server and confirm HTTP 200 + feedback DB preserved).
