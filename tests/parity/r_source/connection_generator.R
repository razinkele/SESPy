# modules/ai_isa/connection_generator.R
# AI ISA Connection Generator Module
# Purpose: AI/ML algorithms for intelligent connection suggestions
#
# This module contains pure functions for generating, filtering, and ranking
# connections between DAPSI(W)R(M) framework elements. It uses a multi-layered
# scoring approach:
#   1. Knowledge base lookup (curated marine SES connections)
#   2. ML model predictions (trained neural network, when available)
#   3. TF-IDF weighted keyword matching with synonym expansion
#   4. Negation-aware polarity detection
#
# Author: Refactored from ai_isa_assistant_module.R
# Date: 2026-01-04 (ML integration: 2026-03-14)
# Dependencies: Base R only (no Shiny, no reactivity)
#   Optional: functions/ml_inference.R (for ML scoring)
#   Optional: data/ses_connection_knowledge_base.R (for knowledge base)

# ==============================================================================
# POLARITY DETECTION (Enhanced with negation + knowledge base)
# ==============================================================================

#' Detect Connection Polarity
#'
#' Determines whether a connection between two elements is positive (+) or
#' negative (-) based on:
#'   1. Knowledge base lookup (highest priority)
#'   2. Negation-aware phrase analysis
#'   3. Compound phrase handling (e.g., "pollution reduction" = positive)
#'   4. DAPSI(W)R(M) framework rules
#'   5. Keyword matching (fallback)
#'
#' @param from_name Character string of source element name
#' @param to_name Character string of target element name
#' @param from_type Character string of source element type
#'   (drivers, activities, pressures, states, impacts, welfare, responses)
#' @param to_type Character string of target element type
#'
#' @return Character: "+" (positive/increasing) or "-" (negative/decreasing)
#'
#' @details
#' Polarity detection uses a layered approach:
#' - Knowledge base: Returns known polarity from published case studies
#' - Negation detection: Handles "no", "without", "prevent", "reduce", "ban on"
#' - Compound phrases: "pollution reduction" -> positive (reducing negative)
#' - Framework rules: e.g., Responses -> Pressures is typically "-"
#' - Keywords: Matching for negative/positive impacts (fallback)
#'
#' @examples
#' \dontrun{
#' detect_polarity("Fishing", "Fish_Stocks", "activities", "states")
#' # Returns: "-" (fishing decreases fish stocks)
#'
#' detect_polarity("Protection", "Biodiversity", "responses", "states")
#' # Returns: "+" (protection increases biodiversity)
#'
#' detect_polarity("Pollution reduction", "Water quality", "responses", "pressures")
#' # Returns: "-" (response reduces pressure)
#' }
#'
#' @export
detect_polarity <- function(from_name, to_name, from_type, to_type) {
  # ---- Step 1: Knowledge base lookup (highest confidence) ----
  if (exists("lookup_knowledge_base", mode = "function")) {
    kb_result <- tryCatch(
      lookup_knowledge_base(from_name, from_type, to_name, to_type),
      error = function(e) NULL
    )
    if (!is.null(kb_result) && !is.null(kb_result$polarity)) {
      debug_log(sprintf("Polarity from knowledge base: %s -> %s = '%s' (source: %s)",
                         from_name, to_name, kb_result$polarity, kb_result$source),
                "AI ISA CONNECTIONS")
      return(kb_result$polarity)
    }
  }

  # ---- Step 2: Negation-aware phrase analysis ----
  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  # Analyze both element names for negation and compound phrases
  from_analysis <- .analyze_polarity_phrase(from_lower)
  to_analysis <- .analyze_polarity_phrase(to_lower)

  # Keywords that suggest negative impacts/changes
  negative_keywords <- c(
    "declin", "degrad", "loss", "reduc", "damag", "destruct", "pollut",
    "eutrophic", "overfish", "bycatch", "invasive", "extinct", "harm",
    "contaminat", "erosion", "acidific", "hypox", "dead zone", "bleach",
    "disease", "mortality", "collapse", "fragment", "depletion"
  )

  # Keywords that suggest positive changes
  positive_keywords <- c(
    "increas", "growth", "restor", "recover", "improv", "enhanc", "protect",
    "conserv", "benefit", "health", "sustain", "resilient", "biodiver",
    "abundance", "productiv", "regenerat", "rehabilit", "rebui"
  )

  # Keywords for mitigation/reduction actions
  mitigation_keywords <- c(
    "ban", "prohibit", "restrict", "limit", "regulat", "control", "manag",
    "reduce", "prevent", "mitigat", "protect", "enforce", "monitor",
    "stop", "remov", "clean", "treat"
  )

  # Check characteristics of target element
  to_is_negative <- any(sapply(negative_keywords, function(kw) grepl(kw, to_lower)))
  to_is_positive <- any(sapply(positive_keywords, function(kw) grepl(kw, to_lower)))

  # Check if source is a mitigation action
  from_is_mitigation <- any(sapply(mitigation_keywords, function(kw) grepl(kw, from_lower)))

  # ---- Step 3: Framework-specific rules with negation awareness ----

  # Special case: Response Measures -> Pressures
  if (from_type == "responses" && to_type == "pressures") {
    # Response measures typically reduce pressures
    return("-")
  }

  # Special case: Response Measures -> States
  if (from_type == "responses" && to_type == "states") {
    if (to_is_negative) {
      return("-")  # Reduces bad state
    } else if (to_is_positive) {
      return("+")  # Increases good state
    }
    return("+")  # Default: responses improve states
  }

  # Activities -> Pressures
  if (from_type == "activities" && to_type == "pressures") {
    # If the activity is a mitigation/reduction activity, it reduces pressure
    if (from_is_mitigation || from_analysis$sentiment == "positive") {
      return("-")
    }
    # Activities generally cause pressures
    return("+")
  }

  # Pressures -> States
  if (from_type == "pressures" && to_type == "states") {
    if (to_is_negative) {
      return("+")  # Pressure increases negative state
    } else if (to_is_positive) {
      return("-")  # Pressure decreases positive state
    }
    return("-")  # Default: pressures degrade states
  }

  # States -> Impacts
  if (from_type == "states" && to_type == "impacts") {
    from_is_negative <- any(sapply(negative_keywords, function(kw) grepl(kw, from_lower)))
    from_is_positive <- any(sapply(positive_keywords, function(kw) grepl(kw, from_lower)))

    # Account for negation in element names
    if (from_analysis$negated && from_is_negative) from_is_negative <- FALSE
    if (to_analysis$negated && to_is_negative) to_is_negative <- FALSE

    if ((from_is_negative && to_is_negative) || (from_is_positive && to_is_positive)) {
      return("+")
    } else if ((from_is_negative && to_is_positive) || (from_is_positive && to_is_negative)) {
      return("-")
    }
    return("-")  # Default: degraded states reduce services
  }

  # Impacts -> Welfare
  if (from_type == "impacts" && to_type == "welfare") {
    from_is_negative <- any(sapply(negative_keywords, function(kw) grepl(kw, from_lower)))
    from_is_positive <- any(sapply(positive_keywords, function(kw) grepl(kw, from_lower)))

    # Account for negation
    if (from_analysis$negated && from_is_negative) from_is_negative <- FALSE

    if (from_is_negative) {
      return("-")
    } else if (from_is_positive) {
      return("+")
    }
    return("-")  # Default: impacts reduce welfare
  }

  # Default fallback
  return("+")
}


