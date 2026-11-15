# Export R's connection knowledge base and synonym table as one JSON file
# (K1b Task 1).
#
#   Rscript scripts/export_r_connection_db.R <R_APP>
#
# <R_APP> is the MarineSABRES_SES_Shiny directory (not the SESToolbox root).
# The output sespy/data/r_kb/ses_connection_db.json is resolved from this
# script's own location. Every value is read from R's own objects
# (SES_CONNECTION_DB, SES_SYNONYM_DB); pattern strings are copied verbatim.

K1B_TAG <- "v1.35.6"

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript scripts/export_r_connection_db.R <R_APP>")
r_app <- normalizePath(args[1], winslash = "/", mustWork = TRUE)

file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_path <- normalizePath(sub("^--file=", "", file_arg[1]), winslash = "/", mustWork = TRUE)
sespy_root <- dirname(dirname(script_path))
out_path <- file.path(sespy_root, "sespy", "data", "r_kb", "ses_connection_db.json")

# ---- Guards: exact tag, and the sourced file untouched ---------------------
sourced <- "data/ses_connection_knowledge_base.R"
git <- function(...) system2("git", c("-C", shQuote(r_app), ...), stdout = TRUE, stderr = TRUE)
tag <- trimws(paste(git("describe", "--tags"), collapse = ""))
if (!identical(tag, K1B_TAG)) stop(sprintf("R checkout is at '%s', expected '%s'", tag, K1B_TAG))
dirty <- git("status", "--porcelain", "--", sourced)
if (length(dirty) > 0) stop("R files modified:\n", paste(dirty, collapse = "\n"))
r_commit <- trimws(paste(git("rev-parse", "--short", "HEAD"), collapse = ""))

# ---- Load only the KB file ---------------------------------------------------
setwd(r_app)
source(sourced, local = FALSE)

# Scalars must stay scalars and the synonym vectors must stay arrays, so check
# the shapes before serialising (auto_unbox would flatten a length-1 vector).
for (i in seq_along(SES_CONNECTION_DB)) {
  e <- SES_CONNECTION_DB[[i]]
  if (!all(vapply(e, length, integer(1)) == 1L)) stop(sprintf("entry %d has a non-scalar field", i))
}
syn <- lapply(SES_SYNONYM_DB, function(v) I(as.character(v)))

doc <- list(version = 1L, r_tag = K1B_TAG, r_commit = r_commit,
            connection_db = unname(SES_CONNECTION_DB), synonym_db = syn)
jsonlite::write_json(doc, out_path, auto_unbox = TRUE, pretty = 1, digits = NA)
cat(sprintf("wrote %s (%d entries, %d synonym groups)\n", out_path,
            length(SES_CONNECTION_DB), length(SES_SYNONYM_DB)))
