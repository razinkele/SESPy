# K1b: SESPy's side of the connection scorer at v1.16.0

Checkout: the SESPy repository at tag `v1.16.0`.
All paths below are relative to that root unless they start with `R:` (R app at
`...\SESToolbox\MarineSABRES_SES_Shiny`, `git describe` = `v1.35.6`) or `MosaicSES:`
(`...\Marine-SABRES\MosaicSES`, HEAD `1b71423`, `v0.8.3-7-g1b71423`).
Ignore `build/lib/sespy/*`: it is a stale copy and is never cited here.

Terms. SP1 to SP4 are the four sub-projects of the AI-ISA wizard
(`docs/superpowers/specs/2026-05-03-ai-isa-wizard-sp3-design.md:3-4`):
- SP1: the wizard skeleton plus a stub `suggest_connections` that returns `[]`.
- SP2: the regional-seas KB.
- **SP3: the rule-based connection scorer** (`sespy/connection_scorer.py`).
- **SP4: the optional Claude API backend** (`sespy/claude_backend.py`).

In the code, "SP3" and "SP4" name the two suggestion sources and their tables
(`accept_sp3_*` and `accept_sp4_*`). "SP4 merge" means `_dedup_accepted` run
over the rows accepted from both tables.

---

## 1. `sespy/connection_scorer.py` (396 lines)

### 1.1 Module setup
- Docstring: the module is the SP3 port of R `connection_generator.R` "with
  KB-lookup and ML branches dropped per scope" (`:1-12`).
- Imports `_CONN_TYPES`, `ELEMENT_TYPE_MAP`, `ConnectionSuggestion`, `Element`
  and `WizardState` from `data_structure` (`:21-27`). It must never import
  `wizard`, which an AST test enforces (`tests/test_connection_scorer.py:596`).
- Loads `sespy/connection_keywords.json` eagerly at import (`:29-39`). The file
  has two sections:
  - `connection_types`: **10** keys (D_A, A_P, P_S, S_I, I_W, R_P, R_D, R_A,
    W_D, W_R), with no `responses_states` key.
  - `polarity_signals`: `negative_keywords`, `positive_keywords`,
    `mitigation_keywords` and `loss_keywords`.
  - `loss_keywords` equals R's inline list at `R:connection_generator.R:440-444`
    (checked).
- `_TYPE_TO_SLUG` inverts `ELEMENT_TYPE_MAP` (`:40`).
- Constants: `_MAX_PER_TYPE = 15` and `_MIN_RELEVANCE = 0.3` (`:45-46`).
- Regex lists are inline: `_REVERSAL_COMPOUNDS` (`:52-56`, bare `X.*Y` stems)
  and `_NEGATION_PATTERNS` (`:60-64`, with `\b`).

### 1.2 Relevance: `calculate_relevance(from_name, to_name, from_slug, to_slug)` (`:67-103`)
This ports only R's `.calculate_basic_relevance` (`R:338-387`). R's real
`calculate_relevance` (`R:264-323`) calls `calculate_enhanced_relevance`
first (KB + TF-IDF) and only falls back to the basic version (`R:266-283`).
SESPy skips that step.

1. The key is `f"{from_slug}_{to_slug}"`. When the keyword JSON has no entry
   for it, the function **returns 0.5** (`:84-87`). That is always the case for
   `responses_states`.
2. It counts keywords found in each lowercased name with
   `re.search(re.escape(kw), …)` (a substring match), then sums the two
   counts (`:89-97`).
3. Score:
   - 0 matches gives **0.3**
   - 1 match gives **0.6**
   - 2 or more gives **0.9**

   (`:99-103`)

So the only values ever emitted are {0.3, 0.5, 0.6, 0.9}. A test pins the
set {0.3, 0.6, 0.9} for D/A/P input (`tests/test_connection_scorer.py:443-459`).

### 1.3 Polarity: `detect_polarity` (`:143-250`) and `_analyze_polarity_phrase` (`:106-140`)
- `_analyze_polarity_phrase` returns:
  - `("positive", True)` on a reversal compound;
  - `("neutral", True)` on a negation pattern;
  - `("neutral", False)` otherwise.

  It never returns "negative" (`:110-114`, `:131-140`).
- **Step A** (`:171-190`) computes these flags by substring match:
  `from/to_is_negative`, `from/to_is_positive` and `from_is_mitigation`. It
  also runs a phrase analysis on each name.
- **Step B** dispatches on the slug pair:

| Pair | Rule | Lines |
|---|---|---|
| R→P | always `-` | `:194-195` |
| R→S | to-negative `-`; to-positive `+`; default `+` | `:198-203` |
| A→P | mitigation or reversal-positive `-`; else `+` | `:206-209` |
| P→S | to-negative `+`; to-positive `-`; default `-` | `:212-217` |
| S→I | negation clears negative flags only; same sign `+`, opposite sign `-`, default `-` | `:220-235` |
| I→W | from-side only; negation clears from-negative; negative `-`, positive `+`, default `-` | `:238-247` |
| all others (D→A, R→D, R→A, W→D, W→R) | `+` | `:250` |

