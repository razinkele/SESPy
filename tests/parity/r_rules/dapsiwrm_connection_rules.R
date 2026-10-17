# functions/dapsiwrm_connection_rules.R
# DAPSIWRM adjacency rules and connection inference
# Defines which types can connect to which, and how to infer connection properties

#' DAPSIWRM Adjacency Rules
#'
#' Defines allowed connections between DAPSIWRM types following the framework logic:
#' Drivers → Activities → Pressures → Marine Processes & Functioning →
#' Ecosystem Services → Goods & Benefits → (Drivers/Responses)
#' Responses → (Drivers/Activities/Pressures/Marine Processes & Functioning/Responses)
#'
#' Fields per source type:
#' - `targets`: the canonical causal-chain targets (Rules 1-12 + collapsed 6/7).
#'   This is what the graphical builder iterates to suggest next elements.
#' - `extension_targets`: the further transitions DAPSIWRM_FRAMEWORK_RULES.md
#'   accepts (Rule 14 R→R, 16 C/S→C/S, 17 P→P, 18 A→A and the D→P ExUP
#'   exception). They are valid connections (validate_connection(),
#'   is_valid_dapsirwrm_transition()) but are not offered as suggestions.
#' - `target_polarities`: default polarity per target type (canonical and
#'   extension). `default_polarity` is the per-source fallback.
#' Use get_rule_default_polarity() / default_polarity_for_matrix() rather than
#' reading `default_polarity` directly (review 2026-10-07 N26 / N61).
#'
#' @format List of allowed connections with polarity and examples
#' @export
DAPSIWRM_ADJACENCY_RULES <- list(

  # ============================================================================
  # DRIVERS (D) → ACTIVITIES (A)
  # ============================================================================
  Drivers = list(
    targets = c("Activities"),
    # D → P: Exogenic Unmanaged Pressures exception (Elliott 2011). The doc
    # gives no sign; "+" follows the neighbouring D→A / A→P convention (the
    # driver produces the pressure).
    extension_targets = c("Pressures"),
    target_polarities = c("Activities" = "+", "Pressures" = "+"),
    default_polarity = "+",
    allowed_polarities = c("+", "-"),

    description = "Drivers create demand for activities",

    examples = list(
      list(
        from = "Food security need",
        to = "Commercial fishing",
        polarity = "+",
        strength = "strong",
        reasoning = "Food demand drives fishing activity"
      ),
      list(
        from = "Economic growth",
        to = "Coastal development",
        polarity = "+",
        strength = "strong",
        reasoning = "Economic growth drives development"
      ),
      list(
        from = "Tourism demand",
        to = "Recreational boating",
        polarity = "+",
        strength = "medium",
        reasoning = "Tourism creates demand for recreation"
      )
    )
  ),

  # ============================================================================
  # ACTIVITIES (A) → PRESSURES (P)
  # ============================================================================
  Activities = list(
    targets = c("Pressures"),
    # Rule 18 A → A (MSP / cumulative-effects extension). Doc: "Varies";
    # "+" follows the doc's example (facilitation).
    extension_targets = c("Activities"),
    target_polarities = c("Pressures" = "+", "Activities" = "+"),
    default_polarity = "+",
    allowed_polarities = c("+", "-"),

    description = "Activities generate pressures on the environment",

    examples = list(
      list(
        from = "Trawl fishing",
        to = "Seabed disturbance",
        polarity = "+",
        strength = "strong",
        reasoning = "Trawling directly disturbs seabed"
      ),
      list(
        from = "Aquaculture",
        to = "Nutrient enrichment",
        polarity = "+",
        strength = "medium",
        reasoning = "Fish farms release nutrients"
      ),
      list(
        from = "Agriculture",
        to = "Nutrient pollution",
        polarity = "+",
        strength = "strong",
        reasoning = "Fertilizer runoff causes nutrient pollution"
      ),
      list(
        from = "Wastewater treatment",
        to = "Nutrient pollution",
        polarity = "-",
        strength = "medium",
        reasoning = "Treatment reduces nutrient pollution"
      )
    )
  ),

  # ============================================================================
  # PRESSURES (P) → MARINE PROCESSES & FUNCTIONING (S)
  # ============================================================================
  Pressures = list(
    targets = c("Marine Processes & Functioning"),
    # Rule 17 P → P (pressure cascades). Doc: "Varies (typically reinforcing)".
    extension_targets = c("Pressures"),
    # Rule 3 P → C/S defaults to "-" (pressures degrade state).
    target_polarities = c("Marine Processes & Functioning" = "-", "Pressures" = "+"),
    default_polarity = "-",
    allowed_polarities = c("-", "+"),

    description = "Pressures negatively affect marine state and processes",

    examples = list(
      list(
        from = "Nutrient enrichment",
        to = "Hypoxia",
        polarity = "+",
        strength = "strong",
        reasoning = "Nutrients cause oxygen depletion"
      ),
      list(
        from = "Overfishing",
        to = "Fish population decline",
        polarity = "+",
        strength = "strong",
        reasoning = "Overfishing reduces populations"
      ),
      list(
        from = "Seabed disturbance",
        to = "Habitat quality",
        polarity = "-",
        strength = "medium",
        reasoning = "Disturbance degrades habitat"
      ),
      list(
        from = "Marine litter",
        to = "Biodiversity",
        polarity = "-",
        strength = "medium",
        reasoning = "Litter harms marine life"
      )
    )
  ),

  # ============================================================================
  # MARINE PROCESSES & FUNCTIONING (S) → ECOSYSTEM SERVICES (I)
  # ============================================================================
  "Marine Processes & Functioning" = list(
    targets = c("Ecosystem Services"),
    # Rule 16 C/S → C/S. Doc: "Varies"; "+" follows the doc's example.
    extension_targets = c("Marine Processes & Functioning"),
    target_polarities = c("Ecosystem Services" = "+", "Marine Processes & Functioning" = "+"),
    default_polarity = "+",
    allowed_polarities = c("+", "-"),

    description = "Healthy ecosystem state provides services",

    examples = list(
      list(
        from = "Seagrass habitat",
        to = "Nursery function",
        polarity = "+",
        strength = "strong",
        reasoning = "Seagrass provides nursery habitat"
      ),
      list(
        from = "Fish population",
        to = "Fish provision",
        polarity = "+",
        strength = "strong",
        reasoning = "Populations provide fish"
      ),
      list(
        from = "Biodiversity",
        to = "Ecosystem resilience",
        polarity = "+",
        strength = "medium",
        reasoning = "Diversity enhances resilience"
      ),
      list(
        from = "Hypoxia",
        to = "Fish provision",
        polarity = "-",
        strength = "strong",
        reasoning = "Oxygen depletion reduces fish availability"
      )
    )
  ),

  # ============================================================================
  # ECOSYSTEM SERVICES (I) → GOODS & BENEFITS (W)
  # ============================================================================
  "Ecosystem Services" = list(
    targets = c("Goods & Benefits"),
    extension_targets = character(0),
    target_polarities = c("Goods & Benefits" = "+"),
    default_polarity = "+",
    allowed_polarities = c("+", "-"),

    description = "Services provide welfare benefits to humans",

    examples = list(
      list(
        from = "Fish provision",
        to = "Food security",
        polarity = "+",
        strength = "strong",
        reasoning = "Fish provision ensures food security"
      ),
      list(
        from = "Coastal protection",
        to = "Property protection",
        polarity = "+",
        strength = "strong",
        reasoning = "Natural barriers protect infrastructure"
      ),
      list(
        from = "Recreation",
        to = "Tourism revenue",
        polarity = "+",
        strength = "medium",
        reasoning = "Recreation attracts tourists"
      ),
      list(
        from = "Carbon sequestration",
        to = "Climate regulation benefit",
        polarity = "+",
        strength = "medium",
        reasoning = "Carbon storage mitigates climate change"
      )
    )
  ),

  # ============================================================================
  # GOODS & BENEFITS (W) → DRIVERS (D) / RESPONSES (R)
  # ============================================================================
  "Goods & Benefits" = list(
    targets = c("Drivers", "Responses"),
    extension_targets = character(0),
    target_polarities = c("Drivers" = "+", "Responses" = "+"),
    default_polarity = "+",
    allowed_polarities = c("+", "-"),

    description = "Benefits can drive demand or trigger responses",

    examples = list(
      list(
        from = "Economic loss",
        to = "Policy demand",
        polarity = "+",
        strength = "medium",
        reasoning = "Losses create pressure for policy"
      ),
      list(
        from = "Income from fishing",
        to = "Fishing demand",
        polarity = "+",
        strength = "medium",
        reasoning = "Profitable fishing increases demand"
      ),
      list(
        from = "Health impacts",
        to = "Regulation demand",
        polarity = "+",
        strength = "strong",
        reasoning = "Health issues trigger regulation calls"
      )
    )
  ),

  # ============================================================================
  # RESPONSES (R) → Multiple targets
  # ============================================================================
  Responses = list(
    targets = c("Drivers", "Activities", "Pressures", "Marine Processes & Functioning"),
    # Rule 14 R → R. Doc: "Varies"; "+" follows the doc's example.
    extension_targets = c("Responses"),
    # Rules 9-11 R → D/A/P: "-" (restrict / mitigate). Rule 12 R → C/S: the doc
    # gives "+" (restoration / protection raises state), so new R → MPF cells
    # seed "+".
    target_polarities = c("Drivers" = "-", "Activities" = "-", "Pressures" = "-",
                          "Marine Processes & Functioning" = "+", "Responses" = "+"),
    default_polarity = "-",
    allowed_polarities = c("-", "+"),

    description = "Responses manage or mitigate drivers, activities, and pressures, or enhance state",

    examples = list(
      list(
        from = "Fishing quota",
        to = "Commercial fishing",
        polarity = "-",
        strength = "strong",
        reasoning = "Quotas limit fishing activity"
      ),
      list(
        from = "Marine Protected Area",
        to = "Trawl fishing",
        polarity = "-",
        strength = "strong",
        reasoning = "MPAs restrict fishing"
      ),
      list(
        from = "Nutrient reduction policy",
        to = "Nutrient enrichment",
        polarity = "-",
        strength = "medium",
        reasoning = "Policy reduces nutrient input"
      ),
      list(
        from = "Habitat restoration",
        to = "Habitat quality",
        polarity = "+",
        strength = "medium",
        reasoning = "Restoration improves habitat"
      ),
      list(
        from = "Fishing ban",
        to = "Fishing demand",
        polarity = "-",
        strength = "strong",
        reasoning = "Ban reduces demand for fishing"
      )
    )
  )
)


