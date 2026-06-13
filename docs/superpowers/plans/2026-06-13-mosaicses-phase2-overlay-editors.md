# MosaicSES Evaluative-Overlay Editors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the #19 tenet scores and #20 equity dimensions editable in-app — a governance-channel tenet editor (Topology inspector) and a per-element tenet+equity editor (Compartments panel), backed by two pure library helpers and a pure app-layer assembly module.

**Architecture:** All `MultiSES` mutation goes through pure library helpers (`replace_channel`, `replace_compartment_overlays`); all input-assembly/normalization and all editor-UI-building/gating go through pure helpers (`multises_app/overlay_edit.py`, and module-private `_*_ui` builders) so the logic is unit-testable without a Shiny session. The `@render.ui` outputs + save `@reactive.effect`s are thin wrappers, covered by the pure-helper tests + e2e. Edits write straight to `state.active_multises` (no `emit_isa_change`, no `active_compartment_project` refresh); durability is the existing manual download.

**Tech Stack:** Python 3, dataclasses, Shiny for Python, pytest + Playwright. Run via micromamba env `shiny`.

**Repos:** Code + tests in the **MosaicSES** repo: `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES`. This plan + spec live in **SESPy** `docs/superpowers/`. **All commits in this plan are in the MosaicSES repo.** Work from the MosaicSES root.

**Spec:** `SESPy/docs/superpowers/specs/2026-06-13-mosaicses-phase2-overlay-editors-design.md`

**Test command:** `micromamba run -n shiny python -m pytest tests/<file> -q` (from the MosaicSES repo root).

**Sequencing:** Tasks 1–4 (library helpers + `overlay_edit.py`) must land before the editors (Tasks 5–8). The Topology editor (5–6) and the Compartments panel (7–8) are independent of each other. Task 9 e2e, Task 10 verify+mark.

---

### Task 1: `replace_channel` library helper

**Files:**
- Modify: `multises/data_structure.py` (add after `replace_compartment`, ~line 900)
- Test: `tests/test_overlay_editors.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_overlay_editors.py`:

```python
"""Tests for the overlay-editor library helpers (replace_channel,
replace_compartment_overlays)."""
from __future__ import annotations

import dataclasses

import pytest

from multises import data_structure as ds
from multises.archetypes import seed_compartment
from multises.channels import make_channel
from multises.data_structure import (
    MultiSES,
    MultiSESMetadata,
    replace_channel,
)
# NOTE: replace_compartment_overlays is added to this import in Task 2 — do NOT
# import it here, or this file fails to COLLECT (ImportError) at Task 1's
# verify-fail step instead of failing the intended test.


def _ms_with_channel(**ch_kw):
    a = seed_compartment("lagoon", label="A", id="a")
    b = seed_compartment("coastal_sea", label="B", id="b")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=[])
    ms.add_channel(make_channel(id="ch1", source="a", target="b",
                                channel_type="governance",
                                governance_regime="WFD", **ch_kw))
    return ms


def test_replace_channel_swaps_and_is_pure():
    ms = _ms_with_channel(tenet_scores={"ecological": 3})
    new_ch = dataclasses.replace(ms.channels[0],
                                 tenet_scores={"ecological": 5, "legal": 4})
    new_ms = replace_channel(ms, "ch1", new_ch)
    assert new_ms.channels[0].tenet_scores == {"ecological": 5, "legal": 4}
    assert ms.channels[0].tenet_scores == {"ecological": 3}        # original unmutated


def test_replace_channel_unknown_id_raises():
    ms = _ms_with_channel()
    with pytest.raises(KeyError):
        replace_channel(ms, "nope", ms.channels[0])


def test_replace_channel_endpoints_preserved_and_round_trip():
    ms = _ms_with_channel(tenet_scores={"ecological": 2})
    new_ch = dataclasses.replace(ms.channels[0], tenet_scores={"political": 1})
    new_ms = replace_channel(ms, "ch1", new_ch)
    assert new_ms.channels[0].source == "a" and new_ms.channels[0].target == "b"
    res = MultiSES.from_json(new_ms.to_json())
    assert res.multises.channels[0].tenet_scores == {"political": 1}
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py -q`
Expected: FAIL — `ImportError: cannot import name 'replace_channel'`.

- [ ] **Step 3: Implement `replace_channel`**

In `multises/data_structure.py`, directly after the `replace_compartment` function (it ends with its `return MultiSES(...)` near line 899), add:

