# Direct QSEM file import — design

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #7.

## Problem / goal

Let SESPy import a native **`.qsem`** file directly, so a model built in the QSEM
web app (Qualitative Systems Exploration Model — the tool behind this session's
factor-quadrant, delay-loop, and multi-rater work) loads with no manual reshaping.

**Format finding (authoritative — from the real sample files).** A `.qsem` file is
**JSON**, a node/link graph (NOT a cross-impact matrix). Verified against
`Food_web_V_00.qsem` and siblings:

```
{ "version", "metadata", "canvas", "loops", "dictionary", "themes", "ui", "analysis" }
canvas.nodes[] : { id:"node-…", label, theme, themeColor, position{x,y}, … }
canvas.links[] : { id, sourceNodeId, targetNodeId, polarity:"positive"|"negative",
                   delay:int, impact:int(1..3), control:int, reviewStatus, … }
themes.definitions[] : { name, color }
```
Real values seen: `polarity` ∈ {positive, negative}; **`impact` ∈ {1,2,3}** (the
strength); `delay` small int (mostly 1, rarely 3); themes = OWFs, Policy,
Environmental pressures, Ecosystem components, Ecosystem Services, LWB, NiD.
`loops`/`analysis` are precomputed QSEM artifacts — **ignored** (SESPy recomputes).

## Decisions

- **Target = native `.qsem` JSON** (the "direct" import). The `QSEM_Connections_*.xlsx`
  edge-list exports are out of scope (the existing `parse_excel` can already approximate
  them).
- **Architecture — isolated module + one upload path:**
  - New `sespy/qsem_import.py`: a **pure** `qsem_to_isa(data) -> (elements, connections)`
    map + `parse_qsem(path) -> ValidationResult` (same contract as
    `excel_import.parse_excel`, ending in the shared `validate_project_payload`).
  - `sespy/modules/import_data.py`: accept `.qsem`/`.json` and **dispatch by extension**
    (`.qsem`/`.json` → `parse_qsem`, else `parse_excel`). Everything downstream
    (preview, commit, event_bus) is already format-agnostic — no other change.
- **No schema/i18n change.** `Connection.ratings` stays `[]` (single-author import).
  The import module's help text is hardcoded English (not `t()`-wired) — update the
  copy only.

## Mapping (`.qsem` → SESPy), grounded in the real files

`qsem_to_isa(data: dict) -> tuple[list[Element], list[Connection]]` (pure):

**Nodes → Elements.** Iterate `data["canvas"]["nodes"]`; assign clean sequential ids
`N001, N002, …` (zero-padded width 3) and build `id_map[node["id"]] = new_id`:
- `id` = generated `N00k`
- `label` = `node["label"]`
- `type` = `node["theme"]` **iff** it exactly matches a `constants.DAPSIWRM_ELEMENTS`
  value (so `"Ecosystem Services"` → real type); otherwise `""`.
- `description` = `f"Theme: {theme}"` when `theme` is set but did NOT map to a type
  (preserve the grouping); else `""`.
- `confidence` = 3
- Duplicate labels are allowed (ids are generated-unique).