#' Get Allowed Target Types for a DAPSIWRM Type
#'
#' @param source_type Source DAPSIWRM type
#' @param include_extensions If TRUE, also return the extension transitions
#'   (R→R, P→P, C/S→C/S, A→A, D→P). Default FALSE: the canonical chain only,
#'   which is what the graphical builder suggests.
#' @return Character vector of allowed target types
#' @export
get_allowed_targets <- function(source_type, include_extensions = FALSE) {
  if (!source_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    log_warning("DAPSIWRM", paste("Unknown DAPSIWRM type:", source_type))
    return(character(0))
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[source_type]]
  if (isTRUE(include_extensions)) {
    return(unique(c(rule$targets, rule$extension_targets)))
  }
  return(rule$targets)
}

#' All valid target types of a rule entry (canonical + extension)
#' @param rule one DAPSIWRM_ADJACENCY_RULES entry
#' @return character vector
.rule_all_targets <- function(rule) unique(c(rule$targets, rule$extension_targets))

#' Default polarity for a DAPSIWRM transition, from the rule table
#'
#' Single source of truth for seeding new matrix cells (review 2026-10-07 N26).
#'
#' @param from_type Source DAPSIWRM type (table name, e.g. "Pressures")
#' @param to_type Target DAPSIWRM type
#' @param fallback returned when the transition is not in the table
#' @return "+" or "-"
#' @export
get_rule_default_polarity <- function(from_type, to_type, fallback = "+") {
  if (!exists("DAPSIWRM_ADJACENCY_RULES") || is.null(from_type) ||
      !from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return(fallback)
  }
  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]
  tp <- rule$target_polarities
  if (!is.null(to_type) && !is.null(tp) && to_type %in% names(tp)) {
    return(unname(tp[[to_type]]))
  }
  if (!is.null(to_type) && to_type %in% .rule_all_targets(rule)) {
    return(rule$default_polarity)
  }
  fallback
}

