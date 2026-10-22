# P1b — Response register, indicator fields, stakeholder roles (schema v8)

**Status:** design, approved by the user 2026-10-21; amended in plan review rounds 1–2 (2026-10-21/22) · **Date:** 2026-10-21
**Roadmap:** `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md` §2 P1b
(branch `docs/r-parity-roadmap`). P0, P1a (v1.13.0) and P2 (v1.14.0) are shipped;
SESPy main is v1.14.2 (`c7fde7f`).
**R reference:** MarineSABRES_SES_Shiny **v1.33.0 (`4017feb`)**, the version laguna
runs (verified 2026-10-20). The 9 files pinned since P2 are identical between
v1.31.0 and v1.33.0 (`git diff --quiet v1.31.0 v1.33.0 -- <9 paths>` exits 0).
R source releases ported: 1.19.0, 1.23.0 (WS-3a), 1.24.0 (WS-4 fields only),
1.29.0 (`PestleTag`), 1.30.0 (WS-9a: `Policy_Target`, stakeholder roles,
duplicate-row fix `33ddd96`/`7914203`), 1.32.0 (`TenetSource`, tenet-level
validation).
**Target release:** SESPy **v1.15.0**, project schema **8**.

## 1. Purpose and success

SESPy users can keep R's Response register (the measures a case study proposes,
their impacts, milestones and appraisal), record indicators on DAPSIWRM
elements, describe connections, and tag stakeholders with the D5.4 actor
roles, and all of it survives save → load. This is the data foundation P1c
(R project import), P4 (governance profiles, indicator picker) and P6a
(impact assessment) build on.

**Done when:**
1. A project with a register (measures with every one of R's 34 columns,
   impacts, milestones), indicator fields on elements, connection
   descriptions and stakeholder roles round-trips through the real upload path
   (`project_to_bytes` → `json.loads` → `validate_project_payload` valid →
   `Project.from_dict`) with every value equal.
2. The Python normaliser reproduces R's `normalize_response_measures` on a
   fixture table of inputs (label → code for all 9 languages, PESTLE ordering
   and dedupe, tenet-level blanking, `Cost` coercion, unknown columns dropped)
   and R's `normalize_stakeholders` `NERoles` cleaning.
3. Measure and stakeholder IDs follow R's `safe_counter` rule (§4.2.3, §4.4) on
   fixtures including a loaded project whose counter is missing or too low, and
   a deleted ID is not handed out again.
4. The Response Register page, the ISA edit panel and the stakeholder roles
   field work end to end (e2e scripts below).
5. The full unit and e2e gates pass, and MosaicSES's unit suite and full e2e
   pass against the branch before merge.

## 2. Roadmap amendments (made by this spec)

- **Node M is already shipped** (MosaicSES v0.4.0, 2026-10-18; live as 0.4.1).
  P1b has no MosaicSES prerequisite. The roadmap's M line refs are stale:
  warning and download are now `multises_app/modules/project_setup.py:299-351`,
  open registration `:371`, recent re-open `recent_projects.py:193`. M's tests
  read `SCHEMA_MIN_READER[PROJECT_SCHEMA_VERSION]` dynamically, so the v8 bump
  leaves them valid.
- **Baseline re-pinned to R v1.33.0 (`4017feb`)**; triage of v1.31.0 → v1.33.0 in §9.
- **"Load DA actor list"** moves to P4 (§8, user decision); the 1.32.x WS-10
  workshop gets a new owner (§9).
- **The roadmap's two P1b decisions** are made in §5.
- **The Response Register page moves from P4 to P1b**: R `response_module.R`
  tabs 1–5, minus the bandit suggestion, the Word exports, the WP5 mechanism tab
  and the D5.4 governance-context tab. P4 keeps the mechanism pane, the
  governance-context tab (its "Add to register" writes through P1b's
  `add_measure`), the indicator picker and "Load DA actor list".
