# MosaicSES Chunk 4b — Project Setup form (design spec)

**Date:** 2026-05-18
**Spec author:** Brainstorm session 2026-05-18.

## 1. Goal + scope

### 1.1 In scope

A single new Shiny module `multises_app/modules/project_setup.py` that fills the existing (currently empty) `"project"` nav-panel slot with a two-column metadata-editing form for the active MultiSES. Direct adaptation of `sespy.modules.pims_project` — same UX shape (left = Project Information / Save; right = System Scope / status), same save protocol (explicit button → build fresh metadata → set the reactive → emit `event_bus.isa_change` → toast), 8 fields drawn from `MultiSESMetadata`.

Acceptance: the app's "Project" tab renders a populated form for the Curonian seed metadata. Edits + Save commit to `state.active_multises`, update `modified_at`, fire a toast, and refresh the status panel.

### 1.2 Out of scope (deferred to later chunks)

| Item | Deferred to |
|---|---|
| `recent_projects.py` (New / Open / Save As file flows) | chunk 4c |
| CSS extraction to `www/mosaic-skin.css` | chunk 4c |
| JS extraction to `multises_app/static/` | chunk 4c |
| `CHANNEL_TYPE_RENDER` constant in `multises_app/colors.py` | chunk 4c |
| Bridge-chart axis fix | chunk 4c |
| pyvis tabular-fallback for screen readers | chunk 4c |
| Domain-specific seed-content per archetype | chunk 4c |
| LOAC-hierarchical topology layout | chunk 4c |
| 2 remaining e2e tests | chunk 4d |
| CI integration (GitHub Actions) | chunk 4d |
| External-API contract tests | chunk 4d |
| v1 ship checklist | chunk 4d |

No new top-level reactive value, no `data_structure.py` changes, no test-infrastructure changes, no e2e test for this chunk.

## 2. Decisions table

| Decision | Choice | Reasoning |
|---|---|---|
| **Reference pattern** | Direct mirror of `sespy.modules.pims_project` (207 lines) | Chunk-3 already follows SESPy module conventions; path of least surprise. Reference has 2 years of production patina via SESPy itself. |
| **Save trigger** | Explicit `input_action_button("save", ...)` | Matches reference. Auto-save adds debounce + undo + provenance complexity for zero UX win on an 8-field form. |
| **Field layout** | 2-column, `col_widths=(6, 6)` | Matches reference + parent spec §7 ("small two-column form"). |
| **Left column grouping** | "Project Information": name, description, da_site, focal_issue, Save button | Information about the project itself. |
| **Right column grouping** | "System Scope": river_basin, regional_sea, temporal_scale, spatial_scale, status panel | The contextual envelope of the system being modeled. |
| **`river_basin` field** | Free-text `input_text` (no constants list) | MultiSES adds this field over the reference; no `MULTISES_RIVER_BASINS` constant exists. Premature to add a constants list for a single v1 demo (Curonian/Nemunas). |
| **`regional_sea` source** | `sespy.regional_seas.get_regional_seas()` (function call, not a constant) | Verified 2026-05-18 against installed sespy: there is NO `REGIONAL_SEAS` constant; only the function `get_regional_seas() -> dict[slug, dict[name, ecosystem_types, ...]]`. The dropdown extracts `(slug, entry["name"])` pairs. |
| **Seed/constants mismatch tolerance** | Selects fall back to empty (`""`) when the saved value isn't in the choice list | Curonian seed has `da_site='Curonian Lagoon'` (NOT in `DA_SITES=('Tuscan Archipelago', 'Arctic Northeast Atlantic', 'Macaronesia')`) and `regional_sea='baltic_sea'` (NOT in `get_regional_seas()` keys, which use `'baltic'`). The form will silently show empty for both on first load. This is a **known cosmetic gap** documented in §9 AC6 below; reconciliation is chunk-4c seed-data work. |
| **Localization** | English-only, raw string values (no `t()` wrappers) | v1 scope; matches chunk-4a's no-i18n stance in `comparative_ui` and `cross_view_ui`. |
| **Empty-name fallback** | `"Untitled MultiSES"` | Matches reference's `"Untitled Project"` semantics. Never persist literally-empty name. |
| **`event_bus.emit_isa_change()` after save** | Yes (mirror reference) | Reference pattern. Slight over-eager (downstream loops recompute), but the listener side is the chunk-3-stable contract — don't break it. Performance optimization is chunk 4c+ if profiling shows pain. |
| **Reset / Discard button** | None | Reference has none. To discard, don't click Save. `_load_form_values` re-populates form from `state.active_multises` on external change. |
| **Status panel content** | saved_at (this-session HH:MM:SS, None until first save) + modified_at (from metadata ISO) + schema_version + #compartments + #channels | First three mirror reference. Two bonuses (#compartments / #channels) are zero-cost reads from `state.active_multises` and give the user a useful "is my MultiSES the right shape" sanity check. |
| **Tests** | 5 unit tests, no e2e | Matches chunk-4a's per-module test budget. E2e deferred to chunk 4d. |
| **MultiSES reconstruction strategy** | `MultiSES(metadata=new_meta, compartments=current.compartments, channels=current.channels)` | Reference uses analogous `Project(metadata=new_meta, isa_data=current.isa_data)`. Preserves cross-collection invariants because compartments/channels references are identical to validated current state. |

