# functions/report_generation.R
# Report Generation Helper Functions
# Purpose: Centralized functions for generating various report types

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

#' Get loop data from project data (handles both old and new storage locations)
#'
#' @param data Project data object
#' @return Dataframe of loop information or NULL
get_loop_data <- function(data) {
  # Check new location first: data$data$analysis$loops$loop_info
  if (!is.null(data$data$analysis$loops$loop_info)) {
    return(data$data$analysis$loops$loop_info)
  }
  # Fall back to legacy location: data$data$cld$loops
  if (!is.null(data$data$cld$loops)) {
    return(data$data$cld$loops)
  }
  # No loops found
  return(NULL)
}

# ============================================================================
# REPORT CONTENT GENERATION
# ============================================================================

#' Generate report content in R Markdown format
#'
#' @param data Project data object containing all SES information
#' @param report_type Type of report: "executive", "technical", "presentation", or "full"
#' @param include_viz Whether to include visualizations (currently unused)
#' @param include_data Whether to include raw data tables (currently unused)
#' @return Character string containing complete R Markdown document
generate_report_content <- function(data, report_type, include_viz = TRUE, include_data = FALSE, options = list()) {

  debug_log(sprintf("Report generation started: type=%s", report_type), "REPORT")

  # ========== YAML HEADER ==========
  # Ensure report_type is a character string, not a list
  report_type_safe <- as.character(report_type)[1]

  # Safely format the date
  report_date <- format(Sys.Date(), "%B %d, %Y")

  header <- paste0(
    "---\n",
    "title: 'MarineSABRES SES Analysis Report'\n",
    "subtitle: '", report_type_safe, " Report'\n",
    "date: '", report_date, "'\n",
    "output:\n",
    "  html_document:\n",
    "    toc: true\n",
    "    toc_float: true\n",
    "---\n\n"
  )

  # ========== PROJECT OVERVIEW SECTION ==========
  # Safely format dates (handle potential list/non-date values)
  created_date <- tryCatch({
    if (is.null(data$created_at)) {
      "Unknown"
    } else if (is.list(data$created_at)) {
      as.character(format(as.POSIXct(data$created_at[[1]]), "%Y-%m-%d"))
    } else {
      as.character(format(data$created_at, "%Y-%m-%d"))
    }
  }, error = function(e) {
    debug_log(sprintf("Error parsing created_at: %s", e$message), "REPORT")
    "Unknown"
  })

  modified_date <- tryCatch({
    if (is.null(data$last_modified)) {
      "Unknown"
    } else if (is.list(data$last_modified)) {
      as.character(format(as.POSIXct(data$last_modified[[1]]), "%Y-%m-%d"))
    } else {
      as.character(format(data$last_modified, "%Y-%m-%d"))
    }
  }, error = function(e) {
    debug_log(sprintf("Error parsing last_modified: %s", e$message), "REPORT")
    "Unknown"
  })

  # Safely extract metadata fields (handle potential list values)
  da_site <- tryCatch({
    if (is.list(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site[[1]])
    } else if (!is.null(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site)
    } else {
      "Not specified"
    }
  }, error = function(e) {
    debug_log(sprintf("Error extracting da_site: %s", e$message), "REPORT")
    "Not specified"
  })

  focal_issue <- tryCatch({
    if (is.list(data$data$metadata$focal_issue)) {
      as.character(data$data$metadata$focal_issue[[1]])
    } else if (!is.null(data$data$metadata$focal_issue)) {
      as.character(data$data$metadata$focal_issue)
    } else {
      "Not defined"
    }
  }, error = function(e) {
    debug_log(sprintf("Error extracting focal_issue: %s", e$message), "REPORT")
    "Not defined"
  })

  # ========== INTRO SECTION ==========

  # Safely extract project name to avoid list issues
  project_name <- if (!is.null(data$project_name)) {
    as.character(data$project_name)
  } else {
    "Unnamed Project"
  }

  intro <- paste0(
    "# Project Overview\n\n",
    "**Project:** ", project_name, "\n\n",
    "**Demonstration Area:** ", da_site, "\n\n",
    "**Focal Issue:** ", focal_issue, "\n\n",
    "**Created:** ", created_date, "\n\n",
    "**Last Modified:** ", modified_date, "\n\n"
  )
  # ========== REGIONAL CONTEXT (from KB) ==========
  # V1: Same full regional section for all report types.
  regional_section <- ""
  regional_sea <- data$data$metadata$regional_sea
  ecosystem_type <- data$data$metadata$ecosystem_type
  include_regional <- options$include_regional_context %||% (!is.null(regional_sea))
  if (include_regional && !is.null(regional_sea) && !is.null(ecosystem_type)) {
    tryCatch({
      kb_ctx <- get_kb_context_for_report(regional_sea, ecosystem_type)

      # Get user edges with labels for matching — resolve IDs to names via nodes
      user_edges <- tryCatch({
        if (!is.null(data$data$cld$edges)) {
          data$data$cld$edges
        } else if (!is.null(data$data$isa_data)) {
          create_edges_df(data$data$isa_data, data$data$isa_data$adjacency_matrices)
        } else {
          data.frame()
        }
      }, error = function(e) data.frame())

      if (nrow(user_edges) > 0 && !"from_label" %in% names(user_edges)) {
        nodes <- tryCatch({
          if (!is.null(data$data$cld$nodes)) data$data$cld$nodes
          else if (!is.null(data$data$isa_data)) create_nodes_df(data$data$isa_data)
          else data.frame(id = character(), label = character())
        }, error = function(e) data.frame(id = character(), label = character()))

        if (nrow(nodes) > 0 && "id" %in% names(nodes) && "label" %in% names(nodes)) {
          id_to_label <- setNames(nodes$label, nodes$id)
          user_edges$from_label <- id_to_label[user_edges$from]
          user_edges$to_label <- id_to_label[user_edges$to]
        } else {
          user_edges$from_label <- user_edges$from
          user_edges$to_label <- user_edges$to
        }
      }

      matched <- match_user_connections_to_kb(user_edges, regional_sea, ecosystem_type)
      gov <- get_governance_context(regional_sea)
      kb_body <- format_kb_section_for_report(kb_ctx, matched, gov)
      if (nchar(trimws(kb_body)) > 0) {
        regional_section <- paste0("# Regional Context\n\n", kb_body)
      }
    }, error = function(e) {
      debug_log(sprintf("Regional context generation failed: %s", e$message), "REPORT")
      # regional_section stays "" (its initialized value)
    })
  }

  # ========== REPORT TYPE-SPECIFIC CONTENT ==========
  if (report_type_safe == "executive") {
    content <- generate_executive_content(data)
  } else if (report_type_safe == "technical") {
    content <- generate_technical_content(data)
  } else if (report_type_safe == "presentation") {
    content <- generate_presentation_content(data)
  } else {
    # Default to full report; options$sections = Prepare Report checkboxes
    content <- generate_full_content(data, sections = options$sections)
  }

  # ========== FOOTER ==========
  footer <- paste0(
    "\n\n---\n\n",
    "*Report generated by MarineSABRES SES Tool*\n\n",
    "*", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "*\n"
  )

  result <- paste0(header, intro, regional_section, content, footer)
  debug_log("Report content generated successfully", "REPORT")

  return(result)
}

