# Capture R's knowledge-base behaviour as five gzipped JSON fixtures (K1 Task 2).
#
#   Rscript scripts/capture_k1_fixtures.R <R_APP>
#
# <R_APP> is the MarineSABRES_SES_Shiny directory (not the SESToolbox root).
# The sespy/regional_seas.json file and the output directory are resolved from
# this script's own location. Every value is recorded by calling R's own
# functions; nothing is computed on the Python side.

K1_TAG <- "v1.35.6"

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript scripts/capture_k1_fixtures.R <R_APP>")
r_app <- normalizePath(args[1], winslash = "/", mustWork = TRUE)

file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_path <- normalizePath(sub("^--file=", "", file_arg[1]), winslash = "/", mustWork = TRUE)
sespy_root <- dirname(dirname(script_path))
seas_path <- file.path(sespy_root, "sespy", "regional_seas.json")
out_dir <- file.path(sespy_root, "tests", "parity", "r_fixtures", "k1")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# ---- Guards: exact tag, and the sourced files + data untouched -------------
sourced <- c("modules/ai_isa_knowledge_base.R",
             "functions/ses_knowledge_db_loader.R",
             "functions/country_governance_loader.R",
             "functions/kb_report_helpers.R")
data_files <- c("data/ses_knowledge_db.json", "data/country_governance_db.json")
git <- function(...) system2("git", c("-C", shQuote(r_app), ...), stdout = TRUE, stderr = TRUE)
tag <- trimws(paste(git("describe", "--tags"), collapse = ""))
if (!identical(tag, K1_TAG)) stop(sprintf("R checkout is at '%s', expected '%s'", tag, K1_TAG))
dirty <- git("status", "--porcelain", "--", sourced, data_files)
if (length(dirty) > 0) stop("R files modified:\n", paste(dirty, collapse = "\n"))
r_commit <- trimws(paste(git("rev-parse", "--short", "HEAD"), collapse = ""))

# ---- Setup -------------------------------------------------------------------
setwd(r_app)
debug_log <- function(message, context = NULL) invisible(NULL)
if (!exists("%||%", mode = "function")) `%||%` <- function(x, y) if (is.null(x)) y else x
Sys.setenv(MARINESABRES_ML_ENABLED = "FALSE")
suppressMessages({
  for (f in sourced) source(f, local = FALSE)
})

seas <- jsonlite::fromJSON(seas_path, simplifyDataFrame = FALSE)$regional_seas
cats <- c("drivers", "activities", "pressures", "states", "impacts", "welfare", "responses")
gov <- jsonlite::fromJSON("data/country_governance_db.json", simplifyDataFrame = FALSE)

# From R v1.35.0 get_context_suggestions ignores main_issue; two sets are
# enough to evidence that (the shape test asserts identical items).
issue_sets <- list(character(0), c("Eutrophication", "Overfishing"))
cover_set <- c("FR", "RU", "FM", "ZA", "BZ", "DK", "AU")

nz <- function(x) if (is.null(x)) NA_character_ else x
write_fixture <- function(name, data) {
  json <- jsonlite::toJSON(list(r_tag = K1_TAG, r_commit = r_commit, data = data),
                           auto_unbox = TRUE, null = "null", na = "null", pretty = FALSE)
  path <- file.path(out_dir, paste0(name, ".json.gz"))
  con <- gzfile(path, "wb")
  writeLines(enc2utf8(as.character(json)), con, useBytes = TRUE)
  close(con)
  cat("wrote", path, file.size(path), "bytes\n")
}
row_of <- function(sea, eco, m) {
  list(sea = sea, ecosystem = eco, key = nz(if (is.null(m)) NULL else m$key),
       match = if (is.null(m)) "fallback" else m$match)
}

t0 <- Sys.time()

# ---- 1. lookup ---------------------------------------------------------------
choices <- list()
for (sea in names(seas)) for (eco in seas[[sea]]$ecosystem_types) {
  choices[[length(choices) + 1]] <- row_of(sea, eco, .find_context(sea, eco))
}
free_text <- lapply(list(c("baltic", "Coastal lagoon and delta"),
                         c("mediterranean", "Posidonia meadows"),
                         c("baltic", "Schären archipelago")),
                    function(p) row_of(p[1], p[2], .find_context(p[1], p[2])))
