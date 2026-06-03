# AI-Assisted SES Creation Wizard — SP1: Wizard Scaffolding (Design)

Date: 2026-05-01
Status: **Implemented** · merged to `main` 2026-05-01 at commit `dfedd28` (15 commits from `feat/ai-isa-wizard-sp1`, fast-forward, including 1 follow-up commit `dfedd28` strengthening e2e coverage post final-review). Post-merge baseline: **122 unit tests + 21 e2e scripts**. SP2 (regional-seas KB) was specced 2026-05-02 at `docs/superpowers/specs/2026-05-02-ai-isa-wizard-sp2-design.md` and respects the SP1→SP2 contract documented in §9 of this spec. Two minor post-implementation deltas worth noting: (a) the `_on_modal_save_first` handler described in early drafts of §3 was simplified to a two-button modal (Continue/Cancel) before ship — the text below already reflects the shipped two-button design; (b) i18n keys added to `core.json` MUST go inside the top-level `"translation"` wrapper object — the loader (`Translator._load_one`) reads `raw.get("translation", {})`, so keys at the file root are silently invisible. This trap was discovered during PIMS (post-PIMS-spec) and is documented here for SP3/SP4 authors.
Source modules in R app:
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa_assistant_module.R` (2612 LOC, main module — orchestration only is in scope here)
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/question_flow.R` (1059 LOC, question flow — most directly ported here)
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/ui_components.R` / `ui_renderers.R` (UI dispatch by step type)
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/step_navigation.R` (Back/Next + breadcrumb logic)
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/answer_processor.R` (per-step validation + commit-to-state logic)

This is the first sub-project (SP1) of a 4-part feature. Subsequent sub-projects will be brainstormed and specced separately:

- **SP1 (this spec):** Wizard scaffolding — 12-step flow, navigation, persistence, confirmation modal. The connection-review step (#11) calls a stub `suggest_connections()` that returns `[]`. The wizard works as guided manual entry on its own.
- **SP2:** Regional-seas knowledge base — JSON data + helpers. Drives the choices on steps 0 and 1.
- **SP3:** Default scoring backend — TF-IDF + polarity rules port of R's `connection_generator.R`. Fills `suggest_connections()` deterministically and offline.
- **SP4:** Optional Claude API backend — alternative implementation of `suggest_connections()`, switchable via setting (`wizard.scoring_backend`). Falls back to SP3 if absent.

This spec is for **SP1 only**.

## 1. Scope

Port the wizard scaffolding (UI + state machine + navigation) from R `ai_isa_assistant_module.R` and its helpers into SESPy as module #16, named "SES Wizard". The wizard guides a user through a 12-step DAPSI(W)R(M) framework definition and writes both **elements** to `project_data.isa_data.elements` (steps 4-10) and **metadata** fields (`regional_sea`, `ecosystem_type`) to `project_data.metadata` (steps 0-1) as it progresses.

**In scope:**
- A new module `sespy/modules/ai_isa_wizard.py` registered in the dashboard's `create` stage.
- A pure-data file `sespy/wizard.py` with the 12-step flow definition (no Shiny imports).
- Per-step UI dispatch covering 4 widget archetypes (single-choice, multi-choice, freeform-multiple, connection-review).
- A confirmation modal on `Start Wizard` that fires only when the existing project has elements.
- Live writes to `project_data` per step — abandoning mid-wizard leaves a partial-but-valid SES.
- A stub `suggest_connections(state) -> []` in `sespy/wizard.py` so the connection-review step renders without scoring.
- Two new dataclasses in `sespy/data_structure.py`: `WizardState` and `ConnectionSuggestion`.
- Full localization: ~50 i18n keys with English values + 8 placeholder languages, matching BOT/PIMS pattern.
- One e2e test (`tests/test_wizard_e2e.py`) covering: empty-project start, full 12-step run, modal-cancel, modal-replace.

**Out of scope (deferred to SP2-SP4):**
- The regional-seas knowledge base data itself — SP1 mocks it with a placeholder dict (`{"baltic": {"name": "Baltic Sea", "ecosystem_types": [...]}}` and similar for 4-5 other seas, just enough to render steps 0 and 1). Real KB lands in SP2.
- TF-IDF / rule-based connection scoring — SP3.
- Claude API backend — SP4.
- Persisting `countries` and `main_issue` answers across wizard sessions — these stay ephemeral in `wizard_answers` and are discarded on Finish (they feed `suggest_connections()` but don't persist to project file).
- The full `ai_isa_assistant_module.R`'s 2612 LOC of decorative UI (welcome message animations, help modals, custom CSS) — SP1 ports the **structural** flow; visual polish is deferred to a later sub-project if the user requests it.

## 2. Architecture

### New files

- `sespy/wizard.py` (~150 LOC) — pure-Python data + helpers. Holds the 12-step flow as a list of `WizardStep` dataclasses, the `suggest_connections` stub, and small validators. No Shiny imports.
- `sespy/modules/ai_isa_wizard.py` (~400-500 LOC) — Shiny module. Reactive state machine + per-step UI dispatch.
- `tests/test_wizard_e2e.py` (~160-200 LOC) — Playwright e2e, 6 cases (full run, modal cancel, modal replace, mid-wizard nav/resume, Back-preserves-writes, validation failure).

### Modified files

- `sespy/data_structure.py` — add `WizardState` and `ConnectionSuggestion` dataclasses.
- `sespy/translations/core.json` — add ~50 keys (1 nav, 1 stepper-related, ~48 module-scoped).
- `app.py` — register `wizard` in NAV (in `create` stage, after `templates`), `NAV_TO_STEP`, `PANELS`, server registration.
- `README.md` — bump module count 15 → 16; add a row to the modules table; update the e2e script count to reflect the actual count after adding `test_wizard_e2e.py` (verify the current count by `ls tests/test_*.py | wc -l` minus the unit-test files first — the README's stated number may have drifted from reality and should be reconciled to truth, not just incremented).

### Step taxonomy (4 widget archetypes, 6 R step types)

The R version has 6 distinct step types; we collapse to 4 widget archetypes for renderer dispatch:

| Archetype | R step types | Widget |
|---|---|---|
| `choice_one` | `choice_regional_sea`, `choice_ecosystem` | `ui.input_radio_buttons` (or `ui.input_select` if list >5) |
| `choice_many` | `country_multiple`, `choice_with_custom_multiple` | `ui.input_selectize(multiple=True)` + free-text "Other" input |
| `freeform_multiple` | `multiple` | List of `ui.input_text` rows + "Add another" button (R uses dynamic UI) |
| `connection_review` | `connection_review` | `ui.output_data_frame` of suggestions, with accept/reject toggles per row |

Each step in `wizard.py` declares its archetype; the renderer in `ai_isa_wizard.py` is a single `match step.archetype` block.

### Step flow (matches R 1:1)

| # | title_key | archetype | target | description |
|---|---|---|---|---|
| 0 | `regional_sea` | choice_one | `regional_sea` | Pick from KB (Baltic / Mediterranean / North Sea / Irish Sea / ...) |
| 1 | `ecosystem` | choice_one | `ecosystem_type` | Pick from regional sea's ecosystem_types list |
| 2 | `countries` | choice_many | `countries` | Multi-select countries within the region |
| 3 | `main_issue` | choice_many | `main_issue` | Multi-select common issues + custom |
| 4 | `drivers` | freeform_multiple | `drivers` | List of driver names |
| 5 | `activities` | freeform_multiple | `activities` | List of activities |
| 6 | `pressures` | freeform_multiple | `pressures` | List of pressures |
| 7 | `states` | freeform_multiple | `states` | List of state changes (Marine Processes & Functioning) |
| 8 | `impacts` | freeform_multiple | `impacts` | List of impacts on welfare |
| 9 | `welfare` | freeform_multiple | `welfare` | List of welfare elements (Goods & Benefits) |
| 10 | `responses` | freeform_multiple | `responses` | List of responses (Measures) |
| 11 | `connection_review` | connection_review | `connections` | Final review — `suggest_connections(state)` + per-row accept/reject |

**Element-type mapping for live writes** (steps 4-10 write `Element` objects to `project_data.isa_data.elements`):

The authoritative source for this mapping is `sespy/constants.py::ELEMENT_ID_PREFIX` — it already encodes the wizard-target → element-type relationship via the id prefix. The wizard MUST use that mapping rather than guess:

| Wizard target | SESPy `Element.type` | id prefix (per `ELEMENT_ID_PREFIX`) |
|---|---|---|
| `drivers` | `Drivers` | `D` |
| `activities` | `Activities` | `A` |
| `pressures` | `Pressures` | `P` |
| `states` | `Marine Processes & Functioning` | `MPF` |
| `impacts` | `Ecosystem Services` | `ES` |
| `welfare` | `Goods & Benefits` | `GB` |
| `responses` | `Responses` | `R` |

Note that R's "impacts" maps to SESPy's "Ecosystem Services" (impacts ON ecosystem services) and R's "welfare" maps to SESPy's "Goods & Benefits" (welfare derived from goods & benefits). The wizard reads this map from a small dict at the top of `sespy/wizard.py` rather than re-encoding it.

### Stub `suggest_connections` and SP3/SP4 contract

```python
@dataclass
class WizardState:
    regional_sea: str = ""
    ecosystem_type: str = ""
    countries: list[str] = field(default_factory=list)
    main_issue: list[str] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)  # all elements collected so far


