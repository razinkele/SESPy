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
  (exact `DAPSIWRM_ELEMENTS` match; else `type=""`).
  When provided, each canonical node's type/description are computed from the
  **resolved** type (membership-based coercion — NOT truthiness — so `None`,
  stale, or non-canonical values become untyped):
  ```python
  theme = node.get("theme") or ""          # identical collapse to today's code
  rt = theme_map.get(theme, "")
  rt = rt if rt in DAPSIWRM_ELEMENTS else ""   # coerce anything not a real type
  el.type = rt
  el.description = "" if (rt or not theme) else f"Theme: {theme}"
  ```
  Both branches (None and mapped) MUST use the same `node.get("theme") or ""`
  collapse and the same `isinstance(n, dict) and not n.get("isGhost")` node
  filter. **Pitfall (review):** deriving `description` from the old
  `theme in DAPSIWRM_ELEMENTS` flag would tag a map-typed node (e.g.
  `OWFs→Activities`) with a redundant `"Theme: OWFs"`; description must key off
  `rt`, not membership of the raw theme.

- `qsem_themes(data) -> list[tuple[str, int]]` — distinct themes of **canonical
  (non-ghost)** nodes with their node counts, sorted by count desc then name.
  **Must use byte-for-byte the same node guard and theme normalization as
  `qsem_to_isa`** (`isinstance(n, dict) and not n.get("isGhost")`, then
  `node.get("theme") or ""`). If they diverge (e.g. `.get("theme","")` leaving a
  `None` key), a genuinely typed theme like "Ecosystem Services" can be keyed
  differently in `theme_map` than `qsem_to_isa` looks up, and — since mapped
  mode has NO exact-match fallback — silently drops to untyped. A unit test
  asserts `{t for t,_ in qsem_themes(data)}` equals the set of themes
  `qsem_to_isa` actually resolves. The empty theme is included as the literal
  `""` (UI renders it "(untyped)").

- `suggest_dapsiwrm_map(themes) -> dict[str, str]` — the heuristic pre-fill.
  Input is an iterable of theme strings; output maps each theme to a DAPSIWRM
  type or `""`. An exact `DAPSIWRM_ELEMENTS` match is checked **first** (e.g.
  "Ecosystem Services" → itself). Otherwise case-insensitive **substring**
  keyword rules, first match wins, in this order (`Responses` deliberately
  precedes `Goods & Benefits` so `governance`/`management` are not shadowed by
  the broad `good`):

  | Order | Keyword(s) in theme | DAPSIWRM type |
  |---|---|---|
  | 1 | `driver` | Drivers |
  | 2 | `pressure` | Pressures |
  | 3 | `activit`, `fishing`, `farm`, `wind`, `owf`, `shipping`, `aquacult`, `tourism` | Activities |
  | 4 | `service` | Ecosystem Services |
  | 5 | `process`, `function`, `component`, `habitat`, `species`, `food web`, `ecolog` | Marine Processes & Functioning |
  | 6 | `policy`, `response`, `management`, `measure`, `governance`, `regulation` | Responses |
  | 7 | `benefit`, `good`, `welfare`, `value`, `econom` | Goods & Benefits |

  No keyword match → `""` (Leave untyped). Verified against every real NiD4OCEAN
  theme: `OWFs`→Activities, `Environmental pressures`→Pressures, `Ecosystem
  components`→Marine Processes, `Policy`→Responses, `Food web`→Marine Processes,
  `Ecosystem Services`→itself; `LWB`, `NiD`, `""` → untyped. **Note (review):**
  bare short/abbrev substrings are fragile — `nid` was DROPPED from the rules (it
  would match "Unidentified…"); `LWB`/`NiD` stay untyped by design and the user
  assigns them in the UI. `good`/`value` remain broad but now sit behind the more
  specific rules, and every guess is user-editable. The table is a starting
  point, not an authority.

### 2. UI — `sespy/modules/import_data.py`

- A checkbox `assign_dapsiwrm` labelled **"Assign DAPSIWRM types"** that is a
  **static** input in `import_data_ui()` (always in the DOM), *shown/hidden* by
  CSS/`panel_conditional` based on whether the current upload is QSEM — NOT
  conditionally created. Default **unchecked**, with helptext ("Map each QSEM
  theme to a DAPSIWRM category so the diagram is coloured and levelled").
  **Rationale (CRITICAL review finding):** if the checkbox were rendered only for
  QSEM, `input["assign_dapsiwrm"]()` would be unset on an Excel upload and raise
  `SilentException`, silently aborting the *shared* `_on_commit` effect — Excel
  import would break with no error. Every read of it in `_on_commit` is still
  guarded (`.is_set()`).
- When checked, a mapping table renders below the preview via `@render.ui`
  (`ui.output_ui("dapsiwrm_map")`). One row per theme from `qsem_themes`:
  `theme label · node count · ui.input_select(...)`. Select choices = the 7
  `DAPSIWRM_ELEMENTS` plus a "Leave untyped" option (value `""`). Each select is
  pre-selected to `suggest_dapsiwrm_map`'s guess.
- Select input ids are **generation-stamped**: `map_{seq}_{i}` where `seq` is an
  upload counter bumped in `_on_upload`, and `i` is the theme index. Bracket
  access only (`input[f"map_{seq}_{i}"]()`; attribute `input.map_i` cannot take a
  computed name). A `{seq, [themes]}` lookup (in a reactive) maps ids back on
  commit. **Rationale (HIGH):** plain reused `map_0..map_k` ids let a *stale*
  value from the previous file be read as the current file's mapping (the id
  still exists, no exception) — the seq stamp makes a stale id simply not exist.
