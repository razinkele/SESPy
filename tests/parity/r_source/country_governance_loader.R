# functions/country_governance_loader.R
# Country Governance and Socio-Economic Database Loader
# Purpose: Loads the JSON-based country governance database and provides
#   lookup functions for governance frameworks, regional conventions, and
#   income-stratified socioeconomic DAPSI(W)R(M) elements per country.
#
# Author: MarineSABRES SES Toolbox
# Date: 2026-03-15
# Dependencies: jsonlite (already loaded in global.R)

# ==============================================================================
# MODULE-LEVEL STATE
# ==============================================================================

# Private environment to hold loaded database (same pattern as ses_knowledge_db_loader.R)
.country_gov_env <- new.env(parent = emptyenv())
.country_gov_env$db <- NULL
.country_gov_env$loaded <- FALSE

# ==============================================================================
# DATABASE LOADING
# ==============================================================================

#' Load the Country Governance Database from JSON
#'
#' Reads and parses the JSON country governance database file. Called once at
#' startup. Subsequent calls return the cached database unless force_reload is TRUE.
#'
#' @param db_path Path to the JSON database file (default: data/country_governance_db.json)
#' @param force_reload If TRUE, reload even if already cached
#' @return The parsed database list, invisibly
#' @export
load_country_governance_db <- function(db_path = NULL, force_reload = FALSE) {
  if (.country_gov_env$loaded && !force_reload) {
    return(invisible(.country_gov_env$db))
  }

  # Determine path
  if (is.null(db_path)) {
    if (exists("get_project_file", mode = "function")) {
      db_path <- get_project_file("data", "country_governance_db.json")
    } else {
      db_path <- file.path("data", "country_governance_db.json")
    }
  }

  if (!file.exists(db_path)) {
    warning(sprintf("[Country Gov] Governance database not found at: %s", db_path))
    .country_gov_env$db <- NULL
    .country_gov_env$loaded <- FALSE
    return(invisible(NULL))
  }

  tryCatch({
    raw <- jsonlite::fromJSON(db_path, simplifyDataFrame = FALSE)
    .country_gov_env$db <- raw
    .country_gov_env$loaded <- TRUE

    n_countries <- length(raw$countries %||% list())
    n_seas <- length(raw$countries_by_sea %||% list())
    if (exists("debug_log", mode = "function")) {
      debug_log(sprintf("Country Governance DB loaded: v%s, %d countries, %d regional seas",
                        raw$version %||% "unknown", n_countries, n_seas), "COUNTRY GOV")
    }

    message(sprintf("[Country Gov] Loaded governance database v%s with %d countries across %d regional seas",
                    raw$version %||% "unknown", n_countries, n_seas))

    invisible(raw)
  }, error = function(e) {
    warning(sprintf("[Country Gov] Failed to load governance database: %s", e$message))
    .country_gov_env$db <- NULL
    .country_gov_env$loaded <- FALSE
    invisible(NULL)
  })
}

# ==============================================================================
# PUBLIC API: AVAILABILITY CHECK
# ==============================================================================

#' Check if Country Governance Database is Available
#'
#' @return TRUE if the database is loaded and has country data
#' @export
country_governance_db_available <- function() {
  return(.country_gov_env$loaded && !is.null(.country_gov_env$db) &&
         length(.country_gov_env$db$countries %||% list()) > 0)
}

# ==============================================================================
# PUBLIC API: COUNTRY LOOKUP
# ==============================================================================

