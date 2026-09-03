# SES hypermodule detection — design

**Issue:** [#24](https://github.com/razinkele/SESPy/issues/24) (Pinheiro,
Peralta & Lewinsohn 2026, *The hypermodular structure of tripartite ecological
networks*, Proc. Roy. Soc. B 293:2077, doi:10.1098/rspb.2026.1348).

**Status:** design approved in conversation 2026-09-04; revised the same day
after an adversarial review (10 agents, 4 confirmed majors) whose probes
executed the algorithm on real data. Implementation plan not yet written.

---

## What this is

SES networks in SESPy are multipartite: DAPSI(W)R(M) typing yields an
ecological tier, a social tier and a governance tier. The shipped cross-tier
metrics measure coupling *density* (`social_ecological_fit`) and structural
*gaps* (`governance_gap`); neither asks which nodes across the tiers form a
cohesive multi-tier subsystem. A hypermodule is such a group: nodes from all
tiers that community detection puts together across the bipartite
projections — the SES analogue of Pinheiro et al.'s
plant–herbivore–parasitoid hypermodules.

## Decisions (made by the owner, 2026-09-04)

| # | Decision | Rationale |
|---|---|---|
| 1 | Tier map extends the shipped precedents, not the issue's shorthand | The issue's S/I/P–D/A–R/M scheme names types SESPy does not have and contradicts `_SUBSYSTEM` on Responses. Chosen map: **governance = Responses + Measures** (exactly the layer `governance_gap` already defines); **ecological = Pressures, Marine Processes & Functioning, Ecosystem Services**; **social = Drivers, Activities, Goods & Benefits** (both per `_SUBSYSTEM`). `_SUBSYSTEM` itself is untouched. |
| 2 | `greedy_modularity_communities`, not Louvain | Deterministic by construction — no RNG, no seed, same modules every run and process. This codebase has twice paid for nondeterminism (`_canonical_cycles` ordering; ALC's sign above the loop cap). Louvain's usually-better modularity is marginal on 20–60-node SES models and costs a reproducibility asterisk. Ships with networkx 3.6; no new dependency. |
| 3 | UI follows the #13–#16 pattern | A button-gated "SES Subsystem Modules" block on the Network Metrics card. |

## The tier constant

```python
#: Three-tier partition for hypermodule detection. Governance matches
#: governance_gap()'s layer exactly; the split of the remaining types is
#: _SUBSYSTEM's. _SUBSYSTEM itself is NOT changed — it answers a different,
#: two-tier question and other shipped metrics depend on it.
_TIER: dict[str, str] = {
    "Pressures": "ecological",
    "Marine Processes & Functioning": "ecological",
    "Ecosystem Services": "ecological",
    "Drivers": "social",
    "Activities": "social",
    "Goods & Benefits": "social",
    "Responses": "governance",
    "Measures": "governance",
}
```

Unknown types get `""` and are excluded from the analysis (reported in the
result's `n_untyped`, never silently dropped).

Note `Measures` is genuinely mapped here — unlike `leverage_realm`, where it
is an accepted gap — because `governance_gap` already treats it as
governance. The two functions answer different questions; the divergence is
deliberate and documented in both docstrings.

## The library function

`hypermodules(isa: IsaData) -> dict` in `sespy/network.py`. Pure,
translation-free, deterministic.

### Departures from issue #24, all named

- **Name:** `hypermodules(isa)`, not `hypermodule_detection(g)` — matching
  `network.py`'s isa-taking convention.
- **Return:** a dict of plain rows, not a DataFrame — the repo's library
  layer returns dicts; modules build frames.
- **Columns:** the issue's `within_tier_module_count` and
  `cross_tier_module_count` are dropped in favour of a single `n_congruent`
  (defined below) — under the hinge reconstruction the two counts have no
  independent meaning, since every projection module is cross-tier by
  construction.
- **Score denominator:** fraction of **tier-assigned** nodes, not of all
  nodes; untyped nodes are excluded and reported via `n_untyped` rather than
  silently deflating the score.
- **Congruence:** reconstructed (below); the issue's literal "same module in
  ≥2 of 3 projections" is vacuous on pairs.

### 1. Bipartite projections

For each tier pair — (ecological, social), (ecological, governance),
(social, governance) — take the subgraph containing exactly the connections
whose endpoints span that pair, as an **undirected** `nx.Graph`.

- Undirected because modularity is defined on undirected graphs and cohesion
  is about association, not causal direction. Edge direction is deliberately
  discarded here; `governance_gap` remains the directed view.
- Parallel edges (duplicate source→target, or A→B plus B→A) collapse to one
  undirected edge. Weightless: community detection sees topology only.
  Strength-weighted modularity is out of scope until someone needs it.
- A projection with no edges yields no modules and simply contributes
  nothing.

### 2. Module detection per projection

`nx.community.greedy_modularity_communities(g)` on each non-empty
projection. A projection with fewer than 2 nodes or no edges is skipped.

**Determinism note for the implementer:** CNM in networkx is deterministic
for a fixed graph, but the *graph construction* must also be order-stable —
build node and edge lists in sorted order before calling it, so hash-seed
variation in set iteration cannot reach the algorithm.

### 3. Congruence — a documented, MEASURED reconstruction

The issue says "same module in at least two of the three projections
(majority vote)". Taken literally on pairs that is **vacuous**: a cross-tier
pair (one ecological, one social node) co-occurs in exactly ONE projection —
the social node never appears in ecological–governance at all. The first
draft of this spec made that mistake.

What makes multi-tier cohesion detectable is the **hinge tier** — the tier
two projections share. Ecological nodes appear in BOTH eco–social and
eco–governance; if a group of them is co-clustered in both, the social
module and the governance module they anchor belong together.

The hinge *threshold* was then chosen by measurement, not taste. A flat
"share ≥ 2 hinge nodes" rule returns **zero hypermodules on the shipped
sample and structurally cannot fire on chain-shaped DAPSI(W)R(M) models**
(one activity → one pressure wiring makes every eco–social module a size-2
pair, so two shared hinge nodes are unreachable) — the review's probes
proved this, and it is the `mean_leverage` failure shape: a metric that is
always zero. The adopted rule adapts to module size:

> Modules **A** (from projection P1) and **B** (from P2 ≠ P1) are linked in
> the *module graph* when they share at least
> `min(2, hinge_capacity)` hinge-tier nodes, where `hinge_capacity` is the
> smaller of the two modules' hinge-tier node counts.
>
> In words: two shared hinge nodes normally; one suffices exactly when
> either module only *has* one hinge-tier node, so tiny chain modules are
> not structurally excluded.

Measured on `data/sample_ses.json`: **2 hypermodules, both spanning all
three tiers, score 9/17 ≈ 0.53** —
`{A001, ES01, ES03, GB01, P001, R002}` and `{A002, P002, R001}` — two
governance-coupled subsystems, not zero and not one undifferentiated blob.
The flat ≥2 rule gives 0/17 on the same data.

**Multi-membership resolution.** Components of the module graph are
components of *modules*, and a node's modules from different projections
need not land in the same component — the review constructed an 11-node
model where one node's memberships straddle two components. The rule:

> After components are formed, hypermodules that share **any** member node
> are merged, iterated to a fixed point. Membership is therefore a
> partition: every node has exactly one `hypermodule_id` or none.

This coarsens rather than splits — defensible because a node genuinely
bridging two candidate subsystems connects them into one — and it is what
makes the one-row-per-node return shape valid and deterministic.

**A hypermodule** is a merged component containing **at least two modules**.
(That is the operative filter. A single bipartite module spans two tiers by
itself, so a "spans ≥ 2 tiers" test would be vacuous — the review caught the
first draft using exactly that dead check. Any component with ≥ 2 modules
from different projections spans all three tiers automatically.)

**Everything above is a reconstruction.** The paper's actual HyperMod
procedure was not verifiable from here (same caveat class as #22's ALC and
#23's depth scheme). The threshold rule and the merge rule live as
module-level code with comments saying exactly this — check against the
paper when it is reachable.

**`n_congruent`, operationally:** for a node in a hypermodule, the number of
*other* nodes of that hypermodule that share at least one projection module
with it; `0` (and `hypermodule_id = None`) for nodes in no hypermodule.

### 4. Stable IDs and return shape

```python
{
    "rows": [  # one per tier-assigned node
        {"node": str, "tier": str, "hypermodule_id": int | None,
         "n_congruent": int},
        ...
    ],
    "hypermodularity": float,   # fraction of tier-assigned nodes with a
                                # non-None hypermodule_id
    "n_hypermodules": int,
    "n_untyped": int,           # elements whose type has no tier
    "note": str,                # see the taxonomy below
}
```

- Hypermodule IDs: sort each hypermodule's member list, sort the list of
  hypermodules by their sorted members, enumerate — no iteration-order
  leakage anywhere.
- Row order: assigned rows first, sorted by `(hypermodule_id, node)`;
  unassigned rows after them, sorted by `node`. (Stated because a naive
  tuple sort of `int | None` raises `TypeError` — key on
  `(id is None, id if id is not None else -1, node)`.)
- `hypermodularity` is `0.0` whenever the count of tier-assigned nodes is
  zero — empty ISA or an ISA of wholly unknown types alike; no 0/0.

### Degenerate-note taxonomy, with precedence

Keyed on **projections**, not tier node-presence — the review showed the
first draft's taxonomy left the most realistic degenerate case (all tiers
populated, governance unwired) with an unexplained empty result.

Exactly one note applies; first match wins:

| Order | `note` | Condition | Result shape |
|---|---|---|---|
| 1 | `no_coupling` | no projection has any edge | 0 hypermodules |
| 2 | `single_projection` | exactly one projection has edges (covers a missing tier AND a present-but-unwired tier) | 0 hypermodules — congruence needs modules from two projections |
| 3 | `no_congruence` | ≥ 2 projections have edges but no modules link | 0 hypermodules; the UI explains rather than showing a bare zero |
| 4 | `""` | ≥ 1 hypermodule found | normal rendering |

Empty ISA → empty rows, score 0.0, `note="no_coupling"`.

## The UI

A button-gated **"SES Subsystem Modules"** block on the Network Metrics
card, cloned from the cascade block — the full shape at
`sespy/modules/analysis_metrics.py:324-386` (the first draft cited only the
server half): the `ui.output_ui(...)` + `hr` slot in
`analysis_metrics_ui()`, then server-side `reactive.value(None)` result,
reset by the existing `isa_change` effect pattern, computed on
`input.run_hypermodules`, hint text until run.

Rendered result: one line per hypermodule — id, size, tier composition
("3 ecological · 2 social · 1 governance"), member labels (via the module's
existing element-label lookup) — plus the hypermodularity score, and the
translated note when degenerate. No graph visualisation; the pyvis canvas
is not touched.

i18n: **eight** new keys — `metrics.hypermodules`,
`metrics.hypermodules_run`, `metrics.hypermodules_hint`,
`metrics.hypermodules_score`, `metrics.hypermodules_no_coupling`,
`metrics.hypermodules_single_projection`,
`metrics.hypermodules_no_congruence`, `metrics.hypermodules_caption` —
× 9 languages, following `metrics.cascade_*`'s conventions. None collide
with existing keys.

## Testing

1. **A planted-hypermodule fixture.** Two deliberately separate clusters,
   each with ≥ 2 ecological hinge nodes plus social and governance nodes
   densely wired within the cluster, one weak inter-cluster link. Assert
   exactly two hypermodules, each spanning three tiers, with the expected
   membership. Must fail against the vacuous pairwise rule (which returns
   zero always) — the guard against reintroducing that reading.
2. **A chain-shaped fixture fires.** The minimal chain
   (A1→P1, A2→P2, R1→P1, R1→P2) must yield ≥ 1 hypermodule — this is the
   fixture that fails under the flat ≥2 threshold and pins the size-aware
   rule.
3. **The multi-membership merge.** The review's 11-node bridging fixture
   (one node whose projection modules straddle two components): assert the
   result is a partition — every node exactly one id — and that the two
   candidate hypermodules merged into one through the bridge node.
4. **Single-module components are excluded:** a model whose only structure
   is one bipartite module yields `n_hypermodules == 0` and
   `note="single_projection"` or `"no_congruence"` as appropriate.
5. **Determinism:** two calls on the sample return identical rows; build
   the same ISA with elements/connections lists reversed and assert
   identical output.
6. **Degenerates:** each note value reachable and correct — no edges,
   one wired projection (both the missing-tier and the unwired-tier
   routes), two projections with no congruence; empty ISA; all-unknown
   types (`n_untyped`, score 0.0).
7. **Sample-project golden:** on `data/sample_ses.json` assert
   `n_hypermodules == 2`, `hypermodularity == 9/17` (±rounding), and the
   two member sets measured above — with a comment on how to re-derive if
   the tier map or rule legitimately changes.
8. **Module:** the block renders, follows the run-button pattern, and the
   i18n keys resolve through `load_translations` (the production path).

Gate: unit baseline **576**; full e2e **32/32** (the Network Metrics card
changes shape); MosaicSES **526**.

## Out of scope

- Strength-weighted modularity (topology-only until someone needs weights).
- Louvain or an `algorithm=` parameter (Decision 2; YAGNI).
- Changing `_SUBSYSTEM`, `subsystem()`, `social_ecological_fit` or
  `governance_gap`.
- Graph visualisation of hypermodules on the pyvis canvas.
- MosaicSES surfacing (a per-compartment aggregation is a separate issue).
- Verifying the reconstruction against the paper (unreachable; documented
  assumption instead).
- Enriching `data/sample_ses.json` — under the adopted rule the shipped
  sample already demonstrates the feature, so the review's alternative
  remedy is unnecessary.
