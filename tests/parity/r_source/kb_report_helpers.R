# functions/kb_report_helpers.R
# Knowledge Base Report Helpers
# Purpose: Provides helper functions for enriching reports with KB context,
#   matching user-defined connections to KB-backed citations, retrieving
#   governance frameworks, and formatting KB-sourced markdown sections.
#
# Author: MarineSABRES SES Toolbox
# Date: 2026-03-24
# Dependencies: ses_knowledge_db_loader.R, country_governance_loader.R

# ==============================================================================
# INTERNAL HELPER
# ==============================================================================

#' i18n translation with English fallback
#' @keywords internal
.kb_t <- function(i18n, key, fallback) {
  if (!is.null(i18n) && is.function(i18n$t)) {
    translated <- tryCatch(i18n$t(key), error = function(e) NULL)
    if (!is.null(translated) && nchar(translated) > 0 && translated != key) {
      return(translated)
    }
  }
  return(fallback)
}

# ==============================================================================
# get_kb_context_for_report
# ==============================================================================

#' Get Knowledge Base Context for Report Generation
#'
#' Queries the SES knowledge database for elements relevant to a given
#' regional sea and ecosystem type, returning a structured list suitable
#' for inclusion in a generated report.
#'
#' @param regional_sea Regional sea key (e.g., "baltic", "mediterranean")
#' @param ecosystem_type Ecosystem/habitat type (free text, e.g., "lagoon", "seagrass")
#' @return Named list with: available (logical), description (character),
#'   top_elements (named list of character vectors per DAPSI(W)R(M) category)
#' @export
get_kb_context_for_report <- function(regional_sea, ecosystem_type) {
  # Input validation
  if (is.null(regional_sea) || is.null(ecosystem_type)) {
    debug_log("get_kb_context_for_report: NULL regional_sea or ecosystem_type", "KB REPORT")
    return(list(available = FALSE, description = "", top_elements = list()))
  }

  if (!ses_knowledge_db_available()) {
    debug_log("get_kb_context_for_report: SES knowledge DB not available", "KB REPORT")
    return(list(available = FALSE, description = "", top_elements = list()))
  }

  # Check if context exists in the database
  context_result <- .find_context(regional_sea, ecosystem_type)
  if (is.null(context_result)) {
    debug_log(sprintf("get_kb_context_for_report: no context found for %s/%s",
                      regional_sea, ecosystem_type), "KB REPORT")
    return(list(available = FALSE, description = "", top_elements = list()))
  }

  # Extract description from context
  description <- context_result$context$description %||%
    sprintf("Marine SES context for %s %s", regional_sea, ecosystem_type)

  # Gather top elements per DAPSI(W)R(M) category
  categories <- c("drivers", "activities", "pressures", "states",
                  "impacts", "welfare", "responses")
  top_elements <- list()

  for (cat in categories) {
    elements <- get_context_elements(regional_sea, ecosystem_type,
                                     category = cat, min_relevance = 0.8)
    if (length(elements) > 0) {
      top_elements[[cat]] <- elements
    }
  }

  debug_log(sprintf("KB report context: %d categories with elements for %s/%s",
                    length(top_elements), regional_sea, ecosystem_type), "KB REPORT")

  return(list(
    available    = TRUE,
    description  = description,
    top_elements = top_elements
  ))
}

# ==============================================================================
# match_user_connections_to_kb
# ==============================================================================

