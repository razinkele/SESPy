# MosaicSES Phase-2 — Evaluative-Overlay Editors — Design

**Repository:** `razinkele/MosaicSES` (code: `multises/data_structure.py`, new `multises_app/overlay_edit.py`, `multises_app/modules/{topology,compartments}.py`; this spec + plan live in `razinkele/SESPy` `docs/superpowers/`).

**Date:** 2026-06-13
**Status:** **Planned** — not yet implemented. (Revised after two review loops: code-integration, Shiny/UX, test-readiness, design-consistency, adversarial edge-case.)
**Parent:** the read→edit follow-up deferred by both shipped overlay increments — [`2026-06-09-mosaicses-phase2-tenets-design.md`](2026-06-09-mosaicses-phase2-tenets-design.md) §11 and [`2026-06-13-mosaicses-phase2-emerald-justice-design.md`](2026-06-13-mosaicses-phase2-emerald-justice-design.md) §11. Backlog: [`2026-05-08-mosaicses-design.md`](2026-05-08-mosaicses-design.md) §11.

## 1. Goal & scope

Both evaluative overlays — the 10-tenets scores (#19) and the Emerald Justice equity dimensions (#20) — are currently **read-only**. This increment makes them **editable in-app**: three editors across two existing modules, backed by two pure library helpers and a pure app-layer assembly module.

| Overlay | Field | Target | Edit home |
|---|---|---|---|
| Governance-channel tenets | `Channel.tenet_scores: dict[str,int] \| None` | governance channels | **Topology** inspector |
| Response tenets | `Compartment.response_tenet_scores: dict[str, dict[str,int]] \| None` (keyed by Response element id) | Response elements (`Element.type == "Responses"`) | **Compartments** "Evaluative scores" panel |
| Outcome equity dims | `Compartment.outcome_equity_dimensions: dict[str, list[str]] \| None` (keyed by outcome element id) | outcome elements (`Element.type ∈ OUTCOME_ELEMENT_TYPES`) | **Compartments** "Evaluative scores" panel |

`"Responses"` and `OUTCOME_ELEMENT_TYPES = ("Ecosystem Services", "Goods & Benefits")` are the **verbatim `Element.type` display strings** already used as literals across the codebase (`response_pressure_gap`, `validate.py`); `OUTCOME_ELEMENT_TYPES`, `TENETS`, `TENET_SLUGS`, `EQUITY_DIMENSIONS` (a tuple of `(slug, label)` pairs), and `EQUITY_SLUGS` are existing constants from #19/#20, re-exported from `multises`.

### 1.1 In scope
- Two pure **library** helpers in `multises/data_structure.py` — `replace_channel`, `replace_compartment_overlays` — re-exported (module-level, like the existing `replace_compartment`).
- A new pure **app-layer** module `multises_app/overlay_edit.py` (`assemble_tenet_scores`, `set_overlay_entry`) — Shiny-free, unit-testable, the single home of the "cleared → `None`" normalization. The Shiny effects are thin wrappers (the `project_setup._build_new_*` precedent).
- Editor 1 (Topology inspector) + Editors 2/3 (Compartments "Evaluative scores" panel, select-then-edit).
- In-memory persistence: Save writes to `state.active_multises`; durability via the existing manual "Save (download .json)". No autosave.
- Library + app-helper unit tests, module render/gating tests, e2e per surface.

### 1.2 Out of scope (deferred)
No autosave/server-side write; no SESPy changes; no schema bump; no bulk/grid editing, undo-redo, confirmation modal; no tenet scoring on non-governance channels; no weighting/composite indices.

## 2. Architecture

The library never imports Shiny; all `MultiSES` mutation goes through pure helpers. `replace_compartment(ms, compartment_id, new_project)` (module-level, `data_structure.py:843`) edits a compartment's **project** and **preserves** its overlay fields — it cannot edit them. There is **no** channel-update helper (`add_channel` only appends). This increment adds both, plus an app-layer assembly module so editor logic is testable without a Shiny session (the repo has no in-harness way to fire a `@reactive.effect`).

### 2.1 `replace_channel` (library)
```python
def replace_channel(ms: MultiSES, channel_id: str, new_channel: Channel) -> MultiSES:
    """Return a NEW MultiSES with channel `channel_id` replaced by `new_channel`
    (pure). KeyError if no channel has that id. `new_channel` is validated at its
    own construction; the returned MultiSES is built via MultiSES(...), which
    re-runs MultiSES.__post_init__ integrity checks (M001/M002 dup ids, M201
    dangling endpoints) — so a swapped channel with a bad endpoint is caught.
    Compartments are reused by reference (the app never mutates them in place)."""
```
Locate the channel index by id (KeyError if absent); swap into a new channels list; return `MultiSES(metadata=ms.metadata, compartments=ms.compartments, channels=new_channels)`.

### 2.2 `replace_compartment_overlays` (library)
```python
_UNSET = object()  # module-level sentinel: "leave unchanged" vs an explicit value (incl. None)

def replace_compartment_overlays(
    ms, compartment_id, *, response_tenet_scores=_UNSET, outcome_equity_dimensions=_UNSET,
) -> MultiSES:
    """Return a NEW MultiSES with the named compartment's overlay field(s)
    overridden (pure). A field at `_UNSET` is preserved; passing an explicit
    value (including None) sets it. Uses dataclasses.replace(old, **changes) —
    which re-runs Compartment.__post_init__ (M206/M207 fire) and re-passes the
    SAME project object and _unknown_archetype_original unchanged. KeyError if no
    compartment has that id."""
```
**`_UNSET` is internal** (not exported); tests exercise "preserve" by **omitting** the argument.

### 2.3 `multises_app/overlay_edit.py` — pure assembly/normalization (the testable core)
Shiny-free. Imports only `TENET_SLUGS` from `multises.data_structure` (no `EQUITY_SLUGS` needed). Owns all input-assembly + the single "cleared → `None`" rule.
```python
def assemble_tenet_scores(values: dict[str, str]) -> dict[str, int] | None:
    """Map {tenet_slug: "" | "1".."5"} -> {slug:int}. The `if v` guard drops
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
- `assemble_tenet_scores` is used by **both** editors (channel + Response). `set_overlay_entry` is used only by the **Compartments** editor (the per-element key/value upsert). The channel editor passes the assembled `dict|None` straight into `dataclasses.replace`.
- **Empty equity list is deliberately collapsed to absent.** `_validate_equity_dimensions` *permits* `[]` (for seed/JSON authors), but in the analysis an outcome with `[]` and an absent outcome are identical (`downstream_equity_outcome_count` counts only non-empty entries). The editor therefore normalizes "no dimensions checked" to absent via `set_overlay_entry` — no behavior change, no empty stubs. Documented so it isn't read as a contradiction.

### 2.4 Shared write-back & persistence
Each Save effect (wrapped in `try/except (_ChannelValidationError, ValueError, KeyError, TypeError)` → error notification + **no** write):
1. **Re-validate the target at save time** (see §3/§4 — the rendered selection may be stale): re-resolve the channel/compartment+element from current state, re-check the gate (governance / element-exists-in-compartment), abort with an error notification if invalid.
2. **Assemble** the new value with §2.3 helpers (`None` when cleared).
3. **Build the new MultiSES**:
   - *Channel path:* `new_ch = dataclasses.replace(old_ch, tenet_scores=scores)`; then `new_ms = replace_channel(ms, ch.id, new_ch)`.
   - *Compartment path:* `new_field = set_overlay_entry(...)`; then `new_ms = replace_compartment_overlays(ms, cid, <field>=new_field)` (the helper does the `dataclasses.replace` internally — the caller does **not** pre-build a Compartment).
4. `state.active_multises.set(new_ms)`; success notification.

**No `active_compartment_project.set(...)`, and no `emit_isa_change`.** The overlay edit changes a compartment/channel field, **not** the project — `replace_compartment_overlays` keeps `.project` as the *same object*, so `active_compartment_project` (already that object) stays coherent. Refreshing it would be gratuitous and could **discard a user's unsaved edits** in the sibling "Edit Data" tab (it rebinds the project reactive that `isa_data_entry` owns) — so it is deliberately omitted. Emitting `isa_change` would be worse: the `_backwrite_to_multises` listener (`@reactive.event(isa_change)`, `compartments.py:262-346`) would immediately overwrite the edit with `replace_compartment(current, cid, edited_project)`. The Comparative cards, Topology inspector/meta-graph, and Cross-view all read `active_multises.get()` in their renders, so a plain `.set()` re-renders them. (A *later, unrelated* element edit's backwrite still preserves overlays, because `replace_compartment` preserves overlay fields — `data_structure.py:879-880`.)

`_ChannelValidationError` is private to `data_structure.py`; the editor modules import it directly (`from multises.data_structure import _ChannelValidationError`), the same reach already used for `replace_compartment` in `compartments.py:40`.

## 3. Editor 1 — governance-channel tenet scores (Topology inspector)

The inspector (`topology_inspector_sb`, `topology.py:284-297`) selects a target via `inspector_target` and renders read-only detail in `inspector_detail` (`topology.py:376-411`). Add a separate `@render.ui` output **`inspector_tenet_editor`** (definitive id) that:

- **Resolves the live Channel by id** (the inspector dict `_inspector_node_info` omits `tenet_scores` and exposes a display-massaged `channel_type`): `target = input.inspector_target()`; `ch = next((c for c in ms.channels if c.id == target), None)`. Gate on `ch is not None and ch.channel_type == "governance"` (the **validated** field); otherwise render nothing.
- **Renders all inputs inside this `@render.ui`** (never `ui.update_select` — that bleeds stale client values across selections). The unit comprises: 10 `ui.input_select(f"tenet_{slug}", label, choices={"":"—","1":"1",…,"5":"5"}, selected=…)` in `TENETS` order (`—`=unset; partial OK per #19), pre-filled from `ch.tenet_scores`; a hidden **`channel_tenet_editing_id`** stamping `ch.id` (so the saved id matches the rendered inputs) — rendered as `ui.input_text("channel_tenet_editing_id", "", value=ch.id)` wrapped/styled `display:none`, NOT a raw `<input type="hidden">` (only a Shiny input widget registers with `input.<id>()`); and `ui.input_action_button("save_channel_tenets", "Save scores")`.

Save effect `@reactive.effect @reactive.event(input.save_channel_tenets)`: read the **stamped** id `cid_ch = input.channel_tenet_editing_id()`; re-resolve `ch = next((c for c in ms.channels if c.id == cid_ch), None)`; **abort (error notification) if `ch is None or ch.channel_type != "governance"`** (save-time re-gate — the inspector target may have changed since render). Else `scores = assemble_tenet_scores({slug: input[f"tenet_{slug}"]() for slug in TENET_SLUGS})`; `new_ch = dataclasses.replace(ch, tenet_scores=scores)`; `replace_channel`; write-back per §2.4.

## 4. Editors 2 & 3 — per-element overlays (Compartments "Evaluative scores" panel)

Add a `ui.nav_panel("Evaluative scores", …)` to the Compartments `navset_tab` (`compartments.py:77-89`), beside "Edit Data", using **select-then-edit**:

- `ui.input_select("overlay_element", …)`: choices are the active compartment's eligible elements — Responses (`type == "Responses"`) and outcomes (`type ∈ OUTCOME_ELEMENT_TYPES`), labelled `"{label} ({type})"`, value = element id. Computed reactively from `active_multises` + `active_compartment_id`. **If `active_compartment_id` is `None`** (a compartment-less MultiSES), the choices are empty and the panel renders a "No compartment selected" note — the choices computation must not call `ms.compartment(None)`.
- A `@render.ui` output **`overlay_editor`** keyed on `input.overlay_element()` rendering, as one unit: the matching inputs (Response → 10 `ui.input_select(f"tenet_{slug}", …)` pre-filled from `response_tenet_scores.get(eid, {})`; outcome → `ui.input_checkbox_group("equity_dims", choices={slug: label for slug, label in EQUITY_DIMENSIONS}, selected=outcome_equity_dimensions.get(eid, []))`); a hidden **`overlay_editing_id`** stamping the eid — rendered as `ui.input_text("overlay_editing_id", "", value=eid)` wrapped/styled `display:none`, NOT a raw `<input type="hidden">` (only a Shiny input widget registers with `input.<id>()`); and `ui.input_action_button("save_overlay", "Save")` (the button lives inside `overlay_editor`, so `input.save_overlay` is live only while an editor is rendered).

Save effect `@reactive.effect @reactive.event(input.save_overlay)`:
1. `cid = state.active_compartment_id.get()`; `eid = input.overlay_editing_id()` (the **stamped** id, guaranteed consistent with the rendered inputs — not the live `overlay_element` select).
2. **Save-time guard:** abort with an error notification if `cid is None`, or the compartment no longer contains an element with id `eid` of an eligible type (handles a since-deleted element or a compartment switch).
3. **Branch on the element's type before reading inputs** (reading an unrendered input id is unsafe):
   - *Response:* `scores = assemble_tenet_scores({slug: input[f"tenet_{slug}"]() for slug in TENET_SLUGS})`; `new_field = set_overlay_entry(cmp.response_tenet_scores, eid, scores)`; `replace_compartment_overlays(ms, cid, response_tenet_scores=new_field)`.
   - *Outcome:* `dims = list(input.equity_dims())` (the checkbox group returns a possibly-empty **tuple**; `list(...)` coerces it — empty when nothing checked); `new_field = set_overlay_entry(cmp.outcome_equity_dimensions, eid, dims)`; `replace_compartment_overlays(ms, cid, outcome_equity_dimensions=new_field)`.
4. Write-back per §2.4 (no `active_compartment_project` refresh).

Because the save-time guard confirms the element exists in the compartment, the editor never writes an orphan overlay key (W304/W305 stay quiet). `set_overlay_entry` normalizes a fully-cleared field to `None`.

## 5. Validation, error handling, normalization
- All writes pass through `Channel`/`Compartment` construction (`dataclasses.replace`), so `_validate_tenet_scores` (`data_structure.py:200-223`, M206) / `_validate_equity_dimensions` (`:226-249`, M207) — both of which raise `_ChannelValidationError` — fire automatically; `Channel`/`Compartment.__post_init__` also raise plain `ValueError` for channel-type / archetype / id checks. The UI only offers valid values, so these are backstops. Both editors catch `(_ChannelValidationError, ValueError, KeyError, TypeError)` and surface an error notification (`ui.notification_show(..., type="error")`) without writing state; on success they show a success notification (the app idiom at `project_setup.py:237/242`). When a save clears everything, the success notification should make that visible so an accidental wipe isn't silently confirmed (exact wording left to implementation).
- **Single normalization rule (both layers):** "no scores / no dims" is `None`, never `{}`/`[]`. `assemble_tenet_scores` returns `None` when all blank; `set_overlay_entry` removes the per-element key and returns `None` when the field empties. The empty-equity-list collapse is intentional (§2.3).
- Save-effect reads of reactive state happen inside the effect body; wrapping them in `reactive.isolate()` (as `_backwrite_to_multises` does) is the recommended hygiene to avoid the effect taking spurious reactive dependencies.

## 6. Testing

**Note on effect tests:** this repo has **no in-harness idiom for firing a `@reactive.effect`** (existing module tests are pure-helper unit tests or `inspect.getsource` checks; effects are exercised only by Playwright e2e). So the editors' logic is unit-tested at the pure-helper layer (§2.3) and the wiring is covered by e2e — **no `@reactive.effect` is tested directly.** Test files partition strictly: `test_overlay_editors.py` = library helpers (no Shiny/app imports); `test_overlay_edit.py` = app-pure helpers (import `multises_app.overlay_edit`, no Shiny session).

### Library helpers (`tests/test_overlay_editors.py`, new)
- `replace_channel`: swap returns a new MultiSES, original unmutated; unknown id → `KeyError`; endpoints preserved (resulting MultiSES constructs); a `new_channel` with a dangling endpoint → MultiSES construction raises (M201 backstop); `tenet_scores=None` stored (not `{}`); partial-scores `to_json`/`from_json` round-trip.
- `replace_compartment_overlays`: override `response_tenet_scores` while **omitting** `outcome_equity_dimensions` (asserts the omitted field unchanged); override the other only; override both; omit both (identity); explicit `response_tenet_scores=None` clears (distinct from omit/preserve); unknown id → `KeyError`; bad slug/out-of-range raises via `__post_init__`; `project` object identity preserved; round-trip lossless; a placeholder-archetype compartment survives — **construct it via** `dataclasses.replace(seed_compartment(...), _unknown_archetype_original="raw_x")` (a real field; this is also how `from_dict` sets it).
- Interleaving: on one MultiSES, `replace_compartment_overlays` then `replace_channel` leave each other intact.

### App-pure helpers (`tests/test_overlay_edit.py`, new)
- `assemble_tenet_scores`: all-blank → `None`; a `None` value among inputs is dropped (not int-cast); partial → correct int dict; full → 10 ints.
- `set_overlay_entry`: set new key; overwrite; falsy (`None`/`{}`/`[]`) removes the key; removing the last key → `None`; input dict not mutated.

### Module render/gating (`tests/test_topology_module.py`, `tests/test_compartments_module.py`, extend)
- Topology: `inspector_tenet_editor` exists; **named positive** test (governance target → editor + `save_channel_tenets` + 10 `tenet_*` present); **named negative** test (a nutrients channel and a compartment target → `"save_channel_tenets" not in html`).
- Compartments: the "Evaluative scores" panel exists (`overlay_element`, `overlay_editor`, `save_overlay`); the eligible-element list excludes non-Response/non-outcome elements.

### e2e (`tests/test_overlay_editors_e2e.py`, new — reuses the existing `mosaicses_app_url` fixture in `conftest.py`, no conftest change)
- Topology: select a governance channel, `wait_for_selector` for the editor container, set `tenet_ecological` to "5", Save, navigate to Comparative, assert the `tenet_table` row for that channel shows `ecological == 5` (assert the specific cell, not mere presence).
- Compartments: drill in, open "Evaluative scores", select an outcome element, `wait_for_selector` for `equity_dims`, check `livelihood_displacement`, Save, navigate to Comparative, assert the `equity_table` shows that Pressure's `affected_equity_dimensions` containing "Livelihood displacement".

## 7. Files touched

| File | Change |
|---|---|
| `multises/data_structure.py` | `_UNSET`; `replace_channel`; `replace_compartment_overlays` |
| `multises/__init__.py` | re-export the two helpers (import block + `__all__`); `_UNSET` stays internal |
| `multises_app/overlay_edit.py` (new) | pure `assemble_tenet_scores`, `set_overlay_entry`; imports `TENET_SLUGS` from `multises.data_structure` |
| `multises_app/modules/topology.py` | `inspector_tenet_editor` `@render.ui` (governance-gated, direct Channel lookup, stamped id) + `save_channel_tenets` effect (save-time re-gate) + `replace_channel`; import `_ChannelValidationError` |
| `multises_app/modules/compartments.py` | "Evaluative scores" nav panel (`overlay_element`, `overlay_editor`, stamped `overlay_editing_id`, `save_overlay`) + save-time existence guard + `replace_compartment_overlays`; import `_ChannelValidationError`; `EQUITY_DIMENSIONS` already exported from `multises` (#20) |
| `tests/test_overlay_editors.py` (new) | library helper unit tests |
| `tests/test_overlay_edit.py` (new) | app-pure helper unit tests |
| `tests/test_topology_module.py` | inspector tenet-editor render + governance gating (positive + negative) |
| `tests/test_compartments_module.py` | Evaluative-scores panel render |
| `tests/test_overlay_editors_e2e.py` (new) | one e2e per surface |

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Effects untestable in-harness | High (designed around) | Logic in pure helpers (§2.3) unit-tested; effects thin; e2e covers wiring; §6 states "no effect tests" |
| Stale selection → write to wrong target | Medium (avoided) | Stamp the rendered id; **re-validate at save time** (re-gate governance; verify element ∈ compartment) — §3/§4 |
| Stale client input values across selections | Medium (avoided) | Inputs + button + stamp all in one `@render.ui`; save reads the stamped id, so id+values are render-consistent |
| `active_compartment_project` refresh discards unsaved edits | Medium (removed) | The refresh was dropped — overlay edits don't change the project; §2.4 |
| `cid is None` (no-compartment MultiSES) crashes the panel | Medium (avoided) | Choices guard + save-time `cid is None` abort — §4 |
| `replace_channel` brand-new primitive | Medium | Pure, mirrors `replace_compartment`; endpoint-integrity unit test |
| Empty edit stores a `{}`/`[]` stub | Low (avoided) | Single `None`-normalization in §2.3 |
| Scope: 3 editors / 2 modules | Medium (accepted) | Plan sequences: library helpers + `overlay_edit.py` first (both editors depend on them merged), then the two editors (independent of each other) |

## 9. Definition of done
- `replace_channel` + `replace_compartment_overlays` in the library, re-exported, unit-tested (swap, KeyError, endpoint integrity, omit-preserve, explicit-`None`, validation propagation, round-trip, placeholder-archetype, interleaving).
- `overlay_edit.py` pure helpers unit-tested (assembly incl. None-drop + all-blank→`None`; key set/remove/empties→`None`; no input mutation).
- Topology inspector edits governance-channel tenets (gated on the validated field at render **and** save; inputs in `@render.ui`; `—`=unset) and persists to `active_multises`.
- Compartments "Evaluative scores" panel edits Response tenets + outcome equity dims (select-then-edit; stamped id; branch-before-read; save-time existence guard; `cid is None` handled); empties → `None`; **no `active_compartment_project` refresh, no `emit_isa_change`**.
- Comparative cards reactively reflect edits; durability via the existing manual download; no autosave; no schema bump; SESPy untouched.
- Full unit suite green + module render/gating tests + one e2e per surface (no `@reactive.effect` tested directly).

## 10. Out-of-scope follow-ups
Autosave / server-side persistence; editable grid / bulk entry; undo-redo; confirmation modal on full clear; tenet scoring on non-governance channels; weighting / composite indices.
