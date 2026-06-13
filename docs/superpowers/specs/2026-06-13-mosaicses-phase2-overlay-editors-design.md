# MosaicSES Phase-2 — Evaluative-Overlay Editors — Design

**Repository:** `razinkele/MosaicSES` (code: `multises/data_structure.py`, new `multises_app/overlay_edit.py`, `multises_app/modules/{topology,compartments}.py`; this spec + plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-13
**Status:** **Planned** — not yet implemented. (Revised after a 4-angle review: code-integration, Shiny/UX, test-readiness, design-consistency.)
**Parent:** the read→edit follow-up explicitly deferred by both shipped overlay increments — [`2026-06-09-mosaicses-phase2-tenets-design.md`](2026-06-09-mosaicses-phase2-tenets-design.md) §11 ("Tenet **editor** UI") and [`2026-06-13-mosaicses-phase2-emerald-justice-design.md`](2026-06-13-mosaicses-phase2-emerald-justice-design.md) §11 ("Equity **editor** UI"). Backlog: parent design [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11.

## 1. Goal & scope

Both evaluative overlays — the 10-tenets scores (#19) and the Emerald Justice equity dimensions (#20) — are currently **read-only** (rendered in the Comparative dashboard, populated only via seeds/JSON). This increment makes them **editable in-app**, completing the read→edit arc. Three editors across two existing modules, backed by two new pure library helpers and a new pure app-layer assembly module.

| Overlay | Field | Element/channel | Edit home |
|---|---|---|---|
| Governance-channel tenets | `Channel.tenet_scores: dict[str,int] \| None` | governance channels | **Topology** inspector |
| Response tenets | `Compartment.response_tenet_scores: dict[str, dict[str,int]] \| None` (keyed by Response element id) | Response elements | **Compartments** "Evaluative scores" panel |
| Outcome equity dims | `Compartment.outcome_equity_dimensions: dict[str, list[str]] \| None` (keyed by outcome element id) | outcome elements (`type ∈ OUTCOME_ELEMENT_TYPES`) | **Compartments** "Evaluative scores" panel |

`OUTCOME_ELEMENT_TYPES = ("Ecosystem Services", "Goods & Benefits")` is the existing constant introduced by #20 (`data_structure.py`, re-exported from `multises`).

### 1.1 In scope
- Two pure **library** helpers in `multises/data_structure.py` — `replace_channel`, `replace_compartment_overlays` — re-exported from `multises/__init__.py` (module-level functions, like the existing `replace_compartment`).
- A new pure **app-layer** module `multises_app/overlay_edit.py` holding `assemble_tenet_scores` and `set_overlay_entry` — Shiny-free, unit-testable, and the single home of the "cleared → `None`" normalization. The Shiny effects are thin wrappers over these (mirroring the `project_setup._build_new_*` precedent).
- Editor 1: governance-channel tenet editor in the Topology inspector.
- Editors 2/3: per-element tenet + equity editors in a new Compartments "Evaluative scores" panel (select-then-edit).
- In-memory persistence: each Save writes the validated edit to `state.active_multises`; durability via the **existing** manual "Save (download .json)". No autosave.
- Library + app-helper unit tests, module render/gating tests, and e2e per surface.

### 1.2 Out of scope (deferred)
- No autosave / server-side write (durability stays manual — consistent with the app today).
- No SESPy changes (the `isa_data_entry` element editor is untouched).
- No schema / no `MULTISES_SCHEMA_VERSION` bump.
- Bulk/grid editing, undo/redo, tenet scoring on non-governance channels, weighting/composite indices.

## 2. Architecture

The library never imports Shiny; all `MultiSES` mutation goes through pure helpers. Today `replace_compartment(ms, compartment_id, new_project)` (module-level, `data_structure.py:843`) edits a compartment's **project** and deliberately **preserves** its overlay fields (`data_structure.py:879-880`) — so it cannot edit the overlays. And there is **no** channel-update helper (`add_channel` only appends; no `replace_channel` exists anywhere). This increment adds both, mirroring `replace_compartment`'s pure style, plus an app-layer assembly module so the editor logic is testable without a Shiny session.

### 2.1 `replace_channel` (library)
```python
def replace_channel(ms: MultiSES, channel_id: str, new_channel: Channel) -> MultiSES:
    """Return a NEW MultiSES with channel `channel_id` replaced by `new_channel`
    (pure — does not mutate `ms`). Raises KeyError if no channel has that id.
    `new_channel` is validated at its own construction (Channel.__post_init__).
    The returned MultiSES is built via MultiSES(...), which re-runs its
    __post_init__ integrity checks (M201 dangling endpoints, dup ids) — so a
    caller that changed source/target to a non-existent compartment is caught.
    Editors only change tenet_scores, leaving endpoints intact."""
```
Locate channel index by id (KeyError if absent); build a new channels list with the swap; return `MultiSES(metadata=ms.metadata, compartments=ms.compartments, channels=new_channels)`. (Compartments are reused by reference; the app never mutates them in place, so no copy is needed.)

### 2.2 `replace_compartment_overlays` (library)
```python
_UNSET = object()  # module-level sentinel: "leave unchanged" vs an explicit value (incl. None)

def replace_compartment_overlays(
    ms: MultiSES, compartment_id: str, *,
    response_tenet_scores=_UNSET, outcome_equity_dimensions=_UNSET,
) -> MultiSES:
    """Return a NEW MultiSES with the named compartment's overlay field(s)
    overridden (pure). A field left at `_UNSET` is preserved; passing an
    explicit value (including None) sets it. Uses dataclasses.replace(old, ...),
    which re-runs Compartment.__post_init__ (M206/M207 fire on bad input). The
    compartment's project and every other field are preserved. KeyError if no
    compartment has that id."""
```
Find the compartment (KeyError if absent); `new_c = dataclasses.replace(old, **changes)` where `changes` carries only the non-`_UNSET` fields; return `MultiSES(...)` with the compartment swapped. `dataclasses.replace` re-passes `project` and `_unknown_archetype_original` (both real fields) and re-validates — cleaner than the `object.__setattr__` dance in `replace_compartment`.

Both are re-exported from `multises/__init__.py` (import block + `__all__`). **`_UNSET` is internal** to `data_structure.py` — not exported; tests exercise "preserve" by **omitting** the argument, not by importing the sentinel.

### 2.3 `multises_app/overlay_edit.py` (app-layer pure helpers — the testable core)
Shiny-free pure functions that own all input-assembly + normalization. This is the key to TDD: the repo has no in-harness way to fire a `@reactive.effect` (all module tests are pure-helper or source-inspection), so the editors' logic lives here and is unit-tested directly; the effects become thin wrappers.

```python
from multises.data_structure import TENET_SLUGS  # (and EQUITY_SLUGS if needed for guards)

def assemble_tenet_scores(values: dict[str, str]) -> dict[str, int] | None:
    """Map {tenet_slug: "" | "1".."5"} -> {slug: int}, dropping blanks.
    Returns None when nothing is set (the canonical 'no scores' shape — never {})."""
    scores = {s: int(v) for s, v in values.items() if v}
    return scores or None

def set_overlay_entry(existing: dict | None, key: str, value) -> dict | None:
    """Return a new overlay dict with `key` set to `value`, or `key` REMOVED when
    `value` is falsy (None / empty dict / empty list). Returns None when the
    resulting dict is empty — so a compartment overlay field never carries an
    empty stub and 'all cleared' normalizes to None, matching the Channel
    convention. Pure; does not mutate `existing`."""
    d = dict(existing or {})
    if value:
        d[key] = value
    else:
        d.pop(key, None)
    return d or None
```

### 2.4 Shared write-back & persistence
Every Save effect is a thin wrapper:
1. **Assemble** the new value with the §2.3 helpers (validation-safe shapes; "cleared" → `None`).
2. **Build** the mutated object: channel via `dataclasses.replace(old_ch, tenet_scores=scores)`; compartment overlays via passing the assembled dict to `replace_compartment_overlays`. Construction re-runs the hard validators.
3. `new_ms = replace_channel(...)` / `replace_compartment_overlays(...)`, wrapped in `try/except (_ChannelValidationError, ValueError, KeyError)` → on error, `ui.notification_show(..., type="error")` and **no** state write.
4. `state.active_multises.set(new_ms)`; for the Compartments editor **also** `state.active_compartment_project.set(new_ms.compartment(cid).project)` (keep the project reactive coherent with the new MultiSES — see §4); then a success notification.

`_ChannelValidationError` is private to `data_structure.py`; the editor modules import it directly (`from multises.data_structure import _ChannelValidationError`), the same established reach already used for `replace_compartment` in `compartments.py:40`.

**Why `active_multises.set` only (no `emit_isa_change`).** The Comparative cards (`tenet_table`/`equity_table`), the Topology inspector detail + meta-graph, and Cross-view all read `state.active_multises.get()` inside their renders, so `.set()` re-renders them. The element editor uses `emit_isa_change` only because it edits the *project* reactive and needs the `_backwrite_to_multises` listener (`compartments.py:262-346`) to fold the project into `active_multises` via `replace_compartment`. Overlay edits target compartment/channel fields directly, so they skip that path. Emitting `isa_change` here would be **wrong**: the backwrite is `@reactive.event(isa_change)` and would immediately overwrite the overlay edit with `replace_compartment(current_ms, cid, edited_project)`. (That backwrite *preserves* overlay fields from the current `active_multises`, so once our edit is in `active_multises`, a *later, unrelated* element edit won't clobber it.)

## 3. Editor 1 — governance-channel tenet scores (Topology inspector)

The inspector sidebar (`topology_inspector_sb`, `topology.py:284-297`) selects a target via `inspector_target` and renders read-only detail in `inspector_detail` (`topology.py:376-411`). Add a **separate** `@render.ui` output `inspector_tenet_editor` (a definitive output id, asserted by tests) that:

- **Resolves the live channel by id, not via the inspector's display dict.** `_inspector_node_info` does **not** include `tenet_scores`, and its `channel_type` is a display string (may carry `_unknown_channel_type_original`). So: `target = input.inspector_target()`; `ch = next((c for c in ms.channels if c.id == target), None)`; gate on `ch is not None and ch.channel_type == "governance"` (the **validated** field). Otherwise render nothing (non-governance channels and compartment targets get no editor).
- **Renders the inputs inside this `@render.ui`** — never via `ui.update_select`. On every selection change the whole subtree is rebuilt, so inputs carry fresh `selected=` pre-fill and no stale client value bleeds across channels. The inputs: 10 `ui.input_select(f"tenet_{slug}", label, choices={"":"—","1":"1",…,"5":"5"}, selected=str(ch.tenet_scores.get(slug)) if set else "")` in canonical `TENETS` order (`—` = unset/gap; partial scoring is valid per #19), plus `ui.input_action_button("save_channel_tenets", "Save scores")`.

Server effect `@reactive.effect @reactive.event(input.save_channel_tenets)`: re-resolve `ms`, `ch`; `scores = assemble_tenet_scores({slug: input[f"tenet_{slug}"]() for slug in TENET_SLUGS})`; `new_ch = dataclasses.replace(ch, tenet_scores=scores)` (→ `None` when fully unset); `replace_channel(ms, ch.id, new_ch)`; write-back per §2.4. Wrapped in the §2.4 try/except.

## 4. Editors 2 & 3 — per-element overlays (Compartments "Evaluative scores" panel)

The Compartments `navset_tab` (`compartments.py:77-90`) holds an "Edit Data" tab (SESPy `isa_data_entry_ui("entry")`, line 78); it does not surface overlays. Add a sibling `ui.nav_panel("Evaluative scores", …)` scoped to the drilled-in compartment (`state.active_compartment_id`), using **select-then-edit**:

- `ui.input_select("overlay_element", …)` whose choices are the active compartment's **eligible** elements — Responses (`type == "Responses"`) and outcomes (`type ∈ OUTCOME_ELEMENT_TYPES`) — labelled `"{label} ({type})"`, value = element id; recomputed reactively from `active_multises` + `active_compartment_id`.
- A `@render.ui` output `overlay_editor` keyed on the selected element id that **renders the matching inputs inline** (not via `update_*`), pre-filled from the current overlay:
  - **Response → tenet editor:** 10 `ui.input_select(f"tenet_{slug}", …)` pre-filled from `response_tenet_scores.get(eid, {})`.
  - **Outcome → equity editor:** `ui.input_checkbox_group("equity_dims", choices={slug: label for slug,label in EQUITY_DIMENSIONS}, selected=outcome_equity_dimensions.get(eid, []))`.
- One `ui.input_action_button("save_overlay", "Save")`.

Server effect `@reactive.effect @reactive.event(input.save_overlay)`: resolve `cid`, the selected element + its **type**, then **branch before reading inputs** (Shiny raises on reading an unregistered input, so read tenet inputs only in the Response branch and `equity_dims` only in the outcome branch):
- **Response:** `scores = assemble_tenet_scores({slug: input[f"tenet_{slug}"]() …})`; `new_field = set_overlay_entry(cmp.response_tenet_scores, eid, scores)`; `replace_compartment_overlays(ms, cid, response_tenet_scores=new_field)`.
- **Outcome:** `dims = list(input.equity_dims() or [])`; `new_field = set_overlay_entry(cmp.outcome_equity_dimensions, eid, dims)`; `replace_compartment_overlays(ms, cid, outcome_equity_dimensions=new_field)`.
- Write-back per §2.4 (incl. `active_compartment_project.set(new_ms.compartment(cid).project)`); try/except.

Because the editor only targets **existing** element ids, it never creates orphan overlay keys (so `W304`/`W305` stay quiet by construction). `set_overlay_entry` guarantees the field normalizes to `None` when the last element is cleared — never an empty `{}` stub.

## 5. Validation, error handling, normalization
- All writes pass through `Channel(...)` / `Compartment(...)` construction (`dataclasses.replace`), so `_validate_tenet_scores` (`data_structure.py:200-223`, M206) and `_validate_equity_dimensions` (`data_structure.py:226-249`, M207) fire automatically. The UI only offers valid values, so the validators are a backstop. `Channel.__post_init__` raises plain `ValueError` for some checks; `Compartment` raises `_ChannelValidationError` — both editors catch `(_ChannelValidationError, ValueError, KeyError)`.
- **Normalization invariant (single rule, both layers):** "no scores / no dims" is represented as **`None`**, never `{}`/`[]` stubs. `assemble_tenet_scores` returns `None` when all blank; `set_overlay_entry` removes the per-element key and returns `None` when the field empties. Error feedback uses the app's established `ui.notification_show` idiom (`project_setup.py:237/242`): a success notification on save, an error notification on a caught exception. (When a save clears all scores, the success notification text should make that visible, e.g. "Saved — scores cleared", so an accidental wipe is not silently confirmed.)

## 6. Testing

### Library helpers (`tests/test_overlay_editors.py`, new)
- `replace_channel`: swaps a channel's `tenet_scores`, returns a new MultiSES, original unmutated; unknown id → `KeyError`; **endpoints preserved** (new channel keeps source/target → resulting MultiSES constructs without M201); a `new_channel` with a dangling endpoint → constructing the MultiSES raises (integrity backstop); `tenet_scores=None` stored (not `{}`); partial-scores round-trip via `to_json`/`from_json`.
- `replace_compartment_overlays`: override `response_tenet_scores` only while **omitting** `outcome_equity_dimensions` (asserts the omitted field is preserved unchanged); override the other only; override both; **omit both** (identity); explicit `response_tenet_scores=None` clears the field (distinct from the omit/preserve case); unknown id → `KeyError`; an out-of-range tenet / bad slug raises via `__post_init__`; `project` object identity preserved; round-trip lossless; a fixture compartment loaded with a **placeholder archetype** (`_unknown_archetype_original` set) survives `dataclasses.replace`.
- Interleaving: on one MultiSES, `replace_compartment_overlays` then `replace_channel` (and vice-versa) leave each other's fields intact.

### App-layer pure helpers (`tests/test_overlay_edit.py`, new)
- `assemble_tenet_scores`: all-blank → `None`; partial (`{"ecological":"5","legal":"","political":"2"}`) → `{"ecological":5,"political":2}`; full → 10-key dict; values are `int`.
- `set_overlay_entry`: set new key; overwrite existing; falsy value (`None`/`{}`/`[]`) removes the key; removing the last key returns `None`; does not mutate the input dict.

### Module render/gating (`tests/test_topology_module.py`, `tests/test_compartments_module.py`, extend)
- Topology: `inspector_tenet_editor` output exists; **named positive** test — for a governance-channel target the editor + `save_channel_tenets` render; **named negative** test — for a non-governance channel (e.g. a nutrients channel) and for a compartment target the editor renders nothing (`"save_channel_tenets" not in html`).
- Compartments: the "Evaluative scores" panel exists with `overlay_element` + `overlay_editor` + `save_overlay`; selecting a Response renders the 10 tenet selects; selecting an outcome renders the `equity_dims` checkbox group.
- (Save-effect behavior is covered by the §2.3/§2.4 pure-helper unit tests + the e2e below; the repo has no in-harness idiom for firing a `@reactive.effect`, so we do not attempt to.)

### e2e (`tests/test_overlay_editors_e2e.py`, new — mirrors `test_comparative_e2e.py` / `conftest.py` `mosaicses_app_url`)
- Topology: open Topology, select a governance channel, **`wait_for_selector`** for the tenet-editor container (it renders conditionally) before setting a `tenet_*` select, click Save, navigate to Comparative, assert "Tenet readiness" reflects the value.
- Compartments: drill into a compartment, open "Evaluative scores", select an outcome element, wait for the `equity_dims` group, check a dimension, Save, navigate to Comparative, assert "Emerald Justice exposure" reflects it.

## 7. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `_UNSET` sentinel; `replace_channel`; `replace_compartment_overlays` |
| `multises/__init__.py` | re-export `replace_channel`, `replace_compartment_overlays` (import block + `__all__`); `_UNSET` stays internal |
| `multises_app/overlay_edit.py` (new) | pure `assemble_tenet_scores`, `set_overlay_entry` (Shiny-free) |
| `multises_app/modules/topology.py` | `inspector_tenet_editor` `@render.ui` (governance-gated, direct Channel lookup) + `save_channel_tenets` effect + `replace_channel` write-back; import `_ChannelValidationError` |
| `multises_app/modules/compartments.py` | "Evaluative scores" nav panel (`overlay_element` + `overlay_editor` + `save_overlay`) + `replace_compartment_overlays` write-back + `active_compartment_project` refresh; import `_ChannelValidationError` |
| `tests/test_overlay_editors.py` (new) | library helper unit tests |
| `tests/test_overlay_edit.py` (new) | app-layer pure-helper unit tests |
| `tests/test_topology_module.py` | inspector tenet-editor render + governance gating (positive + negative) |
| `tests/test_compartments_module.py` | Evaluative-scores panel render |
| `tests/test_overlay_editors_e2e.py` (new) | one e2e per surface |

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `replace_channel` brand-new primitive | Medium | Pure, mirrors `replace_compartment`; unit-tested incl. endpoint integrity; only `tenet_scores` changes |
| Effects untestable in-harness | High (designed around) | All logic in pure helpers (`overlay_edit.py`, §2.3) unit-tested; effects are thin; e2e covers wiring |
| Stale client values across selections | High (avoided) | Inputs rendered inside `@render.ui` keyed on selection; never `ui.update_*` (§3, §4) |
| Gating on display `channel_type` | Medium (avoided) | Gate on the validated `Channel.channel_type` via direct lookup, not the inspector dict (§3) |
| `active_compartment_project` stale after overlay save | Medium | Refresh it on save (§2.4) |
| Empty edit stores `{}` stub instead of `None` | Medium (avoided) | Single normalization rule in `set_overlay_entry`/`assemble_tenet_scores` (§2.3, §5) |
| Reading an unrendered input raises | Medium (avoided) | Branch on element type **before** reading inputs (§4) |
| Silent all-clear wipes scores | Low | Success notification states "scores cleared" (§5) |
| Scope: 3 editors / 2 modules | Medium (accepted) | Plan sequences: helpers + `overlay_edit.py` first (both editors depend on them being merged), then the two editors (independent of each other) |

## 9. Definition of done
- `replace_channel` + `replace_compartment_overlays` in the library, re-exported, unit-tested (swap, KeyError, endpoint integrity, `_UNSET`-omit-preserve, explicit-`None`, validation propagation, round-trip, placeholder-archetype, interleaving).
- `overlay_edit.py` pure helpers unit-tested (assembly, partial, all-blank→`None`, key set/remove, empties→`None`).
- Topology inspector edits a governance channel's tenet scores (gated on the validated field; inputs in `@render.ui`; `—`=unset) and persists to `active_multises`.
- Compartments "Evaluative scores" panel edits Response tenet scores and outcome equity dimensions (select-then-edit; branch-before-read); refreshes `active_compartment_project`; empties normalize to `None`.
- Comparative cards reactively reflect every edit; durability via the existing manual download; no autosave; no schema bump; SESPy untouched.
- Full unit suite green + module render/gating tests + one e2e per surface.

## 10. Out-of-scope follow-ups
- Autosave / server-side persistence (own design).
- Editable data-grid / bulk entry; undo-redo; confirmation modal on full clear.
- Tenet scoring on non-governance channels; weighting / composite indices.