#' Analyze a phrase for polarity with negation detection (internal)
#'
#' Lightweight version of analyze_phrase_polarity for use within detect_polarity.
#' Falls back to the full knowledge base version if available.
#'
#' @param phrase_lower Lowercase phrase to analyze
#' @return List with sentiment, negated, base_sentiment
#' @keywords internal
.analyze_polarity_phrase <- function(phrase_lower) {
  # Use the full knowledge base function if available

  if (exists("analyze_phrase_polarity", mode = "function")) {
    return(tryCatch(
      analyze_phrase_polarity(phrase_lower),
      error = function(e) list(sentiment = "neutral", negated = FALSE, base_sentiment = "neutral")
    ))
  }

  # Inline fallback (minimal negation detection)
  negation_words <- c("\\bno\\b", "\\bnot\\b", "\\bnon[- ]", "\\bwithout\\b",
                       "\\bprevent", "\\bban\\b", "\\breduc", "\\bremov",
                       "\\bcontrol", "\\blimit", "\\brestrict")

  has_negation <- any(sapply(negation_words, function(p) grepl(p, phrase_lower, perl = TRUE)))

  # Reversal compounds (negation of negative = positive)
  reversal_compounds <- c("pollut.*reduc", "emission.*reduc", "pressure.*reduc",
                           "litter.*reduc", "waste.*reduc", "noise.*reduc",
                           "overfish.*prevent", "erosion.*control")
  is_reversal <- any(sapply(reversal_compounds, function(p) grepl(p, phrase_lower, perl = TRUE)))

  if (is_reversal) {
    return(list(sentiment = "positive", negated = TRUE, base_sentiment = "negative"))
  }

  return(list(sentiment = "neutral", negated = has_negation, base_sentiment = "neutral"))
}


# ==============================================================================
# RELEVANCE CALCULATION (Enhanced with KB + ML + TF-IDF)
# ==============================================================================

