"""R-exact knowledge-base lookup and context suggestions (K1).

A pure port of the MarineSABRES R app at v1.35.6:

* lookup (``build_context_key``, ``find_context``, ``get_context_elements``,
  ``get_context_connections``) from ``functions/ses_knowledge_db_loader.R``
  :94-307;
* governance / socioeconomic / countries from
  ``functions/country_governance_loader.R`` :103-287, and the hardcoded
  fallbacks from ``modules/ai_isa_knowledge_base.R`` :112-221;
* ``deduplicate_suggestions`` (:237-297), ``get_context_suggestions``
  (:315-577) and ``get_habitat_specific_suggestions`` (:597-895) from
  ``modules/ai_isa_knowledge_base.R``.

R's behaviour is reproduced exactly, quirks included; nothing here "fixes"
R. ``None`` stands for R's ``NULL``. Functions take the parsed JSON (e.g.
``snapshot.kb()``, ``snapshot.governance()``) as arguments and never read the
registry.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

__all__ = [
    "SOURCES",
    "build_context_key",
    "find_context",
    "get_context_elements",
    "get_context_connections",
    "deduplicate_suggestions",
    "get_habitat_specific_suggestions",
    "get_governance_elements",
    "get_socioeconomic_elements",
    "countries_for_sea",
    "get_context_suggestions",
]

#: Source labels of ``get_context_suggestions``, as R's source map names them.
#: ``issue`` is kept for R's map but is unreachable at v1.35.6 (R no longer
#: assigns ``suggestions$issue``).
SOURCES = ("knowledge_db", "governance", "socioeconomic", "regional", "issue",
           "ecosystem", "habitat", "generic")


# ---------------------------------------------------------------------------
# R primitives
# ---------------------------------------------------------------------------

def _trimws(s: str) -> str:
    """R ``trimws``: strips only ``[ \\t\\r\\n]`` (Python's strip() strips more)."""
    return s.strip(" \t\r\n")


def _grepl(pattern: str, s: str, ignore_case: bool = False) -> bool:
    return re.search(pattern, s, re.IGNORECASE if ignore_case else 0) is not None


def _unique(xs: Iterable[str]) -> list[str]:
    """R ``unique`` on a character vector: first occurrence kept, in order."""
    return list(dict.fromkeys(xs))


def _r_sea(sea: str | None) -> str:
    """``tolower(trimws(sea))`` as used in R's ``paste0(sea, "_")``.

    R: ``tolower(trimws(NULL))`` is ``character(0)`` and
    ``paste0(character(0), "_")`` is ``"_"``, so ``None`` behaves like ``""``.
    """
    return "" if sea is None else _trimws(sea).lower()


# ---------------------------------------------------------------------------
# Lookup (ses_knowledge_db_loader.R)
# ---------------------------------------------------------------------------

def build_context_key(sea: str | None, habitat: str | None) -> str | None:
    """R ``.build_context_key`` (:94-128): the regex cascade, first match wins."""
    if sea is None or habitat is None:
        return None
    s = _trimws(sea).lower()
    hab = _trimws(habitat).lower()
    if _grepl("lagoon", hab):
        key = "lagoon"
    elif _grepl("estuar", hab):
        key = "estuary"
    elif _grepl("offshore|open ocean|open water|deep sea|continental shelf|shelf|pelagic", hab):
        key = "offshore"
    elif _grepl("seagrass|sea grass|posidonia", hab):
        key = "seagrass"
    elif _grepl("sch.ren|sk.rg.rd|rocky coast", hab):
        key = "rocky_coast"
    elif _grepl("rocky|rock shore", hab):
        key = "rocky_shore"
    elif _grepl("atoll", hab):
        key = "island"
    elif _grepl("coral|reef", hab):
        key = "coral_reef"
    elif _grepl("island|insular", hab):
        key = "island"
    elif _grepl("archipelago", hab):
        key = "archipelago"
    elif _grepl("ice|arctic", hab):
        key = "sea_ice"
    elif _grepl("open coast|coast(?!al lagoon)", hab):  # perl = TRUE in R
        key = "open_coast"
    elif _grepl("mangrove", hab):
        key = "mangrove"
    elif _grepl("tidal|mudflat", hab):
        key = "tidal_flat"
    elif _grepl("saltmarsh|salt marsh|marsh", hab):
        key = "estuary"
    elif _grepl("benthic|benthos", hab):
        key = "offshore"
    elif _grepl("kelp", hab):
        key = "kelp_forest"
    elif _grepl("fjord", hab):
        key = "fjord"
    elif _grepl("delta", hab):
        key = "delta"
    elif _grepl("sandy|beach", hab):
        key = "sandy_beach"
    else:
        return None
    return f"{s}_{key}"


def find_context(kb: dict | None, sea: str | None, habitat: str | None) -> tuple[str, dict, str] | None:
    """R ``.find_context`` (:142-178): ``(key, context, match)`` or None.

    ``match`` is ``exact``, ``prefix`` (same-sea key that is a prefix of, or
    prefixed by, the built key) or ``sea_only`` (first same-sea key in JSON
    order). Never cross-region.
    """
    contexts = kb.get("contexts") if isinstance(kb, dict) else None
    if contexts is None:
        return None
    context_key = build_context_key(sea, habitat)
    if context_key is not None and contexts.get(context_key) is not None:
        return context_key, contexts[context_key], "exact"
    prefix = _r_sea(sea) + "_"
    if context_key is not None:
        for key in contexts:
            if key.startswith(prefix) and (key.startswith(context_key) or context_key.startswith(key)):
                return key, contexts[key], "prefix"
    for key in contexts:
        if key.startswith(prefix):
            return key, contexts[key], "sea_only"
    return None


def get_context_elements(kb: dict | None, sea: str | None, habitat: str | None, category: str,
                         min_relevance: float = 0.0) -> list[str]:
    """R ``get_context_elements`` (:209-261).

    Matched context, else ``generic_fallback``. A missing or JSON-null
    ``relevance`` counts as 0.5 and a missing/null name as ``""`` (R's
    ``%||%``); empty names are dropped; stable descending sort by relevance.
    """
    if kb is None:
        return []
    m = find_context(kb, sea, habitat)
    data = m[1] if m is not None else kb.get("generic_fallback")
    if data is None:
        return []
    elements = data.get(category)
    if not elements:
        return []
    rows = []
    for el in elements:
        name = el.get("name")
        rel = el.get("relevance")
        rows.append(("" if name is None else name, 0.5 if rel is None else rel))
    kept = [r for r in rows if r[1] >= min_relevance and len(r[0]) > 0]
    # R order(decreasing = TRUE) uses the stable radix sort: ties keep file order
    kept.sort(key=lambda r: -r[1])
    return [n for n, _ in kept]


def get_context_connections(kb: dict | None, sea: str | None, habitat: str | None) -> list[dict]:
    """R ``get_context_connections`` (:284-307): no generic fallback."""
    if kb is None:
        return []
    m = find_context(kb, sea, habitat)
    if m is None:
        return []
    connections = m[1].get("connections")
    if not connections:
        return []
    return connections


# ---------------------------------------------------------------------------
# Semantic dedup (ai_isa_knowledge_base.R :237-297)
# ---------------------------------------------------------------------------

def _r_words(s: str) -> list[str]:
    """R ``unlist(strsplit(s, "\\\\s+"))``: a leading empty token is kept, a
    trailing one dropped, and ``""`` gives no tokens."""
    words = re.split(r"\s+", s)
    if words and words[-1] == "":
        words = words[:-1]
    return words


def _r_core(words: list[str]) -> list[str]:
    """R ``gsub("ing$|ed$|s$", "", words)``: a single strip per word."""
    return [re.sub(r"ing$|ed$|s$", "", w) for w in words]


def deduplicate_suggestions(items: list[str], protected: Iterable[str] = ()) -> list[str]:
    """R ``deduplicate_suggestions(suggestions, protected)``.

    Pairs whose stemmed words overlap by >= 80% (R ``intersect`` counts
    unique words; the denominator counts duplicates) are near-duplicates.
    Protection is case-sensitive on the original label: both protected ->
    keep both; one protected -> drop the other; otherwise the label with
    fewer words wins (ties keep the earlier one).
    """
    items = list(items)
    if len(items) <= 1:
        return items
    prot = set(protected)
    # R recomputes these inside the pair loop; they depend on one item only.
    words = [_r_words(s.lower()) for s in items]
    cores = [_r_core(w) for w in words]
    ucores = [_unique(c) for c in cores]
    keep = [True] * len(items)
    for i in range(len(items)):
        if not keep[i]:
            continue
        current_words, current_core = words[i], cores[i]
        for j in range(len(items)):
            if i >= j or not keep[j]:
                continue
            other_words, other_core = words[j], cores[j]
            common = [w for w in ucores[i] if w in other_core]
            if not common:
                continue
            ratio = len(common) / min(len(current_core), len(other_core))
            if ratio < 0.8:
                continue
            i_prot = items[i] in prot
            j_prot = items[j] in prot
            if i_prot and j_prot:
                continue
            if i_prot != j_prot:
                if i_prot:
                    keep[j] = False
                else:
                    keep[i] = False
                    break
            elif len(current_words) <= len(other_words):
                keep[j] = False
            else:
                keep[i] = False
                break
    return [s for s, k in zip(items, keep) if k]


# ---------------------------------------------------------------------------
# Habitat-specific fallback (ai_isa_knowledge_base.R :597-895)
# ---------------------------------------------------------------------------

def _habitat_key(eco_lower: str) -> str:
    g = lambda p: _grepl(p, eco_lower)  # noqa: E731
    if g("coral|reef"):
        return "coral_reef"
    if g("mangrove"):
        return "mangrove"
    if g("seagrass|sea grass"):
        return "seagrass"
    if g("estuar"):
        return "estuary"
    if g("lagoon"):
        return "lagoon"
    if g("tidal|mudflat|mud flat"):
        return "tidal_flat"
    if g("rocky|rock shore"):
        return "rocky_shore"
    if g("sandy|sand beach"):
        return "sandy_beach"
    if g("kelp"):
        return "kelp_forest"
    if g("fjord"):
        return "fjord"
    if g("delta"):
        return "delta"
    if g("archipelago"):
        return "archipelago"
    if g("offshore|open ocean|open water|deep sea|continental shelf"):
        return "offshore"
    if g("ice|arctic"):
        return "sea_ice"
    if g("upwelling"):
        return "upwelling"
    if g("coast"):
        return "open_coast"
    return "generic"


def _sea_group(sea: str) -> str:
    if sea in ("baltic", "north_sea", "irish_sea"):
        return "northern"
    if sea in ("mediterranean", "caribbean", "pacific", "indian"):
        return "warm"
    if sea in ("atlantic", "east_atlantic"):
        return "atlantic"
    if sea == "arctic":
        return "arctic"
    if sea == "black_sea":
        return "black_sea"
    return "generic"


class _BySea:
    """R's nested ``switch(sea_group, name = ..., default)``."""

    def __init__(self, default: list[str], **by_group: list[str]) -> None:
        self.default = default
        self.by_group = by_group

    def pick(self, group: str) -> list[str]:
        return self.by_group.get(group, self.default)


_HABITAT: dict[str, dict[str, Any]] = {
    "drivers": {
        "coral_reef": ["Reef tourism demand", "Coastal protection need", "Ornamental fish trade",
                       "Reef fisheries dependence", "Climate vulnerability"],
        "mangrove": ["Coastal protection need", "Shrimp aquaculture demand", "Timber demand",
                     "Carbon sequestration value", "Nursery habitat dependence"],
        "seagrass": ["Water quality requirements", "Carbon storage value", "Nursery habitat need",
                     "Recreational boating demand", "Sediment stabilization need"],
        "estuary": _BySea(
            ["Urban expansion", "Flood management", "Agricultural demand", "Port development"],
            northern=["Port and harbor expansion", "Flood risk management", "Industrial water demand",
                      "Dredging requirements", "Recreational fishing demand"],
            warm=["Aquaculture expansion", "Urban water demand", "Flood protection",
                  "Tourism access", "Agricultural runoff"]),
        "lagoon": _BySea(
            ["Fishery demand", "Tourism development", "Flood protection"],
            northern=["Local fishery demand", "Nature tourism demand", "Flood protection need",
                      "Agricultural catchment use", "Cultural heritage preservation"],
            warm=["Aquaculture demand", "Tourism development", "Water abstraction",
                  "Salt production", "Flood buffer need"]),
        "tidal_flat": ["Coastal development pressure", "Bait collection demand",
                       "Bird watching tourism"],
        "rocky_shore": ["Recreational harvesting", "Scientific research interest",
                        "Coastal access demand", "Kelp harvesting"],
        "sandy_beach": ["Beach tourism demand", "Coastal protection need",
                        "Sand mining demand", "Recreational fishing"],
        "fjord": ["Aquaculture expansion", "Tourism demand", "Hydropower influence",
                  "Shipping access", "Freshwater runoff management"],
        "offshore": _BySea(
            ["Energy demand", "Shipping", "Deep-sea resource extraction"],
            northern=["Wind energy demand", "Oil and gas extraction",
                      "Sand and gravel extraction", "Cable and pipeline corridors"],
            warm=["Deep-sea mining interest", "Shipping lanes", "Tuna fisheries demand",
                  "Oil exploration", "Telecommunications cables"],
            arctic=["Arctic shipping routes", "Hydrocarbon exploration",
                    "Strategic mineral extraction"]),
        "sea_ice": ["Arctic shipping route opening", "Resource exploration demand",
                    "Indigenous subsistence needs"],
        "delta": ["Agricultural expansion", "Urban development", "Flood protection",
                  "Sediment management", "Freshwater demand"],
        "archipelago": ["Island tourism demand", "Ferry transport need",
                        "Aquaculture expansion", "Wind energy potential"],
    },
    "activities": {
        "coral_reef": ["Reef diving and snorkeling", "Reef fishing", "Anchor damage from boats",
                       "Coral harvesting", "Glass-bottom boat tours", "Reef monitoring"],
        "mangrove": ["Mangrove clearance for aquaculture", "Charcoal production",
                     "Timber harvesting", "Coastal construction", "Ecotourism"],
        "seagrass": ["Bottom trawling over seagrass", "Boat anchoring in meadows",
                     "Dredging near seagrass", "Nutrient discharge into seagrass areas",
                     "Seagrass restoration planting", "Water quality monitoring"],
        "estuary": _BySea(
            ["Dredging", "Industrial discharge", "Fishing", "Aquaculture"],
            northern=["Port dredging", "Industrial discharge", "Commercial trawling",
                      "Recreational boating", "Coastal flood defense construction",
                      "Mussel and oyster harvesting", "Shellfish water quality monitoring"],
            warm=["Shellfish aquaculture", "Urban wastewater discharge",
                  "Tourist boat traffic", "Artisanal fishing", "Salt harvesting"]),
        "lagoon": _BySea(
            ["Small-scale fishing", "Reed harvesting", "Tourism", "Aquaculture"],
            northern=["Small-scale net fishing", "Reed harvesting", "Recreational angling",
                      "Agricultural drainage management", "Nature tourism"],
            warm=["Shellfish farming", "Fish pond aquaculture", "Salt harvesting",
                  "Tourism infrastructure", "Wastewater inflow"]),
        "tidal_flat": ["Bait digging", "Cockle and clam harvesting", "Land reclamation",
                       "Sea defense construction", "Recreational walking"],
        "rocky_shore": ["Intertidal harvesting", "Rock pooling tourism",
                        "Seaweed collection", "Coastal path maintenance"],
        "sandy_beach": ["Beach nourishment", "Beach tourism activities", "Sand extraction",
                        "Dune stabilization works", "Coastal construction"],
        "fjord": _BySea(
            ["Aquaculture", "Tourism", "Fishing"],
            northern=["Salmon aquaculture", "Tourism cruises", "Hydropower discharge",
                      "Recreational fishing", "Industrial activities"],
            arctic=["Arctic aquaculture", "Cruise tourism", "Mining discharge",
                    "Small-scale fishing", "Fjord monitoring"]),
        "offshore": _BySea(
            ["Commercial fishing", "Shipping", "Energy extraction"],
            northern=["Offshore wind farm construction", "Bottom trawling", "Oil platform operations",
                      "Submarine cable laying", "Aggregate dredging", "Shipping traffic"],
            warm=["Purse seine fishing", "Longline fishing", "Oil exploration",
                  "Deep-water trawling", "Shipping traffic"],
            arctic=["Ice-class shipping", "Seismic surveys", "Exploratory drilling",
                    "Long-range fishing", "Scientific exploration"]),
        "sea_ice": ["Icebreaker shipping", "Under-ice research", "Polar tourism",
                    "Seal hunting", "Indigenous marine harvesting", "Climate monitoring"],
        "delta": ["Upstream dam operations", "Agricultural irrigation", "Dredging for navigation",
                  "Urban expansion on deltaic land", "Aquaculture in delta channels"],
    },
    "pressures": {
        "coral_reef": ["Ocean warming and bleaching", "Ocean acidification", "Sedimentation from runoff",
                       "Physical damage from anchoring", "Overharvesting of reef fish",
                       "Nutrient enrichment from sewage", "Coral disease spread"],
        "mangrove": ["Habitat conversion for aquaculture", "Altered freshwater flow",
                     "Oil pollution", "Sedimentation changes", "Sea level rise inundation"],
        "seagrass": ["Light reduction from turbidity", "Nutrient loading causing algal overgrowth",
                     "Physical damage from mooring", "Propeller scarring",
                     "Sediment disturbance from dredging"],
        "estuary": _BySea(
            ["Nutrient pollution", "Habitat loss", "Altered hydrology"],
            northern=["Nutrient enrichment from agriculture", "Industrial chemical contaminants",
                      "Habitat loss from port expansion", "Altered salinity from water management",
                      "Noise from shipping and construction", "Microplastic accumulation"],
            warm=["Freshwater diversion", "Urban sewage (nutrients, pathogens)", "Pesticides in runoff",
                  "Thermal pollution", "Invasive species introduction"],
            black_sea=["Eutrophication from Danube inputs", "Hydrogen sulfide zones",
                       "Invasive jellyfish (Mnemiopsis)", "Overfishing of anchovy and sprat"]),
        "lagoon": ["Eutrophication", "Reduced water exchange", "Salinity fluctuations",
                   "Sedimentation and infilling", "Invasive species"],
        "tidal_flat": ["Coastal squeeze from sea level rise", "Land claim and reclamation",
                       "Disruption of sediment transport", "Disturbance to wading birds"],
        "rocky_shore": ["Oil spill exposure", "Microplastic accumulation",
                        "Invasive species colonization", "Thermal stress from warming",
                        "Ocean acidification weakening shells"],
        "sandy_beach": ["Coastal erosion", "Sand mining depletion", "Light pollution affecting nesting",
                        "Litter and microplastics", "Disturbance to nesting species"],
        "offshore": _BySea(
            ["Overfishing", "Pollution", "Habitat disturbance"],
            northern=["Bottom trawling disturbance", "Underwater noise from construction",
                      "Electromagnetic fields from cables", "Sediment plumes from dredging",
                      "Chemical contamination from oil platforms"],
            warm=["Overfishing of pelagic stocks", "Marine debris accumulation",
                  "Ship-strike risk to cetaceans", "Deep-sea habitat disturbance"],
            arctic=["Oil spill risk in ice", "Noise from seismic surveys",
                    "Black carbon deposition", "Arctic warming amplification"]),
        "sea_ice": ["Ice extent reduction", "Earlier ice breakup", "Ocean freshening",
                    "Habitat loss for ice-dependent species", "Increased UV exposure"],
        "delta": ["Reduced sediment supply from dams", "Saltwater intrusion",
                  "Land subsidence", "Flooding regime changes", "Pollutant concentration"],
    },
    "states": {
        "coral_reef": ["Coral cover and health", "Reef fish assemblage", "Reef structural complexity",
                       "Algal cover balance", "Water clarity", "Calcification rates"],
        "mangrove": ["Mangrove forest extent", "Root system integrity", "Sediment trapping capacity",
                     "Nursery habitat quality", "Carbon burial rates"],
        "seagrass": ["Seagrass bed extent", "Shoot density", "Epiphyte load",
                     "Sediment stability", "Associated fauna diversity"],
        "estuary": ["Water column stratification", "Dissolved oxygen levels", "Nutrient cycling efficiency",
                    "Benthic community health", "Fish migration patterns", "Salinity gradient"],
        "lagoon": ["Water exchange rate", "Trophic status", "Sediment quality",
                   "Phytoplankton community", "Macroalgal coverage"],
        "tidal_flat": ["Intertidal area extent", "Benthic invertebrate abundance",
                       "Sediment grain size distribution", "Wading bird populations"],
        "rocky_shore": ["Intertidal community zonation", "Algal canopy cover",
                        "Limpet and barnacle populations", "Rock pool biodiversity"],
        "sandy_beach": ["Beach profile dynamics", "Infauna community", "Dune vegetation cover",
                        "Turtle nesting success", "Shorebird foraging habitat"],
        "offshore": ["Pelagic food web structure", "Demersal community composition",
                     "Primary productivity", "Water column mixing", "Seabed integrity"],
        "sea_ice": ["Sea ice extent and thickness", "Under-ice algal production",
                    "Ice-dependent species populations", "Polar food web dynamics"],
        "delta": ["Sediment budget balance", "Wetland extent", "Freshwater-saltwater interface",
                  "Delta morphodynamics", "Floodplain connectivity"],
        "fjord": ["Water column stratification", "Deep water renewal frequency",
                  "Benthic oxygen conditions", "Plankton community composition"],
    },
    "impacts": {
        "coral_reef": ["Reef fishery productivity", "Coastal wave protection", "Tourism attraction value",
                       "Biodiversity reservoir", "Pharmaceutical potential",
                       "Cultural and spiritual significance"],
        "mangrove": ["Storm surge protection", "Nursery function for fisheries",
                     "Blue carbon storage", "Water filtration", "Timber provision",
                     "Erosion prevention"],
        "seagrass": ["Carbon sequestration", "Nursery grounds for commercial species",
                     "Water clarity maintenance", "Sediment stabilization",
                     "Nutrient cycling support"],
        "estuary": ["Fish and shellfish nursery", "Nutrient processing and removal",
                    "Flood attenuation", "Navigation channel provision",
                    "Recreational and aesthetic value", "Carbon burial"],
        "lagoon": _BySea(
            ["Fish provisioning", "Water purification", "Bird habitat", "Flood buffering"],
            northern=["Freshwater fish provisioning", "Water purification by reed beds",
                      "Waterbird habitat provision", "Flood buffering", "Carbon storage"],
            warm=["Aquaculture production capacity", "Water purification",
                  "Bird habitat provision", "Flood buffering", "Salt production"]),
        "offshore": ["Fish stock provision", "Climate regulation", "Nutrient cycling",
                     "Waste assimilation", "Shipping route provision"],
        "sea_ice": ["Climate regulation (albedo)", "Habitat for ice-dependent species",
                    "Indigenous food provision", "Freshwater storage"],
        "sandy_beach": ["Coastal protection", "Tourism and recreation value",
                        "Nesting habitat for turtles and birds", "Sand resource provision"],
        "rocky_shore": ["Food provision (shellfish, seaweed)", "Education and research value",
                        "Recreation (rock pooling)", "Coastal protection"],
    },
    "welfare": {
        "coral_reef": ["Reef tourism revenue", "Reef fishery livelihoods", "Coastal property protection",
                       "Cultural heritage value", "Dive industry employment"],
        "mangrove": ["Coastal community safety", "Fishery catch value", "Carbon credit revenue",
                     "Traditional resource access", "Ecotourism income"],
        "seagrass": ["Commercial fish catch value", "Carbon offset potential",
                     "Recreational value", "Shoreline protection savings"],
        "estuary": ["Port and shipping revenue", "Fishery income", "Flood damage avoidance",
                    "Waterfront property values", "Recreational spending"],
        "offshore": ["Commercial fish catch value", "Energy production revenue",
                     "Shipping trade value", "Employment in marine sectors"],
        "sea_ice": ["Indigenous food security", "Arctic shipping savings",
                    "Resource extraction revenue", "Climate stability contribution"],
    },
    "responses": {
        "coral_reef": ["Marine Protected Area designation", "Coral reef restoration",
                       "Mooring buoy installation", "Reef-safe sunscreen regulations",
                       "Coral nursery programs", "Tourism carrying capacity limits"],
        "mangrove": ["Mangrove replanting programs", "Aquaculture zoning regulations",
                     "Community mangrove management", "Blue carbon REDD+ projects",
                     "Mangrove protected area designation"],
        "seagrass": ["Seagrass protection zones", "Mooring management areas",
                     "Nutrient reduction programs", "Seagrass transplanting initiatives"],
        "estuary": _BySea(
            ["Water Framework Directive measures", "Habitat restoration", "Pollution control"],
            northern=["Nutrient Action Plans (HELCOM/OSPAR)", "Fish passage restoration",
                      "Industrial discharge permits", "Managed realignment"],
            warm=["Wastewater treatment upgrades", "River basin management plans",
                  "Estuary habitat restoration", "Fishery co-management"]),
        "lagoon": ["Water exchange improvement structures", "Nutrient input reduction",
                   "Lagoon habitat restoration", "Sustainable aquaculture certification"],
        "offshore": _BySea(
            ["Fishery management", "Marine spatial planning", "Pollution prevention"],
            northern=["Fishery quota management", "Marine spatial planning", "Offshore wind farm EIA",
                      "Ship traffic separation schemes", "Decommissioning standards"],
            warm=["Regional fisheries management", "High seas protection agreements",
                  "Vessel monitoring systems", "Bycatch reduction devices"]),
        "sea_ice": ["Arctic environmental protection", "Polar Code shipping regulations",
                    "Ice-dependent species protection", "Climate adaptation planning",
                    "Indigenous co-management agreements"],
        "sandy_beach": ["Beach nourishment programs", "Dune restoration",
                        "Light pollution regulations for nesting", "Litter cleanup initiatives"],
    },
}


def get_habitat_specific_suggestions(category: str, sea: str | None, ecosystem: str | None) -> list[str]:
    """R ``get_habitat_specific_suggestions`` (:597-895).

    Its own regex cascade (not the lookup's) on the lower-cased ecosystem and
    a sea group from the raw sea slug; any key or group without an entry
    falls to R's ``switch`` default.
    """
    if sea is None or ecosystem is None:
        return []
    table = _HABITAT.get(category)
    if table is None:
        return []
    entry = table.get(_habitat_key(ecosystem.lower()))
    if entry is None:
        return []
    if isinstance(entry, _BySea):
        entry = entry.pick(_sea_group(sea))
    return list(entry)


# ---------------------------------------------------------------------------
# Countries, governance, socioeconomic (country_governance_loader.R)
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    "d": "drivers", "drivers": "drivers", "driver": "drivers",
    "a": "drivers",
    "r": "responses", "responses": "responses", "response": "responses",
    "m": "responses", "measures": "responses",
    "hw": "welfare", "welfare": "welfare", "human_wellbeing": "welfare",
    "human wellbeing": "welfare", "gb": "welfare",
    "goods_benefits": "welfare", "goods & benefits": "welfare",
}