## 3. Architecture

**One new file**: `multises_app/modules/project_setup.py`. Module-decorated with `@module.ui` + `@module.server`, matching `topology.py` / `compartments.py` / `comparative.py` / `cross_view.py` shape.

```
multises_app/modules/
    __init__.py          ← +2 lines re-exporting project_setup_ui, project_setup_server
    topology.py
    compartments.py
    comparative.py       ← unchanged
    cross_view.py        ← unchanged
    project_setup.py     ← NEW (~180 lines)
```

`app.py` gains 1 import + 1 server-mount call + replaces the existing empty `"project"` nav-panel content with `project_setup_ui("project")`.

**Read-only consumers of `state.active_multises`** (read via `.get()` inside reactive contexts) for the load-form effect and status-panel render. **Writer of `state.active_multises`** in `_handle_save`. No new top-level reactive.value.

## 4. UI design

```python
@module.ui
def project_setup_ui() -> ui.Tag:
    return ui.card(
        ui.card_header("Project Setup"),
        ui.div(
            ui.tags.p(
                "Project-level metadata. Edits apply on Save.",
                class_="text-muted",
            ),
            ui.layout_columns(
                # Left: Project Information
                ui.div(
                    ui.h4("Project Information"),
                    ui.input_text(
                        "name", "Project name",
                        placeholder="e.g. Curonian Lagoon — Nemunas basin",
                    ),
                    ui.input_text_area(
                        "description", "Description",
                        placeholder="Brief one-paragraph summary of the project",
                        rows=3,
                        width="100%",
                    ),
                    ui.input_select(
                        "da_site", "Demonstration area",
                        choices=_da_site_choices(),
                        selected="",
                    ),
                    ui.input_text_area(
                        "focal_issue", "Focal issue",
                        placeholder="The central management question or risk this project addresses",
                        rows=4,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "save", "Save",
                        class_="btn btn-primary",
                        style="margin-top: 8px;",
                    ),
                ),
                # Right: System Scope
                ui.div(
                    ui.h4("System Scope"),
                    ui.input_text(
                        "river_basin", "River basin",
                        placeholder="e.g. Nemunas",
                    ),
                    ui.input_select(
                        "regional_sea", "Regional sea",
                        choices=_regional_sea_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "temporal_scale", "Temporal scale",
                        choices=_temporal_choices(),
                        selected="",
                    ),
                    ui.input_select(
                        "spatial_scale", "Spatial scale",
                        choices=_spatial_choices(),
                        selected="",
                    ),
                    ui.tags.hr(),
                    ui.output_ui("status"),
                ),
                col_widths=(6, 6),
            ),
            style="padding: 16px;",
        ),
        class_="mosaicses-project-setup-card",
        full_screen=True,
    )
```

**Choice helpers** (module-level, fail-fast on constant drift; defensive `.get("name", slug)` in regional-sea helper protects against partial-dict sespy entries):