#' Calculate Semantic Relevance Between Elements
#'
#' Calculates a relevance score (0-1) between two elements using a multi-layered
#' approach:
#'   1. Knowledge base lookup (highest confidence)
#'   2. ML model prediction (when available)
#'   3. TF-IDF weighted keyword matching with synonym expansion
#'
#' @param from_name Character string of source element name
#' @param to_name Character string of target element name
#' @param from_type Character string of source element type
#' @param to_type Character string of target element type
#'
#' @return Numeric relevance score between 0 and 1
#'
#' @details
#' The scoring layers are combined as follows:
#' - If ML model is available: 0.3 * keyword_score + 0.7 * ml_score
#' - If knowledge base matches: uses KB probability directly
#' - Otherwise: TF-IDF weighted keyword matching with synonym bonus
#'
#' @examples
#' \dontrun{
#' calculate_relevance("Commercial Fishing", "Overfishing", "activities", "pressures")
#' # Returns: ~0.93 (knowledge base match)
#'
#' calculate_relevance("Tourism", "Fish Decline", "activities", "pressures")
#' # Returns: ~0.3 (low relevance - no keyword matches)
#' }
#'
#' @export
calculate_relevance <- function(from_name, to_name, from_type, to_type) {
  # ---- Step 1: Try enhanced relevance with knowledge base + TF-IDF ----
  if (exists("calculate_enhanced_relevance", mode = "function")) {
    keyword_relevance <- tryCatch(
      calculate_enhanced_relevance(from_name, to_name, from_type, to_type),
      error = function(e) {
        debug_log(sprintf("Enhanced relevance failed: %s, using basic", e$message),
                  "AI ISA CONNECTIONS")
        NULL
      }
    )
  } else {
    keyword_relevance <- NULL
  }

  # Fallback to basic keyword matching if enhanced is not available
  if (is.null(keyword_relevance)) {
    keyword_relevance <- .calculate_basic_relevance(from_name, to_name, from_type, to_type)
  }

  # ---- Step 2: ML scoring (optional, highest-quality signal) ----
  ml_score <- NULL
  if (exists("predict_connection_ml", mode = "function") &&
      exists("ml_model_available", mode = "function")) {
    if (ml_model_available()) {
      tryCatch({
        ml_result <- predict_connection_ml(
          source_name = from_name,
          target_name = to_name,
          source_type = from_type,
          target_type = to_type
        )
        if (!is.null(ml_result) && !is.null(ml_result$existence_probability)) {
          ml_score <- ml_result$existence_probability  # 0-1 probability
          debug_log(sprintf("ML score for %s -> %s: %.3f (method: %s)",
                            from_name, to_name, ml_score,
                            ml_result$method %||% "unknown"),
                    "AI ISA CONNECTIONS")
        }
      }, error = function(e) {
        debug_log(sprintf("ML scoring failed for %s -> %s: %s",
                          from_name, to_name, e$message),
                  "AI ISA CONNECTIONS")
      })
    }
  }

  # ---- Step 3: Combine scores ----
  if (!is.null(ml_score)) {
    # ML-weighted combination: ML signal is more reliable when available
    relevance <- 0.3 * keyword_relevance + 0.7 * ml_score
    debug_log(sprintf("Combined relevance for %s -> %s: %.3f (kw=%.3f, ml=%.3f)",
                      from_name, to_name, relevance, keyword_relevance, ml_score),
              "AI ISA CONNECTIONS")
  } else {
    relevance <- keyword_relevance  # Fallback to keyword/KB only
  }

  return(relevance)
}


#' Basic keyword-based relevance calculation (fallback)
#'
#' Original bag-of-words approach used when knowledge base and ML are not
#' available. Kept as a reliable fallback.
#'
#' @param from_name Character string of source element name
#' @param to_name Character string of target element name
#' @param from_type Character string of source element type
#' @param to_type Character string of target element type
#'
#' @return Numeric relevance score between 0 and 1
#' @keywords internal
.calculate_basic_relevance <- function(from_name, to_name, from_type, to_type) {
  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  # Keywords that suggest strong relationships
  connection_keywords <- list(
    drivers_activities = c("fish", "food", "econom", "livelihood", "subsistence",
                           "commerc", "industr", "recreat", "tourism", "develop",
                           "demand", "need", "cultural", "spiritual"),
    activities_pressures = c("fish", "extract", "harvest", "develop", "construct",
                              "pollut", "discharge", "emission", "waste", "noise",
                              "disturb", "remov", "introduc", "invasive"),
    pressures_states = c("pollut", "nutrient", "contamin", "extract", "remov",
                          "habitat", "species", "abundance", "diversity", "structure",
                          "function", "ecosystem", "chemical", "physical", "biological"),
    states_impacts = c("decline", "loss", "degrad", "change", "abundance",
                        "diversity", "habitat", "ecosystem", "service", "provision",
                        "regulat", "cultural", "support"),
    impacts_welfare = c("food", "protein", "nutrition", "income", "livelihood",
                         "employ", "health", "wellbeing", "recreation", "cultural",
                         "spiritual", "aesthetic", "economic", "social"),
    responses_pressures = c("regulat", "protect", "conserv", "restor", "manag",
                             "monitor", "enforc", "limit", "restrict", "ban",
                             "quota", "closure", "zone", "designation"),
    welfare_responses = c("concern", "awareness", "demand", "advocacy", "pressure",
                           "policy", "legislation", "management", "action",
                           "intervention"),
    responses_drivers = c("policy", "awareness", "education", "incentiv", "subsid",
                           "tax", "regulation", "enforcement", "behavior", "demand"),
    responses_activities = c("limit", "restrict", "ban", "regulat", "control",
                              "manage", "permit", "license", "quota", "closure",
                              "zone")
  )

  # Get relevant keywords for this connection type
  key <- paste(from_type, to_type, sep = "_")
  keywords <- connection_keywords[[key]]

  if (is.null(keywords)) return(0.5)  # Default moderate relevance

  # Count keyword matches
  from_matches <- sum(sapply(keywords, function(kw) grepl(kw, from_lower)))
  to_matches <- sum(sapply(keywords, function(kw) grepl(kw, to_lower)))

  # Calculate relevance score (0-1)
  total_matches <- from_matches + to_matches
  if (total_matches == 0) return(0.3)  # Low relevance
  if (total_matches == 1) return(0.6)  # Moderate relevance
  return(0.9)  # High relevance
}

