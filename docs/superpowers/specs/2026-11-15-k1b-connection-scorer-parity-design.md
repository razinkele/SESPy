# K1b — Connection-scorer parity (design)

**Status:** draft for review · **Release:** SESPy v1.17.0 · **Depends on:** K1
(v1.16.0, live 2026-11-15) · **R pin:** v1.35.6 (`d1a655a`), unchanged
**Scope source:** K1 design spec §8 (`2026-11-09-k1-knowledge-base-parity-design.md`)
and roadmap §K1b. **Research appendices** (committed, with file:line references):
`docs/parity/k1b/R_SCORER_NOTES.md` (R side, verified by running R 4.4.1) and
`docs/parity/k1b/SESPY_SCORER_NOTES.md` (SESPy side at v1.16.0). The appendices
hold the algorithm detail; this document decides what to build.

---

## 1. Intent

The SES Wizard's rule-based connection suggestions (wizard step "connections",
the "SP3" table in the code) should be the suggestions the R app makes for the
same elements, carrying R's **strength** and **confidence** onto the saved
connections. Today SESPy ports only R's fallback relevance (0.3 / 0.6 / 0.9 by
keyword count). It scores 11 type pairs where R scores 10, ignores R's
connection knowledge base, and saves every accepted suggestion as
`medium` / confidence 3.

**Why now:** K1 built the reference-data layer this needs. The roadmap lists
K1b as the next step on the K1 branch, and it unblocks P9 (synonym-driven type
suggestions).

**Success:** for any set of wizard elements, SESPy's rule-based suggestions
match R's `generate_connections` output, run with ML off. "Match" means the
same rows in the same order, with equal `(from, to, polarity, strength,
confidence)`. Accepting a suggestion saves R's strength and confidence.

## 2. Goals, non-goals, anti-goals

**Goals**
1. Port R's rule-based scorer, as R runs it with ML off:
   - `lookup_knowledge_base`, `.synonym_match`, `.keyword_idf_weight`,
     `calculate_enhanced_relevance`, `analyze_phrase_polarity` /
     `detect_polarity`, the verb table, the double-negative filter, the
     threshold and the per-pair cap.
2. Vendor R's `SES_CONNECTION_DB` and `SES_SYNONYM_DB` as
   `sespy/data/r_kb/ses_connection_db.json` through K1's layer, pinned and
   hash-checked.
3. Use R's 10 pairs, in R's order, for the rule-based scorer.
4. Carry `strength` and integer `confidence` from suggestion to saved
   `Connection`.
5. Show strength and confidence in the rule-based suggestions table, as R
   shows them.

**Non-goals**
- R's ML branches, its basic-relevance fallback, the inline polarity fallback
  and the JSON seed block:
  - all four are unreachable in R v1.35.6 with ML off (R notes §0, §4);
  - R's wizard never passes a sea or habitat, so the seed block never runs.
- Temporal lag. `SES_CONNECTION_DB` has no `temporal_lag`, so R's delay is
  always NA. SESPy keeps writing its default delay.
- Changing the Claude path (the "SP4" table, `claude_backend.py`). Its
  type-pair list (`_CONN_TYPES` / `_VALID_TYPE_PAIRS`) stays as it is,
  including R→S.
- A live override of the connection DB (`override: false`). Python cannot read
  R's `.R` source at runtime.
- A project schema bump. `Connection` already has `strength` and `confidence`.
  Saved `reference_data` accepts any file name.

**Anti-goals (a failure even if it "works")**
- Suggestions that look plausible but differ from R's in rows, order, polarity,
  strength or confidence on the golden fixtures.
- A vendored file that can stop SESPy or MosaicSES from importing. K1's
  import-time validation runs on every allow-listed file.
- Claude suggestions losing their ability to propose R→S links.

## 3. Decisions

**Carried over from K1 §8:** D1–D5.

**D1 — Parity target is R with ML off, captured by a two-file harness.**
- Setting `MARINESABRES_ML_ENABLED=FALSE` alone does not turn ML off in the
  full app. ML is off there only because loading the model fails (R notes §4).
- Fixtures are therefore produced by sourcing only
  `data/ses_connection_knowledge_base.R` and
  `modules/ai_isa/connection_generator.R`, with stubs for `debug_log` and
  `%||%`, as the committed probes do (`docs/parity/k1b/k1b_probe*.R`). In that
  harness `ml_model_available` does not exist, so every ML branch is skipped.
- The harness calls `generate_connections(elements)` with no sea and no
  habitat, as R's wizard does (`step_navigation.R:92`).

**D2 — Pairs.** The rule-based scorer gets its own list:
- `R_CONNECTION_PAIRS`: D-A, A-P, P-S, S-I, I-W, R-P, W-D, W-R, R-D, R-A, in
  that order (verified, R notes §1). Each pair runs only if both element lists
  are non-empty.
- Rows come out pair-major. Within a pair, candidates are generated in
  `(i, j)` order: outer loop over source elements, inner over targets.