```python
def _da_site_choices() -> dict[str, str]:
    return {"": "—", **{s: s for s in DA_SITES}}

def _regional_sea_choices() -> dict[str, str]:
    # get_regional_seas() returns dict[slug, dict[name, ecosystem_types, ...]];
    # fall back to slug if any entry is missing the "name" key.
    return {"": "—", **{slug: data.get("name", slug) for slug, data in get_regional_seas().items()}}

def _temporal_choices() -> dict[str, str]:
    return {"": "—", **{v: v for v in TEMPORAL_SCALES}}

def _spatial_choices() -> dict[str, str]:
    return {"": "—", **{v: v for v in SPATIAL_SCALES}}
```

Saved metadata stores the SLUG (e.g., `'baltic'`), not the display label (`'Baltic Sea'`). Labels are display-only; slugs are persisted in `MultiSESMetadata.regional_sea`.

Imports (module-level):
- `DA_SITES, TEMPORAL_SCALES, SPATIAL_SCALES` from `sespy.constants` (all three are tuples per Probe 2)
- `get_regional_seas` from `sespy.regional_seas` (function, NOT a constant)

The `_regional_sea_choices()` helper definition is shown below in the "Choice helpers" subsection — it extracts human-readable names from the nested-dict shape with a defensive slug fallback.

## 5. Data flow

**Load (form ← state):**

```
state.active_multises (reactive.Value[MultiSES])
        │ on mount + on external change
        ▼
_load_form_values  @reactive.effect
        │
        ├── meta = state.active_multises.get().metadata
        │
        ▼ ui.update_text / ui.update_text_area / ui.update_select for each of 8 fields
   form inputs (now reflect current metadata)
```

`_load_form_values` SUBSCRIBES to `state.active_multises` but NOT to any input. This is the load-bearing reactive discipline: the effect re-fires only when the underlying state changes (file load, switcher, etc.), never on user keystroke — otherwise keystrokes would trigger re-population and clobber the user's typing.

**Save (form → state):**

```
user clicks Save
        │
        ▼
_handle_save  @reactive.effect @reactive.event(input.save, ignore_init=True)
        │
        ├── 1. name = (input.name() or "").strip() or "Untitled MultiSES"
        ├── 2. read other 7 input values, strip whitespace
        ├── 3. current = state.active_multises.get()
        ├── 4. new_meta = MultiSESMetadata(
        │         name=name,
        │         description=...,
        │         da_site=...,
        │         river_basin=...,
        │         regional_sea=...,
        │         focal_issue=...,
        │         spatial_scale=...,
        │         temporal_scale=...,
        │         created_at=current.metadata.created_at,    # preserve
        │         modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        │         schema_version=current.metadata.schema_version,
        │     )
        ├── 5. ms_new = MultiSES(metadata=new_meta,
        │                       compartments=current.compartments,
        │                       channels=current.channels)
        ├── 6. state.active_multises.set(ms_new)
        ├── 7. state.event_bus.emit_isa_change()
        ├── 8. last_saved_at.set(datetime.now().strftime("%H:%M:%S"))
        ▼
   ui.notification_show("Saved ✓", duration=3, type="message")
```

`last_saved_at` is a module-local `reactive.Value[str | None]` (initial None) — session-only "last saved" indicator, NOT persisted.

**Status panel (with SR-accessible live region, R8 mitigation):**

```python
@output
@render.ui
def status():
    ms = state.active_multises.get()
    meta = ms.metadata
    saved_text = last_saved_at.get() or "—"
    # role="status" + aria-live="polite" so screen readers announce the
    # "Saved this session" timestamp update when the user clicks Save.
    # See R8 — Shiny notification_show is itself SR-invisible.
    return ui.tags.div(
        ui.tags.dl(
            ui.tags.dt("Saved this session"), ui.tags.dd(saved_text),
            ui.tags.dt("Modified at"), ui.tags.dd(meta.modified_at or "—"),
            ui.tags.dt("Schema version"), ui.tags.dd(str(meta.schema_version)),
            ui.tags.dt("Compartments"), ui.tags.dd(str(len(ms.compartments))),
            ui.tags.dt("Channels"), ui.tags.dd(str(len(ms.channels))),
        ),
        role="status",
        **{"aria-live": "polite"},
    )
```

The status panel is fully reactive on `state.active_multises` — re-renders on every change (cheap, all reads are O(1) attribute access). The ARIA live region announces successful saves to screen-reader users (R8).

## 6. Error handling

