# SESPy — Proposed GitHub Issues (from literature alerts)

Ready-to-paste issue drafts. Review and open manually.

---

## [Medium] Stochastic token diffusion simulation in `sespy/dynamics.py`

**Status:** ✅ Opened as razinkele/SESPy#17 (2026-08-04)

**Source paper:** A systems thinking approach to improve participatory processes in small-scale fisheries management, *Research Square* (preprint, 2026). https://doi.org/10.21203/rs.3.rs-10397797/v1
**Alert week:** 2026-08-04

**Motivation.** Donlan et al. apply stochastic token diffusion on a participatory CLD to rank candidate interventions by the reach and speed of their effects through the network. SESPy's existing features (`leverage_scores()`, `causal_paths()`, `uncertainty_scores()`) do not simulate dynamic propagation from a chosen intervention node. `token_diffusion(g, source_node, n_steps, n_tokens)` fills this gap by seeding perturbation tokens at a source node and propagating them via random walks along signed edges, flipping polarity at negative edges, and returning a per-node DataFrame of tokens received, net sign, and step of first arrival.

**Proposal.** Add `token_diffusion(g, source_node, n_steps=10, n_tokens=1000, seed=None)` to `sespy/dynamics.py` with the algorithm described in issue #17. Expose as a collapsible "Intervention Simulation" section in the Network Metrics module with source-node selector, step/token sliders, a ranked table, and a colour-coded bar chart.

**Effort:** Medium. **Labels:** enhancement, analysis, network.

---

## [Medium] Causal path tracer in `sespy/network.py`

**Status:** ✅ Opened as razinkele/SESPy#16 (2026-07-28)

**Source paper:** A dynamic explainability method for fuzzy cognitive maps based on causal and temporal evolution analysis, *Applied Soft Computing* (2026). https://doi.org/10.1016/j.asoc.2026.115925
**Alert week:** 2026-07-28

**Motivation.** FCM explainability paper motivates enumerating open directed causal chains between node pairs in a CLD, annotated by compound polarity (sign product along the path). SESPy already covers closed cycles (`find_loops()`) and node-level centrality (`leverage_scores()`), but cannot answer "How does A influence B?" with path-level causal chain enumeration.

**Proposal.** Add `causal_paths(g, source, target, max_length=None)` to `sespy/network.py` returning a DataFrame of all simple directed paths with `path`, `length`, `compound_polarity` columns. Expose in Network Metrics module as a collapsible "Causal Pathways" section with source/target node selectors.

**Effort:** Small–Medium. **Labels:** enhancement, analysis, network.

---

## ✅ SHIPPED — Uncertainty-aware leverage & loop scoring in `sespy/network.py`

**Shipped 2026-06-24** as the D2D Monte-Carlo feature (`network.uncertainty_scores`,
merged `fa9e212`): edge drop+sign-flip Monte Carlo returning per-node leverage 95%
CIs + per-loop existence/polarity probabilities with a "contested" flag, surfaced
behind off-by-default toggles in the Leverage and Loop Analysis modules. Draft
retained here only for provenance; no longer an open item.

---

## [Medium] Cascade vulnerability indicator in `sespy/network.py`

**Status:** ✅ Opened as razinkele/SESPy#15 (2026-07-21)

**Source paper:** Network cascading effects reveal thresholds and nonlinearity in ecological vulnerability, *Environmental Research Letters* (2026). https://doi.org/10.1088/1748-9326/ae83cb
**Alert week:** 2026-07-21

**Motivation.** ERL paper demonstrates that ecological network vulnerability is nonlinear — sequential node removal produces cascade threshold discontinuities invisible to per-node centrality metrics. SESPy's existing `leverage_scores()` ranks nodes independently by linear centrality composite; `cascade_vulnerability(g)` would simulate iterative removal in leverage-rank order and identify the node triggering the largest structural integrity drop.

