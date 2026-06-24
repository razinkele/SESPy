# Leverage-point Typology Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tag each leverage-table row with a Meadows depth realm (parameters/feedbacks/design/intent) derived from the node's DAPSIWRM element type.

**Architecture:** One pure `network.leverage_realm(type) -> token` lookup; the Leverage module's `ranked()` adds a translated `realm` field and `leverage_table` shows it as a column between `type` and `leverage`. No schema/data-entry/graph change.

**Tech Stack:** Python 3.11, Shiny for Python, pandas, pytest, Playwright.

## Global Constraints

- `leverage_realm(element_type)` is PURE; returns a token `"parameters"|"feedbacks"|"design"|"intent"` or `""` for an unknown type. Backed by a module-level `_DAPSIWRM_REALM` dict.
- Mapping (verbatim): `Pressures`/`Ecosystem Services`/`Goods & Benefits` → `parameters`; `Marine Processes & Functioning` → `feedbacks`; `Activities`/`Responses` → `design`; `Drivers` → `intent`.
- The module maps the token via `t(f"leverage.realm.{token}")`; an empty token renders `"—"`.
- `realm` column goes between `type` and `leverage`: `base_cols = ["rank", "id", "label", "type", "realm", "leverage"]`.
- **Accepted gap:** `"Measures"` is not in `DAPSIWRM_ELEMENTS` and not in `_DAPSIWRM_REALM` → renders `"—"`. Do NOT add it.
- 4 new i18n keys × 9 languages (`en,es,fr,de,lt,pt,it,no,el`).
- `test_i18n.py::test_loader_handles_all_supported_languages` checks per-key language completeness only, NOT key presence — so a dedicated presence test is added.
- No schema change, no data-entry change, no sorting/graph styling.
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `network.leverage_realm`

**Files:**
- Modify: `sespy/network.py` (add `_DAPSIWRM_REALM` + `leverage_realm` near `leverage_scores`)
- Test: `tests/test_network.py`

