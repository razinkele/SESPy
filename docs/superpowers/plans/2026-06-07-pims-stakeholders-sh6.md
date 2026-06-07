# PIMS Stakeholders SH6 — Export Downloads — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add R Tab 5's three export downloads to the SH5 Analysis sub-tab: an Excel full report (openpyxl), a Power-Interest grid PNG (matplotlib), and a summary PDF (reportlab). Pure byte-builders + `@render.download` wiring; i18n; unit + e2e tests.

**Architecture:** Pure byte-builders in a new `sespy/stakeholder_reports.py` (Shiny-free; heavy libs lazy-imported inside each function). The module wires three `ui.download_button`s in `_analysis_panel()` + three `@render.download` handlers that `yield` builder bytes. **No data-model, schema, persistence, or `app.py` change.**

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, openpyxl, matplotlib, reportlab, pytest, Playwright. Run via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-07-pims-stakeholders-sh6-design.md` (rev. 2).

**Plan rev. 2 (from deep-review):** (a) **`reportlab>=4.0` declared** as a runtime
dependency in `pyproject.toml` + `environment.yml` (it was only present locally; clean
installs would `ModuleNotFoundError`); (b) the PDF builder **escapes** the project
name via `xml.sax.saxutils.escape` before `Paragraph` (reportlab parses markup — a
name like `<b>Bad` would raise), with a unit test; (c) corrected the e2e citation —
`test_report_e2e.py` uses accept-downloads/`expect_download` but saves bytes; SH6 uses
the lighter `download.suggested_filename` assertion.

**Conventions verified against live code + a runnable library check (2026-06-07):**
- `@render.download` pattern (`report_export.py:84-97`): `@render.download(filename=lambda: f"…-{_stamp()}.<ext>")` then `yield <bytes>`; handlers do **NOT** use `@output`; `_stamp()` = `datetime.now().strftime("%Y%m%d-%H%M%S")`. `render` is already imported in `pims_stakeholders.py`.
- Playwright downloads (`test_report_e2e.py:12,31-36`): `browser.new_context(accept_downloads=True)`; `async with page.expect_download() as dl_info: await page.click(...)`; `download = await dl_info.value`. (That test then saves bytes; SH6 uses the lighter `download.suggested_filename.endswith("...")` assertion — a standard Playwright `Download` attribute.)
- Libs present + idioms CONFIRMED by running them: openpyxl `wb.save(BytesIO()); buf.getvalue()` → `PK\x03\x04`; matplotlib `Figure()`+`FigureCanvasAgg(fig)`+`fig.savefig(buf, format="png")` → `\x89PNG\r\n\x1a\n` (no pyplot/global state); reportlab `SimpleDocTemplate(BytesIO())`+`doc.build([...])` → `%PDF` (a header-only `Table` is fine; `Table([])` RAISES). PDF uses **reportlab** (installed, pure-Python) — NOT `report.py`'s optional WeasyPrint.
- Data model: `Stakeholder`/`Engagement`/`Communication` dataclasses (`data_structure.py`); `Communication` field is `comm_type`. `level_num` (`stakeholders.py`) maps power/interest → 1..3. `compute_stakeholder_stats` (aliased in the module) returns the 7-key dict.
- Module (`pims_stakeholders.py`): SH5 `_analysis_panel()` (two `layout_columns` rows); server `_items()`/`_engagements()`/`_communications()`/`tr`/`compute_stakeholder_stats`/`project_data`. Existing output ids: `power_interest_grid`, `engagement_coverage`, `type_distribution`, `sector_distribution`, `stakeholder_stats`, the tables — the new download ids (`download_stakeholder_xlsx`/`download_power_interest_png`/`download_summary_pdf`) do **not** collide.
- i18n (`core.json`): top-level `"translation"`; 9 langs (de, el, en, es, fr, it, lt, no, pt); no existing `stakeholders.analysis.export*`.

---

## Task 1: Pure byte-builders (`sespy/stakeholder_reports.py`)

**Files:** Create `sespy/stakeholder_reports.py`; create `tests/test_stakeholder_reports.py`; edit `pyproject.toml` + `environment.yml` (declare `reportlab>=4.0`)

- [ ] **Step 1: Write the failing tests** (`tests/test_stakeholder_reports.py`):
  ```python
  import io

  from openpyxl import load_workbook

  from sespy.data_structure import Communication, Engagement, Stakeholder
  from sespy.stakeholder_reports import (
      build_power_interest_png,
      build_stakeholder_workbook,
      build_summary_pdf,
  )

  _ID = lambda k: k  # noqa: E731  (fake translate for the PNG)


  def _fixture():
      sh = [
          Stakeholder(id="SH001", name="Port Authority", stakeholder_type="government",
                      power="HIGH", interest="HIGH"),
          Stakeholder(id="SH002", name="Coastal NGO", stakeholder_type="ngo",
                      power="LOW", interest="MEDIUM"),
      ]
      eng = [Engagement(id="ENG001", stakeholder_id="SH001", method="workshop")]
      comm = [Communication(id="COMM001", audience="key_players", comm_type="report")]
      return sh, eng, comm


  def test_workbook_is_valid_xlsx_with_three_sheets():
      sh, eng, comm = _fixture()
      data = build_stakeholder_workbook(sh, eng, comm)
      assert data[:4] == b"PK\x03\x04"
      wb = load_workbook(io.BytesIO(data))
      assert wb.sheetnames == ["Stakeholders", "Engagements", "Communications"]
      ws = wb["Stakeholders"]
      # header row + 2 data rows; a known name present
      assert ws.max_row == 3
      assert "Port Authority" in [c.value for c in ws[2]]


  def test_workbook_empty_inputs_header_only():
      data = build_stakeholder_workbook([], [], [])
      wb = load_workbook(io.BytesIO(data))
      assert wb.sheetnames == ["Stakeholders", "Engagements", "Communications"]
      assert wb["Stakeholders"].max_row == 1  # header only


  def test_png_is_valid_png():
      sh, _, _ = _fixture()
      data = build_power_interest_png(sh, translate=_ID)
      assert data[:8] == b"\x89PNG\r\n\x1a\n"


  def test_png_empty_inputs_still_valid():
      data = build_power_interest_png([], translate=_ID)
      assert data[:8] == b"\x89PNG\r\n\x1a\n"


  def test_pdf_is_valid_pdf():
      sh, eng, comm = _fixture()
      from sespy.stakeholders import stakeholder_stats
      stats = stakeholder_stats(sh, eng, comm)
      data = build_summary_pdf("My Project", stats, sh)
      assert data[:4] == b"%PDF"


  def test_pdf_empty_inputs_still_valid():
      from sespy.stakeholders import stakeholder_stats
      data = build_summary_pdf("Empty", stakeholder_stats([], [], []), [])
      assert data[:4] == b"%PDF"


  def test_pdf_escapes_markup_in_project_name():
      # reportlab Paragraph parses markup; an unescaped "<b>" would raise.
      from sespy.stakeholders import stakeholder_stats
      data = build_summary_pdf("<b>Bad & Co", stakeholder_stats([], [], []), [])
      assert data[:4] == b"%PDF"
  ```

- [ ] **Step 2: Run; verify fail** — `micromamba run -n shiny python -m pytest tests/test_stakeholder_reports.py -q` → ImportError (no module).

- [ ] **Step 3: Implement** `sespy/stakeholder_reports.py`:
  ```python
  """Pure byte-builders for the PIMS Stakeholders export downloads (SH6).

  Each function returns file bytes and lazy-imports its heavy library inside the
  body (no Shiny / no matplotlib-pyplot global state), so the module stays cheap to
  import and the builders are unit-testable by magic bytes.
  """
  from __future__ import annotations

  from dataclasses import asdict, fields
  from io import BytesIO

  from sespy.data_structure import Communication, Engagement, Stakeholder
  from sespy.stakeholders import level_num


  def build_stakeholder_workbook(stakeholders, engagements, communications) -> bytes:
      from openpyxl import Workbook

      wb = Workbook()
      specs = [
          ("Stakeholders", Stakeholder, stakeholders),
          ("Engagements", Engagement, engagements),
          ("Communications", Communication, communications),
      ]
      wb.active.title = specs[0][0]
      for i, (name, cls, rows) in enumerate(specs):
          ws = wb.active if i == 0 else wb.create_sheet(name)
          names = [f.name for f in fields(cls)]
          ws.append(names)
          for obj in rows:
              d = asdict(obj)
              ws.append([d.get(n, "") for n in names])
      buf = BytesIO()
      wb.save(buf)
      return buf.getvalue()


  def build_power_interest_png(stakeholders, *, translate) -> bytes:
      from matplotlib.backends.backend_agg import FigureCanvasAgg
      from matplotlib.figure import Figure

      fig = Figure(figsize=(8, 6), dpi=150)
      FigureCanvasAgg(fig)
      ax = fig.subplots()
      ax.set_xlim(0.5, 3.5)
      ax.set_ylim(0.5, 3.5)
      ax.set_xlabel(translate("stakeholders.grid.interest_axis"))
      ax.set_ylabel(translate("stakeholders.grid.power_axis"))
      ax.set_title(translate("stakeholders.grid.title"))
      ax.axhline(2, color="gray", lw=1, ls="--")
      ax.axvline(2, color="gray", lw=1, ls="--")
      plotted = [s for s in stakeholders
                 if level_num(s.power) and level_num(s.interest)]
      for idx, s in enumerate(plotted):
          off = ((idx * 0.37) % 1 - 0.5) * 0.3
          x = level_num(s.interest) + off   # x = interest
          y = level_num(s.power) + off      # y = power
          ax.scatter([x], [y], s=120, color="#2E86AB", zorder=3)
          ax.annotate(s.name, (x, y), textcoords="offset points",
                      xytext=(0, 8), ha="center", fontsize=8)
      if not plotted:
          ax.text(2, 2, translate("stakeholders.grid.empty"),
                  ha="center", va="center")
      buf = BytesIO()
      fig.savefig(buf, format="png", bbox_inches="tight")
      return buf.getvalue()


  def build_summary_pdf(project_name, stats, stakeholders) -> bytes:
      from xml.sax.saxutils import escape

      from reportlab.lib.pagesizes import A4
      from reportlab.lib.styles import getSampleStyleSheet
      from reportlab.platypus import (
          Paragraph, SimpleDocTemplate, Spacer, Table,
      )

      buf = BytesIO()
      doc = SimpleDocTemplate(buf, pagesize=A4)
      styles = getSampleStyleSheet()
      title = f"Stakeholder summary — {escape(str(project_name))}"
      story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
      stat_rows = [["Metric", "Value"]]
      for k in ("total", "types", "sectors", "high_power", "high_interest",
                "engagements", "communications"):
          stat_rows.append([k, str(stats.get(k, 0))])
      story.append(Table(stat_rows))
      story.append(Spacer(1, 18))
      sh_rows = [["Name", "Type", "Power", "Interest"]]
      if stakeholders:
          sh_rows += [[s.name, s.stakeholder_type, s.power, s.interest]
                      for s in stakeholders]
      else:
          sh_rows.append(["No stakeholders", "", "", ""])
      story.append(Table(sh_rows))
      doc.build(story)
      return buf.getvalue()
  ```
  (The PNG reuses the SH2 grid's deterministic jitter + axis i18n keys, which already
  exist; `translate` is injected so the builder stays Shiny-free.)

- [ ] **Step 4: Run + flake8** — `micromamba run -n shiny python -m pytest tests/test_stakeholder_reports.py -q` + `flake8 sespy/stakeholder_reports.py tests/test_stakeholder_reports.py --max-line-length=100` → green/clean.

- [ ] **Step 5: Commit** (include the dependency declarations)
  ```bash
  git add sespy/stakeholder_reports.py tests/test_stakeholder_reports.py pyproject.toml environment.yml
  git commit -m "feat(stakeholders): pure export byte-builders (xlsx/png/pdf) + reportlab dep"
  ```

---

## Task 2: i18n keys (`stakeholders.analysis.export_*`)

**Files:** Modify `sespy/translations/core.json`

- [ ] **Step 1: Add the keys (programmatic)** — temp script: load JSON, reuse the 9-lang set from `stakeholders.tab_activity`, add `{lang: english}`, dump with `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`, delete the script. Keys:
  - `stakeholders.analysis.export_heading` → "Export stakeholder data"
  - `stakeholders.analysis.export_excel` → "Download full report (Excel)"
  - `stakeholders.analysis.export_png` → "Download Power-Interest grid (PNG)"
  - `stakeholders.analysis.export_pdf` → "Download summary (PDF)"

- [ ] **Step 2: Validate**
  ```
  micromamba run -n shiny python -c "import json; d=json.load(open('sespy/translations/core.json',encoding='utf-8'))['translation']; ks=['stakeholders.analysis.export_heading','stakeholders.analysis.export_excel','stakeholders.analysis.export_png','stakeholders.analysis.export_pdf']; [print(k, sorted(d[k].keys())==sorted(d['stakeholders.tab_activity'].keys()), repr(d[k]['en'])) for k in ks]"
  ```
  Expect each present, lang set identical; `git diff --stat` shows only insertions.

- [ ] **Step 3: Commit**
  ```bash
  git add sespy/translations/core.json
  git commit -m "i18n: stakeholders.analysis.export_* (9 langs)"
  ```

---

## Task 3: Module — Export card + download handlers

**Files:** Modify `sespy/modules/pims_stakeholders.py`

- [ ] **Step 1: Imports + `_stamp` + UI** — add near the top:
  ```python
  from datetime import date, datetime   # extend the existing `from datetime import date`
  from sespy.stakeholder_reports import (
      build_power_interest_png,
      build_stakeholder_workbook,
      build_summary_pdf,
  )
  ```
  Add a module-level helper (near `_choices`):
  ```python
  def _stamp() -> str:
      return datetime.now().strftime("%Y%m%d-%H%M%S")
  ```
  Extend `_analysis_panel()` — append a full-width Export card as a final row:
  ```python
      ui.card(
          ui.h5(_t("stakeholders.analysis.export_heading")),
          ui.download_button("download_stakeholder_xlsx",
                             _t("stakeholders.analysis.export_excel")),
          ui.download_button("download_power_interest_png",
                             _t("stakeholders.analysis.export_png")),
          ui.download_button("download_summary_pdf",
                             _t("stakeholders.analysis.export_pdf")),
      ),
  ```
  (Add it inside the `_analysis_panel` `ui.div(...)`, after the second
  `layout_columns` row — i.e. as the div's last child.)

- [ ] **Step 2: Server handlers** — append after the SH5 analysis renders (NO `@output`
  on download handlers, per the report_export precedent):
  ```python
      @render.download(filename=lambda: f"stakeholders-{_stamp()}.xlsx")
      def download_stakeholder_xlsx():
          yield build_stakeholder_workbook(_items(), _engagements(), _communications())

      @render.download(filename=lambda: f"power-interest-{_stamp()}.png")
      def download_power_interest_png():
          yield build_power_interest_png(_items(), translate=tr)

      @render.download(filename=lambda: f"stakeholder-summary-{_stamp()}.pdf")
      def download_summary_pdf():
          stats = compute_stakeholder_stats(_items(), _engagements(), _communications())
          yield build_summary_pdf(project_data.get().metadata.name, stats, _items())
  ```

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
  git commit -m "feat(stakeholders): Analysis export downloads (xlsx/png/pdf buttons)"
  ```

