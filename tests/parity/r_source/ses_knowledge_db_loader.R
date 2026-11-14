# functions/ses_knowledge_db_loader.R
# SES Knowledge Database Loader
# Purpose: Loads the JSON-based marine SES knowledge database and provides
#   context-aware element and connection lookup functions.
#
# The knowledge database provides ecologically plausible, habitat-specific
# DAPSI(W)R(M) element suggestions and scientifically defensible connections
# for specific regional sea x habitat combinations.
#
# Author: MarineSABRES SES Toolbox
# Date: 2026-03-14
# Dependencies: jsonlite (already loaded in global.R)

# ==============================================================================
# MODULE-LEVEL STATE
# ==============================================================================

# Package-level environment to hold loaded database
.ses_kb_env <- new.env(parent = emptyenv())
.ses_kb_env$db <- NULL
.ses_kb_env$loaded <- FALSE

# ==============================================================================
# DATABASE LOADING
# ==============================================================================

#' Load the SES Knowledge Database from JSON
#'
#' Reads and parses the JSON knowledge database file. Called once at startup.
#' Subsequent calls return the cached database unless force_reload is TRUE.
#'
#' @param db_path Path to the JSON database file (default: data/ses_knowledge_db.json)
#' @param force_reload If TRUE, reload even if already cached
#' @return The parsed database list, invisibly
#' @export
load_ses_knowledge_db <- function(db_path = NULL, force_reload = FALSE) {
  if (.ses_kb_env$loaded && !force_reload) {
    return(invisible(.ses_kb_env$db))
  }

  # Determine path

if (is.null(db_path)) {
    if (exists("get_project_file", mode = "function")) {
      db_path <- get_project_file("data", "ses_knowledge_db.json")
    } else {
      db_path <- file.path("data", "ses_knowledge_db.json")
    }
  }

  if (!file.exists(db_path)) {
    warning(sprintf("[SES KB] Knowledge database not found at: %s", db_path))
    .ses_kb_env$db <- NULL
    .ses_kb_env$loaded <- FALSE
    return(invisible(NULL))
  }

  tryCatch({
    raw <- jsonlite::fromJSON(db_path, simplifyDataFrame = FALSE)
    .ses_kb_env$db <- raw
    .ses_kb_env$loaded <- TRUE

    n_contexts <- length(raw$contexts %||% list())
    if (exists("debug_log", mode = "function")) {
      debug_log(sprintf("SES Knowledge DB loaded: v%s, %d contexts",
                        raw$version %||% "unknown", n_contexts), "SES KB")
    }

    message(sprintf("[SES KB] Loaded knowledge database v%s with %d contexts",
                    raw$version %||% "unknown", n_contexts))

    invisible(raw)
  }, error = function(e) {
    warning(sprintf("[SES KB] Failed to load knowledge database: %s", e$message))
    .ses_kb_env$db <- NULL
    .ses_kb_env$loaded <- FALSE
    invisible(NULL)
  })
}

# ==============================================================================
# CONTEXT LOOKUP HELPERS
# ==============================================================================

#' Build Context Key from Regional Sea and Habitat
#'
#' Constructs the lookup key used in the JSON database from user-provided
#' regional sea and habitat/ecosystem type strings.
#'
#' @param regional_sea Regional sea key (e.g., "baltic", "mediterranean")
#' @param habitat Habitat/ecosystem type string (free text from UI)
#' @return Character context key (e.g., "baltic_lagoon") or NULL if no match
#' @keywords internal
.build_context_key <- function(regional_sea, habitat) {
  if (is.null(regional_sea) || is.null(habitat)) return(NULL)

  sea <- tolower(trimws(regional_sea))
  hab <- tolower(trimws(habitat))

  # Map habitat free text to standard keys
  habitat_key <- if (grepl("lagoon", hab)) "lagoon"
    else if (grepl("estuar", hab)) "estuary"
    else if (grepl("offshore|open ocean|open water|deep sea|continental shelf|shelf|pelagic", hab)) "offshore"
    else if (grepl("seagrass|sea grass|posidonia", hab)) "seagrass"
    else if (grepl("sch.ren|sk.rg.rd|rocky coast", hab)) "rocky_coast"  # Baltic Schären
    else if (grepl("rocky|rock shore", hab)) "rocky_shore"  # Mediterranean rocky shore
    else if (grepl("atoll", hab)) "island"  # Atoll → island context
    else if (grepl("coral|reef", hab)) "coral_reef"
    else if (grepl("island|insular", hab)) "island"  # Island ecosystems
    else if (grepl("archipelago", hab)) "archipelago"
    else if (grepl("ice|arctic", hab)) "sea_ice"
    else if (grepl("open coast|coast(?!al lagoon)", hab, perl = TRUE)) "open_coast"
    else if (grepl("mangrove", hab)) "mangrove"
    else if (grepl("tidal|mudflat", hab)) "tidal_flat"
    else if (grepl("saltmarsh|salt marsh|marsh", hab)) "estuary"
    else if (grepl("benthic|benthos", hab)) "offshore"
    else if (grepl("kelp", hab)) "kelp_forest"
    else if (grepl("fjord", hab)) "fjord"
    else if (grepl("delta", hab)) "delta"
    else if (grepl("sandy|beach", hab)) "sandy_beach"
    else NULL

  if (is.null(habitat_key)) return(NULL)

  # Build the key
  context_key <- paste(sea, habitat_key, sep = "_")
  return(context_key)
}


