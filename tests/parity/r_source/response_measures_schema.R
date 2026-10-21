# functions/response_measures_schema.R
# Response-measures register schema (spec 2026-10-11 WS-3a).
# Codes are stored; labels are produced only for display. All columns scalar.

.rm_schema_env <- new.env(parent = emptyenv())

#' Empty register with every schema column (character, Cost numeric)
empty_measures_df <- function() {
  cols <- lapply(RM_REGISTER_COLUMNS, function(cl) if (cl == "Cost") numeric(0) else character(0))
  as.data.frame(setNames(cols, RM_REGISTER_COLUMNS), stringsAsFactors = FALSE)
}

#' Reverse map label -> code for Type / Target / Status, from ALL translation files, all languages
rm_reverse_label_map <- function(force = FALSE) {
  if (!force && !is.null(.rm_schema_env$map)) return(.rm_schema_env$map)
  root <- if (exists("PROJECT_ROOT")) PROJECT_ROOT else "."
  files <- list.files(file.path(root, "translations"), pattern = "[.]json$", recursive = TRUE, full.names = TRUE)
  files <- files[!grepl("_merged|backup", basename(files))]
  vocabs <- list(type = RM_TYPE_CODES, target = RM_TARGET_CODES, status = RM_STATUS_CODES)
  out <- lapply(vocabs, function(v) character(0))
  for (f in files) {
    tr <- tryCatch(jsonlite::fromJSON(f, simplifyVector = FALSE)$translation, error = function(e) NULL)
    if (is.null(tr)) next
    for (vn in names(vocabs)) {
      v <- vocabs[[vn]]
      for (code in names(v)) {
        entry <- tr[[paste0("modules.response.measures.", v[[code]])]]
        if (is.null(entry)) next
        labels <- unique(trimws(unlist(entry)))
        labels <- labels[nzchar(labels)]
        out[[vn]] <- c(out[[vn]], setNames(rep(code, length(labels)), labels))
      }
    }
  }
  out <- lapply(out, function(m) m[!duplicated(names(m))])
  .rm_schema_env$map <- out
  out
}

.map_codes <- function(x, map, codes) {
  x <- as.character(x); x[is.na(x)] <- ""
  hit <- !(x %in% codes) & x %in% names(map)
  x[hit] <- unname(map[x[hit]])
  x
}

