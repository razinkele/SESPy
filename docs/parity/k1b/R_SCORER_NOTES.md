# K1b: R rule-based connection scorer (R v1.35.6, ML off). Port reference

The R repo is checked out at tag `v1.35.6` (`git describe` confirmed this). Paths are relative to
`SESToolbox/MarineSABRES_SES_Shiny/`. Abbreviations: **CG** = `modules/ai_isa/connection_generator.R`,
**KB** = `data/ses_connection_knowledge_base.R`.

I checked the claims empirically with R 4.4.1 (Windows, `English_United States.utf8`). The harness sourced only KB + CG,
with stubs for `debug_log` and `%||%`. The probe scripts are committed beside these notes (run with `R_APP_DIR` set to the R checkout):
`k1b_probe.R`, `k1b_probe2.R`, `k1b_probe3.R`, `k1b_probe4.R`.

---

## 0. Scope: what is actually live with ML off

`generate_connections` (CG:755) calls only the following:

| Called | Defined | Live with ML off? |
|---|---|---|
| `generate_smart_connections` | CG:436 | yes |
| `calculate_relevance` | CG:264 | yes |
| `calculate_enhanced_relevance` | KB:1237 | yes. It always exists because KB is sourced globally (`global.R:698`) |
| `lookup_knowledge_base` | KB:1094 | yes. It is called **3 times per candidate**: relevance, polarity, strength. It is deterministic, so this matters for speed only |
| `.synonym_match` | KB:1161 | yes |
| `.keyword_idf_weight` | KB:1198 | yes |
| `detect_polarity` | CG:62 | yes |
| `.analyze_polarity_phrase` → `analyze_phrase_polarity` | CG:198 → KB:1363 | yes. The inline fallback at CG:208-225 is **dead** because KB defines `analyze_phrase_polarity` |
| `.calculate_basic_relevance` | CG:338 | **effectively dead**. It runs only if `calculate_enhanced_relevance` is missing or throws (CG:266-282). It throws only for a NULL/zero-length name |
| `predict_connection_ml`, `ml_model_available` | `functions/ml_inference.R:272` | **off**, see §4 |
| `ses_knowledge_db_available` / `get_context_connections` (JSON "seed" block, CG:809-919) | `functions/ses_knowledge_db_loader.R:314/284` | **unreachable from the wizard**. It needs `regional_sea` and `habitat` to be non-NULL. The only caller passes neither (`step_navigation.R:92`) |

`functions/dapsiwrm_connection_rules.R` is **not** used by `generate_connections`. Nothing in CG refers to it.
Every function above has exactly one definition in the repo (grep for `^name <-` over `*.R`), so nothing shadows them.

---

## 1. `generate_connections` end to end (ML off)

### Inputs
- Signature: `generate_connections(elements, regional_sea = NULL, habitat = NULL)` (CG:755).
- `elements` is a named list with keys `drivers, activities, pressures, states, impacts, welfare, responses`.
  Each value is an unnamed list of element lists. **Only `$name` is read** (CG:448-449).
  - In the wizard, elements are `list(name = <text>, description = "", timestamp = Sys.time())`
    (`ai_isa_assistant_module.R:2086-2091` quick-option path, `:2395-2400` free-text path). They are also rebuilt from
    saved ISA data at `ai_isa_assistant_module.R:283-349`.
  - The quick-option path dedups by name (`:2050-2051`). I did not verify a duplicate check on the free-text path.
  - Duplicate names are harmless to the generator. They just yield more candidates.
- Constants: `MAX_PER_TYPE <- 15` (CG:757) and `MIN_RELEVANCE <- 0.3` (CG:758).

### Type pairs and exact order (the K1 claim is VERIFIED)
The blocks run in this order. Each runs only if both element lists are non-empty (`length(...) > 0`).

| # | pair | from_type → to_type | matrix | line |
|---|---|---|---|---|
| 1 | D-A | drivers → activities | `d_a` | CG:922-926 |
| 2 | A-P | activities → pressures | `a_p` | CG:929-933 |
| 3 | P-S | pressures → states | `p_mpf` | CG:936-940 |
| 4 | S-I | states → impacts | `mpf_es` | CG:943-947 |
| 5 | I-W | impacts → welfare | `es_gb` | CG:950-954 |
| 6 | R-P | responses → pressures | `r_p` | CG:957-961 |
| 7 | W-D | welfare → drivers | `gb_d` | CG:968-972 |
| 8 | W-R | welfare → responses | `gb_r` | CG:975-979 |
| 9 | R-D | responses → drivers | `r_d` | CG:982-986 |
| 10 | R-A | responses → activities | `r_a` | CG:989-993 |