@dataclass
class ConnectionSuggestion:
    source: str  # element id
    target: str  # element id
    polarity: str  # "+" | "-"
    confidence: float  # 0..1
    rationale: str  # short string explaining why


def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP1 stub: returns []. SP3 fills via TF-IDF + polarity rules; SP4 fills
    via Claude API. SP1's connection-review step renders an empty table with
    a placeholder message ('No suggestions yet — install SP3 or SP4 backend
    to enable AI-assisted connection generation')."""
    return []
```

### Module shape (Shiny module)

The UI has two visual states governed by `wizard_active`:
- **Inactive** (initial state): a single `Start Wizard` button + a one-line description. No breadcrumb, no Back/Next.
- **Active**: breadcrumb + step renderer + Back/Next/Finish buttons.

`wizard_step_render` (a `@render.ui`) renders both states by branching on `wizard_active.get()`. Back is hidden on step 0; Next is shown on steps 0-10; Finish is shown on step 11 (replaces Next, not in addition to it). All three navigation buttons are declared in the static UI but conditionally hidden via `style=display:none` toggled inside the step renderer's wrapper div — this lets `@reactive.event(input.wizard_X)` bindings be set up at module-init time without needing dynamic id wiring.

```python
@module.ui
def ai_isa_wizard_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("wizard.title")),
        ui.div(
            ui.output_ui("wizard_breadcrumb"),    # step pills (empty when wizard_active=False)
            ui.output_ui("wizard_step_render"),   # Start button OR step widget
            ui.div(
                ui.input_action_button("wizard_start", t("wizard.start"),
                                       class_="btn btn-primary",
                                       style="display: none;"),  # toggled by step renderer
                ui.input_action_button("wizard_back", t("wizard.back"),
                                       class_="btn btn-secondary",
                                       style="display: none;"),
                ui.input_action_button("wizard_next", t("wizard.next"),
                                       class_="btn btn-primary",
                                       style="display: none;"),
                ui.input_action_button("wizard_finish", t("wizard.finish"),
                                       class_="btn btn-success",
                                       style="display: none;"),
                style="margin-top: 16px;",
            ),
        ),
        full_screen=True,
    )


