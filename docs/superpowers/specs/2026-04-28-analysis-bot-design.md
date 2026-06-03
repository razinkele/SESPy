# Analysis: BOT (Behaviour Over Time) Module — Design

Date: 2026-04-28
Status: **Implemented** · merged to `main` 2026-04-29 at commit `0afd7e9` (14 commits from `feat/analysis-bot`, fast-forward). Case 8 of the e2e suite was deferred during the original plan and shipped as a follow-up direct-to-main commit `f623b83` later the same day; all 8 e2e cases now pass. LOC and signature estimates below were not corrected post-merge — `_compute_trend` is `_compute_trend(years, values)` (§2 was updated to match); the element-picker label format shipped as the full type string (e.g. `"Drivers · Tourism"`) rather than the spec's one-letter prefix (§1 was updated to match). The module-signature contract changed in commit `af051c1` (2026-04-30) — `project_data` is now `reactive.Value[Project]`; the BOT module's element-list reads moved from `project_data.get().elements` to `project_data.get().isa_data.elements`. **Post-implementation note**: i18n keys added to `core.json` MUST go inside the top-level `"translation"` wrapper object — `Translator._load_one` reads `raw.get("translation", {})`, so keys at the file root are silently invisible. This trap was discovered during PIMS implementation (after BOT had shipped); BOT's keys were correctly nested but future modules in this spec's lineage (SP3, SP4) must do the same.
Source module in R app:
- `../SESToolbox/MarineSABRES_SES_Shiny/modules/analysis_bot.R` (489 LOC)

Supersedes the followup brief at `docs/superpowers/specs/2026-05-11-analysis-bot-followup.md`. Open questions in that brief are resolved below.

## 1. Scope

Port the R `analysis_bot` (Behaviour Over Time) module to SESPy. This is module #14, structurally distinct from prior analysis modules: per-element time-series rather than network-graph analysis. No shared numerics with `sespy/dynamics.py` or `sespy/network.py`.

**In scope:**
- Per-element time-series visualization for one selected ISA element at a time.
- Three input modes: manual entry, CSV upload, ISA-derived synthetic series (with watermark).
- Time-period slider (default 1950–2030, matching R).
- Linear trend line overlay (toggleable).
- Moving average overlay (toggleable, window 2–10).
- Summary statistics block (mean, sd, min, max, slope of trend).
- Per-element data table view + CSV download.

**Out of scope (deferred — R itself ships these as "coming soon"):**
- Pattern detection tab.
- Scenario comparison tab.

These can be re-added later via a one-line nav addition once the underlying logic exists in either codebase.

**Open questions resolved (from followup brief):**

| Question | Decision |
|---|---|
| Element picker label format | Spec decision was type-letter prefix `"G · <label>"` (Q1 → C). **Shipped reality**: `analysis_bot.py:134` uses the full type string `f"{el.type} · {el.label}"` (e.g., `"Drivers · Tourism"`, `"Pressures · Eutrophication"`) — clearer for users at the cost of slightly longer labels. Shipped form is the live convention. |
| CSV column-name flexibility | Case-insensitive matching: `Year/year/YEAR`, `Value/value/VALUE/Measurement/measurement` (Q2 → B). Mirrors `excel_import.py` tolerance. |
| Synthetic ISA mode | Kept, with figure watermark + `"⚠ Demo data"` legend prefix (Q3 → C). Demo-friendly without misinterpretation trap. |
| Pattern Detection / Comparison tabs | Omit both entirely (Q4 → A). SESPy convention is to ship features when they work. |

## 2. Architecture

### New files

- `sespy/modules/analysis_bot.py` — UI + server (~295–340 LOC). Pattern: matches `sespy/modules/analysis_metrics.py` for the `@render.plot` matplotlib style.
- `tests/test_bot_e2e.py` — Playwright e2e (~80–100 LOC).
- `tests/fixtures/bot_sample.csv` — 5 rows, headers `Year,Value`.
- `tests/fixtures/bot_lowercase.csv` — 5 rows, headers `year,value`.
- `tests/fixtures/bot_missing_value_col.csv` — 5 rows, headers `Year,Notes`.

