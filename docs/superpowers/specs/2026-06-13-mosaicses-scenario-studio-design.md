# MosaicSES Scenario Studio — Design (Phase-2 priority D)

**Status:** Draft — pending user review.
**Scope:** Full feature (sub-projects A + B + C), in-app. Estimated ~2–3 prior-phase units; the spec is one coherent design, the implementation plan sequences A→B→C.
**Two-repo convention:** code lands in the **MosaicSES** repo; this spec lives in **SESPy** `docs/superpowers/specs/`.
**Origin:** Designed via a 4-lens judge-panel workflow (`wf_07bc1035-0f2`); algorithm-first spine (highest-scored) grafted with the scientific-fidelity design's honesty assets and the minimal/UX designs' no-schema-bump sidecar discipline.

---

## 1. Motivation

Priority D from the original MosaicSES brainstorm (deferred to Phase-2; design spec `2026-05-08-mosaicses-design.md` §11, lines ~156/597/1313) is **scenario testing / intervention propagation** and **"designing new ecosystems"** (Emerald Growth monograph; depolderisation as the worked example, per Tagliapietra).

The question a user wants to answer: *"If I intervene here — reduce this Pressure, add this Response, restore this wetland, re-open this tidal channel — what happens everywhere else in the connected system?"* MosaicSES already has the substrate: a cross-compartment composite digraph (`multises/composite.py`), per-compartment metrics (`multises/comparative.py`), and SESPy's per-compartment intervention analysis (`sespy.network.intervention_impact`). Scenario Studio is the **MultiSES-level layer** that ties them together: author a non-destructive intervention overlay, propagate its directional effect through the channel network, and compare baseline vs scenario.

**The core honesty constraint (load-bearing).** v1 propagation is **qualitative / sign-based**, not numeric. It predicts a *direction* of change (↑ / ↓ / ambiguous), ignoring magnitude, timescale, and `Channel.delay`. This mirrors the "screening signal only" framing the Emerald Justice equity card already carries (`comparative.py`). Every prediction ships with an explicit disclaimer; "ambiguous" means *genuinely indeterminate under sign reasoning* (conflicting feedback), never "no effect".

## 2. Architecture overview

Three layers, built in order. Each is independently testable; the baseline `MultiSES` is **never mutated** at any layer.

| Layer | New module(s) | Responsibility |
|---|---|---|
| **A — library core** (headless) | `multises/scenario.py`, `multises/propagation.py`, `multises/scenario_compare.py` | the `Scenario`/`Intervention` data model + sidecar persistence; the sign-lattice propagation engine; the qualitative direction diff |
| **B — materialisation + worked example** (headless) | extends `propagation.py`/`scenario_compare.py`; `multises/scenarios/depolderisation.py` | apply structural interventions to produce a derived `MultiSES`; the quantitative metric diff; the depolderisation factory on the Curonian seed |
| **C — Scenario Studio app** (Shiny) | `multises_app/modules/scenario_view.py`; extends `multises_app/state.py`, `app.py` | author interventions, run propagation, and read baseline-vs-scenario in-app |

**Dependency rule:** A has zero Shiny imports; B imports A; C imports A+B. Persistence is a **sidecar** (`<basename>.scenarios.json`) so the baseline project JSON round-trips byte-identical and `MULTISES_SCHEMA_VERSION` stays at 1 — every prior persistence/round-trip test is untouched.

## 3. Data model (sub-project A)

New module `multises/scenario.py` — **stdlib-only**, JSON-round-trippable, mirroring `data_structure.py` conventions (`Literal` aliases + `__post_init__` validation carrying stable error codes like `ErrorCode`; `LoadReport`-style soft-warning collection).