Results are concatenated with `c(connections, new_conns)`. The output is pair-major in the order above.

### Per pair: `generate_smart_connections` (CG:436-574)
1. Nested loops: `for i in seq_along(from)` (outer), then `for j in seq_along(to)` (inner) (CG:446-447).
   Candidates are therefore generated in (i, j) row-major order.
2. `relevance <- calculate_relevance(...)` (CG:451). With ML off this equals `calculate_enhanced_relevance` (CG:319).
3. Threshold: keep the candidate if `relevance >= min_relevance` (**inclusive**, CG:452).
4. **Double-negative filter**, applied after the threshold and before the cap (CG:440-463).
   - `loss_keywords` = `loss, decline, declin, degrad, reduc, damag, destruct, decreas, diminish, deplet, erosion, collapse, extinct, mortality, death, disappear, absent, lack, scarcity`.
   - The candidate is skipped if **both** lowercased names contain any keyword: `grepl(kw, x)`, default TRE, substring match.
   - Example: "Fish stock decline" → "Reduced fish provisioning" is dropped.
   - Skipped candidates do not use up the cap.
5. `polarity <- detect_polarity(...)` (CG:465). See §2.5.
6. Defaults: `strength "medium"`, `confidence 3`, `delay NA_character_`, `scoring_method "keyword"` (CG:468-471).
7. `kb_match <- lookup_knowledge_base(from_name, from_type, to_name, to_type)` (CG:474-499). If it is non-NULL:
   - `strength <- kb_match$strength %||% "medium"`. KB strength is always one of `weak|medium|strong`.
   - `scoring_method <- "kb"`.
   - `confidence <- switch(match_quality, exact = 4, synonym = 3, 3)` (CG:483-487). **So the claim is VERIFIED: 4 for exact, 3 for synonym or no KB match.**
   - `delay` comes from `kb_match$temporal_lag`, but **KB entries have no `temporal_lag` field** and `lookup_knowledge_base` never returns one (KB:1115-1121, 1136-1142). So **delay is always `NA`** and `delay_years` is always `NA_real_`.
8. The ML confidence bump (CG:502-510) is skipped with ML off.
9. The verb comes from `from_type` and polarity (CG:513-529):
   - drivers → `"drives"`
   - activities → `+`: `"increases"`, else `"causes"`
   - pressures → `+`: `"increases"`, else `"decreases"`
   - states → `"impacts"`
   - impacts → `+`: `"increases"`, else `"reduces"`
   - responses → `-`: `"restricts"`, else `"enables"`
   - welfare → `+`: `"motivates"`, else `"reduces"`
   - `rationale = paste(from_name, verb, to_name)` (single spaces, CG:544). It is **not translated**.
10. Candidate = `list(conn = <fields>, relevance = relevance)` (CG:531-549).
11. Sort and cap:
    - `candidates[order(sapply(..., relevance), decreasing = TRUE)]` (CG:556).
    - R's `order()` default method here is radix, which is **stable** even with `decreasing = TRUE`. I verified this: `order(c(.5,.7,.5,.7), decreasing=TRUE)` gives `2 4 1 3`.
    - **Ties therefore keep the (i, j) generation order.** Then the first `min(n, 15)` are kept (CG:557-558).
12. **The returned conn objects drop `relevance`** (CG:558). It is used only for the threshold and the sort.

### Output fields (exact, in order; verified by probe)
`from_type, from_index, from_name, to_type, to_index, to_name, polarity, strength, confidence, delay, delay_years, rationale, matrix, scoring_method`

| field | type | notes |
|---|---|---|
| `from_index`, `to_index` | integer | **1-based** positions in the element lists |
| `polarity` | string | `"+"` or `"-"` |
| `strength` | string | `"weak"`, `"medium"` or `"strong"` |
| `confidence` | number | 3 or 4 (R double) |
| `delay` | `NA_character_` | always NA here |
| `delay_years` | `NA_real_` | always NA here |
| `matrix` | string | matrix code, see the pair table |
| `scoring_method` | string | `"kb"` or `"keyword"` with ML off |

There is **no `relevance` field and no `source` field**.

