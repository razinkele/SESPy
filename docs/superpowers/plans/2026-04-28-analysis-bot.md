# Analysis: BOT (Behaviour Over Time) Module — Implementation Plan

> **Status: Implemented** · 14 plan tasks shipped on `feat/analysis-bot`, fast-forwarded to `main` 2026-04-29 (head `0afd7e9`). Case 8 of the e2e (deferred during the plan as Step 11 case 8) shipped as a follow-up direct-to-main commit `f623b83` later the same day. The plan's `project_data: reactive.Value[IsaData]` module signature was subsequently changed to `reactive.Value[Project]` by the architectural refactor in commit `af051c1` (2026-04-30); current code uses `project_data.get().isa_data` where the plan shows `project_data.get()`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the R `analysis_bot` (Behaviour Over Time) module to SESPy as module #14 — a per-element time-series view with three input modes (manual, CSV, ISA-derived synthetic), trend / moving-average overlays, summary stats, and per-element data persistence within the session.

**Architecture:** Single new module file `sespy/modules/analysis_bot.py` (~295–340 LOC) with inline numerics. Per-element data store keyed by `element_id`. No new helper module, no schema change, no new dependencies. Pattern matches `sespy/modules/analysis_metrics.py` for matplotlib `@render.plot` style and `sespy/modules/analysis_boolean.py` for the symmetric error-handling pattern.

**Tech Stack:** Python 3.11, micromamba env `shiny`, numpy, pandas, matplotlib, Shiny for Python, Playwright (for e2e).

**Spec reference:** `docs/superpowers/specs/2026-04-28-analysis-bot-design.md`. When in doubt, the spec is authoritative.

**Working directory:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy`. All shell commands assume this is the cwd. Use forward slashes.

**Environment:** `micromamba run -n shiny <cmd>`. Never `pip install`.

**Git:** SESPy is a git repo (initialized 2026-04-27). Branch off `main` to `feat/analysis-bot`. Commit per task.

---

## Task 0: Verify environment and branch

**Files:** none (read-only sanity checks + branch creation)

- [ ] **Step 1: Verify `shiny` env has needed packages**

Run:
```bash
micromamba run -n shiny python -c "import numpy, pandas, shiny, matplotlib; print('ok')"
```
Expected: prints `ok`.

If it fails, stop and ask the user to fix the environment. Do not proceed.

- [ ] **Step 2: Verify the existing test suite is green before changes**

Run:
```bash
micromamba run -n shiny pytest tests/ -q -k "not e2e"
```
Expected: tests pass. If any pre-existing failures, note them but proceed — they're not caused by this work.

- [ ] **Step 3: Confirm the spec exists**

Run:
```bash
ls docs/superpowers/specs/2026-04-28-analysis-bot-design.md
```
Expected: file exists.

- [ ] **Step 4: Create and switch to the feature branch**

Run:
```bash
git checkout -b feat/analysis-bot
git status
```
Expected: on branch `feat/analysis-bot`, nothing to commit.

---

## Task 1: Add CSV fixtures

**Files:**
- Create: `tests/fixtures/bot_sample.csv`
- Create: `tests/fixtures/bot_lowercase.csv`
- Create: `tests/fixtures/bot_missing_value_col.csv`

- [ ] **Step 1: Create `tests/fixtures/` if it does not exist**

Run:
```bash
mkdir -p tests/fixtures
```

- [ ] **Step 2: Create `tests/fixtures/bot_sample.csv`** with exact content:

```
Year,Value
1990,12.5
1995,14.2
2000,15.8
2005,17.1
2010,18.6
```

- [ ] **Step 3: Create `tests/fixtures/bot_lowercase.csv`** with exact content:

```
year,value
1990,12.5
1995,14.2
2000,15.8
2005,17.1
2010,18.6
```

- [ ] **Step 4: Create `tests/fixtures/bot_missing_value_col.csv`** with exact content:

```
Year,Notes
1990,baseline
1995,decline
2000,recovery
2005,stable
2010,increase
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/
git commit -m "test(fixtures): add BOT module CSV fixtures"
```

---

## Task 2: Add i18n keys (English first)

**Files:**
- Modify: `sespy/translations/core.json`

The translations file holds all 9 languages keyed by ISO code. Add the new keys under `en` first; the other 8 languages get the same keys with English placeholder values, matching the pattern used when Boolean/Simulation were added.

- [ ] **Step 1: Read the current structure of core.json**

Run:
```bash
head -40 sespy/translations/core.json
```
Note where the `en` block lives, the indent style, and the comma-placement convention.

- [ ] **Step 2: Add these key/value pairs under `en`** (place them near other `nav.*` and module keys; group them together as a `bot.*` block):

```json
"nav.bot": "Behaviour Over Time",
"bot.title": "Behaviour Over Time",
"bot.description": "Per-element time-series visualisation with trend and moving-average overlays.",
"bot.element_picker": "Element",
"bot.data_source": "Data source",
"bot.source_manual": "Manual entry",
"bot.source_csv": "CSV upload",
"bot.source_isa": "ISA-derived (demo)",
"bot.year": "Year",
"bot.value": "Value",
"bot.add_point": "Add point",
"bot.upload_csv": "Upload CSV",
"bot.upload_help": "CSV with Year and Value columns (case-insensitive).",
"bot.year_range": "Year range",
"bot.show_trend": "Show trend line",
"bot.show_moving_avg": "Show moving average",
"bot.trend_label": "Trend",
"bot.moving_avg_label": "Moving avg",
"bot.window_size": "Moving-average window",
"bot.tab_timeseries": "Time series",
"bot.tab_data": "Data",
"bot.download_csv": "Download CSV",
"bot.summary_mean": "Mean",
"bot.summary_sd": "Std. dev.",
"bot.summary_min": "Min",
"bot.summary_max": "Max",
"bot.summary_slope": "Trend slope",
"bot.no_data_yet": "No data yet — pick an element and add data points or upload a CSV.",
"bot.no_element_selected": "Pick an element first.",
"bot.synthetic_warning": "DEMO DATA",
"bot.synthetic_legend": "⚠ Demo",
"bot.csv_error": "Could not read CSV — expected columns Year and Value.",
"bot.csv_no_rows": "CSV has no usable rows.",
"bot.stale_warning": "Selected element was deleted upstream — data cleared."
```

- [ ] **Step 3: Add the same 34 keys under each of `es`, `fr`, `de`, `lt`, `pt`, `it`, `no`, `el`** — values are English placeholders identical to the `en` block. Same pattern as Boolean/Simulation.

- [ ] **Step 4: Verify JSON is valid**

Run:
```bash
micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json'))"
```
Expected: no output (success). Any output means the JSON is malformed — fix the comma/brace error.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(bot): add 34 translation keys for BOT module"
```