**Links → Connections.** Iterate `data["canvas"]["links"]`:
- `source` = `id_map.get(link["sourceNodeId"])`, `target` = `id_map.get(link["targetNodeId"])`
- **Skip** (don't emit) if either ref is missing from `id_map` (dangling), or if
  `source == target` (self-loop).
- `polarity` = `"-"` if `link.get("polarity") == "negative"` else `"+"`.
- `strength` from `impact`: `imp = link.get("impact", 2)`; `"weak" if imp <= 1 else
  "medium" if imp == 2 else "strong"` (so `imp >= 3` → strong; clamp).
- `delay` from `qsem_delay_to_level(link.get("delay", 0))`: `<= 0 → "immediate"`,
  `== 1 → "short"`, `>= 2 → "long"`. (Documented assumption: higher int = longer lag;
  uses all three `DELAY_LEVELS` and preserves QSEM's slow-link signal that
  `normalize_delay` would flatten to `"short"`. `QSEM.docx` does not specify exact
  semantics, so this is the chosen convention.)
- `confidence` = 3; `ratings` = `[]`.

`strength` values are exactly `weak`/`medium`/`strong` (match `network._STRENGTH_RANK`);
`delay` values are exactly from `constants.DELAY_LEVELS`.

## `parse_qsem(path) -> ValidationResult`

1. `json.load` the file. On `JSONDecodeError`/`OSError` → `ValidationResult(False,
   ["Not a valid QSEM/JSON file: <msg>"])`.
2. Shape guard: `data` is a dict with a list at `data["canvas"]["nodes"]`; else
   `ValidationResult(False, ["Not a QSEM file (missing canvas.nodes)"])`.
3. Empty guard: no nodes → `ValidationResult(False, ["QSEM file has no nodes"])`.
4. `elements, connections = qsem_to_isa(data)`.
5. Build the same payload shape `parse_excel` uses
   (`metadata.name = path.stem`, `description = f"Imported from {path.name}"`,
   `isa_data.elements`/`connections` as `__dict__`s) and return
   `validate_project_payload(payload)` — so a bad QSEM file fails the same way a bad
   JSON/Excel load does (dangling refs, duplicate ids, etc.). Because refs are remapped
   and self-loops/dangling links are skipped, a well-formed `.qsem` validates clean.

## Import-module wiring (`import_data.py`)

- `ui.input_file(... accept=[".xlsx", ".xls", ".qsem", ".json"] ...)`; button label and
  the help `<p>` updated to mention "or a `.qsem` model file".
- In `_on_upload`: `result = parse_qsem(path) if path.suffix.lower() in (".qsem", ".json")
  else parse_excel(path)` (import `parse_qsem`). No other change — the preview/commit
  path consumes `ValidationResult` and is format-agnostic.

## Error handling / edge cases

- Malformed JSON / not a dict / missing `canvas.nodes` / empty nodes → friendly
  `ValidationResult` errors (above), surfaced by the existing preview error panel.
- A link to a node absent from `canvas.nodes` → skipped (no dangling ref reaches the
  validator).
- Self-loops → skipped.
- `impact`/`delay` missing on a link → defaults (`impact` 2 → medium, `delay` 0 →
  immediate).
- `impact` out of 1..3 (e.g. 0, 5) → clamped (`<=1` weak, `>=3` strong).
- `theme` absent/null → `type=""`, `description=""`.
- `.json` extension is accepted too (a `.qsem` is JSON); a *non-QSEM* `.json` (no
  `canvas.nodes`) fails the shape guard with a clear message.

## Testing

New `tests/test_qsem_import.py` (+ a committed fixture):
- **`qsem_to_isa` unit** on an inline dict with: a node `theme="Ecosystem Services"`
  (→ `type` match), a node `theme="OWFs"` (→ `type=""`, `description="Theme: OWFs"`),
  a node with no theme; links covering `positive`/`negative`, `impact` 1/2/3 (→
  weak/medium/strong), `delay` 0/1/3 (→ immediate/short/long), one link with a dangling
  `targetNodeId` (skipped), one self-loop (skipped). Assert element ids are remapped
  `N001…`, link refs resolve to those ids, and the skipped links are absent.
- **`qsem_delay_to_level`** boundaries: `-1→immediate`, `0→immediate`, `1→short`,
  `2→long`, `3→long`.
- **`parse_qsem` integration** on a small real-shaped fixture committed at
  `tests/fixtures/sample.qsem` (≤5 nodes, derived/trimmed from a real export): returns
  `valid` with the expected element/connection counts and a sample mapped connection.
- **`parse_qsem` errors**: a non-JSON file → invalid with the JSON message; a JSON file
  without `canvas.nodes` → invalid with the shape message.
- Back-compat: `parse_excel` and the existing `test_excel_import.py` are untouched;
  full e2e (incl. `test_import_e2e.py`) stays green.

## Out of scope (YAGNI)

- The `QSEM_Connections_*.xlsx` / `QSEM_Loops_*.xlsx` edge-list exports (separate path).
- Importing QSEM `loops`/`analysis`/`ui`/`position` data — SESPy recomputes loops and
  lays out its own graph; node positions and precomputed loops are dropped.
- A theme→DAPSIWRM heuristic beyond exact matches (would be opinionated/model-specific).
- `control` / `reviewStatus` link fields (no SESPy counterpart) and per-rater encoding.
- Reverse export SESPy → `.qsem`.
