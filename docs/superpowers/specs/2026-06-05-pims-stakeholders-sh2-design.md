# PIMS Stakeholders SH2 — Power-Interest Grid — Design

Date: 2026-06-05
Status: **Draft** — design phase, not yet implemented.

**Sub-project context:** SH2 of the PIMS Stakeholders port. SH1 (shipped: the
stakeholder **register** — data + CRUD + persistence) is on `main`. SH2 adds the
**Power-Interest (Mendelow) grid** + per-quadrant engagement strategies as a
second sub-tab of the existing Stakeholders panel. R source of truth:
`../SESToolbox/MarineSABRES_SES_Shiny/modules/pims_stakeholder_module.R`, Tab 2
("Power-Interest Grid", lines 116-150 UI; 515-593 server).

**Deferred to a later SH3 (out of scope here):** R's Tab 3 "Engagement Planning"
— the per-stakeholder engagement-activity log (`eng_method`/`eng_objectives`/
`add_engagement`/`engagement_table`), coverage/type/sector analytics, and PNG
downloads. SH2 is intentionally just the grid + the strategy guidance.

## 1. Goal & scope

### 1.1 In scope
- A Power-Interest grid visualization (matplotlib scatter) on a new **Power-Interest
  Grid** sub-tab inside the existing Stakeholders panel.
- A grid summary: the 4 Mendelow strategy descriptions + per-quadrant counts and
  member names.
- Pure, unit-tested classification helpers in `sespy/stakeholders.py`.
- i18n keys; unit + e2e tests.

### 1.2 Out of scope
- Any data-model / schema / persistence change. **SH2 reads SH1's existing
  `Stakeholder.power` / `.interest` / `.engagement_level`; it writes nothing and
  stores nothing new.** No `PROJECT_SCHEMA_VERSION` bump.
- Any `app.py` change (the sub-tab is internal to `pims_stakeholders_ui`; the nav
  item, panel, and server wiring from SH1 are unchanged).
- Click-to-inspect a plotted point (R's `plot_click` → `clicked_stakeholder`).
  Matplotlib `@render.plot` in this repo is a static image; interactive point
  selection is not worth the complexity for SH2. Deferred.
- Engagement-activity log + analytics + downloads (SH3, see above).

### 1.3 Decisions baked in

| Decision | Choice | Reason |
|---|---|---|
| Grid representation | 2×2 Mendelow quadrants, points scatter-plotted at numeric Low/Med/High (1–3) | Faithful R port (R uses `PowerNum = HIGH→3, MEDIUM→2, LOW→1`, midlines at 2). A 3-level scale plotted on a 2×2 grid: MEDIUM sits on the boundary visually. Answers the "2×2 vs 3×3" question — 2×2, per source of truth. |
| Rendering | matplotlib via `@render.plot` | SESPy's established plot convention (analysis_metrics/boolean/simulation/bot all use `@render.plot` + matplotlib). No plotly/pyvis. |
| Quadrant binning for the summary | **≥ MEDIUM = high side** (so `key_players` = power∈{MEDIUM,HIGH} ∧ interest∈{MEDIUM,HIGH}) | Matches the plot's colored quadrant **regions** (R's background rects span `[2, 3.5]`, i.e. start at the midline), and **fixes R's undercount**: R's summary counted only the 4 strict corners (`Power=="HIGH" & Interest=="HIGH"` …), silently dropping every MEDIUM stakeholder from all counts. With ≥MEDIUM=high every stakeholder with both values set lands in exactly one quadrant. Documented divergence/improvement over R. |
| Jitter | **Deterministic** offset derived from the stakeholder's list index (not random) | R uses random `jitter()`, so points jump on every re-render. A deterministic offset keeps points stable across reactive re-renders (better UX) while still de-overlapping co-located points. |
| Placement | Sub-tab inside the Stakeholders panel via `ui.navset_tab` | Mirrors R's tabbed module (Register / Grid / Engagement); keeps stakeholder features cohesive; spends no extra flat-nav slot. Pattern precedent: `analysis_boolean.py:58`. |
| Classification location | Pure helpers in `sespy/stakeholders.py` (no matplotlib/Shiny) | Mirrors SH1's pure-helper approach; trivially unit-testable; the module just calls them + renders. |

