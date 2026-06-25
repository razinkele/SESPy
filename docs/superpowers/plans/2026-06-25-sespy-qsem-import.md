# Direct `.qsem` Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a native `.qsem` (QSEM web app) JSON file directly — map its node/link graph into SESPy elements/connections through the shared validator.

**Architecture:** A new pure `qsem_import.qsem_to_isa(data)` reshape + a `parse_qsem(path)` that mirrors `excel_import.parse_excel`'s `ValidationResult` contract; the Import module dispatches an upload to `parse_qsem` or `parse_excel` by the original filename extension.

**Tech Stack:** Python 3.11, stdlib `json`, pytest.

## Global Constraints

- `.qsem` is JSON: `data["canvas"]["nodes"]` (each `{id, label, theme?, isGhost?, originalNodeId?}`) and `data["canvas"]["links"]` (each `{sourceNodeId, targetNodeId, polarity:"positive"|"negative", impact:int, delay:int}`).
- **Every node-field access is `.get`-safe** — `theme` key is ABSENT (not null) on ~half of real nodes; `node["theme"]` would KeyError.
- **Ghost nodes** (`isGhost:true`) are NOT imported; links referencing a ghost are redirected to its `originalNodeId` (a canonical node) before id-mapping.
- `qsem_to_isa(data) -> tuple[list[Element], list[Connection]]` — pure. Canonical nodes → clean ids `N001, N002, …` (`f"N{i:03d}"`); `id_map[node.id] = new_id`.
  - `type` = `theme` iff `theme` exactly in `constants.DAPSIWRM_ELEMENTS` (e.g. `"Ecosystem Services"`), else `""`; `description` = `f"Theme: {theme}"` only when `theme` is non-empty AND unmapped, else `""`.
  - `strength` from `impact`: `<=1` weak, `==2` medium, `>=3` strong (clamp; default 2→medium).
  - `delay` from `qsem_delay_to_level(delay)`: `<=0` immediate, `==1` short, `>=2` long. **Never use `constants.normalize_delay`** (it flattens every nonzero int to `"short"`).
  - `polarity` = `"-"` if `link.get("polarity") == "negative"` else `"+"`. `confidence` = 3. `ratings` stays `[]`.
  - Skip a link if either ref resolves to `None` (dangling) or `source == target` (self-loop).
- `parse_qsem(path) -> ValidationResult`: `json.load` guarded; `canvas.nodes` must be a list (else error); empty nodes → error; payload mirrors `parse_excel` (`metadata.name=path.stem`, `isa_data.elements/connections` as `__dict__`s) → `validate_project_payload`.
- Dataclasses: `Element(id, label, type, description="", confidence=3)`; `Connection(source, target, polarity="+", strength="medium", confidence=3, delay="immediate", ratings=[])`; `ValidationResult(valid, errors, project=None)`.
- No schema/i18n change. Run pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `sespy/qsem_import.py` — pure map + `parse_qsem`

**Files:**
- Create: `sespy/qsem_import.py`
- Test: `tests/test_qsem_import.py`

**Interfaces:**
- Produces: `qsem_to_isa(data: dict) -> tuple[list[Element], list[Connection]]`; `parse_qsem(path: Path | str) -> ValidationResult`; `qsem_delay_to_level(delay) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_qsem_import.py`:

```python
"""Unit + integration tests for the .qsem JSON importer."""
from __future__ import annotations

import json

from sespy import constants
from sespy.qsem_import import parse_qsem, qsem_to_isa, qsem_delay_to_level


def _node(nid, label, **extra):
    return {"id": nid, "label": label, **extra}


def _link(src, tgt, **extra):
    return {"sourceNodeId": src, "targetNodeId": tgt, **extra}


def test_qsem_delay_to_level_boundaries():
    assert qsem_delay_to_level(-1) == "immediate"
    assert qsem_delay_to_level(0) == "immediate"
    assert qsem_delay_to_level(1) == "short"
    assert qsem_delay_to_level(2) == "long"
    assert qsem_delay_to_level(3) == "long"
    # Guard: documents why a custom fn exists — normalize_delay flattens 2 -> "short".
    assert constants.normalize_delay(2) == "short"


def test_qsem_to_isa_node_and_link_mapping():
    data = {"canvas": {"nodes": [
        _node("n1", "Fish stock", theme="Ecosystem Services"),   # exact -> type
        _node("n2", "OWF installation", theme="OWFs"),           # unmapped -> "" + desc
        _node("n3", "Some factor"),                              # no theme key at all
        _node("n4", "Dup label"),
        _node("n5", "Dup label"),                                # duplicate label
    ], "links": [
        _link("n1", "n2", polarity="positive", impact=3, delay=1),
        _link("n2", "n3", polarity="negative", impact=1, delay=0),
        _link("n3", "n4", polarity="positive", impact=2, delay=2),
        _link("n4", "n4", polarity="positive", impact=2),        # self-loop -> skip
        _link("n5", "ZZZ", polarity="positive", impact=2),       # dangling -> skip
    ]}}
    elements, connections = qsem_to_isa(data)

    assert [e.id for e in elements] == ["N001", "N002", "N003", "N004", "N005"]
    by_id = {e.id: e for e in elements}
    assert by_id["N001"].type == "Ecosystem Services" and by_id["N001"].description == ""
    assert by_id["N002"].type == "" and by_id["N002"].description == "Theme: OWFs"
    assert by_id["N003"].type == "" and by_id["N003"].description == ""
    assert by_id["N004"].label == by_id["N005"].label == "Dup label"

    pairs = {(c.source, c.target): c for c in connections}
    assert set(pairs) == {("N001", "N002"), ("N002", "N003"), ("N003", "N004")}
    assert pairs[("N001", "N002")].polarity == "+"
    assert pairs[("N001", "N002")].strength == "strong"
    assert pairs[("N001", "N002")].delay == "short"
    assert pairs[("N002", "N003")].polarity == "-"
    assert pairs[("N002", "N003")].strength == "weak"
    assert pairs[("N002", "N003")].delay == "immediate"
    assert pairs[("N003", "N004")].strength == "medium"
    assert pairs[("N003", "N004")].delay == "long"


def test_qsem_to_isa_skips_ghosts_and_redirects_links():
    data = {"canvas": {"nodes": [
        _node("real", "Heat emission", theme="OWFs"),
        _node("ghost", "Heat emission", isGhost=True, originalNodeId="real"),
        _node("other", "Seagrass"),
    ], "links": [
        _link("ghost", "other", polarity="positive", impact=2, delay=1),  # from a ghost
    ]}}
    elements, connections = qsem_to_isa(data)
    assert [e.label for e in elements] == ["Heat emission", "Seagrass"]
    assert [e.id for e in elements] == ["N001", "N002"]
    assert len(connections) == 1
    assert connections[0].source == "N001" and connections[0].target == "N002"


def test_parse_qsem_integration(tmp_path):
    data = {"canvas": {"nodes": [
        _node("a", "A", theme="Ecosystem Services"),
        _node("b", "B"),
        _node("c", "C"),
    ], "links": [
        _link("a", "b", polarity="negative", impact=3, delay=2),
        _link("b", "c", polarity="positive", impact=1, delay=1),
        _link("c", "ZZ", polarity="positive", impact=2),  # dangling -> skipped
    ]}}
    f = tmp_path / "sample.qsem"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = parse_qsem(f)
    assert result.valid, result.errors
    proj = result.project
    assert proj is not None
    assert proj.isa_data.element_count() == 3
    assert proj.isa_data.connection_count() == 2
    ab = {(c.source, c.target): c for c in proj.isa_data.connections}[("N001", "N002")]
    assert ab.polarity == "-" and ab.strength == "strong" and ab.delay == "long"


def test_parse_qsem_rejects_non_json(tmp_path):
    f = tmp_path / "bad.qsem"
    f.write_text("this is not json {{{", encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("QSEM/JSON" in e for e in result.errors)


def test_parse_qsem_rejects_missing_canvas_nodes(tmp_path):
    f = tmp_path / "nocanvas.qsem"
    f.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("canvas.nodes" in e for e in result.errors)


def test_parse_qsem_rejects_empty_nodes(tmp_path):
    f = tmp_path / "empty.qsem"
    f.write_text(json.dumps({"canvas": {"nodes": [], "links": []}}), encoding="utf-8")
    result = parse_qsem(f)
    assert not result.valid
    assert any("no nodes" in e for e in result.errors)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_import.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sespy.qsem_import'`.

