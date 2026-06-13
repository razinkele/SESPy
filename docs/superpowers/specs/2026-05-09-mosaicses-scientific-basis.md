# MosaicSES — Scientific Basis & References

**Companion document to:** `2026-05-08-mosaicses-design.md` (the design spec).
**Purpose:** Records the scientific reasoning that drove the v1 design choices — framework lineage, compartment-archetype rationale, channel-type rationale, pilot-system justification, framework-fidelity caveats, and a consolidated reference list. The design spec is the *what*; this document is the *why*.

### Revision log

- **2026-05-09 (initial)** — First version companion to the design spec.
- **2026-05-09 (second pass, EG-lens)** — Major refactor after a multi-agent review put Emerald Growth (Tagliapietra et al. 2020) at the centre rather than treating it as one of many DAPSI(W)R(M) applications. Changes:
  - **§2 reframed as Emerald Growth lineage**, not "DPSIR → DAPSI(W)R(M) → nested" — EG is now the parent framework; DAPSI(W)R(M) is a graph operationalisation tool for EG.
  - **§4.7 (`governance` channel)** rationale expanded with the three-management-regime intersection (WFD / EPSS-Lonsdale / MSFD-MSPD) and the Cooperation/Confrontation Integrity Index.
  - **§5 (Curonian pilot)** annotated with where each citation supports each EG dimension.
  - **§9 reorganised**: new §9.0 EG framework references promoted to top; new §9.6 Connectivity literature; new §9.7 Lagoon ES literature.
  - **New §11 EG framework alignment matrix** documenting which EG concepts v1 implements vs defers, with phase-2 backlog cross-references.
  - **References added (15)**: Tagliapietra et al. 2020 (was inexplicably absent from the original §9 — a critical citation gap caught by review); Elliott 2011 (endogenic/exogenic); Lonsdale et al. 2018 (EPSS); Povilanskas & Razinkovas-Baziukas 2023 (CCI); Povilanskas et al. 2024 (CCS Lake Liepāja); Vannote 1980 (RCC); Junk 1989 (flood-pulse); Polis 1997 (spatial subsidies); Helfield-Naiman 2001 (salmon-N); Cowen-Sponaugle 2009 (larval); Pineda 2007 (larval transport); Waldman-Quinn 2022 (diadromous decline); Nakamura 2006 (dam barrier); Karstens 2022 (Baltic hydrological connectivity); Liu et al. 2013 (telecoupling foundational); Inácio et al. 2018 (Curonian/Szczecin ES); Bartoli et al. 2018 (Curonian cyanobacteria); Sruoga et al. 2007 (Curonian eel genetics); Robbe et al. 2024 (Baltic macrophyte ES).
- **2026-06-08 (citation precision pass)** — Corrected author attributions (Murase et al. third author, Selfati single-author record), added missing DOIs to key Curonian references, clarified `cci_index` as a 0–10 normalization of the source index scale, and softened the upwelling wording to match the cited abstract.

---

## 1. The scientific question MosaicSES is built to answer

Coastal social-ecological systems (SES) are routinely managed as discrete units — a river basin under the Water Framework Directive, an estuary under national port regulation, a lagoon under Ramsar / Habitats Directive, a coastal sea under the Marine Strategy Framework Directive — even though the natural system is a *continuum*. Nutrients loaded onto cropland in a headwater catchment travel through every downstream compartment and arrive in the coastal sea hundreds of kilometres later. Atlantic salmon spawning in the upper Nemunas were extirpated by mid-twentieth-century transformations to the lower river they had to pass through twice. A coastal Marine Protected Area's bycatch rules can drive land-use restrictions in farms that have no view of the sea.

The mismatch between connected ecology and disconnected management is well-documented in the *land-ocean aquatic continuum* (LOAC) and *source-to-sea* literatures. What has been missing is a **practical, qualitative-graph tool** that lets a researcher author the SES of each compartment separately, then express the linkages between them in a way that can be analysed for cross-compartment leverage points and feedback loops.

MosaicSES is that tool. Every modelling choice — the compartment archetypes, the channel typology, the polarity convention, the seed-data confidence values — is traceable to a specific piece of scientific literature or a specific ICES data product. This document records those traces.

---

## 2. Conceptual lineage of the framework

### 2.0 Emerald Growth as the parent framework

The single most important framework anchor for MosaicSES is the **Emerald Growth (EG)** concept introduced by Tagliapietra, Povilanskas, Razinkovas-Baziukas & Taminskas (2020) [`10.3390/w12030894`]. EG positions transitional waters (TW: estuaries, lagoons, deltas, rias, fjords) as a third-colour space between Green Growth (terrestrial sustainability framework) and Blue Growth (marine/maritime sustainability framework). The thesis: TW are neither riverine nor marine but occupy a distinct ecological, legal, and managerial regime, and the existing Green/Blue frameworks fail to capture the connectivity-driven dynamics that govern them.

EG operationalises connectivity as the *defining* feature of TW management. Mike Elliott's authoritative EG definition (in the in-preparation EG monograph; the user is co-author) reads: *"the ability for transitional waters to have a healthy ecological structure and functioning **because of their connectivity** with the catchment and adjacent marine areas in order to create ecosystem services from which society can obtain goods and benefits without having an adverse effect on that ecological structure and functioning; the natural (ecological) and societal (economic, culture, governance and management) connectivity is required for maintaining the **transfer and fluxes of materials, energy, organisms and finance**."*

This definition has four operational consequences for MosaicSES:

1. **Four connectivity flows must be representable.** Materials, energy, organisms, finance — both ecological and societal. v1 covers materials (4 channels), organisms (2 channels), finance (`economic_telecoupling`, partial). v1 acknowledges energy and socio-cultural connectivity as gaps left for phase-2 (`trophic_energy`, `cultural_connectivity` channel slots reserved).
2. **The system is *not* the catchment, *not* the coastal sea, *not* their union — it is the TW with the catchment and coastal sea as *bordering contexts*.** This is encoded in the spec via `Compartment.is_focal_tw` (defaulting True for `delta`/`estuary`/`lagoon`).
3. **Three management regimes meet at TW** — WFD (river-basin), EPSS (estuarine, Lonsdale et al. 2018), MSFD-MSPD (coastal-marine). Encoded as `governance_regime` field on `Channel`.
4. **Transboundary character is structural, not incidental.** Many TW span international borders; for the 108 transboundary TW worldwide (Povilanskas & Razinkovas-Baziukas 2023, [`10.3390/su15139922`]), cooperation-vs-confrontation patterns determine management feasibility. Encoded as `cci_index` (0-10 normalized operationalization of the source-scale index) on transboundary `governance` channels.

The Emerald Growth concept is the **direct parent of MosaicSES** — not the Elliott (2017) DAPSI(W)R(M) paper alone. The DAPSI(W)R(M) framework provides the *intra-compartment* graph-theoretic vocabulary (Drivers, Activities, Pressures, States, Impacts, Welfare, Responses); EG provides the *inter-compartment* connectivity vocabulary and the TW-centric analytical focus. MosaicSES composes both.

A parallel emerging concept developed by Maciej Nyka and the user's research group is **Emerald Justice** — adding equity dimensions (ocean grabbing, fisheries livelihoods, gender, indigenous rights, exclusion from decision-making) to EG. v1 acknowledges Emerald Justice as related future work; concrete phase-2 tasks are listed in spec §11.

### 2.1 DPSIR → DAPSI(W)R(M) → nested-DAPSI(W)R(M)

The Driver–Pressure–State–Impact–Response (DPSIR) framework has been the European environmental-management workhorse for three decades. Its limitations for coupled social-ecological systems are well-rehearsed: ambiguity about what counts as a Driver vs. an Activity, no explicit place for human Welfare alongside ecological State, and Responses framed as outputs rather than as Measures that loop back into the system.

**Elliott, Burdon & Atkins (2017)** [`10.1016/j.marpolbul.2017.03.049`] proposed the DAPSI(W)R(M) extension — Drivers (basic human needs) → Activities → Pressures → State change → Impacts on human Welfare → Responses (as Measures) — to address each of these limitations. The paper is the conceptual foundation of the entire MarineSABRES SES Toolbox and, by extension, of SESPy and MosaicSES. Crucially, the same paper introduces the idea that complex managed seas need *linked* and *nested* DAPSI(W)R(M) frameworks, with the explicit text:

> "the connectivity between marine ecosystems and ecosystems in the catchment and further at sea, requires an interlinked, nested-DAPSI(W)R(M) framework to reflect the continuum between adjacent ecosystems"

This sentence is the kernel of MosaicSES. The nested framework is conceptually present in 2017 but had no operational realisation: no software toolbox, no agreed graph representation, no published worked example until very recently. **MosaicSES is one such operationalisation.**

