# Sampling-Error-Aware Token Diffusion (issue #19) — Design

**Date:** 2026-08-17. **Status:** approved in session.
**Source:** GitHub issue #19, raised by the #17 final review with measurements.

## Problem

`token_diffusion()` reports arrival counts from a single Monte-Carlo sample, and the UI presents them as a firm ranking. Measured on `data/sample_ses.json` from D001: GB01 (1501) outranks A001 (1499) at seed 0, but across 50 seeds that ordering holds only 30 times — a 60/40 coin flip displayed as a rank. Separately, the fixed 5 % contested margin mislabels a structurally balanced node as signed in 6 of 50 seeds, because 5 % of 1000 tokens is comparable to the sampling error itself.

## Decisions (user-confirmed)

1. **Presentation: rank column + `±` margin.** Rows carry a rank in which statistically tied rows share the same number (1, 1, 3, 3, 5…), and arrivals render as `1501 ±32`. The rank makes a tie impossible to misread; the margin shows how wide the uncertainty is.

## Method: batch means

Tokens are i.i.d., so splitting them into `B` independent batches gives an honest standard error with no distributional assumption and O(B × elements) memory:

- `n_batches = min(20, n_tokens)`; token *i* joins batch `(i * B) // n_tokens` (near-equal batches).
- Accumulate per-batch arrival counts and per-batch signed sums (`+1` per positive arrival, `−1` per negative) alongside the existing totals.
- `Var(total) = B · Var(batch totals)` for i.i.d. batches, so `se = sqrt(B · var(batches, ddof=1))`.
- Critical value is Student's *t* at 95 % with `B − 1` degrees of freedom (2.093 at the default B = 20), via a lazily imported `scipy.stats` — scipy is already a hard dependency (`pyproject.toml`), and lazy imports inside functions are the established repo pattern.

**The RNG stream is unchanged** — only accumulation bookkeeping differs — so every shipped count and first-arrival golden stays exactly valid. Verified: all seven sample rows match the pre-change values.

## Changes to `token_diffusion()`

Return dict gains `n_batches`; each row gains:

- `margin: int` — the 95 % half-width on `tokens_received` (`round(t · se)`), 0 when the count is deterministic.
- `rank: int` — competition ranking over the count-descending order: a row ties with the row above it when its interval overlaps that row's (`count + margin >= prev_count − prev_margin`), inheriting its rank; otherwise it takes its positional rank. Ties chain down the list, which is how a reader scans the column; documented as such.

`net_sign` semantics change: `"~"` when `abs(net) <= t · se(net)` or `net == 0` — i.e. the polarity imbalance is not distinguishable from zero at 95 % — replacing the arbitrary fixed 5 % margin. Where `se(net)` is 0 and `net` is non-zero (a structurally determined sign, e.g. a single-route chain) the node stays firmly signed.

**Measured effect** on the balanced fixture (A→X(+)→T, A→Y(−)→T, 1000 tokens): the old rule labelled T as `-` at seed 0 and `~` at seed 1; the new rule says `~` at both. Across 50 seeds, mislabelling drops from 6/50 to 3/50 — and ~5 % is the *nominal* false-positive rate of a 95 % test, so the new rule's error rate is known and controllable where the old one's was arbitrary.

**Sample goldens** (`sample_ses.json`, D001, seed 0, defaults) — counts, signs and steps unchanged; ranks and margins new:

| rank | id | arrivals | margin | net | first |
|---|---|---|---|---|---|
| 1 | P001 | 2000 | 0 | + | 2 |
| 1 | MPF1 | 2000 | 0 | − | 3 |
| 3 | GB01 | 1501 | 32 | − | 5 |
| 3 | A001 | 1499 | 32 | + | 1 |
| 5 | ES03 | 1002 | 44 | − | 4 |
| 5 | ES01 | 998 | 44 | − | 4 |
| 7 | R002 | 501 | 32 | − | 6 |

GB01/A001 — the pair the review flagged — now share rank 3.

## Two existing tests must be updated (not new behaviour, new fields)

`test_token_diffusion_matches_manual_trace` and the sink-source case in `test_token_diffusion_degenerate_shapes` assert whole-dict equality, so they must gain the new `margin`/`rank`/`n_batches` keys. Every other existing assertion (tuple extractions, the contested `~` at seed 1, reproducibility) passes unchanged.

## UI

`sespy/modules/analysis_intervention.py`, diffusion block only:

- Table gains a leading `rank` column; the arrivals cell renders `f"{tokens_received} ±{margin}"`.
- The chart is unchanged (bar height = arrivals, colour = net sign).
- `diffusion.caption` is rewritten (9 languages) to explain the `±` margin, that equal ranks mean "too close to call", and that `~` means the split is within sampling error — replacing the now-redundant "read near-equal counts as ties" instruction, since the rank column does that work. No new i18n keys; table headers stay hardcoded English per module convention.

## Testing

- Unit: sample golden extended to `(rank, id, tokens, margin, net_sign, step)` tuples; balanced fixture asserts `~` at seed 0 **and** seed 1 (the old rule's failure case is now the regression test); chain fixture asserts `margin == 0` and rank 1 for all three rows with signs preserved; `n_tokens=5` asserts `n_batches == 5` (fewer tokens than batches); the two whole-dict tests updated.
- i18n: the existing presence test still covers `diffusion.caption`; the 9-language drift test guards the rewrite.
- e2e: unchanged assertions still hold (summary line, "Anchor damage", "2000", P002's 13-of-17); add an assertion that a rank column and a `±` appear.
- Gates: CI-parity unit suite; FULL detached e2e on an idle machine.

## Out of scope (YAGNI)

Exposing `n_batches` or the confidence level in the UI; bootstrap intervals (batch means is sufficient and cheaper); applying the same treatment to other Monte-Carlo features (`uncertainty_scores` already has its own CIs).
