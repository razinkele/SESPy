# MosaicSES Scenario Studio — Design (Phase-2 priority D)

**Status:** Draft (rev 2 — incorporates a 5-angle adversarial spec review, `wf_96b4600b-89a`). Pending user review.
**Scope:** Full feature (sub-projects A + B + C), in-app. Estimated ~2–3 prior-phase units; one coherent design, the plan sequences A→B→C.
**Two-repo convention:** code lands in the **MosaicSES** repo; this spec lives in **SESPy** `docs/superpowers/specs/`.
**Origin:** Designed via a 4-lens judge-panel workflow (`wf_07bc1035-0f2`), then hardened by a 5-angle adversarial review that *ran the proposed algorithm on the real Curonian seed* and surfaced 2 CRITICAL + ~10 HIGH issues — all addressed below (see §16 changelog).

---

## 1. Motivation

Priority D (deferred to Phase-2; `2026-05-08-mosaicses-design.md` §11) is **scenario testing / intervention propagation** and **"designing new ecosystems"** (Emerald Growth monograph; depolderisation as the worked example, per Tagliapietra).

The question: *"If I intervene here — reduce this Pressure, add this Response, restore this wetland, re-open this tidal channel — what direction does everything else move?"* MosaicSES already has the substrate (per-compartment DAPSI graphs via SESPy, inter-compartment channels, the comparative metrics). Scenario Studio is the **MultiSES-level layer**: author a non-destructive intervention overlay, propagate its directional effect, compare baseline vs scenario.

**Core honesty constraint.** v1 propagation is **qualitative / sign-based**, not numeric — it predicts a *direction* (↑/↓/ambiguous), ignoring magnitude, timescale, and `Channel.delay`. "Ambiguous" means *genuinely indeterminate under sign reasoning* (conflicting feedback), never "no effect". Every prediction ships with explicit caveats (§8).

## 2. Architecture overview

Three layers, built in order. The baseline `MultiSES` is **never mutated** at any layer; persistence is a **sidecar** so the baseline JSON round-trips byte-identical and `MULTISES_SCHEMA_VERSION` stays 1.

| Layer | New module(s) | Responsibility |
|---|---|---|
| **A — library core** (headless) | `multises/scenario.py`, `multises/propagation.py`, `multises/scenario_compare.py` | data model + sidecar persistence; the two-level sign-lattice engine; the qualitative direction diff |
| **B — materialisation + worked example** (headless) | extends `propagation.py`/`scenario_compare.py`; `multises/scenarios/depolderisation.py` | structural materialisation → derived `MultiSES`; the quantitative metric diff; the grounded depolderisation factory |
| **C — Scenario Studio app** (Shiny) | `multises_app/modules/scenario_view.py`; extends `state.py`, `app.py` | author, propagate, and compare in-app |

Dependency rule: A has zero Shiny imports; B imports A; C imports A+B.

## 3. Data model (sub-project A)

`multises/scenario.py` — stdlib-only, JSON-round-trippable, mirroring `data_structure.py` (`Literal` aliases + `__post_init__` validation with stable `ScenarioError` codes; `LoadReport`-style soft-warning collection).

```python
@dataclass(frozen=True)
class Intervention:
    id: str                       # unique within a Scenario
    kind: InterventionKind        # Literal — see §5
    label: str = ""
    compartment_id: str | None = None   # None ONLY for channel ops
    target: dict = field(default_factory=dict)   # kind-specific payload (§5)
    sign: Polarity | None = None  # reuses data_structure Polarity = Literal["+","-"]; the imposed
                                  # direction. REQUIRED for seed_node, else None. Distinct from the
                                  # engine's computed Sign LATTICE in §4 (which adds UNSET/AMBIGUOUS).
    magnitude: Strength = "medium"  # reuses sespy Strength; DISPLAY-ONLY in v1 (§5)
    pressure_origin: PressureOrigin | None = None  # endogenic/exogenic (reuses PressureOrigin)
    rationale: str = ""           # EG-monograph defensibility note
    # __post_init__: validate kind/sign/magnitude against the Literal sets; require target fields
    # iff the kind needs them; raise ScenarioError(code) on violation.

@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str = ""
    baseline_name: str = ""       # advisory provenance — NOT an integrity lock
    interventions: tuple[Intervention, ...] = ()
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = 1

@dataclass
class ScenarioSet:               # persistence envelope (sidecar)
    metadata: ScenarioSetMetadata
    scenarios: list[Scenario]
```

