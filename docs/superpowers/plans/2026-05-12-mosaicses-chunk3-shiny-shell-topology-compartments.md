# MosaicSES Chunk 3: Shiny Shell + Topology + Compartments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Shiny shell + the two architecturally-risky UI modules — Topology editor and Compartments switcher — on top of chunks 1+2. End state: `shiny run app.py` opens the Curonian seed, the user sees the 6-compartment topology, clicks into a compartment, and SESPy's CLD/Loops/Metrics modules work against just that compartment.

**Architecture:** A new `multises_app/` package sits alongside `multises/` (which stays Shiny-free). `app.py` wires `sespy.dashboard.dashboard_page` with two NEW nav panels — `topology` and `compartments` — plus a thin Project Setup placeholder. The Compartments module is the architectural pivot from the chunk-3 pre-spike: it owns the **shared `active_compartment_project: reactive.Value[Project]`** that embedded SESPy modules read, and it implements the switcher protocol (rebind + `event_bus.emit_isa_change()`) and the backwrite listener (id-captured + `reactive.isolate()`-wrapped read) from design spec §7.3.

**Tech Stack:** Python 3.11+; Shiny-for-Python ≥1.5 (already installed in `shiny` env); `pyvis>=0.3` for the topology canvas; `sespy.dashboard`/`sespy.event_bus`/all 9 SESPy compartment-level modules re-mounted unchanged; `multises.seed_curonian()` as default project; pytest for unit + contract tests. Playwright e2e is **chunk 4**, not here — chunk 3 ships behind contract tests + a manual smoke checklist.

**Companion spec:** `docs/superpowers/specs/2026-05-08-mosaicses-design.md`. Section references in this plan refer to that spec.

**Companion pre-spike:** `MosaicSES/docs/2026-05-12-chunk3-prespike-results.md` — four-invariant static verification + `tests/test_compartment_switcher_contract.py`. The pre-spike already shipped (commit `d1acc25`).

**Working directory throughout:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES/`. Run pytest via `micromamba run -n shiny pytest ...`. Run python via `micromamba run -n shiny python ...`. Launch app via `micromamba run -n shiny shiny run --launch-browser app.py`.

### Revision log

- **2026-05-12 (initial)** — Plan drafted following design spec §10.3 pre-spike completion. 14 tasks (1, 1.5, 2-14).
- **2026-05-12 (third in-depth review pass)** — Six-agent review (security / accessibility / cross-platform / documentation / edge-cases / observability). 12 critical+important fixes applied; ~25 lower-priority items deferred to chunk-4 with documentation:

  **Critical fixes (would-have-broken or excluded users):**
  - **`app.py` adds `logging.basicConfig`** (Observability F1) — without it, EVERY `_log.warning` / `_log.error` call across chunks 1+2+3 was silent because every module uses `NullHandler`. Default level WARNING, `LOGLEVEL` env-var override.
  - **Pyvis label/title HTML-escaped + `multi: "html"` removed** (Security F3) — a colleague-supplied JSON with `"label": "<script>..."` would have flowed into pyvis with `multi: "html"` enabled, potentially executing in the browser. Now `html.escape()` on every user-supplied string AND plain-text label rendering.
  - **`lang="en"` on `<html>` element + visually-hidden `<h1>`** (A11y F10, F11) — WCAG SC 3.1.1 (Level A) and SC 2.4.6. JS-based `document.documentElement.lang = 'en'` injection in `head_content`; Bootstrap `visually-hidden` class for the h1.
  - **`_switch_active_compartment` checks `_switching.get()`** (Edge case EC4) — without this guard, the snap-back's reactive sets could cascade through `_populate_picker → ui.update_select → input.compartment_picker` to spuriously re-fire the switcher itself. Now both directions of the cascade are blocked.
  - **`test_compartments_server_backwrite_snaps_back_on_keyerror` tightened** (Edge case EC10) — the original assertion `"active_compartment_id.set(" in src` was a false-positive because `_populate_picker` also contains that string. Now asserts `>= 2` occurrences AND verifies the snap-back occurs AFTER `except KeyError:` in source order.
  - **Task 11 Step 0 multi-line `python -c` rewritten as a `.py` script** (Cross-platform F9) — PowerShell double-quoted strings don't accept embedded newlines. Now uses `@'...'@` here-string to write `.tmp_signature_probe.py`, then executes it, then cleans up.

  **Important fixes (quality + onboarding):**
  - **Snap-back logs `fallback_id`** so operators can correlate the error with the resulting state (Observability F2).
  - **`ui.notification_show(...)` on snap-back** so the user sees an explanation toast instead of an unexplained compartment switch (Observability F9).
  - **Backwrite happy-path DEBUG log + topology-rebuild DEBUG log + switcher DEBUG log** — gives the developer an audit trail when debugging "why is my edit gone?" or "why is the canvas slow?" (Observability F3, F4, F5).
  - **Task 14 `tail -40` → `Select-Object -Last 40`** (Cross-platform F4) — `tail` is not a PowerShell cmdlet.
  - **README "Run the app" section added to Task 12** (Docs F1+F8) — closes the most common onboarding dead-end (clone → install → test → ??).
  - **`.gitattributes` added to Task 12** (Cross-platform F3) — enforces LF line endings cross-platform, prevents whitespace diffs when Linux/macOS collaborators commit.

  **Deferred to chunk 4 (third-pass review findings explicitly NOT fixed; documented here):**
  - `ARCHITECTURE.md` (Docs F2) and `CONTRIBUTING.md` (Docs F16+F17) — separate documentation sprint, not a chunk-3 deliverable.
  - Shape-per-archetype in pyvis (A11y F2) — color-blind discrimination polish, chunk-4 with the LOAC-hierarchical layout.
  - Pyvis canvas `aria-label` + `<figcaption>` skip-link (A11y F1) — chunk-4 with focus management.
  - Inspector dropdown labels using `Type: label` notation (A11y F8) — chunk-4 with editor controls.
  - Channel dropdown filtering for dangling endpoints (Edge case EC6) — chunk-4 with topology editing.
  - JSON schema docstring on `seed_curonian()` (Maintainability F5 / Docs F9) — chunk-4 docs sprint.
  - `SCIENTIFIC_BASIS.md` pointer file (Docs F6+F12) — chunk-4 docs sprint.
  - HTTP security headers (Security F12), `persistence.save` path sanitization (Security F7), translator session-isolation audit (Security F4) — all chunk-4 pre-deployment items.
  - Focus management on compartment switch (A11y F5) — chunk-4 with Playwright JS bridge.
  - `analysis_simulation` / `analysis_bot` stale-store auto-clear — SESPy upstream concern.

- **2026-05-12 (second in-depth review pass)** — Five-agent review (performance / maintainability / determinism+flakiness / chunks-1+2 idiom consistency / scientific accuracy / subagent execution risk). Applied changes:

  **Hard blockers fixed:**
  - **Task 0 test key**: `classify_loops()` returns dicts with key `"type"`, not `"polarity_type"` (the latter only exists on `CrossLoop` dataclass). Changed `c.get("polarity_type")` to `c.get("type")` in `test_seed_curonian_lagoon_eutrophication_governance_loop_exists`. Would have failed on every run.
  - **Task 0 loop tautology**: `P002 (Hypoxia) → MPF003 (Bottom-water DO) [-]` is causally circular under DAPSI(W)R(M) (hypoxia IS low DO). Replaced P002 with P003 (Algal blooms — already in archetype defaults), giving the scientifically correct mechanism: eutrophication → cyanobacterial bloom formation → bloom-collapse oxygen demand → DO depletion. Polarity arithmetic unchanged (still 3 negatives → Balancing).
  - **Tasks 9 + 10 source-inspection target**: `@module.server` wraps the function and `inspect.getsource(compartments.compartments_server)` returns wrapper source, not body. Changed to `inspect.getsource(_comp_mod)` (full module) — matching the pre-spike's working pattern. All 5 contract tests would have failed on every run.
  - **Task 2 `git add`**: Original commit step listed only 2 of the 4 modified files. Updated to include `multises/data_structure.py` + `tests/test_data_structure.py` (the new library helper + its tests). Without this, Task 10's import of `replace_compartment` would fail with `ModuleNotFoundError`.
  - **Task 10 import instruction**: Original "extend the existing import line" wording would have likely produced `from ..state import MultiSESState, replace_compartment` (single bad import). Rewrote as: explicit "add a NEW import line BELOW the existing one" with explanation that the two symbols live in different modules.
  - **Task 12 Step 5 server launch**: `shiny run app.py` is blocking; automated subagent would stall. Added `SKIP_IF_AUTOMATED_SUBAGENT` instruction and an in-process import-smoke alternative (`python -c "import app; print(app.app)"`) that covers the same regression class.

  **Scientific accuracy refinements (Reviewer #5, marine-science angle):**
  - R001 renamed from "BSAP nutrient-cap response" to "National eutrophication management programme (BSAP-derived)" — BSAP is regional intergovernmental, lagoon-level instruments are MSFD-derived national programmes.
  - GB001→R001 and R001→P001 strengths downgraded to `"weak"` with `confidence: 2` — HELCOM BSAP compliance ~30%, Curonian/Nemunas N-loads not trending down per Stakėnienė 2023 and Čerkasova 2021. Direction correct; effective magnitude weak.
  - All 5 new connections now carry explicit `confidence` values (P001→P003: 4 per Bartoli/Žilius; P003→MPF003: 4; MPF003→GB001: 3; GB001→R001: 2; R001→P001: 2). Previously implicit defaults.
  - §8.4 mislabel corrected: Task 0's loop is now explicitly framed as a within-lagoon SURROGATE, not "§8.4 within-lagoon portion" (§8.4 is purely cross-compartment). Test docstring updated.
  - Added `test_seed_curonian_lagoon_connections_survive_save_load_roundtrip` to guard against `Compartment.to_dict()` silently dropping the Task 0 connections (Determinism Finding 10).

  **Performance + maintainability quick wins:**
  - `node_ids` set rebuild hoisted OUT of the channel loop in `_build_topology_network` (Performance Finding 1; O(C×N) → O(N+C)).
  - `_log.warning(...)` added for unknown archetype and unknown channel-type fallbacks (Maintainability Finding 2; converts silent grey-rendering into a logged event).
  - `_log.warning(...)` added for dangling-channel skip in topology canvas (was previously silent).
  - Snap-back code in Task 10 backwrite listener now wraps `set()` calls in the `_switching` guard (Maintainability Finding 11) to prevent re-entrant listener fire during error recovery.

  **Determinism + idiom-drift fixes:**
  - `test_build_topology_network_returns_pyvis_network` derives counts from `len(ms.compartments)` / `len(ms.channels)` instead of hardcoded `6` / `26` (Determinism Finding 3).
  - `test_build_topology_network_archetype_colors_distinct` looks up compartments by id instead of `zip(net.nodes, ms.compartments)` positional pairing (Determinism Finding 4).
  - `test_app_module_loads` saves and restores `sespy.i18n` default translator to prevent global-state contamination of subsequent tests (Determinism Finding 7).
  - `_switching.is_set()` removed from the contract test (not a Shiny method); only `_switching.get()` accepted (Determinism #9 wrap-up).
  - Task 0's `_SElement(**e_raw)` and `_SConn(**ch_raw)` now wrapped in `MultiSESIntegrityError` to match the chunk-1+2 loader pattern (Consistency Finding 12).
  - `replace_compartment` now re-exported from `multises/__init__.py` (Consistency Finding 1, the `__all__` gap).

  **Subagent-execution defensive notes added:**
  - Task 10 explicitly says "DO NOT redeclare `_switching` at module level — capture it from `compartments_server`'s closure scope" (Subagent Risk F2).
  - Task 9's `_switching: reactive.Value[bool] = reactive.value(False)` line carries an inline note that `reactive.value(...)` is the CONSTRUCTOR and `reactive.Value[...]` is the TYPE annotation; `reactive.Value(False)` would not work (Subagent Risk F13).
  - Task 11 pre-flight signature probe is now an explicit checkboxed Step 0 with instruction to update the `expectations` table from the probe output AND record the kwarg list in the commit message (Subagent Risk F4, F5).
  - Task 11 `expectations` table now ships with the correct kwarg sets for all 10 modules (verified at plan-write time): only `cld_viz_server` and `analysis_loops_server` lack `translator`.
  - Task 13 Step 2 explicitly instructs automated subagents to mark `SKIPPED_AUTOMATED_SUBAGENT` and return `DONE_WITH_CONCERNS` (Subagent Risk F6).
  - Task 0 Step 2 JSON edit instruction now specifies the EXACT old_string to match (single-line lagoon entry) and explicitly forbids sed/regex (Subagent Risk F8).

  **Accepted as v1 limitations (documented, not fixed):**
  - Source-inspection tests still use string-match patterns rather than full AST traversal — refactor-fragile but acceptable for chunk-3 contract pinning. Chunk-4 Playwright will cover semantic correctness.
  - 5 non-lagoon compartments still have empty intra-compartment connections — chunk 4 polish.
  - `logging.getLogger("multises")` flat name instead of `__name__` per module — chunk-1 convention; changing breaks chunk-1+2 too.
  - 6-point module-registration pattern for SESPy module additions — chunk-4 refactor opportunity.
  - `analysis_simulation.sim_store` / `analysis_bot` stale-store auto-clear — SESPy upstream limitation.

- **2026-05-12 (first in-depth review pass)** — Five-agent review (architectural soundness / spec coverage / silent failures / test coverage / executability + forward-compat + scientific UX). Applied changes:

  **Scientific blocker fixed:**
  - **Task 0 (NEW)** — adds intra-compartment Connections + a Response element to the Curonian Lagoon compartment so the eutrophication-governance balancing loop fires within the lagoon. Without this, `Loop Analysis → Detect` returns empty results for every compartment and the smoke checklist's "cycles appear" item fails trivially. Task 0 also extends `seed_curonian()` to honour per-compartment `connections` / `elements_extra` overrides from the JSON.

  **Backwrite safety fixes (Reviewer 1 Issue 3 + Reviewer 3 C-1, I-1):**
  - **Task 10** rewritten — the listener now wraps BOTH `active_compartment_id.get()` AND `active_compartment_project.get()` in `reactive.isolate()` (the original plan only isolated the project read). On `KeyError` from `replace_compartment`, the listener now snaps `active_compartment_project` + `active_compartment_id` back to the first remaining compartment and logs at ERROR level, instead of silently dropping the edit.
  - **Task 9** adds a `_switching` boolean guard set True before `emit_isa_change()` and reset False after `active_compartment_id.set(new_id)`. The Task 10 listener no-ops while `_switching` is True, preventing the double-emit race (Reviewer 3 I-1).
  - **Task 9** documents the verified Shiny 1.5 behaviour for the input-flush concern: `@reactive.event(input.compartment_picker, ignore_init=True)` does NOT auto-flush pending text inputs in nested SESPy modules. The plan accepts this v1 limitation and adds a smoke-checklist item to verify the trade-off.

  **Code-drift fixes (Reviewer 3 + Executability reviewer):**
  - **Task 2** — `replace_compartment` reconstructs `Compartment` with ALL 8 fields preserved (`id, label, archetype, project, description, geometry, is_focal_tw, _unknown_archetype_original`), not just the 4 the original plan listed. Function moved to `multises/data_structure.py` as a pure library helper (Reviewer 1 Issue 1) so it can be tested without Shiny and so `multises_app/state.py` keeps its "Shiny-bridge only" responsibility.
  - **Task 12** — `app.py` uses `from sespy.i18n import set_default` directly (eliminating the bare-`sespy` import that would have broken the allow-list scanner if extended to `app.py`).
  - **Task 12** — `_ALLOWED_SESPY_IMPORTS` adds `"sespy"` and `"sespy.modules"` (parent paths), and the scanner now covers `app.py` in addition to the two package directories (Reviewer 4 R5).
  - **Task 12** — `pyproject.toml` uses spec-compliant `sespy @ file:///${PROJECT_ROOT}/../SESPy` path-dep + adds `networkx>=3.2` to the declared deps (Reviewer 2).
  - **Task 10** — "Add the import at the top" instruction rewritten as "extend the existing `from ..state import ...` line" to prevent duplicate-import errors (Executability reviewer T10-A).
  - **Test-count math** — all task totals corrected by −1 (baseline is 200, not 201) (Executability reviewer).

  **New tests (Reviewer 4 + Reviewer 3 I-4):**
  - **Task 12** — `test_multises_library_has_no_shiny_imports` enforces the §2.1 "library is Shiny-free" architectural rule via AST scan (R1, blocking).
  - **Task 12** — `test_app_module_loads` smoke test catches `app.py` startup regressions invisible to other tests (R2).
  - **Task 11** — `test_sespy_module_server_signatures_accept_expected_kwargs` catches future SESPy signature drift, replacing the original plan's "track in commit message" non-guard (I-4).
  - **Task 2** — `test_replace_compartment_preserves_unknown_archetype_original` pins the forward-compat invariant (R3).
  - **Task 9** — additional ORDER assertion: `set(` index precedes `emit_isa_change()` index (R4).

  **Deferred to chunk 4 (with explicit rationale, addressing Reviewer 2 spec-coverage gaps and Reviewer 5 scientific-UX gaps):**
  - **§7.2 left-column add/remove/rename buttons + archetype dropdown** — chunk 3 ships a read-only compartments list. Editing affordances move to chunk 4 alongside the Project Setup form. Rationale: read-only is sufficient to validate the architecture; editing requires the same mutation helpers that Project Setup needs.
  - **§7.2 inspector polarity/strength/confidence editors** — chunk 3 ships read-only inspector detail. Editor controls move to chunk 4 alongside the Comparative panel's intervention UI.
  - **§7.2 "Seed diadromous channels" + "Suggest neighbours" buttons** — chunk 4 polish; Curonian seed is pre-populated so these conveniences are not needed for the v1 demo.
  - **Hierarchical `typical_position`-aware pyvis layout** (Reviewer 5) — chunk 4 visual polish. v1 ships physics-driven layout which is correct, just not LOAC-encoded spatially. Smoke checklist documents this as a known v1 limitation.
  - **Save / Load UI buttons** (Reviewer 5) — chunk 4 ships these alongside the Project Setup form. v1 user must use `persistence.save()` from a Python session manually.
  - **`analysis_simulation.sim_store` / `analysis_bot` store invalidation** (Reviewer 1 Issue 9) — these SESPy modules show "stale" toasts but don't auto-clear on compartment switch. v1 smoke checklist adds a "Simulation staleness" verification item; the proper fix is upstream in SESPy and lands with chunk 4.

