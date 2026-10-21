# functions/stakeholder_schema.R
# =============================================================================
# PIMS stakeholder register schema (WP5 WS-9a, spec 2026-10-17 §4.1).
# The module, the JSON loader and the D5.4 actor seeding build rows through
# normalize_stakeholders(), so older projects gain NERoles/SourceId as "".
# =============================================================================

#' Normalise a stakeholder register to PIMS_STAKEHOLDER_COLUMNS (idempotent)
#' @param df NULL, data.frame, or list of row lists (jsonlite simplifyVector = FALSE)
normalize_stakeholders <- function(df) {
  if (is.list(df) && !is.data.frame(df)) {
    rows <- Filter(is.list, df)
    df <- if (length(rows) == 0) NULL else {
      keys <- union(PIMS_STAKEHOLDER_COLUMNS, unique(unlist(lapply(rows, names))))
      cols <- lapply(keys, function(cl) vapply(rows, function(r) {
        v <- r[[cl]]
        if (is.null(v) || length(v) == 0 || all(is.na(unlist(v)))) "" else paste(unlist(v), collapse = ";")
      }, character(1)))
      as.data.frame(stats::setNames(cols, keys), stringsAsFactors = FALSE)
    }
  }
  if (!is.data.frame(df)) df <- data.frame()
  n <- nrow(df)
  out <- lapply(PIMS_STAKEHOLDER_COLUMNS, function(cl) {
    v <- if (cl %in% names(df)) as.character(df[[cl]]) else rep("", n)
    v[is.na(v)] <- ""
    v
  })
  out <- as.data.frame(stats::setNames(out, PIMS_STAKEHOLDER_COLUMNS), stringsAsFactors = FALSE)
  out$NERoles <- vapply(strsplit(out$NERoles, ";", fixed = TRUE), function(t) {
    t <- trimws(t)
    bad <- setdiff(t[nzchar(t)], STAKEHOLDER_TYPES)
    if (length(bad) && exists("debug_log", mode = "function")) {
      debug_log(sprintf("normalize_stakeholders: dropped unknown role(s): %s", paste(bad, collapse = ", ")), "WARN")
    }
    paste(STAKEHOLDER_TYPES[STAKEHOLDER_TYPES %in% t], collapse = ";")
  }, character(1))
  out
}

#' TRUE when a register uses the WS-9a columns (needs WP5_GOVERNANCE_MIN_APP_VERSION)
stakeholders_use_governance_fields <- function(df) {
  df <- normalize_stakeholders(df)
  any(nzchar(df$NERoles)) || any(nzchar(df$SourceId))
}

#' Register table view: roles as translated labels, SourceId hidden
stakeholders_display_view <- function(df, i18n) {
  df <- normalize_stakeholders(df)
  # i18n-ref: modules.wp5_governance.role.inputters
  # i18n-ref: modules.wp5_governance.role.extractors
  # i18n-ref: modules.wp5_governance.role.regulators
  # i18n-ref: modules.wp5_governance.role.affectees
  # i18n-ref: modules.wp5_governance.role.beneficiaries
  # i18n-ref: modules.wp5_governance.role.influencers
  df$NERoles <- vapply(strsplit(df$NERoles, ";", fixed = TRUE), function(t) {
    paste(vapply(t, function(r) as.character(i18n$t(paste0("modules.wp5_governance.role.", tolower(r)))),
                 character(1)), collapse = ", ")
  }, character(1))
  df[, setdiff(names(df), "SourceId"), drop = FALSE]
}

#' TRUE when a non-empty register is written in the 14-column schema; older apps
#' rbind() a 12-column row onto it and fail, so it needs WP5_GOVERNANCE_MIN_APP_VERSION
stakeholders_need_governance_version <- function(df) {
  nrow(normalize_stakeholders(df)) > 0
}