#' Standard Entry matrix key -> c(source type, target type) in table names
DAPSIWRM_MATRIX_KEY_TYPES <- list(
  d_a    = c("Drivers", "Activities"),
  a_p    = c("Activities", "Pressures"),
  p_mpf  = c("Pressures", "Marine Processes & Functioning"),
  mpf_es = c("Marine Processes & Functioning", "Ecosystem Services"),
  es_gb  = c("Ecosystem Services", "Goods & Benefits"),
  gb_d   = c("Goods & Benefits", "Drivers"),
  gb_r   = c("Goods & Benefits", "Responses"),
  r_d    = c("Responses", "Drivers"),
  r_a    = c("Responses", "Activities"),
  r_p    = c("Responses", "Pressures"),
  r_mpf  = c("Responses", "Marine Processes & Functioning"),
  r_r    = c("Responses", "Responses")
)

#' Default polarity used to seed a NEW cell of a Standard Entry matrix
#'
#' Looks the transition up in DAPSIWRM_ADJACENCY_RULES so every seeding path
#' (Standard Entry save, Responses save, Excel/project recovery) agrees with
#' the framework rules — e.g. p_mpf seeds "-" (Rule 3), not a hard-coded "+".
#'
#' @param matrix_key e.g. "p_mpf", "r_d", "gb_r"
#' @param fallback used for unknown keys
#' @return "+" or "-"
#' @export
default_polarity_for_matrix <- function(matrix_key, fallback = "+") {
  types <- DAPSIWRM_MATRIX_KEY_TYPES[[matrix_key]]
  if (is.null(types)) return(fallback)
  get_rule_default_polarity(types[1], types[2], fallback = fallback)
}