#' Normalize a register to the WS-3a schema (idempotent)
#' @param df NULL, data.frame, or list of row lists (jsonlite simplifyVector = FALSE)
normalize_response_measures <- function(df) {
  if (is.null(df) || (is.list(df) && !is.data.frame(df) && length(df) == 0)) return(empty_measures_df())
  if (is.list(df) && !is.data.frame(df)) {
    # Column-wise build: rows may carry different keys (jsonlite drops NA fields
    # unless na = "null"), so never rbind per-row frames (WS-3a review C1).
    rows <- Filter(is.list, df)
    keys <- union(RM_REGISTER_COLUMNS, unique(unlist(lapply(rows, names))))
    cols <- lapply(keys, function(cl) vapply(rows, function(r) {
      v <- r[[cl]]
      if (is.null(v) || length(v) == 0 || all(is.na(unlist(v)))) NA_character_
      else paste(unlist(v), collapse = ";")
    }, character(1)))
    n_dropped <- length(df) - length(rows)
    df <- as.data.frame(setNames(cols, keys), stringsAsFactors = FALSE)
    if (n_dropped > 0 && exists("debug_log", mode = "function")) {
      debug_log(sprintf("normalize_response_measures: dropped %d non-row item(s)", n_dropped), "WARN")
    }
  }
  if (!is.data.frame(df)) return(empty_measures_df())
  n <- nrow(df)
  out <- lapply(RM_REGISTER_COLUMNS, function(cl) {
    v <- if (cl %in% names(df)) df[[cl]] else if (cl == "Cost") rep(NA_real_, n) else rep("", n)
    if (cl == "Cost") return(suppressWarnings(as.numeric(v)))
    v <- as.character(unlist(lapply(v, function(e) if (is.null(e) || length(e) == 0) "" else paste(e, collapse = ";"))))
    v[is.na(v)] <- ""
    v
  })
  out <- as.data.frame(setNames(out, RM_REGISTER_COLUMNS), stringsAsFactors = FALSE)
  m <- rm_reverse_label_map()
  out$Type   <- .map_codes(out$Type,   m$type,   names(RM_TYPE_CODES))
  out$Target <- .map_codes(out$Target, m$target, names(RM_TARGET_CODES))
  out$Status <- .map_codes(out$Status, m$status, names(RM_STATUS_CODES))
  out$PestleTag <- vapply(strsplit(out$PestleTag, ";", fixed = TRUE), function(t) {
    t <- trimws(t)
    bad <- setdiff(t[nzchar(t)], PESTLE_CODES)
    if (length(bad) && exists("debug_log", mode = "function")) {
      debug_log(sprintf("normalize_response_measures: dropped unknown PESTLE code(s): %s",
                        paste(bad, collapse = ", ")), "WARN")
    }
    paste(PESTLE_CODES[PESTLE_CODES %in% t], collapse = ";")
  }, character(1))
  # Tenet levels (WS-10 follow-up): only TENET_LEVELS codes; "intermediate" exists only
  # for ecological effectiveness (EBM framework). Anything else is blanked, not guessed.
  for (cd in EBM_TENETS$code) {
    cl <- paste0("Tenet_", cd)
    ok <- if (cd == "ecol_effective") TENET_LEVELS else setdiff(TENET_LEVELS, "intermediate")
    tidy <- tolower(trimws(out[[cl]]))                    # a hand-edited "Full " is kept, not lost
    out[[cl]][tidy %in% ok] <- tidy[tidy %in% ok]
    bad <- nzchar(out[[cl]]) & !out[[cl]] %in% ok
    if (any(bad)) {
      if (exists("debug_log", mode = "function")) {
        debug_log(sprintf("normalize_response_measures: blanked invalid %s value(s): %s", cl,
                          paste(unique(out[[cl]][bad]), collapse = ", ")), "WARN")
      }
      out[[cl]][bad] <- ""
    }
  }
  out
}

#' Suggested register Target code for an EBM code (management measures only)
suggest_rm_target <- function(ebm_code) {
  if (is.null(ebm_code) || !nzchar(ebm_code)) return("")
  t <- EBM_MANAGEMENT_MEASURES$dapsiwrm_target[EBM_MANAGEMENT_MEASURES$code == ebm_code]
  if (length(t) == 0) return("")
  switch(t, "A" = "activities", "P" = "pressures", "C" = "state", "A|P|C" = "multiple", "")
}

#' EBM picker choices for a kind; names = labels, values = codes; "" first
ebm_code_choices <- function(kind, i18n) {
  if (identical(kind, "instrument")) {
    codes <- EBM_POLICY_INSTRUMENTS$code[EBM_POLICY_INSTRUMENTS$level == "type"]
    labels <- paste(codes, wp5_vocab_label("instrument", codes, i18n))
  } else if (identical(kind, "measure")) {
    codes <- EBM_MANAGEMENT_MEASURES$code
    labels <- wp5_vocab_label("measure", codes, i18n)
  } else {
    return(c(" " = ""))
  }
  c(" " = "", setNames(codes, labels))
}

