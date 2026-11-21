# Boolean attractor search beyond 20 nodes — investigation

Date: 2026-11-21. Companion to `2026-11-21-boolean-scale-design.md` (options 1 and 2). This note
looks at ways to go further, with measurements.

The probe scripts lived in the session scratchpad: `core_reduction.py` and `probe2.py`. Their results are recorded below.

## Key finding: exact feedback-core reduction

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

### Verification
- **Differential test:** 300 random networks (n ≤ 12; 223 with an upstream part, 233 with read-outs, 174 with both; int and float weights including ±0.1/0.2/0.3 ties). Reduced attractor sets **and exact basin sizes** were identical to `sespy.dynamics.boolean_attractors` on the full network in **300/300**.
- **Fisheries template (26 nodes):**
  - upstream 9, core 14, read-out 3;
  - one attractor, a fixed point with basin 2^26 (sum checked);
  - 49 s with the unoptimised probe, dominated by the 2^9 × 2^14 exact-basin pass;
  - a full-space cross-check from 20,000 random full states with the plain kernel reached the same single attractor and nothing else.

### Distribution (57 networks: 11 SESPy templates + sample, 45 MosaicSES compartments)
- **Networks over 20 nodes: 32.** Of those, **31 have a core of 20 or fewer**.
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
| **Compiled exhaustive** (numba, uint32 map + int32 labels) on full n, or on the core | yes | yes | measured single-thread on this laptop: n=22 2.0 s; n=24 8.4 s / ~192 MB; n=26 37 s / ~768 MB (state map dominates; `prange` could divide by cores) | numba: **not declared** in `pyproject.toml`; laguna availability unknown | memory-bound; 24 is the practical shared-server ceiling |
| **Block-by-block (SCC condensation)**: solve upstream cycle clusters first, then drive downstream clusters with their periodic outputs | yes | hard (periodic forcing; state × phase spaces) | sum of cluster sizes instead of their product (sample: 8 + 6 instead of 16) | none | later phase |
| **Feedback-vertex-set enumeration**: remove a FVS, the rest is a DAG | fixed points yes; cycles of period p via periodic FVS sequences, 2^(\|FVS\|·p) | no | Caribbean: FVS ≈ 8, so 256 checks for all fixed points; period ≤ 3 ≈ 2^24 | none (networkx) | cheap for fixed points |
| **MILP fixed points** (pulp/CBC, no-good cuts) | fixed points; bounded cycles by unrolling | no | hundreds of nodes | pulp: not declared; laguna unknown | modest; strict `>` with float weights needs an epsilon, which is a tie-semantics risk |
| **Sampling** (option 2) | no (reached attractors only) | estimates | any size | none | cheap |
| SAT / BDD symbolic | — | — | — | python-sat not on conda-forge; no BDD library installed | parked |

## Constraints for any adoption
- **API.**
  - Don't fold reduction silently into `boolean_attractors`. The cap would then apply to core size, the `too_large` sentinel would change, and `basin_size` is documented to sum to 2^n.
  - Use an opt-in parameter (`reduce=True`) or a new function (`boolean_attractors_reduced`) that reports `n_nodes`, `core_size`, `upstream`, `readout` and `basin_method` (`"exact"` | `"sampled"`).
  - The UI shows "26 nodes, 14 in the feedback core".
- **Kernel.** Evaluate the core with the shared kernel on full-width states, holding non-core bits fixed, as the probe does. Rebuilding sub-rules risks changing float-tie behaviour.
- **Dependencies.** numba and pulp are installed locally but not declared, and their presence on laguna is unknown.