---

## Chunk-3 scope decisions (read these before starting any task)

1. **What ships in chunk 3:** the Shiny app skeleton, the Topology editor module, the Compartments switcher module + its embedded SESPy modules, and the bridge state (`multises_app/state.py`) that owns the shared reactives. The Curonian seed loads as the default project.

2. **What ships in chunk 4 (NOT here):**
   - `comparative.py` UI panel (priority A grid — 5 cards built on `multises.comparative.*` functions from chunk 2).
   - `cross_view.py` UI panel (priority B composite view — 3 cards built on `multises.composite.*` functions from chunk 2).
   - `project_setup.py` two-column metadata form.
   - `recent_projects.py` wrapper.
   - CSS skinning (`www/mosaic-skin.css`).
   - All Playwright e2e tests (`test_topology_e2e.py`, `test_compartments_e2e.py`, `test_comparative_e2e.py`, `test_cross_view_e2e.py`, `test_compartment_switcher_rebind.py` — the e2e flavour; the contract flavour already exists from the pre-spike).

3. **What's deferred to phase-2 explicitly:** language switcher, autosave, export, map view, flux simulation. The `t()` calls stay in place (English-only) so phase-2 can flip a switch.

4. **Forward-compat fixes from chunk-2 review baked into chunk-3 tasks:**
   - **Task 1.5 (NEW)** adds `cross_compartment_loops(..., g=None)` as an optional pre-built-graph parameter. The chunk-4 Cross-view panel will call this in a tight loop and benefit from caching `build_composite_digraph(ms)` once per session.
   - Module-level `_log = logging.getLogger("multises")` for every new module (chunk-1 idiom).

5. **What the four reactivity invariants mean for chunk-3 code:**
   - Invariant 1 (rebind triggers CLD redraw) — automatic. No code in chunk 3 enforces it; the contract test already pins it.
   - Invariant 2 (silent corruption case) — exists in upstream SESPy; chunk 3's switcher protocol must mitigate, see Task 9.
   - Invariant 3 (emit `isa_change` after rebind) — Task 9 implements this.
   - Invariant 4 (isolate-wrap the read in the backwrite listener) — Task 10 implements this.

---

## File structure overview

```
MosaicSES/
├── app.py                                NEW — top-level entry point
├── multises/                             (unchanged from chunks 1+2)
│   ├── data_structure.py                 MODIFIED — Task 2 adds replace_compartment()
│   ├── composite.py                      MODIFIED — Task 1.5 adds g= param
│   ├── curonian/
│   │   ├── __init__.py                   MODIFIED — Task 0 honours per-compartment overrides
│   │   └── curonian_loac.json            MODIFIED — Task 0 adds lagoon connections + R001
│   └── ...
├── multises_app/                         NEW — Shiny UI package
│   ├── __init__.py                       NEW — package marker
│   ├── dashboard.py                      NEW — thin wrapper over sespy.dashboard
│   ├── state.py                          NEW — Shiny-bridge reactives only (no library helpers)
│   └── modules/
│       ├── __init__.py                   NEW — package marker
│       ├── topology.py                   NEW — topology editor (UI + server, read-only v1)
│       └── compartments.py               NEW — switcher + embedded SESPy modules
├── tests/
│   ├── test_compartment_switcher_contract.py  (unchanged — shipped with spike)
│   ├── test_multises_app_imports.py      NEW — package smoke + import allow-list + library-purity guard
│   ├── test_state_bridge.py              NEW — listener wiring contract
│   ├── test_topology_module.py           NEW — UI helpers (pyvis HTML inspection)
│   └── test_compartments_module.py       NEW — picker + nested-tabs scaffolding + SESPy signature probe
└── pyproject.toml                        MODIFIED — add shiny, pyvis, networkx as runtime deps
```

**Responsibility split:**

- `multises/data_structure.py` owns the data-model mutation helpers (`add_compartment`, `add_channel`, `replace_compartment`). All are pure `MultiSES → MultiSES` and Shiny-free.
- `multises_app/state.py` owns the Shiny reactive bridge — `MultiSESState` dataclass + `create_multises_state` factory. It does NOT define library helpers; it imports them from `multises.data_structure`.
- `multises_app/modules/topology.py` knows about pyvis + the topology UI. It does NOT mutate `MultiSES` directly; mutations would go via `multises.data_structure.replace_compartment(...)` etc. when chunk-4 adds editing.
- `multises_app/modules/compartments.py` knows about embedding SESPy modules. It does NOT know about pyvis (that's topology's concern).
- `app.py` is the glue: dashboard + nav + initial `seed_curonian()`.

