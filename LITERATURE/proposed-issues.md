# SESPy — Proposed GitHub Issues (from literature alerts)

Ready-to-paste issue drafts. Not created on GitHub — review and open manually.

---

## [High] Uncertainty-aware leverage & loop scoring in `sespy/network.py`

**Source paper:** Uleman et al., *Diagrams-to-Dynamics (D2D): exploring causal loop diagram leverage points under uncertainty*, BMC Medicine (2026). https://doi.org/10.1186/s12916-026-04971-0
**Alert week:** 2026-06-22

**Motivation.** D2D converts causal loop diagrams to dynamics and ranks leverage points while propagating uncertainty. SESPy already has the building blocks — `feedback_loops`, `loop_polarity`, `classify_loops`, `leverage_scores` (z(betweenness)+z(eigenvector)+z(PageRank)), Monte Carlo in the simulation module, and an edge `strength`/`confidence` column — but they don't yet combine: leverage and loop classification are computed on point-estimate edge weights only.

**Proposal.** Add uncertainty-aware variants that resample edge weights from their `confidence` and return distributions/CIs.
- `leverage_scores(..., n_samples=None)` → when set, returns per-node mean + CI instead of a point score.
- `classify_loops(..., n_samples=None)` → return probability of reinforcing vs. balancing per loop.
- Reuse the existing Monte Carlo sampler from the dynamic-simulation module.

**Acceptance criteria.**
- New golden-value unit tests in `tests/test_network.py` for tiny graphs with known confidence.
- Backward compatible: default behaviour (no `n_samples`) unchanged.
- Results surfaced to the Leverage Points and Loop Analysis modules.

**Effort:** moderate. **Labels:** enhancement, analysis, network.

---

## [Medium] Social-ecological "fit" metric in `sespy/network.py`

**Source paper:** Fang et al., *Assessing social–ecological fit of sustained watershed environmental governance*, Env. Impact Assessment Review (2026). https://doi.org/10.1016/j.eiar.2026.108522
**Alert week:** 2026-06-22

**Motivation.** "Fit" measures alignment between social ties and ecological interdependencies — a diagnostic SESPy does not currently compute.

**Proposal.** Add a `social_ecological_fit(isa_data)` function operating on the DAPSI(W)R(M) node typing (social vs. ecological partition) and report mismatch/alignment scores. Expose as a new metric in the Network Metrics module.

**Effort:** moderate. **Labels:** enhancement, analysis, network.