def _map_category(category: str | None) -> str | None:
    """R ``.map_category`` (:154-168). An unmapped name errors in R
    (``subscript out of bounds``); ``get_context_suggestions`` then takes the
    hardcoded fallback, which yields nothing for such names, so None here
    means "return []"."""
    if not isinstance(category, str):
        return None
    return _CATEGORY_MAP.get(_trimws(category).lower())


def _gov_available(gov: dict | None) -> bool:
    """R ``country_governance_db_available``: loaded and has countries."""
    return isinstance(gov, dict) and bool(gov.get("countries"))


def _resolve_countries(gov: dict, codes: Iterable[str]) -> list[dict]:
    """R ``.resolve_countries``: trimmed upper-case codes; a repeated code
    keeps its first position (``records[[uc]] <- rec``)."""
    countries = gov.get("countries")
    if countries is None:
        return []
    records: dict[str, dict] = {}
    for code in codes:
        if not isinstance(code, str):
            continue
        uc = _trimws(code).upper()
        rec = countries.get(uc)
        if rec is not None:
            records[uc] = rec
    return list(records.values())


def get_governance_elements(gov: dict | None, codes: list[str] | None, category: str) -> list[str]:
    """R ``get_governance_elements`` (:184-234)."""
    if gov is None or not codes:
        return []
    cat_key = _map_category(category)
    if cat_key is None:
        return []
    records = _resolve_countries(gov, codes)
    if not records:
        return []
    elements: list[str] = []
    groups = [g for g in _unique((r.get("governance_group") or "") for r in records) if len(g) > 0]
    gov_elements = gov.get("governance_elements") or {}
    for grp in groups:
        grp_data = gov_elements.get(grp)
        if grp_data is not None and grp_data.get(cat_key) is not None:
            elements.extend(grp_data[cat_key])
    conventions = _unique(c for r in records for c in (r.get("regional_conventions") or []))
    if cat_key == "responses" and conventions:
        conv_table = gov.get("regional_conventions") or {}
        for conv in conventions:
            conv_data = conv_table.get(conv)
            if conv_data is not None and conv_data.get("responses") is not None:
                elements.extend(conv_data["responses"])
    return _unique(elements)


