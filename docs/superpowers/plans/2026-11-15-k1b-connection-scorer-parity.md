# K1b Connection-Scorer Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The SES Wizard's rule-based connection suggestions become exactly R
v1.35.6's (ML off), and accepted suggestions save R's strength and confidence.

**Architecture:**
- R's connection and synonym databases are exported once to
  `sespy/data/r_kb/ses_connection_db.json` and registered in K1's
  reference-data layer (`override=False`).
- A new pure module, `sespy/r_connection_kb.py`, ports R's KB lookup and
  relevance.
- `sespy/connection_scorer.py` is rewritten on top of it, using R's 10 pairs.
- `ConnectionSuggestion` gains `strength` and integer `confidence`, and its
  old 0..1 field becomes `relevance`.
- The wizard carries strength and confidence to `Connection` and shows them.

**Tech Stack:** Python 3.11+, Shiny for Python 1.7+, pytest, Playwright e2e; R
4.4.1 only for the export and the fixture capture.

**Spec:** `docs/superpowers/specs/2026-11-15-k1b-connection-scorer-parity-design.md`.
Algorithm detail with R file:line references:
`docs/parity/k1b/R_SCORER_NOTES.md`. SESPy current state:
`docs/parity/k1b/SESPY_SCORER_NOTES.md`. Read all three before Task 1.

## Global Constraints

**Versions and pins**
- Release v1.17.0. **No schema bump:** `SCHEMA_VERSION` stays 9.
- R pin stays v1.35.6 (`d1a655a`).

**Parity target**
- R run with ML off, through the two-file harness only:
  - source `data/ses_connection_knowledge_base.R` and
    `modules/ai_isa/connection_generator.R`;
  - stub `debug_log <- function(...) invisible(NULL)` and `%||%`;
  - call `generate_connections(elements)` with no sea and no habitat.
- Parity means equal `(from_type, from_index, to_type, to_index, polarity,
  strength, confidence)` and equal row order. Relevance is compared only as a
  diagnostic, with `abs ≤ 1e-12`.

**Values pinned by the spec**
- Threshold: relevance `>= 0.3` (inclusive). Cap: 15 per pair. No
  deduplication.
- Pairs in this exact order: D-A, A-P, P-S, S-I, I-W, R-P, W-D, W-R, R-D, R-A.
- Confidence: 4 for an exact KB match, 3 otherwise. Strength comes from the
  KB entry, otherwise `"medium"`.

**Regex**
- Every R match is a regex: `grepl`, PCRE or TRE. There are no fixed-string
  matches.
- Several "keywords" are regexes (`gear.*restrict`, `anti.?foul`,
  `well.?being`).
- Python uses `re.search` (unanchored) for every match, **never `in`**, and
  adds `re.ASCII` wherever a pattern contains `\b`.

**Unchanged**
- Claude's pair list (`_CONN_TYPES`, `_VALID_TYPE_PAIRS`) stays as it is,
  including R→S.
- The flip/reverse JS rewrite stays as it is.

**Running the tests**
- Commands are written in their POSIX form. On this Windows machine:
  - run through `micromamba run -n shiny ...`;
  - set `SESPY_R_DATA_DIR=off`;
  - set `PYTHONPATH` to the worktree.
- Never use a bare `python`.

**Before merge**
- Wait for CI's Linux unit and full-app jobs.
- Never use Windows-only tools (`cygpath`) in tests without a fallback.

## Review Focus

1. **Element names with uppercase letters, non-ASCII letters or extra
   spaces** (for example "  Pêche côtière ", "TOURISM") must score and polarise
   exactly as R's `tolower`-then-match does. Test: the Task 3 capture includes
   such names; Task 4 and Task 6 assert parity on them.
2. **Duplicate element names, within a type or across types,** must produce
   R's extra candidates, and each suggestion must map to the right distinct
   element id. Test: Task 6
   `test_duplicate_names_map_to_distinct_ids`.
3. **Large projects** (40 elements per type, so 1,600 candidates per pair)
   must not stall the step-11 transition. Test: Task 6
   `test_scorer_runs_under_two_seconds_for_40_per_type`.
4. **No rule-based row passes 0.3** (for example only welfare and responses
   with unrelated names). The table must show the `wizard.no_suggestions`
   text, and Finish must still work with Claude rows only. Test: Task 7
   `test_no_rule_rows_shows_message_and_finish_works`.