The `multises/` library stays Shiny-free (architectural rule #1 from design spec §2.1) — enforced by `test_multises_library_has_no_shiny_imports` in Task 12.

---

## Task 0: Curonian seed within-lagoon connections + Response element (demo-loop enabler)

**Depends on Tasks:** none (chunk-2 data + library extension).

**Files:**
- Modify: `MosaicSES/multises/curonian/curonian_loac.json`
- Modify: `MosaicSES/multises/curonian/__init__.py` (extend `seed_curonian()` to honour per-compartment overrides)
- Modify: `MosaicSES/tests/test_curonian_seed.py` (add a 5-edge balancing-loop assertion against the lagoon)

**Why this exists.** The chunk-2 Curonian seed JSON ships compartment-level metadata + 26 inter-compartment Channels, but NO intra-compartment Connections and NO Response elements. Every compartment loads with `project.isa_data.connections == []`. Result: when the chunk-3 smoke checklist asks the operator to "Click Detect on Loop Analysis with Curonian Lagoon active — cycles appear", the table is empty and the architectural-pivot test (Invariant 3 verification) passes trivially for the wrong reason (empty → empty is not a meaningful clear).

This task adds the minimum within-lagoon Connections to demonstrate a within-compartment Balancing loop in SESPy's Loop Analysis module. The loop is a 5-edge cycle, 3 negatives → Balancing (per SESPy `loop_polarity` convention: odd negatives = Balancing = negative feedback).

The cycle: `P001 (Eutrophication) → P003 (Algal blooms) → MPF003 (Bottom-water DO) → GB001 (Lagoon fishery) → R001 (National eutrophication management programme) → P001`.

**Scientific framing — this is a within-compartment SURROGATE, NOT design spec §8.4.** Design spec §8.4 Loop 1 is a CROSS-compartment loop that spans `nemunas_lower → curonian_lagoon → baltic_se → klaipeda_strait → curonian_lagoon` and closes via the existing `bs_to_ks_helcom_gov` + `ks_to_cl_msfd` governance channels. Detecting §8.4 requires the composite-graph loop detector (chunk-2's `cross_compartment_loops`), which is the chunk-4 Cross-view panel demo. The Task 0 within-lagoon surrogate exists to demonstrate the embedded SESPy Loop Analysis UI in chunk 3 without requiring composite analysis. Both loops are scientifically defensible; they answer different questions.

**Why P003 (Algal blooms), not P002 (Hypoxia), as the intermediate:** P002 "Hypoxia/anoxia" and MPF003 "Bottom-water DO" represent the same physical phenomenon (hypoxia IS low DO), so an edge `P002 → MPF003 [-]` is causally tautological. The scientifically correct mechanism (Bartoli et al. 2018; Žilius et al. 2012) is: eutrophication drives cyanobacterial bloom formation (P001 → P003 [+]) → bloom collapse depletes bottom-water DO (P003 → MPF003 [-]) → low DO compresses benthic fishery habitat (MPF003 → GB001 [+]) → fishery decline triggers governance response (GB001 → R001 [-]; weak — Baltic governance is multi-decadal) → response programmes reduce nutrient loading (R001 → P001 [-]; weak — BSAP compliance ~30%).

**Why "weak" on R001's two edges:** HELCOM BSAP compliance is approximately 30% as of 2024; Curonian/Nemunas N-loads show no clear reduction trend (Stakėnienė et al. 2023; Čerkasova et al. 2021). Confidence=2 reflects the empirical reality. The loop direction is correct (the policy target, if achieved, would reduce eutrophication); the strength of the actual effect is weak.

**Why "National eutrophication management programme (BSAP-derived)" not "BSAP nutrient-cap response":** HELCOM-BSAP is a regional intergovernmental agreement; it does not directly manage any single lagoon. The within-lagoon governance instrument is the Lithuanian MSFD/WFD-derived national programme that implements BSAP targets.

- [ ] **Step 1: Verify current state**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny python -c "from multises import seed_curonian; ms = seed_curonian(); lg = ms.compartment('curonian_lagoon'); print('Lagoon connections:', len(lg.project.isa_data.connections)); print('Lagoon Responses:', [e.id for e in lg.project.isa_data.elements if e.type == 'Responses'])"
```

Expected (before fix): `Lagoon connections: 0` / `Lagoon Responses: []`.

- [ ] **Step 2: Edit `multises/curonian/curonian_loac.json`**

Find the compartment entry for `curonian_lagoon` and replace it with a version that carries per-compartment `elements_extra` and `connections` overrides.

**Use the Edit tool with the EXACT old_string** (single line including the trailing comma): `{"id": "curonian_lagoon", "label": "Curonian Lagoon (~1584 km^2, oligohaline)", "archetype": "lagoon"},`. Do NOT use sed, regex replace, or rewrite the entire file.

Replace it with this multi-line object:

```json
    {
      "id": "curonian_lagoon",
      "label": "Curonian Lagoon (~1584 km^2, oligohaline)",
      "archetype": "lagoon",
      "elements_extra": [
        {"id": "R001", "label": "National eutrophication management programme (BSAP-derived)", "type": "Responses", "confidence": 2}
      ],
      "connections": [
        {"source": "P001", "target": "P003", "polarity": "+", "strength": "strong", "confidence": 4},
        {"source": "P003", "target": "MPF003", "polarity": "-", "strength": "strong", "confidence": 4},
        {"source": "MPF003", "target": "GB001", "polarity": "+", "strength": "medium", "confidence": 3},
        {"source": "GB001", "target": "R001", "polarity": "-", "strength": "weak", "confidence": 2},
        {"source": "R001", "target": "P001", "polarity": "-", "strength": "weak", "confidence": 2}
      ]
    },
```

(Note the trailing comma — the lagoon is one of several compartments in a JSON array, not the last one in this seed.)

Leave the other 5 compartment entries unchanged.

**Confidence rationale:** P001→P003 and P003→MPF003 at confidence 4 reference Bartoli et al. 2018 + Žilius et al. 2012 (the latter co-authored by Razinkovas-Baziukas). MPF003→GB001 at confidence 3 is the well-supported benthic-DO/fishery-habitat link. GB001→R001 and R001→P001 at confidence 2 reflect documented multi-decadal Baltic governance lag and ~30% BSAP compliance (HELCOM 2024 BSAP progress report; Stakėnienė et al. 2023; Čerkasova et al. 2021).

- [ ] **Step 3: Extend `seed_curonian()` to honour the new overrides**

In `multises/curonian/__init__.py`, in the loop that builds compartments, replace the existing compartment-building snippet:

```python
    compartments = []
    for c_raw in compartments_raw:
        cmp = seed_compartment(
            c_raw["archetype"],
            label=c_raw["label"],
            id=c_raw["id"],
        )
        compartments.append(cmp)
```

with:

```python
    # Local import — keeps these SESPy types out of multises.curonian's
    # namespace; the underscore aliases signal "internal use only".
    # DO NOT hoist this import to module level (Subagent Risk F7).
    from sespy.data_structure import Connection as _SConn, Element as _SElement

    compartments = []
    for c_raw in compartments_raw:
        cmp = seed_compartment(
            c_raw["archetype"],
            label=c_raw["label"],
            id=c_raw["id"],
        )
        # Per-compartment overrides: optional `elements_extra` appended to
        # archetype defaults, optional `connections` set on the project.
        # Both lists are SESPy-shape dicts (Element / Connection kwargs).
        # Wrap construction in MultiSESIntegrityError to match the chunk-1+2
        # loader pattern (Consistency Finding 12, second-pass review).
        try:
            for e_raw in c_raw.get("elements_extra", []):
                cmp.project.isa_data.elements.append(_SElement(**e_raw))
            for ch_raw in c_raw.get("connections", []):
                cmp.project.isa_data.connections.append(_SConn(**ch_raw))
        except TypeError as e:
            raise MultiSESIntegrityError(
                f"curonian_loac.json: per-compartment override on {c_raw.get('id')!r} "
                f"has unrecognised field(s): {e}. "
                "Supported keys: elements_extra (list of Element kwargs), "
                "connections (list of Connection kwargs)."
            ) from e
        compartments.append(cmp)
```

This keeps the per-archetype defaults as the foundation and layers in any per-compartment science on top. Other 5 compartments have no `elements_extra` or `connections` keys and are unaffected.

- [ ] **Step 4: Append acceptance tests to `tests/test_curonian_seed.py`**

```python
def test_seed_curonian_lagoon_has_response_element():
    """Task 0: the lagoon ships at least one Response element so the
    eutrophication-governance balancing loop can close."""
    ms = seed_curonian()
    lg = ms.compartment("curonian_lagoon")
    responses = [e for e in lg.project.isa_data.elements if e.type == "Responses"]
    assert len(responses) >= 1, (
        "Lagoon must have ≥ 1 Response element after Task 0; otherwise "
        "the eutrophication-governance demo loop cannot close."
    )


def test_seed_curonian_lagoon_eutrophication_governance_loop_exists():
    """Task 0: within-compartment loop detection on the lagoon must
    return ≥ 1 Balancing cycle.

    This is a WITHIN-COMPARTMENT SURROGATE balancing loop — distinct
    from §8.4 Loop 1 of the design spec, which is a CROSS-compartment
    loop that closes via `bs_to_ks_helcom_gov` + `ks_to_cl_msfd` and
    requires the composite-graph loop detector (chunk-4 demo milestone).
    The within-lagoon surrogate exists to demonstrate SESPy's compartment-
    level Loop Analysis module in chunk-3 without requiring composite
    analysis.

    The classification key is `"type"` (not `"polarity_type"`) — that's
    what sespy.network.classify_loops returns on plain dicts. CrossLoop
    dataclass uses `polarity_type`, but classify_loops uses `type`."""
    from sespy.network import feedback_loops, classify_loops
    ms = seed_curonian()
    lg = ms.compartment("curonian_lagoon")
    cycles = feedback_loops(lg.project.isa_data, max_length=6, max_loops=50)
    assert len(cycles) >= 1, (
        "Lagoon must have ≥ 1 within-compartment cycle after Task 0. "
        "If empty, check the connections list in curonian_loac.json."
    )
    classified = classify_loops(cycles, lg.project.isa_data)
    balancing = [c for c in classified if c.get("type") == "Balancing"]
    assert len(balancing) >= 1, (
        "Lagoon must have ≥ 1 BALANCING cycle (eutrophication-governance "
        "loop with odd negatives). Got types: "
        f"{[c.get('type') for c in classified]}"
    )


def test_seed_curonian_lagoon_connections_survive_save_load_roundtrip(tmp_path):
    """Task 0's intra-compartment connections must survive `persistence.save`
    + `persistence.load`. If chunk-2's `Compartment.to_dict()` silently
    drops them, the eutrophication demo loop disappears on next launch —
    silent science regression invisible to the chunk-2 round-trip test."""
    from multises import seed_curonian, persistence
    ms = seed_curonian()
    path = tmp_path / "curonian.multises.json"
    persistence.save(ms, path)
    ms2, _ = persistence.load(path)
    lg2 = ms2.compartment("curonian_lagoon")
    assert len(lg2.project.isa_data.connections) == 5, (
        f"Lagoon must have 5 within-compartment connections after "
        f"save/load round-trip, got {len(lg2.project.isa_data.connections)}. "
        "If 0, chunk-2's Compartment.to_dict() likely drops Connections — "
        "investigate before proceeding (see Task 0 Step 5 troubleshooting note)."
    )
    # The Response element (R001) must also round-trip.
    responses = [e for e in lg2.project.isa_data.elements if e.type == "Responses"]
    assert len(responses) >= 1
```

- [ ] **Step 5: Run tests**

```powershell
micromamba run -n shiny pytest tests/test_curonian_seed.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 3 new PASSED in `test_curonian_seed.py` (response-element existence + balancing-loop existence + save/load round-trip survival); full suite = 203 PASSED (200 prior + 3 new). All existing tests must continue to pass — verify chunk-2's existing Curonian tests (compartment count, archetypes, save/load round-trip, canary loops) are unaffected by the new lagoon overrides.

If `test_seed_curonian_save_load_roundtrip_clean` fails after this change: chunk-2's `Compartment.to_dict()` may not serialise the new Connections. Investigate by running `micromamba run -n shiny python -c "from multises import seed_curonian, persistence; import json; ms = seed_curonian(); print(json.dumps(ms.to_dict()['compartments'][3], indent=2)[:1500])"` to confirm the lagoon connections appear in the dict. If not, the chunk-2 `Compartment.to_dict()` needs the same `connections` round-trip path — that's a chunk-2 patch (rare), file a small follow-up if needed.

- [ ] **Step 6: Commit**

```powershell
git add multises/curonian/curonian_loac.json multises/curonian/__init__.py tests/test_curonian_seed.py
git commit -m "feat(mosaicses): Curonian Lagoon within-compartment connections + R001 Response (demo loop)"
```

---

## Task 1: Add `multises_app/` package skeleton

**Depends on Tasks:** none (chunks 1+2 only).

**Files:**
- Create: `MosaicSES/multises_app/__init__.py`
- Create: `MosaicSES/multises_app/modules/__init__.py`
- Create: `MosaicSES/tests/test_multises_app_imports.py`

- [ ] **Step 1: Write the failing import smoke test first**

Create `tests/test_multises_app_imports.py`:

```python
"""Package smoke test: multises_app imports cleanly and exposes its
public submodules. Mirrors chunk-1's test_import_allowlist.py for
multises/. The full allow-list scan extends in Task 12."""
from __future__ import annotations


def test_multises_app_package_imports():
    """The package itself must import without side effects (no Shiny
    server-startup, no I/O, no logging configuration)."""
    import multises_app  # noqa: F401
    assert multises_app.__doc__ is not None


def test_multises_app_modules_subpackage_imports():
    import multises_app.modules  # noqa: F401
```

- [ ] **Step 2: Run the test to verify it fails**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```

Expected: 2 FAIL with `ModuleNotFoundError: No module named 'multises_app'`.

- [ ] **Step 3: Create the package files**

`multises_app/__init__.py`:

```python
"""MosaicSES Shiny UI package.

Provides the thin Shiny shell around the chunk-1+2 library. Architectural
rule from design spec §2.1: this package depends on the library, never the
other way around — the library has zero Shiny imports.
"""
```

`multises_app/modules/__init__.py`:

```python
"""Shiny modules for MosaicSES — one module per nav panel.

Chunk-3 ships `topology` and `compartments`. Chunk-4 will add
`comparative`, `cross_view`, `project_setup`, `recent_projects`.
"""
```

- [ ] **Step 4: Run the test to verify it passes**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/ tests/test_multises_app_imports.py
git commit -m "feat(mosaicses): multises_app package skeleton"
```

---

## Task 1.5: composite.cross_compartment_loops accepts optional pre-built graph

**Depends on Tasks:** none (chunk-2 follow-up from final review).

**Files:**
- Modify: `MosaicSES/multises/composite.py`
- Modify: `MosaicSES/tests/test_composite.py`

The chunk-2 final review flagged: `cross_compartment_loops(ms)` rebuilds the composite digraph on every call. Chunk-4's Cross-view panel will bind a reactive to it; without caching, every UI tick rebuilds the graph. Add an optional `g: nx.DiGraph | None = None` parameter so callers can pre-build once and pass it in. Default behaviour unchanged.

- [ ] **Step 1: Append a failing test to `tests/test_composite.py`**

```python
def test_cross_compartment_loops_accepts_prebuilt_graph(empty_project):
    """Callers can pass a pre-built composite digraph to skip rebuild.
    Output must match the no-argument case exactly (same ids, same order)."""
    a = Compartment(id="A", label="A", archetype="river_lower", project=empty_project)
    b = Compartment(id="B", label="B", archetype="lagoon", project=empty_project)
    chs = [
        ch_kb.make_channel(id="ab", source="A", target="B", channel_type="nutrients"),
        ch_kb.make_channel(id="ba", source="B", target="A",
                           channel_type="governance", governance_regime="MSFD"),
    ]
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=chs)

    # Default (no g): rebuilds internally
    loops_default = composite.cross_compartment_loops(ms)

    # Pre-built: caller passes the digraph
    g = composite.build_composite_digraph(ms)
    loops_prebuilt = composite.cross_compartment_loops(ms, g=g)

    assert [l.id for l in loops_default] == [l.id for l in loops_prebuilt]
    assert [l.compartments_visited for l in loops_default] == [
        l.compartments_visited for l in loops_prebuilt
    ]
```

- [ ] **Step 2: Run to verify it fails**

```powershell
micromamba run -n shiny pytest tests/test_composite.py::test_cross_compartment_loops_accepts_prebuilt_graph -v
```

Expected: FAIL with `TypeError: cross_compartment_loops() got an unexpected keyword argument 'g'`.

- [ ] **Step 3: Modify `cross_compartment_loops` signature in `multises/composite.py`**

Find the existing `def cross_compartment_loops(...)` (around line 173) and change the signature + body:

```python
def cross_compartment_loops(
    ms: MultiSES,
    *,
    g: nx.DiGraph | None = None,
    max_length: int = 12,
    max_loops: int = 50,
) -> list[CrossLoop]:
    """Detect cycles in the composite digraph that touch ≥ 2 compartments.

    Parameters:
      g: optional pre-built composite digraph. When None (default), the
         function calls `build_composite_digraph(ms)` to build one. Callers
         that run multiple analyses on the same MultiSES can pre-build once
         and pass it here to avoid rebuild cost — chunk-4's Cross-view
         panel uses this.

    (... rest of docstring unchanged ...)
    """
    if g is None:
        g = build_composite_digraph(ms)
    if g.number_of_nodes() == 0:
        return []
    # ... rest of function body unchanged ...
```

Only the parameter list, the new `if g is None` branch, and the docstring change. Everything below `if g.number_of_nodes() == 0:` stays as-is.

- [ ] **Step 4: Run all composite tests + the full suite**

```powershell
micromamba run -n shiny pytest tests/test_composite.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: all composite tests pass (including the new one); full suite = 206 PASSED (205 prior + 1 new). The 205 prior includes 200 baseline + Task 0's 3 lagoon tests + Task 1's 2 package-import tests.

- [ ] **Step 5: Commit**

```powershell
git add multises/composite.py tests/test_composite.py
git commit -m "feat(mosaicses): cross_compartment_loops accepts optional prebuilt graph for caching"
```

---

## Task 2: `multises_app/state.py` — shared reactive state

**Depends on Tasks:** Task 1.

**Files:**
- Create: `MosaicSES/multises_app/state.py`
- Create: `MosaicSES/tests/test_state_bridge.py`

The bridge between the `MultiSES` data model and the Shiny reactive graph. Holds three reactive values plus two helper functions for mutation:

- `active_multises: reactive.Value[MultiSES]` — the source of truth.
- `active_compartment_id: reactive.Value[str | None]` — which compartment the user is currently editing.
- `active_compartment_project: reactive.Value[Project]` — the shared `Project` reactive that embedded SESPy modules bind to. Rebound by the switcher; written back by `_backwrite_to_multises`.
- `MultiSESState` — dataclass holding the three reactives + event_bus, plus `replace_compartment(...)` / `replace_metadata(...)` helpers.

This task only ships the dataclass + helper functions + module-level `create_multises_state(...)` factory. The switcher protocol and the backwrite listener live in Task 9 and Task 10 respectively — they're inside the Compartments server, not at module level, because they need access to `input` and `session`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_state_bridge.py`:

```python
"""Contract test for multises_app.state — the reactive bridge between
MultiSES (library) and Shiny (UI).

These tests verify the SHAPE of the state object and the helper-function
contracts. They do NOT exercise reactivity (the switcher protocol's
runtime behaviour is covered by Playwright in chunk 4)."""
from __future__ import annotations

import pytest
from shiny import reactive

from multises import seed_curonian
from multises_app import state as state_mod


def test_create_multises_state_returns_dataclass():
    ms = seed_curonian()
    s = state_mod.create_multises_state(ms)
    # The state object exposes the three reactive values
    assert isinstance(s.active_multises, reactive.Value)
    assert isinstance(s.active_compartment_id, reactive.Value)
    assert isinstance(s.active_compartment_project, reactive.Value)
    # And the event_bus
    assert hasattr(s, "event_bus")
    assert hasattr(s.event_bus, "emit_isa_change")


def test_create_multises_state_initial_compartment_is_first_compartment():
    """When constructed from a non-empty MultiSES, the active compartment
    defaults to the first one in `ms.compartments`."""
    ms = seed_curonian()
    s = state_mod.create_multises_state(ms)
    # We can't read reactive.Value outside a session, but we can read
    # the dataclass's stored initial values via the helper.
    assert state_mod.initial_active_compartment_id(ms) == ms.compartments[0].id


def test_create_multises_state_empty_multises_has_none_active_id():
    """When constructed from an empty MultiSES, active_compartment_id
    defaults to None (and active_compartment_project is a fresh empty Project)."""
    from multises import MultiSES
    ms = MultiSES.empty()
    assert state_mod.initial_active_compartment_id(ms) is None


def test_create_multises_state_active_project_matches_first_compartment():
    """The initial active_compartment_project must be the FIRST compartment's
    project, not _empty_project() or some other stub. Tested via the helper
    that the factory uses internally (avoids the reactive-outside-session
    constraint)."""
    ms = seed_curonian()
    initial_id = state_mod.initial_active_compartment_id(ms)
    assert initial_id is not None
    expected = ms.compartment(initial_id).project
    assert state_mod._initial_active_project(ms) is expected
```

The corresponding `replace_compartment` tests have been moved to `tests/test_data_structure.py` (chunk-1 file) because `replace_compartment` is now a pure library helper in `multises.data_structure`, not a Shiny-bridge helper. See Step 3b below.

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_state_bridge.py -v
```

Expected: 4 FAIL with `ModuleNotFoundError: No module named 'multises_app.state'`.

**Note on step ordering (Subagent Risk F16):** Steps 3a-3b technically write the `replace_compartment` library implementation before its tests in `test_data_structure.py`. This is a partial TDD relaxation specifically for chunks-1+2 library extensions, because the helper is small enough that the RED phase adds no value — the runtime tests in Step 4 cover both files. The Shiny-bridge code in Step 3c IS tested test-first (Step 1 wrote the state-bridge tests first). If you'd prefer strict TDD discipline, write the test code in 3b BEFORE the impl in 3a, then merge the Step 2 / Step 4 pytest runs.

- [ ] **Step 3a: Add `replace_compartment` to `multises/data_structure.py` (library helper, Shiny-free)**

This is a pure `MultiSES → MultiSES` transformation with no Shiny dependency. It belongs alongside the other library mutators per Reviewer 1's Issue 1.

Add as a **module-level free function** near the bottom of `multises/data_structure.py` (after the `MultiSES` class definition). It does NOT need to be a method; the call site is `compartments.py`, which can do `from multises.data_structure import replace_compartment` cleanly.

```python
def replace_compartment(
    ms: "MultiSES",
    compartment_id: str,
    new_project: "_Project",
) -> "MultiSES":
    """Return a new MultiSES with one compartment's project replaced.

    Pure function — does not mutate `ms`. The new MultiSES shares
    metadata, channels, and all other compartments with the original
    (structural sharing, no deep copy).

    Preserves ALL Compartment fields of the replaced compartment except
    `project`: `id`, `label`, `archetype`, `description`, `geometry`,
    `is_focal_tw`, and `_unknown_archetype_original`. This is the
    backwrite contract — UI editing within a compartment must NEVER
    silently drop compartment-level metadata.

    Raises:
      KeyError: if `compartment_id` is not in `ms.compartments`.
    """
    target_idx = next(
        (i for i, c in enumerate(ms.compartments) if c.id == compartment_id),
        None,
    )
    if target_idx is None:
        raise KeyError(compartment_id)

    old = ms.compartments[target_idx]
    new = Compartment(
        id=old.id,
        label=old.label,
        archetype=old.archetype,
        project=new_project,
        description=old.description,
        geometry=old.geometry,
        is_focal_tw=old.is_focal_tw,
    )
    # `_unknown_archetype_original` IS a regular dataclass field with a
    # default of None, so it would also work as a constructor kwarg. We
    # set it via `object.__setattr__` here only because passing the
    # underscore-prefixed name to `Compartment(...)` looks like reaching
    # into a private API at the call site; the explicit setattr makes
    # the forward-compat preservation intent visible.
    orig_unknown = getattr(old, "_unknown_archetype_original", None)
    if orig_unknown is not None:
        object.__setattr__(new, "_unknown_archetype_original", orig_unknown)

    new_compartments = list(ms.compartments)
    new_compartments[target_idx] = new

    return MultiSES(
        metadata=ms.metadata,
        compartments=new_compartments,
        channels=list(ms.channels),
    )
```

Also:
- Add `"replace_compartment"` to the `__all__` list at the top of `multises/data_structure.py` (alphabetical).
- Re-export from `multises/__init__.py`: add the import line `from .data_structure import (..., replace_compartment, ...)` (extending the existing import block alphabetically) AND add `"replace_compartment"` to the `__all__` list in `__init__.py` alphabetically (between `"PressureOrigin"` and `"Strength"`). This keeps `from multises import replace_compartment` working — the chunks 1+2 convention of "everything public is reachable from the top-level package" (Consistency Finding 1, second-pass review).

- [ ] **Step 3b: Append library-helper tests to `tests/test_data_structure.py`**

These cover the pure-function behaviour, including the forward-compat invariant from Reviewer 4 R3.

```python
def test_replace_compartment_returns_new_multises():
    """replace_compartment is pure — returns a new MultiSES; original unchanged."""
    from multises import seed_curonian
    from multises.data_structure import replace_compartment
    from sespy.data_structure import IsaData, Project, ProjectMetadata
    ms = seed_curonian()
    new_project = Project(
        metadata=ProjectMetadata.new("override"),
        isa_data=IsaData(elements=[], connections=[]),
    )
    target_id = ms.compartments[0].id
    ms2 = replace_compartment(ms, target_id, new_project)
    assert ms2 is not ms
    assert ms2.compartment(target_id).project is new_project
    # Other compartments are reused (structural sharing)
    for orig, new in zip(ms.compartments[1:], ms2.compartments[1:]):
        assert orig is new
    # Channels list reused
    assert ms2.channels == ms.channels


def test_replace_compartment_preserves_compartment_metadata():
    """All Compartment fields except `project` must round-trip through
    replace_compartment. Pin description, geometry, is_focal_tw, label."""
    from multises import seed_curonian
    from multises.data_structure import Compartment, replace_compartment
    from sespy.data_structure import IsaData, Project, ProjectMetadata

    # Build a compartment carrying every metadata field
    orig_proj = Project(
        metadata=ProjectMetadata.new("orig"),
        isa_data=IsaData(elements=[], connections=[]),
    )
    c = Compartment(
        id="C1",
        label="Compartment One",
        archetype="lagoon",
        project=orig_proj,
        description="Literature citation: Razinkovas-Baziukas 2023",
        geometry={"type": "Polygon", "coordinates": []},
        is_focal_tw=True,
    )
    from multises.data_structure import MultiSES, MultiSESMetadata
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[c], channels=[])

    new_proj = Project(
        metadata=ProjectMetadata.new("new"),
        isa_data=IsaData(elements=[], connections=[]),
    )
    ms2 = replace_compartment(ms, "C1", new_proj)
    out = ms2.compartment("C1")
    assert out.project is new_proj
    assert out.label == "Compartment One"
    assert out.archetype == "lagoon"
    assert out.description == "Literature citation: Razinkovas-Baziukas 2023"
    assert out.geometry == {"type": "Polygon", "coordinates": []}
    assert out.is_focal_tw is True


def test_replace_compartment_preserves_unknown_archetype_original(empty_project):
    """Forward-compat invariant: _unknown_archetype_original (set by
    persistence.load on a future-schema file) must survive a replace_-
    compartment roundtrip."""
    from multises.data_structure import (
        Compartment, MultiSES, MultiSESMetadata, replace_compartment,
    )
    from sespy.data_structure import IsaData, Project, ProjectMetadata
    c = Compartment(id="C1", label="C", archetype="lagoon", project=empty_project)
    object.__setattr__(c, "_unknown_archetype_original", "lagoon_brackish_v2")
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[c], channels=[])
    new_proj = Project(
        metadata=ProjectMetadata.new("new"),
        isa_data=IsaData(elements=[], connections=[]),
    )
    ms2 = replace_compartment(ms, "C1", new_proj)
    out = ms2.compartment("C1")
    assert getattr(out, "_unknown_archetype_original", None) == "lagoon_brackish_v2"


def test_replace_compartment_unknown_id_raises():
    from multises import seed_curonian
    from multises.data_structure import replace_compartment
    from sespy.data_structure import IsaData, Project, ProjectMetadata
    ms = seed_curonian()
    new_project = Project(
        metadata=ProjectMetadata.new("override"),
        isa_data=IsaData(elements=[], connections=[]),
    )
    with pytest.raises(KeyError, match="ghost"):
        replace_compartment(ms, "ghost", new_project)
