# P1a — Link rules, schema v7 and the R template mapper

**Status:** design, awaiting user review · **Date:** 2026-10-17
**Roadmap:** `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md` §2 P1a
(branch `docs/r-parity-roadmap`). P0 (v1.12.2 + v1.12.3) is shipped.
**R reference:** MarineSABRES_SES_Shiny **v1.29.0 (`e33faea`)**. The files P1a
reads are unchanged since the roadmap baseline `e3c3b77`: the 7
`data/*_SES_Template.json`, `functions/dapsiwrm_connection_rules.R`,
`functions/template_loader.R` and `modules/template_ses_module.R`.
R source releases ported: 1.17.1, 1.18.0, 1.22.0 (N26/N61/N62), 1.22.3.
**Target release:** SESPy **v1.13.0**.

## 1. Purpose and success

P1a is the foundation that P2 (gallery templates) and P1b/P1c (Response
register, indicator fields) build on. It does **not** add the 7 R templates to
the template gallery; that is P2.

**Done when:**
1. All 7 R templates convert with the mapper, and SESPy save → load keeps every
   link's `(source, target, polarity, strength, confidence, description)`
   equal to the R JSON. Element counts also match. The mapper reports **zero
   off-rule links** for all 7.
2. The R fields not carried over are listed (§6).
3. The full unit and e2e gates pass, and so does MosaicSES's suite against the
   branch.

Counts are always read from the fixture files, never hard-coded. The roadmap's
"320 links" predates R 1.22.3, which added 15 GB→Response/Measure links.

## 2. Decisions already taken (with the user, 2026-10-17)