## 2. No data-model change
SH2 adds **nothing** to `sespy/data_structure.py`. It consumes the SH1 fields:
`Stakeholder.power` and `.interest` (canonical codes `"HIGH"|"MEDIUM"|"LOW"|""`),
`.name`, and (for the strategy panel) `.engagement_level`. A stakeholder with an
empty `power` or `interest` is excluded from the grid (and reported as "unplotted"
in the summary — see §4).

## 3. Pure classification helpers (`sespy/stakeholders.py`, extend; no Shiny/matplotlib)

```python
# Canonical quadrant keys + the level→axis-position map.
_LEVEL_NUM = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
QUADRANTS = ("key_players", "keep_satisfied", "keep_informed", "monitor")


def level_num(level: str) -> int | None:
    """Map a power/interest code to its 1–3 axis position, or None if blank/unknown."""
    return _LEVEL_NUM.get(level)


def classify_quadrant(power: str, interest: str) -> str | None:
    """Mendelow quadrant for a (power, interest) pair, or None if either is unset.

    Binning: a value is "high" iff it is MEDIUM or HIGH (>= 2 on the 1–3 axis),
    matching the plot's colored regions. This classifies MEDIUM stakeholders
    (R dropped them from its summary entirely).
    """
    p, i = level_num(power), level_num(interest)
    if p is None or i is None:
        return None
    high_p, high_i = p >= 2, i >= 2
    if high_p and high_i:
        return "key_players"
    if high_p and not high_i:
        return "keep_satisfied"
    if not high_p and high_i:
        return "keep_informed"
    return "monitor"


def summarize_quadrants(items: list[Stakeholder]) -> dict:
    """Return {quadrant_key: [stakeholder names]} for the 4 quadrants, plus
    "unplotted" for stakeholders missing power or interest. Every quadrant key is
    always present (possibly empty) so the UI can render a stable layout."""
    out = {q: [] for q in QUADRANTS}
    out["unplotted"] = []
    for s in items:
        q = classify_quadrant(s.power, s.interest)
        out[q if q is not None else "unplotted"].append(s.name)
    return out
```

## 4. Module changes (`sespy/modules/pims_stakeholders.py`)

### 4.1 UI — wrap existing register + new grid in `navset_tab`
The current `pims_stakeholders_ui` returns the register card directly. Restructure:
```python
@module.ui
def pims_stakeholders_ui() -> ui.Tag:
    return ui.div(
        ui.h3(_t("stakeholders.title")),
        ui.navset_tab(
            ui.nav_panel(_t("stakeholders.tab_register"), _register_panel()),
            ui.nav_panel(_t("stakeholders.tab_grid"), _grid_panel()),
        ),
        class_="sespy-card",
    )
```
`_register_panel()` = the existing `layout_columns(...)` form+table content (extracted
verbatim — no behavior change). `_grid_panel()` = `ui.output_plot("power_interest_grid", height="520px")` + `ui.output_ui("grid_summary")`.

### 4.2 Server — grid plot
```python
@output
@render.plot
def power_interest_grid():
    import matplotlib.pyplot as plt
    items = [s for s in _items() if level_num(s.power) and level_num(s.interest)]
    fig, ax = plt.subplots()
    # quadrant background rects (gray / blue / amber / green), dashed midlines at 2,
    # quadrant labels (4 corners), axis ticks {1:Low,2:Med,3:High}, xlim/ylim 0.5–3.5.
    # deterministic jitter: offset = ((idx * 0.37) % 1 - 0.5) * 0.3 on each axis
    # scatter points (x=interest_num, y=power_num), annotate each with s.name.
    # empty state: if not items -> ax.text("Add stakeholders with Power and Interest…")
    ax.set_xlabel(tr("stakeholders.grid.interest_axis"))
    ax.set_ylabel(tr("stakeholders.grid.power_axis"))
    ax.set_title(tr("stakeholders.grid.title"))
    return fig
```
- Axis labels/ticks/quadrant labels all via `tr(...)` (i18n). Colors mirror R
  (gray monitor, blue keep-informed, amber keep-satisfied, green key-players).
- Deterministic jitter keyed off the enumerate index keeps points stable.

### 4.3 Server — grid summary
```python
@output
@render.ui
def grid_summary():
    summary = summarize_quadrants(_items())
    # For each of the 4 quadrants: a heading (strategy name), the recommended
    # action text (tr "stakeholders.grid.<quad>.strategy"), the count, and the
    # member names (or an em-dash if empty). Plus an "unplotted" line if any
    # stakeholder is missing power/interest.
    ...
    return ui.div(...)
```
- The 4 strategy descriptions are i18n strings, not hard-coded English.
- Reads `_items()` reactively → updates when the Register tab adds/edits/removes.