- `_CONN_TYPES` stays unchanged: it also drives Claude validation, the Claude
  prompt and `test_link_rules.py`.

**D3 — Per-pair selection, exactly as R does it.**
1. Keep a candidate when relevance ≥ 0.3 (inclusive).
2. Drop it when both lowercased names contain a `loss_keywords` substring.
3. Sort by relevance, descending and stable.
4. Keep the first 15.
5. No deduplication.

Relevance is computed with R's operation order (R notes §2). Float order
decides ties at the 15th place.

**D4 — Confidence and strength.**
- Exact KB match: confidence 4. Synonym match or no match: 3.
- Strength comes from the KB entry, otherwise `medium`.
- The best KB entry is chosen R's way: a synonym match scores `0.8·p` and ties
  go to the first entry in KB order (strict `>`). So a synonym hit can beat a
  weak exact hit, as in R.

**D5 — `ConnectionSuggestion` fields** (`data_structure.py:793`):
- The existing 0..1 field `confidence` is **renamed `relevance`**.
- New fields `strength: str = "medium"` and `confidence: int = 3` are added.
- Rule-based suggestions fill all three from the port. `relevance` is R's
  value, which R computes and then drops.
- Claude suggestions put Claude's 0..1 score in `relevance` and keep
  `strength="medium"` and `confidence=3` (my call; §6).

**D6 — Merge rule ("how an SP4 merge is won") — my call.**
- `_dedup_accepted` keeps its contract. Among ticked rows, keyed on
  `(source, target, polarity)` after the flip and reverse edits, the higher
  `relevance` wins, and a tie goes to the rule-based row because it is read
  first.
- Only the field name changes (`confidence` → `relevance`).
- **Why this is enough:** R's continuous relevance sits on the same 0..1 scale
  as Claude's score. Only the step values (0.3 / 0.6 / 0.9) disappear.
- **What changes in effect:** the winner's `strength` and `confidence` now
  reach the saved connection. Before K1b both sources saved `medium` / 3, so
  the winner did not matter.

**D7 — Accept path.** `_on_finish` (`ai_isa_wizard.py:1371-1378`, not the
`:926-928` K1 §8 cites) builds each `Connection` with `strength=s.strength` and
`confidence=s.confidence`:
- Flip (polarity) and reverse (swap) keep strength and confidence.
- The rationale is **not** saved, as in R (R saves `"<pol><strength>:<conf>"`
  only, R notes §5).

**D8 — Vendored export** `sespy/data/r_kb/ses_connection_db.json`:

```json
{ "version": 1, "r_tag": "v1.35.6", "r_commit": "d1a655a",
  "connection_db": [ {…137 entries, KB order…} ],
  "synonym_db":   { "<group>": ["term", …], …17 groups… } }
```

- `version` is an integer export-format version. K1's validator calls
  `version_major()` on it, and the K1 §8 shape without `version` would raise
  at import.
- `connection_db` is an ordered array, because ties depend on KB order.
- Regex strings are copied verbatim. They use only `[a-z0-9] . * ? |`.
- The export script is `scripts/export_r_connection_db.R`, run with
  `R_APP_DIR` set like the probes. It is deterministic: fixed field order and
  `auto_unbox`.

