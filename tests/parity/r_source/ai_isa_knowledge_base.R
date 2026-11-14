# modules/ai_isa_knowledge_base.R
# Knowledge Base and Context-Aware Suggestions for AI ISA Assistant
# Purpose: Provides regional seas data and context-aware suggestions for DAPSI(W)R(M) elements

# ============================================================================
# REGIONAL SEAS KNOWLEDGE BASE
# ============================================================================

#' Get Regional Seas Knowledge Base
#'
#' Returns a list of regional seas with their characteristics, common issues,
#' and ecosystem types.
#'
#' @param i18n Internationalization object for translations
#' @return List of regional seas with their properties
get_regional_seas_knowledge_base <- function(i18n) {
  list(
    baltic = list(
      name_en = "Baltic Sea",
      name_i18n = i18n$t("common.misc.baltic_sea"),
      common_issues = c("Eutrophication", "Overfishing", "Pollution", "Invasive species", "Climate change"),
      ecosystem_types = c("Open coast", "Rocky coast (Schären)", "Archipelago", "Island", "Estuary", "Coastal lagoon", "Offshore waters")
    ),
    mediterranean = list(
      name_en = "Mediterranean Sea",
      name_i18n = i18n$t("common.misc.mediterranean_sea"),
      common_issues = c("Overfishing", "Coastal development", "Tourism pressure", "Marine litter", "Invasive species", "Climate change"),
      ecosystem_types = c("Open coast", "Island", "Coastal lagoon", "Rocky shore", "Sandy beach", "Seagrass meadow", "Offshore waters")
    ),
    north_sea = list(
      name_en = "North Sea",
      name_i18n = i18n$t("common.misc.north_sea"),
      common_issues = c("Overfishing", "Oil and gas extraction", "Shipping", "Wind energy development", "Climate change", "Eutrophication"),
      ecosystem_types = c("Open coast", "Estuary", "Tidal flat", "Offshore waters", "Rocky shore", "Sandy beach")
    ),
    irish_sea = list(
      name_en = "Irish Sea",
      name_i18n = i18n$t("common.misc.irish_sea"),
      common_issues = c("Overfishing", "Coastal development", "Shipping", "Marine litter", "Eutrophication", "Climate change"),
      ecosystem_types = c("Open coast", "Estuary", "Coastal lagoon", "Rocky shore", "Sandy beach", "Offshore waters")
    ),
    east_atlantic = list(
      name_en = "East Atlantic",
      name_i18n = i18n$t("common.misc.east_atlantic"),
      common_issues = c("Overfishing", "Climate change", "Ocean acidification", "Shipping", "Coastal erosion", "Marine litter"),
      ecosystem_types = c("Open coast", "Continental shelf", "Offshore waters", "Rocky shore", "Sandy beach", "Estuary")
    ),
    black_sea = list(
      name_en = "Black Sea",
      name_i18n = i18n$t("common.misc.black_sea"),
      common_issues = c("Eutrophication", "Overfishing", "Pollution", "Invasive species", "Coastal erosion"),
      ecosystem_types = c("Open coast", "Delta", "Coastal lagoon", "Offshore waters", "Estuary")
    ),
    atlantic = list(
      name_en = "Atlantic Ocean",
      name_i18n = i18n$t("common.misc.atlantic_ocean"),
      common_issues = c("Overfishing", "Climate change", "Ocean acidification", "Shipping", "Deep-sea mining"),
      ecosystem_types = c("Open ocean", "Island", "Estuary", "Continental shelf", "Coastal upwelling", "Open coast", "Offshore waters")
    ),
    pacific = list(
      name_en = "Pacific Ocean",
      name_i18n = i18n$t("common.misc.pacific_ocean"),
      common_issues = c("Overfishing", "Coral bleaching", "Plastic pollution", "Climate change", "Illegal fishing"),
      ecosystem_types = c("Coral reef", "Island", "Atoll", "Open ocean", "Coastal waters", "Mangrove", "Offshore waters")
    ),
    indian = list(
      name_en = "Indian Ocean",
      name_i18n = i18n$t("common.misc.indian_ocean"),
      common_issues = c("Overfishing", "Coastal erosion", "Mangrove loss", "Climate change", "Illegal fishing"),
      ecosystem_types = c("Coral reef", "Island", "Mangrove", "Open coast", "Lagoon", "Offshore waters")
    ),
    caribbean = list(
      name_en = "Caribbean Sea",
      name_i18n = i18n$t("common.misc.caribbean_sea"),
      common_issues = c("Coral bleaching", "Overfishing", "Tourism pressure", "Hurricanes", "Sargassum blooms"),
      ecosystem_types = c("Coral reef", "Island", "Mangrove", "Seagrass bed", "Sandy beach", "Open coast")
    ),
    arctic = list(
      name_en = "Arctic Ocean",
      name_i18n = i18n$t("common.misc.arctic_ocean"),
      common_issues = c("Climate change", "Sea ice loss", "Oil and gas exploration", "Shipping increase", "Arctic fisheries"),
      ecosystem_types = c("Sea ice", "Island", "Open ocean", "Fjord", "Coastal waters", "Continental shelf")
    ),
    other = list(
      name_en = "Other/Regional",
      name_i18n = i18n$t("common.misc.otherregional"),
      common_issues = c("Overfishing", "Pollution", "Coastal development", "Climate change"),
      ecosystem_types = c("Open coast", "Estuary", "Lagoon", "Offshore waters", "Rocky shore")
    )
  )
}

# ============================================================================
# COUNTRY DATA FOR REGIONAL SEAS
# ============================================================================

