r_app_dir <- Sys.getenv("R_APP_DIR"); if (!nzchar(r_app_dir)) stop("set R_APP_DIR to the MarineSABRES_SES_Shiny checkout at v1.35.6"); setwd(r_app_dir)
debug_log <- function(...) invisible(NULL)
`%||%` <- function(a, b) if (is.null(a)) b else a
source("constants.R")
r <- tryCatch({
  if (!exists("load_ml_model", mode = "function")) source("functions/ml_inference.R", local = TRUE)
  load_ml_model(); TRUE
}, error = function(e) { cat("ERR:", conditionMessage(e), "\n"); FALSE })
cat("classifier ok:", r, " ml_model_available exists:", exists("ml_model_available", mode = "function"),
    " torch attached:", "package:torch" %in% search(), "\n")
if (exists("ml_model_available", mode = "function")) cat("ml_model_available():", ml_model_available(), "\n")