```

- [ ] **Step 3c: Write `multises_app/state.py` (Shiny-bridge only — no library helpers)**

```python
"""Shared reactive state for the MosaicSES Shiny app.

This is the bridge between the MultiSES data model (chunks 1+2, Shiny-
free) and the Shiny reactive graph. Owns three reactive values:

- active_multises: the source of truth.
- active_compartment_id: which compartment is currently "drilled into".
- active_compartment_project: the Project that embedded SESPy modules
  share. Rebound by the Compartments-module switcher protocol; written
  back to active_multises by the backwrite listener (both implemented
  inside compartments_server, not here, because they need session).

Architectural rule: this module is allowed to import shiny.reactive,
but the chunk-1/2 library modules (multises/*) are NOT. Mutation
helpers (replace_compartment, etc.) are pure library functions in
`multises.data_structure` — this module does NOT redefine them.

See design spec §7.3 for the switcher protocol motivation, and
docs/2026-05-12-chunk3-prespike-results.md for invariants 1-4.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from shiny import reactive

from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import EventBus, create_event_bus

from multises.data_structure import MultiSES

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())


@dataclass
class MultiSESState:
    """Bundle of reactives that the Shiny app threads through its modules."""
    active_multises: reactive.Value[MultiSES]
    active_compartment_id: reactive.Value[str | None]
    active_compartment_project: reactive.Value[Project]
    event_bus: EventBus


def initial_active_compartment_id(ms: MultiSES) -> str | None:
    """Return the id of the first compartment, or None for empty MultiSES."""
    if ms.compartments:
        return ms.compartments[0].id
    return None


def _empty_project() -> Project:
    """A vanilla Project for the no-compartment edge case (so
    active_compartment_project always holds a valid Project)."""
    return Project(
        metadata=ProjectMetadata.new("(no compartment)"),
        isa_data=IsaData(elements=[], connections=[]),
    )


def _initial_active_project(ms: MultiSES) -> Project:
    """Compute the initial Project to bind to active_compartment_project.

    Extracted as a testable helper so the reactive-outside-session
    constraint doesn't prevent us from pinning the initial-value
    contract. Returns the first compartment's project, or
    `_empty_project()` for an empty MultiSES.
    """
    initial_id = initial_active_compartment_id(ms)
    if initial_id is None:
        return _empty_project()
    return ms.compartment(initial_id).project


def create_multises_state(ms: MultiSES) -> MultiSESState:
    """Build a fresh MultiSESState from a MultiSES.

    The state object's three reactive values are initialised so that:
      - active_multises holds `ms`.
      - active_compartment_id holds the first compartment's id, or None.
      - active_compartment_project holds that compartment's Project,
        or a fresh empty Project if `ms` has no compartments.
    """
    return MultiSESState(
        active_multises=reactive.value(ms),
        active_compartment_id=reactive.value(initial_active_compartment_id(ms)),
        active_compartment_project=reactive.value(_initial_active_project(ms)),
        event_bus=create_event_bus(),
    )
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_state_bridge.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 8 new PASSED total — 4 in `test_state_bridge.py` (dataclass shape + initial-id helper + empty-MultiSES + active-project-helper) AND 4 in `test_data_structure.py` (replace_compartment: returns-new + preserves-metadata + preserves-unknown-archetype + unknown-id-raises). Full suite = 214 PASSED (206 prior + 8 new).

- [ ] **Step 5: Commit**

```powershell
git add multises/data_structure.py tests/test_data_structure.py multises_app/state.py tests/test_state_bridge.py
git commit -m "feat(mosaicses): replace_compartment helper + multises_app.state reactive bridge"
```

**ALL FOUR FILES must be in the commit** — Task 2 touches `multises/data_structure.py` (Step 3a adds the helper), `tests/test_data_structure.py` (Step 3b adds 4 library tests), `multises_app/state.py` (Step 3c creates the Shiny bridge), and `tests/test_state_bridge.py` (Step 1 creates the bridge tests). Omitting any file leaves downstream tasks unable to import `replace_compartment` and causes silent test-passes-but-app-breaks failures in Task 10.

---

## Task 3: `multises_app/dashboard.py` — thin dashboard wrapper

**Depends on Tasks:** Task 1.

**Files:**
- Create: `MosaicSES/multises_app/dashboard.py`

A thin wrapper that builds the dashboard config (`NavItem`s + `StepperItem`s + nav_to_step) for the MosaicSES app. Re-uses `sespy.dashboard.dashboard_page` / `dashboard_server` directly — no UI re-implementation. The wrapper exists so `app.py` stays terse and so the nav config can be unit-tested without spinning up a session.

- [ ] **Step 1: Append failing test to `tests/test_multises_app_imports.py`**

```python
def test_dashboard_nav_items_exist():
    """The dashboard wrapper exposes a NAV constant with at least one
    NavItem for each chunk-3 panel: topology, compartments. (Chunk 4
    will extend with comparative, cross_view, recent.)"""
    from multises_app.dashboard import NAV
    ids = {item.id for item in NAV}
    assert "topology" in ids
    assert "compartments" in ids


def test_dashboard_stepper_steps_exist():
    """The stepper config has at least the chunk-3 stages."""
    from multises_app.dashboard import STEPPER
    ids = {item.id for item in STEPPER}
    # Setup → Topology → Drill-in are the v1 chunk-3 stages
    assert "setup" in ids
    assert "topology" in ids
    assert "drill" in ids
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```

Expected: 2 new FAIL with `ImportError: cannot import name 'NAV' from 'multises_app.dashboard'`.

- [ ] **Step 3: Write `multises_app/dashboard.py`**

```python
"""MosaicSES dashboard config — NavItems + StepperItems + nav_to_step map.

Thin wrapper around sespy.dashboard. The actual page builder
(`dashboard_page`) and server wiring (`dashboard_server`) are re-used
unchanged from upstream sespy.
"""
from __future__ import annotations

from sespy.dashboard import NavItem, StepperItem

# Chunk-3 ships 3 panels. Chunk-4 will append comparative + cross_view + recent.
NAV: list[NavItem] = [
    NavItem(id="project",      icon="clipboard-list",  label="Project"),
    NavItem(id="topology",     icon="diagram-project", label="Topology"),
    NavItem(id="compartments", icon="layer-group",     label="Compartments"),
]

# Workflow stepper — MosaicSES has its own stages (different from SESPy's
# create-visualize-analyze flow because the multi-compartment lens is its
# own narrative). Three stages cover chunk-3 scope; chunk-4 will add
# "comparative" and "cross-view".
STEPPER: list[StepperItem] = [
    StepperItem(id="setup",    label="Setup"),
    StepperItem(id="topology", label="Topology"),
    StepperItem(id="drill",    label="Drill into compartment"),
]

NAV_TO_STEP: dict[str, str] = {
    "project":      "setup",
    "topology":     "topology",
    "compartments": "drill",
}
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
```

Expected: all imports tests pass.

- [ ] **Step 5: Commit**

```powershell
git add multises_app/dashboard.py tests/test_multises_app_imports.py
git commit -m "feat(mosaicses): multises_app.dashboard nav + stepper config"
```

---

## Task 4: `topology.py` — UI shell (3-column layout, no canvas yet)

**Depends on Tasks:** Task 2 (state) + Task 3 (dashboard).

**Files:**
- Create: `MosaicSES/multises_app/modules/topology.py`
- Create: `MosaicSES/tests/test_topology_module.py`

The Topology module's UI is a 3-column layout per design spec §7.2:
- **Left** (~25%): compartments list with add/remove/rename + archetype dropdown + element-count badge.
- **Centre** (~55%): pyvis canvas — implemented in Task 5.
- **Right** (~20%): inspector panel — implemented in Task 6.

Task 4 ships the SHELL only — three `ui.card` placeholders with the layout. Server side: subscribe to `state.active_multises` and render a simple table of compartment ids in the left card (so the test has something to assert on). Centre + right cards stay placeholder text.

- [ ] **Step 1: Write the failing test**

Create `tests/test_topology_module.py`:

```python
"""Tests for the Topology module — UI helpers and server-side data shaping.

UI structure is tested via inspection of returned Tag objects; server
behaviour is tested via small reactive flushes around the public helpers.
Browser rendering correctness is a chunk-4 Playwright concern."""
from __future__ import annotations

import pytest

from multises_app.modules import topology


def test_topology_ui_returns_a_tag():
    """topology_ui(id) must return a Shiny Tag object (the UI fragment
    embedded in the nav panel)."""
    from htmltools import Tag, TagList
    out = topology.topology_ui("topology")
    assert isinstance(out, (Tag, TagList))


def test_topology_ui_contains_three_column_cards():
    """The UI shell must contain three named regions: compartments-list,
    pyvis-canvas (placeholder OK for Task 4), and inspector. We test by
    serialising to HTML and looking for the section ids — a coarse but
    robust contract test."""
    html = str(topology.topology_ui("topology"))
    assert "topology-compartments-list" in html
    assert "topology-canvas" in html
    assert "topology-inspector" in html


def test_compartment_summary_rows_renders_label_and_archetype():
    """The helper `_compartment_summary_rows(ms)` returns one row per
    compartment as a list of dicts. The Shiny renderer in Task 5 will
    bind to this — keeping the dict shape testable in isolation here
    avoids a Shiny-session dependency."""
    from multises import seed_curonian
    ms = seed_curonian()
    rows = topology._compartment_summary_rows(ms)
    assert len(rows) == 6
    # Every row has the columns the UI binds to
    expected_keys = {"id", "label", "archetype", "element_count",
                     "is_focal_tw"}
    for r in rows:
        assert expected_keys.issubset(r.keys())
    # Spot-check the Curonian seed has the expected archetypes
    arches = {r["archetype"] for r in rows}
    assert arches == {"river_upper", "river_lower", "delta",
                      "estuary", "lagoon", "coastal_sea"}
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v
```

Expected: 3 FAIL with `ModuleNotFoundError: No module named 'multises_app.modules.topology'`.

- [ ] **Step 3: Write `multises_app/modules/topology.py`**

```python
"""Topology editor module.

Design spec §7.2: 3-column layout — compartments list (left), pyvis
canvas (centre), inspector (right). Channel and compartment editing
both happen on this page.

This file is built up across Tasks 4-6:
  - Task 4: UI shell + left-column compartments table.
  - Task 5: pyvis canvas in centre column.
  - Task 6: inspector panel in right column.
"""
from __future__ import annotations

import logging

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from multises.data_structure import MultiSES

from ..state import MultiSESState

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())


def _compartment_summary_rows(ms: MultiSES) -> list[dict]:
    """Shape the MultiSES compartments list for the left-column table.

    Returns one dict per compartment with the columns the UI binds to:
      - id, label, archetype, element_count, is_focal_tw.

    The archetype column displays `_unknown_archetype_original` when
    present (non-destructive round-trip), falling back to the validated
    slug. Mirrors `multises.comparative.compartment_summary`'s convention.
    """
    rows: list[dict] = []
    for c in ms.compartments:
        archetype_display = c._unknown_archetype_original or c.archetype
        rows.append({
            "id": c.id,
            "label": c.label,
            "archetype": archetype_display,
            "element_count": len(c.project.isa_data.elements),
            "is_focal_tw": c.is_focal_tw,
        })
    return rows


@module.ui
def topology_ui() -> ui.Tag:
    """3-column layout shell."""
    return ui.layout_columns(
        ui.card(
            ui.card_header("Compartments"),
            ui.output_ui("compartments_list"),
            id="topology-compartments-list",
        ),
        ui.card(
            ui.card_header("Topology"),
            ui.tags.div(
                "(Topology canvas — populated in Task 5)",
                class_="placeholder",
            ),
            id="topology-canvas",
        ),
        ui.card(
            ui.card_header("Inspector"),
            ui.tags.div(
                "(Inspector — populated in Task 6)",
                class_="placeholder",
            ),
            id="topology-inspector",
        ),
        col_widths=[3, 6, 3],
    )


@module.server
def topology_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    state: MultiSESState,
) -> None:
    @output
    @render.ui
    def compartments_list() -> ui.Tag:
        ms = state.active_multises.get()
        rows = _compartment_summary_rows(ms)
        if not rows:
            return ui.tags.p("(No compartments yet.)")

        return ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Label"),
                    ui.tags.th("Archetype"),
                    ui.tags.th("Elements"),
                )
            ),
            ui.tags.tbody(
                *[
                    ui.tags.tr(
                        ui.tags.td(r["label"]),
                        ui.tags.td(r["archetype"]),
                        ui.tags.td(str(r["element_count"])),
                    )
                    for r in rows
                ]
            ),
            class_="topology-compartments-table",
        )
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 3 new PASSED (topology helpers + UI shell); full suite = 219 PASSED total (after Tasks 0, 1, 1.5, 2, 3, 4 cumulative: 200 baseline + 3 + 2 + 1 + 8 + 2 + 3 = 219).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): topology module shell (3-column layout + compartments table)"
```

---

## Task 5: `topology.py` — pyvis canvas of compartments + channels

**Depends on Tasks:** Task 4.

**Files:**
- Modify: `MosaicSES/multises_app/modules/topology.py`
- Modify: `MosaicSES/tests/test_topology_module.py`

Render the compartments as hexagonal nodes (one per compartment, coloured by archetype) and channels as typed edges (colour + style from channels.json). Use `pyvis.shiny.render_pyvis_network` exactly like SESPy's CLD module — same height (650px), same `cdn_resources="local"` setting.

Archetype-to-colour mapping comes from `multises.archetypes` JSON. For chunk-3 use a hardcoded palette (defined inline) — chunk-4 polish can move it to a CSS-driven scheme.

- [ ] **Step 1: Append failing tests to `tests/test_topology_module.py`**

```python
def test_build_topology_network_returns_pyvis_network():
    """The `_build_topology_network(ms)` helper returns a `pyvis.Network`
    instance with one node per compartment and one edge per channel.

    Counts are derived from `ms` (not hardcoded) so the test stays valid
    if the Curonian seed evolves — Determinism Finding 3."""
    from pyvis.network import Network
    from multises import seed_curonian
    ms = seed_curonian()
    net = topology._build_topology_network(ms)
    assert isinstance(net, Network)
    assert len(net.nodes) == len(ms.compartments)
    assert len(net.edges) == len(ms.channels)


def test_build_topology_network_node_ids_match_compartment_ids():
    """Compartment id is the node id — the inspector panel (Task 6)
    uses pyvis's click event to look up the compartment by id."""
    from multises import seed_curonian
    ms = seed_curonian()
    net = topology._build_topology_network(ms)
    node_ids = {n["id"] for n in net.nodes}
    assert node_ids == {c.id for c in ms.compartments}


def test_build_topology_network_archetype_colors_distinct():
    """Different archetypes produce visibly different node colours so the
    LOAC continuum is legible.

    Look up compartments by their pyvis node id, NOT by zip-with-position
    — Determinism Finding 4. The zip-with-position pattern silently
    misattributes colours if pyvis or the builder ever changes ordering."""
    from multises import seed_curonian
    ms = seed_curonian()
    net = topology._build_topology_network(ms)
    comp_by_id = {c.id: c for c in ms.compartments}
    colors_by_archetype: dict[str, str] = {}
    for n in net.nodes:
        c = comp_by_id[n["id"]]
        colors_by_archetype[c.archetype] = n.get("color", "")
    # Six distinct archetypes → six distinct colours
    assert len(set(colors_by_archetype.values())) == 6


def test_build_topology_network_empty_multises():
    from multises import MultiSES
    net = topology._build_topology_network(MultiSES.empty())
    assert len(net.nodes) == 0
    assert len(net.edges) == 0
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v -k topology_network
```

Expected: 4 FAIL with `AttributeError: module 'multises_app.modules.topology' has no attribute '_build_topology_network'`.

- [ ] **Step 3: Add imports + the `_build_topology_network` helper + wire it into the UI**

In `multises_app/modules/topology.py`:

1. Add imports at the top:

```python
from pyvis.network import Network
from pyvis.shiny import output_pyvis_network, render_pyvis_network
```

2. Add a colour palette dict at module scope (after `_log`):

```python
# Archetype colour palette — hand-picked for the LOAC continuum legibility.
# Chunk-4 polish may move these into mosaic-skin.css; for now they live here.
_ARCHETYPE_COLORS: dict[str, str] = {
    "river_upper":  "#5cb85c",   # green
    "river_lower":  "#5bc0de",   # cyan
    "delta":        "#f0ad4e",   # amber
    "lagoon":       "#5582d6",   # blue
    "estuary":      "#d9534f",   # red
    "coastal_sea":  "#292b2c",   # dark slate
}

# Channel-type styling for the topology canvas. Colours mirror SESPy's
# CLD edge palette where they overlap (governance "−" → red).
_CHANNEL_TYPE_STYLE: dict[str, dict] = {
    "water_discharge":           {"color": "#0d6efd", "dashes": False},
    "nutrients":                  {"color": "#198754", "dashes": False},
    "sediment":                   {"color": "#6c757d", "dashes": False},
    "pollutants":                 {"color": "#fd7e14", "dashes": False},
    "organisms_diadromous":       {"color": "#6610f2", "dashes": True},
    "organisms_marine_estuarine": {"color": "#0dcaf0", "dashes": True},
    "governance":                 {"color": "#dc3545", "dashes": [4, 6]},
    "economic_telecoupling":      {"color": "#ffc107", "dashes": True},
}
```

3. Add the `_build_topology_network` helper between `_compartment_summary_rows` and `topology_ui`:

```python
def _build_topology_network(ms: MultiSES) -> Network:
    """Build the pyvis Network for the topology canvas.

    Each compartment is a hexagonal node coloured by archetype. Each
    channel is a directed edge styled by channel_type. Unknown
    archetype/channel-type slugs fall back to grey + solid line so the
    forward-compat round-trip story remains visible to the user.

    Security (third-pass review Security F3): all user-supplied strings
    (`c.label`, `c.id`, `ch.id`) flow through `html.escape()` before
    being passed to pyvis. The `font={"multi": "html"}` option is
    explicitly NOT set — labels render as plain text. Combined, this
    means a colleague-supplied JSON with `"label": "<script>..."` will
    render as visible literal text in the canvas, never as executable
    HTML/JS.
    """
    import html as _html
    _log.debug(
        "topology: rebuilding canvas — %d compartments, %d channels",
        len(ms.compartments), len(ms.channels),
    )

    net = Network(
        height="650px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#2c3e50",
        cdn_resources="local",
    )
    net.set_options(
        '{"physics": {"enabled": true, "stabilization": {"iterations": 150}},'
        ' "interaction": {"hover": true, "tooltipDelay": 150}}'
    )

    for c in ms.compartments:
        archetype_display = c._unknown_archetype_original or c.archetype
        if c.archetype not in _ARCHETYPE_COLORS:
            _log.warning(
                "topology: unknown archetype %r on compartment %r — rendered "
                "grey. Add an entry to _ARCHETYPE_COLORS.",
                c.archetype, c.id,
            )
        color = _ARCHETYPE_COLORS.get(c.archetype, "#cccccc")
        net.add_node(
            c.id,  # node id is a stable slug, no HTML chars by construction
            label=_html.escape(c.label),
            title=_html.escape(
                f"{archetype_display} — "
                f"{len(c.project.isa_data.elements)} elements"
            ),
            shape="hexagon",
            color=color,
            size=40,
            # NOTE: `"multi": "html"` deliberately omitted — pyvis renders
            # labels as plain text. See docstring Security note.
            font={"size": 18},
        )

    # Hoist node_ids OUT of the channel loop (one set build, not C×N)
    # — Performance Finding 1 from the second-pass review.
    node_ids = {n["id"] for n in net.nodes}
    for ch in ms.channels:
        ch_type = ch._unknown_channel_type_original or ch.channel_type
        if ch_type not in _CHANNEL_TYPE_STYLE:
            # Maintainability Finding 2: log unknown types so a new channel
            # type silently rendered grey doesn't hide a missing style entry.
            _log.warning(
                "topology: unknown channel_type %r on channel %r — rendered "
                "grey/solid. Add an entry to _CHANNEL_TYPE_STYLE.",
                ch_type, ch.id,
            )
        style = _CHANNEL_TYPE_STYLE.get(ch_type, {"color": "#cccccc", "dashes": False})
        # Only add the edge if both endpoints exist as nodes (validate
        # already enforces this; defensive check guards against partial
        # state during chunk-4 mid-edit topology rendering).
        if ch.source in node_ids and ch.target in node_ids:
            net.add_edge(
                ch.source, ch.target,
                title=_html.escape(
                    f"{ch_type} ({ch.polarity}, {ch.strength}) — {ch.id}"
                ),
                color=style["color"],
                dashes=style.get("dashes", False),
                arrows="to",
            )
        else:
            _log.warning(
                "topology: channel %r skipped — source %r or target %r not "
                "in compartment node set.", ch.id, ch.source, ch.target,
            )

    return net