- R's KB-lookup branch at the top of `detect_polarity` (`R:63-75`) is **not
  ported** (docstring `:166-169`). K1b ports `lookup_knowledge_base` and
  `analyze_phrase_polarity` here; see the spec at
  `docs/superpowers/specs/2026-11-09-k1-knowledge-base-parity-design.md:1308-1310`.

### 1.4 Verb and rationale: `_select_verb` (`:253-285`)
Verbs per source type, matching `R:513-529`:

| Source type | `+` | `-` |
|---|---|---|
| drivers | drives | drives |
| activities | increases | causes |
| pressures | increases | decreases |
| states | impacts | impacts |
| impacts | increases | reduces |
| responses | enables | restricts |
| welfare | motivates | reduces |

The rationale is `f"{from.label} {verb} {to.label}"` (`:348`).

### 1.5 Per-pair generator: `_generate_smart_connections` (`:288-353`)
For each pair in the cross product, in `from` × `to` order (`:317-318`):
1. Compute relevance (`:319-321`).
2. Drop the pair if relevance `< min_relevance` (`:324`). This never fires,
   because the floor is 0.3.
3. **Double-negative filter**: drop the pair if both labels match
   `loss_keywords` (`:328-337`).
4. Compute polarity and verb (`:339-342`).
5. Build `ConnectionSuggestion(source=id, target=id, polarity,
   confidence=relevance, rationale)` (`:343-349`).

Then sort with `candidates.sort(key=confidence, reverse=True)`. The sort is
stable, so ties keep cross-product order (`:352`). Finally cap at 15 (`:353`).

- R sorts by `order(sapply(relevance), decreasing=TRUE)` (`R:556`), which
  is also stable for ties.
- R does not sort on `confidence`: R's `confidence` is the integer 3 or 4
  (`R:469`, `R:482-486`). SESPy puts the 0..1 relevance in the field called
  `confidence`.
- R's per-candidate `strength` (`"medium"`, or `kb_match$strength`, `R:468`,
  `R:480`), `delay` and `scoring_method` (`R:470-471`, `R:540-545`) have no
  SESPy equivalent.

### 1.6 Orchestrator: `suggest_connections(state: WizardState) -> list[ConnectionSuggestion]` (`:356-396`)
1. Group `state.elements` by `_TYPE_TO_SLUG[el.type]`. An unknown type logs a
   warning and is skipped (`:369-380`).
2. Loop over **`_CONN_TYPES`**, the shared 11-pair list
   (`sespy/data_structure.py:77-89`). Skip a pair when either side is empty
   (`:387-391`).
3. Concatenate the results (`:392-396`).

Output: a flat `list[ConnectionSuggestion]` of at most 165 rows (11 × 15),
grouped in `_CONN_TYPES` order, with confidence descending inside each group.
There is no global sort and no dedup. The signature takes **no snapshot
argument**. Tests call it bare (`suggest_connections(state)`), and so do the
wizard (`sespy/modules/ai_isa_wizard.py:1090`) and `sespy/wizard.py:86`.

### 1.7 Pair order: SESPy vs R

| # | SESPy `_CONN_TYPES` (`data_structure.py:77-89`) | R wizard path (`R:923-990`) |
|---|---|---|
| 1 | D→A | D→A (d_a) |
| 2 | A→P | A→P |
| 3 | P→S | P→S (p_mpf) |
| 4 | S→I | S→I (mpf_es) |
| 5 | I→W | I→W (es_gb) |
| 6 | R→P | R→P |
| 7 | **R→D** | **W→D** (gb_d) |
| 8 | **R→A** | **W→R** (gb_r) |
| 9 | **R→S** (extra) | R→D |
| 10 | W→D | R→A |
| 11 | W→R | — |

K1b drops R→S and moves W→D and W→R ahead of R→D and R→A (spec `:1320-1321`).
R's comment on the counters, "10 types x 15 = max 150" (`R:757`), confirms 10.

R's KB-seed block (`R:803-919`) maps 14 type keys, including
`responses_states` and `r_r`/`p_p`/`s_s` (`R:831-839`). **It is dead in the
wizard**: it runs only when `regional_sea` and `habitat` are non-NULL
(`R:812-814`), and R's wizard calls `generate_connections(rv$elements)` with
neither (`R:modules/ai_isa/step_navigation.R:92`). The K1b capture should call
it exactly that way. Otherwise extra-pair seed rows would appear in the
goldens. `kb_seeded_keys` is collected (`R:810`, `R:894`) but never used to dedup the
smart rows.

---

## 2. Data types, the two backends, and how merges are won

### 2.1 `ConnectionSuggestion` (`sespy/data_structure.py:793-801`)
```python
@dataclass
class ConnectionSuggestion:
    source: str      # element id
    target: str      # element id
    polarity: str    # "+" / "-"
    confidence: float  # 0..1
    rationale: str
```
- It is not frozen and has no defaults. The block comment at `:760-772` says
  SP3/SP4 "must define the float→int confidence mapping when converting
  accepted suggestions to Connection objects (see spec §9)". **That mapping
  was never implemented** (see 2.4).