5. **Accepted strength and confidence must survive save, load and
   autosave,** and a v1.16.0 file without them must still load as
   `medium` / 3. Test: Task 7 `test_accepted_strength_confidence_round_trip`.

---

## File map

| File | Change | Task |
|---|---|---|
| `scripts/export_r_connection_db.R` | create | 1 |
| `sespy/data/r_kb/ses_connection_db.json` | create (generated) | 1 |
| `sespy/r_kb.py` | allow-list row, `CONNECTION_DB_NAME`, `Snapshot.connection_db()` | 1 |
| `sespy/r_template_catalogue.py` | `K1B_R_SOURCES`, generated-runtime handling, manifest | 2 |
| `tests/parity/r_source/{ses_connection_knowledge_base.R,connection_generator.R}` | create (copied by sync) | 2 |
| `tests/parity/r_sync.json`, `sespy/data/r_kb/manifest.json`, `docs/parity/R_SYNC.md` | regenerate | 2, 3 |
| `tests/parity/check_live.py` | `check_shipped` covers the generated file | 2 |
| `scripts/capture_k1b_fixtures.R` | create | 3 |
| `tests/parity/r_fixtures/k1b/{connections,lookup,polarity}.json.gz` | create (generated) | 3 |
| `tests/parity/k1b_fixtures.py` | create | 3 |
| `sespy/r_connection_kb.py` | create | 4 |
| `sespy/connection_scorer.py` | rewrite on `r_connection_kb`, R pairs, polarity | 5, 6 |
| `sespy/data_structure.py` | `ConnectionSuggestion` fields | 5 |
| `sespy/claude_backend.py`, `sespy/modules/ai_isa_wizard.py` | rename, accept path, UI, provenance | 5, 7 |
| `sespy/translations/core.json` | help and no-suggestions text (9 languages) | 7 |
| `CHANGELOG.md`, `docs/MANUAL.md`, `README.md`, `sespy/__init__.py` | release | 8 |

---

### Task 1: Export R's connection DB and register it in the reference-data layer

**Files:**
- Create: `scripts/export_r_connection_db.R`,
  `sespy/data/r_kb/ses_connection_db.json`
- Modify: `sespy/r_kb.py` (constants near `:20`, `ALLOW_LIST` near `:37`,
  `Snapshot` near `:157`)
- Test: `tests/test_r_kb.py`

**Interfaces:**
- Produces: `r_kb.CONNECTION_DB_NAME = "ses_connection_db.json"`, and
  `Snapshot.connection_db() -> dict`, which returns the JSON object below. The
  vendored load validates the file at import, as for K1's files.

The JSON shape (spec D8). Keys appear in this order. The integer `version` is
required: without it, `version_major()` raises at import.

```json
{"version": 1, "r_tag": "v1.35.6", "r_commit": "d1a655a",
 "connection_db": [ {<entry fields exactly as in SES_CONNECTION_DB, KB order>} ],
 "synonym_db": {"<group>": ["term", ...]} }
```

- [ ] **Step 1: Write the failing tests** in `tests/test_r_kb.py`:

```python
def test_connection_db_vendored_and_valid():
    db = r_kb.VENDORED.connection_db()
    assert db["version"] == 1 and db["r_tag"] == "v1.35.6"
    assert isinstance(db["connection_db"], list) and len(db["connection_db"]) == 137
    assert isinstance(db["synonym_db"], dict) and len(db["synonym_db"]) == 17
    assert sum(len(v) for v in db["synonym_db"].values()) == 146

def test_connection_db_row_is_vendored_only():
    row = r_kb._row(r_kb.CONNECTION_DB_NAME)
    assert row.override is False
    assert row.containers == {"connection_db": list, "synonym_db": dict}
    assert r_kb.VENDORED.files[r_kb.CONNECTION_DB_NAME].source == "vendored"
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `pytest tests/test_r_kb.py -k connection_db -v`
Expected: FAIL, because `CONNECTION_DB_NAME` is not defined.

- [ ] **Step 3: Write `scripts/export_r_connection_db.R`**
- Usage: `Rscript scripts/export_r_connection_db.R <R_APP>`.
- Guard: the R checkout must be at the exact tag v1.35.6. Copy the guard
  block from `scripts/capture_k1_fixtures.R`.
- Load: `source()` only `data/ses_connection_knowledge_base.R`.
- Write: `jsonlite::write_json(..., auto_unbox = TRUE, pretty = 1, digits = NA)`
  to `sespy/data/r_kb/ses_connection_db.json`, resolved from the script's own
  location.
- Shape: `connection_db` stays an unnamed array in KB order, and every
  pattern string is copied verbatim.
- Run it once, and commit both the script and its output.

- [ ] **Step 4: Register the file in `sespy/r_kb.py`**
- Add `CONNECTION_DB_NAME`.
- Add an `AllowRow`:
  - `required_keys=("version", "r_tag", "connection_db", "synonym_db")`;
  - `min_counts={"connection_db": 137, "synonym_db": 17}`;
  - `containers={"connection_db": list, "synonym_db": dict}`;
  - `version_key="version"`, `override=False`.
- Add `Snapshot.connection_db()`.
- `_load_vendored` (`r_kb.py:191-222`) raises unless every allow-listed file's
  hash is in `manifest.json`. **Do not commit Task 1 alone:** Task 2's sync
  writes the manifest entry, so Task 2's steps continue in the same working
  tree and the two tasks share one commit and one review.

- [ ] **Step 5: Continue with Task 2.** Commit and test at Task 2's Step 6.

### Task 2: Pin both R sources and the generated JSON in the sync (continues Task 1; one commit)

**Files:**
- Modify: `sespy/r_template_catalogue.py` (`K1_R_SOURCES` near `:74`,
  `RUNTIME_INPUTS` near `:80`, `INPUTS` near `:94`, the manifest build near
  `:464`), `tests/parity/check_live.py` (`check_shipped`, `:56`),
  `tests/test_k1_sync.py` (`:74-85`, `:137-143`), `tests/test_r_kb.py`
  (`:129`), `docs/parity/R_SYNC.md`
- Create (generated by the sync): `tests/parity/r_source/ses_connection_knowledge_base.R`,
  `tests/parity/r_source/connection_generator.R`

**Interfaces:**
- Consumes: Task 1's file.
- Produces:
  - `K1B_R_SOURCES = ("data/ses_connection_knowledge_base.R",
    "modules/ai_isa/connection_generator.R")`, copied to
    `tests/parity/r_source/<basename>` and pinned with `sha256_text_norm`;
  - `GENERATED_RUNTIME: dict[str, str] = {"scripts/export_r_connection_db.R":
    "sespy/data/r_kb/ses_connection_db.json"}`. The generated file is read
    from the repo in both sync modes. It is hashed into the manifest and the
    pin, and its `r_tag` must equal the pinned tag, like `LOCAL_PINS`.

- [ ] **Step 1: Write the failing tests** in `tests/test_k1_sync.py`:

```python
def test_k1b_sources_pinned():
    assert C.K1B_R_SOURCES == ("data/ses_connection_knowledge_base.R",
                               "modules/ai_isa/connection_generator.R")
    pin = json.loads((ROOT / C.PIN_PATH).read_text(encoding="utf-8"))
    for r in C.K1B_R_SOURCES:
        assert f"tests/parity/r_source/{r.rsplit('/', 1)[-1]}" in pin["files"]
    assert "sespy/data/r_kb/ses_connection_db.json" in pin["files"]