- **`metadata.r_min_app_version` moves to P1c** (*my call*). Only an R import
  writes it (R's top-level `min_app_version`, for import diagnostics), and P1c
  bumps the schema anyway. P1b ships `min_sespy_version` only.
- **The roadmap's `33ddd96` check** (one stakeholder row per add, safe id
  counter; R_SYNC.md check item) is closed by §4.4: SESPy adds one row per
  click, and stakeholder IDs now come from R's persisted counter.

## 3. Non-goals

- The WP5 indicator **registry picker**, registry snapshot and drift check (R
  `indicator_registry.R`, `wp5_indicators.json`). They need the K1 runtime
  reference-data loader; the roadmap assigns the picker to P4. P1b adds the six
  fields only; `Registry_Id`/`Registry_Version` are stored and shown read-only.
- R's WP5 mechanism reference tab and D5.4 governance-context tab of the
  response page (P4 / mechanism sub-project).
- The WS-10 workshop page that writes `TenetSource` (§9). P1b stores and shows
  `TenetSource`; nothing in SESPy writes it yet except load and import.
- R's LinUCB "bandit" suggestion (ML; roadmap §4 excludes it).
- R's Word "priority report" / "implementation plan" exports (*my call*: they
  belong with the shared report pipeline, P6c/P14). P1b exports Excel only.
- Importing R projects or R registers (P1c). Writing R-format JSON (roadmap §4).
- Changing SESPy-only features.

## 4. Data model (schema v8)

### 4.1 Schema bump
- `PROJECT_SCHEMA_VERSION = 8`, `SCHEMA_MIN_READER[8] = "1.15.0"`. The **first
  commit** of the branch sets `__version__`, `pyproject.toml` and the
  `docs/MANUAL.md` version line to 1.15.0 together with the schema number and
  the min-reader entry (roadmap §3; `tests/test_schema_v7.py:60` fails
  otherwise).
- Every saved file is stamped `min_sespy_version >= "1.15.0"`, including files
  with no P1b data, because the floor is keyed on the schema number
  (`_min_reader_stamp`). This is intended: a v1.14 reader would silently drop
  the new stakeholder fields, which are always serialised (4.4).
- Tests that pin the number are updated: `tests/test_data_structure.py:17`,
  `tests/test_schema_v7.py:279-280` (the "newer file" becomes
  `PROJECT_SCHEMA_VERSION + 1`), `tests/test_schema_v7.py:231-238` (the two
  stamp tests compare with the floor, not "1.13.0"),
  `tests/test_r_template_catalogue.py:202`.
  `tests/test_schema_v7.py:57` (`SCHEMA_MIN_READER[7] == "1.13.0"`) stays: the
  v7 entry is kept. The first commit also regenerates the 7 shipped templates
  from the committed fixtures (`--from-fixtures`), so every commit is green.
- A v7 file loads as before (missing blocks default). A newer file still trips
  P0b's guard.

### 4.2 Response register block
`Project.response_measures: ResponseRegister`, kw_only, default empty, carried
by `Project.replace()`. Serialised as a top-level `response_measures` key
**only when non-empty** (any table has rows, or `counter > 0`).

```
ResponseRegister:
  measures:   list[dict[str, str | float | None]]   # R column names, §4.2.1
  impacts:    list[dict[str, str]]                   # §4.2.2
  milestones: list[dict[str, str]]                   # §4.2.2
  counter:    int = 0
```
Rows are plain dicts keyed by **R's column names** (roadmap: "Measures use R's
column names"), so P1c can import R rows with no renaming and the normaliser
mirrors R line by line. JSON is row-wise (an array of objects), as R's
`jsonlite::toJSON` writes a data.frame.