```python
@dataclass(frozen=True)
class Intervention:
    id: str                       # unique within a Scenario
    kind: InterventionKind        # Literal — see vocabulary §5
    label: str = ""
    compartment_id: str | None = None   # None ONLY for channel ops
    target: dict = field(default_factory=dict)   # kind-specific payload (see §5)
    sign: Polarity | None = None  # reuses data_structure Polarity = Literal["+","-"]; the imposed
                                  # direction. REQUIRED for seed_node, else None. Distinct from the
                                  # engine's computed Sign LATTICE in §4 (which adds UNSET/AMBIGUOUS).
    magnitude: Strength = "medium"  # reuses sespy Strength; DISPLAY-ONLY in v1 (§5)
    pressure_origin: PressureOrigin | None = None  # endogenic/exogenic (reuses PressureOrigin)
    rationale: str = ""           # EG-monograph defensibility note
    # __post_init__: validate kind/sign/magnitude against the Literal sets;
    # require target fields iff the kind needs them; raise ScenarioError(code) on violation.

@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str = ""
    baseline_name: str = ""       # advisory provenance (metadata.name authored against) — NOT an integrity lock
    interventions: tuple[Intervention, ...] = ()
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = 1

@dataclass
class ScenarioSet:               # persistence envelope (sidecar)
    metadata: ScenarioSetMetadata
    scenarios: list[Scenario]
```

- **Relationship to baseline.** A `Scenario` holds NO copy of compartments/channels — it references baseline ids by string only. Referential integrity (do targets resolve against a given baseline?) is collected as **soft `ScenarioReport` warnings at materialisation time**, mirroring `LoadReport`/the W30x soft-overlay pattern — *not* a hard raise. This keeps scenarios portable across baseline edits that rename/add elements.
- **Element-id namespacing (risk-driven, §13).** Element ids are unique only *within* a compartment. Intervention targets are therefore keyed by `(compartment_id, element_id)`, and the engine operates on namespaced composite nodes (`{cmp}::{element_id}`) throughout, de-namespacing only at output.
- **Persistence.** `save_scenario_set` / `load_scenario_set` are thin wrappers over `persistence.py`'s existing atomic-write + SHA-256 machinery, writing `<basename>.scenarios.json`. `to_dict` via `dataclasses.asdict`; `from_dict`/`from_file` follow the existing `from_dict`/`LoadResult`/`LoadReport` pattern.
- **Mutation helpers.** In-app edits use `_UNSET`-sentinel `add_intervention` / `replace_intervention` / `remove_intervention` pure helpers (mirroring `replace_compartment_overlays`).

## 4. Propagation engine (sub-project A)

New module `multises/propagation.py`. The decisive design choice is a **monotone 3-valued sign-lattice fixpoint**, *not* a first-settle BFS flood (which is visitation-order-dependent on cyclic graphs — and SES graphs are full of feedback loops).

**Sign lattice.** `Sign ∈ {UNSET, "+", "-", AMBIGUOUS}`, ordered `UNSET < {+,-} < AMBIGUOUS` (AMBIGUOUS absorbing). Combine = lattice **JOIN**: `+ ⊔ + = +`, `- ⊔ - = -`, `+ ⊔ - = AMBIGUOUS`, `x ⊔ UNSET = x`.

**Sign algebra.** Edge sign from `polarity` attr (`"+"→+1`, `"-"→-1`). `internal_link` synthetic edges are pinned `"+"` in `composite.py`, so traversal through the synthetic compartment-bottleneck nodes is sign-transparent with **zero special-casing**. Path sign = product of edge signs × seed sign — the **same even-#-of-negatives convention** as `cross_compartment_loops`/`sespy.network.loop_polarity`, so the new engine and the existing loop classifier provably agree rather than drift.

**Algorithm** (`propagate_signs(g, seeds) -> dict[node, Sign]`, Bellman-Ford-style relaxation, cycle-safe by construction):
1. `state[n] = UNSET` for all `n`; for each seed, `state[seed] = JOIN(state[seed], seed_sign)`; worklist := seeded nodes (conflicting seeds on one node start it AMBIGUOUS).
2. Pop `n`; for each out-edge `(n, m, polarity)`: `contributed = state[n] × edge_sign`; `new = JOIN(state[m], contributed)`; if `new != state[m]`: set and push `m`.
3. Repeat until worklist empty.