**Elliott & O'Higgins (2020)** [`10.1007/978-3-030-45843-0_4`] extend DAPSI(W)R(M) into the "Butterfly" model, splitting State into ecosystem-structure-and-functioning vs. ecosystem-services-supply, and introducing demand-side considerations. MosaicSES does not adopt the Butterfly's full restructure — SESPy's existing DAPSI(W)R(M) element types are inherited unchanged — but the Butterfly's emphasis on supply/demand telecoupling motivates the `economic_telecoupling` channel type (§5).

**Polette, Tischer & Elliott (2026)** [`10.1016/j.ocecoaman.2025.108018`] apply DAPSI(W)R(M) to coastal management with an explicit focus on tourism–environment interactions. This is the most recent published application and confirms the framework's continued evolution as the canonical European coastal-SES tool. Its "triple whammy" framing (climate + tourism + governance) reinforces the case for cross-compartment Drivers.

**Lovecraft & Meek (2019)** [`10.1016/b978-0-12-814003-1.00039-3`] apply DAPSI(W)R(M) to Arctic coastal systems, providing one of the few worked applications of the *nested* framework. This validates the approach for high-latitude systems and indirectly underwrites MosaicSES's choice of "Arctic NE Atlantic" as a future demonstration area.

### 2.2 The Land-Ocean Aquatic Continuum (LOAC)

Parallel to the DAPSI(W)R(M) lineage, the biogeochemistry community has developed the **LOAC** framing: the recognition that materials (carbon, nutrients, sediment, pollutants) are transformed during transit from terrestrial source through inland waters, estuaries, and coastal seas, and that quantifying these fluxes requires treating the whole continuum as a coupled system.

**Felgate (EGU 2022)** showed that 21 % of riverine dissolved organic carbon (DOC) export in Great Britain is "invisible" — non-coloured DOC that escapes optical detection — and that the prevalence of this pool varies systematically with anthropogenic catchment influence and water residence time. This is one of many recent results showing that LOAC fluxes cannot be reduced to the most-easily-measured component. The MosaicSES `nutrients` and `pollutants` channel types implicitly cover such flux pathways at qualitative resolution; phase-2's `units` reservation is what would let them be calibrated quantitatively.

The LOAC framing also justifies why MosaicSES treats **water_discharge** as a first-class channel: discharge is the master variable that drives every other downstream-only flux. A compartment graph that omits discharge would have the right elements but miss the architectural backbone.

### 2.3 Source-to-sea management

The "source-to-sea" community of practice (UNDP, SIWI, GEF) has been articulating since 2014 a parallel *governance-side* case for connected coastal management. Source-to-sea explicitly recognises the asymmetry that ecosystem services flow from upstream while management authority is overwhelmingly nested inside downstream administrative units. This asymmetry is the policy argument for MosaicSES's `governance` channel — Responses in compartment A targeting Pressures in compartment B is the empirical pattern of how MPAs actually drive land-use change, even though the Elliott et al. (2017) framework defines Responses as acting within a single managed system. §7 below explains why we treat this as an operational extension rather than a literal framework reading.

---

## 3. Compartment-archetype scientific rationale

The choice of six v1 archetypes — `river_upper`, `river_lower`, `delta`, `estuary`, `lagoon`, `coastal_sea` — is grounded in the LOAC's standard discretisation. Each archetype carries default DAPSI(W)R(M) elements drawn from peer-reviewed literature on its dominant pressures, characteristic states, and characteristic ecosystem services.

### 3.1 Estuaries and the fish-guild dependency continuum

The most influential single paper for the `estuary` and `lagoon` archetypes is **Whitfield (2020)** [`10.1111/jfb.14476`], which argues that fish "estuarine dependency" is best treated as a *continuum* rather than a binary. Whitfield's guild categories — solely-estuarine, estuarine-dependent, marine-estuarine-dependent, marine-estuarine-opportunist, marine straggler — are encoded directly into MosaicSES's `default fish_guilds` field per archetype. This lets phase-2 work map ICES survey data to expected guild composition without re-categorising.

**Whitfield, Potter & Neira (2023)** [`10.1111/faf.12745`] follow up by reviewing the *modes* of marine-fish ingress into estuaries — passive flood-tide entry vs. selective tidal stream transport vs. active swimming — across microtidal, mesotidal, and macrotidal systems. The Curonian Lagoon (microtidal, semi-enclosed) falls in the "passive flood-tide entry / active swimming" category, which is exactly the regime under which the `organisms_marine_estuarine` channel type is most relevant.

**Tulp, Chen & Vrooman (2022)** [`10.18174/583972`] is a Wageningen Marine Research report on the nursery function of the Ems estuary that provides a worked example of how Pressures (silt, suspended sediments) cascade through States (turbidity, oxygen) into Impacts on juvenile fish recruitment. The DAPSI causal chain from this report is the template used for MosaicSES's `estuary` archetype default Pressures and States.

### 3.2 Coastal lagoons as semi-closed SES

The `lagoon` archetype's defaults are derived from a tighter literature focused on semi-enclosed temperate and Mediterranean lagoons. **Aleksandrov, Krek & Bubnova (2018)** [`10.5200/baltica.2018.31.01`] document the eutrophication / algal-bloom signature of the Curonian Lagoon's southwestern (Russian-controlled) part, providing the empirical basis for the dominant Pressures `eutrophication`, `cyanobacterial_blooms`, and `hypoxia` in the archetype defaults.

**Cheung, Žilius & Politi (2025)** [`10.1029/2024jg008510`] document nitrate-driven N₂O production in coastal lagoons including the Curonian, supporting the framing of lagoons as nutrient-processing compartments — a *State* characteristic that motivates the `nutrient_retention` ecosystem service in the archetype defaults. This is also the empirical basis for showing lagoons as net positive contributors to the coastal sea's nutrient budget when their retention capacity is exceeded — relevant for cross-compartment loops.

**Murase, Yamasaki & Ikehara (2025)** [`10.1111/maec.70031`] document blackfin seabass juveniles using small (<1 km²) estuarine lagoons as nurseries in temperate Japan, showing the lagoon-as-nursery function is not restricted to large systems — relevant for phase-2 expansion to smaller European lagoons.

### 3.3 Rivers, deltas, and the longitudinal-connectivity literature

**Park, Riedel & Ju (2020)** [`10.3390/jmse8070496`] document how an estuary weir on the Lower Nakdong River fragments fish assemblages between freshwater and estuarine habitats, with the weir disturbing diadromous migration and recruitment for regional fish fauna. This is a worked example of how a single Pressure (`connectivity_barriers`) propagates causal effects across compartments — a pattern reproduced repeatedly in the Pan-European context (Rhine, Danube, Vistula, Nemunas).

**Bruno, Delpiani & Eduardo (2018)** [`10.1016/j.ecss.2018.03.015`] document diel ichthyoplankton recruitment in a wind-dominated temperate coastal lagoon, providing the empirical basis for the `organisms_marine_estuarine` channel type's default direction (`upstream_recruitment`) and seasonal timestep (phase-2 reservation).

**Avigliano, Ibáñez & Fabré (2021)** [`10.1002/aqc.3486`] use otolith Sr/Ca microchemistry to trace habitat use of *Mugil curema* across river, lagoon, estuary and sea — providing one of the cleanest empirical pictures of compartment-crossing habitat use, and the strongest case for representing fish movements as edges crossing compartment boundaries rather than internal compartment dynamics.

**Selfati (2023)** [`10.21608/ejabf.2023.291755`] documents fish-fauna response to hydrological intervention in the Marchica Lagoon (Mediterranean) — relevant for understanding how engineering interventions propagate through guild composition.

**Whitfield (2020)**, again, supplies the *philosophical* anchor for treating partial vs. complete estuarine dependency as a continuum (rather than a binary) — directly mapped into how MosaicSES treats compartment-archetype boundaries as graded rather than crisp.

---

## 4. Channel-type scientific rationale

The choice of eight v1 channel types is the most consequential modelling decision in MosaicSES. Each type is defended below with the literature that motivated it.

### 4.1 `water_discharge` — the master variable

Hydrological discharge drives every downstream-only material flux and sets the residence time of every receiving compartment. Without a discharge channel, nutrient/sediment/pollutant fluxes have no physical mechanism. Discharge is also the variable that climate change is most aggressively perturbing in European catchments (timing of snowmelt, frequency of summer low-flow). Default polarity `+`, default direction downstream-only, default strength strong.

### 4.2 `nutrients` — the eutrophication backbone

Nitrogen and phosphorus fluxes from agricultural and urban catchments are the single best-documented LOAC pathway. **Stakėnienė, Jokšas & Kriaučiūnienė (2023)** [`10.3390/w15234096`] document the Curonian Lagoon's nutrient exchange with the Baltic over two decades (2001–2020), providing empirical strength estimates for the Curonian seed dataset's `nutrients` channels and a calibration target for phase-2's `units` work.