- **Empty name**: coerced to `"Untitled MultiSES"`. Never persisted as literal empty string.
- **Whitespace-only values**: `.strip()` reduces them to empty string; for `name`, empty → fallback. For other fields, empty string is accepted (matches the `default: str = ""` schema in `MultiSESMetadata`).
- **`None` input values**: if `input.<field>()` returns `None` (race: module not fully mounted), the `(inputs.get(...) or "").strip()` idiom coerces to empty string. For `name`, this fires the fallback — could rename the project to "Untitled MultiSES" if a save fires before mount completes. Acceptable: this race is theoretical given Shiny's `ignore_init=True` guard on the Save effect.
- **Unknown choice value at load time**: seed metadata may contain values not in the dropdown's choice list (e.g., Curonian seed has `da_site='Curonian Lagoon'` not in `DA_SITES`; `regional_sea='baltic_sea'` not in `get_regional_seas()` slugs). `ui.update_select(selected=<unknown>)` silently falls back to `""`. Form shows empty for affected fields on first load. Documented in §9 AC6; reconciled in chunk-4c.
- **Unknown choice value at save time**: shouldn't happen — dropdowns are constrained at save. If a race produces one, `MultiSESMetadata` accepts arbitrary strings (no dataclass-level validation).
- **`_handle_save` error wrapping**: the body MUST be wrapped in `try/except Exception as e: log + notify`. Critical to avoid partial-state mutation: if `state.active_multises.set(ms_new)` succeeds but `event_bus.emit_isa_change()` raises (chunk-3 listener failure), the toast and `last_saved_at` would never update — user sees no confirmation and retries, double-saving. The try/except logs the exception, fires an error toast (`ui.notification_show("Save failed — see log", type="error")`), and leaves the partial state in place (cannot rollback cleanly; rollback would require capturing the pre-save MultiSES, which is wasteful for a presumed-rare error path).
- **`MultiSES.__post_init__` validation**: re-runs on the new instance. Since we preserve `current.compartments` and `current.channels` references (not copies), the validation that already passed for `current` will pass for `ms_new`. Failure would indicate either external mutation of the lists between `get()` and `set()` (impossible — Shiny serializes effects) or a bug in `data_structure.py` itself (out of scope). Caught by the try/except above.
- **No "Discard / Reset" button**: by design. To revert unsaved edits, the user just doesn't click Save. Acceptable for v1; chunk 4c can add a Reset button if smoke testing surfaces a need.
- **No optimistic concurrency**: single-user app. No multi-tab sync semantics.

## 7. Risks + mitigations

**R1 — Form repopulation clobbers in-flight edits.** If `_load_form_values` were to subscribe to `state.active_multises` AND user is in the middle of typing in a field, an external state change (file load, switcher) would call `ui.update_text` and replace the user's typed value. Mitigation: this is exactly the chunk-3 / reference pattern — accepted behavior; an external state change *should* discard in-flight form edits (the form was reflecting old state). Document in spec; no code change required.