write_fixture("lookup", list(choices = choices, free_text = free_text))

# ---- 2. suggestions_grid (dedup lists by serialised content, O(n)) ------------
sources <- list(); id_of <- new.env(hash = TRUE); cells <- list(); n_ids <- 0L
country_sets <- function(sea) {
  codes <- unlist(gov$countries_by_sea[[sea]])
  list(character(0), head(codes, 2), rev(head(codes, 2)), cover_set)
}
for (sea in names(seas)) {
  csets <- country_sets(sea)
  for (eco in seas[[sea]]$ecosystem_types) for (cc in cats) {
    for (iss in issue_sets) for (cs in csets) {
      r <- get_context_suggestions(cc, sea, eco, iss,
                                   countries = if (length(cs)) cs else NULL,
                                   return_sources = TRUE)
      nm <- as.character(r$suggestions); sr <- unname(as.character(r$sources))
      key <- paste0("k:", paste(c(rbind(nm, sr)), collapse = "\x1f"))
      id <- id_of[[key]]
      if (is.null(id)) {
        n_ids <- n_ids + 1L
        id <- sprintf("L%d", n_ids)
        id_of[[key]] <- id
        sources[[id]] <- lapply(seq_along(nm), function(i) list(nm[i], sr[i]))
      }
      cells[[length(cells) + 1]] <- list(sea = sea, ecosystem = eco, category = cc,
        issues = as.list(iss), countries = as.list(cs), items = id)
    }
  }
}
write_fixture("suggestions_grid", list(sources = sources, cells = cells))

# ---- 3. habitat_specific ------------------------------------------------------
hab <- list()
for (sea in names(seas)) for (eco in seas[[sea]]$ecosystem_types) for (cc in cats) {
  hab[[length(hab) + 1]] <- list(sea = sea, ecosystem = eco, category = cc,
    items = as.list(as.character(get_habitat_specific_suggestions(cc, sea, eco))))
}
write_fixture("habitat_specific", hab)

# ---- 4. countries ---------------------------------------------------------------
countries <- list()
for (sea in names(seas)) {
  countries[[sea]] <- lapply(unname(get_countries_for_sea(sea)), function(r)
    list(code = r$code, name_en = r$name_en, eu_member = isTRUE(r$eu_member)))
}
write_fixture("countries", countries)

# ---- 5. report --------------------------------------------------------------------
mk_edges <- function(from, to) data.frame(from_label = from, to_label = to, stringsAsFactors = FALSE)
cases <- list(
  baltic_lagoon = list(sea = "baltic", eco = "Coastal lagoon", edges = mk_edges(
    c("Agricultural drainage into lagoon",   # matches a KB connection
      "Cyanobacteria bloom formation",       # matches a KB connection
      "Wind farm construction noise",        # no match
      "Recreational boating",                # no match
      ""),                                   # empty from-label
    c("Nutrient enrichment from agricultural sources",
      "Water transparency and light penetration",
      "Seal haul-out disturbance",
      "Seabed scouring",
      "Nutrient loading"))),
  med_seagrass = list(sea = "mediterranean", eco = "Seagrass meadow", edges = NULL),
  irish_sea = list(sea = "irish_sea", eco = "Open coast", edges = NULL)
)
report <- list()
for (id in names(cases)) {
  cs <- cases[[id]]
  kb <- get_kb_context_for_report(cs$sea, cs$eco)
  matched <- match_user_connections_to_kb(cs$edges, cs$sea, cs$eco)
  g <- get_governance_context(cs$sea)
  md <- paste0("# Regional Context\n\n", format_kb_section_for_report(kb, matched, g))
  edges <- if (is.null(cs$edges)) list() else
    lapply(seq_len(nrow(cs$edges)), function(i) list(cs$edges$from_label[i], cs$edges$to_label[i]))
  report[[id]] <- list(sea = cs$sea, ecosystem = cs$eco, edges = edges, markdown = md)
}
write_fixture("report", report)

cat(sprintf("ok: %d choices, %d cells, %d distinct lists, %d habitat rows, %.1f min\n",
            length(choices), length(cells), n_ids, length(hab),
            as.numeric(difftime(Sys.time(), t0, units = "mins"))))