# ==============================================================================
# SMART CONNECTION GENERATION
# ==============================================================================

#' Generate Smart Connections Between Element Sets
#'
#' Generates filtered and ranked connections between two sets of elements
#' using a multi-layered scoring approach:
#'   1. Knowledge base + TF-IDF keyword relevance scoring
#'   2. ML model predictions (when available, weighted 70%)
#'   3. Negation-aware polarity detection
#'   4. Knowledge base polarity lookup
#'
#' @param from_elements List of source elements (each with $name attribute)
#' @param to_elements List of target elements (each with $name attribute)
#' @param from_type Character string of source element type
#' @param to_type Character string of target element type
#' @param matrix_name Character string identifying the connection matrix
#' @param max_count Integer maximum number of connections to return
#' @param min_relevance Numeric minimum relevance threshold (0-1)
#'
#' @return List of connection objects, sorted by relevance (highest first)
#'
#' @details
#' Each connection object contains:
#' - from_type, from_index, from_name
#' - to_type, to_index, to_name
#' - polarity ("+"/"-")
#' - strength ("weak"/"medium"/"strong")
#' - confidence (1-5)
#' - rationale (human-readable description)
#' - matrix (connection matrix identifier)
#' - scoring_method ("ml+kb", "kb", "keyword")
#'
#' The function filters out low-relevance connections and returns only the
#' top-ranked suggestions up to max_count.
#'
#' @examples
#' \dontrun{
#' drivers <- list(list(name = "Economic Growth"), list(name = "Population Growth"))
#' activities <- list(list(name = "Commercial Fishing"), list(name = "Tourism"))
#' connections <- generate_smart_connections(
#'   drivers, activities, "drivers", "activities", "d_a", max_count = 15, min_relevance = 0.3
#' )
#' }
#'
#' @export
generate_smart_connections <- function(from_elements, to_elements, from_type, to_type, matrix_name, max_count, min_relevance) {
  candidates <- list()

  # Keywords indicating negative states/losses - used to filter double-negative connections
  loss_keywords <- c(
    "loss", "decline", "declin", "degrad", "reduc", "damag", "destruct",
    "decreas", "diminish", "deplet", "erosion", "collapse", "extinct",
    "mortality", "death", "disappear", "absent", "lack", "scarcity"
  )

  for (i in seq_along(from_elements)) {
    for (j in seq_along(to_elements)) {
      from_name <- from_elements[[i]]$name
      to_name <- to_elements[[j]]$name

      relevance <- calculate_relevance(from_name, to_name, from_type, to_type)
      if (relevance >= min_relevance) {
        # FILTER: Skip double-negative connections (loss -> loss)
        from_lower <- tolower(from_name)
        to_lower <- tolower(to_name)
        from_is_loss <- any(sapply(loss_keywords, function(kw) grepl(kw, from_lower)))
        to_is_loss <- any(sapply(loss_keywords, function(kw) grepl(kw, to_lower)))

        if (from_is_loss && to_is_loss) {
          debug_log(sprintf("Skipping double-negative connection: '%s' -> '%s'",
                     from_name, to_name), "AI ISA CONNECTIONS")
          next  # Skip this connection
        }

        polarity <- detect_polarity(from_name, to_name, from_type, to_type)

        # Determine strength from knowledge base or ML if available
        strength <- "medium"
        confidence <- 3
        delay_category <- NA_character_
        scoring_method <- "keyword"

        # Check knowledge base for strength info and temporal lag
        if (exists("lookup_knowledge_base", mode = "function")) {
          kb_match <- tryCatch(
            lookup_knowledge_base(from_name, from_type, to_name, to_type),
            error = function(e) NULL
          )
          if (!is.null(kb_match)) {
            strength <- kb_match$strength %||% "medium"
            scoring_method <- "kb"
            # Adjust confidence based on match quality
            confidence <- switch(kb_match$match_quality %||% "exact",
              "exact"   = 4,
              "synonym" = 3,
              3
            )
            # Extract delay category if available
            if (!is.null(kb_match$temporal_lag)) {
              delay_category <- switch(tolower(kb_match$temporal_lag),
                "immediate" = "immediate",
                "short-term" = "short-term",
                "medium-term" = "medium-term",
                "long-term" = "long-term",
                NA_character_
              )
            }
          }
        }

        # ML can further refine confidence
        if (exists("ml_model_available", mode = "function") && ml_model_available()) {
          scoring_method <- if (scoring_method == "kb") "ml+kb" else "ml"
          # ML already factored into relevance score; use relevance for confidence
          if (relevance >= 0.85) {
            confidence <- max(confidence, 4)
          } else if (relevance >= 0.7) {
            confidence <- max(confidence, 3)
          }
        }

        # Choose appropriate verb based on connection type
        verb <- if (from_type == "drivers") {
          "drives"
        } else if (from_type == "activities") {
          if (polarity == "+") "increases" else "causes"
        } else if (from_type == "pressures") {
          if (polarity == "+") "increases" else "decreases"
        } else if (from_type == "states") {
          "impacts"
        } else if (from_type == "impacts") {
          if (polarity == "+") "increases" else "reduces"
        } else if (from_type == "responses") {
          if (polarity == "-") "restricts" else "enables"
        } else if (from_type == "welfare") {
          if (polarity == "+") "motivates" else "reduces"
        } else {
          if (polarity == "+") "affects positively" else "affects negatively"
        }

        candidates[[length(candidates) + 1]] <- list(
          conn = list(
            from_type = from_type,
            from_index = i,
            from_name = from_name,
            to_type = to_type,
            to_index = j,
            to_name = to_name,
            polarity = polarity,
            strength = strength,
            confidence = confidence,
            delay = delay_category,
            delay_years = NA_real_,
            rationale = paste(from_name, verb, to_name),
            matrix = matrix_name,
            scoring_method = scoring_method
          ),
          relevance = relevance
        )
      }
    }
  }

  # Sort by relevance and return top connections
  if (length(candidates) > 0) {
    candidates <- candidates[order(sapply(candidates, function(x) x$relevance), decreasing = TRUE)]
    n_to_return <- min(length(candidates), max_count)
    result <- lapply(1:n_to_return, function(i) candidates[[i]]$conn)

    # Log scoring method distribution
    methods <- sapply(result, function(c) c$scoring_method %||% "keyword")
    method_counts <- table(methods)
    method_str <- paste(names(method_counts), method_counts, sep = ":", collapse = " ")

    debug_log(sprintf("Generated %d %s->%s connections (from %d candidates, %.0f%% filtered) [methods: %s]",
                n_to_return, toupper(substring(from_type, 1, 1)), toupper(substring(to_type, 1, 1)),
                length(candidates), (1 - n_to_return/length(candidates)) * 100, method_str),
              "AI ISA CONNECTIONS")
    return(result)
  }

  debug_log(sprintf("No relevant %s->%s connections found", from_type, to_type), "AI ISA CONNECTIONS")
  return(list())
}