- It is never serialised to project files. `export_test_values` exports only
  `wizard_state`, not suggestions (`ai_isa_wizard.py:1108-1116`).

### 2.2 `Connection` (`sespy/data_structure.py:153-164`)
- `source`, `target`
- `polarity="+"`
- `strength: str = "medium"`, commented `# weak | medium | strong`
- `confidence: int = 3`, on a 1–5 scale:
  - `CONFIDENCE_OPACITY` covers {1..5} (`sespy/constants.py:67-73`);
  - MANUAL says "Confidence (1 to 5)" (`docs/MANUAL.md:190`).
- `delay="immediate"`, `ratings=[]`, `description=""` (kw-only; serialised
  only when non-empty).
- Serialised by `_connection_to_dict` (`:261-269`).

Both fields already exist and are serialised, so writing them needs no schema
bump. This confirms spec `:1304-1305`.

### 2.3 The two `suggest_connections`
- **`sespy/wizard.py:78-86`** is a thin wrapper:
  `return _suggest_impl(state)`, with
  `from .connection_scorer import suggest_connections as _suggest_impl`
  (`:23`).
  - Stale comments call SP3 "TF-IDF + rules" (`:71-76`); no TF-IDF exists.
  - "SP4 will replace the implementation behind a settings switch" (`:83-84`)
    is stale too: SP4 runs alongside SP3 and does not replace it.
- **`sespy/claude_backend.py:469-593`**: `suggest_connections(state) ->
  ValidationOutcome`. This is a different return type: `suggestions`,
  `raw_count`, `drops_by_reason` (`:62-75`).
  - Runs synchronously inside `@reactive.extended_task` through
    `asyncio.to_thread` (`ai_isa_wizard.py:1119-1128`).
  - Model output is constrained to `confidence ∈ {0.3, 0.5, 0.7, 0.9}` by the
    prompt (`:166-175`) and the tool schema enum (`:261-262`).
  - Validation clamps to [0, 1] but does **not** enforce the enum
    (`:434-448`).
  - It also validates pairs against `_VALID_TYPE_PAIRS`, the **2-tuple
    projection of the same `_CONN_TYPES`** (`:24`, `:425-429`;
    `data_structure.py:93-95`). The prompt lists the 11 directions, including
    R->S (`:144-146`).
  - Errors map to i18n keys through `_REASON_TO_I18N` (`:116-124`).

### 2.4 Wizard flow (`sespy/modules/ai_isa_wizard.py`)
- **State**:
  - `wizard_suggestions_sp3: reactive.Value[list[ConnectionSuggestion]]`
    (`:637`)
  - `wizard_claude_status`: Idle, Loading, `Returned(outcome)` or
    `Failed(error)` (`:61-86`, `:639-641`)
  - consent flag (`:643`)
  - generation counter (`:647`)
- **SP3 computed once on entry to step 11**: `if step_idx + 1 == 11:
  wizard_suggestions_sp3.set(suggest_connections(_assemble_wizard_state()))`
  (`:1089-1090`). It is set before `_enter_step` so the first render already
  has the rows (`:1070-1076`).
- `_assemble_wizard_state` (`:1094-1106`) builds `WizardState` with sea,
  ecosystem, country codes, issues, `elements=list(isa.elements)` and
  `country_names` from the snapshot.
- **SP4 runs on demand**: the Generate button and one-time consent modal
  (`:1202-1255`), then `_trigger_claude_call` (`:1131-1140`), then the
  observer (`:1143-1199`). The observer discards stale generations
  (`:1189-1197`).
- **Back from step 11** resets Claude to Idle and bumps the generation
  (`:1259-1268`). SP3 is recomputed on the next 10→11.
- **Rendering** (`:403-497`):
  - The SP3 table always shows, plus the help note when non-empty
    (`:431-437`).
  - The Generate button appears only when `ANTHROPIC_API_KEY` is set and
    `SESPY_DISABLE_CLAUDE` is not (`:1469-1472`).
  - The SP4 table, with its drops badge, appears under it (`:466-495`).
- **Accept path, `_on_finish`** (`:1302-1393`):
  1. Iterate SP3 rows first. If `input[f"accept_sp3_{i}"]()` is set, append
     `_apply_row_edits(s, "sp3", i)` (`:1313-1322`).
  2. Then do the same for SP4 rows (`:1324-1337`).
  3. Any checkbox read failure aborts with a toast (`:1339-1355`).
  - `_apply_row_edits` (`:1288-1300`) applies the per-row polarity switch and
    the "reverse" swap **before dedup**.
  - Dedup: `final, discarded, overwritten = _dedup_accepted(accepted)`
    (`:1361`), with toast `wizard.duplicates_resolved_n` (`:1363-1368`).
  - Write (`:1371-1378`):
    ```python
    new_conns.append(Connection(
        source=s.source, target=s.target, polarity=s.polarity,
    ))
    ```
    Strength and confidence take their defaults (`"medium"`, `3`). Confidence
    and rationale are thrown away. The new connections are **appended to
    existing `isa_data.connections` with no dedup against them**.
  - **Stale spec reference**: spec `:1314` cites "`ai_isa_wizard.py:926-928`"
    for the accept path. At v1.16.0, lines 926-928 are the K1 chip handler
    (`freeform_counts` update). The real accept path is **`:1371-1378`**.

