# Capture R's rule-based connection scorer as three gzipped JSON fixtures
# (K1b Task 3): connections (generate_connections goldens), lookup
# (lookup_knowledge_base + calculate_enhanced_relevance) and polarity
# (detect_polarity).
#
#   Rscript scripts/capture_k1b_fixtures.R <R_APP>
#
# <R_APP> is the MarineSABRES_SES_Shiny directory (not the SESToolbox root).
# The output directory is resolved from this script's own location.
#
# Harness: only two R files are sourced, data/ses_connection_knowledge_base.R
# and modules/ai_isa/connection_generator.R, with stubs for debug_log and
# `%||%`. This keeps ML off no matter whether torch is installed (the full app
# can switch ML on through a back door, see docs/parity/k1b/R_SCORER_NOTES.md
# section 4). Every value is recorded by calling R's own functions; nothing is
# computed on the Python side.
#
# generate_connections drops each candidate's relevance. It is recorded by
# wrapping calculate_relevance (the only place the number is produced) in an
# observer that returns R's value unchanged; generate_smart_connections and
# its selection logic are not touched. Every case is also run once WITHOUT the
# observer and the two results must be identical.

K1B_TAG <- "v1.35.6"

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript scripts/capture_k1b_fixtures.R <R_APP>")
r_app <- normalizePath(args[1], winslash = "/", mustWork = TRUE)

file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_path <- normalizePath(sub("^--file=", "", file_arg[1]), winslash = "/", mustWork = TRUE)
sespy_root <- dirname(dirname(script_path))
out_dir <- file.path(sespy_root, "tests", "parity", "r_fixtures", "k1b")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# ---- Guards: exact tag, and the sourced files + template data untouched ----
sourced <- c("data/ses_connection_knowledge_base.R", "modules/ai_isa/connection_generator.R")
template_stems <- c("Aquaculture", "Caribbean", "ClimateChange", "Fisheries",
                    "OffshoreWind", "Pollution", "Tourism")
template_files <- sprintf("data/%s_SES_Template.json", template_stems)
git <- function(...) system2("git", c("-C", shQuote(r_app), ...), stdout = TRUE, stderr = TRUE)
tag <- trimws(paste(git("describe", "--tags"), collapse = ""))
if (!identical(tag, K1B_TAG)) stop(sprintf("R checkout is at '%s', expected '%s'", tag, K1B_TAG))
dirty <- git("status", "--porcelain", "--", sourced, template_files)
if (length(dirty) > 0) stop("R files modified:\n", paste(dirty, collapse = "\n"))
r_commit <- trimws(paste(git("rev-parse", "--short", "HEAD"), collapse = ""))

# ---- Harness -----------------------------------------------------------------
setwd(r_app)
skip_log <- character(0)
debug_log <- function(message, context = NULL) {
  if (grepl("^Skipping double-negative", message)) skip_log <<- c(skip_log, message)
  invisible(NULL)
}
`%||%` <- function(a, b) if (is.null(a)) b else a
Sys.setenv(MARINESABRES_ML_ENABLED = "FALSE")
invisible(capture.output(suppressMessages(for (f in sourced) source(f, local = FALSE))))
if (exists("ml_model_available")) stop("ml_model_available exists: ML could be on")

rel_env <- new.env(hash = TRUE)
key_of <- function(ft, fn, tt, tn) paste(ft, enc2utf8(fn), tt, enc2utf8(tn), sep = "\x1f")
orig_rel <- calculate_relevance
observed_rel <- function(from_name, to_name, from_type, to_type) {
  r <- orig_rel(from_name, to_name, from_type, to_type)
  assign(key_of(from_type, from_name, to_type, to_name), r, envir = rel_env)
  r
}
use_observer <- function(on) assign("calculate_relevance", if (on) observed_rel else orig_rel,
                                    envir = globalenv())

