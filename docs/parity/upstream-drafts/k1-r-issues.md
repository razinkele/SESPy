# Upstream R issue drafts from K1

Drafts only. Nothing here has been filed; the user files them on the R
repository (MarineSABRES_SES_Shiny). They come from SESPy K1 (knowledge-base
parity, SESPy 1.16.0), which ports R's knowledge-base lookup, suggestions and
Regional Context report section exactly, quirks included, and reports the
quirks here instead of fixing them in SESPy.

All findings are against R **v1.35.6** (`d1a655a`). Line numbers are at that
tag. Re-check them against the current R `main` before filing.

---

## 1. Habitat lookup lands on unexpected contexts; five contexts are unreachable from the wizard

**Where:** `functions/ses_knowledge_db_loader.R`, `.build_context_key()`
(from line 94) and `.find_context()` (from line 142).

**What happens.** The AI assistant's sea × ecosystem choices (the
`ecosystem_types` of each sea in `modules/ai_isa_knowledge_base.R`) are
mapped to a knowledge-base context by keyword rules, then a prefix match,
then a fallback to the sea's first context. Of the 69 choices, 29 hit a
keyword rule (`exact`; not always the context the name suggests, e.g.
Atlantic "Open ocean" and "Continental shelf" → `atlantic_offshore`), 2 match
by prefix, 26 fall back to
another habitat of the same sea (`sea_only`) and 12 (Irish Sea, East
Atlantic) have no context at all and use `generic_fallback`. Highlights:

- Every **Pacific** choice resolves to `pacific_island_atoll`: Island and
  Atoll by prefix, Coral reef, Open ocean, Coastal waters, Mangrove and
  Offshore waters by fallback.
- Every **Indian Ocean** choice resolves to `indian_ocean_coral_reef`;
  `indian_ocean_island` is never reached, not even from "Island".
- Same-sea fallbacks: North Sea Open coast, Rocky shore and Sandy beach →
  `north_sea_offshore`; Mediterranean Sandy beach and Offshore waters →
  `mediterranean_lagoon`; Black Sea Delta, Coastal lagoon, Offshore waters
  and Estuary → `black_sea_open_coast`; Caribbean Mangrove, Sandy beach and
  Open coast → `caribbean_coral_reef`; Arctic Open ocean, Coastal waters and
  Continental shelf → `arctic_sea_ice`.
- Atlantic "Coastal upwelling" resolves (as `exact`) to `atlantic_open_coast`,
  through the bare `coast(?!al lagoon)` branch (line 112).
- `irish_sea` and `east_atlantic` have no contexts. The wizard shows
  `generic_fallback` items badged as knowledge-base items, and the report
  has no site context, because `get_kb_context_for_report` needs a real
  context.

**Unreachable from the wizard's choices:** `tropical_mangrove`,
`indian_ocean_island`, `macaronesia_island`, `macaronesia_seamount` and
`macaronesia_open_coast` (33 contexts, 28 reached). The wizard's sea list has
no macaronesia entry. A legacy `macaronesia` slug from a saved project does
resolve (with "Open coast" exactly to `macaronesia_open_coast`, otherwise to
`macaronesia_island`), so the `macaronesia_*` contexts are reachable only
that way.

**Related, in the same area:** `match_user_connections_to_kb()`
(`functions/kb_report_helpers.R`, from line 105) tests
`grepl(tolower(user_from), tolower(kb_from), fixed = TRUE)`. An empty user
label is a substring of every string, so a connection whose element label is
empty matches the first knowledge-base connection whose other end matches.

