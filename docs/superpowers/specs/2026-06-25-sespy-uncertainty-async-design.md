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
- **Mechanism = explicit `unc_state` `reactive.Value` + a generation counter +
  `.result()`/`SilentException`** (the wizard's approach). **A generation counter IS
  required** (an earlier draft wrongly claimed otherwise): per the installed Shiny
  `reactive/_extended_task.py`, `invoke()` *queues* a re-invocation rather than
  cancelling the in-flight run, and `_done_callback` sets `status="success"` +
  `value=result1` and **flushes before** starting the queued run-2 — so the observe
  effect fires once with run-1's **stale** result and would overwrite the "computing"
  sentinel. The task therefore returns `(gen, result)`; the observe discards a result
  whose `gen` is not the latest. **The counter is a plain mutable cell `_gen = [0]`, NOT
  a `reactive.Value`** — the trigger both reads and increments it every run, and a
  `reactive.Value` read+set in the same effect would self-invalidate into an infinite
  loop. The observe reads `_gen[0]` non-reactively (its reactivity comes from
  `_unc_task.result()`).

## Architecture (per module — Leverage and Loops)

Add `import asyncio`, `import logging`, and `from shiny.types import SilentException`
(neither module imports these yet). In each module server, replace the synchronous
`@reactive.calc uncertainty()` with:

```python
_COMPUTING = object()                       # module-level sentinel

# in the server:
unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>
_gen = [0]                                  # plain mutable cell (NOT reactive — see Decisions)

@reactive.extended_task
async def _unc_task(isa, n_samples, gen):   # Loops: (isa, cycles, n_samples, gen)
    result = await asyncio.to_thread(
        net_analysis.uncertainty_scores, isa, n_samples=n_samples, seed=0,
    )                                       # Loops: ..., cycles=cycles, n_samples=..., seed=0
    return (gen, result)

@reactive.effect
def _unc_trigger():
    _gen[0] += 1                            # bump on EVERY run (incl. toggle-off) so any
    gen = _gen[0]                           # in-flight run becomes stale and is discarded
    if not input.show_uncertainty():
        unc_state.set(None)
        return
    event_bus.isa_change.get()              # re-run on graph edits
    isa = project_data.get().isa_data
    n = int(input.n_samples() or 100)
    # Loops: cycles = detected.get(); if not cycles: unc_state.set(None); return
    unc_state.set(_COMPUTING)
    _unc_task(isa, n, gen)                   # Loops: _unc_task(isa, cycles, n, gen)

@reactive.effect
def _unc_observe():
    try:
        gen, result = _unc_task.result()    # raises SilentException while running
    except SilentException:
        raise                               # RE-RAISE: registers the status dependency so
                                            # the effect re-fires on completion (per wizard)
    except Exception:                       # a real task error (e.g. MemoryError) — clear
        logging.getLogger(__name__).exception("uncertainty task failed")
        unc_state.set(None)                 # don't crash the session / stick the spinner
        return
    if gen != _gen[0]:
        return                              # stale: superseded re-run or toggled-off run
    unc_state.set(result)
```

The consumer render reads `unc_state.get()` and **must branch on the sentinel
explicitly** (the current `if unc is None` / `if not unc` guards do NOT catch the truthy
`_COMPUTING` object and would `AttributeError` on `unc.get(...)`):

```python
    unc = unc_state.get()
    computing = unc is _COMPUTING
    data = unc if isinstance(unc, dict) else None   # None when idle OR computing
```
- `data is None and not computing` → render as today with the toggle off (no CIs).
- `computing` → the "computing…" caption + `…` placeholders in the CI cells; the base
  table/summary is fully rendered (never blocked).
- `data` (a dict) → render CIs exactly as the current synchronous path does.

**Leverage** (`analysis_leverage.py:169-193`): `leverage_table()` currently does `unc =
uncertainty()` then `if unc is None: ...`; it now reads `unc_state.get()` with the
three-state guard above.
**Loops** (`analysis_loops.py`): the current `uncertainty_loops()` calc returns the
`{loop_id: loop}` mapping consumed by `classification_summary` **and** `loops_table()`;
the task stores the raw `uncertainty_scores` result in `unc_state`, and a small read
helper builds the `{id: loop}` map when `unc_state` is a dict (returns `{}` when idle or
computing). **Both** consumers of the old `uncertainty_loops()` must route through the
helper, and a separate read of `unc_state is _COMPUTING` drives the caption.

## i18n

One new shared key joining the existing `uncertainty.*` namespace (which already holds
several keys incl. `uncertainty.toggle`, `uncertainty.n_samples`):
**`uncertainty.computing`** × 9 languages, en = `"Computing uncertainty (Monte Carlo)…"`.
A presence test guards it (per-key, like the other `uncertainty.*` keys). The error path
clears silently (logged, no user-facing string), so no `uncertainty.error` key is added.

## Error handling / edge cases

- **Re-invoke while running** (e.g. change `n_samples` mid-run) → handled by the
  generation counter: `_unc_trigger` bumps `_gen[0]` and sets `_COMPUTING`; when the
  superseded run-1 completes and the observe fires with its stale `gen`, the
  `gen != _gen[0]` check discards it, so the "computing…" state holds until the latest
  run finishes.
- **Toggle off mid-run** → `_unc_trigger` bumps `_gen[0]` and sets `unc_state=None`; the
  in-flight run's captured `gen` is now stale, so its late `_unc_observe` is discarded —
  nothing is shown. (The bump-on-every-trigger is what makes this work without also
  gating the render on the toggle.)
- **Loops with no detected cycles** → `unc_state=None` (no MC invoked), same as today.
- **A real task error** (e.g. `MemoryError` on a huge graph) — `_unc_task.result()`
  re-raises it (status `"error"`); the observe's catch-all logs it and sets
  `unc_state=None` (clears the spinner, does not crash the session). `uncertainty_scores`
  is total over valid graphs, so this is a safety net, not an expected path.

## Testing

This is reactive/UI wiring — the pure `uncertainty_scores` is already unit-tested, so
coverage is the **existing leverage + loops e2e**, updated:
- The existing e2e already `wait_for_function`-poll for content; point each poll at the
  **CI text itself** (e.g. a `[lo, hi]` interval / contested marker), not just the toggle
  or row count, so it waits through the now-async "computing…" state before asserting.
  Without this the read would race the worker thread and flake.
- Optionally assert the intermediate **`uncertainty.computing`** caption appears right
  after toggling (proves the offload is actually async, not synchronous).
- The base ranks / classification assertions are unchanged (never blocked).
- i18n: a presence test for `uncertainty.computing` (all 9 languages).
- No `network.py` test changes.

## Out of scope (YAGNI)

- A shared async-task factory / new util module (only two consumers; inline is the idiom).
- Cancelling an in-flight MC when inputs change (Shiny's `ExtendedTask` queues rather
  than cancels; we don't cancel — the generation counter discards the superseded run's
  result so it never reaches the display).
- Progress percentage / cancel button.
- Touching `network.uncertainty_scores` or the Monte-Carlo math.
- Debounce (unavailable + numeric input).