### 2.5 How a merge is won today: `_dedup_accepted` (`:500-527`)
```python
key = (s.source, s.target, s.polarity)
prev = seen.get(key)
if prev is None:            seen[key] = s
elif s.confidence > prev.confidence: seen[key] = s; overwritten += 1
else:                       discarded += 1
return list(seen.values()), discarded, overwritten
```
1. **Only accepted rows take part.** An unaccepted suggestion never competes.
2. **The key is (source, target, polarity) after row edits.** The same edge
   with opposite polarity is not a duplicate: both are kept and both are
   written. A reversed SP3 row can collide with an SP4 row in the other
   direction.
3. **A strictly greater 0..1 `confidence` wins.** On a tie the first entry
   wins, and SP3 is iterated first, so **SP3 wins ties** (`:1313` comment).
   Duplicates *within* one table cannot happen: a scorer pair is unique, and
   Claude is told one per pair, although that is not enforced by validation.
4. **Position**: an overwrite replaces the value under an existing dict key,
   so the winner takes the first-seen row's slot in output order.
5. **Comparable scales today**: SP3 emits {0.3, 0.5, 0.6, 0.9} and Claude
   emits {0.3, 0.5, 0.7, 0.9}. SP3 0.6 loses to Claude 0.7. SP3 0.9 ties
   Claude 0.9, and SP3 wins.
6. **The winner currently changes nothing that is persisted.** The write
   (`:1375-1377`) uses only source, target and polarity, and all of them are
   in the key. Only the toast counts differ. Once K1b writes strength and
   integer confidence (and possibly the rationale into `Connection.description`),
   the winner starts to matter. K1b must decide whether to compare SP3's new
   continuous relevance (kept as a separate 0..1 field, spec `:1311-1313`)
   with Claude's enum values, or to rank by source.

---

## 3. Tests that pin current behaviour

**No artefact called "SP3 goldens" exists.** `grep -i golden` finds none in the
SP3/SP4 specs and plans or in any scorer or wizard test. The only occurrence is
the K1 spec itself (`:1321`). The de facto goldens are the value-pinning tests
below, plus the help text and the MANUAL.

### 3.1 `tests/test_connection_scorer.py` (652 lines; groups G1–G5 per `:3-8`). Must be re-derived.
- `:29` `test_keyword_json_has_10_keys_for_the_11_pairs`: exact set of 10 keys,
  with no `responses_states`.
- `:45`, `:53`, `:67`: polarity-signal keys, non-empty lists, lowercase.
- `:86/:94/:102`: 0, 1, 2+ matches give 0.3, 0.6, 0.9. `:109/:123`: substring
  match, case-insensitive. `:129`: an unknown pair gives 0.5.
- `:145`: reversal compound.
- `:169-247`: polarity branches (R→P `-`, A→P mitigation, P→S, S→I negation
  flip, default `+`).
- `:270-293`: 14 parametrized verb cases.
- `:312-403`: cross-product, loss filter, confidence-descending sort, cap,
  relevance exactly 0.3 survives.
- `:425/:433`: an empty state or a single element gives `[]`.
- `:443`: `test_full_state_returns_typed_suggestions` asserts
  `confidence in {0.3, 0.6, 0.9}`.
- `:462`: 5×5 D→A gives exactly 15.
- `:480-541`: `test_every_keyword_type_yields_high_confidence_suggestions`
  needs confidence ≥ 0.6 for each `_CONN_TYPES` key except `responses_states`.
- `:544`: unknown type is skipped. `:567`: slug map inverse. `:576`: polarity
  default. `:596`: no wizard import.
- `:635` `test_r_to_mpf_relevance_is_flat_05` and `:644-652`
  `test_detect_polarity_responses_to_states`: both are R→S specific and get
  deleted or rewritten when K1b drops the pair.

### 3.2 Shared-topology pins (these break if `_CONN_TYPES` itself is edited)
- `tests/test_data_structure.py:143-157`: 3-tuple shape and `len == 11`.
  `:160-175`: exact 11 entries **in order**. `:178-186`: `_VALID_TYPE_PAIRS`
  is the projection of `_CONN_TYPES`, with length 11.
- `tests/test_link_rules.py:235-240`: `_CONN_TYPES` must be set-equal to the
  canonical targets of `DAPSIWRM_ADJACENCY_RULES` (`sespy/constants.py:230-263`,
  which includes Responses→MPF rule "12" at `:260`).