# ==============================================================================
# ADJACENCY MATRIX CONVERSION
# ==============================================================================

#' Convert Adjacency Matrices to Connection List
#'
#' Converts adjacency matrix representation to a list of connection objects.
#' Used when loading connections from saved ISA data format.
#'
#' @param matrices List of adjacency matrices (named by matrix type)
#' @param elements List of element collections (drivers, activities, etc.)
#'
#' @return List of connection objects parsed from matrix cells
#'
#' @details
#' Matrix cell format: "+strong:5" or "-medium:3"
#' - First character: polarity (+/-)
#' - Middle part: strength (weak/medium/strong)
#' - After colon: confidence level (1-5)
#'
#' Supported matrices:
#' - d_a: Drivers -> Activities
#' - a_p: Activities -> Pressures
#' - p_mpf: Pressures -> States
#' - mpf_es: States -> Impacts
#' - es_gb: Impacts -> Welfare
#' - gb_d: Welfare -> Drivers
#' - gb_r: Welfare -> Responses
#' - r_d: Responses -> Drivers
#' - r_a: Responses -> Activities
#' - r_p: Responses -> Pressures
#'
#' @examples
#' \dontrun{
#' # Matrix with format: "+strong:5"
#' matrices <- list(d_a = matrix(c("+medium:4", "", "", "-weak:2"), nrow = 2))
#' elements <- list(
#'   drivers = list(list(name = "Growth"), list(name = "Policy")),
#'   activities = list(list(name = "Fishing"), list(name = "Tourism"))
#' )
#' connections <- convert_matrices_to_connections(matrices, elements)
#' }
#'
#' @export
convert_matrices_to_connections <- function(matrices, elements) {
  connections <- list()

  # Matrix mapping: matrix_name -> list(from_type, to_type, from_list, to_list)
  matrix_map <- list(
    d_a = list(from_type = "drivers", to_type = "activities", from = elements$drivers, to = elements$activities),
    a_p = list(from_type = "activities", to_type = "pressures", from = elements$activities, to = elements$pressures),
    p_mpf = list(from_type = "pressures", to_type = "states", from = elements$pressures, to = elements$states),
    mpf_es = list(from_type = "states", to_type = "impacts", from = elements$states, to = elements$impacts),
    es_gb = list(from_type = "impacts", to_type = "welfare", from = elements$impacts, to = elements$welfare),
    gb_d = list(from_type = "welfare", to_type = "drivers", from = elements$welfare, to = elements$drivers),
    gb_r = list(from_type = "welfare", to_type = "responses", from = elements$welfare, to = elements$responses),
    r_d = list(from_type = "responses", to_type = "drivers", from = elements$responses, to = elements$drivers),
    r_a = list(from_type = "responses", to_type = "activities", from = elements$responses, to = elements$activities),
    r_p = list(from_type = "responses", to_type = "pressures", from = elements$responses, to = elements$pressures),
    r_mpf = list(from_type = "responses", to_type = "states", from = elements$responses, to = elements$states),
    r_r = list(from_type = "responses", to_type = "responses", from = elements$responses, to = elements$responses),
    p_p = list(from_type = "pressures", to_type = "pressures", from = elements$pressures, to = elements$pressures),
    s_s = list(from_type = "states", to_type = "states", from = elements$states, to = elements$states)
  )

  for (matrix_name in names(matrices)) {
    # Skip if not in our map
    if (!matrix_name %in% names(matrix_map)) next

    mat <- matrices[[matrix_name]]
    map_info <- matrix_map[[matrix_name]]

    # Skip if elements lists are empty
    if (is.null(map_info$from) || is.null(map_info$to) ||
        length(map_info$from) == 0 || length(map_info$to) == 0) next

    # Loop through matrix cells
    for (i in seq_len(nrow(mat))) {
      for (j in 1:ncol(mat)) {
        value <- mat[i, j]
        # Skip empty cells
        if (is.null(value) || is.na(value) || value == "" || trimws(value) == "") next

        # Parse value (format: "+strong:5" or "-medium:3")
        polarity <- "+"
        strength <- "medium"
        confidence <- 3

        if (grepl("^[+-]", value)) {
          polarity <- substr(value, 1, 1)
          rest <- substr(value, 2, nchar(value))

          # Extract strength and confidence
          if (grepl(":", rest)) {
            parts <- strsplit(rest, ":")[[1]]
            strength <- parts[1]
            if (length(parts) > 1) {
              confidence <- as.integer(parts[2])
            }
          } else {
            strength <- rest
          }
        }

        # Create connection object
        connections[[length(connections) + 1]] <- list(
          from_type = map_info$from_type,
          from_index = i,
          from_name = map_info$from[[i]]$name,
          to_type = map_info$to_type,
          to_index = j,
          to_name = map_info$to[[j]]$name,
          polarity = polarity,
          strength = strength,
          confidence = confidence,
          rationale = paste(map_info$from[[i]]$name,
                          if(polarity == "+") "increases" else "decreases",
                          map_info$to[[j]]$name),
          matrix = matrix_name
        )
      }
    }
  }

  debug_log(sprintf("Converted %d connections from %d matrices",
              length(connections), length(matrices)), "AI ISA")
  return(connections)
}