# get_countries_for_sea() lives in functions/country_governance_loader.R
# (JSON-backed, records carry $name_en). A hard-coded copy here used to
# shadow or be shadowed by it depending on source() order (review
# 2026-10-07 N39).

#' Get Governance Elements Based on Countries (hardcoded fallback)
#'
#' Returns governance-related DAPSIWRM suggestions based on selected countries.
#' Focuses on policy frameworks, regulations, and institutional responses
#' relevant to the selected countries. Used as fallback when the JSON-based
#' country governance database is not available.
#'
#' @param countries Character vector of country codes
#' @param category DAPSIWRM category
#' @return Character vector of governance-related suggestions
.get_governance_elements_hardcoded <- function(countries, category) {
  if (is.null(countries) || length(countries) == 0) return(character(0))

  # Only relevant for responses category
  if (category != "responses") return(character(0))

  governance <- character(0)

  # Check if any EU member states are selected
  eu_countries <- c("SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE",
                    "ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY",
                    "NL", "BE", "PT", "IE", "BG", "RO")
  has_eu <- any(countries %in% eu_countries)

  if (has_eu) {
    governance <- c(governance,
      "EU Marine Strategy Framework Directive (MSFD)",
      "EU Common Fisheries Policy (CFP)",
      "EU Water Framework Directive",
      "Natura 2000 marine sites",
      "EU Biodiversity Strategy 2030",
      "EU Blue Economy Strategy"
    )
  }

  # Regional convention-based governance
  if (any(countries %in% c("SE", "FI", "DK", "DE", "PL", "LT", "LV", "EE", "RU"))) {
    governance <- c(governance, "HELCOM Baltic Sea Action Plan")
  }
  if (any(countries %in% c("ES", "FR", "IT", "GR", "HR", "SI", "MT", "CY",
                            "TR", "TN", "DZ", "MA", "LY", "EG", "IL", "LB",
                            "SY", "ME", "AL"))) {
    governance <- c(governance, "Barcelona Convention (UNEP/MAP)")
  }
  if (any(countries %in% c("GB", "NL", "BE", "DE", "DK", "NO", "SE", "FR",
                            "PT", "ES", "IE", "IS"))) {
    governance <- c(governance, "OSPAR Convention")
  }
  if (any(countries %in% c("NO", "RU", "CA", "US", "DK", "IS", "SE", "FI"))) {
    governance <- c(governance, "Arctic Council frameworks")
  }

  return(unique(governance))
}

#' Get Socioeconomic Elements Based on Countries (hardcoded fallback)
#'
#' Returns socioeconomic-related DAPSIWRM suggestions based on selected countries.
#' Focuses on drivers and welfare elements specific to the economic profiles
#' of selected countries. Used as fallback when the JSON-based country
#' governance database is not available.
#'
#' @param countries Character vector of country codes
#' @param category DAPSIWRM category
#' @return Character vector of socioeconomic suggestions
.get_socioeconomic_elements_hardcoded <- function(countries, category) {
  if (is.null(countries) || length(countries) == 0) return(character(0))

  suggestions <- character(0)

  # Socioeconomic drivers
  if (category == "drivers") {
    # Small island developing states or coastal-dependent economies
    coastal_dependent <- c("FJ", "MV", "BB", "BS", "JM", "TT", "MT",
                           "CY", "IS", "MG", "MZ", "BZ")
    if (any(countries %in% coastal_dependent)) {
      suggestions <- c(suggestions,
        "Tourism-dependent economy",
        "Coastal community livelihoods",
        "Small-scale fisheries dependency"
      )
    }

    # Major fishing nations
    fishing_nations <- c("NO", "IS", "ES", "JP", "CN", "ID", "PH",
                          "IN", "TH", "PE", "CL")
    if (any(countries %in% fishing_nations)) {
      suggestions <- c(suggestions,
        "Industrial fisheries demand",
        "Seafood export economy",
        "Fish processing industry"
      )
    }

    # Major shipping nations
    shipping_nations <- c("NL", "DE", "GB", "NO", "DK", "GR", "CN",
                           "JP", "SG", "US")
    if (any(countries %in% shipping_nations)) {
      suggestions <- c(suggestions,
        "Maritime transport demand",
        "Port infrastructure development"
      )
    }
  }

  # Socioeconomic welfare impacts
  if (category == "welfare") {
    coastal_dependent <- c("FJ", "MV", "BB", "BS", "JM", "TT", "MT",
                           "CY", "IS", "MG", "MZ", "BZ")
    if (any(countries %in% coastal_dependent)) {
      suggestions <- c(suggestions,
        "Tourism revenue vulnerability",
        "Coastal community displacement risk",
        "Food security from marine resources"
      )
    }
  }

  return(unique(suggestions))
}

# ============================================================================
# CONTEXT-AWARE SUGGESTIONS
# ============================================================================

