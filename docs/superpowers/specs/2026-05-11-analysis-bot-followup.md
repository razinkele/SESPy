# Analysis: BOT (Behaviour Over Time) Module — Follow-up Spec

> **⚠ SUPERSEDED — 2026-04-29.** This brief was written as a launch point for a future session, but the BOT port shipped on 2026-04-29 (merged to `main` at `0afd7e9`). The full design lives at [`2026-04-28-analysis-bot-design.md`](./2026-04-28-analysis-bot-design.md) — open questions Q1–Q4 below are resolved in §1 of that spec. This file is retained as historical context only; the "When to revisit" guidance at the bottom is no longer applicable.
>
> **Note on filename date:** the filename prefix `2026-05-11` reflects the deferred earliest-start date (see "Earliest start" line below), NOT the authoring date. The file was written on 2026-04-28. Renaming to `2026-04-28-analysis-bot-followup.md` would match the authoring-date convention used by every other spec in this directory; left as-is to preserve git history and to match the cross-reference at the top of `2026-04-28-analysis-bot-design.md`.

Date written: 2026-04-28
Earliest start: 2026-05-11 (or whenever you pick this up)
Status: ~~Deferred~~ Superseded by `2026-04-28-analysis-bot-design.md` (shipped 2026-04-29).

## What this is

A spec stub for porting the R MarineSABRES `analysis_bot` (Behaviour Over Time) module into SESPy. Independent of `sespy/dynamics.py` — no shared numerics — and structurally different from the other analysis modules: per-element time-series rather than network-graph analysis.

This file is **not a fully reviewed spec** like `2026-04-27-analysis-boolean-simulation-design.md`. It is a starting brief so that a future session can spin up the full brainstorm → spec → plan → implement flow without re-doing the discovery work.

## Source

- R module: `../SESToolbox/MarineSABRES_SES_Shiny/modules/analysis_bot.R` (489 R LOC).
- R UI structure: left panel (data input + analysis options) + right tabset (Time Series, Pattern Detection, Data, Comparison).
- R server uses `bot_rv$timeseries_data` (a `data.frame(Year, Value)` reactive) as the source of truth.

## Recommended scope (matches the Boolean+Simulation precedent)