# lookup_knowledge_base is deterministic and R calls it about four times per
# candidate; a memo makes the capture tractable. It returns R's value
# unchanged, and the case self-checks below re-run two cases with the memo off
# and require identical output.
orig_lookup <- lookup_knowledge_base
memo_env <- new.env(hash = TRUE)
memo_lookup <- function(from_name, from_type, to_name, to_type, use_synonyms = TRUE) {
  k <- paste(from_type, enc2utf8(from_name), to_type, enc2utf8(to_name), use_synonyms, sep = "\x1f")
  hit <- memo_env[[k]]
  if (is.null(hit)) {
    hit <- list(m = orig_lookup(from_name, from_type, to_name, to_type, use_synonyms))
    assign(k, hit, envir = memo_env)
  }
  hit$m
}
use_memo <- function(on) assign("lookup_knowledge_base", if (on) memo_lookup else orig_lookup,
                                envir = globalenv())
use_memo(TRUE)

cats <- c("drivers", "activities", "pressures", "states", "impacts", "welfare", "responses")
pairs10 <- list(c("drivers", "activities"), c("activities", "pressures"),
                c("pressures", "states"), c("states", "impacts"), c("impacts", "welfare"),
                c("responses", "pressures"), c("welfare", "drivers"), c("welfare", "responses"),
                c("responses", "drivers"), c("responses", "activities"))
as_elements <- function(el) lapply(el, function(v) lapply(v, function(n) list(name = n)))

# ---- 1. connections ------------------------------------------------------------
run_case <- function(id, el) {
  el <- el[cats]
  stopifnot(all(lengths(el) >= 0), identical(names(el), cats))
  r_el <- as_elements(el)
  use_observer(FALSE)
  plain <- generate_connections(r_el)
  use_observer(TRUE)
  skip_log <<- character(0)
  rel_env <<- new.env(hash = TRUE)
  observed <- generate_connections(r_el)
  n_skipped <- length(skip_log)
  use_observer(FALSE)
  if (!identical(plain, observed)) stop("observer changed R's output for case ", id)
  rows <- lapply(observed, function(cn) {
    rel <- get(key_of(cn$from_type, cn$from_name, cn$to_type, cn$to_name), envir = rel_env)
    list(from_type = cn$from_type, from_index = cn$from_index, from_name = cn$from_name,
         to_type = cn$to_type, to_index = cn$to_index, to_name = cn$to_name,
         polarity = cn$polarity, strength = cn$strength, confidence = cn$confidence,
         scoring_method = cn$scoring_method, rationale = cn$rationale, relevance = rel)
  })
  cat(sprintf("case %-24s %3d rows, %2d double-negative skips\n", id, length(rows), n_skipped))
  list(id = id, elements = lapply(el, as.list), rows = rows, n_skipped = n_skipped)
}

template_elements <- function(stem) {
  j <- jsonlite::fromJSON(sprintf("data/%s_SES_Template.json", stem), simplifyDataFrame = FALSE)
  fw <- j$dapsiwrm_framework
  nm <- function(l) as.character(vapply(l %||% list(), function(e) e$name, ""))
  # R's template_loader folds `measures` after `responses`.
  list(drivers = nm(fw$drivers), activities = nm(fw$activities), pressures = nm(fw$pressures),
       states = nm(fw$marine_processes %||% fw$states),
       impacts = nm(fw$ecosystem_services %||% fw$impacts),
       welfare = nm(fw$goods_benefits %||% fw$welfare),
       responses = c(nm(fw$responses), nm(fw$measures)))
}

worked <- list(
  drivers = c("Food security", "Economic growth"),
  activities = c("Commercial fishing", "Tourism"),
  pressures = c("Overfishing", "Nutrient enrichment"),
  states = c("Fish stock decline", "Eutrophication"),
  impacts = "Reduced fish provisioning",
  welfare = c("Food security loss", "Income"),
  responses = c("Fishing quotas", "Wastewater treatment"))