### Caps, dedup, totals
- At most 15 per pair, so at most 150 in total.
- The wizard's 200 cap (`step_navigation.R:96-105`) can never trigger with ML off and no seed.
- **There is no cross-pair dedup.** It is not needed, because pairs are distinct type pairs and each (i, j) is visited once.
- The seed block records `kb_seeded_keys` (CG:810, 894) but **never reads it**, so even with seeding the generator does not dedup. Do not port the seed block for K1b.

### Worked parity example (probe output, R 4.4.1)
Elements:
- D: Food security, Economic growth
- A: Commercial fishing, Tourism
- P: Overfishing, Nutrient enrichment
- S: Fish stock decline, Eutrophication
- I: Reduced fish provisioning
- W: Food security loss, Income
- R: Fishing quotas, Wastewater treatment

Result: 16 rows, in this exact order:
```
d_a   Food security        -> Commercial fishing   + strong conf=4 kb      | Food security drives Commercial fishing
d_a   Economic growth      -> Commercial fishing   + strong conf=4 kb      | Economic growth drives Commercial fishing
a_p   Commercial fishing   -> Overfishing          + strong conf=4 kb      | Commercial fishing increases Overfishing
a_p   Commercial fishing   -> Nutrient enrichment  + strong conf=3 kb      | Commercial fishing increases Nutrient enrichment
p_mpf Overfishing          -> Fish stock decline   - strong conf=4 kb      | Overfishing decreases Fish stock decline
p_mpf Nutrient enrichment  -> Eutrophication       + strong conf=4 kb      | Nutrient enrichment increases Eutrophication
p_mpf Nutrient enrichment  -> Fish stock decline   + strong conf=3 kb      | Nutrient enrichment increases Fish stock decline
p_mpf Overfishing          -> Eutrophication       - medium conf=3 kb      | Overfishing decreases Eutrophication
es_gb Reduced fish provisioning -> Income          - strong conf=3 kb      | Reduced fish provisioning reduces Income
r_p   Fishing quotas       -> Overfishing          - strong conf=4 kb      | Fishing quotas restricts Overfishing
r_p   Wastewater treatment -> Nutrient enrichment  - strong conf=3 kb      | Wastewater treatment restricts Nutrient enrichment
gb_d  Food security loss   -> Food security        + medium conf=3 keyword | Food security loss motivates Food security
gb_d  Food security loss   -> Economic growth      + medium conf=3 keyword | Food security loss motivates Economic growth
gb_d  Income               -> Food security        + medium conf=3 keyword | Income motivates Food security
gb_d  Income               -> Economic growth      + medium conf=3 keyword | Income motivates Economic growth
r_a   Fishing quotas       -> Commercial fishing   - strong conf=3 kb      | Fishing quotas restricts Commercial fishing
```
This is a good first golden fixture. Synonym-quality rows show the semantics already: `Commercial fishing -> Nutrient enrichment` is synonym-matched to a KB entry.

---

## 2. Scoring algorithms

### 2.1 `lookup_knowledge_base(from_name, from_type, to_name, to_type, use_synonyms = TRUE)` (KB:1094-1149)
- `from_lower <- tolower(from_name)` and `to_lower <- tolower(to_name)`.
- `best_match <- NULL` and `best_score <- 0`. Iterate `SES_CONNECTION_DB` **in list order**.
- Skip an entry unless `entry$from_type == from_type && entry$to_type == to_type` (exact string compare).
- `from_match <- grepl(entry$from_pattern, from_lower, perl = TRUE)`. `to_match` is the same with `to_pattern`. This is **PCRE**, unanchored search.
- **Exact match** (both sides match):
  - `score = p * 1.0`.
  - If `score > best_score` (**strict**), the result becomes `list(probability = p, polarity, strength, source, match_quality = "exact")`.
- **Synonym match**: else-branch, `use_synonyms` is TRUE and exactly one side matched.
  - Run `.synonym_match(<non-matching side text>, <that side's pattern>)`.
  - If TRUE: `score = p * 0.8`, and if `score > best_score`, the result is `list(probability = p * 0.9, ..., match_quality = "synonym")` (KB:1132-1143).