**D9 — Reference-data registration.**
- New `ALLOW_LIST` row:
  - `override=False`;
  - `required_keys` = the four top-level keys plus `version`;
  - `min_counts = {"connection_db": 137, "synonym_db": 17}`;
  - `containers = {"connection_db": list, "synonym_db": dict}` (K1's container
    check, added in the PR #33 review).
- Pins in `tests/parity/r_sync.json`: `sha256_text_norm` of
  `data/ses_connection_knowledge_base.R` and `sha256_norm` of the JSON.
- The sync script's check mode verifies the `.R` pin, so a changed R source
  flags. It does not need R installed. Regenerating needs R and the export
  script.
- Update the hard-coded file sets: `check_live.check_shipped` (`:56`),
  `test_k1_sync.py:74-85`, `:140`, and `test_r_kb.py:129`.
- Provenance needs an explicit `r_kb.add_reads(rr, [CONNECTION_DB])` where the
  scorer runs (wizard step-11 entry, `:1089-1090`). Without it,
  `metadata.reference_data` would not record the file.
- About shows the file as "vendored".

**D10 — UI** (`_render_suggestions_table`, `ai_isa_wizard.py:335-400`; my call,
following R's review list, `action_handlers.R:76-77`):
- The rule-based table drops the 0..1 "Confidence" column and shows
  **Strength** and **Confidence** (1–5, R's integer).
- The Claude table keeps its 0..1 column, relabelled "Score".
- `wizard.confidence_help_rules` is rewritten in all 9 languages: KB exact
  match → 4, synonym or keyword match → 3, strength from the KB.
- Correct the stale `wizard.no_suggestions` text, which mentions "install the
  SP3 or SP4 scoring backend".

**D11 — Rationale text** (my call):
- Port R's verb table (R notes §1 step 9; drives / increases / causes /
  decreases / impacts / reduces / restricts / enables / motivates).
- Each verb gets an i18n key in 9 languages. English equals R's text exactly.
- R does not translate the rationale; SESPy does today, and keeps doing so.
  Record this as a known difference.

## 4. Behaviour to reproduce (summary; detail in the R notes)

- **Relevance** (`calculate_enhanced_relevance`):
  - exact KB match → entry `p`;
  - synonym match → `(p·0.9)·0.9`;
  - no match → `0.2 + 0.75·min(1, matched/total + bonus)`, with the bonus capped
    at 0.3, using the keyword IDF weights (R notes §2).
- **Polarity:**
  - with a KB match, the KB entry's polarity, even when it reads oddly (for
    example "Overfishing decreases Fish stock decline");
  - without one: R-P is always `-`; A-P, P-S, S-I and I-W use keyword rules
    with negation and reversal; D-A, W-D, W-R, R-D and R-A fall through to `+`.
- **Regex:**
  - KB entry patterns, synonym matching and negation/reversal checks are PCRE
    in R (`grepl(perl=TRUE)`);
  - the other keyword checks are substring searches (TRE);
  - in Python use `re.search`, with `re.ASCII` wherever `\b` appears, because
    R's `\b` is ASCII-only.
- **Quirks to keep (parity):**
  - `ecosystem` gets the low IDF weight through `system`;
  - `mpa` matches inside "impact" and `ice` inside "service";
  - multi-word synonyms never match in the bonus step.

## 5. Testing

1. **Goldens from R:**
   - What to capture: `scripts/capture_k1b_fixtures.R` (two-file harness, D1)
     runs `generate_connections` on the 7 P2 template projects' elements plus
     3 wizard fixtures. The R notes' 16-row worked example is one of the 3.
   - What to assert: Python output equals R's on
     `(from_type, from_index, to_type, to_index, polarity, strength,
     confidence)` and order.
   - Fixture contents: the harness also dumps each candidate's relevance, for
     diagnostics only (compared at `1e-12`).
   - Pinning: fixtures are pinned in `r_sync.json` like K1's.
2. **Function tables:**
   - `lookup_knowledge_base` (exact / synonym / none, best-entry choice
     including the synonym-beats-weak-exact case);
   - `analyze_phrase_polarity` / `detect_polarity` over a phrase table captured
     from R.
3. **Selection unit tests:** inclusive 0.3 threshold, the double-negative
   filter not counting toward the cap, stable ties at the cap, the empty-list
   pair skip.
4. **Wizard:**
   - accept writes strength and confidence; flip and reverse keep them;
   - `_dedup_accepted` on `relevance`, with ties going to the rule-based row;
   - the new table columns and the Claude "Score" label.
5. **Re-derive or retire old pins:**
   - `test_connection_scorer.py` (the 0.3/0.6/0.9 values);
   - `test_link_rules.py:243`, which asserts the scorer emits R→S: move it to
     the Claude list or drop it;
   - `test_wizard_confidence_help.py:60-68`;
   - the `_dedup_accepted` tests (rename);
   - MANUAL.md lines 148 and 150.
6. **e2e:**
   - Re-check that `test_wizard_e2e.py`'s fixtures still yield at least one
     rule-based row under R's relevance; the old 0.3 floor guaranteed one. If
     not, change the fixture elements, not the scorer.
   - Run the full e2e suite before merging.
7. **CI before merge:** wait for the Linux unit and full-app jobs. K1's
   Windows-only test assumptions slipped through local gates.

## 6. Constraints and calls left to the builder

- **Python only**, reusing `sespy/r_kb.py`'s layer. No new runtime dependencies.
  R is needed only to regenerate fixtures and the export.
- **MosaicSES:** no code there uses the scorer or `ConnectionSuggestion` (both
  reports grepped it). It still imports `r_kb`, so the new allow-list row must
  validate at import. Run the MosaicSES gate (unit + e2e with
  `PYTHONPATH=<K1b tree>`, reds baselined against v1.16.0) before release.
- **Builder's calls:**
  - module layout: whether the port lives in `connection_scorer.py` or a new
    `sespy/r_connection_kb.py`;
  - whether `ConnectionSuggestion` keeps a deprecated `confidence` alias
    during the rename;
  - test file organisation.
- **My calls, open to change on review:**
  - D5: Claude rows default to `medium` / 3;
  - D6: merge on `relevance`, ties to the rule-based row;
  - D10: UI columns and the "Score" label;
  - D11: translated verbs.

## 7. Release

- v1.17.0, no schema bump. CHANGELOG sections: Added, Changed (suggestions now
  match R; strength and confidence saved), Known differences (translated
  rationale), Deferred.
- Rollback to v1.16.0 is a plain redeploy: no schema change, so no forward-fix
  constraint.
- Deploy as for K1: the pre-flight is unaffected, because `override=false`
  files are not fetched live.
