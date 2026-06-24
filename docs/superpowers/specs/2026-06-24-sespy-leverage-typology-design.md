# Leverage-point typology tagging (Meadows realm) design

**Date:** 2026-06-24
**Status:** approved (brainstorm)
**Motivated by:** Garcia et al., *How land-use scenarios shape sustainability?
Indicator-based analysis to identify leverage points*, Ecological Indicators
(2026), 10.1016/j.ecolind.2026.115042 — see `LITERATURE/2026-06-22.md` (Medium,
"quick"). Concept: Meadows / Abson et al. (2017) "leverage points" realms.

## Problem

The Leverage Points module ranks nodes by `network.leverage_scores` but gives no
sense of *what kind* of intervention each node represents. Meadows' core insight —
deep leverage points (intent, design) are more powerful but less obvious than
shallow ones (parameters) — is invisible. Tag each leverage row with a
Meadows-style depth realm so the user can see whether their top-ranked nodes are
shallow parameter-tweaks or deep intent-shifts.

## Decisions (from brainstorm)

- **Deterministic DAPSIWRM-type → Meadows-realm lookup.** Pure, zero-config, tags
  every node automatically. Rejected: structural/centrality basis (conceptually
  wrong — depth is the *kind* of intervention, not centrality, which is already
  what leverage measures, so it would be circular); manual per-node tag (needs a
  schema field + data-entry UI — not "quick").
- **Caveat (documented, accepted):** DAPSIWRM (causal-chain position) and Meadows
  realms (intervention depth) are orthogonal framings, so the map is a useful
  heuristic label, not a claim of truth. It is a single editable dict.
- **Fixed mapping** (7 DAPSIWRM types → 4 realms, shallow→deep):

  | DAPSIWRM type | realm token |
  |---|---|
  | `Pressures` | `parameters` |
  | `Ecosystem Services` | `parameters` |
  | `Goods & Benefits` | `parameters` |
  | `Marine Processes & Functioning` | `feedbacks` |
  | `Activities` | `design` |
  | `Responses` | `design` |
  | `Drivers` | `intent` |

## Architecture / components

### `sespy/network.py` — one pure classifier
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
    'parameters' | 'feedbacks' | 'design' | 'intent', or '' for an unknown
    type. Pure; translation-free (the module maps the token through t())."""
    return _DAPSIWRM_REALM.get(element_type, "")
```

### `sespy/modules/analysis_leverage.py` — surface it
- `ranked()` adds a `realm` field to each row: compute
  `token = net_analysis.leverage_realm(el.type if el else "")` and store the
  display value `t(f"leverage.realm.{token}") if token else "—"`.
- `leverage_table`: insert `"realm"` into `base_cols` after `"type"`:
  `["rank", "id", "label", "type", "realm", "leverage"]`. Both render paths work
  unchanged — the no-uncertainty path builds `pd.DataFrame(rows, columns=base_cols)`
  and the uncertainty path spreads `{**r, …}`, so `realm` flows through both.
- Raw `"realm"` column header (matches the table's other raw headers, e.g.
  `type`, `leverage`).

### i18n — `sespy/translations/core.json`
4 new keys × 9 languages: `leverage.realm.parameters` ("Parameters"),
`leverage.realm.feedbacks` ("Feedbacks"), `leverage.realm.design` ("Design"),
`leverage.realm.intent` ("Intent").

## Data flow

`ranked()` already depends on `event_bus.isa_change` (via `scores()`); the realm is
derived from the (already-loaded) element type at render time. No new reactivity,
persistence, or analysis — pure display enrichment.

## Error handling / edge cases

- Unknown / empty element type → `leverage_realm` returns `""` → cell shows `"—"`.
- A node id with no matching element (dangling) → `el` is `None` → type `""` →
  `"—"` (mirrors the existing `label`/`type` fallback in `ranked()`).
- Empty graph → `ranked()` returns `[]` → table renders the empty `base_cols`
  (now including `realm`), unchanged behavior.
- Composes with the D2D uncertainty columns: when the toggle is on, `realm` sits
  between `type` and `leverage`, and the CI/unstable columns still append after.

## Testing

`tests/test_network.py`:
- `leverage_realm` returns the expected token for each of the 7 DAPSIWRM types
  (`Drivers`→`intent`, `Activities`→`design`, `Responses`→`design`,
  `Marine Processes & Functioning`→`feedbacks`, `Pressures`/`Ecosystem Services`/
  `Goods & Benefits`→`parameters`); unknown/empty type → `""`.

`tests/test_leverage_e2e.py` (extend):
- Assert the leverage table has a `realm` column header, and that its cells are
  drawn from the expected label set (the 4 translated realms or `—`). The
  type→realm correctness is the unit test's job; the e2e proves the wiring +
  i18n render. (i18n key coverage is auto-enforced by `test_i18n.py`.)

## Out of scope (YAGNI)

- No schema change, no data-entry change, no manual override tag.
- No sorting/grouping by realm, no depth-ordinal column, no realm filter.
- No configuration UI for the mapping (it is an editable dict in code).
- No realm styling on the leverage network graph (table only).
