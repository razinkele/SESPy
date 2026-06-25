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

3. **i18n** — two new keys in the existing `rate.*` namespace, **each with all 9
   languages** (every existing `rate.*` key carries all 9; `test_i18n.py`'s
   `test_loader_handles_all_supported_languages` iterates EVERY key and hard-fails on the
   first missing language, so English-only is not an option). Supply verbatim:

   `rate.blind_mode`:
   | lang | value |
   |---|---|
   | en | Blind mode (hide others' ratings) |
   | es | Modo ciego (ocultar valoraciones ajenas) |
   | fr | Mode aveugle (masquer les évaluations des autres) |
   | de | Blindmodus (Bewertungen anderer ausblenden) |
   | lt | Aklasis režimas (slėpti kitų vertinimus) |
   | pt | Modo cego (ocultar avaliações de outros) |
   | it | Modalità cieca (nascondi le valutazioni altrui) |
   | no | Blindmodus (skjul andres vurderinger) |
   | el | Τυφλή λειτουργία (απόκρυψη αξιολογήσεων άλλων) |

   `rate.blind_hidden`:
   | lang | value |
   |---|---|
   | en | Hidden until you submit your own rating (blind mode). |
   | es | Oculto hasta que envíes tu propia valoración (modo ciego). |
   | fr | Masqué jusqu'à ce que vous soumettiez votre évaluation (mode aveugle). |
   | de | Ausgeblendet, bis Sie Ihre eigene Bewertung abgeben (Blindmodus). |
   | lt | Paslėpta, kol pateiksite savo vertinimą (aklasis režimas). |
   | pt | Oculto até enviares a tua avaliação (modo cego). |
   | it | Nascosto finché non invii la tua valutazione (modalità cieca). |
   | no | Skjult til du sender inn din egen vurdering (blindmodus). |
   | el | Κρυμμένο μέχρι να υποβάλετε τη δική σας αξιολόγηση (τυφλή λειτουργία). |

## Error handling / edge cases

- **No rater selected** under blind mode → `rater_has_rated` is False → list hidden. (You
  pick a rater before entering one; nothing to anchor on while unselected. Acceptable.)
- **Blind on, connection with no ratings yet** → the `not conn.ratings` early-return shows
  `"—"` (blind branch not reached); correct — nothing to hide.
- **Blind off** → unchanged behavior (full peer list as today).
- **A rater who already rated** the selected connection → list shows (incl. their own +
  peers) even under blind — they've committed, so anchoring no longer applies.

## Testing

The hidden state is **only reachable with a peer rating present AND a *different* current
rater who hasn't rated** — from a blank project `conn.ratings` is empty, so the
`if conn is None or not conn.ratings: return "—"` early-return fires and the blind branch
is never hit. The e2e must therefore use a **two-rater** setup (parallel to the existing
contested-edge block in `test_rate_connections_e2e.py`, which already adds two
stakeholders and switches rater):

- Append a block after the existing two-rater flow: with rater 1's rating already saved
  on the connection, switch the rater to stakeholder 2 (who has NOT rated it), re-click
  the same `RATE_ROW`, then **check `#rate-blind_mode`**. Now `conn.ratings` is non-empty
  but `rater_has_rated` is False → the blind branch renders.
- Assert `#rate-current_ratings` **text equals the `rate.blind_hidden` string** (the app
  runs in English in the e2e) — a class-only check is vacuous, since both `"—"` and the
  blind placeholder are `<p class="text-muted">`. Also assert rater 1's value line is NOT
  present.
- Click `#rate-save_rating`; assert `#rate-current_ratings` now reveals the peer-list
  `<ul>` (both rater 1's and rater 2's lines visible — the reveal lands on a connection
  that now has two ratings).
- i18n presence test for `rate.blind_mode` and `rate.blind_hidden`; the existing
  `test_loader_handles_all_supported_languages` then enforces all 9 languages.
- No `network.py` / consensus test changes (gate is display-only).

## Out of scope (YAGNI)

- Persisting blind mode per project / per rater.
- Hiding the aggregate `#ratings` / `mine` / disagreement signals (they don't anchor).
- A global "facilitator lock" that forces blind mode for all raters.
- Hiding the consensus scalars shown elsewhere (this is about the per-rater list only).