#' Find Matching Context in Database
#'
#' Attempts to find an exact context match, then falls back to partial matches
#' within the SAME regional sea only. Cross-region fallbacks are intentionally
#' excluded to prevent content contamination (e.g., Black Sea data appearing
#' when North Sea is selected).
#'
#' @param regional_sea Regional sea key
#' @param habitat Habitat/ecosystem type string
#' @return List with $context (the data) and $key (the matched key), or NULL
#' @keywords internal
.find_context <- function(regional_sea, habitat) {
  db <- .ses_kb_env$db
  if (is.null(db) || is.null(db$contexts)) return(NULL)

  # Try exact match first
  context_key <- .build_context_key(regional_sea, habitat)
  if (!is.null(context_key) && !is.null(db$contexts[[context_key]])) {
    return(list(context = db$contexts[[context_key]], key = context_key, match = "exact"))
  }

  # Try prefix match (handles pacific_island matching pacific_island_atoll etc.)
  # Only allow matches that share the same regional sea prefix
  sea <- tolower(trimws(regional_sea))
  if (!is.null(context_key)) {
    for (key in names(db$contexts)) {
      if (startsWith(key, paste0(sea, "_")) &&
          (startsWith(key, context_key) || startsWith(context_key, key))) {
        return(list(context = db$contexts[[key]], key = key, match = "prefix"))
      }
    }
  }

  # Fallback: same sea, different habitat (never cross-region)
  # This ensures we only return data from the same regional sea
  for (key in names(db$contexts)) {
    if (startsWith(key, paste0(sea, "_"))) {
      if (exists("debug_log", mode = "function")) {
        debug_log(sprintf("SES KB: No exact match for '%s', falling back to '%s' (sea_only)",
                          context_key %||% "NULL", key), "SES KB")
      }
      return(list(context = db$contexts[[key]], key = key, match = "sea_only"))
    }
  }

  # No match found for this regional sea -- caller will use generic_fallback
  return(NULL)
}

# ==============================================================================
# PUBLIC API: ELEMENT SUGGESTIONS
# ==============================================================================