def get_socioeconomic_elements(gov: dict | None, codes: list[str] | None, category: str) -> list[str]:
    """R ``get_socioeconomic_elements`` (:250-287): drivers and welfare only."""
    if gov is None or not codes:
        return []
    cat_key = _map_category(category)
    if cat_key is None or cat_key not in ("drivers", "welfare"):
        return []
    records = _resolve_countries(gov, codes)
    if not records:
        return []
    elements: list[str] = []
    levels = [lv for lv in _unique((r.get("income_level") or "") for r in records) if len(lv) > 0]
    socio = gov.get("socioeconomic_elements") or {}
    for lvl in levels:
        lvl_data = socio.get(lvl)
        if lvl_data is not None and lvl_data.get(cat_key) is not None:
            elements.extend(lvl_data[cat_key])
    return _unique(elements)


def countries_for_sea(gov: dict | None, sea: str | None) -> list[dict]:
    """R ``get_countries_for_sea`` (:103-128) as ``{code, name_en, eu_member}``
    in ``countries_by_sea`` order (``eu_member`` is R's ``isTRUE``)."""
    if gov is None or not isinstance(sea, str):
        return []
    codes = (gov.get("countries_by_sea") or {}).get(_trimws(sea).lower())
    if not codes:
        return []
    countries = gov.get("countries") or {}
    records: dict[str, dict] = {}
    for code in codes:
        rec = countries.get(code)
        if rec is not None:
            records[code] = rec
    return [{"code": r.get("code"), "name_en": r.get("name_en"), "eu_member": r.get("eu_member") is True}
            for r in records.values()]