The Baltic-wide context is the HELCOM Baltic Sea Action Plan, whose nutrient-input-ceilings form the policy backbone for the `governance` channel polarities. Without `nutrients`, no eutrophication–governance cross-compartment loops exist — and these are the publishable Marine-SABRES headline.

### 4.3 `sediment` — the silent driver of delta morphology

Sediment is treated separately from `nutrients` because its dynamics are different: it accumulates rather than dissolves, it has long residence times in floodplains and reservoirs, and dam reservoirs can starve downstream deltas of sediment for decades. The `sediment` channel's default strength is medium (rather than strong like discharge / nutrients) because much of the European catchment sediment supply is intercepted by dams.

The `sediment_starvation` Pressure in the `delta` archetype defaults references this empirically — Po Delta land subsidence, Rhine outflow morphology, and (for Curonian) the post-1970s Nemunas dam-and-reservoir construction.

### 4.4 `pollutants` — persistent contaminants and plastics

Polarity `+` because more upstream load = more downstream concentration. Strength medium reflecting the unevenness of evidence — point sources are easy to attribute, diffuse pollution and microplastics much harder. Listed separately from nutrients because pollutants have qualitatively different remediation pathways (clean-up vs. nutrient management) and qualitatively different governance instruments (REACH, Stockholm Convention vs. Nitrates Directive).

### 4.5 `organisms_diadromous` — the bidirectional life-cycle channel

This is the channel type that most distinguishes MosaicSES from a one-way LOAC flux model. Diadromous fish — anadromous (freshwater-spawning, marine-feeding: salmon, sea trout, smelt, twaite shad, allis shad, sturgeons, lampreys) and catadromous (marine-spawning, freshwater-feeding: European eel) — physically link compartments through their life cycles, with different life stages traversing the continuum in different directions.

The empirical basis is the ICES diadromous-species working-group catalogue (`mcp__ices-fish-data__migratory_species_catalog`), which lists 13 species relevant to the European LOAC context. Six are seeded into the Curonian Lagoon dataset (salmon 127186, sea trout 127187, eel 126281, smelt 126736, twaite shad 126415, river lamprey 101172) and a seventh (Atlantic sturgeon 151802) was added in the 2026-05-09 review. ICES working groups WGDIAD (Working Group on Diadromous Species), WKESDLS (Workshop on Estuarine and Diadromous Species), WGEEL (Joint EIFAAC/ICES/GFCM Working Group on Eels), and WGBAST (Baltic Salmon and Trout Assessment Working Group) are the authoritative scientific bodies.

The phase-2 `lifestage` field on `organisms_diadromous` channels lets the model represent that an eel's "glass-eel ingress" channel has different polarity, timing, and pressure-vulnerability than the same species' "silver-eel emigration" channel — a refinement that diadromous-fish biologists routinely insist on but is rarely operationalised in SES models.

### 4.6 `organisms_marine_estuarine` — recruitment of the next generation

Distinct from `organisms_diadromous` in that the species involved spend their *adult* phase at sea and only their *juvenile* phase in estuaries / lagoons. Examples: Atlantic herring (126417), European sprat (126425), European flounder (127141), Atlantic cod (126436). These are the species whose population dynamics are most affected by estuarine nursery quality — Tulp et al. (2022) is the definitive worked example.

The default direction is `upstream_recruitment` (sea → estuary / lagoon), polarity `+` (more healthy adult stock = more larvae available for recruitment). Adult emigration on the same channel-type runs in reverse.

### 4.7 `governance` — the upstream-flowing channel

The most novel channel type, and the one with the weakest direct framework support. Governance encompasses regulatory cascades (HELCOM BSAP → national water-management plans → catchment land-use rules), MPA designations, fishing quotas, EU directive transposition, Ramsar / UNESCO obligations.

The default polarity `-` (Responses dampen Pressures) follows from Elliott et al. (2017)'s framing of Responses-as-Measures. The default direction `any` reflects that governance signals can flow downstream (national framework → local implementation) or upstream (coastal MPA bycatch rules → upstream catchment nitrogen restrictions), with the upstream case being the most policy-relevant for cross-compartment SES analysis.

§7 below records the operational-extension caveat for this channel: Elliott et al. (2017) define Responses as acting within a managed system, not across systems. Cross-compartment governance modelling is defensible but extends the framework.

### 4.8 `economic_telecoupling` — the demand-side coupling

Built on the *telecoupling* literature (Liu et al. 2013 and successors, primarily in *Ecology and Society*) and the Elliott & O'Higgins (2020) "Butterfly" model's supply/demand framing. Examples: coastal-fisheries demand drives upstream catchment activity; downstream tourism revenue funds upstream restoration; international commodity prices drive land-use intensification in headwater catchments.

Default direction `any`, default polarity `+`, default strength weak — reflecting that telecoupling links are real but typically harder to quantify than physical flux links, and the seed dataset's confidence levels should reflect that.

---

## 5. The Curonian Lagoon pilot — system characterisation

The choice of the Curonian Lagoon system as v1 pilot rests on five facts:

### 5.1 Six-archetype fit

The Nemunas → Delta → Curonian Lagoon → Klaipėda Strait → SE Baltic system maps onto MosaicSES's six v1 archetypes with the only nontrivial mapping being **Klaipėda Strait as the `estuary` archetype**. This is technically defensible: the strait is the salinity-gradient zone where Nemunas-via-lagoon water meets Baltic water, and it is the salinity-stratification + tidal-pumping + nursery-function zone for the system. Whitfield (2020)'s estuarine dependency continuum applies here, with marine-estuarine-dependent and marine-estuarine-opportunist guilds (cod, herring, sprat, flounder, smelt) using the strait as nursery.

The system has no classical estuary in the geographical sense — the Nemunas does not have a single mouth where freshwater meets seawater along a salinity gradient — but the strait performs every functional role of an estuary archetype in the LOAC discretisation.

### 5.2 Hydrology and salinity

**Stakėnienė, Jokšas & Kriaučiūnienė (2023)** [`10.3390/w15234096`] characterise the lagoon as "southern and central parts… freshwater (<0.5 psu), while the northern part is oligohaline with irregular salinity (from 0 to 8 psu) fluctuations." This is the empirical basis for the `lagoon` archetype's default State `salinity_oligohaline` and for treating the lagoon as functionally separate from the strait. Lagoon area is ~1584 km² (confirmed by Sosnina et al. 2024 [`10.5200/baltica.2024.1.8`] and Cheung et al. 2025); ~98 % of inflow comes from the Nemunas; ~90 % of inflow leaves via the Klaipėda Strait into the SE Baltic.

### 5.3 Eutrophication regime

The Curonian Lagoon is classified as hypereutrophic. **Aleksandrov, Krek & Bubnova (2018)** [`10.5200/baltica.2018.31.01`] document the southwestern part's algal-bloom signature. **Cheung, Žilius & Politi (2025)** [`10.1029/2024jg008510`] document nitrate-driven N₂O production. **Stakėnienė et al. (2023)** [`10.3390/w15234096`] document two decades of nutrient-load and lagoon-Baltic exchange data. These three papers form the scientific backbone of the **eutrophication–governance balancing loop** (Section 8.4 Loop 1 in the design spec) — the headline demo artefact for the v1 release.

### 5.4 Diadromous fish — the salmon-vs-sturgeon distinction

The 2026-05-09 scientific review caught a framing error in the original spec: the strongest documented Nemunas extirpation/reintroduction story is **Atlantic sturgeon** *Acipenser oxyrinchus* (AphiaID 151802), not Atlantic salmon. Last sturgeon caught in the Nemunas Basin in 1962; restocking efforts began in 2011 and continue. **Stakėnas & Pilinkovskij (2019)** [`10.1111/jai.13871`] document the migration patterns and survival of the stocked sturgeons. **Leliūna & Virbickas (2006)** [`10.1080/13921657.2006.10512736`] describe the Atlantic salmon population as depleted but persisting — a phylogeographically distinct Nemunas lineage. The v1 seed dataset reflects this corrected framing: salmon channel is "depleted, recovering"; sturgeon channel is "extirpated, reintroduction underway".

The full v1 diadromous seed contains seven species (six original + sturgeon added in review). Houting (*Coregonus oxyrinchus*, AphiaID 154238) is included in the `delta` archetype's default `iconic_species_aphia` even though its taxonomic status in the SE Baltic is contested — this is flagged as a caveat in the seed dataset documentation; phase-2 work may revisit its inclusion.

### 5.5 Coastal upwelling — a phase-2 channel candidate

**Dabulevičienė, Vaičiūtė & Kozlov (2020)** [`10.3390/rs12213661`] document chlorophyll-a variability during upwelling events at the Curonian Lagoon mouth and southeastern Baltic. Upwelling episodes can shift the local sea↔lagoon productivity contrast (including reduced Chl-a at the lagoon mouth relative to typical non-upwelling periods), i.e., temporarily weakening or reversing the usual gradient pattern. This is one of the most distinctive marine-physical features of the pilot system.

