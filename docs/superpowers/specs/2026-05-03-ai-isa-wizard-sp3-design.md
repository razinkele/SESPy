# AI-ISA Wizard SP3: Connection Scoring Backend — Design

Status: **Draft** — design phase, not yet implemented.
**Sub-project context:** SP3 of 4 in the AI-Assisted SES Creation series. SP1 shipped 2026-05-01 (commit `dfedd28`); SP2 shipped 2026-05-02 (commit `3c18fd8`); SP4 (optional Claude API backend, switchable via setting) follows. SP3 fills SP1's stub `def suggest_connections(state) -> []` (sespy/wizard.py:92) with a real rule-based scoring backend ported from R's `modules/ai_isa/connection_generator.R` (1009 LOC).

---

## 1. Goal & scope

Replace SP1's empty-list stub with a deterministic, offline, rule-based connection-scoring backend. SP3 is a **backend swap** — no wizard renderer, state-machine, or UI changes. Step 11 (connection_review) in the SP1 wizard already renders whatever `suggest_connections(state)` returns; SP3 makes it return real suggestions.

**Source of truth for all algorithm and keyword data:**
`..\SESToolbox\MarineSABRES_SES_Shiny\modules\ai_isa\connection_generator.R` (sibling repo to SESPy):
- Lines 62–187: `detect_polarity()` — per-pair polarity classifier with precomputed per-name signals (the KB-lookup branch at lines 63–75 is dropped per the rule-based-only choice).
- Lines 198–226: `.analyze_polarity_phrase()` — negation-regex + reversal-compounds analysis (returns `(sentiment, negated)`).
- Lines 264–323: `calculate_relevance()` — outer scoring orchestrator (KB-lookup branch dropped at lines ~270–283; ML scoring branch dropped at lines 284–309; basic-relevance branch ported).
- Lines 338–387: `.calculate_basic_relevance()` — keyword-count → 0.3/0.6/0.9 scoring (0 matches → 0.3 floor at line 384; 0.5 default for unknown type-pair at line 376).
- Lines 436–574: `generate_smart_connections()` — per-pair generator with the double-negative filter (loss-keyword definition at lines 440–444; filter check at lines 454–462; verb selection at lines 513–529).
- Lines 755–1001: `generate_connections()` — top-level orchestrator over the 10 connection types with `MAX_PER_TYPE=15` and `MIN_RELEVANCE=0.3` (constants at lines 757–758).