# ============================================================================
# REPORT TYPE-SPECIFIC CONTENT GENERATORS
# ============================================================================

#' Generate executive summary content
#'
#' @param data Project data object
#' @return Character string with executive summary content
generate_executive_content <- function(data) {
  # Count elements correctly by summing rows in each dataframe
  # Safely count each component
  count_rows <- function(df) {
    if (is.null(df)) return(0)
    if (is.data.frame(df)) return(nrow(df))
    return(0)
  }

  # Use safe_get_nested for defensive data access
  isa_data <- safe_get_nested(data, "data", "isa_data", default = list())
  n_elements <- sum(
    count_rows(isa_data$drivers),
    count_rows(isa_data$activities),
    count_rows(isa_data$pressures),
    count_rows(isa_data$marine_processes),
    count_rows(isa_data$ecosystem_services),
    count_rows(isa_data$goods_benefits),
    count_rows(isa_data$responses)
  )
  # Safely extract metadata fields
  da_site <- tryCatch({
    if (is.list(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site[[1]])
    } else if (!is.null(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site)
    } else {
      "the study area"
    }
  }, error = function(e) "the study area")

  focal_issue <- tryCatch({
    if (is.list(data$data$metadata$focal_issue)) {
      as.character(data$data$metadata$focal_issue[[1]])
    } else if (!is.null(data$data$metadata$focal_issue)) {
      as.character(data$data$metadata$focal_issue)
    } else {
      "key system issues"
    }
  }, error = function(e) "key system issues")

  # Safely count loops using helper function
  loops_data <- get_loop_data(data)
  n_loops <- if (!is.null(loops_data) && is.data.frame(loops_data)) {
    as.integer(nrow(loops_data))
  } else {
    0L
  }

  n_stakeholders <- if (!is.null(data$data$pims$stakeholders) && is.data.frame(data$data$pims$stakeholders)) {
    as.integer(nrow(data$data$pims$stakeholders))
  } else {
    0L
  }

  content <- paste0(
    "# Executive Summary\n\n",
    "This report provides a high-level overview of the social-ecological system analysis.\n\n",
    "## Key Findings\n\n",
    "- **System elements identified:** ", as.character(n_elements), "\n",
    "- **Feedback loops detected:** ", as.character(n_loops), "\n",
    "- **Stakeholders involved:** ", as.character(n_stakeholders), "\n\n",
    "## System Overview\n\n",
    "The analysis focuses on ", da_site,
    " with particular attention to ", focal_issue, ".\n\n"
  )

  return(content)
}

#' Generate technical analysis content
#'
#' @param data Project data object
#' @return Character string with technical analysis content
generate_technical_content <- function(data) {

  # Use safe_get_nested for defensive data access
  isa_data <- safe_get_nested(data, "data", "isa_data", default = list())

  # Helper to count rows safely
  safe_nrow <- function(df) {
    if (!is.null(df) && is.data.frame(df)) nrow(df) else 0
  }

  # Build sections separately to avoid if-else list issues in paste0
  drivers_section <- if (safe_nrow(isa_data$drivers) > 0) {
    paste0("Identified ", nrow(isa_data$drivers), " drivers in the system.\n\n")
  } else {
    "No drivers data available.\n\n"
  }

  activities_section <- if (safe_nrow(isa_data$activities) > 0) {
    paste0("Identified ", nrow(isa_data$activities), " activities.\n\n")
  } else {
    "No activities data available.\n\n"
  }

  pressures_section <- if (safe_nrow(isa_data$pressures) > 0) {
    paste0("Identified ", nrow(isa_data$pressures), " pressures.\n\n")
  } else {
    "No pressures data available.\n\n"
  }

  states_section <- if (safe_nrow(isa_data$marine_processes) > 0) {
    paste0("Identified ", nrow(isa_data$marine_processes), " state changes (marine processes/impacts).\n\n")
  } else {
    "No state changes data available.\n\n"
  }

  services_section <- if (safe_nrow(isa_data$ecosystem_services) > 0) {
    paste0("Identified ", nrow(isa_data$ecosystem_services), " ecosystem services.\n\n")
  } else {
    "No ecosystem services data available.\n\n"
  }

  benefits_section <- if (safe_nrow(isa_data$goods_benefits) > 0) {
    paste0("Identified ", nrow(isa_data$goods_benefits), " goods and benefits.\n\n")
  } else {
    "No goods and benefits data available.\n\n"
  }

  content <- paste0(
    "# Technical Analysis\n\n",
    "## DAPSI(W)R(M) Framework Elements\n\n",
    "### Drivers (D)\n\n",
    drivers_section,
    "### Activities (A)\n\n",
    activities_section,
    "### Pressures (P)\n\n",
    pressures_section,
    "### State Changes (S/I)\n\n",
    states_section,
    "### Ecosystem Services (W)\n\n",
    services_section,
    "### Goods & Benefits (R)\n\n",
    benefits_section
  )

  return(content)
}

# ============================================================================
# CONTEXT-SPECIFIC RECOMMENDATION GENERATORS
# ============================================================================

