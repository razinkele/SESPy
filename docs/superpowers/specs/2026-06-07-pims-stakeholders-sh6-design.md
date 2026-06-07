# PIMS Stakeholders SH6 — Export Downloads — Design

Date: 2026-06-07 (rev. 2 — after deep-review + library-idiom verification)
Status: **Draft** — design phase, not yet implemented.

**rev. 2 notes (verified idioms, detailed in the plan):** (a) Excel headers come from
`dataclasses.fields(cls)` (NOT `items[0]`) so empty exports yield header-only sheets;
build sheets via `wb.active.title = "Stakeholders"` + two `create_sheet()` (no stray
`"Sheet"`). (b) reportlab `Table([])` **raises** — always include a header row + a
placeholder row when data is empty. (c) PNG uses the no-pyplot idiom
(`matplotlib.figure.Figure` + `FigureCanvasAgg` + `matplotlib.patches.Rectangle`),
axes **x = interest, y = power**. (d) e2e asserts `download.suggested_filename`
endswith the extension; `@render.download` handlers do **not** use `@output`. All
three byte-builder idioms were run and confirmed (PNG `\x89PNG`, xlsx `PK`, PDF `%PDF`;
header-only reportlab table is fine).

**Sub-project context:** SH6 (final) of the PIMS Stakeholders port. SH1–SH5 are on
`main`. SH6 adds the three **export downloads** from R Tab 5's "Export stakeholder
data" panel into the SH5 **Analysis** sub-tab: an Excel full report, a Power-Interest
grid PNG, and a summary PDF. R source:
`../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_stakeholder_module.R`, Tab 5
download handlers (`download_stakeholder_report` ~777-800, `download_power_interest`
PNG, `download_summary` PDF).

**The novel piece of the port.** Unlike SH1–SH5, this needs file builders +
`@render.download`. The repo already has a proven download pattern
(`report_export.py`: `@render.download(filename=lambda: …)` + `yield bytes`, builders
in `report.py`) and a Playwright download-test pattern
(`test_report_e2e.py`: `new_context(accept_downloads=True)` +
`page.expect_download()`). SH6 mirrors both.

**Deferred (out of scope, §1.2):** grid click-to-inspect (static-PNG limitation,
unchanged from SH2/SH3).

## 1. Goal & scope

### 1.1 In scope
- Three **pure byte-builder** functions in a new `sespy/stakeholder_reports.py`
  (no Shiny; heavy libs lazy-imported inside each function):
  - `build_stakeholder_workbook(stakeholders, engagements, communications) -> bytes`
    (`.xlsx`, openpyxl) — 3 sheets.
  - `build_power_interest_png(stakeholders, *, translate) -> bytes` (`.png`, matplotlib).
  - `build_summary_pdf(project_name, stats, stakeholders) -> bytes` (`.pdf`, reportlab).
- Wiring in the SH5 Analysis panel: an "Export" card with three `ui.download_button`s
  + three `@render.download` handlers that `yield` the builder bytes.
- i18n keys (`stakeholders.analysis.export_*`, 9 langs).
- Unit + e2e tests.

