# PIMS Stakeholders SH5 — Analysis Summary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only **Analysis** sub-tab to the Stakeholders panel: a 7-metric statistics summary + 3 matplotlib charts (engagement coverage, type distribution, sector distribution). Pure helpers + render layer; i18n; tests.

**Architecture:** A pure read/visualization layer over SH1–SH4 data — like SH2's grid. Pure aggregation helpers (`stakeholder_stats`, `engagement_coverage`, `count_by`) in `sespy/stakeholders.py` (Shiny-free); the module adds a 5th `nav_panel`, a `@render.ui` stats summary, and three `@render.plot` charts. **No data-model, schema, persistence, or `app.py` change.**

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, matplotlib, pandas, pytest, Playwright. Run via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-07-pims-stakeholders-sh5-design.md` (rev. 2).

**Conventions verified against live code (2026-06-07, post-SH4):**
- `Stakeholder` fields: `stakeholder_type`, `sector`, `power`, `interest` (`data_structure.py`); `Engagement.stakeholder_id`; `Project.stakeholders`/`.engagements`/`.communications`. **No schema change** (`PROJECT_SCHEMA_VERSION = 5` stays).
- `@render.plot` idiom (`pims_stakeholders.py:336-385`, SH2 grid): `import matplotlib.pyplot as plt` inside; `fig, ax = plt.subplots()`; draw; `return fig`. UI companion `ui.output_plot("id", height="...")`.
- `@render.ui` idiom (SH2 `grid_summary`): returns `ui.div(...)`; `ui.output_ui("id")` companion.
- Module: code lists `_TYPE_CODES` (:37) and `_SECTOR_CODES` (:39) are module-level; `_choices`; plain un-decorated `_register_panel`/`_grid_panel`/`_engagement_panel`/`_communication_panel`; `navset_tab(..., id="stakeholder_tabs")` now has **4** panels; server has `tr`/`_t`/`_items()`/`_engagements()`/`_communications()`; existing SH1's `stakeholders.type.*`/`stakeholders.sector.*` i18n labels cover all codes (verified).
- **Name-collision (rev. 2):** the pure helpers `stakeholder_stats`/`engagement_coverage` must be imported ALIASED (`compute_stakeholder_stats`/`compute_engagement_coverage`) because the `@render.ui`/`@render.plot` output functions reuse those exact names (= the output ids `ui.output_ui("stakeholder_stats")`/`ui.output_plot("engagement_coverage")`).
- i18n (`core.json`): top-level `"translation"`; 9 langs (de, el, en, es, fr, it, lt, no, pt); JSON round-trips with `json.dumps(d, indent=2, ensure_ascii=False) + "\n"`; **no existing `stakeholders.analysis*`/`tab_analysis`** (verified).
- Tests: `tests/test_stakeholders.py` style + `_proj_with`/`_proj_with_eng`/`_proj_with_comm` factories. e2e (`test_stakeholders_e2e.py`): SH4 section 9 switches tab via `a[data-value='Communication Plan']` and reads the table inline in a poll loop; `_set_select` helper.

---

## Task 1: Pure aggregation helpers

**Files:** Modify `sespy/stakeholders.py`, `tests/test_stakeholders.py`

- [ ] **Step 1: Write the failing tests** — extend the `from sespy.stakeholders import (...)` block with `count_by`, `engagement_coverage`, `stakeholder_stats`. Append:
  ```python
  def test_stakeholder_stats_counts():
      sh = [
          Stakeholder(id="SH001", name="A", stakeholder_type="government",
                      sector="fisheries", power="HIGH", interest="HIGH"),
          Stakeholder(id="SH002", name="B", stakeholder_type="ngo",
                      sector="fisheries", power="HIGH", interest="LOW"),
          Stakeholder(id="SH003", name="C", stakeholder_type="ngo",
                      sector="", power="LOW", interest="HIGH"),
      ]
      eng = [Engagement(id="ENG001", stakeholder_id="SH001")]
      comm = [Communication(id="COMM001"), Communication(id="COMM002")]
      s = stakeholder_stats(sh, eng, comm)
      assert s["total"] == 3
      assert s["types"] == 2          # government, ngo (distinct non-empty)
      assert s["sectors"] == 1        # fisheries (blank not counted)
      assert s["high_power"] == 2
      assert s["high_interest"] == 2
      assert s["engagements"] == 1
      assert s["communications"] == 2


  def test_stakeholder_stats_empty_is_all_zero():
      s = stakeholder_stats([], [], [])
      assert s == {"total": 0, "types": 0, "sectors": 0, "high_power": 0,
                   "high_interest": 0, "engagements": 0, "communications": 0}


  def test_engagement_coverage():
      sh = [Stakeholder(id="SH001", name="A"), Stakeholder(id="SH002", name="B")]
      assert engagement_coverage([], []) == 0.0
      assert engagement_coverage(sh, []) == 0.0
      # one of two engaged, deduped across multiple engagements
      eng = [Engagement(id="ENG001", stakeholder_id="SH001"),
             Engagement(id="ENG002", stakeholder_id="SH001")]
      assert engagement_coverage(sh, eng) == 50.0
      eng2 = eng + [Engagement(id="ENG003", stakeholder_id="SH002")]
      assert engagement_coverage(sh, eng2) == 100.0


  def test_count_by_first_seen_order_and_blanks():
      sh = [
          Stakeholder(id="SH001", name="A", stakeholder_type="ngo"),
          Stakeholder(id="SH002", name="B", stakeholder_type="government"),
          Stakeholder(id="SH003", name="C", stakeholder_type="ngo"),
          Stakeholder(id="SH004", name="D", stakeholder_type=""),
      ]
      assert count_by(sh, "stakeholder_type") == {"ngo": 2, "government": 1, "": 1}
      assert count_by([], "sector") == {}
  ```

- [ ] **Step 2: Run; verify fail** — ImportError on the new names.

- [ ] **Step 3: Implement** — append to `sespy/stakeholders.py`:
  ```python
  # --- SH5: analysis summary (pure) ------------------------------------------
  def stakeholder_stats(stakeholders, engagements, communications) -> dict:
      return {
          "total": len(stakeholders),
          "types": len({s.stakeholder_type for s in stakeholders if s.stakeholder_type}),
          "sectors": len({s.sector for s in stakeholders if s.sector}),
          "high_power": sum(1 for s in stakeholders if s.power == "HIGH"),
          "high_interest": sum(1 for s in stakeholders if s.interest == "HIGH"),
          "engagements": len(engagements),
          "communications": len(communications),
      }


  def engagement_coverage(stakeholders, engagements) -> float:
      if not stakeholders:
          return 0.0
      engaged = {e.stakeholder_id for e in engagements}
      covered = sum(1 for s in stakeholders if s.id in engaged)
      return covered / len(stakeholders) * 100


  def count_by(stakeholders, field: str) -> dict:
      counts: dict = {}
      for s in stakeholders:
          key = getattr(s, field)
          counts[key] = counts.get(key, 0) + 1
      return counts
  ```
  (`Stakeholder`/`Engagement`/`Communication` are already imported in this file.)

- [ ] **Step 4: Run + flake8** — `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q` + `flake8 sespy/stakeholders.py tests/test_stakeholders.py --max-line-length=100` → green/clean.

- [ ] **Step 5: Commit**
  ```bash
  git add sespy/stakeholders.py tests/test_stakeholders.py
  git commit -m "feat(stakeholders): pure analysis helpers (stats/coverage/count_by)"
  ```

---

## Task 2: i18n keys (`stakeholders.analysis.*` + `stakeholders.tab_analysis`)

**Files:** Modify `sespy/translations/core.json`

- [ ] **Step 1: Add the keys (programmatic)** — temp script: load JSON, reuse the 9-lang set from `stakeholders.tab_activity`, add each key as `{lang: english}`, dump with `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`, then delete the script. Keys + English:
  - `stakeholders.tab_analysis` → **"Analysis"**
  - `stakeholders.analysis.heading` → "Stakeholder analysis summary"
  - `stakeholders.analysis.stats_heading` → "Stakeholder statistics"
  - `stakeholders.analysis.empty` → "No stakeholders added yet."
  - `stakeholders.analysis.unset` → "(unset)"
  - `stakeholders.analysis.total` → "Total stakeholders"
  - `stakeholders.analysis.types` → "Stakeholder types"
  - `stakeholders.analysis.sectors` → "Sectors represented"
  - `stakeholders.analysis.high_power` → "High-power stakeholders"
  - `stakeholders.analysis.high_interest` → "High-interest stakeholders"
  - `stakeholders.analysis.engagements` → "Total engagements"
  - `stakeholders.analysis.communications` → "Total communications"
  - `stakeholders.analysis.coverage_title` → "Stakeholder engagement coverage"
  - `stakeholders.analysis.engaged` → "Engaged"
  - `stakeholders.analysis.not_engaged` → "Not engaged"
  - `stakeholders.analysis.percentage` → "Percentage"
  - `stakeholders.analysis.by_type` → "Stakeholders by type"
  - `stakeholders.analysis.by_sector` → "Stakeholders by sector"
  - `stakeholders.analysis.count` → "Count"
  - `stakeholders.analysis.add_stakeholders` → "Add stakeholders to see this chart."

- [ ] **Step 2: Validate**
  ```
  micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation']; ks=['stakeholders.tab_analysis','stakeholders.analysis.total','stakeholders.analysis.by_type','stakeholders.analysis.empty','stakeholders.analysis.add_stakeholders']; [print(k, sorted(d[k].keys())==sorted(d['stakeholders.tab_activity'].keys()), repr(d[k]['en'])) for k in ks]"
  ```
  Expect each present, language set identical to `tab_activity`'s; `git diff --stat` shows only insertions.

- [ ] **Step 3: Commit**
  ```bash
  git add sespy/translations/core.json
  git commit -m "i18n: stakeholders.analysis.* + tab_analysis (9 langs)"
  ```

---

## Task 3: Module — Analysis sub-tab

**Files:** Modify `sespy/modules/pims_stakeholders.py`

- [ ] **Step 1: Imports + panel** — extend the `from sespy.stakeholders import (...)` block, **aliasing** the two colliding helper names:
  ```python
  from sespy.stakeholders import (
      ...,  # existing
      count_by,
      engagement_coverage as compute_engagement_coverage,
      stakeholder_stats as compute_stakeholder_stats,
  )
  ```
  Add a module-level label helper (near `_choices`):
  ```python
  def _code_label(code, group, known, translate):
      if not code:
          return translate("stakeholders.analysis.unset")
      if code in known:
          return translate(f"stakeholders.{group}.{code}")
      return code
  ```
  Add a plain panel next to `_communication_panel`:
  ```python
  def _analysis_panel() -> ui.Tag:
      """Analysis tab — statistics summary + distribution charts. Plain (un-decorated)."""
      return ui.div(
          ui.h5(_t("stakeholders.analysis.heading")),
          ui.layout_columns(
              ui.card(
                  ui.h5(_t("stakeholders.analysis.stats_heading")),
                  ui.output_ui("stakeholder_stats"),
              ),
              ui.card(ui.output_plot("engagement_coverage", height="300px")),
              col_widths=[5, 7],
          ),
          ui.layout_columns(
              ui.card(ui.output_plot("type_distribution", height="300px")),
              ui.card(ui.output_plot("sector_distribution", height="300px")),
              col_widths=[6, 6],
          ),
      )
  ```
  Add the 5th nav panel (after the `tab_comm` panel):
  ```python
  ui.nav_panel(_t("stakeholders.tab_analysis"), _analysis_panel()),
  ```

- [ ] **Step 2: Server renders** — append after the SH4 communication renders:
  ```python
      @output
      @render.ui
      def stakeholder_stats():
          s = compute_stakeholder_stats(_items(), _engagements(), _communications())
          if s["total"] == 0:
              return ui.p(tr("stakeholders.analysis.empty"))
          keys = ("total", "types", "sectors", "high_power", "high_interest",
                  "engagements", "communications")
          return ui.tags.ul(*[
              ui.tags.li(f"{tr('stakeholders.analysis.' + k)}: {s[k]}")
              for k in keys
          ])

      @output
      @render.plot
      def engagement_coverage():
          import matplotlib.pyplot as plt
          fig, ax = plt.subplots()
          items = _items()
          if not items:
              ax.text(0.5, 0.5, tr("stakeholders.analysis.add_stakeholders"),
                      ha="center", va="center")
              ax.axis("off")
              return fig
          cov = compute_engagement_coverage(items, _engagements())
          ax.bar([tr("stakeholders.analysis.engaged"),
                  tr("stakeholders.analysis.not_engaged")],
                 [cov, 100 - cov], color=["#2E86AB", "#CCCCCC"])
          ax.set_ylim(0, 100)
          ax.set_ylabel(tr("stakeholders.analysis.percentage"))
          ax.set_title(f"{tr('stakeholders.analysis.coverage_title')} ({round(cov, 1)}%)")
          return fig

      def _distribution_plot(field, known, group, title_key):
          import matplotlib.pyplot as plt
          fig, ax = plt.subplots()
          items = _items()
          if not items:
              ax.text(0.5, 0.5, tr("stakeholders.analysis.add_stakeholders"),
                      ha="center", va="center")
              ax.axis("off")
              return fig
          counts = count_by(items, field)
          labels = [_code_label(c, group, known, tr) for c in counts]
          ax.bar(labels, list(counts.values()), color="#A23B72")
          ax.set_ylabel(tr("stakeholders.analysis.count"))
          ax.set_title(tr(title_key))
          ax.set_xticklabels(labels, rotation=45, ha="right")
          fig.tight_layout()
          return fig

      @output
      @render.plot
      def type_distribution():
          return _distribution_plot("stakeholder_type", _TYPE_CODES, "type",
                                    "stakeholders.analysis.by_type")

      @output
      @render.plot
      def sector_distribution():
          return _distribution_plot("sector", _SECTOR_CODES, "sector",
                                    "stakeholders.analysis.by_sector")
  ```
  (`ax.set_xticklabels(labels, ...)` after `ax.bar(labels, ...)` is safe — the ticks are already the label positions; alternatively use `ax.tick_params(axis="x", rotation=45)`. Keep `fig.tight_layout()`.)

- [ ] **Step 3: Verify**
  ```
  micromamba run -n shiny python -c "from sespy.modules.pims_stakeholders import pims_stakeholders_ui; pims_stakeholders_ui('stakeholders'); print('ui ok')"
  micromamba run -n shiny python -m flake8 sespy/modules/pims_stakeholders.py --max-line-length=100
  micromamba run -n shiny python -c "import app; print('app ok')"
  ```
  **SH1 input-preservation guard** (count → 10):
  `(Select-String -Path sespy\modules\pims_stakeholders.py -Pattern 'sh_(name|type|sector|contact|interests|role|power|interest|attitude|engagement_level)' -AllMatches | ForEach-Object { $_.Matches.Value }) | Sort-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count`
  Then the unit suite: `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` → green.

- [ ] **Step 4: Commit**
  ```bash
  git add sespy/modules/pims_stakeholders.py
  git commit -m "feat(stakeholders): Analysis sub-tab (stats summary + distribution charts)"
  ```

---

## Task 4: e2e — Analysis stats

**Files:** Modify `tests/test_stakeholders_e2e.py` (extend; sections 1–9 UNCHANGED)

- [ ] **Step 1: Develop selectors against the live app** — `micromamba run -n shiny shiny run app.py --port 8000` (background). Probe: nav `#sespy_nav_stakeholders`, ensure a stakeholder exists, switch to the analysis tab via `#stakeholders-stakeholder_tabs a[data-value='Analysis']`, read `#stakeholders-stakeholder_stats` inner text — confirm it shows the "Total stakeholders" label and a count. Delete the probe.