#' Generate context-specific strategic recommendations based on analysis outputs
#'
#' @param data Project data object
#' @param top_leverage Top leverage point nodes
#' @param high_in High in-degree nodes (Receivers)
#' @param high_out High out-degree nodes (Drivers)
#' @param high_between High betweenness nodes (Connectors)
#' @param loops_data Loop analysis dataframe
#' @return Character string with context-specific recommendations
generate_strategic_recommendations <- function(data, top_leverage, high_in, high_out, high_between, loops_data) {
  recs <- character(0)

  # Analyze top leverage points for specific recommendations
  if (!is.null(top_leverage) && is.data.frame(top_leverage) && nrow(top_leverage) > 0) {
    top_3 <- head(top_leverage, 3)
    recs <- c(recs, paste0(
      "1. **Priority Intervention Points**: Target the following high-leverage nodes:\n",
      paste(sapply(1:min(3, nrow(top_3)), function(i) {
        paste0("   - **", top_3$label[i], "**: ",
               "Leverage score ", round(top_3$leverage_score[i], 2),
               " (", top_3$in_degree[i], " influences in, ",
               top_3$out_degree[i], " influences out). ",
               if (top_3$out_degree[i] > top_3$in_degree[i]) {
                 "Strong driver - intervening here will cascade through the system."
               } else if (top_3$in_degree[i] > top_3$out_degree[i]) {
                 "Key indicator - changes here reflect broader system shifts."
               } else {
                 "Balanced influence - critical connector in the system."
               })
      }), collapse = "\n"),
      "\n\n"
    ))
  }

  # Analyze Driver nodes for specific intervention targets
  if (!is.null(high_out) && is.data.frame(high_out) && nrow(high_out) > 0) {
    driver_names <- paste(head(high_out$label, 3), collapse = ", ")
    avg_outd <- round(mean(high_out$out_degree, na.rm = TRUE), 1)
    recs <- c(recs, paste0(
      "2. **Cascading Intervention Strategy**: Focus on Driver nodes (",
      driver_names, ") which each influence an average of ", avg_outd,
      " other system elements. Interventions targeting these nodes will have ",
      "multiplicative effects across the system. Recommended actions:\n",
      "   - Conduct detailed impact assessments for each Driver node\n",
      "   - Design interventions that strengthen positive outgoing influences\n",
      "   - Monitor downstream effects after any Driver node interventions\n\n"
    ))
  }

  # Analyze Receiver nodes for monitoring strategy
  if (!is.null(high_in) && is.data.frame(high_in) && nrow(high_in) > 0) {
    receiver_names <- paste(head(high_in$label, 3), collapse = ", ")
    avg_ind <- round(mean(high_in$in_degree, na.rm = TRUE), 1)
    recs <- c(recs, paste0(
      "3. **Early Warning Monitoring System**: Establish monitoring protocols for ",
      "Receiver nodes (", receiver_names, ") which are each influenced by an average of ",
      avg_ind, " system elements. These nodes serve as sensitive indicators:\n",
      "   - Set up regular monitoring intervals for these indicators\n",
      "   - Establish baseline and threshold values for each Receiver\n",
      "   - Use changes in Receivers to detect early system shifts\n\n"
    ))
  }

  # Analyze loop composition for system dynamics recommendations
  if (!is.null(loops_data) && nrow(loops_data) > 0) {
    n_reinforcing <- sum(loops_data$Type == "Reinforcing", na.rm = TRUE)
    n_balancing <- sum(loops_data$Type == "Balancing", na.rm = TRUE)
    total_loops <- nrow(loops_data)
    pct_reinforcing <- round(n_reinforcing / total_loops * 100, 1)

    if (pct_reinforcing > 70) {
      recs <- c(recs, paste0(
        "4. **High Reinforcing Loop Alert** (", pct_reinforcing, "% of loops): ",
        "The system is heavily dominated by reinforcing feedback, indicating:\n",
        "   - High risk of rapid, accelerating changes (tipping points)\n",
        "   - Need for stabilization mechanisms to prevent runaway dynamics\n",
        "   - Recommended: Strengthen balancing feedbacks through regulatory interventions\n",
        "   - Recommended: Implement early warning systems for exponential trends\n",
        "   - Recommended: Design 'circuit breaker' interventions to interrupt acceleration\n\n"
      ))
    } else if (pct_reinforcing < 30) {
      recs <- c(recs, paste0(
        "4. **High Balancing Loop System** (", 100 - pct_reinforcing, "% balancing): ",
        "The system shows strong self-regulation, but this creates challenges:\n",
        "   - Interventions will face significant resistance from balancing mechanisms\n",
        "   - System will tend to return to previous states after disturbances\n",
        "   - Recommended: Design persistent, sustained interventions rather than one-off actions\n",
        "   - Recommended: Identify and work with balancing loops rather than against them\n",
        "   - Recommended: Focus on shifting equilibrium points rather than fighting homeostasis\n\n"
      ))
    } else {
      recs <- c(recs, paste0(
        "4. **Balanced Loop Structure** (", pct_reinforcing, "% reinforcing, ",
        100 - pct_reinforcing, "% balancing): The system shows moderate stability:\n",
        "   - Expect both change potential and self-regulation\n",
        "   - Interventions should leverage reinforcing loops for desired changes\n",
        "   - Balancing loops can be used to stabilize improvements\n",
        "   - Recommended: Map which loops affect your intervention targets\n",
        "   - Recommended: Design interventions that work with loop dynamics\n\n"
      ))
    }
  }

  # Analyze Connector nodes for resilience
  if (!is.null(high_between) && is.data.frame(high_between) && nrow(high_between) > 0) {
    connector_names <- paste(head(high_between$label, 3), collapse = ", ")
    recs <- c(recs, paste0(
      "5. **System Resilience Protection**: Protect Connector nodes (",
      connector_names, ") which bridge different parts of the system:\n",
      "   - Avoid interventions that would remove or isolate these nodes\n",
      "   - Consider these nodes when assessing intervention impacts\n",
      "   - Strengthen connections around these critical bridges\n",
      "   - Use these nodes as communication pathways for system-wide changes\n\n"
    ))
  }

  # KB-informed regional recommendations (no signature change — reads from data)
  regional_sea <- data$data$metadata$regional_sea
  ecosystem_type <- data$data$metadata$ecosystem_type
  if (!is.null(regional_sea) && !is.null(ecosystem_type)) {
    tryCatch({
      kb_ctx <- get_kb_context_for_report(regional_sea, ecosystem_type)
      if (kb_ctx$available && length(kb_ctx$top_elements) > 0) {
        top_pressures <- kb_ctx$top_elements$pressures
        top_responses <- kb_ctx$top_elements$responses
        if (!is.null(top_pressures) && length(top_pressures) > 0) {
          recs <- c(recs, paste0(
            "**Regional Management Priorities**: For ", regional_sea, " ",
            ecosystem_type, " systems, published literature highlights these key pressures: ",
            paste(head(top_pressures, 3), collapse = ", "), ".\n\n"
          ))
        }
        if (!is.null(top_responses) && length(top_responses) > 0) {
          recs <- c(recs, paste0(
            "**KB-Suggested Responses**: ",
            paste(head(top_responses, 3), collapse = ", "), ".\n\n"
          ))
        }
      }
      gov <- get_governance_context(regional_sea)
      if (gov$available && length(gov$frameworks) > 0) {
        recs <- c(recs, paste0(
          "**Relevant Governance Frameworks**: ",
          paste(gov$frameworks, collapse = ", "), ".\n\n"
        ))
      }
    }, error = function(e) {
      debug_log(sprintf("KB recommendations failed: %s", e$message), "REPORT")
    })
  }

  # If no recommendations were generated, provide a fallback message
  if (length(recs) == 0) {
    return(paste0(
      "**Note**: Context-specific strategic recommendations require:\n",
      "- Leverage point analysis to be completed\n",
      "- Loop detection analysis to be completed\n\n",
      "Please run these analyses to generate targeted recommendations.\n\n"
    ))
  }

  paste(recs, collapse = "")
}