### No new helper module

Linear regression and moving averages are 2–3 line calls (`np.polyfit(years, values, 1)` and `pd.Series.rolling(window).mean()`). Inline as private `_compute_trend(years, values)` and `_moving_average(values, window)` in the module file. (Note: `_compute_trend` takes both args because `np.polyfit` requires the x-axis (years); an earlier draft of this spec said `_compute_trend(values)` — the shipped two-arg signature is the live one.)

**Promotion criterion:** if either helper grows beyond ~10 LOC during implementation, factor into `sespy/bot.py` and add `tests/test_bot.py`. Decision deferred to implementation phase.

### Wire-up changes (app.py)

Four touch points, mirroring the Boolean+Simulation precedent:

- **`NAV`** — append `NavItem(id="bot", icon="chart-area", label="Behaviour Over Time", label_key="nav.bot")`. Insert after `simulation` and before `intervention` to follow the R workflow ordering.
- **`NAV_TO_STEP`** — `"bot": "analyze"`.
- **`PANELS`** — add `ui.nav_panel("Behaviour Over Time", analysis_bot_ui("bot"), value="bot")` in the same position as the NAV entry.
- **Server registration** — `analysis_bot_server("bot", project_data, event_bus, T)`.

### Wire-up changes (translations)

`sespy/translations/core.json` — add ~32 keys plus 1 nav key:

```
nav.bot
bot.title, bot.description
bot.element_picker, bot.data_source, bot.source_manual, bot.source_csv, bot.source_isa
bot.year, bot.value, bot.add_point, bot.upload_csv, bot.upload_help
bot.year_range, bot.show_trend, bot.show_moving_avg, bot.window_size
bot.tab_timeseries, bot.tab_data, bot.download_csv
bot.summary_mean, bot.summary_sd, bot.summary_min, bot.summary_max, bot.summary_slope
bot.no_data_yet, bot.no_element_selected, bot.synthetic_warning, bot.synthetic_legend
bot.csv_error, bot.csv_no_rows, bot.stale_warning
```

English keys first; the other 8 languages (es, fr, de, lt, pt, it, no, el) get the same keys with English placeholder values. Same pattern as Boolean+Simulation.

### README

Bump module count `13 → 14`, add row to module table, update test count.

### Dependencies

None. matplotlib + pandas + numpy already in `pyproject.toml`.

### Schema / persistence

No changes to `sespy/data_structure.py`, `sespy/project_io.py`, or `sespy/event_bus.py`. BOT data is **session-only**, matching R's `bot_rv$timeseries_data`. Not persisted across project save/load.

## 3. Components & Data Flow

### Reactive stores (module-local)

- `bot_data_store: reactive.value[dict[str, pd.DataFrame]]` — maps `element_id` to its `Year, Value` frame. Empty dict initially. Per-element keying ensures switching elements preserves each element's data independently.
- `bot_error_store: reactive.value[str | None]` — last user-facing error message; `None` when clean.

### Effects (write to stores)

- **`_handle_manual_add`** — `@reactive.event(input.add_point, ignore_init=True)`. Reads `int(input.year() or 0)` + `float(input.value() or 0)` + `input.element()`. If no element selected, no-op silently. **Match on year only:** if a row with that year already exists for that element, replace its value; else append a new row.
- **`_handle_csv_upload`** — `@reactive.event(input.csv_upload, ignore_init=True)`. Reads pandas via case-insensitive column match. **Replaces** the active element's frame (no append). Errors surface to `bot_error_store` with `t("bot.csv_error")` or `t("bot.csv_no_rows")`. If no element selected, errors with `t("bot.no_element_selected")`.
- **`_handle_isa_synthetic`** — `@reactive.event(input.element, input.data_source, input.year_range, ignore_init=True)`. Active only when `data_source == "isa"`. Generates deterministic series:
  - **Seed**: `hash(element_id) & 0xFFFFFFFF` — same element always produces same series.
  - **Noise scale**: derived from `element.confidence` (an `int` in 1–5; default 3). Lower confidence = noisier series. Mapping: `noise_scale = (6 - confidence) * 0.15` so confidence 5 → 0.15, confidence 1 → 0.75. Defended with `confidence or 3` for missing values.
  - **Range**: `input.year_range()` slider values (default 1950–2030).