stress <- list(
  drivers = c("Food security", "Economic growth", "Energy demand", "Declining fish demand"),
  activities = c("Commercial fishing", "Bottom trawling", "Aquaculture", "Shipping", "Tourism",
                 "Dredging", "Offshore wind", "Coastal development", "Recreational angling",
                 "Seine fishing", "Mussel farming", "Port operations", "Beach recreation",
                 "Sand extraction", "Cruise tourism", "Gillnetting", "Fish farming",
                 "Harbour construction", "Agriculture runoff", "Oil extraction"),
  pressures = c("Overfishing", "Seabed abrasion", "Nutrient enrichment", "Chemical pollution",
                "Underwater noise", "Habitat loss", "Marine litter", "Ghost nets", "Bycatch",
                "Invasive species", "Antibiotics", "Ship strikes", "Sediment disturbance",
                "Oil spills", "Light pollution", "Thermal discharge", "Escapees",
                "Organic enrichment", "Physical disturbance", "Wastewater discharge"),
  states = c("Fish stock decline", "Eutrophication", "Habitat loss", "Seagrass degradation",
             "Water quality", "Coral bleaching", "Biodiversity", "Hypoxia"),
  impacts = c("Reduced fish provisioning", "Loss of recreation opportunities",
              "Degraded water quality", "Nursery habitat", "Coastal protection",
              "Climate regulation"),
  welfare = c("Food security loss", "Income", "Income loss", "Human health", "Cultural identity",
              "Employment"),
  responses = c("Fishing quotas", "Wastewater treatment", "Marine protected area",
                "Reduced fishing effort", "Gear restrictions", "Habitat restoration"))

quirks <- list(
  drivers = c("FOOD SECURITY", "  Economic growth  ", "Food security", "Food security",
              "Sécurité alimentaire"),
  activities = c("Pêche côtière", "COMMERCIAL FISHING", "Commercial fishing ",
                 "Public service operations", "Tourism"),
  pressures = c("Overfishing", "OVERFISHING", "Impact on the seabed", "Nutrient enrichment",
                "Pêche côtière"),
  states = c("Fish stock decline", "Eutrophication", "Ecosystem collapse", "Coastal ecosystem",
             "ÉTAT DE L'ÉCOSYSTÈME CÔTIER"),
  impacts = c("Ecosystem services", "Reduced fish provisioning", "Cultural service loss",
              "Impact on tourism", "Pêche côtière"),
  welfare = c("Food security loss", "Income", "Public services", "Revenu côtier", "Income"),
  responses = c("Fishing quotas", "Wastewater treatment", "  Marine protected area ",
                "MPA designation", "Service delivery improvement"))

cases <- c(
  lapply(template_stems, function(s) run_case(s, template_elements(s))),
  list(run_case("wizard_worked_example", worked),
       run_case("wizard_stress", stress),
       run_case("wizard_text_quirks", quirks)))
names(cases) <- vapply(cases, function(c) c$id, "")

# ---- Case self-checks ----------------------------------------------------------
# R notes section 1: the worked example has exactly these 16 rows, in order.
expected_worked <- c(
  "drivers|Food security|activities|Commercial fishing|+|strong|4|kb",
  "drivers|Economic growth|activities|Commercial fishing|+|strong|4|kb",
  "activities|Commercial fishing|pressures|Overfishing|+|strong|4|kb",
  "activities|Commercial fishing|pressures|Nutrient enrichment|+|strong|3|kb",
  "pressures|Overfishing|states|Fish stock decline|-|strong|4|kb",
  "pressures|Nutrient enrichment|states|Eutrophication|+|strong|4|kb",
  "pressures|Nutrient enrichment|states|Fish stock decline|+|strong|3|kb",
  "pressures|Overfishing|states|Eutrophication|-|medium|3|kb",
  "impacts|Reduced fish provisioning|welfare|Income|-|strong|3|kb",
  "responses|Fishing quotas|pressures|Overfishing|-|strong|4|kb",
  "responses|Wastewater treatment|pressures|Nutrient enrichment|-|strong|3|kb",
  "welfare|Food security loss|drivers|Food security|+|medium|3|keyword",
  "welfare|Food security loss|drivers|Economic growth|+|medium|3|keyword",
  "welfare|Income|drivers|Food security|+|medium|3|keyword",
  "welfare|Income|drivers|Economic growth|+|medium|3|keyword",
  "responses|Fishing quotas|activities|Commercial fishing|-|strong|3|kb")
got_worked <- vapply(cases$wizard_worked_example$rows, function(r)
  paste(r$from_type, r$from_name, r$to_type, r$to_name, r$polarity, r$strength,
        r$confidence, r$scoring_method, sep = "|"), "")