```

4. Replace the centre-column placeholder card body in `topology_ui` with `output_pyvis_network("network", height="650px")`:

```python
ui.card(
    ui.card_header("Topology"),
    output_pyvis_network("network", height="650px",
                          show_toolbar=False, show_search=False,
                          show_layout_switcher=False, show_export=True,
                          show_status=False),
    id="topology-canvas",
),
```

5. Add the renderer inside `topology_server`:

```python
    @output(id="network")
    @render_pyvis_network(height="650px", show_toolbar=False, show_search=False,
                          show_layout_switcher=False, show_export=True,
                          show_status=False)
    def _network() -> Network:
        return _build_topology_network(state.active_multises.get())
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 4 new PASSED; full suite = 223 PASSED total (219 + 4).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): topology pyvis canvas (compartments + typed channels)"
```

---

## Task 6: `topology.py` — inspector panel

**Depends on Tasks:** Task 5.

**Files:**
- Modify: `MosaicSES/multises_app/modules/topology.py`
- Modify: `MosaicSES/tests/test_topology_module.py`

When a compartment node is clicked in the pyvis canvas, the inspector panel shows:
- archetype + label + element count + connection count + is_focal_tw badge
- "Open in Compartments tab" button (chunk-3 wires this; chunk-4 polishes the navigation hand-off)

When a channel edge is clicked, the inspector shows:
- channel_type, polarity, strength, confidence, delay, governance_regime (if set), description (if set)

Channel/compartment selection: pyvis fires browser-side events, but plumbing them to Shiny reactives requires either a custom JS callback or `PyVisNetworkController`. For chunk 3, ship a **dropdown picker** in the inspector that drives a `selected_node: reactive.value(str | None)` — pure-Shiny, no JS bridge. Chunk 4 can swap in the click handler.

- [ ] **Step 1: Append failing tests**

```python
def test_inspector_node_info_for_compartment_id():
    """`_inspector_node_info(ms, compartment_id)` returns a dict of the
    fields the inspector renders. None when the id isn't a compartment."""
    from multises import seed_curonian
    ms = seed_curonian()
    info = topology._inspector_node_info(ms, "nemunas_delta")
    assert info["kind"] == "compartment"
    assert info["archetype"] == "delta"
    assert info["label"].startswith("Nemunas Delta")
    assert info["element_count"] >= 1
    assert info["is_focal_tw"] is True


def test_inspector_node_info_for_channel_id():
    """When the id matches a channel, returns its detail dict instead."""
    from multises import seed_curonian
    ms = seed_curonian()
    info = topology._inspector_node_info(ms, "bs_to_ks_helcom_gov")
    assert info["kind"] == "channel"
    assert info["channel_type"] == "governance"
    assert info["polarity"] == "-"
    assert info["governance_regime"] == "MSFD"


def test_inspector_node_info_unknown_id_returns_none():
    from multises import seed_curonian
    ms = seed_curonian()
    assert topology._inspector_node_info(ms, "ghost") is None
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v -k inspector
```

Expected: 3 FAIL with `AttributeError: ... has no attribute '_inspector_node_info'`.

- [ ] **Step 3: Implement `_inspector_node_info` + wire it through the UI**

Add the helper:

```python
def _inspector_node_info(ms: MultiSES, target_id: str | None) -> dict | None:
    """Return the inspector dict for either a compartment or a channel id.

    `kind` is "compartment" or "channel". None when `target_id` is not
    in the MultiSES (or is None).
    """
    if not target_id:
        return None

    for c in ms.compartments:
        if c.id == target_id:
            return {
                "kind":            "compartment",
                "id":              c.id,
                "label":           c.label,
                "archetype":       c._unknown_archetype_original or c.archetype,
                "element_count":   len(c.project.isa_data.elements),
                "connection_count": len(c.project.isa_data.connections),
                "is_focal_tw":     c.is_focal_tw,
            }

    for ch in ms.channels:
        if ch.id == target_id:
            return {
                "kind":              "channel",
                "id":                ch.id,
                "channel_type":      ch._unknown_channel_type_original or ch.channel_type,
                "source":            ch.source,
                "target":            ch.target,
                "polarity":          ch.polarity,
                "strength":          ch.strength,
                "confidence":        ch.confidence,
                "delay":             ch.delay,
                "governance_regime": ch.governance_regime,
                "description":       ch.description,
            }

    return None
```

Update `topology_ui` inspector card to include the picker:

```python
ui.card(
    ui.card_header("Inspector"),
    ui.input_select(
        "inspector_target",
        "Inspect:",
        choices={},  # populated reactively
    ),
    ui.output_ui("inspector_detail"),
    id="topology-inspector",
),
```

Inside `topology_server`:

```python
    @reactive.effect
    def _update_inspector_choices():
        ms = state.active_multises.get()
        choices: dict[str, str] = {"": "(none)"}
        for c in ms.compartments:
            choices[c.id] = f"[compartment] {c.label}"
        for ch in ms.channels:
            choices[ch.id] = f"[channel] {ch.id}"
        ui.update_select("inspector_target", choices=choices, session=session)

    @output
    @render.ui
    def inspector_detail() -> ui.Tag:
        target = (input.inspector_target() or None)
        info = _inspector_node_info(state.active_multises.get(), target)
        if info is None:
            return ui.tags.p("(Pick a compartment or channel from the dropdown.)",
                              class_="placeholder")
        if info["kind"] == "compartment":
            return ui.tags.div(
                ui.tags.h5(info["label"]),
                ui.tags.dl(
                    ui.tags.dt("Archetype"), ui.tags.dd(info["archetype"]),
                    ui.tags.dt("Elements"), ui.tags.dd(str(info["element_count"])),
                    ui.tags.dt("Connections"), ui.tags.dd(str(info["connection_count"])),
                    ui.tags.dt("Focal TW"), ui.tags.dd("Yes" if info["is_focal_tw"] else "No"),
                ),
            )
        # channel
        rows = [
            ("Type", info["channel_type"]),
            ("From → To", f"{info['source']} → {info['target']}"),
            ("Polarity", info["polarity"]),
            ("Strength", info["strength"]),
            ("Confidence", str(info["confidence"])),
            ("Delay", info["delay"] or "—"),
        ]
        if info["governance_regime"]:
            rows.append(("Governance regime", info["governance_regime"]))
        if info["description"]:
            rows.append(("Description", info["description"]))
        dl_children = []
        for k, v in rows:
            dl_children.extend([ui.tags.dt(k), ui.tags.dd(v)])
        return ui.tags.div(
            ui.tags.h5(info["id"]),
            ui.tags.dl(*dl_children),
        )
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_topology_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite = 226 PASSED total (223 + 3 inspector tests).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/topology.py tests/test_topology_module.py
git commit -m "feat(mosaicses): topology inspector panel (compartment + channel details)"
```

---

## Task 7: `compartments.py` — top bar + picker + state binding

**Depends on Tasks:** Task 2 (state).

**Files:**
- Create: `MosaicSES/multises_app/modules/compartments.py`
- Create: `MosaicSES/tests/test_compartments_module.py`

The Compartments module's top bar holds:
- Compartment picker (dropdown selectInput).
- Archetype label (read-only).
- Element / connection count badges.

This task ships the top bar + the server skeleton that subscribes to `state.active_multises` and `state.active_compartment_id`. No nested SESPy tabs yet — Task 8 wires the first one.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compartments_module.py`:

```python
"""Tests for the Compartments switcher module.

UI structure tested via Tag inspection. Switcher protocol's reactive
behaviour (Task 9) is covered by test_compartment_switcher_contract.py
(shipped with the spike) + by chunk-4 Playwright e2e."""
from __future__ import annotations

import pytest

from multises_app.modules import compartments


def test_compartments_ui_returns_a_tag():
    from htmltools import Tag, TagList
    out = compartments.compartments_ui("compartments")
    assert isinstance(out, (Tag, TagList))


def test_compartments_ui_contains_picker_and_top_bar():
    html = str(compartments.compartments_ui("compartments"))
    assert "compartment_picker" in html
    assert "compartments-top-bar" in html


def test_compartment_picker_choices_uses_label():
    """`_picker_choices(ms)` returns a dict {id: f"{label} ({archetype})"}
    so the dropdown's display text is informative even when ids are
    abbreviated."""
    from multises import seed_curonian
    ms = seed_curonian()
    choices = compartments._picker_choices(ms)
    assert "curonian_lagoon" in choices
    assert choices["curonian_lagoon"].startswith("Curonian Lagoon")
    assert "(lagoon)" in choices["curonian_lagoon"]
    assert len(choices) == 6


def test_compartment_picker_choices_empty():
    from multises import MultiSES
    assert compartments._picker_choices(MultiSES.empty()) == {}
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
```

Expected: 4 FAIL with `ModuleNotFoundError: No module named 'multises_app.modules.compartments'`.

- [ ] **Step 3: Write `multises_app/modules/compartments.py`**

```python
"""Compartments switcher module.

Design spec §7.3: top bar with compartment picker + nested SESPy module
tabs. The switcher protocol (rebind active_compartment_project +
emit_isa_change) is implemented in Task 9. The backwrite listener (id-
captured + reactive.isolate()-wrapped read) is implemented in Task 10.

Tasks 8 and 11 wire in the embedded SESPy modules.
"""
from __future__ import annotations

import logging

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from multises.data_structure import MultiSES

from ..state import MultiSESState

_log = logging.getLogger("multises")
_log.addHandler(logging.NullHandler())


def _picker_choices(ms: MultiSES) -> dict[str, str]:
    """Build the dropdown choices dict for the compartment picker.

    Returns {compartment_id: f"{label} ({archetype})"}. Empty dict when
    `ms` has no compartments.
    """
    out: dict[str, str] = {}
    for c in ms.compartments:
        archetype_display = c._unknown_archetype_original or c.archetype
        out[c.id] = f"{c.label} ({archetype_display})"
    return out


@module.ui
def compartments_ui() -> ui.Tag:
    """Top bar (compartment picker + counts) + placeholder for nested tabs."""
    return ui.tags.div(
        ui.tags.div(
            ui.input_select(
                "compartment_picker",
                "Compartment:",
                choices={},
                width="320px",
            ),
            ui.output_ui("top_bar_summary"),
            class_="d-flex gap-3 align-items-center",
            id="compartments-top-bar",
        ),
        ui.tags.hr(),
        # Nested SESPy module tabs land in Tasks 8 and 11.
        ui.tags.div(
            "(SESPy modules wire in at Tasks 8 and 11.)",
            class_="placeholder",
            id="compartments-nested-tabs",
        ),
    )


@module.server
def compartments_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    state: MultiSESState,
) -> None:
    @reactive.effect
    def _populate_picker():
        """Keep the picker's choice list in sync with active_multises."""
        ms = state.active_multises.get()
        choices = _picker_choices(ms)
        current = state.active_compartment_id.get()
        if current not in choices and choices:
            current = next(iter(choices))
            state.active_compartment_id.set(current)
        ui.update_select(
            "compartment_picker",
            choices=choices,
            selected=current,
            session=session,
        )

    @output
    @render.ui
    def top_bar_summary() -> ui.Tag:
        ms = state.active_multises.get()
        cid = state.active_compartment_id.get()
        if cid is None:
            return ui.tags.span("(no compartment)", class_="text-muted")
        c = ms.compartment(cid)
        archetype_display = c._unknown_archetype_original or c.archetype
        return ui.tags.span(
            ui.tags.span(archetype_display, class_="badge bg-secondary me-2"),
            ui.tags.span(
                f"{len(c.project.isa_data.elements)} elements",
                class_="me-2",
            ),
            ui.tags.span(
                f"{len(c.project.isa_data.connections)} connections",
                class_="me-2",
            ),
            ui.tags.span(
                "focal TW" if c.is_focal_tw else "",
                class_="badge bg-success" if c.is_focal_tw else "",
            ),
        )
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 4 new PASSED; full suite = 230 PASSED total (226 + 4).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): compartments module top bar + picker"
```

---

## Task 8: `compartments.py` — embed CLD module (single tab smoke test)

**Depends on Tasks:** Task 7.

**Files:**
- Modify: `MosaicSES/multises_app/modules/compartments.py`
- Modify: `MosaicSES/tests/test_compartments_module.py`

Wire one embedded SESPy module — `cld_visualization` — into the Compartments page. This is the smoke test of the embedding pattern. If this works, Task 11 can wire the remaining 8 modules in a parallel structure.

The pattern: `cld_viz_ui("compartments-cld")` mounted inside a nav panel; `cld_viz_server("compartments-cld", project_data=state.active_compartment_project, event_bus=state.event_bus)` in the server. The `project_data` parameter receives the SHARED `state.active_compartment_project` reactive — when the switcher (Task 9) reassigns it, the CLD renderer redraws (invariant 1).

- [ ] **Step 1: Append failing tests**

```python
def test_compartments_ui_contains_cld_panel():
    """After Task 8, the compartments UI must mount the CLD module."""
    html = str(compartments.compartments_ui("compartments"))
    # cld_viz_ui's pyvis output uses the id pattern "{module_id}-network"
    # We just check the nested namespace prefix exists in the rendered UI.
    assert "compartments-cld" in html or "cld-network" in html
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v -k contains_cld
```

Expected: 1 FAIL.

- [ ] **Step 3: Wire the CLD module**

In `multises_app/modules/compartments.py`:

1. Add the import at the top:

```python
from sespy.modules.cld_visualization import cld_viz_server, cld_viz_ui
```

2. Replace the placeholder nested-tabs div in `compartments_ui` with a `ui.navset_tab` (one tab for now):

```python
ui.navset_tab(
    ui.nav_panel("CLD Visualization", cld_viz_ui("cld")),
    id="compartments-nested-tabs",
),
```

3. In `compartments_server`, after `_populate_picker` and `top_bar_summary`, mount the SESPy module:

```python
    cld_viz_server(
        "cld",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
    )
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite = 231 PASSED total (230 + 1).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): compartments mounts embedded SESPy CLD module"
```

---

## Task 9: `compartments.py` — switcher protocol (rebind + emit_isa_change)

**Depends on Tasks:** Task 8.

**Files:**
- Modify: `MosaicSES/multises_app/modules/compartments.py`
- Modify: `MosaicSES/tests/test_compartments_module.py`

Implement design spec §7.3's switcher protocol. When the user changes the compartment picker:

1. **Set a `_switching` flag** so the backwrite listener (Task 10) can no-op while we're mid-switch and not mistake the switcher's own `isa_change` emit for a user edit (Reviewer 3 I-1 — double-emit race fix).
2. Rebind `state.active_compartment_project` to the new compartment's project.
3. Force-invalidate every embedded SESPy module's derived state via `state.event_bus.emit_isa_change()`.
4. Update `state.active_compartment_id`.
5. Clear `_switching`.

Per the chunk-3 pre-spike, this protocol is the FIX for the silent-corruption case (invariant 2 → invariant 3).

**On the `session.send_input_message` flush from spec §7.3 "Open issue":** Verified in this revision pass that Shiny-for-Python 1.5.1's `@reactive.event(input.compartment_picker, ignore_init=True)` does NOT auto-flush pending text inputs in nested embedded modules (Reviewer 3 C-2). Implementing the `session.send_input_message`-driven flush would require a JS bridge that fires `blur()` on focused text inputs in every nested SESPy module — out of scope for chunk 3 because the JS plumbing has no test infrastructure until chunk-4 Playwright. v1 ships without the flush; the smoke checklist (Task 13) adds an explicit "unsaved text edits" verification item, and the chunk-3 Project Setup placeholder will display a "Save edits before switching compartments" notice (Task 12 update).

- [ ] **Step 1: Append a contract test**

