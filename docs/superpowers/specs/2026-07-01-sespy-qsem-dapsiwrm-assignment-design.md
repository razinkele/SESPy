# Optional DAPSIWRM assignment on QSEM import — design

_Date: 2026-07-01_

## Problem

QSEM / food-web `.qsem` models use their own node themes (`Environmental
pressures`, `Ecosystem components`, `Policy`, `OWFs`, `LWB`, `NiD`, …) or none.
`qsem_to_isa` only assigns a SESPy DAPSIWRM `type` on an **exact** match against
`DAPSIWRM_ELEMENTS` (in practice only "Ecosystem Services" matches), so almost
every imported element is `type=""`. Untyped elements now render in the CLD
(fixed in `e73cfeb` via `cld_keep_types`), but they get no DAPSIWRM colour,
shape, or hierarchical level — the diagram is a flat, uncoloured band.

## Goal

Let the user **optionally** assign DAPSIWRM types to imported QSEM nodes during
import, so the CLD renders with the DAPSIWRM structure. Assignment is a
**hybrid**: a deterministic heuristic pre-fills a best-guess mapping, shown as
**editable per-theme dropdowns** the user can correct before committing.
Opt-in via a checkbox that is **OFF by default** (current behaviour preserved).

## Non-goals

- Per-element (per-node) assignment. Granularity is **per-theme**: every node
  sharing a theme gets the same type. (Per-node is a possible future step.)
- AI/LLM classification. Deterministic heuristic only; no ANTHROPIC_API_KEY.
- Changing Excel import. The option is QSEM-only.
- Re-mapping already-committed projects (this is an import-time step only).

## Design

### 1. Data layer — `sespy/qsem_import.py`

Add three pure functions (no Shiny), keeping `qsem_to_isa` as the single
theme→type authority:

- `qsem_to_isa(data, theme_map=None)` — new optional
  `theme_map: dict[str, str] | None`. When `None`, behaviour is **unchanged**
  (exact `DAPSIWRM_ELEMENTS` match; else `type=""`). When provided, a node's
  `type = theme_map.get(theme, "")` — a value of `""` (or a theme absent from
  the map) means untyped. Only values in `DAPSIWRM_ELEMENTS` are accepted as
  types; anything else is coerced to `""` (defensive, so a stale/hostile map
  can't inject a bogus type). The `description="Theme: X"` annotation for
  untyped nodes is retained.

- `qsem_themes(data) -> list[tuple[str, int]]` — distinct themes of **canonical
  (non-ghost)** nodes with their node counts, sorted by count desc then name.
  The empty theme is included in the list as the literal `""` (the UI renders it
  as "(untyped)"). Used to build the mapping table.

- `suggest_dapsiwrm_map(themes) -> dict[str, str]` — the heuristic pre-fill.
  Input is an iterable of theme strings; output maps each theme to a DAPSIWRM
  type or `""`. Case-insensitive **substring** keyword rules, first match wins,
  evaluated in this order (most specific first):

  | Keyword(s) in theme | DAPSIWRM type |
  |---|---|
  | `driver` | Drivers |
  | `pressure` | Pressures |
  | `activit`, `fishing`, `farm`, `wind`, `owf`, `shipping`, `aquacult`, `tourism` | Activities |
  | `service` | Ecosystem Services |
  | `benefit`, `good`, `welfare`, `value`, `econom` | Goods & Benefits |
  | `process`, `function`, `component`, `habitat`, `species`, `food web`, `ecolog` | Marine Processes & Functioning |
  | `policy`, `response`, `management`, `measure`, `governance`, `regulation`, `nid` | Responses |

  No keyword match (incl. the empty theme and opaque abbreviations like `LWB`)
  → `""` (Leave untyped). An exact `DAPSIWRM_ELEMENTS` match always wins over
  keywords (e.g. "Ecosystem Services" → itself). The table is a starting point;
  the user corrects any row in the UI.

### 2. UI — `sespy/modules/import_data.py`

- A checkbox `assign_dapsiwrm` labelled **"Assign DAPSIWRM types"**, shown only
  when the current upload is a `.qsem`/`.json` (hidden for Excel). Default
  **unchecked**.
- When checked, a mapping table renders below the preview via `@render.ui`
  (`ui.output_ui("dapsiwrm_map")`). One row per theme from `qsem_themes`:
  `theme label · node count · ui.input_select(...)`. Select choices = the 7
  `DAPSIWRM_ELEMENTS` plus a "Leave untyped" option (value `""`). Each select is
  pre-selected to `suggest_dapsiwrm_map`'s guess.
- Select input ids are **index-based** (`map_0`, `map_1`, …) to avoid unsafe
  characters in theme strings; an index→theme lookup (kept in a reactive) maps
  them back on commit.
- On **Load into project** (`_on_commit`): if the box is checked and the upload
  is QSEM, read each `map_i` select, build `theme_map = {theme_i: input.map_i()}`,
  call `qsem_to_isa(raw_data, theme_map)` to rebuild elements/connections,
  wrap into the same payload/Project, and set `project_data`. Otherwise the
  existing commit path runs unchanged.

### 3. Data flow / plumbing

- `_on_upload` already parses the file. For QSEM uploads, also store the raw
  parsed `dict` in a `raw_qsem: reactive.Value[dict | None]` and the theme list
  in a reactive, so (a) the mapping table can render and (b) `_on_commit` can
  re-map without re-reading the temp file. Non-QSEM uploads set `raw_qsem` to
  `None`, which hides the checkbox + table.
- The preview (element/connection counts) continues to reflect the *unmapped*
  parse; the mapping only affects `type`, not counts, so the preview stays
  valid. (Optional nicety, out of scope: live-update the "Element types" preview
  line as the map changes.)

### 4. Edge cases

- Unmapped / "Leave untyped" themes → `type=""`; still visible in the CLD via
  `cld_keep_types`.
- Excel upload → checkbox and table absent.
- Checkbox toggled on then off → commit uses the plain (unmapped) path.
- Ghost nodes are already filtered by `qsem_to_isa` before typing; the mapping
  operates on canonical themes only. `qsem_themes` must apply the same
  non-ghost filter so counts match what actually gets typed.
- A theme string present at upload but edited to a non-DAPSIWRM value → coerced
  to `""` by `qsem_to_isa`'s validation.

### 5. Testing

**Unit (pure, no browser):**
- `suggest_dapsiwrm_map`: known themes → expected types (`Environmental
  pressures→Pressures`, `Policy→Responses`, `OWFs→Activities`, `Ecosystem
  components→Marine Processes & Functioning`, `Ecosystem Services→` itself);
  unknown (`LWB`, ``) → `""`.
- `qsem_to_isa(data, theme_map)`: overrides applied; `""`/absent → untyped;
  non-DAPSIWRM map value coerced to `""`; `theme_map=None` unchanged vs. today.
- `qsem_themes`: correct distinct themes + counts on a real model; empty theme
  present; ghosts excluded.

**e2e (`tests/test_import_e2e.py` extension or a new script):**
- Upload a `.qsem`, tick "Assign DAPSIWRM types", assert the mapping table
  appears with pre-filled selects, commit, navigate to CLD, assert nodes now
  carry DAPSIWRM group/colour (e.g. `pyvisNetworks['cld-network']` node groups
  include DAPSIWRM types, not just `""`).
- Regression: upload `.qsem` **without** ticking the box → behaves as today.

## Files touched

- `sespy/qsem_import.py` — `theme_map` param, `qsem_themes`, `suggest_dapsiwrm_map`.
- `sespy/modules/import_data.py` — checkbox, mapping table, commit wiring, raw-qsem reactive.
- `sespy/translations/core.json` — new i18n keys (checkbox label, table headers,
  "Leave untyped") × 9 languages.
- `tests/test_qsem_dapsiwrm_map.py` (new) — unit tests.
- `tests/test_import_e2e.py` — e2e extension (or new `test_qsem_map_e2e.py`).
- `CHANGELOG.md` — `[Unreleased]` entry.

## Rollout

Standard: full e2e gate green (28/29, WeasyPrint the only known false-red) →
commit → push → deploy (`deploy.sh` preserves the server feedback DB) → verify
live via the `ssh -L 8899:127.0.0.1:3838` tunnel + a real import.