```python
def replace_channel(
    ms: "MultiSES",
    channel_id: str,
    new_channel: "Channel",
) -> "MultiSES":
    """Return a new MultiSES with channel `channel_id` replaced by `new_channel`.

    Pure — does not mutate `ms`; metadata and compartments are shared by
    reference, channels are a new list. `new_channel` is validated at its own
    construction; the returned MultiSES is built via MultiSES(...), which
    re-runs the integrity checks (M001/M002 dup ids, M201 dangling endpoints),
    so a swapped channel with a bad endpoint is caught.

    Raises:
      KeyError: if `channel_id` is not in `ms.channels`.
    """
    target_idx = next(
        (i for i, ch in enumerate(ms.channels) if ch.id == channel_id),
        None,
    )
    if target_idx is None:
        raise KeyError(channel_id)
    new_channels = list(ms.channels)
    new_channels[target_idx] = new_channel
    return MultiSES(
        metadata=ms.metadata,
        compartments=ms.compartments,
        channels=new_channels,
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add multises/data_structure.py tests/test_overlay_editors.py
git commit -m "feat(mosaicses): replace_channel pure library helper (overlay editors)"
```

---

### Task 2: `replace_compartment_overlays` library helper

**Files:**
- Modify: `multises/data_structure.py` (`import dataclasses`; `_UNSET`; helper after `replace_channel`)
- Test: `tests/test_overlay_editors.py` (extend)

- [ ] **Step 1: Write the failing tests**

First, add `replace_compartment_overlays` to the existing top-of-file import block (and remove the Task-1 NOTE comment about it):

```python
from multises.data_structure import (
    MultiSES,
    MultiSESMetadata,
    replace_channel,
    replace_compartment_overlays,
)
```

Then append to `tests/test_overlay_editors.py`:

```python
def _ms_one_compartment(**overlay):
    a = seed_compartment("lagoon", label="A", id="a")
    for k, v in overlay.items():
        setattr(a, k, v)
    return MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[]), a


def test_rco_override_response_only_preserves_other_and_project():
    ms, a = _ms_one_compartment(outcome_equity_dimensions={"GB001": ["ocean_grabbing"]})
    new_ms = replace_compartment_overlays(
        ms, "a", response_tenet_scores={"R1": {"ecological": 4}})
    c = new_ms.compartment("a")
    assert c.response_tenet_scores == {"R1": {"ecological": 4}}
    assert c.outcome_equity_dimensions == {"GB001": ["ocean_grabbing"]}   # omitted -> preserved
    assert c.project is a.project                                          # project identity
    assert ms.compartment("a").response_tenet_scores is None              # original unmutated


def test_rco_explicit_none_clears():
    ms, _ = _ms_one_compartment(response_tenet_scores={"R1": {"ecological": 4}})
    new_ms = replace_compartment_overlays(ms, "a", response_tenet_scores=None)
    assert new_ms.compartment("a").response_tenet_scores is None


def test_rco_unknown_id_raises():
    ms, _ = _ms_one_compartment()
    with pytest.raises(KeyError):
        replace_compartment_overlays(ms, "nope", response_tenet_scores=None)


def test_rco_bad_score_raises_via_post_init():
    ms, _ = _ms_one_compartment()
    with pytest.raises(ds._ChannelValidationError):
        replace_compartment_overlays(ms, "a", response_tenet_scores={"R1": {"ecological": 9}})


def test_rco_placeholder_archetype_survives():
    a = dataclasses.replace(seed_compartment("lagoon", label="A", id="a"),
                            _unknown_archetype_original="raw_x")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    new_ms = replace_compartment_overlays(
        ms, "a", outcome_equity_dimensions={"GB001": ["gender_inequity"]})
    assert new_ms.compartment("a")._unknown_archetype_original == "raw_x"
    assert new_ms.compartment("a").outcome_equity_dimensions == {"GB001": ["gender_inequity"]}


def test_rco_interleaves_with_replace_channel():
    a = seed_compartment("lagoon", label="A", id="a")
    b = seed_compartment("coastal_sea", label="B", id="b")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=[])
    ms.add_channel(make_channel(id="ch1", source="a", target="b",
                                channel_type="governance", governance_regime="WFD",
                                tenet_scores={"ecological": 3}))
    ms = replace_compartment_overlays(ms, "a", outcome_equity_dimensions={"GB001": ["ocean_grabbing"]})
    ms = replace_channel(ms, "ch1", dataclasses.replace(ms.channels[0], tenet_scores={"legal": 5}))
    assert ms.compartment("a").outcome_equity_dimensions == {"GB001": ["ocean_grabbing"]}
    assert ms.channels[0].tenet_scores == {"legal": 5}
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py -k rco -q`
Expected: FAIL — `cannot import name 'replace_compartment_overlays'`.

- [ ] **Step 3: Implement the helper**

In `multises/data_structure.py`, add a bare `import dataclasses` to the top-of-file imports if it isn't already there — `replace_compartment_overlays` calls `dataclasses.replace`, which needs the **module name** bound (the file's existing `from dataclasses import dataclass, field` / `from dataclasses import asdict as _asdict` lines do NOT bind `dataclasses`). Then, directly after `replace_channel`, add:

```python
_UNSET = object()  # sentinel: "leave unchanged" vs an explicit value (incl. None)


def replace_compartment_overlays(
    ms: "MultiSES",
    compartment_id: str,
    *,
    response_tenet_scores=_UNSET,
    outcome_equity_dimensions=_UNSET,
) -> "MultiSES":
    """Return a new MultiSES with the named compartment's overlay field(s)
    overridden. Pure. A field left at `_UNSET` is preserved; passing an explicit
    value (including None) sets it. Uses dataclasses.replace(old, **changes),
    which re-runs Compartment.__post_init__ (M206/M207 fire on bad input) and
    re-passes the SAME project object and _unknown_archetype_original unchanged.

    Raises:
      KeyError: if `compartment_id` is not in `ms.compartments`.
    """
    target_idx = next(
        (i for i, c in enumerate(ms.compartments) if c.id == compartment_id),
        None,
    )
    if target_idx is None:
        raise KeyError(compartment_id)
    changes: dict = {}
    if response_tenet_scores is not _UNSET:
        changes["response_tenet_scores"] = response_tenet_scores
    if outcome_equity_dimensions is not _UNSET:
        changes["outcome_equity_dimensions"] = outcome_equity_dimensions
    new_c = dataclasses.replace(ms.compartments[target_idx], **changes)
    new_compartments = list(ms.compartments)
    new_compartments[target_idx] = new_c
    return MultiSES(
        metadata=ms.metadata,
        compartments=new_compartments,
        channels=list(ms.channels),
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py -q`
Expected: PASS (all Task 1 + 2 tests).

- [ ] **Step 5: Commit**

```bash
git add multises/data_structure.py tests/test_overlay_editors.py
git commit -m "feat(mosaicses): replace_compartment_overlays pure helper (overlay editors)"
```

---

### Task 3: Re-export both helpers from the package

**Files:**
- Modify: `multises/__init__.py`
- Test: `tests/test_overlay_editors.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_overlay_editors.py`:

```python
def test_helpers_reexported_from_package():
    import multises
    assert multises.replace_channel is replace_channel
    assert multises.replace_compartment_overlays is replace_compartment_overlays
    assert "replace_channel" in multises.__all__
    assert "replace_compartment_overlays" in multises.__all__
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py::test_helpers_reexported_from_package -q`
Expected: FAIL — `AttributeError: module 'multises' has no attribute 'replace_channel'`.

- [ ] **Step 3: Re-export**

In `multises/__init__.py`, in the `from .data_structure import (` block, add (alphabetical, near `replace_compartment`):

```python
    replace_channel,
    replace_compartment_overlays,
```

In `__all__`, add:

```python
    "replace_channel",
    "replace_compartment_overlays",
```

(Leave `_UNSET` internal — do NOT export it.)

- [ ] **Step 4: Run to verify it passes**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multises/__init__.py tests/test_overlay_editors.py
git commit -m "feat(mosaicses): re-export overlay-editor helpers from multises (overlay editors)"
```

---

### Task 4: `overlay_edit.py` pure assembly/normalization

**Files:**
- Create: `multises_app/overlay_edit.py`
- Test: `tests/test_overlay_edit.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_overlay_edit.py`:

```python
"""Tests for the pure overlay input-assembly/normalization helpers."""
from __future__ import annotations

from multises_app.overlay_edit import assemble_tenet_scores, set_overlay_entry


def test_assemble_all_blank_returns_none():
    assert assemble_tenet_scores({"ecological": "", "legal": ""}) is None


def test_assemble_drops_none_and_blanks():
    assert assemble_tenet_scores({"ecological": None, "legal": "3", "political": ""}) == {"legal": 3}


def test_assemble_partial_returns_int_dict():
    assert assemble_tenet_scores({"ecological": "5", "political": "2"}) == {"ecological": 5, "political": 2}


def test_set_overlay_sets_new_key():
    assert set_overlay_entry(None, "x", {"a": 1}) == {"x": {"a": 1}}


def test_set_overlay_overwrites_existing():
    assert set_overlay_entry({"x": 1}, "x", 2) == {"x": 2}


def test_set_overlay_falsy_removes_key():
    assert set_overlay_entry({"x": 1, "y": 2}, "x", []) == {"y": 2}


def test_set_overlay_removing_last_returns_none():
    assert set_overlay_entry({"x": {"a": 1}}, "x", None) is None


def test_set_overlay_does_not_mutate_input():
    d = {"x": 1}
    set_overlay_entry(d, "y", 2)
    assert d == {"x": 1}
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_edit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'multises_app.overlay_edit'`.

- [ ] **Step 3: Create the module**

Create `multises_app/overlay_edit.py`:

```python
"""Pure (Shiny-free) input-assembly + normalization for the overlay editors.

The single home of the 'cleared -> None' rule, so the editor logic is
unit-testable without a Shiny session (the @reactive.effects are thin wrappers).
"""
from __future__ import annotations

# Single source of truth for the tenet-score select choices, shared by BOTH
# editors (Topology channel editor + Compartments Response editor). "" is the
# unset/gap option.
TENET_SCORE_CHOICES: dict[str, str] = {
    "": "— not scored (gap)", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
}