- `tests/test_link_rules.py:243-251` `test_rule_based_scorer_suggests_r_to_mpf`
  **asserts the scorer emits R001→MPF1**. It must be inverted or removed under
  K1b.
- `:254-266`: the scorer never emits extension pairs.
- `:269+` `test_claude_backend_accepts_r_to_mpf` must stay green: Claude keeps R→S.
- `tests/test_claude_backend.py:91`: the prompt lists the 11 directions,
  including "R->S". `:343` and `:453` cover `invalid_pair`.

### 3.3 Wizard unit tests
- `tests/test_wizard.py:63-72`: an empty state gives `[]`.
  `:94-104`, `:107-118`, `:121-130`: `_dedup_accepted` keeps both polarities,
  higher confidence wins and counts `overwritten`, and an equal-confidence tie
  goes to SP3 (`rationale == "sp3 r"`). The fixtures use 0.5, 0.7 and 0.9.
- `tests/test_wizard_confidence_help.py`:
  - `:27-28`: fixture `confidence=0.6`.
  - `:31-57`: the help note appears per table, in 9 languages, and each
    non-English text differs from the English.
  - **`:60-68` `test_rule_explanation_matches_the_scorer`**: the English text
    must contain "0.3", "0.6", "0.9" and "0.5", and
    `calculate_relevance("zzz","qqq","drivers","activities") == 0.3` and
    `("responses","states") == 0.5`.
- `tests/test_wizard_review_polarity.py`:
  - `:40-41`: fixture.
  - `:44-56`: row attributes.
  - `:85-106`: drives the wizard and needs at least one `accept_sp3_` row.
  - `:116-135`: Finish writes exactly `[(tgt, src, flipped)]` or
    `[(src, tgt, pol)]` and **compares only (source, target, polarity)**. If
    K1b writes strength and confidence, these tests can add assertions.
- `tests/test_wizard_completion.py:57-74`: drives the wizard with labels
  "Item 4"…"Item 10", unticks every `accept_sp3_` row, and expects
  `connections=0` in the completion body (`:100-104`). This works for any
  suggestion count.

### 3.4 e2e (`tests/test_wizard_e2e.py`)
- `:476-490` case 7: no Generate button without a key.
- `:493-521` case 8, `case_review_flip_and_reverse`:
  - Labels are "E2E {target} sample" (`:102`, `:136`).
  - Needs a row `tr.wiz-sugg` with `#wizard-pol_sp3_0`, `swap_sp3_0` and
    `accept_sp3_0`.
  - Asserts the reworded rationale and "1 connections".
  - Under K1b this still needs **at least one SP3 row** for keyword-free
    labels. R's 0.3 floor still holds unless the enhanced relevance changes
    the floor; verify on the R side.
- `:524-561` cases 8b and 9: consent and auth-error toast. Then it waits for
  `#wizard-accept_sp3_0`.
- No e2e test asserts numeric confidence. `tests/test_kb_wizard_e2e.py:295-305`
  asserts the About "Reference data" panel text (vendored, `R v1.35.6`, no
  "differs"). A third allow-listed file adds a line there, which is fine.

### 3.5 Docs and strings that carry the old numbers
- `docs/MANUAL.md:148`: "(none 0.3, one 0.6, two or more 0.9; 0.5 for Response
  → Marine Processes links…)". `:150`: "with the higher confidence winning".
- `sespy/translations/core.json:2863` `wizard.confidence_help_rules` in 9
  languages repeats the same numbers and the R→MPF sentence.

---

## 4. Hosting `ses_connection_db.json` (`override: false`) in K1's layer

### 4.1 `sespy/r_kb.py`
- Add `CONNECTION_DB_NAME = "ses_connection_db.json"` next to `:20-22`.
- Add an `AllowRow` to `ALLOW_LIST` (`:37-57`) with `required_keys`,
  `min_counts`, `version_key` and `override=False`, plus `containers`.
  - `containers` keys must equal `min_counts` keys
    (`tests/test_r_kb.py:69-71`).
  - Pick containers that match the export: `connection_db` (an R list of
    entries, likely a JSON array) and `synonym_db` (a named list, a JSON
    object).
- Add an accessor `Snapshot.connection_db()` beside `kb()` and
  `governance()` (`:166-170`; spec `:341`).
- **Version-key trap**: `_load_vendored` requires `row.version_key in data`
  and runs `validate` → `version_major` on it (`:198-202`, `:67-73`). The
  spec's export shape `{r_tag, connection_db, synonym_db}` (spec `:1323`) has
  **no `version` key**. `r_tag` cannot serve: `version_major("v1.35.6")`
  raises `ValueError: invalid literal for int() with base 10: 'v1'`
  (verified). Two options:
  - the export script writes a `version` (e.g. `1` or `"1.0"`); or
  - `version_major` learns to strip a leading `v`.

  The first option is simpler and keeps `version_major` unchanged.
