# PIMS Stakeholders SH2 — Power-Interest Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Power-Interest (Mendelow) grid + per-quadrant engagement strategies as a second sub-tab of the Stakeholders panel.

**Architecture:** A pure read/visualization layer over SH1's existing `Stakeholder.power`/`.interest`. Pure classification helpers in `sespy/stakeholders.py`; the `pims_stakeholders` module UI is restructured into a `navset_tab` (Register | Power-Interest Grid); the grid is a matplotlib `@render.plot`, the summary a `@render.ui`. **No data-model, schema, persistence, or `app.py` change.**

**Tech Stack:** Python 3.11/3.12, Shiny for Python 1.6.x, matplotlib, pandas, pytest, Playwright. Run via `micromamba run -n shiny ...`.

**Spec:** `docs/superpowers/specs/2026-06-05-pims-stakeholders-sh2-design.md` (rev. 2, post-deep-review).

**Conventions verified against live code (2026-06-05):**
- `@render.plot` idiom (`analysis_metrics.py:191-204`): `import matplotlib.pyplot as plt` inside; `fig, ax = plt.subplots(...)`; draw; `return fig`. UI companion `ui.output_plot("id", height="...")`.
- `navset_tab` (`analysis_boolean.py:58-70`): `ui.navset_tab(ui.nav_panel(label, ui.output_plot(...), ui.output_ui(...)), ..., id="boolean_tabs")` — **id is required**.
- `ui.output_ui("id")` ↔ `@output @render.ui def id(): return ui.div(...)`.
- SH1 module current UI (`pims_stakeholders.py`): `ui.div(ui.h3(_t("stakeholders.title")), ui.layout_columns(ui.card(<form>), ui.card(<table>), col_widths=[5,7]), class_="sespy-card")`. The server already has `_items()` returning `project_data.get().stakeholders` and `tr`/`_t`.
- `sespy/stakeholders.py` already imports `Stakeholder` (line 13) and `next_id`; helpers are appended.
- i18n: `core.json` top-level `"translation"`, per-key 9-lang objects; existing keys `stakeholders.power.HIGH/MEDIUM/LOW` are reused for axis ticks.

---

## Task 1: Pure classification helpers

**Files:**
- Modify: `sespy/stakeholders.py` (append `level_num`, `classify_quadrant`, `summarize_quadrants`, `QUADRANTS`, `_LEVEL_NUM`)
- Test: `tests/test_stakeholders.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stakeholders.py` (the import goes at the TOP with the other imports, not mid-file — to avoid E402):

Top-of-file import to add:
```python
from sespy.stakeholders import (
    classify_quadrant,
    level_num,
    summarize_quadrants,
)
```
Tests (append at end):
```python
def test_level_num():
    assert level_num("HIGH") == 3
    assert level_num("MEDIUM") == 2
    assert level_num("LOW") == 1
    assert level_num("") is None
    assert level_num("x") is None


def test_classify_quadrant_truth_table():
    assert classify_quadrant("HIGH", "HIGH") == "key_players"
    assert classify_quadrant("MEDIUM", "MEDIUM") == "key_players"   # >=MEDIUM=high
    assert classify_quadrant("HIGH", "LOW") == "keep_satisfied"
    assert classify_quadrant("MEDIUM", "LOW") == "keep_satisfied"
    assert classify_quadrant("LOW", "HIGH") == "keep_informed"
    assert classify_quadrant("LOW", "MEDIUM") == "keep_informed"
    assert classify_quadrant("LOW", "LOW") == "monitor"
    assert classify_quadrant("", "HIGH") is None
    assert classify_quadrant("HIGH", "") is None
    assert classify_quadrant("junk", "HIGH") is None


def test_summarize_quadrants():
    items = [
        Stakeholder(id="SH001", name="Key", power="HIGH", interest="HIGH"),
        Stakeholder(id="SH002", name="Sat", power="HIGH", interest="LOW"),
        Stakeholder(id="SH003", name="Inf", power="LOW", interest="HIGH"),
        Stakeholder(id="SH004", name="Mon", power="LOW", interest="LOW"),
        Stakeholder(id="SH005", name="Blank", power="", interest="HIGH"),
    ]
    out = summarize_quadrants(items)
    assert out["key_players"] == ["Key"]
    assert out["keep_satisfied"] == ["Sat"]
    assert out["keep_informed"] == ["Inf"]
    assert out["monitor"] == ["Mon"]
    assert out["unplotted"] == ["Blank"]
    # all keys always present (stable layout)
    assert set(out) == {"key_players", "keep_satisfied", "keep_informed", "monitor", "unplotted"}
```