| Topic | Decision |
|---|---|
| Off-rule links | **Allow and warn**, as R does (`validate_connection(strict=FALSE)`). ISA entry shows a note; loading, templates and Excel import accept the link and log it. |
| Mapper location | **Approach A:** a library module, `sespy/r_template_mapper.py`. R's JSONs are sha256-pinned **test fixtures** and never ship to the server. P2's sync script reuses the function. |
| Polarity seeding | ISA entry pre-fills polarity from the rule table when a source and target are chosen, and the user can override it (R's main entry path, `default_polarity_for_matrix`). |
| Keyword polarity overrides | Not in P1a. R uses `infer_connection_polarity` only in the Graphical SES builder, so it moves to **P9**. |
| Boolean ceiling | 20 nodes (R `DYNAMICS_MAX_BOOLEAN_NODES`). SESPy's default stays 12. |

**Deliberate divergences from R** (SESPy keeps more than R does):
- R drops connection `description` on template load; it never reaches the
  matrices (`template_loader.R:455`, `template_ses_module.R:782-852`). SESPy
  keeps it.
- R ignores element-level `type` labels and all extras
  (`json_elements_to_df`, `template_loader.R:40`). SESPy keeps them in
  `r_extra`.

## 3. Link rules

### 3.1 Data: `sespy/constants.py`
`DAPSIWRM_ADJACENCY_RULES`: a mapping from source type to a frozen record with:
- `targets`: canonical pairs, offered as suggestions;
- `extension_targets`: valid pairs that are never suggested;
- `fallback_polarity`: used only when a pair has no polarity of its own.

Each target carries `(to_type, polarity, rule_id)`. Type names are SESPy's 7
`DAPSIWRM_ELEMENTS`, the same strings R uses. Values are copied from
`dapsiwrm_connection_rules.R:26-341`:

| From | Canonical (polarity, rule) | Extension (polarity, rule) | Fallback |
|---|---|---|---|
| Drivers | Activities (+, 1) | Pressures (+, ExUP) | + |
| Activities | Pressures (+, 2) | Activities (+, 18) | + |
| Pressures | MPF (−, 3) | Pressures (+, 17) | − |
| MPF | Ecosystem Services (+, 4) | MPF (+, 16) | + |
| Ecosystem Services | Goods & Benefits (+, 5) | — | + |
| Goods & Benefits | Drivers (+, 6/7), Responses (+, 8) | — | + |
| Responses | Drivers (−, 9), Activities (−, 10), Pressures (−, 11), MPF (+, 12) | Responses (+, 14) | − |

- Polarity is **per pair**: P→MPF is −, while P→P is +; R→MPF and R→R are +,
  while R→D/A/P are −. A per-source default would be wrong.
- There is no Measures entry. R folds Measures into Responses; see §5.
- D→GB (R's removed Rule 15) is off-rule.

### 3.2 Logic: `sespy/link_rules.py` (new; no Shiny import)
- `classify(from_type, to_type) -> "canonical" | "extension" | "off_rule" | "untyped"`.
  The result is `"untyped"` whenever either type is `""`; QSEM themes are
  untyped, and they are never flagged.
- `default_polarity(from_type, to_type) -> "+" | "-"`. It returns the pair's
  polarity, else the source's fallback, else `"+"` (R's
  `get_rule_default_polarity`).
- `rule_id(from_type, to_type) -> str | None`.
- `off_rule_message(from_label, to_label, translator)` returns the i18n text
  for the entry warning. It is translated into all 9 languages.

### 3.3 Derived topology
`data_structure._CONN_TYPES` and `_VALID_TYPE_PAIRS` are **derived** from the
canonical targets. The 10 pairs become 11, adding `("responses", "states",
"responses_states")`. The slug order still follows DAPSI(W)R(M) layer flow.
Consumers:
- `connection_scorer.py`, the rule-based suggestion scorer;
- `claude_backend.py`, which validates model-proposed pairs;
- the comment in `network.py:970`.

Both suggestion backends will now **propose Responses → MPF links**. This is
intended parity and gets an explicit test. Extension pairs are not suggested,
as in R.

### 3.4 ISA data entry (`sespy/modules/isa_data_entry.py`)
- When both a source and a target are chosen, the polarity select is set to
  `default_polarity(...)`. The user can still change it before adding the link.
  The selected source and target are restored with the `isolate()` pattern
  already used in this module.
- An off-rule pair shows a yellow note under the form, naming the pair and why
  it is off-rule. The link still saves.
- Untyped elements: no note, polarity `+`.

### 3.5 Loading, templates and Excel import
Off-rule links are accepted and logged (`link_rules` logger, one line per
project with the count and the first few pairs). They are never rejected, so
existing projects behave exactly as before.

## 4. Schema v7 (`sespy/data_structure.py`)

| Field | Type, default | Serialised |
|---|---|---|
| `Connection.description` | `str = ""`, keyword-only | only when non-empty |
| `Element.r_extra` | `dict[str, Any] = {}`, keyword-only (`default_factory`) | only when non-empty |
| `ProjectMetadata.origin` | `str = ""` (e.g. `"r_template"`) | always |
| `ProjectMetadata.r_template_version` | `str = ""` (R `metadata.version`, e.g. `"2.3"`) | always |
| `ProjectMetadata.min_sespy_version` | `str = ""` | always; stamped on save |

- **Omit when empty.** A native project saved by 1.13 has the same element and
  connection shape as v6, so 1.12.2, which crashes on unknown element keys,
  still opens it. 1.12.3 and later tolerate the keys either way.
- **`PROJECT_SCHEMA_VERSION = 7`.** A 1.12.3 reader opening a v7 file shows the
  P0b warning and disables autosave, because it would drop `description` and
  `r_extra`. That is intended.
- **Stamping.** A new `SCHEMA_MIN_READER = {7: "1.13.0"}` table. On every save
  (`project_to_bytes`, `save_project_atomic`, autosave), `min_sespy_version`
  becomes the higher of the existing value and `SCHEMA_MIN_READER[current
  schema]`, compared with `packaging.version`. It is **never lowered**, so a
  file last written by a newer build keeps that build's higher stamp. An
  unparsable existing stamp is replaced.
- **Serialisation.** `to_dict`/`from_dict` have explicit code for each new
  field; there is no reliance on `asdict`. A round-trip test covers every field.
- **Load validation** (`persistent_storage.validate_project_payload`):
  - `description` must be a string, or the load is rejected with a clear message
    (the same treatment as a bad `polarity`);
  - an `r_extra` that is not an object is **dropped with a logged warning**,
    never fatal, because it is opaque passthrough data;
  - the element type `"Measures"` is never written. The mapper folds it, and
    validation's type list does not change.
- **`Project.replace()`** must keep both new fields through every editor path.
  Editors already edit through `replace()`, and a test pins this for
  `description` and `r_extra`.

## 5. R template mapper (`sespy/r_template_mapper.py`, new; no Shiny import)

```python
@dataclass(frozen=True)
class ConversionReport:
    key: str
    counts_by_type: dict[str, int]
    link_count: int
    folded_measures: tuple[str, ...]          # element ids
    off_rule_links: tuple[tuple[str, str], ...]
    type_mismatches: tuple[str, ...]          # from_type/to_type vs category
    extra_fields: tuple[str, ...]             # field names moved into r_extra
    template_meta: dict[str, Any]             # complexity, usage_notes, source,
                                              # applicable_regions, regional_context

def convert_r_template(raw: dict, *, key: str) -> tuple[Project, ConversionReport]: ...
```

**Input format.** R's current shape: `dapsiwrm_framework` holds per-category
lists, plus a flat `connections` list. Legacy category keys are accepted as
aliases: `states` for `marine_processes`, `impacts` for `ecosystem_services`,
`welfare` for `goods_benefits` (R `.extract_template_elements`,
`template_loader.R:165`). The older `elements` + `template_info` format raises
`ValueError("unsupported legacy R template format")`: none of the 7 use it.

**Categories → SESPy type:**

| Category | Type |
|---|---|
| drivers | Drivers |
| activities | Activities |
| pressures | Pressures |
| marine_processes (or states) | Marine Processes & Functioning |
| ecosystem_services (or impacts) | Ecosystem Services |
| goods_benefits (or welfare) | Goods & Benefits |
| responses | Responses |
| measures | Responses, plus `r_extra["r_kind"] = "measure"` |

**Elements.**
- `id` is kept (R ids are unique within a template; verified for all 7).
- `name` → `label`; `description` → `description`; `confidence` = 3.
- The **type comes from the category**, never from the element's `type`. That
  field is missing in three templates, and Caribbean uses it for domain labels.
  The literal `type` is stored as `r_extra["r_type"]`. Every other field
  without a SESPy column goes into `r_extra` under its R name.

**Measures fold into Responses** (as R does, `template_loader.R:103,189-190`).
As a result, M→R links become R→R (extension, Rule 14), and GB→M links become
GB→R (canonical, Rule 8).

**Connections.**
- `from_id` → `source`, `to_id` → `target`.
- `polarity` (`+`/`-`) and `strength` (`weak`/`medium`/`strong`) are kept
  as-is. `confidence` is kept as an integer clamped to 1–5. `description` is
  kept.
- `delay = "immediate"`, since R templates have no delay.
- R's `from_type`/`to_type` labels (driver, activity, pressure, state, impact,
  welfare, response, measure) are checked against each endpoint's category.
  A mismatch goes into `type_mismatches` and is not fatal.