**In scope (core + headline features):**
- Per-element time-series visualization for one selected ISA element at a time.
- Three data sources: manual entry (Year + Value form), CSV upload, ISA-data-derived (placeholder fallback when actual time-series isn't in the project — the R version uses synthetic series too).
- Time period slider (the R default is 1950–2030).
- Trend line (linear regression overlay) — toggleable.
- Moving average — toggleable, with adjustable window size (R uses 2–10).
- Summary statistics block (mean, sd, min, max, slope of trend).
- Per-element data table view + CSV download.

**Deferred to a future spec (R has these as "coming soon"):**
- Pattern detection (the R Pattern Analysis tab is gated behind `detect_patterns` checkbox and the R UI itself says coming-soon for the underlying detector).
- Scenario comparison (the R Comparison tab is explicitly labeled "coming soon").

## Recommended architecture

**No new helper file required.** Unlike Boolean+Simulation, BOT does not have substantial standalone numerics. Linear regression and moving averages are 5-line numpy/pandas calls; inline them in the module file.

**New files:**
- `sespy/modules/analysis_bot.py` (~280–320 LOC estimated). Pattern: matches `sespy/modules/analysis_metrics.py` for the matplotlib `@render.plot` style.
- `tests/test_bot_e2e.py` (~80 LOC).

**No new unit-test file** unless inline numerics get non-trivial. If a `_compute_trend(values)` or `_moving_average(values, window)` helper grows beyond 10 LOC each, factor them into `sespy/bot.py` and add a `tests/test_bot.py` — but probably overkill for this scope. *(Shipped reality: `_compute_trend` ended up as `_compute_trend(years, values)` with both args; see main BOT spec §2.)*

**Wire-up changes (same checklist as before):**
- `sespy/translations/core.json` — add `nav.bot` and `bot.*` keys (~30 keys following the boolean/simulation pattern).
- `app.py` — register the module in NAV / NAV_TO_STEP / PANELS / server.
- `README.md` — bump module count from 13 → 14.

**No deps changes.** Matplotlib + pandas are already pulled.

## Architectural conventions to reuse (from `sespy_port_context.md` memory)

- **Plotting:** matplotlib via `@render.plot`, never plotly. Match `analysis_metrics.py` style.
- **Stale-data warning:** subscribe to `event_bus.isa_change` inside a `@reactive.effect`, read `bot_data_store.get()` inside `with reactive.isolate():`. Without isolate, the warning fires after every Run — same trap as the Boolean module hit.
- **Action buttons:** `@reactive.event(input.X, ignore_init=True)` is required (action buttons start at 0, not None).
- **Defensive input reads:** `int(input.x() or default)` — Shiny inputs can return `None` when fields are cleared; matches `analysis_loops.py` style.
- **Error handling:** `try/except (ValueError, np.linalg.LinAlgError)` (or just `Exception` since BOT doesn't do eigenvalues). Surface error strings into the result store; the renderers display a `class="alert alert-danger"` div from a stored error rather than `req(False)`-ing into a blank tab.
- **i18n:** `from ..i18n import t` and call `t("bot.<key>")` directly. UI labels constructed at `@module.ui` time capture the language; `@render.ui` labels update reactively. The page-reload pattern for static labels is acceptable.

## Things to decide during the brainstorming step

1. **Element picker shape.** R uses `selectInput` with prefixed labels like `"G&B: <name>"`. SESPy's `Element.type` is the DAPSIWRM letter — `selectize` with `f"{el.type} · {el.label}"` (matching `analysis_intervention.py:178-185`) is more consistent.

2. **CSV schema.** R accepts a 2-column CSV (Year, Value). Decide whether to allow alternate column names (`year/Year`, `value/Value`, etc.) like `excel_import.py` already does for ISA data. Probably yes — code reuse is small.

3. **"ISA data" mode synthetic series.** The R version generates a synthetic time-series when the user picks "use ISA data" since real time-series don't exist in the project schema. Decide whether to:
   (a) Mirror that — synthetic series based on the element's `confidence` field as a noise scale, so it varies per element.
   (b) Drop the option and require manual or CSV input.
   (b) is more honest; (a) is more demo-friendly. Lean (b) unless the user pushes back.

4. **Persistence.** R's `bot_rv$timeseries_data` is session-only. Match that — no project-schema changes (otherwise this becomes a much bigger task touching `data_structure.py` and `project_io.py`).

## Risks / open questions

- The R module's "Pattern Detection" tab is in scope per the R UI but the underlying detector is unimplemented. Confirm with user during brainstorm whether that tab should appear at all in SESPy or just be skipped.
- Existing CSV-import infrastructure (`excel_import.py`) is Excel-shaped. Plain CSV upload uses pandas directly; keep it lightweight.
- The R module shows `dygraphOutput` (interactive line chart with zoom). SESPy decision precedent (Boolean+Simulation spec) was matplotlib over plotly. Stay matplotlib here too — the trajectory plot in `analysis_simulation.py` already shows matplotlib handles 17-line overlays cleanly.

## Workflow for the future session

1. `git checkout -b feat/analysis-bot`
2. Brainstorm via `superpowers:brainstorming` — confirm the four open questions above.
3. Write a full spec at `docs/superpowers/specs/YYYY-MM-DD-analysis-bot-design.md`.
4. Plan via `superpowers:writing-plans` using the Boolean+Simulation plan as the structural template.
5. Execute via `superpowers:subagent-driven-development`. Estimated 6–10 implementer dispatches.
6. Merge to main when done.

## Estimated effort

~3–6 hours of clock time including reviews, based on the Boolean+Simulation cadence and BOT's smaller surface area (one module file vs two, no shared numerics layer to build first).

## When to revisit

No deadline. Pick this up when you have a clear afternoon and want SESPy to reach 14 modules. The R app stays the source of truth in the meantime.