The v1 channel typology cannot represent upwelling cleanly: it is a directional process (coastal sea → strait → lagoon) but the direction is opposite to the conventional `water_discharge` direction, and it operates on a timescale (event-driven, days) far shorter than the v1 "annual" implicit timestep. Phase-2 introduces an `upwelling` channel type or a `physical_exchange` superchannel to address this.

### 5.6 Transboundary realism

The Curonian system straddles three jurisdictions: Lithuania, Belarus (upper Nemunas Basin), Russian Federation Kaliningrad Oblast (southern lagoon). The `governance` channel polarity becomes interesting precisely because cross-border governance signals are *weaker* (lower confidence, lower strength) than within-Lithuania ones — a realistic feature the seed dataset explicitly captures via reduced confidence on transboundary governance channels.

---

## 6. Scientific dimensions deferred to phase 2

The 2026-05-09 review identified five LOAC dimensions that v1 does not represent and that a marine ecologist would expect:

1. **Atmospheric N deposition.** Aerial reactive nitrogen deposition onto lagoon and coastal-sea compartments is a major Baltic input pathway. It cannot be modelled as a "downstream" channel in v1's typology because its source is the atmosphere, not an upstream compartment. Phase 2 considers either a new `atmospheric_deposition` channel type or a singleton "atmosphere" pseudo-compartment.

2. **Coastal upwelling.** See §5.5 above.

3. **Submarine groundwater discharge / surface-water exchange.** Relevant in deltaic settings where freshwater seeps into the coastal sea below the surface. v1 channels are surface-water only; phase 2 could introduce `groundwater_discharge`.

4. **Riparian / wetland buffer as first-class archetype.** v1 demotes `wetland` to a phase-2-reserved archetype slot. Phase 2 promotes it with default DAPSI vocabulary and integrates it with `nutrients` channel routing — wetland buffer attenuation as a strength-reduction on incident channels.

5. **Climate as cross-cutting Driver.** Currently each compartment carries its own climate Drivers. Phase 2 considers a singleton "climate" pseudo-compartment whose Drivers fan out to every other compartment via a new `climate_forcing` channel type. This is the framing increasingly preferred in IPCC AR6 Working Group II coastal chapters and in the Polette, Tischer & Elliott (2026) "triple whammy" coastal-tourism paper.

Two further channel types were also flagged as v1 omissions:

6. **`larval_propagule_drift`** — distinct from `organisms_marine_estuarine`, relevant for invertebrates and macrophytes whose dispersal is passive rather than via active swimming.

7. **`invasive_species_spread`** — highly relevant in the Baltic, where round goby, Chinese mitten crab, and *Marenzelleria* polychaetes have spread along the LOAC over the past two decades. Defers because invasion dynamics are bidirectional and timescale-specific.

---

## 7. Operational-extension caveat for the nested framework

Elliott, Burdon & Atkins (2017) define Responses-as-Measures as acting on *Activities* and *Pressures* within the managed system — not across systems. Their nested framework calls for "interlinked" and "nested" structures but does not explicitly endorse cross-system **Response→Pressure causation** as edges in a single composite digraph.

MosaicSES's `governance` channel (a Response in compartment A targeting Pressures in compartment B) is therefore an **operationalisation** of the nested framework, not a literal reading. The operationalisation is defensible:

- Polette, Tischer & Elliott (2026) [`10.1016/j.ocecoaman.2025.108018`] discuss governance cascades across coastal-management scales without formally specifying them as graph edges.
- Lovecraft & Meek (2019) [`10.1016/b978-0-12-814003-1.00039-3`] apply DAPSI(W)R(M) to Arctic coastal systems with explicit nesting but do not formalise cross-system Response edges.
- Source-to-sea practice (UNDP, SIWI, GEF) routinely treats coastal MPAs as drivers of upstream catchment regulation — this is what the channel is meant to represent.

The same caveat applies to `economic_telecoupling`. The telecoupling literature (Liu et al. 2013 and successors) explicitly treats demand-supply pairs as edges in a directed graph, but Elliott et al.'s framework does not. v1 represents both as edges with appropriate confidence weighting; users see the edges as `kind="channel"`, `channel_type="governance"` or `"economic_telecoupling"` and can audit the operationalisation by inspection.

The design spec §1.1 carries this caveat in user-facing form. Future publications using MosaicSES should cite this section explicitly when reporting cross-compartment governance loops.

---

## 8. Fidelity checks against the data sources

The 2026-05-09 review verified the following against authoritative sources:

| Claim | Source | Status |
|---|---|---|
| Curonian Lagoon area = 1584 km² | Sosnina et al. 2024; Cheung et al. 2025 | ✓ confirmed |
| Curonian salinity: south freshwater, north oligohaline | Stakėnienė et al. 2023 | ✓ verbatim |
| Klaipėda Strait as port + salinity gradient | Stakėnienė et al. 2023 | ✓ confirmed |
| Curonian transboundary LT/RU | Standard literature | ✓ uncontested |
| Curonian hypereutrophic state | Aleksandrov et al. 2018; Cheung et al. 2025 | ✓ confirmed |
| Atlantic sturgeon Nemunas extirpation 1962 / restocking 2011 | Stakėnas & Pilinkovskij 2019 | ✓ confirmed |
| Atlantic salmon Nemunas population persisting | Leliūna & Virbickas 2006 | ✓ confirmed |
| AphiaID 127186 = Atlantic salmon | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 127187 = Sea trout | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 126281 = European eel (catadromous) | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 126736 = European smelt | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 126415 = Twaite shad | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 101172 = River lamprey | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 151802 = Atlantic sturgeon | ICES `migratory_species_catalog` | ✓ verified |
| AphiaID 154238 = Houting (taxonomically contested) | ICES `migratory_species_catalog` | ⚠ flagged |
| Coastal upwelling Chl-a gradient shift at Curonian mouth during events | Dabulevičienė et al. 2020 | ✓ confirmed |
| ICES WGDIAD covers diadromous species | ICES `migratory_list_working_groups` | ✓ confirmed |
| Elliott et al. 2017 quote on nested framework | DOI 10.1016/j.marpolbul.2017.03.049 | ✓ verbatim from abstract |

Scientific-credibility verdict from the review (2026-05-09): **publishable** after the seven targeted fixes were applied to the v1 design spec.

---

## 8a. Emerald Growth framework alignment matrix (added second-pass review)

This matrix records exactly which EG framework dimensions are implemented in v1 vs deferred to phase 2. It is the single most-cited table for future EG-aligned publications using MosaicSES. Columns: dimension, source citation, v1 status, where in spec.

