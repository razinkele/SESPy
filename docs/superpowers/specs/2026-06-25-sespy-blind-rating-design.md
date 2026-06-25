# Anchoring-independent ("blind") rating mode — design

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #6. Follow-up to QSEM-C2 (`e3f75cc`); see memory
`sespy-qsem-multirater`.

## Problem / goal

The Rate Connections module shows every peer's exact rating in the `current_ratings`
list (`rate_connections.py:175-187` — `name: polarity/strength/confidence/delay`) while
a stakeholder fills in the editor directly above it. Seeing peers' values risks
**anchoring bias** (raters pulled toward the visible consensus). Add an optional "blind"
mode that hides the per-rater list until the current rater has submitted their own
rating for the selected connection (Delphi-style: independence first, transparency after).

## Decisions (from brainstorm)

- **A per-session sidebar checkbox, default off** (`blind_mode`), placed next to the
  existing `contested_only` toggle — opt-in, stateless, mirrors the existing toggle.
  (Not a persisted per-project setting — over-machinery for a workshop-time preference.)
- **Gate keyed on "this rater has rated this connection"** — per-connection, reusing the
  predicate the `mine` column uses (`any(r.rater_id == rater for r in conn.ratings)`).
  Moving to a not-yet-rated connection re-hides; saving reveals.
- **Hide only the per-rater `current_ratings` list.** The `#ratings` count, `mine` flag,
  and the `disagreement`/contested column stay visible — those are *aggregate* signals
  ("N raters; they disagree on sign") that don't reveal *what direction* anyone chose, so
  they don't anchor, and the contested view is a shipped feature worth keeping live.

## Architecture

A display gate on one output in `sespy/modules/rate_connections.py`; no schema/consensus
change, nothing the analyses touch.

1. **Sidebar toggle.** In `rate_connections_ui`, after the `contested_only` checkbox
   (~line 31), add:
   ```python
   ui.input_checkbox("blind_mode", t("rate.blind_mode"), value=False),
   ```

2. **`current_ratings` gate.** The render currently returns the peer `<ul>` whenever the
   connection has ratings. Add the blind branch (read `input.blind_mode()` **directly** —
   it is a static, always-present checkbox; a `try/except` guard would silently drop the
   reactive dependency, matching the `contested_only` convention):
   ```python
   @output
   @render.ui
   def current_ratings():
       event_bus.isa_change.get()
       _, conn = _selected()
       if conn is None or not conn.ratings:
           return ui.tags.p("—", class_="text-muted")
       try:
           rater = input.rater()
       except Exception:
           rater = None
       rater_has_rated = bool(rater) and any(r.rater_id == rater for r in conn.ratings)
       if input.blind_mode() and not rater_has_rated:
           return ui.tags.p(t("rate.blind_hidden"), class_="text-muted")
       name_by_id = {s.id: s.name for s in project_data.get().stakeholders}
       return ui.tags.ul(*[ ... unchanged ... ])
   ```
   Reveal-after-submit is automatic: after `_save`, `conn.ratings` includes the rater, so
   the predicate flips and the list renders. The `sel_idx` selection-cache (the
   render-clears-selection workaround) keeps the same connection selected across the save
   re-render, so the reveal lands on the row just rated.

3. **i18n** — two new keys × 9 languages in the existing `rate.*` namespace:
   - `rate.blind_mode` — toggle label, en = `"Blind mode (hide others' ratings)"`.
   - `rate.blind_hidden` — placeholder, en = `"Hidden until you submit your own rating (blind mode)."`

## Error handling / edge cases

- **No rater selected** under blind mode → `rater_has_rated` is False → list hidden. (You
  pick a rater before entering one; nothing to anchor on while unselected. Acceptable.)
- **Blind on, connection with no ratings yet** → the `not conn.ratings` early-return shows
  `"—"` (blind branch not reached); correct — nothing to hide.
- **Blind off** → unchanged behavior (full peer list as today).
- **A rater who already rated** the selected connection → list shows (incl. their own +
  peers) even under blind — they've committed, so anchoring no longer applies.

## Testing

- Extend `tests/test_rate_connections_e2e.py`: after a rater is set and a connection
  selected, check `#rate-blind_mode`, assert `#rate-current_ratings` shows the
  blind-hidden text (peer values NOT visible) for a not-yet-rated connection; click
  `#rate-save_rating`; assert `#rate-current_ratings` now reveals the rater's
  `+/strength/...` line. (Reuses the existing stakeholder-add + nav + RATE_ROW flow.)
- i18n presence test for `rate.blind_mode` and `rate.blind_hidden` (all 9 languages).
- No `network.py` / consensus test changes (gate is display-only).

## Out of scope (YAGNI)

- Persisting blind mode per project / per rater.
- Hiding the aggregate `#ratings` / `mine` / disagreement signals (they don't anchor).
- A global "facilitator lock" that forces blind mode for all raters.
- Hiding the consensus scalars shown elsewhere (this is about the per-rater list only).