- On **Load into project** (`_on_commit`): read the guarded checkbox; if set and
  the upload is QSEM, build `theme_map` by reading each select **defensively**,
  falling back to the heuristic guess when a select isn't set yet (render not
  settled): `val = input[key]() if input[key].is_set() else suggested[theme]`.
  **Rationale (HIGH):** an unguarded read of a not-yet-rendered `map_i` raises
  `SilentException` and silently no-ops the whole import; the fallback makes
  "commit before the UI settled" degrade to the pre-filled guess. Then call the
  shared `build_project(raw, name, theme_map)` helper (below) and
  `project_data.set(...)`. Otherwise the existing commit path runs unchanged.

### 3. Data flow / plumbing

- **`raw_qsem` plumbing must be added** — `_on_upload → parse_upload → parse_qsem`
  currently reads the JSON and returns only a `ValidationResult`; the raw dict is
  discarded (review finding). For a QSEM suffix, `_on_upload` re-`json.load`s the
  temp `datapath` and stores the dict in `raw_qsem: reactive.Value[dict | None]`
  **at upload time** (the temp `datapath` may be gone by commit, so re-reading at
  commit is not an option). It also stores the theme list + `seq`. Non-QSEM
  uploads set `raw_qsem=None`, which hides the checkbox + table.
- **`build_project(raw, name, theme_map)` helper (in `qsem_import.py`)** — the
  re-map path must NOT just call `qsem_to_isa` (that returns `(elements,
  connections)`, not a validated `Project`, and would lose the workbook name).
  Factor out the payload-build + `validate_project_payload` + `metadata.name =
  Path(name).stem` steps that `parse_qsem`/`parse_upload` do today into one
  helper, and call it from both `parse_qsem` (theme_map=None) and `_on_commit`
  (with the map). Guarantees the mapped project is validated and named
  identically to the unmapped one.
- **Commit resets the new state** — the existing `_on_commit` ends by clearing
  `parsed` + disabling the button; it must also reset `raw_qsem=None`, clear the
  theme/`seq` reactive, and `ui.update_checkbox("assign_dapsiwrm", value=False)`,
  so the mapping table/checkbox don't linger with stale themes into the next
  upload.
- The preview (element/connection counts) reflects the *unmapped* parse; the
  mapping only affects `type`, not counts, so the preview stays valid. A small
  post-commit notification reports how many nodes were typed vs left untyped.

### 4. Edge cases

- Unmapped / "Leave untyped" themes → `type=""`; still visible in the CLD via
  `cld_keep_types`.
- Excel upload → checkbox present in DOM but **hidden**; table not rendered; the
  guarded read in `_on_commit` returns unset → plain path (no `SilentException`).
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
  unknown (`LWB`, `NiD`, ``) → `""`. Ordering guard: a synthetic
  `"Good governance"` → Responses (not Goods & Benefits), proving rule 6 precedes
  rule 7.
- `qsem_to_isa(data, theme_map)`: overrides applied; `""`/absent → untyped;
  non-DAPSIWRM map value coerced to `""`; a map-typed non-DAPSIWRM theme (e.g.
  `OWFs→Activities`) has `description == ""` (NOT `"Theme: OWFs"`); `theme_map=None`
  byte-identical to today (regression).
- **Consistency invariant:** `{t for t,_ in qsem_themes(data)}` ==
  `{el's resolved theme for el in qsem_to_isa(data)}` on every real model — the
  key set the UI offers must equal what `qsem_to_isa` looks up (guards the
  silent-drop-to-untyped bug).
- `qsem_themes`: correct distinct themes + counts on a real model; empty theme
  present as `""`; ghosts + non-dict nodes excluded; `None`/missing theme
  collapses to `""` (same as `qsem_to_isa`).
- `build_project(raw, name, theme_map)`: returns a validated `Project` with
  `metadata.name == Path(name).stem` for both `theme_map=None` and a real map.

**e2e (`tests/test_import_e2e.py` extension or a new script — wait_for_selector
on `#cld-network` + poll, per the pyvis-timing-flake convention):**
- Upload a `.qsem`, tick "Assign DAPSIWRM types", assert the mapping table
  appears with pre-filled selects, commit, navigate to CLD, assert nodes now
  carry DAPSIWRM group/colour (e.g. `pyvisNetworks['cld-network']` node groups
  include DAPSIWRM types, not just `""`).
- Regression: upload `.qsem` **without** ticking the box → behaves as today.
- **Regression (CRITICAL):** upload an **Excel** file and commit — must succeed
  (proves the static-checkbox guard didn't break the shared commit path).

## Files touched

- `sespy/qsem_import.py` — `theme_map` param on `qsem_to_isa`, new `qsem_themes`,
  `suggest_dapsiwrm_map`, and `build_project(raw, name, theme_map)` (factored
  from the current `parse_qsem` body so both paths validate + name identically).
- `sespy/modules/import_data.py` — static `assign_dapsiwrm` checkbox (shown/hidden),
  `dapsiwrm_map` render.ui table, generation-stamped select ids, guarded reads,
  `raw_qsem`/theme/`seq` reactives, commit re-map + state reset.
- `sespy/translations/core.json` — new i18n keys (checkbox label, table headers,
  "Leave untyped") × 9 languages.
- `tests/test_qsem_dapsiwrm_map.py` (new) — unit tests.
- `tests/test_import_e2e.py` — e2e extension (or new `test_qsem_map_e2e.py`).
- `CHANGELOG.md` — `[Unreleased]` entry.

## Rollout

Standard: full e2e gate green (28/29, WeasyPrint the only known false-red) →
commit → push → deploy (`deploy.sh` preserves the server feedback DB) → verify
live via the `ssh -L 8899:127.0.0.1:3838` tunnel + a real import.