**In scope (Feature A only — connection generation):**
- Per-pair polarity + relevance scoring covering all 10 DAPSI(W)R(M) connection types.
- Per-pair polarity dispatch (R lines 62–187) using precomputed per-name signals (mitigation flag, positive/negative impact-keyword hits, negation flag from `.analyze_polarity_phrase`). KB-lookup and ML branches dropped per scope decision.
- Threshold filtering at `MIN_RELEVANCE=0.3` (with R's 0.3 floor → every cross-product pair survives by construction; per-type cap at 15 is the effective filter).
- Double-negative filter (drops `(loss_X, loss_Y)` cross-pairs using a dedicated `loss_keywords` list, distinct from polarity's `negative_keywords`).
- The full `suggest_connections(state)` function as the SP3 contract — same signature SP1 stubbed and SP4 will replace.
- JSON-stored keyword data with eager Python loader (matches SP2 pattern).

**Out of scope (Feature B — deferred to SP3.5+):**
- Country-aware governance suggestions (`.get_governance_elements_hardcoded` in `ai_isa_knowledge_base.R` — HELCOM/OSPAR/Barcelona/Arctic-Council element name suggestions).
- Country-aware socioeconomic suggestions (`.get_socioeconomic_elements_hardcoded` in `ai_isa_knowledge_base.R` — coastal_dependent / fishing_nations / shipping_nations groups).
- Element name suggestions in general (Feature B is about helping the user *name* elements; SP3 takes already-named elements and scores connections between them).

**Out of scope (deferred to SP4+):**
- Knowledge-base seed connections (R's `SES_CONNECTION_DB` lookup at `connection_generator.R` lines 803–919).
- ML-model scoring (R's `ml_inference.R` hook at `connection_generator.R` lines 284–309).
- Claude API backend — SP4.
- i18n for rationale strings (English-only verbs).

### Decisions baked in (from brainstorming, 2026-05-03)

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Feature A only (connection generation) | Feature B (element-name suggestions) is independent — different R helpers, different UI surface; clean to defer. |
| Scoring layers | Rule-based only | Skip JSON KB lookup and ML hook. Keeps SP3 deterministic, offline, and 1-file-of-data + 1-file-of-algorithm. SP4 can layer KB/ML on top via the same contract. |
| Connection types | All 10 (D→A, A→P, P→S, S→I, I→W, R→{P,D,A}, W→{D,R}) | R provides 9 keyword lists verbatim; `welfare_drivers` is hand-curated by SP3 because R's `connection_keywords` list omits it (see §3). The 10 type-pair branches in `_CONN_TYPES` are otherwise R-faithful. |
| File location | `sespy/connection_scorer.py` | Single-file at package root, mirrors SP2's `regional_seas.py`. No sub-package. |
| Thresholds | `MAX_PER_TYPE=15`, `MIN_RELEVANCE=0.3` verbatim | R's tuned values; no reason to deviate. |
| UI text | Keep element IDs in `source`/`target`; leave SP1 renderer alone | SP3 is a pure backend swap. The wizard's `connection_review` renderer already names both elements via the rationale field. |
| Confidence semantics | Direct passthrough: `confidence = relevance_score` | One of `{0.3, 0.6, 0.9}` (plus a defensive `0.5` for unknown type-pairs — see §5; schema test pins all 10 pairs present so `0.5` doesn't fire in practice). R's `.calculate_basic_relevance` returns `0.3` for 0 keyword matches, `0.6` for 1 match, `0.9` for 2+ matches — the 0.3 floor means every pair passes `MIN_RELEVANCE=0.3` by construction; per-type cap at 15 is the real filter. Downstream `Connection.confidence` (int 1-5) maps via `int(round(c*4))+1` → `{2, 3, 5}` (note: `round(0.9*4)=4`, so 0.9 → 5; the int range is non-contiguous by design — pinned by a unit test on `Connection.from_suggestion` if/when SP4 implements that conversion). Faithful to R; preserves the keyword-count gradient end-to-end. |
| Data storage | JSON + Python loader (mirrors SP2) | `sespy/connection_keywords.json` + `sespy/connection_scorer.py`. ~300 LOC JSON + ~450 LOC Python (algorithm + helpers + module-level regex constants). Same eager-load discipline as `regional_seas.py`. |

---

## 2. File organization

**New files (3):**
- `sespy/connection_keywords.json` (~300 LOC) — `connection_types` (10 keyword lists per connection-type pair) + `polarity_signals` (4 word sets: negative, positive, mitigation, loss).
- `sespy/connection_scorer.py` (~450 LOC) — pure-Python algorithm. No Shiny imports. Eager `_KW = _load_keywords()` at module import. Module-level `_REVERSAL_COMPOUNDS` and `_NEGATION_PATTERNS` regex constants (algorithm-shape, not data — see §5).
- `tests/test_connection_scorer.py` (~320 LOC) — 33 unit tests across 5 groups.

**Modified files (4):**
- `sespy/data_structure.py` — accept the relocated `ELEMENT_TYPE_MAP` (moved from `wizard.py`). New top-of-file constant; no other change. See §6.
- `sespy/wizard.py` — replace SP1's stub at line 92 with delegation to `connection_scorer.suggest_connections`. Remove the local `ELEMENT_TYPE_MAP` definition; re-export from `data_structure` so SP1 import sites keep working.
- `tests/test_wizard.py` — rename `test_suggest_connections_stub_returns_empty` (line 62) to `test_suggest_connections_empty_state_returns_empty`. Narrower name; richer behavioral coverage moves to `test_connection_scorer.py`.
- `pyproject.toml` — add `[build-system]`, `[tool.setuptools.packages.find]`, and `[tool.setuptools.package-data]` entries so `sespy/*.json` files (both SP2's `regional_seas.json` and SP3's new `connection_keywords.json`) ship in installed wheels. **This is a latent SP2 hazard fixed in passing**: today's `pyproject.toml` has no `[build-system]` table at all (relies on PEP 517's legacy fallback to `setuptools.build_meta:__legacy__`) and no package-data declaration, so SP2's eager `_load_kb()` already fails on `pip install`; SP3 brings the fix in scope because the same hazard would block SP3, and a single coordinated config change covers both. Concretely (~10 LOC of TOML):

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["sespy*"]

[tool.setuptools.package-data]
sespy = ["*.json"]
```

(setuptools `>=68` is chosen over `>=61` to avoid known historical edge cases with `package-data` honoring under PEP 517 builds. The `[tool.setuptools.packages.find]` block uses the implicit `where = ["."]` because SESPy uses a flat layout — `sespy/` lives at the repo root. If a future refactor adopts `src/` layout, the `where` key must be added explicitly.)

**Pattern reference:** SP3 mirrors SP2's `regional_seas.json + regional_seas.py + test_regional_seas.py` shape exactly. Same `Path(__file__).parent` resolution, same `_load_X()` private helper, same module-scope `_X = _load_X()` eager initialization.

**Dependencies:** None new. Pure-Python: `re`, `json`, `dataclasses`, plus existing `sespy.data_structure.{WizardState, ConnectionSuggestion, Element, ELEMENT_TYPE_MAP}` (the last item is the relocated constant).

**Identifier stability contract.** Connection-type slug keys (`drivers_activities`, `activities_pressures`, `pressures_states`, `states_impacts`, `impacts_welfare`, `responses_pressures`, `responses_drivers`, `responses_activities`, `welfare_drivers`, `welfare_responses`) are **stable identifiers** — slug shape is `f"{from_slug}_{to_slug}"` (plural underscore-joined, matching R's `paste(from_type, to_type, sep="_")` at `connection_generator.R:373`). They appear in the JSON schema, in `_CONN_TYPES` (§4), and in test pinning. They MUST NOT be renamed without coordinated updates to the JSON, the Python loader, and the test suite. Keyword content within each list IS mutable — adding/removing keywords is the expected maintenance pattern.

---

## 3. Data shape (`connection_keywords.json`)

Single document with two top-level keys: `connection_types` (per-pair relevance keywords, ported from R's `connection_keywords` list at `connection_generator.R:343–370`) and `polarity_signals` (per-name impact-keyword sets used by `detect_polarity`, ported from `connection_generator.R:87–91` (`negative_keywords`), `94–98` (`positive_keywords`), `101–105` (`mitigation_keywords`), and `441–444` (`loss_keywords`)).

```json
{
  "connection_types": {
    "drivers_activities":    ["fish", "food", "econom", "livelihood", "subsistence", ...],
    "activities_pressures":  ["fish", "extract", "harvest", "develop", "construct", ...],
    "pressures_states":      ["pollut", "nutrient", "contamin", "extract", ...],
    "states_impacts":        ["decline", "loss", "degrad", "change", "abundance", ...],
    "impacts_welfare":       ["food", "protein", "nutrition", "income", ...],
    "responses_pressures":   ["regulat", "protect", "conserv", "restor", ...],
    "responses_drivers":     ["policy", "awareness", "education", "incentiv", ...],
    "responses_activities":  ["limit", "restrict", "ban", "regulat", ...],
    "welfare_drivers":       ["concern", "demand", "advocacy", "campaign", "lobby",
                                "policy", "legislation", "awareness"],
    "welfare_responses":     ["concern", "awareness", "demand", "advocacy", ...]
  },
  "polarity_signals": {
    "negative_keywords": ["declin", "degrad", "loss", "reduc", "damag", "destruct",
                           "pollut", "eutrophic", "overfish", "bycatch", "invasive",
                           "extinct", "harm", "contaminat", "erosion", "acidific",
                           "hypox", "dead zone", "bleach", "disease", "mortality",
                           "collapse", "fragment", "depletion"],
    "positive_keywords": ["increas", "growth", "restor", "recover", "improv", "enhanc",
                           "protect", "conserv", "benefit", "health", "sustain",
                           "resilient", "biodiver", "abundance", "productiv",
                           "regenerat", "rehabilit", "rebui"],
    "mitigation_keywords": ["ban", "prohibit", "restrict", "limit", "regulat", "control",
                              "manag", "reduce", "prevent", "mitigat", "protect", "enforce",
                              "monitor", "stop", "remov", "clean", "treat"],
    "loss_keywords": ["loss", "decline", "declin", "degrad", "reduc", "damag", "destruct",
                        "decreas", "diminish", "deplet", "erosion", "collapse", "extinct",
                        "mortality", "death", "disappear", "absent", "lack", "scarcity"]
  }
}
```

The truncations above (`...`) are display-only; the JSON ports R's full lists. R reference content: `negative_keywords` 24 stems (R lines 87–91), `positive_keywords` 18 stems (R lines 94–98), `mitigation_keywords` 17 stems (R lines 101–105), `loss_keywords` 19 stems (R lines 441–444). SP3's JSON must contain those exact stems. The `welfare_drivers` list (8 stems shown above) is the SP3 hand-curated full set, not a truncation.

### Important: keyword entries are **stems** for substring matching

R uses `grepl(kw, name_lower)` — substring match, not token-exact match. Keywords are stems: `"fish"` matches `"fishing"`, `"fisher"`, `"fishery"`; `"econom"` matches `"economic"`, `"economy"`, `"economical"`; `"declin"` matches `"decline"`, `"declining"`, `"declined"`. The Python port uses `re.search(re.escape(kw), name_lower)` to mirror this exactly (no Python word boundaries, no tokenization).

### `welfare_drivers` is an SP3 addition not in R

R's `connection_keywords` list at `connection_generator.R:343–370` has only **9** keys — `welfare_drivers` is omitted. This means in R, every welfare→driver pair falls through to the `0.5` default at line 376 (relevance unaffected by name content). SP3's `_CONN_TYPES` includes `welfare_drivers` to honor the "all 10 connection types" decision (§1), so SP3 ships a hand-curated keyword list for it. The chosen stems mirror `welfare_responses` (since both encode "welfare drives behavior" semantically): `concern, demand, advocacy, campaign, lobby, policy, legislation, awareness`. Note: `"pressure"` was considered and dropped because it would substring-match labels containing the DAPSI(W)R(M) framework's own `pressures` term (a label like `"Public pressure"` would otherwise score relevance via the `welfare_drivers` list AND be confusable with a Pressures-element name). Documented as an SP3 addition; future R updates that add a real `welfare_drivers` keyword list should replace SP3's curated set verbatim. Pinned by `test_every_keyword_list_non_empty` (Group 1; the bullet explicitly calls out `welfare_drivers` as a member).

### Per-list invariants

- Every keyword is **lowercase and stripped** (runtime call lowercases input names; keywords must already be lowercase to match).
- Every list under `connection_types` is non-empty (`len ≥ 1`) — though even an empty list would return `0.3` per R's `.calculate_basic_relevance` line 384, meaning no functional difference; the test pins this for documentation hygiene.
- `connection_types` covers all 10 connection types exactly (set equality on keys); slug shape is `f"{from_slug}_{to_slug}"` matching R's `paste(from_type, to_type, sep="_")` at `connection_generator.R:373`.
- `polarity_signals` has exactly the 4 keys listed (set equality).
- **`loss_keywords` and `negative_keywords` overlap but are NOT the same set** — `loss_keywords` (used only by the double-negative filter in `_generate_smart_connections`) is the more restrictive "absolute decline" set; `negative_keywords` (used by polarity detection in `detect_polarity`) is broader and includes pollutants/contaminants. R defines them as separate lists at lines 440 and 86; SP3 mirrors this separation.

**Why no `framework_rules` JSON dict.** R's per-pair polarity logic is not a simple `{type_pair → polarity}` lookup — each branch may use the precomputed per-name signals (`from_is_mitigation`, `to_is_negative`, etc.) to refine. That logic is *algorithm shape*, not data shape, so it lives in Python's `detect_polarity` function with explicit per-pair branches matching R's structure. JSON only stores the data inputs to that algorithm.

---

## 4. Loader API (`sespy/connection_scorer.py`)

```python
"""Connection scoring backend for the AI-ISA wizard.

Loaded eagerly at module import via _load_keywords(). The algorithm
exposes suggest_connections(state) as the SP3 contract — same
signature as SP1's stub, replacing it via sespy/wizard.py.
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any

from .data_structure import (
    WizardState,
    ConnectionSuggestion,
    Element,
    ELEMENT_TYPE_MAP,  # post-relocation home (§6, Task 3)
)

_KW_PATH = Path(__file__).parent / "connection_keywords.json"
_logger = logging.getLogger(__name__)


def _load_keywords() -> dict[str, Any]:
    with _KW_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_KW = _load_keywords()
_TYPE_TO_SLUG = {v: k for k, v in ELEMENT_TYPE_MAP.items()}
# {"Drivers": "drivers", "Activities": "activities", ...,
#  "Marine Processes & Functioning": "states", "Ecosystem Services": "impacts",
#  "Goods & Benefits": "welfare", "Responses": "responses"}

_MAX_PER_TYPE = 15
_MIN_RELEVANCE = 0.3

# 10 connection types as (from_slug, to_slug, conn_type_key) tuples.
# Iteration order follows the natural DAPSI(W)R(M) layer order, matching R.
# Connection-type key shape is f"{from_slug}_{to_slug}" (R: paste(from_type,
# to_type, sep="_")); used to look up keywords in _KW["connection_types"].
_CONN_TYPES: list[tuple[str, str, str]] = [
    ("drivers", "activities", "drivers_activities"),
    ("activities", "pressures", "activities_pressures"),
    ("pressures", "states", "pressures_states"),
    ("states", "impacts", "states_impacts"),
    ("impacts", "welfare", "impacts_welfare"),
    ("responses", "pressures", "responses_pressures"),
    ("responses", "drivers", "responses_drivers"),
    ("responses", "activities", "responses_activities"),
    ("welfare", "drivers", "welfare_drivers"),
    ("welfare", "responses", "welfare_responses"),
]


def _select_verb(from_slug: str, polarity: str) -> str:
    """Verb for the rationale string, polarity-aware for some types.
    Matches R's verb selection at connection_generator.R:513-529.

    drivers     → "drives"                (polarity-insensitive)
    activities  → "increases" (+) | "causes" (-)
    pressures   → "increases" (+) | "decreases" (-)
    states      → "impacts"               (polarity-insensitive)
    impacts     → "increases" (+) | "reduces" (-)
    responses   → "enables" (+)   | "restricts" (-)
    welfare     → "motivates" (+) | "reduces" (-)
    default     → "affects positively" (+) | "affects negatively" (-)
                  (unreachable from _CONN_TYPES' 7 from-slugs; included
                   for forward-compat with future Element-type additions
                   that might appear as from-elements via _TYPE_TO_SLUG.)

    Polarity-insensitive entries (drivers, states) return the same verb
    for both polarities — the test parameterization runs them twice and
    asserts the same output (matches R lines 514-515 and 519-520).
    """


def _analyze_polarity_phrase(name_lower: str) -> tuple[str, bool]:
    """Return (sentiment, negated) for a single name. Two-check scheme:
    (a) match name_lower against the 8 _REVERSAL_COMPOUNDS regexes — if
    any matches, return ("positive", True); (b) otherwise scan against
    the 11 _NEGATION_PATTERNS regexes (with \\b word boundaries) — if any
    matches, return ("neutral", True). Else return ("neutral", False).
    See §5 for full algorithm and R provenance (lines 198-226)."""


def calculate_relevance(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> float:
    """Return one of {0.3, 0.6, 0.9} based on keyword-substring-match count
    across both names (0 matches → 0.3 floor, 1 → 0.6, 2+ → 0.9). Returns
    0.5 if the (from_slug, to_slug) pair is missing from the keyword JSON
    (defensive default at R line 376; schema test pins all 10 pairs present
    so 0.5 doesn't fire in normal operation). Slug params are lowercase
    (e.g., "drivers", "states"), NOT the human Element.type strings."""


def detect_polarity(
    from_name: str, to_name: str, from_slug: str, to_slug: str
) -> str:
    """Return '+' or '-' via per-pair dispatch over (from_slug, to_slug)
    using precomputed per-name signals (mitigation flag, positive/negative
    impact-keyword hits, negation flag from _analyze_polarity_phrase).
    See §5 for the per-pair decision table; default fallback is '+'.
    Slug params are lowercase, NOT human Element.type strings."""


def _generate_smart_connections(
    from_elements: list[Element],
    to_elements: list[Element],
    from_slug: str, to_slug: str,
    max_count: int = _MAX_PER_TYPE,
    min_relevance: float = _MIN_RELEVANCE,
) -> list[ConnectionSuggestion]:
    """Per-type pair generator. Cross-product, threshold filter,
    double-negative filter, sort desc by confidence, cap at max_count.
    Verb derived per-pair via _select_verb(from_slug, polarity) — NOT a
    parameter, because verb is polarity-aware and polarity varies per pair."""


def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    Same signature as SP1 stub. Returns flat list of ≤150 (10×15) items."""
```

### Design choices (matches SP2 §4)

- **Eager load at module import.** The keyword KB is ~10–20 KB and never changes at runtime. Lazy loading would add complexity for zero benefit.
- **No defensive copy of `_KW` in scoring functions.** Internal callers only read; future mutation would be a caller bug.
- **`_TYPE_TO_SLUG` derived from `ELEMENT_TYPE_MAP`, not duplicated.** Single source of truth — adding an Element type to SP1 propagates automatically. Verified by a unit test (`test_type_slug_map_is_inverse_of_wizard_map`).
- **`_CONN_TYPES` is a flat list of tuples, not a dict.** Iteration order is the natural DAPSI(W)R(M) layer order; preserving it makes the output `list[ConnectionSuggestion]` reproducible across runs.

---

## 5. Components (4 functions)

### `detect_polarity(from_name, to_name, from_slug, to_slug) -> str`

**Per-pair dispatch with precomputed per-name signals** (faithful to R's structure at `connection_generator.R:62–187`). NOT a 3-layer fall-through — each connection-type branch has its own decision logic that consumes precomputed signals from both element names.

**Step A: Precompute per-name signals** (R lines 86–112):
- Lowercase both names: `from_lower = from_name.lower()`, `to_lower = to_name.lower()`.
- Substring-match each `polarity_signals` keyword set against both names (`re.search(re.escape(kw), name_lower)`):
  - `from_is_negative`, `to_is_negative` ← any `negative_keywords` match.
  - `from_is_positive`, `to_is_positive` ← any `positive_keywords` match.
  - `from_is_mitigation` ← any `mitigation_keywords` match in `from_lower`.
- Compute per-name semantics by calling the helper **twice** (once per name): `from_analysis = _analyze_polarity_phrase(from_lower)` and `to_analysis = _analyze_polarity_phrase(to_lower)`. The helper returns `(sentiment: "positive"|"neutral", negated: bool)` — see helper spec below. Note: R computes the `_is_negative` / `_is_positive` flags locally inside the `("states", "impacts")` and `("impacts", "welfare")` branches that need them (R lines 154–155, 171–172); SP3 hoists them to Step A for clarity. Functionally equivalent because the inputs are pure functions of the name strings.

**`_analyze_polarity_phrase(name_lower) -> tuple[str, bool]`** (port of R `.analyze_polarity_phrase` at lines 198–226):

The helper has two checks; reversal takes precedence in the return. **Returns only `("positive", True)`, `("neutral", True)`, or `("neutral", False)`** — never `("negative", *)` (R's helper has no path that emits a `"negative"` sentiment string; the negative semantic is captured separately by the `from_is_negative` / `to_is_negative` substring flags computed in Step A).

**Drop of R's `base_sentiment` field, documented.** R's helper actually returns a 3-field list: `list(sentiment=..., negated=..., base_sentiment=...)` (see R lines 220–225). SP3 returns a 2-tuple `(sentiment, negated)`, deliberately dropping `base_sentiment` because R's `detect_polarity` (the only consumer) reads only `sentiment` and `negated` — never `base_sentiment`. Verified against R lines 117–186 (no `$base_sentiment` access). Future R-sync should re-verify this assumption: if a new R caller starts reading `base_sentiment`, SP3 must extend the tuple.

*Reversal-compounds check (R lines 216–223).* Match `name_lower` against 8 regex patterns that detect "negative-of-negative" phrases like *"pollution reduction"*. Each pattern is a bare stem-pair `X.*Y` (no `\b` word boundaries — matches R's `pollut.*reduc` etc. verbatim) where X is a negative concept and Y is a neutralizer:

```python
_REVERSAL_COMPOUNDS = [
    r"pollut.*reduc",  r"emission.*reduc",  r"pressure.*reduc",
    r"litter.*reduc",  r"waste.*reduc",     r"noise.*reduc",
    r"overfish.*prevent",  r"erosion.*control",
]
```

If any matches, return `("positive", True)` — sentiment positive AND negated flag set (R sets both: this signals "this name semantically reverses what the words say"). The §5 dispatch's `("activities", "pressures")` branch checks `from_analysis.sentiment == "positive"` to detect mitigation-by-reversal, so this path is load-bearing.

*Negation-regex check (R lines 209–213; `negation_words` list at 209–211, `has_negation <- ...` computation at 213).* If no reversal-compound matched, scan `name_lower` for 11 negation patterns with `\b` word boundaries:

```python
_NEGATION_PATTERNS = [
    r"\bno\b",       r"\bnot\b",       r"\bnon[- ]",     r"\bwithout\b",
    r"\bprevent",    r"\bban\b",       r"\breduc",       r"\bremov",
    r"\bcontrol",    r"\blimit",       r"\brestrict",
]
```

If any matches, return `("neutral", True)` — negated flag set, sentiment neutral. Otherwise return `("neutral", False)`. R's source-order is: define-then-check `has_negation` first (lines 209–213), then define-then-check `is_reversal` (lines 216–219), then the early-return tests `is_reversal` before falling through; reversal effectively takes precedence in the return because `if (is_reversal) return("positive", TRUE)` runs before the fallthrough that uses `has_negation`. Either implementation order in Python produces the same observable behaviour.

**Unicode caveat (out of scope but flagged).** R uses `perl = TRUE` for these regexes (R line 213); Python `re` `\b` semantics for non-ASCII characters differ subtly from PCRE's `\b` under UNICODE flag. For ASCII-only labels (the SP3 design assumption), both engines produce identical matches. For non-ASCII labels (Spanish, German, Greek wizard inputs) match results may diverge. SP3 inherits R's ASCII-centric assumption and does not handle non-ASCII labels specially; SP4 i18n consideration if multilingual labels become a target.

R's helper has additional KB-aware fallback at lines 199–207 that we drop per scope. Both pattern lists live as module-level constants in `connection_scorer.py` (not in JSON) because they're algorithm-shape (regex with backslash escapes) rather than data; the negation-pattern set is rarely tuned and tightly coupled to this helper's logic.

**Step B: Per-pair dispatch** (R lines 117–183, ported verbatim — only the type-pairs that appear in `_CONN_TYPES` are listed; R's `("responses", "states")` branch at lines 122–130 is NOT ported because `_CONN_TYPES` does not include it, so the branch would be unreachable dead code; SP4 can re-add it with a test if needed):

| `(from_slug, to_slug)` | Logic |
|---|---|
| `("responses", "pressures")` | Always `"-"`. Response measures reduce pressures by definition. (R line 117.) |
| `("activities", "pressures")` | If `from_is_mitigation` OR `from_analysis.sentiment == "positive"` → `"-"`; else `"+"`. (R lines 133–140.) |
| `("pressures", "states")` | If `to_is_negative` → `"+"` (pressure increases negative state); if `to_is_positive` → `"-"`; else default `"-"`. (R lines 143–150.) |
| `("states", "impacts")` | Apply negation flip on **both names' negative flags only** (NOT positive flags — R lines 158–159 flip only `from_is_negative` and `to_is_negative`): `if from_analysis.negated and from_is_negative: from_is_negative = False`; `if to_analysis.negated and to_is_negative: to_is_negative = False`. The `from_is_positive` and `to_is_positive` flags are NEVER flipped — a label like `"Reduced biodiversity loss"` keeps `from_is_positive=True` after the flip even though `from_analysis.negated=True`. Then if `(from_is_negative AND to_is_negative) OR (from_is_positive AND to_is_positive)` → `"+"` (same-sign reinforcement); elif `(from_is_negative AND to_is_positive) OR (from_is_positive AND to_is_negative)` → `"-"` (opposite-sign opposition); else `"-"` (default for ambiguous/neutral pairs — fires when at least one name has no polarity-keyword hits in either `negative_keywords` or `positive_keywords`). (R lines 153–167.) |
| `("impacts", "welfare")` | Apply negation flip on `from_is_negative` only (R line 175). `to_is_*` flags ARE precomputed in Step A (universal hoist) but **unused** in this branch — R reads only `from_*` (R lines 170–183). `from_is_positive` is NOT flipped. Then if `from_is_negative` → `"-"`; elif `from_is_positive` → `"+"`; else default `"-"` (matches R's "impacts reduce welfare" default semantic). (R lines 170–183.) |
| All others (D→A, R→D, R→A, W→D, W→R) | Default fallback: `"+"`. R has no special branch for these; `return("+")` at the function-end fallback (R line 186, with comment at line 185). Polarity is name-content-insensitive for these 5 type-pairs — see §9 risks for the UX consequence. |

**Returns:** Always `"+"` or `"-"`. Never raises. R's KB-lookup branch (lines 64–75) and ML-scoring branch are not ported per the rule-based-only scope decision.

### `calculate_relevance(from_name, to_name, from_slug, to_slug) -> float`

Direct port of R's `.calculate_basic_relevance` (`connection_generator.R:338–387`):

1. Look up keyword list: `keywords = _KW["connection_types"][f"{from_slug}_{to_slug}"]`. If the type-pair key is missing (shouldn't happen — schema test pins all 10 keys present), return `0.5` (R's default for unknown pair at line 376).
2. Lowercase both names: `from_lower = from_name.lower()`, `to_lower = to_name.lower()`.
3. Count substring matches: `from_matches = sum(1 for kw in keywords if re.search(re.escape(kw), from_lower))` (similarly `to_matches`). **Substring match is critical** — keywords are stems (`"fish"` matches `"fishing"`, `"econom"` matches `"economic"`); using token-exact match would miss most real labels.
4. `total_matches = from_matches + to_matches`.
5. Map `total_matches` → score (R lines 384–386):
   - `0 → 0.3` (low relevance — but still passes `MIN_RELEVANCE=0.3` because R uses `>=` at line 452)
   - `1 → 0.6`
   - `2+ → 0.9`

**Returns:** Float in `{0.3, 0.5, 0.6, 0.9}` (the `0.5` only on schema-violation; in practice the schema test guarantees `{0.3, 0.6, 0.9}`). Never raises.

**Quirk worth flagging.** Because the floor is `0.3` and `MIN_RELEVANCE = 0.3`, every cross-product pair survives the threshold gate by construction. The per-type cap at 15 (after sort by confidence descending) is the effective filter. R's authors chose this floor deliberately ("Lower threshold to ensure core DAPSIWR connections are generated" — comment at line 758); SP3 inherits the choice verbatim. The visible effect is that small SES networks (≤ 15 elements per type) get every cross-pair as a suggestion, ranked by keyword-density.

### `_generate_smart_connections(from_elements, to_elements, ...) -> list[ConnectionSuggestion]`

Per-type pair generator (R lines 436–574, simplified — KB and ML branches dropped per scope):

1. For each `(from_el, to_el)` cross-pair:
   - `relevance = calculate_relevance(from_el.label, to_el.label, from_slug, to_slug)`.
   - If `relevance < min_relevance`: skip. R uses `>=` at line 452, so 0.3 ≥ 0.3 survives — the gate is vacuous given R's 0.3 floor (see §5 quirk below). Pinned for forward-compat with future scoring backends that might return `0.0`.
   - **Double-negative filter** (R lines 440–463: definition at 440–444, check at 454–462, `next` at 462): if BOTH `from_el.label` AND `to_el.label` contain any `loss_keywords` substring, skip. Semantically: a connection from "Loss of biodiversity" to "Decline in fish stocks" is the same direction (both negative outcomes) and emitting it would generate a misleading `+` polarity. Note: this uses `loss_keywords` (specific decline/loss vocabulary) **not** `negative_keywords` (broader, includes pollutants like `"pollut"`, `"contaminat"`) — the two sets overlap but are distinct in R.
   - `polarity = detect_polarity(from_el.label, to_el.label, from_slug, to_slug)`.
   - `verb = _select_verb(from_slug, polarity)`.
   - Build `ConnectionSuggestion(source=from_el.id, target=to_el.id, polarity=polarity, confidence=relevance, rationale=f"{from_el.label} {verb} {to_el.label}")`.
2. Sort by `confidence` descending (stable sort — preserves cross-product order on ties).
3. Cap at `max_count`.

### `suggest_connections(state) -> list[ConnectionSuggestion]` — the SP3 contract

Top-level orchestrator (R lines 755–1001; constants `MAX_PER_TYPE=15` and `MIN_RELEVANCE=0.3` at lines 757–758):

1. **Group `state.elements` by type** using `_TYPE_TO_SLUG`. Elements with `.type` not in `_TYPE_TO_SLUG` → `_logger.warning(f"unknown Element.type {el.type!r} for id {el.id!r}; skipping")` (one warning per unknown-typed element, with element id and type in the message for diagnostics) and skip the element (defensive: future Element types added without updating SP3 won't crash).
2. **For each `(from_slug, to_slug, _conn_type_key)` in `_CONN_TYPES`** (the third tuple field is destructured but unused — `calculate_relevance` rebuilds it internally): call `_generate_smart_connections(from_list, to_list, from_slug, to_slug)`. Verb is derived per-pair inside `_generate_smart_connections` via `_select_verb(from_slug, polarity)` because verb is polarity-aware for some types (R lines 513–529) and polarity is computed per pair. Skip the call entirely if either list is empty (cross-product would be empty anyway).
3. **Concatenate** all 10 type results into a flat list (≤ 150 total).

**Returns:** `list[ConnectionSuggestion]`. Empty list if `state.elements` is empty or all connections fail filters.

---

## 6. Migration of `sespy/wizard.py`

**Before (SP1, line 92):**

```python
def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP1 stub: returns []. SP3 fills via TF-IDF + polarity rules; SP4 fills
    via Claude API. SP1's connection-review renderer surfaces an empty
    table with a placeholder message ("No suggestions yet — install SP3
    or SP4 backend to enable AI-assisted connection generation").
    """
    return []
```

(The "TF-IDF" mention in the SP1 docstring is outdated speculation from before SP3 brainstorm. SP3 actually uses keyword substring matching with a 0/1/2+-match score, not TF-IDF — see §1 Decisions and §5 `calculate_relevance`. The SP3 implementation will replace the docstring with the post-SP3 wording shown below.)

**After (SP3):**

```python
# At top of sespy/wizard.py, alongside other imports:
from .connection_scorer import suggest_connections as _suggest_impl

# Replacing the SP1 stub at line 92:
def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    SP4 (Claude API) will replace the implementation behind a settings
    switch; the signature is the contract."""
    return _suggest_impl(state)
```

**Prerequisite: relocate `ELEMENT_TYPE_MAP`** (single Edit operation, scoped within Task 3 of §8).

The naive top-level import is circular today: `sespy/wizard.py` defines `ELEMENT_TYPE_MAP` (line 60) and would now import from `sespy/connection_scorer.py`, which would import `ELEMENT_TYPE_MAP` back from `sespy/wizard.py` — Python re-enters `wizard.py` mid-load and hits an `AttributeError` (or worse, sees a half-built module). The clean fix is a 5-line relocation: move `ELEMENT_TYPE_MAP` from `sespy/wizard.py` to `sespy/data_structure.py` (where the `Element.type` strings the map's values reference are already conceptually rooted), then re-export from `wizard.py` as `from .data_structure import ELEMENT_TYPE_MAP` so SP1 callers (`tests/test_wizard.py:5-6 (multi-line import)`, `sespy/modules/ai_isa_wizard.py`) keep working unchanged.

The dependency graph after the move is linear:
- `data_structure` → (stdlib only)
- `wizard` → `data_structure`, `regional_seas`, `connection_scorer`
- `connection_scorer` → `data_structure` (NOT wizard)

Top-level import of `_suggest_impl` in `wizard.py` is now safe; no lazy-import band-aid needed. The `_KW = _load_keywords()` JSON read happens at app startup (every `import sespy.wizard` triggers it), so a missing JSON file fails loudly at boot rather than on the user's first wizard step 11 click.

**SP1 renderer impact: zero.** The `connection_review` renderer at `sespy/modules/ai_isa_wizard.py` reads `wizard_suggestions: reactive.Value[list[ConnectionSuggestion]]` and renders rows. Returning a non-empty list works exactly as the SP1 design anticipated.

**SP1 import-site impact: zero.** `tests/test_wizard.py:5-6 (multi-line import)` already does `from sespy.wizard import (..., ELEMENT_TYPE_MAP, ...)` — the re-export from `data_structure` keeps that line working. The `sespy/modules/ai_isa_wizard.py` import (`from ..wizard import ELEMENT_TYPE_MAP`) is unchanged for the same reason.

**SP1 unit-test impact:** one test rewritten in `tests/test_wizard.py` (see §7).

---

## 7. Testing (`tests/test_connection_scorer.py`)

**33 unit tests** across 5 groups (G1=5, G2=6, G3=7, G4=6, G5=9). No new e2e — `test_wizard_e2e.py` case 1 (full 12-step run) already exercises the SP3 path end-to-end and (post-SP3) will see ≥1 suggestion appear at step 11.

### Group 1: JSON schema / loader (5 tests)

- `test_keywords_json_loads` — file loads via `_load_keywords()` without error.
- `test_all_10_connection_types_present` — set-equality on `connection_types` keys against the 10 expected slug-pair keys.
- `test_polarity_signals_keys_present` — `negative_keywords`, `positive_keywords`, `mitigation_keywords`, `loss_keywords` all present (set-equality).
- `test_every_keyword_list_non_empty` — `len ≥ 1` for each list under both top-level keys, including `welfare_drivers` (the SP3 hand-curated addition; pinned so a future "minimize JSON" pass can't drop it silently).
- `test_keywords_are_lowercase_and_stripped` — canonicalization invariant; catches a hand-edit that adds `"Fishing"` instead of `"fishing"`.

### Group 2: `calculate_relevance` (6 tests)

- `test_zero_matches_returns_03` — names with no keyword substring match → `0.3` (R's "Low relevance" floor; passes `MIN_RELEVANCE=0.3` by construction).
- `test_one_match_returns_06` — exactly one keyword substring match across both names → `0.6`.
- `test_two_plus_matches_returns_09` — two or more matches → `0.9`.
- `test_relevance_uses_substring_match` — `"Fishing"` matches keyword stem `"fish"` (substring, not token-exact). Pinned because the substring-vs-token semantics is load-bearing.
- `test_relevance_is_case_insensitive` — `"FISHING"` matches keyword `"fish"` (input lowercased before matching).
- `test_relevance_unknown_pair_returns_05` — passing a `(from_slug, to_slug)` pair not in the keyword JSON returns `0.5` (R's default at line 376). Defensive path; pinned so future removal is a deliberate decision.

### Group 3: `detect_polarity` (7 tests)

- `test_responses_to_pressures_is_minus` — always `"-"` regardless of names (R line 117 invariant).
- `test_activities_to_pressures_mitigation_is_minus` — `"Pollution reduction"` from `activities` → `"-"` via the reversal-compound path (`_analyze_polarity_phrase` returns `("positive", True)`, then dispatch checks `from_analysis.sentiment == "positive"`).
- `test_activities_to_pressures_default_is_plus` — neutral names → `"+"`.
- `test_pressures_to_states_branches` — pins all three pressures→states branches (R lines 143–150): to-name with `"declin"` (negative) → `"+"`; to-name with `"health"`/`"biodiver"` (positive) → `"-"`; neutral to-name → default `"-"`.
- `test_states_to_impacts_negation_flip` — `"Reduced biodiversity"` flips its negative flag via the `_analyze_polarity_phrase` negated-detection (R lines 156–159).
- `test_default_fallback_for_unspecified_pair` — `(drivers, activities)` and similar unspecified pairs return `"+"` per R line 186 (default fallback).
- `test_analyze_polarity_phrase_reversal_compound` — direct test on the helper: `"pollution reduction"` returns `("positive", True)`; `"emission reduction"` likewise; an unrelated phrase like `"fishing activity"` returns `("neutral", False)`. Pins the 8-pattern reversal-compound list as a falsifiable invariant.

**Acknowledged G3 coverage gap:** the `("impacts", "welfare")` branch (R lines 170–183) is not directly tested in G3. It is indirectly exercised by G5's `test_full_state_returns_typed_suggestions` and `test_all_10_types_yield_high_confidence_suggestions`, both of which include I→W pairs in their fixtures and would surface a regression — but a unit-level pin is absent. Decision: accepted as a known gap; if the branch becomes a regression hot-spot in practice, add `test_impacts_to_welfare_branches` to G3 (would bump G3=8, total logical=34).

### Group 4: `_generate_smart_connections` (6 tests)

- `test_cross_product_pair_generation` — 2 from × 3 to → ≤ 6 candidates pre-filter (some may drop via double-negative).
- `test_double_negative_filter_uses_loss_keywords` — both names contain `loss_keywords` substring (e.g., `"Loss of biodiversity"` + `"Decline in stocks"`) → suggestion dropped. Names with `negative_keywords` that are NOT `loss_keywords` (e.g., `"Pollution"`) survive — pinning the filter's specific vocabulary.
- `test_results_sorted_by_confidence_desc` — descending order invariant.
- `test_max_count_cap_honored` — > 15 candidates → exactly 15 returned.
- `test_pair_with_relevance_exactly_03_survives` — pins R's `>=` threshold semantics at the floor: a pair with `relevance == 0.3` IS emitted, not filtered. Future change to `min_relevance > 0.3` (or strict `>`) would change this; the test forces a deliberate decision.
- `test_verb_selection_per_from_slug_polarity_pair` — parameterized over all 7 from-slugs × 2 polarities (14 cases). Pins the §4 `_select_verb` table verbatim. Critical because the §4 docstring is the only place this mapping lives in the spec; without coverage of all 14 cases, a typo ships silently. Cases derived from R lines 513–529.

### Group 5: `suggest_connections` (the SP3 contract) (9 tests)

- `test_empty_state_returns_empty` — `state.elements = []` → `[]`.
- `test_single_element_state_returns_empty` — only one element → no possible cross-product → `[]`.
- `test_full_state_returns_typed_suggestions` — multi-type state → all items are `ConnectionSuggestion`, all `confidence ∈ {0.3, 0.6, 0.9}`, all `polarity ∈ {"+", "-"}`.
- `test_per_type_cap_honored_end_to_end` — state designed to overflow `D→A` → ≤ 15 `D→A` suggestions in output.
- `test_all_10_types_yield_high_confidence_suggestions` — fixture with ≥2 elements per type, overlap-rich labels, and at least one element per S/I/W group with NO loss_keyword (so the double-negative filter doesn't drop every S→I and I→W pair). Asserts at least one suggestion with `confidence >= 0.6` for each of the 10 connection-type keys — strengthens the "≥1 suggestion per type" form (which would pass trivially given R's 0.3 floor) into a real verification that the keyword JSON has overlap-rich coverage for every type. Pins §11 DoD's "all 10 types produce suggestions" claim.
- `test_unknown_element_type_skipped` — `Element` with `.type = "Foo"` (not in `_TYPE_TO_SLUG`) is skipped without raising; one `logging.warning` is emitted per unknown-typed element (caplog-asserted message contains the element id and type for diagnostics). Pins the defensive path described in §5.
- `test_type_slug_map_is_inverse_of_wizard_map` — `_TYPE_TO_SLUG` exactly inverts `ELEMENT_TYPE_MAP` (set equality + per-key roundtrip). Pins the §4 derivation; if `ELEMENT_TYPE_MAP` ever gains a duplicate value (silent inversion loss), this fails.
- `test_polarity_default_fallback_returns_positive` — pair of `(drivers, activities)` (one of the 5 type-pairs without a named branch) → `"+"` regardless of name content (R line 186 fallback). Distinct from `test_default_fallback_for_unspecified_pair` in Group 3 by being end-to-end through `suggest_connections` rather than a direct `detect_polarity` call.
- `test_no_wizard_import_in_connection_scorer` — defensive: parse `sespy/connection_scorer.py` source (or AST) and assert no `from .wizard import` or `from sespy.wizard import` line exists. Pins the §6 import-graph linearity post-relocation; if a future refactor accidentally re-introduces a `wizard` import, the cycle returns and SP1 e2e cases fail at boot. This test catches the regression at unit-test time before it reaches e2e.

### Updated SP1 test (`tests/test_wizard.py`)

- `test_suggest_connections_stub_returns_empty` (line 62) → renamed to `test_suggest_connections_empty_state_returns_empty`. Same body (`assert suggest_connections(state) == []` for empty state); narrower name. Coexists with `test_empty_state_returns_empty` in the new file: the wizard-level test smokes the wrapper after the import-graph relocation; the connection-scorer-level test pins the implementation behavior.

### Coverage targets

- `sespy/connection_scorer.py`: ~95% line coverage. Substrate-level — silent regressions surface only as "wrong suggestions" which are hard to spot without tests.
- `sespy/connection_keywords.json`: schema-validated by Group 1 tests (no other "coverage" possible for static data).

### Test count delta

`134 unit + 21 e2e` (current baseline) → **`180 unit + 21 e2e`** (post-SP3: +33 *logical* tests, but Group 4's `test_verb_selection_per_from_slug_polarity_pair` parametrize expands 1 logical test into 14 pytest items, so the *pytest item count* — what `pytest -q` reports — is +46. The README phrase "X unit tests" matches `pytest -q` output (current `134` matches today's `134 passed`), so post-SP3 it becomes `180`. The `test_suggest_connections_stub_returns_empty` rename in `test_wizard.py` is a rename, not an addition).

SP3 introduces the first `@pytest.mark.parametrize` in SESPy's test corpus; this is the reason logical-test count and pytest-item count diverge here for the first time.

---

## 8. Build sequence (preview)

**Task summary** — not a substitute for an executable plan. Per SESPy convention, a separate plan at `docs/superpowers/plans/2026-05-03-ai-isa-wizard-sp3.md` MUST be written via `superpowers:writing-plans` before implementation. The 8 tasks below (Task 0 setup through Task 7 README) set the contract for that plan.

| Task | What | Commit | Effort |
|---|---|---|---|
| 0 | Verify env, cut `feat/ai-isa-wizard-sp3`, baseline 134 unit + 21 e2e green. **Verify R source-of-truth is accessible** at `../SESToolbox/MarineSABRES_SES_Shiny/modules/ai_isa/connection_generator.R` — Task 1 (JSON authoring) and Task 2 (algorithm port) both require reading specific R lines that the spec cites but does not inline (the 9 R-derived `connection_types` keyword lists at R 343–370, the per-pair dispatch logic at R 117–186, the `_analyze_polarity_phrase` helper at R 198–226). | (no commit) | 5 min |
| 1 | Create `sespy/connection_keywords.json` (10 keyword lists + 4 polarity word sets, ported from R) | `feat(connection_scorer): keyword JSON ported from R generator` | ~90 min |
| 2 | Create `sespy/connection_scorer.py` with `_load_keywords` + `_KW` + the 4 functions + `_select_verb` + `_analyze_polarity_phrase`; TDD with `tests/test_connection_scorer.py` (33 logical tests / 46 pytest items after parametrize expansion) | `feat(connection_scorer): rule-based scoring with 33 unit tests` | ~3.5 h |
| 3 | Relocate `ELEMENT_TYPE_MAP` from `sespy/wizard.py` to `sespy/data_structure.py`; re-export from `wizard.py` so SP1 callers keep working unchanged. Verify `tests/test_wizard.py` still passes. | `refactor(data_structure): move ELEMENT_TYPE_MAP to break SP3 import cycle` | ~15 min |
| 4 | Wire `sespy/wizard.py:92` to top-level-import `connection_scorer.suggest_connections`; rename SP1 test in `test_wizard.py` | `feat(wizard): SP3 backend swap — replace stub with connection_scorer` | ~10 min |
| 5 | Add `[build-system]` + `[tool.setuptools.packages.find]` + `[tool.setuptools.package-data]` entries to `pyproject.toml` (~10 LOC; see §2) so `sespy/*.json` ships in installed wheels (fixes a latent SP2 hazard in passing — SP2's missing `[build-system]` declaration is also now repaired). Verify via a one-shot **CI/manual** invocation (NOT a pytest unit test — Group 1's `test_keywords_json_loads` already covers source-tree imports; the wheel-installation hazard requires installing into a throwaway environment and importing from there, which can't run inside pytest in the same source tree). On this machine (per `~/.claude/CLAUDE.md`: "Do NOT create virtual environments"), use a disposable micromamba env rather than `python -m venv`: `micromamba create -n sespy-wheel-test python=3.11 -y && micromamba run -n sespy-wheel-test pip install . && micromamba run -n sespy-wheel-test python -c "import sespy.connection_scorer, sespy.regional_seas; print('ok')" && micromamba env remove -n sespy-wheel-test -y`. | `fix(packaging): include package data in wheel for SP2/SP3 JSON files` | ~30 min |
| 6 | Run SP1 e2e + browser smoke at step 11 (≥1 suggestion appears for the Coastal Tourism template) | (no commit unless fix needed) | ~20 min |
| 7 | Update `README.md`: `134 → 180` unit tests at both occurrences | `docs(readme): bump unit test count to 180 after SP3` | ~10 min |

**Total estimate:** ~4.5–5.5 hours focused work. Task 1 is data porting from R (largest); Task 2 is the algorithm (most logic-dense); Tasks 3 + 5 are short config/refactor work; rest are mechanical.

**Branch:** `feat/ai-isa-wizard-sp3` cut from main at HEAD (post-`13a042e` SP3-spec round-1 commit, or whatever the current main HEAD is at branch-cut time). **Expected 6 commits** (Tasks 1, 2, 3, 4, 5, 7 each produce one commit; Tasks 0 and 6 are read-only verification steps).

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Keyword lists drift from R as R updates them | Out of scope for SP3 — current snapshot. Future R-side updates require a separate sync task. The JSON file is the single point of update. |
| Substring-match semantics: `re.search(re.escape(kw), name_lower)` mirrors R's `grepl(kw, name_lower)` byte-for-byte (no Python word-boundaries, no NFC normalization, no Unicode case-folding) | Pinned by `test_relevance_uses_substring_match` and `test_relevance_is_case_insensitive`. Documented in §3 ("keyword entries are stems") and §5 (calculate_relevance step 3). |
| Per-pair polarity-dispatch table (§5) drifts from R's branches | The 5 named branches plus default-fallback are pinned by Group 3 tests. (R has a 6th branch for `("responses", "states")` at lines 122–130 that SP3 does not port because `_CONN_TYPES` doesn't include that pair — see §5 dispatch-table prose.) Adding a new branch (e.g., explicit `("drivers", "activities")` with non-default behavior) requires both a code change AND a new pinned test, forcing the change to be documented. |
| Connection-type slug-shape (`f"{from_slug}_{to_slug}"`) drifts between JSON keys and the keyword lookup; a typo in the JSON would silently fall back to the `0.5` default in `calculate_relevance` | Group 1 `test_all_10_connection_types_present` asserts exact set-equality, so a typo fails CI. The `0.5` fallback only fires on schema violation; a unit test (`test_relevance_unknown_pair_returns_05`) pins this defensive path so removing it later is a deliberate decision. |
| Would-be circular import (`wizard.py` ↔ `connection_scorer.py`) | Resolved at the architecture level (Task 3 of §8) by relocating `ELEMENT_TYPE_MAP` from `wizard.py` to `data_structure.py`. `connection_scorer` then imports only from `data_structure`; `wizard.py` does a normal top-level import of `connection_scorer.suggest_connections`. The dependency graph is linear. |
| `welfare_drivers` keyword list is SP3-curated (not in R) — divergence from "verbatim port" | Documented in §3 with the curation rationale (including why `"pressure"` was dropped to avoid a substring collision with the framework's own `pressures` element type). Pinned by `test_every_keyword_list_non_empty` (Group 1) which asserts `welfare_drivers` is non-empty. Future R updates that add a real `welfare_drivers` list should replace SP3's curated set verbatim. |
| Five connection types (D→A, R→D, R→A, W→D, W→R) fall through to the default `+` polarity in `detect_polarity` | This is faithful to R (those branches don't exist there either). The design choice is documented in the §5 dispatch table prose ("only the type-pairs that appear in `_CONN_TYPES` are listed"); UX consequence is that polarity for those types is name-content-insensitive. SP4 (Claude API) can refine. |
| Confidence semantics drift (someone "improves" the score later by adding fractional values) | Group 5 test pins `confidence ∈ {0.3, 0.6, 0.9}` (plus the defensive `0.5` schema-violation path) — adding new values fails the test and forces a documented decision. |
| Default `"+"` polarity for the 5 type-pairs without a named branch (D→A, R→D, R→A, W→D, W→R) — name content is ignored | Pinned end-to-end by `test_polarity_default_fallback_returns_positive` in Group 5 (full `suggest_connections` path) and at the unit level by `test_default_fallback_for_unspecified_pair` in Group 3 (direct `detect_polarity` call). The two together pin both R line 186's fallback and the `_CONN_TYPES` flow into it. |
| Element with type not in `_TYPE_TO_SLUG` (future Element-type additions) | Defensive skip + `logging.warning` once. Won't crash. Pinned by `test_unknown_element_type_skipped`. |
| **Latent SP2 hazard: eager JSON load fails on `pip install`** because `pyproject.toml` lacks both `[build-system]` and `[tool.setuptools.package-data]` declarations. SP2's `regional_seas.json` already affected; SP3 inherits and would extend the breakage to `connection_keywords.json`. | Fixed in passing as Task 5 of §8 — the ~10-LOC `pyproject.toml` config change covers both SP2 and SP3 JSON files. Verified by a CI/manual `pip install . && python -c "import sespy.connection_scorer, sespy.regional_seas"` in a throwaway micromamba env (never `python -m venv` per CLAUDE.md) (not a pytest unit test — see Task 5). |
| Empty SP3 output for valid states (e.g., all keywords missed but cross-product is empty) | Cross-product is empty only when one side is empty (single-element state, etc.). For non-trivial states, R's 0.3 floor guarantees ≥1 suggestion per non-empty `(from_list, to_list)` pair — so empty SP3 output for a multi-type state is a defect, caught by `test_all_10_types_yield_high_confidence_suggestions`. UX of "no suggestions" is the same as SP1's empty-stub behavior; renderer falls back to `t("wizard.no_suggestions")`. |
| SP4 (Claude API) may want different `confidence` semantics (e.g., model probability) | The `0..1` float type in `ConnectionSuggestion.confidence` accommodates any value. SP4 would document its own semantics; the type contract holds. |

---

## 10. Out of scope, explicitly

- **Feature B** (element-name suggestions, governance/socioeconomic context helpers) — own SP, likely SP3.5.
- KB lookup (`SES_CONNECTION_DB`) — SP4+ if ever ported (low priority; rule-based is sufficient for the wizard's use case).
- ML scoring (`ml_inference.R`) — SP4+ if ever ported (depends on whether a trained model travels with SESPy).
- Claude API backend — SP4.
- i18n for verbs in rationale strings — future polish (would need `wizard.connection_verb.<conn_type>` keys).
- Hot-reload of `connection_keywords.json` — never planned; restart Python.
- Per-pair confidence beyond `{0.3, 0.6, 0.9}` — would require a different relevance algorithm (e.g., TF-IDF weighting by corpus frequency); out of scope for the rule-based-only choice.
- Connection-direction inference (auto-detecting whether `(A, B)` should be `A→B` or `B→A` based on element types) — N/A: the 10 connection types are fixed by the DAPSI(W)R(M) framework; direction is determined by from-type/to-type, not inferred.

---

## 11. Definition of done

- `sespy/connection_keywords.json` exists and parses; `sespy/connection_scorer.py` loads it via `_load_keywords()`.
- `ELEMENT_TYPE_MAP` lives in `sespy/data_structure.py` (relocated); `sespy/wizard.py` re-exports it via `from .data_structure import ELEMENT_TYPE_MAP` so SP1 callers work unchanged.
- `suggest_connections(WizardState(elements=[]))` returns `[]`.
- `suggest_connections(state)` for a multi-type state with overlap-rich labels returns a non-empty list, all items typed `ConnectionSuggestion`, all confidences in `{0.3, 0.6, 0.9}`, all polarities in `{"+", "-"}`.
- All 10 connection types produce at least some suggestions for the designed-to-overlap reference fixture in `test_connection_scorer.py` (≥2 elements per type, labels chosen to hit ≥1 keyword per pair).
- Per-type cap honored: ≤ 15 suggestions per connection type.
- Threshold honored at the floor: pairs with `confidence == 0.3` survive (matching R's `>=` semantics at line 452).
- `tests/test_connection_scorer.py`: 33 logical tests pass (`pytest -q` reports 46 items including the 14-case parametrize expansion of `test_verb_selection_per_from_slug_polarity_pair`).
- `tests/test_wizard.py`: renamed test passes; the rest are unchanged.
- All existing SP1+SP2 unit tests pass (134 baseline preserved); `pytest -q` reports `180 passed` post-SP3 (134 + 46 pytest items).
- All 6 SP1 e2e cases pass; case 1 (full run) shows ≥1 connection suggestion at step 11 with the Coastal Tourism template (which has ≥2 elements per type).
- Browser smoke at step 11: connection_review table populates with ≥1 row, accept/reject toggles work (renderer behavior is SP1's; SP3 just supplies real rows).
- `pyproject.toml` includes the new `[build-system]` + `[tool.setuptools.packages.find]` + `[tool.setuptools.package-data]` entries; a one-shot CI/manual `pip install . && python -c "import sespy.connection_scorer, sespy.regional_seas"` from a throwaway micromamba env passes (also retroactively fixes SP2's latent `pip install` hazard; CLAUDE.md forbids `python -m venv` on this machine). This is a CI step, NOT a pytest test — running pytest from the source tree always finds the JSONs via `Path(__file__).parent`.
- `README.md` reflects the new unit-test count (180, matching `pytest -q` output).
- Branch `feat/ai-isa-wizard-sp3` ready for fast-forward merge to main.