**Proposal.** Add `cascade_vulnerability(g)` to `sespy/network.py` returning a DataFrame (removal step × `lccf`, `loop_count`, `delta_lccf`) and a `cascade_threshold_node` scalar. Expose in Network Metrics module as a collapsible section.

**Effort:** Medium. **Labels:** enhancement, analysis, network.

---

## [Medium] Governance actor influence scores in `sespy/network.py`

**Status:** ✅ Opened as razinkele/SESPy#14 (2026-07-14)

**Source paper:** Unpacking power dynamics and actor interactions across fisheries and marine protected areas governance: a comparative study of Saint Louis and Sangomar, Senegal, *Maritime Studies* (2026). https://doi.org/10.1007/s40152-026-00501-z
**Alert week:** 2026-07-14

**Motivation.** Governance networks in MPAs show significant power asymmetries — some actors dominate co-management while others are peripheral. `governance_gap()` (#13) detects *whether* governance actors are linked; `governance_actor_influence()` quantifies *how influential* each R/M-typed node is by computing full-graph centrality restricted to governance nodes.

**Proposal.** Add `governance_actor_influence(g)` to `sespy/network.py` returning a DataFrame of betweenness, eigenvector, PageRank, and composite `influence_rank` for all R/M nodes; expose in the Network Metrics module.

**Effort:** Small–Medium. **Labels:** enhancement, analysis, network.

---

## [Medium] Governance gap detection in `sespy/network.py`

**Status:** ✅ Opened as razinkele/SESPy#13 (2026-07-07)

**Source paper:** Social–ecological network analysis of governance gaps in a newly designated marine protected area of the Global South, *Marine Policy* (2026). https://doi.org/10.1016/j.marpol.2026.107169
**Alert week:** 2026-07-07

**Motivation.** Governance gap detection identifies ecological nodes with no governance actor coverage and governance actors with no ecological target — a structural diagnostic distinct from the shipped `social_ecological_fit` coupling density metric.

**Proposal.** Add `governance_gap(g)` to `sespy/network.py` partitioning DAPSIWR(M) node types into governance (R, M) vs. ecological (S, I, P), returning `{ecological_gaps, governance_orphans, gap_fraction}`, surfaced in the Network Metrics module.

**Effort:** Small–Medium. **Labels:** enhancement, analysis, network.

---

## ✅ SHIPPED — Social-ecological "fit" metric in `sespy/network.py`

**Shipped 2026-06-25** (merged `030321c`, closes GitHub #1): `social_ecological_fit`
cross-boundary coupling + `subsystem()` partition, surfaced in the Network Metrics
module. Draft retained here only for provenance; no longer an open item.

**Was tracked as GitHub issue #1:** https://github.com/razinkele/SESPy/issues/1

**Source paper:** Fang et al., *Assessing social–ecological fit of sustained watershed environmental governance*, Env. Impact Assessment Review (2026). https://doi.org/10.1016/j.eiar.2026.108522
**Alert week:** 2026-06-22

**Motivation.** "Fit" measures alignment between social ties and ecological interdependencies — a diagnostic SESPy does not currently compute.

**Proposal.** Add a `social_ecological_fit(isa_data)` function operating on the DAPSI(W)R(M) node typing (social vs. ecological partition) and report mismatch/alignment scores. Expose as a new metric in the Network Metrics module.

**Effort:** moderate. **Labels:** enhancement, analysis, network.

---

## [High] Loop dominance over time in `sespy/network.py`

**Source papers:** Nguyen, Dinh & Tran, *Scaling Regenerative Supply Chains in Agriculture*, Systems Research and Behavioral Science (2026). https://doi.org/10.1002/sres.70145 ; Imtihan, Edinov & Suhaemi, *Analysis of 5R Waste Management on Green Economy using Causal Loop Diagram Model in West Sumatera*, Indonesian J. Urban & Environmental Technology 9(2) (2026). https://doi.org/10.25105/urbanenvirotech.v9i2.22457
**Alert week:** 2026-08-25

**Motivation.** Nguyen et al. build a CLD with five reinforcing loops (R1–R5) and one balancing loop (B1), and their central result is not the loop inventory but the *shift in loop dominance*: B1 dominates the early transition phase, creating a temporal trap, before reinforcing loops take over. Imtihan et al. likewise report a balancing loop (low public awareness) acting as the operative barrier. SESPy's `find_loops()` returns loops with reinforcing/balancing polarity as a flat, time-invariant list. It cannot answer "which loop is governing behaviour at step t?", even though the linear-matrix iteration and Behaviour-Over-Time machinery needed to compute this already exist.

**Proposal.** Add `loop_dominance(g, timesteps, weights=None)` to `sespy/network.py`:
- For each loop returned by `find_loops()`, compute loop gain as the product of signed edge weights around the cycle.
- Re-evaluate loop gain at each timestep of the existing linear-matrix iteration (using the current node-state-scaled edge contributions).
- Return a DataFrame indexed by (timestep × loop_id) with `gain`, `polarity`, `dominance_rank`.
- Expose in the Loop Analysis module as an optional overlay annotating the Behaviour-Over-Time plot with the dominant loop per phase.

**Acceptance criteria.**
- Function returns per-timestep dominance ranking for a test network with a known B→R dominance shift.
- Reuses existing loop detection and simulation code; no new dependency.
- Off by default; degrades gracefully when no simulation has been run.

**Related metric — ALC.** *Adjusted Loop Centrality* (Environmental Science & Policy 167:103996, 2026, https://doi.org/10.1016/j.envsci.2025.103996) weights a node by the loops it participates in — loop strength, and whether the node initiates or reinforces — instead of scoring nodes independently as the current `z(betweenness)+z(eigenvector)+z(PageRank)` composite does. It is the node-side view of the same blind spot this issue addresses from the loop side, and it needs the same inputs (the `find_loops()` set plus per-node loop membership and a gain measure). Tracked here deliberately rather than as a second issue: if `loop_dominance()` lands, emitting an ALC column alongside the per-timestep ranking is nearly free. Surfaced by the scheduled 2026-08-25 alert run, which had deferred it pending #20–21.

**Effort:** Moderate. **Labels:** enhancement, analysis, network, loops.

---

## [High] Leverage-point depth classification alongside the leverage composite

**Source papers:** Geekiyanage, Fernando & Teixeira Fernando, *Revealing leverage points of anticipatory action for fisheries through a systems thinking lens in developing island states*, Climate Risk Management 53:100843 (2026). https://doi.org/10.1016/j.crm.2026.100843 ; Brons, Mathijs & Kiel, *Leveraging change: a soft systems approach to transforming the EU food system*, Sustainability Science (2026). https://doi.org/10.1007/s11625-026-01872-2
**Alert week:** 2026-08-25

**Motivation.** Both papers identify leverage points by *intervention depth* (parameter → feedback structure → rules → goals/paradigm), not by structural prominence. SESPy's leverage composite `z(betweenness)+z(eigenvector)+z(PageRank)` says a node is well-positioned but not how deep an intervention on it would reach, so two nodes with identical scores can imply very different policy asks. Note: the Geekiyanage abstract was not returned by the literature API — this draft is motivated by the paper's stated framing, and the depth scheme should be checked against the full text before implementation.

**Proposal.** Extend the leverage output with a categorical `leverage_depth` column derived from (a) the node's DAPSI(W)R(M) type and (b) whether it participates in a detected feedback loop:
- Pressure / Marine Process and Function → *parameter*
- Activity inside a loop → *feedback structure*
- Measure / response node → *rules*
- Driver → *goals / paradigm*
Report depth next to the z-score composite in the Leverage module and allow sorting by it.

**Acceptance criteria.**
- `leverage_scores()` output gains a `leverage_depth` column with the four classes above.
- Depth assignment documented and configurable (mapping table, not hard-coded).
- Existing composite ranking unchanged; depth is additive.

**Effort:** Moderate. **Labels:** enhancement, analysis, leverage, decision-support.