#### 4.2.1 Measures (`RM_REGISTER_COLUMNS`, `constants.R:831-840`)
34 columns in this order: `ID, Name, Type, Target, Description, Mechanism,
TargetElement, Effectiveness, Feasibility, Cost, Status, Stakeholders,
Barriers, DateAdded, Kind, EbmCode, GovernanceLevel, CompetentAuthority,
LegalBasis, ImplementingStakeholders, PairedWith, PestleTag`, the 11
`Tenet_<code>` columns (`ecol_effective, tech_feasible, econ_efficient,
econ_viable, socially_desirable, ethically_defensible, culturally_inclusive,
legally_permissible, admin_achievable, communicable, politically_expedient`),
`TenetSource`. All strings ("" default) except `Cost`: float or `None` (R
`NA_real_`).

Code lists, ported verbatim from `constants.R` v1.33.0 into
`sespy/response_register.py` (stored value = code):
- `RM_TYPE_CODES`: regulatory, economic, educational, technical, institutional,
  voluntary, mixed.
- `RM_TARGET_CODES`: drivers, activities, pressures, state, multiple (label key
  `multiple_levels`).
- `RM_STATUS_CODES`: proposed, planned, implemented, partially_implemented,
  abandoned.
- `GOVERNANCE_LEVELS` (7): local, island, regional, national, eu, regional_sea,
  international.
- `TENET_LEVELS`: minimal, intermediate, full; `intermediate` only for
  `ecol_effective`.
- `PESTLE_CODES` (this order everywhere): political, economic, social,
  technological, legal, environmental.
- Kind: instrument | measure. EbmCode: `EBM_POLICY_INSTRUMENTS` "type"-level
  codes for instruments (1.1–1.6, 2.1–2.5, 3.1–3.4, 3.6, 3.7, 4.1–4.3; there is
  no 3.5) and all 12 `EBM_MANAGEMENT_MEASURES` codes for measures, with each
  measure code's `dapsiwrm_target` (`suggest_rm_target`: A → activities,
  P → pressures, C → state, A|P|C → multiple).
- Effectiveness HIGH/MEDIUM/LOW/UNKNOWN/""; Feasibility HIGH/MEDIUM/LOW/"".
  Not validated (R passes any string).

`normalize_measures(rows)` ports `normalize_response_measures`
(`response_measures_schema.R:49-107`) step for step: key-union build over
ragged rows; exactly the 34 columns in order (unknown columns dropped, missing
→ "" / `None`); `Cost` → float or `None`; list values joined with ";"; label →
code for Type/Target/Status through a reverse map built from **all 9
languages** of the vendored R translations (R `rm_reverse_label_map`; note the
English `activities` label is literally "Activities:"), values that are neither
codes nor labels pass through; `PestleTag` split/trim/drop-unknown/re-order;
tenet values `lower().strip()`, blanked when not allowed. Idempotent. It runs
on load and on every write.

#### 4.2.2 Impacts and milestones
- Impacts: `ResponseID, ProblemType, ProblemElementID, ImpactStrength,
  Timeframe`. Milestones: `ResponseID, Milestone, TargetDate, Status, Notes`.
- **Deviation from R (*my call*):** R stores the *translated label* in
  `ProblemType`, `ImpactStrength`, `Timeframe` and milestone `Status`, so the
  value depends on the UI language at entry time. SESPy stores codes:
  ProblemType `specific_pressure|specific_activity|specific_driver|system_wide_issue`,
  ImpactStrength `strong|moderate|weak`, Timeframe
  `immediate|short_term_1_3y|medium_term_3_10y|long_term_10y`, Status
  `pending|in_progress|completed|delayed`. Every code is exactly R's i18n key
  suffix under `modules.response.measures.` (`response_module.R:208-224,340`),
  so code → label is the key lookup, with no extra table. The normaliser maps any
  9-language label to its code the same way as Type/Target/Status, so P1c's
  importer gets R's labels mapped for free.