#' Match User-Defined Connections to Knowledge Base Records
#'
#' Performs fuzzy case-insensitive matching of user-supplied edge labels
#' against KB connection from/to names, retrieving scientific rationale,
#' references, temporal_lag, reversibility, and confidence for matched rows.
#'
#' @param user_edges Data frame with at least columns: from_label, to_label
#' @param regional_sea Regional sea key (e.g., "baltic")
#' @param ecosystem_type Ecosystem/habitat type (free text)
#' @return Data frame with columns: user_from, user_to, kb_matched (logical),
#'   rationale, references, temporal_lag, reversibility, kb_confidence
#' @export
match_user_connections_to_kb <- function(user_edges, regional_sea, ecosystem_type) {
  # Build empty result template
  empty_result <- data.frame(
    user_from      = character(0),
    user_to        = character(0),
    kb_matched     = logical(0),
    rationale      = character(0),
    references     = character(0),
    temporal_lag   = character(0),
    reversibility  = character(0),
    kb_confidence  = numeric(0),
    stringsAsFactors = FALSE
  )

  if (is.null(user_edges) || nrow(user_edges) == 0) {
    return(empty_result)
  }

  # Get KB connections for this context
  kb_connections <- get_context_connections(regional_sea, ecosystem_type)

  # Build output rows
  rows <- lapply(seq_len(nrow(user_edges)), function(i) {
    user_from <- as.character(user_edges$from_label[i])
    user_to   <- as.character(user_edges$to_label[i])

    kb_matched    <- FALSE
    rationale     <- ""
    references    <- ""
    temporal_lag  <- ""
    reversibility <- ""
    kb_confidence <- NA_real_

    for (kb_conn in kb_connections) {
      kb_from <- kb_conn$from %||% ""
      kb_to   <- kb_conn$to   %||% ""

      # Skip trivially short KB names
      if (nchar(kb_from) <= 2 || nchar(kb_to) <= 2) next

      # Fuzzy match: user label contains KB name or KB name contains user label
      # Check both directions for from/to
      from_match <- grepl(kb_from, user_from, fixed = TRUE, ignore.case = FALSE) ||
        grepl(tolower(kb_from), tolower(user_from), fixed = TRUE) ||
        grepl(tolower(user_from), tolower(kb_from), fixed = TRUE)

      to_match <- grepl(kb_to, user_to, fixed = TRUE, ignore.case = FALSE) ||
        grepl(tolower(kb_to), tolower(user_to), fixed = TRUE) ||
        grepl(tolower(user_to), tolower(kb_to), fixed = TRUE)

      if (from_match && to_match) {
        kb_matched    <- TRUE
        rationale     <- kb_conn$rationale    %||% ""
        references    <- paste(unlist(kb_conn$references %||% list()), collapse = "; ")
        temporal_lag  <- kb_conn$temporal_lag  %||% ""
        reversibility <- kb_conn$reversibility %||% ""
        kb_confidence <- as.numeric(kb_conn$confidence  %||% NA_real_)
        break
      }
    }

    data.frame(
      user_from      = user_from,
      user_to        = user_to,
      kb_matched     = kb_matched,
      rationale      = rationale,
      references     = references,
      temporal_lag   = temporal_lag,
      reversibility  = reversibility,
      kb_confidence  = kb_confidence,
      stringsAsFactors = FALSE
    )
  })

  result <- do.call(rbind, rows)
  if (is.null(result)) return(empty_result)

  debug_log(sprintf("KB match: %d/%d user connections matched to KB",
                    sum(result$kb_matched), nrow(result)), "KB REPORT")

  return(result)
}

# ==============================================================================
# get_governance_context
# ==============================================================================

#' Get Governance Context for a Regional Sea
#'
#' Retrieves regional conventions and optionally country-specific policies
#' for the given regional sea, returning a deduplicated list of governance
#' frameworks suitable for report sections.
#'
#' @param regional_sea Regional sea key (e.g., "baltic", "north_sea")
#' @param countries Optional character vector of ISO country codes to filter
#'   country-specific policies (default: NULL = all countries for the sea)
#' @return Named list with: available (logical), frameworks (character vector
#'   of deduplicated regional convention names), country_policies (named list
#'   of character vectors of policy notes per country)
#' @export
get_governance_context <- function(regional_sea, countries = NULL) {
  empty_result <- list(available = FALSE, frameworks = character(0),
                       country_policies = list())

  if (is.null(regional_sea) || nchar(trimws(regional_sea)) == 0) {
    return(empty_result)
  }

  country_records <- get_countries_for_sea(regional_sea)

  if (length(country_records) == 0) {
    return(empty_result)
  }

  # Optionally filter to specific countries
  if (!is.null(countries) && length(countries) > 0) {
    country_records <- country_records[
      names(country_records) %in% toupper(trimws(countries))
    ]
  }

  # Collect and deduplicate regional conventions across all countries
  all_conventions <- unique(unlist(lapply(country_records, function(r) {
    r$regional_conventions %||% character(0)
  })))
  all_conventions <- all_conventions[!is.na(all_conventions) & nchar(all_conventions) > 0]

  # Collect country-specific policies
  country_policies <- list()
  for (code in names(country_records)) {
    rec <- country_records[[code]]
    # Use governance_group as a proxy for policy context
    gov_group <- rec$governance_group %||% NULL
    if (!is.null(gov_group) && nchar(gov_group) > 0) {
      country_policies[[code]] <- gov_group
    }
  }

  available <- length(all_conventions) > 0 || length(country_policies) > 0

  debug_log(sprintf("Governance context: %d conventions, %d countries for '%s'",
                    length(all_conventions), length(country_policies),
                    regional_sea), "KB REPORT")

  return(list(
    available        = available,
    frameworks       = all_conventions,
    country_policies = country_policies
  ))
}