**IMPORTANT (Reviewer determinism #9):** `inspect.getsource(compartments.compartments_server)` returns the `@module.server` WRAPPER's source, NOT the inner function body. The pre-spike (`test_compartment_switcher_contract.py`) uses the correct pattern: `inspect.getsource(<module>)` returns the full module source, which DOES contain the inner function body. Mirror that pattern here.

```python
import inspect
from multises_app.modules import compartments as _comp_mod


def test_compartments_server_calls_emit_isa_change_after_rebind():
    """Inspect the source of `compartments.py` (the full module, not the
    @module.server-decorated wrapper which hides the body): after the
    active_compartment_project.set(...) call inside the picker-change
    effect, there MUST be a state.event_bus.emit_isa_change() call,
    AND the set must precede the emit (call-order invariant — Reviewer 4 R4).
    This is invariant 3 from the chunk-3 pre-spike — if it's missing or
    out-of-order, switching compartments silently corrupts analysis_loops's
    `detected` reactive."""
    src = inspect.getsource(_comp_mod)
    assert "active_compartment_project.set(" in src, (
        "compartments.py must call state.active_compartment_project.set(...) "
        "inside the picker-change effect."
    )
    assert "emit_isa_change()" in src, (
        "compartments.py must call state.event_bus.emit_isa_change() after "
        "the rebind — invariant 3 from the chunk-3 pre-spike."
    )
    # ORDER invariant: set() must precede emit_isa_change() in the source.
    # Use the LAST occurrence of set() and the FIRST of emit_isa_change()
    # to avoid false positives from comments/docstrings mentioning either name.
    set_idx = src.rfind("active_compartment_project.set(")
    emit_idx = src.find("emit_isa_change()")
    assert set_idx < emit_idx, (
        "active_compartment_project.set(...) must be called BEFORE "
        "emit_isa_change() in the switcher effect. Swapped order would "
        "fire isa_change against the OLD compartment's project, causing "
        "the bug invariant 3 is supposed to prevent."
    )


def test_compartments_server_uses_switching_guard_flag():
    """The switcher must set a `_switching` flag (or equivalent re-entry
    guard) so the backwrite listener can no-op while a switch is in
    progress. Without this, the switcher's own emit_isa_change() would
    trigger an unwanted backwrite (Reviewer 3 I-1, double-emit race)."""
    src = inspect.getsource(_comp_mod)
    assert "_switching" in src, (
        "compartments.py must define a `_switching` boolean reactive "
        "value to suppress backwrite during compartment switch. See "
        "Reviewer 3 I-1 in the revision log."
    )
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v -k "emit_isa_change or switching"
```

Expected: 2 FAIL.

- [ ] **Step 3: Implement the switcher effect with `_switching` guard**

Inside `compartments_server`, AFTER `_populate_picker` and the CLD mount, add:

```python
    # Re-entry guard: True while a picker-driven switch is mid-flight.
    # The backwrite listener (Task 10) reads this and skips its work,
    # avoiding the double-emit race where switcher's own emit_isa_change
    # triggers an unwanted backwrite (Reviewer 3 I-1).
    # Note: `reactive.Value[bool]` is the TYPE annotation; `reactive.value(False)`
    # (lowercase 'v') is the CONSTRUCTOR. Do NOT write `reactive.Value(False)`
    # — the capital-V class is not directly instantiable. Subagent Risk F13.
    # Must be reactive.Value, not plain bool — _backwrite_to_multises reads
    # it inside a reactive context; see Task 10. (Maintainability Finding 3.)
    _switching: reactive.Value[bool] = reactive.value(False)

    @reactive.effect
    @reactive.event(input.compartment_picker, ignore_init=True)
    def _switch_active_compartment():
        """Compartment switch protocol (design spec §7.3, pre-spike invariant 3):
          1. Raise the `_switching` re-entry guard.
          2. Rebind the shared active_compartment_project reactive.
          3. Force-invalidate every embedded SESPy module's derived state.
          4. Update active_compartment_id.
          5. Lower the re-entry guard.

        NOTE on pending text-input flush (spec §7.3 "Open issue"):
        Shiny-for-Python 1.5.1's @reactive.event does not auto-flush
        pending text inputs in nested embedded modules. Unsaved edits
        in isa_data_entry's text fields will be silently lost on
        compartment switch. v1 documents this limitation in the smoke
        checklist; the proper JS-bridge fix lands with chunk-4
        Playwright infrastructure.
        """
        # Edge-case fix (third-pass review EC4): no-op when the picker is
        # fired by the snap-back path's `active_compartment_id.set(...)` →
        # `_populate_picker` cascade. The snap-back sets `_switching=True`
        # around its reactive writes; this guard lets the switcher skip
        # the spurious re-entry instead of running a redundant rebind.
        if _switching.get():
            return

        new_id = input.compartment_picker()
        if not new_id:
            return
        _log.debug("compartments: switcher firing — new_id=%r", new_id)
        try:
            cmp = state.active_multises.get().compartment(new_id)
        except KeyError:
            _log.warning("compartments: picker fired with unknown id %r", new_id)
            return

        _switching.set(True)
        try:
            # Step 2: rebind the shared reactive.
            state.active_compartment_project.set(cmp.project)
            # Step 3: emit isa_change so analysis_loops's `detected`,
            # any cached centrality metrics, etc. are invalidated.
            state.event_bus.emit_isa_change()
            # Step 4: track the new active id.
            state.active_compartment_id.set(new_id)
        finally:
            _switching.set(False)
```

The `_switching` reactive value lives in `compartments_server`'s local scope. Task 10's backwrite listener is defined in the SAME function, so it reads `_switching` directly via closure — no module-level attribute is needed.

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite = 233 PASSED total (231 + 2 new tests: emit_isa_change-after-rebind + switching-guard).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): compartments switcher protocol — rebind + emit_isa_change"
```

---

## Task 10: `compartments.py` — backwrite listener with `reactive.isolate()`

**Depends on Tasks:** Task 9.

**Files:**
- Modify: `MosaicSES/multises_app/modules/compartments.py`
- Modify: `MosaicSES/tests/test_compartments_module.py`

When the user edits inside an embedded SESPy module (e.g. clicks "Save" in `isa_data_entry`), the SESPy module sets its `project_data` reactive (i.e. `state.active_compartment_project`) and emits `event_bus.isa_change`. The Compartments module listens for that signal and writes the edited Project back into `state.active_multises` so the canonical MultiSES is updated.

Per pre-spike invariant 4 AND Reviewer 1 Issue 3, the listener:
- **Wraps BOTH `state.active_compartment_id.get()` AND `state.active_compartment_project.get()` in `reactive.isolate()`** so the listener registers ZERO new reactive dependencies (avoids both the invariant-4 infinite loop AND the secondary `_populate_picker → active_compartment_id.set()` loop path).
- Checks the `_switching` guard from Task 9 and no-ops if the emit was triggered by the switcher itself (Reviewer 3 I-1).
- On `KeyError` from `replace_compartment` (compartment was removed between emit and listener fire), **snaps `active_compartment_project` and `active_compartment_id` back to a valid first-remaining compartment** and logs at ERROR level, instead of silently dropping the edit. Without this snap, the displayed UI shows the edit while `active_multises` has no slot for it — Reviewer 3 C-1 silent-data-loss case.

- [ ] **Step 1: Append a contract test**

```python
def test_compartments_server_backwrite_listener_uses_reactive_isolate():
    """Inspect compartments.py module source: the @reactive.event(event_-
    bus.isa_change)-decorated listener MUST wrap BOTH active_compartment_-
    id.get() AND active_compartment_project.get() in `with reactive.isolate():`
    blocks. Pre-spike invariant 4 + Reviewer 1 Issue 3."""
    src = inspect.getsource(_comp_mod)
    assert "event_bus.isa_change" in src, (
        "compartments.py must register a listener on event_bus.isa_change "
        "for the backwrite path."
    )
    assert src.count("reactive.isolate()") >= 1, (
        "The backwrite listener must wrap its reads of active_compartment_id "
        "AND active_compartment_project in `with reactive.isolate():` — both "
        "are reactive dependencies that would create infinite loops. "
        "(Both reads can share one isolate block.)"
    )
    assert "replace_compartment(" in src, (
        "The backwrite listener must call the library helper replace_compartment "
        "(from multises.data_structure, moved in Task 2) to produce the new MultiSES."
    )


def test_compartments_server_backwrite_snaps_back_on_keyerror():
    """Reviewer 3 C-1 + Edge-case EC10 fix: when replace_compartment
    raises KeyError (target compartment was removed), the listener must
    snap reactives back AND log at ERROR.

    Note: `active_compartment_id.set(` also appears in `_populate_picker`'s
    fallback branch, so a substring count of >=2 is required, AND we
    additionally check that the snap-back text appears AFTER an
    `except KeyError:` token in the source (call-site verification,
    Edge-case Finding EC10)."""
    src = inspect.getsource(_comp_mod)
    set_count = src.count("active_compartment_id.set(")
    assert set_count >= 2, (
        f"Expected ≥2 occurrences of `active_compartment_id.set(`: one in "
        f"_populate_picker's fallback branch + one in the snap-back path. "
        f"Got {set_count}. Snap-back may have been deleted."
    )
    # The snap-back set must appear AFTER an `except KeyError:` token
    # in source order — pins it to the error-recovery branch, not the
    # happy path.
    except_idx = src.find("except KeyError")
    assert except_idx >= 0, "Backwrite listener must have an `except KeyError:` block."
    # Find the first set() AFTER the except token
    set_after_except = src.find("active_compartment_id.set(", except_idx)
    assert set_after_except >= 0, (
        "On KeyError from replace_compartment, the listener must call "
        "state.active_compartment_id.set(...) INSIDE the except block to "
        "snap the active id back to a valid compartment. Silent data loss "
        "of user edits is unacceptable. See Reviewer 3 C-1 + Edge-case EC10."
    )
    assert "_log.error" in src, (
        "Snap-back must log at ERROR level (not WARNING) — the situation "
        "is structural inconsistency, not a soft warning."
    )


def test_compartments_server_backwrite_respects_switching_guard():
    """Reviewer 3 I-1 fix: when _switching is True (compartment switcher
    is mid-flight), the backwrite listener must no-op. Without this guard
    the switcher's own emit_isa_change() triggers an unwanted backwrite.

    Only `_switching.get()` is accepted — `_switching.is_set()` is NOT
    a method on Shiny's reactive.Value and would raise AttributeError
    at runtime. Pinning the correct method here."""
    src = inspect.getsource(_comp_mod)
    assert "_switching.get()" in src, (
        "The backwrite listener must read the _switching guard via "
        "`.get()` (the Shiny reactive.Value method). Reviewer 3 I-1."
    )
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v -k backwrite
```

Expected: 3 FAIL.

- [ ] **Step 3: Implement the backwrite listener**

In `multises_app/modules/compartments.py`:

1. **Add a NEW import line BELOW the existing `from ..state import MultiSESState`** (which was added in Task 7). These are two SEPARATE imports from two DIFFERENT modules — DO NOT combine them into `from ..state import MultiSESState, replace_compartment` (that would fail at import time because `replace_compartment` is in `multises.data_structure`, not `multises_app.state`).

The relevant imports section becomes:

```python
from ..state import MultiSESState
from multises.data_structure import replace_compartment
```

(`replace_compartment` lives in the library — moved there in Task 2 per Reviewer 1 Issue 1.)

**DO NOT redeclare `_switching` at module scope.** `_switching` is already declared as `reactive.value(False)` inside `compartments_server`'s local scope by Task 9. The backwrite listener you're adding is in the SAME function body, so it captures `_switching` from the enclosing scope via Python closure — leave the declaration alone, just read it via `_switching.get()`.

2. After `_switch_active_compartment` in `compartments_server`, add:

```python
    @reactive.effect
    @reactive.event(state.event_bus.isa_change)
    def _backwrite_to_multises():
        """When isa_change fires, persist the edited Project back into
        active_multises.

        Pre-spike invariant 4 + Reviewer 1 Issue 3: BOTH reactive reads
        (active_compartment_id and active_compartment_project) are wrapped
        in `reactive.isolate()` so the listener registers ZERO new reactive
        dependencies. Without isolating active_compartment_id, _populate_-
        picker's `state.active_compartment_id.set(...)` fallback creates a
        secondary infinite loop path.

        Reviewer 3 I-1: the `_switching` guard from the switcher effect
        (Task 9) lets us distinguish a switcher-originated emit_isa_change
        (which we must NOT backwrite from) from a user-edit-originated one.

        Reviewer 3 C-1: on KeyError (compartment removed between emit and
        listener fire), snap active_compartment_id + active_compartment_-
        project back to a valid first-remaining compartment and log at
        ERROR level. Silent data loss is unacceptable.
        """
        # No-op if the switcher fired this isa_change itself.
        if _switching.get():
            return

        # Isolate ALL reactive reads so the listener depends on NOTHING.
        with reactive.isolate():
            target_id = state.active_compartment_id.get()
            edited_project = state.active_compartment_project.get()
            current_ms = state.active_multises.get()

        if target_id is None:
            return

        try:
            new_ms = replace_compartment(current_ms, target_id, edited_project)
        except KeyError:
            # Compute fallback BEFORE logging so the log line names the
            # actual fallback target (Observability F2).
            if current_ms.compartments:
                fallback_id: str | None = current_ms.compartments[0].id
                fallback_project = current_ms.compartments[0].project
            else:
                fallback_id = None
                from ..state import _empty_project
                fallback_project = _empty_project()
            _log.error(
                "compartments: backwrite failed — compartment %r was removed "
                "before save. Snapped back to %r (first remaining); in-flight "
                "edit discarded.",
                target_id, fallback_id,
            )
            # User-facing notification (Observability F9): without this, the
            # user sees a compartment switch with no explanation and assumes
            # they did something wrong. Toast lasts 8s.
            try:
                ui.notification_show(
                    f"Your edit was discarded — compartment {target_id!r} was "
                    f"removed before the save could complete. Switched to "
                    f"{fallback_id!r}.",
                    type="error",
                    duration=8,
                    session=session,
                )
            except Exception:
                # ui.notification_show requires an active session context;
                # if called from a non-session context (e.g. unit tests),
                # silently skip rather than masking the underlying error.
                pass
            # Snap reactives back to a valid state. Wrap in `_switching`
            # guard so the cascade through _populate_picker doesn't trigger
            # a spurious _switch_active_compartment re-fire (Edge case EC4).
            _switching.set(True)
            try:
                state.active_compartment_id.set(fallback_id)
                state.active_compartment_project.set(fallback_project)
            finally:
                _switching.set(False)
            return

        _log.debug(
            "compartments: backwriting project for compartment %r", target_id,
        )
        state.active_multises.set(new_ms)
```

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite = 236 PASSED total (233 + 3 new tests: reactive.isolate + snap-back-on-KeyError + switching-guard-check).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): compartments backwrite listener with reactive.isolate()"
```

---

## Task 11: `compartments.py` — wire the remaining 8 SESPy modules

**Depends on Tasks:** Task 10.

**Files:**
- Modify: `MosaicSES/multises_app/modules/compartments.py`
- Modify: `MosaicSES/tests/test_compartments_module.py`

Mount the remaining 8 SESPy compartment-level modules as nested tabs alongside the CLD tab from Task 8. Per design spec §7.3:

| Module | Tab label | sespy import path |
|---|---|---|
| isa_data_entry | "Edit Data" | `sespy.modules.isa_data_entry` |
| (cld_visualization) | "CLD Visualization" | already mounted (Task 8) |
| analysis_loops | "Loop Analysis" | `sespy.modules.analysis_loops` |
| analysis_metrics | "Network Metrics" | `sespy.modules.analysis_metrics` |
| analysis_leverage | "Leverage Points" | `sespy.modules.analysis_leverage` |
| analysis_boolean | "Boolean & Laplacian" | `sespy.modules.analysis_boolean` |
| analysis_simulation | "Dynamic Simulation" | `sespy.modules.analysis_simulation` |
| analysis_bot | "Behaviour Over Time" | `sespy.modules.analysis_bot` |
| analysis_intervention | "Intervention" | `sespy.modules.analysis_intervention` |
| analysis_simplify | "Simplify Network" | `sespy.modules.analysis_simplify` |

All take the same kwargs as `cld_viz_server`: `project_data=state.active_compartment_project, event_bus=state.event_bus`. Some additionally need a `translator=T` — for chunk 3, pass a stub English-only translator (see Task 12 for the app-level translator).

- [ ] **Step 0 (Pre-flight): confirm each SESPy module's server signature**

The plan needs to know which servers accept `translator=` and which don't. Run this signature probe ONCE before starting Step 3 — it generates the authoritative kwarg table. **Subagent Risk F4: the result MUST be captured in the commit message (Step 5) AND used to update the `expectations` table in the test code (Step 1).**

**PowerShell-safe (Cross-platform F9):** multi-line `python -c "..."` fails in PowerShell because double-quoted strings don't accept embedded newlines. Write the probe to a temp file and execute it instead.

Step 0a — write a temporary probe script:

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
@'
import ast, inspect
from sespy.modules.cld_visualization import cld_viz_server
from sespy.modules.isa_data_entry import isa_data_entry_server
from sespy.modules.analysis_loops import analysis_loops_server
from sespy.modules.analysis_metrics import analysis_metrics_server
from sespy.modules.analysis_leverage import analysis_leverage_server
from sespy.modules.analysis_boolean import analysis_boolean_server
from sespy.modules.analysis_simulation import analysis_simulation_server
from sespy.modules.analysis_bot import analysis_bot_server
from sespy.modules.analysis_intervention import analysis_intervention_server
from sespy.modules.analysis_simplify import analysis_simplify_server

for fn in [cld_viz_server, isa_data_entry_server, analysis_loops_server,
           analysis_metrics_server, analysis_leverage_server, analysis_boolean_server,
           analysis_simulation_server, analysis_bot_server,
           analysis_intervention_server, analysis_simplify_server]:
    # @module.server hides the original signature; AST-walk to recover it.
    src = inspect.getsource(fn)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn.__name__:
            kws = [a.arg for a in node.args.kwonlyargs]
            print(f"{fn.__name__}: {kws}")
            break
'@ | Out-File -FilePath .tmp_signature_probe.py -Encoding utf8
```

Step 0b — execute it:

```powershell
micromamba run -n shiny python .tmp_signature_probe.py
```

Step 0c — clean up:

```powershell
Remove-Item .tmp_signature_probe.py
```

Record the kwarg list per module in the commit message. The signature-probe test below pins the result so future SESPy drift is caught.

- [ ] **Step 1: Append a tab-count test AND a signature-probe test**

```python
def test_compartments_ui_has_all_sespy_module_tabs():
    """After Task 11, the nested tabs include all 10 compartment-level
    SESPy modules: Edit Data, CLD, Loops, Metrics, Leverage, Boolean,
    Simulation, BoT, Intervention, Simplify."""
    html = str(compartments.compartments_ui("compartments"))
    expected_labels = [
        "Edit Data",
        "CLD Visualization",
        "Loop Analysis",
        "Network Metrics",
        "Leverage Points",
        "Boolean",  # "Boolean & Laplacian" — match prefix to dodge entity quirks
        "Dynamic Simulation",
        "Behaviour Over Time",
        "Intervention",
        "Simplify Network",
    ]
    for lbl in expected_labels:
        assert lbl in html, f"Compartments nested tabs missing label: {lbl!r}"


