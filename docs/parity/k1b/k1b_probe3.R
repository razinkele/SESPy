r_app_dir <- Sys.getenv("R_APP_DIR"); if (!nzchar(r_app_dir)) stop("set R_APP_DIR to the MarineSABRES_SES_Shiny checkout at v1.35.6"); setwd(r_app_dir)
debug_log <- function(...) invisible(NULL)
`%||%` <- function(a, b) if (is.null(a)) b else a
suppressMessages(source("data/ses_connection_knowledge_base.R"))
db <- SES_CONNECTION_DB
# find (from,to) name pairs where the winner is a synonym match although some exact match exists
names_from <- c("Fishing", "Commercial fishing", "Trawling", "Seine fishing", "Aquaculture", "Fish farming", "Shipping")
names_to <- c("Ghost nets", "Marine litter", "Abandoned gear and litter", "Chemical pollution", "Invasive species", "Antibiotics", "Escapees", "Ship strikes", "Collision with marine mammals")
for (f in names_from) for (t in names_to) {
  r <- lookup_knowledge_base(f, "activities", t, "pressures")
  ex <- lookup_knowledge_base(f, "activities", t, "pressures", use_synonyms = FALSE)
  if (!is.null(r) && !is.null(ex) && r$match_quality == "synonym")
    cat(sprintf("%s -> %s : winner synonym p=%.4f (%s %s) beats exact p=%.2f (%s %s)\n", f, t, r$probability, r$polarity, r$strength, ex$probability, ex$polarity, ex$strength))
}
