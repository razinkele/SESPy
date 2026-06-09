# MosaicSES — Spatially Distributed, Connected SES Along the Land–Ocean Aquatic Continuum

**Repository:** `razinkele/MosaicSES` (separate from `razinkele/SESPy`; consumes SESPy as `sespy` library dependency via editable install)

**Status:** **Implemented** ✓ (v1) — shipped in MosaicSES `main` across chunks 1–4d (library, persistence, Shiny shell, topology, compartments, comparative, cross-view, project setup, recent projects, file flows + a11y). Phase-2 items (§11) remain deferred by design.
**Working name:** `MosaicSES` (alternatives: `SESPy-LOAC`, `SES-Continuum`).
**Pilot system:** Curonian Lagoon (Nemunas → Delta → Lagoon → Klaipėda Strait → SE Baltic).
**Scope:** v1 priorities A + B from brainstorming Q4 (per-compartment comparative dashboard + cross-compartment structural analyses). C–F deferred to phase 2.

### Revision log

- **2026-05-08** — Initial draft committed.
- **2026-05-09** — First multi-agent review pass (architecture / type-design / silent-failure / test-plan / scientific-accuracy reviewers in parallel). Applied changes:
  - **Architecture.** §2.1 rule 5 reframed: only downstream-only material channels DAG-validated; bidirectional channels exempt. New rule 6 mandates `event_bus.emit_isa_change()` after every compartment switch + `reactive.isolate()` in backwrite listener (silent-corruption fix). New rule 8: schema-version policy (refuse on unknown-future, migrate on older).
  - **Synthetic bottleneck.** §6.4 augmented: `internal_link` polarity pinned to `+`; polarity-composition correctness explained and pinned by tests; `expansion="strict" | "full"` mode added to `build_composite_digraph`.
  - **Type design.** §3 refactored: `Polarity`, `Strength`, `Archetype`, `ChannelType` declared as `Literal` aliases; `__post_init__` enforces ranges; `ValidationIssue` and `LoadReport` defined; `MultiSES.add_compartment / add_channel / remove_compartment` mutators added.
  - **Validation.** §3.1 split into hard invariants (raise) and soft invariants (warn-and-collect); stable error codes (`M001`/`W101`/etc.) for test assertions; logging channel specified.
  - **Persistence.** §6.1 mandates fsync + post-replace sanity check (OneDrive-aware) and `from_dict` returns `(MultiSES, LoadReport)`. `cross_compartment_loops` returns `(loops, truncated: bool)` so the cap is no longer silent.
  - **Curonian seed.** §8.2 corrects salmon-vs-sturgeon framing: Atlantic sturgeon (AphiaID 151802) is the Nemunas extirpation/reintroduction story (Stakėnas & Pilinkovskij, 2019), salmon was depleted-but-persistent (Leliūna & Virbickas, 2006). Sturgeon added to seed.
  - **Test plan.** §9.4 expanded from 80 to ~100 tests; double canary loops in Curonian seed; new `test_import_allowlist.py`; reactive-rebind promoted from one-off spike to permanent test (`test_compartment_switcher_rebind.py`); persistence test count increased from 8 to 12 to cover schema migration + crash semantics.
  - **Phase 2 backlog.** §11 expanded with atmospheric N deposition, coastal upwelling, SGD, riparian-buffer-as-archetype, climate cross-cutting Driver, larval drift, invasive species — all flagged by scientific reviewer as v1 omissions.
  - **Scientific framing.** §1.1 explicit caveat that cross-compartment `governance` / `economic_telecoupling` channels are an *operationalisation* of Elliott et al. (2017)'s nested framework, not a literal reading.
  - **References.** §12 adds 7 Curonian/Nemunas/Baltic citations from the scientific review.
- **2026-05-09 (second pass)** — Emerald Growth-lens review (3 specialist agents: framework-alignment / connectivity-literature / monograph-integration). The user is co-author of the foundational Emerald Growth paper (Tagliapietra, Povilanskas, Razinkovas-Baziukas & Taminskas 2020, `10.3390/w12030894`) and of an in-preparation EG monograph with Mike Elliott, Davide Tagliapietra, Ramūnas Povilanskas and Maciej Nyka. The review re-positioned the spec against this framework. Applied changes:
  - **Foundational citation.** Tagliapietra et al. 2020 EG paper added as §1.1 anchor and §12 first-listed reference (was previously absent from §12 — a critical citation gap).
  - **TW-centric positioning.** §1.1 reframed: while the LOAC scope is unchanged, the *analytical focus* is on Transitional Waters (estuaries / lagoons / deltas) as EG's focal objects; bordering compartments (river_upper/lower, coastal_sea) serve as source-and-receptor contexts. New `is_focal_tw: bool` flag on `Compartment` (true by default for `delta`, `estuary`, `lagoon` archetypes).
  - **Elliott four-flow connectivity definition** (materials, energy, organisms, finance — both ecological and societal). §5 now maps the 8 channels onto the four flows and *explicitly acknowledges* the energy gap (no `trophic_energy` channel in v1). `economic_telecoupling` clarified as the "finance" flow.
  - **Endogenic vs exogenic pressures** (Elliott 2011, `10.1016/j.marpolbul.2011.01.040`). New `pressure_origin: Literal["endogenic","exogenic",None]` tag on archetype default Pressures. §4.3 archetype defaults populated; cross-compartment pressures are exogenic by definition.
  - **Three-management-regime intersection** (WFD river-basin / EPSS estuarine / MSFD-MSPD coastal-marine). New `governance_regime: Literal[...] | None = None` field on `Channel`. Curonian seed §8 populated: HELCOM BSAP channels = `MSFD`; Nemunas catchment plan = `WFD`; Klaipėda port = `EPSS`.
  - **CICES v5.1 ES codes** promoted from phase-2 to v1. Optional `cices_code` field on Element; populated on Curonian seed `default_es` lists.
  - **Cooperation/Confrontation Integrity Index** (Povilanskas & Razinkovas-Baziukas 2023, `10.3390/su15139922`) promoted to v1: optional `cci_index: int | None` (0–10) on transboundary `governance` channels. Curonian transboundary channels (LT/RU, LT/BY) populated.
  - **New §1.7 "Position within the EG monograph"** declares the spec as the software realisation of Chapter 6 (Elliott, in prep) of the in-preparation EG monograph; explains how the spec consumes Chapters 1–5 as inputs.
  - **New §3.4 "Monograph terminology mapping"** maps spec slugs to EG-canonical terms (endogenic/exogenic, three-regime intersection, TW squeeze, 10-tenets, depolderization, designing new ecosystems).
  - **Phase 2 backlog (§11)** expanded with: `trophic_energy` channel (closes Elliott's energy-flow gap); `trophic_subsidy` channel (Polis 1997, Helfield-Naiman 2001 spatial-subsidy literature); `cultural_connectivity` channel (Elliott's "social/cultural" flow, currently completely unrepresented); 10-tenets evaluation framework (Elliott et al. 2017, 2025) on Responses; Emerald Justice integration (the user-developed parallel concept on equity); EG monograph deliverables (per-chapter analytical hooks).
  - **References (§12)** adds 11 connectivity-literature citations: Vannote 1980 (RCC); Junk-Bayley-Sparks 1989 (flood-pulse); Polis-Anderson-Holt 1997 (spatial subsidies); Helfield-Naiman 2001 (salmon-derived N); Cowen-Sponaugle 2009 (larval connectivity); Pineda-Hare-Sponaugle 2007 (larval transport); Waldman-Quinn 2022 (diadromous declines); Nakamura-Katano-Abe 2006 (dam barrier); Karstens-Kiesel-Petersen 2022 (Baltic hydrological connectivity); Liu et al. 2013 (telecoupling); Inácio-Schernewski-Nazemtseva 2018 (Curonian/Szczecin ES comparison); Bartoli-Žilius-Bresciani 2018 (Curonian cyanobacteria); Sruoga-Butkauskas-Ragauskas 2007 (Curonian eel genetics); Elliott 2011 (endogenic/exogenic pressures); Lonsdale et al. 2018 (EPSS).
  - **Demoted to "further applications" footnote in §12:** Hassan 2021, Caviedes 2019, Izar 2022, Murase 2025, Selfati 2023, Bruno 2018 — DAPSI/lagoon references that add little beyond Elliott 2017 + Polette 2026 + Whitfield 2020.
- **2026-05-09 (drift-fix from chunk-1 plan review)** — Five-agent review of the chunk-1 plan surfaced three drift items where the spec contradicted the plan after plan revisions:
  - **§4.3 archetype JSON** — `default_pressures` arrays restructured from flat strings to `{label, pressure_origin}` objects, satisfying §1.1(b)'s "v1 fully implements `pressure_origin` tag on archetype Pressures" claim. The original spec's example contradicted its own §1.1 promise; the chunk-1 plan caught this and restructured archetypes.json; now the spec follows.
  - **§3 `LoadReport`** — `warnings: list[ValidationIssue]` and `migrations_applied: list[str]` changed to `tuple[..., ...]` so `frozen=True` actually enforces immutability (a list field would still allow `.append()` to slip past `frozen=True` at runtime). Default literals updated from `[]` to `()`.
  - **§3.1 soft invariants** — added `W400_SCHEMA_VERSION_MIGRATED` (issued by the loader on missing or older `schema_version`, mandated by §2.1 rule 8 but not previously listed); added a clarifying note on W303 deferral pending Compartment country-metadata field in chunk 2.
  - **§3.2 Key design decisions** — added a new bullet documenting non-destructive round-trip via `Channel._unknown_channel_type_original` and `Compartment._unknown_archetype_original` private fields. Without this mechanism, save→load→save would silently rewrite phase-2 slugs to v1 placeholders — the chunk-1 plan caught this lossy-coercion bug and added the preservation fields; the spec now documents the contract.
- **2026-05-09 (delay field added)** — User flagged that Channel was missing a `delay` field, which `sespy.Connection` already carries. Cross-compartment delays are scientifically *more* important than within-compartment delays (governance cascades take years, sediment transport takes seasons, water discharge is hours). Added:
  - **§3 `Delay` Literal alias** (`{"immediate", "short", "medium", "long", "very_long"}`).
  - **§3 `Channel.delay: Delay = "immediate"` field** with `__post_init__` validation.
  - **§3 `Channel.delay_units: str | None = None`** as phase-2 reservation for numeric calibration.
  - **§3.1 hard-invariant `M205_INVALID_DELAY`** for delay outside the closed set.
  - **New §5.4.1 channel-type delay defaults table** — water_discharge=immediate, nutrients=short, sediment=medium, pollutants=long, diadromous=long, marine_estuarine=medium, governance=long, telecoupling=medium.
  - **§3.3 JSON envelope** includes `delay` field on Channel rows.