- **Relationship to baseline.** A `Scenario` holds NO copy of compartments/channels — it references baseline ids by string. Referential integrity is collected as **soft `ScenarioReport` warnings at materialisation time** (mirrors `LoadReport`), *not* a hard raise — scenarios stay portable across baseline edits.
- **Element-id namespacing.** Element ids are unique only *within* a compartment, so intervention targets are keyed by `(compartment_id, element_id)`; the engine namespaces internally and de-namespaces at output.
- **Persistence.** `save_scenario_set`/`load_scenario_set` are thin wrappers over `persistence.py`'s atomic-write + SHA-256, writing the sidecar `<basename>.scenarios.json`. `to_dict` via `dataclasses.asdict`; `from_dict`/`from_file` follow the existing `LoadResult`/`LoadReport` pattern.
- **Mutation helpers.** `_UNSET`-sentinel `add_intervention`/`replace_intervention`/`remove_intervention` pure helpers.

## 4. Propagation engine (sub-project A)

`multises/propagation.py`. **Key correction (spec review): the engine does NOT propagate on `build_composite_digraph`'s synthetic-compartment-node graph.** That node is a *bidirectional* hub (`composite.py` adds both `synthetic→dapsi` and `dapsi→synthetic` `internal_link` edges), so every element's sign collides there — an empirical run on the Curonian seed drove **100% of reached nodes to AMBIGUOUS**. The composite digraph is right for loop/reachability analysis, wrong for directional sign propagation.

Instead: a **two-level monotone sign-lattice fixpoint** — per-element *within* compartments (on the real signed DAPSI edges), and compartment-level *across* channels (v1 channels are compartment-level, not element-targeted).

**Sign lattice.** `Sign ∈ {UNSET, "+", "-", AMBIGUOUS}`, `UNSET < {+,-} < AMBIGUOUS` (AMBIGUOUS absorbing). **JOIN:** `+⊔+=+`, `-⊔-=-`, `+⊔-=AMBIGUOUS`, `x⊔UNSET=x`, `AMBIGUOUS⊔x=AMBIGUOUS`.

**Sign-multiply lift (complete).** `signed(±) × edge(±1) = product`; **`UNSET × edge = no contribution`** (skip; never marks the target reached); **`AMBIGUOUS × edge = AMBIGUOUS`**. A **sign-blocking** edge contributes `UNSET` for any source (JOIN identity — adds nothing, never marks reached, never a contributing sign-source).

**Within-compartment pass (per-element, precise).** Build each compartment's real signed DAPSI digraph from `IsaData.connections` via `sespy.network.to_digraph` (edge sign from connection polarity). Seed the imposed `±` on each `seed_node` target element, then relax to a fixpoint (pop `n`; for out-edge `(n,m)`: `new = JOIN(state[m], lift(state[n], edge_sign))`; if changed, set + push `m`). **A seed sign is the imposed direction of that element's *own* state variable; the engine multiplies by OUTBOUND edge polarity only** — it does NOT re-apply the Response/governance dampening convention (that dampening already lives in the negative Response→Pressure edge).