- Returns `best_match` or `NULL`. The `"partial"` quality in the docs is never produced.
- Tie-breaking: **the first entry in DB order wins** (strict `>`).
- **Cross-quality inversion.** Selection uses `0.8p` for synonym matches, so a synonym match on a high-p entry beats an exact match on a low-p entry.
  - Verified: "Fish farming" → "Chemical pollution" (A→P). The exact match is KB:450-454 (p = 0.50, `+ weak`). The winner is a synonym match with p_returned = 0.837 (`+ strong`, entry p = 0.93).
  - Result: confidence 3, strength strong, relevance 0.7533.

### 2.2 `.synonym_match(text, pattern)` (KB:1161-1187)
1. `pattern_terms <- unlist(strsplit(pattern, "\\||\\.\\*|\\.|\\?|\\*|\\+|\\(|\\)"))`.
   - This is a default-engine (TRE) split on `|`, `.*`, `.`, `?`, `*`, `+`, `(`, `)`.
   - Example: `food.?secur|protein.?demand|nutrition` → `food,"",secur,protein,"",demand,nutrition`.
   - Then `trimws`, and keep terms with `nchar >= 3`.
   - Over all 274 KB patterns the term set is 471 unique, purely `[a-z0-9]` fragments (verified).
2. If there are no terms, return FALSE.
3. For each `SES_SYNONYM_DB` group, in names order:
   - `text_has_synonym = any(grepl(s, text, perl = TRUE))` over the group's synonyms. The synonym is used **as a PCRE regex** on the full lowercased text.
   - If not, go to the next group.
   - `pattern_has_synonym = any over terms pt, synonyms s of (grepl(pt, s, perl=TRUE) || grepl(s, pt, perl=TRUE))`. In practice `pt` is a literal substring of `s`, or `s` (as a regex) matches inside `pt`.
   - If both are TRUE, return TRUE.
4. Return FALSE.

Group order changes nothing, because the result is a boolean OR.

### 2.3 `.keyword_idf_weight(keyword)` (KB:1198-1219)
- `rare_words`: `eutrophic, hypox, acidif, bleach, trawl, bycatch, bioaccumul, calcif, permafrost, denitrif, anox, pteropod, sargassum, ballast, anti.?foul, discarding, ghost.*net`. If any matches, the weight is **2.0**. This check runs first.
- `common_words`: `chang, increas, decreas, loss, impact, effect, manag, develop, system, environ, marine, coast, ocean, sea, water`. If any matches, the weight is **0.6**.
- Otherwise the weight is **1.0**.
- All matching is `grepl(word, tolower(keyword))`, TRE substring. Note that `ecosystem` gets 0.6 via `system`.
- The keyword lists are fixed, so the weights are constants. Precomputed (probe 2):

| key | total | weight ≠ 1.0 |
|---|---|---|
| drivers_activities | 16.6 | develop 0.6 |
| activities_pressures | 18.6 | develop 0.6, trawl 2.0 |
| pressures_states | 19.6 | ecosystem 0.6, acidif 2.0 |
| states_impacts | 13.8 | loss 0.6, change 0.6, ecosystem 0.6 |
| impacts_welfare | 17.0 | (none) |
| responses_pressures | 16.6 | manag 0.6 |
| welfare_responses | 11.6 | management 0.6 |
| responses_drivers | 10.0 | (none) |
| responses_activities | 11.6 | manage 0.6 |
| welfare_drivers | 10.0 | (none) |

### 2.4 `calculate_enhanced_relevance(from_name, to_name, from_type, to_type, base_keywords = NULL)` (KB:1237-1341). This is the 0..1 relevance.

**Step 1, KB** (KB:1240-1249):
- `kb_match <- lookup_knowledge_base(...)`. If it is non-NULL, return `min(1, kb_score)`, where:
  - exact: `kb_score = probability`, which is `p`.
  - synonym: `kb_score = probability * 0.9`, which is **`(p * 0.9) * 0.9`**, because the returned probability is already `p * 0.9`. Example: 0.95 → 0.7695.
  - other: `* 0.8`. This branch is unreachable.

**Step 2, TF-IDF fallback**:
- Keyword lists are at KB:1257-1291. Ten keys: the ten pairs above, keyed `"<from>_<to>"`.
- `key` is not in the list → return **0.5** (KB:1297). This is unreachable for the 10 pairs.
- Loop: for each `kw` in list order (KB:1303-1315):
  - `total_weight += w`.
  - `from_hit <- grepl(kw, from_lower)` and `to_hit <- grepl(kw, to_lower)`. Default TRE. Note that `gear.*restrict` is a regex.
  - Both hit: `matched += w * 1.5`. Exactly one hits: `matched += w`.