#' Generate context-specific management recommendations based on system analysis
#'
#' @param data Project data object
#' @param nodes All CLD nodes
#' @param loops_data Loop analysis dataframe
#' @param n_stakeholders Number of stakeholders
#' @return Character string with context-specific management recommendations
generate_management_recommendations <- function(data, nodes, loops_data, n_stakeholders) {
  recs <- character(0)

  # Validate inputs
  if (is.null(nodes) || !is.data.frame(nodes) || nrow(nodes) == 0) {
    return("No network data available for generating specific recommendations.\n\n")
  }

  # Calculate network characteristics
  n_nodes <- nrow(nodes)
  n_edges <- if (!is.null(data$data$cld$edges) && is.data.frame(data$data$cld$edges)) {
    nrow(data$data$cld$edges)
  } else {
    0
  }
  density <- if (n_nodes > 1) n_edges / (n_nodes * (n_nodes - 1)) else 0

  # 1. INTERVENTION DESIGN based on network density
  if (density < 0.1) {
    recs <- c(recs, paste0(
      "1. **Intervention Design** (Sparse Network, Density: ", round(density, 3), "):\n",
      "   - The low network connectivity (", round(density * 100, 1), "% of possible connections) ",
      "suggests a modular system\n",
      "   - **Action**: Design targeted interventions for specific subsystems\n",
      "   - **Action**: Expect limited spillover effects between modules\n",
      "   - **Action**: Consider strengthening key cross-module connections if system integration is desired\n",
      "   - **Advantage**: Interventions can be tested in isolated parts with minimal system-wide risk\n\n"
    ))
  } else if (density < 0.3) {
    recs <- c(recs, paste0(
      "1. **Intervention Design** (Moderate Connectivity, Density: ", round(density, 3), "):\n",
      "   - The moderate network connectivity (", round(density * 100, 1), "% of possible connections) ",
      "suggests interconnected subsystems\n",
      "   - **Action**: Design interventions considering immediate neighbors and secondary effects\n",
      "   - **Action**: Map 2-3 step impact pathways from intervention points\n",
      "   - **Action**: Expect some spillover but not full system-wide propagation\n",
      "   - **Caution**: Monitor for unintended consequences in connected subsystems\n\n"
    ))
  } else {
    recs <- c(recs, paste0(
      "1. **Intervention Design** (High Connectivity, Density: ", round(density, 3), "):\n",
      "   - The high network connectivity (", round(density * 100, 1), "% of possible connections) ",
      "indicates a tightly coupled system\n",
      "   - **Warning**: Any intervention will likely affect the entire system\n",
      "   - **Action**: Conduct comprehensive impact assessments before any changes\n",
      "   - **Action**: Use scenario analysis to explore cascading effects\n",
      "   - **Action**: Consider pilot interventions with careful monitoring\n",
      "   - **Advantage**: System-wide changes can be achieved through strategic single interventions\n\n"
    ))
  }

  # 2. MONITORING STRATEGY based on leverage points
  if ("leverage_score" %in% names(nodes) && "in_degree" %in% names(nodes)) {
    high_leverage <- nodes[!is.na(nodes$leverage_score) & nodes$leverage_score > quantile(nodes$leverage_score, 0.75, na.rm = TRUE), ]
    high_in <- nodes[!is.na(nodes$in_degree) & nodes$in_degree >= quantile(nodes$in_degree, 0.75, na.rm = TRUE), ]

    if (!is.null(high_in) && is.data.frame(high_in) && nrow(high_in) > 0) {
      top_indicators <- paste(head(high_in$label, 5), collapse = ", ")
      avg_influences <- round(mean(high_in$in_degree, na.rm = TRUE), 1)

      recs <- c(recs, paste0(
        "2. **Monitoring Strategy** (Data-Driven Indicator Selection):\n",
        "   - Establish monitoring for the following high-sensitivity indicators:\n",
        "     ", top_indicators, "\n",
        "   - These nodes each integrate signals from an average of ", avg_influences, " system elements\n",
        "   - **Action**: Set up quarterly monitoring protocols for these specific indicators\n",
        "   - **Action**: Establish baseline values and alert thresholds\n",
        "   - **Action**: Create a dashboard tracking these nodes as system health metrics\n\n"
      ))
    }
  }

  # 3. ADAPTIVE MANAGEMENT based on loop dynamics
  if (!is.null(loops_data) && nrow(loops_data) > 0) {
    n_reinforcing <- sum(loops_data$Type == "Reinforcing", na.rm = TRUE)
    n_balancing <- sum(loops_data$Type == "Balancing", na.rm = TRUE)

    # Calculate average loop length - handle different column names
    if ("Path" %in% names(loops_data) && !all(is.na(loops_data$Path))) {
      loop_lengths <- nchar(gsub("[^→]", "", loops_data$Path)) + 1
    } else if ("Elements" %in% names(loops_data) && !all(is.na(loops_data$Elements))) {
      loop_lengths <- nchar(gsub("[^→]", "", loops_data$Elements)) + 1
    } else if ("Length" %in% names(loops_data) && !all(is.na(loops_data$Length))) {
      loop_lengths <- loops_data$Length
    } else {
      # Fallback: use default
      loop_lengths <- rep(4, nrow(loops_data))
    }
    avg_loop_length <- round(mean(loop_lengths, na.rm = TRUE), 1)

    # Handle NaN case
    if (is.nan(avg_loop_length) || is.na(avg_loop_length)) {
      avg_loop_length <- 4  # Default reasonable value
    }

    if (avg_loop_length < 4) {
      time_scale <- "rapid (days to weeks)"
    } else if (avg_loop_length < 6) {
      time_scale <- "moderate (weeks to months)"
    } else {
      time_scale <- "slow (months to years)"
    }

    recs <- c(recs, paste0(
      "3. **Adaptive Management** (Loop-Informed Strategy):\n",
      "   - System contains ", n_reinforcing, " reinforcing and ", n_balancing, " balancing loops\n",
      "   - Average loop length of ", avg_loop_length, " nodes suggests ", time_scale, " feedback response\n",
      "   - **Action**: Time intervention assessments to match feedback cycle duration\n",
      if (n_reinforcing > n_balancing) {
        paste0("   - **Critical**: Monitor for accelerating trends due to reinforcing loop dominance\n",
               "   - **Action**: Implement 'speed limits' or caps to prevent runaway dynamics\n",
               "   - **Action**: Prepare rapid response protocols for exponential changes\n")
      } else {
        paste0("   - **Action**: Plan for sustained, persistent interventions to overcome balancing resistance\n",
               "   - **Action**: Work with existing balancing loops to stabilize desired states\n",
               "   - **Action**: Shift equilibrium points rather than fighting homeostatic pressures\n")
      },
      "\n"
    ))
  }

  # 4. STAKEHOLDER ENGAGEMENT based on leverage points and stakeholder count
  if (n_stakeholders > 0 && "leverage_score" %in% names(nodes)) {
    # Order by leverage score and handle NA values
    valid_leverage <- nodes[!is.na(nodes$leverage_score), ]
    if (nrow(valid_leverage) > 0) {
      high_leverage_top5 <- head(valid_leverage[order(-valid_leverage$leverage_score), ], 5)
    } else {
      high_leverage_top5 <- head(nodes, 5)
    }

    recs <- c(recs, paste0(
      "4. **Stakeholder Engagement** (Strategic Alignment):\n",
      "   - ", n_stakeholders, " stakeholders identified in the system\n",
      "   - **Action**: Prioritize engaging stakeholders connected to top leverage points:\n",
      "     ", paste(high_leverage_top5$label, collapse = ", "), "\n",
      "   - **Action**: Use system maps to facilitate shared understanding with stakeholders\n",
      "   - **Action**: Co-design interventions with stakeholders who manage Driver nodes\n",
      "   - **Action**: Engage stakeholders as monitors for Receiver node indicators\n",
      "   - **Action**: Build stakeholder coalitions around specific leverage point interventions\n\n"
    ))
  } else if (n_stakeholders > 0) {
    recs <- c(recs, paste0(
      "4. **Stakeholder Engagement**:\n",
      "   - ", n_stakeholders, " stakeholders identified in the system\n",
      "   - **Action**: Map stakeholder interests to system components\n",
      "   - **Action**: Use participatory system mapping to build shared understanding\n",
      "   - **Action**: Identify stakeholder roles in monitoring and intervention\n\n"
    ))
  }

  # 5. NEXT STEPS - specific and actionable
  recs <- c(recs, paste0(
    "### Immediate Next Steps\n\n",
    "1. **Validation Workshop**: Convene domain experts and stakeholders to validate:\n",
    "   - The identified top leverage points and their rankings\n",
    "   - The loop pathways and their reinforcing/balancing classification\n",
    "   - The network structure and key connections\n\n",
    "2. **Intervention Design Sessions**: For the top 3 leverage points, develop:\n",
    "   - Specific intervention options (3-5 alternatives per leverage point)\n",
    "   - Theory of change mapping how interventions propagate through loops\n",
    "   - Risk assessment for unintended consequences\n",
    "   - Success metrics and monitoring indicators\n\n",
    "3. **Monitoring Protocol Development**:\n",
    "   - Establish data collection procedures for identified Receiver nodes\n",
    "   - Set baseline values and alert thresholds\n",
    "   - Create reporting dashboards for system health tracking\n",
    "   - Define monitoring frequency based on feedback loop timing\n\n",
    "4. **Pilot Intervention Selection**:\n",
    "   - Select 1-2 high-leverage, low-risk intervention points for initial testing\n",
    "   - Design monitoring to detect both intended and unintended effects\n",
    "   - Establish clear success criteria and decision points for scaling\n",
    "   - Plan adaptive management responses to unexpected outcomes\n\n",
    "5. **Stakeholder Communication Plan**:\n",
    "   - Develop system visualizations for different stakeholder audiences\n",
    "   - Schedule engagement sessions around priority leverage points\n",
    "   - Create feedback mechanisms for stakeholder input during implementation\n\n"
  ))

  paste(recs, collapse = "")
}