---

## Task 3: Module skeleton (UI shell, no functionality yet)

**Files:**
- Create: `sespy/modules/analysis_bot.py`

Goal: get the module to import cleanly and render an empty card in the dashboard. We wire it into `app.py` in Task 4.

- [ ] **Step 1: Create `sespy/modules/analysis_bot.py`** with this content:

```python
"""Behaviour Over Time (BOT) analysis module.

Mirrors `modules/analysis_bot.R` (489 LOC). Per-element time-series view
with three input modes (manual entry, CSV upload, ISA-derived synthetic),
trend and moving-average overlays, summary statistics, and a data
table + CSV download.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot, no pyvis)
and `analysis_boolean.py` (symmetric error handling via stored error string).
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import IsaData
from ..event_bus import EventBus
from ..i18n import Translator, t


@module.ui
def analysis_bot_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("bot.title")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("bot.element_picker")),
                ui.output_ui("element_picker_ui"),
                ui.tags.hr(),
                ui.h5(t("bot.data_source")),
                ui.input_radio_buttons(
                    "data_source",
                    None,
                    {
                        "manual": t("bot.source_manual"),
                        "csv": t("bot.source_csv"),
                        "isa": t("bot.source_isa"),
                    },
                    selected="manual",
                ),
                ui.tags.hr(),
                ui.output_ui("input_panel"),
                ui.tags.hr(),
                ui.input_slider(
                    "year_range",
                    t("bot.year_range"),
                    min=1950, max=2030, value=(1950, 2030), step=1, sep="",
                ),
                ui.input_checkbox("show_trend", t("bot.show_trend"), value=True),
                ui.input_checkbox("show_moving_avg", t("bot.show_moving_avg"), value=False),
                ui.input_slider(
                    "window_size", t("bot.window_size"),
                    min=2, max=10, value=3, step=1,
                ),
                width=300,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("bot.tab_timeseries"),
                    ui.output_plot("bot_plot", height="320px"),
                    ui.tags.hr(),
                    ui.output_ui("bot_summary"),
                ),
                ui.nav_panel(
                    t("bot.tab_data"),
                    ui.output_data_frame("bot_table"),
                    ui.tags.hr(),
                    ui.download_button("bot_download", t("bot.download_csv")),
                ),
                id="bot_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_bot_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[IsaData],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    # Per-element time-series data: dict keyed by element_id → DataFrame[Year, Value].
    bot_data_store: reactive.Value[dict[str, pd.DataFrame]] = reactive.value({})
    bot_error_store: reactive.Value[str | None] = reactive.value(None)

    @output
    @render.ui
    def element_picker_ui():
        event_bus.isa_change.get()
        elements = project_data.get().elements
        if not elements:
            return ui.tags.p(t("bot.no_element_selected"), class_="text-muted")
        choices = {el.id: f"{el.type} · {el.label}" for el in elements}
        return ui.input_selectize("element", None, choices=choices)

    @output
    @render.ui
    def input_panel():
        # Placeholder — Task 5 wires the per-mode controls.
        return ui.tags.p("...", class_="text-muted")

    @output
    @render.plot
    def bot_plot():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.text(0.5, 0.5, t("bot.no_data_yet"),
                ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def bot_summary():
        return ui.tags.p(t("bot.no_data_yet"), class_="text-muted")

    @output
    @render.data_frame
    def bot_table():
        return pd.DataFrame(columns=["Year", "Value"])

    @render.download(filename="bot_data.csv")
    def bot_download():
        yield b"Year,Value\n"
```