- [ ] **Step 3: Implement `sespy/qsem_import.py`**

```python
"""Direct .qsem (QSEM web app) JSON import — companion to excel_import.py.

A .qsem file is JSON: a node/link graph under `canvas`. Canonical nodes map to
Elements, links map to Connections, then the shared `validate_project_payload`
runs — so a bad .qsem fails the same way a bad JSON/Excel load does.
"""
from __future__ import annotations

import json
from pathlib import Path

from .constants import DAPSIWRM_ELEMENTS
from .data_structure import Connection, Element
from .persistent_storage import ValidationResult, validate_project_payload


def qsem_delay_to_level(delay: object) -> str:
    """Map a QSEM integer delay to a SESPy DELAY_LEVELS token: <=0 immediate,
    ==1 short, >=2 long. NOT `constants.normalize_delay` — that flattens every
    nonzero int to 'short', losing QSEM's slow-link signal."""
    try:
        d = int(delay)
    except (TypeError, ValueError):
        return "immediate"
    if d <= 0:
        return "immediate"
    if d == 1:
        return "short"
    return "long"


def _impact_to_strength(impact: object) -> str:
    try:
        imp = int(impact)
    except (TypeError, ValueError):
        imp = 2
    if imp <= 1:
        return "weak"
    if imp == 2:
        return "medium"
    return "strong"


def qsem_to_isa(data: dict) -> tuple[list[Element], list[Connection]]:
    """Pure map: a QSEM dict -> (elements, connections). Ghost nodes are skipped;
    links referencing a ghost are redirected to its `originalNodeId`. Dangling
    and self-loop links are skipped. Every node-field access is `.get`-safe."""
    canvas = data.get("canvas", {}) if isinstance(data, dict) else {}
    nodes = canvas.get("nodes") if isinstance(canvas.get("nodes"), list) else []
    links = canvas.get("links") if isinstance(canvas.get("links"), list) else []

    canonical = [n for n in nodes if not n.get("isGhost")]
    ghost_to_original = {
        n.get("id"): n.get("originalNodeId") for n in nodes if n.get("isGhost")
    }

    elements: list[Element] = []
    id_map: dict[str, str] = {}
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

    def resolve(ref: object) -> str | None:
        return id_map.get(ghost_to_original.get(ref, ref))

    connections: list[Connection] = []
    for link in links:
        src = resolve(link.get("sourceNodeId"))
        tgt = resolve(link.get("targetNodeId"))
        if src is None or tgt is None or src == tgt:
            continue
        connections.append(Connection(
            source=src,
            target=tgt,
            polarity="-" if link.get("polarity") == "negative" else "+",
            strength=_impact_to_strength(link.get("impact", 2)),
            confidence=3,
            delay=qsem_delay_to_level(link.get("delay", 0)),
        ))
    return elements, connections


def parse_qsem(path: Path | str) -> ValidationResult:
    """Parse a .qsem JSON file into a Project. Same contract as parse_excel."""
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

    elements, connections = qsem_to_isa(data)
    payload = {
        "metadata": {
            "name": path.stem,
            "description": f"Imported from {path.name}",
        },
        "isa_data": {
            "elements": [e.__dict__ for e in elements],
            "connections": [c.__dict__ for c in connections],
        },
    }
    return validate_project_payload(payload)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_import.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/qsem_import.py tests/test_qsem_import.py
git commit -m "feat(import): direct .qsem JSON importer (qsem_to_isa + parse_qsem)"
```

---