# Hardcoded fallbacks, used by R only when the governance DB is unavailable
# (ai_isa_knowledge_base.R :112-221).

_EU = {"SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "ES", "FR", "IT", "GR", "HR", "SI",
       "MT", "CY", "NL", "BE", "PT", "IE", "BG", "RO"}
_HELCOM = {"SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "RU"}
_BARCELONA = {"ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY", "TR", "TN", "DZ", "MA", "LY",
              "EG", "IL", "LB", "SY", "ME", "AL"}
_OSPAR = {"GB", "NL", "BE", "DE", "DK", "NO", "SE", "FR", "PT", "ES", "IE", "IS"}
_ARCTIC = {"NO", "RU", "CA", "US", "DK", "IS", "SE", "FI"}
_COASTAL_DEPENDENT = {"FJ", "MV", "BB", "BS", "JM", "TT", "MT", "CY", "IS", "MG", "MZ", "BZ"}
_FISHING_NATIONS = {"NO", "IS", "ES", "JP", "CN", "ID", "PH", "IN", "TH", "PE", "CL"}
_SHIPPING_NATIONS = {"NL", "DE", "GB", "NO", "DK", "GR", "CN", "JP", "SG", "US"}


def _governance_elements_hardcoded(codes: list[str], category: str) -> list[str]:
    """R ``.get_governance_elements_hardcoded``: raw codes, exact match."""
    if not codes or category != "responses":
        return []
    cs = set(codes)
    out: list[str] = []
    if cs & _EU:
        out += ["EU Marine Strategy Framework Directive (MSFD)", "EU Common Fisheries Policy (CFP)",
                "EU Water Framework Directive", "Natura 2000 marine sites",
                "EU Biodiversity Strategy 2030", "EU Blue Economy Strategy"]
    if cs & _HELCOM:
        out.append("HELCOM Baltic Sea Action Plan")
    if cs & _BARCELONA:
        out.append("Barcelona Convention (UNEP/MAP)")
    if cs & _OSPAR:
        out.append("OSPAR Convention")
    if cs & _ARCTIC:
        out.append("Arctic Council frameworks")
    return _unique(out)


def _socioeconomic_elements_hardcoded(codes: list[str], category: str) -> list[str]:
    """R ``.get_socioeconomic_elements_hardcoded``."""
    if not codes:
        return []
    cs = set(codes)
    out: list[str] = []
    if category == "drivers":
        if cs & _COASTAL_DEPENDENT:
            out += ["Tourism-dependent economy", "Coastal community livelihoods",
                    "Small-scale fisheries dependency"]
        if cs & _FISHING_NATIONS:
            out += ["Industrial fisheries demand", "Seafood export economy", "Fish processing industry"]
        if cs & _SHIPPING_NATIONS:
            out += ["Maritime transport demand", "Port infrastructure development"]
    if category == "welfare":
        if cs & _COASTAL_DEPENDENT:
            out += ["Tourism revenue vulnerability", "Coastal community displacement risk",
                    "Food security from marine resources"]
    return _unique(out)


# ---------------------------------------------------------------------------
# get_context_suggestions (ai_isa_knowledge_base.R :315-577)
# ---------------------------------------------------------------------------

_UNIVERSAL = {
    "drivers": ["Food security", "Economic development", "Recreation and tourism",
                "Energy needs", "Coastal protection", "Cultural heritage",
                "Employment", "Trade and commerce"],
    "activities": ["Commercial fishing", "Aquaculture", "Shipping", "Coastal development",
                   "Environmental monitoring"],
    "pressures": ["Nutrient enrichment", "Overfishing", "Physical disturbance",
                  "Marine litter", "Underwater noise", "Habitat loss"],
    "states": ["Water quality decline", "Biodiversity loss", "Habitat degradation",
               "Species population changes", "Oxygen depletion"],
    "impacts": ["Loss of ecosystem services", "Reduced fish catches", "Coastal vulnerability",
                "Economic losses", "Health risks", "Cultural loss"],
    "welfare": ["Income loss", "Food insecurity", "Health impacts", "Cultural identity loss",
                "Displacement", "Recreational opportunities loss"],
    "responses": ["Marine Protected Areas", "Fishing regulations", "Pollution controls",
                  "Ecosystem restoration", "Stakeholder engagement"],
}


def _regional(category: str, sea: str) -> list[str] | None:
    """R's region-specific branches; compares the RAW sea (case-sensitive)."""
    if category == "activities":
        if sea in ("baltic", "north_sea", "irish_sea"):
            return ["Wind farm development", "Dredging", "Oil and gas extraction",
                    "Trawl fishing", "Marine aggregate extraction"]
        if sea in ("mediterranean", "caribbean"):
            return ["Beach recreation", "Yacht tourism", "Scuba diving", "Coastal construction"]
        if sea == "arctic":
            return ["Ice navigation", "Arctic oil exploration", "Cold-water fishing"]
        if sea in ("pacific", "indian"):
            return ["Reef fishing", "Mangrove clearing", "Port expansion"]
    elif category == "pressures":
        if sea == "baltic":
            return ["Hypoxia", "Algal blooms", "Sediment resuspension"]
        if sea == "north_sea":
            return ["Seabed abrasion", "Hydrocarbon contamination", "Noise from shipping"]
        if sea in ("mediterranean", "caribbean"):
            return ["Coastal erosion", "Beach trampling", "Anchor damage"]
        if sea == "arctic":
            return ["Oil spill risk", "Ice habitat loss", "Black carbon deposition"]
    elif category == "states":
        if sea == "baltic":
            return ["Benthic fauna decline", "Cod stock collapse", "Seagrass decline"]
        if sea in ("mediterranean", "caribbean", "pacific", "indian"):
            return ["Coral bleaching", "Seagrass loss", "Reef degradation"]
        if sea == "arctic":
            return ["Sea ice reduction", "Permafrost thaw", "Species range shifts"]
        if sea == "north_sea":
            return ["Benthic community changes", "Fish stock declines", "Phytoplankton shifts"]
    elif category == "responses":
        if sea == "baltic":
            return ["Nutrient reduction targets", "Oxygen restoration", "Fish stock recovery plans"]
        if sea in ("mediterranean", "caribbean"):
            return ["Coral restoration", "Beach management plans", "Marine debris reduction"]
        if sea == "north_sea":
            return ["Trawling restrictions", "Wind farm planning", "Oil spill preparedness"]
        if sea == "arctic":
            return ["Shipping regulations", "Ice habitat protection", "Indigenous co-management"]
    # drivers: no region-specific lists since v1.35.0; impacts/welfare never had any
    return None


def _ecosystem(category: str, eco: str) -> list[str] | None:
    """R's ecosystem branches: case-insensitive regex on the RAW ecosystem."""
    g = lambda p: _grepl(p, eco, ignore_case=True)  # noqa: E731
    if category == "states":
        if g("coral|reef"):
            return ["Coral cover decline", "Fish diversity loss", "Reef structural complexity loss"]
        if g("mangrove"):
            return ["Mangrove forest area loss", "Carbon storage reduction", "Nursery habitat loss"]
        if g("estuar"):
            return ["Salinity changes", "Turbidity increase", "Migratory fish decline"]
    elif category == "impacts":
        if g("coral|reef"):
            return ["Tourism revenue loss", "Coastal protection loss", "Fishery collapse"]
        if g("mangrove"):
            return ["Storm protection loss", "Nursery habitat loss", "Carbon release"]
        if g("seagrass"):
            return ["Nursery function loss", "Water clarity decline", "Carbon storage loss"]
        if g("estuar"):
            return ["Fishery productivity loss", "Water quality impacts", "Flood risk increase"]
    return None


def get_context_suggestions(kb: dict | None, gov: dict | None, category: str, sea: str | None,
                            ecosystem: str | None, main_issue: list[str] | None = None,
                            countries: list[str] | None = None) -> list[tuple[str, str]]:
    """R ``get_context_suggestions(..., return_sources = TRUE)`` as ``(name, source)``.

    ``main_issue`` is accepted and ignored, as R ignores it from v1.35.0.
    """
    del main_issue  # R: "kept for callers; unused"
    s: dict[str, list[str]] = {}

    # Priority 1: the JSON KB, only when "available" (loaded with contexts)
    if isinstance(kb, dict) and kb.get("contexts"):
        try:
            kb_elements = get_context_elements(kb, sea, ecosystem, category, min_relevance=0.5)
        except Exception:  # R: tryCatch(..., error = function(e) character(0))
            kb_elements = []
        if kb_elements:
            s["knowledge_db"] = kb_elements
    kb_sufficient = len(s.get("knowledge_db", [])) >= 3

    # Priority 2: hardcoded lists
    if category in _UNIVERSAL and not kb_sufficient:
        s["universal"] = list(_UNIVERSAL[category])
    if sea is not None:
        regional = _regional(category, sea)
        if regional is not None:
            s["regional"] = regional
    if ecosystem is not None:
        eco_list = _ecosystem(category, ecosystem)
        if eco_list is not None:
            s["ecosystem"] = eco_list

    if not s.get("knowledge_db"):
        habitat = get_habitat_specific_suggestions(category, sea, ecosystem)
        if habitat:
            s["habitat"] = habitat

    if countries:
        if _gov_available(gov):
            gov_elements = get_governance_elements(gov, countries, category)
            se_elements = get_socioeconomic_elements(gov, countries, category)
        else:
            gov_elements = _governance_elements_hardcoded(countries, category)
            se_elements = _socioeconomic_elements_hardcoded(countries, category)
        if gov_elements:
            s["governance"] = gov_elements
        if se_elements:
            s["socioeconomic"] = se_elements

    order = ("knowledge_db", "universal", "regional", "ecosystem", "habitat", "issue",
             "governance", "socioeconomic")
    all_suggestions = _unique(x for k in order for x in s.get(k, []))
    deduplicated = deduplicate_suggestions(all_suggestions, protected=s.get("knowledge_db", []))

    priority = ("knowledge_db", "governance", "socioeconomic", "regional", "issue",
                "ecosystem", "habitat")
    sets = {k: set(s.get(k, [])) for k in priority}
    out: list[tuple[str, str]] = []
    for name in deduplicated:
        out.append((name, next((k for k in priority if name in sets[k]), "generic")))
    return out