- A connection whose endpoint id does not exist raises `ValueError`. This
  cannot happen with the 7 fixtures, which were verified.

**Metadata.**
- `name` = `template_name`; `description` = `template_description`;
  `regional_sea` = `regional_context.regional_sea` when present.
- `origin = "r_template"`; `r_template_version` = `metadata.version`.
- Gallery-only facts go into `report.template_meta` for P2's card, not into
  the project.

**Fixtures and drift.**
- The 7 files are copied to `tests/parity/r_templates/` with their R file
  names: Aquaculture, Caribbean, ClimateChange, Fisheries, OffshoreWind,
  Pollution, Tourism. `Caribbean_SES_Template_backup.json` is excluded.
- New `docs/parity/R_SYNC.md` records the R tag and commit (v1.29.0,
  `e33faea`) and each file's `sha256_norm`. That is the sha256 of the parsed
  JSON re-serialised with sorted keys, UTF-8 and LF (roadmap §3).
- `tests/parity/test_r_sync.py` asserts the hashes. A new R release is adopted
  by re-copying the fixtures and updating `R_SYNC.md` in the same commit.

## 6. R fields not carried over

- **Connections:** none. All fields are kept, and `from_type`/`to_type` are only
  used for the mismatch check.
- **Elements:** none are lost; all go to `r_extra`.
- **Template top level:** `complexity`, `usage_notes`, `metadata.source`,
  `metadata.applicable_regions`, `metadata.created_date` and the rest of
  `regional_context` are not stored in the project. They are available in
  `ConversionReport.template_meta` for P2.

## 7. Boolean hardening

- `sespy/dynamics.py`: a new `BOOLEAN_MAX_NODES_CEILING = 20`.
  `boolean_attractors(rules, max_nodes=12, *, ceiling=BOOLEAN_MAX_NODES_CEILING)`
  clamps `max_nodes` to `[1, ceiling]` before the size check. P7 may pass a
  different `ceiling` explicitly.
- `sespy/modules/analysis_boolean.py`: `input.max_nodes()` goes through
  `safe_int(..., 12)` and is then clamped to `[1, ceiling]` on the server. The
  UI input's `max` is the ceiling.
