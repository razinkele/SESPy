# PIMS Stakeholders SH5 — Analysis Summary — Design

Date: 2026-06-07 (rev. 3 — status update after implementation)
Status: **Implemented** ✓ (shipped on `main`; analysis summary sub-tab live).

**rev. 2 changes (from the review):** (a) **name-collision fix** — the pure helpers
`stakeholder_stats`/`engagement_coverage` share names with their Shiny output
functions, so the module imports them aliased (`compute_stakeholder_stats`,
`compute_engagement_coverage`) and the renders call the aliases (§4); (b) the
distribution renders use a `_analysis_code_label` helper so an **unknown** type/sector
code renders verbatim (not the i18n key), blanks → `analysis.unset`, known →
`stakeholders.type/sector.<code>` (§4); (c) the e2e **polls** the stats output (§6);
(d) distribution charts rotate tick labels + `fig.tight_layout()` for legibility (§4).

**Sub-project context:** SH5 of the PIMS Stakeholders port. SH1 (register), SH2
(Power-Interest grid), SH3 (engagement log), and SH4 (communication plan) are all on
`main`. SH5 adds an **Analysis** sub-tab (R Tab 5 "Analysis & Reports") — a read-only
analytics view: a statistics summary + three distribution charts. R source:
`../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_stakeholder_module.R`, Tab 5 (UI
~274-334; server `stakeholder_stats` ~705-719, `engagement_coverage` ~721-740,
`type_distribution` ~742-757, `sector_distribution` ~759-774).

**A pure read/visualization layer** over SH1–SH4 data (stakeholders + engagements +
communications). Like SH2's grid, it writes nothing and adds no schema/persistence.

**Deferred to SH6 (out of scope here, §1.2):** R Tab 5's three `downloadButton`s —
the Excel full report, the Power-Interest grid PNG, and the summary PDF.
`@render.download` has no Playwright precedent in this repo and the file builders
(openpyxl workbook / matplotlib PNG / PDF) are non-trivial; they are their own
increment. Also still deferred: grid click-to-inspect (SH2/SH3 static-PNG limitation).

## 1. Goal & scope

### 1.1 In scope
- A new **Analysis** sub-tab inside the existing Stakeholders `navset_tab`.
- A **statistics summary** (7 metrics) as a `@render.ui`, backed by a pure
  `stakeholder_stats(...)` helper.
- Three matplotlib `@render.plot` charts: **engagement coverage** (% of stakeholders
  with ≥1 engagement), **stakeholders by type**, **stakeholders by sector** — each
  backed by a pure, unit-tested aggregation helper.
- i18n keys (`stakeholders.analysis.*` + `stakeholders.tab_analysis`, 9 langs).
- Unit + e2e tests.

