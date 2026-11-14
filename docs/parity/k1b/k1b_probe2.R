r_app_dir <- Sys.getenv("R_APP_DIR"); if (!nzchar(r_app_dir)) stop("set R_APP_DIR to the MarineSABRES_SES_Shiny checkout at v1.35.6"); setwd(r_app_dir)
debug_log <- function(...) invisible(NULL)
`%||%` <- function(a, b) if (is.null(a)) b else a
suppressMessages(source("data/ses_connection_knowledge_base.R"))
suppressMessages(source("modules/ai_isa/connection_generator.R"))
db <- SES_CONNECTION_DB
pats <- c(sapply(db, `[[`, "from_pattern"), sapply(db, `[[`, "to_pattern"))
for (ch in c("+", "(", ")", " ", "?")) cat(sprintf("patterns containing '%s': %d\n", ch, sum(grepl(ch, pats, fixed=TRUE))))
print(head(pats[grepl("(", pats, fixed=TRUE)], 3)); print(head(pats[grepl(" ", pats, fixed=TRUE)], 5)); print(head(pats[grepl("+", pats, fixed=TRUE)], 3))
# fragment set used by .synonym_match
frags <- unique(unlist(lapply(pats, function(p) { t <- trimws(unlist(strsplit(p, "\\||\\.\\*|\\.|\\?|\\*|\\+|\\(|\\)"))); t[nchar(t) >= 3] })))
cat("fragments:", length(frags), " with non [a-z0-9]:", paste(frags[grepl("[^a-z0-9]", frags)], collapse=" | "), "\n")
# IDF weights per key list (from calculate_enhanced_relevance body)
# evaluates only the keyword-list literal from the repo's own function body (local probe, no external input)
f <- calculate_enhanced_relevance
b <- body(f)
# extract the base_keywords list expression: b[[3]] is the if(is.null(base_keywords)) block
idx <- which(sapply(as.list(b), function(e) is.call(e) && identical(e[[1]], as.name("if")) && grepl("is.null(base_keywords)", deparse(e[[2]]), fixed=TRUE)))
blk <- b[[idx]]            # if (is.null(base_keywords)) { base_keywords <- list(...) }
kw <- eval(blk[[3]][[2]][[3]])
for (k in names(kw)) { w <- sapply(kw[[k]], .keyword_idf_weight); cat(sprintf("%s total=%.1f : %s\n", k, sum(w), paste(sprintf("%s=%.1f", names(w), w), collapse=" "))) }
# exact-vs-synonym inversion: does any synonym beat an exact?
res <- 0
types <- unique(t(sapply(db, function(e) c(e$from_type, e$to_type))))
cat("min prob:", min(sapply(db, `[[`, "probability")), "\n")
# Tie/ordering demo: first entry wins on ties (strict >)
cat("lookup Fishing->Bycatch:", unlist(lookup_knowledge_base("Fishing", "activities", "Bycatch", "pressures")), "\n")
# exact low-prob vs synonym high-prob: search candidates
lowp <- Filter(function(e) e$probability <= 0.7, db)
for (e in lowp) cat(sprintf("lowp %s->%s %.2f %s || %s\n", e$from_type, e$to_type, e$probability, e$from_pattern, e$to_pattern))
cat("Ghost nets case:", unlist(lookup_knowledge_base("Fishing", "activities", "Ghost nets", "pressures")), "\n")
cat("Seine->marine litter:", unlist(lookup_knowledge_base("Seine fishing", "activities", "Marine litter", "pressures")), "\n")
# double-neg filter + keyword fallback examples
cat("enh Tourism->Fish decline (A->P):", calculate_enhanced_relevance("Tourism", "Fish decline", "activities", "pressures"), "\n")
cat("enh unknown key (states->drivers):", calculate_enhanced_relevance("x", "y", "states", "drivers"), "\n")
cat("analyze 'pollution reduction':", unlist(analyze_phrase_polarity("pollution reduction")), "\n")
cat("analyze 'no fishing':", unlist(analyze_phrase_polarity("no fishing")), "\n")
cat("analyze 'non-target':", unlist(analyze_phrase_polarity("non-target")), "\n")
cat("analyze 'habitat restoration and loss':", unlist(analyze_phrase_polarity("habitat restoration and loss")), "\n")
# \b semantics with non-ascii under PCRE without UCP
cat("PCRE \\bno\\b on 'noé':", grepl("\\bno\\b", "no\u00e9", perl=TRUE), "  python re would say False (unicode \\w)\n")
cat("PCRE \\bno\\b on 'no-take':", grepl("\\bno\\b", "no-take", perl=TRUE), "\n")