#' Semantic Deduplication Helper
#'
#' Removes semantically similar suggestions to avoid showing "trawl fishing" and "trawling" together
#'
#' @param suggestions Character vector of suggestions
#' @param protected Labels that must survive (knowledge-base labels): a
#'   near-duplicate pair with one protected label keeps the protected one, and
#'   two protected labels are both kept. Without it the shorter label wins,
#'   which used to replace specific KB labels by generic hardcoded ones.
#' @return Deduplicated character vector
deduplicate_suggestions <- function(suggestions, protected = character(0)) {
  if (length(suggestions) <= 1) return(suggestions)

  # Convert to lowercase for comparison
  lower_suggestions <- tolower(suggestions)

  # Track which items to keep
  keep <- rep(TRUE, length(suggestions))

  for (i in seq_along(lower_suggestions)) {
    if (!keep[i]) next  # Already marked for removal

    current <- lower_suggestions[i]

    # Check against all subsequent items
    for (j in seq_along(lower_suggestions)) {
      if (i >= j || !keep[j]) next  # Skip self and already removed items

      other <- lower_suggestions[j]

      # Extract core words (remove common suffixes/prefixes)
      current_words <- unlist(strsplit(current, "\\s+"))
      other_words <- unlist(strsplit(other, "\\s+"))

      # Check for significant overlap
      # If one is a subset of the other, or they share key root words, mark as duplicate
      current_core <- gsub("ing$|ed$|s$", "", current_words)
      other_core <- gsub("ing$|ed$|s$", "", other_words)

      # Calculate overlap - if 80%+ of words match (after stemming), it's a duplicate
      common_words <- intersect(current_core, other_core)

      # If they share most core words, keep the shorter/simpler one
      if (length(common_words) > 0) {
        overlap_ratio <- length(common_words) / min(length(current_core), length(other_core))

        if (overlap_ratio >= 0.8) {
          i_prot <- suggestions[i] %in% protected
          j_prot <- suggestions[j] %in% protected
          if (i_prot && j_prot) next          # two curated labels: keep both
          if (i_prot != j_prot) {             # keep the curated (KB) label
            if (i_prot) {
              keep[j] <- FALSE
            } else {
              keep[i] <- FALSE
              break
            }
          # Otherwise keep the one with fewer words (simpler)
          } else if (length(current_words) <= length(other_words)) {
            keep[j] <- FALSE
          } else {
            keep[i] <- FALSE
            break  # Current item removed, move to next i
          }
        }
      }
    }
  }

  return(suggestions[keep])
}