### 1.2 Out of scope
- Any data-model / schema / persistence change, or `app.py` change.
- Click-to-inspect a plotted grid point (static-PNG limitation).
- Localized/translated **cell values** in the Excel (export the canonical codes +
  raw fields — a faithful data dump, like R's data-frame write); column headers are
  the dataclass field names. (Level/label translation is a possible later polish.)

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Builder location | New `sespy/stakeholder_reports.py`, pure functions returning `bytes`; openpyxl/matplotlib/reportlab **lazy-imported inside** each builder | Mirrors `report.py` (lazy heavy imports); keeps the functions Shiny-free + unit-testable by magic bytes. |
| PDF engine | **reportlab** (installed, pure-Python, no native deps) | The existing `report.py` PDF uses **WeasyPrint**, which needs native libs and is an optional `pdf` extra; reportlab avoids that — SH6 downloads must work out-of-the-box. |
| Excel engine | **openpyxl** via a direct `Workbook` (3 sheets) | Installed; direct openpyxl avoids a pandas/ExcelWriter dependency chain and gives explicit sheet/headers control. |
| Excel contents | One sheet each for Stakeholders / Engagements / Communications; header row = dataclass field names; rows = `asdict` values | Faithful to R (writes the 3 data frames); pure, deterministic, testable. |
| PNG source | A self-contained Power-Interest scatter drawn from `level_num(power)`/`level_num(interest)` (quadrant lines + named points) | Re-draws the grid to a file (as R does); a `translate` callback supplies axis/quadrant labels so it stays pure/Shiny-free. |
| PDF contents | Title (project name) + the 7-metric stats list + a stakeholders table (name/type/power/interest) | Mirrors R's summary PDF; reportlab `SimpleDocTemplate` + `Table`. |
| Empty-data handling | Each builder still returns valid bytes for empty inputs (empty sheets / "no stakeholders" placeholder text / a stats-only PDF) | Downloads must never raise; tested. |
| UI placement | A third row in the SH5 `_analysis_panel()` — an "Export" card with 3 download buttons | Keeps all of R Tab 5 in one Analysis tab. |
| Download wiring | `@render.download(filename=lambda: f"…-{_stamp()}.<ext>")` + `yield <builder>(…)` | Exact `report_export.py` pattern (`_stamp()` = `datetime.now().strftime("%Y%m%d-%H%M%S")`). |

## 2. Data model
**No change.** SH6 reads `Project.stakeholders`/`.engagements`/`.communications` and
the SH5 `stakeholder_stats`. No schema bump.

## 3. Builders (`sespy/stakeholder_reports.py`, no Shiny imports)
```python
def build_stakeholder_workbook(stakeholders, engagements, communications) -> bytes:
    # openpyxl Workbook; 3 sheets ("Stakeholders","Engagements","Communications");
    # header row = field names (dataclasses.fields); rows = asdict values; save to
    # BytesIO; return bytes. Empty lists -> header-only sheets.

def build_power_interest_png(stakeholders, *, translate) -> bytes:
    # matplotlib (Agg): scatter of stakeholders with level_num(power)/level_num(interest);
    # quadrant lines/labels via `translate`; fig.savefig(BytesIO, format="png");
    # return bytes. No plottable stakeholders -> an empty-grid PNG with a notice.

def build_summary_pdf(project_name, stats, stakeholders) -> bytes:
    # reportlab SimpleDocTemplate -> BytesIO: title (project_name), a 7-row stats
    # table from `stats` (the stakeholder_stats dict), and a stakeholders table
    # (name/type/power/interest). return bytes.
```
All three lazy-import their heavy lib inside the function body (matplotlib uses the
non-interactive Agg backend via `matplotlib.use("Agg")` is unnecessary — `fig =
Figure()` from `matplotlib.figure` avoids pyplot/global-state entirely; prefer
`from matplotlib.figure import Figure` + `FigureCanvasAgg`).

## 4. Module — Export card (`sespy/modules/pims_stakeholders.py`)
**UI** — extend `_analysis_panel()` with a third `layout_columns` row / a full-width
card:
```python
ui.card(
    ui.h5(_t("stakeholders.analysis.export_heading")),
    ui.download_button("download_stakeholder_xlsx", _t("stakeholders.analysis.export_excel")),
    ui.download_button("download_power_interest_png", _t("stakeholders.analysis.export_png")),
    ui.download_button("download_summary_pdf", _t("stakeholders.analysis.export_pdf")),
),
```
**Server** — add three handlers (mirroring `report_export.py`), with a module-level
`_stamp()`:
```python
    @render.download(filename=lambda: f"stakeholders-{_stamp()}.xlsx")
    def download_stakeholder_xlsx():
        yield build_stakeholder_workbook(_items(), _engagements(), _communications())

    @render.download(filename=lambda: f"power-interest-{_stamp()}.png")
    def download_power_interest_png():
        yield build_power_interest_png(_items(), translate=tr)

    @render.download(filename=lambda: f"stakeholder-summary-{_stamp()}.pdf")
    def download_summary_pdf():
        proj = project_data.get()
        stats = compute_stakeholder_stats(_items(), _engagements(), _communications())
        yield build_summary_pdf(proj.metadata.name, stats, _items())
```
Import the builders at module top: `from sespy.stakeholder_reports import (...)`.
Note the download-output ids differ from the SH5 plot id `power_interest_grid` and
the `engagement_coverage` plot — **`download_power_interest_png`** is a distinct id
(no collision). No `app.py` change.

## 5. i18n (`sespy/translations/core.json`)
Fresh keys inside `"translation"`, 9 langs: `stakeholders.analysis.export_heading`
("Export stakeholder data"), `stakeholders.analysis.export_excel` ("Download full
report (Excel)"), `stakeholders.analysis.export_png` ("Download Power-Interest grid
(PNG)"), `stakeholders.analysis.export_pdf` ("Download summary (PDF)").

## 6. Testing
- **Unit — `tests/test_stakeholder_reports.py`** (new): each builder returns valid,
  non-empty bytes with the right magic header — xlsx starts with `PK\x03\x04` (zip),
  PNG starts with `\x89PNG\r\n\x1a\n`, PDF starts with `%PDF`. Content checks:
  the workbook (re-opened with `openpyxl.load_workbook(BytesIO(...))`) has the 3
  expected sheet names and the stakeholder row count + a known name; the PDF builder
  runs on a populated `stats`+stakeholders fixture; **empty-input** cases for all
  three return valid bytes (no exception). A trivial `translate=lambda k: k` fake
  drives the PNG.
- **No** `test_data_structure.py` / schema change.
- **e2e — `tests/test_stakeholders_e2e.py`** (extend; sections 1–10 UNCHANGED): the
  context already needs `accept_downloads=True` — **update `new_context()`** to pass
  it (sections 1–10 don't download, so this is safe). Add a section 11 on the Analysis
  tab: for each of the 3 buttons, `async with page.expect_download() as dl: await
  page.click("#stakeholders-<id>")`, then assert `await dl.value` has the expected
  filename suffix (`.xlsx`/`.png`/`.pdf`). (Mirrors `test_report_e2e.py`.)

## 7. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/stakeholder_reports.py` | new | pure `build_stakeholder_workbook`/`build_power_interest_png`/`build_summary_pdf` (lazy heavy imports) |
| `sespy/modules/pims_stakeholders.py` | edit | Export card (3 download buttons) + 3 `@render.download` handlers + `_stamp()` |
| `sespy/translations/core.json` | edit | `stakeholders.analysis.export_*` (inside `"translation"`, 9 langs) |
| `tests/test_stakeholder_reports.py` | new | builder magic-byte + content + empty-input unit tests |
| `tests/test_stakeholders_e2e.py` | edit | `accept_downloads=True` + section 11 expect_download for the 3 files |

No changes to `sespy/data_structure.py`, `app.py`, `project_io.py`,
`recent_projects.py`, `persistent_storage.py`, or `sespy/report.py`; SH1–SH5 untouched.