**Step 3, synonym bonus** (KB:1318-1331):
- `from_words <- unlist(strsplit(gsub("[^a-z ]", "", from_lower), "\\s+"))`, and the same for `to_words`.
  - This strips digits, hyphens and every non-ASCII letter, so `"non-target"` → `"nontarget"` and `"co2"` → `"co"`.
  - A leading space yields a `""` token.
- For each group: `from_in_group = any(sapply(synonyms, function(s) any(grepl(s, from_words))))`. This is default **TRE**, with the synonym as a regex **against each single word**, so multi-word synonyms like `fish farm` or `sea level` can never hit here. The same applies to `to_in_group`.
  - If both are in the group: `bonus += 0.1`.
- `bonus <- min(bonus, 0.3)`.

**Final** (KB:1334-1340):
- If `total_weight == 0`, return 0.3. This is unreachable.
- `relevance = 0.2 + 0.75 * min(1, matched/total + bonus)`, then `min(1, relevance)`.
- So the range is [0.2, 0.95]. Passing 0.3 needs `matched/total + bonus >= 0.1333…`.

### 2.5 `detect_polarity(from_name, to_name, from_type, to_type)` (CG:62-187)

**Step 1** (CG:64-75): if `lookup_knowledge_base(...)` is non-NULL, return its `polarity`. This is the same lookup, so polarity always comes from the same winning entry.

**Step 2**:
- `from_lower` and `to_lower`. `from_analysis` and `to_analysis` come from `analyze_phrase_polarity` (§2.6).
- Keyword lists:
  - `negative_keywords`: CG:86-91, contains "dead zone".
  - `positive_keywords`: CG:94-98.
  - `mitigation_keywords`: CG:101-105.
- Flags, all TRE substring matches:
  - `to_is_negative` and `to_is_positive` (CG:108-109).
  - `from_is_mitigation` (CG:112).

**Step 3, rules** (first match returns). Only the 10 generated pairs matter:

| pair | rule | line |
|---|---|---|
| R-P | `"-"` always | CG:117-120 |
| A-P | `"-"` if `from_is_mitigation \|\| from_analysis$sentiment == "positive"`, else `"+"` | CG:133-140 |
| P-S | `"+"` if `to_is_negative`, else `"-"` if `to_is_positive`, else `"-"` | CG:143-150 |
| S-I | see below | CG:153-167 |
| I-W | see below | CG:170-183 |
| D-A, W-D, W-R, R-D, R-A | **no rule → `"+"`**. So R-A without a KB hit gets `"+"` and the verb `"enables"` | CG:186 |

The R→S rule (CG:123-130) exists but that pair is not generated.

S-I rule (CG:153-167):
1. Compute `from_is_negative` and `from_is_positive` with the same keyword lists.
2. If `from_analysis$negated`, clear `from_is_negative`. If `to_analysis$negated`, clear `to_is_negative`.
3. Return `"+"` if (neg & neg) or (pos & pos), `"-"` if mixed, and `"-"` otherwise.

I-W rule (CG:170-183):
1. Compute `from_is_negative` and `from_is_positive`. If `from_analysis$negated`, clear `from_is_negative`.
2. Return `"-"` if negative, else `"+"` if positive, else `"-"`.

### 2.6 `analyze_phrase_polarity(phrase)` (KB:1363-1435)
1. `phrase_lower <- tolower(phrase)`. The input is already lowercased by its callers.
2. `reversal_compounds` (KB:1377-1389, 28 patterns, for example `pollut.*reduc`) are tested with **PCRE**. If any matches, return `list(sentiment = "positive", negated = TRUE, base_sentiment = "negative")`.
3. `has_negation`: any of the 19 `negation_patterns` (KB:1367-1373) matches with **PCRE**. They use `\b`, for example `\bno\b`, `\bnon[- ]`, `\breduc`.
4. `has_positive` and `has_negative`: `positive_kw` (KB:1392-1394) and `negative_kw` (KB:1397-1400), with **TRE** substring matching.
5. `base_sent`:
   - positive only → `"positive"`
   - negative only → `"negative"`
   - both → `"mixed"`
   - neither → `"neutral"`
6. Negation flips sentiment: positive → `{negative, TRUE, positive}` and negative → `{positive, TRUE, negative}`. Otherwise return `{base_sent, has_negation, base_sent}`.

Only `sentiment` (for A-P) and `negated` (for S-I and I-W) are consumed.