#' Get Countries for a Regional Sea
#'
#' Returns the list of country records for a given regional sea.
#'
#' @param regional_sea Regional sea key (e.g., "baltic", "mediterranean", "north_sea")
#' @return List of country records, each with code, name_en, eu_member, income_level,
#'   governance_group, and regional_conventions. Returns empty list if sea not found.
#' @export
get_countries_for_sea <- function(regional_sea) {
  if (is.null(regional_sea) || length(regional_sea) != 1 || is.na(regional_sea)) return(list())
  if (!.country_gov_env$loaded) load_country_governance_db()
  db <- .country_gov_env$db
  if (is.null(db)) return(list())

  sea_key <- tolower(trimws(regional_sea))
  country_codes <- db$countries_by_sea[[sea_key]]
  if (is.null(country_codes) || length(country_codes) == 0) return(list())

  # Resolve codes to full country records
  result <- list()
  for (code in country_codes) {
    record <- db$countries[[code]]
    if (!is.null(record)) {
      result[[code]] <- record
    }
  }

  if (exists("debug_log", mode = "function")) {
    debug_log(sprintf("Country Gov: %d countries for sea '%s'",
                      length(result), sea_key), "COUNTRY GOV")
  }

  return(result)
}

# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

#' Resolve Country Codes to Records
#' @keywords internal
.resolve_countries <- function(country_codes) {
  db <- .country_gov_env$db
  if (is.null(db) || is.null(db$countries)) return(list())

  records <- list()
  for (code in country_codes) {
    uc <- toupper(trimws(code))
    rec <- db$countries[[uc]]
    if (!is.null(rec)) records[[uc]] <- rec
  }
  return(records)
}

#' Map DAPSI(W)R(M) category name to JSON field names
#'
#' The JSON stores elements under "drivers", "responses", "welfare".
#' This maps user-facing category names to those keys.
#' @keywords internal
.map_category <- function(category) {
  cat_lower <- tolower(trimws(category))
  mapping <- c(
    "d" = "drivers", "drivers" = "drivers", "driver" = "drivers",
    "a" = "drivers",  # activities not separately stored; drivers can inform
    "r" = "responses", "responses" = "responses", "response" = "responses",
    "m" = "responses", "measures" = "responses",
    "hw" = "welfare", "welfare" = "welfare", "human_wellbeing" = "welfare",
    "human wellbeing" = "welfare", "gb" = "welfare",
    "goods_benefits" = "welfare", "goods & benefits" = "welfare"
  )
  result <- mapping[[cat_lower]]
  if (is.null(result)) return(NULL)
  return(result)
}

# ==============================================================================
# PUBLIC API: GOVERNANCE ELEMENTS
# ==============================================================================

#' Get Governance Elements for Selected Countries
#'
#' Returns governance-specific DAPSI(W)R(M) elements based on the governance
#' groups and regional conventions of the selected countries.
#'
#' @param country_codes Character vector of ISO 3166-1 alpha-2 country codes
#' @param category DAPSI(W)R(M) category: "drivers", "responses", "welfare", or
#'   single-letter codes "D", "R", "HW", "M", "GB"
#' @return Character vector of governance element suggestions (deduplicated)
#' @export
get_governance_elements <- function(country_codes, category) {
  if (!.country_gov_env$loaded) load_country_governance_db()
  db <- .country_gov_env$db
  if (is.null(db)) return(character(0))
  if (is.null(country_codes) || length(country_codes) == 0) return(character(0))

  cat_key <- .map_category(category)
  if (is.null(cat_key)) return(character(0))

  records <- .resolve_countries(country_codes)
  if (length(records) == 0) return(character(0))

  elements <- character(0)

  # Collect unique governance groups
  gov_groups <- unique(vapply(records, function(r) r$governance_group %||% "", character(1)))
  gov_groups <- gov_groups[nchar(gov_groups) > 0]

  # Add elements from each governance group
  for (grp in gov_groups) {
    grp_data <- db$governance_elements[[grp]]
    if (!is.null(grp_data) && !is.null(grp_data[[cat_key]])) {
      elements <- c(elements, unlist(grp_data[[cat_key]]))
    }
  }

  # Collect unique regional conventions
  all_conventions <- unique(unlist(lapply(records, function(r) {
    r$regional_conventions %||% character(0)
  })))

  # Add convention-specific responses
  if (cat_key == "responses" && length(all_conventions) > 0) {
    for (conv in all_conventions) {
      conv_data <- db$regional_conventions[[conv]]
      if (!is.null(conv_data) && !is.null(conv_data$responses)) {
        elements <- c(elements, unlist(conv_data$responses))
      }
    }
  }

  result <- unique(elements)

  if (exists("debug_log", mode = "function")) {
    debug_log(sprintf("Country Gov: %d governance %s elements for %d countries (%s)",
                      length(result), cat_key, length(records),
                      paste(names(records), collapse = ", ")), "COUNTRY GOV")
  }

  return(result)
}