- **Automatic for an `override=False` row**:
  - `_load_vendored` loads it, validates it and checks its hash against
    `manifest["files"][name]` (`:196-211`). The import fails if the file is
    missing or unpinned.
  - The registry skips it in `_refresh` (`:328-330`, `:348-350`). Live
    snapshots copy the vendored entry through `files = dict(self._vendored.files)`
    (`:367`). `_fall_to_vendored` copies everything too (`:425`).
  - About lists every `ALLOW_LIST` row (`sespy/modules/topbar_actions.py:268-278`).
  - `hashes_for_load_check(name)` works for any allow-listed name
    (`r_kb.py:293-295`, `:453-455`). The "shared" half is always `None` here,
    because `_last_shared` is filled only from override parses (`:360`).
  - `provenance_outcome` (`sespy/modules/project_io.py:53-75`) then reports:
    - `None` if the saved hash equals the snapshot's;
    - `"differs"` never, because the saved hash would equal the vendored one,
      which is the snapshot's;
    - `"unavailable"` for any other hash.

    So a project saved by a future SESPy with a different vendored connection
    DB gets the "unavailable" toast (`project_io.py:349-352` builds it). That
    is acceptable, but the K1b spec should say so.

### 4.2 Provenance is **not** automatic
- `current_provenance(meta, snapshot, reads)` writes only the names in the
  session's `reads` (`r_kb.py:131-133`). That is called from
  `project_io.py:172-180`.
- Reads are recorded explicitly with `r_kb.add_reads(...)`. Today that
  happens at `ai_isa_wizard.py:863` (chips) and `:1461` (countries), both with
  `(KB_NAME, GOVERNANCE_NAME)`, and at `report_export.py:103`.
- K1b must add `r_kb.add_reads(reference_reads, (r_kb.CONNECTION_DB_NAME,))`
  where the scorer runs, i.e. next to `:1089-1090`.
  - `add_reads` is isolate-safe in an effect (`r_kb.py:136-153`).
  - It is a no-op when `reference_reads is None` (unit tests, or a mount
    without it, `:145-146`).
- The scorer must get the snapshot. The wizard already has
  `snap = snapshot if snapshot is not None else r_kb.VENDORED`
  (`ai_isa_wizard.py:623`). Either thread `snap.connection_db()` into
  `suggest_connections` as a new optional parameter (keep the bare call
  working, because many tests use it), or have the scorer default to
  `r_kb.VENDORED.connection_db()`. Since the row is `override=False`, every
  snapshot holds the same vendored data, so the default is behaviourally
  identical.
- Keep `connection_scorer.py` Shiny-free: `r_kb` imports Shiny lazily
  (`r_kb.py:147`), so it is safe to import.

### 4.3 Schema
**No bump is needed** (spec `:1303-1305`).
- `Connection.strength` and `Connection.confidence` already exist and are
  serialised.