- [ ] **Step 2: Verify the file imports cleanly**

Run:
```bash
micromamba run -n shiny python -c "from sespy.modules.analysis_bot import analysis_bot_ui, analysis_bot_server; print('ok')"
```
Expected: prints `ok`. Any ImportError or SyntaxError must be fixed before continuing.

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): module skeleton with empty placeholders"
```

---

## Task 4: Wire into app.py

**Files:**
- Modify: `app.py:71-85` (NAV list)
- Modify: `app.py:99-107` (NAV_TO_STEP map)
- Modify: `app.py:109-123` (PANELS tuple)
- Modify: `app.py` (server registration block — find by searching `analysis_simulation_server`)
- Modify: `app.py` (imports block — find by searching `from sespy.modules.analysis_simulation`)

Insert the BOT entries after `simulation` and before `intervention` so the nav order matches the spec (Section 2 Wire-up).

- [ ] **Step 1: Add the import**

The existing module imports are sorted alphabetically by module name. `analysis_bot` belongs between `analysis_boolean` and `analysis_intervention`. Find the multi-line `from sespy.modules.analysis_boolean import (...)` block (around `app.py:31-34`) and insert this line directly after its closing `)`:

```python
from sespy.modules.analysis_bot import analysis_bot_server, analysis_bot_ui
```

- [ ] **Step 2: Add the NAV entry**

In the `NAV` list, insert this line after the `simulation` entry and before the `intervention` entry:

```python
    NavItem(id="bot", icon="chart-area", label="Behaviour Over Time", label_key="nav.bot"),
```

- [ ] **Step 3: Add the NAV_TO_STEP entry**

In the `NAV_TO_STEP` dict, add `"bot"` to the analyze-stage block:

```python
    "leverage": "analyze", "boolean": "analyze", "simulation": "analyze",
    "bot": "analyze",
    "intervention": "analyze", "simplify": "analyze",
```

- [ ] **Step 4: Add the PANELS entry**

In the `PANELS` tuple, insert this line after `Dynamic Simulation` and before `Intervention`:

```python
    ui.nav_panel("Behaviour Over Time", analysis_bot_ui("bot"),                  value="bot"),