#' Get Context-Specific Element Suggestions from Knowledge Database
#'
#' Returns element name suggestions for a specific DAPSI(W)R(M) category
#' tailored to the regional sea and habitat combination. Falls back to
#' generic suggestions if no specific context is found.
#'
#' @param regional_sea Regional sea key (e.g., "baltic", "mediterranean", "north_sea")
#' @param habitat Habitat/ecosystem type (free text, e.g., "Coastal lagoon", "Offshore waters")
#' @param category DAPSI(W)R(M) category: one of "drivers", "activities", "pressures",
#'   "states", "impacts", "welfare", "responses"
#' @param min_relevance Minimum relevance score (0-1) to include an element (default: 0.0)
#' @return Character vector of element name suggestions, sorted by relevance (highest first).
#'   Returns character(0) if no database match and no fallback available.
#' @export
#'
#' @examples
#' \dontrun{
#' # Get activity suggestions for a Baltic lagoon
#' get_context_elements("baltic", "Coastal lagoon", "activities")
#' # Returns: c("Small-scale gillnet fishing for pike-perch",
#' #            "Agricultural drainage into lagoon", ...)
#'
#' # Get pressures for a Mediterranean seagrass meadow
#' get_context_elements("mediterranean", "Seagrass meadow", "pressures")
#' }
get_context_elements <- function(regional_sea, habitat, category, min_relevance = 0.0) {
  # Ensure database is loaded
  if (!.ses_kb_env$loaded) {
    load_ses_knowledge_db()
  }

  db <- .ses_kb_env$db
  if (is.null(db)) return(character(0))

  # Find matching context
  match <- .find_context(regional_sea, habitat)

  # Use matched context or generic fallback
  context_data <- if (!is.null(match)) {
    match$context
  } else if (!is.null(db$generic_fallback)) {
    db$generic_fallback
  } else {
    return(character(0))
  }

  # Get elements for the requested category
  elements <- context_data[[category]]
  if (is.null(elements) || length(elements) == 0) return(character(0))

  # Extract names and relevance scores
  names_vec <- character(length(elements))
  relevance_vec <- numeric(length(elements))

  for (i in seq_along(elements)) {
    el <- elements[[i]]
    names_vec[i] <- el$name %||% ""
    relevance_vec[i] <- el$relevance %||% 0.5
  }

  # Filter by minimum relevance
  keep <- relevance_vec >= min_relevance & nchar(names_vec) > 0
  if (!any(keep)) return(character(0))

  # Sort by relevance (descending)
  order_idx <- order(relevance_vec[keep], decreasing = TRUE)
  result <- names_vec[keep][order_idx]

  if (exists("debug_log", mode = "function")) {
    match_type <- if (!is.null(match)) match$match else "fallback"
    debug_log(sprintf("SES KB: %d %s for %s/%s (match: %s)",
                      length(result), category,
                      regional_sea %||% "NULL", habitat %||% "NULL",
                      match_type), "SES KB")
  }

  return(result)
}

# ==============================================================================
# PUBLIC API: CONNECTION SUGGESTIONS
# ==============================================================================

#' Get Context-Specific Connection Suggestions from Knowledge Database
#'
#' Returns pre-defined, scientifically defensible connections for a specific
#' regional sea and habitat combination. These connections have curated
#' polarity, strength, confidence scores, and rationale text.
#'
#' @param regional_sea Regional sea key
#' @param habitat Habitat/ecosystem type (free text)
#' @return List of connection objects, each with: from, from_type, to, to_type,
#'   polarity, strength, confidence, rationale. Returns empty list if no match.
#' @export
#'
#' @examples
#' \dontrun{
#' conns <- get_context_connections("baltic", "Coastal lagoon")
#' # Returns list of 15 connection objects with polarity, strength, etc.
#' }
get_context_connections <- function(regional_sea, habitat) {
  # Ensure database is loaded
  if (!.ses_kb_env$loaded) {
    load_ses_knowledge_db()
  }

  db <- .ses_kb_env$db
  if (is.null(db)) return(list())

  # Find matching context
  match <- .find_context(regional_sea, habitat)
  if (is.null(match)) return(list())

  connections <- match$context$connections
  if (is.null(connections) || length(connections) == 0) return(list())

  if (exists("debug_log", mode = "function")) {
    debug_log(sprintf("SES KB: %d connections for %s (match: %s, key: %s)",
                      length(connections), paste(regional_sea, habitat, sep = "/"),
                      match$match, match$key), "SES KB")
  }

  return(connections)
}


#' Check if Knowledge Database is Available
#'
#' @return TRUE if the database is loaded and has contexts
#' @export
ses_knowledge_db_available <- function() {
  return(.ses_kb_env$loaded && !is.null(.ses_kb_env$db) &&
         length(.ses_kb_env$db$contexts %||% list()) > 0)
}


#' Get List of Available Contexts
#'
#' @return Character vector of context keys (e.g., "baltic_lagoon", "caribbean_coral_reef")
#' @export
get_available_contexts <- function() {
  if (!.ses_kb_env$loaded) return(character(0))
  return(names(.ses_kb_env$db$contexts %||% list()))
}


# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Auto-load on source
load_ses_knowledge_db()

debug_log("SES Knowledge Database loader initialized", "INIT")