#' Infer Connection Polarity
#'
#' Determines the most likely polarity (+/-) for a connection between two elements
#'
#' @param from_name Source element name
#' @param to_name Target element name
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @return Character: "+" or "-"
#' @export
infer_connection_polarity <- function(from_name, to_name, from_type, to_type) {

  # Get rule for this connection
  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return("+")  # Default positive
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]

  # Check if target type is allowed
  if (!to_type %in% .rule_all_targets(rule)) {
    log_warning("DAPSIWRM", paste("Connection", from_type, "->", to_type, "not in standard DAPSIWRM framework"))
    return("+")
  }

  # Use the per-target default polarity from the rule table
  default_pol <- get_rule_default_polarity(from_type, to_type)

  # Check for negative keywords that might reverse polarity
  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  # Special cases for Activities → Pressures
  if (from_type == "Activities" && to_type == "Pressures") {
    # If activity is about treatment/reduction, polarity is negative
    if (grepl("treatment|reduction|control|mitigation|restoration", from_lower)) {
      return("-")
    }
    return("+")  # Most activities create pressures
  }

  # Special cases for Pressures → State
  if (from_type == "Pressures" && to_type == "Marine Processes & Functioning") {
    # Check if "to" is negative (decline, loss) or positive (quality, health)
    if (grepl("decline|loss|depletion|degradation|mortality", to_lower)) {
      return("+")  # Pressure increases decline
    } else if (grepl("quality|health|abundance|biodiversity|resilience", to_lower)) {
      return("-")  # Pressure decreases quality
    }
    return("-")  # Default: pressures harm state
  }

  # Special cases for Responses
  if (from_type == "Responses") {
    # Check target type
    if (to_type %in% c("Drivers", "Activities", "Pressures")) {
      return("-")  # Responses typically reduce these
    } else if (to_type == "Marine Processes & Functioning") {
      # Rule 12: restoration AND protection raise state ("Marine protected
      # areas" -> "Increase fish stocks" (+)). Use the rule-table default so
      # the graphical builder and Standard Entry seed the same sign (N61).
      return(default_pol)
    }
  }

  return(default_pol)
}


