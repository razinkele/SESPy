# FCM (fuzzy cognitive map) edge weights on import — design

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #2.
**Motivated by:** Ratnayake et al., *Mapping the Social–Ecological Nexus, Village
Tank Cascade Systems* (2026), 10.3390/su18126151 — see `LITERATURE/2026-06-22.md`.

## Problem

`excel_import.py` already maps a `weight`/`Weight` column into `Connection.strength`
(`CONN_STRENGTH_COLS = ("strength","Strength","weight","Weight")`), but it only
`str()`-casts the value. So an FCM continuous weight **silently degrades**: `0.7`
becomes `strength="0.7"` → `_STRENGTH_RANK.get("0.7", 2)` = medium, and a negative
weight `-0.7` imports as `polarity="+"` (the polarity column's default) with
`strength="-0.7"` = medium. FCM-built models therefore lose both their sign and
their magnitude on import. Fix: interpret a numeric weight cell as a signed FCM
weight (sign → polarity, magnitude → strength).

## Decisions (from brainstorm)

- **Q1 — map a signed FCM weight `w` onto the existing `Connection` fields** (no new
  field, no schema change): `polarity = "+" if w >= 0 else "-"`; `strength` from
  `|w|` magnitude bins (FCM standard `[-1, 1]`, clamp out-of-range):
  `(0, 1/3] → weak`, `(1/3, 2/3] → medium`, `(2/3, 1] → strong`; `confidence`
  default 3 (FCM carries none). Edge cases: `w == 0 → ("+", "weak")` (keep the
  listed edge; degenerate); `|w| > 1 → clamp to strong`. A pure helper does the
  mapping.
- **Q2 — extend `excel_import.py`, no separate importer or sheet format:** per
  connection row, if the strength/weight cell **parses as a finite float**, route it
  through the FCM mapping (sign → polarity, `|w|` → strength, *overriding* any
  polarity column); otherwise keep the current categorical path. Auto-detected per
  row, so an FCM `.xlsx` "just works" and KUMU sheets are unchanged.
- **Q3 — no interaction with the C1 ratings model:** import is single-author, so it
  sets the consensus scalars directly and leaves `ratings=[]` — the "empty ratings ⇒
  scalars stand" invariant. No consensus recompute, no rating synthesis. (Import-as-
  rater is out of scope.)

## Architecture / components

### `sespy/excel_import.py` — pure mapping + per-row detection
```python
def fcm_weight_to_fields(weight: float) -> tuple[str, str]:
    """Map a signed FCM weight to (polarity, strength). Sign → polarity;
    |weight| (clamped to [0,1]) → weak/medium/strong by 1/3, 2/3 thresholds.
    weight 0 → ('+', 'weak'); |weight| > 1 → clamped to 'strong'. Pure."""
    polarity = "+" if weight >= 0 else "-"
    mag = min(abs(weight), 1.0)
    strength = "weak" if mag <= 1/3 else ("medium" if mag <= 2/3 else "strong")
    return polarity, strength


def _try_float(value) -> float | None:
    """Return the value as a finite float, or None if it is not numeric
    (empty/text/NaN/inf). Used to detect an FCM weight cell."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None
```
- In `parse_excel`'s connection loop, replace the `polarity`/`strength` derivation:
  ```python
  raw_strength = _pick(row, CONN_STRENGTH_COLS, default="")
  fcm = _try_float(raw_strength)
  if fcm is not None:                       # numeric → FCM weight
      polarity, strength = fcm_weight_to_fields(fcm)
  else:                                     # text/empty → categorical (unchanged)
      polarity = str(_pick(row, CONN_POLARITY_COLS, default="+")) or "+"
      strength = str(raw_strength) or "medium"
  ```
  `confidence` and `delay` derivation unchanged. `add math` import at the top.
- Back-compat: a sheet with no weight/strength column → `raw_strength == ""` →
  `_try_float` returns `None` → categorical path → `strength="medium"`, polarity from
  the polarity column — identical to today.

### No UI / i18n change
The import is backend; no new user-facing strings. Existing upload UI, validation,
and error surfacing are untouched (FCM rows produce valid `Connection`s that pass the
same `validate_project_payload`).

## Data flow

`parse_excel` → per-row FCM-or-categorical interpretation → `Connection(... ratings
defaulting to [])` → the existing payload/validation path → `Project`. Every
downstream analysis reads the resulting scalar `polarity`/`strength` exactly as for a
KUMU import. `ratings=[]` means the C1 consensus equals the imported scalars.

## Error handling / edge cases

- `w == 0` → `("+", "weak")` (keeps a listed 0-weight edge rather than dropping it).
- `|w| > 1` (non-standard FCM scale) → clamped, so it maps to `strong` (sign kept).
- `NaN`/`inf`/text strength cell → `_try_float` returns `None` → categorical path
  (text like `"strong"` works as today; `NaN` falls back to `"medium"`).
- A numeric weight overrides any `polarity` column for that row (FCM weight is the
  source of truth for sign). A row with categorical strength keeps using its
  polarity column.
- Boundary values: `|w| == 1/3` → weak; `|w| == 2/3` → medium (inclusive upper
  bounds per the `<=` thresholds).
- Missing weight/strength column entirely → categorical default `"medium"` (no
  regression for existing imports).

## Testing

`tests/test_excel_import.py` (create if absent, else extend):
- `fcm_weight_to_fields` golden values: `0.7→("+","strong")`, `0.5→("+","medium")`,
  `0.2→("+","weak")`, `0.0→("+","weak")`, `-0.2→("-","weak")`, `-0.5→("-","medium")`,
  `-0.7→("-","strong")`, `1.5→("+","strong")` (clamp), `-1.5→("-","strong")` (clamp);
  boundaries `1/3→weak`, `0.34→medium`, `2/3→medium`, `0.7→strong`.
- `_try_float`: numbers (incl. negatives, `"0.5"` string) → float; `""`, `"strong"`,
  `None`, `NaN` → `None`.
- `parse_excel` integration on a **temp `.xlsx` built in-test** (pandas `to_excel`):
  a Connections sheet mixing FCM numeric weights and categorical strengths →
  - an FCM row `weight=-0.7` → resulting `Connection.polarity == "-"` and
    `strength == "strong"`;
  - a categorical row `strength="weak", polarity="+"` → unchanged;
  - a row with a numeric weight AND a contradictory `polarity` column → the weight's
    sign wins.
- Back-compat: an existing categorical-only sheet imports identically to before
  (regression guard).

## Out of scope (YAGNI)

- Matrix-format FCM (an adjacency-matrix sheet) — edge-list only.
- Per-column normalization / inferring the scale from the data (assume `[-1,1]`,
  clamp).
- Deriving `confidence` from FCM (none available → default 3).
- Importing FCM as a specific rater (C1 multi-rater) — single-author import only.
- A reverse export of SESPy strengths to FCM weights.