### Regex engine per call site (port map)

| Engine | Call sites |
|---|---|
| **PCRE** (`perl = TRUE`) | KB:1107-1108 (entry patterns), KB:1175 and 1180 (synonym match), KB:1403 and 1409 (reversal/negation) |
| **TRE** (default) | KB:1212 and 1215 (IDF), KB:1307-1308 (TF-IDF hits), KB:1324-1325 (word bonus), KB:1412-1413 (phrase keywords), CG:108-112, 154-155, 171-172 (polarity keywords), CG:456-457 (loss filter) |
| fixed | none in the live path. `fixed = TRUE` appears only in the dead seed block, CG:867/879 |

Everything is case-sensitive, applied to `tolower`'d text. All patterns and keywords are lowercase (0 uppercase in DB patterns).

---

## 3. Data structures

### `SES_CONNECTION_DB` (KB:47-1012)
- An unnamed R `list` of **137** entries. Each entry is a named list with **exactly 8 fields**, in this order:
  `from_type, to_type, from_pattern, to_pattern, probability, polarity, strength, source`.
  All 137 have the same field set. Each value is length-1 `character`, except `probability`, which is length-1 `numeric`.
- There are no NULLs, factors, functions, NAs or vectors. There are no duplicate entries.
- Counts per pair:

| pair | entries |
|---|---|
| A→P | 31 |
| D→A | 19 |
| I→W | 10 |
| P→S | 28 |
| R→A | 5 |
| R→D | 5 |
| R→P | 8 |
| S→I | 17 |
| W→D | 8 |
| W→R | 6 |

  These are exactly the 10 generated pairs. There are no R→S, P→P or similar entries.
- Polarity: 72 `+`, 65 `-`. Strength: 88 strong, 41 medium, 8 weak.
- Probability ranges from 0.45 to 0.95, with distinct values `0.45 0.5 0.65 0.7 0.75 0.78 0.8 0.82 0.83 0.85 0.87 0.88 0.9 0.92 0.93 0.95`.
- Regex characters used in patterns: only `[a-z0-9]`, `.`, `*`, `?`, `|`.
  - There are **no spaces, backslashes, brackets, parentheses, `+`, `^` or `$`**. 22 patterns use `?`.
  - All patterns compile in PCRE.
  - So there is **no escaping hazard**, and every pattern means the same in Python `re`.
- JSON: `jsonlite::toJSON(db, auto_unbox = TRUE, digits = NA)` round-trips **identically** (verified).
  - **Keep it an ordered array**, because first-wins on ties depends on DB order.
  - Use `digits = NA` (or ≥ 2) so probabilities stay exact decimals.

### `SES_SYNONYM_DB` (KB:1025-1060)
- A **named** list of **17** groups. The names in order are:
  `fishing, aquaculture, pollution, nutrient, habitat, biodiversity, climate, tourism, shipping, development, conservation, decline, increase, management, livelihood, health, food`.
- Each value is an unnamed `character` vector (146 terms in total).
- Two terms are regexes: `econom.*benefit` (livelihood) and `well.?being` (health).
- Seven terms contain spaces: `fish farm`, `shellfish farm`, `mussel farm`, `oyster farm`, `salmon farm`, `shrimp farm`, `sea level`.
- JSON: `toJSON` without auto_unbox gives `{"fishing":["fish",...],...}` and round-trips identically. Group order does not affect results (boolean OR, equal 0.1 increments), but keep it anyway.
- Note: vectors of length 1 would be unboxed by `auto_unbox = TRUE`. None exist, but do not use auto_unbox for this object.

### Function-local constant tables (port verbatim, not in the DB objects)
- `loss_keywords` (CG:440-444)
- polarity keyword lists (CG:86-105)
- `negation_patterns`, `reversal_compounds`, `positive_kw`, `negative_kw` (KB:1367-1400)
- IDF word lists (KB:1200-1208)
- TF-IDF `base_keywords` (KB:1257-1291)

In R source these are written as `"\\bno\\b"`, which means the regex `\bno\b`.

---

## 4. ML on vs off, randomness, locale

### What ML on adds (do NOT port)
- Relevance becomes `0.3*kw + 0.7*ml` (CG:285-320).
- `scoring_method` becomes `"ml"` or `"ml+kb"`. Confidence is raised to max(conf, 4) if rel ≥ 0.85, or max(conf, 3) if rel ≥ 0.7 (CG:502-510).
- Polarity and strength are unaffected.