#### 4.2.3 IDs and counter (R parity, not SESPy's `next_id`)
New measure ID = `"RM%03d" % n` where
`n = max(counter, largest numeric suffix of existing "RM…" IDs) + 1` (suffixes
read as R's `as.numeric` reads them: `RM1e2` → 100)
(R `safe_counter` + `next_element_id`); `counter` is then set to `n`. Deleting
never lowers `counter`, so IDs are not reused while the counter survives. One
ID per add (the `33ddd96` bug cannot occur). On load the stored `counter` is
kept as it is (a non-numeric value → 0 with a log line); `safe_counter` applies
only when a measure is added (R `response_module.R:494-509`). Stakeholder IDs
follow the same rule (§4.4). Element IDs keep SESPy's gap-filling `next_id`
(a SESPy design, `tests/test_utils.py`); the ISA page warns when a deleted
element is still referenced by the register (§6.2).

### 4.3 Element indicator fields
Six kw_only `str` fields on `Element`, default "": `indicator,
indicator_unit, data_source, registry_id, registry_version, policy_target`
(R's `ISA_INDICATOR_COLUMNS`, in the lowercase form R's loader produces).
Serialised by `_element_to_dict` **only when non-empty**, so a project without
indicators has the v7 element shape. `_isa_from_dict` picks them up through
`fields(Element)`; non-str values → `str()` with a log line, `None` → ""
silently (as `Connection.description`).
- **Saved projects (*my call*):** on load, a non-empty string
  `r_extra["indicator"]` moves into `Element.indicator` when that field is
  empty and is removed from `r_extra` (one log line per project), so projects
  saved from the v1.14.x Caribbean template get the field like a fresh
  conversion (§5(b)). `baseline` stays in `r_extra`.
- Responses: the fields are **hidden in the UI only** (R `isa_form_builders.R:74-86`).
  Load and validation keep whatever a file carries on a Responses element and
  log nothing (R behaves the same).
- `policy_target`: one of `kmgbf_30x30, eu_nrr, msfd_ges_d1, msfd_ges_d6,
  national_mpa_pct` (`WP5_POLICY_TARGETS`) **or free text**.

### 4.4 Stakeholder roles
`Stakeholder` gains `ne_roles: str = ""` and `source_id: str = ""` (kw_only).
`ne_roles` is a ";"-joined, ordered, deduplicated subset of
`STAKEHOLDER_TYPES` = Inputters, Extractors, Regulators, Affectees,
Beneficiaries, Influencers (capitalised codes, as R stores them); unknown
values are dropped with a log line (`normalize_stakeholders`,
`stakeholder_schema.R:30-37`). The Python name is `STAKEHOLDER_ROLES` (R
`STAKEHOLDER_TYPES`; SESPy already has an unrelated `stakeholder_type`).
`source_id` (`d54:<actor id>`) is never user-entered;
P1b only stores it (it is written by the actor-list loader, §8) and loads it
tolerantly like the indicator fields. `Stakeholder`
is serialised with `asdict`, so both keys are always written (an exception to
P1a's explicit-serialisation rule, kept because a v1.14 reader filters unknown
stakeholder keys).
- **Stakeholder IDs (R parity, *my call*):** `Project.stakeholder_counter: int`
  (kw_only, default 0) is R's `pims$stakeholder_counter`. Adding a stakeholder
  allocates `SH%03d` from `safe_counter(stakeholder_counter, ids, "SH") + 1`
  and stores the new counter (`pims_stakeholder_module.R:458-460`); it is
  written as a top-level key only when > 0. A deleted stakeholder's ID is
  therefore never handed to a new stakeholder, so a measure's
  `ImplementingStakeholders` cannot silently start naming someone else. P1c
  maps R's `pims.stakeholder_counter`. Engagement and communication IDs keep
  `next_id` (nothing refers to them).
- **Projects saved before v1.15 (*my call*):** they carry no counter, so it
  loads as 0. Deleting a stakeholder therefore also raises the counter to cover
  the IDs present before the removal; otherwise deleting the highest ID before
  any add would hand it out again. R files always carry the counter, so this
  guard is SESPy-only and changes nothing for them.

### 4.5 Connection description
`Connection.description` already exists (P1a) with no UI. P1b adds the UI only;
no data change.

## 5. The roadmap's two decisions

**(a) Template "measures" are not promoted into the register.** R itself never
does it: `template_loader.R:186-189` folds a template's `measures` into the ISA
Responses (`all_responses <- c(responses_list, measures_list)`), and nothing in
R writes template measures into `response_measures`. SESPy keeps the 11
`r_kind == "measure"` Responses elements as they are.

**(b) `r_extra["indicator"]` moves into `Element.indicator`; `baseline` stays in
`r_extra`.** Only Caribbean carries them: its 10 marine-process elements S1–S10
(not Responses, so the field is allowed). The mapper
(`sespy/r_template_mapper.py:112-117`) maps the R key `indicator` to the field
instead of `r_extra`. `baseline` has no field in R's `ISA_INDICATOR_COLUMNS`
(R's legacy `baseline_value` column is unrelated), so it stays in `r_extra`.
Chain: the commit that changes the conversion regenerates the shipped templates
with `python -m scripts.sync_r_templates --from-fixtures` (the schema bump
rewrites all 7, the mapper change rewrites Caribbean); the re-pin then also
moves `catalogue.json`'s `r_tag`/`r_commit` to v1.33.0 / `4017feb`, and
`tests/test_r_template_catalogue.py:202` moves to "1.15.0" with the bump.
`ConversionReport.extra_fields` no longer lists `indicator`. Projects already
saved with `r_extra["indicator"]` are hoisted on load (§4.3).

**(c) Excel import (*my call*).** `excel_import.py:29` uses an "Indicator"
column as the element *description* fallback. From v1.15.0 an
`Indicator`/`indicator` column fills `Element.indicator`, and the description
comes only from `Description`/`description`. The other five R column names
(`Indicator_Unit`, `Data_Source`, `Registry_Id`, `Registry_Version`,
`Policy_Target`) are read as well; all six headers match case-insensitively.
CHANGELOG notes the behaviour change.

## 6. UI

Read the matching Shiny skill references before UI work (`modules-core.md`,
`reactivity.md`, `data-frames.md`, `testing.md`; project CLAUDE.md).

### 6.1 Response Register page (new)
New module `sespy/modules/response_register.py` + pure helpers in
`sespy/response_register.py`. A `NavItem(id="responses", label_key="nav.responses")`
placed directly after **Edit Data** (*my call*), stepper stage "create", and a
`## N. Response Register` section in `docs/MANUAL.md` (required by
`tests/test_help_offcanvas.py`; later sections renumber). Four tabs, following
R's tabs 1–5:

1. **Register.** Add form with R's fields (`response_module.R:28-190`): name
   and type required; target, status (default proposed, no blank choice), description,
   mechanism, target element, effectiveness, feasibility, cost (1–10, default 5),
   responsible stakeholders, barriers; a collapsible "EBM classification and
   governance" section with kind, EBM code (choices follow kind; picking a
   measure code suggests target), governance level, competent authority, legal
   basis, paired with (select of existing "ID - Name", R's hyphen), implementing
   stakeholders (multi-select of the project's PIMS stakeholders, stored as
   ";"-joined IDs), PESTLE (multi), and the 11 tenet selects. `TenetSource` is
   shown read-only when set. Table: R's 15 `RM_DISPLAY_COLUMNS`, with R's column
   names as headers (untranslated, as R's DT table) and translated values as R's
   `rm_display_label` (`response_measures_schema.R:146-157`): a blank value
   shows "" in every column ("Not assessed" is only the label of a tenet
   select's empty choice), an EBM code shows its vocabulary label without the
   code (only the instrument picker prefixes the code).
   Row selection → **Edit** (repopulates the form; *my call*: R has add/delete
   only, SESPy's stakeholder page has edit and R's register API has `update`)
   and **Delete** (multi-select; counter unchanged).
   **Edit keeps every stored value:** a select whose stored value is not one of
   its choices (a hand-typed Type, an unvalidated Effectiveness, a dangling
   `PairedWith` or `ImplementingStakeholders` ID) gets that value as an extra
   choice shown raw, so saving never rewrites data the user did not touch.
   Two more rules serve the same promise (*my call*; R has no Edit):
   - Filling the form for Edit must not trigger R's follow-up rules, which
     clear the EBM code when Kind changes and replace Target with the EBM
     code's suggestion. Those rules run only on the user's own change of Kind
     or EBM code.
   - When a picker's choices refresh because the project changed (a
     stakeholder added on the PIMS page), the user's current picks are kept.
   **Stale edits are refused (*my call*):** Edit remembers the record it
   opened; if the project was replaced or the record changed before Save (a
   project load, a MosaicSES compartment switch), Save writes nothing and says
   why. After a successful add the page shows R's "Response measure added!".
   `TargetElement` is a **select of the project's non-Response element IDs**
   rather than R's free text (*my call*; it stores the same ";"-joined ID
   string, and IDs not in the project are kept and shown).
2. **Impacts.** R's tab 2: measure, problem type, element (select, as above),
   strength, timeframe; table with delete (*my call*: R has no delete). R's
   heatmap, its "Priority ranking" summary and its "Cost vs expected impact"
   plot have no renderer in R and are not ported.
3. **Prioritisation.** Weights (effectiveness 0.4, feasibility 0.3, cost 0.3),
   R's score `w_e*Eff/3 + w_f*Feas/3 + w_c*(11-Cost)/10` with HIGH 3 / MEDIUM 2 /
   LOW 1 / else 0, ranked table (R's columns minus BanditSuggestion,
   `PriorityScore` rounded to 3 places), and R's effectiveness-vs-feasibility
   plot (`response_module.R:796-837`): only measures whose Effectiveness and
   Feasibility are both HIGH/MEDIUM/LOW are drawn, x = feasibility,
   y = effectiveness, axes 0.5–3.5 with Low/Medium/High ticks, dashed lines at
   2, the four quadrant labels, points labelled by ID; with no rated measure an
   empty plot titled "Add effectiveness and feasibility ratings".
   Unit tests reproduce R's scores on a fixture.
4. **Milestones and export.** R's tab 4 form (measure, milestone, target date
   default today + 365, status, notes), table with delete; an **Excel download**
   with R's three sheets `Response_Measures` (all 34 columns, values translated
   as R's `rm_translate_for_display`), `Impact_Matrix`, `Implementation`
   (openpyxl, as `stakeholder_reports.py`). R exports impacts and milestones as
   stored, i.e. as labels; SESPy stores codes (§4.2.2), so it translates
   ProblemType, ImpactStrength, Timeframe and Status on export to produce R's
   output.

**Deletes do not cascade (R parity, *my call*).** R's delete
(`response_module.R:650-653`) drops only the measure rows. Impacts and
milestones whose `ResponseID` is gone, a `PairedWith` that points at a deleted
measure, and `ImplementingStakeholders` IDs of stakeholders deleted on the
PIMS page are all kept and shown as the raw ID (a stakeholder ID is never
handed out again, §4.4). The delete toast is R's "deleted" message, followed,
when any remain, by how many impact and milestone rows still reference the
deleted measures. Element deletion on the ISA page does not touch
`TargetElement`/`ProblemElementID` either; because element IDs can be reused
(§4.2.3), it warns, naming the measures that still reference the element.

The page writes through `project_data.set(project.replace(response_measures=…))`
and emits the change event like the stakeholder page, so autosave picks it up.
The page is empty-state friendly (no stakeholders → hint, as R).

### 6.2 ISA entry edit panel
`sespy/modules/isa_data_entry.py` has no editing today. Add, below each table,
an edit panel bound to the selected row (stakeholder-page pattern:
`editing_id` + `_repopulate` on `@reactive.event(editing_id)` only):
- **Element:** label, description, and (non-Responses only) indicator, unit,
  data source, policy target (selectize, 5 codes + free text; a stored free
  text is offered as a choice so it survives Edit), and registry id/version
  shown read-only when present. Labels use R's
  `modules.indicator_registry.field_*` keys.
- **Connection:** description.
Save goes through the existing `_replace(isa)` path, and is refused like the
register's when the project was replaced or the record changed since Edit
(MosaicSES compartments repeat element IDs). Deleting an element that
the register references warns (§6.1). MosaicSES compartments
reuse `isa_data_entry_server`, so the panel appears there too (§10).

### 6.3 Stakeholder roles
`pims_stakeholders.py`: a "Roles (D5.4 actor typology)" multi-select in the
register form (add and edit), and a Roles column in the table (translated
labels, ", "-joined). `source_id` is never shown in the UI (R hides it).
The xlsx export (`stakeholder_reports.py`) writes every `Stakeholder` field, so
its Stakeholders sheet gains `ne_roles` (codes, ";"-joined) and `source_id`
columns: they are data, as in R's register (*my call*). Adding a stakeholder
adds exactly one row and takes its ID from the counter (§4.4).

## 7. i18n
Strings with an R counterpart **adopt R's keys and R's text in all 9
languages**, vendored as a key subset into
`sespy/translations/modules/{response_measures,response_governance,wp5_vocabulary,wp5_scenarios,wp5_governance,indicator_registry}.json`
(the loader already merges sub-directories). The subset **must include every
`modules.response.measures.<code>` key used by the Type, Target, Status,
impact and milestone vocabularies**; at v1.33.0 they all live in
`response_measures.json`, which is what makes the 9-language reverse map
complete (a test checks every code has a label in every language). A small sync helper copies the
listed keys from the R fixture files (§9) so re-pinning is mechanical; a test
asserts each vendored string equals the fixture's. SESPy-only strings (nav
label, edit-panel labels, the TargetElement hint) go in `core.json`. A
`test_p1b_keys_present` test covers both.
- Six form labels that R takes from `common.labels.*` (response name, response
  type, implementation status, description, target date, status) live in
  `translations/common/labels.json`, which is not vendored. `core.json` holds
  them as `responses.*` keys with R's text in all 9 languages, copied from that
  file at v1.33.0 (*my call*: vendoring a whole common file for six keys is
  out of proportion).
