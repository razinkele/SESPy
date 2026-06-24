# QSEM-C2 — Elicitation UI (Rate Connections) design

**Date:** 2026-06-24
**Status:** approved (brainstorm)
**Sub-project:** C2 of QSEM-C. Builds on C1 (`Connection.ratings`,
`recompute_consensus`, `connection_disagreement` — shipped `0a76046`). C3
(contested-edges view) follows as a separate cycle.
**Roadmap:** `docs/superpowers/2026-06-22-qsem-followups-roadmap.md` (Follow-up 2,
resolves Q4 + Q6).

## Problem

C1 added the data model for multiple stakeholders to rate a connection, but there
is no way to enter ratings. C2 adds a **dedicated "Rate Connections" module** where
a stakeholder picks a connection and records their own rating
(strength/confidence/polarity/delay). Each save upserts one rating per
`(rater, connection)` and recomputes the connection's consensus so every existing
analysis immediately reflects it.

## Decisions (from brainstorm)

- **Q6 — a dedicated module/page** (`nav.rate`), not an extension of the
  author-centric *Edit Data* form. Separation of concerns (authoring vs.
  rating), matches the one-module-per-page codebase pattern, and is the future
  home of C3's contested view.
- **Q4 — reuse the PIMS Stakeholders register** as the rater list
  (`rater_id = Stakeholder.id`); no second identity concept. Empty register →
  a guard message ("add stakeholders first").
- **Show others' ratings** during entry (transparency; a local feasibility tool,
  not a blind Delphi). The anchoring-independence trade-off is noted; hiding
  individual ratings until self-entry is a deferred refinement.

## Architecture / components

**Implementation order (prerequisite):** the `sespy/network.py` helpers
(`upsert_rating`, `remove_rating`) and their `tests/test_network.py` tests MUST be
implemented and passing **before** `sespy/modules/rate_connections.py` is written —
the module imports and calls them directly. (Verified: `network.py` currently has
`recompute_consensus`/`connection_disagreement` but neither helper yet.)

### `sespy/network.py` — two pure mutation helpers (testable, thin module)
Beside `recompute_consensus` (the sole consensus writer, which these call):

- `upsert_rating(connection: Connection, rating: Rating) -> Connection` — return a
  copy whose `ratings` has `rating` replacing any existing entry with the same
  `rater_id` (else appended), then `recompute_consensus` applied. Pure.
- `remove_rating(connection: Connection, rater_id: str) -> Connection` — return a
  copy with that rater's rating dropped, then `recompute_consensus` applied. Pure.
  (When the last rating is removed, `recompute_consensus` is a no-op, so the
  consensus scalars freeze at their last value — acceptable; documented.)

### `sespy/modules/rate_connections.py` — new module
`rate_connections_ui() -> ui.Tag` and
`@module.server def rate_connections_server(input, output, session, *, project_data, event_bus, translator=None)`.

**UI** (sidebar + main, mirroring other analysis modules):
- Sidebar: `output_ui("rater_picker")` → an `input_select("rater", …)` built from
  `project_data.get().stakeholders` as `{s.id: s.name}` (note `.get()` — `project_data`
  is a `reactive.Value[Project]`, per `pims_stakeholders.py`); when the register is
  empty, render a muted guard message instead.
- Main:
  - `output_data_frame("connections_table")` (row-select) — one row per connection:
    `source→target` (with element labels), consensus `polarity/strength/confidence/delay`,
    `#ratings` (len of `ratings`), and `mine` (`✓` if the selected rater has a
    rating on it, else `—`).
  - `output_ui("rating_editor")` — when a connection row is selected: polarity
    `input_radio_buttons` (`+`/`−`), strength `input_select`
    (`weak/medium/strong`), confidence `input_slider` (1–5, step 1), delay
    `input_select` (`constants.DELAY_LEVELS`), **pre-filled** from the rater's
    existing rating on that connection if present, else defaults
    (`+`/`medium`/`3`/`immediate`). `input_action_button("save_rating")` +
    `input_action_button("remove_rating")` (outline-danger). Rendered against the
    cached `sel_idx` (see Selection persistence) and re-rendered on rater/`sel_idx`
    change so pre-fill is deterministic and survives the post-save re-render.
  - `output_ui("current_ratings")` — for the selected connection, a list of all
    ratings: rater name (resolved from the register, fallback to `rater_id`) +
    `polarity/strength/confidence/delay`.

**Server data flow:**
- Selection persistence (REQUIRED): saving emits `isa_change`, which re-renders
  `connections_table`, and Shiny's `render.DataGrid` **clears row selection on every
  re-render** — so a naive `cell_selection()` read would collapse the editor and
  current-ratings panels after each save. Cache the selection in a
  `reactive.Value[int | None]` (`sel_idx`): a `@reactive.effect` updates `sel_idx`
  from `connections_table.cell_selection()["rows"][0]` whenever the user clicks a
  row; the save/remove handlers read `sel_idx` (not the live `cell_selection`), and
  the `rating_editor` / `current_ratings` outputs render against `sel_idx` so they
  survive the post-save re-render. Reset `sel_idx` to `None` on rater change.