def assemble_tenet_scores(values: dict[str, str]) -> dict[str, int] | None:
    """Map {tenet_slug: "" | "1".."5"} -> {slug: int}. The `if v` guard drops
    blanks AND None (both falsy), so a missing/unregistered input never reaches
    int(). Returns None when nothing is set (canonical 'no scores' — never {})."""
    scores = {s: int(v) for s, v in values.items() if v}
    return scores or None


def set_overlay_entry(existing: dict | None, key: str, value) -> dict | None:
    """Return a new overlay dict with `key` set to `value`, or `key` REMOVED when
    `value` is falsy. Returns None when the dict empties — so 'all cleared'
    normalizes to None and overlays never carry empty stubs. Pure."""
    d = dict(existing or {})
    if value:
        d[key] = value
    else:
        d.pop(key, None)
    return d or None
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_edit.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add multises_app/overlay_edit.py tests/test_overlay_edit.py
git commit -m "feat(mosaicses): pure overlay assembly/normalization helpers (overlay editors)"
```

---

### Task 5: Topology `_tenet_editor_ui` pure builder + gating

**Files:**
- Modify: `multises_app/modules/topology.py` (add a module-private `_tenet_editor_ui`; new imports)
- Test: `tests/test_topology_module.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_topology_module.py`:

```python
def _gov_channel(**kw):
    from multises.channels import make_channel
    return make_channel(id="g", source="a", target="b",
                        channel_type="governance", governance_regime="WFD", **kw)


def _nutrient_channel(**kw):
    from multises.channels import make_channel
    return make_channel(id="n", source="a", target="b",
                        channel_type="nutrients", **kw)


def test_tenet_editor_ui_renders_for_governance():
    html = str(topology._tenet_editor_ui(_gov_channel(tenet_scores={"ecological": 5})).tagify())
    assert "save_channel_tenets" in html
    assert "tenet_ecological" in html
    assert "channel_tenet_editing_id" in html


def test_tenet_editor_ui_none_for_unscored_non_governance():
    assert topology._tenet_editor_ui(_nutrient_channel()) is None


def test_tenet_editor_ui_none_for_none_channel():
    assert topology._tenet_editor_ui(None) is None


def test_tenet_editor_ui_readonly_note_for_scored_non_governance():
    out = topology._tenet_editor_ui(_nutrient_channel(tenet_scores={"ecological": 4}))
    html = str(out.tagify())
    assert "governance channels only" in html
    assert "save_channel_tenets" not in html
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_topology_module.py -k tenet_editor -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_tenet_editor_ui'`.

- [ ] **Step 3: Implement the pure builder**

In `multises_app/modules/topology.py`, add to the imports near the top: `from multises.data_structure import TENETS` and `from multises_app.overlay_edit import TENET_SCORE_CHOICES`. Then add this module-level function (next to the other `_`-helpers like `_inspector_node_info`):

```python
def _tenet_editor_ui(ch):
    """Pure: the tenet-score editor Tag for a governance channel; a read-only
    note for a non-governance channel that already carries scores; None
    otherwise. Inputs read `selected=` from the channel data (not from prior
    input), which is what makes select-then-edit reset correctly on re-render."""
    if ch is None:
        return None
    if ch.channel_type != "governance":
        if ch.tenet_scores:
            return ui.tags.p(
                "Tenet editing is available for governance channels only.",
                class_="placeholder",
            )
        return None
    scores = ch.tenet_scores or {}
    selects = [
        ui.input_select(f"tenet_{slug}", label,
                        choices=TENET_SCORE_CHOICES,
                        selected=str(scores.get(slug, "")))
        for slug, label in TENETS
    ]
    return ui.tags.div(
        ui.tags.h6("Tenet scores"),
        *selects,
        ui.div(ui.input_text("channel_tenet_editing_id", "", value=ch.id),
               style="display:none"),
        ui.input_action_button("save_channel_tenets", "Save scores"),
        class_="tenet-editor",
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_topology_module.py -k tenet_editor -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): _tenet_editor_ui pure builder + gating (overlay editors)"
```

---

### Task 6: Topology — mount output, render wrapper, save effect