# ==============================================================================
# MAIN CONNECTION GENERATION ORCHESTRATOR
# ==============================================================================

#' Generate All Connections for DAPSI(W)R(M) Framework
#'
#' Main orchestrator function that generates all logical connections between
#' element types based on the DAPSI(W)R(M) framework structure.
#'
#' @param elements List containing all 7 element types:
#'   - drivers: Economic/social drivers
#'   - activities: Human activities
#'   - pressures: Environmental pressures
#'   - states: Ecosystem state changes
#'   - impacts: Impacts on ecosystem services
#'   - welfare: Human welfare impacts
#'   - responses: Management responses
#'
#' @return List of all generated connection objects
#'
#' @details
#' Generates connections for 10 connection types:
#' - Forward chain: D->A->P->S->I->W
#' - Response interventions: R->P, R->D, R->A
#' - Feedback loops: W->D, W->R
#'
#' Default limits:
#' - MAX_PER_TYPE: 15 connections per type (max 150 total)
#' - MIN_RELEVANCE: 0.3 (30% relevance threshold)
#'
#' Scoring layers (in order of priority):
#' 1. ML model predictions (70% weight when available)
#' 2. Knowledge base lookup (curated marine SES connections)
#' 3. TF-IDF weighted keyword matching with synonym expansion
#'
#' @examples
#' \dontrun{
#' elements <- list(
#'   drivers = list(list(name = "Economic Growth")),
#'   activities = list(list(name = "Fishing")),
#'   pressures = list(list(name = "Overfishing")),
#'   states = list(list(name = "Fish Stock Decline")),
#'   impacts = list(list(name = "Reduced Fish Provisioning")),
#'   welfare = list(list(name = "Food Security Loss")),
#'   responses = list(list(name = "Fishing Quotas"))
#' )
#' connections <- generate_connections(elements)
#' }
#'
#' @export
generate_connections <- function(elements, regional_sea = NULL, habitat = NULL) {
  connections <- list()
  MAX_PER_TYPE <- 15  # Reduced limit for better quality (10 types x 15 = max 150 total)
  MIN_RELEVANCE <- 0.3  # Lower threshold to ensure core DAPSIWR connections are generated

  # Per-type counters
  count_da <- 0  # Drivers -> Activities
  count_ap <- 0  # Activities -> Pressures
  count_ps <- 0  # Pressures -> States
  count_si <- 0  # States -> Impacts
  count_iw <- 0  # Impacts -> Welfare
  count_rp <- 0  # Responses -> Pressures
  count_wd <- 0  # Welfare -> Drivers (feedback)
  count_wr <- 0  # Welfare -> Responses (feedback)
  count_rd <- 0  # Responses -> Drivers (feedback)
  count_ra <- 0  # Responses -> Activities (feedback)

  # Log ML availability status
  ml_status <- if (exists("ml_model_available", mode = "function") && ml_model_available()) {
    "ML model ACTIVE"
  } else {
    "ML model not available (using KB + keywords)"
  }
  kb_status <- if (exists("SES_CONNECTION_DB") && length(SES_CONNECTION_DB) > 0) {
    sprintf("Knowledge base ACTIVE (%d entries)", length(SES_CONNECTION_DB))
  } else {
    "Knowledge base not loaded"
  }

  debug_log(sprintf("Generating connections (max %d per type)...", MAX_PER_TYPE), "AI ISA CONNECTIONS")
  debug_log(sprintf("Scoring: %s | %s", ml_status, kb_status), "AI ISA CONNECTIONS")
  debug_log(sprintf("Element counts: D=%d, A=%d, P=%d, S=%d, I=%d, W=%d, R=%d",
              length(elements$drivers %||% list()),
              length(elements$activities %||% list()),
              length(elements$pressures %||% list()),
              length(elements$states %||% list()),
              length(elements$impacts %||% list()),
              length(elements$welfare %||% list()),
              length(elements$responses %||% list())), "AI ISA CONNECTIONS")

  # Debug: Print actual element names
  if (length(elements$drivers) > 0) {
    debug_log(sprintf("Drivers: %s", paste(sapply(elements$drivers, function(x) x$name), collapse=", ")), "AI ISA CONNECTIONS")
  }
  if (length(elements$activities) > 0) {
    debug_log(sprintf("Activities: %s", paste(sapply(elements$activities, function(x) x$name), collapse=", ")), "AI ISA CONNECTIONS")
  }

  # ========================================================================
  # SEED: Knowledge Database Connections (highest confidence)
  # ========================================================================
  # If a regional_sea and habitat context is available, seed connections
  # from the JSON knowledge database. These are pre-validated, ecologically
  # plausible connections with curated polarity, strength, and rationale.
  kb_seeded <- 0
  kb_seeded_keys <- character(0)  # Track seeded connections to avoid duplicates

  if (!is.null(regional_sea) && !is.null(habitat) &&
      exists("ses_knowledge_db_available", mode = "function") &&
      ses_knowledge_db_available()) {
    tryCatch({
      kb_connections <- get_context_connections(regional_sea, habitat)
      if (length(kb_connections) > 0) {
        # Build a name lookup for elements (lowercase name -> index per type)
        element_index <- list()
        for (etype in c("drivers", "activities", "pressures", "states", "impacts", "welfare", "responses")) {
          el_list <- elements[[etype]] %||% list()
          if (length(el_list) > 0) {
            element_index[[etype]] <- setNames(
              seq_along(el_list),
              tolower(sapply(el_list, function(x) x$name))
            )
          }
        }

        # Matrix name mapping for DAPSI(W)R(M) connection types
        matrix_map <- list(
          "drivers_activities" = "d_a", "activities_pressures" = "a_p",
          "pressures_states" = "p_mpf", "states_impacts" = "mpf_es",
          "impacts_welfare" = "es_gb", "welfare_drivers" = "gb_d",
          "welfare_responses" = "gb_r", "responses_drivers" = "r_d",
          "responses_activities" = "r_a", "responses_pressures" = "r_p",
          "responses_states" = "r_mpf", "responses_responses" = "r_r",
          "pressures_pressures" = "p_p", "states_states" = "s_s"
        )

        for (kb_conn in kb_connections) {
          from_type <- kb_conn$from_type
          to_type <- kb_conn$to_type
          from_name <- kb_conn$from
          to_name <- kb_conn$to

          if (is.null(from_type) || is.null(to_type) ||
              is.null(from_name) || is.null(to_name)) next

          # Find matching elements by name (case-insensitive partial match)
          from_idx <- NULL
          to_idx <- NULL

          from_lookup <- element_index[[from_type]]
          to_lookup <- element_index[[to_type]]
          if (is.null(from_lookup) || is.null(to_lookup)) next

          # Exact match first, then partial
          from_lower <- tolower(from_name)
          to_lower <- tolower(to_name)

          if (from_lower %in% names(from_lookup)) {
            from_idx <- from_lookup[[from_lower]]
          } else {
            # Partial match: check if any element name is contained in or contains the KB name
            for (nm in names(from_lookup)) {
              if (grepl(nm, from_lower, fixed = TRUE) || grepl(from_lower, nm, fixed = TRUE)) {
                from_idx <- from_lookup[[nm]]
                from_name <- elements[[from_type]][[from_idx]]$name
                break
              }
            }
          }

          if (to_lower %in% names(to_lookup)) {
            to_idx <- to_lookup[[to_lower]]
          } else {
            for (nm in names(to_lookup)) {
              if (grepl(nm, to_lower, fixed = TRUE) || grepl(to_lower, nm, fixed = TRUE)) {
                to_idx <- to_lookup[[nm]]
                to_name <- elements[[to_type]][[to_idx]]$name
                break
              }
            }
          }

          if (is.null(from_idx) || is.null(to_idx)) next

          # Determine matrix name
          type_key <- paste(from_type, to_type, sep = "_")
          mat_name <- matrix_map[[type_key]] %||% type_key

          conn_key <- paste(from_type, from_idx, to_type, to_idx, sep = "_")
          kb_seeded_keys <- c(kb_seeded_keys, conn_key)

          connections[[length(connections) + 1]] <- list(
            from_type = from_type,
            from_index = from_idx,
            from_name = from_name,
            to_type = to_type,
            to_index = to_idx,
            to_name = to_name,
            polarity = kb_conn$polarity %||% "+",
            strength = kb_conn$strength %||% "medium",
            confidence = kb_conn$confidence %||% 4,
            rationale = kb_conn$rationale %||% paste(from_name, "affects", to_name),
            matrix = mat_name,
            scoring_method = "knowledge_db"
          )
          kb_seeded <- kb_seeded + 1
        }

        debug_log(sprintf("Seeded %d connections from SES Knowledge DB (%s/%s)",
                          kb_seeded, regional_sea, habitat), "AI ISA CONNECTIONS")
      }
    }, error = function(e) {
      debug_log(sprintf("SES KB connection seeding failed: %s", e$message), "AI ISA CONNECTIONS")
    })
  }

  # D -> A (Drivers -> Activities): Smart connection generation
  if (length(elements$drivers) > 0 && length(elements$activities) > 0) {
    new_conns <- generate_smart_connections(elements$drivers, elements$activities, "drivers", "activities", "d_a", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_da <- length(new_conns)
  }

  # A -> P (Activities -> Pressures): Smart connection generation
  if (length(elements$activities) > 0 && length(elements$pressures) > 0) {
    new_conns <- generate_smart_connections(elements$activities, elements$pressures, "activities", "pressures", "a_p", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_ap <- length(new_conns)
  }

  # P -> S (Pressures -> States): Smart connection generation
  if (length(elements$pressures) > 0 && length(elements$states) > 0) {
    new_conns <- generate_smart_connections(elements$pressures, elements$states, "pressures", "states", "p_mpf", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_ps <- length(new_conns)
  }

  # S -> I (States -> Impacts): Smart connection generation
  if (length(elements$states) > 0 && length(elements$impacts) > 0) {
    new_conns <- generate_smart_connections(elements$states, elements$impacts, "states", "impacts", "mpf_es", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_si <- length(new_conns)
  }

  # I -> W (Impacts -> Welfare): Smart connection generation
  if (length(elements$impacts) > 0 && length(elements$welfare) > 0) {
    new_conns <- generate_smart_connections(elements$impacts, elements$welfare, "impacts", "welfare", "es_gb", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_iw <- length(new_conns)
  }

  # R -> P (Responses -> Pressures): Smart connection generation
  if (length(elements$responses) > 0 && length(elements$pressures) > 0) {
    new_conns <- generate_smart_connections(elements$responses, elements$pressures, "responses", "pressures", "r_p", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_rp <- length(new_conns)
  }

  # ========================================================================
  # FEEDBACK LOOPS - Additional logical connections
  # ========================================================================

  # W -> D (Welfare -> Drivers): Smart feedback loop generation
  if (length(elements$welfare) > 0 && length(elements$drivers) > 0) {
    new_conns <- generate_smart_connections(elements$welfare, elements$drivers, "welfare", "drivers", "gb_d", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_wd <- length(new_conns)
  }

  # W -> R (Welfare -> Responses): Smart feedback loop generation
  if (length(elements$welfare) > 0 && length(elements$responses) > 0) {
    new_conns <- generate_smart_connections(elements$welfare, elements$responses, "welfare", "responses", "gb_r", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_wr <- length(new_conns)
  }

  # R -> D (Responses -> Drivers): Smart feedback loop generation
  if (length(elements$responses) > 0 && length(elements$drivers) > 0) {
    new_conns <- generate_smart_connections(elements$responses, elements$drivers, "responses", "drivers", "r_d", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_rd <- length(new_conns)
  }

  # R -> A (Responses -> Activities): Smart feedback loop generation
  if (length(elements$responses) > 0 && length(elements$activities) > 0) {
    new_conns <- generate_smart_connections(elements$responses, elements$activities, "responses", "activities", "r_a", MAX_PER_TYPE, MIN_RELEVANCE)
    connections <- c(connections, new_conns)
    count_ra <- length(new_conns)
  }

  # Log final count and per-type breakdown
  debug_log(sprintf("TOTAL GENERATED: %d connections (KB seeded: %d) | D->A:%d A->P:%d P->S:%d S->I:%d I->W:%d R->P:%d W->D:%d W->R:%d R->D:%d R->A:%d",
    length(connections), kb_seeded, count_da, count_ap, count_ps, count_si, count_iw, count_rp, count_wd, count_wr, count_rd, count_ra),
    "AI ISA CONNECTIONS")

  return(connections)
}

# ==============================================================================
# MODULE INITIALIZATION MESSAGE
# ==============================================================================

debug_log("AI ISA Connection Generator module loaded successfully", "INIT")
debug_log("Available functions: detect_polarity, calculate_relevance, generate_smart_connections, convert_matrices_to_connections, generate_connections", "INIT")
debug_log("Enhanced with: ML integration, knowledge base lookup, TF-IDF scoring, negation-aware polarity detection, synonym expansion", "INIT")
