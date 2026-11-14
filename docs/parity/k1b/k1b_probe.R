r_app_dir <- Sys.getenv("R_APP_DIR"); if (!nzchar(r_app_dir)) stop("set R_APP_DIR to the MarineSABRES_SES_Shiny checkout at v1.35.6"); setwd(r_app_dir)
debug_log <- function(...) invisible(NULL)
`%||%` <- function(a, b) if (is.null(a)) b else a
source("data/ses_connection_knowledge_base.R")
source("modules/ai_isa/connection_generator.R")
cat("R:", R.version.string, " locale:", Sys.getlocale("LC_CTYPE"), "\n")
cat("exists ml_model_available:", exists("ml_model_available", mode="function"), "\n")
db <- SES_CONNECTION_DB
cat("N entries:", length(db), " N syn groups:", length(SES_SYNONYM_DB), " syn terms:", length(unlist(SES_SYNONYM_DB)), "\n")
fields <- sapply(db, function(e) paste(names(e), collapse=","))
print(table(fields))
cat("classes:\n"); print(table(unlist(lapply(db, function(e) sapply(e, function(v) paste(class(v), length(v)))))))
pairs <- sapply(db, function(e) paste(e$from_type, e$to_type, sep="->"))
print(table(pairs))
print(table(sapply(db, `[[`, "polarity"))); print(table(sapply(db, `[[`, "strength")))
print(summary(sapply(db, `[[`, "probability")))
cat("probability distinct decimals:", paste(sort(unique(sapply(db, `[[`, "probability"))), collapse=" "), "\n")
pats <- c(sapply(db, `[[`, "from_pattern"), sapply(db, `[[`, "to_pattern"))
cat("pattern chars outside [a-z0-9 .*?|()+]:\n")
odd <- unique(unlist(regmatches(pats, gregexpr("[^a-z0-9 .*?|()+]", pats))))
print(odd)
for (ch in odd) { cat("--", ch, ":\n"); print(head(pats[grepl(ch, pats, fixed=TRUE)], 5)) }
cat("patterns with uppercase:", sum(grepl("[A-Z]", pats)), "\n")
cat("syn terms with regex meta:\n"); s <- unlist(SES_SYNONYM_DB); print(s[grepl("[^a-z0-9 ]", s)])
cat("syn terms with space:\n"); print(s[grepl(" ", s)])
dup <- duplicated(t(sapply(db, function(e) c(e$from_type, e$to_type, e$from_pattern, e$to_pattern))))
cat("exact duplicate entries:", sum(dup), "\n")
# pattern validity in TRE vs PCRE
bad <- pats[sapply(pats, function(p) inherits(try(grepl(p, "x", perl=TRUE), silent=TRUE), "try-error"))]
cat("invalid PCRE:", length(bad), "\n")
# JSON roundtrip
if (requireNamespace("jsonlite", quietly=TRUE)) {
  j <- jsonlite::toJSON(db, auto_unbox=TRUE, digits=NA)
  back <- jsonlite::fromJSON(j, simplifyVector=FALSE)
  cat("json roundtrip identical (db):", identical(lapply(back, function(e) e[names(db[[1]])]), lapply(db, function(e) e[names(db[[1]])])), "\n")
  js <- jsonlite::toJSON(SES_SYNONYM_DB, digits=NA)
  cat(substr(js, 1, 200), "\n")
  backs <- jsonlite::fromJSON(js, simplifyVector=TRUE)
  cat("json roundtrip syn:", identical(backs, SES_SYNONYM_DB), "\n")
}
# synonym split behaviour
cat("split of 'food.?secur|protein.?demand|nutrition':\n")
print(unlist(strsplit("food.?secur|protein.?demand|nutrition", "\\||\\.\\*|\\.|\\?|\\*|\\+|\\(|\\)")))
# lookups
show <- function(f, ft, t, tt) { r <- lookup_knowledge_base(f, ft, t, tt); cat(sprintf("%s(%s) -> %s(%s): ", f, ft, t, tt)); if (is.null(r)) cat("NULL\n") else cat(unlist(r), "\n"); cat("   enhanced:", calculate_enhanced_relevance(f, t, ft, tt), " polarity:", detect_polarity(f, t, ft, tt), "\n") }
show("Food security", "drivers", "Commercial fishing", "activities")
show("Food security", "drivers", "Netting", "activities")
show("Tourism", "drivers", "Beach recreation", "activities")
show("Tourism demand", "drivers", "Sailing", "activities")
show("Fishing quotas", "responses", "Activities", "activities")
els <- list(
  drivers = list(list(name="Food security"), list(name="Economic growth")),
  activities = list(list(name="Commercial fishing"), list(name="Tourism")),
  pressures = list(list(name="Overfishing"), list(name="Nutrient enrichment")),
  states = list(list(name="Fish stock decline"), list(name="Eutrophication")),
  impacts = list(list(name="Reduced fish provisioning")),
  welfare = list(list(name="Food security loss"), list(name="Income")),
  responses = list(list(name="Fishing quotas"), list(name="Wastewater treatment"))
)
res <- generate_connections(els)
cat("N generated:", length(res), "\n")
cat("fields:", paste(names(res[[1]]), collapse=","), "\n")
for (c in res) cat(sprintf("%-6s %-26s -> %-26s %s %-6s conf=%s %s | %s\n", c$matrix, c$from_name, c$to_name, c$polarity, c$strength, c$confidence, c$scoring_method, c$rationale))
# tie order check: R order() is stable for decreasing? (radix default for short)
x <- c(0.5, 0.7, 0.5, 0.7)
cat("order(decreasing=TRUE) of 0.5,0.7,0.5,0.7:", order(x, decreasing=TRUE), "\n")
# tolower non-ascii
cat("tolower:", tolower("ÉTAT Ø"), " gsub:", gsub("[^a-z ]", "", tolower("Pêche côtière co2 non-target")), "\n")
cat("grepl TRE [a-z] on e-acute:", grepl("^[a-z]$", "\u00e9"), "\n")
cat("strsplit leading space:", deparse(unlist(strsplit(" a  b", "\\s+"))), "\n")
cat("strsplit empty:", deparse(unlist(strsplit("", "\\s+"))), "\n")