if (!identical(got_worked, expected_worked)) {
  stop("worked example differs from R notes section 1:\n", paste(got_worked, collapse = "\n"))
}

# The lookup memo must not change R's output: re-run two cases without it.
for (id in c("wizard_worked_example", "Fisheries")) {
  el <- as_elements(cases[[id]]$elements)
  with_memo <- generate_connections(el)
  use_memo(FALSE); no_memo <- generate_connections(el); use_memo(TRUE)
  if (!identical(with_memo, no_memo)) stop("lookup memo changed R's output for ", id)
  cat("memo-off identity ok:", id, "\n")
}

# The stress case must make the cap bind and put a relevance tie across the
# 15th place of activities -> pressures.
ap_rel <- sort(as.vector(outer(stress$activities, stress$pressures, Vectorize(function(a, p)
  orig_rel(a, p, "activities", "pressures")))), decreasing = TRUE)
if (length(ap_rel) <= 15 || ap_rel[15] != ap_rel[16]) stop("stress: no tie across the 15th place")
n_ap <- sum(vapply(cases$wizard_stress$rows, function(r) r$from_type == "activities", TRUE))
if (n_ap != 15) stop("stress: activities -> pressures not capped at 15")
if (cases$wizard_stress$n_skipped < 3) stop("stress: fewer than 3 double-negative skips")
cat(sprintf("stress: a_p sorted relevance [14..17] = %s\n",
            paste(format(ap_rel[14:17], digits = 17), collapse = " ")))

# ---- 2. lookup ----------------------------------------------------------------------
# About 300 rows, chosen deliberately (not a cross-product): every name pair of
# the text-quirks case, plus from the stress case the pairs R kept for
# activities -> pressures and the first 3 x 3 names of every type pair.
lk_cache <- new.env(hash = TRUE)
cached_lookup <- function(fn, ft, tn, tt) {
  k <- key_of(ft, fn, tt, tn)
  hit <- lk_cache[[k]]
  if (is.null(hit)) {
    hit <- list(m = lookup_knowledge_base(fn, ft, tn, tt))
    assign(k, hit, envir = lk_cache)
  }
  hit$m
}
lookup_row <- function(fn, ft, tn, tt) {
  m <- cached_lookup(fn, ft, tn, tt)
  list(from_name = fn, from_type = ft, to_name = tn, to_type = tt,
       match = if (is.null(m)) NA else list(polarity = m$polarity, strength = m$strength,
                                            match_quality = m$match_quality,
                                            probability = m$probability),
       relevance = calculate_enhanced_relevance(from_name = fn, to_name = tn,
                                                from_type = ft, to_type = tt))
}
lk_seen <- new.env(hash = TRUE); lk <- list()
add_lk <- function(fn, ft, tn, tt) {
  k <- key_of(ft, fn, tt, tn)
  if (!is.null(lk_seen[[k]])) return(invisible(NULL))
  assign(k, TRUE, envir = lk_seen)
  lk[[length(lk) + 1]] <<- lookup_row(fn, ft, tn, tt)
}
for (p in pairs10) {
  for (fn in quirks[[p[1]]]) for (tn in quirks[[p[2]]]) add_lk(fn, p[1], tn, p[2])
  for (fn in head(stress[[p[1]]], 3)) for (tn in head(stress[[p[2]]], 3)) add_lk(fn, p[1], tn, p[2])
}
for (r in cases$wizard_stress$rows) if (r$from_type == "activities")
  add_lk(r$from_name, r$from_type, r$to_name, r$to_type)
# The known synonym winner over an exact match (R notes section 2.1).
add_lk("Fish farming", "activities", "Chemical pollution", "pressures")
q <- vapply(lk, function(r) if (is.list(r$match)) r$match$match_quality else "none", "")
cat("lookup rows:", length(lk), " match kinds:", paste(names(table(q)), table(q), collapse = ", "), "\n")
if (length(lk) < 200 || !all(c("exact", "synonym", "none") %in% q)) stop("lookup coverage")
syn_only <- Filter(function(r) is.list(r$match) && r$match$match_quality == "synonym" &&
  is.null(lookup_knowledge_base(r$from_name, r$from_type, r$to_name, r$to_type,
                                use_synonyms = FALSE)), lk)