**Files:**
- Modify: `multises_app/modules/topology.py` (UI mount; `inspector_tenet_editor` render; `save_channel_tenets` effect; imports)
- Test: `tests/test_topology_module.py` (extend — UI mount only; the render/effect are covered by Task 5's pure-builder tests + Task 9 e2e)

- [ ] **Step 1: Write the failing test (UI mount)**

Append to `tests/test_topology_module.py`:

```python
def test_topology_ui_mounts_tenet_editor_output():
    html = str(topology.topology_ui("topology").tagify())
    assert "inspector_tenet_editor" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_topology_module.py::test_topology_ui_mounts_tenet_editor_output -q`
Expected: FAIL — `inspector_tenet_editor` not in HTML.

- [ ] **Step 3: Mount the output + add render + save effect**

(a) In `topology_ui()`, in the inspector `ui.sidebar(...)`, add `ui.output_ui("inspector_tenet_editor")` directly after `ui.output_ui("inspector_detail")`:

```python
                ui.output_ui("inspector_detail"),
                ui.output_ui("inspector_tenet_editor"),
```

(b) Add to the top-of-file imports:

```python
from multises.data_structure import TENET_SLUGS, _ChannelValidationError, replace_channel
from multises_app.overlay_edit import assemble_tenet_scores
import dataclasses
```

(c) In `topology_server`, after the `inspector_detail` render function, add:

```python
    @output
    @render.ui
    def inspector_tenet_editor() -> ui.Tag:
        target = input.inspector_target() or None
        ms = state.active_multises.get()
        ch = next((c for c in ms.channels if c.id == target), None)
        out = _tenet_editor_ui(ch)
        return out if out is not None else ui.tags.div()

    @reactive.effect
    @reactive.event(input.save_channel_tenets)
    def _save_channel_tenets():
        try:
            ms = state.active_multises.get()
            cid_ch = input.channel_tenet_editing_id()
            ch = next((c for c in ms.channels if c.id == cid_ch), None)
            if ch is None or ch.channel_type != "governance":
                ui.notification_show("Channel no longer available.",
                                     type="error", duration=6)
                return
            scores = assemble_tenet_scores(
                {slug: getattr(input, f"tenet_{slug}")() for slug in TENET_SLUGS})
            new_ch = dataclasses.replace(ch, tenet_scores=scores)
            state.active_multises.set(replace_channel(ms, ch.id, new_ch))
            ui.notification_show(
                "Saved ✓" if scores else "Saved — scores cleared",
                duration=3)
        except (_ChannelValidationError, ValueError, KeyError, TypeError) as e:
            ui.notification_show(f"Could not save: {e}", type="error", duration=6)
```

- [ ] **Step 4: Run to verify the UI-mount test passes + no regressions**

Run: `micromamba run -n shiny python -m pytest tests/test_topology_module.py -q`
Expected: PASS. Also import-smoke the app: `micromamba run -n shiny python -c "import app"` from the repo root → no error.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): governance-channel tenet editor in Topology inspector (overlay editors)"
```

---

### Task 7: Compartments `_eligible_overlay_elements` + `_overlay_editor_ui` pure builders

**Files:**
- Modify: `multises_app/modules/compartments.py` (two module-private builders; imports)
- Test: `tests/test_compartments_module.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compartments_module.py`:

```python
def _lagoon():
    from multises.archetypes import seed_compartment
    return seed_compartment("lagoon", label="L", id="cl")


def test_eligible_overlay_elements_includes_responses_and_outcomes_only():
    from multises_app.modules import compartments
    from sespy.data_structure import Element
    cmp = _lagoon()
    cmp.project.isa_data.elements.append(Element(id="R1", label="Resp", type="Responses"))
    elig = compartments._eligible_overlay_elements(cmp)
    # GB001 (Goods & Benefits) and ES001 (Ecosystem Services) are outcomes; R1 a Response
    assert "GB001" in elig and "ES001" in elig and "R1" in elig
    # a Pressure (e.g. P001) is NOT eligible
    assert "P001" not in elig
    assert elig["R1"] == "Resp (Responses)"


def test_overlay_editor_ui_response_shows_tenet_inputs():
    from multises_app.modules import compartments
    from sespy.data_structure import Element
    el = Element(id="R1", label="Resp", type="Responses")
    html = str(compartments._overlay_editor_ui(el, {"ecological": 5}, None).tagify())
    assert "tenet_ecological" in html
    assert "save_overlay" in html
    assert "overlay_editing_id" in html


def test_overlay_editor_ui_outcome_shows_equity_checkboxes():
    from multises_app.modules import compartments
    from sespy.data_structure import Element
    el = Element(id="GB001", label="Fishery", type="Goods & Benefits")
    html = str(compartments._overlay_editor_ui(el, None, ["livelihood_displacement"]).tagify())
    assert "equity_dims" in html
    assert "save_overlay" in html
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py -k overlay -q`
Expected: FAIL — `_eligible_overlay_elements` / `_overlay_editor_ui` not defined.

- [ ] **Step 3: Implement the builders**

In `multises_app/modules/compartments.py`, add to the imports: `from multises.data_structure import TENETS, EQUITY_DIMENSIONS, OUTCOME_ELEMENT_TYPES` and `from multises_app.overlay_edit import TENET_SCORE_CHOICES`. Then add the two module-level helpers (near `_picker_choices`):

```python
def _eligible_overlay_elements(cmp) -> dict[str, str]:
    """Pure: {element_id: 'label (type)'} for the compartment's Response and
    outcome (Ecosystem Services / Goods & Benefits) elements only."""
    out: dict[str, str] = {}
    for e in cmp.project.isa_data.elements:
        if e.type == "Responses" or e.type in OUTCOME_ELEMENT_TYPES:
            out[e.id] = f"{e.label} ({e.type})"
    return out