### How "ML off" really happens at v1.35.6 (important for golden fixtures)
- `MARINESABRES_ML_ENABLED` is read once at `global.R:744`. It gates only the block at `global.R:748-931`.
- But `modules/graphical_ses_ai_classifier.R:7-15`, sourced unconditionally at `global.R:733`, sources `functions/ml_inference.R` and calls `load_ml_model()` regardless of the flag.
- With the flag FALSE, ML stays off only because of what follows:

| torch state | What happens | ML |
|---|---|---|
| torch **installed but not attached** (this machine; nothing before line 733 attaches it; `library(torch)` appears only at `global.R:757`) | `ml_inference.R:29-31` sources `ml_models.R`, which fails at `ml_models.R:51` (`nn_module` not found). The source aborts before `ml_model_available` is defined (`ml_inference.R:272`). **Reproduced** (probe 4: "could not find function nn_module", `exists("ml_model_available") == FALSE`) | off |
| torch **not installed** | `.ml_torch_available` is FALSE (`ml_inference.R:20`), so `ml_model_available()` exists but returns FALSE (`:274-276`) | off |
| torch **attached earlier** by some other path (none found) | `load_ml_model()` would succeed if `models/connection_predictor_best.pt` exists. It does exist locally (git-ignored, `.gitignore:106`) | **on despite the flag** |

- **Recommendation:** generate golden fixtures with the two-file harness (KB + CG, stub `debug_log`/`%||%`), as in `k1b_probe.R`, and assert `!exists("ml_model_available")`. Do not use the full app.

### Randomness
None. There is no RNG, no hashing and no time dependence in the live path (`Sys.time` appears only in the caller attribute).

### Locale and encoding
- `tolower` is used everywhere. In a UTF-8 locale it lowercases non-ASCII (`"ÉTAT Ø"` → `"état ø"`), which matches Python `str.lower()` except for exotic cases (`İ`, final sigma).
- The `gsub("[^a-z ]", "", …)` in the bonus step drops non-ASCII letters. Verified: TRE `[a-z]` does not match `é` here. Python `re.sub(r"[^a-z ]", "", s)` does the same.
- PCRE `\b` in R is ASCII-only (no UCP): `\bno\b` matches `"noé"` in R (probe 2). Python `re` on `str` is Unicode-aware and would NOT match, so **use `re.ASCII` for the PCRE call sites**.
- There is no locale-sensitive sorting. The only sort is numeric (CG:556).

---

## 5. Callers and how suggestions become connections

1. **Trigger.** On advancing to the step whose `type == "connection_review"` (`step_navigation.R:63`), if any elements exist:
   - `all_connections <- generate_connections(rv$elements)` (`:92`). No regional_sea or habitat is passed.
   - The list is truncated to 200 (`:96-105`, never hit), and `attr(..., "generated_at")` is set (`:108`).
   - The result is stored in `rv$suggested_connections`.
2. **Review UI.** `connection_review_tabbed_server(connections_reactive = reactive(rv$suggested_connections), …)` (`ai_isa_assistant_module.R:890-920`):
   - `on_approve` appends the **position index** to `rv$approved_connections` (`:894-901`).
   - `on_reject` removes it with `setdiff` (`:902-907`).
   - `on_amend` overwrites `polarity`, `strength`, `confidence`, `delay`, `delay_years` in place (`:908-919`).
   - "Approve all" sets `approved <- seq_along(suggested)` (`:923-928`).
3. **Finish.** `.do_finish_and_save` (`:967-1018`):
   - `apply_connection_swaps` (`:981-984`).
   - `save_to_project_format(rv, current_data, CONFIDENCE_DEFAULT)` (`:995`, `CONFIDENCE_DEFAULT <- 3` at `constants.R:273`).
4. **Persistence.**
   - `isa_data$connections <- list(suggested = rv$suggested_connections, approved = rv$approved_connections)` (`data_persistence.R:524-527`). This stores the full conn objects plus approved **positions**, so output order is persisted.
   - Then `build_adjacency_matrices(...)` (`data_persistence.R:545-550`, def `:168-381`). For each approved index:
     - The cell value is `paste0(polarity, strength, ":", confidence)`, e.g. `"+strong:4"`. `:delay[:years]` is appended only if delay is non-NA, which never happens here (`:315-339`).
     - The value goes in `matrices[[matrix]][from_index, to_index]`, with the forward-pair remap via `AI_ISA_FORWARD_MATRIX` (`:346-353`) and a bounds check (`:370-377`).
   - **So strength and confidence ARE written. `rationale`, `scoring_method` and relevance are not** (except inside the saved `suggested` list).