#' Infer Connection Strength
#'
#' Estimates connection strength based on element names and types
#'
#' @param from_name Source element name
#' @param to_name Target element name
#' @param context User's context (optional)
#' @return Character: "strong", "medium", or "weak"
#' @export
infer_connection_strength <- function(from_name, to_name, context = NULL) {

  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  # Check for word overlap (indicates direct relationship)
  from_words <- strsplit(from_lower, "[\\s,.-]+")[[1]]
  to_words <- strsplit(to_lower, "[\\s,.-]+")[[1]]

  # Remove common stopwords
  stopwords <- c("the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or")
  from_words <- setdiff(from_words, stopwords)
  to_words <- setdiff(to_words, stopwords)

  overlap_count <- length(intersect(from_words, to_words))

  # High overlap = strong connection
  if (overlap_count >= 2) {
    return("strong")
  } else if (overlap_count == 1) {
    return("medium")
  }

  # Check for strong relationship keywords
  strong_keywords <- c(
    "overfishing|fishing", "nutrient enrichment|nutrient", "pollution|contamination",
    "quota|fishing", "MPA|protection", "habitat|biodiversity"
  )

  for (pair in strong_keywords) {
    keywords <- strsplit(pair, "\\|")[[1]]
    if (grepl(keywords[1], from_lower) && grepl(keywords[2], to_lower)) {
      return("strong")
    }
  }

  # Default to medium
  return("medium")
}


#' Get Connection Confidence
#'
#' Estimates how confident we are about a suggested connection
#'
#' @param from_element Source element data (with type)
#' @param to_element Target element data (with type)
#' @param context User's context
#' @return Numeric confidence (1-5 scale)
#' @export
get_connection_confidence <- function(from_element, to_element, context = NULL) {

  confidence <- 3  # Default: medium confidence

  # Increase confidence if connection follows DAPSIWRM rules
  allowed_targets <- get_allowed_targets(from_element$type)
  if (to_element$type %in% allowed_targets) {
    confidence <- confidence + 1
  }

  # Increase confidence if names have keyword overlap
  strength <- infer_connection_strength(from_element$name, to_element$name, context)
  if (strength == "strong") {
    confidence <- confidence + 1
  }

  # Decrease confidence if types are unusual
  if (from_element$type == "Marine Processes & Functioning" && to_element$type == "Drivers") {
    confidence <- confidence - 1  # Unusual connection
  }

  # Cap at 1-5 range
  return(max(1, min(5, confidence)))
}


#' Validate Connection
#'
#' Checks if a proposed connection is valid according to DAPSIWRM rules
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @param strict If TRUE, only allow standard connections. If FALSE, allow all
#' @return TRUE if valid, FALSE otherwise
#' @export
validate_connection <- function(from_type, to_type, strict = FALSE) {

  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return(!strict)  # Allow if not strict
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]
  is_allowed <- to_type %in% .rule_all_targets(rule)

  if (!is_allowed && !strict) {
    debug_log(paste("Non-standard connection:", from_type, "->", to_type), "CONNECTION")
    return(TRUE)  # Allow non-standard connections in permissive mode
  }

  return(is_allowed)
}


#' Get Connection Description
#'
#' Returns a human-readable description of what a connection means
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @return Character string describing the relationship
#' @export
get_connection_description <- function(from_type, to_type) {

  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return("Related element")
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]

  if (to_type %in% rule$targets) {
    return(rule$description)
  }

  # Generic description
  return(paste(from_type, "affects", to_type))
}


#' Get Connection Examples
#'
#' Returns example connections for a given type pair
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @return List of example connections
#' @export
get_connection_examples <- function(from_type, to_type) {

  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return(list())
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]

  if (!to_type %in% rule$targets) {
    return(list())
  }

  # Filter examples for this target type
  # (Examples in rule don't specify target type explicitly,
  #  but we can infer from the allowed targets)
  return(rule$examples)
}