---

## Task 4: e2e — the three downloads fire

**Files:** Modify `tests/test_stakeholders_e2e.py`

- [ ] **Step 1: Enable downloads on the context** — change the single
  `browser.new_context()` call to `browser.new_context(accept_downloads=True)`
  (sections 1–10 don't download, so this is safe). Find the exact current call first.

- [ ] **Step 2: Add section 11** — after section 10 (still on the Analysis tab), before
  the screenshot:
  ```python
  # 11. EXPORT — the three download buttons fire with the right file types
  for btn, ext in (("download_stakeholder_xlsx", ".xlsx"),
                   ("download_power_interest_png", ".png"),
                   ("download_summary_pdf", ".pdf")):
      async with page.expect_download() as dl_info:
          await page.click(f"#stakeholders-{btn}")
      download = await dl_info.value
      assert download.suggested_filename.endswith(ext), (
          f"{btn} -> {download.suggested_filename}")
  print("11. export: xlsx/png/pdf downloads fire — PASS")
  ```

- [ ] **Step 3: Run** — `micromamba run -n shiny shiny run app.py --port 8000` (background); `micromamba run -n shiny python tests/test_stakeholders_e2e.py` → exit 0 (re-run once if the section-7 grid img flakes). Stop the server.

- [ ] **Step 4: Commit**
  ```bash
  git add tests/test_stakeholders_e2e.py
  git commit -m "test(stakeholders): e2e — Analysis export downloads fire"
  ```

---

## Final verification
- [ ] `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — green.
- [ ] `micromamba run -n shiny python tests/run_e2e.py` — stakeholders e2e passes (note known pre-existing pyvis/render flakiness on data_entry/simulation under load).
- [ ] Then invoke **superpowers:finishing-a-development-branch** (merge no-ff into `main`, delete the branch).

## Sequencing notes
- TDD order: byte-builders (1) → i18n (2) → module wiring (3) → e2e (4). No data-model task. Branch `feat/pims-stakeholders-sh6` is already cut from `main`.
- SH6 completes the PIMS Stakeholders port (all 5 R tabs).