def _overlay_editor_ui(element, response_scores, equity_dims):
    """Pure: the overlay editor Tag for the selected element — a 10-tenet editor
    for a Response, an equity checkbox group for an outcome — with a stamped
    hidden id + Save button. Inputs read `selected=` from the passed-in data."""
    if element is None:
        return ui.tags.p("Select an element to score.", class_="placeholder")
    if element.type == "Responses":
        scores = response_scores or {}
        body = [
            ui.input_select(f"tenet_{slug}", label,
                            choices=TENET_SCORE_CHOICES,
                            selected=str(scores.get(slug, "")))
            for slug, label in TENETS
        ]
    else:  # outcome element
        body = [ui.input_checkbox_group(
            "equity_dims", "Equity dimensions",
            choices={slug: label for slug, label in EQUITY_DIMENSIONS},
            selected=list(equity_dims or []),
        )]
    return ui.tags.div(
        *body,
        ui.div(ui.input_text("overlay_editing_id", "", value=element.id),
               style="display:none"),
        ui.input_action_button("save_overlay", "Save"),
        class_="overlay-editor",
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py -k overlay -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): pure overlay-editor builders for Compartments (overlay editors)"
```

---

### Task 8: Compartments — nav panel, repopulation effect, render, save effect

**Files:**
- Modify: `multises_app/modules/compartments.py` (nav panel; `overlay_element` repopulation effect; `overlay_editor` render; `save_overlay` effect; imports)
- Test: `tests/test_compartments_module.py` (extend — UI structure; render/effect covered by Task 7 + Task 9 e2e)

- [ ] **Step 1: Write the failing test (UI structure)**

Append to `tests/test_compartments_module.py`:

```python
def test_compartments_ui_has_evaluative_scores_panel():
    from multises_app.modules import compartments
    html = str(compartments.compartments_ui("compartments").tagify())
    assert "Evaluative scores" in html
    assert "overlay_element" in html
    assert "overlay_editor" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py::test_compartments_ui_has_evaluative_scores_panel -q`
Expected: FAIL — "Evaluative scores" not in HTML.

- [ ] **Step 3: Add the nav panel + server wiring**

(a) In `compartments_ui()`, in the `ui.navset_tab(...)`, add directly after the `ui.nav_panel("Edit Data", …)` line:

```python
                ui.nav_panel("Evaluative scores",
                             ui.input_select("overlay_element", "Element:",
                                             choices={}, width="320px"),
                             ui.output_ui("overlay_editor")),
```

(b) Add to imports:

```python
from multises.data_structure import replace_compartment_overlays, TENET_SLUGS, _ChannelValidationError
from multises_app.overlay_edit import assemble_tenet_scores, set_overlay_entry
```

(`OUTCOME_ELEMENT_TYPES`, `TENETS`, `EQUITY_DIMENSIONS` and `TENET_SCORE_CHOICES` were already imported into `compartments.py` by Task 7 — the `_save_overlay` effect below reuses `OUTCOME_ELEMENT_TYPES`. Task 7 is a prerequisite of Task 8.)

(c) In `compartments_server`, add (e.g. after `_populate_picker`):

```python
    @reactive.effect
    def _populate_overlay_element():
        ms = state.active_multises.get()
        cid = state.active_compartment_id.get()
        choices = {} if cid is None else _eligible_overlay_elements(ms.compartment(cid))
        ui.update_select("overlay_element", choices=choices, session=session)

    @output
    @render.ui
    def overlay_editor() -> ui.Tag:
        ms = state.active_multises.get()
        cid = state.active_compartment_id.get()
        eid = input.overlay_element() or None
        if cid is None or eid is None:
            return ui.tags.p("Select a compartment and element to score.",
                             class_="placeholder")
        cmp = ms.compartment(cid)
        element = next((e for e in cmp.project.isa_data.elements if e.id == eid), None)
        rscores = (cmp.response_tenet_scores or {}).get(eid)
        edims = (cmp.outcome_equity_dimensions or {}).get(eid)
        return _overlay_editor_ui(element, rscores, edims)

    @reactive.effect
    @reactive.event(input.save_overlay)
    def _save_overlay():
        try:
            ms = state.active_multises.get()
            cid = state.active_compartment_id.get()
            eid = input.overlay_editing_id()
            if cid is None:
                ui.notification_show("No compartment selected.", type="error", duration=6)
                return
            cmp = ms.compartment(cid)
            element = next((e for e in cmp.project.isa_data.elements if e.id == eid), None)
            if element is None or not (
                element.type == "Responses" or element.type in OUTCOME_ELEMENT_TYPES
            ):
                ui.notification_show("Element no longer available.", type="error", duration=6)
                return
            if element.type == "Responses":
                scores = assemble_tenet_scores(
                    {slug: getattr(input, f"tenet_{slug}")() for slug in TENET_SLUGS})
                new_field = set_overlay_entry(cmp.response_tenet_scores, eid, scores)
                new_ms = replace_compartment_overlays(ms, cid, response_tenet_scores=new_field)
            else:
                dims = list(input.equity_dims())
                new_field = set_overlay_entry(cmp.outcome_equity_dimensions, eid, dims)
                new_ms = replace_compartment_overlays(ms, cid, outcome_equity_dimensions=new_field)
            state.active_multises.set(new_ms)
            ui.notification_show("Saved ✓", duration=3)
        except (_ChannelValidationError, ValueError, KeyError, TypeError) as e:
            ui.notification_show(f"Could not save: {e}", type="error", duration=6)