# ==============================================================================
# PUBLIC API: SOCIOECONOMIC ELEMENTS
# ==============================================================================

#' Get Socioeconomic Elements for Selected Countries
#'
#' Returns income-level-stratified socioeconomic DAPSI(W)R(M) elements based on
#' the income classification of the selected countries.
#'
#' @param country_codes Character vector of ISO 3166-1 alpha-2 country codes
#' @param category DAPSI(W)R(M) category: "drivers", "welfare", or single-letter
#'   codes "D", "HW", "GB"
#' @return Character vector of socioeconomic element suggestions (deduplicated)
#' @export
get_socioeconomic_elements <- function(country_codes, category) {
  if (!.country_gov_env$loaded) load_country_governance_db()
  db <- .country_gov_env$db
  if (is.null(db)) return(character(0))
  if (is.null(country_codes) || length(country_codes) == 0) return(character(0))

  cat_key <- .map_category(category)
  if (is.null(cat_key)) return(character(0))
  # Socioeconomic elements only cover drivers and welfare

  if (!cat_key %in% c("drivers", "welfare")) return(character(0))

  records <- .resolve_countries(country_codes)
  if (length(records) == 0) return(character(0))

  elements <- character(0)

  # Collect unique income levels
  income_levels <- unique(vapply(records, function(r) r$income_level %||% "", character(1)))
  income_levels <- income_levels[nchar(income_levels) > 0]

  for (lvl in income_levels) {
    lvl_data <- db$socioeconomic_elements[[lvl]]
    if (!is.null(lvl_data) && !is.null(lvl_data[[cat_key]])) {
      elements <- c(elements, unlist(lvl_data[[cat_key]]))
    }
  }

  result <- unique(elements)

  if (exists("debug_log", mode = "function")) {
    debug_log(sprintf("Country Gov: %d socioeconomic %s elements for income levels: %s",
                      length(result), cat_key,
                      paste(income_levels, collapse = ", ")), "COUNTRY GOV")
  }

  return(result)
}

# ==============================================================================
# PUBLIC API: COMBINED ENRICHED SUGGESTIONS
# ==============================================================================

#' Get Country-Enriched Element Suggestions
#'
#' Combined function that returns both governance and socioeconomic elements
#' for the selected countries and DAPSI(W)R(M) category, deduplicated and
#' sorted alphabetically.
#'
#' @param country_codes Character vector of ISO 3166-1 alpha-2 country codes
#' @param category DAPSI(W)R(M) category (see get_governance_elements for options)
#' @return Character vector of combined governance + socioeconomic suggestions
#' @export
get_country_enriched_suggestions <- function(country_codes, category) {
  gov_elements <- get_governance_elements(country_codes, category)
  socio_elements <- get_socioeconomic_elements(country_codes, category)

  result <- sort(unique(c(gov_elements, socio_elements)))

  if (exists("debug_log", mode = "function")) {
    debug_log(sprintf("Country Gov: %d enriched suggestions (%d gov + %d socio) for category '%s'",
                      length(result), length(gov_elements), length(socio_elements),
                      category), "COUNTRY GOV")
  }

  return(result)
}

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Auto-load on source
load_country_governance_db()

debug_log("Country Governance Database loader initialized", "INIT")