### Task 2: Wire `.qsem` into the Import Data module

**Files:**
- Modify: `sespy/modules/import_data.py`
- Test: `tests/test_qsem_import.py`

**Interfaces:**
- Consumes: `parse_qsem` (Task 1), `parse_excel` (existing).
- Produces: `parse_upload(name: str, datapath: Path | str) -> ValidationResult`.

- [ ] **Step 1: Write the failing routing test**

Append to `tests/test_qsem_import.py`:

```python
def test_parse_upload_dispatches_by_extension(tmp_path):
    # The dispatch keys off the ORIGINAL filename, not the temp datapath.
    from sespy.modules.import_data import parse_upload

    data = {"canvas": {"nodes": [{"id": "a", "label": "A"}], "links": []}}
    f = tmp_path / "model.qsem"
    f.write_text(json.dumps(data), encoding="utf-8")

    # .qsem name -> parse_qsem -> valid (1 node, 0 connections)
    qsem_result = parse_upload("model.qsem", f)
    assert qsem_result.valid, qsem_result.errors
    assert qsem_result.project.isa_data.element_count() == 1

    # same JSON bytes but a .xlsx name -> parse_excel -> invalid (not a real xlsx)
    xlsx_result = parse_upload("model.xlsx", f)
    assert not xlsx_result.valid
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_import.py::test_parse_upload_dispatches_by_extension -v`
Expected: FAIL — `ImportError: cannot import name 'parse_upload'`.

- [ ] **Step 3: Implement the dispatch in `sespy/modules/import_data.py`**

a) Update the import near the top (after `from ..excel_import import parse_excel`):

```python
from ..excel_import import parse_excel
from ..qsem_import import parse_qsem
```

b) Add a module-level helper (place it just below the imports, before `import_data_ui`):

```python
def parse_upload(name: str, datapath: Path | str) -> ValidationResult:
    """Dispatch an uploaded file to the right parser by its ORIGINAL filename
    extension — Shiny's temp `datapath` may not preserve the suffix."""
    suffix = Path(name).suffix.lower()
    if suffix in (".qsem", ".json"):
        return parse_qsem(datapath)
    return parse_excel(datapath)
```

c) In `_on_upload`, replace the parse call. Change:

```python
        path = Path(files[0]["datapath"])
        result = parse_excel(path)
        parsed.set(result)
```

to:

```python
        info = files[0]
        result = parse_upload(info["name"], info["datapath"])
        parsed.set(result)
```

d) Widen the file picker and update the copy. Change the `ui.input_file(...)` `accept` and `button_label`:

```python
            ui.input_file(
                "xlsx",
                "",
                accept=[".xlsx", ".xls", ".qsem", ".json"],
                multiple=False,
                button_label="Choose a file…",
                placeholder="No file selected",
            ),
```

and append one sentence to the help `<p>` (after the existing Connections-sheet text, before `class_="text-muted"`):

```python
                " You can also upload a ",
                ui.tags.b(".qsem"),
                " model file exported from the QSEM app.",
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_qsem_import.py -v`
Expected: PASS (8 tests). Then confirm the app imports:
`micromamba run -n shiny python -c "import app; print('ok')"` → prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/import_data.py tests/test_qsem_import.py
git commit -m "feat(import): accept .qsem uploads (dispatch by extension)"
```

---

## Definition of Done

- [ ] `micromamba run -n shiny python -m pytest tests/test_qsem_import.py tests/test_excel_import.py -q` — all green (new QSEM tests + the untouched Excel tests).
- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
- [ ] `import app` builds cleanly: `micromamba run -n shiny python -c "import app; print('ok')"`.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py` (the existing `test_import_e2e.py` xlsx path must still pass — the dispatch falls through to `parse_excel` for `.xlsx`).
- [ ] Sanity (manual, optional): `parse_qsem` on a real file loads valid — e.g. `Food_web_V_00.qsem` → **69 elements** (80 nodes minus 11 ghosts) and most of its 111 links as connections (exact count = links minus any that resolve to a self-loop/dangling after ghost-redirect).