```

- [ ] **Step 5: Add the server registration**

The server registrations follow nav order (not alphabetical). Find the closing `)` of the `analysis_simulation_server(...)` block (around `app.py:189-194`) and insert this block directly after it, before `analysis_intervention_server(...)`:

```python
    analysis_bot_server(
        "bot",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 6: Verify the app starts without crashing**

Run:
```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: prints `ok`. ImportError → fix import path; AttributeError → check the kwargs match the existing registrations.

- [ ] **Step 7: Smoke-test in browser**

Run (in a separate terminal):
```bash
micromamba run -n shiny shiny run app.py --port 8000
```
Then open `http://127.0.0.1:8000` in a browser. Click the new "Behaviour Over Time" nav button. Expected: the panel renders with sidebar controls visible and the time-series area showing the "no data yet" placeholder. Stop the server (Ctrl+C) when verified.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat(bot): wire BOT module into app nav, panels, and server"
```

---

## Task 5: Manual-entry mode

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Add the manual-entry input panel (`year` numeric_input + `value` numeric_input + `add_point` action button), the `_handle_manual_add` effect, and update `bot_plot` to render the actual data.

- [ ] **Step 1: Update the `input_panel` renderer to switch on `data_source`**

Replace the existing `input_panel` body with:

```python
    @output
    @render.ui
    def input_panel():
        mode = input.data_source() or "manual"
        if mode == "manual":
            return ui.div(
                ui.input_numeric("year", t("bot.year"), value=2000, min=1900, max=2100, step=1),
                ui.input_numeric("value", t("bot.value"), value=0.0, step=0.1),
                ui.input_action_button(
                    "add_point", t("bot.add_point"),
                    class_="btn btn-primary btn-block",
                ),
            )
        if mode == "csv":
            return ui.div(
                ui.input_file("csv_upload", t("bot.upload_csv"), accept=[".csv"]),
                ui.tags.p(t("bot.upload_help"), class_="text-muted small"),
            )
        # mode == "isa"
        return ui.tags.p(t("bot.upload_help"), class_="text-muted small")
```

- [ ] **Step 2: Add the `_handle_manual_add` effect**

Below the stores, add:

```python
    @reactive.effect
    @reactive.event(input.add_point, ignore_init=True)
    def _handle_manual_add() -> None:
        eid = input.element()
        if not eid:
            return  # silent no-op; spec §4 validation rule
        try:
            year = int(input.year() or 0)
            value = float(input.value() or 0)
        except (TypeError, ValueError):
            bot_error_store.set("Invalid year or value.")
            return
        store = dict(bot_data_store.get())  # copy for immutable swap
        existing = store.get(eid)
        if existing is None or existing.empty:
            store[eid] = pd.DataFrame({"Year": [year], "Value": [value]})
        else:
            mask = existing["Year"] == year
            if mask.any():
                # Match on year only — replace value.
                updated = existing.copy()
                updated.loc[mask, "Value"] = value
                store[eid] = updated
            else:
                store[eid] = pd.concat(
                    [existing, pd.DataFrame({"Year": [year], "Value": [value]})],
                    ignore_index=True,
                )
        bot_data_store.set(store)
        bot_error_store.set(None)
```

- [ ] **Step 3: Add the `_active_frame` and `_filtered_frame` calcs**

Below the manual-add effect, add:

```python
    @reactive.calc
    def _active_frame() -> pd.DataFrame | None:
        eid = input.element()
        if not eid:
            return None
        df = bot_data_store.get().get(eid)
        if df is None or df.empty:
            return None
        return df.sort_values("Year").reset_index(drop=True)

    @reactive.calc
    def _filtered_frame() -> pd.DataFrame | None:
        df = _active_frame()
        if df is None:
            return None
        lo, hi = input.year_range() or (1950, 2030)
        return df[(df["Year"] >= lo) & (df["Year"] <= hi)].reset_index(drop=True)
```

- [ ] **Step 4: Replace `bot_plot` to render the actual data**

Replace the placeholder `bot_plot` body with:

```python
    @output
    @render.plot
    def bot_plot():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3.2))
        df = _filtered_frame()
        err = bot_error_store.get()
        if err:
            ax.text(0.5, 0.5, err, ha="center", va="center",
                    color="#a02020", transform=ax.transAxes, wrap=True)
            ax.axis("off")
            fig.tight_layout()
            return fig
        if df is None or df.empty:
            ax.text(0.5, 0.5, t("bot.no_data_yet"),
                    ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            fig.tight_layout()
            return fig
        ax.plot(df["Year"], df["Value"], marker="o", color="#4a90b8",
                linewidth=2, markersize=5, label=t("bot.value"))
        ax.set_xlabel(t("bot.year"))
        ax.set_ylabel(t("bot.value"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="best")
        fig.tight_layout()
        return fig
```

- [ ] **Step 5: Replace `bot_table` to use `_filtered_frame`**

```python
    @output
    @render.data_frame
    def bot_table():
        df = _filtered_frame()
        if df is None:
            return pd.DataFrame(columns=["Year", "Value"])
        return df
```

- [ ] **Step 6: Replace `bot_download` to use `_filtered_frame`**

```python
    @render.download(filename="bot_data.csv")
    def bot_download():
        df = _filtered_frame()
        if df is None:
            yield b"Year,Value\n"
            return
        buf = BytesIO()
        df.to_csv(buf, index=False)
        yield buf.getvalue()
```

- [ ] **Step 7: Smoke-test in browser**

Start the app, navigate to BOT, pick an element (load a template first if elements are empty), enter a year and value, click Add. Plot updates. Add a second point with the same year — value replaces. Add a third with a different year — both points appear. Verify the year-range slider clips the displayed points.

- [ ] **Step 8: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): manual-entry mode with year-only-match replace semantics"
```

---

## Task 6: CSV-upload mode

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Add `_handle_csv_upload` effect with case-insensitive column-name fallbacks.

- [ ] **Step 1: Add the column-match helper at module level (above `analysis_bot_ui`)**

```python
_YEAR_COL_CANDIDATES = ("year",)
_VALUE_COL_CANDIDATES = ("value", "measurement")


def _match_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercase form matches a candidate, or None."""
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None
```

- [ ] **Step 2: Add the `_handle_csv_upload` effect**

Below `_handle_manual_add`, add:

```python
    @reactive.effect
    @reactive.event(input.csv_upload, ignore_init=True)
    def _handle_csv_upload() -> None:
        files = input.csv_upload()
        if not files:
            return
        eid = input.element()
        if not eid:
            bot_error_store.set(t("bot.no_element_selected"))
            return
        path = files[0]["datapath"]
        try:
            raw = pd.read_csv(path)
            year_col = _match_column(list(raw.columns), _YEAR_COL_CANDIDATES)
            value_col = _match_column(list(raw.columns), _VALUE_COL_CANDIDATES)
            if year_col is None or value_col is None:
                bot_error_store.set(t("bot.csv_error"))
                return
            df = pd.DataFrame({
                "Year": pd.to_numeric(raw[year_col], errors="coerce"),
                "Value": pd.to_numeric(raw[value_col], errors="coerce"),
            }).dropna().reset_index(drop=True)
            if df.empty:
                bot_error_store.set(t("bot.csv_no_rows"))
                return
            df["Year"] = df["Year"].astype(int)
            store = dict(bot_data_store.get())
            store[eid] = df  # replace, not append (spec §3)
            bot_data_store.set(store)
            bot_error_store.set(None)
        except Exception:
            bot_error_store.set(t("bot.csv_error"))
```

- [ ] **Step 3: Smoke-test in browser**

Start the app, switch BOT to CSV mode, pick an element, upload `tests/fixtures/bot_sample.csv`. Plot renders with 5 points. Switch element to a different one — plot reverts to "no data yet" (data is per-element). Switch back — 5 points return. Upload `bot_lowercase.csv` — also works. Upload `bot_missing_value_col.csv` — error alert appears.

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): CSV-upload mode with case-insensitive column matching"
```

---

## Task 7: ISA-derived synthetic mode

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Add `_handle_isa_synthetic` effect, and update `bot_plot` to add a watermark + legend prefix when synthetic mode is active.

- [ ] **Step 1: Add the `_handle_isa_synthetic` effect**

Below `_handle_csv_upload`, add:

```python
    @reactive.effect
    @reactive.event(input.element, input.data_source, input.year_range, ignore_init=True)
    def _handle_isa_synthetic() -> None:
        if (input.data_source() or "manual") != "isa":
            return
        eid = input.element()
        if not eid:
            return
        # Find the element to read its confidence.
        confidence = 3
        for el in project_data.get().elements:
            if el.id == eid:
                confidence = el.confidence or 3
                break
        # Map confidence (1-5) to noise scale: confidence 5 → 0.15, confidence 1 → 0.75.
        noise_scale = (6 - int(confidence)) * 0.15
        lo, hi = input.year_range() or (1950, 2030)
        years = np.arange(int(lo), int(hi) + 1)
        seed = hash(eid) & 0xFFFFFFFF
        rng = np.random.default_rng(seed=seed)
        # Smooth baseline + per-element noise.
        baseline = np.linspace(10.0, 20.0, len(years))
        noise = rng.normal(loc=0.0, scale=noise_scale * 5, size=len(years))
        values = baseline + noise
        df = pd.DataFrame({"Year": years, "Value": values})
        store = dict(bot_data_store.get())
        store[eid] = df
        bot_data_store.set(store)
        bot_error_store.set(None)
```

- [ ] **Step 2: Update `bot_plot` to add the watermark and legend prefix when synthetic**

Replace the line `ax.plot(df["Year"], df["Value"], marker="o", color="#4a90b8", ...` with this block:

```python
        is_synthetic = (input.data_source() or "manual") == "isa"
        legend_label = (
            f"{t('bot.synthetic_legend')} {t('bot.value')}"
            if is_synthetic else t("bot.value")
        )
        ax.plot(df["Year"], df["Value"], marker="o", color="#4a90b8",
                linewidth=2, markersize=5, label=legend_label)
```

Then, after `ax.legend(loc="best")` and before `fig.tight_layout()`, add:

```python
        if is_synthetic:
            fig.text(
                0.5, 0.5, t("bot.synthetic_warning"),
                alpha=0.18, ha="center", va="center",
                fontsize=44, color="#a02020", weight="bold",
                transform=fig.transFigure,
            )
```

- [ ] **Step 3: Smoke-test in browser**

Start the app, load a template, switch to BOT, pick an element, switch data source to ISA. The plot should populate with a smooth-noisy curve, legend label prefixed with "⚠ Demo", and the figure should have a faint "DEMO DATA" watermark across the middle. Switch element — plot regenerates with a different (deterministic) curve. Switch back — same curve as before (deterministic seed).

**Known UX gotcha (per spec §3):** entering ISA mode after manual entries **overwrites** the manual data with the synthetic series for that element. This is intentional (matches R behavior) and accepted at brainstorming Q3. Verify that the watermark is clearly visible so a user notices they're looking at demo data, not their entries.

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): ISA-derived synthetic mode with watermark + demo legend"
```

---

## Task 8: Trend line and moving-average overlays

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Compute `_trend_coeffs` and `_moving_average_series` reactive calcs, and overlay them on `bot_plot` when their checkboxes are on.

- [ ] **Step 1: Add the inline numerics helpers at module level (above `analysis_bot_ui`)**

```python
def _compute_trend(years: np.ndarray, values: np.ndarray) -> tuple[float, float] | None:
    """Linear regression. Returns (slope, intercept) or None if degenerate."""
    if len(years) < 2:
        return None
    try:
        slope, intercept = np.polyfit(years, values, 1)
        return float(slope), float(intercept)
    except (ValueError, np.linalg.LinAlgError):
        return None


def _moving_average(values: np.ndarray, window: int) -> np.ndarray | None:
    """Centred moving average. Returns None if window > len(values)."""
    if len(values) < window or window < 2:
        return None
    return pd.Series(values).rolling(window=window, center=True).mean().to_numpy()
```

- [ ] **Step 2: Add the `_trend_coeffs` reactive calc**

Below `_filtered_frame`, add:

```python
    @reactive.calc
    def _trend_coeffs() -> tuple[float, float] | None:
        if not input.show_trend():
            return None
        df = _filtered_frame()
        if df is None or df.empty:
            return None
        return _compute_trend(df["Year"].to_numpy(), df["Value"].to_numpy())
```

- [ ] **Step 3: Update `bot_plot` to draw the overlays**

After the `ax.plot(df["Year"], df["Value"], ...)` call (the main data series) and before `ax.legend(...)`, add:

```python
        coeffs = _trend_coeffs()
        if coeffs is not None:
            slope, intercept = coeffs
            xs = df["Year"].to_numpy()
            ys = slope * xs + intercept
            ax.plot(xs, ys, color="#a02020", linestyle="--", linewidth=1.5,
                    label=t("bot.trend_label"))

        if input.show_moving_avg():
            ma = _moving_average(df["Value"].to_numpy(), int(input.window_size() or 3))
            if ma is not None:
                ax.plot(df["Year"].to_numpy(), ma, color="#2d8b50", linewidth=1.8,
                        label=t("bot.moving_avg_label"))
```

- [ ] **Step 4: Smoke-test in browser**

With BOT showing data, toggle the trend checkbox — a red dashed line appears/disappears. Toggle moving-average — green line appears/disappears, and changing the window slider re-renders.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): trend and moving-average overlays"
```

---

## Task 9: Summary statistics renderer

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Replace the placeholder `bot_summary` with the real stats block.

- [ ] **Step 1: Add the `_summary_stats` reactive calc**

Below `_trend_coeffs`, add:

```python
    @reactive.calc
    def _summary_stats() -> dict | None:
        df = _filtered_frame()
        if df is None or df.empty:
            return None
        values = df["Value"].to_numpy()
        coeffs = _compute_trend(df["Year"].to_numpy(), values)
        slope = coeffs[0] if coeffs is not None else float("nan")
        return {
            "mean": float(np.mean(values)),
            "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "slope": slope,
        }
```

- [ ] **Step 2: Replace `bot_summary` to render the stats block**

```python
    @output
    @render.ui
    def bot_summary():
        err = bot_error_store.get()
        if err:
            return ui.tags.div(err, class_="alert alert-danger")
        s = _summary_stats()
        if s is None:
            return ui.tags.p(t("bot.no_data_yet"), class_="text-muted")
        return ui.tags.dl(
            ui.tags.dt(t("bot.summary_mean")),
            ui.tags.dd(f"{s['mean']:.4f}"),
            ui.tags.dt(t("bot.summary_sd")),
            ui.tags.dd(f"{s['sd']:.4f}"),
            ui.tags.dt(t("bot.summary_min")),
            ui.tags.dd(f"{s['min']:.4f}"),
            ui.tags.dt(t("bot.summary_max")),
            ui.tags.dd(f"{s['max']:.4f}"),
            ui.tags.dt(t("bot.summary_slope")),
            ui.tags.dd(f"{s['slope']:.6f}"),
            class_="row",
        )
```

- [ ] **Step 3: Smoke-test in browser**

With BOT showing data, the summary block below the plot displays five rows: Mean, Std. dev., Min, Max, Trend slope.

- [ ] **Step 4: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): summary statistics renderer"
```

---

## Task 10: Stale-data warning

**Files:**
- Modify: `sespy/modules/analysis_bot.py`

Watch `event_bus.isa_change`, prune deleted elements from the store, post a notification when the *active* element was deleted.

- [ ] **Step 1: Add the `_stale_warning` effect**

Below `_handle_isa_synthetic`, add:

```python
    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe to ISA changes; isolate the store reads so this effect
        # does NOT re-fire on our own writes (manual add, csv upload, synthetic).
        event_bus.isa_change.get()
        with reactive.isolate():
            store = bot_data_store.get()
            if not store:
                return
            current_element_ids = {el.id for el in project_data.get().elements}
            stale_keys = set(store.keys()) - current_element_ids
            if not stale_keys:
                return
            new_store = {k: v for k, v in store.items() if k in current_element_ids}
            bot_data_store.set(new_store)
            active = input.element()
            if active in stale_keys:
                ui.notification_show(
                    t("bot.stale_warning"),
                    duration=5,
                    type="warning",
                )
```

- [ ] **Step 2: Smoke-test in browser**

Start the app, load a template, switch to BOT, pick an element, add a manual point. Switch to "Edit Data", delete that element. Switch back to BOT — notification appears, plot reverts to "no data yet". Add data on a different element, then delete a *non*-active element — no notification, but the deleted element's data should be silently pruned (verifiable by reactive devtools or by re-creating an element with the same id and checking the store is empty).

- [ ] **Step 3: Commit**

```bash
git add sespy/modules/analysis_bot.py
git commit -m "feat(bot): stale-data warning with isolate-on-store-read"
```

---

## Task 11: E2e test suite

**Files:**
- Create: `tests/test_bot_e2e.py`

Mirror the script style of `tests/test_boolean_happy_e2e.py` (asyncio + Playwright, run by booting the app on port 8000 and pointing the script at it).

- [ ] **Step 1: Create `tests/test_bot_e2e.py`** with this content:

```python
"""E2E for the BOT (Behaviour Over Time) module.

Eight cases per spec §5. Loads the Minimal Demo template (5 elements) for
all cases. Mirrors the script style of test_boolean_happy_e2e.py — boot
the app on port 8000, run this script.
"""
import asyncio
from playwright.async_api import async_playwright


async def _load_minimal_demo(page):
    await page.wait_for_selector("#sespy_nav_templates", timeout=15000)
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2500)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    assert "Minimal Demo" in cards, f"Minimal Demo missing: {cards}"
    idx = cards.index("Minimal Demo")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)


async def _open_bot(page):
    await page.click("#sespy_nav_bot")
    await page.wait_for_timeout(1500)


async def _pick_first_element(page):
    # Selectize: open the dropdown then click the first option.
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    await page.click(".selectize-dropdown-content [data-selectable]:first-child")
    await page.wait_for_timeout(500)


async def case_manual_entry_happy(page):
    print("\n=== case 1: manual entry happy path ===")
    await _open_bot(page)
    await _pick_first_element(page)
    # Default mode is manual. Enter 3 points.
    for year, value in [(1990, 12.5), (2000, 15.8), (2010, 18.6)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(800)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot did not render after manual entry"
    n_dt = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary dl dt').length"
    )
    assert n_dt >= 5, f"expected >=5 summary fields, got {n_dt}"
    print("  ok")


async def case_csv_upload_happy(page):
    print("\n=== case 2: csv upload happy path ===")
    await page.click("input[type=radio][value=csv]")
    await page.wait_for_timeout(500)
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_sample.csv")
    await page.wait_for_timeout(2000)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot did not render after csv upload"
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger == 0, f"unexpected error alert: {danger}"
    print("  ok")


async def case_csv_lowercase_columns(page):
    print("\n=== case 3: csv with lowercase columns ===")
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_lowercase.csv")
    await page.wait_for_timeout(2000)
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger == 0, f"lowercase-column csv should succeed: {danger} errors"
    print("  ok")


async def case_csv_bad_data(page):
    print("\n=== case 4: csv with missing value column ===")
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_missing_value_col.csv")
    await page.wait_for_timeout(2000)
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger >= 1, "expected error alert for missing value column"
    print("  ok")


async def case_synthetic_mode(page):
    print("\n=== case 5: synthetic isa mode ===")
    # Per spec §9: the watermark text in the rendered PNG is hard to assert from
    # the DOM. The legend prefix in `bot.synthetic_legend` ('⚠ Demo') is the
    # more reliable proxy. We assert the plot renders AND that the alt-text or
    # img src contains evidence the synthetic path ran (data populated).
    await page.click("input[type=radio][value=isa]")
    await page.wait_for_timeout(2000)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "synthetic plot did not render"
    # Summary stats should populate (synthetic series spans the full slider range).
    n_dt = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary dl dt').length"
    )
    assert n_dt >= 5, f"expected synthetic series to populate summary, got {n_dt} fields"
    print("  ok")


async def case_trend_toggle(page):
    print("\n=== case 6: trend toggle ===")
    # Trend is on by default. Turn it off then back on; assert no crash.
    await page.click("#bot-show_trend")
    await page.wait_for_timeout(800)
    await page.click("#bot-show_trend")
    await page.wait_for_timeout(800)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot disappeared after trend toggle"
    print("  ok")


async def case_per_element_persistence(page):
    print("\n=== case 7: per-element data persistence ===")
    # Per spec §5 case 7: enter 3 points on element A, switch to B, enter 2,
    # switch back to A, assert A's 3 points still present.
    await page.click("input[type=radio][value=manual]")
    await page.wait_for_timeout(500)
    # Element A is currently selected from earlier cases. Clear and add 3 points.
    # (Earlier cases left various amounts of data on A; we re-write to a known
    # 3-point state by adding 3 fresh points with unique years.)
    for year, value in [(1980, 1.0), (1985, 2.0), (1990, 3.0)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(600)
    # Switch to element B (second selectable option in the dropdown).
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    options = await page.evaluate(
        "() => document.querySelectorAll("
        "  '.selectize-dropdown-content [data-selectable]'"
        ").length"
    )
    assert options >= 2, f"need >=2 elements for this case, got {options}"
    await page.click(".selectize-dropdown-content [data-selectable]:nth-child(2)")
    await page.wait_for_timeout(800)
    # Add 2 points to element B.
    for year, value in [(2000, 10.0), (2005, 20.0)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(600)
    # Switch back to element A (first option).
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    await page.click(".selectize-dropdown-content [data-selectable]:first-child")
    await page.wait_for_timeout(800)
    # Assert A's 3 points are still there. The Data tab table is the simplest
    # check; switch to it.
    await page.click("text=Data")
    await page.wait_for_timeout(800)
    n_rows = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_table table tbody tr').length"
    )
    # By case 7 element A actually holds whatever the prior cases left there:
    # case 5 (synthetic) populated ~80 rows spanning 1950-2030, then the 3
    # manual adds above replaced years 1980/1985/1990 in that series (year-only
    # match). Net: A has many rows. Switching to B then back must not erase
    # them. Assert >= 3 to confirm preservation (the actual count is much
    # higher but exact value is sensitive to test ordering).
    assert n_rows >= 3, f"element A should have >=3 rows after switch-back, got {n_rows}"
    # Switch back to Time series tab for next cases.
    await page.click("text=Time series")
    await page.wait_for_timeout(500)
    print(f"  ok ({n_rows} rows preserved on element A)")


async def case_stale_warning(page):
    print("\n=== case 8: stale-data warning ===")
    # Navigate to Edit Data, find the currently-selected element, delete it,
    # then return to BOT. Expect a warning notification.
    # Implementation deferred — requires knowing the Edit-Data delete-button
    # selector, which is not stable across Shiny versions and not used by any
    # other e2e test in this repo. Add this case in a follow-up after the rest
    # of the suite is green; the stale-warning code path was smoke-tested
    # manually in Task 10 step 2.
    print("  skipped (requires Edit-Data delete-button selector)")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await _load_minimal_demo(page)

        await case_manual_entry_happy(page)
        await case_csv_upload_happy(page)
        await case_csv_lowercase_columns(page)
        await case_csv_bad_data(page)
        await case_synthetic_mode(page)
        await case_trend_toggle(page)
        await case_per_element_persistence(page)
        await case_stale_warning(page)

        await page.screenshot(path="tests/screenshots/bot_e2e.png")
        print("\nbot e2e: 7 cases passed, 1 skipped")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the e2e test against a running app**

In one terminal:
```bash
micromamba run -n shiny shiny run app.py --port 8000
```

In another terminal (or after starting in background):
```bash
micromamba run -n shiny python tests/test_bot_e2e.py
```
Expected: prints `bot e2e: 7 cases passed, 1 skipped`.

If any case fails, read the failure message; common causes: nav-button id mismatch (check `app.py:71-85`), selectize-class mismatch (Shiny may use a different version), timing flakes (bump `wait_for_timeout` values).

- [ ] **Step 3: Commit**

```bash
git add tests/test_bot_e2e.py
git commit -m "test(bot): e2e coverage for 7 of 8 spec cases"
```

---

## Task 12: README update + final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the README modules section**

Run:
```bash
head -80 README.md
```
Locate the modules table and the "13 modules" reference.

- [ ] **Step 2: Bump module count to 14 and add a row to the modules table**

Replace `13 modules` with `14 modules`. Add a row to the modules table for "Behaviour Over Time" — match the existing row format (description should reference per-element time-series, three input modes, trend + moving-average).

- [ ] **Step 3: Update the e2e test count (if mentioned)**

Search for the test count line (e.g., "15 e2e scripts") and bump to 16.

- [ ] **Step 4: Run the full unit-test suite to confirm no regressions**

Run:
```bash
micromamba run -n shiny pytest tests/ -q -k "not e2e"
```
Expected: same pass count as before plus no new failures.

- [ ] **Step 5: Verify the app starts cleanly**

Run:
```bash
micromamba run -n shiny python -c "import app; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): note BOT module — now 14 modules"
```

- [ ] **Step 7: Final branch summary**

Run:
```bash
git log --oneline main..feat/analysis-bot
```
Expected: 12 commits — one per task across Tasks 1-12 (Task 0 is read-only and does not commit). Each commit message should be self-descriptive.

---

## Definition of done

- All 12 tasks complete.
- `feat/analysis-bot` branch contains 12 commits (one per task; Task 0 is read-only).
- E2e suite (`tests/test_bot_e2e.py`) prints `7 cases passed, 1 skipped`.
- App boots cleanly; "Behaviour Over Time" appears in the nav between "Dynamic Simulation" and "Intervention".
- All three input modes work: manual entry adds points (with year-only-match replace), CSV upload reads `Year/year` and `Value/value` columns, ISA mode renders a deterministic series with watermark.
- Per-element data persists when switching elements within a session.
- Deleting an element upstream removes its data and posts a stale-warning if it was active.
- README reflects 14 modules.
- Existing unit-test suite still passes (no regressions).

## Out of scope (deferred to future work)

- **Pattern Detection / Comparison tabs** — omitted per Q4 decision.
- **Helper-module extraction** (`sespy/bot.py` + `tests/test_bot.py`) — only if `_compute_trend` or `_moving_average` grow beyond ~10 LOC during implementation. Currently each is ~5 lines. Re-evaluate if implementation balloons.
- **Stale-warning e2e case (#8)** — script-level skipped; requires knowing the Edit-Data delete-button selector. Add in a follow-up after the rest is green.
- **Project-file persistence** — BOT data is session-only. Persisting to `.sespy` files would require schema changes in `data_structure.py` and `project_io.py`; out of scope.