def test_sespy_module_server_signatures_accept_expected_kwargs():
    """Reviewer 3 I-4 / Reviewer 1 Issue 6 fix: catch SESPy signature
    drift before it causes silent TypeError at runtime. Each module's
    server function MUST accept the kwargs that compartments.py passes
    when mounting it. If a future SESPy version adds/removes a kwarg,
    this test fails at PR time instead of at app launch."""
    import ast
    import inspect
    from sespy.modules.cld_visualization import cld_viz_server
    from sespy.modules.isa_data_entry import isa_data_entry_server
    from sespy.modules.analysis_loops import analysis_loops_server
    from sespy.modules.analysis_metrics import analysis_metrics_server
    from sespy.modules.analysis_leverage import analysis_leverage_server
    from sespy.modules.analysis_boolean import analysis_boolean_server
    from sespy.modules.analysis_simulation import analysis_simulation_server
    from sespy.modules.analysis_bot import analysis_bot_server
    from sespy.modules.analysis_intervention import analysis_intervention_server
    from sespy.modules.analysis_simplify import analysis_simplify_server

    # (fn, set_of_required_kwargs_we_pass) — UPDATE THIS TABLE FROM THE
    # STEP 0 PRE-FLIGHT PROBE OUTPUT. The defaults below show the minimum
    # universally-required kwargs. Per Subagent Risk F5: after running
    # the probe, add `"translator"` to the set for every server that accepts
    # it. Live SESPy state at plan-write time:
    #   - cld_viz_server, analysis_loops_server: do NOT take translator
    #   - all other 8: DO take translator (verified via inspect.signature)
    # Re-verify with the pre-flight probe before relying on this comment.
    expectations = [
        (cld_viz_server,             {"project_data", "event_bus"}),
        (analysis_loops_server,      {"project_data", "event_bus"}),
        (isa_data_entry_server,      {"project_data", "event_bus", "translator"}),
        (analysis_metrics_server,    {"project_data", "event_bus", "translator"}),
        (analysis_leverage_server,   {"project_data", "event_bus", "translator"}),
        (analysis_boolean_server,    {"project_data", "event_bus", "translator"}),
        (analysis_simulation_server, {"project_data", "event_bus", "translator"}),
        (analysis_bot_server,        {"project_data", "event_bus", "translator"}),
        (analysis_intervention_server, {"project_data", "event_bus", "translator"}),
        (analysis_simplify_server,   {"project_data", "event_bus", "translator"}),
    ]
    for fn, must_accept in expectations:
        src = inspect.getsource(fn)
        tree = ast.parse(src)
        kws: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == fn.__name__:
                kws.update(a.arg for a in node.args.kwonlyargs)
                break
        missing = must_accept - kws
        assert not missing, (
            f"{fn.__name__} server signature is missing kwargs {missing}. "
            "MosaicSES compartments_server passes these — either update the "
            "SESPy module or update the expectations table in this test."
        )
```

- [ ] **Step 2: Run to verify failure**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v -k all_sespy_module_tabs
```

Expected: 1 FAIL.

- [ ] **Step 3: Wire the remaining modules**

In `multises_app/modules/compartments.py`:

1. Add all 9 missing imports (keep alphabetical):

```python
from sespy.i18n import Translator
from sespy.modules.analysis_bot import analysis_bot_server, analysis_bot_ui
from sespy.modules.analysis_boolean import analysis_boolean_server, analysis_boolean_ui
from sespy.modules.analysis_intervention import (
    analysis_intervention_server, analysis_intervention_ui,
)
from sespy.modules.analysis_leverage import (
    analysis_leverage_server, analysis_leverage_ui,
)
from sespy.modules.analysis_loops import analysis_loops_server, analysis_loops_ui
from sespy.modules.analysis_metrics import (
    analysis_metrics_server, analysis_metrics_ui,
)
from sespy.modules.analysis_simplify import (
    analysis_simplify_server, analysis_simplify_ui,
)
from sespy.modules.analysis_simulation import (
    analysis_simulation_server, analysis_simulation_ui,
)
from sespy.modules.isa_data_entry import isa_data_entry_server, isa_data_entry_ui
```

2. Update the signature of `compartments_server` to accept an optional `translator`:

```python
@module.server
def compartments_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    state: MultiSESState,
    translator: Translator | None = None,
) -> None:
```

3. Replace the navset_tab body in `compartments_ui` with all 10 nav panels:

```python
ui.navset_tab(
    ui.nav_panel("Edit Data",            isa_data_entry_ui("entry")),
    ui.nav_panel("CLD Visualization",    cld_viz_ui("cld")),
    ui.nav_panel("Loop Analysis",        analysis_loops_ui("loops")),
    ui.nav_panel("Network Metrics",      analysis_metrics_ui("metrics")),
    ui.nav_panel("Leverage Points",      analysis_leverage_ui("leverage")),
    ui.nav_panel("Boolean & Laplacian",  analysis_boolean_ui("boolean")),
    ui.nav_panel("Dynamic Simulation",   analysis_simulation_ui("simulation")),
    ui.nav_panel("Behaviour Over Time",  analysis_bot_ui("bot")),
    ui.nav_panel("Intervention",         analysis_intervention_ui("intervention")),
    ui.nav_panel("Simplify Network",     analysis_simplify_ui("simplify")),
    id="compartments-nested-tabs",
),
```

4. After the existing `cld_viz_server(...)` call in `compartments_server`, mount the 9 remaining:

```python
    isa_data_entry_server(
        "entry",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_loops_server(
        "loops",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
    )
    analysis_metrics_server(
        "metrics",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_leverage_server(
        "leverage",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_boolean_server(
        "boolean",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_simulation_server(
        "simulation",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_bot_server(
        "bot",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_intervention_server(
        "intervention",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
    analysis_simplify_server(
        "simplify",
        project_data=state.active_compartment_project,
        event_bus=state.event_bus,
        translator=translator,
    )
```

**Note:** the analysis modules' exact server signatures may vary (some take `translator`, some don't). If a server call raises `TypeError: unexpected keyword 'translator'`, inspect that module's signature (`inspect.signature(module.server_fn)`) and remove the offending kwarg. Track any such adjustments in the commit message.

- [ ] **Step 4: Run to verify passing**

```powershell
micromamba run -n shiny pytest tests/test_compartments_module.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: full suite = 238 PASSED total (236 + 2: 1 tab-count test + 1 signature-probe test from Task 11).

- [ ] **Step 5: Commit**

```powershell
git add multises_app/modules/compartments.py tests/test_compartments_module.py
git commit -m "feat(mosaicses): compartments mounts all 10 nested SESPy module tabs"
```

---

## Task 12: `app.py` — top-level entry point

**Depends on Tasks:** Tasks 4-11 (topology + compartments fully wired).

**Files:**
- Create: `MosaicSES/app.py`
- Modify: `MosaicSES/pyproject.toml` (add `shiny`, `pyvis` runtime deps)
- Modify: `MosaicSES/tests/test_multises_app_imports.py` (allow-list extension)

The app launches `multises_app/dashboard.py`'s NAV + STEPPER config, mounts a placeholder Project Setup tab plus the two real tabs (`topology`, `compartments`), and seeds with `seed_curonian()`.

- [ ] **Step 1: Update `pyproject.toml` runtime dependencies**

Edit `MosaicSES/pyproject.toml`. Find the existing `dependencies` block and replace it with:

```toml
dependencies = [
    "sespy",  # editable install from ../SESPy — see install note below
    "pandas>=2.1",
    "networkx>=3.2",
    "shiny>=1.5",
    "pyvis>=0.3",
    # Future chunks add: matplotlib, openpyxl
]
```

**SESPy install note.** SESPy is not on PyPI. The bare `"sespy"` entry assumes the user has already done `pip install -e ../SESPy` (or `micromamba run -n shiny pip install -e ../SESPy`) once into the `shiny` env. The design spec §9.2 prescribed a `sespy @ file:///${PROJECT_ROOT}/../SESPy` form, but `${PROJECT_ROOT}` is NOT a pip/setuptools substitution variable — that form fails on `pip install`. Until SESPy is published, the bare `"sespy"` + manual `-e` install is the working pattern (consistent with the chunks 1+2 `pyproject.toml` which already shipped this way). `networkx>=3.2` is a direct dep (not just transitive via sespy) — required by `multises.composite`.

Verify the deps install in the `shiny` env:

```powershell
micromamba run -n shiny python -c "import shiny, pyvis, networkx, pandas; print('shiny:', shiny.__version__, 'pyvis:', pyvis.__version__, 'networkx:', networkx.__version__, 'pandas:', pandas.__version__)"
```

- [ ] **Step 2: Extend the import allow-list test + add architectural-rule tests**

In `tests/test_multises_app_imports.py`, append:

```python
import ast
from pathlib import Path


_ALLOWED_SESPY_IMPORTS = {
    # design spec §9.3 — re-stated here to detect regressions at PR time
    "sespy",  # for `from sespy import i18n` style imports (none currently, but allow)
    "sespy.data_structure",
    "sespy.constants",
    "sespy.network",
    "sespy.utils",
    "sespy.regional_seas",
    "sespy.event_bus",
    "sespy.dashboard",
    "sespy.i18n",
    "sespy.modules",  # for `from sespy.modules import xxx` (bare-module form)
    "sespy.modules.cld_visualization",
    "sespy.modules.analysis_loops",
    "sespy.modules.analysis_metrics",
    "sespy.modules.analysis_leverage",
    "sespy.modules.analysis_boolean",
    "sespy.modules.analysis_simulation",
    "sespy.modules.analysis_bot",
    "sespy.modules.analysis_intervention",
    "sespy.modules.analysis_simplify",
    "sespy.modules.isa_data_entry",
}


def _scan_sespy_imports_in_dir(pkg_dir: Path) -> set[str]:
    """Return every `from sespy.xxx import ...` module path under pkg_dir."""
    used: set[str] = set()
    for py_file in pkg_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        used |= _scan_sespy_imports_in_file(py_file)
    return used


def _scan_sespy_imports_in_file(py_file: Path) -> set[str]:
    used: set[str] = set()
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "sespy" or node.module.startswith("sespy."):
                used.add(node.module)
        elif isinstance(node, ast.Import):
            # Handle `import sespy.X` form
            for alias in node.names:
                if alias.name == "sespy" or alias.name.startswith("sespy."):
                    used.add(alias.name)
    return used


def test_multises_and_app_only_import_from_allowed_sespy_modules():
    """Architectural rule (design spec §9.3): MosaicSES only depends on
    the public SESPy surface. Regression detection if someone reaches
    into sespy._private or imports a module not on the allow-list.

    Covers multises/, multises_app/, AND the top-level app.py
    (Reviewer 4 R5 — app.py was previously not scanned)."""
    repo = Path(__file__).parent.parent  # MosaicSES/
    used = _scan_sespy_imports_in_dir(repo / "multises")
    used |= _scan_sespy_imports_in_dir(repo / "multises_app")
    app_py = repo / "app.py"
    if app_py.exists():
        used |= _scan_sespy_imports_in_file(app_py)
    illegal = used - _ALLOWED_SESPY_IMPORTS
    assert not illegal, (
        f"Illegal SESPy imports detected: {sorted(illegal)}. "
        "Add to the allow-list in design spec §9.3 (and this test) if "
        "the new dependency is justified."
    )


def test_multises_library_has_no_shiny_imports():
    """Reviewer 4 R1: architectural rule §2.1 says the library has zero
    Shiny imports. Enforced here via AST scan, not human grep. If a future
    PR adds `from shiny import reactive` to any file under multises/, this
    test fails immediately."""
    repo = Path(__file__).parent.parent  # MosaicSES/
    lib_dir = repo / "multises"
    offenders: list[tuple[str, str]] = []
    for py_file in lib_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "shiny" or node.module.startswith("shiny."):
                    offenders.append((str(py_file.relative_to(repo)), node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "shiny" or alias.name.startswith("shiny."):
                        offenders.append((str(py_file.relative_to(repo)), alias.name))
    assert not offenders, (
        f"multises/ must remain Shiny-free (design spec §2.1). "
        f"Offending imports: {offenders}. Move Shiny-dependent code to multises_app/."
    )


def test_app_module_loads():
    """Reviewer 4 R2: app.py is the top-level entry point and is not
    imported by any other test. A typo in `from multises import seed_curonian`
    or a `seed_curonian()` call that raises at module-load time would
    silently escape CI. This smoke test catches that class of regression.

    Determinism Finding 7: `app.py`'s module-level `set_default(T)` mutates
    the SESPy global translator. Save and restore around the test so other
    tests that depend on `t()` are not contaminated."""
    import importlib.util
    from sespy import i18n as _sespy_i18n
    repo = Path(__file__).parent.parent
    app_py = repo / "app.py"
    assert app_py.exists(), "app.py must exist at the repo root."

    # Save current default translator (may be None if no test set it).
    _prior_default = getattr(_sespy_i18n, "_default", None)
    try:
        spec = importlib.util.spec_from_file_location("app", app_py)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # raises on any import or load-time error
        assert hasattr(mod, "app"), "app.py must define a top-level `app` object."
    finally:
        # Restore prior default so subsequent tests see the untouched translator.
        # If sespy.i18n exposes a set_default API, prefer it; otherwise reset
        # the module-private attribute directly (best-effort).
        if hasattr(_sespy_i18n, "set_default") and _prior_default is not None:
            _sespy_i18n.set_default(_prior_default)
        elif hasattr(_sespy_i18n, "_default"):
            _sespy_i18n._default = _prior_default
```

- [ ] **Step 3: Create `MosaicSES/app.py`**

```python
"""Top-level MosaicSES app entry point.

Launch:
  micromamba run -n shiny shiny run --launch-browser app.py

The Curonian seed loads as the default project. Three nav panels in
chunk-3: Project (read-only metadata), Topology, Compartments. Chunk 4
will add Comparative, Cross-view, Recent Projects + full Project Setup
form with save/load buttons.
"""
from __future__ import annotations

import logging
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, ui

from sespy.dashboard import dashboard_page, dashboard_server
from sespy.i18n import Translator, set_default

from multises import seed_curonian


# Logging configuration (third-pass review Observability F1):
# Every chunk-1/2/3 module declares `_log = logging.getLogger("multises")`
# with a NullHandler. Without basicConfig here, ALL warnings/errors from
# the library and the Shiny shell are invisible. With basicConfig, the
# operator sees a meaningful trail in the terminal where they launched
# `shiny run app.py`. Set to WARNING by default so the console stays
# clean during normal use; export LOGLEVEL=DEBUG before launch to see
# the full reactive-trace stream.
import os
_loglevel = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=_loglevel, format="%(levelname)s %(name)s: %(message)s")

from multises_app.dashboard import NAV, NAV_TO_STEP, STEPPER
from multises_app.modules.compartments import (
    compartments_server, compartments_ui,
)
from multises_app.modules.topology import topology_server, topology_ui
from multises_app.state import create_multises_state


ROOT = Path(__file__).parent
WWW = ROOT / "www"  # created in chunk 4 for skin assets

# Translator stub — chunk 3 ships English-only. SESPy's `t()` returns the
# key as-is when not found in any loaded dict (verified Shiny-for-Python
# 1.5.1 behaviour). The empty dict is safe but will display dotted keys
# for any SESPy module label that's translation-only. Chunk 4 wires a
# real translations/core.json with English fallbacks for the SESPy
# module labels actually mounted.
T = Translator(translations={"en": {}})
set_default(T)


# Pre-build a "Project" placeholder that shows the loaded MultiSES
# metadata read-only. This is the chunk-3 substitute for the chunk-4
# Project Setup form. Built lazily via a reactive output so a future
# `state.active_multises.set(...)` (e.g. chunk-4 file-load) refreshes it.
_PROJECT_PLACEHOLDER = ui.tags.div(
    ui.tags.h4("Project (read-only in this release)"),
    ui.output_ui("project_metadata_card"),
    ui.tags.p(
        "Editing of compartment metadata is in chunk 4. "
        "IMPORTANT: unsaved text edits inside the Compartments → Edit Data tab "
        "are lost when switching compartments — save your edits before switching.",
        class_="text-muted small mt-3",
    ),
    class_="placeholder",
)

PANELS = (
    ui.nav_panel("Project",      _PROJECT_PLACEHOLDER,           value="project"),
    ui.nav_panel("Topology",     topology_ui("topology"),         value="topology"),
    ui.nav_panel("Compartments", compartments_ui("compartments"), value="compartments"),
)


_app_ui_inner = dashboard_page(
    *PANELS,
    nav_items=NAV,
    initial="topology",
    title="MosaicSES",
    brand_title="MosaicSES",
)

# A11y baseline (third-pass review):
# - WCAG SC 3.1.1 (Level A): set lang="en" on the <html> element so screen
#   readers select the correct pronunciation dictionary. Shiny's
#   dashboard_page doesn't expose a lang= kwarg portably across versions,
#   so set it via a one-line JS in head_content (runs once on page load).
# - WCAG SC 2.4.6: a visually-hidden <h1> gives screen-reader users a
#   page-level heading without affecting the sighted layout. Bootstrap's
#   `visually-hidden` class is part of bslib's bundled stylesheet.
app_ui = ui.TagList(
    ui.head_content(
        ui.tags.script("document.documentElement.lang = 'en';"),
    ),
    ui.tags.h1(
        "MosaicSES — Spatially connected SES dashboard",
        class_="visually-hidden",
    ),
    _app_ui_inner,
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    from shiny import reactive, render
    # Seed with the Curonian Lagoon dataset as the default project.
    state = create_multises_state(seed_curonian())

    dashboard_server(
        input, output, session,
        nav_items=NAV,
        initial="topology",
        stepper_steps=STEPPER,
        nav_to_step=NAV_TO_STEP,
        translator=T,
    )

    @output
    @render.ui
    def project_metadata_card() -> ui.Tag:
        """Render the loaded MultiSES metadata as a small dl card."""
        ms = state.active_multises.get()
        meta = ms.metadata
        rows = [
            ("Name",          getattr(meta, "name", "")),
            ("DA site",       getattr(meta, "da_site", "")),
            ("River basin",   getattr(meta, "river_basin", "")),
            ("Regional sea",  getattr(meta, "regional_sea", "")),
            ("Focal issue",   getattr(meta, "focal_issue", "")),
            ("Compartments",  str(len(ms.compartments))),
            ("Channels",      str(len(ms.channels))),
        ]
        return ui.tags.dl(
            *[child for k, v in rows for child in (ui.tags.dt(k), ui.tags.dd(str(v) or "—"))],
            class_="row",
        )

    topology_server("topology", state=state)
    compartments_server("compartments", state=state, translator=T)


app = App(app_ui, server)
```

