# MosaicSES Phase-2 — Evaluative-Overlay Editors — Design

**Repository:** `razinkele/MosaicSES` (code: `multises/data_structure.py` + `multises_app/modules/{topology,compartments}.py`; this spec + plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-13
**Status:** **Planned** — not yet implemented.
**Parent:** the read→edit follow-up explicitly deferred by both shipped overlay increments — [`2026-06-09-mosaicses-phase2-tenets-design.md`](2026-06-09-mosaicses-phase2-tenets-design.md) §11 ("Tenet **editor** UI") and [`2026-06-13-mosaicses-phase2-emerald-justice-design.md`](2026-06-13-mosaicses-phase2-emerald-justice-design.md) §11 ("Equity **editor** UI"). Backlog context: parent design [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11.

## 1. Goal & scope

Both evaluative overlays — the 10-tenets scores (#19) and the Emerald Justice equity dimensions (#20) — are currently **read-only** (rendered in the Comparative dashboard, populated only via seeds/JSON). This increment makes them **editable in-app**, completing the read→edit arc. Three editors across two existing modules, backed by two new pure write-back helpers.

The three overlays and their edit homes:

| Overlay | Field | Element/channel | Edit home |
|---|---|---|---|
| Governance-channel tenets | `Channel.tenet_scores: dict[str,int]` | governance channels | **Topology** inspector |
| Response tenets | `Compartment.response_tenet_scores: dict[str, dict[str,int]]` (keyed by Response element id) | Response elements | **Compartments** "Evaluative scores" panel |
| Outcome equity dims | `Compartment.outcome_equity_dimensions: dict[str, list[str]]` (keyed by outcome element id) | outcome elements (`type ∈ {"Ecosystem Services","Goods & Benefits"}`) | **Compartments** "Evaluative scores" panel |

### 1.1 In scope
- Two pure library helpers in `multises/data_structure.py`: `replace_channel` and `replace_compartment_overlays` (re-exported from `multises/__init__.py`).
- Editor 1: governance-channel tenet editor in the Topology inspector.
- Editor 2/3: per-element tenet + equity editors in a new Compartments "Evaluative scores" panel (select-then-edit).
- In-memory persistence: each Save writes the validated edit straight to `state.active_multises`; durability via the **existing** manual "Save (download .json)". No autosave (matches every other edit in the app).
- Library unit tests (both helpers), module tests (editor render + save mutates `active_multises`), and one e2e per surface.

### 1.2 Out of scope (deferred)
- **No autosave / server-side file write** — durability stays manual, consistent with the current app (the library `multises.persistence.save()` exists but is not called from the Shiny app).
- **No SESPy changes** — the SESPy `isa_data_entry` element editor is not modified; the overlay editors live entirely in the MosaicSES layer.
- **No new schema / no `MULTISES_SCHEMA_VERSION` bump** — pure in-memory edits to existing fields.
- Bulk/grid editing, undo/redo, weighting, and editing tenet scores on non-governance channels (tenet scoring is meaningful only on governance channels — §3).

## 2. Architecture — two pure write-back helpers

The app mutates `MultiSES` only through pure helpers (the library never imports Shiny). Today `replace_compartment(ms, compartment_id, new_project)` (`data_structure.py:843`) edits a compartment's **project** and deliberately **preserves** its overlay fields — so it cannot edit the overlays themselves. And there is **no** channel-update helper at all (`add_channel` only appends; verified — no `replace_channel` in the codebase). This increment adds both, mirroring `replace_compartment`'s pure-function style.

### 2.1 `replace_channel`
```python
def replace_channel(ms: MultiSES, channel_id: str, new_channel: Channel) -> MultiSES:
    """Return a NEW MultiSES with the channel `channel_id` replaced by
    `new_channel` (pure — does not mutate `ms`). Raises KeyError if no channel
    has that id. `new_channel` is validated at its own construction
    (Channel.__post_init__); callers should preserve source/target so the
    MultiSES stays endpoint-consistent. Compartments are shared by reference."""
```
Locate the channel index by id (KeyError if absent); build a new channels list with the swap; return `MultiSES(metadata=ms.metadata, compartments=ms.compartments, channels=new_channels)`.

### 2.2 `replace_compartment_overlays`
```python
_UNSET = object()  # module-level sentinel — distinguishes "leave unchanged" from "set to None"

def replace_compartment_overlays(
    ms: MultiSES, compartment_id: str, *,
    response_tenet_scores=_UNSET, outcome_equity_dimensions=_UNSET,
) -> MultiSES:
    """Return a NEW MultiSES with the named compartment's overlay field(s)
    overridden (pure). Fields left at the _UNSET sentinel are preserved from
    the existing compartment. Internally uses dataclasses.replace(old, ...),
    which re-runs Compartment.__post_init__ (so M206/M207 validation fires).
    The compartment's project and every other field are preserved. Raises
    KeyError if no compartment has that id."""
```
Find the compartment (KeyError if absent); `new_c = dataclasses.replace(old, **changes)` where `changes` includes only the non-`_UNSET` overlay fields; return `MultiSES(...)` with the compartment swapped. (`dataclasses.replace` re-passes `project` and `_unknown_archetype_original` unchanged and re-validates via `__post_init__`.)

Both are re-exported from `multises/__init__.py` (`replace_channel`, `replace_compartment_overlays`) alongside `replace_compartment`.

### 2.3 Shared write-back & persistence
Every editor's Save path is:
1. Build the updated object with `dataclasses.replace(old, field=new_value)` (channel) or pass the new overlay dict to the helper — construction re-runs the hard validators (`_validate_tenet_scores` / `_validate_equity_dimensions`), so an invalid edit raises before any state write.
2. `new_ms = replace_channel(...)` / `replace_compartment_overlays(...)`.
3. `state.active_multises.set(new_ms)` — and **nothing else**.
4. `ui.notification_show("Saved ✓")` (or `type="error"` on a caught validation error).

**Why `active_multises.set` only (no `emit_isa_change`).** The Comparative cards (`tenet_table`/`equity_table`), the Topology meta-graph, and Cross-view all read `state.active_multises.get()` inside their render functions, so they are already reactive on it — setting it re-renders them. The element editor uses `emit_isa_change` because it edits the *project* reactive (`active_compartment_project`) and needs the `_backwrite_to_multises` listener (`compartments.py:262-346`) to fold the project into `active_multises` via `replace_compartment`. Overlay edits target *compartment-level fields directly on `active_multises`*, so they skip that indirection. Deliberately not emitting `isa_change` also avoids a redundant backwrite. **Consistency note:** even if a later element edit *does* fire the backwrite, `replace_compartment` preserves `response_tenet_scores`/`outcome_equity_dimensions` from the (already-overlay-updated) `active_multises`, so the two paths never clobber each other.

## 3. Editor 1 — governance-channel tenet scores (Topology inspector)

The Topology inspector sidebar (`topology_inspector_sb`, `topology.py:~284`) already selects a channel via `inspector_target` and renders a read-only `<dl>` in `inspector_detail` (`topology.py:376-411`). Add an editor that appears **only when the selected target is a governance channel** (`channel_type == "governance"`):

- A new `@render.ui` output (e.g. `inspector_tenet_editor`) rendering **10 `ui.input_select`** controls, one per tenet in canonical `TENETS` order, choices `{"": "—", "1":"1", … "5":"5"}` (`—` = unset/gap, because partial scoring is valid per #19), each pre-filled from the channel's current `tenet_scores.get(slug)`.
- A `ui.input_action_button("save_channel_tenets", "Save scores")`.
- Server `@reactive.effect @reactive.event(input.save_channel_tenets)`: read the 10 selects → assemble `{slug: int(v) for slug,v in … if v}` (omitting `—`) → `new_ch = dataclasses.replace(old_ch, tenet_scores=new_scores or None)` (a fully-unset channel stores `None`, not `{}`) → `replace_channel(ms, ch_id, new_ch)` → `active_multises.set`. Wrap construction in `try/except (_ChannelValidationError, ValueError)` → error notification.

Non-governance channels and compartment targets render nothing (the inspector stays read-only for them). Tenet scoring on non-governance channels is out of scope (§1.2).

## 4. Editors 2 & 3 — per-element overlays (Compartments "Evaluative scores" panel)

The Compartments module mounts an "Edit Data" tab (SESPy `isa_data_entry_ui("entry")`, `compartments.py:78`) and a top-bar summary; it does **not** currently surface overlay values. Add a sibling panel **"Evaluative scores"**, scoped to the drilled-in compartment (`state.active_compartment_id`), using **select-then-edit** (mirroring the Topology inspector):

- `ui.input_select("overlay_element", …)` whose choices are the active compartment's **eligible** elements — Response elements (`type == "Responses"`) and outcome elements (`type ∈ OUTCOME_ELEMENT_TYPES`) — labelled `"{label} ({type})"`, value = element id. Reactively recomputed from `active_multises` + `active_compartment_id`.
- A conditional `@render.ui` editor keyed on the selected element's type:
  - **Response → tenet editor:** 10 `ui.input_select` (`—/1–5`), pre-filled from `response_tenet_scores.get(eid, {})`.
  - **Outcome → equity editor:** one `ui.input_checkbox_group("equity_dims", choices={slug: label})` over the 6 `EQUITY_DIMENSIONS`, pre-checked from `outcome_equity_dimensions.get(eid, [])`.
- One `ui.input_action_button("save_overlay", "Save")`.

Server `@reactive.effect @reactive.event(input.save_overlay)`:
- Resolve the selected element + its type from the active compartment.
- **Response:** build `scores` from the 10 selects; update the compartment's `response_tenet_scores` dict → set `eid → scores` if non-empty, else **remove** the `eid` key (don't store empty dicts); call `replace_compartment_overlays(ms, cid, response_tenet_scores=updated_dict)`.
- **Outcome:** read `equity_dims`; update `outcome_equity_dimensions` → set `eid → list` if non-empty, else **remove** the `eid` key (an empty selection clears the element); call `replace_compartment_overlays(ms, cid, outcome_equity_dimensions=updated_dict)`.
- `active_multises.set(new_ms)`; success/error notification (construction validates via `__post_init__`).

Because the editor only ever targets **existing** element ids (drawn from the live element list), it never creates orphan overlay keys, so the soft `W304`/`W305` referential warnings stay quiet by construction.

## 5. Validation & error handling
- All writes flow through `Channel(...)` / `Compartment(...)` construction (`dataclasses.replace`), so the hard validators fire automatically: `_validate_tenet_scores` (`data_structure.py:200-223`, M206, ints 1–5, partial OK) and `_validate_equity_dimensions` (`data_structure.py:226-249`, M207, slugs ∈ `EQUITY_SLUGS`, no dup, empty OK). The UI cannot construct an out-of-range value (selects only offer `—/1–5`; checkboxes only offer valid slugs), so the validators are a backstop, not the primary guard.
- A caught `_ChannelValidationError`/`ValueError`/`KeyError` surfaces as `ui.notification_show(..., type="error")`; the state is not mutated.
- Empty edits normalize to **absent** (key removed / `None`), keeping overlays free of empty stubs.

## 6. Testing

### Library unit tests (`tests/test_overlay_editors.py`, new)
- `replace_channel`: swaps a channel's `tenet_scores` and returns a new MultiSES (original unmutated); unknown id → `KeyError`; the swapped channel round-trips through `to_json`/`from_json`; an invalid `new_channel` can't be constructed (validation is at `Channel(...)`, demonstrated separately).
- `replace_compartment_overlays`: override `response_tenet_scores` only (leaves `outcome_equity_dimensions` and project untouched); override `outcome_equity_dimensions` only; override both; `_UNSET` preserves; unknown id → `KeyError`; an out-of-range tenet / bad slug raises (via `dataclasses.replace` → `__post_init__`); the project object identity is preserved; round-trip lossless.

### Module tests
- `tests/test_topology_module.py` (extend): the inspector renders the tenet editor (`inspector_tenet_editor` / `save_channel_tenets`) when a governance channel is the target, and renders nothing for a non-governance channel / compartment target.
- `tests/test_compartments_module.py` (extend): the "Evaluative scores" panel exists with `overlay_element` + `save_overlay`; selecting a Response shows the tenet editor, selecting an outcome shows the equity checkbox group.
- Save behavior (module-level, using the SESPy/Shiny test harness pattern already used for backwrite tests): invoking the save effect with chosen inputs produces a new `active_multises` whose channel/compartment carries the edited overlay; an empty edit removes the key.

### e2e (`tests/`)
- Topology: select a governance channel, set a tenet score, Save → the value persists in the inspector and the Comparative "Tenet readiness" table reflects it.
- Compartments: drill into a compartment, select an outcome element, check an equity dimension, Save → the Comparative "Emerald Justice exposure" table reflects it.

## 7. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `_UNSET` sentinel; `replace_channel`; `replace_compartment_overlays` |
| `multises/__init__.py` | re-export `replace_channel`, `replace_compartment_overlays` (import block + `__all__`) |
| `multises_app/modules/topology.py` | governance-channel tenet editor in the inspector (`inspector_tenet_editor` UI + `save_channel_tenets` effect + `replace_channel` write-back) |
| `multises_app/modules/compartments.py` | "Evaluative scores" panel (`overlay_element` select + conditional tenet/equity editor + `save_overlay` effect + `replace_compartment_overlays` write-back) |
| `tests/test_overlay_editors.py` (new) | helper unit tests |
| `tests/test_topology_module.py` | inspector tenet-editor render/gating |
| `tests/test_compartments_module.py` | Evaluative-scores panel render + save |
| `tests/test_*_e2e.py` | one e2e per surface |

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `replace_channel` is a brand-new primitive (no precedent) | Medium | Pure, tiny, mirrors `replace_compartment`; dedicated unit tests first; only `tenet_scores` changes (endpoints preserved → MultiSES stays consistent) |
| Overlay edit clobbered by a later element-edit backwrite | Low | `replace_compartment` preserves overlay fields from the current `active_multises`; documented in §2.3 |
| Reusing the wrong update granularity (storing empty `{}`/`[]` stubs) | Low | Empty edits remove the key (§4) |
| Topology inspector layout already complex (Inspector sidebar) | Medium | Editor is an additive `@render.ui` gated on governance type; no restructure of existing detail render |
| Scope: three editors + two modules in one spec | Medium (accepted) | Plan sequences as separable tasks: helpers → channel editor → per-element panel; each independently testable |
| `dataclasses.replace` re-passing `project`/`_unknown_archetype_original` | Low | Both are normal dataclass fields; `replace` preserves them; round-trip test guards |

## 9. Definition of done
- `replace_channel` + `replace_compartment_overlays` in the library, re-exported, unit-tested (incl. KeyError + validation propagation + round-trip + pure-ness).
- Topology inspector edits a governance channel's tenet scores (partial allowed; `—` = unset) and persists to `active_multises`.
- Compartments "Evaluative scores" panel edits Response tenet scores and outcome equity dimensions (select-then-edit), empties removed, persists to `active_multises`.
- Comparative cards reactively reflect every edit; durability via the existing manual download; no autosave; no schema bump; SESPy untouched.
- Full unit suite green + module tests + one e2e per surface.

## 10. Out-of-scope follow-ups
- Autosave / server-side persistence (would be its own design).
- Editable data-grid / bulk entry; undo-redo.
- Tenet scoring on non-governance channels (if ever needed).
- Tenet/equity **weighting** + composite indices (already deferred by #19/#20).
