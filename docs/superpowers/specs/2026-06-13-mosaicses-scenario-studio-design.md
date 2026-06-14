# MosaicSES Scenario Studio — Design (Phase-2 priority D)

**Status:** Draft (rev 3 — **re-scoped to the structural core** after two adversarial review loops showed the qualitative sign-propagation engine was where all the risk concentrated). Pending user review.
**Scope (this phase):** Structural scenario authoring + materialisation + **metric diff** of the existing comparative analyses, in-app. Sub-projects A + B + C below.
**Deferred to a follow-on phase:** the qualitative **sign-propagation "predicted direction" overlay** (`seed_node` interventions + the seed-pinned propagation engine). The engine semantics are now validated in prototype (see §15) but need their own spec; they are out of scope here.
**Two-repo convention:** code lands in **MosaicSES**; this spec lives in **SESPy** `docs/superpowers/specs/`.
**Origin:** judge-panel design (`wf_07bc1035-0f2`) → 5-angle review (`wf_96b4600b-89a`, rev 2) → 5-angle review (`wf_1aff91f7-c93`, this re-scope). The reviews *ran candidate engines on the real Curonian seed*; the structural metric-diff half was consistently sound, so it is shipped first.

---

## 1. Motivation & decision to re-scope

Priority D (`2026-05-08-mosaicses-design.md` §11) is **scenario testing / "designing new ecosystems"** — *"if I restore this wetland / re-open this tidal channel / remove this barrier, how does the connected system change?"* — with **depolderisation** as the Emerald-Growth worked example (Tagliapietra).

Two review loops established that the **structural** answer — apply the intervention, rebuild the system, and compare the established network analyses before vs after — is well-defined, useful, and demonstrable on the real seed. The **qualitative direction-prediction** answer (sign-propagation) is scientifically attractive but fragile: every fatal review finding came from it (balancing feedback loops, which are central to SES, saturate a sign lattice to "ambiguous"). A validated fix exists (seed-pinning, §15), but it warrants its own spec.

**This phase therefore ships the structural core**; the direction-prediction overlay is a clean follow-on. The user still gets the headline capability — *materialise a redesigned ecosystem and see how leverage, centrality, governance-coverage, and tenet-readiness shift* — without the engine risk.

## 2. Architecture overview

Three layers, built in order. The baseline `MultiSES` is **never mutated**; persistence is a **sidecar** so the baseline JSON round-trips byte-identical and `MULTISES_SCHEMA_VERSION` stays 1.

| Layer | New module(s) | Responsibility |
|---|---|---|
| **A — library core** (headless) | `multises/scenario.py`, `multises/materialise.py`, `multises/scenario_compare.py` | data model + sidecar persistence; structural materialisation → derived `MultiSES`; the before/after metric diff |
| **B — worked example** (headless) | `multises/scenarios/depolderisation.py` | the self-grounding depolderisation factory on the Curonian seed + its end-to-end metric-delta test |
| **C — Scenario Studio app** (Shiny) | `multises_app/modules/scenario_view.py`; extends `state.py`, `app.py` | author interventions, materialise, and compare in-app |

Dependency rule: A has zero Shiny imports; B imports A; C imports A+B.

## 3. Data model (sub-project A)

`multises/scenario.py` — stdlib-only, JSON-round-trippable, mirroring `data_structure.py` (`Literal` aliases + `__post_init__` validation with stable `ScenarioError` codes; `LoadReport`-style soft-warning collection).