**Suggested fix.** Map each wizard choice to a context explicitly (a table
in the knowledge base or next to `ecosystem_types`), or add the missing
contexts, and make the fallback visible (e.g. say "showing suggestions for
<context>"). Skip empty labels in the matcher.

**Full table** (captured by running R v1.35.6 headless over every wizard
choice; SESPy pins it as `tests/parity/r_fixtures/k1/lookup.json.gz`).
`match`: `exact` = keyword rule hit, `prefix` = prefix match, `sea_only` =
fallback to the sea's first context, `fallback` = no context for the sea
(`generic_fallback`).

| # | Sea | Ecosystem choice | Resolved key | Match |
|---|---|---|---|---|
| 1 | `baltic` | Open coast | `baltic_open_coast` | exact |
| 2 | `baltic` | Rocky coast (Schären) | `baltic_rocky_coast` | exact |
| 3 | `baltic` | Archipelago | `baltic_archipelago` | exact |
| 4 | `baltic` | Island | `baltic_island` | exact |
| 5 | `baltic` | Estuary | `baltic_estuary` | exact |
| 6 | `baltic` | Coastal lagoon | `baltic_lagoon` | exact |
| 7 | `baltic` | Offshore waters | `baltic_offshore` | exact |
| 8 | `mediterranean` | Open coast | `mediterranean_open_coast` | exact |
| 9 | `mediterranean` | Island | `mediterranean_island` | exact |
| 10 | `mediterranean` | Coastal lagoon | `mediterranean_lagoon` | exact |
| 11 | `mediterranean` | Rocky shore | `mediterranean_rocky_shore` | exact |
| 12 | `mediterranean` | Sandy beach | `mediterranean_lagoon` | sea_only |
| 13 | `mediterranean` | Seagrass meadow | `mediterranean_seagrass` | exact |
| 14 | `mediterranean` | Offshore waters | `mediterranean_lagoon` | sea_only |
| 15 | `north_sea` | Open coast | `north_sea_offshore` | sea_only |
| 16 | `north_sea` | Estuary | `north_sea_estuary` | exact |
| 17 | `north_sea` | Tidal flat | `north_sea_tidal_flat` | exact |
| 18 | `north_sea` | Offshore waters | `north_sea_offshore` | exact |
| 19 | `north_sea` | Rocky shore | `north_sea_offshore` | sea_only |
| 20 | `north_sea` | Sandy beach | `north_sea_offshore` | sea_only |
| 21 | `irish_sea` | Open coast | `(none)` | fallback |
| 22 | `irish_sea` | Estuary | `(none)` | fallback |
| 23 | `irish_sea` | Coastal lagoon | `(none)` | fallback |
| 24 | `irish_sea` | Rocky shore | `(none)` | fallback |
| 25 | `irish_sea` | Sandy beach | `(none)` | fallback |
| 26 | `irish_sea` | Offshore waters | `(none)` | fallback |
| 27 | `east_atlantic` | Open coast | `(none)` | fallback |
| 28 | `east_atlantic` | Continental shelf | `(none)` | fallback |
| 29 | `east_atlantic` | Offshore waters | `(none)` | fallback |
| 30 | `east_atlantic` | Rocky shore | `(none)` | fallback |
| 31 | `east_atlantic` | Sandy beach | `(none)` | fallback |
| 32 | `east_atlantic` | Estuary | `(none)` | fallback |
| 33 | `black_sea` | Open coast | `black_sea_open_coast` | exact |
| 34 | `black_sea` | Delta | `black_sea_open_coast` | sea_only |
| 35 | `black_sea` | Coastal lagoon | `black_sea_open_coast` | sea_only |
| 36 | `black_sea` | Offshore waters | `black_sea_open_coast` | sea_only |
| 37 | `black_sea` | Estuary | `black_sea_open_coast` | sea_only |
| 38 | `atlantic` | Open ocean | `atlantic_offshore` | exact |
| 39 | `atlantic` | Island | `atlantic_island` | exact |
| 40 | `atlantic` | Estuary | `atlantic_estuary` | exact |
| 41 | `atlantic` | Continental shelf | `atlantic_offshore` | exact |
| 42 | `atlantic` | Coastal upwelling | `atlantic_open_coast` | exact |
| 43 | `atlantic` | Open coast | `atlantic_open_coast` | exact |
| 44 | `atlantic` | Offshore waters | `atlantic_offshore` | exact |
| 45 | `pacific` | Coral reef | `pacific_island_atoll` | sea_only |
| 46 | `pacific` | Island | `pacific_island_atoll` | prefix |
| 47 | `pacific` | Atoll | `pacific_island_atoll` | prefix |
| 48 | `pacific` | Open ocean | `pacific_island_atoll` | sea_only |
| 49 | `pacific` | Coastal waters | `pacific_island_atoll` | sea_only |
| 50 | `pacific` | Mangrove | `pacific_island_atoll` | sea_only |
| 51 | `pacific` | Offshore waters | `pacific_island_atoll` | sea_only |
| 52 | `indian` | Coral reef | `indian_ocean_coral_reef` | sea_only |
| 53 | `indian` | Island | `indian_ocean_coral_reef` | sea_only |
| 54 | `indian` | Mangrove | `indian_ocean_coral_reef` | sea_only |
| 55 | `indian` | Open coast | `indian_ocean_coral_reef` | sea_only |
| 56 | `indian` | Lagoon | `indian_ocean_coral_reef` | sea_only |
| 57 | `indian` | Offshore waters | `indian_ocean_coral_reef` | sea_only |
| 58 | `caribbean` | Coral reef | `caribbean_coral_reef` | exact |
| 59 | `caribbean` | Island | `caribbean_island` | exact |
| 60 | `caribbean` | Mangrove | `caribbean_coral_reef` | sea_only |
| 61 | `caribbean` | Seagrass bed | `caribbean_seagrass` | exact |
| 62 | `caribbean` | Sandy beach | `caribbean_coral_reef` | sea_only |
| 63 | `caribbean` | Open coast | `caribbean_coral_reef` | sea_only |
| 64 | `arctic` | Sea ice | `arctic_sea_ice` | exact |
| 65 | `arctic` | Island | `arctic_island` | exact |
| 66 | `arctic` | Open ocean | `arctic_sea_ice` | sea_only |
| 67 | `arctic` | Fjord | `arctic_fjord` | exact |
| 68 | `arctic` | Coastal waters | `arctic_sea_ice` | sea_only |
| 69 | `arctic` | Continental shelf | `arctic_sea_ice` | sea_only |

---

## 2. The knowledge-base seeding path in `generate_connections` never runs

**Where:** `modules/ai_isa/connection_generator.R`,
`generate_connections(elements, regional_sea = NULL, habitat = NULL)` (line
755); seeding block at lines 806-919.

**What happens.** The block that seeds connections from the knowledge base
(`get_context_connections(regional_sea, habitat)`, which would also add
Responses → Responses, Pressures → Pressures and State → State pairs) runs
only when `regional_sea` and `habitat` are both given. The only call site,
`modules/ai_isa/step_navigation.R:92`, is
`generate_connections(rv$elements)`, with neither. So the assistant never
uses the knowledge base's 1,183 curated connections, with their rationale,
references, time lag and reversibility, when it suggests links.

**Suggested fix.** Pass the selected sea and ecosystem at
`step_navigation.R:92`, or remove the dead block. If it is enabled, note that
it introduces the extension pairs into the suggestions.

---

## 3. `.map_category()` raises on an unmapped category instead of returning `NULL`

**Where:** `functions/country_governance_loader.R`, `.map_category()` (from
line 154).

**What happens.** The function looks the category up with
`mapping[[cat_lower]]` on a named character vector. For a name that is not
in the vector, `[[` raises "subscript out of bounds", so the following
`if (is.null(result)) return(NULL)` is never reached. For categories with
no mapping (pressures, states, impacts, ...), `get_governance_elements()` and
`get_socioeconomic_elements()` therefore always raise, and
`get_context_suggestions()` (`modules/ai_isa_knowledge_base.R`, lines
500-527) catches the error, logs "Governance lookup error ... using
hardcoded fallback" and calls the hardcoded fallback instead. Every such
call goes through the error path and the hardcoded tables, not the JSON
database, and fills the debug log with errors.

**Suggested fix.** `result <- unname(mapping[cat_lower]); if (is.na(result)) return(NULL)`,
or test `cat_lower %in% names(mapping)` first.

---

## 4. `country_governance_db.json` changed content without a version bump

**Where:** `data/country_governance_db.json`.

**What happens.** Between v1.31.0 and v1.33.0 the file went from 99 to 105
countries (MQ, GP and MF as EU members; HN, NI and GT) and the Caribbean list
from 21 to 27, with `"version": "1.0"` and `last_updated` unchanged. At
v1.35.6 it still says version `1.0` (`last_updated` 2026-10-17). The general
knowledge base (`ses_knowledge_db.json`) likewise stays at `"version": "1.0"`
across content changes (14 contexts edited and net -2 connections in
1.35.3-1.35.4).

**Why it matters.** Consumers that cache or vendor the file (SESPy pins it
by hash) cannot tell from the file itself that it changed.

**Suggested fix.** Bump `version` (or at least `last_updated`) whenever the
content changes, ideally checked by a test.
