# Boolean attractor search beyond 20 nodes — investigation

Date: 2026-11-21. Companion to `2026-11-21-boolean-scale-design.md` (options 1 and 2). This note
looks at ways to go further, with measurements.

The probe scripts that produced every number here are in `boolean-scale-probes/`, next to this note.

## Decision (user, 2026-11-21): no R parity for this analysis
SESPy keeps its weighted-threshold rules. The difference from R below is recorded as an intentional, scoped divergence, not a defect.

## What the analysis returns on shipped networks (`probe5.py`, attractor set via core search)
- **57 networks:** 52 have a single attractor. Under these rules state 0 is always fixed, so that attractor is **all-off**.
- **4 have two or more:** `minimal_demo` (12), `offshore_wind` (14), Venice `drainage_basin` (4), Venice `lagoon_central` (34 nodes, core 17: 4).
- **Caribbean** (core 64) can only be sampled.
- **Speed:** every attractor-set search took ≤ 0.4 s.
- **Basin-split check:** reduced and full results are identical, basins included, on both multi-attractor networks within 20 nodes (`minimal_demo`, `offshore_wind`). This closes the basin-split gap for those shapes.

**Opt-in variant, measured (`probe6.py`): input-less "driver" nodes hold their starting value.** Every driver setting gave exactly **one** attractor:

| Network | Drivers | Settings | Settings where the core activates |
|---|---|---|---|
| Fisheries | 5 | 32 | 0 |
| Tourism | 6 | 64 | 0 |
| Pollution | 8 | 256 | 176 |
| OffshoreWind | 6 | 64 | 32 |
| Aquaculture | 9 | 512 | 0 |

So the variant behaves as a deterministic **driver scenario → response** map, and a user-chosen scenario is a single cheap run.

## Finding 0: SESPy's Boolean rules are not R's (intentional, see Decision)

The 2026-04-27 spec calls `create_boolean_rules` a port of R `ses_create_boolean_rules`
(`ses_dynamics.R:455`), but the two differ in semantics, and no document records the difference:

| | R / BoolNet (the reference) | SESPy |
|---|---|---|
| Combining inputs | OR over regulators; an inhibitor contributes `!x` (`A \| B \| !C`) | weighted sum `Σ w·x` and `> 0` |
| Magnitude | ignored (`sign(mat)`) | used |
| No regulators | self-rule `X = X` (keeps its starting value) | inflow 0, so it switches off |
| All-off state | not generally a fixed point (an inhibitor that is off turns its target on) | always a fixed point |

Measured on the Fisheries template (26 nodes), `probe4.py`:
- **SESPy rules:** exactly **1** attractor, all-off, with basin 2^26.
- **R rules:** **36** distinct attractors reached from 20,000 sampled starts, all fixed points. Its 5 sources keep their values, so they act as parameters.

The same network gives qualitatively different answers. Every core-0 (acyclic) network below gives a single all-off attractor under SESPy rules. Recorded for transparency; the user ruled that no parity is expected here.

## Key finding: exact feedback-core reduction (under SESPy's current rules)

Synchronous threshold rules (`inflow > 0`) give every node with no cycle upstream a constant value after
at most |upstream| steps. A node with no inputs has inflow 0, so it switches off; constants then propagate down
the acyclic part. Nodes below all cycles ("read-outs") are deterministic outputs of the core.

So the attractors of the full network are determined by the **feedback core**: nodes that both lie
downstream of a cycle and upstream of one. The full attractors follow by reconstruction.

