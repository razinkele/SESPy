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
canvas.nodes[] : { id:"node-…", label, theme?(optional), themeColor?, position{x,y},
                   isGhost?(bool), originalNodeId?(str), … }
canvas.links[] : { id, sourceNodeId, targetNodeId, polarity:"positive"|"negative",
                   delay:int, impact:int(1..3), control:int, reviewStatus, … }
themes.definitions[] : { name, color }
```
Real values seen (verified across all four sample files): `label` always present;
`theme` **key is ABSENT (not null) on ~half the nodes** — must use `.get`;
`polarity` ∈ {positive, negative} (always present); **`impact` ∈ {1,2,3}** (the
strength, always present); `delay` int **∈ {0,1,2,3} seen** (0 and 2 appear in
`Social-Economic focus.qsem`); themes = OWFs, Policy, Environmental pressures,
Ecosystem components, Ecosystem Services, LWB, NiD, Food web. **Ghost nodes**
(`isGhost:true` + `originalNodeId`) are visual duplicates of a canonical node used to
draw cross-canvas edges — e.g. `Food_web_V_00.qsem` has 11 ghosts among 80 nodes (69
canonical = `metadata.nodeCount`), and 7 links source from a ghost. `loops`/`analysis`
are precomputed QSEM artifacts — **ignored** (SESPy recomputes).

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

**Nodes → Elements.** First split ghosts from canonical nodes:
`canonical = [n for n in data["canvas"]["nodes"] if not n.get("isGhost")]` and
`ghost_to_original = {n["id"]: n.get("originalNodeId") for n in nodes if n.get("isGhost")}`.
Iterate **canonical** nodes only; assign clean sequential ids `N001, N002, …`
(zero-padded width 3) and build `id_map[node["id"]] = new_id`:
- `id` = generated `N00k`
- `label` = `node.get("label", "")`
- `theme = node.get("theme") or ""` (the key is ABSENT on ~half of real nodes — every
  node-field access must use `.get`, never `node["theme"]`).
- `type` = `theme` **iff** `theme` exactly matches a `constants.DAPSIWRM_ELEMENTS` value
  (so `"Ecosystem Services"` → real type); otherwise `""`.
- `description` = `f"Theme: {theme}"` when `theme` is non-empty but did NOT map to a
  type (preserve the grouping); else `""`.
- `confidence` = 3
- Duplicate labels are allowed (ids are generated-unique) — real files carry 5–15
  duplicate labels, partly from ghosts now filtered out.

**Links → Connections.** Iterate `data["canvas"]["links"]` (guard a missing/non-list
`links` as `[]`). For each link, **resolve ghost refs to their canonical node first**,
then map to the generated id — `resolve(ref) = id_map.get(ghost_to_original.get(ref, ref))`:
- `source = resolve(link.get("sourceNodeId"))`, `target = resolve(link.get("targetNodeId"))`
- **Skip** (don't emit) if either resolved ref is `None` (dangling / unknown), or if
  `source == target` (self-loop — incl. a ghost edge that resolves back to its origin).
- `polarity` = `"-"` if `link.get("polarity") == "negative"` else `"+"`.
- `strength` from `impact`: `imp = link.get("impact", 2)`; `"weak" if imp <= 1 else
  "medium" if imp == 2 else "strong"` (so `imp >= 3` → strong; clamp).
- `delay` from `qsem_delay_to_level(link.get("delay", 0))`: `<= 0 → "immediate"`,
  `== 1 → "short"`, `>= 2 → "long"`. (Documented assumption: higher int = longer lag;
  uses all three `DELAY_LEVELS` and preserves QSEM's slow-link signal. `QSEM.docx` does
  not specify exact semantics, so this is the chosen convention.) **Do not substitute
  `constants.normalize_delay` here**: its numeric branch maps every nonzero int to
  `"short"` (`"long"` is only reachable by an exact string match), so `delay=2` and
  `delay=3` would silently lose their slow-link signal.
- `confidence` = 3; `ratings` = `[]`.

`strength` values are exactly `weak`/`medium`/`strong` (match `network._STRENGTH_RANK`);
`delay` values are exactly from `constants.DELAY_LEVELS`.

## `parse_qsem(path) -> ValidationResult`

1. `json.load` the file. On `JSONDecodeError`/`OSError` → `ValidationResult(False,
   ["Not a valid QSEM/JSON file: <msg>"])`.
2. Shape guard (all `.get`-safe — never raise): `canvas = data.get("canvas", {})` must be
   a dict with a list at `canvas.get("nodes")`; else
   `ValidationResult(False, ["Not a QSEM file (missing canvas.nodes)"])`. A missing/non-list
   `canvas.get("links")` is tolerated (treated as `[]`), not an error.
3. Empty guard: no nodes → `ValidationResult(False, ["QSEM file has no nodes"])`. (Note:
   `validate_project_payload` accepts an empty elements list as *valid*, so this step-3
   guard is the ONLY place an empty QSEM is rejected — it must be tested.)
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
- **Ghost nodes** (`isGhost:true`) → not imported as elements; links referencing a ghost
  are redirected to the ghost's `originalNodeId` (a canonical node) so the edge attaches
  to the real node instead of being dropped or duplicating it.
- A link to a node absent from `canvas.nodes` (and not a resolvable ghost) → skipped (no
  dangling ref reaches the validator).
- Self-loops (including a ghost edge that resolves back onto its origin) → skipped.
- `theme` key absent (the common case — ~half of real nodes) → `type=""`, `description=""`.
- `impact`/`delay` missing on a link → defaults (`impact` 2 → medium, `delay` 0 →
  immediate).
- `impact` out of 1..3 (e.g. 0, 5) → clamped (`<=1` weak, `>=3` strong).
- `theme` absent/null → `type=""`, `description=""`.
- `.json` extension is accepted too (a `.qsem` is JSON); a *non-QSEM* `.json` (no
  `canvas.nodes`) fails the shape guard with a clear message.

## Testing

New `tests/test_qsem_import.py` (inline-built JSON via `tmp_path`/`json.dump` — the same
build-on-the-fly convention `test_excel_import.py` uses; **no committed binary fixture**,
no hand-trimming a 178 KB file):
- **`qsem_to_isa` unit** on an inline dict with: a node `theme="Ecosystem Services"`
  (→ `type` match), a node `theme="OWFs"` (→ `type=""`, `description="Theme: OWFs"`),
  a node with **no `theme` key at all** (→ `type=""`, `description=""` — guards the
  KeyError trap), and **two nodes sharing a label** (→ both imported, distinct `N00k`
  ids); links covering `positive`/`negative`, `impact` 1/2/3 (→ weak/medium/strong),
  `delay` 0/1/2/3 (→ immediate/short/long/long), one link with a dangling `targetNodeId`
  (skipped), one self-loop (skipped). Assert element ids are remapped `N001…`, link refs
  resolve to those ids, the skipped links are absent.
- **Ghost handling**: an inline dict with a canonical node, a `isGhost:true` node whose
  `originalNodeId` is the canonical node (same label), and a link sourced from the ghost
  → assert the ghost is NOT imported as an element, and the link is emitted connecting
  the canonical node's generated id (ref redirected through `originalNodeId`).
- **`qsem_delay_to_level`** boundaries: `-1→immediate`, `0→immediate`, `1→short`,
  `2→long`, `3→long`. **Plus** assert `constants.normalize_delay(2) == "short"` — a guard
  documenting *why* the custom function exists (a refactor swapping in `normalize_delay`
  would silently break slow links).
- **`parse_qsem` integration**: write a minimal inline dict (3 canonical nodes, 2 valid
  links + 1 dangling link to be skipped) to `tmp_path / "sample.qsem"` via `json.dump`,
  `parse_qsem` it → `valid` with 3 elements / 2 connections and a spot-checked mapped
  connection (polarity + strength + delay).
- **`parse_qsem` errors**: a non-JSON file → invalid with the JSON message; a JSON file
  with no `canvas.nodes` → invalid with the shape message; a JSON file whose
  `canvas.nodes` is `[]` → invalid with the "QSEM file has no nodes" message.
- Back-compat: `parse_excel` and the existing `test_excel_import.py` are untouched;
  full e2e (incl. `test_import_e2e.py`) stays green.

## Out of scope (YAGNI)

- The `QSEM_Connections_*.xlsx` / `QSEM_Loops_*.xlsx` edge-list exports (separate path).
- Importing QSEM `loops`/`analysis`/`ui`/`position` data — SESPy recomputes loops and
  lays out its own graph; node positions and precomputed loops are dropped.
- A theme→DAPSIWRM heuristic beyond exact matches (would be opinionated/model-specific).
- `control` / `reviewStatus` link fields (no SESPy counterpart) and per-rater encoding.
- Reverse export SESPy → `.qsem`.