def test_manifest_lists_connection_db():
    man = json.loads((ROOT / C.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert "ses_connection_db.json" in json.dumps(man)

def test_generated_runtime_tag_must_match_pin(tmp_path):
    # Copy the repo inputs into tmp_path (as the existing fixture-mode sync
    # tests do), rewrite the copied ses_connection_db.json with
    # r_tag "v1.34.2", run the sync in check mode on tmp_path.
    result = run_sync_check(tmp_path)          # the existing tests' helper
    assert result.code == 1
    assert any("ses_connection_db.json" in m and "v1.34.2" in m for m in result.messages)
```

Also update the existing exact-set assertions (`:74-85`, `:137-143`,
`test_r_kb.py:129`) to include the new entries.

- [ ] **Step 2: Run them and confirm they fail**

Run: `pytest tests/test_k1_sync.py tests/test_r_kb.py -v`
Expected: FAIL on the new tests.

- [ ] **Step 3: Implement**
- Add `K1B_R_SOURCES` to the `INPUTS` comprehension.
- Add `GENERATED_RUNTIME`, read from `repo_root` in both modes, include it in
  the manifest's runtime hashes and the pin, and add the r_tag check.
- Make `check_live.check_shipped` iterate `RUNTIME_INPUTS.values()` plus
  `GENERATED_RUNTIME.values()`.

- [ ] **Step 4: Regenerate**
- Run the sync in git mode against the R checkout at v1.35.6, then run it in
  check mode.
- This rewrites `r_sync.json`, `manifest.json`, the `R_SYNC.md` table and the
  two `r_source` copies.
- Add one R_SYNC.md prose row that says the JSON is generated by
  `scripts/export_r_connection_db.R`.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `pytest tests/test_k1_sync.py tests/test_r_kb.py tests/test_r_kb_registry.py tests/test_r_template_catalogue.py tests/parity/test_check_live.py -v`
Expected: PASS, including Task 1's tests. The sync's check mode exits 0.
MosaicSES imports `r_kb` too; Task 8 gates it.

- [ ] **Step 6: Commit (Tasks 1 and 2 together)**: `feat(k1b): vendor and pin R's connection DB; pin the KB and generator sources`.

### Task 3: Capture R's golden fixtures (two-file harness)

**Files:**
- Create: `scripts/capture_k1b_fixtures.R`,
  `tests/parity/r_fixtures/k1b/{connections,lookup,polarity}.json.gz`,
  `tests/parity/k1b_fixtures.py`
- Modify: `sespy/r_template_catalogue.py` (`LOCAL_PINS` gains the 3
  fixtures), the pin and `R_SYNC.md` (regenerated)
- Test: `tests/parity/test_k1b_fixture_shape.py`

**Interfaces:**
- Produces: `load_k1b_fixture(name) -> dict` for `name` in
  `("connections", "lookup", "polarity")`, mirroring `k1_fixtures.py`. Each
  fixture has `r_tag` and `r_commit`. The contents:
  - **`connections`:** `{"cases": [{"id": str, "elements": {<7 R keys>: [name,
    ...]}, "rows": [{from_type, from_index, from_name, to_type, to_index,
    to_name, polarity, strength, confidence, scoring_method, rationale,
    relevance}]}]}`. The rows are R's output, in order. `relevance` is taken
    from the harness's candidate list before R drops it; wrap
    `generate_smart_connections` to record it.
  - **`lookup`:** `{"rows": [{from_name, from_type, to_name, to_type,
    match: null | {polarity, strength, match_quality, probability},
    relevance}]}`.
  - **`polarity`:** `{"rows": [{from_name, to_name, from_type, to_type,
    polarity}]}`.

- [ ] **Step 1: Write the failing shape test** `test_k1b_fixture_shape.py`:

```python
def test_connections_cases():
    fx = load_k1b_fixture("connections")
    assert fx["r_tag"] == "v1.35.6"
    ids = [c["id"] for c in fx["cases"]]
    assert len(ids) == 10 and len(set(ids)) == 10      # 7 templates + 3 wizard cases
    worked = next(c for c in fx["cases"] if c["id"] == "wizard_worked_example")
    assert len(worked["rows"]) == 16                   # R notes §1 worked example

def test_lookup_covers_all_match_kinds():
    q = {r["match"]["match_quality"] if r["match"] else None
         for r in load_k1b_fixture("lookup")["rows"]}
    assert q == {"exact", "synonym", None}
```

- [ ] **Step 2: Run it and confirm it fails** (the fixtures don't exist yet).

- [ ] **Step 3: Write `scripts/capture_k1b_fixtures.R`** (usage `<R_APP>`,
  with the same tag and untouched-source guards as
  `capture_k1_fixtures.R`).
- **Harness:** source only the two files, with the stubs from Global
  Constraints.
- **Cases:**
  - The 7 P2 templates: build `elements` from each R template JSON
    (`data/<Stem>_SES_Template.json`), with the names per category in
    template order.
  - `wizard_worked_example`: the R notes §1 element list.
  - `wizard_stress`: 20 elements in A and P so that pairs exceed the cap,
    names that tie on relevance at the 15th place, double-negative pairs, and
    one pair whose names hit only synonyms.
  - `wizard_text_quirks`: uppercase, non-ASCII ("Pêche côtière"),
    leading and trailing spaces, duplicate names within and across types, and
    the substring traps "impact" (mpa), "service" (ice) and "ecosystem"
    (system).
- **Lookup rows:** every from/to name pair from `wizard_stress` and
  `wizard_text_quirks`, at least 200 rows.
- **Polarity rows:** at least 150 rows. Cover every pair in the 10, and every
  keyword, negation and reversal rule named in R notes §2.5.
- Write gzipped JSON with `digits = NA`, so doubles round-trip.
- Run it once, then add the 3 fixtures to `LOCAL_PINS`, re-run the sync and
  commit.

- [ ] **Step 4: Run the shape test and the sync check, and confirm they pass**

Run: `pytest tests/parity/test_k1b_fixture_shape.py tests/test_k1_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**: `test(k1b): capture R's connection goldens, lookup and polarity tables`.

### Task 4: Port KB lookup, synonyms, IDF weights and relevance (`sespy/r_connection_kb.py`)

**Files:**
- Create: `sespy/r_connection_kb.py`, `tests/test_r_connection_kb.py`

**Interfaces:**
- Consumes: `Snapshot.connection_db()` (Task 1), and the `lookup` fixture
  (Task 3).
- Produces (all pure; `db` is the JSON object from Task 1):

```python
@dataclass(frozen=True)
class KBMatch:
    polarity: str                     # "+" | "-"
    strength: str                     # "weak" | "medium" | "strong"
    probability: float
    match_quality: Literal["exact", "synonym"]

def lookup_knowledge_base(from_name: str, from_type: str, to_name: str,
                          to_type: str, db: dict) -> KBMatch | None: ...
def calculate_enhanced_relevance(from_name: str, to_name: str, from_type: str,
                                 to_type: str, db: dict) -> float: ...
```

Types are R's plural slugs ("drivers", ..., "responses"), the values of
`connection_scorer._TYPE_TO_SLUG`. Private helpers mirror R:
`_synonym_match`, `_keyword_idf_weight`.

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("row", load_k1b_fixture("lookup")["rows"], ids=...)
def test_lookup_matches_r(row):
    got = lookup_knowledge_base(row["from_name"], row["from_type"],
                                row["to_name"], row["to_type"], DB)
    want = row["match"]
    assert (got is None) == (want is None)
    if want:
        assert (got.polarity, got.strength, got.match_quality) == \
               (want["polarity"], want["strength"], want["match_quality"])
        assert got.probability == pytest.approx(want["probability"], abs=1e-12)

@pytest.mark.parametrize("row", load_k1b_fixture("lookup")["rows"], ids=...)
def test_relevance_matches_r(row):
    assert calculate_enhanced_relevance(row["from_name"], row["to_name"],
        row["from_type"], row["to_type"], DB) == pytest.approx(row["relevance"], abs=1e-12)

def test_synonym_hit_beats_weak_exact_hit():
    # R notes §2: best entry scores synonym matches at 0.8·p; ties go to the
    # first entry (strict >). The case R verified: Fish farming -> Chemical pollution.
    m = lookup_knowledge_base("Fish farming", "activities", "Chemical pollution", "pressures", DB)
    # R notes §2.1: the exact entry (p=0.50, "+ weak") loses to a synonym hit
    # on an entry with p=0.93 ("+ strong").
    assert m is not None and (m.match_quality, m.strength, m.polarity) == ("synonym", "strong", "+")
    assert calculate_enhanced_relevance("Fish farming", "Chemical pollution",
        "activities", "pressures", DB) == pytest.approx(0.7533, abs=5e-5)
```

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement**, following R notes §2 exactly:
- **Matching:**
  - lowercase with `str.lower()`;
  - every pattern and keyword with `re.search` (unanchored; `re.ASCII` where
    a pattern contains `\b`), never `in`;
  - in the KB scan, the synonym branch runs only when exactly one side
    matched exactly (R notes §6.5).
- **Arithmetic:** keep R's operation order, including the synonym case,
  which is `(p*0.9)*0.9` and not `p*0.81`.
- **Best entry:** strict `>` over KB order.
- **Keyword lists for the no-match path:** use R's lists from the vendored
  data, or from `connection_keywords.json` if R's lists live in
  `connection_generator.R`.
  - If `connection_keywords.json` differs from R's lists, regenerate it from
    the pinned `tests/parity/r_source/connection_generator.R` and say so in
    the commit.
  - The lookup fixture is the arbiter.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_r_connection_kb.py -v`
Expected: PASS on every fixture row.

- [ ] **Step 5: Commit**: `feat(k1b): port R's KB lookup, synonym match and enhanced relevance`.

### Task 5: `ConnectionSuggestion` fields and R polarity

**Files:**
- Modify: `sespy/data_structure.py:793-801`,
  `sespy/connection_scorer.py` (`detect_polarity`, `_analyze_polarity_phrase`,
  `_select_verb`), `sespy/claude_backend.py` (every
  `ConnectionSuggestion(...)` and `.confidence` read),
  `sespy/modules/ai_isa_wizard.py` (`_dedup_accepted` `:500-527` and every
  `.confidence` read), and the tests that construct or read suggestions
  (SESPY notes §3 lists them; find the rest with
  `grep -rn "ConnectionSuggestion(\|\.confidence" sespy tests`)
- Test: `tests/test_connection_polarity.py` (new), `tests/test_wizard.py`

**Interfaces:**
- Produces:

```python
@dataclass
class ConnectionSuggestion:
    source: str
    target: str
    polarity: str            # "+" | "-"
    relevance: float         # 0..1 (rule-based: R's relevance; Claude: its score)
    rationale: str
    strength: str = "medium" # "weak" | "medium" | "strong"
    confidence: int = 3      # 1..5; rule-based: 4 exact KB match, else 3
```

- `connection_scorer.detect_polarity(from_name: str, to_name: str,
  from_type: str, to_type: str, db: dict) -> str` returns the KB entry's
  polarity when `lookup_knowledge_base` matches, otherwise R's keyword rules
  (R notes §2.5).
- `_dedup_accepted` keeps its contract on `relevance`: the higher one wins,
  and a tie goes to the first row, which is the rule-based one.

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("row", load_k1b_fixture("polarity")["rows"], ids=...)
def test_polarity_matches_r(row):
    assert detect_polarity(row["from_name"], row["to_name"], row["from_type"],
                           row["to_type"], DB) == row["polarity"]

def test_verbs_match_r_table():
    want = {("drivers", "+"): "drives", ("drivers", "-"): "drives",
            ("activities", "+"): "increases", ("activities", "-"): "causes",
            ("pressures", "+"): "increases", ("pressures", "-"): "decreases",
            ("states", "+"): "impacts", ("states", "-"): "impacts",
            ("impacts", "+"): "increases", ("impacts", "-"): "reduces",
            ("responses", "+"): "enables", ("responses", "-"): "restricts",
            ("welfare", "+"): "motivates", ("welfare", "-"): "reduces"}
    assert {k: _select_verb(*k) for k in want} == want

def test_dedup_on_relevance_tie_keeps_rule_row():
    rule = ConnectionSuggestion("a", "b", "+", 0.7, "r", "strong", 4)
    claude = ConnectionSuggestion("a", "b", "+", 0.7, "c")
    kept, discarded, overwritten = _dedup_accepted([rule, claude])
    assert kept == [rule] and (discarded, overwritten) == (1, 0)
```

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement**
- **Rename:** do it everywhere. No `confidence` alias (spec §6 leaves this to
  the builder; a clean break is chosen here).
- **Claude rows:** put Claude's score in `relevance` and keep the defaults
  (spec D5).
- **`_select_verb`:** fix it only if it disagrees with the table.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_connection_polarity.py tests/test_wizard.py tests/test_claude_backend.py -v`, then the full unit suite.
Expected: PASS. Old scorer value tests may fail now; Task 6 re-derives them.
Mark them `xfail(strict=True, reason="re-derived in K1b Task 6")` rather than
deleting them here.

- [ ] **Step 5: Commit**: `refactor(k1b): ConnectionSuggestion relevance/strength/confidence; R polarity`.

### Task 6: Rule-based scorer on R's 10 pairs

**Files:**
- Modify: `sespy/connection_scorer.py` (`_generate_smart_connections`,
  `suggest_connections`), `sespy/wizard.py:78-86`
- Test: `tests/test_connection_scorer.py` (re-derive), `tests/test_link_rules.py:235-243`

**Interfaces:**
- Consumes: Tasks 4 and 5.
- Produces:
  - `connection_scorer.R_CONNECTION_PAIRS: tuple[tuple[str, str], ...]`, the
    10 `(from_slug, to_slug)` pairs in spec order;
  - `suggest_connections(state: WizardState, snapshot: Snapshot | None = None)
    -> list[ConnectionSuggestion]`. A `None` snapshot means
    `r_kb.VENDORED`. `sespy.wizard.suggest_connections` gets the same
    signature and passes `snapshot` through.

- [ ] **Step 1: Write the failing tests:**

```python
@pytest.mark.parametrize("case", load_k1b_fixture("connections")["cases"], ids=lambda c: c["id"])
def test_matches_r_generate_connections(case):
    state, ids = _state_from_case(case)   # ids[(type, 1-based index)] -> element id
    got = suggest_connections(state)
    want = [(ids[(r["from_type"], r["from_index"])], ids[(r["to_type"], r["to_index"])],
             r["polarity"], r["strength"], int(r["confidence"])) for r in case["rows"]]
    assert [(s.source, s.target, s.polarity, s.strength, s.confidence) for s in got] == want
    for s, r in zip(got, case["rows"]):
        assert s.relevance == pytest.approx(r["relevance"], abs=1e-12)

def test_pairs_are_rs_ten_in_order():
    assert [f"{a[0]}-{b[0]}".upper() for a, b in R_CONNECTION_PAIRS] == \
        ["D-A", "A-P", "P-S", "S-I", "I-W", "R-P", "W-D", "W-R", "R-D", "R-A"]

def test_duplicate_names_map_to_distinct_ids(): ...   # two "Tourism" activities → two source ids
def test_scorer_runs_under_two_seconds_for_40_per_type(): ...  # time.perf_counter() < 2.0
```

- Move `test_link_rules.py:243`'s R→S assertion to the Claude pair list, or
  drop it with a comment citing spec D2.
- Remove the `xfail` marks from Task 5. Re-derive or delete each old value
  test so that none asserts 0.3 / 0.6 / 0.9 / 0.5.
- `_state_from_case` builds one `Element` per fixture name. It uses SESPy's
  type for each R key (via `ELEMENT_TYPE_MAP`) and a deterministic id such as
  `f"{type}-{index}"`.

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement**
- Follow R notes §1 steps 1–12.
- Group elements by slug and preserve their order in `state.elements`. That
  order is R's element order.
- Skip a pair when either side is empty.
- Generate candidates in (i, j) order.
- Selection:
  - inclusive threshold;
  - double-negative filter with R's `loss_keywords`, each tested with
    `re.search` on the lowercased name;
  - stable sort descending (`sorted(..., key=-relevance)` is stable);
  - `[:15]`.
- `confidence` is 4 when `match_quality == "exact"`, else 3. `strength` is
  `match.strength` when there is a match, else `"medium"`.
- The rationale is `f"{from_label} {verb} {to_label}"`.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_connection_scorer.py tests/test_link_rules.py -v`, then the full unit suite.
Expected: PASS. Every golden case matches.

- [ ] **Step 5: Commit**: `feat(k1b): rule-based scorer matches R's generate_connections (10 pairs)`.

### Task 7: Wizard — provenance, accept path, table and help text

**Files:**
- Modify: `sespy/modules/ai_isa_wizard.py` (step-11 call `:1089-1090`,
  `_on_finish` `:1371-1378`, `_render_suggestions_table` `:335-400`, help
  notes `:435`, `:484`), `sespy/translations/core.json`
  (`wizard.confidence_help_rules` `:2863`, `wizard.confidence_help_claude`
  `:2874`, `wizard.no_suggestions` `:2940`, plus new column keys),
  `docs/MANUAL.md:148,150`
- Test: `tests/test_wizard.py`, `tests/test_wizard_confidence_help.py`,
  `tests/test_wizard_e2e.py`

**Interfaces:**
- Consumes: Task 6's `suggest_connections(state, snapshot)`, and the wizard's
  session `snap` (`:623`) and `reference_reads`.
- Produces:
  - At step-11 entry: `r_kb.add_reads(reference_reads,
    (r_kb.CONNECTION_DB_NAME,))`, then `suggest_connections(state, snap)`.
  - `_on_finish` builds `Connection(source, target, polarity,
    strength=s.strength, confidence=s.confidence)`. Flip and reverse keep
    both. The rationale is not saved.
  - The rule-based table columns are `#`, Source, Target, Polarity, Reverse,
    **Strength**, **Confidence**, Rationale, Accept. The Claude table relabels
    its 0..1 column as **Score**. New keys: `wizard.col_strength`,
    `wizard.col_confidence`, `wizard.col_score`, in 9 languages.

- [ ] **Step 1: Write the failing tests:**

```python
def test_accept_writes_strength_and_confidence(): ...      # Finish -> Connection(strength="strong", confidence=4)
def test_flip_and_reverse_keep_strength_confidence(): ...
def test_step11_records_connection_db_read(): ...          # metadata.reference_data has ses_connection_db.json
def test_rule_table_shows_strength_and_confidence_columns(): ...
def test_claude_table_labels_score(): ...
def test_no_rule_rows_shows_message_and_finish_works(): ...   # Review Focus 4
def test_accepted_strength_confidence_round_trip(tmp_path): ...  # Review Focus 5: save/load/autosave; v1.16 file -> medium/3
```

- Rewrite `test_wizard_confidence_help.py:60-68` to assert the new text: an
  exact KB match gives 4, a synonym or keyword match gives 3, and strength
  comes from the KB.

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement.**
- **Help text (`wizard.confidence_help_rules`):** English first, then the
  other 8 languages, in the file's existing style. Exact English copy:
  "Strength and confidence come from R's connection knowledge base: an exact
  match gives confidence 4, a synonym or keyword match gives 3; strength is
  the knowledge base's, otherwise medium."
- **`wizard.no_suggestions`:** drop the SP3/SP4 backend wording.
- **MANUAL.md lines 148 and 150:** describe R-matched suggestions and the new
  columns.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `pytest tests/test_wizard.py tests/test_wizard_confidence_help.py -v`, then the full unit suite. Then run `tests/test_wizard_e2e.py` alone. If its fixtures no longer yield a rule-based row, change the fixture elements, not the scorer (spec §5.6).
Expected: PASS.

- [ ] **Step 5: Commit**: `feat(k1b): wizard saves R strength/confidence, shows them, records the DB read`.

### Task 8: Release v1.17.0 and gates

**Files:**
- Modify: `sespy/__init__.py` (`__version__ = "1.17.0"`), `CHANGELOG.md`,
  `docs/MANUAL.md` (version line), `README.md` (test counts), and docs
  screenshots via `tests/make_docs_screenshots.py` if the wizard table
  appears in them

- [ ] **Step 1: Write the CHANGELOG `[1.17.0]` entry** (spec §7):
- **Added:** R-matched rule-based suggestions; the vendored connection DB.
- **Changed:**
  - suggestions and their order now match R;
  - strength and confidence are saved;
  - R→S is no longer a rule-based suggestion, though Claude still proposes it;
  - the table columns.
- **Known differences:** the flip/reverse rewrite uses generic translated
  verbs.
- **Deferred.**
- **Rollback:** a plain redeploy of v1.16.0. No schema change.

- [ ] **Step 2: Run the gates, one at a time, on an idle machine:**
- **Full unit suite:** expect 0 failures.
- **Full e2e** (`tests/run_e2e.py`): expect all pass. Rerun a lone timeout
  alone before calling it a failure.
- **MosaicSES gate:** unit + e2e with `PYTHONPATH=<K1b tree>;<MosaicSES clean
  worktree>`. Baseline every red against SESPy v1.16.0, and repeat
  flaky-looking ones per version.
- **Sync check mode:** exit 0.
- **`ruff check .`:** no increase over v1.16.0's 53.

- [ ] **Step 3: Commit**: `docs(k1b): 1.17.0 release notes, manual, version`.

- [ ] **Step 4: Open the PR, then wait for CI's Linux unit and full-app jobs
  before merge.** The release itself (merge, tag, deploy, post-deploy checks)
  follows K1's runbook in the user's hands.
