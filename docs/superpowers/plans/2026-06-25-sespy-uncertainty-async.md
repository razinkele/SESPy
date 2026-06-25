# Async Uncertainty Offload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `network.uncertainty_scores()` Monte Carlo on a worker thread so toggling the uncertainty view in the Leverage and Loop modules no longer freezes the UI.

**Architecture:** Per module, replace the synchronous `@reactive.calc` with the shipped `ai_isa_wizard.py` `@reactive.extended_task` + `asyncio.to_thread` pattern: an `unc_state` reactive holds `None | _COMPUTING | <result dict>`; a generation counter discards superseded/stale runs; a "computing…" caption shows while the worker runs. `network.uncertainty_scores` is unchanged.

**Tech Stack:** Python 3.11, Shiny for Python (`reactive.extended_task`, `asyncio.to_thread`), pytest/Playwright.

## Global Constraints

- Mechanism per module (verbatim shape):
  - `_COMPUTING = object()` module-level sentinel.
  - `unc_state = reactive.value(None)` — `None | _COMPUTING | <result dict>`.
  - `_gen = [0]` — **plain mutable cell, NOT a `reactive.Value`** (the trigger reads+increments it; a reactive value read+set in one effect self-invalidates into an infinite loop).
  - `@reactive.extended_task async def _unc_task(...) -> (gen, result)`: body `await asyncio.to_thread(net_analysis.uncertainty_scores, isa, …, seed=0)`.
  - `@reactive.effect _unc_trigger`: bump `_gen[0]` **first, every run**; if toggle off (or Loops: no cycles) → `unc_state.set(None)` and return; else `unc_state.set(_COMPUTING)` then invoke `_unc_task(..., gen)`.
  - `@reactive.effect _unc_observe`: `try: gen, result = _unc_task.result()`; `except SilentException: raise` (RE-RAISE — registers the dependency so the effect re-fires on completion); `except Exception:` log + `unc_state.set(None)`; then `if gen != _gen[0]: return` else `unc_state.set(result)`.
- Consumers must NOT crash on the truthy `_COMPUTING` sentinel: a table reads `data = unc if isinstance(unc, dict) else None` (the old `if unc is None` / `if not unc` guards would `AttributeError`); a caption checks `unc_state.get() is _COMPUTING`.
- Imports to add in each module: `import asyncio`, `import logging`, `from shiny.types import SilentException`.
- i18n: new shared key `uncertainty.computing` × 9 languages (en/es/fr/de/lt/pt/it/no/el), en = `"Computing uncertainty (Monte Carlo)…"`; presence test.
- No change to `sespy/network.py`. Run pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: i18n key + Leverage module async offload

**Files:**
- Modify: `sespy/translations/core.json` (add `uncertainty.computing` × 9)
- Modify: `sespy/modules/analysis_leverage.py` (imports; replace `@reactive.calc uncertainty()` ~158-167; `leverage_table()` guard ~179-183; new `uncertainty_status` caption + its ui slot)
- Test: `tests/test_i18n.py` (presence test)

**Interfaces:**
- Produces: the async `unc_state`/`_unc_task` machinery (module-internal); the `uncertainty.computing` i18n key (consumed by Task 2 too).

- [ ] **Step 1: Write the failing i18n presence test**

In `tests/test_i18n.py` add (the file has a module-scoped `translations` fixture — take it as the param):

```python
def test_uncertainty_computing_key_present(translations):
    assert "uncertainty.computing" in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py::test_uncertainty_computing_key_present -v`
Expected: FAIL — key not present.

- [ ] **Step 3: Add the i18n key**

In `sespy/translations/core.json`, inside the `"translation"` object, add (keep valid JSON — mind the comma; UTF-8, keep accents/Greek exactly):