- [ ] **Step 2: Run; verify fail**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q -k "level_num or classify or summarize"`
Expected: FAIL — `ImportError: cannot import name 'level_num'`.

- [ ] **Step 3: Implement the helpers**

Append to `sespy/stakeholders.py` (it already imports `Stakeholder`; no new import):
```python
# --- SH2: Power-Interest grid classification (pure) -------------------------
_LEVEL_NUM = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
QUADRANTS = ("key_players", "keep_satisfied", "keep_informed", "monitor")


def level_num(level: str) -> int | None:
    """Map a power/interest code to its 1-3 axis position, or None if blank/unknown."""
    return _LEVEL_NUM.get(level)


def classify_quadrant(power: str, interest: str) -> str | None:
    """Mendelow quadrant for a (power, interest) pair, or None if either is unset.

    Binning: a value is "high" iff it is MEDIUM or HIGH (>= 2 on the 1-3 axis),
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


def summarize_quadrants(items: list[Stakeholder]) -> dict[str, list[str]]:
    """Return {quadrant_key: [names]} for the 4 quadrants plus "unplotted"
    (stakeholders missing power or interest). All 5 keys always present."""
    out: dict[str, list[str]] = {q: [] for q in QUADRANTS}
    out["unplotted"] = []
    for s in items:
        q = classify_quadrant(s.power, s.interest)
        out[q if q is not None else "unplotted"].append(s.name)
    return out
```

- [ ] **Step 4: Run; verify pass**

Run: `micromamba run -n shiny python -m pytest tests/test_stakeholders.py -q`
Expected: PASS (all stakeholder tests).

- [ ] **Step 5: flake8 + commit**

Run: `micromamba run -n shiny python -m flake8 sespy/stakeholders.py tests/test_stakeholders.py --max-line-length=100` (expect clean).
```bash
git add sespy/stakeholders.py tests/test_stakeholders.py
git commit -m "feat(stakeholders): pure Power-Interest quadrant classification helpers"
```

---

## Task 2: i18n keys

**Files:**
- Modify: `sespy/translations/core.json`

- [ ] **Step 1: Add the keys (programmatic, lowest-risk)**

Add these keys inside the top-level `"translation"` object, each as an object with all 9 language codes (`en,es,fr,de,lt,pt,it,no,el`) set to the same English string. Use a one-off Python script (load json, add keys if absent, `json.dump(..., indent=2, ensure_ascii=False)` + trailing newline, utf-8) and DELETE the script after. Verify the diff is additive-only and existing non-ASCII (Greek) is preserved (`ensure_ascii=False`).

Keys (values are the English placeholder for all 9 langs):
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

Do NOT add `stakeholders.grid.high/medium/low` — axis ticks reuse the existing
`stakeholders.power.HIGH/MEDIUM/LOW`.

- [ ] **Step 2: Validate**

Run (single line):
`micromamba run -n shiny python -c "import json;d=json.load(open('sespy/translations/core.json',encoding='utf-8'));t=d['translation'];ks=['stakeholders.tab_grid','stakeholders.grid.title','stakeholders.grid.key_players.strategy','stakeholders.grid.monitor'];import sys;[sys.exit('MISSING '+k) for k in ks if k not in t or len(t[k])!=9];print('ok')"`
Expected: `ok`. Then confirm app still imports: `micromamba run -n shiny python -c "import app; print('app ok')"`.

- [ ] **Step 3: Commit**
```bash
git add sespy/translations/core.json
git commit -m "i18n: stakeholders.grid.* + tab keys (9 langs)"
```

---

## Task 3: Module — navset_tab restructure + grid plot + summary

**Files:**
- Modify: `sespy/modules/pims_stakeholders.py`

- [ ] **Step 1: Restructure the UI into a `navset_tab`**

In `pims_stakeholders_ui`, extract the existing `ui.layout_columns(...)` (the form card + table card) into a module-level plain helper `_register_panel()`, add `_grid_panel()`, and wrap both in a `navset_tab`. Replace the current `pims_stakeholders_ui` body:

```python
def _register_panel() -> ui.Tag:
    # The existing SH1 register content, extracted verbatim (no behavior change).
    return ui.layout_columns(
        ui.card(
            ui.card_header(_t("stakeholders.add_heading")),
            ui.input_text("sh_name", _t("stakeholders.name")),
            # ... (all existing form inputs, unchanged) ...
            ui.input_action_button("save_stakeholder", _t("stakeholders.save"),
                                   class_="btn btn-primary"),
            ui.input_action_button("cancel_edit", _t("stakeholders.cancel")),
        ),
        ui.card(
            ui.card_header(_t("stakeholders.title")),
            ui.output_data_frame("stakeholder_table"),
            ui.div(
                ui.input_action_button("edit_selected", _t("stakeholders.edit_selected")),
                ui.input_action_button("remove_selected", _t("stakeholders.remove_selected")),
            ),
        ),
        col_widths=[5, 7],
    )


def _grid_panel() -> ui.Tag:
    return ui.div(
        ui.output_plot("power_interest_grid", height="520px"),
        ui.tags.hr(),
        ui.output_ui("grid_summary"),
    )


@module.ui
def pims_stakeholders_ui() -> ui.Tag:
    return ui.div(
        ui.h3(_t("stakeholders.title")),
        ui.navset_tab(
            ui.nav_panel(_t("stakeholders.tab_register"), _register_panel()),
            ui.nav_panel(_t("stakeholders.tab_grid"), _grid_panel()),
            id="stakeholder_tabs",
        ),
        class_="sespy-card",
    )
```
**IMPORTANT — do not lose inputs.** Move the EXISTING register content into
`_register_panel()` by **reading the current `pims_stakeholders_ui` and copying the two
`ui.card(...)` blocks (form + table) VERBATIM** — do NOT retype from the sketch above
(it elides inputs with `# ...`). The form card has exactly **10 inputs** that must all
survive: `sh_name`, `sh_type`, `sh_sector`, `sh_contact`, `sh_interests`, `sh_role`,
`sh_power`, `sh_interest`, `sh_attitude`, `sh_engagement_level` (plus the `save_stakeholder`,
`cancel_edit` buttons). `_form_fields()` in the server reads all 10 — dropping any
breaks add/edit. Step 5 includes a count check to enforce this.

`_register_panel`/`_grid_panel` are **plain module-level functions returning `ui.Tag`,
with NO `@module.ui` decorator** (decorating them would double-namespace the ids to
e.g. `stakeholders-_register_panel-sh_name` and break `input.sh_name()` resolution).
The inputs they build still receive the `stakeholders` namespace because namespacing is
applied by the enclosing `@module.ui` at render time. Register is listed FIRST →
default-active tab → existing SH1 e2e unaffected.

- [ ] **Step 2: Add imports for the helpers**

At the top of `pims_stakeholders.py`, extend the stakeholders import. The grid render
uses `level_num` (to filter plottable rows) and the summary uses `summarize_quadrants`;
**`classify_quadrant` is NOT imported here** — it's called internally by
`summarize_quadrants` inside `sespy/stakeholders.py`, so importing it at module scope
would be an unused import (flake8 F401). Correct import set (5 names):
```python
from sespy.stakeholders import (
    add_stakeholder,
    level_num,
    remove_stakeholder,
    summarize_quadrants,
    update_stakeholder,
)
```

- [ ] **Step 3: Add the grid plot render (in the server)**

Add inside `pims_stakeholders_server` (after the existing renders/handlers). Mirror `analysis_metrics.py:191`'s `@render.plot` idiom (build `fig, ax`, return `fig`):
```python
    @output
    @render.plot
    def power_interest_grid():
        import matplotlib.pyplot as plt

        items = [s for s in _items()
                 if level_num(s.power) and level_num(s.interest)]
        fig, ax = plt.subplots()
        ax.set_xlim(0.5, 3.5)
        ax.set_ylim(0.5, 3.5)
        ax.set_xlabel(tr("stakeholders.grid.interest_axis"))
        ax.set_ylabel(tr("stakeholders.grid.power_axis"))
        ax.set_title(tr("stakeholders.grid.title"))
        ax.set_xticks([1, 2, 3])
        ax.set_yticks([1, 2, 3])
        tick_labels = [tr("stakeholders.power.LOW"),
                       tr("stakeholders.power.MEDIUM"),
                       tr("stakeholders.power.HIGH")]
        ax.set_xticklabels(tick_labels)
        ax.set_yticklabels(tick_labels)

        if not items:
            ax.text(2, 2, tr("stakeholders.grid.empty"),
                    ha="center", va="center", wrap=True)
            return fig

        # Quadrant background rects (interest=x, power=y); colors mirror R.
        ax.add_patch(plt.Rectangle((0.5, 0.5), 1.5, 1.5, color="#ececec", zorder=0))  # monitor
        ax.add_patch(plt.Rectangle((2, 0.5), 1.5, 1.5, color="#dceaf6", zorder=0))    # keep_informed
        ax.add_patch(plt.Rectangle((0.5, 2), 1.5, 1.5, color="#fbedcf", zorder=0))    # keep_satisfied
        ax.add_patch(plt.Rectangle((2, 2), 1.5, 1.5, color="#d9f0d9", zorder=0))      # key_players
        ax.axhline(2, color="gray", lw=1.5, ls="--")
        ax.axvline(2, color="gray", lw=1.5, ls="--")
        # Quadrant labels
        ax.text(2.75, 2.75, tr("stakeholders.grid.key_players"), ha="center", color="gray", fontweight="bold")
        ax.text(1.25, 2.75, tr("stakeholders.grid.keep_satisfied"), ha="center", color="gray")
        ax.text(2.75, 1.25, tr("stakeholders.grid.keep_informed"), ha="center", color="gray")
        ax.text(1.25, 1.25, tr("stakeholders.grid.monitor"), ha="center", color="gray")

        # Deterministic jitter (stable across re-renders): +/- 0.15 from index.
        for idx, s in enumerate(items):
            off = ((idx * 0.37) % 1 - 0.5) * 0.3
            x = level_num(s.interest) + off
            y = level_num(s.power) + off
            ax.scatter([x], [y], s=120, color="#2E86AB", zorder=3)
            ax.annotate(s.name, (x, y), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8)
        return fig
```

- [ ] **Step 4: Add the grid summary render (in the server)**
```python
    @output
    @render.ui
    def grid_summary():
        summary = summarize_quadrants(_items())
        # total counts only the 4 PLOTTED quadrants; "unplotted" (missing
        # power/interest) is reported separately below.
        total = sum(len(summary[q]) for q in ("key_players", "keep_satisfied",
                                              "keep_informed", "monitor"))

        def _block(key: str) -> ui.Tag:
            names = summary[key]
            return ui.div(
                ui.tags.strong(f"{tr('stakeholders.grid.' + key)} ({len(names)})"),
                ui.p(tr(f"stakeholders.grid.{key}.strategy")),
                ui.p(", ".join(names) if names else "—"),
            )

        blocks = [_block(q) for q in ("key_players", "keep_satisfied",
                                      "keep_informed", "monitor")]
        unplotted = summary["unplotted"]
        footer = [ui.tags.hr(),
                  ui.p(f"{tr('stakeholders.grid.total')}: {total}")]
        if unplotted:
            footer.append(ui.p(f"{tr('stakeholders.grid.unplotted')}: "
                               + ", ".join(unplotted)))
        return ui.div(ui.h5(tr("stakeholders.grid.summary_heading")), *blocks, *footer)
```

- [ ] **Step 5: Verify**

```
micromamba run -n shiny python -c "from sespy.modules.pims_stakeholders import pims_stakeholders_ui, pims_stakeholders_server; pims_stakeholders_ui('stakeholders'); print('ok')"
micromamba run -n shiny python -m flake8 sespy/modules/pims_stakeholders.py --max-line-length=100
micromamba run -n shiny python -c "import app; print('app ok')"
```
**Input-preservation guard** — confirm all 10 register inputs survived the refactor:
`grep -oE "sh_(name|type|sector|contact|interests|role|power|interest|attitude|engagement_level)" sespy/modules/pims_stakeholders.py | sort -u | wc -l` → must be **10**. If fewer, an input was dropped in the `_register_panel()` extraction — fix before proceeding.
Expected: `ok`, flake8 clean, `app ok`, count 10. Then full unit suite (exclude self-running e2e):
`micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` → all pass.

- [ ] **Step 6: Commit**
```bash
git add sespy/modules/pims_stakeholders.py
git commit -m "feat(stakeholders): Power-Interest grid sub-tab (plot + quadrant summary)"
```

---

## Task 4: e2e — grid sub-tab renders + summary

**Files:**
- Modify: `tests/test_stakeholders_e2e.py` (extend the existing script)

- [ ] **Step 1: Develop the tab-switch selector against the live app**

Launch `micromamba run -n shiny shiny run app.py --port 8000` (background). Using the Playwright MCP: nav to `#sespy_nav_stakeholders`, add a stakeholder with power=HIGH & interest=HIGH (via the existing form pattern + `el.value`+dispatch selects), then find the selector that switches to the **Power-Interest Grid** sub-tab (a Bootstrap `nav-link` — likely `#stakeholders-stakeholder_tabs` contains `a.nav-link` elements; click the one whose text is the grid tab label, e.g. `page.click("#stakeholders-stakeholder_tabs a:has-text('Power-Interest Grid')")`). Confirm via snapshot that the plot `<img>` appears and the summary text shows the name. Record the working selector.

- [ ] **Step 2: Extend the e2e script**

After the existing CRUD assertions in `tests/test_stakeholders_e2e.py` (which stay UNCHANGED — Register is the default tab), add a focused grid section. In the Register tab, add a stakeholder with a **concrete, documented name** held in a variable — use `KEY_NAME = "TestKey"` — and power=HIGH & interest=HIGH (drive the selects via the `el.value`+dispatch pattern). Then click the grid sub-tab (your Step 1 selector) and assert. There is NO literal `<...>` placeholder — use the `KEY_NAME` variable in both the add step and the assertions:
```python
KEY_NAME = "TestKey"
# ... (add a stakeholder named KEY_NAME with sh_power=HIGH, sh_interest=HIGH, sh_type=government) ...
# plot renders as an <img> (matplotlib @render.plot)
await page.wait_for_selector("#stakeholders-power_interest_grid img", timeout=10000)
# summary lists the stakeholder under Key players
txt = ""
for _ in range(16):
    txt = await page.inner_text("#stakeholders-grid_summary")
    if "Key players" in txt and KEY_NAME in txt:
        break
    await page.wait_for_timeout(500)
assert "Key players" in txt and KEY_NAME in txt, "grid summary missing key player"
print("grid: plot img + key-player summary — PASS")
```

- [ ] **Step 3: Run**

With the app running on :8000: `micromamba run -n shiny python tests/test_stakeholders_e2e.py` → exit 0. Stop the background server. Optionally run the full battery `micromamba run -n shiny python tests/run_e2e.py` (24→still 24 scripts; the stakeholders script now also asserts the grid).

- [ ] **Step 4: Commit**
```bash
git add tests/test_stakeholders_e2e.py
git commit -m "test(stakeholders): e2e — Power-Interest grid renders + summary"
```

---

## Final verification
- [ ] `micromamba run -n shiny python -m pytest tests/ -q --ignore-glob="*_e2e.py" --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` — green.
- [ ] `micromamba run -n shiny python tests/run_e2e.py` — all scripts pass (incl. the extended stakeholders e2e).
- [ ] Then invoke **superpowers:finishing-a-development-branch**.

## Self-review (against spec rev.2)
**Spec coverage:** §3 helpers → Task 1; §5 i18n → Task 2 (and the "reuse power.* for ticks, no grid.high/medium/low" decision is honored); §4.1 navset restructure (id, Register-first, plain helpers) → Task 3 Step 1; §4.2 plot (empty-state, deterministic jitter, no click tracking, quadrant rects/labels/ticks) → Task 3 Step 3; §4.3 summary → Task 3 Step 4; §6.1 unit → Task 1; §6.2 e2e (existing CRUD unchanged + grid img + summary) → Task 4. Covered.
**Placeholders:** Task 3 Step 1 deliberately says "copy the existing form inputs verbatim" rather than retyping them (correctness over transcription) — the implementer reads the current file. Task 4 carries `<the name>`/selector placeholders that are resolved against the live DOM (the one genuinely runtime-discovered item, flagged like SH1's row selector).
**Type/name consistency:** helper names (`level_num`/`classify_quadrant`/`summarize_quadrants`) identical across Tasks 1/3; output ids `power_interest_grid`/`grid_summary` match render-fn names and the `ui.output_*` companions; i18n keys in Task 2 match the `tr(...)` calls in Task 3; `stakeholder_tabs` id consistent Task 3/4.