```

- [ ] **Step 4: Run to verify the UI test passes + import smoke**

Run: `micromamba run -n shiny python -m pytest tests/test_compartments_module.py -q`
Expected: PASS. Then `micromamba run -n shiny python -c "import app"` → no error.

- [ ] **Step 5: Commit**

```bash
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): Evaluative scores panel — per-element tenet+equity editor (overlay editors)"
```

---

### Task 9: e2e — both surfaces

**Files:**
- Create: `tests/test_overlay_editors_e2e.py` (mirrors `tests/test_comparative_e2e.py` + `conftest.py` `mosaicses_app_url`)

- [ ] **Step 1: Write the e2e tests**

First open `tests/test_comparative_e2e.py` and `tests/conftest.py` to copy the exact fixture name + Playwright launch idiom used in this repo (the `mosaicses_app_url` session fixture and the `sync_playwright()` pattern). Then create `tests/test_overlay_editors_e2e.py` following that idiom. The two tests:

```python
"""e2e: the overlay editors write to active_multises and the Comparative cards
reflect it. Mirrors the launch + nav idiom in test_comparative_e2e.py."""
from __future__ import annotations

from playwright.sync_api import sync_playwright


def test_topology_tenet_editor_persists(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(mosaicses_app_url, wait_until="networkidle")
        # nav via the dashboard's sespy_nav_<value> buttons (the repo idiom)
        page.click("#sespy_nav_topology")
        # select a governance channel by VALUE on the raw <select> (Playwright
        # select_option works through selectize); nd_to_nl_wfd is a Curonian
        # governance channel id.
        page.locator("#topology-inspector_target").select_option("nd_to_nl_wfd")
        # the conditional tenet editor appears
        page.wait_for_selector("#topology-save_channel_tenets", timeout=30_000)
        page.locator("#topology-tenet_ecological").select_option("5")
        page.click("#topology-save_channel_tenets")
        # Comparative reflects a tenet-readiness row (row-level assertion)
        page.click("#sespy_nav_comparative")
        page.wait_for_selector("#comparative-tenet_table tbody tr", timeout=30_000)
        browser.close()


def test_compartments_equity_editor_persists(mosaicses_app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(mosaicses_app_url, wait_until="networkidle")
        page.click("#sespy_nav_compartments")
        # drill into the lagoon, which has GB001 = "Lagoon fishery" (Goods &
        # Benefits = an outcome element)
        page.locator("#compartments-compartment_picker").select_option("curonian_lagoon")
        # open the nested "Evaluative scores" tab (nested navset — text click is fine)
        page.click("text=Evaluative scores")
        # pick the outcome element by VALUE (element id)
        page.locator("#compartments-overlay_element").select_option("GB001")
        page.wait_for_selector("#compartments-equity_dims", timeout=30_000)
        page.check("#compartments-equity_dims input[value='livelihood_displacement']")
        page.click("#compartments-save_overlay")
        page.click("#sespy_nav_comparative")
        page.wait_for_selector("#comparative-equity_table", timeout=30_000)
        # the display label appears after the equity_table renderer maps the slug
        assert "Livelihood displacement" in page.content()
        browser.close()
```

> Selectors use the repo's proven idiom: dashboard nav via `#sespy_nav_<value>` (verify the exact ids by inspecting `test_comparative_e2e.py` / `test_cross_view_e2e.py`), and `select_option(<value>)` on the raw `<select>` (Playwright drives the underlying element even when selectize wraps it — this is how `test_comparative_e2e.py` drives the metric select). If a selector still can't be made stable against the live DOM, fall back to a row-level / `page.content()` text assertion (the spec permits row-level), but do NOT weaken to a tautology, and do NOT fake a pass — fix against the real DOM.

- [ ] **Step 2: Run the e2e**

Run: `micromamba run -n shiny python -m pytest tests/test_overlay_editors_e2e.py -q`
Expected: PASS (2 passed). If the harness boots its own server, this runs ~30–60s. If a selector needs adjustment, fix it against the live DOM (do not fake a pass) and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_overlay_editors_e2e.py
git commit -m "test(mosaicses): e2e for the overlay editors (Topology + Compartments)"
```

---

### Task 10: Full-suite verification + mark spec implemented

**Files:**
- Modify (SESPy repo): `docs/superpowers/specs/2026-06-13-mosaicses-phase2-overlay-editors-design.md` (Status → Implemented)

- [ ] **Step 1: Run the full MosaicSES unit suite**

Run (MosaicSES root): `micromamba run -n shiny python -m pytest tests/ -q --ignore=tests/test_comparative_e2e.py --ignore=tests/test_overlay_editors_e2e.py`
Expected: PASS (all prior + new `test_overlay_editors.py`, `test_overlay_edit.py`, extended module tests). Then run the e2e files (they boot the app): `micromamba run -n shiny python -m pytest tests/test_overlay_editors_e2e.py -q`.

- [ ] **Step 2: Manual smoke (recommended)**

Boot the app; on Topology, select a governance channel → edit a tenet → Save → confirm the Comparative "Tenet readiness" reflects it. On Compartments → Evaluative scores, score a Response and tag an outcome's equity → Save → confirm "Emerald Justice exposure" reflects it.

- [ ] **Step 3: Mark the spec implemented (SESPy repo)**

In the SESPy repo, edit `docs/superpowers/specs/2026-06-13-mosaicses-phase2-overlay-editors-design.md`: set the `**Status:**` line to:

```markdown
**Status:** **Implemented** ✓ — shipped in MosaicSES `main`; full unit suite green + overlay-editor e2e green.
```

- [ ] **Step 4: Commit (SESPy repo)**

```bash
git add docs/superpowers/specs/2026-06-13-mosaicses-phase2-overlay-editors-design.md
git commit -m "docs(spec): mark overlay-editors as implemented (shipped to MosaicSES)"
```

---

## Self-Review

**Spec coverage (every spec section → task):**
- §2.1 `replace_channel` → Task 1 ✓
- §2.2 `replace_compartment_overlays` (+ `_UNSET`) → Task 2 ✓; re-export → Task 3 ✓
- §2.3 `overlay_edit.py` (`assemble_tenet_scores`, `set_overlay_entry`, None-normalization, empty-collapse) → Task 4 ✓
- §2.4 write-back (active_multises.set only; no project refresh; no emit_isa_change; try/except incl. TypeError; "scores cleared" message) → Tasks 6 & 8 ✓
- §3 Topology editor (direct Channel lookup; governance gate render+save; stamped id; non-gov read-only note; `@render.ui` inputs; `— not scored (gap)`) → Tasks 5 (pure builder + gating) & 6 (mount/render/save) ✓
- §4 Compartments panel (eligible elements; select-then-edit; branch-before-read; stamped id; save-time existence + cid-None guard; repopulation effect; no `req()` needed) → Tasks 7 (builders) & 8 (panel/effects) ✓
- §5 validation/error handling/normalization → Tasks 4, 6, 8 ✓
- §6 tests (library; app-pure; module render/gating positive+negative; e2e per surface; no effect tests) → Tasks 1–9 ✓ (gating positive+negative = Task 5; UI mounts = Tasks 6/8; e2e = Task 9)
- §7 files-touched → all covered across tasks ✓
- §9 DoD → Task 10 verification ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. The only "match the existing idiom" notes are for e2e selectors/fixture (house-specific Playwright wiring) — they point at concrete existing e2e files to copy, with a stated row-level fallback the spec already permits.

**Type/name consistency:** `replace_channel`, `replace_compartment_overlays`, `_UNSET`, `assemble_tenet_scores`, `set_overlay_entry`, `TENET_SCORE_CHOICES`, `_tenet_editor_ui`, `_eligible_overlay_elements`, `_overlay_editor_ui`, and the input ids `tenet_<slug>` / `channel_tenet_editing_id` / `save_channel_tenets` / `overlay_element` / `overlay_editor` / `overlay_editing_id` / `equity_dims` / `save_overlay` are used identically across tasks and match the spec. The pure-builder-plus-thin-wrapper split (Tasks 5/6 and 7/8) is the established topology.py pattern (`_inspector_node_info`, `_network_table_ui`).

**Post-review corrections (3rd review loop):** (1) test imports split across Tasks 1/2 so the append-style `test_overlay_editors.py` always COLLECTs at each verify-fail step; (2) the duplicated tenet-select choices extracted to a single `TENET_SCORE_CHOICES` constant in `overlay_edit.py`; (3) dynamic input reads use `getattr(input, f"tenet_{slug}")()` (local idiom); (4) e2e selectors corrected to the repo idiom (`#sespy_nav_<value>` nav + `select_option(<value>)` on the raw `<select>` + deterministic lagoon/GB001 drill-in); (5) `OUTCOME_ELEMENT_TYPES` import dependency on Task 7 noted in Task 8; (6) decisive `import dataclasses`. **On `reactive.isolate()` (spec §5):** not added — the save effects are `@reactive.event(input.save_*)`-gated, which already isolates the body from its reactive reads, so explicit `isolate()` is redundant here.
