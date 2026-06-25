# Async uncertainty offload — design

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #4. Follow-up to the shipped D2D uncertainty feature
(`fa9e212`); see memory `sespy-uncertainty-scoring`.

## Problem / goal

`network.uncertainty_scores()` runs synchronously on the Shiny reactive thread, so
toggling the uncertainty view freezes the whole UI for the duration of the Monte Carlo
(~78 ms/sample × default `n_samples=100` ≈ 8 s; 500 froze it ~39 s). Move the MC onto a
worker thread so the UI stays responsive and shows a "computing…" state, then fills in
the CIs when the result arrives.

## Decisions (from brainstorm)

- **Offload via `@reactive.extended_task` + `asyncio.to_thread`**, using the **exact
  proven pattern already shipped in `ai_isa_wizard.py`** (the Claude backend call).
  `network.uncertainty_scores` is pure and **unchanged** — all work is reactive plumbing
  in the two consumer modules.
- **"Computing…" UX (not stale, not blank).** While the MC runs, the uncertainty
  area shows a "Computing uncertainty (Monte Carlo)…" caption + `…` placeholders in the
  CI cells; the base ranks / loop-classification are never blocked. On completion the
  CIs replace the placeholders. We do **not** show stale CIs from a previous run (they
  could mismatch the current graph after an edit).
- **Inline `@reactive.extended_task` per module — no shared factory.** The genuinely
  shared surface is one line (`asyncio.to_thread(uncertainty_scores, …)`); the invoke
  triggers differ (Loops also depends on `detected` cycles) and the displays differ
  (Leverage CI columns vs Loops per-loop summary). Inline matches the wizard idiom.
- **No debounce.** `reactive.debounce` is not available in this Shiny version, and
  `n_samples` is an `input_numeric` (fires on change/blur, already lightly debounced by
  Shiny) — not a continuously-firing slider, so task pile-up is a non-issue.
- **Mechanism = explicit status `reactive.Value` + `.result()`/`SilentException`** (the
  wizard's approach), because `ExtendedTask.status()` is not exposed in this Shiny
  version. A new run re-enters the "running" state where `.result()` raises
  `SilentException`, so the observe effect does not overwrite "computing" with a stale
  prior result — no generation counter is needed here (unlike the wizard's Back-race).

## Architecture (per module — Leverage and Loops)

Add `import asyncio` and `from shiny.types import SilentException` (Leverage doesn't yet
import them; Loops likewise). In each module server, replace the synchronous
`@reactive.calc uncertainty()` with:

```python
_COMPUTING = object()                       # module-level sentinel

# in the server:
unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>

@reactive.extended_task
async def _unc_task(isa, n_samples):        # Loops: (isa, cycles, n_samples)
    return await asyncio.to_thread(
        net_analysis.uncertainty_scores, isa, n_samples=n_samples, seed=0,
    )                                       # Loops: ..., cycles=cycles, n_samples=..., seed=0

@reactive.effect
def _unc_trigger():
    if not input.show_uncertainty():
        unc_state.set(None)
        return
    event_bus.isa_change.get()              # re-run on graph edits
    isa = project_data.get().isa_data
    n = int(input.n_samples() or 100)
    # Loops: cycles = detected.get(); if not cycles: unc_state.set(None); return
    unc_state.set(_COMPUTING)
    _unc_task(isa, n)                        # Loops: _unc_task(isa, cycles, n)

@reactive.effect
def _unc_observe():
    try:
        result = _unc_task.result()         # raises SilentException while running
    except SilentException:
        return                              # leave unc_state == _COMPUTING
    unc_state.set(result)
```

The consumer render reads `unc_state.get()`:
- `None` → render as today with the toggle off (no CI columns / hidden).
- `_COMPUTING` → the "computing…" caption + `…` placeholders in the CI cells; base
  table/summary fully rendered.
- result dict → render CIs exactly as the current synchronous path does.

**Leverage** (`analysis_leverage.py`): `leverage_table()` currently does `unc =
uncertainty()`; it now does `unc = unc_state.get()` and branches on the three states.
**Loops** (`analysis_loops.py`): the current `uncertainty_loops()` calc returns the
`{loop_id: loop}` mapping; keep that transform on the **read** side — the task stores the
raw `uncertainty_scores` result in `unc_state`, and a small read helper builds the
`{id: loop}` map when `unc_state` is a dict (returns `{}` / "computing" otherwise).

## i18n

One new shared key in the existing `uncertainty.*` namespace (joins
`uncertainty.toggle`, `uncertainty.n_samples`): **`uncertainty.computing`** × 9 languages,
en = `"Computing uncertainty (Monte Carlo)…"`. A presence test guards it.

## Error handling / edge cases

- Toggle off mid-run → `_unc_trigger` sets `unc_state=None`; a late `_unc_observe` would
  set it to the (now-unwanted) result, but the render is gated on
  `input.show_uncertainty()` so nothing shows. (Acceptable; the render already checks the
  toggle.)
- Loops with no detected cycles → `unc_state=None` (no MC invoked), same as today.
- The MC itself cannot raise on valid ISA data (pure, deterministic with `seed=0`); an
  `ExtendedTask` error surfaces as `_unc_task.result()` raising — `_unc_observe`'s
  `except SilentException` does NOT catch a real error, so it would propagate. uncertainty_scores
  is total over valid graphs, so this path is not expected; we do not add error UI (YAGNI).

## Testing

This is reactive/UI wiring — the pure `uncertainty_scores` is already unit-tested, so
coverage is the **existing leverage + loops e2e**, updated:
- After toggling `show_uncertainty`, **wait for the async result** — poll until the
  "computing…" caption is gone and the CI text (e.g. a `[lo, hi]` interval / contested
  marker) appears — before asserting. The current e2e read CIs synchronously; that read
  is now async.
- The base ranks / classification assertions are unchanged (never blocked).
- i18n: a presence test for `uncertainty.computing` (all 9 languages).
- No `network.py` test changes.

## Out of scope (YAGNI)

- A shared async-task factory / new util module (only two consumers; inline is the idiom).
- Cancelling an in-flight MC when inputs change (the new run supersedes the displayed
  result; a stale completed run can't overwrite "computing").
- Progress percentage / cancel button.
- Touching `network.uncertainty_scores` or the Monte-Carlo math.
- Debounce (unavailable + numeric input).