```json
    "uncertainty.computing": {
      "en": "Computing uncertainty (Monte Carlo)…",
      "es": "Calculando incertidumbre (Monte Carlo)…",
      "fr": "Calcul de l'incertitude (Monte-Carlo)…",
      "de": "Unsicherheit wird berechnet (Monte-Carlo)…",
      "lt": "Skaičiuojamas neapibrėžtumas (Monte Karlo)…",
      "pt": "A calcular incerteza (Monte Carlo)…",
      "it": "Calcolo dell'incertezza (Monte Carlo)…",
      "no": "Beregner usikkerhet (Monte Carlo)…",
      "el": "Υπολογισμός αβεβαιότητας (Monte Carlo)…"
    }
```

- [ ] **Step 4: Run i18n tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS (the new presence test + the existing per-language completeness test).

- [ ] **Step 5: Refactor the Leverage module to async**

In `sespy/modules/analysis_leverage.py`:

a) Add imports near the top of the file (with the other stdlib/third-party imports):
```python
import asyncio
import logging
from shiny.types import SilentException
```
and a module-level sentinel (after the imports, before the module funcs):
```python
_COMPUTING = object()
```

b) Replace the whole `@reactive.calc def uncertainty(): ...` block (currently ~lines 158-167) with:
```python
    unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>
    _gen = [0]                                  # plain cell — NOT reactive (avoids self-loop)

    @reactive.extended_task
    async def _unc_task(isa, n_samples, gen):
        result = await asyncio.to_thread(
            net_analysis.uncertainty_scores, isa, n_samples=n_samples, seed=0,
        )
        return (gen, result)

    @reactive.effect
    def _unc_trigger():
        _gen[0] += 1
        gen = _gen[0]
        if not input.show_uncertainty():
            unc_state.set(None)
            return
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        n = int(input.n_samples() or 100)
        unc_state.set(_COMPUTING)
        _unc_task(isa, n, gen)

    @reactive.effect
    def _unc_observe():
        try:
            gen, result = _unc_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("leverage uncertainty task failed")
            unc_state.set(None)
            return
        if gen != _gen[0]:
            return
        unc_state.set(result)
```

c) In `leverage_table()` (currently ~179-181) replace:
```python
        unc = uncertainty()
        if unc is None:
            return pd.DataFrame(rows, columns=base_cols)

        lev = unc.get("leverage", {})
```
with:
```python
        unc = unc_state.get()
        data = unc if isinstance(unc, dict) else None   # None when idle OR computing
        if data is None:
            return pd.DataFrame(rows, columns=base_cols)

        lev = data.get("leverage", {})
```
(the rest of `leverage_table` is unchanged.)

d) Add a "computing…" caption output. In the module UI (the `ui.div(...)` holding the table — right after `ui.output_data_frame("leverage_table"),`), add:
```python
                ui.output_ui("uncertainty_status"),
```
and in the server, add the render:
```python
    @output
    @render.ui
    def uncertainty_status():
        if unc_state.get() is _COMPUTING:
            return ui.p(t("uncertainty.computing"), class_="text-muted")
        return ui.div()
```

- [ ] **Step 6: Verify the app builds + leverage e2e still green**

Run: `micromamba run -n shiny python -c "import app; print('ok')"` → `ok`.
Then (server must be running on :8000): `micromamba run -n shiny python tests/test_leverage_e2e.py`
Expected: PASS — the e2e already polls up to 30×1 s (`for _ in range(30)`) for the `CI` column header, so it waits through the async "computing…" state; the CI column appears when the worker thread finishes (~4 s at n_samples=50).

- [ ] **Step 7: Commit**

```bash
git add sespy/translations/core.json sespy/modules/analysis_leverage.py tests/test_i18n.py
git commit -m "feat(leverage): offload uncertainty Monte Carlo to a worker thread (#4)"
```

---

### Task 2: Loops module async offload

**Files:**
- Modify: `sespy/modules/analysis_loops.py` (imports; replace `@reactive.calc uncertainty_loops()` ~186-199 with the machinery + a read helper; `classification_summary()` caption ~203)
- Test: existing `tests/test_loops_e2e.py` (verify still green; optional caption assertion)

**Interfaces:**
- Consumes: `uncertainty.computing` i18n key (Task 1); the same mechanism shape as Task 1, plus the `cycles` argument.