#' Validate Connection with Feedback
#'
#' Validates a DAPSI(W)R(M) connection and returns structured feedback
#' including validity, severity level, message, and suggestions.
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @param strict If TRUE, reject non-standard connections. If FALSE, warn but allow.
#' @return List with: valid (logical), level (character), message (character),
#'   suggestion (character or NULL), warning (logical)
#' @export
validate_connection_with_feedback <- function(from_type, to_type, strict = FALSE) {
  # Check if from_type is known

  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    if (strict) {
      return(list(
        valid = FALSE,
        level = "error",
        message = paste("Unknown source type:", from_type),
        suggestion = paste("Valid types:", paste(names(DAPSIWRM_ADJACENCY_RULES), collapse = ", ")),
        warning = FALSE
      ))
    } else {
      return(list(
        valid = TRUE,
        level = "warning",
        message = paste("Unknown source type:", from_type, "- connection allowed in permissive mode"),
        suggestion = NULL,
        warning = TRUE
      ))
    }
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]
  is_standard <- to_type %in% .rule_all_targets(rule)

  if (is_standard) {
    # Standard DAPSIWRM connection
    return(list(
      valid = TRUE,
      level = "success",
      message = paste("Valid DAPSI(W)R(M) connection:", from_type, "->", to_type),
      suggestion = NULL,
      warning = FALSE
    ))
  }

  # Non-standard connection

  valid_targets <- .rule_all_targets(rule)
  suggestion_text <- paste("Standard targets for", from_type, "are:",
                           paste(valid_targets, collapse = ", "))

  if (strict) {
    return(list(
      valid = FALSE,
      level = "error",
      message = paste("Non-standard connection:", from_type, "->", to_type,
                       "is not allowed in strict mode"),
      suggestion = suggestion_text,
      warning = FALSE
    ))
  } else {
    return(list(
      valid = TRUE,
      level = "warning",
      message = paste("Non-standard connection:", from_type, "->", to_type,
                       "- allowed but not typical in DAPSI(W)R(M)"),
      suggestion = suggestion_text,
      warning = TRUE
    ))
  }
}


#' Get Connection Validation Message
#'
#' Returns a human-readable validation message for a connection.
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @param strict If TRUE, use strict validation
#' @return Character string with validation message
#' @export
get_connection_validation_message <- function(from_type, to_type, strict = FALSE) {
  result <- validate_connection_with_feedback(from_type, to_type, strict = strict)
  return(result$message)
}


#' Check Connection with Notification
#'
#' Validates a connection and optionally shows a Shiny notification.
#'
#' @param from_type Source DAPSIWRM type
#' @param to_type Target DAPSIWRM type
#' @param strict If TRUE, use strict validation
#' @param notify If TRUE, show a Shiny notification (requires active session)
#' @return List with validation result (same as validate_connection_with_feedback)
#' @export
check_connection_with_notification <- function(from_type, to_type, strict = FALSE, notify = TRUE) {
  result <- validate_connection_with_feedback(from_type, to_type, strict = strict)

  if (notify && requireNamespace("shiny", quietly = TRUE)) {
    notification_type <- switch(result$level,
      "success" = "message",
      "warning" = "warning",
      "error" = "error",
      "default"
    )
    tryCatch({
      shiny::showNotification(result$message, type = notification_type)
    }, error = function(e) {
      # No active Shiny session - silently skip notification
      debug_log(paste("Could not show notification:", e$message), "CONNECTION")
    })
  }

  return(result)
}


#' Get Valid Targets for UI
#'
#' Returns a data frame of valid target types for a given source type,
#' suitable for populating UI dropdown menus.
#'
#' @param from_type Source DAPSIWRM type
#' @return Data frame with columns: type, description
#' @export
get_valid_targets_for_ui <- function(from_type) {
  if (!from_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
    return(data.frame(type = character(0), description = character(0),
                      stringsAsFactors = FALSE))
  }

  rule <- DAPSIWRM_ADJACENCY_RULES[[from_type]]
  targets <- rule$targets

  # Build descriptions for each target
  descriptions <- vapply(targets, function(target_type) {
    if (target_type %in% names(DAPSIWRM_ADJACENCY_RULES)) {
      # Use the description from the target's own rule entry
      target_rule <- DAPSIWRM_ADJACENCY_RULES[[target_type]]
      return(paste(from_type, "->", target_type))
    }
    return(paste(from_type, "->", target_type))
  }, character(1))

  data.frame(
    type = targets,
    description = descriptions,
    stringsAsFactors = FALSE
  )
}