### 1.2 Out of scope (SH6 / later)
- The three **downloads** (Excel / PNG / PDF) — SH6.
- Click-to-inspect a plotted grid point (static-PNG limitation).
- Any data-model / schema / persistence change, or `app.py` change. SH5 is a pure
  read layer internal to `pims_stakeholders_ui`/`_server`.

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Layer type | Pure read/visualization over existing data; NO model/schema/persistence change | Mirrors SH2's grid; the data already exists from SH1–SH4. |
| Stats helper | Pure `stakeholder_stats(stakeholders, engagements, communications) -> dict` (7 int counts) | Trivially unit-testable; the `@render.ui` just formats it. |
| Distinct-count semantics | `types`/`sectors` count **distinct non-empty** codes | R's `length(unique())` includes `""`; counting blanks as a "type" is misleading — an intentional, documented divergence (cf. SH1's R-bug corrections). |
| "high" counts | `high_power`/`high_interest` = count where the code `== "HIGH"` exactly | Faithful to R (`sum(df$Power == "HIGH")`); MEDIUM is not "high" here (distinct from the grid's ≥MEDIUM binning, which is a different lens). |
| Coverage helper | Pure `engagement_coverage(stakeholders, engagements) -> float` = % of stakeholders whose id appears in any engagement's `stakeholder_id`; `0.0` when no stakeholders | Matches R (`sum(ID %in% engaged_ids)/n*100`); pure + testable, plot draws it. |
| Distribution helper | Pure `count_by(stakeholders, field) -> dict[code, int]` (insertion-ordered, blanks grouped under `""`) | One helper serves both type + sector charts; the render maps codes→labels via `tr` and draws bars. |
| Charts | matplotlib `@render.plot` (build `fig, ax`; return `fig`), mirroring SH2 grid | Proven idiom (`pims_stakeholders.py` SH2 plot); `ui.output_plot(id, height=...)`. |
| Empty state | Each render shows a friendly "add stakeholders…" message (text in the plot / a `ui.p` in the summary) when there are no stakeholders | Matches R's empty-state guards. |
| UI placement | A 5th `ui.nav_panel` (last) in the existing `navset_tab` (`id="stakeholder_tabs"`) | Register \| Power-Interest Grid \| Engagement Planning \| Communication Plan \| **Analysis**. Register stays first → default-active → SH1–SH4 e2e unaffected. |

## 2. Data model
**No change.** SH5 reads `Project.stakeholders` / `.engagements` / `.communications`.
No `Communication`/`Engagement`/`Stakeholder` edit, no `to_dict`/`from_dict` change,
**no `PROJECT_SCHEMA_VERSION` bump** (stays 5).

## 3. Pure helpers (`sespy/stakeholders.py`, no Shiny imports)
```python
def stakeholder_stats(stakeholders, engagements, communications) -> dict:
    # {"total", "types", "sectors", "high_power", "high_interest",
    #  "engagements", "communications"} -> int.
    # types/sectors = count of DISTINCT NON-EMPTY stakeholder_type / sector codes.
    # high_power/high_interest = count where power/interest == "HIGH".

def engagement_coverage(stakeholders, engagements) -> float:
    # % of stakeholders whose id is the stakeholder_id of >=1 engagement.
    # 0.0 when there are no stakeholders. Range 0..100.

def count_by(stakeholders, field) -> dict:
    # {code: count} over getattr(s, field) for each stakeholder, in first-seen
    # order; blank ("") values are kept under the "" key (the render labels them).
```
All pure, no Shiny, no matplotlib. The render layer formats/draws.

## 4. Module — Analysis sub-tab (`sespy/modules/pims_stakeholders.py`)

**UI** — add a 5th panel + a plain `_analysis_panel()` (NO `@module.ui`):
```python
ui.nav_panel(_t("stakeholders.tab_analysis"), _analysis_panel()),
```
`_analysis_panel()` builds (cards in a `layout_columns`):
- `ui.output_ui("stakeholder_stats")` (the 7-metric summary).
- `ui.output_plot("engagement_coverage", height="300px")`.
- `ui.output_plot("type_distribution", height="300px")`.
- `ui.output_plot("sector_distribution", height="300px")`.

**Server** — add (read-only; `_items()`/`_engagements()`/`_communications()` already
exist). **Import the pure helpers ALIASED** to avoid clashing with the output-function
names (`stakeholder_stats`/`engagement_coverage` are also the `output_ui`/`output_plot`
ids):
```python
from sespy.stakeholders import (
    stakeholder_stats as compute_stakeholder_stats,
    engagement_coverage as compute_engagement_coverage,
    count_by,
)
```
A small module-level label helper for the distribution charts (known code → label,
blank → "unset", unknown → verbatim; uses SH1's `_TYPE_CODES`/`_SECTOR_CODES`):
```python
def _code_label(code, group, known, translate):
    if not code:
        return translate("stakeholders.analysis.unset")
    if code in known:
        return translate(f"stakeholders.{group}.{code}")
    return code  # unknown code: verbatim, not the i18n key
```
- **Stats** (`@render.ui def stakeholder_stats`): `s = compute_stakeholder_stats(
  _items(), _engagements(), _communications())`; if `s["total"] == 0` → a single
  `ui.p(tr("stakeholders.analysis.empty"))`; else a `ui.tags.ul` of seven
  `ui.tags.li(f"{tr('stakeholders.analysis.<key>')}: {value}")` rows.
- **Coverage plot** (`@render.plot def engagement_coverage`, SH2 idiom): `import
  matplotlib.pyplot as plt`; if no stakeholders, `ax.text(...)` the
  `analysis.add_stakeholders` message + return `fig`; else `cov =
  compute_engagement_coverage(_items(), _engagements())` and a 2-bar barplot
  (engaged `cov`, not-engaged `100-cov`) titled with `round(cov, 1)`%.
- **Type distribution** (`@render.plot def type_distribution`): `counts = count_by(
  _items(), "stakeholder_type")`; empty guard; bars over `counts`, x-labels via
  `_code_label(code, "type", _TYPE_CODES, tr)`; rotate tick labels (`rotation=45,
  ha="right"`) + `fig.tight_layout()`.
- **Sector distribution** (`@render.plot def sector_distribution`): same with
  `count_by(_items(), "sector")` and `_code_label(code, "sector", _SECTOR_CODES, tr)`.

No `app.py` change.

## 5. i18n (`sespy/translations/core.json`)
Fresh `stakeholders.analysis.*` + `stakeholders.tab_analysis`, **inside the top-level
`"translation"` wrapper**, 9 langs (English placeholder per SP4). Keys:
`tab_analysis` (English **"Analysis"** — the tab's `data-value` for the e2e);
`analysis.heading`, `analysis.stats_heading`, `analysis.empty`, `analysis.unset`;
the 7 stat labels `analysis.total`, `analysis.types`, `analysis.sectors`,
`analysis.high_power`, `analysis.high_interest`, `analysis.engagements`,
`analysis.communications`; the chart titles/labels `analysis.coverage_title`,
`analysis.engaged`, `analysis.not_engaged`, `analysis.percentage`,
`analysis.by_type`, `analysis.by_sector`, `analysis.count`,
`analysis.add_stakeholders` (the plot empty-state text). Reuse SH1's existing
`stakeholders.type.*` and `stakeholders.sector.*` labels for the distribution
x-axes (no new keys for those).

## 6. Testing
- **Unit — `tests/test_stakeholders.py`** (append): `stakeholder_stats` over a mixed
  fixture (distinct non-empty type/sector counts; HIGH-only power/interest counts;
  engagement + communication totals) and the **empty** case (all zeros);
  `engagement_coverage` — 0.0 with no stakeholders, 50.0 when 1 of 2 is engaged, 100.0
  when all engaged, and **dedup** (a stakeholder with 2 engagements counts once);
  `count_by` — first-seen order, blank grouped under `""`, empty list → `{}`.
- **No** `test_data_structure.py` change (no schema bump).
- **e2e — `tests/test_stakeholders_e2e.py`** (extend; sections 1–9 UNCHANGED): add a
  section 10 — switch to the Analysis sub-tab via
  `#stakeholders-stakeholder_tabs a[data-value='Analysis']`, then **poll**
  `#stakeholders-stakeholder_stats` inner text (a short loop, like the grid/engagement
  sections) until it contains a known label and a count (e.g. the total-stakeholders
  label, since earlier sections added stakeholders). Reading the `@render.ui` text is
  reliable (avoids plot-img flake); optionally also `wait_for_selector` the
  `#stakeholders-type_distribution img`.

## 7. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/stakeholders.py` | edit | append pure `stakeholder_stats`/`engagement_coverage`/`count_by` (no Shiny) |
| `sespy/modules/pims_stakeholders.py` | edit | 5th `nav_panel`; `_analysis_panel()`; stats `@render.ui` + 3 `@render.plot` |
| `sespy/translations/core.json` | edit | `stakeholders.analysis.*` + `stakeholders.tab_analysis` (inside `"translation"`, 9 langs) |
| `tests/test_stakeholders.py` | edit | unit tests for the 3 pure helpers |
| `tests/test_stakeholders_e2e.py` | edit | add Analysis-tab stats e2e section |

No changes to `sespy/data_structure.py`, `app.py`, `project_io.py`,
`recent_projects.py`, or `persistent_storage.py`; SH1–SH4 features untouched.