- Connections are uniquely keyed by `(source, target)` (Edit Data forbids
  duplicates), so the cached index maps to the same connection across the
  save-triggered re-render.
- Bounds guard (REQUIRED, both handlers): `connections_table` renders a stub row on
  an empty project (mirroring `isa_data_entry.py`), so index 0 is selectable with no
  real connection. After the no-selection guard, check
  `if idx >= len(project_data.get().isa_data.connections): return` (exactly as
  `isa_data_entry`'s remove handler does) before building the `Rating`.
- Save (`@reactive.event(input.save_rating)`): read `rater`, the cached `sel_idx`,
  and the four editor inputs; guard missing rater/selection with
  `ui.notification_show`, then apply the bounds guard above. Build
  `Rating(rater_id=rater, strength, confidence,
  polarity, delay)`; `new_conn = network.upsert_rating(conn, rating)`; rebuild the
  connections list with `new_conn` at the index; persist:
  ```python
  current = project_data.get()
  project_data.set(current.replace(isa_data=IsaData(
      elements=current.isa_data.elements, connections=new_conns)))
  event_bus.emit_isa_change()
  event_bus.emit_cld_update()
  ```
  (the exact pattern from `isa_data_entry._replace`). Notify "rating saved".
- Remove (`@reactive.event(input.remove_rating)`): `network.remove_rating(conn,
  rater)` then persist identically. Notify "rating removed".

### `app.py`
- Add `NavItem(id="rate", icon="user-pen", label="Rate Connections",
  label_key="nav.rate")` to `NAV`, placed immediately after the `entry` item.
- **Add `"rate": "create"` to the `NAV_TO_STEP` dict** (alongside the existing
  `"entry": "create"`). Every nav id maps to a workflow-stepper step; without this
  entry the stepper shows no active step on the Rate Connections page
  (`dashboard_server` falls through to no highlight for unmapped ids).
- Import `rate_connections_ui/_server`; add the panel to the UI dispatch and call
  `rate_connections_server(..., project_data=…, event_bus=…, translator=…)`
  alongside the other module servers.

### i18n — `sespy/translations/core.json`
New keys × 9 languages: `nav.rate`, `rate.title`, `rate.rating_as`,
`rate.no_stakeholders`, `rate.num_ratings`, `rate.mine`, `rate.your_rating`,
`rate.polarity`, `rate.strength`, `rate.confidence`, `rate.delay`,
`rate.save`, `rate.remove`, `rate.current_ratings`, `rate.select_connection`,
`rate.saved`, `rate.removed` (17 keys). **Plus three NEW strength-label keys**
`strength.weak`, `strength.medium`, `strength.strong` (20 keys total): verified that
`core.json` has NO top-level `strength.*` family — only `simplify.strength.{weak,
medium,strong}`, which is scoped to the Simplify Network filter and must NOT be
reused here. Delay option labels DO reuse the existing `delay.immediate/short/long`
keys. The connection table's consensus columns reuse existing `entry.*` headers
where available. All keys × 9 languages.

## Error handling / edge cases

- Empty stakeholder register → guard message; save/remove are no-ops with a
  notification.
- No connection selected → save/remove notify "select a connection first".
- Remove with no existing rating by this rater → no-op; notify "nothing to remove"
  (not "rating removed"), so the message reflects reality.
- Re-rating by the same rater replaces (never duplicates) — enforced by
  `upsert_rating` keying on `rater_id`.
- Removing the last rating leaves consensus scalars at their last value (no-op
  recompute) — documented behaviour, not a bug.
- A `rater_id` that no longer matches any stakeholder (deleted stakeholder) still
  renders in `current_ratings` by its raw id (fallback), and its rating still
  counts — consistent with the no-denormalization pattern.

## Testing

`tests/test_network.py` (pure helpers — the testable core):
- `upsert_rating` appends a new rater's rating and recomputes consensus (golden
  values); a second call with the same `rater_id` **replaces** (ratings length
  stays 1, consensus follows the new values, no duplicate).
- `remove_rating` drops the named rater (length decreases, consensus recomputed);
  removing the only rating leaves `ratings == []` and scalars unchanged (no-op
  recompute).
- Both are pure (input connection unmutated; new object returned).

`tests/test_rate_connections.py` or extend an existing module test — server-light
checks if the project has a module-test harness; otherwise rely on the pure-helper
unit tests + the e2e for the wiring.

`tests/test_rate_connections_e2e.py` (new Playwright script, registered by
`run_e2e.py`'s `test_*_e2e.py` glob):
- Navigate to `#sespy_nav_stakeholders`, add one stakeholder; navigate to
  `#sespy_nav_rate`; select the rater; select a connection row (the sample project
  has connections); set the rating inputs; click `#rate-save_rating`; assert the
  table's `#ratings`/`mine` cell for that row updates (e.g. `mine` shows `✓`).
- i18n key-coverage is enforced by the existing
  `tests/test_i18n.py::test_loader_handles_all_supported_languages`.

## Out of scope (later chunks)

- C3: the contested-edges / disagreement *view* (consumes
  `connection_disagreement`) and any edge styling by disagreement.
- Hiding others' ratings during entry (anchoring-independent mode).
- Bulk/CSV rating import, per-stakeholder URL-scoped sessions, real-time sync.