5. Wizard elements: see §1. Only `name` matters for scoring.

---

## 6. Porting traps

1. **Mirror floating-point operation order exactly.** Ties decide which 15 survive.
   - Use `(p*0.9)*0.9` for synonym relevance, not `p*0.81`.
   - Accumulate `total_weight` and `matched_weight` sequentially in keyword order, with no `math.fsum`.
   - Add the bonus as repeated `+0.1` (three adds give 0.30000000000000004), then `min(bonus, 0.3)`.
   - Compute `0.2 + 0.75*min(1, ks + bonus)` in that order.
2. **Stable descending sort.** Use `sorted(cands, key=lambda c: -c.relevance)`, or `sort(reverse=True)`, which is also stable in Python. Ties keep (i outer, j inner) order. Then slice `[:15]`.
3. **Inclusive threshold** (`>= 0.3`). The loss filter runs **after** the threshold and **before** the cap.
4. **Strict `>` in the KB scan.** The first DB entry wins ties. Exact uses score `p` and synonym uses score `0.8p`, so a synonym on a high-p entry can beat an exact match (see the Fish farming case). Do not "fix" this by preferring exact.
5. **The synonym branch runs only when exactly one side matched**, and only for the non-matching side. Keep the `if/elif` shape: exact first, else synonym.
6. **Regex semantics.** Use `re.search` (unanchored) everywhere, never `re.match` or `in`.
   - Several "keywords" are regexes: `gear.*restrict`, `anti.?foul`, `ghost.*net`, `econom.*benefit`, `well.?being`.
   - Add `re.ASCII` at least for the `\b` negation patterns. TRE `.` matches newline but PCRE and Python `.` do not; names are single-line, so this is moot.
   - Precompile patterns.
7. **Substring quirks to preserve, not fix:**
   - `ecosystem` gets IDF 0.6 via `system`.
   - The loss filter fires on `reduc` and `lack` anywhere, so "Emission reduction" → "Habitat loss" is skipped.
   - Synonyms used as regexes on the full text (`.synonym_match`) hit inside other words: `mpa` in "impact", `port` in "transport", `ice` in "service", `plan` in "plankton".
   - Multi-word synonyms never hit in the per-word bonus loop but do hit in `.synonym_match`.
8. **The word tokeniser:** `re.sub(r"[^a-z ]", "", lower)` then `re.split(r"\s+", …)`.
   - Keep the `""` token from a leading space. It is harmless, but `re.split` also yields a trailing `""`, which R's strsplit drops. That is harmless too, because `grepl(nonempty, "")` is FALSE.
   - An empty name gives `[]` in R (`strsplit("")` → `character(0)`). In Python `re.split` gives `[""]`. The result is the same: no hits.
9. **`.synonym_match` term split:** `re.split(r"\||\.\*|\.|\?|\*|\+|\(|\)", pattern)`, then strip, then keep `len >= 3`. R `nchar` counts characters, and Python `len` also counts characters.
10. **Polarity fall-through.** D-A, W-D, W-R, R-D and R-A have no rule, so they get `"+"`. R-P always gets `"-"`. With no KB hit, R-A gets `"+"` and the verb "enables". Activities with `-` get the verb "causes" (sic).
11. **Indices are 1-based** (`from_index`, `to_index`). Decide at the boundary whether SESPy stores 0-based, and convert in exactly one place.
12. **Null outputs:** `delay` is always NA and `delay_years` always NA. Emit `None` consistently rather than omitting the keys, if SESPy mirrors the R field set.
13. **Do not port** the following, all dead or unreachable at v1.35.6 with ML off:
    - `.calculate_basic_relevance` (CG:338-387)
    - the inline `.analyze_polarity_phrase` fallback (CG:208-225)
    - the JSON seed block (CG:809-919)
    - the ML branches
14. `rationale` is English verb glue around user-typed names, and R does not translate it. Decide whether SESPy should i18n it, and note that as a known difference if so.
15. **Performance:** R calls `lookup_knowledge_base` three times per candidate (each a 137-entry scan with nested synonym loops). A Python port can memoise per (from, to, types) without changing results.