- [ ] **Step 2: Extend the e2e script** — after section 9, add section 10 (poll the stats UI; reliable, avoids plot-img flake):
  ```python
  # 10. ANALYSIS — switch to the Analysis tab; assert the stats summary
  await page.click(
      "#stakeholders-stakeholder_tabs a[data-value='Analysis']"
  )
  await page.wait_for_timeout(800)
  stats_txt = ""
  for _ in range(16):
      stats_txt = await page.inner_text("#stakeholders-stakeholder_stats")
      if "Total stakeholders" in stats_txt:
          break
      await page.wait_for_timeout(500)
  assert "Total stakeholders" in stats_txt, "analysis stats not rendered"
  print("10. analysis: stats summary rendered — PASS")
  ```
  (Insert before the screenshot block. A stakeholder exists by this point — section 6 added "Coastal NGO".)

- [ ] **Step 3: Run** — with the app on :8000: `micromamba run -n shiny python tests/test_stakeholders_e2e.py` → exit 0 (re-run once if the section-7 grid img flakes). Stop the server.

- [ ] **Step 4: Commit**
  ```bash
  git add tests/test_stakeholders_e2e.py
  git commit -m "test(stakeholders): e2e — Analysis stats summary"
  ```

---

## Final verification
- [ ] `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — green.
- [ ] `micromamba run -n shiny python tests/run_e2e.py` — stakeholders e2e passes (note: `test_data_entry_e2e`/`test_simulation_e2e` have a KNOWN pre-existing pyvis/render-timing flakiness reproducible on `main`, unrelated to SH5).
- [ ] Then invoke **superpowers:finishing-a-development-branch** (merge no-ff into `main`, delete the branch).

## Sequencing notes
- TDD order: pure helpers (1) → i18n (2) → module (3) → e2e (4). No data-model task (no schema change). Branch `feat/pims-stakeholders-sh5` is already cut from `main`.