**R2 — `emit_isa_change` over-eagerness.** Metadata-only saves trigger downstream invalidation of analysis loops in chunk-3 `analysis_loops.py:141`. For pure metadata changes (name, focal_issue, etc.), this is wasteful (re-runs cycle detection that didn't change). Mitigation: matches the reference's stance — accept overhead; performance optimization to a separate `metadata_change` event is chunk 4c+ if profiling demands it.

**R3 — New constants drift.** If chunk-4c adds a new entry to `TEMPORAL_SCALES`, the `_temporal_choices()` helper continues to work (no label-key mapping like the reference's i18n version). But a new `DA_SITES` value would surface in the dropdown without a label — fine since v1 is English-only and labels are slugs. No mitigation needed.

**R4 — `regional_seas` import shape (RESOLVED 2026-05-18 via Round-1 review).** Initially the spec assumed a `REGIONAL_SEAS` constant. Multi-angle review verified against installed sespy: there is NO such constant; only `get_regional_seas() -> dict[slug, dict[name, ...]]`. Spec §4 and §2 decisions updated. Probe 1 in the plan is now a confirmation, not a discovery.

**R5 — `event_bus.emit_isa_change()` re-entry loop.** If any chunk-3 listener responds to `isa_change` by writing back to `state.active_multises`, the form's `_load_form_values` effect re-fires, potentially in a loop. Mitigation: chunk-3 listeners are read-only by contract (`compartments.py` only invalidates derived state via `event_bus`; `analysis_loops.py` only clears its own `detected` reactive). The Save's try/except (per §6) caps any runaway; combined with Shiny's effect-serialization per session, an infinite loop would manifest as session unresponsiveness rather than corruption. Smoke checklist explicitly tests this scenario (R5 acceptance: Save → no hang).

**R6 — Seed/constants drift, expected on first load.** Curonian seed's `da_site` and `regional_sea` values predate this form's constants-based dropdowns. First load shows empty for both fields. Users can re-select from dropdown and Save — restoring the saved value (under the reconciled slug) via the standard save flow. Not a bug in the form; a data-reconciliation task for chunk-4c.

**R7 — Hardcoded import vs probe drift.** Earlier plan revision had `from sespy.regional_seas import REGIONAL_SEAS` as a NOTE-comment-adjustable hardcode. Reviewed and replaced with the verified-correct `get_regional_seas` import in this spec; plan Task 2 reflects the fix verbatim. No probe-adjustment path needed.

**R8 — Shiny `notification_show` has no ARIA semantics.** Verified 2026-05-18 via multi-angle review against installed Shiny 1.6.1: the `#shiny-notification-panel` and individual `.shiny-notification` divs carry NO `aria-live`, NO `role="status"`, NO `role="alert"`. Both the "Saved ✓" success toast and the "Save failed:" error toast are silent to screen readers. Mitigation in this spec: wrap the status panel `<dl>` in a `<div role="status" aria-live="polite">` so SR users hear the "Saved this session" timestamp update on successful save. The error path is partially exposed — when error fires, the status dl does NOT update (no success timestamp added), so the absence-of-update is a weak signal. Full SR-error coverage requires a dedicated `role="alert" aria-live="assertive"` region; deferred to chunk-4c (full a11y/CSS pass).

**R9 — Tautological server-callable test.** `assert callable(project_setup_server)` passes for any function, regardless of whether it's a `@module.server`-decorated callable with the right signature. Replaced (see plan Task 2 Step 1) with a stronger check that the decorator was applied (looks for `_module_decorator` attribute) and the signature includes the keyword-only `state: MultiSESState` parameter.

## 8. Testing

New file `tests/test_project_setup_module.py` with 5 tests, mirroring chunk-4a's `test_comparative_module.py` structure:

```python
"""Project Setup module tests (chunk 4b)."""
from __future__ import annotations


def test_project_setup_module_importable():
    from multises_app.modules import project_setup  # noqa: F401


def test_project_setup_ui_renders_8_inputs():
    from multises_app.modules.project_setup import project_setup_ui
    html = str(project_setup_ui("test_id"))
    # 4 text/textarea + 4 select + 1 action button + 1 output_ui
    for input_id in ("name", "description", "da_site", "focal_issue",
                     "river_basin", "regional_sea", "temporal_scale",
                     "spatial_scale", "save"):
        assert input_id in html, f"missing input: {input_id}"


def test_project_setup_server_is_module_decorated():
    # @module.server wraps the function so signature shows (id, *args, **kwargs).
    # Verified against chunk-4a comparative_server / cross_view_server.
    import inspect
    from multises_app.modules.project_setup import project_setup_server
    params = list(inspect.signature(project_setup_server).parameters.keys())
    assert params == ["id", "args", "kwargs"], (
        f"Expected @module.server wrapper signature; got {params}"
    )


def test_build_new_metadata_applies_empty_name_fallback():
    from multises_app.modules.project_setup import _build_new_metadata
    from multises import seed_curonian
    ms = seed_curonian()
    inputs = {"name": "", "description": "test",
              "da_site": "", "river_basin": "", "regional_sea": "",
              "focal_issue": "", "temporal_scale": "", "spatial_scale": ""}
    new_meta = _build_new_metadata(ms.metadata, inputs)
    assert new_meta.name == "Untitled MultiSES"
    assert new_meta.created_at == ms.metadata.created_at  # preserved
    assert new_meta.modified_at != ms.metadata.modified_at  # updated


def test_build_new_multises_preserves_compartments_and_channels():
    from multises_app.modules.project_setup import _build_new_multises
    from multises import seed_curonian
    ms = seed_curonian()
    new_meta = ms.metadata  # same metadata, different shape doesn't matter
    ms_new = _build_new_multises(ms, new_meta)
    assert ms_new.compartments is ms.compartments  # same reference
    assert ms_new.channels is ms.channels
    assert ms_new.metadata is new_meta  # new
```

Tests 4 and 5 require extracting two pure helpers from `_handle_save`:

```python
def _build_new_metadata(current_meta: MultiSESMetadata,
                       inputs: dict[str, str]) -> MultiSESMetadata:
    name = (inputs.get("name") or "").strip() or "Untitled MultiSES"
    return MultiSESMetadata(
        name=name,
        description=(inputs.get("description") or "").strip(),
        da_site=(inputs.get("da_site") or "").strip(),
        river_basin=(inputs.get("river_basin") or "").strip(),
        regional_sea=(inputs.get("regional_sea") or "").strip(),
        focal_issue=(inputs.get("focal_issue") or "").strip(),
        temporal_scale=(inputs.get("temporal_scale") or "").strip(),
        spatial_scale=(inputs.get("spatial_scale") or "").strip(),
        created_at=current_meta.created_at,
        modified_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        schema_version=current_meta.schema_version,
    )


def _build_new_multises(current: MultiSES,
                        new_meta: MultiSESMetadata) -> MultiSES:
    return MultiSES(
        metadata=new_meta,
        compartments=current.compartments,
        channels=current.channels,
    )
```

These pure-helper extractions also let the `_handle_save` server effect become a thin 4-line wrapper that's mechanically obvious.

## 9. Acceptance criteria

1. App boots without console errors.
2. Project nav panel renders the form populated with Curonian seed metadata. `name`, `description`, `river_basin`, `focal_issue`, `temporal_scale`, `spatial_scale` populate from the seed. **Known cosmetic gap (R6)**: `da_site` and `regional_sea` show empty on first load because seed values (`'Curonian Lagoon'`, `'baltic_sea'`) are not in the dropdown's choice list. Workaround: user picks the closest match from the dropdown and Saves. Reconciliation deferred to chunk-4c.
3. All 8 inputs present with correct labels and types.
4. Editing the `name` field + clicking Save:
   - Updates the status panel's "Saved this session" timestamp.
   - Updates `modified_at` (visible in status panel).
   - Fires a toast "Saved ✓".
5. Empty `name` + Save: form re-shows `"Untitled MultiSES"` after the `_load_form_values` round-trip.
6. Status panel shows correct #compartments (6) and #channels (≥ 26, depending on chunk-4a seed expansion state).
7. `state.active_multises` change from any source (e.g., chunk-3 compartment edit propagates to channels) re-populates the form.
8. Save preserves all 6 compartments and channels byte-for-byte (verified via the pure-helper unit test).
9. `pytest tests/ -q` → approximately 274 passed (chunk-4a baseline was 269 = 267 unit + 2 e2e; + 5 new unit tests = 274). If e2e is excluded (`--ignore=tests/test_*_e2e.py`), expect ~272. Load-bearing assertion: 0 FAILED, 0 ERROR.

## 10. Hand-off

This spec is the source of truth for chunk 4b. The next step is `superpowers:writing-plans` to produce a step-by-step implementation plan. The plan should:

- Begin with Task 0 probes verifying:
  1. `from sespy.regional_seas import REGIONAL_SEAS` (or equivalent) — actual name/shape.
  2. `from sespy.constants import DA_SITES, TEMPORAL_SCALES, SPATIAL_SCALES` resolve.
  3. The existing `"project"` nav slot in `app.py` is genuinely empty (or contains a placeholder we should replace).
  4. `state.event_bus.emit_isa_change()` is callable in the chunk-3 baseline (it is, per chunk-3 prespike).
- Tasks 1–N implement the module + tests TDD-style.
- Final task: wire into `app.py`, run full suite, commit. No e2e for this chunk.
- Plan should expect approximately 6-8 tasks (much smaller than chunk 4a's 22).

Implementation invocation: `superpowers:subagent-driven-development` against the plan (same workflow that shipped chunk 4a; per [[feedback_multi_round_agent_review]], the fresh-subagent-per-task with two-stage review pattern caught two latent bugs in the chunk-4a plan).