- [ ] **Step 1: Refactor the Loops module to async**

In `sespy/modules/analysis_loops.py`:

a) Add imports near the top:
```python
import asyncio
import logging
from shiny.types import SilentException
```
and a module-level sentinel:
```python
_COMPUTING = object()
```

b) Replace the whole `@reactive.calc def uncertainty_loops(): ...` block (currently ~186-199) with the machinery **plus** a read helper that keeps the `{loop_id: loop}` shape `loops_table()` already consumes:
```python
    unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>
    _gen = [0]                                  # plain cell — NOT reactive (avoids self-loop)

    @reactive.extended_task
    async def _unc_task(isa, cycles, n_samples, gen):
        result = await asyncio.to_thread(
            net_analysis.uncertainty_scores, isa,
            cycles=cycles, n_samples=n_samples, seed=0,
        )
        return (gen, result)

    @reactive.effect
    def _unc_trigger():
        _gen[0] += 1
        gen = _gen[0]
        if not input.show_uncertainty():
            unc_state.set(None)
            return
        cycles = detected.get()
        if not cycles:
            unc_state.set(None)
            return
        isa = project_data.get().isa_data
        n = int(input.n_samples() or 100)
        unc_state.set(_COMPUTING)
        _unc_task(isa, cycles, n, gen)

    @reactive.effect
    def _unc_observe():
        try:
            gen, result = _unc_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("loops uncertainty task failed")
            unc_state.set(None)
            return
        if gen != _gen[0]:
            return
        unc_state.set(result)

    @reactive.calc
    def uncertainty_loops() -> dict[str, dict]:
        unc = unc_state.get()
        if not isinstance(unc, dict):
            return {}
        return {lp["id"]: lp for lp in unc["loops"]}
```
(`loops_table()` is unchanged — it calls `uncertainty_loops()` and its `if not unc:` guard works because the helper returns `{}` when idle/computing.)

c) Add the "computing…" caption to `classification_summary()`. Replace its final `return ui.div(...)` (currently ~215-219) with a children list that prepends the caption when computing:
```python
        children = []
        if unc_state.get() is _COMPUTING:
            children.append(ui.p(t("uncertainty.computing"), class_="text-muted"))
        children += [
            line("reinforcing"), line("balancing"), line("oscillating"),
            ui.tags.div(t("loops.oscillating_disclaimer"),
                        class_="text-muted", style="font-size: 0.72rem; margin-top: 6px;"),
        ]
        return ui.div(*children)
```

- [ ] **Step 2: Verify the app builds**

Run: `micromamba run -n shiny python -c "import app; print('ok')"` → `ok`.

- [ ] **Step 3: Verify the loops e2e still green**

(server running on :8000) `micromamba run -n shiny python tests/test_loops_e2e.py`
Expected: PASS — the e2e detects loops, toggles uncertainty, and polls for the probability column headers; they appear when the worker thread completes. The base classification/table assertions are unaffected (never blocked).

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/analysis_loops.py
git commit -m "feat(loops): offload uncertainty Monte Carlo to a worker thread (#4)"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  (incl. the new `uncertainty.computing` presence test + the per-language completeness test).
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`. `test_leverage_e2e.py` and `test_loops_e2e.py` must pass (they already poll for the async CI/probability columns).
- [ ] Manual sanity (optional): toggle uncertainty on the Leverage/Loops page with `n_samples=500` — the UI stays responsive (nav clickable, "computing…" caption shows) instead of freezing ~39 s; CIs fill in when done.

## Notes for the reviewer

- The extended-task machinery is intentionally duplicated across the two modules (not a shared factory): the genuinely-shared surface is one line, the triggers differ (Loops needs `cycles`), and inline matches the shipped `ai_isa_wizard.py` idiom. This is the YAGNI call recorded in the spec.
- The generation counter is **required** (not optional): Shiny's `ExtendedTask.invoke()` queues rather than cancels, and `_done_callback` flushes a `status="success"` for the superseded run before the queued run starts — without the `gen` guard, the observe would display stale CIs. (Source-verified in the spec review.)
