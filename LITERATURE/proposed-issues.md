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