cat("synonym-only pairs in lookup:", length(syn_only), "\n")
if (length(syn_only) < 1) stop("no synonym-only pair in the lookup rows")

# ---- 3. polarity ------------------------------------------------------------------------
# Keyword lists copied from connection_generator.R detect_polarity and
# ses_connection_knowledge_base.R analyze_phrase_polarity (tag-guarded above).
negative_keywords <- c("declin", "degrad", "loss", "reduc", "damag", "destruct", "pollut",
  "eutrophic", "overfish", "bycatch", "invasive", "extinct", "harm", "contaminat", "erosion",
  "acidific", "hypox", "dead zone", "bleach", "disease", "mortality", "collapse", "fragment",
  "depletion")
positive_keywords <- c("increas", "growth", "restor", "recover", "improv", "enhanc", "protect",
  "conserv", "benefit", "health", "sustain", "resilient", "biodiver", "abundance", "productiv",
  "regenerat", "rehabilit", "rebui")
mitigation_keywords <- c("ban", "prohibit", "restrict", "limit", "regulat", "control", "manag",
  "reduce", "prevent", "mitigat", "protect", "enforce", "monitor", "stop", "remov", "clean",
  "treat")
phrase_positive_kw <- c("increas", "improv", "enhanc", "restor", "recover", "growth", "benefit",
  "gain", "protect", "conserv", "sustain", "resilient", "healthy", "abundant")
phrase_negative_kw <- c("declin", "loss", "degrad", "damag", "destruct", "pollut", "contamin",
  "overfish", "erosion", "deplet", "collapse", "extinct", "harm", "bleach", "hypox", "mortality")
negation_words <- c("no", "not", "non-", "without", "prevent", "prohibit", "ban", "banned",
  "reduc", "remov", "elimin", "avoid", "control", "limit", "restrict", "stop", "less", "lack",
  "absence")
reversal_compounds <- c("pollut.*reduc", "pollut.*remov", "pollut.*control", "emission.*reduc",
  "emission.*control", "emission.*limit", "pressure.*reduc", "stress.*reduc", "risk.*reduc",
  "litter.*reduc", "litter.*remov", "litter.*clean", "waste.*reduc", "waste.*treat",
  "waste.*remov", "erosion.*control", "erosion.*prevent", "noise.*reduc", "noise.*control",
  "overfish.*prevent", "overfish.*reduc", "deforest.*prevent", "habitat.*loss.*prevent",
  "decline.*halt", "decline.*revers", "degradat.*halt", "degradat.*revers")
reversal_phrases <- vapply(reversal_compounds, function(p) gsub("\\.\\*", " ", p), "")
kw_phrase <- function(w) paste0("Qzx ", w, " yz")

# About 300 rows, deliberate: each keyword / negation / reversal rule gets one
# phrase, in the role where the pair's rule reads it.
pol_seen <- new.env(hash = TRUE); pol <- list()
add_pol <- function(fn, tn, ft, tt) {
  k <- key_of(ft, fn, tt, tn)
  if (!is.null(pol_seen[[k]])) return(invisible(NULL))
  assign(k, TRUE, envir = pol_seen)
  pol[[length(pol) + 1]] <<- list(from_name = fn, to_name = tn, from_type = ft, to_type = tt,
                                  polarity = detect_polarity(fn, tn, ft, tt))
}
thing <- "Qzx thing"
# A-P reads the source: mitigation keywords, phrase sentiment, negation, reversal.
for (f in c(kw_phrase(mitigation_keywords), kw_phrase(c(phrase_positive_kw, phrase_negative_kw)),
            paste0("Qzx ", negation_words, " decline"), kw_phrase(reversal_phrases)))
  add_pol(f, thing, "activities", "pressures")