#' Generate stakeholder presentation content
#'
#' @param data Project data object
#' @return Character string with presentation content
generate_presentation_content <- function(data) {
  # Safely extract metadata field
  da_site <- tryCatch({
    if (is.list(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site[[1]])
    } else if (!is.null(data$data$metadata$da_site)) {
      as.character(data$data$metadata$da_site)
    } else {
      "the study area"
    }
  }, error = function(e) "the study area")

  content <- paste0(
    "# Stakeholder Presentation\n\n",
    "## System Overview\n\n",
    "This analysis examines the social-ecological system in ",
    da_site, ".\n\n",
    "## Key Insights\n\n",
    "- Multiple interconnected system components\n",
    "- Feedback loops influencing system behavior\n",
    "- Management opportunities identified\n\n",
    "## Next Steps\n\n",
    "This presentation provides a foundation for stakeholder discussions on:\n\n",
    "- System understanding and mental model alignment\n",
    "- Identification of key leverage points\n",
    "- Development of response strategies\n\n"
  )

  return(content)
}

#' Generate full analysis content
#'
#' @param data Project data object
#' @return Character string with complete analysis content
#' @param sections Prepare Report section ids to include ("summary", "isa",
#'   "cld", "metrics", "loops", "leverage", "recommendations"). NULL keeps the
#'   long-standing full report (all sections except isa and cld). Stakeholder
#'   analysis has no checkbox and is always included.
generate_full_content <- function(data, sections = NULL) {
  include <- function(id) is.null(sections) || id %in% sections

  # ========== SYSTEM OVERVIEW ==========
  n_nodes <- if (!is.null(data$data$cld$nodes) && is.data.frame(data$data$cld$nodes)) {
    as.integer(nrow(data$data$cld$nodes))
  } else {
    0L
  }

  n_edges <- if (!is.null(data$data$cld$edges) && is.data.frame(data$data$cld$edges)) {
    as.integer(nrow(data$data$cld$edges))
  } else {
    0L
  }

  # Get loop count using helper function
  loops_data <- get_loop_data(data)
  n_loops <- if (!is.null(loops_data) && is.data.frame(loops_data)) {
    as.integer(nrow(loops_data))
  } else {
    0L
  }

  # Calculate network density separately to avoid if-else in paste0
  network_density <- if (n_nodes > 1) {
    as.character(round(n_edges / (n_nodes * (n_nodes - 1)), 3))
  } else {
    "0"
  }

  title_section <- "# Complete SES Analysis Report\n\n"
  overview_section <- paste0(
    "## Executive Summary\n\n",
    "This report presents a comprehensive analysis of the social-ecological system, including:\n\n",
    "- **Network Structure**: ", as.character(n_nodes), " system elements with ", as.character(n_edges), " causal connections\n",
    "- **Feedback Dynamics**: ", as.character(n_loops), " feedback loops identified\n",
    "- **System Complexity**: Network density of ", network_density, "\n\n"
  )
  # ========== DETAILED LOOP ANALYSIS ==========
  # Check both possible locations: data$data$analysis$loops$loop_info (new) or data$data$cld$loops (legacy)
  loops_data <- if (!is.null(data$data$analysis$loops$loop_info)) {
    data$data$analysis$loops$loop_info
  } else {
    data$data$cld$loops
  }
  
  loops_section <- if (!is.null(loops_data) && nrow(loops_data) > 0) {
    loops <- loops_data

    n_reinforcing <- sum(loops$Type == "Reinforcing", na.rm = TRUE)
    n_balancing <- sum(loops$Type == "Balancing", na.rm = TRUE)

    # Analyze loop lengths - handle both Path and Elements columns
    if ("Path" %in% names(loops) && !all(is.na(loops$Path))) {
      loop_lengths <- nchar(gsub("[^→]", "", loops$Path)) + 1
    } else if ("Elements" %in% names(loops) && !all(is.na(loops$Elements))) {
      loop_lengths <- nchar(gsub("[^→]", "", loops$Elements)) + 1
    } else if ("Length" %in% names(loops) && !all(is.na(loops$Length))) {
      loop_lengths <- loops$Length
    } else {
      # Fallback: estimate from loop data or use default
      loop_lengths <- rep(4, nrow(loops))  # Default reasonable loop length
    }

    avg_length <- round(mean(loop_lengths, na.rm = TRUE), 1)
    # Handle NaN for avg_length
    if (is.nan(avg_length) || is.na(avg_length)) avg_length <- 4

    max_length <- if (length(loop_lengths[!is.na(loop_lengths)]) > 0) max(loop_lengths, na.rm = TRUE) else avg_length
    min_length <- if (length(loop_lengths[!is.na(loop_lengths)]) > 0) min(loop_lengths, na.rm = TRUE) else avg_length

    # Ensure min/max are valid
    if (is.infinite(max_length) || is.na(max_length)) max_length <- avg_length
    if (is.infinite(min_length) || is.na(min_length)) min_length <- avg_length

    # Get top loops by length
    top_loops_idx <- head(order(loop_lengths, decreasing = TRUE), min(5, nrow(loops)))

    # Determine which column to use for path display
    path_col <- if ("Path" %in% names(loops)) {
      "Path"
    } else if ("Elements" %in% names(loops)) {
      "Elements"
    } else {
      NULL
    }

    top_loops_text <- if (!is.null(path_col) && length(top_loops_idx) > 0) {
      paste(sapply(top_loops_idx, function(i) {
        # Calculate ellipsis separately to avoid if-else in paste0
        path_text <- if (!is.na(loops[[path_col]][i])) as.character(loops[[path_col]][i]) else "Unknown path"
        path_ellipsis <- if(nchar(path_text) > 80) "..." else ""
        paste0("   - **Loop ", i, "** (", loops$Type[i], ", ", loop_lengths[i], " nodes): ",
               substr(path_text, 1, 80), path_ellipsis, "\n")
      }), collapse = "")
    } else {
      paste0("   - ", nrow(loops), " feedback loops detected (details require path information)\n")
    }
    # Calculate system implications separately to avoid if-else in paste0
    system_implications_text <- if (n_reinforcing > n_balancing) {
      paste0("⚠️ **High proportion of reinforcing loops** (", round(n_reinforcing/nrow(loops)*100, 1),
             "%) suggests the system may be prone to rapid changes and potential instability. ",
             "Management interventions should focus on:\n",
             "1. Monitoring for early warning signals of tipping points\n",
             "2. Strengthening balancing mechanisms\n",
             "3. Managing reinforcing loops to prevent runaway dynamics\n\n")
    } else if (n_balancing > n_reinforcing) {
      paste0("✓ **High proportion of balancing loops** (", round(n_balancing/nrow(loops)*100, 1),
             "%) suggests the system has strong self-regulating capacity and resilience. ",
             "However, this may also indicate:\n",
             "1. Resistance to change and management interventions\n",
             "2. Need for persistent effort to achieve desired outcomes\n",
             "3. Importance of identifying leverage points to overcome system inertia\n\n")
    } else {
      "The balanced mix of reinforcing and balancing loops suggests moderate system stability with capacity for both change and self-regulation.\n\n"
    }

    # Convert all numeric values to characters for safe paste0
    total_loops <- as.character(as.integer(nrow(loops)))
    pct_reinforcing <- as.character(round(n_reinforcing/nrow(loops)*100, 1))
    pct_balancing <- as.character(round(n_balancing/nrow(loops)*100, 1))

    result <- paste0(
      "## Feedback Loop Analysis\n\n",
      "### Loop Discovery\n\n",
      "Detected **", total_loops, " feedback loops** in the system:\n\n",
      "- **", as.character(n_reinforcing), " Reinforcing loops** (", pct_reinforcing, "%) - These amplify changes and can lead to exponential growth or decline\n",
      "- **", as.character(n_balancing), " Balancing loops** (", pct_balancing, "%) - These stabilize the system and resist change\n\n",
      "### Loop Characteristics\n\n",
      "- **Average loop length**: ", as.character(avg_length), " nodes\n",
      "- **Shortest loop**: ", as.character(min_length), " nodes\n",
      "- **Longest loop**: ", as.character(max_length), " nodes\n\n",
      "### Key Feedback Loops\n\n",
      "The following loops represent the most complex feedback structures:\n\n",
      top_loops_text, "\n",
      "### System Implications\n\n",
      system_implications_text
    )
    result
  } else {
    "## Feedback Loop Analysis\n\n⚠️ No feedback loops detected yet. Run loop detection analysis to identify circular causality in the system.\n\n"
  }

  # ========== LEVERAGE POINT ANALYSIS ==========
  leverage_section <- if (!is.null(data$data$cld$nodes) && nrow(data$data$cld$nodes) > 0) {
    nodes <- data$data$cld$nodes

    # Check if leverage scores exist
    if ("leverage_score" %in% names(nodes) && any(nodes$leverage_score > 0, na.rm = TRUE)) {
      leverage_nodes <- nodes[nodes$leverage_score > 0, ]
      leverage_nodes <- leverage_nodes[order(-leverage_nodes$leverage_score), ]

      top_n <- min(10, nrow(leverage_nodes))
      top_leverage <- leverage_nodes[1:top_n, ]

      # Categorize by influence type
      high_in <- top_leverage[top_leverage$in_degree >= quantile(nodes$in_degree, 0.75, na.rm = TRUE), ]
      high_out <- top_leverage[top_leverage$out_degree >= quantile(nodes$out_degree, 0.75, na.rm = TRUE), ]
      high_between <- if ("betweenness" %in% names(top_leverage)) {
        top_leverage[top_leverage$betweenness >= quantile(nodes$betweenness, 0.75, na.rm = TRUE), ]
      } else { data.frame() }

      top_leverage_text <- paste(sapply(1:top_n, function(i) {
        node <- top_leverage[i, ]
        # Calculate betweenness text separately to avoid if-else in paste0
        betweenness_text <- if ("betweenness" %in% names(node)) paste0(" | Betweenness: ", round(node$betweenness, 2)) else ""
        paste0("   ", i, ". **", node$label, "** (Score: ", round(node$leverage_score, 2), ")\n",
               "      - In-degree: ", node$in_degree, " | Out-degree: ", node$out_degree,
               betweenness_text, "\n")
      }), collapse = "")

      # Calculate category examples separately to avoid if-else in paste0
      receivers_text <- if (nrow(high_in) > 0) paste0(":\n   ", paste(head(high_in$label, 3), collapse = ", "), "\n") else "\n"
      drivers_text <- if (nrow(high_out) > 0) paste0(":\n   ", paste(head(high_out$label, 3), collapse = ", "), "\n") else "\n"
      connectors_text <- if (nrow(high_between) > 0) paste0(":\n   ", paste(head(high_between$label, 3), collapse = ", "), "\n") else "\n"

      # Generate context-specific strategic recommendations
      strategic_recs <- generate_strategic_recommendations(data, top_leverage, high_in, high_out, high_between, loops_data)

      paste0(
        "## Leverage Point Analysis\n\n",
        "### Overview\n\n",
        "Identified **", nrow(leverage_nodes), " nodes with leverage potential** based on network centrality metrics.\n\n",
        "### Top 10 Leverage Points\n\n",
        top_leverage_text, "\n",
        "### Leverage Point Categories\n\n",
        "**Receivers** (High in-degree, ", nrow(high_in), " nodes): These are affected by many system components", receivers_text,
        "   → *Management implication*: Monitor as indicators of system state\n\n",
        "**Drivers** (High out-degree, ", nrow(high_out), " nodes): These influence many system components", drivers_text,
        "   → *Management implication*: Target for interventions to create cascading effects\n\n",
        "**Connectors** (High betweenness, ", nrow(high_between), " nodes): These bridge different system parts", connectors_text,
        "   → *Management implication*: Critical for maintaining system connectivity\n\n",
        # recommendations content follows the Recommendations checkbox (CodeRabbit #130)
        if (include("recommendations")) paste0("### Strategic Recommendations\n\n", strategic_recs)
      )
    } else {
      "## Leverage Point Analysis\n\n⚠️ No leverage point analysis performed yet. Run leverage point detection to identify high-impact intervention points.\n\n"
    }
  } else {
    "## Leverage Point Analysis\n\n⚠️ No CLD nodes available for leverage analysis.\n\n"
  }
  # ========== NETWORK METRICS ==========
  network_section <- if (!is.null(data$data$cld$nodes) && nrow(data$data$cld$nodes) > 0) {
    nodes <- data$data$cld$nodes
    # Safely get edges to avoid list issues
    edges <- if (!is.null(data$data$cld$edges)) data$data$cld$edges else data.frame()

    n_nodes <- nrow(nodes)
    n_edges <- nrow(edges)
    density <- if (n_nodes > 1) n_edges / (n_nodes * (n_nodes - 1)) else 0

    avg_in <- mean(nodes$in_degree, na.rm = TRUE)
    avg_out <- mean(nodes$out_degree, na.rm = TRUE)

    # Calculate interpretation separately to avoid if-else in paste0
    interpretation_text <- if (density < 0.1) {
      "**Sparse network**: Low connectivity suggests modular structure with distinct subsystems. Management can focus on specific components with limited spillover effects.\n\n"
    } else if (density < 0.3) {
      "**Moderate connectivity**: Balanced structure with some interconnections. Interventions will have localized effects with some system-wide implications.\n\n"
    } else {
      "**Highly connected network**: Dense interconnections mean interventions will have widespread effects. Requires careful analysis of cascading impacts.\n\n"
    }

    paste0(
      "## Network Structure Metrics\n\n",
      "### Basic Metrics\n\n",
      "- **Nodes**: ", n_nodes, " system elements\n",
      "- **Edges**: ", n_edges, " causal connections\n",
      "- **Density**: ", round(density, 3), " (", round(density * 100, 1), "% of possible connections)\n",
      "- **Average in-degree**: ", round(avg_in, 2), " connections per node\n",
      "- **Average out-degree**: ", round(avg_out, 2), " connections per node\n\n",
      "### Interpretation\n\n",
      interpretation_text
    )
  } else {
    "## Network Structure\n\n⚠️ No CLD network available for analysis.\n\n"
  }
  # ========== STAKEHOLDER ANALYSIS ==========
  stakeholder_section <- if (!is.null(data$data$pims$stakeholders) && nrow(data$data$pims$stakeholders) > 0) {
    n_stakeholders <- nrow(data$data$pims$stakeholders)
    paste0(
      "## Stakeholder Analysis\n\n",
      "Identified **", n_stakeholders, " stakeholders** in the system.\n\n",
      "Key considerations for stakeholder engagement:\n\n",
      "1. Align stakeholder interests with leverage point interventions\n",
      "2. Engage stakeholders affected by high-impact feedback loops\n",
      "3. Build coalitions around shared system goals\n",
      "4. Communicate system complexity and interconnections\n\n"
    )
  } else {
    "## Stakeholder Analysis\n\n⚠️ No stakeholder data available.\n\n"
  }
  # ========== MANAGEMENT RECOMMENDATIONS ==========
  # Generate context-specific management recommendations
  n_stakeholders <- if (!is.null(data$data$pims$stakeholders) && nrow(data$data$pims$stakeholders) > 0) {
    nrow(data$data$pims$stakeholders)
  } else {
    0L
  }

  recommendations_section <- paste0(
    "## Management Recommendations\n\n",
    "### Strategic Priorities\n\n",
    "Based on the system analysis, the following management priorities are recommended:\n\n",
    generate_management_recommendations(data, nodes, loops_data, n_stakeholders)
  )

  # ========== COMBINE ALL SECTIONS ==========

  content <- paste0(
    title_section,
    if (include("summary")) overview_section,
    if (!is.null(sections) && "isa" %in% sections) report_isa_elements_section(data),
    if (!is.null(sections) && "cld" %in% sections) report_cld_section(data),
    if (include("loops")) loops_section,
    if (include("leverage")) leverage_section,
    if (include("metrics")) network_section,
    stakeholder_section,
    if (include("recommendations")) recommendations_section
  )

  return(content)
}

