# FCM Edge Weights on Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Excel importer interpret a numeric (FCM continuous) weight cell as a signed weight — sign → polarity, magnitude → strength bins — instead of silently degrading it to `medium`.

**Architecture:** A pure `excel_import.fcm_weight_to_fields(w)` mapping + a `_try_float` detector; `parse_excel`'s connection loop routes a numeric weight cell through the FCM mapping (overriding any polarity column) and keeps the categorical path for text/empty cells. No schema/UI/i18n change.

**Tech Stack:** Python 3.11, pandas/openpyxl, pytest.

## Global Constraints

- `fcm_weight_to_fields(weight: float) -> tuple[str, str]`: `polarity = "+" if weight >= 0 else "-"`; `mag = min(abs(weight), 1.0)`; `strength = "weak" if mag <= 1/3 else "medium" if mag <= 2/3 else "strong"`. (`w == 0 → ("+","weak")`; `|w| > 1 → clamped → "strong"`.)
- `_try_float(value) -> float | None`: returns a finite float or `None` (text/empty/NaN/inf via `math.isfinite`). Requires `import math` in `excel_import.py`.
- Per-row detection in `parse_excel`: if the strength/weight cell parses as a finite float → FCM mapping (sign → polarity, magnitude → strength, **overriding** any polarity column); else categorical (unchanged). Missing column → `"medium"` (no regression).
- `strength` values must be exactly `weak`/`medium`/`strong` (match `network._STRENGTH_RANK`).
- Single-author import: `Connection.ratings` stays `[]` (default) — no C1 consensus interaction.
- No new field, no schema bump, no UI/i18n.
- Tests in `tests/test_excel_import.py` (already exists; has `_write_workbook(tmp_path, *, elements, connections, ...)` + `VALID_ELEMENTS`). The integration test's Connections `source`/`target` ids MUST all be in the Elements sheet (reuse `VALID_ELEMENTS`) or validation fails on a dangling ref before the FCM mapping runs.
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `fcm_weight_to_fields` + `_try_float` (pure)

**Files:**
- Modify: `sespy/excel_import.py` (add `import math`; add the two helpers after `_resolve_sheet`, ~line 61)
- Test: `tests/test_excel_import.py`

**Interfaces:**
- Produces: `fcm_weight_to_fields(weight: float) -> tuple[str, str]`; `_try_float(value) -> float | None`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_excel_import.py`, change the import on line 9 from
`from sespy.excel_import import parse_excel` to:
```python
from sespy.excel_import import parse_excel, _try_float, fcm_weight_to_fields
```
Then add:

```python
def test_fcm_weight_to_fields_magnitude_bins():
    assert fcm_weight_to_fields(0.2) == ("+", "weak")
    assert fcm_weight_to_fields(0.5) == ("+", "medium")
    assert fcm_weight_to_fields(0.7) == ("+", "strong")
    assert fcm_weight_to_fields(0.0) == ("+", "weak")


def test_fcm_weight_to_fields_sign():
    assert fcm_weight_to_fields(-0.2) == ("-", "weak")
    assert fcm_weight_to_fields(-0.5) == ("-", "medium")
    assert fcm_weight_to_fields(-0.7) == ("-", "strong")


def test_fcm_weight_to_fields_clamps_out_of_range():
    assert fcm_weight_to_fields(1.5) == ("+", "strong")
    assert fcm_weight_to_fields(-1.5) == ("-", "strong")


def test_fcm_weight_to_fields_boundaries():
    assert fcm_weight_to_fields(1/3) == ("+", "weak")     # inclusive upper
    assert fcm_weight_to_fields(0.34) == ("+", "medium")
    assert fcm_weight_to_fields(2/3) == ("+", "medium")   # inclusive upper
    assert fcm_weight_to_fields(0.7) == ("+", "strong")


def test_try_float_detects_numbers_only():
    assert _try_float(0.5) == 0.5
    assert _try_float(-0.7) == -0.7
    assert _try_float("0.5") == 0.5
    assert _try_float("") is None
    assert _try_float("strong") is None
    assert _try_float(None) is None
    assert _try_float(float("nan")) is None
    assert _try_float(float("inf")) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_excel_import.py -k "fcm_weight_to_fields or try_float" -v`
Expected: FAIL — `cannot import name 'fcm_weight_to_fields'`.

- [ ] **Step 3: Implement**

In `sespy/excel_import.py`, add `import math` to the stdlib import block (after `from __future__ import annotations`). Add the two helpers after `_resolve_sheet`:

```python
def fcm_weight_to_fields(weight: float) -> tuple[str, str]:
    """Map a signed FCM weight to (polarity, strength). Sign → polarity;
    |weight| (clamped to [0, 1]) → weak/medium/strong by the 1/3, 2/3
    thresholds. weight 0 → ('+', 'weak'); |weight| > 1 → clamped to 'strong'.
    Pure."""
    polarity = "+" if weight >= 0 else "-"
    mag = min(abs(weight), 1.0)
    strength = "weak" if mag <= 1 / 3 else ("medium" if mag <= 2 / 3 else "strong")
    return polarity, strength