| EG dimension | Source | v1 status | Spec location |
|---|---|---|---|
| TW as third-colour space (Green/Blue/Emerald) | Tagliapietra et al. 2020 §1 | ✓ implemented | §1.1 framing, `is_focal_tw` flag in §3 |
| Connectivity as defining TW feature | Elliott (EG monograph definition) | ✓ implemented | §5 channels |
| **Materials** flow (Elliott four-flow) | Elliott (EG definition) | ✓ implemented | §5: water_discharge, nutrients, sediment, pollutants |
| **Organisms** flow (Elliott four-flow) | Elliott (EG definition); ICES WGDIAD | ✓ implemented | §5: organisms_diadromous, organisms_marine_estuarine |
| **Finance** flow (Elliott four-flow) | Elliott (EG definition); Liu 2013 | ⚠ partial | §5: economic_telecoupling (commodity demand only) |
| **Energy** flow (Elliott four-flow) | Elliott (EG definition); Polis 1997 | ✗ deferred | Phase-2 `trophic_energy` channel (spec §11 #16) |
| Cultural / social connectivity | Elliott (EG definition); Robbe et al. 2024 | ✗ deferred | Phase-2 `cultural_connectivity` channel (§11 #18) |
| Endogenic vs exogenic pressures | Elliott 2011 | ✓ implemented (archetype level) | §3 PressureOrigin Literal; §4.3 archetype defaults |
| Three-management-regime intersection (WFD/EPSS/MSFD-MSPD) | Tagliapietra et al. 2020 §3; Lonsdale et al. 2018 | ✓ implemented | §3 GovernanceRegime Literal; §5.5 |
| Cooperation/Confrontation Integrity Index for TTW (0-10 normalized in v1) | Povilanskas & Razinkovas-Baziukas 2023 | ✓ implemented | §3 `cci_index`; §5.5 |
| CICES v5.1 ES coding | Haines-Young & Potschin 2018 (CICES) | ✓ implemented (optional) | §3 `cices_code`; §4.3 archetype defaults |
| 10-tenets evaluation framework | Elliott et al. 2017, 2025 revisited | ✓ implemented (Phase-2 #19) | `tenet_scores` overlay + `tenet_gap_analysis()` (§11 #19) |
| Emerald Justice equity dimensions | Nyka, EG monograph; emerald_justice working draft | ✓ implemented (Phase-2 #20) | `outcome_equity_dimensions` overlay + equity columns on `response_pressure_gap()` (§11 #20) |
| Coastal Circles of Sustainability indicators | Povilanskas et al. 2024 | ✗ deferred | Phase-2 `circles_indicators` (§11 #24) |
| Per-archetype monograph deliverables (Ch.1-Ch.5) | EG monograph chapters | ⚠ partial | §11 #22 (some functions in v1 via comparative dashboard) |
| Designing-new-ecosystems / depolderisation | Tagliapietra notes | ✗ deferred | Phase-2 scenario module (priority D from Q4) |
| TW squeeze (climate-pressured TW) | Tagliapietra notes (Adriatic thermal squeeze analogue) | ✗ deferred | Phase-2 `climate_forcing` channel applied to TW (§11 #13) |

**Coverage summary:** 11 implemented (incl. Phase-2 #19 10-tenets and #20 Emerald Justice, both now shipped to MosaicSES `main`); 6 deferred to phase 2 with concrete backlog entries.

The implementation prioritises the EG framework's **structural** dimensions — the connectivity-flow channels, the pressure origin, the regime intersection, the transboundary index — over its **evaluative** dimensions (tenets, equity, CCS indicators). This is defensible: structural dimensions need to be in the data model from v1 to avoid breaking schema changes; evaluative dimensions are layers on top of an already-correct structural model.

---

## 9. References (consolidated)

### 9.0 Emerald Growth — parent framework (added 2026-05-09 second pass)

Tagliapietra, D., Povilanskas, R., Razinkovas-Baziukas, A., & Taminskas, J. (2020). Emerald Growth: A New Framework Concept for Managing Ecological Quality and Ecosystem Services of Transitional Waters. *Water*, 12(3), 894. https://doi.org/10.3390/w12030894

Povilanskas, R., & Razinkovas-Baziukas, A. (2023). Transboundary Transitional Waters: Arenas for Cross-Border Cooperation or Confrontation? *Sustainability*, 15(13), 9922. https://doi.org/10.3390/su15139922

Povilanskas, R., Jurkienė, A., & Dailidienė, I. (2024). Circles of Coastal Sustainability and Emerald Growth Perspectives for Transitional Waters under Human Stress. *Sustainability*, 16(6), 2544. https://doi.org/10.3390/su16062544

Elliott, M. (2011). Marine science and management means tackling exogenic unmanaged pressures and endogenic managed pressures — A numbered guide. *Marine Pollution Bulletin*, 62(4), 651–655. https://doi.org/10.1016/j.marpolbul.2011.01.040

Lonsdale, J.-A., Nicholson, R., Weston, K., et al. (2018). A user's guide to coping with estuarine management bureaucracy: An Estuarine Planning Support System (EPSS) tool. *Marine Pollution Bulletin*, 127, 463–477. https://doi.org/10.1016/j.marpolbul.2017.12.032

### 9.1 Conceptual framework (DPSIR / DAPSI(W)R(M) / nested)

Elliott, M., Burdon, D., & Atkins, J. P. (2017). "And DPSIR begat DAPSI(W)R(M)!" — A unifying framework for marine environmental management. *Marine Pollution Bulletin*, 118(1–2), 27–40. https://doi.org/10.1016/j.marpolbul.2017.03.049

Elliott, M., & O'Higgins, T. (2020). From DPSIR the DAPSI(W)R(M) Emerges… a Butterfly. In *Ecosystem-Based Management, Ecosystem Services and Aquatic Biodiversity* (pp. 61–86). Springer. https://doi.org/10.1007/978-3-030-45843-0_4

Lovecraft, A. L., & Meek, C. L. (2019). Arctic Coastal Systems: Evaluating the DAPSI(W)R(M) Framework. In *Coasts and Estuaries* (pp. 671–686). Elsevier. https://doi.org/10.1016/b978-0-12-814003-1.00039-3

Polette, M., Tischer, V., & Elliott, M. (2026). The 'triple whammy' of threats to coasts and the 'environment-tourism paradox' — the DAPSI(W)R(M) unifying framework for coastal management. *Ocean & Coastal Management*, 273, 108018. https://doi.org/10.1016/j.ocecoaman.2025.108018

*Further DAPSI(W)R(M) applications, deprioritised footnote (added little beyond Elliott 2017 + Polette 2026):*

Hassan, R., Takyi, R., & Almahrad, B. (2021). Addressing the Drying up of Euphrates River Using DAPSI(W)R(M). https://doi.org/10.13140/rg.2.2.13533.95205

Caviedes Sánchez, V., Elliott, M., & Arenas-Granados, P. (2019). An integrated marine analysis based on the DAPSI(W)R(M) framework for the Southern Belize coastal region. https://doi.org/10.13140/rg.2.2.36019.45602

Izar, G. M., Choueri, R. B., & Martinez, S. T. (2022). The application of the DAPSI(W)R(M) framework to the plastic pellets chain. *Marine Pollution Bulletin*, 180, 113807. https://doi.org/10.1016/j.marpolbul.2022.113807

### 9.2 Estuaries, lagoons, and the fish-guild continuum

Whitfield, A. K. (2020). Fish species in estuaries — from partial association to complete dependency. *Journal of Fish Biology*, 97(4), 1262–1264. https://doi.org/10.1111/jfb.14476

Whitfield, A. K., Potter, I. C., & Neira, F. J. (2023). Modes of ingress by larvae and juveniles of marine fishes into estuaries: From microtidal to macrotidal systems. *Fish and Fisheries*, 24(3), 488–503. https://doi.org/10.1111/faf.12745

Tulp, I., Chen, C., & Vrooman, J. (2022). The nursery function of the Ems estuary for fish. Wageningen Marine Research. https://doi.org/10.18174/583972

Bruno, D. O., Delpiani, S. M., & Eduardo, M. (2018). Diel variation of ichthyoplankton recruitment in a wind-dominated temperate coastal lagoon (Argentina). *Estuarine, Coastal and Shelf Science*, 205, 91–99. https://doi.org/10.1016/j.ecss.2018.03.015

Murase, A., Yamasaki, Y., & Ikehara, Y. (2025). Blackfin Seabass Utilize Small Estuarine Lagoons as Nurseries: Implications From Juvenile Sampling at Habitat and Seascape Scales. *Marine Ecology*, 46(4). https://doi.org/10.1111/maec.70031

Avigliano, E., Ibáñez, A. L., & Fabré, N. N. (2021). Unravelling the complex habitat use of the white mullet, *Mugil curema*, in several coastal environments from Neotropical Pacific and Atlantic waters. *Aquatic Conservation: Marine and Freshwater Ecosystems*, 31(4), 789–801. https://doi.org/10.1002/aqc.3486

Selfati, M. (2023). Updated and comprehensive checklist of the fish fauna of the Marchica Lagoon (Alboran Sea, Morocco), following hydrological intervention. *Egyptian Journal of Aquatic Biology and Fisheries*, 27(2), 251–274. https://doi.org/10.21608/ejabf.2023.291755

Park, J. M., Riedel, R., & Ju, H. H. (2020). Fish Assemblage Structure Comparison between Freshwater and Estuarine Habitats in the Lower Nakdong River, South Korea. *Journal of Marine Science and Engineering*, 8(7), 496. https://doi.org/10.3390/jmse8070496

### 9.3 LOAC biogeochemistry

Felgate, S. L. (2022). The importance of 'invisible' dissolved organic carbon along the land-ocean aquatic continuum. *EGU General Assembly 2022*. https://doi.org/10.5194/egusphere-egu22-13281

### 9.4 Curonian Lagoon, Nemunas, and SE Baltic

Aleksandrov, S. V., Krek, A., & Bubnova, E. S. (2018). Eutrophication and effects of algal bloom in the south-western part of the Curonian Lagoon. *Baltica*, 31(1), 1–12. https://doi.org/10.5200/baltica.2018.31.01

Cheung, H. L. S., Žilius, M., & Politi, T. (2025). Nitrate-driven eutrophication supports high nitrous oxide production and emission in coastal lagoons. *Journal of Geophysical Research: Biogeosciences*, 130(4). https://doi.org/10.1029/2024jg008510

Dabulevičienė, T., Vaičiūtė, D., & Kozlov, I. (2020). Chlorophyll-a variability during upwelling events in the south-eastern Baltic Sea and in the Curonian Lagoon. *Remote Sensing*, 12(21), 3661. https://doi.org/10.3390/rs12213661

Leliūna, E., & Virbickas, J. (2006). Phylogeographic characteristics of the Atlantic salmon (*Salmo salar* L.) population of the Nemunas River. *Acta Zoologica Lituanica*, 16(3), 229–234. https://doi.org/10.1080/13921657.2006.10512736

Sosnina, I., Šeirienė, V., & Grigienė, A. (2024). Holocene environmental changes inferred from palaeobotanical data of Curonian Lagoon sediments. *Baltica*, 77–86. https://doi.org/10.5200/baltica.2024.1.8

Stakėnas, S., & Pilinkovskij, A. (2019). Migration patterns and survival of stocked Atlantic sturgeon (*Acipenser oxyrinchus* Mitchill, 1815) in Nemunas Basin, Baltic Sea. *Journal of Applied Ichthyology*, 35(1), 128–137. https://doi.org/10.1111/jai.13871

Stakėnienė, R., Jokšas, K., & Kriaučiūnienė, J. (2023). Nutrient loadings and exchange between the Curonian Lagoon and the Baltic Sea: Changes over the past two decades (2001–2020). *Water*, 15(23), 4096. https://doi.org/10.3390/w15234096

### 9.6 Connectivity literature (added 2026-05-09 second + third pass)

The connectivity literature is foundational for an Emerald Growth tool. Three concepts deserve foregrounding before the reference list:

**Sheaves 2009 — the coastal ecosystem mosaic.** Sheaves's 2009 paper *"Consequences of ecological connectivity: the coastal ecosystem mosaic"* (`10.3354/meps08121`) is the **conceptual ancestor of the name "MosaicSES"**. Sheaves reframed coastal connectivity beyond the migration-and-nursery view that had dominated estuarine ecology since the 1970s, arguing that a coastal landscape is a mosaic of habitats coupled by movements of organisms, nutrients, and propagules across multiple ontogenetic stages. The MosaicSES compartment-and-channel architecture is a direct software instantiation of this mosaic concept: each compartment is a habitat patch with its own DAPSI internal dynamics, and channels are the connectivity links between patches. Future MosaicSES publications should cite Sheaves 2009 as the conceptual ancestor.

**Pringle 2001 — hydrologic connectivity as matter, energy, organisms.** Pringle's 2001 paper *"Hydrologic connectivity and the management of biological reserves"* (`10.1890/1051-0761(2001)011[0981:hcatmo]2.0.co;2`) defines hydrologic connectivity as "water-mediated transfer of matter, energy, and organisms across the landscape." This is **almost identically the same triple Elliott names** in the EG four-flow definition (materials, energy, organisms — plus finance for the societal-flow extension). Pringle's framing is older and more familiar to the freshwater-ecology community; citing it explicitly in §2.0 makes the lineage from hydrologic-connectivity science to EG legible for that audience.

**Pilosof et al. 2017 — multilayer ecological networks.** Pilosof, Porter, Pascual & Kéfi's 2017 *Nature Ecology & Evolution* paper (`10.1038/s41559-017-0101`) provides the mathematical foundation for representing ecological systems as multilayer networks — exactly what MosaicSES is (compartments × DAPSI element types × channel types). The intra-layer / inter-layer distinction maps directly onto MosaicSES's DAPSI-edges (intra-compartment) vs channel-edges (inter-compartment) architecture. The spec's network-theoretic claims about cross-compartment loop detection and inter-compartment leverage rest on multilayer-network methodology that this paper formalised.

#### 9.6.0 Conceptual / canonical connectivity references (added 2026-05-09 third pass)

Sheaves, M. (2009). Consequences of ecological connectivity: the coastal ecosystem mosaic. *Marine Ecology Progress Series*, 391, 107–115. https://doi.org/10.3354/meps08121 — **Conceptual ancestor of MosaicSES.** Reframes coastal connectivity beyond migration to nutrients, food webs, and ontogeny across a habitat mosaic.

Pringle, C. M. (2001). Hydrologic connectivity and the management of biological reserves: a global perspective. *Ecological Applications*, 11(4), 981–998. https://doi.org/10.1890/1051-0761(2001)011[0981:hcatmo]2.0.co;2 — Defines hydrologic connectivity as water-mediated transfer of matter, energy, and organisms; direct mapping onto Elliott's EG four-flow taxonomy.

Pilosof, S., Porter, M. A., Pascual, M., & Kéfi, S. (2017). The multilayer nature of ecological networks. *Nature Ecology & Evolution*, 1, 0101. https://doi.org/10.1038/s41559-017-0101 — Mathematical foundation for MosaicSES's compartment × DAPSI × channel multilayer architecture.

Tylianakis, J. M., & Morris, R. J. (2017). Ecological networks across environmental gradients. *Annual Review of Ecology, Evolution, and Systematics*, 48, 25–48. https://doi.org/10.1146/annurev-ecolsys-110316-022821 — Network stability and scaling considerations relevant to MosaicSES's metanetwork analyses.

Calabrese, J. M., & Fagan, W. F. (2004). A comparison-shopper's guide to connectivity metrics. *Frontiers in Ecology and the Environment*, 2(10), 529–536. https://doi.org/10.1890/1540-9295(2004)002[0529:acgtcm]2.0.co;2 — Canonical structural / potential / actual-functional connectivity taxonomy; classifies which connectivity-metric class each MosaicSES channel implements (see §9.6.1).

Fausch, K. D., Torgersen, C. E., Baxter, C. V., & Li, H. W. (2002). Landscapes to riverscapes: bridging the gap between research and conservation of stream fishes. *BioScience*, 52(6), 483–498. https://doi.org/10.1641/0006-3568(2002)052[0483:ltrbtg]2.0.co;2 — Bridges scale-mismatch problem; supports MosaicSES's cross-compartment graph at riverscape scale.

Bracken, L. J., & Croke, J. (2007). The concept of hydrological connectivity and its contribution to understanding runoff-dominated geomorphic systems. *Hydrological Processes*, 21(13), 1749–1763. https://doi.org/10.1002/hyp.6313 — Geomorphological foundation for the `sediment` and `water_discharge` channels.

Thorp, J. H., Thoms, M. C., & Delong, M. D. (2006). The riverine ecosystem synthesis: biocomplexity in river networks across space and time. *River Research and Applications*, 22(2), 123–147. https://doi.org/10.1002/rra.901 — Patch-mosaic / functional-process-zone update to the River Continuum Concept; supports compartment-as-patch-mosaic abstraction.

Pérez-Ruzafa, A., Pérez-Ruzafa, I. M., & De Pascalis, F. (2019). Connectivity between coastal lagoons and sea: asymmetrical effects on assemblages' and population's structure. *Estuarine, Coastal and Shelf Science*, 216, 171–186. https://doi.org/10.1016/j.ecss.2018.02.031 — **Canonical inter-lagoon comparative reference** explicitly comparing Mar Menor, Curonian, and Venice lagoons on Lagrangian connectivity asymmetry. Justifies the `lagoon` archetype's inflow/outflow asymmetry semantics.

Hull, V., & Liu, J. (2018). Telecoupling: a new frontier for global sustainability. *Ecology and Society*, 23(4), 41. https://doi.org/10.5751/es-10494-230441 — Update to Liu 2013; introduces "spillover" and multi-level governance vocabulary directly relevant to `economic_telecoupling` and phase-2 `cultural_connectivity` channels.

Macreadie, P. I., et al. (2023). BlueCAM: an Australian blue carbon method to estimate, project, and value coastal blue carbon ecosystems. *Restoration Ecology*, 31(7), e13739. https://doi.org/10.1111/rec.13739 — Operational accounting model linking saltmarsh restoration to carbon-finance flows; bridges materials and `economic_telecoupling` channels for phase-2 `blue_carbon` slot.

Lin, M., Wang, Y., & Zhu, J. (2025). Extreme heatwave affects saltwater intrusion and river plume in the Changjiang Estuary. *Journal of Geophysical Research: Oceans*, 130(4). https://doi.org/10.1029/2024jc022287 — Climate change as connectivity disruptor: heatwave-driven stratification and evaporation reorganise estuarine salinity / plume dynamics. Closes the spec's missing climate-connectivity gap (see §9.6.2).

#### 9.6.1 Foundational longitudinal / lateral connectivity (already in spec, repositioned)

Vannote, R. L., Minshall, G. W., Cummins, K. W., Sedell, J. R., & Cushing, C. E. (1980). The river continuum concept. *Canadian Journal of Fisheries and Aquatic Sciences*, 37(1), 130–137. https://doi.org/10.1139/f80-017 — Foundational longitudinal-connectivity reference; justifies §4.1 `water_discharge` as the LOAC's master variable.

Junk, W. J., Bayley, P. B., & Sparks, R. E. (1989). The flood pulse concept in river-floodplain systems. *Canadian Special Publication of Fisheries and Aquatic Sciences*, 106, 110–127. — Lateral-connectivity foundation; phase-2 wetland/floodplain promotion.

Polis, G. A., Anderson, W. B., & Holt, R. D. (1997). Toward an integration of landscape and food web ecology: the dynamics of spatially subsidized food webs. *Annual Review of Ecology and Systematics*, 28, 289–316. https://doi.org/10.1146/annurev.ecolsys.28.1.289 — Spatial subsidies; basis for phase-2 `trophic_subsidy` channel.

Helfield, J. M., & Naiman, R. J. (2001). Effects of salmon-derived nitrogen on riparian forest growth and implications for stream productivity. *Ecology*, 82(9), 2403–2409. https://doi.org/10.1890/0012-9658(2001)082[2403:eosdno]2.0.co;2 — Worked example of bidirectional diadromous-mediated nutrient connectivity; pairs with §4.5 to show why diadromous channels carry nutrients, not just biomass.

Cowen, R. K., & Sponaugle, S. (2009). Larval dispersal and marine population connectivity. *Annual Review of Marine Science*, 1, 443–466. https://doi.org/10.1146/annurev.marine.010908.163757 — Marine larval-connectivity canonical reference.

Pineda, J., Hare, J. A., & Sponaugle, S. (2007). Larval transport and dispersal in the coastal ocean and consequences for population connectivity. *Oceanography*, 20(3), 22–39. https://doi.org/10.5670/oceanog.2007.27 — Complements Cowen & Sponaugle for benthic-invertebrate dispersal.

Waldman, J. R., & Quinn, T. P. (2022). North American diadromous fishes: drivers of decline and potential for recovery in the Anthropocene. *Science Advances*, 8(4), eabl5486. https://doi.org/10.1126/sciadv.abl5486 — Diadromous-decline review.

Nakamura, T., Katano, O., & Abe, S. (2006). Comparison of fish communities between above- and below-dam sections of small streams: Barrier effect to diadromous fishes. *Journal of Fish Biology*, 68(3), 767–782. https://doi.org/10.1111/j.0022-1112.2006.00964.x — Empirical anchor for the `connectivity_barriers` Pressure.

Karstens, S., Kiesel, J., & Petersen, L. (2022). Human-induced hydrological connectivity: Impacts of footpaths on beach wrack transport in a frequently visited Baltic coastal wetland. *Frontiers in Marine Science*, 9, 929274. https://doi.org/10.3389/fmars.2022.929274 — Baltic-system anchor for lateral hydrological connectivity; ties to phase-2 `wetland` archetype.

Liu, J., Hull, V., Batistella, M., DeFries, R., Dietz, T., Fu, F., et al. (2013). Framing sustainability in a telecoupled world. *Ecology and Society*, 18(2), 26. https://doi.org/10.5751/es-05873-180226 — Foundational telecoupling paper; basis for `economic_telecoupling` channel.

#### 9.6.2 Functional-vs-structural connectivity classification of MosaicSES channels

Following Calabrese & Fagan (2004), connectivity metrics fall into three classes:
- **Structural connectivity** — the physical / spatial linkage between habitats independent of organism movement (e.g., the existence of a hydrological pathway).
- **Potential connectivity** — the predicted movement of organisms through the structural linkage given dispersal capabilities (e.g., the inferred salmon-passable status of a river segment).
- **Actual / functional connectivity** — observed flow of organisms, matter, or information through the linkage.

MosaicSES v1 channels are mostly **structural-with-implied-potential** at qualitative resolution. The `polarity` / `strength` / `confidence` triple captures inferred *potential* connectivity (likely-direction-and-magnitude given system properties); v1 does not require *actual* (measured-flow) evidence. Phase-2's `units` / `timestep` reservation is what would let the actual-functional class be populated. This matters for publication framing: MosaicSES claims should be hedged as potential-connectivity claims unless empirical actual-flow data is added.

#### 9.6.3 Climate change as connectivity disruptor (added 2026-05-09 third pass)

Climate change does not just stress individual compartments — it **reorganises connectivity** itself. Lin, Wang & Zhu (2025, `10.1029/2024jc022287`) document how an extreme heatwave reorganised saltwater intrusion and river-plume dynamics in the Changjiang Estuary; the analogue for the Curonian system is documented coastal upwelling (Dabulevičienė et al. 2020 `10.3390/rs12213661`), heatwave-driven cyanobacterial-bloom intensification, and Nemunas hydrology shift under climate (Čerkasova et al. 2021 `10.1016/j.jhydrol.2021.126422`). v1's `pressure_origin = "exogenic"` tag on climate-related Pressures is the v1 stub; phase-2's `climate_forcing` channel + the proposed *TW squeeze* concept (Tagliapietra notes; analogous to the Adriatic thermal squeeze) operationalises this dimension fully.

### 9.7 Curonian / Baltic lagoon ecosystem services (added 2026-05-09 second pass)

Inácio, M., Schernewski, G., & Nazemtseva, Y. (2018). Ecosystem services provision today and in the past: a comparative study in two Baltic lagoons. *Ecological Research*, 33(6), 1255–1274. https://doi.org/10.1007/s11284-018-1643-8 — Curonian + Szczecin Lagoons; semi-quantitative ES assessment with 39 indicators × 22 services. Direct CICES-ready precedent for v1's ES-coding work.

Bartoli, M., Žilius, M., & Bresciani, M. (2018). Drivers of cyanobacterial blooms in a hypertrophic lagoon. *Frontiers in Marine Science*, 5, 434. https://doi.org/10.3389/fmars.2018.00434 — Drivers of cyanobacterial blooms in Curonian; provides the N-fixation / P-feedback mechanism the §5.3 eutrophication backbone needs in addition to Aleksandrov 2018 + Cheung 2025.

Sruoga, A., Butkauskas, D., & Ragauskas, A. (2007). Investigation of genetic variability in the European eel in Lithuania. *Acta Zoologica Lituanica*, 17(2), 116–123. https://doi.org/10.1080/13921657.2007.10512822 — Curonian eel genetic-connectivity; underpins phase-2 `lifestage` × population-structure expansion of `organisms_diadromous`.

Robbe, E., Rogge, L., & Lesutienė, J. (2024). Assessment of Ecosystem Services Provided by Macrophytes in Southern Baltic and Southern Mediterranean Coastal Lagoons. *Environmental Management*, 74(2), 206–229. https://doi.org/10.1007/s00267-024-01955-9 — Macrophyte ES with Curonian co-author Lesutienė; cultural ES emphasis.

### 9.7.1 Curonian benthic-pelagic and microbial connectivity (added 2026-05-09 third pass)

The Klaipėda University / CORPI research group (Žilius, Vybernaite-Lubiene, Lesutienė, Pilkaitytė, Daunys and collaborators including the Italian Bartoli–Nizzoli–Bresciani group) has published a substantial body of empirical Curonian-system connectivity work that directly underwrites the v1 seed dataset's `nutrients`, `sediment`, `pollutants` and (phase-2) `trophic_energy` channels. These references provide the rate constants, seasonal stoichiometries, and benthic-pelagic coupling mechanisms that *make the Curonian eutrophication–governance loop* (the v1 demo canary, §8.4 Loop 1) scientifically defensible:

Žilius, M., Barisevičiūtė, R., Bonaglia, S., et al. (2024). Riverine inputs and phytoplankton community composition control nitrate cycling in a coastal lagoon. *Biogeosciences*, 21(7), 1693–1709. https://doi.org/10.5194/egusphere-2023-3054 — Spring vs summer benthic-pelagic coupling regimes in Curonian: spring diatoms drive benthic dissimilatory NO₃ processes; summer cyanobacteria drive pelagic assimilatory uptake. **Quantitative basis for the seasonally-varying `nutrients` channel strength in the seed.**

Žilius, M., Marzocchi, U., Bonaglia, S., et al. (2021). Zebra Mussel Holobionts Fix and Recycle Nitrogen in Lagoon Sediments. *Frontiers in Microbiology*, 11, 610269. https://doi.org/10.3389/fmicb.2020.610269 — Zebra mussel densities in Curonian (40–57,000 ind./m², median 12,600 — Daunys et al. 2006). Mussel-associated N₂ fixation as overlooked source of bioavailable N. **Empirical basis for representing benthic invertebrate communities as State elements with feedback to the `nutrients` channel.**

Žilius, M., Vybernaite‐Lubiene, I., Vaičiūtė, D., et al. (2020). Spatiotemporal patterns of N₂ fixation in coastal waters derived from rate measurements and remote sensing. *Biogeosciences*, 17(23), 6047–6062. https://doi.org/10.5194/bg-2020-419 — Combines in-situ N₂-fixation rates with remote-sensing Chl-a to derive lagoon-scale N-budget estimates. **Methodological basis for phase-2 quantitative `nutrients` channel calibration.**

Žilius, M., Bartoli, M., Nizzoli, D., et al. (2021). Denitrification, Nitrogen Uptake, and Organic Matter Quality Undergo Different Seasonality in Sandy and Muddy Sediments of a Turbid Estuary. *Frontiers in Microbiology*, 11, 612700. https://doi.org/10.3389/fmicb.2020.612700 — Denitrification attenuates N delivery from estuary to coastal area by ~35 % in spring; nearly 100 % attenuation in summer. **Quantitative anchor for the lagoon→strait `nutrients` channel attenuation in the seed; demonstrates the lagoon's nutrient-retention ES (one of the lagoon archetype's `default_es`).**

Vybernaite-Lubiene, I., Žilius, M., Bartoli, M., et al. (2018). Recent trends (2012–2016) of N, Si, and P export from the Nemunas River watershed: Loads, unbalanced stoichiometry, and threats for downstream aquatic ecosystems. *Water*, 10(9), 1178. https://doi.org/10.3390/w10091178 — Catchment N/P/Si load time-series; **basis for `nemunas_lower → nemunas_delta` and `nemunas_delta → curonian_lagoon` channel strength values in the seed.**

Lesutienė, J., Bukaveckas, P. A., Gasiūnaitė, Z. R., Pilkaitytė, R., & Razinkovas-Baziukas, A. (2014). Tracing the isotopic signal of a cyanobacteria bloom through the food web of a Baltic Sea coastal lagoon. *Estuarine, Coastal and Shelf Science*, 138, 47–56. https://doi.org/10.1016/j.ecss.2013.12.017 — Stable-isotope tracing of cyanobacterial-bloom carbon and nitrogen through the Curonian food web. **Empirical basis for phase-2 `trophic_energy` and `trophic_subsidy` channels — the user is co-author.**

Pilkaitytė, R., & Razinkovas, A. (2006). Factors controlling phytoplankton blooms in a temperate estuary: Nutrient limitation and physical forcing. *Hydrobiologia*, 555(1), 41–48. https://doi.org/10.1007/s10750-005-1104-6 — User-co-authored phytoplankton-bloom controls; basis for the `lagoon` archetype's `phytoplankton_biomass` State default.

Daunys, D., Zemlys, P., Olenin, S., Zaiko, A., & Ferrarin, C. (2006). Impact of the zebra mussel *Dreissena polymorpha* invasion on the budget of suspended material in a shallow lagoon ecosystem. *Helgoland Marine Research*, 60(2), 113–120. https://doi.org/10.1007/s10152-006-0028-5 — Zebra mussel impact on lagoon suspended-material budget; **basis for representing invasive-species filtration as a phase-2 channel attribute.**

Ferrarin, C., Razinkovas, A., Gulbinskas, S., Umgiesser, G., & Bliūdžiutė, L. (2008). Hydraulic regime-based zonation scheme of the Curonian Lagoon. *Hydrobiologia*, 611(1), 133–146. https://doi.org/10.1007/s10750-008-9453-6 — User-co-authored hydrodynamic zonation; **basis for compartmental sub-zonation if phase-2 promotes intra-lagoon resolution.**

Bresciani, M., Adamo, M., De Carolis, G., et al. (2014). Monitoring blooms and surface accumulation of cyanobacteria in the Curonian Lagoon by combining MERIS and ASAR data. *Remote Sensing of Environment*, 146, 124–135. https://doi.org/10.1016/j.rse.2013.07.040 — Remote-sensing of Curonian cyanobacterial blooms; **complements Dabulevičienė 2020 for lagoon Chl-a monitoring.**

Krevš, A., Koreivienė, J., Paškauskas, R., & Šulijienė, R. (2007). Phytoplankton production and community respiration in different zones of the Curonian Lagoon during the mid-summer vegetation period. *Transitional Waters Bulletin*, 1(1), 17–26. — Lagoon zonation by primary-production regime; basis for lagoon-archetype default States.

Čerkasova, N., Umgiesser, G., & Ertürk, A. (2021). Modelling framework for flow, sediments and nutrient loads in a large transboundary river watershed: A climate change impact assessment of the Nemunas River basin. *Journal of Hydrology*, 598, 126422. https://doi.org/10.1016/j.jhydrol.2021.126422 — Nemunas catchment modelling under climate change; **basis for phase-2 climate-forcing channel calibration.**

Gasiūnaitė, Z. R., Razinkovas-Baziukas, A., & Grinienė, E. (2012). Pelagic patterns along the Nemunas–Curonian Lagoon transition. *Baltica*, 25(1), 77–86. https://doi.org/10.5200/baltica.2012.25.07 — **User-co-authored;** direct empirical characterisation of the river→lagoon plankton-community transition. **Direct seed-data anchor for the `nemunas_delta → curonian_lagoon` boundary.**

Lesutienė, J., Bukaveckas, P. A., Gasiūnaitė, Z. R., et al. (2014). Tracing the isotopic signal of a cyanobacteria bloom through the food web of a Baltic Sea coastal lagoon. *Estuarine, Coastal and Shelf Science*, 138, 47–56. https://doi.org/10.1016/j.ecss.2013.12.017 — Stable-isotope tracing of cyanobacterial bloom carbon and nitrogen through the Curonian food web. **User is co-author; key empirical basis for phase-2 `trophic_energy` and `trophic_subsidy` channels.**

Lesutienė, J., Bukaveckas, P. A., Gasiūnaitė, Z. R., et al. (2017). Microcystin in the food web of the Baltic and Chesapeake Bay coastal regions. *Estuarine, Coastal and Shelf Science*, 191, 50–59. https://doi.org/10.1016/j.ecss.2017.04.016 — Toxin-mediated trophic connectivity along the Curonian–Baltic axis with Chesapeake Bay comparison. **User-group co-authored; basis for phase-2 `pollutants × trophic` cross-channel coupling.**

Žilius, M., Daunys, D., Petkuvienė, J., & Bartoli, M. (2012). Sediment-water O₂, N and P fluxes in the eutrophic Curonian Lagoon under different temperature regimes. *Journal of Limnology*, 71(2), e33. https://doi.org/10.4081/jlimnol.2012.e33 — Daunys + Žilius co-authorship; benthic regulation of pelagic nutrients in Curonian. **Empirical anchor for the `lagoon` archetype's `bottom_water_DO` / `phytoplankton_biomass` State coupling.**

These references are drawn from the Klaipėda University CORPI / Marine Research Institute output — the user's own institutional context — and are non-negotiable for any MosaicSES publication targeting Lithuanian or Baltic peer-reviewers. The user is co-author or institutional-affiliate co-author on at least: Tagliapietra 2020 (EG founding paper), Povilanskas & Razinkovas-Baziukas 2023 (TTW), Povilanskas et al. 2024 (CCS), Gasiūnaitė et al. 2012 (Nemunas-Curonian transition), Lesutienė et al. 2014 (food-web isotopes), Lesutienė et al. 2017 (microcystin food webs), Pilkaitytė & Razinkovas 2006 (phytoplankton), and Ferrarin et al. 2008 (hydraulic zonation).

### 9.5 ICES data sources and working groups

ICES *Migratory species catalogue* — curated diadromous-species list with WoRMS Aphia IDs, accessed via `mcp__ices-fish-data__migratory_species_catalog`. The **diadromous** species v1 references — all verified against the catalogue 2026-06-04 — are: salmon 127186, sea trout 127187, Arctic char 127188, European eel 126281, smelt 126736, twaite shad 126415, allis shad 126413, houting 154238, river lamprey 101172, sea lamprey 101174, Atlantic sturgeon 151802, **European sturgeon 126279** (*Acipenser sturio* — a second, distinct sturgeon, not a typo). The catalogue also includes Vendace 127178 (amphidromous), which v1 does not seed. The **marine-estuarine** species 127141 (flounder), 126417 (herring), 126425 (sprat), 126436 (cod) are from §4.6 / `organisms_marine_estuarine`, NOT this diadromous catalogue.

ICES *Migratory working groups list* — accessed via `mcp__ices-fish-data__migratory_list_working_groups`:
- WGBAST — Baltic Salmon and Trout Assessment Working Group
- WGEEL — Joint EIFAAC/ICES/GFCM Working Group on Eels
- WGNAS — Working Group on North Atlantic Salmon
- **WGDIAD** — Working Group on Diadromous Species (all diadromous: shad, smelt, lamprey, sturgeon)
- WGRECORDS — Working Group on Recreational Fisheries Surveys
- WKBALT — Workshop on Baltic Salmon
- WKTRUTTA — Workshop on Sea Trout
- WKEELMIGR — Workshop on European Eel Migration
- **WKESDLS** — Workshop on Estuarine and Diadromous Species (estuarine phase)

ICES DATRAS, SAG, and SID products are referenced in the design spec for forward integration in phase 2 (per-compartment fish-stock data overlay) but are not consumed by v1.

---

## 10. Document maintenance

This scientific-basis document is maintained alongside the design spec. New literature added during phase-2 work should be appended to the appropriate §9 subsection. Empirical claims about the Curonian system, in particular, should be re-verified against current literature whenever the seed dataset is updated — the lagoon has been actively studied for two decades and recent results frequently sharpen older characterisations.

When a future MosaicSES publication is drafted, this document supplies the methods-section references for the framework choices, the compartment-archetype defaults, and the channel-typology defence. The companion design spec supplies the architectural and software-engineering rationale.