### Algorithm (as probed)
1. **Partition.** Split the nodes into upstream (not downstream of any cycle), core (downstream ∩ upstream of a cycle) and read-out (downstream only).
2. **Constant propagation.** Step the full-width kernel |U| + 1 times; U settles to a fixed pattern u*, which the probe asserts. This uses the general rule, not a hard-coded 0.
3. **Core map.** Enumerate 2^|C| core states as full-width states (U = u*, R = 0), apply the **shared kernel**, read back the core bits, then label cycles (pointer doubling with orbit minimum).
4. **Reconstruction.** From each core attractor, step the full network until the state repeats. That gives the full attractor, read-outs included.
5. **Exact basins.**
   - Read-outs multiply basins by exactly 2^|R|.
   - Upstream initial values perturb the core during the transient, so they are **not** a simple factor. The probe enumerates every upstream pattern × every core state, steps |U| + 1 times and looks up the core label. The cost is 2^|U| × 2^|C|.
   - A refinement: enumerate only distinct *input sequences into the core* (simulate U alone and deduplicate by the feeders' values over the transient). Its cost is (distinct sequences) × 2^|C|.

### Verification (scope: single-cluster cores)
- **Differential test:** 300 random networks (n ≤ 12; 223 with an upstream part, 233 with read-outs, 174 with both; int and float weights including ±0.1/0.2/0.3 ties). Reduced attractor sets **and exact basin sizes** were identical to `sespy.dynamics.boolean_attractors` on the full network in **300/300**.
  - The generator builds one ring-shaped core with single-edge chains above and below it. It has no multi-cluster cores, bridge nodes, fan-in, or upstream-to-read-out edges. So the result is **verified for single-cluster cores**.
- **17-node sample (two cycle clusters, 8 + 6, with a bridge):** reduced and full results are identical, attractors and basins (`probe3.py`). It has only one attractor, so this says nothing about basin splits.
- **Fisheries template (26 nodes):**
  - upstream 9, core 14, read-out 3;
  - one attractor: the **all-off fixed point** (state 0 is always fixed under these rules), with basin 2^26;
  - 49 s with the unoptimised probe, dominated by the 2^9 × 2^14 exact-basin pass. The attractor set alone costs 2^14;
  - a full-space cross-check from 20,000 random full states reached the same single attractor. With one attractor, this checks the attractor, not basin splits.

### Distribution (57 shipped networks: 11 SESPy templates + sample, 45 MosaicSES example compartments, several sharing a shape across projects)
- **Networks over 20 nodes: 32.** Of those, **31 have a core of 20 or fewer**: 11 are acyclic (core 0, trivially one all-off attractor under SESPy rules) and 20 have cores of 3–17.
- **Typical cores:**

  | Network | Nodes | Core |
  |---|---|---|
  | Fisheries | 26 | 14 |
  | Tourism | 26 | 13 |
  | Pollution | 28 | 10 |
  | Aquaculture | 28 | 7 |
  | OffshoreWind | 23 | 12 |
  | Venice lagoon_central | 34 | 17 |
  | other MosaicSES compartments | 19–32 | 0–8 |

  A core of 0 means the network is acyclic: one fixed point, trivially.
- **The exception: Caribbean, 78 nodes, core 64.** That is one 64-node cycle cluster. A greedy feedback vertex set has **8** nodes.
- **No gain:** coastal_tourism / sample has 17 nodes and a core of 16. It has two cycle clusters (8 + 6) in series.

### Exact-basin cost (upstream sizes)

| Network | U | U feeding the core | C | R |
|---|---|---|---|---|
| Fisheries | 9 | 4 | 14 | 3 |
| Tourism | 9 | 7 | 13 | 4 |
| Pollution | 17 | 7 | 10 | 1 |
| Aquaculture | 21 | 2 | 7 | 0 |
| OffshoreWind | 10 | 5 | 12 | 1 |
| Caribbean | 6 | 6 | 64 | 8 |

Naive exact basins (2^(U+C)) would be 2^27 for Pollution and 2^28 for Aquaculture. The input-sequence
deduplication should cut those to near 2^C, because few upstream nodes feed the core directly. Not yet measured.

## Other approaches

| Approach | Attractors exact | Basins exact | Practical limit | New dependency | Server cost |
|---|---|---|---|---|---|
| **Core reduction** + vectorised core search (this note) | yes (verified) | yes, cost 2^C × distinct upstream input sequences (else sampled estimate) | **core ≤ 20** (31/32 real networks above 20 nodes) | none (numpy, networkx already declared) | as option 1 on the core |
| **Compiled exhaustive** (numba, uint32 map + int32 labels) on full n, or on the core | yes | yes | measured single-thread time on this laptop (random 3-input rules): n=22 2.0 s; n=24 8.4 s; n=26 37 s. MB figures are array-size sums (~192 MB at 24, ~768 MB at 26), not measured peaks. The state map dominates; `prange` could divide by cores | numba: **not declared** in `pyproject.toml`; laguna availability unknown | memory-bound; 24 is the practical shared-server ceiling |
| **Block-by-block (SCC condensation)**: solve upstream cycle clusters first, then drive downstream clusters with their periodic outputs | yes (argument, not run) | hard (periodic forcing; state × phase spaces) | sum of cluster sizes instead of their product (sample: 8 + 6 instead of 16) | none | later phase |
| **Feedback-vertex-set enumeration**: remove a FVS, the rest is a DAG | fixed points yes, **run**; cycles of period p via periodic FVS sequences, 2^(\|FVS\|·p), argument only | no | Caribbean (78 nodes): greedy FVS of 8, 256 assignments in 0.08 s, giving **exactly 1 fixed point (all-off)**. 5,000 sampled starts reached no fixed point within 400 steps, so its long-run behaviour is cycles or long transients that this method does not find | none (networkx) | cheap for fixed points |
| **MILP fixed points** (pulp/CBC, no-good cuts) | fixed points; bounded cycles by unrolling | no | hundreds of nodes | pulp: not declared; laguna unknown | modest; strict `>` with float weights needs an epsilon, which is a tie-semantics risk |
| **Sampling** (option 2) | no (reached attractors only) | estimates | any size | none | cheap |
| SAT / BDD symbolic | — | — | — | python-sat not on conda-forge; no BDD library installed | parked |

## Effect of R semantics on these approaches
Under R/BoolNet rules, a source is a self-loop that keeps its value: it acts as a **parameter**, not a constant. Core reduction carries over in this form:
1. enumerate the 2^s source settings;
2. for each one, propagate the acyclic rest and search the remaining core;
3. read-outs are reconstructed as before.

The cost is 2^s × 2^core', where core' excludes the sources. The Fisheries network has s = 5.
- **Fixed points by FVS enumeration** carry over unchanged.
- **MILP** gets simpler: OR of literals is linear, with no float-tie epsilon.
- **Sampling** is unchanged.

## Constraints for any adoption
- **API.**
  - Don't fold reduction silently into `boolean_attractors`. The cap would then apply to core size, the `too_large` sentinel would change, and `basin_size` is documented to sum to 2^n.
  - Use an opt-in parameter (`reduce=True`) or a new function (`boolean_attractors_reduced`) that reports `n_nodes`, `core_size`, `upstream`, `readout` and `basin_method` (`"exact"` | `"sampled"`).
  - The UI shows "26 nodes, 14 in the feedback core".
- **Kernel.** Evaluate the core with the shared kernel on full-width states, holding non-core bits fixed, as the probe does. Rebuilding sub-rules risks changing float-tie behaviour.
- **Dependencies.** numba and pulp are installed locally but not declared, and their presence on laguna is unknown.
