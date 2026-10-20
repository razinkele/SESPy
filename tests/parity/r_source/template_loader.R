# functions/template_loader.R
# JSON Template Loader for SES Templates
# Purpose: Load and convert JSON templates to R data structures

library(jsonlite)

# ============================================================================
# TEMPLATE CACHE (Memoization)
# ============================================================================
# Cache environment for loaded templates to avoid repeated disk reads
# Cache key is the normalized file path + file modification time

.template_cache <- new.env(parent = emptyenv())

#' Get cache key for a file (path + mtime for cache invalidation)
#' @param file_path Path to file
#' @return Cache key string
.get_cache_key <- function(file_path) {
  if (!file.exists(file_path)) return(NULL)
  norm_path <- normalizePath(file_path, mustWork = FALSE)
  mtime <- file.mtime(file_path)
  paste0(norm_path, "|", as.numeric(mtime))
}

#' Clear template cache (useful for testing or after template updates)
#' @export
clear_template_cache <- function() {
  rm(list = ls(.template_cache), envir = .template_cache)
  invisible(TRUE)
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

#' Convert JSON element array to data frame
#' @param elements List of elements from JSON
#' @param element_type Type of element (for Type column)
#' @return Data frame with standardized columns
json_elements_to_df <- function(elements, element_type) {
  if (is.null(elements) || length(elements) == 0) {
    return(data.frame(
      ID = character(0),
      Name = character(0),
      Type = character(0),
      Description = character(0),
      Stakeholder = character(0),
      Importance = character(0),
      Trend = character(0)
      
    ))
  }

  # Handle case where element_type might be empty/NULL
  if (is.null(element_type) || length(element_type) == 0) {
    element_type <- "Unknown"
  }

  df <- data.frame(
    ID = sapply(elements, function(x) if (!is.null(x$id)) x$id else ""),
    Name = sapply(elements, function(x) {
      # Prefer 'name' field, fallback to 'id' if name is missing
      name <- x$name
      if (is.null(name) || length(name) == 0 || name == "") {
        return(x$id)
      }
      return(name)
    }),
    Type = element_type,
    Description = sapply(elements, function(x) if (!is.null(x$description)) x$description else ""),
    Stakeholder = sapply(elements, function(x) if (!is.null(x$stakeholder)) x$stakeholder else ""),
    Importance = "",
    Trend = ""
    
  )

  return(df)
}

#' Build adjacency matrix from connections
#' @param connections List of connection objects from JSON
#' @param from_elements Vector of element IDs for rows
#' @param to_elements Vector of element IDs for columns
#' @param from_type Type of source elements
#' @param to_type Type of target elements
#' @return Matrix with connection strengths
build_adjacency_matrix <- function(connections, from_elements, to_elements,
                                   from_type, to_type, from_names, to_names) {
  # Initialize empty matrix
  mat <- matrix("", nrow = length(from_elements), ncol = length(to_elements),
                dimnames = list(from_names, to_names))

  # Normalize type names to handle different conventions
  normalize_type <- function(type) {
    type_lower <- tolower(type)
    # Map variations to canonical names
    if (type_lower %in% c("state", "marineprocess", "marine_process")) return("state")
    if (type_lower %in% c("impact", "ecosystemservice", "ecosystem_service")) return("impact")
    if (type_lower %in% c("goodsbenefit", "goods_benefit", "welfare")) return("welfare")
    if (type_lower %in% c("enmp", "pressure")) return("pressure")
    # Measures are a subtype of Responses and share their matrix rows (gb_r etc.);
    # rows are matched by ID, so this only lets "welfare" -> "measure" reach gb_r.
    if (type_lower == "measure") return("response")
    return(type_lower)
  }
  
  # Filter connections for this matrix (normalized comparison)
  relevant_connections <- Filter(function(conn) {
    normalize_type(conn$from_type) == normalize_type(from_type) &&
    normalize_type(conn$to_type) == normalize_type(to_type)
  }, connections)

  # Fill matrix
  for (conn in relevant_connections) {
    from_idx <- which(from_elements == conn$from_id)
    to_idx <- which(to_elements == conn$to_id)

    if (length(from_idx) > 0 && length(to_idx) > 0) {
      polarity <- conn$polarity %||% "+"
      strength <- conn$strength %||% "medium"
      confidence <- conn$confidence %||% 3

      mat[from_idx, to_idx] <- paste0(polarity, strength, ":", confidence)
    }
  }

  return(mat)
}

#' Null-coalescing operator
#' @param x Value to check
#' @param y Default value if x is NULL
`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

# ============================================================================
# TEMPLATE LOADER HELPERS
# ============================================================================

#' Detect JSON format and extract framework data with metadata
#' @param json_data Parsed JSON list
#' @return List with fw (framework data), name, and description
.detect_template_format <- function(json_data) {
  if (!is.null(json_data$dapsiwrm_framework)) {
    list(
      fw = json_data$dapsiwrm_framework,
      name = json_data$template_name %||% "Unknown Template",
      description = json_data$template_description %||% ""
    )
  } else if (!is.null(json_data$elements)) {
    list(
      fw = json_data$elements,
      name = json_data$template_info$name %||% "Unknown Template",
      description = json_data$template_info$description %||% ""
    )
  } else {
    stop("Unknown JSON format - neither dapsiwrm_framework nor elements found")
  }
}

#' Convert framework elements to data frames
#' @param fw Framework list from JSON
#' @return List of data frames and response counts
.extract_template_elements <- function(fw) {
  drivers_df <- json_elements_to_df(fw$drivers, "Driver")
  activities_df <- json_elements_to_df(fw$activities, "Activity")
  pressures_df <- json_elements_to_df(fw$pressures, "EnMP")

  mpf_list <- fw$marine_processes %||% fw$states
  marine_processes_df <- json_elements_to_df(mpf_list, "State Change")

  es_list <- fw$ecosystem_services %||% fw$impacts
  es_type <- "Provisioning"
  if (!is.null(es_list) && length(es_list) > 0 && !is.null(es_list[[1]]$type)) {
    es_type <- es_list[[1]]$type
  } else if (!is.null(fw$impacts)) {
    es_type <- "Impact"
  }
  ecosystem_services_df <- json_elements_to_df(es_list, es_type)

  gb_list <- fw$goods_benefits %||% fw$welfare
  goods_benefits_df <- json_elements_to_df(gb_list, "Welfare")

  responses_list <- fw$responses %||% list()
  measures_list <- fw$measures %||% list()
  n_original_responses <- length(responses_list)
  n_measures <- length(measures_list)
  all_responses <- c(responses_list, measures_list)
  responses_df <- json_elements_to_df(all_responses, "Response")

  list(
    drivers = drivers_df,
    activities = activities_df,
    pressures = pressures_df,
    marine_processes = marine_processes_df,
    ecosystem_services = ecosystem_services_df,
    goods_benefits = goods_benefits_df,
    responses = responses_df,
    n_original_responses = n_original_responses,
    n_measures = n_measures,
    n_total_responses = nrow(responses_df)
  )
}

#' Expand or create an adjacency matrix to include measure rows
#' @param existing_matrix Existing matrix (or NULL)
#' @param measure_matrix Temporary matrix for measure connections
#' @param n_total Total row count for full matrix
#' @param n_original Number of original response rows
#' @param row_names Full row names vector
#' @return Expanded matrix
.merge_measure_matrix <- function(existing_matrix, measure_matrix, n_total, n_original, row_names) {
  if (!is.null(existing_matrix) && nrow(existing_matrix) != n_total) {
    full <- matrix("", nrow = n_total, ncol = ncol(existing_matrix),
                   dimnames = list(row_names, colnames(existing_matrix)))
    full[1:n_original, ] <- existing_matrix
    full[(n_original + 1):n_total, ] <- measure_matrix
    return(full)
  } else if (is.null(existing_matrix)) {
    full <- matrix("", nrow = n_total, ncol = ncol(measure_matrix),
                   dimnames = list(row_names, colnames(measure_matrix)))
    full[(n_original + 1):n_total, ] <- measure_matrix
    return(full)
  }
  existing_matrix
}

#' Build all adjacency matrices for a template
#' @param elems List of element data frames (from .extract_template_elements)
#' @param connections Raw connections list from JSON
#' @return Named list of adjacency matrices
.build_template_matrices <- function(elems, connections) {
  matrices <- list()
  if (nrow(elems$drivers) == 0 || nrow(elems$activities) == 0 || length(connections) == 0) {
    return(matrices)
  }

  # Core DAPSI(W)R chain
  matrices$d_a <- build_adjacency_matrix(
    connections, elems$drivers$ID, elems$activities$ID,
    "driver", "activity", elems$drivers$Name, elems$activities$Name)

  if (nrow(elems$pressures) > 0)
    matrices$a_p <- build_adjacency_matrix(
      connections, elems$activities$ID, elems$pressures$ID,
      "activity", "pressure", elems$activities$Name, elems$pressures$Name)

  if (nrow(elems$pressures) > 1) {
    p_p <- build_adjacency_matrix(
      connections, elems$pressures$ID, elems$pressures$ID,
      "pressure", "pressure", elems$pressures$Name, elems$pressures$Name)
    if (any(p_p != "")) matrices$p_p <- p_p
  }

  if (nrow(elems$marine_processes) > 0 && nrow(elems$pressures) > 0)
    matrices$p_mpf <- build_adjacency_matrix(
      connections, elems$pressures$ID, elems$marine_processes$ID,
      "pressure", "state", elems$pressures$Name, elems$marine_processes$Name)

  if (nrow(elems$marine_processes) > 1) {
    s_s <- build_adjacency_matrix(
      connections, elems$marine_processes$ID, elems$marine_processes$ID,
      "state", "state", elems$marine_processes$Name, elems$marine_processes$Name)
    if (any(s_s != "")) matrices$s_s <- s_s
  }

  if (nrow(elems$ecosystem_services) > 0 && nrow(elems$marine_processes) > 0)
    matrices$mpf_es <- build_adjacency_matrix(
      connections, elems$marine_processes$ID, elems$ecosystem_services$ID,
      "state", "impact", elems$marine_processes$Name, elems$ecosystem_services$Name)

  if (nrow(elems$goods_benefits) > 0 && nrow(elems$ecosystem_services) > 0)
    matrices$es_gb <- build_adjacency_matrix(
      connections, elems$ecosystem_services$ID, elems$goods_benefits$ID,
      "impact", "welfare", elems$ecosystem_services$Name, elems$goods_benefits$Name)

  if (nrow(elems$goods_benefits) > 0 && nrow(elems$drivers) > 0)
    matrices$gb_d <- build_adjacency_matrix(
      connections, elems$goods_benefits$ID, elems$drivers$ID,
      "welfare", "driver", elems$goods_benefits$Name, elems$drivers$Name)

  # Response matrices
  n_orig <- elems$n_original_responses
  n_total <- elems$n_total_responses
  resp_df <- elems$responses

  if (n_orig > 0) {
    orig_ids <- resp_df$ID[1:n_orig]
    orig_names <- resp_df$Name[1:n_orig]

    if (nrow(elems$goods_benefits) > 0)
      matrices$gb_r <- build_adjacency_matrix(
        connections, elems$goods_benefits$ID, resp_df$ID,
        "welfare", "response", elems$goods_benefits$Name, resp_df$Name)

    if (nrow(elems$drivers) > 0)
      matrices$r_d <- build_adjacency_matrix(
        connections, orig_ids, elems$drivers$ID,
        "response", "driver", orig_names, elems$drivers$Name)

    if (nrow(elems$activities) > 0)
      matrices$r_a <- build_adjacency_matrix(
        connections, orig_ids, elems$activities$ID,
        "response", "activity", orig_names, elems$activities$Name)

    if (nrow(elems$pressures) > 0)
      matrices$r_p <- build_adjacency_matrix(
        connections, orig_ids, elems$pressures$ID,
        "response", "pressure", orig_names, elems$pressures$Name)

    if (nrow(elems$marine_processes) > 0)
      matrices$r_mpf <- build_adjacency_matrix(
        connections, orig_ids, elems$marine_processes$ID,
        "response", "state", orig_names, elems$marine_processes$Name)
  }

  # Merge measure connections into response matrices
  n_meas <- elems$n_measures
  if (n_meas > 0) {
    m_ids <- resp_df$ID[(n_orig + 1):n_total]
    m_names <- resp_df$Name[(n_orig + 1):n_total]

    measure_targets <- list(
      list(key = "r_d",   df = elems$drivers,           src_type = "measure", tgt_type = "driver"),
      list(key = "r_a",   df = elems$activities,         src_type = "measure", tgt_type = "activity"),
      list(key = "r_p",   df = elems$pressures,          src_type = "measure", tgt_type = "pressure"),
      list(key = "r_mpf", df = elems$marine_processes,   src_type = "measure", tgt_type = "state")
    )

    for (mt in measure_targets) {
      if (nrow(mt$df) > 0) {
        temp <- build_adjacency_matrix(
          connections, m_ids, mt$df$ID,
          mt$src_type, mt$tgt_type, m_names, mt$df$Name)
        matrices[[mt$key]] <- .merge_measure_matrix(
          matrices[[mt$key]], temp, n_total, n_orig, resp_df$Name)
      }
    }

    # M → R (Measures to Responses) — becomes R×R
    if (n_orig > 0) {
      m_r_temp <- build_adjacency_matrix(
        connections, m_ids, resp_df$ID[1:n_orig],
        "measure", "response", m_names, resp_df$Name[1:n_orig])

      matrices$r_r <- matrix("", nrow = n_total, ncol = n_total,
                             dimnames = list(resp_df$Name, resp_df$Name))
      matrices$r_r[(n_orig + 1):n_total, 1:n_orig] <- m_r_temp
    }
  }

  matrices
}

#' Determine template category from metadata
#' @param json_data Parsed JSON list
#' @return Character string category
.determine_template_category <- function(json_data) {
  if (is.null(json_data$regional_context$main_issues)) return("General")

  issues <- json_data$regional_context$main_issues
  if (length(issues) > 1) return("Multi-Stressor")
  if (any(grepl("fish", issues, ignore.case = TRUE))) return("Extraction")
  if (any(grepl("touris", issues, ignore.case = TRUE))) return("Recreation")
  if (any(grepl("aqua|farm", issues, ignore.case = TRUE))) return("Production")
  if (any(grepl("pollut|contamin", issues, ignore.case = TRUE))) return("Pollution")
  if (any(grepl("climat|warm|sea level", issues, ignore.case = TRUE))) return("Climate")
  if (any(grepl("wind|energy", issues, ignore.case = TRUE))) return("Energy")
  "General"
}

#' Determine template icon from name
#' @param template_name Template name string
#' @return FontAwesome icon name
.determine_template_icon <- function(template_name) {
  if (grepl("fish", template_name, ignore.case = TRUE)) return("fish")
  if (grepl("touris|beach", template_name, ignore.case = TRUE)) return("umbrella-beach")
  if (grepl("aqua", template_name, ignore.case = TRUE)) return("shrimp")
  if (grepl("pollut", template_name, ignore.case = TRUE)) return("smog")
  if (grepl("climat", template_name, ignore.case = TRUE)) return("temperature-high")
  if (grepl("wind", template_name, ignore.case = TRUE)) return("wind")
  if (grepl("caribbean|island", template_name, ignore.case = TRUE)) return("globe-americas")
  "globe"
}

# ============================================================================
# MAIN LOADER FUNCTION
# ============================================================================

#' Load template from JSON file (with memoization)
#' @param json_path Path to JSON template file
#' @param use_cache Whether to use cached result (default TRUE)
#' @return List with template data in R format
#' @export
load_template_from_json <- function(json_path, use_cache = TRUE) {
  # Validate file path
  if (is.null(json_path) || !is.character(json_path) || !nzchar(json_path)) {
    log_warning("TEMPLATE", "Invalid template path provided (NULL or empty)")
    return(NULL)
  }
  if (!file.exists(json_path)) {
    log_warning("TEMPLATE", paste("Template file not found:", json_path))
    return(NULL)
  }
  if (!grepl("\\.json$", json_path, ignore.case = TRUE)) {
    log_warning("TEMPLATE", paste("Only JSON files are allowed, got:", json_path))
    return(NULL)
  }

  # Check cache
  if (use_cache) {
    cache_key <- .get_cache_key(json_path)
    if (!is.null(cache_key) && exists(cache_key, envir = .template_cache)) {
      return(get(cache_key, envir = .template_cache))
    }
  }

  result <- tryCatch({
    json_data <- jsonlite::fromJSON(json_path, simplifyVector = FALSE)

    # 1. Detect format and extract metadata
    fmt <- .detect_template_format(json_data)

    # 2. Convert elements to data frames
    elems <- .extract_template_elements(fmt$fw)

    # 3. Build adjacency matrices
    connections <- json_data$connections %||% list()
    adjacency_matrices <- .build_template_matrices(elems, connections)

    # 4. Determine category and icon
    category <- .determine_template_category(json_data)
    icon <- .determine_template_icon(fmt$name)

    # 5. Determine complexity (default to "simple" if not specified)
    complexity <- json_data$complexity %||% "simple"

    # 5. Assemble result
    list(
      name = fmt$name,
      name_key = fmt$name,
      description = fmt$description,
      description_key = fmt$description,
      icon = icon,
      category_key = category,
      complexity = complexity,
      drivers = elems$drivers,
      activities = elems$activities,
      pressures = elems$pressures,
      marine_processes = elems$marine_processes,
      ecosystem_services = elems$ecosystem_services,
      goods_benefits = elems$goods_benefits,
      responses = elems$responses,
      connections = connections,
      adjacency_matrices = adjacency_matrices
    )
  }, error = function(e) {
    log_warning("TEMPLATE", paste("Error loading template from", json_path, ":", e$message))
    NULL
  })

  # Store in cache
  if (use_cache && !is.null(result)) {
    cache_key <- .get_cache_key(json_path)
    if (!is.null(cache_key)) {
      assign(cache_key, result, envir = .template_cache)
    }
  }

  result
}

# ============================================================================
# BATCH LOADER
# ============================================================================

#' Load all templates from data directory
#' @param data_dir Directory containing JSON template files
#' @return Named list of templates
load_all_templates <- function(data_dir = "data") {
  # Candidate directories to search (relative to current working directory)
  candidates <- c(
    data_dir,
    file.path("..", data_dir),
    file.path("..", "..", data_dir),
    "inst/data",
    file.path("..", "inst", "data"),
    file.path("..", "..", "inst", "data"),
    # Test fixtures (ensure deterministic templates available during tests/CI)
    "tests/fixtures/templates",
    "tests/fixtures",
    file.path("..", "tests", "fixtures", "templates")
  )

  json_files <- character(0)

  # Try each candidate until we find matching files
  for (cand in candidates) {
    if (dir.exists(cand)) {
      files_found <- list.files(cand, pattern = "_SES_Template\\.json$", full.names = TRUE, ignore.case = TRUE)
      if (length(files_found) > 0) {
        json_files <- files_found
        found_dir <- cand
        break
      }
    }
  }

  # If none found, return empty list with a message
  if (length(json_files) == 0) {
    debug_log(paste("No template JSON files found in candidates:", paste(candidates, collapse = ", ")), "TEMPLATE")
    return(list())
  }

  templates <- list()

  for (json_file in json_files) {
    # Extract template key from filename
    template_key <- tolower(gsub("_SES_Template\\.json$", "", basename(json_file)))
    template_key <- gsub("_", "", template_key)  # Remove underscores

    # Load template
    template <- load_template_from_json(json_file)

    if (!is.null(template)) {
      templates[[template_key]] <- template
      debug_log(paste("Loaded template:", template_key), "TEMPLATE")
    } else {
      debug_log(paste("Failed to load:", json_file), "TEMPLATE")
    }
  }

  return(templates)
}