def _try_float(value) -> float | None:
    """Return `value` as a finite float, or None if it is not numeric
    (empty/text/None/NaN/inf). Used to detect an FCM weight cell."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_excel_import.py -k "fcm_weight_to_fields or try_float" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/excel_import.py tests/test_excel_import.py
git commit -m "feat(import): fcm_weight_to_fields + _try_float (FCM weight mapping)"
```

---

### Task 2: per-row FCM detection in `parse_excel` + integration test

**Files:**
- Modify: `sespy/excel_import.py` (the connection-building loop, ~lines 110-124)
- Test: `tests/test_excel_import.py`

**Interfaces:**
- Consumes: `fcm_weight_to_fields`, `_try_float` (Task 1); `_pick`, `CONN_STRENGTH_COLS`, `CONN_POLARITY_COLS` (existing).

- [ ] **Step 1: Write the failing integration tests**

Add to `tests/test_excel_import.py`:

```python
def test_parse_excel_fcm_numeric_weights(tmp_path):
    # All source/target ids must exist in Elements or validation fails on a
    # dangling ref BEFORE the FCM mapping is reached.
    f = _write_workbook(
        tmp_path,
        elements=VALID_ELEMENTS,  # D001, A001, P001
        connections=[
            {"source": "D001", "target": "A001", "weight": -0.7},   # FCM: -/strong
            {"source": "A001", "target": "P001", "weight": 0.2},    # FCM: +/weak
            {"source": "D001", "target": "P001",
             "polarity": "+", "strength": "medium"},                # categorical: unchanged
            {"source": "P001", "target": "A001",
             "weight": 0.5, "polarity": "-"},                       # numeric weight wins → +
        ],
    )
    result = parse_excel(f)
    assert result.valid, result.errors
    conns = {(c.source, c.target): c for c in result.project.isa_data.connections}

    fcm_neg = conns[("D001", "A001")]
    assert fcm_neg.polarity == "-" and fcm_neg.strength == "strong"

    fcm_pos = conns[("A001", "P001")]
    assert fcm_pos.polarity == "+" and fcm_pos.strength == "weak"

    cat = conns[("D001", "P001")]
    assert cat.polarity == "+" and cat.strength == "medium"

    wins = conns[("P001", "A001")]
    assert wins.polarity == "+" and wins.strength == "medium"  # weight sign (+0.5) overrides polarity "-"

    # downstream sanity: an FCM strong lands as a real strength rank, not a degraded default.
    from sespy import network
    assert network._STRENGTH_RANK[fcm_neg.strength] == 3


def test_parse_excel_categorical_weight_back_compat(tmp_path):
    # A text "weight" cell stays categorical (regression guard for KUMU sheets).
    f = _write_workbook(
        tmp_path,
        elements=VALID_ELEMENTS,
        connections=[{"source": "D001", "target": "A001",
                      "Polarity": "-", "Weight": "weak"}],
    )
    result = parse_excel(f)
    assert result.valid, result.errors
    c = result.project.isa_data.connections[0]
    assert c.polarity == "-" and c.strength == "weak"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_excel_import.py -k "fcm_numeric_weights or categorical_weight_back_compat" -v`
Expected: FAIL — the FCM row resolves to `strength="-0.7"`/`polarity="+"` (current degraded behavior), so the assertions fail.

- [ ] **Step 3: Implement the per-row detection**

In `sespy/excel_import.py`, replace the `Connection(...)` append in the connection loop (the block that currently sets `polarity=str(_pick(... CONN_POLARITY_COLS ...))` and `strength=str(_pick(... CONN_STRENGTH_COLS ...))`) with:

```python
        raw_strength = _pick(row, CONN_STRENGTH_COLS, default="")
        fcm = _try_float(raw_strength)
        if fcm is not None:                       # numeric → FCM weight
            polarity, strength = fcm_weight_to_fields(fcm)
        else:                                     # text/empty → categorical (unchanged)
            polarity = str(_pick(row, CONN_POLARITY_COLS, default="+")) or "+"
            strength = str(raw_strength) or "medium"
        connections.append(Connection(
            source=str(src),
            target=str(tgt),
            polarity=polarity,
            strength=strength,
            confidence=int(_pick(row, CONN_CONF_COLS, default=3) or 3),
            delay=normalize_delay(_pick(row, CONN_DELAY_COLS, default="immediate")),
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_excel_import.py -v`
Expected: PASS — the new FCM + back-compat tests AND all pre-existing import tests (esp. `test_parse_excel_alternative_column_names`, which uses a categorical `"Weight": "weak"`).

- [ ] **Step 5: Commit**

```bash
git add sespy/excel_import.py tests/test_excel_import.py
git commit -m "feat(import): interpret numeric weight cell as a signed FCM weight"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: prior baseline + the new `fcm_weight_to_fields`/`_try_float`/`parse_excel` FCM tests, all passing; `test_excel_import.py` fully green (incl. the pre-existing categorical tests).
- [ ] `import app` builds cleanly: `micromamba run -n shiny python -c "import app; print('ok')"`.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py` (the import path is exercised by `test_import_e2e.py`, which must still pass — the change is back-compatible for the categorical sheets it uses).
- [ ] Back-compat: categorical KUMU sheets and no-weight sheets import identically to before; only numeric weight cells change behavior.
