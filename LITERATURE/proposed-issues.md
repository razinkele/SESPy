# SESPy — Proposed GitHub Issues (from literature alerts)

Ready-to-paste issue drafts. Review and open manually.

---

## ✅ SHIPPED — Uncertainty-aware leverage & loop scoring in `sespy/network.py`

**Shipped 2026-06-24** as the D2D Monte-Carlo feature (`network.uncertainty_scores`,
merged `fa9e212`): edge drop+sign-flip Monte Carlo returning per-node leverage 95%
CIs + per-loop existence/polarity probabilities with a "contested" flag, surfaced
behind off-by-default toggles in the Leverage and Loop Analysis modules. Draft
retained here only for provenance; no longer an open item.

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

## [Medium] Social-ecological "fit" metric in `sespy/network.py`

**Tracked as GitHub issue #1:** https://github.com/razinkele/SESPy/issues/1

**Source paper:** Fang et al., *Assessing social–ecological fit of sustained watershed environmental governance*, Env. Impact Assessment Review (2026). https://doi.org/10.1016/j.eiar.2026.108522
**Alert week:** 2026-06-22

**Motivation.** "Fit" measures alignment between social ties and ecological interdependencies — a diagnostic SESPy does not currently compute.

**Proposal.** Add a `social_ecological_fit(isa_data)` function operating on the DAPSI(W)R(M) node typing (social vs. ecological partition) and report mismatch/alignment scores. Expose as a new metric in the Network Metrics module.

**Effort:** moderate. **Labels:** enhancement, analysis, network.