# Markdown-safe single line (element names are user text)
.report_md_text <- function(x) {
  x <- gsub("[\r\n]+", " ", as.character(x))
  gsub("([\\\\`*_\\[\\]<>|#])", "\\\\\\1", x)
}

#' DAPSI(W)R(M) elements per category ("isa" section of the full report)
report_isa_elements_section <- function(data) {
  isa <- safe_get_nested(data, "data", "isa_data", default = list())
  cats <- c(drivers = "Drivers", activities = "Activities", pressures = "Pressures",
            marine_processes = "Marine Processes & Functions", ecosystem_services = "Ecosystem Services",
            goods_benefits = "Goods & Benefits", responses = "Responses")
  parts <- vapply(names(cats), function(k) {
    df <- isa[[k]]
    if (!is.data.frame(df) || !nrow(df) || !"name" %in% names(df)) return("")
    paste0("### ", cats[[k]], " (", nrow(df), ")\n\n",
           paste0("- ", .report_md_text(df$name), collapse = "\n"), "\n\n")
  }, "")
  body <- paste(parts, collapse = "")
  paste0("## DAPSI(W)R(M) Elements\n\n",
         if (nzchar(body)) body else "No elements have been entered yet.\n\n")
}

#' Element and link counts of the causal loop diagram ("cld" section)
report_cld_section <- function(data) {
  nodes <- data$data$cld$nodes
  edges <- data$data$cld$edges
  if (!is.data.frame(nodes) || !nrow(nodes)) {
    return("## Causal Loop Diagram\n\nNo causal loop diagram has been built yet.\n\n")
  }
  by_type <- if ("group" %in% names(nodes)) table(nodes$group) else table(rep("Elements", nrow(nodes)))
  n_edges <- if (is.data.frame(edges)) nrow(edges) else 0L
  pol <- if (is.data.frame(edges) && "polarity" %in% names(edges)) edges$polarity else character(0)
  paste0(
    "## Causal Loop Diagram\n\n",
    "The diagram has **", nrow(nodes), " elements** and **", n_edges, " links** (",
    sum(pol == "+", na.rm = TRUE), " reinforcing (+), ", sum(pol == "-", na.rm = TRUE), " opposing (-)).\n\n",
    "| Element type | Elements |\n|---|---|\n",
    paste0("| ", .report_md_text(names(by_type)), " | ", as.integer(by_type), " |", collapse = "\n"),
    "\n\n"
  )
}