@module.server
def ai_isa_wizard_server(
    input: Inputs, output: Outputs, session: Session, *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    wizard_step: reactive.Value[int] = reactive.value(0)
    wizard_answers: reactive.Value[dict[str, Any]] = reactive.value({})
    wizard_active: reactive.Value[bool] = reactive.value(False)

    @reactive.effect
    @reactive.event(input.wizard_start, ignore_init=True)
    def _on_start(): ...  # confirmation-modal logic (see §4)

    @reactive.effect
    @reactive.event(input.wizard_next, ignore_init=True)
    def _on_next(): ...  # validate, write elements, increment step

    @reactive.effect
    @reactive.event(input.wizard_back, ignore_init=True)
    def _on_back(): ...

    @reactive.effect
    @reactive.event(input.wizard_finish, ignore_init=True)
    def _on_finish(): ...  # sets wizard_active=False on step 11

    @reactive.effect
    @reactive.event(input.wizard_replace, ignore_init=True)
    def _on_modal_replace(): ...  # preserves metadata, clears isa_data, jumps to step 0

    @reactive.effect
    @reactive.event(input.wizard_cancel_modal, ignore_init=True)
    def _on_modal_cancel(): ...  # closes modal, no state change

    @output
    @render.ui
    def wizard_breadcrumb(): ...

    @output
    @render.ui
    def wizard_step_render(): ...
```

### Confirmation modal flow

The wizard panel has a `Start Wizard` button visible when `wizard_active.get() is False`. Clicking it triggers `_on_start`:

1. Read `len(project_data.get().isa_data.elements)`.
2. If zero: directly set `wizard_active=True`, reset answers, jump to step 0.
3. If non-zero: open a modal via `ui.modal_show()` with TWO buttons (not three):
   - **Continue, replace it** (id `wizard_replace`) — preserves the existing metadata (so PIMS Project Setup answers survive) but clears ISA: `current = project_data.get(); project_data.set(Project(metadata=current.metadata, isa_data=IsaData()))`. Then `wizard_active=True`, then jump to step 0. Note: do NOT call `Project.from_isa(IsaData())` — that synthesizes a fresh `ProjectMetadata.new()` and silently discards focal_issue, da_site, definition_statement, etc.
   - **Cancel** (id `wizard_cancel_modal`) — `ui.modal_remove()`, no state change.

The modal **body** includes a sentence: *"Tip: if you want to keep your current SES, click Cancel and use the Save Project button in the sidebar before re-starting the wizard."*

This replaces the original three-button design (which had a "Save first" button intended to programmatically trigger the global `save_project` download). That design is unimplementable: `save_project` is a `@render.download` whose only entry point is a browser-driven HTTP GET; there is no Python-side API to invoke it programmatically and know it completed. A JS-driven `.click()` on the download button opens the browser's Save As dialog with no callback the wizard can wait on. The two-button design + tip text matches what the R `action_handlers.R` does and is robust.

Each button is wired to its own `@reactive.event` handler in the server.

### Live writes per step

`project_data` is a `reactive.Value[Project]` over an immutable dataclass — **in-place mutation does NOT propagate**. Every write must call `project_data.set(new_project)` with a freshly-constructed `Project` value. The PIMS `_handle_save` (in `pims_project.py`) is the canonical pattern.

**Prerequisite**: `_next_id` currently lives in `sespy/modules/isa_data_entry.py` as a private helper. SP1 promotes it to a new `sespy/utils.py` as the very first implementation step so both `isa_data_entry` and `wizard.py` can share it. The promotion is a three-part change: (a) create `sespy/utils.py` with `next_id(existing_ids, prefix)` (now public, no leading underscore), (b) **delete** the private `_next_id` from `isa_data_entry.py` and replace its sole call site with `from ..utils import next_id` + `next_id(...)`, (c) `wizard.py` imports the same. **No private copy remains anywhere** — the two implementations cannot diverge because there is only one. Signature: `next_id(existing_ids: list[str], prefix: str) -> str` — first arg is a list of id strings (NOT `Element` objects); wizard call: `next_id([e.id for e in current.isa_data.elements], prefix)`.

When the user clicks Next on a `freeform_multiple` step (4-10), the handler runs in this exact order (pinning the order matters for reactive correctness):

1. **Validate**: read inputs; ensure at least one non-empty entry; no duplicates within the step. On failure: show toast + return without state change.
2. **Build `new_isa_data`**: copy the current `IsaData` and append one new `Element(id=_next_id(...), label=entry, type=ELEMENT_TYPE_MAP[step.target])` per entry.
3. **Build `new_project`**: `Project(metadata=current.metadata, isa_data=new_isa_data)` — keeps metadata intact.
4. **`project_data.set(new_project)`** — single reactive write that propagates to every downstream module.
5. **`event_bus.emit_isa_change()` AND `event_bus.emit_cld_update()`** — both signals: `isa_change` for stale-data warnings on analysis modules + autosave; `cld_update` so the CLD canvas refreshes live (the CLD module subscribes to `cld_update`, not `isa_change`, per `cld_visualization.py`'s reactive flow). Steps 2 and 3 (`countries`, `main_issue`) are ephemeral and DO NOT call `project_data.set()` or emit anything — they only update `wizard_answers`.
6. **`wizard_answers.set({...wizard_answers.get(), step.target: entries})`** — record what was answered for SP3/SP4 access.
7. **`wizard_step.set(wizard_step.get() + 1)`** — LAST so the step renderer fires once after everything else has settled.

For step 0 (regional_sea) and step 1 (ecosystem_type), the same 7-step order applies — including emitting **both** `isa_change` AND `cld_update`, consistent with how `pims_project.py::_handle_save` emits `isa_change` even for metadata-only writes. Step 2 of the sequence becomes "build new `metadata` with the answer, then build new `Project(metadata=new_meta, isa_data=current.isa_data)`" instead of touching `isa_data`.

For step 11 (connection_review), the user sees suggested connections (empty in SP1) and can accept some. Accepted suggestions get written via the same pattern: build a new `IsaData` with the appended `Connection` objects, build a new `Project`, call `project_data.set`, emit `isa_change`. Then the wizard finishes (sets `wizard_active=False`).

### Where the wizard lives

- `NAV`: insert `NavItem(id="wizard", icon="wand-magic-sparkles", label="SES Wizard", label_key="nav.wizard")` after `templates` (so the create stage reads: PIMS → Templates → SES Wizard → Edit Data).
- `NAV_TO_STEP`: `"wizard": "create"`.
- `PANELS`: `ui.nav_panel("SES Wizard", ai_isa_wizard_ui("wizard"), value="wizard")` after `templates`.
- Server registration: `ai_isa_wizard_server("wizard", project_data=project_data, event_bus=event_bus, translator=T)`.

### i18n keys (~50)

Approximate key list:

```
nav.wizard
wizard.title
wizard.start
wizard.next
wizard.back
wizard.finish
wizard.cancel
wizard.replace
wizard.modal_title
wizard.modal_body
wizard.no_suggestions
wizard.step_0_title  ... wizard.step_11_title  (12 keys)
wizard.step_0_question ... wizard.step_11_question  (12 keys)
wizard.placeholder_drivers
wizard.placeholder_activities
wizard.placeholder_pressures
wizard.placeholder_states
wizard.placeholder_impacts
wizard.placeholder_welfare
wizard.placeholder_responses
wizard.add_another
wizard.remove
wizard.regional_sea_label
wizard.ecosystem_type_label
wizard.countries_label
wizard.main_issue_label
wizard.connection_suggestions_table
wizard.confidence
wizard.rationale
wizard.accept
wizard.reject
```

### Dependencies

None new. Uses existing Shiny, dataclasses, json. No matplotlib (text-driven UI only).

### Persistence

The wizard's state (`wizard_step`, `wizard_answers`, `wizard_active`) is **session-only** — refresh resets. Elements written to `project_data` during the wizard persist as normal project state (autosaved, savable to file). Matches every other SESPy module's default.

## 3. Components & Data Flow

### Reactive stores (module-local)

- `wizard_step: reactive.value(0)` — current step index, 0-11.
- `wizard_answers: reactive.value({})` — dict from step.target → answer (str | list[str]).
- `wizard_active: reactive.value(False)` — True only after Start (and modal-resolved).

### Effects (write project_data)

- `_on_start` — confirmation modal logic; if no existing elements, just sets wizard_active=True directly.
- `_on_modal_replace` — preserves metadata, clears `isa_data`, **clears `wizard_answers`** (so a stale partial run from earlier doesn't contaminate the new run), sets wizard_active=True, jumps to step 0, and emits **both** `isa_change` and `cld_update` (so autosave + CLD react immediately to the clearance, not on the user's next click).
- `_on_modal_cancel` — closes modal via `ui.modal_remove()`. No state change needed: `wizard_active` is guaranteed `False` at this point by construction (the modal is only shown when `wizard_active is False` per the `_on_start` flow), so Cancel preserves that.
- `_on_next` — **MUST guard with `if wizard_step.get() >= 11: return`** at the top (symmetric with `_on_finish`'s `!= 11: return` guard — the Next button is hidden via CSS on step 11 but the input is still fireable by automation). Validates current step's answer; writes elements (steps 4-10) or metadata (steps 0-1); increments wizard_step. Step 11's connection writes go through `_on_finish`, NOT `_on_next`.
- `_on_back` — decrements wizard_step. Doesn't undo writes (R behavior).
- `_on_finish` — fires on `wizard_finish` button click. **MUST guard with `if wizard_step.get() != 11: return`** before acting — the Finish button is hidden via CSS `display:none` on other steps, but a stray JS call (e.g. an automation driver) could still fire the input. Sets `wizard_active=False`.

(There is no `_on_modal_save_first` handler — the original three-button modal design with programmatic Save was replaced by a two-button modal + tip text. See §2 Confirmation modal flow.)

### Renderers

- `wizard_breadcrumb` — pills of step titles, current highlighted, completed marked. Returns `ui.tags.div()` (empty) when `wizard_active.get() is False` so the inactive state shows just the Start button cleanly.
- `wizard_step_render` — dispatches on `step.archetype` to the right widget.

**Pre-population on re-entry.** When the user navigates Back to a previously visited step, the renderer MUST restore the prior selection from `wizard_answers` so the widget shows what was there:
- `choice_one` → `selected=wizard_answers.get().get(step.target, "")` on `ui.input_radio_buttons`/`ui.input_select`.
- `choice_many` → `selected=wizard_answers.get().get(step.target, [])` on `ui.input_selectize(multiple=True)`.
- `freeform_multiple` → render one input row per saved entry; values from `wizard_answers.get().get(step.target, [])`.

Without pre-population the user would see a default-empty widget on re-entry — the data is still in `project_data` but the UI looks blank, which contradicts the documented "Back doesn't undo writes" invariant.

**`freeform_multiple` input-id scheme.** Use indexed ids: `entry_{step.target}_{i}` (e.g. `entry_drivers_0`, `entry_drivers_1`). The renderer keeps a `reactive.value[dict[str, int]]` mapping `step.target → entry_count` so Add/Remove buttons can manage the count without losing typing-in-progress. Stable ids across renders is the key invariant — re-rendering the list (e.g. after a Remove click) MUST reuse the same id slots for surviving entries.

### Data flow diagram

```
[Start button] → _on_start ──► (project has elements?) ──► modal → user picks
                                       │ no
                                       ▼
                              wizard_active=True; step=0
                                       │
[Next clicks N times]                  ▼
              _on_next ──► validate input → write to project_data → step += 1
                                                  │
                                                  ▼
                              event_bus.emit_isa_change()
                              event_bus.emit_cld_update()
                                                  │
                              CLD / analysis modules see growing SES
                                                  │
                                       (eventually step==11)
                                                  ▼
                              suggest_connections(state) → [] (SP1)
                                                  │
                              user accepts some → connections written
                                                  │
                              [Finish] → wizard_active=False
```

### Stub `suggest_connections` integration

The connection-review step (#11) calls `from sespy.wizard import suggest_connections`. SP1 returns `[]` so the table is empty. The renderer shows `t("wizard.no_suggestions")` ("No connection suggestions available — enable a scoring backend in settings.").

**Invocation timing**: `suggest_connections(state)` is called **once** when step 11 is entered (i.e., when `wizard_step.set(11)` is committed). The result is stored in a local module reactive `wizard_suggestions: reactive.value([])` and rendered statically — re-entering step 11 (e.g., user clicks Back from the connection-review then Next again) re-invokes `suggest_connections` with a fresh state snapshot. This keeps SP3/SP4 backends from having to be reactive themselves; they're pure functions called at known moments.

**WizardState assembly** (called at step 11 entry):

```python
def _assemble_wizard_state() -> WizardState:
    answers = wizard_answers.get()
    isa = project_data.get().isa_data
    return WizardState(
        regional_sea=answers.get("regional_sea", ""),
        ecosystem_type=answers.get("ecosystem_type", ""),
        countries=answers.get("countries", []),
        main_issue=answers.get("main_issue", []),
        elements=list(isa.elements),  # snapshot
    )
```

Note that `WizardState.elements` comes from `project_data` (the truth-of-record), NOT from `wizard_answers`. The other fields come from `wizard_answers` because countries/main_issue are ephemeral (never persist to project file).

When SP3 or SP4 lands, the stub is replaced; the wizard module doesn't change.

## 4. Error Handling

### Validation per step

| Step | Validation |
|---|---|
| 0 (regional_sea) | non-empty (a sea was picked) |
| 1 (ecosystem_type) | non-empty |
| 2 (countries) | at least 1 country |
| 3 (main_issue) | at least 1 issue |
| 4-10 (freeform_multiple) | at least 1 non-empty, non-whitespace entry; no duplicate labels within the step |
| 11 (connection_review) | always allowed (Finish button enabled regardless of suggestions count) |

If validation fails, show a transient `ui.notification_show(t("wizard.error_X"), type="warning", duration=3)` and don't advance.

### Mid-wizard navigation

The user CAN navigate away from the wizard panel (e.g., click `nav.cld` to peek at the partial CLD). The wizard's reactive state survives. Coming back lands them on the same step with the same answers. This is the in-session resume guarantee.

### Refresh / app restart

Refresh kills all reactives. The user lands on step 0 of an empty wizard, but `project_data` retains whatever was written via live writes. They can either re-start the wizard (with the modal, since project_data has elements) or pick up via Edit Data manually. This matches R behavior; not a regression.

### `next_id` collisions

Live writes call `utils.next_id([e.id for e in current.isa_data.elements], prefix)` — the public helper promoted to `sespy/utils.py` per the §2 Prerequisite. First arg is a list of **id strings**, not `Element` objects. If the user manually adds elements via Edit Data BEFORE starting the wizard (then chooses Continue, replace it in the modal), `project_data` is reset to empty — no collision risk. If they don't reset (which can't happen in SP1 because Continue mandatorily resets), there's no conflict path.

### No fatal paths

All step-validation failures land as toasts. No `req(False)` or unhandled exceptions in the reactive flow. The `suggest_connections()` stub is pure (returns `[]`); SP3/SP4 will need their own error handling for failed scoring (out of scope here).

## 5. Testing

### Unit tests (extend `tests/test_data_structure.py`)

About 3 new tests for the new dataclasses:

- `WizardState` defaults to empty fields.
- `ConnectionSuggestion(source="A", target="B", polarity="+", confidence=0.7, rationale="...")` constructs cleanly.
- `suggest_connections(empty_state)` returns `[]` (SP1 stub).

### E2e test (`tests/test_wizard_e2e.py`)

6 cases (covers full state-machine including Back, validation failure, Finish-clears-active):

1. **Empty project — full 12-step run.** Start with empty project. Click `#wizard-wizard_start` (no modal expected). For each step 0-10, fill in valid answers, click `#wizard-wizard_next`. On step 11, click `#wizard-wizard_finish`. Assert: `project_data` has the expected number of elements (sum of entries across steps 4-10), `metadata.regional_sea` is set, `wizard_active=False` (Start button visible again).

2. **Non-empty project — modal cancel.** Load Coastal Tourism SES template. Navigate to wizard. Click Start. Modal appears. Click Cancel (`#wizard-wizard_cancel_modal`). Assert wizard_active stays False, project_data unchanged.

3. **Non-empty project — modal replace.** Load template. Click Start. Modal appears. Click `#wizard-wizard_replace`. Assert project_data is reset to empty, wizard_active=True, breadcrumb shows step 0.

4. **Mid-wizard nav and resume.** Start wizard, advance to step 3, navigate away to CLD via `#sespy_nav_cld`, navigate back via `#sespy_nav_wizard`. Assert breadcrumb shows step 3, answers from steps 0-2 are preserved. (Note: this case requires the `wizard` nav item to be wired into `app.py` first; run only after that wire-up step is complete, not against an intermediate skeleton.)

5. **Back button preserves writes.** Start wizard, advance through step 4 (drivers) entering 2 drivers. Click Next to land on step 5. Click `#wizard-wizard_back` to return to step 4. Assert: step is back to 4 with the 2 driver entries still in the form, AND `project_data.isa_data.elements` still contains the 2 driver elements (Back doesn't undo writes — matches R behavior; this is the documented invariant).

6. **Validation failure on freeform step.** On step 4 (drivers), leave all entry fields empty. Click Next. Assert: a `.shiny-notification` warning appears, breadcrumb still shows step 4 (didn't advance), `project_data` unchanged.

The selectors use the module-namespaced id pattern: `#wizard-<input_id>` for buttons inside the wizard module's UI. Modal buttons are also namespace-prefixed because `ui.modal_show()` is called from within the module's server.

### Coverage targets

- `sespy/wizard.py` — pure helpers, ~95% line coverage via unit tests.
- `sespy/modules/ai_isa_wizard.py` — covered only by the e2e (reactive callbacks aren't usefully unit-testable).

## 6. Architectural conventions to reuse

These are pinned in `sespy_port_context.md` memory:

- **`project_data` is `reactive.Value[Project]`** — use `project_data.get().isa_data.elements` for elements, `project_data.get().metadata` for metadata writes.
- **i18n keys** must be inside the `"translation"` wrapper of `core.json` (this is a load-time trap caught during PIMS).
- **Action buttons** need `@reactive.event(input.X, ignore_init=True)`.
- **Defensive input reads:** `(input.X() or "").strip()`.
- **Modules emit `isa_change`** on element/connection writes.
- **Selectize-wrapped inputs in e2e** need `Shiny.setInputValue(...)`, not native `<select>` manipulation.
- **`@output @render.ui` pattern** for dynamic-UI rendering — used in `wizard_breadcrumb` and `wizard_step_render`.
- **i18n labels on `@module.ui`** capture language at construction time. Reactive UI in `@render.ui` updates live.

## 7. Roll-out plan

1. Branch: `feat/ai-isa-wizard-sp1` off `main`.
2. Implementation order: data_structure additions + 3 unit tests → wizard.py (pure data + stub) → i18n batch → module skeleton → step renderers → state machine effects → confirmation modal flow → app.py wiring → e2e test → README.
3. Browser smoke-test before pushing.
4. Fast-forward merge to `main`.
5. Hand the WizardState / ConnectionSuggestion contract to SP2 (regional-seas KB) and SP3 (default scoring backend).

## 8. Estimated effort

~13 hours of focused work, typically 2-3 working days when iterating with reviews. Slower than PIMS (~5h) because the dynamic-UI list for `freeform_multiple` archetypes is non-trivial.

| Task | Time |
|---|---|
| Dataclasses + 3 unit tests | 30 min |
| wizard.py (12-step data + stub) | 1 h |
| i18n batch (50 keys × 9 langs) | 45 min |
| Module skeleton + breadcrumb renderer | 1 h |
| Step archetype renderers (4 archetypes) | 2.5 h |
| State machine effects (start/next/back/finish + 4 modal handlers) | 2 h |
| Confirmation modal UI + wiring | 45 min |
| app.py NAV/STEPPER/PANELS wiring | 30 min |
| Live-write logic for steps 0-1 (metadata) and 4-10 (elements) | 1 h |
| Step 11 connection-review renderer (with SP1's empty-list stub) | 1 h |
| E2e test (6 cases) | 2.5 h |
| README + memory updates | 30 min |

## 9. Risks / known unknowns

- **Element-type mapping for impacts/welfare** — resolved. The codebase's `ELEMENT_ID_PREFIX` (`sespy/constants.py:20-28`) is the authority: `impacts → Ecosystem Services`, `welfare → Goods & Benefits`. The §2 table now matches.
- **`country_multiple` step and SP2 dependency**: step 2 needs a list of countries to choose from. SP1 will hardcode a small placeholder list (~10 countries). SP2 (KB) will replace it with the real KB's per-region country lists.
- **Step 3 (`main_issue`) suggestions placeholder**: step 3 also draws from the regional-seas KB (each sea has its own `common_issues`). SP1 hardcodes a small per-sea placeholder dict (3-5 issues per sea) co-located with the country-list placeholder. SP2 replaces it.
- **Shiny for Python `ui.modal_show()` namespacing — verify before relying**: when the modal body is constructed inside `@module.server` and shown via `ui.modal_show(...)`, the input ids of `ui.input_action_button` widgets inside the modal SHOULD be auto-namespaced under the module prefix (so `wizard_replace` becomes `#wizard-wizard_replace` in the DOM and `input.wizard_replace` in the server). The codebase has no existing `ui.modal_show()` call from inside a module server to confirm this. The implementer MUST do a quick spike (write a minimal modal in the wizard skeleton and inspect the DOM) BEFORE writing the rest of the modal flow. If namespacing doesn't apply automatically, the workaround is to construct the modal body using `session.ns(...)` to manually prefix ids. Failure mode if unverified: the modal renders, the buttons appear clickable, but `_on_modal_replace` and `_on_modal_cancel` never fire.
- **Mock KB shape is an interface contract for SP2**: the SP1 placeholder dict in `sespy/wizard.py` will use the shape `{"baltic": {"name": "Baltic Sea", "ecosystem_types": [...], "countries": [...], "common_issues": [...]}, ...}`. SP2 must produce data with the same key structure. This shape is the SP1→SP2 contract; SP2 may add fields but must not rename or restructure these.
- **`ConnectionSuggestion` → `Connection` field gap (SP3 concern, noted here for completeness)**: `Connection` has fields the wizard doesn't naturally produce — `strength` (default `"medium"`), `delay` (default `"immediate"`), and `confidence` is `int 1-5` whereas `ConnectionSuggestion.confidence` is `float 0..1`. SP3 must define the float-to-int mapping (e.g. `int(round(suggestion.confidence * 4)) + 1`) and pick reasonable strength/delay defaults. SP1 has no impact (stub returns `[]`).
- **Modal "Save first" was originally specified as a third button** that programmatically triggered the global download. That design was found unimplementable (download_button has no programmatic trigger; JS .click() opens browser Save-As dialog with no callback). The spec now uses a two-button modal + tip text. No risk remaining — call this resolved.
- **Live writes during the wizard mean the user can ABANDON the wizard halfway**: their partially-built SES is real, not a draft. This is intentional (matches R) but worth flagging for UX testing.
- **`freeform_multiple` dynamic UI complexity**: Shiny for Python's pattern for "list of inputs with Add/Remove buttons" is `@render.ui` with `reactive.value[list[str]]` driving the rendered list. Each Add/Remove has its own indexed action button. This is more complex than a single `input_text_area` and historically a source of subtle reactive bugs (input ids must remain stable across renders, otherwise typing-in-progress is lost). Implementer should sanity-test the typing-then-add flow before considering steps 4-10 complete.
- **Stub `suggest_connections` returning `[]`**: makes step 11 functionally a no-op in SP1 — the user just clicks Finish without reviewing anything. SP3 makes this step meaningful. Acceptable for SP1.

## 10. Non-goals

- Full localization to Lithuanian/Greek/etc. — placeholder English values for non-EN languages, same as BOT/PIMS.
- Animation, custom CSS, or visual polish from `ai_isa_assistant_module.R` (welcome animations, decorative help modals).
- Persistence of `countries` and `main_issue` answers to project file — they're consumed by `suggest_connections()` and discarded.
- Cross-session wizard resume — no autosave integration; refresh resets.
- Mobile/responsive layout — same as the rest of SESPy (desktop-first).
- Multi-user collaboration — single-user wizard, same as the rest of SESPy.