**Cross-compartment pass (compartment-level, honest coarse).** Each compartment exposes a **net direction** = majority tally of its determinate member-element signs: `up` if `n_up>n_down`, `down` if reverse, else `ambiguous` (ties/none → `ambiguous`). For each `Channel A→B`, inject `net_dir(A) × channel_polarity` as a single compartment-level **inflow** influence into B (a coarse seed re-entering B's within-compartment pass).

**Joint fixpoint.** The two passes iterate together: re-run a compartment's within-pass when an inbound channel's inflow changes; recompute net directions; repeat. Monotone over the same height-2 lattice ⇒ **terminates** (element signs and compartment net directions each climb ≤2×; total work `O(Σ|E_within| + |channels|·|compartments|)`, near-linear). No acyclicity assumption; within- or cross-compartment cycles settle to a stable AMBIGUOUS, never oscillate. (Termination bound stated honestly: each node is enqueued ≤3× — initial seed + 2 monotone increases — so within-compartment edge relaxations are `≤3|E_within|`.)

**Result — `propagate_scenario(baseline, scenario) -> ScenarioResult`:** per-element `{compartment_id, element_id, element_type, label, direction ∈ {up,down,ambiguous,unchanged}, is_seed, reached_via, is_cross_compartment, is_outcome, leverage}`; per-compartment `{net_direction, n_up, n_down, n_ambiguous}`. Integrations:
- **Reachable-equity — computed DIRECTLY from the result, NOT via `comparative._downstream_outcome_ids`** (which runs on a single compartment's `to_digraph` *and* ignores sign — wrong on both counts). For each signed (`≠UNSET`) outcome element (`element_type ∈ OUTCOME_ELEMENT_TYPES`), de-namespace to `(compartment_id, element_id)`, look up that compartment's `outcome_equity_dimensions`, and emit each flagged dimension with `equity_direction ∈ {up,down,ambiguous}` — AMBIGUOUS outcomes are surfaced with `ambiguous`, never dropped. Agnostic to which dimensions are finalised (so the provisional `cultural_heritage` sign-off does not block it).
- **Leverage ranking:** `sespy.network.leverage_scores` (per-compartment IsaData) ranks targets + impacted elements.
- **Explain ambiguity:** for an AMBIGUOUS node, report the sign-conflicting contributing paths and consult **`sespy.network.feedback_loops()` (per-compartment)** — NOT `cross_compartment_loops`, which filters out <2-compartment cycles and would miss the dominant *within*-compartment balancing source (e.g. `R001 -[-]→ P001 → … → R001`). `hops`/`contributing_paths` are min-depth-BFS bookkeeping for **explanation only** and do NOT participate in the order-independent fixpoint. **No `max_hops` cap** — the lattice already terminates in `O(|E|)`, and an order-dependent depth cutoff would break order-independence.

**The engine owns no cross-session cache** — it builds (or accepts a caller-supplied) per-compartment digraph set per call; A stays headless and self-contained.

**Honest asymmetry (a named caveat, §8).** Within-compartment predictions are per-element and precise; **cross-compartment predictions are compartment-level coarse** — a channel carries the source compartment's net direction, not an element-targeted effect, because v1 channels are not element-targeted. Element-level cross-compartment targeting is deferred to a future "targeted-channel" phase (the reserved `targeted_pressure_ids` field).

## 5. Intervention vocabulary (sub-projects A + B)

| Primitive | Layer | Meaning / overlay |
|---|---|---|
| `seed_node(+/-)` | **A** | Impose a directional push on one element `{cmp}::{element_id}`, or a whole-compartment shock by seeding ALL member elements of a compartment with the sign. Pure seed, zero graph mutation. The primary primitive. Tinted + ringed on the canvas. |
| `remove_channel` / `retune_channel` | **A** (read-only edit of the per-call graph) | Close a channel, or flip its polarity, or mark it **sign-blocking** (contributes UNSET). Drawn dashed/recoloured, baseline ghosted. |
| `add_node` | **B** | Introduce a new element (id, label, `type`). Primary "designing new ecosystems" primitive. |
| `remove_node` | **B** | Ablate an element + its incident edges (reuses `sespy.network.remove_nodes` on the compartment's `IsaData`). |
| `add_channel` | **B** | Open a new inter-compartment channel. |

**Decisions baked in:**
- **`magnitude`** (all kinds) reuses sespy `Strength {weak,medium,strong}` — **captured and displayed but NEVER folded into the sign arithmetic** (labelled "display-only / future quantitative-flux mode").
- **Whole-compartment seed = seed all member elements** (well-defined now that the engine uses per-compartment real DAPSI graphs — no `expansion="strict"` participation problem).
- **Channel type strings are validated against the real vocabulary** (`organisms_marine_estuarine`, `organisms_diadromous`, `water_discharge`, `nutrients`, `governance`, …). There is **no** bare `organisms` type.
- **Deferred:** within-compartment edge surgery (`add_edge`/`remove_edge`/`retune_edge`) is **out of scope** (§14).

## 6. Structural materialisation (sub-project B)

`materialise_scenario(baseline, scenario) -> MultiSES` produces a *derived* baseline for the quantitative diff, applying structural interventions non-destructively: rebuild a new `MultiSES` via `replace_compartment` (per-compartment `IsaData` edits for add/remove node) + `replace_channel` (channel ops) + `replace_compartment_overlays` (preserve overlays).

- **The IsaData↔MultiSES seam (risk §13):** `sespy.network.remove_nodes`/`intervention_impact`/`leverage_scores` take a single `Compartment.project.isa_data`, **not** `MultiSES`. Materialisation translates per-compartment, then reassembles; cross-compartment edits go through `replace_channel`.
- **Sign-block vs polarity-flip vs attenuate:** `retune_channel` supports (a) polarity flip and (b) sign-block (edge contributes UNSET). **Note (domain review):** a wetland *attenuates* (partial, dose-dependent), it does not *nullify* — so the depolderisation factory (§8) does NOT sign-block the nutrient channel; it represents buffering honestly via competing `±` seeds (§8). Sign-block is reserved for a true barrier (e.g. a closed sluice).

## 7. Comparison output (sub-projects A + B)

`multises/scenario_compare.py`. Two diffs (both using `comparative.py`'s empty-frame-with-full-columns contract):

**Primary — qualitative direction diff (always).** Baseline is the trivial empty scenario (every reached node "unchanged"), so the diff IS the `ScenarioResult`:
- `node_directions`: per reached element — `compartment_id, element_id, element_label, element_type, predicted_direction ∈ {up,down,ambiguous,unchanged}, is_seed, reached_via, is_cross_compartment, is_outcome, leverage, affected_equity_dimensions, equity_direction ∈ {up,down,ambiguous}`.
- `compartment_directions`: per compartment `net_direction` (the §4 tally) + `n_up/n_down/n_ambiguous`.

**Secondary — quantitative metric diff (only when the scenario has STRUCTURAL interventions).** **"Structural" is defined as any intervention whose `kind ∈ {add_node, remove_node, add_channel, remove_channel, retune_channel}`** (anything `materialise_scenario` applies); `seed_node` is the only non-structural kind. Re-run the existing metrics on baseline vs `materialise_scenario(...)` and diff: `compartment_summary`, `leverage_hotspots`, `response_pressure_gap`, `tenet_gap_analysis`, `inter_compartment_metrics`. **Per-metric diff contract:** each diff is an outer-join on a stated key — `compartment_id` for `compartment_summary`/`inter_compartment_metrics`; `(compartment_id, element_id)` for `leverage_hotspots`; `(compartment_id, pressure_id)` for `response_pressure_gap`; `(subject_kind, subject_id)` for `tenet_gap_analysis` — emitting `{before, after, delta}` per numeric column, with added/removed rows rendering `before=NaN`/`after=NaN`. **Honesty rule:** sign-only scenarios leave structure untouched, so the secondary panel renders **"no structural change"**, never a spurious delta.

## 8. Depolderisation worked example (sub-project B)

**Grounding correction (review): the Curonian seed contains no polder/dyke Pressure** (its lagoon Pressures are `P001` Eutrophication, `P002` Hypoxia, `P003` …). Depolderisation only makes sense against a *poldered* baseline, so `build_depolderisation_scenario(ms)` **constructs its own "before" state first**, then breaches it:
1. `add_node` a polder/dyke Pressure + its State-suppression connections into the focal `curonian_lagoon` compartment (the pre-depolderisation barrier);
2. `remove_node` that polder Pressure (the breach);
3. `add_node` a restored intertidal-wetland habitat (`type="Marine Processes & Functioning"`), a regulating buffering service (`type="Ecosystem Services"`), and its outcome (`type="Goods & Benefits"`) — **canonical type strings, not the loose "State"/"ES" of rev 1**;
4. `add_channel` a restored tidal exchange to the neighbouring coastal-sea compartment as `organisms_marine_estuarine` (marine larvae/juvenile ingress; a `channel_type` **not already present** between that pair, so the `nx.DiGraph` parallel-edge collapse does not shadow it);
5. `seed_node "-"` on residual eutrophication `P001` and `"+"` on the new wetland habitat. **Buffering-vs-residual is represented honestly** by the JOIN of these competing seeds at contested downstream nodes (→ AMBIGUOUS where indeterminate), NOT by sign-blocking the nutrient channel.

The example exercises within-compartment per-element propagation, the cross-compartment net-direction crossing, competing-seed JOIN, and a within-compartment balancing loop → ≥1 AMBIGUOUS node, proving the lattice. It is bound to concrete seed element ids and is the engine's end-to-end integration test.

**Named caveat constants** (rendered in the UI disclaimer):
1. Qualitative direction only — not a hydrodynamic/biogeochemical model; no magnitudes/timescales despite `Channel.delay`.
2. Non-monotonic: depolderisation is site/timescale-dependent (short-term nutrient/sediment pulse vs long-term buffering); delayed-channel nodes are labelled "long-run intent; transient may differ".
3. Endogenic breach, exogenic dependency (sea-level rise, upstream load) — flagged via `pressure_origin`.
4. "Designing new ecosystems" ≠ restored-to-reference — a predicted `+` on a habitat means *changed, not restored*.
5. **No dose/threshold** *(added in review):* a predicted direction means a signed pathway exists, not that the effect is large enough to matter; sub-threshold interventions can show a direction yet produce no real change.
6. **Cross-compartment is coarse** *(added in review):* a channel carries the source compartment's net direction, not an element-specific effect; per-element cross-compartment claims are not supported in v1.

Caveat text is flagged for EG-domain-author (Tagliapietra) review.

## 9. Scenario Studio app module (sub-project C)

`multises_app/modules/scenario_view.py`, mirroring `cross_view.py`:
- **Intervention-editor sidebar** (the `overlay_edit` selectize grammar + Refresh/dirty-hint): pick kind → compartment → target → sign/magnitude → rationale; list + add/remove.
- **Composite propagation canvas** (`output_pyvis_network`/`render_pyvis_network`) with nodes tinted by `predicted_direction` (green=up, red=down, amber=ambiguous, faded=unchanged), seeds ringed, modified channels dashed/ghosted; a `digraph_table_ui` a11y fallback. (Canvas is for *display*; it may show the composite layout, but the **directions come from the §4 two-level engine, not from a composite-graph walk**.)
- **Tables:** "Predicted direction of change" `render.DataGrid` (filterable to outcomes-only), the per-compartment net-direction strip, the equity-direction table, and the secondary metric-delta DataGrid (structural scenarios only).
- **Disclaimer:** the `sticky-disclaimer`/`help_text` pattern stating the qualitative-sign-only contract, the within-precise/cross-coarse asymmetry, and the meaning of "ambiguous".
- **State:** extend `MultiSESState` with `active_scenario: reactive.Value[Scenario|None]` + `scenario_set: reactive.Value[ScenarioSet]` (baseline untouched); reuse `event_bus` + the `dirty` wiring. New nav panel in `app.py`.

## 10. Decisions (resolved questions)

| # | Decision | Rationale |
|---|---|---|
| Phase scope | **A + B + C** (full, in-app) | user choice |
| Engine graph | **two-level fixpoint on per-compartment real DAPSI graphs + compartment-level channel crossing**, NOT the composite synthetic-hub graph | the hub collides all element signs → ~100% AMBIGUOUS (measured); also simpler/cheaper |
| Channel crossing | **compartment-level** — source net direction × polarity into the target | v1 channels are compartment-level; honest coarse; element-targeting deferred |
| Compartment direction | **majority tally** of determinate member signs | the synthetic-node sign is degenerate (first to go AMBIGUOUS) |
| Persistence | **sidecar**, schema stays v1 | baseline round-trips byte-identical |
| Sign-only | magnitude/`delay` captured + displayed, **never in the arithmetic** | qualitative honesty |
| AMBIGUOUS | absorbing, **never collapsed**; explained via `feedback_loops()` | conflicting feedback is genuinely indeterminate |
| Whole-compartment seed | **seed all member elements** | well-defined on the per-compartment graph |
| Edge surgery | **deferred** | YAGNI; depolderisation doesn't need it |
| Equity | computed **directly from the propagation result**, no `_downstream_outcome_ids` reuse; agnostic to which dimensions are finalised | that helper is per-compartment + sign-ignoring |
| Depolderisation | factory **builds its own polder substrate** then breaches; canonical types; buffering via competing seeds | seed has no polder Pressure; wetland attenuates ≠ nullifies |
| `max_hops` | **dropped** | the lattice terminates; a depth cap breaks order-independence |

## 11. Error handling

- **Scenario validation** is fail-fast at construction (`ScenarioError` codes), like `_ChannelValidationError`.
- **Referential integrity** is *soft* at materialisation: a dangling target collects a `ScenarioReport` warning and that intervention is skipped — never a hard crash.
- **App layer** routes all save/load/propagation failures through the `friendly_error` helper into sanitized toasts; the engine never raises on graph shape (empty MultiSES → empty result, per the UI-hardening empty-state discipline).

## 12. Testing strategy

- **A (`tests/test_propagation.py`, `test_scenario.py`, `test_scenario_compare.py`):**
  - sign-algebra truth table **including the multiply lift (`UNSET×`, `AMBIGUOUS×`) and the sign-block operator**;
  - conflict→AMBIGUOUS; reinforcing-even / balancing-odd cycle cases;
  - **order-independence**: identical final signs across (i) shuffled seed order, (ii) FIFO vs LIFO worklist, (iii) shuffled per-node out-edge order — plus an independent reference oracle (recompute each node's sign as the JOIN over all simple paths on a small graph);
  - cross-compartment net-direction crossing (a 2-compartment hand graph: seed in A → expected coarse direction in B);
  - **saturation-ceiling regression (HARD acceptance):** on `seed_curonian()`, a single `seed_node` must leave **≥40% of reached nodes determinate** (`+`/`-`) — guards against a regression to the synthetic-hub saturation;
  - `Scenario` `to_dict`/`from_dict` round-trip + soft-warning on dangling refs; the primary direction-diff full-column-when-empty contract.
- **B:** `materialise_scenario` per-compartment translation; add/remove node + channel ops; the secondary metric diff contract (join keys, NaN rows); **depolderisation end-to-end** — builds its polder substrate, breaches, and yields the expected determinate directions (residual-pressure-linked Impacts down, wetland-linked outcomes up) with ≥1 AMBIGUOUS node, on the real Curonian seed.
- **C:** pure-helper UI assertions via `str(...tagify())` (sidebar grammar, canvas tint classes, disclaimer text, a11y table); Playwright e2e (author a seed → Refresh → tints appear → outcomes-only filter), using the `mosaicses_app_url` fixture (180 s startup) from UI-hardening.

## 13. Risks & mitigations

1. **IsaData↔MultiSES seam** — sespy `remove_nodes`/`intervention_impact`/`leverage_scores` take `IsaData`, not `MultiSES`. Materialisation translates per-compartment; cross-compartment via `replace_channel`. *Most likely overrun (sub-project B).*
2. **Parallel-channel collapse** — `nx.DiGraph` overwrites parallel synthetic→synthetic edges; an `add_channel` of an already-present type between a pair is shadowed. *Mitigation:* the depolderisation factory uses a `channel_type` not present between the pair; the engine/materialiser warns on collision; no `MultiDiGraph` this phase. (Less load-bearing now that within-compartment propagation no longer routes through synthetic nodes.)
3. **Residual ambiguity** — even de-bottlenecked, genuine within-compartment balancing loops produce some AMBIGUOUS nodes. *Mitigation:* the tally-based net direction (robust to a few ambiguous members) + `feedback_loops()` explanation + the ≥40%-determinate ceiling test + honest disclaimer. (No longer ~100% as in the broken design.)
4. **Cross-compartment coarseness is a deliberate v1 limitation** — element-level cross-compartment claims are not supported. *Mitigation:* the named caveat (6) + the within-precise/cross-coarse asymmetry stated on every cross-compartment row (`is_cross_compartment`).
5. **Element-id non-uniqueness across compartments** — key by `(compartment_id, element_id)`; validate resolution at materialisation.
6. **Direction ≠ magnitude/causation overreach** — caveats (1),(5),(6) + the "long-run intent; transient may differ" label on delayed-channel nodes; caveat text gets EG-domain-author review.

## 14. Out of scope / deferred

- Within-compartment edge surgery (`add_edge`/`remove_edge`/`retune_edge`).
- Numeric/magnitude-weighted or `delay`-driven dynamics.
- **Element-targeted cross-compartment propagation** (awaits the reserved `targeted_pressure_ids` channel field).
- A guided "restore ecosystem" wizard (the depolderisation factory is a fixed worked example).
- `MultiDiGraph` parallel-channel support.

## 15. Build order (for the plan)

1. **A** — `scenario.py` (data model + sidecar persistence + validation) → `propagation.py` (Sign lattice + multiply lift + within-compartment fixpoint + compartment-level crossing + joint fixpoint; equity/leverage/explain integrations) → `scenario_compare.py` primary direction diff. Acceptance: the full §12-A suite green, **including the ≥40%-determinate saturation-ceiling test on the Curonian seed**.
2. **B** — `materialise_scenario` (structural ops, per-compartment translation) → secondary metric diff (per-metric join contract) → `scenarios/depolderisation.py` (self-grounding factory) + Curonian end-to-end test.
3. **C** — `scenario_view.py` (editor sidebar + tinted canvas + direction/equity/metric DataGrids + disclaimers + a11y table) → `MultiSESState` extension → `app.py` nav wiring → e2e.

## 16. Changelog (rev 1 → rev 2, from the adversarial review)

- **Engine de-bottlenecked** (CRITICAL): two-level per-compartment fixpoint replaces the composite synthetic-hub graph that produced ~100% AMBIGUOUS.
- **Depolderisation grounded** (CRITICAL): factory builds its own polder substrate; canonical element types; concrete seed ids; buffering via competing seeds not sign-block; tidal channel = `organisms_marine_estuarine`.
- Sign algebra completed (`UNSET×`, `AMBIGUOUS×`, block operator); `max_hops` dropped; termination stated as `≤3|E|`.
- Equity computed directly (no `_downstream_outcome_ids`); `equity_direction` includes `ambiguous`.
- Compartment direction by tally; ambiguity explained via `feedback_loops()` not `cross_compartment_loops`.
- Canonical type strings throughout; `organisms` channel-type fixed.
- Added caveats (5) dose/threshold and (6) cross-compartment coarseness; "structural" defined; metric-diff join contract specified; order-independence + saturation-ceiling tests added; "engine owns no cache" wording.