- `metadata.reference_data` is a free dict of dicts. A loader accepts any
  file key (`data_structure.py:601-605`; the check is only "dict whose values
  are dicts").
- v1.16.0 readers skip unknown names at load-check, because `name not in
  snapshot.files` gives `None` (`project_io.py:66-67`).

### 4.4 Sync, manifest and pins (`sespy/r_template_catalogue.py`)
The JSON is **generated by an R export script, not stored in R's git**. That
breaks the existing models:
- `RUNTIME_INPUTS` (`:80-83`) maps an R repo path to its vendored target and
  is fetched with `git show {tag}:{path}` (`:447-452`). This does not fit.
- The manifest is built only from `RUNTIME_INPUTS` hashes (`:463-465`,
  `build_manifest` `:358-363`).
- `LOCAL_PINS` (`:85-87`) are R-generated gz fixtures whose `r_tag` must equal
  the target tag (`_local_pin_hashes` `:338-355`). This is the closest model,
  but local pins are not in the manifest and are not vendored.

The changes K1b needs:
1. A new constant, e.g. `EXPORTED_RUNTIME = ("sespy/data/r_kb/ses_connection_db.json",)`.
   - It is read from `repo_root`.
   - Its top-level `r_tag` must equal the target tag. Reuse the
     `fixture_r_tag` idea for plain JSON.
   - Hash it with `sha256_norm`.
   - Merge it into `runtime_hashes` before `build_manifest`, so the manifest
     lists 3 files.
   - Add it to the pin `files` in git mode (`:484-492`).
   - In fixture mode, read it like the `RUNTIME_INPUTS` targets (`:433-438`).
2. Pin the R sources with `sha256_text_norm` through `INPUTS`: add
   `data/ses_connection_knowledge_base.R` and
   `modules/ai_isa/connection_generator.R`, and any other ported file (the
   enhanced-relevance file, whichever defines `calculate_enhanced_relevance`
   and `.keyword_idf_weight`), to a `K1B_R_SOURCES` tuple. They land under
   `tests/parity/r_source/<basename>` (`:98`).
   - **Gotcha**: fixture mode reads every `INPUTS` key starting with `"data/"`
     as a conversion input (`:428-432`). A `data/*.R` key is harmless there,
     but it is read for nothing.
3. Add `scripts/export_r_connection_db.R`, modelled on
   `scripts/capture_k1_fixtures.R`:
   - tag guard and dirty guard (`:24-35`);
   - `Sys.setenv(MARINESABRES_ML_ENABLED = "FALSE")` (`:40`).

   It writes the vendored JSON. A K1b capture of `generate_connections`
   goldens probably belongs in a new `LOCAL_PINS` entry,
   `tests/parity/r_fixtures/k1b/*.json.gz`.
4. `tests/parity/r_sync.json` gains the vendored JSON, the new `.R` sources and
   the new fixtures. `docs/parity/R_SYNC.md` is regenerated in the same run.
   The pinned path set is guarded by `build_pin` (`:366-381`) and by
   `tests/parity/test_r_sync.py:24-65`.
5. **`tests/parity/check_live.py:56` `check_shipped`** iterates only
   `(*RUNTIME_INPUTS.values(), MANIFEST_PATH)`. Add the exported file, or the
   deploy pre-flight never checks the shipped copy against its pin.
   - The live checks iterate only `override` rows (`:105-106`, `:173`, `:274`,
     `:330`), so they skip it correctly.
   - The deploy `--print-override-names` list is unchanged
     (`tests/test_deploy_script.py:464`).
6. Packaging: `pyproject.toml:90` already globs `data/r_kb/*.json`.

### 4.5 Tests that pin exact sets and must be edited
- `tests/test_k1_sync.py:74-85` `test_constants`: exact `RUNTIME_INPUTS`,
  `LOCAL_PINS` and `K1_R_SOURCES` mapping.
- `tests/test_k1_sync.py:133-142` (assert at `:140`): the manifest `files` must equal exactly
  `["country_governance_db.json", "ses_knowledge_db.json"]`.
- `tests/test_r_kb.py`:
  - `:22-31` iterates `ALLOW_LIST`, so a new row is automatic, but it needs
    the manifest hash;
  - `:86-97` package-data covers `ALLOW_LIST`, automatic;
  - `:99-…` `test_import_fails_without_vendored_file` is still valid;
  - `:118-131` `test_wheel_contains_r_kb` has a **hard-coded** tuple of 3
    names (`:129`): add the new file;
  - `:38-48`: `ALLOW_LIST[0]` is assumed to be the KB, so keep the new row
    last.
- `tests/test_topbar_reference_data.py:20-28` iterates `ALLOW_LIST`, automatic.

---

## 5. Consumers, UI and i18n

### 5.1 Consumers
- `suggest_connections`, `ConnectionSuggestion` and `_CONN_TYPES` are used only
  in:
  - `sespy/connection_scorer.py`
  - `sespy/wizard.py`
  - `sespy/claude_backend.py`
  - `sespy/modules/ai_isa_wizard.py`
  - `sespy/data_structure.py`
  - the tests above
- **MosaicSES**: a grep of all tracked `.py`, `.js`, `.json` and `.md` files
  for `suggest_connections|ConnectionSuggestion|connection_scorer|claude_backend|_dedup_accepted|ai_isa_wizard|WizardState|_CONN_TYPES|_VALID_TYPE_PAIRS`
  found **no hits**. MosaicSES does not import the wizard module at all. Its
  `sespy.modules` imports are analysis, CLD and data-entry modules
  (`MosaicSES:multises_app/modules/compartments.py:21-41`). This confirms spec
  `:1340`. The comment at `ai_isa_wizard.py:621-622` ("MosaicSES … mount[s]
  the wizard without them") is stale.
  - Caveat: the grepped checkout is HEAD `1b71423` (v0.8.3+7). Per memory,
    the live MosaicSES has been ahead of local checkouts before.
  - MosaicSES does consume `r_kb` indirectly through the shared `sespy`
    package (vendored data), so the import-time `_load_vendored` of a third
    file applies to MosaicSES deploys too. The deploy symlinks SESPy's
    `sespy/`.

### 5.2 UI (`_render_suggestions_table`, `ai_isa_wizard.py:335-400`)
- Columns (`:360-368`): `#`, Source, Target, Polarity (switch), Reverse,
  Confidence, Rationale, Accept.
- Source and Target show **element ids**, not labels (`:373-374`). Labels
  appear only through `data-*` attributes for the JS rewording (`:387-393`;
  JS at `:314-332`).
- Confidence is printed `f"{s.confidence:.2f}"` (`:383`). **Strength is not
  shown.** If K1b shows R's strength or integer confidence, it needs new
  columns and keys.
- Per-row ids: `pol_sp3_{i}`, `swap_sp3_{i}`, `accept_sp3_{i}` (and `_sp4_`).
- Notes under each title: `wizard.confidence_help_rules` and
  `wizard.confidence_help_claude` (`:435`, `:484`).

### 5.3 i18n keys involved (`sespy/translations/core.json`, 9 languages)
| Key | Line |
|---|---|
| `wizard.confidence_help_rules` | `:2863` |
| `wizard.confidence_help_claude` | `:2874` |
| `wizard.verb_positive` / `verb_negative` | `:2885` |
| `wizard.no_suggestions` | `:2940` (stale text mentions "install the SP3 or SP4 scoring backend") |
| `wizard.confidence` | `:3127` |
| `wizard.suggestions_rule_based_n` | `:3677` |
| `wizard.duplicates_resolved_n` | `:3699` ("…replaced with higher-confidence version") |

Also used: `wizard.source`, `target`, `polarity`, `reverse`, `rationale`,
`accept`, `read_failures_n`, the `wizard.claude_*` set, and the presence test
`tests/test_claude_backend.py:795-825`.

- `confidence_help_rules` must be rewritten in all 9 languages, because it
  describes 0.3/0.6/0.9/0.5 and the R→MPF exception. Each non-English text
  must differ from the English (`tests/test_wizard_confidence_help.py:56-57`).
- The rationale verbs are English-only literals in `_select_verb`.

---

## 6. Risks and traps for the port

1. **`_CONN_TYPES` is shared.** It also feeds `_VALID_TYPE_PAIRS` (Claude
   validation), the Claude prompt's 11 directions, and the set-equality test
   against `DAPSIWRM_ADJACENCY_RULES` (`test_link_rules.py:235`). Do not edit
   it. Give the scorer its own R-ordered 10-pair tuple. Otherwise Claude
   starts dropping R→S as `invalid_pair` and the link-rules test fails.
2. **The pair order changes**: W→D and W→R now come before R→D and R→A. Any
   test or e2e step that reads "row 0" or relies on group order shifts. For
   example `test_wizard_review_polarity._first_suggestion` reads the first row
   only, so it is fine, but recheck the e2e `accept_sp3_0` cases.
3. **The merge rule needs a decision**:
   - The winner is irrelevant today (2.5 point 6) but becomes relevant once
     strength and confidence are written.
   - The spec keeps 0..1 relevance as a separate field for dedup. R's ML-off
     relevance is continuous (enhanced or IDF), so it no longer lines up with
     Claude's {0.3, 0.5, 0.7, 0.9}, and ties become rare.
   - Decide also what an SP4 winner writes for strength and confidence. Claude
     has neither, so keep the `Connection` defaults or map from its 0..1 value.
4. **Field naming**: `ConnectionSuggestion.confidence` is the 0..1 relevance
   today, while R's `confidence` is an integer. Rename it (e.g. `relevance`)
   or add `confidence_int`/`strength` with defaults. Otherwise every
   positional or keyword construction in the tests breaks: 10 files build
   `ConnectionSuggestion(...)` with `confidence=0.x`.
5. **Version key**: the planned export has no `version`, and
   `version_major("v1.35.6")` raises (4.1). The vendored load would make
   **import fail**, which takes SESPy and MosaicSES down at start.
6. **Sync model gap**: the file is R-generated, not in R's git (4.4). The
   manifest, `check_shipped`, `test_constants`, the manifest file list and
   `test_wheel_contains_r_kb` all pin exact sets.
7. **Provenance needs an explicit `add_reads`** at step-11 entry. Without it,
   saved projects never record the connection DB.
8. **R's KB-seed branch**: the wizard calls `generate_connections(rv$elements)`
   without sea or habitat, so the branch never runs. The capture must match
   that call, or seeded R→S, R→R, P→P and S→S rows enter the goldens.
9. **Regex engines**: per spec `:1327-1329`, `lookup_knowledge_base` and
   `.synonym_match` use `grepl(perl=TRUE)`, which Python `re` mostly matches.
   `.keyword_idf_weight` uses R's TRE engine (POSIX ERE semantics), so
   `[[:alpha:]]` and similar classes and longest-match alternation differ from
   `re`. Store the regexes verbatim and test them on a phrase table.
10. **The 0.3 floor in e2e**: case 8 (`test_wizard_e2e.py:493`) and the
    completion and polarity unit tests rely on at least one SP3 row for
    labels with no keywords ("E2E drivers sample", "Item 4"). If R's ML-off
    enhanced relevance can fall below `MIN_RELEVANCE = 0.3`, those tests lose
    their rows.
11. **Delay**: R's KB match sets `delay` from `temporal_lag` (`R:489-497`). The
    spec says `SES_CONNECTION_DB` has none (spec `:1330`). Keep
    `Connection.delay="immediate"`.
12. **`Connection.description`**: R keeps the rationale. SESPy discards it at
    accept (`ai_isa_wizard.py:1375-1377`). Decide whether K1b writes
    `description=s.rationale`. That is a behaviour change, not a schema bump,
    since the field is already serialised when non-empty.
13. **No dedup against existing connections** at Finish (`:1371-1378`). This
    is unchanged, but a re-run of the wizard on the same SES duplicates edges.
14. **Docs**: `MANUAL.md:148,150`, the `wizard.py:71-84` comments and the
    `data_structure.py:760-772` block (the "float→int mapping") all go stale.
    The manual version line and screenshots follow the release rule.