# P-S reads the target: negative and positive keywords.
for (t in kw_phrase(c(negative_keywords, positive_keywords))) add_pol(thing, t, "pressures", "states")
# S-I reads both sides, with negation and reversal clearing the negative flag.
for (f in c(paste0("Qzx ", negation_words, " decline"), kw_phrase(reversal_phrases)))
  add_pol(f, "Qzx decline", "states", "impacts")
s3 <- c(thing, "Qzx decline", "Qzx growth", "No qzx decline", "Qzx growth and decline")
for (f in s3) for (t in s3) add_pol(f, t, "states", "impacts")
# I-W reads the source's sentiment keywords.
for (f in kw_phrase(c(negative_keywords, positive_keywords))) add_pol(f, thing, "impacts", "welfare")
# No-rule pairs (default "+") and R-P ("-" always).
small <- c(thing, "Qzx decline", "Qzx growth")
for (p in pairs10) for (f in small) for (t in small) add_pol(f, t, p[1], p[2])
# KB-first polarity: every kept row of the worked example and of the stress
# activities -> pressures block.
for (r in cases$wizard_worked_example$rows) add_pol(r$from_name, r$to_name, r$from_type, r$to_type)
for (r in cases$wizard_stress$rows) if (r$from_type == "activities")
  add_pol(r$from_name, r$to_name, r$from_type, r$to_type)

pp <- vapply(pol, function(r) paste(r$from_type, r$to_type, sep = ">"), "")
kb_free <- vapply(pol, function(r) is.null(cached_lookup(r$from_name, r$from_type,
                                                         r$to_name, r$to_type)), TRUE)
cat("polarity rows:", length(pol), " without a KB hit:", sum(kb_free), "\n")
for (p in pairs10) {
  k <- paste(p, collapse = ">")
  sel <- pp == k & kb_free
  v <- vapply(pol[sel], function(r) r$polarity, "")
  cat(sprintf("  %-22s rows %3d kb-free %3d  plus %3d minus %3d\n", k, sum(pp == k), sum(sel),
              sum(v == "+"), sum(v == "-")))
}
if (length(pol) < 150) stop("polarity coverage")

# ---- Write -----------------------------------------------------------------------------
write_fixture <- function(name, key, value) {
  doc <- list(r_tag = K1B_TAG, r_commit = r_commit)
  doc[[key]] <- value
  json <- jsonlite::toJSON(doc, auto_unbox = TRUE, null = "null", na = "null",
                           digits = NA, pretty = FALSE)
  path <- file.path(out_dir, paste0(name, ".json.gz"))
  con <- gzfile(path, "wb")
  writeLines(enc2utf8(as.character(json)), con, useBytes = TRUE)
  close(con)
  cat("wrote", path, file.size(path), "bytes\n")
  path
}
conn_cases <- lapply(unname(cases), function(c) c[c("id", "elements", "rows")])
p1 <- write_fixture("connections", "cases", conn_cases)
p2 <- write_fixture("lookup", "rows", lk)
p3 <- write_fixture("polarity", "rows", pol)

# ---- Read-back: doubles must survive the round trip -------------------------------------
back <- function(p) jsonlite::fromJSON(gzfile(p, "rb"), simplifyVector = FALSE, simplifyDataFrame = FALSE)
b1 <- back(p1); b2 <- back(p2)
max_err <- 0
for (i in seq_along(cases)) {
  stopifnot(identical(b1$cases[[i]]$id, cases[[i]]$id),
            length(b1$cases[[i]]$rows) == length(cases[[i]]$rows))
  for (j in seq_along(cases[[i]]$rows)) {
    a <- cases[[i]]$rows[[j]]$relevance; b <- b1$cases[[i]]$rows[[j]]$relevance
    max_err <- max(max_err, abs(a - b))
  }
}
for (j in seq_along(lk)) max_err <- max(max_err, abs(lk[[j]]$relevance - b2$rows[[j]]$relevance))
cat(sprintf("max round-trip relevance error: %g\n", max_err))
if (max_err > 1e-12) stop("doubles did not round-trip")
cat(sprintf("ok: %d cases (%s rows), %d lookup rows, %d polarity rows\n", length(cases),
            paste(vapply(cases, function(c) length(c$rows), 1L), collapse = "/"), length(lk),
            length(pol)))