# ==============================================================================
# format_kb_section_for_report
# ==============================================================================

#' Format Knowledge Base Section for Report Markdown
#'
#' Assembles a Markdown-formatted section suitable for embedding in a generated
#' report. Includes site description, top elements per DAPSI(W)R(M) category,
#' a scientific references table for matched connections, and governance
#' frameworks list.
#'
#' @param kb_context Output of get_kb_context_for_report() or NULL
#' @param matched_connections Output of match_user_connections_to_kb() or NULL
#' @param governance Output of get_governance_context() or NULL
#' @param i18n Optional shiny.i18n translator object (uses English fallback)
#' @return Character string of Markdown text (never NULL)
#' @export
format_kb_section_for_report <- function(kb_context = NULL,
                                          matched_connections = NULL,
                                          governance = NULL,
                                          i18n = NULL) {
  sections <- character(0)

  # ---- Site description ----
  if (!is.null(kb_context) && isTRUE(kb_context$available)) {
    desc <- kb_context$description %||% ""
    if (nchar(trimws(desc)) > 0) {
      heading <- .kb_t(i18n, "modules.kb_report.site_context", "## Site Ecological Context")
      sections <- c(sections, heading, "", desc, "")
    }

    # ---- Top elements per category ----
    top_elements <- kb_context$top_elements %||% list()
    if (length(top_elements) > 0) {
      cat_heading <- .kb_t(i18n, "modules.kb_report.key_elements",
                           "### Key DAPSI(W)R(M) Elements from Knowledge Base")
      sections <- c(sections, cat_heading, "")

      # Human-readable category labels
      cat_labels <- c(
        drivers    = "Drivers (D)",
        activities = "Activities (A)",
        pressures  = "Pressures (P)",
        states     = "States/Components (C)",
        impacts    = "Impacts (ES)",
        welfare    = "Welfare (HW/GB)",
        responses  = "Responses (R/M)"
      )

      for (cat in names(top_elements)) {
        items <- top_elements[[cat]]
        if (length(items) == 0) next
        label <- cat_labels[[cat]] %||% cat
        sections <- c(sections,
                      sprintf("**%s**", label),
                      paste0("- ", items),
                      "")
      }
    }
  }

  # ---- Scientific references table ----
  if (!is.null(matched_connections) && nrow(matched_connections) > 0) {
    matched_only <- matched_connections[matched_connections$kb_matched == TRUE, , drop = FALSE]

    if (nrow(matched_only) > 0) {
      ref_heading <- .kb_t(i18n, "modules.kb_report.scientific_evidence",
                           "### Scientific Evidence for Connections")
      sections <- c(sections, ref_heading, "")

      # Build markdown table
      header <- "| Connection | Rationale | References | Temporal Lag | Reversibility |"
      sep    <- "|---|---|---|---|---|"
      rows   <- apply(matched_only, 1, function(r) {
        from_to  <- sprintf("%s → %s", r["user_from"], r["user_to"])
        rationale <- gsub("|", "\\|", r["rationale"] %||% "", fixed = TRUE)
        refs      <- gsub("|", "\\|", r["references"] %||% "", fixed = TRUE)
        tlag      <- r["temporal_lag"]  %||% ""
        rev       <- r["reversibility"] %||% ""
        sprintf("| %s | %s | %s | %s | %s |", from_to, rationale, refs, tlag, rev)
      })
      sections <- c(sections, header, sep, rows, "")
    }
  }

  # ---- Governance frameworks ----
  if (!is.null(governance) && isTRUE(governance$available)) {
    frameworks <- governance$frameworks %||% character(0)
    if (length(frameworks) > 0) {
      gov_heading <- .kb_t(i18n, "modules.kb_report.governance_frameworks",
                           "### Relevant Governance Frameworks")
      sections <- c(sections, gov_heading, "")
      sections <- c(sections, paste0("- ", frameworks), "")
    }

    country_policies <- governance$country_policies %||% list()
    if (length(country_policies) > 0) {
      pol_heading <- .kb_t(i18n, "modules.kb_report.country_policies",
                           "#### Country-Specific Governance Groups")
      sections <- c(sections, pol_heading, "")
      for (code in names(country_policies)) {
        sections <- c(sections,
                      sprintf("- **%s**: %s", code, country_policies[[code]]))
      }
      sections <- c(sections, "")
    }
  }

  if (length(sections) == 0) {
    return("")
  }

  return(paste(sections, collapse = "\n"))
}

debug_log("KB report helpers initialized", "INIT")