**Interfaces:**
- Produces: `leverage_realm(element_type: str) -> str` (token or `""`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py` (the module is imported as `from sespy import network` at the top of that file; reuse it):

```python
def test_leverage_realm_all_dapsiwrm_types():
    expected = {
        "Drivers": "intent",
        "Activities": "design",
        "Responses": "design",
        "Marine Processes & Functioning": "feedbacks",
        "Pressures": "parameters",
        "Ecosystem Services": "parameters",
        "Goods & Benefits": "parameters",
    }
    for etype, token in expected.items():
        assert network.leverage_realm(etype) == token


def test_leverage_realm_unknown_returns_empty():
    assert network.leverage_realm("Measures") == ""
    assert network.leverage_realm("") == ""
    assert network.leverage_realm("Bogus") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "leverage_realm" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'leverage_realm'`.

- [ ] **Step 3: Implement**

Add to `sespy/network.py` near `leverage_scores`:

```python
_DAPSIWRM_REALM: dict[str, str] = {
    "Pressures": "parameters",
    "Ecosystem Services": "parameters",
    "Goods & Benefits": "parameters",
    "Marine Processes & Functioning": "feedbacks",
    "Activities": "design",
    "Responses": "design",
    "Drivers": "intent",
}


def leverage_realm(element_type: str) -> str:
    """Meadows-realm token for a DAPSIWRM element type — one of
    'parameters' | 'feedbacks' | 'design' | 'intent', or '' for an unknown type
    (incl. 'Measures', an accepted gap). Pure; translation-free."""
    return _DAPSIWRM_REALM.get(element_type, "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "leverage_realm" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): leverage_realm — DAPSIWRM type to Meadows realm"
```

---

### Task 2: i18n keys + presence test

**Files:**
- Modify: `sespy/translations/core.json`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces keys consumed by Task 3: `leverage.realm.parameters/feedbacks/design/intent`.

- [ ] **Step 1: Write the failing presence test**

Add to `tests/test_i18n.py` (it has a module-scoped `translations` fixture):

```python
def test_leverage_realm_keys_present(translations):
    for token in ("parameters", "feedbacks", "design", "intent"):
        assert f"leverage.realm.{token}" in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -k "leverage_realm_keys_present" -v`
Expected: FAIL — the keys are not in `core.json` yet.

- [ ] **Step 3: Add the 4 keys**

Insert into the `"translation"` object in `sespy/translations/core.json` (valid JSON, UTF-8, non-ASCII as-is):

```json
"leverage.realm.parameters": {"en": "Parameters", "es": "Parámetros", "fr": "Paramètres", "de": "Parameter", "lt": "Parametrai", "pt": "Parâmetros", "it": "Parametri", "no": "Parametre", "el": "Παράμετροι"},
"leverage.realm.feedbacks": {"en": "Feedbacks", "es": "Retroalimentaciones", "fr": "Rétroactions", "de": "Rückkopplungen", "lt": "Grįžtamieji ryšiai", "pt": "Retroalimentações", "it": "Retroazioni", "no": "Tilbakekoblinger", "el": "Ανατροφοδοτήσεις"},
"leverage.realm.design": {"en": "Design", "es": "Diseño", "fr": "Conception", "de": "Gestaltung", "lt": "Sandara", "pt": "Conceção", "it": "Progettazione", "no": "Utforming", "el": "Σχεδιασμός"},
"leverage.realm.intent": {"en": "Intent", "es": "Intención", "fr": "Intention", "de": "Absicht", "lt": "Ketinimas", "pt": "Intenção", "it": "Intento", "no": "Hensikt", "el": "Πρόθεση"}
```

- [ ] **Step 4: Run the i18n suite**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS — including `test_leverage_realm_keys_present` and `test_loader_handles_all_supported_languages`.

- [ ] **Step 5: Commit**

```bash
git add sespy/translations/core.json tests/test_i18n.py
git commit -m "i18n(leverage): Meadows realm labels (4 keys, 9 languages)"
```

---

### Task 3: Realm column in the Leverage table + e2e

**Files:**
- Modify: `sespy/modules/analysis_leverage.py` (`ranked()` ~line 138; `leverage_table` `base_cols` ~line 173)
- Test: `tests/test_leverage_e2e.py`

**Interfaces:**
- Consumes: `net_analysis.leverage_realm` (Task 1), the 4 i18n keys (Task 2). `t` and `net_analysis` are already imported in this module.

- [ ] **Step 1: Add `realm` to `ranked()`**

In `analysis_leverage.py`, in the `ranked()` calc, replace the row-append block so each row carries a translated `realm`:

```python
        out: list[dict] = []
        for rank, (nid, value) in enumerate(rows, start=1):
            el = by_id.get(nid)
            token = net_analysis.leverage_realm(el.type if el else "")
            out.append({
                "rank": rank,
                "id": nid,
                "label": el.label if el else nid,
                "type":  el.type if el else "",
                "realm": t(f"leverage.realm.{token}") if token else "—",
                "leverage": round(value, 3),
            })
        return out[: int(input.top_n() or 8)]
```

- [ ] **Step 2: Add `realm` to `base_cols`**

In `leverage_table`, change the `base_cols` definition to include `realm` between `type` and `leverage`:

```python
        base_cols = ["rank", "id", "label", "type", "realm", "leverage"]
```

(No other change to `leverage_table` — the no-uncertainty path `pd.DataFrame(rows, columns=base_cols)` and the uncertainty path `{**r, …}` both carry `realm` automatically.)

- [ ] **Step 3: Smoke-test import + app build**

Run: `micromamba run -n shiny python -c "import app; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Extend the e2e**

In `tests/test_leverage_e2e.py`, insert this block after `print("\nleverage e2e assertions pass")` and BEFORE the `# --- Uncertainty toggle …` block (the realm column shows by default, no toggle needed):

```python
        # --- realm column (leverage typology) renders with valid labels ---
        await page.wait_for_selector("#leverage-leverage_table table tbody tr", timeout=30000)
        realm_cells = await page.evaluate(
            "() => { const ths = Array.from(document.querySelectorAll("
            "'#leverage-leverage_table table thead th')).map(th => th.textContent.trim());"
            " const i = ths.indexOf('realm');"
            " if (i < 0) return null;"
            " return Array.from(document.querySelectorAll("
            "'#leverage-leverage_table table tbody tr')).map("
            "tr => (tr.querySelectorAll('td')[i]?.textContent || '').trim()); }"
        )
        assert realm_cells is not None, "no 'realm' column header in leverage table"
        # No "—" expected: every sample_ses.json node has a known DAPSIWRM type,
        # so a "—" here means the realm wiring is broken (leverage_realm never
        # called / token always ""). Keeping "—" out of `allowed` makes that fail.
        allowed = {"Parameters", "Feedbacks", "Design", "Intent"}
        assert realm_cells and all(c in allowed for c in realm_cells), \
            f"unexpected realm cell values: {realm_cells}"
        assert "—" not in realm_cells, \
            f"dash in realm cells — wiring broken or unknown type in sample data: {realm_cells}"
        print(f"leverage realm column: OK ({realm_cells})")
```

- [ ] **Step 5: Run the e2e**

Start a server and run the script directly (as prior tasks did):
```
# background: micromamba run -n shiny shiny run --port 8000 app.py
# then:       micromamba run -n shiny python tests/test_leverage_e2e.py
```
Expected: prints `leverage realm column: OK (...)` (and the existing assertions still pass). If it can't run for an infra reason (not a code defect), report DONE_WITH_CONCERNS with detail and still commit.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/analysis_leverage.py tests/test_leverage_e2e.py
git commit -m "feat(leverage): Meadows realm column in the leverage table"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: prior baseline + the new `leverage_realm` and `leverage_realm_keys_present` tests, all passing.
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`; `test_leverage_e2e.py` passes (realm column + existing CI-toggle check).
- [ ] `realm` column appears between `type` and `leverage`; values are the 4 translated realms or `—`; "Measures" left unmapped (accepted gap).