- Divergence: R maps a non-integer input to the ceiling, while SESPy keeps its
  existing fallback of 12, which is cheaper.

## 8. Excel import (`sespy/excel_import.py`)

- `CONN_DESC_COLS = ("description", "Description", "rationale", "Rationale")`
  is read into `Connection.description`.
- **Kumu polarity.** When no polarity column is present, a connection's
  `Label`/`label` column decides: a value of `-`, or one starting with `-`, is
  negative; anything else is positive (R `excel_import_helpers.R:432-437`).
- **Element type aliases**, taken from R's list (`excel_import_helpers.R:160-175`):
  `Driver`, `Activity`, `Pressure`, `Marine Process and Function`,
  `Marine Process and Functioning`, `State`, `State Change`,
  `Ecosystem Service`, `Impact`, `Good and Benefit`, `Goods and Benefits`,
  `Welfare`, `Response`, `Measure`. They are matched case-insensitively. A
  `Measure` becomes Responses with `r_extra["r_kind"] = "measure"`.
- Off-rule links import with a logged warning (§3.5).
- **Not in P1a:** R's multi-sheet "Standard Entry" workbook (`Matrix_<key>`,
  `Linked*` columns). It is matrix-shaped like R projects and belongs with the
  R project import.

## 9. MosaicSES

MosaicSES builds `Project`/`Element`/`Connection` directly and embeds Projects
in `.multises.json`.
- The new fields are keyword-only with defaults, so construction is unchanged.
- MosaicSES imports `_CONN_TYPES` nowhere (checked); it imports
  `sespy.constants` and `sespy.data_structure`, which are on its §9.3
  allow-list.
- **Gate:** MosaicSES unit tests and its full suite run against the SESPy
  branch before merge, and the live MosaicSES is checked after deploy.
- Known follow-up, not in P1a: MosaicSES does not yet warn about P0b's
  `newer_build` on compartments.

## 10. Testing

TDD throughout. New unit test files:
- `tests/test_link_rules.py`:
  - every row of §3.1;
  - classification, per-pair polarity, untyped exemption;
  - the 11 derived `_CONN_TYPES`;
  - the scorer and the Claude backend accept R→MPF.
- `tests/test_schema_v7.py`:
  - round-trip of `description`/`r_extra`;
  - empty values omitted;
  - a v6 file loads;
  - stamping: raised, never lowered, unparsable stamp replaced;
  - a bad `description` is rejected and a bad `r_extra` is dropped;
  - `replace()` keeps both fields;
  - P0b still flags a v8 file.
- `tests/test_r_template_mapper.py`:
  - the done-when test over all 7 fixtures;
  - Measures folding with `r_kind`;
  - `r_type` capture;
  - report contents;
  - the legacy-format error and dangling-id error.
- `tests/parity/test_r_sync.py`: fixture hashes against `R_SYNC.md`.
- Additions to `tests/test_dynamics.py` (ceiling and clamp) and
  `tests/test_excel_import.py` (description, Kumu label, aliases, Measure).

**Existing tests that change:** `test_schema_version_is_6` becomes 7, and the
scorer and Claude-backend pair-count tests go from 10 to 11.

**New e2e test, `tests/test_link_rules_e2e.py`:**
- choosing a Pressure → MPF pair pre-fills polarity `−`;
- choosing Drivers → Goods & Benefits shows the off-rule note, and the link
  still saves;
- selectors are scoped (memory: e2e text-selector collisions).

**Gates:** the CI unit command; the full e2e gate with nothing heavy running
alongside, where any red result is rerun on its own before it is believed; the
MosaicSES suite; two in-loop reviews (spec and implementation), each run until a
round finds no Critical or Important issues.

## 11. Release (v1.13.0)

- CHANGELOG `[1.13.0]` naming P1a and R 1.17.1 / 1.18.0 / 1.22.0 / 1.22.3, and
  listing the divergences (§2).
- Version bumps in `pyproject.toml`, `sespy/__init__.py` and the MANUAL version
  line.
- MANUAL: link rules, the polarity default and the off-rule note.
- Re-shoot only the ISA-entry screenshot.
- Deploy and verify on laguna, including a server-side check that a v7 project
  with descriptions and `r_extra` loads, and recheck the live MosaicSES.

## 12. Out of scope (later sub-projects)

- Gallery entries for the 7 templates and `scripts/sync_r_templates.py` (P2).
- Response register and indicator fields (P1b/P1c).
- Keyword polarity overrides (P9).
- R project import and the Standard Entry workbook.