- **2026-05-09 (third pass — connectivity deep-dive)** — User asked for deeper coverage of connectivity literature. Found and added 11 Curonian-system connectivity references from the Klaipėda University CORPI / Marine Research Institute group (the user's own institutional context). These are *empirical anchors* for the v1 seed: they provide rate constants, seasonal stoichiometries, and benthic-pelagic coupling mechanisms that *make the eutrophication–governance demo loop* (§8.4 Loop 1) scientifically defensible to Lithuanian / Baltic reviewers. Added under new scientific-basis §9.7.1:
  - Žilius et al. 2024 (`10.5194/egusphere-2023-3054`) — riverine inputs + phytoplankton control NO₃ cycling; spring/summer benthic-pelagic coupling regimes.
  - Žilius et al. 2021a (`10.3389/fmicb.2020.610269`) — zebra mussel holobiont N₂ fixation in Curonian sediments.
  - Žilius et al. 2020 (`10.5194/bg-2020-419`) — N₂ fixation + remote sensing for lagoon-scale N-budget.
  - Žilius et al. 2021b (`10.3389/fmicb.2020.612700`) — denitrification + N uptake in turbid estuary; ~35–100% N attenuation.
  - Vybernaite-Lubiene et al. 2017 — Nemunas catchment N/P/Si load time-series; basis for `nemunas_*` channel strengths in seed.
  - **Lesutienė et al. 2014** (`10.1016/j.ecss.2013.12.017`) — stable-isotope tracing of cyanobacterial-bloom C and N through Curonian food web. **User is co-author**; key empirical basis for phase-2 `trophic_energy` / `trophic_subsidy` channels.
  - **Pilkaitytė & Razinkovas 2006** — phytoplankton-bloom controls. **User is co-author.**
  - Daunys et al. 2006 (`10.1007/s10152-006-0028-5`) — zebra mussel suspended-material budget.
  - **Ferrarin et al. 2008** (`10.1007/s10750-008-9453-6`) — hydraulic-regime zonation of Curonian Lagoon. **User is co-author.**
  - Bresciani et al. 2012 — remote sensing of Curonian cyanobacteria.
  - Krevš et al. 2007 — Curonian primary-production zonation.
  - Čerkasova et al. 2021 (`10.1016/j.jhydrol.2021.126422`) — Nemunas climate-change modelling; basis for phase-2 climate-forcing channel.
  - Plus three additional Curonian-group works: Gasiūnaitė, Razinkovas-Baziukas & Grinienė 2012 (`10.5200/baltica.2012.25.07`) — user co-authored, Nemunas-Curonian plankton transition; Lesutienė et al. 2017 (`10.1016/j.ecss.2017.04.016`) — microcystin trophic connectivity; Žilius, Daunys, Petkuvienė & Bartoli 2012 (`10.4081/jlimnol.2012.e33`) — benthic-pelagic O/N/P fluxes.

  Also added **12 canonical connectivity-science references** that anchor the spec's connectivity claims to the broader literature (added under §9.6.0 and §9.6.2 of scientific basis):
  - **Sheaves 2009** (`10.3354/meps08121`) "*Consequences of ecological connectivity: the coastal ecosystem mosaic*" — **conceptual ancestor of the name MosaicSES.** Reframes connectivity as multi-flow habitat-mosaic dynamics. **Highest-priority addition; future MosaicSES publications must cite as origin.**
  - **Pringle 2001** (`10.1890/1051-0761(2001)011[0981:hcatmo]2.0.co;2`) — defines hydrologic connectivity as "matter, energy, organisms" — directly maps to Elliott's EG four-flow.
  - **Pilosof, Porter, Pascual & Kéfi 2017** (`10.1038/s41559-017-0101`) — multilayer ecological networks; mathematical foundation for MosaicSES's compartment × DAPSI × channel architecture.
  - **Tylianakis & Morris 2017** (`10.1146/annurev-ecolsys-110316-022821`) — networks across environmental gradients.
  - **Calabrese & Fagan 2004** (`10.1890/1540-9295(2004)002[0529:acgtcm]2.0.co;2`) — structural / potential / actual-functional connectivity classification. Used to position v1 channels as "structural-with-implied-potential" connectivity (NOT actual-flow connectivity).
  - **Fausch, Torgersen, Baxter & Li 2002** (`10.1641/0006-3568(2002)052[0483:ltrbtg]2.0.co;2`) — landscapes-to-riverscapes scale-bridge.
  - **Bracken & Croke 2007** (`10.1002/hyp.6313`) — geomorphological foundation for `sediment` channel.
  - **Thorp, Thoms & Delong 2006** (`10.1002/rra.901`) — riverine ecosystem synthesis update to RCC.
  - **Pérez-Ruzafa, Pérez-Ruzafa & De Pascalis 2019** (`10.1016/j.ecss.2018.02.031`) — **canonical inter-lagoon comparative reference** explicitly comparing Mar Menor, Curonian, and Venice on Lagrangian connectivity asymmetry. Directly justifies the `lagoon` archetype.
  - **Hull & Liu 2018** (`10.5751/es-10494-230441`) — telecoupling update with "spillover" + multi-level governance vocabulary.
  - **Macreadie et al. 2023** (`10.1111/rec.13739`) — BlueCAM blue-carbon accounting model; basis for phase-2 `blue_carbon` channel.
  - **Lin, Wang & Zhu 2025** (`10.1029/2024jc022287`) — extreme-heatwave reorganisation of estuarine connectivity; closes the climate-connectivity gap.

  New scientific-basis sections added: §9.6.0 conceptual / canonical connectivity references; §9.6.1 functional-vs-structural channel classification (positions v1 as potential-connectivity claims, not actual-flow); §9.6.2 climate change as connectivity disruptor; §9.7.1 Curonian benthic-pelagic and microbial connectivity (11 user-group references).

---

## 1. Goal & scope

### 1.1 Scientific framing — Emerald Growth as the parent framework

MosaicSES is the software operationalisation of the **Emerald Growth (EG)** framework (Tagliapietra, Povilanskas, Razinkovas-Baziukas & Taminskas 2020, `10.3390/w12030894`) for managing transitional waters (TW: estuaries, lagoons, deltas, rias) as the third-colour space between Green Growth (terrestrial) and Blue Growth (marine). EG's central claim is that TW deserve a dedicated framework because they are neither riverine nor marine but occupy a distinct ecological, legal, and managerial regime — a continuum not captured by either parent paradigm.

EG operationalises connectivity. Mike Elliott's authoritative EG definition (in the in-preparation EG monograph) reads: *"the ability for transitional waters to have a healthy ecological structure and functioning **because of their connectivity** with the catchment and adjacent marine areas in order to create ecosystem services from which society can obtain goods and benefits without having an adverse effect on that ecological structure and functioning; the natural (ecological) and societal (economic, culture, governance and management) connectivity is required for maintaining the **transfer and fluxes of materials, energy, organisms and finance**."* The eight channel types in §5 are the v1 instantiation of these four flows; §5 explicitly acknowledges the energy-flow gap left for phase-2.

The compartment-graph architecture is grounded in Elliott, Burdon & Atkins (2017)'s call for an *interlinked, nested-DAPSI(W)R(M) framework* "to reflect the continuum between adjacent ecosystems" (`10.1016/j.marpolbul.2017.03.049`). Each compartment is a self-contained DAPSI(W)R(M) SES (a vanilla `sespy.data_structure.Project`); the nested structure links them through the typed channels.

**Transitional Waters as analytical focus.** While MosaicSES models the full LOAC from headwaters to open shelf, its analytical centre of gravity is on TW compartments (`delta`, `estuary`, `lagoon`). Bordering compartments (`river_upper`, `river_lower`, `coastal_sea`) serve as source-and-receptor contexts for TW dynamics — supplying material loads, receiving exports, providing larvae and adult fish stocks, hosting upstream Drivers and downstream Markets. The data model carries an `is_focal_tw: bool` flag on `Compartment` (defaults `True` for the three TW archetypes) so that the Comparative dashboard can produce a TW-first summary view and EG-aligned publications can declare scope precisely.

**EG framework dimensions named here, with implementation depth varying.** v1 fully implements:
- (a) The connectivity backbone — 8 typed channels mapped onto Elliott's four-flow definition (§5).
- (b) **Endogenic vs exogenic pressure distinction** (Elliott 2011, `10.1016/j.marpolbul.2011.01.040`) — `pressure_origin: Literal["endogenic","exogenic",None]` tag on archetype Pressures (§4.3). Endogenic pressures originate inside a compartment (locally manageable); exogenic pressures originate outside (requiring upstream-governance channels or force-majeure acknowledgment). Cross-compartment pressures are exogenic by definition.
- (c) **Three-management-regime intersection** — WFD river-basin / EPSS-Lonsdale estuarine (Lonsdale et al. 2018) / MSFD-MSPD coastal-marine — encoded as `governance_regime: Literal[...] | None` on `Channel` (§5).
- (d) **Transboundary cooperation/confrontation indexing** (Povilanskas & Razinkovas-Baziukas 2023, `10.3390/su15139922`) — `cci_index: int | None` (0–10) on transboundary `governance` channels (§8).
- (e) **CICES v5.1 ecosystem-service coding** on Element-typed Ecosystem Services (§4.3).

v1 acknowledges-but-defers (phase-2 backlog §11):
- The **10-tenets framework** (Elliott et al. 2017, 2025 — Ecologically sustainable / Technologically feasible / Economically viable / Socially desirable / Legally permissible / Administratively achievable / Politically expedient / Ethically defensible / Culturally inclusive / Effectively communicable) as a Response-evaluation layer.
- **Trophic-energy connectivity** (the energy limb of Elliott's four-flow definition).
- **Socio-cultural connectivity** (the culture limb — heritage, identity, livelihoods crossing administrative boundaries).
- **Emerald Justice** — a parallel emerging concept developed by Maciej Nyka and the user's research group on equity dimensions: ocean grabbing, fisheries livelihoods, gender, indigenous rights, exclusion from decision-making.

**Operational-extension caveat (unchanged from first review pass).** Elliott et al. (2017) define Responses-as-Measures as acting on Activities/Pressures *within* the managed system, and the nested framework calls for "interlinked" and "nested" structures without explicitly endorsing cross-system Response→Pressure causation as graph edges. MosaicSES's `governance` channel and `economic_telecoupling` channel are therefore an **operationalisation** of the nested framework, not a literal reading. Polette et al. (2026), Lovecraft & Meek (2019) and the in-preparation EG monograph provide nesting precedents but none formalises this graph representation. The choice is defensible — coastal MPA designations *do* drive upstream catchment regulation in practice — but the spec is explicit that this is an extension.

Anchor literature:

**Parent framework**
- **Tagliapietra, Povilanskas, Razinkovas-Baziukas & Taminskas 2020** — `10.3390/w12030894` — Emerald Growth foundational paper. **Parent framework.**

**Conceptual ancestors**
- **Sheaves 2009** — `10.3354/meps08121` — *Consequences of ecological connectivity: the coastal ecosystem mosaic.* **The conceptual ancestor of the name MosaicSES.** Reframes coastal connectivity as multi-flow habitat-mosaic dynamics.
- **Pringle 2001** — `10.1890/1051-0761(2001)011[0981:hcatmo]2.0.co;2` — Hydrologic connectivity defined as "matter, energy, organisms" — direct mapping to Elliott's EG four-flow taxonomy.
- **Pilosof, Porter, Pascual & Kéfi 2017** — `10.1038/s41559-017-0101` — Mathematical foundation for multilayer ecological networks; legitimises MosaicSES's compartment × DAPSI × channel architecture.

**DAPSI(W)R(M) lineage**
- Elliott, Burdon & Atkins 2017 — `10.1016/j.marpolbul.2017.03.049` — defines nested-DAPSI(W)R(M).
- Elliott 2011 — `10.1016/j.marpolbul.2011.01.040` — endogenic/exogenic pressures distinction.
- Elliott & O'Higgins 2020 — `10.1007/978-3-030-45843-0_4` — "Butterfly" extension with ES supply/demand.
- Lonsdale et al. 2018 — Estuarine Planning Support System (EPSS).
- Polette, Tischer & Elliott 2026 — `10.1016/j.ocecoaman.2025.108018` — applied DAPSI(W)R(M) for coastal management.

**Transboundary, sustainability circles, ES**
- Povilanskas & Razinkovas-Baziukas 2023 — `10.3390/su15139922` — transboundary TW cooperation/confrontation index.
- Povilanskas, Jurkienė & Dailidienė 2024 — `10.3390/su16062544` — Circles of Coastal Sustainability + EG (Lake Liepāja worked example).
- Inácio, Schernewski & Nazemtseva 2018 — `10.1007/s11284-018-1643-8` — Curonian + Szczecin Lagoons ES (CICES-ready precedent).

**Estuary / lagoon connectivity**
- **Pérez-Ruzafa, Pérez-Ruzafa & De Pascalis 2019** — `10.1016/j.ecss.2018.02.031` — Mar Menor / Curonian / Venice lagoon connectivity asymmetry; **canonical inter-lagoon comparison.**
- Whitfield 2020 — `10.1111/jfb.14476` — estuarine fish-guild dependency continuum.

**Connectivity classifications**
- Calabrese & Fagan 2004 — `10.1890/1540-9295(2004)002[0529:acgtcm]2.0.co;2` — structural / potential / actual connectivity taxonomy.

**Telecoupling**
- Liu et al. 2013 — `10.5751/es-05873-180226` — telecoupling foundational paper.
- Hull & Liu 2018 — `10.5751/es-10494-230441` — telecoupling update with spillover + multi-level governance.

**ICES**
- `WGDIAD`, `WKESDLS`, `WGEEL`, `WGBAST` — diadromous species working groups.

### 1.2 In scope (v1)

1. Library `multises/`: `MultiSES`, `Compartment`, `Channel` dataclasses + JSON persistence + composite-graph builder.
2. **Priority A** — per-compartment analyses presented as a comparative grid: every existing SESPy analysis run on each compartment, results laid out side-by-side (heatmap, leverage hotspots, response–pressure gap).
3. **Priority B** — cross-compartment structural analyses: composite digraph with channel edges, cross-compartment loop detection (cycles touching ≥ 2 compartments), inter-compartment leverage / bridge metrics.
4. Shiny shell: SESPy embedded with compartment switcher + four new pages (Project Setup / Topology / Compartments / Comparative / Cross-compartment view).
5. Curonian Lagoon seed dataset: 6 compartments × ~15–20 elements each, ~25 channels, seeded from ICES diadromous catalogue + literature.

### 1.3 Out of scope (deferred)

- Flux units / timesteps / numerical propagation (priority C, phase 2).
- Scenario simulation / intervention propagation across compartments (priority D, phase 2).
- GeoJSON / map view (priority E, phase 2).
- Diadromous-species "thread" analysis with life-stage edges (priority F, phase 2).
- Internationalisation: v1 is **English-only**. Phase-2 fields (`geometry`, `units`, `timestep`, `lifestage`) are reserved as nullable now to avoid schema breaks later.
- Export reports (HTML / PDF / Word) — phase 2.
- Autosave at the MultiSES level — phase 2.

### 1.4 Non-goals

MosaicSES is **not** a hydrological model, **not** a population dynamics model, **not** a GIS system. It is a *coupled-CLD analysis framework* — qualitative graph topology with confidence/strength weights, in the spirit of SESPy's parent. Numerical models can be plugged in at phase-2 by populating the reserved `units`/`timestep` fields on channels.

### 1.5 Decisions baked in (from brainstorming, 2026-05-08)

| Decision | Choice | Reason |
|---|---|---|
| Project structure | Sister tool wrapping SESPy | Inter-compartment edges have different semantics from DAPSI; collapsing them would break SESPy's existing algorithms. Composition over inheritance keeps SESPy untouched. |
| Topology shape | Typed compartment archetypes, free DAG | Real river-coast systems branch (Po) and aren't always linear (Curonian). Typed archetypes carry default DAPSI vocabulary + fish-guild knowledge so each compartment isn't a blank slate. |
| Inter-compartment edges | Eight typed channels | Water/nutrients/sediment/pollutants (downstream-only), diadromous & marine-estuarine organisms (bidirectional), governance (any direction), economic telecoupling (any direction). The science demands type distinctions. |
| v1 priority | A + B (dashboard + structural) | C–F all in scope as phase 2; A+B are achievable in a single design cycle and reuse SESPy heavily. |
| Pilot dataset | Curonian Lagoon | Six-archetype fit (Klaipėda Strait as estuary), local domain expertise, ICES Baltic data leverage, transboundary realism. |
| User-facing form | Library + minimal Shiny shell (compartment switcher pattern) | Library is the truth, ~70% of v1 effort. Shell is thin: switcher remounts SESPy modules with a different `project_data` reactive — zero changes to SESPy. |

### 1.6 EG monograph coverage matrix

The in-preparation Emerald Growth monograph (multi-author: Razinkovas-Baziukas, Nyka, Tagliapietra, Povilanskas, Elliott) has six chapters. MosaicSES draws on Chapters 1–5 as inputs and *operationalises* Chapter 6.

| Monograph chapter | Author | What MosaicSES does with it |
|---|---|---|
| Ch. 1 — Geographical definition of TWs (WFD + geography) | Razinkovas-Baziukas | Constrains the `estuary` / `lagoon` / `delta` archetype semantics; archetype `typical_position` field carries the WFD geographical reading. |
| Ch. 2 — Legal conceptualisation (WFD vs MSPD vs international) | Nyka | Motivates the `governance_regime` field on `Channel` (§5); v1 distinguishes WFD / EPSS / MSFD / MSPD / national / international jurisdictions. |
| Ch. 3 — TW specific ecology | Tagliapietra | Supplies ecotone, saprobity, and Remane-minima vocabulary for archetype default DAPSI elements. v1 imports the language verbatim into archetype `description` fields. |
| Ch. 4 — TW ecosystem services & societal benefits | Razinkovas-Baziukas | Motivates **CICES v5.1 ES coding** on Element-typed Ecosystem Services (promoted to v1). Curonian seed populates `cices_code` for all `default_es` entries. |
| Ch. 5 — Transboundary TW & management | Povilanskas | Motivates the **Cooperation/Confrontation Integrity Index** (`cci_index`) on transboundary `governance` channels (promoted to v1). The Curonian system (LT/RU/BY) populates this. |
| Ch. 6 — System approach to TW & EG | Elliott (in prep) | **MosaicSES is the operational realisation of this chapter.** See §1.7. |

### 1.7 Position within the EG monograph

MosaicSES is the **software realisation of Chapter 6** ("System approach to TW and Emerald Growth", Elliott, in prep) of the multi-author *Emerald Growth* monograph. The monograph defines Emerald Growth as the meeting of three management regimes (WFD river-basin / EPSS estuarine / MSFD-MSPD coastal-marine) and characterises EG's system through endogenic-managed vs exogenic-unmanaged pressures, the 10-tenets of sustainable adaptive management, the three-regime governance intersection, and transboundary continuity. MosaicSES inherits this conceptual frame and provides the graph-theoretic operationalisation Chapter 6 currently describes only in prose.

**What MosaicSES contributes back to the monograph** (i.e. analyses no chapter currently produces):
1. **Cross-compartment loop detection** with polarity arithmetic (§6.4) — the eutrophication–governance balancing loop in the Curonian seed (§8.4) is the demonstration figure.
2. **Inter-compartment leverage / bridge metrics** (§6.4) — quantifies which compartment's Responses are most leveraged across the LOAC; surfaces estuaries as structural bottlenecks.
3. **Per-archetype comparative dashboard** across 6 archetypes (§7.4) — produces a TW-vs-bordering-context comparison table that Ch.6 needs in prose form.
4. **Confidence-weighted graph reasoning** with stable error codes (§3.1) — formalises Elliott's qualitative endogenic/exogenic distinction as a typed graph attribute.

Future EG monograph chapters and follow-on publications can cite this design spec and its companion scientific-basis document as the analysis-engine reference.

---

## 2. Architecture overview

```
┌──────────────────────── MosaicSES (NEW) ─────────────────────────┐
│                                                                  │
│  Library (pure Python, no Shiny)                                 │
│  ├── multises/data_structure.py    Compartment, Channel,         │
│  │                                  MultiSES envelope            │
│  ├── multises/archetypes.py        + archetypes.json             │
│  │                                  (6 compartment defaults)     │
│  ├── multises/channels.py          + channels.json               │
│  │                                  (8 channel-type definitions) │
│  ├── multises/composite.py         build_composite_digraph,      │
│  │                                  cross_compartment_loops,     │
│  │                                  inter_compartment_metrics    │
│  ├── multises/comparative.py       per_compartment_grid,         │
│  │                                  leverage_hotspots,           │
│  │                                  response_pressure_gap        │
│  ├── multises/curonian/*.json      Seed dataset                  │
│  └── multises/persistence.py       Atomic JSON save/load         │
│                                                                  │
│  Shiny shell (thin)                                              │
│  ├── app.py                        bs4Dash shell, reuses         │
│  │                                  sespy.dashboard              │
│  ├── modules/topology.py           NEW — compartment & channel   │
│  │                                  editor (pyvis canvas)        │
│  ├── modules/compartments.py       NEW — switcher + embedded     │
│  │                                  SESPy modules                │
│  ├── modules/comparative.py        NEW — per-compartment grid    │
│  ├── modules/cross_view.py         NEW — composite graph view    │
│  └── (re-mounted from sespy)       cld, loops, metrics,          │
│                                     leverage, boolean, sim,      │
│                                     bot, intervention,           │
│                                     simplify, isa_data_entry     │
│                                                                  │
└──────────────── depends on: ../SESPy (sespy package) ────────────┘
```

### 2.1 Architectural rules

1. **The library has zero Shiny imports.** Mirrors SESPy's `network.py` / `data_structure.py` discipline. Everything testable with pytest, no headless browser.
2. **A `Compartment` *contains* a `sespy.data_structure.Project`.** Not a copy, not a derived class — composition. This is what makes "every SESPy analysis works on a compartment for free" true.
3. **Composite digraph is *derived*, never persisted.** `build_composite_digraph(multises)` returns a `networkx.DiGraph`. Two edge kinds: SESPy DAPSI edges (one per `Connection` per compartment, namespaced by compartment id) and channel edges (one per `Channel`). Both carry `kind` attribute (`"dapsi"` | `"channel"` | `"internal_link"`) so analyses can filter.
4. **Cross-compartment loop = a cycle in the composite digraph that touches ≥ 2 distinct compartments.** Detection = `nx.simple_cycles` on the composite, then filter by `len({n.compartment for n in cycle}) >= 2`. Loop-polarity arithmetic reuses SESPy's classifier unchanged because channel edges carry the same `polarity ∈ {+, -}` attribute as DAPSI edges. `internal_link` edges always carry `polarity="+"` (neutral); their contribution to cycle polarity is multiplicative-identity by construction (see Section 6.4 for the polarity-composition test that pins this).
5. **Compartment-graph DAG property is per-channel-type, not global.** Downstream-only channel types (`water_discharge`, `nutrients`, `sediment`, `pollutants`) MUST form a DAG between compartments — `validate()` enforces this. Bidirectional / upstream-permitted channel types (`organisms_diadromous`, `organisms_marine_estuarine`, `governance`, `economic_telecoupling`) are explicitly exempt; they may form cycles between compartments. The composite digraph as a whole therefore can and should contain cycles — that is the scientific point of priority B.
6. **Compartment switcher = one shared `reactive.value(Project)` rebound on picker change, *plus* an explicit `event_bus.emit_isa_change()` call after every rebind.** Without the explicit emit, downstream SESPy modules that hold session-scoped derived state (e.g. `analysis_loops.py`'s `detected` reactive) retain stale loops from the previous compartment while their `classified()` calc now runs against new data — silent corruption. The backwrite listener (Section 7.3) must wrap its `project_data.get()` in `reactive.isolate()` to avoid an infinite reactivity loop.
7. **Persistence: one JSON envelope, with hard-error guarantees.** `MultiSES` serialises to a single file; each `Compartment`'s embedded `Project` uses SESPy's existing `Project.to_dict()`. Loader is forward-tolerant on **unknown slugs** (channel types, archetypes — warn-not-fail, since these are legitimate phase-2 forward-compat scenarios) but **hard-fails** on structural corruption: dangling channel endpoints, duplicate compartment or channel ids, polarity values outside `{+, -}`, confidence outside `[1, 5]`. See Section 3.1.
8. **Schema-version policy.** A loader encountering `schema_version > MULTISES_SCHEMA_VERSION` MUST refuse with an explicit error (no silent dropping of unknown structure). A loader encountering `schema_version < MULTISES_SCHEMA_VERSION` (or missing) MUST warn, run a migration shim, and proceed. Phase-2 fields (`geometry`, `units`, `timestep`, `lifestage`) are nullable in v1 and round-trip as `null` regardless of `schema_version`.
9. **Repo layout: sibling to SESPy.** `Marine-SABRES/MosaicSES/` next to `Marine-SABRES/SESPy/`. `pyproject.toml` declares `sespy` as a path-dependency until SESPy is published to PyPI.

---

## 3. Data model

Three new dataclasses, mirroring SESPy's `data_structure.py` style: stdlib-only, JSON-roundtrippable, frozen-by-convention. Type aliases use `typing.Literal` so IDEs / mypy catch invalid values at edit time without runtime cost.

```python
# multises/data_structure.py

from typing import Literal

MULTISES_SCHEMA_VERSION = 1

# --- Type aliases (Literal[]; zero runtime cost, full IDE/mypy support) ---

Polarity = Literal["+", "-"]
Strength = Literal["weak", "medium", "strong"]

# Channel propagation delay — qualitative timescale of cross-compartment
# connectivity. Mirrors sespy.Connection.delay but spans a wider range:
# water_discharge propagates in hours (immediate); sediment in months
# (medium); governance cascades over years (long).
Delay = Literal["immediate", "short", "medium", "long", "very_long"]

Archetype = Literal[
    "river_upper", "river_lower", "delta",
    "estuary", "lagoon", "coastal_sea",
    # phase-2 extras, accepted in v1 schema:
    "tributary", "floodplain", "wetland",
]

ChannelType = Literal[
    "water_discharge",
    "nutrients",
    "sediment",
    "pollutants",
    "organisms_diadromous",
    "organisms_marine_estuarine",
    "governance",
    "economic_telecoupling",
]

# Tuple sources of truth (used for runtime validation at JSON-load boundary
# where the Literal alias has been erased to plain `str`):
COMPARTMENT_ARCHETYPES: tuple[Archetype, ...] = (
    "river_upper", "river_lower", "delta",
    "estuary", "lagoon", "coastal_sea",
    "tributary", "floodplain", "wetland",
)

CHANNEL_TYPES: tuple[ChannelType, ...] = (
    "water_discharge", "nutrients", "sediment", "pollutants",
    "organisms_diadromous", "organisms_marine_estuarine",
    "governance", "economic_telecoupling",
)

# Set of channel types that MUST form a DAG across compartments (rule 5):
DOWNSTREAM_ONLY_CHANNELS: frozenset[ChannelType] = frozenset({
    "water_discharge", "nutrients", "sediment", "pollutants",
})

# --- Validation result types ---

@dataclass(frozen=True)
class ValidationIssue:
    """Result of multises.validate(). Stable `code` enables UI filtering and
    test assertions on identifier rather than human-prose `message`."""
    severity: Literal["error", "warning", "info"]
    code: str           # e.g. "M001_DUPLICATE_COMPARTMENT_ID", "M201_DANGLING_CHANNEL_SOURCE"
    message: str        # human-readable, may be i18n'd in phase 2
    path: str           # JSON-pointer-style location, e.g. "channels[3].source"

@dataclass(frozen=True)
class LoadReport:
    """Returned alongside MultiSES from from_dict / from_file. Carries warnings
    encountered during tolerant load (unknown slugs, missing schema_version,
    migrated fields) so the UI / caller can surface them. A clean load returns
    LoadReport(warnings=(), migrations_applied=()).

    Fields are tuples (not lists) so frozen=True actually enforces
    immutability (a list field would still allow .append() to slip past
    frozen=True at runtime)."""
    warnings: tuple[ValidationIssue, ...]
    migrations_applied: tuple[str, ...]   # e.g. ("v0_flat_isa_to_v1_envelope",)


# --- Domain dataclasses ---

# EG focal-object archetypes — Transitional Waters (TW) per Tagliapietra et al. 2020
TW_ARCHETYPES: frozenset[Archetype] = frozenset({"delta", "estuary", "lagoon"})

# Three-regime intersection (Tagliapietra et al. 2020 §3; Lonsdale et al. 2018 EPSS):
GovernanceRegime = Literal[
    "WFD",          # EU Water Framework Directive — river-basin
    "EPSS",         # Estuarine Planning Support System — Lonsdale et al. 2018
    "MSFD",         # EU Marine Strategy Framework Directive
    "MSPD",         # EU Marine Spatial Planning Directive
    "national",     # National jurisdiction (e.g. LT WMP, Habitats Directive transposition)
    "international", # International customary law / bilateral agreements
]

# Pressure origin per Elliott 2011 (`10.1016/j.marpolbul.2011.01.040`):
PressureOrigin = Literal["endogenic", "exogenic"]


@dataclass
class Compartment:
    id: str                              # e.g. "nemunas_lower"
    label: str                           # human-readable
    archetype: Archetype                 # validated at construction (post_init)
    project: Project                     # sespy.data_structure.Project (composition)
    description: str = ""
    geometry: dict | None = None         # phase-2: GeoJSON polygon; None in v1
    is_focal_tw: bool | None = None      # EG focal object flag (None = use archetype default)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError(f"Compartment.id must be a non-empty str (got {self.id!r})")
        if self.archetype not in COMPARTMENT_ARCHETYPES:
            # Unknown archetype is warn-not-fail at JSON-load level, but a direct
            # constructor call with a bogus archetype is a programmer error.
            raise ValueError(
                f"Unknown archetype {self.archetype!r}; expected one of "
                f"{COMPARTMENT_ARCHETYPES}"
            )
        if self.is_focal_tw is None:
            # Default focality from archetype: TW archetypes are focal
            self.is_focal_tw = self.archetype in TW_ARCHETYPES


@dataclass
class Channel:
    id: str                              # MUST be unique within MultiSES.channels
    source: str                          # compartment id (must resolve)
    target: str                          # compartment id (must resolve)
    channel_type: ChannelType
    polarity: Polarity = "+"
    strength: Strength = "medium"
    confidence: int = 3                  # 1..5 inclusive, enforced
    delay: Delay = "immediate"           # qualitative propagation delay
    description: str = ""

    # EG-aligned fields (added 2026-05-09 second review pass):
    governance_regime: GovernanceRegime | None = None
        # Three-regime intersection per Tagliapietra et al. 2020 §3.
        # Required-by-convention for channel_type == "governance"; advisory
        # otherwise. Validated as soft-warning W302_GOVERNANCE_REGIME_MISSING
        # if a governance channel has None.
    cci_index: int | None = None
        # Cooperation/Confrontation Integrity Index (Povilanskas &
        # Razinkovas-Baziukas 2023, `10.3390/su15139922`). 0 = highest
        # confrontation risk; 10 = highest cooperation. Only meaningful for
        # transboundary governance channels (i.e. when source.country !=
        # target.country at the compartment-metadata level).

    # phase-2 reserved (None in v1):
    units: str | None = None
    timestep: str | None = None
    lifestage: str | None = None
    delay_units: str | None = None       # phase-2: numeric calibration of `delay`

    def __post_init__(self) -> None:
        if self.polarity not in ("+", "-"):
            raise ValueError(f"Channel.polarity must be '+' or '-' (got {self.polarity!r})")
        if self.strength not in ("weak", "medium", "strong"):
            raise ValueError(f"Channel.strength invalid (got {self.strength!r})")
        if not 1 <= int(self.confidence) <= 5:
            raise ValueError(f"Channel.confidence must be in 1..5 (got {self.confidence!r})")
        if self.channel_type not in CHANNEL_TYPES:
            raise ValueError(
                f"Unknown channel_type {self.channel_type!r}; expected one of "
                f"{CHANNEL_TYPES}"
            )
        if self.cci_index is not None and not 0 <= self.cci_index <= 10:
            raise ValueError(f"Channel.cci_index must be in 0..10 (got {self.cci_index!r})")

@dataclass
class MultiSESMetadata:
    name: str = "Untitled MultiSES"
    description: str = ""
    da_site: str = ""
    river_basin: str = ""
    regional_sea: str = ""               # reuses sespy.regional_seas slugs
    focal_issue: str = ""
    spatial_scale: str = ""
    temporal_scale: str = ""
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = MULTISES_SCHEMA_VERSION

@dataclass
class MultiSES:
    metadata: MultiSESMetadata
    compartments: list[Compartment]
    channels: list[Channel]

    # Mutator methods that maintain cross-collection invariants. The Topology
    # editor in Section 7.2 is the primary mutator; raw list manipulation is
    # discouraged because it skips these guards.

    def add_compartment(self, c: Compartment) -> None:
        if any(existing.id == c.id for existing in self.compartments):
            raise ValueError(f"Duplicate compartment id {c.id!r}")
        self.compartments.append(c)

    def add_channel(self, ch: Channel) -> None:
        if any(existing.id == ch.id for existing in self.channels):
            raise ValueError(f"Duplicate channel id {ch.id!r}")
        cmp_ids = {c.id for c in self.compartments}
        if ch.source not in cmp_ids:
            raise ValueError(f"Channel.source {ch.source!r} not in compartments")
        if ch.target not in cmp_ids:
            raise ValueError(f"Channel.target {ch.target!r} not in compartments")
        self.channels.append(ch)

    def remove_compartment(self, compartment_id: str) -> list[Channel]:
        """Remove a compartment and all incident channels. Returns the
        cascaded-deleted channels for caller diagnostics."""
        cascaded = [ch for ch in self.channels
                    if ch.source == compartment_id or ch.target == compartment_id]
        self.channels = [ch for ch in self.channels if ch not in cascaded]
        self.compartments = [c for c in self.compartments if c.id != compartment_id]
        return cascaded

    def with_compartment_replaced(self, compartment_id: str, edited_project: Project) -> "MultiSES":
        """Return a new MultiSES with the specified compartment's project
        updated to edited_project. The compartment's id, archetype, and metadata
        remain unchanged; only the DAPSI graph (sespy.Project.isa_data) is
        replaced. Raises ValueError if compartment_id not found."""
        cmp = next((c for c in self.compartments if c.id == compartment_id), None)
        if not cmp:
            raise ValueError(f"Compartment {compartment_id!r} not found")
        new_cmp = cmp.replace(project=edited_project)
        new_compartments = [new_cmp if c.id == compartment_id else c
                           for c in self.compartments]
        return MultiSES(metadata=self.metadata, compartments=new_compartments,
                       channels=self.channels)
```

### 3.1 Validation invariants

Two layers, both feeding `ValidationIssue` results:

**Hard invariants (rejected at construction or at `from_dict`/`load` time, never tolerated):**
- Every `compartment.id` is unique. Code: `M001_DUPLICATE_COMPARTMENT_ID`.
- Every `channel.id` is unique. Code: `M002_DUPLICATE_CHANNEL_ID`.
- Every `channel.source` / `channel.target` resolves to a `compartment.id`. Code: `M201_DANGLING_CHANNEL_ENDPOINT`.
- Every `channel.polarity ∈ {"+", "-"}`. Code: `M202_INVALID_POLARITY`.
- Every `channel.strength ∈ {"weak", "medium", "strong"}`. Code: `M203_INVALID_STRENGTH`.
- Every `channel.confidence ∈ [1, 5]`. Code: `M204_INVALID_CONFIDENCE`.
- Every `channel.delay ∈ {"immediate", "short", "medium", "long", "very_long"}`. Code: `M205_INVALID_DELAY`.

These produce `ValidationIssue(severity="error", ...)` and **fail the load**: `from_dict` returns `MultiSES, LoadReport` only if the structure is parseable; structurally corrupt data raises `MultiSESIntegrityError`. The reasoning: forward-compat for unknown *slugs* (channel types / archetypes) is legitimate phase-2 prep, but forward-compat for malformed *values* (bad polarity, dangling endpoints) is silent data corruption — the composite-graph polarity arithmetic and cycle detection cannot recover from these.

**Soft invariants (warn-not-fail; surfaced in `LoadReport.warnings` and Topology UI banner):**
- `channel_type ∈ CHANNEL_TYPES` (warn-not-fail on unknown — phase-2 forward compat). Code: `W101_UNKNOWN_CHANNEL_TYPE`.
- `archetype ∈ COMPARTMENT_ARCHETYPES` (warn-not-fail on unknown — phase-2 forward compat). Code: `W102_UNKNOWN_ARCHETYPE`.
- For every `channel_type ∈ DOWNSTREAM_ONLY_CHANNELS` (water_discharge, nutrients, sediment, pollutants), the subgraph induced by channels of that type forms a DAG between compartments. Detected cycles produce a warning. Code: `W301_DOWNSTREAM_CHANNEL_CYCLE`. Bidirectional channel types are explicitly exempt.
- For every `channel.channel_type == "governance"`, `governance_regime` should be set. Code: `W302_GOVERNANCE_REGIME_MISSING`. Soft because the field is optional, but UI surfaces this prominently for EG-aligned analyses.
- For every governance channel between compartments in different countries (per compartment metadata), `cci_index` should be set. Code: `W303_TRANSBOUNDARY_CCI_MISSING`. Soft because the index is research-effort to populate, but the Curonian seed must satisfy this for the canary tests. **Note:** v1's `Compartment` dataclass does not yet carry a `country` field; W303 is therefore deferred to chunk 2 (when the Compartment metadata extension lands) — see chunk-1 plan self-review note.
- For metadata loaded with a missing or older `schema_version`, the loader migrates and emits a soft warning. Code: `W400_SCHEMA_VERSION_MIGRATED`. Mandated by §2.1 rule 8.
- Within each compartment, SESPy's `Project` validation runs unchanged. Issues bubble up with code prefix `S_*` to disambiguate from MosaicSES codes.

**Logging.** All `ValidationIssue` items emit through `logging.getLogger("multises").warning(code + " " + path + " " + message)` so library users not running the Shiny app still see the signal. The Shiny app installs a handler that converts WARNING+ messages into a Shiny notification toast (Section 9.4).

The codes above are stable identifiers; tests assert on the code, not the message text.

### 3.2 Key design decisions

- **Compartment ids namespace elements.** Composite-graph node keys = `f"{compartment.id}::{element.id}"` to prevent collision between two compartments' auto-generated `D1`, `P3`, etc.
- **Channel polarity matches `Connection`.** `+` = increase propagates as increase; `-` = damping. Allows SESPy's loop classifier to operate on the composite graph unchanged.
- **`organisms_diadromous` channels need TWO directed rows per species, not one** (e.g. salmon: spawning-adult upstream + smolt downstream). Phase-2 `lifestage` field disambiguates.
- **`governance` channels can flow upstream.** A coastal-MPA Response driving an upstream catchment Activity restriction is a `governance` channel `coastal_sea → river_upper`. Default polarity `-` (Responses dampen Pressures).
- **Phase-2 fields reserved as nullable now.** `geometry`, `units`, `timestep`, `lifestage` round-trip as `null` in v1. When phase-2 modules consume them, old project files load unchanged.
- **Non-destructive round-trip for unknown slugs.** `Channel._unknown_channel_type_original: str | None = None` and `Compartment._unknown_archetype_original: str | None = None` are private fields populated by `from_dict` whenever a v1 file presents a slug outside `CHANNEL_TYPES` / `COMPARTMENT_ARCHETYPES`. The dataclass's main `channel_type` / `archetype` field is set to a v1-valid placeholder so `__post_init__` accepts; `to_dict()` then emits the original from the `_unknown_*_original` field if present. This makes "unknown but tolerated" slugs (phase-2 channel types loaded by a v1 reader, e.g.) round-trip *non-destructively* — without this mechanism, save→load→save would silently rewrite the slug to the placeholder.

### 3.3 JSON envelope shape

```json
{
  "metadata": {
    "name": "Curonian Lagoon LOAC",
    "river_basin": "Nemunas",
    "regional_sea": "baltic_sea",
    "schema_version": 1,
    "created_at": "2026-05-08T12:00:00+00:00",
    "modified_at": "2026-05-08T12:00:00+00:00"
  },
  "compartments": [
    {
      "id": "curonian_lagoon",
      "label": "Curonian Lagoon",
      "archetype": "lagoon",
      "project": { /* sespy.Project.to_dict() */ },
      "geometry": null
    }
  ],
  "channels": [
    {
      "id": "nemunas_delta_to_curonian_nutrients",
      "source": "nemunas_delta",
      "target": "curonian_lagoon",
      "channel_type": "nutrients",
      "polarity": "+",
      "strength": "strong",
      "confidence": 4,
      "delay": "short",
      "governance_regime": null,
      "cci_index": null,
      "units": null,
      "timestep": null,
      "lifestage": null,
      "delay_units": null
    },
    {
      "id": "baltic_to_klaipeda_helcom_bsap_governance",
      "source": "baltic_se",
      "target": "klaipeda_strait",
      "channel_type": "governance",
      "polarity": "-",
      "strength": "medium",
      "confidence": 3,
      "delay": "long",
      "governance_regime": "MSFD",
      "cci_index": 7,
      "description": "HELCOM Baltic Sea Action Plan eutrophication-management measures cascading from Baltic-wide policy onto Klaipėda Strait management."
    }
  ]
}
```

### 3.4 Monograph terminology mapping

The EG monograph (Razinkovas-Baziukas, Nyka, Tagliapietra, Povilanskas, Elliott, in prep) uses domain-specific terminology that the spec encodes via short slugs. This table is the canonical mapping; future EG publications citing MosaicSES outputs should use the monograph terms in prose and the spec slugs in code/figures.

| Monograph term | Spec slug / encoding | Source |
|---|---|---|
| Endogenic managed pressure | `pressure_origin = "endogenic"` (on archetype Pressure defaults; phase-2 also on `Element` instances) | Elliott 2011, `10.1016/j.marpolbul.2011.01.040` |
| Exogenic unmanaged pressure | `pressure_origin = "exogenic"` | Elliott 2011 |
| Three-regime intersection | `governance_regime ∈ {WFD, EPSS, MSFD, MSPD}` (national/international as fall-throughs) | Tagliapietra et al. 2020 §3; Lonsdale et al. 2018 (EPSS) |
| TW squeeze | Phase-2 `climate_forcing` channel applied to TW compartments under climate-Driver pressure (analogous to Adriatic thermal squeeze) | Tagliapietra notes (EG monograph) |
| 10-tenets | Phase-2 `tenet_scores: dict[str, int]` field on Element (Response type) and on Channel (governance type) | Elliott et al. 2017 (`10.1016/j.marpolbul.2017.03.049`); 2025 revisited |
| Designing new ecosystems | Phase-2 scenario-design module (priority D from Q4) operating on archetype default DAPSI; depolderisation as worked example | Tagliapietra notes (EG monograph) |
| Cooperation/Confrontation Integrity Index | `cci_index ∈ [0, 10]` on `Channel` | Povilanskas & Razinkovas-Baziukas 2023 (`10.3390/su15139922`) |
| TW focal object / focality | `Compartment.is_focal_tw: bool` (defaults `True` for `delta`/`estuary`/`lagoon`) | Tagliapietra et al. 2020 (TW as central object of EG analysis) |
| Emerald Justice equity dimensions | Phase-2 `equity_dimensions: list[str]` on Element (Impact type) | Nyka, EG monograph; user's "emerald justice" working draft |
| CICES v5.1 ES code | Optional `cices_code: str` on Element (Ecosystem Service type) | CICES v5.1 (Haines-Young & Potschin 2018) |

---

## 4. Compartment archetypes (`multises/archetypes.json`)

Six v1 archetypes + three phase-2 reserved. JSON file mirrors SESPy's `regional_seas.json` pattern: eager-loaded at module import, schema-validated.

Each archetype carries: canonical label, characteristic DAPSI elements (seed lists — *suggestions, not enforcement*), characteristic fish guilds (Whitfield 2020 categories), iconic species AphiaIDs (forward integration with ICES `migratory_aphia_map`), typical position-in-continuum hint (drives "suggest neighbours" UI feature).

### 4.1 Six v1 archetypes

| Slug | Label | Position | Iconic species (AphiaID) |
|---|---|---|---|
| `river_upper` | Upper river / catchment | headwaters | salmon (127186), sea trout (127187), Arctic char (127188), river lamprey (101172) |
| `river_lower` | Lower river / floodplain | lowland | twaite shad (126415), allis shad (126413), smelt (126736), lampreys (101172, 101174) |
| `delta` | Delta / distributary | river_mouth | shads (126415, 126413), eel (126281), houting (154238) |
| `estuary` | Estuary / strait | freshwater-marine_transition | eel (126281), herring (126417), sprat (126425), flounder (127141), smelt (126736) |
| `lagoon` | Coastal lagoon | semi_enclosed_coastal | smelt (126736), shads (126415), eel (126281) |
| `coastal_sea` | Coastal sea / shelf | open_marine_shelf | cod (126436), herring (126417), sprat (126425), salmon (127186) |

### 4.2 Three phase-2 reserved

`tributary`, `floodplain`, `wetland`. Permitted in v1 schema (validation accepts them) but no default DAPSI lists provided.

### 4.3 Default DAPSI seed (full content per archetype)

Each archetype defines `default_drivers`, `default_activities`, `default_pressures`, `default_states`, `default_es`, `default_gb`, `fish_guilds`, `iconic_species_aphia`, `typical_position`, `label`. Used by `archetypes.seed_compartment(slug, ...)` to pre-populate a new compartment's `sespy.Project`. Confidence = 2 on every seeded element (deliberately lower than user-authored content) so seeded content visually flags as "review me" via SESPy's `CONFIDENCE_OPACITY` rendering.

The authoritative JSON content for the six archetypes is given below (verbatim shape; minor copy-edits permitted during implementation):

```json
{
  "compartment_archetypes": {
    "river_upper": {
      "label": "Upper river / catchment",
      "typical_position": "headwaters",
      "default_drivers": ["Forestry", "Agriculture (extensive)", "Hydropower demand"],
      "default_activities": ["Forestry harvest", "Diffuse-source agriculture", "Reservoir operation"],
      "default_pressures": [
        {"label": "Sediment loading", "pressure_origin": "endogenic"},
        {"label": "Nutrient runoff (N, P)", "pressure_origin": "endogenic"},
        {"label": "Flow regulation", "pressure_origin": "endogenic"},
        {"label": "Connectivity barriers (dams, weirs)", "pressure_origin": "endogenic"}
      ],
      "default_states": ["River geomorphology", "Hyporheic exchange", "Riparian vegetation"],
      "default_es": ["Salmonid spawning habitat", "Drinking water provisioning", "Carbon sequestration (riparian)"],
      "default_gb": ["Recreational angling", "Drinking water supply", "Tourism (wilderness)"],
      "fish_guilds": ["freshwater_resident", "diadromous_spawning"],
      "iconic_species_aphia": [127186, 127187, 127188, 101172]
    },
    "river_lower": {
      "label": "Lower river / floodplain",
      "typical_position": "lowland",
      "default_drivers": ["Agriculture (intensive)", "Urban demand", "Navigation demand"],
      "default_activities": ["Cropland cultivation", "Urban discharge", "Channel maintenance dredging", "Commercial fishing"],
      "default_pressures": [
        {"label": "Nutrient loading (point + diffuse)", "pressure_origin": "endogenic"},
        {"label": "Organic pollution", "pressure_origin": "endogenic"},
        {"label": "Channelisation", "pressure_origin": "endogenic"},
        {"label": "Bank reinforcement", "pressure_origin": "endogenic"}
      ],
      "default_states": ["Floodplain inundation regime", "Sediment transport balance", "Dissolved-oxygen profile"],
      "default_es": ["Fish nursery (smelt, shad)", "Flood regulation", "Nutrient processing"],
      "default_gb": ["Commercial freshwater fishery", "Inland navigation", "Recreational fishing"],
      "fish_guilds": ["freshwater_resident", "diadromous_migratory", "estuarine_dependent"],
      "iconic_species_aphia": [126415, 126413, 126736, 101172, 101174]
    },
    "delta": {
      "label": "Delta / distributary",
      "typical_position": "river_mouth",
      "default_drivers": ["Coastal urbanisation", "Agriculture (delta plain)", "Tourism"],
      "default_activities": ["Delta-plain agriculture", "Aquaculture", "Sediment management"],
      "default_pressures": [
        {"label": "Land subsidence", "pressure_origin": "exogenic"},
        {"label": "Sediment starvation", "pressure_origin": "exogenic"},
        {"label": "Salinity intrusion", "pressure_origin": "exogenic"},
        {"label": "Habitat fragmentation", "pressure_origin": "endogenic"}
      ],
      "default_states": ["Delta morphology", "Salinity wedge", "Distributary network"],
      "default_es": ["Sediment-derived land", "Habitat for migratory birds", "Spawning grounds (shad)"],
      "default_gb": ["Delta-plain agricultural production", "Bird-watching tourism", "Aquaculture yields"],
      "fish_guilds": ["diadromous_transit", "estuarine_dependent", "marine_estuarine_opportunist"],
      "iconic_species_aphia": [126415, 126413, 126281, 154238]
    },
    "estuary": {
      "label": "Estuary / strait",
      "typical_position": "freshwater-marine_transition",
      "default_drivers": ["Port activity", "Coastal urbanisation", "Industrial demand"],
      "default_activities": ["Port operations", "Capital + maintenance dredging", "Industrial discharge", "Aquaculture"],
      "default_pressures": [
        {"label": "Turbidity", "pressure_origin": "endogenic"},
        {"label": "Hypoxia", "pressure_origin": "endogenic"},
        {"label": "Contaminant loading", "pressure_origin": "exogenic"},
        {"label": "Hydrodynamic alteration", "pressure_origin": "endogenic"}
      ],
      "default_states": ["Salinity gradient", "Turbidity maximum zone", "Stratification regime"],
      "default_es": ["Fish nursery (juvenile cod, herring, flatfish)", "Diadromous migratory corridor", "Carbon burial"],
      "default_gb": ["Port revenue", "Commercial coastal fisheries", "Recreational fisheries"],
      "fish_guilds": ["estuarine_dependent", "marine_estuarine_dependent", "marine_estuarine_opportunist", "diadromous_transit"],
      "iconic_species_aphia": [126281, 126417, 126425, 127141, 126736]
    },
    "lagoon": {
      "label": "Coastal lagoon",
      "typical_position": "semi_enclosed_coastal",
      "default_drivers": ["Tourism", "Aquaculture demand", "Agriculture (catchment-fed)"],
      "default_activities": ["Lagoon aquaculture", "Recreational boating", "Catchment-derived discharge"],
      "default_pressures": [
        {"label": "Eutrophication", "pressure_origin": "exogenic"},
        {"label": "Hypoxia / anoxia", "pressure_origin": "endogenic"},
        {"label": "Algal blooms", "pressure_origin": "endogenic"},
        {"label": "Sediment infilling", "pressure_origin": "exogenic"},
        {"label": "Inlet alteration", "pressure_origin": "endogenic"}
      ],
      "default_states": ["Water residence time", "Phytoplankton biomass", "Bottom-water DO", "Macrophyte cover"],
      "default_es": ["Nursery for marine juveniles", "Nutrient retention / removal", "Bird habitat (Ramsar value)"],
      "default_gb": ["Lagoon fishery (smelt, perch, pikeperch)", "Tourism revenue", "Aquaculture production"],
      "fish_guilds": ["solely_estuarine", "estuarine_dependent", "marine_estuarine_opportunist"],
      "iconic_species_aphia": [126736, 126415, 126281]
    },
    "coastal_sea": {
      "label": "Coastal sea / shelf",
      "typical_position": "open_marine_shelf",
      "default_drivers": ["EU fisheries policy", "Maritime trade", "Climate change", "Offshore energy demand"],
      "default_activities": ["Commercial fishing", "Shipping", "Offshore wind", "Marine tourism"],
      "default_pressures": [
        {"label": "Fishing mortality", "pressure_origin": "endogenic"},
        {"label": "Nutrient inputs (cumulative)", "pressure_origin": "exogenic"},
        {"label": "Underwater noise", "pressure_origin": "endogenic"},
        {"label": "Bottom disturbance", "pressure_origin": "endogenic"},
        {"label": "Acidification", "pressure_origin": "exogenic"}
      ],
      "default_states": ["Stock biomass", "Plankton community", "Benthic habitat condition", "Stratification"],
      "default_es": ["Commercial fish provisioning", "Climate regulation", "Cultural identity"],
      "default_gb": ["Commercial fishery revenue", "Shipping revenue", "Coastal tourism"],
      "fish_guilds": ["marine_resident", "marine_estuarine_dependent", "marine_migratory"],
      "iconic_species_aphia": [126436, 126417, 126425, 127186]
    }
  },
  "phase2_archetypes": ["tributary", "floodplain", "wetland"]
}
```

---

## 5. Channel types (`multises/channels.json`)

Eight v1 channel types. JSON file eager-loaded at import. Each channel type instantiates one of Mike Elliott's four EG connectivity flows (materials, energy, organisms, finance) — see §5.0.

### 5.0 Mapping to Elliott's four-flow EG connectivity definition

Elliott's authoritative EG definition (in the EG monograph, in preparation) requires connectivity to maintain "the transfer and fluxes of **materials, energy, organisms, and finance**" — both ecological and societal. The eight v1 channels map onto three of the four flows; the fourth (energy) is acknowledged here as a v1 gap and a phase-2 priority.

| Elliott flow | v1 channel(s) | Coverage status |
|---|---|---|
| **Materials** | `water_discharge`, `nutrients`, `sediment`, `pollutants` | ✓ well covered |
| **Organisms** | `organisms_diadromous`, `organisms_marine_estuarine` | ✓ well covered |
| **Finance** | `economic_telecoupling` | ⚠ partial — captures commodity-market demand telecoupling but not direct investment, subsidies, port revenue, fisheries-quota markets |
| **Energy** | — none — | ✗ **missing in v1**; `trophic_energy` channel slot reserved in phase-2 (§11) |

Two further connectivity dimensions present in Elliott's "societal connectivity" sub-clause are also missing in v1:
- **Cultural connectivity** (heritage, identity, livelihoods crossing administrative boundaries) — phase-2 `cultural_connectivity` channel.
- **Institutional/governance social connectivity** — partial via `governance` channel but only at the regulatory-cascade level, not at the actor-network/co-management level.

The spec foregrounds these gaps because EG-aligned publications need to be transparent about which limbs of the EG framework v1 implements vs. defers.

### 5.1 v1 channel-type table

| Slug | Default direction | Default polarity | Default strength | Edge style | Elliott flow |
|---|---|---|---|---|---|
| `water_discharge` | downstream_only | + | strong | solid blue | materials |
| `nutrients` | downstream_only | + | strong | solid green | materials |
| `sediment` | downstream_only | + | medium | solid amber | materials |
| `pollutants` | downstream_only | + | medium | solid red | materials |
| `organisms_diadromous` | bidirectional_per_lifestage | + | medium | dashed cyan | organisms |
| `organisms_marine_estuarine` | upstream_recruitment | + | medium | dashed teal | organisms |
| `governance` | any | − | medium | dotted purple | societal (governance, partial) |
| `economic_telecoupling` | any | + | weak | dotted amber | finance |

### 5.2 Channel rendering

- `edge_color` + `edge_style` give each channel type a distinct visual identity.
- Multiple parallel channels between the same compartment pair are *expected* (e.g. `river_lower → estuary` will typically have water + nutrients + sediment + pollutants + diadromous + governance). Pyvis renders these as smoothly-curved parallel edges with `roundness` offsets.

### 5.3 Polarity composition for cross-compartment loops

A cross-compartment cycle has the form: `(DAPSI edges in A) → (channel A→B) → (DAPSI edges in B) → (channel B→A) → ...`. Every edge carries `polarity ∈ {+, -}`. Loop polarity = product of all edge polarities, exactly as SESPy's `loop_polarity()` already does. **No new polarity arithmetic needed** — the channel-edge `polarity` attribute is written onto the composite digraph and SESPy's existing classifier consumes it directly.

### 5.4 Phase-2 reserved channel attributes

`units` (e.g. `m^3/s`, `tN/yr`, `individuals/yr`), `timestep` (`daily`, `seasonal`, `annual`), `lifestage` (`glass_eel`, `silver_eel`, `smolt`, `spawning_adult`, ...). Listed per channel-type in `channels.json` as `phase2_units`, `phase2_timestep`, `phase2_lifestage` — descriptive only in v1.

### 5.4.1 Channel `delay` field (added 2026-05-09)

Every `Channel` carries a qualitative propagation `delay ∈ {"immediate", "short", "medium", "long", "very_long"}`, mirroring `sespy.Connection.delay` but with a wider span appropriate to inter-compartment timescales. The default per channel-type:

| Channel type | Default delay | Rationale |
|---|---|---|
| `water_discharge` | immediate | Hydrological flux propagates in hours. |
| `nutrients` | short | Days to weeks for dissolved transport; longer for particulate. |
| `sediment` | medium | Months for transport; years for floodplain residence. |
| `pollutants` | long | Persistent contaminants accumulate over years; legacy contaminants over decades. |
| `organisms_diadromous` | long | Annual life-cycle migrations (smolt→sea→adult→spawn). |
| `organisms_marine_estuarine` | medium | Seasonal recruitment cycles. |
| `governance` | long | Years from policy formulation to enforced implementation. |
| `economic_telecoupling` | medium | Months to years for demand-side feedback. |

Delay is qualitative in v1 — it informs the user / Comparative dashboard but does not (yet) drive numeric simulation. Phase-2 adds a `delay_units` field for numeric calibration (e.g., `delay="medium"` + `delay_units="6 months"` for a specific lagoon nutrient turnover). Cross-compartment loop classification (Section 6.4) currently ignores `delay`; phase-2 simulation does not.

### 5.5 Channel `governance_regime` and `cci_index` (added second review pass)

For `channel_type = "governance"`, the v1 `governance_regime` field carries which of WFD / EPSS / MSFD / MSPD / national / international jurisdictions the regulatory cascade originates in. This is the operationalisation of EG's three-management-regime intersection (Tagliapietra et al. 2020 §3). The Comparative dashboard (§7.4) breaks out `response_pressure_gap()` by regime so a user can ask "which orphan Pressures lie in WFD jurisdiction but have only MSFD-channel Responses targeting them?".

For transboundary `governance` channels (i.e. when `source` and `target` compartments are in different countries per metadata), the `cci_index` (0–10, Povilanskas & Razinkovas-Baziukas 2023 `10.3390/su15139922`) records cooperation-vs-confrontation status. Curonian seed populates `cci_index` on the LT/RU and LT/BY transboundary governance channels, allowing the cross-compartment view to colour-flag low-cooperation channels.

---

## 6. Library API

Mirrors SESPy's `network.py` discipline: pure functions or methods on dataclasses, no global state, no Shiny imports.

### 6.1 `multises/data_structure.py`

```python
# Constructors
MultiSES.empty(name: str = "Untitled") -> MultiSES

MultiSES.from_dict(raw: dict) -> tuple[MultiSES, LoadReport]
    # Hard errors (M001/M002/M201/M202/M203/M204) raise MultiSESIntegrityError.
    # Soft errors (W101/W102/W301) collected into LoadReport.warnings.
    # Schema migrations recorded into LoadReport.migrations_applied.

MultiSES.from_json(text: str) -> tuple[MultiSES, LoadReport]
MultiSES.from_file(path: Path | str) -> tuple[MultiSES, LoadReport]

# Persistence
MultiSES.to_dict() -> dict
MultiSES.to_json(*, indent: int = 2) -> str

multises.persistence.save(ms: MultiSES, path: Path) -> None
    # Atomic write: mkstemp in same directory as `path` (so os.replace is
    # rename-within-volume), write JSON, fsync the temp file (forcing OS write
    # buffer to disk before the rename — required because `path` may live on
    # OneDrive / network drives where post-rename reads can transiently return
    # the prior contents), os.replace, then re-read first 64 bytes of `path`
    # and assert they match the just-written prefix (post-replace sanity check
    # for OneDrive / network-drive corner cases). On any exception, the temp
    # file is unlinked in `finally` so the temp directory does not accumulate.

multises.persistence.load(path: Path) -> tuple[MultiSES, LoadReport]
    # Refuses with explicit error if metadata.schema_version > MULTISES_SCHEMA_VERSION.
    # Warns + runs migration shim if schema_version < MULTISES_SCHEMA_VERSION
    # (shim names are listed in LoadReport.migrations_applied).

# Lookups
MultiSES.compartment(id: str) -> Compartment
MultiSES.channels_from(compartment_id: str) -> list[Channel]
MultiSES.channels_to(compartment_id: str) -> list[Channel]
MultiSES.channels_between(a_id: str, b_id: str) -> list[Channel]

# Mutators (defined on the dataclass — see Section 3)
MultiSES.add_compartment(c: Compartment) -> None
MultiSES.add_channel(ch: Channel) -> None
MultiSES.remove_compartment(compartment_id: str) -> list[Channel]

# Validation
multises.validate(ms: MultiSES) -> list[ValidationIssue]
    # Returns hard + soft issues. Hard issues here would indicate the MultiSES
    # was constructed via raw list manipulation that bypassed the mutator
    # methods — useful for tests and for validating in-flight Topology edits.
```

### 6.2 `multises/archetypes.py`

```python
get_archetypes() -> dict[str, dict]
get_archetype(slug: str) -> dict
suggest_neighbours(archetype_slug: str) -> list[str]
seed_compartment(archetype_slug: str, *, label: str, id: str) -> Compartment
```

### 6.3 `multises/channels.py`

```python
get_channel_types() -> dict[str, dict]
get_channel_type(slug: str) -> dict
make_channel(*, source: str, target: str, channel_type: str,
             polarity: str | None = None, strength: str | None = None,
             confidence: int = 3, lifestage: str | None = None) -> Channel
seed_diadromous_channels(ms: MultiSES, species_aphia: int) -> list[Channel]
```

### 6.4 `multises/composite.py` — heart of cross-compartment analysis

```python
build_composite_digraph(ms: MultiSES, *,
                       include_dapsi: bool = True,
                       include_channels: bool = True,
                       channel_types: set[str] | None = None) -> nx.DiGraph

cross_compartment_loops(ms: MultiSES, *,
                       max_length: int = 12, max_loops: int = 50,
                       expansion: Literal["strict", "full"] = "strict",
                       ) -> tuple[list[CrossLoop], bool]
    # Returns (loops, truncated). `truncated=True` when more than `max_loops`
    # were available — UI shows "showing 50 of N+ loops, increase max_loops"
    # banner. Without this flag the cap is silent.

@dataclass
class CrossLoop:
    id: str                             # "X-001" style
    nodes: list[str]                    # composite-graph node ids in order
    compartments_visited: list[str]
    length: int
    polarity_type: str                  # "Reinforcing" | "Balancing"
    channel_types_used: list[str]
    polarity_string: str                # e.g. "+ + - + -"

inter_compartment_metrics(ms: MultiSES) -> dict[str, dict]
```

**Synthetic-bottleneck design.** Each compartment has one synthetic node `f"{id}::__compartment__"` plus all its DAPSI nodes. The synthetic node is connected internally to every DAPSI node (zero-weight ingress/egress, `kind="internal_link"`, `polarity="+"`). Channel edges connect synthetic→synthetic. This forces every cross-compartment traversal through one well-defined choke point per compartment, keeping cycle enumeration to the same complexity class as the within-compartment case. Within-compartment loops are still handled by SESPy's per-compartment `feedback_loops()` — the two analyses stay cleanly separate.

**Polarity arithmetic across the synthetic bottleneck.** A cross-compartment cycle traversing compartment B enters via an `internal_link` edge (polarity `+`) from B's synthetic node to some DAPSI node, walks DAPSI edges with their authored polarities, then exits via another `internal_link` edge (polarity `+`) back to the synthetic node. Both `internal_link` edges contribute `polarity="+"` to the polarity product, which is multiplicative-identity — so the within-B contribution to the cycle polarity is exactly the product of the DAPSI edges traversed inside B, unchanged by the bottleneck routing. This is correctness-preserving **only because** `internal_link` edges are pinned to `polarity="+"`. Implementation MUST enforce this; tests MUST pin it. See `test_composite.py::test_internal_link_polarity_is_neutral` and `test_composite.py::test_balancing_loop_through_governance_channel` (Section 9.4).

**False-cycle filtering.** `nx.simple_cycles` will enumerate cycles that traverse a single compartment's synthetic node twice (entering one DAPSI node, exiting via another, then re-entering through a different `internal_link` pair). These are spurious — they touch only one compartment so the `len({...compartment...}) >= 2` filter discards them. They do, however, inflate the enumeration space and accelerate `max_loops` truncation. The composite builder therefore offers an `expansion="strict"` mode (default) that only adds `internal_link` edges between the synthetic node and DAPSI nodes that are actually endpoints of authored cross-compartment channels, reducing the false-cycle space dramatically. An `expansion="full"` mode (used by tests + power users) connects synthetic to all DAPSI nodes.

### 6.5 `multises/comparative.py` — Priority A grid

```python
per_compartment_grid(ms: MultiSES, *,
                    metrics: tuple[str, ...] = sespy.network.CENTRALITY_METRICS) -> pd.DataFrame
    # Long DF: one row per (compartment_id, element_id, metric, value).

leverage_hotspots(ms: MultiSES, *, top_n_per_compartment: int = 5) -> pd.DataFrame
    # Top-N per compartment + a global rank column (z-score across all compartments).

compartment_summary(ms: MultiSES) -> pd.DataFrame
    # One row per compartment: archetype, element_count, connection_count,
    # weakly_connected_components, mean_leverage, top_leverage_label,
    # dominant_pressure_count.

response_pressure_gap(ms: MultiSES) -> pd.DataFrame
    # For each Pressure across all compartments, count Responses targeting it
    # (within compartment + via governance channels into the compartment).
    # Surfaces governance gaps — pressures with zero Responses anywhere.
    # The publishable Marine-SABRES policy view.
```

### 6.6 SESPy reuse (no wrapper, direct calls)

```python
from sespy import network as sn

cmp = ms.compartment("curonian_lagoon")
sn.feedback_loops(cmp.project.isa_data, max_length=6, max_loops=50)
sn.centrality_metrics(cmp.project.isa_data)
sn.leverage_scores(cmp.project.isa_data)
sn.intervention_impact(cmp.project.isa_data, ["P_eutrophication"])
sn.simplify_by_strength(cmp.project.isa_data, min_strength="medium")
```

---

## 7. Shiny shell — four primary new modules + small Project Setup form

Single Shiny-for-Python app at `MosaicSES/app.py`. Reuses `sespy.dashboard` shell, `sespy.i18n` (English-only translations dict for v1), `sespy.event_bus`. ~80% of codebase is library, ~20% is UI.

The four primary new modules are **Topology, Compartments, Comparative, Cross-view** — these are the substantive UI work. Two further surfaces (Project Setup, Recent Projects) are bookkeeping: Project Setup is a small two-column metadata form (name, river basin, regional sea, focal issue, scales) modelled on `sespy.modules.pims_project`; Recent Projects is a thin wrapper around `sespy.recent_projects` with the `.multises.json` extension swapped in.

### 7.1 Nav layout

| Nav id | Module | New / reused |
|---|---|---|
| `project` | Project Setup (MultiSES metadata) | small new form |
| `topology` | Topology editor | **NEW (primary)** |
| `compartments` | Compartment switcher + embedded SESPy modules | **NEW (primary)** |
| `comparative` | Priority A grid | **NEW (primary)** |
| `cross_view` | Priority B composite view | **NEW (primary)** |
| `recent` | Recent Projects | thin wrapper over `sespy.recent_projects` |

### 7.2 Module — Topology

Compartment + channel editor. 3-column layout:
- **Left**: compartments list (add/remove/rename, archetype dropdown, element count badge).
- **Centre**: pyvis canvas — compartments as large hexagonal nodes (coloured by archetype), channels as typed edges (colour + style from `channels.json`). Hierarchical layout aware of `typical_position`.
- **Right**: inspector panel — when compartment selected: archetype info + "Open in Compartments tab" button. When channel selected: channel-type info + polarity/strength/confidence editors.

One-click conveniences: "Seed diadromous channels" (calls `seed_diadromous_channels` for each AphiaID found in any compartment's `iconic_species_aphia`); "Suggest neighbours" (offers to create archetype-suggested neighbour compartments).

### 7.3 Module — Compartments

Compartment-switcher + embedded SESPy. The "drill into one compartment" page.

**Top bar:** compartment picker, archetype label, element/connection counts.

**Nested tabs (re-using SESPy modules unchanged):** Edit Data, CLD Visualization, Loop Analysis, Network Metrics, Leverage Points, Boolean & Laplacian, Dynamic Simulation, Behaviour Over Time, Intervention, Simplify Network. Each tab mounts the corresponding module's `*_ui` and `*_server` functions with `project_data = active_compartment_project` (a shared `reactive.value(Project)`). Example: `sespy.modules.loop_analysis_ui("compartments-loop-analysis")` and `loop_analysis_server(...)`; CLD Visualization uses `cld_viz_ui` and `cld_viz_server` (not the generic `<module>_ui` pattern).

**Compartment switch protocol (REQUIRED — silent corruption otherwise).** SESPy modules hold session-scoped derived state that only invalidates on `event_bus.isa_change` — most importantly `analysis_loops.py:141`'s `detected` reactive. When the picker rebinds `active_compartment_project`, derived state from the previous compartment survives unless explicitly invalidated. The switcher MUST therefore:

```python
@reactive.effect
@reactive.event(input.compartment_picker)
def _switch_active_compartment():
    new_id = input.compartment_picker()
    cmp = multises_data().compartment(new_id)
    # 1. Flush any pending text inputs in the embedded modules so a half-typed
    #    edit does not silently land on the new compartment:
    session.send_input_message(...)  # pseudocode — see Shiny session API
    # 2. Rebind the shared reactive:
    active_compartment_project.set(cmp.project)
    # 3. Force-invalidate every SESPy module's derived state:
    event_bus.emit_isa_change()
    active_compartment_id.set(new_id)
```

**Persistence backwrite — closure-captured compartment id, isolated read.** When the user edits inside an embedded SESPy module, the SESPy module sets its `project_data` reactive and emits `event_bus.isa_change`. MosaicSES listens, but **must** capture the active compartment id at the moment the listener fires (not at write time) and **must** wrap its read in `reactive.isolate()` to avoid an infinite reactivity loop:

```python
@reactive.effect
@reactive.event(event_bus.isa_change)
def _backwrite_to_multises():
    target_id = active_compartment_id.get()    # captured now
    with reactive.isolate():
        edited_project = active_compartment_project.get()
    ms = multises_data().with_compartment_replaced(target_id, edited_project)
    multises_data.set(ms)
```

The switch step (3) above triggers this listener too. That's harmless: the listener writes back the just-rebound new compartment's project to itself (no-op write), but it does so for the *new* compartment id captured at listener-fire time, not the previous one — closure capture by id, not by reference, is what prevents stale-write race.

**Open issue, decided here for clarity.** Compartment switch with unsaved (uncommitted-to-reactive) edits in `isa_data_entry`: v1 forces a flush via `session.send_input_message` (Shiny session API). v2 may upgrade to a confirmation modal. Tested in `test_compartment_switcher_rebind.py`.

### 7.4 Module — Comparative (Priority A)

Five cards:
1. **Compartment vital signs** — `compartment_summary()` table.
2. **Centrality heatmap** — rows = compartments, columns = top-K elements, cells = chosen metric value (slider). matplotlib `imshow` rendered to PNG.
3. **Global leverage table** — `leverage_hotspots()` global rank: top 20 elements by composite leverage z-score.
4. **Response–Pressure gap** — `response_pressure_gap()`. Two-column split: orphan Pressures left, well-covered Pressures right. **Publishable view.**
5. **Compartment-level meta-graph** — pyvis canvas: each compartment one node (size = element count, colour = archetype), each channel one edge.

### 7.5 Module — Cross-view (Priority B)

Three cards:
1. **Composite graph viewer** — full pyvis render of the composite digraph. Toggle filters: DAPSI? channels? which channel types? Highlight cross-compartment cycles only. **Refresh button-triggered**, not reactive (manage rendering cost).
2. **Cross-compartment loops table** — `cross_compartment_loops()` output. Click a loop → highlights it on the canvas, dims everything else.
3. **Inter-compartment leverage / bridge compartments** — `inter_compartment_metrics()` bar chart: compartments ranked by meta-graph betweenness. Identifies LOAC structural bottlenecks.

### 7.6 What v1 explicitly does NOT include

- Language switcher (English-only; `t()` calls remain in place for phase-2).
- Autosave at MultiSES level.
- PDF/HTML/Word export.
- Map view (Leaflet).
- Flux numerical simulation.

---

## 8. Curonian Lagoon seed dataset

Six compartments, ~15–20 elements each, ~25 channels.

### 8.1 Topology

```
nemunas_upper (river_upper, transboundary LT/BY)
   └─ water + nutrients + sediment + pollutants + diadromous(↕) + governance(↑)
nemunas_lower (river_lower, Kaunas → Rusnė bifurcation)
   └─ all of above + governance ↑↓
nemunas_delta (delta, Ramsar wetland)
   └─ water + nutrients + sediment + diadromous(↕)
curonian_lagoon (lagoon, ~1584 km², oligohaline, transboundary LT/RU)
   └─ residual outflow + diadromous(↕) + marine-estuarine ingress (↑)
klaipeda_strait (estuary, port + salinity gradient)
   └─ all material + organism + governance
baltic_se (coastal_sea, ICES SD 26)
```

### 8.2 Diadromous species seeded

| Common | AphiaID | Habitat | Compartments touched (v1) |
|---|---|---|---|
| Atlantic salmon | 127186 | anad | nemunas_upper ↔ baltic_se (via lower, delta, lagoon, strait) |
| Sea trout | 127187 | anad | nemunas_lower ↔ baltic_se |
| European eel | 126281 | cata | nemunas_lower ↔ baltic_se (glass-eel ↑, silver-eel ↓) |
| European smelt | 126736 | anad | curonian_lagoon ↔ nemunas_delta |
| Twaite shad | 126415 | anad | nemunas_lower ↔ baltic_se |
| River lamprey | 101172 | anad | nemunas_lower ↔ baltic_se |
| **Atlantic sturgeon** | **151802** | **anad** | **nemunas_upper ↔ baltic_se (extirpated from Nemunas Basin, last caught 1962; restocking from 2011)** |

The **Atlantic sturgeon** (*Acipenser oxyrinchus*) entry is the single most important addition the seed needs to make. The historical Nemunas extirpation–reintroduction story is documented for sturgeon, not salmon (Stakėnas & Pilinkovskij, 2019, `10.1111/jai.13871`). Atlantic salmon was depleted but persisted as a reproducing Nemunas population (Leliūna & Virbickas, 2006, `10.1080/13921657.2006.10512736`). v1 seed must reflect this: the salmon channel is "depleted, recovering"; the sturgeon channel is "extirpated, reintroduction underway".

### 8.3 Confidence convention

Seeded **elements** (every Element pre-populated by `archetypes.seed_compartment` or shipped in the Curonian dataset) use `confidence = 2`. Seeded **channels** in the Curonian dataset use channel-specific confidence reflecting how well-attested the linkage is in the literature (3–5 for water/nutrient flux backed by HELCOM monitoring data; 2–3 for diadromous channels where stocks are degraded; 2 for economic-telecoupling channels which are mostly hypothesised). User-authored content typically uses `≥ 3`. SESPy's `CONFIDENCE_OPACITY` renders confidence-2 edges as pale/translucent — the visual cue for "starter scaffolding awaiting review".

### 8.4 Demonstrative cross-compartment loops

**Loop 1 — Eutrophication–governance balancing loop (headline demo):**

```
nemunas_lower :: A_intensive_agriculture (+)→ P_nutrient_loading
        └── nutrients channel (+) ──→ curonian_lagoon
                                     :: P_eutrophication (+)→ S_hypoxia
                                                              (+)→ I_smelt_kill
                                                              (-)→ ES_smelt_nursery
                                                              (-)→ GB_lagoon_fishery_revenue
                                                              (+)→ R_helcom_baltic_bsap_lagoon_actions
        ←── governance channel (-) ──┘
nemunas_lower :: R_catchment_action_plan (-)→ A_intensive_agriculture     [closes loop]
```

Compartments: 2; classification: balancing; channel types used: nutrients + governance. **Pinned in `test_curonian_seed.py`** as the integration-test canary.

**Loop 2 — Diadromous-fish telecoupling reinforcing loop:**

```
baltic_se :: D_atlantic_salmon_market (+)→ A_recreational_angling
                                          (+)→ GB_angling_revenue
                                          (+)→ R_salmon_recovery_funding
        └── economic_telecoupling channel (+) ──→ nemunas_upper
                                                  :: A_riparian_restoration (-)→ P_habitat_loss
                                                                              (+)→ S_spawning_habitat
                                                                              (+)→ ES_spawning_grounds
        ←── organisms_diadromous channel (+) ──┘
baltic_se :: ES_atlantic_salmon_stock (+)→ D_atlantic_salmon_market   [closes loop]
```

### 8.5 Citations seeded into compartment `description` fields

Cross-cutting: Elliott et al. 2017, Whitfield 2020, Polette/Tischer/Elliott 2026. Per-compartment: HELCOM BSAP references, Curonian-specific literature (Razinkovas-Baziukas et al.), Marine-SABRES task references.

---

## 9. File layout, dependencies, testing

### 9.1 Repo structure

```
Marine-SABRES/
├── SESPy/                              (untouched)
└── MosaicSES/                          (NEW — sibling repo)
    ├── README.md
    ├── pyproject.toml
    ├── app.py
    ├── data/
    │   └── curonian_loac.json
    ├── multises/
    │   ├── __init__.py
    │   ├── data_structure.py
    │   ├── archetypes.py
    │   ├── archetypes.json
    │   ├── channels.py
    │   ├── channels.json
    │   ├── composite.py
    │   ├── comparative.py
    │   ├── persistence.py
    │   ├── validate.py
    │   └── curonian/
    │       ├── __init__.py
    │       └── curonian_loac.json
    ├── multises_app/
    │   ├── __init__.py
    │   ├── dashboard.py
    │   ├── modules/
    │   │   ├── project_setup.py
    │   │   ├── topology.py
    │   │   ├── compartments.py
    │   │   ├── comparative.py
    │   │   ├── cross_view.py
    │   │   └── recent_projects.py
    │   └── translations/
    │       └── core.json               # English-only for v1
    ├── www/
    │   └── mosaic-skin.css
    └── tests/
        ├── test_data_structure.py
        ├── test_archetypes.py
        ├── test_channels.py
        ├── test_composite.py
        ├── test_comparative.py
        ├── test_persistence.py
        ├── test_curonian_seed.py
        ├── test_topology_e2e.py
        ├── test_compartments_e2e.py
        ├── test_comparative_e2e.py
        └── test_cross_view_e2e.py
```

### 9.2 `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mosaic-ses"
version = "0.1.0"
description = "Spatially distributed, connected SES along the Land-Ocean Aquatic Continuum"
requires-python = ">=3.11"
dependencies = [
    "sespy @ file:///${PROJECT_ROOT}/../SESPy",
    "shiny>=0.10",
    "networkx>=3.2",
    "pandas>=2.1",
    "matplotlib>=3.8",
    "pyvis>=0.3",
    "openpyxl>=3.1",
]

[tool.setuptools.packages.find]
include = ["multises*", "multises_app*"]

[tool.setuptools.package-data]
multises = ["*.json", "curonian/*.json", "translations/*.json"]
```

### 9.3 SESPy import allow-list

```python
from sespy.data_structure import Project, IsaData, Element, Connection, ProjectMetadata
from sespy.constants import (DAPSIWRM_ELEMENTS, ELEMENT_COLORS, ELEMENT_SHAPES,
                             DAPSIWRM_LEVEL, ELEMENT_ID_PREFIX)
from sespy.network import (centrality_metrics, leverage_scores, feedback_loops,
                           classify_loops, top_n_by_metric, intervention_impact,
                           simplify_by_strength, to_digraph, loop_polarity,
                           remove_nodes, CENTRALITY_METRICS)
from sespy.utils import next_id
from sespy.regional_seas import get_regional_seas
from sespy.event_bus import create_event_bus
from sespy.dashboard import dashboard_page, dashboard_server, NavItem, StepperItem
from sespy.i18n import Translator, load_translations, t, set_default
from sespy.modules import (cld_visualization, analysis_loops, analysis_metrics,
                          analysis_leverage, analysis_boolean, analysis_simulation,
                          analysis_bot, analysis_intervention, analysis_simplify,
                          isa_data_entry)
```

A test `test_no_sespy_private_imports` scans `multises/` + `multises_app/` and asserts no imports outside this list.

### 9.4 Testing

**~100 unit tests target** (revised upward from the initial 80 after review found gaps in tolerant-load and composite-correctness coverage):

| File | Tests | Covers |
|---|---|---|
| `test_data_structure.py` | ~18 | dataclass round-trip; JSON envelope shape; `__post_init__` rejects bad polarity / strength / confidence / archetype / channel_type; mutator methods enforce invariants; **edge shapes** (empty MultiSES, single-compartment MultiSES, isolated compartment, channel pointing at non-existent compartment yields error not warning) |
| `test_archetypes.py` | ~8 | every archetype has all required fields; `seed_compartment` produces valid Project; iconic_species_aphia entries resolve in ICES catalog |
| `test_channels.py` | ~10 | every channel-type has all fields; `seed_diadromous_channels` correct for salmon (anad), eel (cata), sturgeon (anad — extirpated edge case) |
| `test_composite.py` | ~18 | composite digraph node namespacing (`compA::D1` ≠ `compB::D1`, no edge cross-contamination); synthetic-bottleneck correctness on hand-crafted 2-compartment graph (cycle returned exactly once); **`test_internal_link_polarity_is_neutral`** — the polarity-composition pin from Section 6.4; **`test_balancing_loop_through_governance_channel`** — 3-compartment cycle with two `+` DAPSI runs + one `governance` `−` channel must classify Balancing; cross-loop ranking; max_length boundary; max_loops truncation flag (returns `truncated=True`); `expansion="strict"` vs `"full"` produce same legitimate cross-loops |
| `test_comparative.py` | ~10 | per-compartment grid shape; leverage hotspots; response-pressure gap with 2 known orphans |
| `test_persistence.py` | ~12 | atomic save/load round-trip; **corrupt-JSON load (truncated brace) raises typed error**; **unknown channel_type warns + preserves row**; **unknown archetype warns + preserves**; **`schema_version=999` future-version load refuses with explicit error**; **`schema_version` missing loads as v1 with warning + migration shim**; **`schema_version=0` flat-shape file migrates and notes migration in LoadReport**; **atomic-save crash mid-write leaves prior file intact** (mock `os.replace` failure); **fsync + post-replace sanity check fires on corrupted re-read**; **temp file unlinked on exception** |
| `test_curonian_seed.py` | ~8 | seed dataset loads; **`multises.validate(seed) == []` strictly**; **compartment count = 6 and archetype list matches §8.1 exactly**; eutrophication–governance balancing loop appears (canary 1); **diadromous-fish reinforcing loop appears (canary 2)**; **`response_pressure_gap()` returns ≥ 2 orphan Pressures**; pressure-driver causation per compartment is consistent with archetype defaults; assertions on cross-loop fields use `polarity_type` + `channel_types_used` set (not exact node sequence — labels may evolve) |
| `test_import_allowlist.py` | ~3 | (NEW separate file) AST-scan of `multises/` and `multises_app/` confirms no `from sespy._private`, only the allow-listed names from §9.3; counts allow-listed import sites (regression detection if allow-list grows silently) |

**5 e2e tests** (headless Chromium, mirror SESPy's pattern): `test_topology_e2e.py`, `test_compartments_e2e.py`, `test_comparative_e2e.py`, `test_cross_view_e2e.py`, plus **`test_compartment_switcher_rebind.py`** — switches compartment 3 times mid-session and asserts CLD + metrics + loops all redraw cleanly (this is the architectural-pivot test, not a one-off spike).

**Curonian seed = double-canary integration test.** Two pinned cross-compartment loops:
- Canary 1: eutrophication–governance balancing loop (Section 8.4 Loop 1) — confirms nutrients channel + governance channel composition produces a balancing classification.
- Canary 2: diadromous-fish telecoupling reinforcing loop (Section 8.4 Loop 2) — confirms organisms_diadromous + economic_telecoupling channels compose to reinforcing.

Two canaries are far more robust than one: a regression that flips polarity arithmetic shows in both; a regression that affects only one channel type shows in only one. Acceptance criteria in Section 10.5 require both.

---

## 10. Build sequence

Four sequential chunks. Each chunk gets its own implementation plan from `writing-plans`.

### 10.1 Chunk 1 — Library skeleton + persistence

`data_structure.py`, `archetypes.py` + `archetypes.json`, `channels.py` + `channels.json`, `persistence.py`, `validate.py`. Unit tests for each. End state: author a `MultiSES`, save to JSON, load back, validate. No Shiny.

### 10.2 Chunk 2 — Composite + comparative + Curonian seed

`composite.py`, `comparative.py`, `curonian/curonian_loac.json` and `seed_curonian()`. Unit tests + the `test_curonian_seed.py` integration test (canary loop). End state: full library functionality testable from a Jupyter notebook; library is shippable for Python users. **Natural release point** if Shiny work runs into trouble.

### 10.3 Chunk 3 — Shiny shell, Topology + Compartments

`app.py`, `multises_app/dashboard.py`, `topology.py`, `compartments.py`. The compartment-switcher embedding pattern is the **architectural risk** — testing this end-to-end is what de-risks the rest. End state: open the app, see Curonian topology, switch between compartments, see SESPy modules working on each.

**Pre-chunk-3 spike (REQUIRED, not optional).** ~50 lines that swap `project_data` to a different `Project` mid-session AND verify the four invariants below. If the spike fails on any, the design falls back to alternative A from Q6 (full module re-implementation):

1. After `active_compartment_project.set(new_project)`, `cld_visualization` redraws for the new project. (Plain reactivity — should pass.)
2. After only step 1, `analysis_loops`'s loop table still shows the *previous* compartment's loops with new compartment's labels (intentional failure case — pins the silent-corruption risk that motivates step 3 below).
3. Adding `event_bus.emit_isa_change()` immediately after step 1 makes `analysis_loops` reset its `detected` reactive and recompute against the new project. (The fix.)
4. Wrapping `active_compartment_project.get()` in `reactive.isolate()` inside the backwrite listener prevents an infinite reactivity loop when the listener writes back to the envelope. (Prevents pathological loop.)

These four checks are the four-line specification of the spike. They become permanent tests in `test_compartment_switcher_rebind.py` (Section 9.4) — the spike is not throwaway code.

### 10.4 Chunk 4 — Comparative + Cross-view + polish

`comparative.py`, `cross_view.py`, `project_setup.py`, `recent_projects.py`, CSS skinning, e2e tests. End state: shippable v1; demo-ready.

### 10.5 Acceptance criteria for v1

- Library: 80+ unit tests pass; `multises.validate(seed_curonian()) == []`.
- App: opens cleanly; all 6 nav items work; Curonian seed loads as default project.
- Cross-view: composite digraph renders the 6 compartments; cross-loop table includes the eutrophication–governance balancing loop.
- Comparative: all 5 cards render; `response_pressure_gap()` shows ≥ 2 orphan Pressures.
- Save → reload → identical-via-deep-equal: round-trip works.
- E2E: 4 e2e tests pass against `shiny run app.py`.

---

## 11. Phase 2 backlog (out of v1 scope)

In rough priority order:

1. **Diadromous-thread analysis (F).** For each species in `iconic_species_aphia`, trace its life-stage path through compartments and overlay Pressures encountered at each stage. Requires phase-2 `lifestage` field on `organisms_diadromous` channels.
2. **Scenario testing / interventions (D).** "Restore upstream wetland" → user marks intervention on one compartment; tool propagates expected changes through the channel network; returns updated metrics on every other compartment.
3. **Channel-typed flux propagation (C).** Treat channels as typed transport edges with units and timesteps. Bow-tie risk-assessment style propagation. Requires phase-2 `units` / `timestep` fields.
4. **Spatial overlay / map view (E).** GeoJSON polygons on each compartment; Leaflet map with channel arrows; click compartment → opens its SES.
5. **Multi-language support.** Activate the `t()` calls left in v1; extend `sespy.i18n` keys.
6. **Additional pilot datasets.** Po (branched topology stress-test); Gironde (sturgeon recovery); templates pattern mirroring SESPy's `templates/*.json`.
7. **Export reports.** HTML / PDF / Word — same three-format pattern SESPy uses.
8. **MultiSES-level autosave.**
9. **Atmospheric N deposition channel.** Aerial deposition of reactive nitrogen onto lagoon / coastal-sea compartments is a major Baltic input pathway and is *not* representable as a "downstream" channel in v1's typology. Flagged by scientific reviewer; deferred because it requires a new channel-type (or a "source: atmosphere" pseudo-compartment) whose semantics deserve their own design pass.
10. **Coastal upwelling channel.** Upwelling inverts the conventional sea→lagoon Chl-a gradient and is documented at the Curonian pilot site (Dabulevičienė et al., 2020, `10.3390/rs12213661`). Inversion of the typical downstream-only material flow direction means it cannot be modelled as `water_discharge` reversed; it is its own phenomenon.
11. **Submarine groundwater discharge / surface-water exchange.** Relevant for delta and lagoon archetypes; deferred because v1 channels are surface-water only.
12. **Riparian / wetland buffer as first-class archetype.** v1 demotes wetland to a phase-2 archetype slot (already accepted by the schema). Phase 2 promotes it with default DAPSI vocabulary, integrates it with `nutrients` channel routing (wetland buffer attenuation as a reduction-of-strength on incident channels).
13. **Climate as cross-cutting Driver above all compartments.** Currently each compartment carries its own climate Drivers; phase 2 considers a singleton "climate" pseudo-compartment whose Drivers fan out to every other compartment via a new `climate_forcing` channel type.
14. **Larval / propagule drift channel.** Distinct from `organisms_marine_estuarine`; relevant for invertebrates and macrophytes. Cited via Cowen & Sponaugle 2009 (`10.1146/annurev.marine.010908.163757`) and Pineda, Hare & Sponaugle 2007 (`10.5670/oceanog.2007.27`).
15. **Invasive-species spread channel.** Highly relevant in the Baltic; defers because invasion dynamics are bidirectional and timescale-specific (need phase-2 `timestep`).

### EG-aligned phase-2 items (added 2026-05-09 second review pass)

16. **`trophic_energy` channel type** — closes the **energy gap** in Elliott's four-flow EG definition (§5.0). Carries cross-compartment trophic energy transfer (food-web subsidies, carbon export), with default polarity `+`, default direction `bidirectional`, and a phase-2 `unit ∈ {gC/yr, kJ/yr, biomass-equiv}` field. Justification: Polis, Anderson & Holt (1997, `10.1146/annurev.ecolsys.28.1.289`) spatial-subsidies framework; Helfield & Naiman (2001, `10.1890/0012-9658(2001)082[2403:eosdno]2.0.co;2`) salmon-derived nitrogen as worked example.
17. **`trophic_subsidy` channel type** — alternative or complement to `trophic_energy`, for biologically-vectored nutrient transfer (e.g. salmon carcasses delivering marine-N to riparian forests; cormorant-mediated nutrient regeneration in lagoons). Default polarity `+`, default direction `bidirectional`, weak default strength.
18. **`cultural_connectivity` channel type** — closes the **culture/social gap** in Elliott's "societal connectivity" sub-clause. Captures heritage, identity, livelihood-network connectivity crossing administrative boundaries. Default polarity `+`, default direction `any`, weak default strength. Curonian-relevant example: Curonian Spit UNESCO heritage site spans LT/RU; cross-border fisheries heritage of Klaipėda fishing communities. References: Robbe et al. 2024 (`10.1007/s00267-024-01955-9`); Karstens, Kiesel & Petersen 2022 (`10.3389/fmars.2022.929274`).
19. **10-tenets evaluation framework** (Elliott et al. 2017, `10.1016/j.marpolbul.2017.03.049`; 2025 revisited). Add `tenet_scores: dict[str, int] | None` field to Element (Response type) and to Channel (governance type). Each tenet (Ecologically sustainable / Technologically feasible / Economically viable / Socially desirable / Legally permissible / Administratively achievable / Politically expedient / Ethically defensible / Culturally inclusive / Effectively communicable) scored 1–5. New analysis function `tenet_gap_analysis()` produces a per-Response tenet-readiness panel — the EG monograph's analytical claim that policies should be tenet-scored.
20. **Emerald Justice integration** — parallel concept developed by Maciej Nyka and the user's research group (working draft `emerald justice.docx`). Three concrete tasks: (a) add `equity_dimension: list[str] | None` to `Element` (Impact type), capturing dimensions like `ocean_grabbing`, `livelihood_displacement`, `gender_inequity`, `indigenous_rights`, `decision_exclusion`; (b) add an EJ perspective to `response_pressure_gap()` outputs (which orphan Pressures most affect equity-flagged Impacts?); (c) develop a Curonian case-study EJ seed drawing on small-scale fishery and transboundary community literature (LT/RU/BY context).
21. **Endogenic/exogenic Pressure tagging at Element level** — v1 carries `pressure_origin` only on archetype defaults (`archetypes.json`). Phase-2 promotes the field to `sespy.Element` itself (requires upstream SESPy change), so per-instance Pressures can be tagged. Enables `endogenic_orphan()` analysis: which endogenic (locally-managed) Pressures have no within-compartment Response — distinct from exogenic Pressures whose orphan-ness is force-majeure rather than governance failure.
22. **Per-archetype EG monograph deliverables.** Each EG monograph chapter has a deliverable that MosaicSES can produce given v1 + phase-2 fields:
    - Ch.1 (Geographical TW definition): `tw_geographic_summary()` — outputs the WFD/typology-faithful TW description per pilot system.
    - Ch.2 (Legal): `governance_regime_breakdown()` — already in v1 via `response_pressure_gap()` slicing.
    - Ch.3 (Ecology): `ecotone_indicator_panel()` — Tagliapietra-style ecotone characterisation per `estuary` / `lagoon` compartment.
    - Ch.4 (ES): `cices_inventory()` — already in v1 via populated `cices_code` fields.
    - Ch.5 (Transboundary): `cci_summary()` — already in v1 via `cci_index` fields.
    - Ch.6 (System approach): the comparative + cross-view dashboards themselves are the deliverable.
23. **CICES-aligned ES service-class crosswalk** — phase-2 widens the v1 optional `cices_code` field to a full service-class lookup (provisioning / regulating / cultural splits with sub-classes), supporting MAES (Mapping and Assessment of Ecosystems and their Services) reporting.
24. **Coastal Circles of Sustainability (CCS) integration** — Povilanskas et al. 2024 (`10.3390/su16062544`) Lake Liepāja worked example. Phase-2 `circles_indicators: dict[str, dict[str, str]]` field on Compartment — four-pillar (Environment+Ecology, Social+Culture, Economy, Governance+Policy) sustainability assessment as a Compartment-level dashboard.
25. **Lake Liepāja (Latvia) as v2 pilot.** Sister TTW (transboundary transitional water) to Curonian, already worked-example for CCS. Add as second template with `cci_index` and `circles_indicators` populated.

---

## 12. References

### Foundational / parent-framework references (added or repositioned 2026-05-09 second pass)

- **Tagliapietra, D., Povilanskas, R., Razinkovas-Baziukas, A., & Taminskas, J. (2020).** Emerald Growth: A New Framework Concept for Managing Ecological Quality and Ecosystem Services of Transitional Waters. *Water*, 12(3), 894. https://doi.org/10.3390/w12030894 — **The parent framework. MosaicSES is its software operationalisation.**
- Elliott, M. (2011). Marine science and management means tackling exogenic unmanaged pressures and endogenic managed pressures. *Marine Pollution Bulletin*, 62(4), 651–655. https://doi.org/10.1016/j.marpolbul.2011.01.040 — Endogenic vs exogenic pressure distinction; basis for `pressure_origin` field.
- Lonsdale, J., et al. (2018). A user's guide to coping with estuarine management bureaucracy: An Estuarine Planning Support System (EPSS) tool. *Marine Pollution Bulletin*, 133, 935–948. — EPSS regime in the three-regime intersection.
- Povilanskas, R., & Razinkovas-Baziukas, A. (2023). Transboundary Transitional Waters: Arenas for Cross-Border Cooperation or Confrontation? *Sustainability*, 15(13), 9922. https://doi.org/10.3390/su15139922 — Cooperation/Confrontation Integrity Index basis.
- Povilanskas, R., Jurkienė, A., & Dailidienė, I. (2024). Circles of Coastal Sustainability and Emerald Growth Perspectives for Transitional Waters under Human Stress. *Sustainability*, 16(6), 2544. https://doi.org/10.3390/su16062544 — Lake Liepāja CCS worked example; phase-2 second-pilot candidate.

### DAPSI(W)R(M) framework lineage

- Elliott, M., Burdon, D., & Atkins, J. P. (2017). "And DPSIR begat DAPSI(W)R(M)!" — A unifying framework for marine environmental management. *Marine Pollution Bulletin*, 118(1–2), 27–40. https://doi.org/10.1016/j.marpolbul.2017.03.049
- Elliott, M., & O'Higgins, T. (2020). From DPSIR the DAPSI(W)R(M) Emerges… a Butterfly. In *Ecosystem-Based Management, Ecosystem Services and Aquatic Biodiversity* (pp. 61–86). Springer. https://doi.org/10.1007/978-3-030-45843-0_4
- Polette, M., Tischer, V., & Elliott, M. (2026). The 'triple whammy' of threats to coasts and the 'environment-tourism paradox' — the DAPSI(W)R(M) unifying framework for coastal management. *Ocean & Coastal Management*, 273, 108018. https://doi.org/10.1016/j.ocecoaman.2025.108018
- Lovecraft, A. L., & Meek, C. L. (2019). Arctic Coastal Systems: Evaluating the DAPSI(W)R(M) Framework. In *Coasts and Estuaries* (pp. 671–686). Elsevier. https://doi.org/10.1016/b978-0-12-814003-1.00039-3

### Connectivity literature (added 2026-05-09 second pass — connectivity reviewer)

- Vannote, R. L., Minshall, G. W., Cummins, K. W., et al. (1980). The river continuum concept. *Canadian Journal of Fisheries and Aquatic Sciences*, 37(1), 130–137. https://doi.org/10.1139/f80-017 — Longitudinal connectivity foundation; justifies `water_discharge` as master variable.
- Junk, W. J., Bayley, P. B., & Sparks, R. E. (1989). The flood pulse concept in river-floodplain systems. *Canadian Special Publication of Fisheries and Aquatic Sciences*, 106, 110–127. — Lateral connectivity foundation; phase-2 wetland/floodplain promotion.
- Polis, G. A., Anderson, W. B., & Holt, R. D. (1997). Toward an integration of landscape and food web ecology. *Annual Review of Ecology and Systematics*, 28, 289–316. https://doi.org/10.1146/annurev.ecolsys.28.1.289 — Spatial subsidies; basis for phase-2 `trophic_subsidy` channel.
- Helfield, J. M., & Naiman, R. J. (2001). Effects of salmon-derived nitrogen on riparian forest growth. *Ecology*, 82(9), 2403–2409. https://doi.org/10.1890/0012-9658(2001)082[2403:eosdno]2.0.co;2 — Worked example of bidirectional diadromous-mediated nutrient connectivity.
- Cowen, R. K., & Sponaugle, S. (2009). Larval dispersal and marine population connectivity. *Annual Review of Marine Science*, 1, 443–466. https://doi.org/10.1146/annurev.marine.010908.163757 — Marine larval-connectivity canonical reference.
- Pineda, J., Hare, J. A., & Sponaugle, S. (2007). Larval transport and dispersal in the coastal ocean and consequences for population connectivity. *Oceanography*, 20(3), 22–39. https://doi.org/10.5670/oceanog.2007.27
- Waldman, J. R., & Quinn, T. P. (2022). North American diadromous fishes: drivers of decline and potential for recovery. *Science Advances*, 8(4), eabl5486. https://doi.org/10.1126/sciadv.abl5486 — Diadromous-decline review.
- Nakamura, T., Katano, O., & Abe, S. (2006). Comparison of fish communities between above- and below-dam sections. *Journal of Fish Biology*, 68(3), 767–782. https://doi.org/10.1111/j.0022-1112.2006.00964.x — Dam barrier empirical anchor for `connectivity_barriers` Pressure.
- Karstens, S., Kiesel, J., & Petersen, L. (2022). Human-induced hydrological connectivity. *Frontiers in Marine Science*, 9, 929274. https://doi.org/10.3389/fmars.2022.929274 — Baltic-system anchor for lateral hydrological connectivity.
- Liu, J., Hull, V., Batistella, M., et al. (2013). Framing sustainability in a telecoupled world. *Ecology and Society*, 18(2), 26. https://doi.org/10.5751/es-05873-180226 — Foundational telecoupling paper; basis for `economic_telecoupling` channel.
- Hull, V., & Liu, J. (2018). Telecoupling: a new frontier for global sustainability. *Ecology and Society*, 23(4), 41. https://doi.org/10.5751/es-10494-230441 — Update introducing "spillover" and multi-level governance vocabulary; informs phase-2 `cultural_connectivity`.
- **Sheaves, M. (2009).** Consequences of ecological connectivity: the coastal ecosystem mosaic. *Marine Ecology Progress Series*, 391, 107–115. https://doi.org/10.3354/meps08121 — **Conceptual ancestor of the name MosaicSES.** Reframes connectivity beyond migration to the multi-flow coastal-mosaic.
- **Pringle, C. M. (2001).** Hydrologic connectivity and the management of biological reserves: a global perspective. *Ecological Applications*, 11(4), 981–998. https://doi.org/10.1890/1051-0761(2001)011[0981:hcatmo]2.0.co;2 — Defines hydrologic connectivity as "matter, energy, organisms" — close cousin of Elliott's EG four-flow.
- **Pilosof, S., Porter, M. A., Pascual, M., & Kéfi, S. (2017).** The multilayer nature of ecological networks. *Nature Ecology & Evolution*, 1, 0101. https://doi.org/10.1038/s41559-017-0101 — Mathematical foundation for MosaicSES's multilayer architecture.
- Tylianakis, J. M., & Morris, R. J. (2017). Ecological networks across environmental gradients. *Annual Review of Ecology, Evolution, and Systematics*, 48, 25–48. https://doi.org/10.1146/annurev-ecolsys-110316-022821
- Calabrese, J. M., & Fagan, W. F. (2004). A comparison-shopper's guide to connectivity metrics. *Frontiers in Ecology and the Environment*, 2(10), 529–536. https://doi.org/10.1890/1540-9295(2004)002[0529:acgtcm]2.0.co;2 — Structural / potential / actual-functional connectivity taxonomy; positions v1 as potential-connectivity.
- Fausch, K. D., Torgersen, C. E., Baxter, C. V., & Li, H. W. (2002). Landscapes to riverscapes: bridging the gap between research and conservation of stream fishes. *BioScience*, 52(6), 483–498. https://doi.org/10.1641/0006-3568(2002)052[0483:ltrbtg]2.0.co;2
- Bracken, L. J., & Croke, J. (2007). The concept of hydrological connectivity and its contribution to understanding runoff-dominated geomorphic systems. *Hydrological Processes*, 21(13), 1749–1763. https://doi.org/10.1002/hyp.6313
- Thorp, J. H., Thoms, M. C., & Delong, M. D. (2006). The riverine ecosystem synthesis: biocomplexity in river networks across space and time. *River Research and Applications*, 22(2), 123–147. https://doi.org/10.1002/rra.901
- **Pérez-Ruzafa, A., Pérez-Ruzafa, I. M., & De Pascalis, F. (2019).** Connectivity between coastal lagoons and sea: asymmetrical effects on assemblages' and population's structure. *Estuarine, Coastal and Shelf Science*, 216, 171–186. https://doi.org/10.1016/j.ecss.2018.02.031 — **Canonical inter-lagoon comparative reference (Mar Menor / Curonian / Venice).**
- Macreadie, P. I., et al. (2023). BlueCAM: an Australian blue carbon method. *Restoration Ecology*, 31(7), e13739. https://doi.org/10.1111/rec.13739 — Phase-2 `blue_carbon` channel basis.
- Lin, M., Wang, Y., & Zhu, J. (2025). Extreme heatwave affects saltwater intrusion and river plume in the Changjiang Estuary. *JGR Oceans*, 130(4). https://doi.org/10.1029/2024jc022287 — Climate as connectivity disruptor.

### Curonian-system connectivity references (Klaipėda University CORPI / Marine Research Institute group, added third pass)

- Žilius, M., Barisevičiūtė, R., Bonaglia, S., et al. (2024). Riverine inputs and phytoplankton community composition control nitrate cycling in a coastal lagoon. *Biogeosciences*, 21(7), 1693–1709. https://doi.org/10.5194/egusphere-2023-3054
- Žilius, M., Marzocchi, U., Bonaglia, S., et al. (2021). Zebra Mussel Holobionts Fix and Recycle Nitrogen in Lagoon Sediments. *Frontiers in Microbiology*, 11, 610269. https://doi.org/10.3389/fmicb.2020.610269
- Žilius, M., Vybernaite‐Lubiene, I., Vaičiūtė, D., et al. (2020). Spatiotemporal patterns of N₂ fixation in coastal waters derived from rate measurements and remote sensing. *Biogeosciences*, 17(23), 6047–6062. https://doi.org/10.5194/bg-2020-419
- Žilius, M., Bartoli, M., Nizzoli, D., et al. (2021). Denitrification, Nitrogen Uptake, and Organic Matter Quality Undergo Different Seasonality in Sandy and Muddy Sediments of a Turbid Estuary. *Frontiers in Microbiology*, 11, 612700. https://doi.org/10.3389/fmicb.2020.612700
- Žilius, M., Daunys, D., Petkuvienė, J., & Bartoli, M. (2012). Sediment-water O₂, N and P fluxes in the eutrophic Curonian Lagoon under different temperature regimes. *Journal of Limnology*, 71(2), e33. https://doi.org/10.4081/jlimnol.2012.e33
- Vybernaite-Lubiene, I., Žilius, M., Bartoli, M., et al. (2017). Recent trends (2012–2016) of N, Si, and P export from the Nemunas River watershed: Loads, unbalanced stoichiometry, and threats for downstream aquatic ecosystems. *Water*, 9(11), 880.
- **Lesutienė, J., Bukaveckas, P. A., Gasiūnaitė, Z. R., Pilkaitytė, R., & Razinkovas-Baziukas, A. (2014).** Tracing the isotopic signal of a cyanobacteria bloom through the food web of a Baltic Sea coastal lagoon. *Estuarine, Coastal and Shelf Science*, 138, 47–56. https://doi.org/10.1016/j.ecss.2013.12.017 — *user is co-author.*
- **Lesutienė, J., Bukaveckas, P. A., Gasiūnaitė, Z. R., et al. (2017).** Microcystin in food webs of the Baltic and Chesapeake Bay coastal regions. *ECSS*, 191, 50–59. https://doi.org/10.1016/j.ecss.2017.04.016 — User-group co-authored.
- **Gasiūnaitė, Z. R., Razinkovas-Baziukas, A., & Grinienė, E. (2012).** Pelagic patterns along the Nemunas–Curonian Lagoon transition. *Baltica*, 25(1), 77–86. https://doi.org/10.5200/baltica.2012.25.07 — *user is co-author;* direct seed-data anchor for the `nemunas_delta → curonian_lagoon` boundary.
- **Pilkaitytė, R., & Razinkovas, A. (2006).** Factors controlling phytoplankton blooms in a temperate estuary: Nutrient limitation and physical forcing. *Hydrobiologia*, 555(1), 41–48. — *user is co-author.*
- **Ferrarin, C., Razinkovas, A., Gulbinskas, S., Umgiesser, G., & Bliūdžiutė, L. (2008).** Hydraulic regime-based zonation scheme of the Curonian Lagoon. *Hydrobiologia*, 611(1), 133–146. https://doi.org/10.1007/s10750-008-9453-6 — *user is co-author.*
- Daunys, D., Zemlys, P., Olenin, S., Zaiko, A., & Ferrarin, C. (2006). Impact of the zebra mussel *Dreissena polymorpha* invasion on the budget of suspended material in a shallow lagoon ecosystem. *Helgoland Marine Research*, 60(2), 113–120. https://doi.org/10.1007/s10152-006-0028-5
- Bresciani, M., Adamo, M., De Carolis, G., et al. (2012). Monitoring blooms and surface accumulation of cyanobacteria in the Curonian Lagoon by combining MERIS and ASAR data. *Remote Sensing of Environment*, 146, 124–135.
- Krevš, A., Koreivienė, J., Paškauskas, R., & Šulijienė, R. (2007). Phytoplankton production and community respiration in different zones of the Curonian Lagoon during the mid-summer vegetation period. *Transitional Waters Bulletin*, 1(1), 17–26.
- Čerkasova, N., Umgiesser, G., & Ertürk, A. (2021). Modelling framework for flow, sediments and nutrient loads in a large transboundary river watershed: A climate change impact assessment of the Nemunas River basin. *Journal of Hydrology*, 598, 126422. https://doi.org/10.1016/j.jhydrol.2021.126422

### Estuary / lagoon / fish-guild references

- Whitfield, A. K. (2020). Fish species in estuaries — from partial association to complete dependency. *Journal of Fish Biology*, 97(4), 1262–1264. https://doi.org/10.1111/jfb.14476
- Whitfield, A. K., Potter, I. C., & Neira, F. J. (2023). Modes of ingress by larvae and juveniles of marine fishes into estuaries. *Fish and Fisheries*, 24(3), 488–503. https://doi.org/10.1111/faf.12745
- Tulp, I., Chen, C., & Vrooman, J. (2022). The nursery function of the Ems estuary for fish. Wageningen Marine Research. https://doi.org/10.18174/583972
- Inácio, M., Schernewski, G., & Nazemtseva, Y. (2018). Ecosystem services provision today and in the past: a comparative study in two Baltic lagoons. *Ecological Research*, 33(6), 1255–1274. https://doi.org/10.1007/s11284-018-1643-8 — Curonian + Szczecin Lagoons ES comparison; CICES-relevant.
- Robbe, E., Rogge, L., & Lesutienė, J. (2024). Assessment of Ecosystem Services Provided by Macrophytes in Southern Baltic and Southern Mediterranean Coastal Lagoons. *Environmental Management*, 74(2), 206–229. https://doi.org/10.1007/s00267-024-01955-9 — Macrophyte ES, Curonian co-author.

### Further DAPSI(W)R(M) applications (deprioritized to footnote)

The following were cited in earlier drafts but provide minimal additional warrant beyond the core Elliott 2017 + Polette 2026 + Whitfield 2020 + Tagliapietra 2020 set; they remain in scope as worked examples but should not be over-cited:

- Hassan, R., Takyi, R., & Almahrad, B. (2021). Addressing the Drying up of Euphrates River Using DAPSI(W)R(M). https://doi.org/10.13140/rg.2.2.13533.95205
- Caviedes Sánchez, V., Elliott, M., & Arenas-Granados, P. (2019). An integrated marine analysis based on the DAPSI(W)R(M) framework for the Southern Belize coastal region. https://doi.org/10.13140/rg.2.2.36019.45602
- Izar, G. M., Choueri, R. B., & Martinez, S. T. (2022). The application of the DAPSI(W)R(M) framework to the plastic pellets chain. *Marine Pollution Bulletin*, 180, 113807. https://doi.org/10.1016/j.marpolbul.2022.113807
- Murase, A., Yamasaki, Y., & Mukai, M. (2025). Blackfin Seabass Utilize Small Estuarine Lagoons as Nurseries. *Marine Ecology*, 46(4). https://doi.org/10.1111/maec.70031
- Selfati, M., et al. (2023). Updated checklist of the fish fauna of the Marchica Lagoon. *Egyptian Journal of Aquatic Biology and Fisheries*, 27(2), 251–274. https://doi.org/10.21608/ejabf.2023.291755
- Bruno, D. O., Delpiani, S. M., & Eduardo, M. (2018). Diel variation of ichthyoplankton recruitment in a wind-dominated temperate coastal lagoon (Argentina). *Estuarine, Coastal and Shelf Science*, 205, 91–99. https://doi.org/10.1016/j.ecss.2018.03.015

Curonian / Nemunas / Baltic references (added during 2026-05-09 scientific review):

- Aleksandrov, S. V., Krek, A., & Bubnova, E. S. (2018). Eutrophication and effects of algal bloom in the south-western part of the Curonian Lagoon. *Baltica*, 31(1), 1–12. https://doi.org/10.5200/baltica.2018.31.01
- Cheung, H. L. S., Žilius, M., & Politi, T. (2025). Nitrate-driven eutrophication supports high nitrous oxide production and emission in coastal lagoons. *Journal of Geophysical Research: Biogeosciences*, 130(4). https://doi.org/10.1029/2024jg008510
- Dabulevičienė, T., Vaičiūtė, D., & Kozlov, I. (2020). Chlorophyll-a variability during upwelling events in the south-eastern Baltic Sea and in the Curonian Lagoon. *Remote Sensing*, 12(21), 3661. https://doi.org/10.3390/rs12213661
- Leliūna, E., & Virbickas, J. (2006). Phylogeographic characteristics of the Atlantic salmon (*Salmo salar* L.) population of the Nemunas River. *Acta Zoologica Lituanica*, 16(3), 229–234. https://doi.org/10.1080/13921657.2006.10512736
- Sosnina, I., Šeirienė, V., & Grigienė, A. (2024). Holocene environmental changes inferred from palaeobotanical data of Curonian Lagoon sediments. *Baltica*, 77–86. https://doi.org/10.5200/baltica.2024.1.8
- Stakėnas, S., & Pilinkovskij, A. (2019). Migration patterns and survival of stocked Atlantic sturgeon (*Acipenser oxyrinchus* Mitchill, 1815) in Nemunas Basin, Baltic Sea. *Journal of Applied Ichthyology*, 35(1), 128–137. https://doi.org/10.1111/jai.13871
- Stakėnienė, R., Jokšas, K., & Kriaučiūnienė, J. (2023). Nutrient loadings and exchange between the Curonian Lagoon and the Baltic Sea: Changes over the past two decades (2001–2020). *Water*, 15(23), 4096. https://doi.org/10.3390/w15234096

ICES references:
- WGDIAD — Working Group on Diadromous Species (all diadromous: shad, smelt, lamprey, sturgeon).
- WKESDLS — Workshop on Estuarine and Diadromous Species (estuarine phase).
- WGEEL — Joint EIFAAC/ICES/GFCM Working Group on Eels.
- WGBAST — Baltic Salmon and Trout Assessment Working Group.
