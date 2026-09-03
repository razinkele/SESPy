# SES hypermodule detection — design

**Issue:** [#24](https://github.com/razinkele/SESPy/issues/24) (Pinheiro,
Peralta & Lewinsohn 2026, *The hypermodular structure of tripartite ecological
networks*, Proc. Roy. Soc. B 293:2077, doi:10.1098/rspb.2026.1348).

**Status:** design approved in conversation 2026-09-04. Implementation plan
not yet written.

---

## What this is

SES networks in SESPy are multipartite: DAPSI(W)R(M) typing yields an
ecological tier, a social tier and a governance tier. The shipped cross-tier
metrics measure coupling *density* (`social_ecological_fit`) and structural
*gaps* (`governance_gap`); neither asks which nodes across the tiers form a
cohesive multi-tier subsystem. A hypermodule is such a group: nodes from at
least two tiers that community detection puts together in more than one
bipartite projection — the SES analogue of Pinheiro et al.'s
plant–herbivore–parasitoid hypermodules.

## Decisions (made by the owner, 2026-09-04)

| # | Decision | Rationale |
|---|---|---|
| 1 | Tier map extends the shipped precedents, not the issue's shorthand | The issue's S/I/P–D/A–R/M scheme names types SESPy does not have and contradicts `_SUBSYSTEM` on Responses. Chosen map: **governance = Responses + Measures** (exactly the layer `governance_gap` already defines); **ecological = Pressures, Marine Processes & Functioning, Ecosystem Services**; **social = Drivers, Activities, Goods & Benefits** (both per `_SUBSYSTEM`). `_SUBSYSTEM` itself is untouched. |
| 2 | `greedy_modularity_communities`, not Louvain | Deterministic by construction — no RNG, no seed, same modules every run and process. This codebase has twice paid for nondeterminism (`_canonical_cycles` ordering; ALC's sign above the loop cap). Louvain's usually-better modularity is marginal on 20–60-node SES models and costs a reproducibility asterisk. Ships with networkx 3.6; no new dependency. |
| 3 | UI follows the #13–#16 pattern | A button-gated "SES Subsystem Modules" block on the Network Metrics card: `reactive.value(None)` result, reset on `isa_change`, computed on `input.run_hypermodules`, hint text until run. |

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
projection. Wrapped in the repo's standard degenerate guards: a projection
with fewer than 2 nodes or no edges is skipped.

**Determinism note for the implementer:** CNM in networkx is
deterministic for a fixed graph, but the *graph construction* must also be
order-stable — build node and edge lists in sorted order before calling it,
so hash-seed variation in set iteration cannot reach the algorithm.

### 3. Congruence — a documented reconstruction, via hinge tiers

The issue says "same module in at least two of the three projections
(majority vote)". Taken literally on pairs that is **vacuous**: a cross-tier
pair (say one ecological, one social node) co-occurs in exactly ONE
projection — the ecological–social one; the social node never appears in
ecological–governance at all. A first draft of this spec made that mistake
and would have returned zero hypermodules on every input.

What makes multi-tier cohesion detectable is the **hinge tier** — the tier
two projections share. Ecological nodes appear in BOTH eco–social and
eco–governance; if a group of them is co-clustered in both, the social
module and the governance module they anchor belong together. That is
Pinheiro et al.'s "module congruence across interlinked bipartite
sub-networks" as their abstract describes it.

Operational rule:

1. Vertices of a *module graph*: every (projection, module) pair from step 2.
2. Two modules from **different** projections are linked when they share at
   least **two** hinge-tier nodes (`MIN_HINGE = 2`; one shared node is a
   coincidence, two is co-clustering).
3. A **hypermodule** is the union of the member nodes of a connected
   component of the module graph, kept only if it spans **at least two
   tiers**. Components containing a single module are ordinary within-
   projection modularity, not hypermodules.

**This is a reconstruction.** The paper's actual HyperMod procedure was not
verifiable from here (same caveat class as #22's ALC and #23's depth
scheme). `MIN_HINGE = 2` is a module-level constant with a comment saying
exactly this — check both the rule and the threshold against the paper when
it is reachable.

A node's `n_congruent` in the output counts the hinge partners it shares a
merged component with — 0 for nodes in no hypermodule.

### 4. Stable IDs and return shape

```python
{
    "rows": [  # one per tier-assigned node, sorted by (hypermodule_id, node)
        {"node": str, "tier": str, "hypermodule_id": int | None,
         "n_congruent": int},   # congruent partners; 0 -> hypermodule_id None
        ...
    ],
    "hypermodularity": float,   # fraction of tier-assigned nodes in a
                                # hypermodule (component with >= 2 tiers)
    "n_hypermodules": int,
    "n_untyped": int,           # elements whose type has no tier
    "note": str,                # "" | "missing_tier" | "no_coupling"
}
```

- Hypermodule IDs are assigned by sorting each component's member list and
  enumerating the sorted list of components — no iteration-order leakage.
- `note="missing_tier"` when a tier has no nodes: the analysis degrades to
  the one available projection, and congruence (which needs two) cannot
  fire, so `n_hypermodules == 0`. The UI explains rather than showing an
  empty table.
- `note="no_coupling"` when no projection has an edge.
- Empty ISA → empty rows, score 0.0, no error.

## The UI

A button-gated **"SES Subsystem Modules"** block on the Network Metrics
card, cloned from the cascade block's shape
(`sespy/modules/analysis_metrics.py:324-349`): `reactive.value(None)`
result, reset by the existing `isa_change` effect pattern, computed on
`input.run_hypermodules`, hint text until run.

Rendered result: one line per hypermodule — id, size, tier composition
("3 ecological · 2 social · 1 governance"), member labels — plus the
hypermodularity score, and the translated note when degenerate. No graph
visualisation; the existing pyvis canvas is not touched.

i18n: approximately six new keys (`metrics.hypermodules`,
`metrics.hypermodules_run`, `metrics.hypermodules_hint`,
`metrics.hypermodules_score`, `metrics.hypermodules_missing_tier`,
`metrics.hypermodules_no_coupling`) × 9 languages, following
`metrics.cascade_*`'s exact conventions.

## Testing

1. **A planted-hypermodule fixture.** Build an ISA with two deliberately
   separate clusters, each containing >= 2 ecological hinge nodes plus social
   and governance nodes densely wired within the cluster (so the eco-social
   and eco-governance modules share two hinge nodes and merge), and a single
   weak link between clusters. Assert exactly two hypermodules, each spanning
   three tiers, with the expected membership. This is the test that fails if
   the hinge rule, the tier map, or the component step is wrong.
   **It must also fail against the first draft's vacuous pairwise rule** —
   which returns zero hypermodules always — so it doubles as the guard
   against reintroducing that reading.
2. **Determinism:** two calls on the sample project return identical rows;
   additionally, construction-order independence — build the same ISA with
   elements/connections lists in reversed order and assert identical output.
3. **Degenerate cases:** missing tier (`note`, zero hypermodules), no
   cross-tier edges, empty ISA, unknown types counted in `n_untyped`.
4. **Single-tier components are excluded:** a fixture whose congruent pairs
   are all within one tier yields `n_hypermodules == 0`.
5. **Sample-project golden:** pin `n_hypermodules` and the score on
   `data/sample_ses.json` — with a comment that a *legitimate* change to the
   tier map or congruence rule may move it, and how to re-derive.
6. **Module:** the block renders, follows the run-button pattern, and the
   i18n keys resolve through `load_translations` (the production path — the
   lesson from #23's plan review).

Gate: unit baseline **576**; full e2e **32/32** (the Network Metrics card
changes shape); MosaicSES **526** (it does not import `hypermodules`, but
the gate is cheap insurance).

## Out of scope

- Strength-weighted modularity (topology-only until someone needs weights).
- Louvain or an `algorithm=` parameter (Decision 2; YAGNI).
- Changing `_SUBSYSTEM`, `subsystem()`, `social_ecological_fit` or
  `governance_gap`.
- Graph visualisation of hypermodules on the pyvis canvas.
- MosaicSES surfacing (its comparative panel could aggregate hypermodules
  per compartment later; separate issue if wanted).
- Verifying the reconstruction against the paper (unreachable; documented
  assumption instead).