```python
@dataclass(frozen=True)
class Intervention:
    id: str                       # unique within a Scenario
    kind: InterventionKind        # Literal["add_node","remove_node",
                                  #         "add_channel","remove_channel","retune_channel"]
    label: str = ""
    compartment_id: str | None = None   # required for node ops; None for channel ops
    target: dict = field(default_factory=dict)   # kind-specific payload (§5)
    rationale: str = ""           # EG-monograph defensibility note
    # __post_init__: validate kind against the Literal set; require the target fields the kind
    # needs (element {id,label,type} for add_node; element_id for remove_node; channel fields for
    # channel ops); raise ScenarioError(code) on violation.

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

- **No `seed_node`, no `sign`, no propagation `magnitude`** this phase — every intervention is a structural edit `materialise_scenario` applies. (`add_channel`/`retune_channel` carry the channel's own `strength`/`polarity`/`channel_type`, which feed the structural metrics.)
- **Relationship to baseline.** A `Scenario` holds NO copy of compartments/channels — it references baseline ids by string. Referential integrity is collected as **soft `ScenarioReport` warnings at materialisation time** (mirrors `LoadReport`), not a hard raise — scenarios stay portable across baseline edits.
- **Element-id namespacing.** Element ids are unique only within a compartment, so node targets are keyed by `(compartment_id, element_id)`.
- **`pressure_origin` (display-only).** If a `rationale`/UI wants to flag endogenic vs exogenic on an added Pressure, that metadata lives only on the `Intervention` payload — **SESPy `Element` has no `pressure_origin` field** (it is `{id,label,type,description,confidence}`), so it is never round-tripped onto the materialised element. *(review T19)*
- **Persistence (sidecar).** `save_scenario_set`/`load_scenario_set` write `<basename>.scenarios.json`. **`persistence.save` is hard-typed to `MultiSES` (it calls `ms.to_dict()`); there is no generic atomic-write+SHA-256 helper to reuse** *(review T15)*. So sub-project A first **extracts** a generic `_atomic_write_bytes(path, body: bytes)` (+ a SHA-256 sidecar-verify) from `persistence.save` and has BOTH `MultiSES.save` and `save_scenario_set` call it — this is new code, not a thin wrapper.
- **Mutation helpers.** `_UNSET`-sentinel `add_intervention`/`replace_intervention`/`remove_intervention` pure helpers; a `remove`/`replace` keyed by intervention id.

## 4. Materialisation (sub-project A)

`multises/materialise.py` — `materialise_scenario(baseline, scenario) -> tuple[MultiSES, ScenarioReport]` produces a derived `MultiSES` by applying the interventions non-destructively, in a defined order: **all `remove_*` then `add_*` then `retune_*`**, structural-node ops before channel ops *(review T9 — deterministic ordering)*.

- **Node ops are per-compartment**: `add_node`/`remove_node` edit one `Compartment.project.isa_data` (reusing `sespy.network.remove_nodes` for ablation + incident-edge cleanup), then `replace_compartment` rebuilds the `MultiSES` (preserving overlays via `replace_compartment_overlays`). **The seam:** `remove_nodes`/`leverage_scores`/`centrality_metrics` take a single `IsaData`, not `MultiSES` — materialisation translates per-compartment then reassembles. *(review §13 risk 1, confirmed real.)*
- **Channel ops** go through `replace_channel` (add/remove/retune). `retune_channel` changes `polarity`/`strength`/`channel_type`.
- **Soft integrity:** a dangling target id (element/compartment/channel absent in the baseline) collects a `ScenarioReport` warning and that intervention is skipped — never a hard crash. A duplicate-target policy (two interventions touching the same element) is **reject-at-validation** with a `ScenarioError` code.

## 5. Intervention vocabulary (sub-projects A + B)

| Primitive | `target` payload | Effect |
|---|---|---|
| `add_node` | `{element: {id,label,type}}` | add a DAPSI element to `compartment_id`. Primary "designing new ecosystems" primitive (new wetland habitat / regulating service). |
| `remove_node` | `{element_id}` | ablate an element + incident connections (via `remove_nodes`). Primary depolderisation primitive (remove the polder/dyke barrier). |
| `add_channel` | `{source,target,channel_type,polarity,strength}` | open a new inter-compartment channel. |
| `remove_channel` | `{channel_id}` | close a channel. |
| `retune_channel` | `{channel_id, polarity?/strength?/channel_type?}` | change a channel's attributes. |

- **Channel-type strings validated** against the real vocabulary (`organisms_marine_estuarine`, `organisms_diadromous`, `water_discharge`, `nutrients`, `governance`, …) — there is no bare `organisms` type. *(review)*
- **Deferred (with the sign engine):** `seed_node` (the directional-push primitive) and within-compartment edge surgery.

## 6. Metric diff (sub-project A) — the output

`multises/scenario_compare.py` — `compare_scenario(baseline, scenario) -> dict[str, pd.DataFrame]` re-runs the five established comparative analyses on `baseline` and `materialise_scenario(baseline, scenario)` and emits a per-metric **before/after/delta** diff. **Per-metric join contracts** (the reviews verified the actual shapes):

| Metric | Source | Join key | Numeric (delta-able) cols | Descriptive (carry-through) |
|---|---|---|---|---|
| `compartment_summary` | `comparative` (DataFrame) | `compartment_id` | `element_count, connection_count, mean_leverage, dominant_pressure_count` | `label, archetype, is_focal_tw, top_leverage_label` |
| `leverage_hotspots` | `comparative` (DataFrame) | `(compartment_id, element_id)` | `leverage, global_rank_zscore` | `element_label, element_type` |
| `response_pressure_gap` | `comparative` (DataFrame, full-column even when empty) | `(compartment_id, pressure_id)` | the count cols + `downstream_equity_outcome_count` | `pressure_label, affected_equity_dimensions, is_equity_relevant_orphan` |
| `tenet_gap_analysis` | `comparative` (DataFrame) | **`(subject_kind, source_compartment_id, target_compartment_id, subject_id)`** *(review T7 — `subject_id` alone collides Responses across compartments; the frame's own sort key already includes the compartment)* | `scored_count, gap_count, mean_score, min_score` + per-tenet score cols | `subject_label, weakest_tenet` |
| `inter_compartment_metrics` | `composite` — **returns a `dict[compartment_id, dict]`, NOT a DataFrame** *(review T6)* | normalise dict→frame (`index=compartment_id`) first | `channel_in_degree, channel_out_degree, betweenness` | `incoming_channel_types, outgoing_channel_types` (list[str] — **set-diff, not numeric delta**) |

Each diff is an **outer join** on its key; added rows render `before=NaN`, removed rows `after=NaN`; `delta = after − before` for numeric cols, set-diff (`{col}_added`/`{col}_removed`) for list cols (computed with an isinstance-list guard, **never `pd.notna`** — that raises on a list cell, plan-review F1), and descriptive cols carried through as `{col}_before`/`{col}_after`. The result is the literal `{before, after, delta}` shape `sespy.network.intervention_impact` already uses — but computed at the `MultiSES` level across all five metrics.

## 7. Depolderisation worked example (sub-project B)

`multises/scenarios/depolderisation.py` — `build_depolderisation_scenario(ms)` is a **structural factory** grounded in the *actual* Curonian seed. The seed encodes **no polder**, so an add-then-remove of a barrier nets to zero structural change (plan-review F2); depolderisation here is the **additive "designing a new ecosystem" restoration**:
1. `add_node` a restored intertidal-wetland habitat (`type="Marine Processes & Functioning"`), a regulating nutrient-buffering service (`type="Ecosystem Services"`), and its outcome (`type="Goods & Benefits"`) — **canonical type strings**;
2. `add_channel` a restored tidal exchange **`curonian_lagoon → klaipeda_strait`** (its true adjacent estuary — **the lagoon does NOT border `baltic_se`**) as `organisms_marine_estuarine` (a `channel_type` not already present on that pair).

**Honest limitation (plan-review):** because within-compartment edge surgery is deferred, the added wetland nodes are **isolated** (no authored connections). So the substantive metric deltas (verified by running `compare_scenario` on the seed, **pinned to the exact created ids** — no aspirational claims) are modest: lagoon `element_count` **+3**, while `compartment_summary.mean_leverage` is **materially unchanged** (the isolated nodes carry ~zero leverage — `mean_leverage_delta ≈ 2e-16`, floating-point noise — and do NOT appear in `leverage_hotspots`' top-N); and the tidal channel registers ONLY in `inter_compartment_metrics`' **`outgoing_channel_types` set-diff** (new `organisms_marine_estuarine` on the lagoon→strait edge) — NOT in `channel_out_degree`/`betweenness` (both delta 0), since that pair is already connected and the composite `nx.DiGraph` collapses the parallel edge. A richer, wired depolderisation awaits the edge-surgery phase.

**Caveats (rendered in the UI):** (1) this is a **structural network analysis, not a process/biogeochemical model** — it shows how the *connectivity and graph metrics* change, not predicted ecological dynamics, magnitudes, or timescales; (2) "designing new ecosystems" ≠ restored-to-reference; (3) endogenic breach / exogenic dependency (driven by the `Intervention` metadata, not the materialised element — *review T19*). Caveat text gets EG-domain-author (Tagliapietra) review.

## 8. Scenario Studio app module (sub-project C)

`multises_app/modules/scenario_view.py`, mirroring `cross_view.py`:
- **Intervention-editor sidebar** — plain inputs: `input_select(kind)`, `input_text(compartment_id)`, `input_select(element_type)` (the canonical DAPSI types), `input_text(target)`, `input_text(rationale)`, an Add button + the current intervention list. (`overlay_edit.py` is Shiny-free helpers — `set_overlay_entry`, `friendly_error` — not UI grammar.)
- **Before/after comparison** — the five metric-diff `render.DataGrid`s, each with a "changed rows only" filter.
- The `sticky-disclaimer` stating the structural-analysis-not-prediction contract.
- **Deferred to a follow-on refinement:** the **sidecar load/save UI + its baseline-drift banner** (count resolved vs dangling interventions on load — *review T22*), and the side-by-side baseline/materialised composite-graph view + `digraph_table_ui` a11y fallback. v1 authors a scenario in-session; the accessible `render.DataGrid` diffs are the v1 output, and the `drift_banner` output exists as an inert placeholder.
- **State:** extend `MultiSESState` with `active_scenario: reactive.Value[Scenario|None]` + `scenario_set: reactive.Value[ScenarioSet]` (baseline untouched); reuse `event_bus` + the `dirty` wiring. New nav panel in `app.py`.

## 9. Decisions

| # | Decision | Rationale |
|---|---|---|
| Scope | **structural core only**; sign-propagation overlay deferred | all fatal review findings came from the sign engine; structural half is sound |
| Persistence | **sidecar**, schema stays v1; extract a generic atomic-write+SHA-256 helper | baseline round-trips byte-identical; `persistence.save` is `MultiSES`-typed |
| Output | **before/after/delta** of the 5 existing comparative metrics on the materialised system | well-defined, reuses shipped analyses, no saturation/ambiguity |
| Application order | remove → add → retune, nodes before channels | deterministic materialisation |
| Duplicate target | reject at validation (`ScenarioError`) | avoid undefined double-edits |
| Depolderisation | additive restoration (added nodes isolated — edge surgery deferred); tidal channel to **`klaipeda_strait`** | the seed has no polder/barrier to remove; the lagoon's marine neighbour is the strait, not the coastal sea |
| Edge surgery / `seed_node` | **deferred** | YAGNI / belongs to the propagation phase |

## 10. Error handling

- **Scenario validation** fail-fast at construction (`ScenarioError` codes), like `_ChannelValidationError`.
- **Referential integrity** soft at materialisation (dangling target → `ScenarioReport` warning, intervention skipped).
- **App layer** routes save/load/materialise failures through `friendly_error` into sanitized toasts; an empty/all-dangling scenario renders a clear "no effective interventions" state (the empty-state discipline from UI-hardening).

## 11. Testing strategy

- **A (`tests/test_scenario.py`, `test_materialise.py`, `test_scenario_compare.py`):** `Scenario` `to_dict`/`from_dict` round-trip + soft-warning on dangling refs + duplicate-target rejection; the extracted `_atomic_write_bytes` + SHA-256 verify; `materialise_scenario` for each kind (add/remove node, add/remove/retune channel) incl. the per-compartment `IsaData` translation and overlay preservation; the **metric-diff join contracts** — added/removed rows render NaN, `inter_compartment_metrics` dict→frame normalisation + list-column set-diff, the tenet compound key — on the real seed.
- **B:** `build_depolderisation_scenario(ms)` end-to-end — materialises without error (no dangling warnings), the wetland nodes are added (isolated — edge surgery deferred), the tidal channel lands on `klaipeda_strait`, and the **metric deltas match the pinned expected values** for the concrete created ids (no aspirational claims).
- **C:** pure-helper UI assertions via `str(...tagify())` (sidebar grammar, the five namespaced diff outputs, disclaimer); Playwright e2e (author an `add_node` → materialise → diff tables populate), using the `mosaicses_app_url` fixture (180 s startup) from UI-hardening.

## 12. Risks & mitigations

1. **IsaData↔MultiSES seam** — `remove_nodes`/`leverage_scores`/`centrality_metrics` take `IsaData`, not `MultiSES`. Materialisation translates per-compartment; cross-compartment via `replace_channel`. *Most likely overrun.*
2. **Parallel-channel collapse** — `nx.DiGraph` overwrites parallel synthetic→synthetic edges; an `add_channel` of an already-present type between a pair is shadowed in `inter_compartment_metrics`/composite views. *Mitigation:* the factory uses a type not present on the pair; the materialiser warns on collision; no `MultiDiGraph`.
3. **Degenerate metrics on sparse compartments** — `leverage_hotspots` z-scores / centrality over a compartment whose only connected component is a small loop with many isolated elements are near-degenerate; the diff carries them through honestly and the disclaimer notes structural sparsity.
4. **`persistence.save` refactor** — extracting the generic writer touches a shipped, SHA-256-verified path; cover both `MultiSES.save` and the sidecar with round-trip + integrity tests so the refactor is safe.

## 13. Out of scope / deferred

- **The qualitative sign-propagation "predicted direction" overlay** (`seed_node` + the seed-pinned engine) — its own follow-on phase (engine validated in §15).
- Within-compartment edge surgery; numeric/`delay`-driven dynamics; element-targeted cross-compartment effects; a guided "restore ecosystem" wizard; `MultiDiGraph`.

## 14. Build order (for the plan)

1. **A** — extract `_atomic_write_bytes` from `persistence.py`; `scenario.py` (data model + sidecar persistence + validation) → `materialise.py` (per-compartment structural ops + soft integrity) → `scenario_compare.py` (5 metric diffs with the §6 join contracts). Acceptance: the §11-A suite green on the real seed.
2. **B** — `scenarios/depolderisation.py` (self-grounding factory: additive isolated wetland nodes + `klaipeda_strait` tidal channel) + the pinned metric-delta end-to-end test.
3. **C** — `scenario_view.py` (editor sidebar + the five diff DataGrids + disclaimer) → `MultiSESState` extension → `app.py` nav wiring → e2e. (Sidecar load/save UI + drift banner + composite-graph view are a follow-on.)

## 15. Appendix — the deferred sign-propagation engine (validated, for the follow-on)

For the record, so the follow-on phase starts from solid ground: a qualitative direction-prediction overlay is viable with **seed-pinned** propagation. The pure JOIN-to-fixpoint design (rev 1/2) saturates balancing loops to AMBIGUOUS (the Curonian lagoon's authored DAPSI is a single balancing loop, so the headline scenario gave **0/6 determinate**). Prototyped on the real seed, **pinning the seed against its own loop feedback** (propagate the imposed sign forward; don't let the loop overwrite the seed; report the loop's pushback as an annotation) gives **6/6 determinate** (`P001↓ → P003↓, MPF003↑, GB001↑ (fishery improves), ES003↓, R001↓`). The follow-on spec must also resolve the cross-compartment crossing for an ambiguous source (inject UNSET, not AMBIGUOUS), parallel-channel polarity conflicts, the injection-target element, and the unreached/`UNSET`→`unchanged` output mapping (review T3/T4/T12/T14/T17). Not built this phase.