- **`_stale_warning`** — subscribes to `event_bus.isa_change`, reads `bot_data_store.get()` inside `with reactive.isolate():`. On upstream element deletion: remove that key from the dict; if it was the active selection, clear and post `t("bot.stale_warning")` notification. Without `isolate()`, every successful manual-add re-fires the warning — same trap Boolean module hit.

### Computed values (`@reactive.calc`)

- **`_active_frame()`** — `bot_data_store.get().get(input.element())`, or `None` if missing.
- **`_filtered_frame()`** — `_active_frame()` clipped to `input.year_range()`.
- **`_trend_coeffs()`** — `np.polyfit(years, values, 1)` if `input.show_trend()` and frame has ≥ 2 rows; `None` otherwise. Wrapped in `try/except (ValueError, np.linalg.LinAlgError)`.
- **`_summary_stats()`** — dict of `{mean, sd, min, max, slope}` if frame is non-empty; `None` otherwise.

### Renderers

- **`@render.plot bot_plot`** — matplotlib line + optional trend line + optional moving-average line. Synthetic-mode adds `fig.text(0.5, 0.5, t("bot.synthetic_warning"), alpha=0.2, ha="center", va="center", fontsize=36, transform=fig.transFigure)` watermark + `t("bot.synthetic_legend")` prefix on the data series legend.
- **`@render.ui bot_summary`** — stats block from `_summary_stats()`; or `alert-danger` div from `bot_error_store`; or `t("bot.no_data_yet")` placeholder when both stats and error are `None`.
- **`@render.data_frame bot_table`** — `_filtered_frame()`.
- **`@render.download bot_download`** — CSV bytes from `_filtered_frame()`.

### Data flow

```
Manual:   add_point click  → _handle_manual_add    ─┐
CSV:      csv_upload event → _handle_csv_upload    ─┼─→ bot_data_store[element_id]
ISA:      element/mode/range → _handle_isa_synthetic┘

bot_data_store → _active_frame → _filtered_frame ─→ all renderers
                                                  ╲→ _trend_coeffs → bot_plot
                                                   ╲→ _summary_stats → bot_summary
```

One funnel, three sources. Mode switching never mutates the store; only mode-specific input actions write.

## 4. Error Handling

### Boundary catches (try/except)

- **`_handle_csv_upload`** — catches `Exception` (pandas read surface is wide: `pd.errors.ParserError`, `UnicodeDecodeError`, `KeyError`, `FileNotFoundError`). Writes `t("bot.csv_error")` to `bot_error_store`.
- **`_handle_manual_add`** — `int()`/`float()` parse failures caught as `ValueError`. Writes a generic format error.
- **`_trend_coeffs`** — `(ValueError, np.linalg.LinAlgError)`. Returns `None`; renderer skips the overlay silently.
- **`_moving_average`** — `n < window` returns the input unmodified; renderer skips overlay.

### Validation rules (write `bot_error_store`, no exception)

| Condition | Behavior |
|---|---|
| Empty `_active_frame` | Renderers show `t("bot.no_data_yet")`; not an error. |
| Year out of slider range | Clipped silently. |
| CSV with extra columns | Ignored (use only matched two). |
| CSV with no rows after column-match | Error `t("bot.csv_no_rows")`. |
| Manual-add with year already present | Replace, not duplicate; no warning. |
| Manual-add with no element selected | Silent no-op. |
| CSV upload with no element selected | Error `t("bot.no_element_selected")`. |
| Upstream deletion of selected element | Remove key, clear selection, notify. |

### No fatal paths