#' Display labels for register codes; unknown values pass through unchanged
rm_display_label <- function(vocab, code, i18n) {
  code <- as.character(code); code[is.na(code)] <- ""
  key_for <- function(cd) {
    switch(vocab,
      type   = if (cd %in% names(RM_TYPE_CODES))   paste0("modules.response.measures.", RM_TYPE_CODES[[cd]]),
      target = if (cd %in% names(RM_TARGET_CODES)) paste0("modules.response.measures.", RM_TARGET_CODES[[cd]]),
      status = if (cd %in% names(RM_STATUS_CODES)) paste0("modules.response.measures.", RM_STATUS_CODES[[cd]]),
      kind   = if (cd %in% c("instrument", "measure")) paste0("modules.response.governance.kind.", cd),
      governance_level = if (cd %in% GOVERNANCE_LEVELS) paste0("modules.response.governance.level.", cd),
      tenet_level = if (cd %in% TENET_LEVELS) paste0("modules.response.governance.tenet_level.", cd),
      pestle = if (cd %in% PESTLE_CODES) paste0("modules.wp5_scenarios.pestle.", cd),
      level  = if (cd %in% c("HIGH", "MEDIUM", "LOW", "UNKNOWN")) paste0("modules.response.measures.", tolower(cd)),
      NULL)
  }
  vapply(code, function(cd) {
    if (!nzchar(cd)) return("")
    if (vocab == "ebm_code") {
      if (cd %in% EBM_MANAGEMENT_MEASURES$code) return(wp5_vocab_label("measure", cd, i18n))
      if (cd %in% EBM_POLICY_INSTRUMENTS$code) return(wp5_vocab_label("instrument", cd, i18n))
      return(cd)
    }
    k <- key_for(cd)
    if (is.null(k)) return(cd)
    lbl <- tryCatch(as.character(i18n$t(k)), error = function(e) cd)
    if (length(lbl) != 1 || !nzchar(lbl)) cd else lbl
  }, character(1), USE.NAMES = FALSE)
}

#' Stakeholder-id codec (scalar column)
encode_ids <- function(x) {
  x <- as.character(unlist(x)); x <- x[!is.na(x) & nzchar(x)]
  paste(x, collapse = ";")
}
decode_ids <- function(s) {
  if (is.null(s) || is.na(s) || !nzchar(s)) return(character(0))
  strsplit(s, ";", fixed = TRUE)[[1]]
}

#' Translate every coded register column for display (tables, Word/Excel exports)
#' Effectiveness/Feasibility, Type/Target/Status, Kind/EbmCode/GovernanceLevel and
#' Tenet_* are mapped to labels; unknown values pass through (WS-3a review I1/I2).
rm_translate_for_display <- function(df, i18n) {
  if (is.null(df) || !is.data.frame(df) || nrow(df) == 0) return(df)
  # i18n-ref: modules.response.measures.high
  # i18n-ref: modules.response.measures.medium
  # i18n-ref: modules.response.measures.low
  # i18n-ref: modules.response.measures.unknown
  pairs <- list(c("Effectiveness", "level"), c("Feasibility", "level"), c("Type", "type"),
                c("Target", "target"), c("Status", "status"), c("Kind", "kind"),
                c("EbmCode", "ebm_code"), c("GovernanceLevel", "governance_level"))
  for (p in pairs) if (p[1] %in% names(df)) df[[p[1]]] <- rm_display_label(p[2], df[[p[1]]], i18n)
  if ("PestleTag" %in% names(df)) {
    # i18n-ref: modules.wp5_scenarios.pestle.political
    # i18n-ref: modules.wp5_scenarios.pestle.economic
    # i18n-ref: modules.wp5_scenarios.pestle.social
    # i18n-ref: modules.wp5_scenarios.pestle.technological
    # i18n-ref: modules.wp5_scenarios.pestle.legal
    # i18n-ref: modules.wp5_scenarios.pestle.environmental
    df$PestleTag <- vapply(strsplit(ifelse(is.na(df$PestleTag), "", df$PestleTag), ";", fixed = TRUE),
                           function(t) paste(rm_display_label("pestle", t, i18n), collapse = ", "), character(1))
  }
  for (cl in grep("^Tenet_", names(df), value = TRUE)) df[[cl]] <- rm_display_label("tenet_level", df[[cl]], i18n)
  df
}

#' Stakeholder picker update that keeps the user's selection (WS-3a review I3)
#' @param sh PIMS stakeholders data.frame (ID, Name) or NULL
#' @param current Currently selected IDs
#' @param previous_choices Choices last sent to the client (NULL = none yet)
#' @return list(skip, choices, selected); skip = TRUE when choices are unchanged
stakeholder_picker_update <- function(sh, current, previous_choices) {
  ch <- if (is.data.frame(sh) && nrow(sh) > 0) {
    setNames(as.character(sh$ID), paste0(sh$Name, " (", sh$ID, ")"))
  } else character(0)
  list(skip = !is.null(previous_choices) && identical(ch, previous_choices),
       choices = ch,
       selected = intersect(as.character(unlist(current)), unname(ch)))
}