**Termination proof:** lattice height 2 (`UNSET → signed → AMBIGUOUS`, absorbing); each node's value is monotone non-decreasing under JOIN and changes ≤2×, so total relaxations ≤ `2·|E|` — O(V+E) per seed-set, no acyclicity assumption, never hangs on cycles. An optional `max_hops` cap mirrors `composite.py`'s `max_length`/`max_loops` guards.

**Cycles:** a reinforcing cycle (even negatives) re-enters a node with the *same* sign → no change → fixpoint; a balancing cycle (odd negatives) re-enters with the *opposite* sign → `JOIN(+,-) = AMBIGUOUS`, then stable. A node on a sign-flipping feedback loop is correctly **AMBIGUOUS, never oscillating, never silently collapsed** to a net sign.

**`g` is never mutated.** Read-only scenarios propagate on the cached baseline `build_composite_digraph(ms)`. Structural scenarios propagate on a `g.copy()` (see §6).

**`propagate_scenario(baseline, scenario) -> ScenarioResult`** maps namespaced-node signs back to per-element `{compartment_id, element_id, element_type, label, direction}` and per-compartment direction (synthetic-node sign with a member-DAPSI JOIN fallback). It integrates:
- **Reachable-equity (sign-aware, reuses #20):** intersect reached OUTCOME nodes (`element_type in OUTCOME_ELEMENT_TYPES`, sign ≠ UNSET) with each `Compartment.outcome_equity_dimensions` to report *which flagged equity dimensions move and in which direction*. (Requires promoting the private `comparative._downstream_outcome_ids` to public or re-deriving — see §13.) The scenario layer is **agnostic** to which dimensions are finalised; it consumes whatever exists (so the provisional `cultural_heritage` sign-off does not block it).
- **Leverage ranking (reuses sespy):** rank intervention *targets* and *impacted* elements by `sespy.network.leverage_scores` (per-compartment `IsaData`).
- **Provenance / explanation:** each reached node carries `reached_via ∈ {seed, dapsi, channel, mixed}`, whether its inbound influence crossed a compartment boundary, and — **for explanation only** — `hops` (BFS depth) and `contributing_paths`. These auxiliary fields are *order-sensitive bookkeeping and do NOT participate in the order-independent Sign fixpoint*. The loop classifier (`cross_compartment_loops`) is reused to explain *why* a node went ambiguous (reinforcing vs balancing).

## 5. Intervention vocabulary (sub-projects A + B)

| Primitive | Layer | Meaning / overlay | Materialisation |
|---|---|---|---|
| `seed_node(+/-)` | **A** | Impose a directional push on one DAPSI element `{cmp}::{element_id}`, or on the synthetic `{cmp}::__compartment__` node for a whole-compartment shock. Pure propagation seed, **zero graph mutation**. The primary primitive. | none (seed only) |
| `remove_channel` / `retune_channel` | **A** (read-only on `g.copy()`) | Close or flip-polarity/sign-block one inter-compartment channel for this scenario. Drawn dashed/recoloured, baseline ghosted. | edit the copied `g` edge |
| `add_node` | **B** | Introduce a new DAPSI element (id, label, type) into a compartment. Primary "designing new ecosystems" primitive (new wetland State / new regulating Ecosystem Service). | add to copied `g` + materialised `IsaData` |
| `remove_node` | **B** | Ablate an element + its incident edges (reuses `sespy.network.remove_nodes` semantics on the compartment's `IsaData`). Primary **depolderisation** primitive (remove the polder/dyke Pressure). | per-compartment `remove_nodes` |
| `add_channel` | **B** | Open a new inter-compartment channel (e.g. restored tidal `water_discharge`/`organisms` exchange). | `replace_channel`/add on materialised set |

- **`magnitude`** (all kinds): reuses sespy `Strength {weak,medium,strong}`; **captured and displayed but NEVER folded into the sign arithmetic** — labelled "display-only / future quantitative-flux mode" in the UI so it is never mistaken for affecting the predicted direction.
- **Whole-compartment seed semantics (decision §10):** a seed on `{cmp}::__compartment__` fans to ALL member DAPSI nodes via the `internal_link` `"+"` edges.
- **Deferred:** within-compartment edge surgery (`add_edge`/`remove_edge`/`retune_edge`) is **out of scope** this phase (the depolderisation story works without it; §14).

## 6. Structural materialisation (sub-project B)

`materialise_scenario(baseline, scenario) -> MultiSES` produces a *derived* baseline for the quantitative diff, applying structural interventions non-destructively:
- `g.copy()` for the propagation graph (engine side); for the metric side, rebuild a new `MultiSES` via `replace_compartment` (per-compartment `IsaData` edits for add/remove node) + `replace_channel` (channel ops) + `replace_compartment_overlays` (preserve overlays).
- **The real integration seam (risk §13):** `sespy.network.remove_nodes` / `intervention_impact` / `leverage_scores` operate on a single `Compartment.project.isa_data`, **not on `MultiSES`**. Materialisation translates per-compartment, then reassembles the `MultiSES`; cross-compartment edits go through `replace_channel`.
- **Channel retune-attenuate:** a "buffering" retune (restored wetland attenuates a nutrient channel) marks the edge **sign-blocking** — a signed input yields `UNSET` downstream — distinct from a polarity flip.

## 7. Comparison output (sub-projects A + B)

New module `multises/scenario_compare.py`. Two complementary, non-destructive diffs (both using `comparative.py`'s empty-frame-with-full-columns DataFrame contract):

**Primary — qualitative direction diff (always present; the engine's native output).** Baseline is the trivial empty scenario (every reachable node "unchanged"), so the diff *is* the `ScenarioResult` as change-from-baseline:
- `node_directions`: one row per reached element — `compartment_id, element_id, element_label, element_type, predicted_direction ∈ {up,down,ambiguous,unchanged}, is_seed, reached_via, hops, contributing_paths, is_cross_compartment, is_outcome, leverage, affected_equity_dimensions, equity_direction`.
- `compartment_directions`: per-compartment `net_direction` (`up` if up>down & no dominant ambiguity, `down` if reverse, else `mixed/ambiguous`) + `n_up/n_down/n_ambiguous`.

**Secondary — quantitative metric diff (only when the scenario has STRUCTURAL interventions).** Re-run the EXISTING comparative metrics on baseline vs `materialise_scenario(...)` and diff — `compartment_summary`, `leverage_hotspots`, `response_pressure_gap`, `tenet_gap_analysis`, `inter_compartment_metrics` — emitting per-metric `{before, after, delta}` frames (the literal shape `intervention_impact` already returns). **Honesty rule:** sign-only scenarios leave structure untouched, so the secondary panel renders **"no structural change"** rather than a spurious centrality/leverage delta.

## 8. Depolderisation worked example (sub-project B)

`multises/scenarios/depolderisation.py` — `build_depolderisation_scenario(ms)` is a **scenario factory** (not a new primitive) and the engine's end-to-end integration test, bound to the Curonian seed (`curonian_loac.json`). It composes existing primitives over a focal estuary/lagoon compartment:
1. `remove_node` the polder/dyke Pressure (+ its State-suppression links via `remove_nodes`);
2. `add_node` a restored intertidal-wetland State and a new regulating Ecosystem Service (nutrient buffering) + its Goods-&-Benefits outcome;
3. **channel modelling (decision §10):** `add_channel` restoring tidal `water_discharge`/`organisms` exchange with the neighbour, **AND** a `retune_channel` sign-blocking the incident nutrient channel (wetland buffering);
4. `seed_node "-"` on the residual eutrophication Pressure and `"+"` on the new wetland State, then propagate.

Because it touches both within-compartment DAPSI and inter-compartment channels, it exercises synthetic-bottleneck traversal, conflicting-path JOIN, and a balancing loop (residual pressure vs new buffering) → at least one AMBIGUOUS node, proving the lattice.

**Named caveat constants** (rendered in the UI disclaimer): (1) qualitative direction only — not a hydrodynamic/biogeochemical model, no magnitudes/timescales despite `Channel.delay` existing; (2) depolderisation is strongly site/timescale-dependent and **non-monotonic** (short-term nutrient/sediment pulse vs long-term buffering) — nodes whose incident channel `delay` differs are labelled "direction shown is long-run intent; transient may differ"; (3) the breach is `endogenic` (locally managed) but its benefit depends on `exogenic` drivers (sea-level rise, upstream load); (4) "designing new ecosystems" ≠ restored-to-reference — a predicted `+` on a habitat State means *changed, not restored*. The caveat text is flagged for EG-domain-author (Tagliapietra) review.

## 9. Scenario Studio app module (sub-project C)

`multises_app/modules/scenario_view.py`, mirroring `cross_view.py`:
- **Intervention-editor sidebar** using the `overlay_edit` selectize choice-dict grammar + Refresh/dirty-hint pattern; pick kind → compartment → target → sign/magnitude → rationale; list + add/remove interventions.
- **Composite propagation canvas** reusing `output_pyvis_network`/`render_pyvis_network`, nodes **tinted by `predicted_direction`** (green=up, red=down, amber=ambiguous, faded=unchanged), seeds ringed, modified channels dashed with baseline ghosted; a `digraph_table_ui` a11y fallback (the WCAG pattern shipped in the UI-hardening phase).
- **Tables:** a "Predicted direction of change" `render.DataGrid` (filterable to outcomes-only), the per-compartment roll-up strip, the equity-direction table, and the secondary metric-delta DataGrid (structural scenarios only).
- **Disclaimer:** the `comparative.py` `sticky-disclaimer`/`help_text` pattern stating the qualitative-sign-only contract and the meaning of "ambiguous".
- **State:** extend `MultiSESState` with `active_scenario: reactive.Value[Scenario|None]` and `scenario_set: reactive.Value[ScenarioSet]` beside `active_multises` (baseline untouched); reuse `event_bus` + the `dirty` wiring shipped in UI-hardening. New nav panel wired in `app.py`.

## 10. Decisions (resolved open questions)

| # | Decision | Rationale |
|---|---|---|
| Phase scope | **A + B + C** (full, in-app) | user choice; B/C build directly on A |
| Propagation | **monotone sign-lattice fixpoint**, not BFS flood | order-independent result + ≤2|E| termination proof on cyclic graphs |
| Persistence | **sidecar** `<basename>.scenarios.json`, schema stays v1 | baseline round-trips byte-identical; prior tests untouched |
| Sign-only | magnitude/`delay` captured + displayed, **never in the arithmetic** | honours the qualitative decision; same "screening signal" honesty as the equity card |
| AMBIGUOUS | absorbing, **never collapsed** to a net sign | conflicting feedback is genuinely indeterminate; reuse `loop_polarity` to explain why |
| Compartment seed | **whole-compartment shock** (fans to member DAPSI via `internal_link`) | matches the "shock this compartment" intuition; stricter mode deferred |
| Edge surgery | **deferred** (out of scope) | depolderisation works without it; YAGNI |
| Depolderisation channels | factory composes **both** `add_channel` (tidal exchange) + retune-attenuate (buffering) | most faithful ecology; exercises both primitives |
| Equity dimensions | scenario layer **agnostic** to which are finalised | decouples from the provisional `cultural_heritage` Nyka sign-off |

## 11. Error handling

- **Scenario validation** is fail-fast at construction (`ScenarioError` codes for bad kind/sign/magnitude/missing target fields) — like `_ChannelValidationError`.
- **Referential integrity** is *soft* at materialisation: a dangling target id collects a `ScenarioReport` warning and that intervention is skipped, never a hard crash (a scenario must survive baseline edits).
- **App layer** routes all save/load/propagation failures through the `friendly_error` helper (shipped in UI-hardening) into sanitized toasts; the propagation engine itself never raises on graph shape (cycles/empties are handled by construction — empty MultiSES → empty result, the same empty-state discipline as the UI-hardening crash guards).

## 12. Testing strategy

- **A (`tests/test_propagation.py`, `test_scenario.py`, `test_scenario_compare.py`):** sign-algebra truth table; conflict→AMBIGUOUS; reinforcing vs balancing cycle cases; fixpoint **termination bound + order-independence** (shuffle worklist seed order, assert identical signs); synthetic-bottleneck traversal; channel flip/sign-block; `Scenario` `to_dict`/`from_dict` round-trip + soft-warning on dangling refs; qualitative direction-diff frame contract (full columns when empty).
- **B:** `materialise_scenario` per-compartment translation; `add_node`/`remove_node`/channel ops; the secondary metric diff `{before,after,delta}`; **depolderisation end-to-end** expected directions (nutrient-related Impacts down, fish-habitat ES up, ≥1 AMBIGUOUS node) on the Curonian seed.
- **C:** pure-helper UI assertions via `str(...tagify())` (sidebar grammar, canvas tint classes, disclaimer text, a11y table); Playwright e2e (author a seed_node → Refresh → direction tints appear → outcomes-only filter), using the `mosaicses_app_url` fixture (180 s startup) shipped in UI-hardening.

## 13. Risks & mitigations

1. **IsaData↔MultiSES seam** — sespy `remove_nodes`/`intervention_impact`/`leverage_scores` take `IsaData`, not `MultiSES`. Materialisation translates per-compartment; cross-compartment edits via `replace_channel`. *Most likely overrun (sub-project B) — own it explicitly.*
2. **Parallel-channel collapse** — `build_composite_digraph` uses `nx.DiGraph`, which overwrites parallel synthetic→synthetic edges (warned in `composite.py`). `add_channel`/`retune_channel` on an already-connected pair can shadow an existing edge. *Mitigation:* detect + warn when an edited channel's edge carries a different `channel_id`; do **not** upgrade to `MultiDiGraph` this phase.
3. **Ambiguous saturation** — dense graphs with many balancing loops can drive most nodes to AMBIGUOUS, reducing decision value. *Mitigation:* surface `contributing_paths` + dominant-sign tally + reinforcing/balancing loop character so users see *why*; magnitude-weighted tie-break is a documented future mode, never v1 math.
4. **Private/shape refactors** — `comparative._downstream_outcome_ids` is private; `intervention_impact` is per-metric. Promote to public or re-derive. Small but real friction.
5. **Element-id non-uniqueness across compartments** — key targets by `(compartment_id, element_id)`; operate on namespaced composite nodes; validate resolution at materialisation.
6. **Direction ≠ causation overreach** — signed reachability ignores strength/timescale; depolderisation is non-monotonic. *Mitigation:* the named-caveat constants + sticky-disclaimer on every prediction + the "long-run intent; transient may differ" label on delayed-channel nodes; caveat text gets EG-domain-author review.

## 14. Out of scope / deferred

- Within-compartment edge surgery (`add_edge`/`remove_edge`/`retune_edge`).
- Numeric / magnitude-weighted flux propagation; any timescale/`delay`-driven dynamics.
- A guided "restore ecosystem" wizard (the depolderisation factory is a fixed worked example, not a generalised wizard).
- `MultiDiGraph` parallel-channel support.

## 15. Build order (for the plan)

1. **A** — `scenario.py` (data model + sidecar persistence + validation) → `propagation.py` (Sign lattice + `propagate_signs` + `propagate_scenario` for seed_node + read-only channel ops) → `scenario_compare.py` primary direction diff. Acceptance: sign truth-table, cycle/conflict/order-independence, a hand-built two-compartment propagation pass, round-trip + soft-warning tests all green.
2. **B** — `materialise_scenario` (structural ops, per-compartment translation) → secondary metric diff → `scenarios/depolderisation.py` + Curonian end-to-end test.
3. **C** — `scenario_view.py` (editor sidebar + tinted canvas + direction/equity/metric DataGrids + disclaimers + a11y table) → `MultiSESState` extension → `app.py` nav wiring → e2e.