No `req(False)`. Every failure mode lands as either a stored error string or a silent skip with a placeholder.

## 5. Testing

### Unit tests

**None required initially.** `_compute_trend` and `_moving_average` are 2–3 line numpy/pandas calls. Promote to `sespy/bot.py` and add `tests/test_bot.py` only if either grows beyond ~10 LOC during implementation.

### E2e tests (`tests/test_bot_e2e.py`)

Eight cases:

1. **Manual entry happy path** — load Minimal Demo, navigate to BOT, pick element, enter 3 `(year, value)` pairs, assert plot renders + summary stats populate + table shows 3 rows.
2. **CSV upload happy path** — upload `bot_sample.csv`, assert plot + summary + table.
3. **CSV column-name flexibility** — upload `bot_lowercase.csv`, assert success.
4. **CSV bad data** — upload `bot_missing_value_col.csv`, assert `alert-danger` div appears with text matching `t("bot.csv_error")`.
5. **Synthetic ISA mode** — switch `data_source` to "isa", assert plot renders + watermark text appears in figure.
6. **Trend toggle** — enable trend checkbox, assert plot re-renders without crash. No numerics assertion.
7. **Element switch preserves per-element data** — enter 3 points on element A, switch to B, enter 2 points, switch back to A, assert 3 points still present.
8. **Stale-data warning** — enter data for element X, then delete element X via Edit Data, assert notification appears.

**Out of scope** — Pattern Detection / Comparison tabs (omitted), CSV download contents (Shiny `@render.download` is well-tested; just check the link exists).

## 6. Architectural conventions to reuse

These are pinned in `sespy_port_context.md` memory and apply directly to BOT:

- **Plotting:** matplotlib via `@render.plot`. Never plotly. Match `analysis_metrics.py` style.
- **Stale-data reactives:** `event_bus.isa_change.get()` triggers; `bot_data_store.get()` reads inside `with reactive.isolate():`. Without isolate, the warning fires after every store write (every successful add/upload/regen) — same trap Boolean module hit on its Run button, but BOT writes more frequently so the bug would be more visible.
- **Action buttons:** `@reactive.event(input.add_point, ignore_init=True)` is required. Action buttons start at 0, not None — without `ignore_init`, the default fires once at session init.
- **Defensive input reads:** `int(input.year() or 0)` and similar — Shiny inputs return `None` when fields are cleared.
- **Error handling:** symmetric — catch at boundaries, write to error store, render `class="alert alert-danger"` div from stored string.
- **i18n:** `from ..i18n import t`; call `t("bot.<key>")` directly. UI labels constructed at `@module.ui` time capture the current language (page-reload pattern); `@render.ui` labels update reactively.
- **Reactive self-write:** any reactive that reads-and-writes the same store needs `with reactive.isolate():` on the read side.

## 7. Roll-out plan

1. Branch: `feat/analysis-bot` (off `main`).
2. Implementation order: module file → e2e tests + fixtures → wire-up (app.py) → i18n batch → README.
3. Local Playwright run (8 cases) before pushing.
4. Merge to `main` when green.

## 8. Estimated effort

~3–6 hours of clock time including reviews, based on the Boolean+Simulation cadence and BOT's smaller surface area (one module file vs two; no shared numerics layer to build first; no schema change).

## 9. Risks / known unknowns

- **Synthetic mode realism:** `element.confidence` is an `int` 1–5 (default 3). Defend with `confidence or 3` for missing values to avoid `KeyError` in the noise-scale mapping.
- **Watermark in headless tests:** matplotlib's `fig.text` should render in `@render.plot` PNG output, but the e2e watermark assertion may need to inspect the figure's text artists rather than the PNG. Backup approach: assert the legend prefix text is present in the rendered HTML legend.
- **Element picker on empty project:** if `project_data.get().isa_data.elements` is empty (path post-`af051c1`; spec was authored against the older `project_data.get().elements` shape), the selectize choices dict is empty. Renderer should show `t("bot.no_element_selected")` placeholder rather than an empty selector.