### 4.4 No new server inputs/handlers, no event emits
SH2 is read-only over `project_data`; it adds no `reactive.value`, no
`event_bus` emit, no CRUD. The existing SH1 handlers are untouched.

## 5. i18n (`sespy/translations/core.json`, extend; 9 langs, English placeholders)
New keys (inside `"translation"`):
- `stakeholders.tab_register` → "Register"
- `stakeholders.tab_grid` → "Power-Interest Grid"
- `stakeholders.grid.title` → "Stakeholder Power-Interest Grid"
- `stakeholders.grid.power_axis` → "Power / influence →"
- `stakeholders.grid.interest_axis` → "Interest / impact →"
- `stakeholders.grid.empty` → "Add stakeholders with Power and Interest set to populate the grid."
- `stakeholders.grid.summary_heading` → "Grid summary"
- `stakeholders.grid.total` → "Total plotted"
- `stakeholders.grid.unplotted` → "Not plotted (missing power/interest)"
- `stakeholders.grid.key_players` → "Key players"
- `stakeholders.grid.keep_satisfied` → "Keep satisfied"
- `stakeholders.grid.keep_informed` → "Keep informed"
- `stakeholders.grid.monitor` → "Monitor"
- `stakeholders.grid.key_players.strategy` → "Manage closely — engage and collaborate; these high-power, high-interest stakeholders are critical."
- `stakeholders.grid.keep_satisfied.strategy` → "Keep satisfied — high power but lower interest; meet their needs without over-involving them."
- `stakeholders.grid.keep_informed.strategy` → "Keep informed — lower power but high interest; consult and keep them in the loop."
- `stakeholders.grid.monitor.strategy` → "Monitor — lower power and interest; minimal effort, periodic check-ins."
- `stakeholders.grid.high` / `.medium` / `.low` → axis tick labels "High"/"Medium"/"Low" (or reuse existing `stakeholders.power.HIGH` etc. — implementer may reuse rather than add).

## 6. Testing

### 6.1 Unit (`tests/test_stakeholders.py`, extend)
- `classify_quadrant` truth table: HIGH/HIGH→key_players; MEDIUM/MEDIUM→key_players
  (≥MEDIUM rule); HIGH/LOW→keep_satisfied; LOW/HIGH→keep_informed; LOW/LOW→monitor;
  MEDIUM/LOW→keep_satisfied; ""/HIGH→None; HIGH/""→None; "junk"/HIGH→None.
- `level_num`: HIGH→3, MEDIUM→2, LOW→1, ""→None, "x"→None.
- `summarize_quadrants`: a list spanning all quadrants + one blank-power stakeholder
  → correct member lists per quadrant and the blank one in "unplotted"; all 4
  quadrant keys + "unplotted" always present (empty lists when none).

### 6.2 e2e (`tests/test_stakeholders_e2e.py`, extend the existing script)
After the existing CRUD assertions (or in a focused addition): add a stakeholder with
power=HIGH, interest=HIGH; click the **Power-Interest Grid** sub-tab; assert (a) the
plot image renders — `#stakeholders-power_interest_grid img` is present (matplotlib
`@render.plot` emits an `<img>`); and (b) the summary (`#stakeholders-grid_summary`)
text contains the stakeholder's name under the "Key players" strategy. Drive the
sub-tab switch by clicking the tab link (a Bootstrap `nav-link` with the tab label
text — develop the exact selector against the live DOM, as with SH1's row selector).

## 7. Files

| File | Status | Purpose |
|---|---|---|
| `sespy/stakeholders.py` | edit | add `level_num`, `classify_quadrant`, `summarize_quadrants`, `QUADRANTS` (pure) |
| `sespy/modules/pims_stakeholders.py` | edit | UI → `navset_tab` (Register + Grid); `@render.plot power_interest_grid`; `@render.ui grid_summary` |
| `sespy/translations/core.json` | edit | `stakeholders.tab_*` + `stakeholders.grid.*` keys (9 langs) |
| `tests/test_stakeholders.py` | edit | unit tests for the 3 helpers |
| `tests/test_stakeholders_e2e.py` | edit | grid sub-tab renders + summary updates |

**Unchanged:** `sespy/data_structure.py`, `sespy/persistent_storage.py`, `app.py`,
all other modules. No schema bump, no `Project` change, no new nav item.