- Table headers are R's column names, untranslated, as in R's DT tables.

## 8. "Load DA actor list" moves to P4 (decided by the user, 2026-10-21)
The roadmap listed it under P1b (stakeholder roles bullet) but put its data
file, `wp5_governance_profiles.json` (88 KB, 89 actors, 3 DAs), on **P4's**
allow-list for the K1 runtime loader. The user moved the button to **P4**,
where the file, its loader and the D5.4 governance context land together. P1b
ships the `ne_roles`/`source_id` fields it writes. The roadmap's P1b and P4
sections are amended accordingly.

## 9. R sync

- **Pin** moves to v1.33.0 (`4017feb`) via `scripts.sync_r_templates`; the 9
  existing files are unchanged. New **fixtures** (hashed, never shipped):
  `tests/parity/r_source/{constants.R, response_measures_schema.R,
  stakeholder_schema.R}` (code lists and normalisers are test-checked against
  them: a parity test extracts each ported vector from `constants.R`) and the 6
  translation JSONs of §7 under `tests/parity/r_translations/`.
- **Triage of v1.31.0 → v1.33.0** into `docs/parity/R_SYNC.md`, one row per
  path of `git diff --name-status v1.31.0 v1.33.0` (71 paths), as R_SYNC.md's
  procedure requires. The table below summarises the owners:

| R change | Owner |
|---|---|
| `RM_REGISTER_COLUMNS` + `TenetSource`; tenet validation (`response_measures_schema.R`); register `update` API; `modules/response_module.R` register tabs | **P1b** (the governance-context tab: P4) |
| WS-10 workshop elicitation (1.32.0–1.32.4: `wp5_workshop.R`, `wp5_workshop_module.R`, `wp5_tenet_guiding_questions.json` and its test, the sidebar entry, workshops block + 1.32.0 stamp) | **new sub-project, proposed P15** (after P4; it writes `TenetSource`) |
| `repair_template_connection_matrices` (1.33.0, AI-template matrices) | not relevant (R-only matrix storage; SESPy templates are edge lists) |
| AI assistant template fixes (`modules/ai_isa/*`, 1.33.0) | P13 / AI wizard parity, re-check then |
| Report sections, plot downloads (`report_generation.R`, `prepare_report_module.R`, `export_reports_module.R`) | P14 / P6c |
| Decision lens (`analysis_decision_lens.R`) | P3 |
| Scenario builder and network (`scenario_builder_module.R`, `scenario_network.R`) | P8 |
| User-level project test (`test-user-level-keeps-project.R`) | P12 |
| Template-links toast (`server/project_io.R`) | P13 |
| `translations/modules/isa_data_entry.json`, `server/modals.R`, `translations/common/{buttons,messages}.json` | inspected per path in the R_SYNC.md table (owner per change) |
| Loop plots, simplify, leverage fixes | not relevant now; re-triage when the owning analysis is ported |
| `country_governance_db.json` | K1 (re-check counts at K1's pin) |
| `wp5_readiness.R` | P4 |
| `entry_point_module.R`, sidebar | P11 |
| feedback analyzer, `.claude/`, CI | not relevant |

## 10. MosaicSES
- Before merge: MosaicSES unit suite and **full** e2e against the P1b branch
  (PYTHONPATH to the worktree; the env's editable sespy points elsewhere).
- Check: the new ISA edit panel's ids are namespaced, so no cross-panel
  selector collision with MosaicSES panels (all panels share one DOM). Checked
  2026-10-21: MosaicSES's pattern selectors (`[id$=`, `[id^=`) match no new id;
  the gate re-greps before merge.
- `Project(...)` constructions at `multises_app/state.py:131` and
  `multises/archetypes.py:100` rely on the new fields' defaults; `materialise`
  uses `dataclasses.replace`, which carries `response_measures`.
- After deploy: MosaicSES `deploy/verify_live.py` (it runs on the deployed
  SESPy through its symlink).

## 11. Testing and release
- **Where expected values come from (*my call*):** derived by hand from the
  pinned R source and R's own testthat cases
  (`tests/testthat/test-response-measures-schema.R`,
  `test-response-module.R`, `test-pims-stakeholder-module.R` at v1.33.0); each
  expected value cites its R file:line. No `Rscript` step: R is not in the
  `shiny` environment, and the fixtures are pinned so the source cannot drift
  silently. The testthat files are not fixtures, so their citations name the
  v1.33.0 commit (`4017feb`).
- Unit: register normaliser and reverse map (9 languages), ID allocation
  (measures and stakeholders), prioritisation scores, v8 round trip incl. all
  34 columns, omit-when-empty, v7 file load, Element indicator fields,
  Responses hiding (UI) vs keep (load), the load-time `indicator` hoist,
  stakeholder roles normalisation, mapper `indicator` hoist, Excel import
  columns, parity tests against the R fixtures.
- Module (`shiny.testing`/server tests): register add/edit/delete, counter,
  values outside a select's choices kept through Edit; ISA edit panel saves
  description/indicators; stakeholder roles, one row per add.
- e2e: `test_response_register_e2e.py` (add two measures → IDs RM001/RM002,
  edit one, add an impact and a milestone, download Excel), an ISA edit e2e,
  a roles e2e step in the stakeholder e2e. Scoped, namespaced selectors; full
  e2e gate with nothing heavy running alongside.
- Docs: CHANGELOG (names P1b and R v1.33.0), MANUAL section + version line,
  screenshots for the affected pages (`tests/make_docs_screenshots.py`).
- Release: v1.15.0 tag, deploy, laguna verify (worker python `-s`), MosaicSES
  `verify_live.py`.

## 12. Left to the builder
Module and helper layout beyond what is named; exact plot library (matplotlib
via `render.plot`, as elsewhere); table widget details; how the sync helper is
structured; task order after Task 1 (version + schema).