#' Get Context-Aware Suggestions for DAPSI(W)R(M) Elements
#'
#' Returns suggestions based on regional sea and ecosystem type. The chosen
#' focus topics (`main_issue`) deliberately do not change them: the former
#' topic-triggered lists existed only for fishing, nutrients, litter, tourism
#' and climate (none for shipping, energy, mining) and were mostly negative,
#' which biased the suggestions (user feedback 2026-10-13). When the JSON knowledge database provides 3+
#' suggestions for a category, generic universal suggestions are suppressed
#' to avoid polluting context-specific results.
#'
#' @param category DAPSIWRM category (drivers, activities, pressures, states, impacts, welfare, responses)
#' @param regional_sea Selected regional sea key
#' @param ecosystem_type Selected ecosystem type
#' @param main_issue Focus topics chosen in step 3 (kept for callers; unused)
#' @param return_sources If TRUE, return a list with suggestions and source attribution (for UI badges)
#' @return Character vector of context-aware suggestions, or list with $suggestions and $sources if return_sources=TRUE
get_context_suggestions <- function(category, regional_sea, ecosystem_type, main_issue, countries = NULL, return_sources = FALSE) {
  suggestions <- list()

  # ---- Priority 1: JSON Knowledge Database (context-specific, ecologically validated) ----
  if (exists("ses_knowledge_db_available", mode = "function") && ses_knowledge_db_available()) {
    kb_elements <- tryCatch(
      get_context_elements(regional_sea, ecosystem_type, category, min_relevance = 0.5),
      error = function(e) character(0)
    )
    if (length(kb_elements) > 0) {
      suggestions$knowledge_db <- kb_elements
      debug_log(sprintf("SES KB provided %d %s suggestions for %s/%s",
                        length(kb_elements), category,
                        regional_sea %||% "NULL", ecosystem_type %||% "NULL"),
                "AI ISA KB")
    }
  }

  # Determine if KB has sufficient context-specific suggestions (3+ items).
  # When KB provides enough items, universal (generic) suggestions are suppressed

  # to prevent context pollution (e.g., "Coastal protection" showing up for a
  # lagoon focused on eutrophication).
  kb_sufficient <- length(suggestions$knowledge_db) >= 3

  # ---- Priority 2: Hardcoded suggestions (generic and region-specific fallbacks) ----

  if (category == "drivers") {
    # Universal drivers - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Food security", "Economic development", "Recreation and tourism",
                                 "Energy needs", "Coastal protection", "Cultural heritage",
                                 "Employment", "Trade and commerce")
    }
    # No region-specific drivers: the former lists ("Maritime transport",
    # "Beach tourism", "Shipping routes", ...) were activities/sectors, so
    # every session showed activities as Drivers (user feedback 2026-10-13).
  }

  else if (category == "activities") {
    # Universal activities - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Commercial fishing", "Aquaculture", "Shipping", "Coastal development",
                                 "Environmental monitoring")
    }

    # Region-specific
    if (!is.null(regional_sea)) {
      if (regional_sea %in% c("baltic", "north_sea", "irish_sea")) {
        suggestions$regional <- c("Wind farm development", "Dredging", "Oil and gas extraction",
                                  "Trawl fishing", "Marine aggregate extraction")
      } else if (regional_sea %in% c("mediterranean", "caribbean")) {
        # ("Marine debris disposal" removed: litter is a pressure, not an activity)
        suggestions$regional <- c("Beach recreation", "Yacht tourism", "Scuba diving",
                                  "Coastal construction")
      } else if (regional_sea == "arctic") {
        suggestions$regional <- c("Ice navigation", "Arctic oil exploration", "Cold-water fishing")
      } else if (regional_sea %in% c("pacific", "indian")) {
        suggestions$regional <- c("Reef fishing", "Mangrove clearing", "Port expansion")
      }
    }
  }

  else if (category == "pressures") {
    # Universal pressures - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Nutrient enrichment", "Overfishing", "Physical disturbance",
                                 "Marine litter", "Underwater noise", "Habitat loss")
    }

    # Region-specific
    if (!is.null(regional_sea)) {
      if (regional_sea == "baltic") {
        suggestions$regional <- c("Hypoxia", "Algal blooms", "Sediment resuspension")
      } else if (regional_sea == "north_sea") {
        suggestions$regional <- c("Seabed abrasion", "Hydrocarbon contamination", "Noise from shipping")
      } else if (regional_sea %in% c("mediterranean", "caribbean")) {
        suggestions$regional <- c("Coastal erosion", "Beach trampling", "Anchor damage")
      } else if (regional_sea == "arctic") {
        suggestions$regional <- c("Oil spill risk", "Ice habitat loss", "Black carbon deposition")
      }
    }
  }

  else if (category == "states") {
    # Universal state changes - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Water quality decline", "Biodiversity loss", "Habitat degradation",
                                 "Species population changes", "Oxygen depletion")
    }

    # Region-specific
    if (!is.null(regional_sea)) {
      if (regional_sea == "baltic") {
        suggestions$regional <- c("Benthic fauna decline", "Cod stock collapse", "Seagrass decline")
      } else if (regional_sea %in% c("mediterranean", "caribbean", "pacific", "indian")) {
        suggestions$regional <- c("Coral bleaching", "Seagrass loss", "Reef degradation")
      } else if (regional_sea == "arctic") {
        suggestions$regional <- c("Sea ice reduction", "Permafrost thaw", "Species range shifts")
      } else if (regional_sea == "north_sea") {
        suggestions$regional <- c("Benthic community changes", "Fish stock declines", "Phytoplankton shifts")
      }
    }

    # Ecosystem-specific
    if (!is.null(ecosystem_type)) {
      if (grepl("coral|reef", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Coral cover decline", "Fish diversity loss", "Reef structural complexity loss")
      } else if (grepl("mangrove", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Mangrove forest area loss", "Carbon storage reduction", "Nursery habitat loss")
      } else if (grepl("estuar", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Salinity changes", "Turbidity increase", "Migratory fish decline")
      }
    }
  }

  else if (category == "impacts") {
    # Universal impacts - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Loss of ecosystem services", "Reduced fish catches", "Coastal vulnerability",
                                 "Economic losses", "Health risks", "Cultural loss")
    }

    # Ecosystem-specific
    if (!is.null(ecosystem_type)) {
      if (grepl("coral|reef", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Tourism revenue loss", "Coastal protection loss", "Fishery collapse")
      } else if (grepl("mangrove", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Storm protection loss", "Nursery habitat loss", "Carbon release")
      } else if (grepl("seagrass", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Nursery function loss", "Water clarity decline", "Carbon storage loss")
      } else if (grepl("estuar", ecosystem_type, ignore.case = TRUE)) {
        suggestions$ecosystem <- c("Fishery productivity loss", "Water quality impacts", "Flood risk increase")
      }
    }
  }

  else if (category == "welfare") {
    # Universal welfare impacts - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Income loss", "Food insecurity", "Health impacts", "Cultural identity loss",
                                 "Displacement", "Recreational opportunities loss")
    }
  }

  else if (category == "responses") {
    # Universal responses - only add as padding when KB has fewer than 3 items
    if (!kb_sufficient) {
      suggestions$universal <- c("Marine Protected Areas", "Fishing regulations", "Pollution controls",
                                 "Ecosystem restoration", "Stakeholder engagement")
    }

    # Region-specific
    if (!is.null(regional_sea)) {
      if (regional_sea == "baltic") {
        suggestions$regional <- c("Nutrient reduction targets", "Oxygen restoration", "Fish stock recovery plans")
      } else if (regional_sea %in% c("mediterranean", "caribbean")) {
        suggestions$regional <- c("Coral restoration", "Beach management plans", "Marine debris reduction")
      } else if (regional_sea == "north_sea") {
        suggestions$regional <- c("Trawling restrictions", "Wind farm planning", "Oil spill preparedness")
      } else if (regional_sea == "arctic") {
        suggestions$regional <- c("Shipping regulations", "Ice habitat protection", "Indigenous co-management")
      }
    }
  }

  # NOTE: Habitat-specific suggestions are now provided by the JSON knowledge database
  # (data/ses_knowledge_db.json) which is the single source of truth for context-specific
  # elements. The old get_habitat_specific_suggestions() function is kept as fallback only
  # for habitat types not yet in the JSON database.
  if (length(suggestions$knowledge_db) == 0) {
    habitat_suggestions <- get_habitat_specific_suggestions(category, regional_sea, ecosystem_type)
    if (length(habitat_suggestions) > 0) {
      suggestions$habitat <- habitat_suggestions
    }
  }

  # ---- Country-based governance and socioeconomic suggestions ----
  # Uses JSON-based country governance database (functions/country_governance_loader.R)
  # when available, falling back to hardcoded lookup tables defined above.
  if (!is.null(countries) && length(countries) > 0) {
    use_json_gov <- exists("country_governance_db_available", mode = "function") &&
                    tryCatch(country_governance_db_available(), error = function(e) FALSE)

    # Governance elements (responses, drivers)
    gov_elements <- tryCatch({
      if (use_json_gov) {
        get_governance_elements(countries, category)
      } else {
        .get_governance_elements_hardcoded(countries, category)
      }
    }, error = function(e) {
      debug_log(sprintf("Governance lookup error: %s — using hardcoded fallback", e$message), "AI ISA KB")
      tryCatch(.get_governance_elements_hardcoded(countries, category), error = function(e2) character(0))
    })
    if (length(gov_elements) > 0) {
      suggestions$governance <- gov_elements
      debug_log(sprintf("%s governance: %d %s suggestions for countries: %s",
                        if (use_json_gov) "JSON DB" else "Hardcoded",
                        length(gov_elements), category,
                        paste(countries, collapse = ", ")), "AI ISA KB")
    }

    # Socioeconomic elements (drivers, welfare)
    se_elements <- tryCatch({
      if (use_json_gov) {
        get_socioeconomic_elements(countries, category)
      } else {
        .get_socioeconomic_elements_hardcoded(countries, category)
      }
    }, error = function(e) {
      debug_log(sprintf("Socioeconomic lookup error: %s — using hardcoded fallback", e$message), "AI ISA KB")
      tryCatch(.get_socioeconomic_elements_hardcoded(countries, category), error = function(e2) character(0))
    })
    if (length(se_elements) > 0) {
      suggestions$socioeconomic <- se_elements
      debug_log(sprintf("%s socioeconomic: %d %s suggestions for countries: %s",
                        if (use_json_gov) "JSON DB" else "Hardcoded",
                        length(se_elements), category,
                        paste(countries, collapse = ", ")), "AI ISA KB")
    }
  }

  # Combine all suggestions and remove exact duplicates
  # Knowledge DB suggestions come first (highest quality, context-specific)
  all_suggestions <- unique(c(suggestions$knowledge_db, suggestions$universal,
                              suggestions$regional, suggestions$ecosystem,
                              suggestions$habitat, suggestions$issue,
                              suggestions$governance, suggestions$socioeconomic))

  # Apply semantic deduplication to remove similar terms
  deduplicated <- deduplicate_suggestions(all_suggestions,
                                          protected = suggestions$knowledge_db %||% character(0))

  # Build source attribution map for UI badges (P3)
  if (return_sources) {
    source_map <- character(length(deduplicated))
    names(source_map) <- deduplicated
    kb_items <- suggestions$knowledge_db %||% character(0)
    for (s in deduplicated) {
      if (s %in% kb_items) {
        source_map[s] <- "knowledge_db"
      } else if (s %in% (suggestions$governance %||% character(0))) {
        source_map[s] <- "governance"
      } else if (s %in% (suggestions$socioeconomic %||% character(0))) {
        source_map[s] <- "socioeconomic"
      } else if (s %in% (suggestions$regional %||% character(0))) {
        source_map[s] <- "regional"
      } else if (s %in% (suggestions$issue %||% character(0))) {
        source_map[s] <- "issue"
      } else if (s %in% (suggestions$ecosystem %||% character(0))) {
        source_map[s] <- "ecosystem"
      } else if (s %in% (suggestions$habitat %||% character(0))) {
        source_map[s] <- "habitat"
      } else {
        source_map[s] <- "generic"
      }
    }
    return(list(suggestions = deduplicated, sources = source_map))
  }

  return(deduplicated)
}