- [ ] **Step 4: Run the import allow-list test + full suite**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pytest tests/test_multises_app_imports.py -v
micromamba run -n shiny pytest tests/ -q
```

Expected: 3 new PASSED in `test_multises_app_imports.py` (allow-list scan + no-shiny-in-library + app-module-loads). Full suite = 241 PASSED total (238 + 3).

NOTE: the `test_app_module_loads` smoke test imports `app.py` which executes its module-level code — this includes `T = Translator(translations={"en": {}})` and `set_default(T)`. Both must succeed at module load without side effects. If `app.py` ever adds module-level I/O (e.g., a file read), the smoke test would either need a fixture or `app.py` would need to defer the I/O into `server()`.

- [ ] **Step 5: Smoke-test the app launches**

**SKIP_IF_AUTOMATED_SUBAGENT.** `shiny run app.py` is a blocking interactive process that an automated subagent cannot Ctrl+C. If you are an automated subagent executing this plan, run the subagent-safe verification instead:

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny python -c "import app; print('app.app type:', type(app.app).__name__); print('PANELS count:', len(app.PANELS))"
```

Expected output: `app.app type: App` and `PANELS count: 3`. This verifies `app.py` imports cleanly, all module-level code (Translator, set_default, seed_curonian, NavItem etc.) executes, and the `app` Shiny App object is constructed. Combined with `test_app_module_loads` already in the test suite, this is sufficient automated coverage for chunk 3.

**For human operators only:** if you want to interactively verify the UI, run:
```powershell
micromamba run -n shiny shiny run app.py
```
Server prints `INFO:     Uvicorn running on http://127.0.0.1:8000`. Visit that URL in a browser. Verify the page loads with the three nav items in the sidebar and Topology panel shows the Curonian compartments table + pyvis canvas. Press Ctrl+C to stop. The smoke checklist in Task 13 covers the manual verification thoroughly.

If the import smoke test raises a server-side error, capture the traceback and fix in the next iteration. Common likely causes: kwarg mismatch on a SESPy module signature (Task 11 note); CSS asset 404 (harmless for chunk 3, ignore).

- [ ] **Step 6: Commit**

- [ ] **Step 5.5: Update README with "Run the app" section (Docs F1+F8)**

The chunk-3 third-pass review flagged that `README.md` doesn't mention the app. New developers reading the README after chunk 3 ships will see install + test commands but no path to running the UI. Add this section to `README.md` after the existing `## Test` section:

```markdown
## Run the app

```powershell
micromamba run -n shiny shiny run --launch-browser app.py
```

The app boots with the Curonian Lagoon seed loaded as the default project.
Three nav panels: **Project** (read-only metadata), **Topology** (pyvis
canvas + compartments list + inspector), **Compartments** (compartment
picker + embedded SESPy analysis modules per compartment).

To see library warnings in the console, set `LOGLEVEL=DEBUG` before launch:

```powershell
$env:LOGLEVEL = "DEBUG"
micromamba run -n shiny shiny run app.py
```
```

- [ ] **Step 5.6: Add `.gitattributes` for cross-platform line endings (Cross-platform F3)**

Create `MosaicSES/.gitattributes` to enforce LF line endings on text files (prevents spurious whitespace diffs when Linux/macOS collaborators commit):

```
* text=auto
*.py text eol=lf
*.json text eol=lf
*.toml text eol=lf
*.md text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
```

- [ ] **Step 6: Commit**

```powershell
git add app.py pyproject.toml tests/test_multises_app_imports.py README.md .gitattributes
git commit -m "feat(mosaicses): top-level app.py + shiny/pyvis/networkx runtime deps + architectural-rule tests + a11y baseline + README run-the-app section"
```

---

## Task 13: Manual smoke-test checklist + chunk-3 acceptance verification

**Depends on Tasks:** Task 12.

**Files:**
- Create: `MosaicSES/docs/2026-05-12-chunk3-smoke-checklist.md`

Write the manual smoke-test checklist a human operator runs to confirm chunk 3 is shippable. This is the **chunk-3 acceptance test** until chunk-4 Playwright e2e tests automate the same scenarios.

- [ ] **Step 1: Write the checklist**

Create `MosaicSES/docs/2026-05-12-chunk3-smoke-checklist.md`:

```markdown
# Chunk-3 smoke-test checklist

Run this against `shiny run app.py` before declaring chunk 3 done. Each
item is a single user action with an expected observation. Failure of
any item is a chunk-3 regression — fix before merging.

Set up:
- `cd MosaicSES`
- `micromamba run -n shiny shiny run app.py`
- Open http://127.0.0.1:8000

## App boot

- [ ] Page loads without server-side traceback in the terminal.
- [ ] Sidebar shows three nav items: Project, Topology, Compartments.
- [ ] Topology panel is the initial active panel.

## Project panel

- [ ] Project panel shows a read-only metadata card with the loaded
      MultiSES name ("Curonian Lagoon LOAC seed"), DA site, river basin
      ("Nemunas"), regional sea ("baltic_sea"), and compartment + channel
      counts (6 and 26).
- [ ] The "unsaved text edits will be lost when switching compartments"
      muted note is visible at the bottom of the Project panel.

## Topology panel

- [ ] Left card "Compartments" shows 6 rows with the Curonian seed labels:
      Upper Nemunas, Lower Nemunas, Nemunas Delta, Curonian Lagoon,
      Klaipeda Strait, SE Baltic.
- [ ] Centre card "Topology" renders a pyvis canvas with 6 hexagonal
      nodes (one per compartment) coloured per archetype, and 26 directed
      edges (one per channel). NOTE: layout is physics-driven in v1; the
      river-to-coast LOAC continuum is NOT spatially encoded — that's a
      chunk-4 polish item (hierarchical typical_position-aware layout).
- [ ] Right card "Inspector" shows the picker dropdown with all 32
      compartment+channel entries.
- [ ] Picking a compartment from the dropdown displays its archetype,
      element count, connection count, and Focal TW badge.
- [ ] Picking a channel from the dropdown displays its channel_type,
      polarity, strength, confidence, source → target, and (for
      governance channels) the governance_regime.

## Compartments panel

- [ ] Top bar shows the compartment picker dropdown with all 6 compartments.
- [ ] Switching to "Curonian Lagoon" updates the badge to show
      `lagoon` + element count + connection count + "focal TW".
- [ ] The CLD Visualization tab renders a pyvis canvas with the lagoon's
      DAPSI elements (≥ 1 Driver, ≥ 1 Pressure, ≥ 1 Response — R001 added
      by Task 0).
- [ ] Switching from "Curonian Lagoon" to "SE Baltic" via the picker
      causes the CLD canvas to redraw with the SE Baltic compartment's
      DAPSI elements (different label set).
- [ ] The Loop Analysis tab renders without server-side error.
- [ ] Click "Detect" on Loop Analysis with Curonian Lagoon active.
      **Cycles appear** — at least one Balancing cycle (the 5-edge
      eutrophication-governance loop from Task 0). If the table is empty,
      verify the Curonian seed JSON's lagoon `connections` array exists
      and contains 5 entries.
- [ ] **Invariant 3 verification (the architectural pivot test):**
      With cycles shown in the Loop Analysis table for the lagoon, switch
      the compartment picker to "SE Baltic". The Loop Analysis table
      should reset to the pre-detection placeholder ("Click Detect to
      find feedback loops" or similar) — NOT continue showing the lagoon's
      cycles. If the table keeps the previous rows with new labels, the
      switcher protocol is broken.
- [ ] **Simulation staleness** (Reviewer 1 Issue 9): with Curonian
      Lagoon active, click "Dynamic Simulation" → "Run". A trajectory
      chart appears. Switch to "SE Baltic". A "stale" toast notification
      appears, BUT the chart does NOT update until you click "Run" again.
      This is a known v1 limitation; the fix is upstream in SESPy.

## Backwrite + persistence smoke

- [ ] In the Compartments → Edit Data tab on the Curonian Lagoon, add a
      new Element via the "Add Element" form. CLICK SAVE — do NOT just
      type in the field.
- [ ] Switch to another compartment, then back. The new element is still
      there (the backwrite listener wrote it back to active_multises).
- [ ] **Unsaved-text-edit limitation** (Reviewer 3 C-2): type a new label
      in the Edit Data text field WITHOUT pressing Save. Switch
      compartments. Return. The typed value is GONE — Shiny did not
      flush pending text inputs across the switch. This is a known v1
      limitation; chunk 4 fixes it.

## Stop the server

Press Ctrl+C in the terminal.

## What chunk 3 deliberately does NOT do

Documented v1 limitations a chunk-4 colleague should NOT raise as bugs:

- Topology canvas layout is physics-driven, not LOAC-hierarchical.
- No Save button — `persistence.save()` must be called from a Python REPL.
- Topology editor is read-only (no add/remove/rename, no archetype editor).
- Inspector is read-only (no polarity/strength/confidence editors).
- Unsaved text edits in nested SESPy modules are lost on compartment switch.
- `analysis_simulation` + `analysis_bot` results don't auto-clear on compartment switch.
- No "Seed diadromous channels" or "Suggest neighbours" one-click buttons.
- Project panel is read-only metadata (no edit, no recent-projects, no file load).
```

- [ ] **Step 2: Run the checklist manually (OPERATOR ONLY — skip if automated subagent)**

This step requires a human with a browser. **If you are an automated subagent executing this plan**: mark this step as `SKIPPED_AUTOMATED_SUBAGENT` in your status report and proceed directly to Step 3. Do NOT report the checklist as "passing" — you cannot have observed the architectural-pivot test (Loop Analysis clearing on compartment switch) without a real browser. The calling controller (or the user) runs the smoke pass before flagging chunk 3 complete.

**Subagent Risk F6:** report status as `DONE_WITH_CONCERNS` with note "Step 2 skipped — automated subagent cannot execute manual UI checks; smoke checklist awaits human verification."

- [ ] **Step 3: Commit the checklist**

```powershell
git add docs/2026-05-12-chunk3-smoke-checklist.md
git commit -m "docs(mosaicses): chunk-3 manual smoke-test checklist"
```

---

## Task 14: Push to remote + final review hook

**Depends on Tasks:** Task 13.

- [ ] **Step 1: Run the full test suite one final time**

```powershell
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
micromamba run -n shiny pytest tests/ -v 2>&1 | Select-Object -Last 40
```

(PowerShell-portable: `tail -40` only works on Unix shells; `Select-Object -Last 40` is the PowerShell equivalent.)

Expected: all chunk-1 + chunk-2 + chunk-3 tests pass. Final count = 241 PASSED (200 chunk-1+2+pre-spike baseline + 41 new chunk-3 tests including the Task 0 demo-loop tests + round-trip survival check, the architectural-rule tests in Task 12, the signature probe in Task 11, and the safety-critical contract tests in Tasks 9-10).

- [ ] **Step 2: Verify the git log is clean**

```powershell
git log --oneline 28a8d5b..HEAD
```

Expected: 15-16 commits from chunk 3 (Task 0 + Task 1 + Task 1.5 + Tasks 2-14), each with the `feat(mosaicses): ...` or `test(mosaicses): ...` or `docs(mosaicses): ...` prefix.

- [ ] **Step 3: Push to origin**

```powershell
git push origin main
```

Expected: clean push, no force needed.

- [ ] **Step 4: Trigger the final cross-cutting review**

This step is for the controller: dispatch a final code reviewer with the full chunk-3 diff (`git diff d1acc25..HEAD`) and the smoke-checklist results. Apply any CRITICAL fixes as one final commit. Then chunk 3 is shippable.

---

## Acceptance criteria for chunk 3

- [ ] All 241 unit + contract tests pass (`pytest tests/ -v`).
- [ ] `multises.validate(seed_curonian()) == []` — chunk-2 invariant must still hold after Task 0's added connections.
- [ ] `shiny run app.py` boots cleanly, all three panels load, Curonian seed is the default.
- [ ] Project panel displays read-only metadata (name, basin, sea, focal issue, counts).
- [ ] Topology panel renders the 6-compartment pyvis canvas and the inspector picker covers all 32 ids.
- [ ] Compartments panel switches between compartments and the CLD canvas redraws (invariant 1).
- [ ] Loop Analysis on Curonian Lagoon returns ≥ 1 Balancing cycle (Task 0 demo-loop verification).
- [ ] Switching compartments mid-loop-detection resets the Loop Analysis table to the pre-detection state (invariant 3 — the architectural-pivot test, verified meaningfully because the lagoon has a real cycle to lose).
- [ ] No Shiny imports in `multises/*.py` (verified by `test_multises_library_has_no_shiny_imports` — automated, not human-grepped).
- [ ] No SESPy imports outside the allow-list (verified by `test_multises_and_app_only_import_from_allowed_sespy_modules` — scans `multises/`, `multises_app/`, AND `app.py`).
- [ ] `app.py` module loads without error (verified by `test_app_module_loads`).
- [ ] All 10 SESPy module servers accept the kwargs `compartments_server` passes (verified by `test_sespy_module_server_signatures_accept_expected_kwargs`).
- [ ] Conventional-commit format on all task commits.
- [ ] Smoke-checklist (Task 13) fully ticked by a human operator — including the architectural-pivot test (Loop Analysis reset on compartment switch) and the simulation-staleness limitation.

---

## Self-review notes (post-revision)

**1. Spec coverage** —
- Shiny shell (§7) — `app.py` + `multises_app/dashboard.py` ✓ Tasks 3, 12.
- Topology editor (§7.2) — 3-column layout + pyvis canvas + inspector ✓ Tasks 4-6. **Editing affordances (add/remove/rename, archetype dropdown, polarity/strength/confidence editors, "Seed diadromous channels" / "Suggest neighbours" buttons) deferred to chunk 4** — documented in Revision log scope decisions.
- Compartments switcher (§7.3) — picker + embedded SESPy modules + switcher (with `_switching` guard) + backwrite (with snap-back-on-KeyError) ✓ Tasks 7-11. **`session.send_input_message` flush** is documented as a known v1 limitation in Task 9's docstring + the smoke checklist.
- Curonian seed demo-loop content (§8.4) — within-lagoon eutrophication-governance balancing loop ✓ Task 0.
- Pre-spike invariants 1-4 (§10.3) — already shipped + contract tests pinning them; chunk-3 code respects ALL FOUR (the original plan only honoured 3 because `active_compartment_id` was unisolated — fixed in Task 10).
- File layout (§9.1) — `multises_app/` + `app.py` placement matches; `state.py` added with documented justification (Shiny-bridge only, `replace_compartment` lives in library) ✓ Task 12. `translations/core.json` deferred to chunk 4 (empty-dict Translator is sufficient until then).
- Import allow-list (§9.3) — extended test covers `app.py`, `multises/`, and `multises_app/`; includes `"sespy"` and `"sespy.modules"` parent paths ✓ Task 12.

**Out of chunk-3 scope (chunk-4 deferred, explicitly):**
- Project Setup form, Recent Projects (read-only metadata card in `app.py` Project tab for chunk 3).
- Comparative + Cross-view panels.
- CSS skinning (`www/mosaic-skin.css`).
- Playwright e2e tests.
- Hierarchical `typical_position`-aware pyvis layout for the LOAC continuum.
- Save / Load UI buttons.
- Topology editor mutations (add/remove/rename/edit).
- `analysis_simulation` / `analysis_bot` stale-store auto-clear on compartment switch.

**2. Placeholder scan** — every step contains concrete code or commands. Step 5 of Task 12 calls out a manual operator action (browser smoke); not a code placeholder. Task 13's checklist is itself a placeholder for the chunk-4 Playwright suite — by design.

**3. Type consistency** —
- `MultiSESState` field names match across `state.py` and downstream `compartments_server` references.
- `state.active_compartment_project` type is `reactive.Value[Project]` everywhere it's mentioned.
- `state.event_bus.emit_isa_change()` call site (Task 9) matches the EventBus method declared in `sespy.event_bus.EventBus`.
- `replace_compartment` signature is `(ms: MultiSES, compartment_id: str, new_project: Project) -> MultiSES` consistently in `multises.data_structure` (Task 2) and at all call sites (Task 10).

**4. Known caveats (post-revision)**
- The reactive-isolate + emit_isa_change pattern is fragile under refactor. Contract tests pin syntax (call order, isolate presence, snap-back-on-KeyError, `_switching` guard read), but don't guard against semantic drift inside SESPy modules. Mitigation: chunk-4 Playwright e2e on the full switcher flow.
- Forward-compat: `cross_compartment_loops(..., g=None)` from Task 1.5 unblocks chunk-4's Cross-view panel caching. Existing chunk-2 callers continue working because `g` defaults to None.
- The `_switching` guard pattern relies on a Shiny `reactive.value` set/get inside a single effect chain. If Shiny's scheduler ever splits the set/get across event-loop boundaries, the guard could miss a fire. Verified safe in Shiny 1.5.1 by reading the reactive-flush ordering doc; pinned by `test_compartments_server_backwrite_respects_switching_guard`.
- Task 0's per-compartment JSON `connections` overrides assume `Compartment.to_dict()` round-trips the connections. Chunk-2's persistence test already covers this implicitly via the canary tests; if `test_seed_curonian_save_load_roundtrip_clean` fails after Task 0, the issue is in chunk-2's `Compartment.to_dict()` and needs a small chunk-2 follow-up patch (separate commit).