# ============================================================================
# REGIONAL SEA × HABITAT KNOWLEDGE BASE
# ============================================================================
#
# Comprehensive DAPSIWRM element suggestions for each combination of
# regional sea and ecosystem/habitat type. Based on published marine
# SES case studies and the MSFD, IPBES, and DAPSIWRM literature.

#' Get habitat-specific DAPSIWRM suggestions
#'
#' Returns element suggestions tailored to the combination of regional sea
#' and ecosystem/habitat type. Provides much more specific suggestions than
#' the generic regional or ecosystem branches.
#'
#' @param category DAPSIWRM category
#' @param regional_sea Regional sea key
#' @param ecosystem_type Ecosystem/habitat type string
#' @return Character vector of suggestions (may be empty)
get_habitat_specific_suggestions <- function(category, regional_sea, ecosystem_type) {
  if (is.null(regional_sea) || is.null(ecosystem_type)) return(character())

  eco_lower <- tolower(ecosystem_type)

  # Build a lookup key from habitat type
  habitat_key <- if (grepl("coral|reef", eco_lower)) "coral_reef"
    else if (grepl("mangrove", eco_lower)) "mangrove"
    else if (grepl("seagrass|sea grass", eco_lower)) "seagrass"
    else if (grepl("estuar", eco_lower)) "estuary"
    else if (grepl("lagoon", eco_lower)) "lagoon"
    else if (grepl("tidal|mudflat|mud flat", eco_lower)) "tidal_flat"
    else if (grepl("rocky|rock shore", eco_lower)) "rocky_shore"
    else if (grepl("sandy|sand beach", eco_lower)) "sandy_beach"
    else if (grepl("kelp", eco_lower)) "kelp_forest"
    else if (grepl("fjord", eco_lower)) "fjord"
    else if (grepl("delta", eco_lower)) "delta"
    else if (grepl("archipelago", eco_lower)) "archipelago"
    else if (grepl("offshore|open ocean|open water|deep sea|continental shelf", eco_lower)) "offshore"
    else if (grepl("ice|arctic", eco_lower)) "sea_ice"
    else if (grepl("upwelling", eco_lower)) "upwelling"
    else if (grepl("coast", eco_lower)) "open_coast"
    else "generic"

  # Sea groupings for regional matching
  northern_seas <- c("baltic", "north_sea", "irish_sea")
  warm_seas <- c("mediterranean", "caribbean", "pacific", "indian")
  atlantic_seas <- c("atlantic", "east_atlantic")

  sea_group <- if (regional_sea %in% northern_seas) "northern"
    else if (regional_sea %in% warm_seas) "warm"
    else if (regional_sea %in% atlantic_seas) "atlantic"
    else if (regional_sea == "arctic") "arctic"
    else if (regional_sea == "black_sea") "black_sea"
    else "generic"

  # ---- DRIVERS ----
  if (category == "drivers") {
    return(switch(habitat_key,
      coral_reef = c("Reef tourism demand", "Coastal protection need", "Ornamental fish trade",
                     "Reef fisheries dependence", "Climate vulnerability"),
      mangrove = c("Coastal protection need", "Shrimp aquaculture demand", "Timber demand",
                   "Carbon sequestration value", "Nursery habitat dependence"),
      seagrass = c("Water quality requirements", "Carbon storage value", "Nursery habitat need",
                   "Recreational boating demand", "Sediment stabilization need"),
      estuary = switch(sea_group,
        northern = c("Port and harbor expansion", "Flood risk management", "Industrial water demand",
                     "Dredging requirements", "Recreational fishing demand"),
        warm = c("Aquaculture expansion", "Urban water demand", "Flood protection",
                 "Tourism access", "Agricultural runoff"),
        c("Urban expansion", "Flood management", "Agricultural demand", "Port development")),
      lagoon = switch(sea_group,
        northern = c("Local fishery demand", "Nature tourism demand", "Flood protection need",
                     "Agricultural catchment use", "Cultural heritage preservation"),
        warm = c("Aquaculture demand", "Tourism development", "Water abstraction",
                 "Salt production", "Flood buffer need"),
        c("Fishery demand", "Tourism development", "Flood protection")),
      tidal_flat = c("Coastal development pressure", "Bait collection demand",
                     "Bird watching tourism"),
      rocky_shore = c("Recreational harvesting", "Scientific research interest",
                      "Coastal access demand", "Kelp harvesting"),
      sandy_beach = c("Beach tourism demand", "Coastal protection need",
                      "Sand mining demand", "Recreational fishing"),
      fjord = c("Aquaculture expansion", "Tourism demand", "Hydropower influence",
                "Shipping access", "Freshwater runoff management"),
      offshore = switch(sea_group,
        northern = c("Wind energy demand", "Oil and gas extraction",
                     "Sand and gravel extraction", "Cable and pipeline corridors"),
        warm = c("Deep-sea mining interest", "Shipping lanes", "Tuna fisheries demand",
                 "Oil exploration", "Telecommunications cables"),
        arctic = c("Arctic shipping routes", "Hydrocarbon exploration",
                   "Strategic mineral extraction"),
        c("Energy demand", "Shipping", "Deep-sea resource extraction")),
      sea_ice = c("Arctic shipping route opening", "Resource exploration demand",
                  "Indigenous subsistence needs"),
      delta = c("Agricultural expansion", "Urban development", "Flood protection",
                "Sediment management", "Freshwater demand"),
      archipelago = c("Island tourism demand", "Ferry transport need",
                      "Aquaculture expansion", "Wind energy potential"),
      character()
    ))
  }

  # ---- ACTIVITIES ----
  if (category == "activities") {
    return(switch(habitat_key,
      coral_reef = c("Reef diving and snorkeling", "Reef fishing", "Anchor damage from boats",
                     "Coral harvesting", "Glass-bottom boat tours", "Reef monitoring"),
      mangrove = c("Mangrove clearance for aquaculture", "Charcoal production",
                   "Timber harvesting", "Coastal construction", "Ecotourism"),
      seagrass = c("Bottom trawling over seagrass", "Boat anchoring in meadows",
                   "Dredging near seagrass", "Nutrient discharge into seagrass areas",
                   "Seagrass restoration planting", "Water quality monitoring"),
      estuary = switch(sea_group,
        northern = c("Port dredging", "Industrial discharge", "Commercial trawling",
                     "Recreational boating", "Coastal flood defense construction",
                     "Mussel and oyster harvesting", "Shellfish water quality monitoring"),
        warm = c("Shellfish aquaculture", "Urban wastewater discharge",
                 "Tourist boat traffic", "Artisanal fishing", "Salt harvesting"),
        c("Dredging", "Industrial discharge", "Fishing", "Aquaculture")),
      lagoon = switch(sea_group,
        northern = c("Small-scale net fishing", "Reed harvesting", "Recreational angling",
                     "Agricultural drainage management", "Nature tourism"),
        warm = c("Shellfish farming", "Fish pond aquaculture", "Salt harvesting",
                 "Tourism infrastructure", "Wastewater inflow"),
        c("Small-scale fishing", "Reed harvesting", "Tourism", "Aquaculture")),
      tidal_flat = c("Bait digging", "Cockle and clam harvesting", "Land reclamation",
                     "Sea defense construction", "Recreational walking"),
      rocky_shore = c("Intertidal harvesting", "Rock pooling tourism",
                      "Seaweed collection", "Coastal path maintenance"),
      sandy_beach = c("Beach nourishment", "Beach tourism activities", "Sand extraction",
                      "Dune stabilization works", "Coastal construction"),
      fjord = switch(sea_group,
        northern = c("Salmon aquaculture", "Tourism cruises", "Hydropower discharge",
                     "Recreational fishing", "Industrial activities"),
        arctic = c("Arctic aquaculture", "Cruise tourism", "Mining discharge",
                   "Small-scale fishing", "Fjord monitoring"),
        c("Aquaculture", "Tourism", "Fishing")),
      offshore = switch(sea_group,
        northern = c("Offshore wind farm construction", "Bottom trawling", "Oil platform operations",
                     "Submarine cable laying", "Aggregate dredging", "Shipping traffic"),
        warm = c("Purse seine fishing", "Longline fishing", "Oil exploration",
                 "Deep-water trawling", "Shipping traffic"),
        arctic = c("Ice-class shipping", "Seismic surveys", "Exploratory drilling",
                   "Long-range fishing", "Scientific exploration"),
        c("Commercial fishing", "Shipping", "Energy extraction")),
      sea_ice = c("Icebreaker shipping", "Under-ice research", "Polar tourism",
                  "Seal hunting", "Indigenous marine harvesting", "Climate monitoring"),
      delta = c("Upstream dam operations", "Agricultural irrigation", "Dredging for navigation",
                "Urban expansion on deltaic land", "Aquaculture in delta channels"),
      character()
    ))
  }

  # ---- PRESSURES ----
  if (category == "pressures") {
    return(switch(habitat_key,
      coral_reef = c("Ocean warming and bleaching", "Ocean acidification", "Sedimentation from runoff",
                     "Physical damage from anchoring", "Overharvesting of reef fish",
                     "Nutrient enrichment from sewage", "Coral disease spread"),
      mangrove = c("Habitat conversion for aquaculture", "Altered freshwater flow",
                   "Oil pollution", "Sedimentation changes", "Sea level rise inundation"),
      seagrass = c("Light reduction from turbidity", "Nutrient loading causing algal overgrowth",
                   "Physical damage from mooring", "Propeller scarring",
                   "Sediment disturbance from dredging"),
      estuary = switch(sea_group,
        northern = c("Nutrient enrichment from agriculture", "Industrial chemical contaminants",
                     "Habitat loss from port expansion", "Altered salinity from water management",
                     "Noise from shipping and construction", "Microplastic accumulation"),
        warm = c("Freshwater diversion", "Urban sewage (nutrients, pathogens)", "Pesticides in runoff",
                 "Thermal pollution", "Invasive species introduction"),
        black_sea = c("Eutrophication from Danube inputs", "Hydrogen sulfide zones",
                      "Invasive jellyfish (Mnemiopsis)", "Overfishing of anchovy and sprat"),
        c("Nutrient pollution", "Habitat loss", "Altered hydrology")),
      lagoon = c("Eutrophication", "Reduced water exchange", "Salinity fluctuations",
                 "Sedimentation and infilling", "Invasive species"),
      tidal_flat = c("Coastal squeeze from sea level rise", "Land claim and reclamation",
                     "Disruption of sediment transport", "Disturbance to wading birds"),
      rocky_shore = c("Oil spill exposure", "Microplastic accumulation",
                      "Invasive species colonization", "Thermal stress from warming",
                      "Ocean acidification weakening shells"),
      sandy_beach = c("Coastal erosion", "Sand mining depletion", "Light pollution affecting nesting",
                      "Litter and microplastics", "Disturbance to nesting species"),
      offshore = switch(sea_group,
        northern = c("Bottom trawling disturbance", "Underwater noise from construction",
                     "Electromagnetic fields from cables", "Sediment plumes from dredging",
                     "Chemical contamination from oil platforms"),
        warm = c("Overfishing of pelagic stocks", "Marine debris accumulation",
                 "Ship-strike risk to cetaceans", "Deep-sea habitat disturbance"),
        arctic = c("Oil spill risk in ice", "Noise from seismic surveys",
                   "Black carbon deposition", "Arctic warming amplification"),
        c("Overfishing", "Pollution", "Habitat disturbance")),
      sea_ice = c("Ice extent reduction", "Earlier ice breakup", "Ocean freshening",
                  "Habitat loss for ice-dependent species", "Increased UV exposure"),
      delta = c("Reduced sediment supply from dams", "Saltwater intrusion",
                "Land subsidence", "Flooding regime changes", "Pollutant concentration"),
      character()
    ))
  }

  # ---- STATES (Marine Processes & Functioning) ----
  if (category == "states") {
    return(switch(habitat_key,
      coral_reef = c("Coral cover and health", "Reef fish assemblage", "Reef structural complexity",
                     "Algal cover balance", "Water clarity", "Calcification rates"),
      mangrove = c("Mangrove forest extent", "Root system integrity", "Sediment trapping capacity",
                   "Nursery habitat quality", "Carbon burial rates"),
      seagrass = c("Seagrass bed extent", "Shoot density", "Epiphyte load",
                   "Sediment stability", "Associated fauna diversity"),
      estuary = c("Water column stratification", "Dissolved oxygen levels", "Nutrient cycling efficiency",
                  "Benthic community health", "Fish migration patterns", "Salinity gradient"),
      lagoon = c("Water exchange rate", "Trophic status", "Sediment quality",
                 "Phytoplankton community", "Macroalgal coverage"),
      tidal_flat = c("Intertidal area extent", "Benthic invertebrate abundance",
                     "Sediment grain size distribution", "Wading bird populations"),
      rocky_shore = c("Intertidal community zonation", "Algal canopy cover",
                      "Limpet and barnacle populations", "Rock pool biodiversity"),
      sandy_beach = c("Beach profile dynamics", "Infauna community", "Dune vegetation cover",
                      "Turtle nesting success", "Shorebird foraging habitat"),
      offshore = c("Pelagic food web structure", "Demersal community composition",
                   "Primary productivity", "Water column mixing", "Seabed integrity"),
      sea_ice = c("Sea ice extent and thickness", "Under-ice algal production",
                  "Ice-dependent species populations", "Polar food web dynamics"),
      delta = c("Sediment budget balance", "Wetland extent", "Freshwater-saltwater interface",
                "Delta morphodynamics", "Floodplain connectivity"),
      fjord = c("Water column stratification", "Deep water renewal frequency",
                "Benthic oxygen conditions", "Plankton community composition"),
      character()
    ))
  }

  # ---- IMPACTS (Ecosystem Services) ----
  if (category == "impacts") {
    return(switch(habitat_key,
      coral_reef = c("Reef fishery productivity", "Coastal wave protection", "Tourism attraction value",
                     "Biodiversity reservoir", "Pharmaceutical potential",
                     "Cultural and spiritual significance"),
      mangrove = c("Storm surge protection", "Nursery function for fisheries",
                   "Blue carbon storage", "Water filtration", "Timber provision",
                   "Erosion prevention"),
      seagrass = c("Carbon sequestration", "Nursery grounds for commercial species",
                   "Water clarity maintenance", "Sediment stabilization",
                   "Nutrient cycling support"),
      estuary = c("Fish and shellfish nursery", "Nutrient processing and removal",
                  "Flood attenuation", "Navigation channel provision",
                  "Recreational and aesthetic value", "Carbon burial"),
      lagoon = switch(sea_group,
        northern = c("Freshwater fish provisioning", "Water purification by reed beds",
                     "Waterbird habitat provision", "Flood buffering", "Carbon storage"),
        warm = c("Aquaculture production capacity", "Water purification",
                 "Bird habitat provision", "Flood buffering", "Salt production"),
        c("Fish provisioning", "Water purification", "Bird habitat", "Flood buffering")),
      offshore = c("Fish stock provision", "Climate regulation", "Nutrient cycling",
                   "Waste assimilation", "Shipping route provision"),
      sea_ice = c("Climate regulation (albedo)", "Habitat for ice-dependent species",
                  "Indigenous food provision", "Freshwater storage"),
      sandy_beach = c("Coastal protection", "Tourism and recreation value",
                      "Nesting habitat for turtles and birds", "Sand resource provision"),
      rocky_shore = c("Food provision (shellfish, seaweed)", "Education and research value",
                      "Recreation (rock pooling)", "Coastal protection"),
      character()
    ))
  }

  # ---- WELFARE (Goods & Benefits) ----
  if (category == "welfare") {
    return(switch(habitat_key,
      coral_reef = c("Reef tourism revenue", "Reef fishery livelihoods", "Coastal property protection",
                     "Cultural heritage value", "Dive industry employment"),
      mangrove = c("Coastal community safety", "Fishery catch value", "Carbon credit revenue",
                   "Traditional resource access", "Ecotourism income"),
      seagrass = c("Commercial fish catch value", "Carbon offset potential",
                   "Recreational value", "Shoreline protection savings"),
      estuary = c("Port and shipping revenue", "Fishery income", "Flood damage avoidance",
                  "Waterfront property values", "Recreational spending"),
      offshore = c("Commercial fish catch value", "Energy production revenue",
                   "Shipping trade value", "Employment in marine sectors"),
      sea_ice = c("Indigenous food security", "Arctic shipping savings",
                  "Resource extraction revenue", "Climate stability contribution"),
      character()
    ))
  }

  # ---- RESPONSES ----
  if (category == "responses") {
    return(switch(habitat_key,
      coral_reef = c("Marine Protected Area designation", "Coral reef restoration",
                     "Mooring buoy installation", "Reef-safe sunscreen regulations",
                     "Coral nursery programs", "Tourism carrying capacity limits"),
      mangrove = c("Mangrove replanting programs", "Aquaculture zoning regulations",
                   "Community mangrove management", "Blue carbon REDD+ projects",
                   "Mangrove protected area designation"),
      seagrass = c("Seagrass protection zones", "Mooring management areas",
                   "Nutrient reduction programs", "Seagrass transplanting initiatives"),
      estuary = switch(sea_group,
        northern = c("Nutrient Action Plans (HELCOM/OSPAR)", "Fish passage restoration",
                     "Industrial discharge permits", "Managed realignment"),
        warm = c("Wastewater treatment upgrades", "River basin management plans",
                 "Estuary habitat restoration", "Fishery co-management"),
        c("Water Framework Directive measures", "Habitat restoration", "Pollution control")),
      lagoon = c("Water exchange improvement structures", "Nutrient input reduction",
                 "Lagoon habitat restoration", "Sustainable aquaculture certification"),
      offshore = switch(sea_group,
        northern = c("Fishery quota management", "Marine spatial planning", "Offshore wind farm EIA",
                     "Ship traffic separation schemes", "Decommissioning standards"),
        warm = c("Regional fisheries management", "High seas protection agreements",
                 "Vessel monitoring systems", "Bycatch reduction devices"),
        c("Fishery management", "Marine spatial planning", "Pollution prevention")),
      sea_ice = c("Arctic environmental protection", "Polar Code shipping regulations",
                  "Ice-dependent species protection", "Climate adaptation planning",
                  "Indigenous co-management agreements"),
      sandy_beach = c("Beach nourishment programs", "Dune restoration",
                      "Light pollution regulations for nesting", "Litter cleanup initiatives"),
      character()
    ))
  }

  character()  # Default: no habitat-specific suggestions
}
