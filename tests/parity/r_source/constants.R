# =============================================================================
# CONSTANTS: Marine SES Network Analysis
# File: constants.R
# =============================================================================
#
#' @title MarineSABRES SES Toolbox Constants
#'
#' @description
#' Centralized configuration for all constants, magic numbers, and thresholds
#' used throughout the MarineSABRES SES Toolbox application. This file provides
#' a single source of truth for configuration values.
#'
#' @section Constant Categories:
#' \itemize{
#'   \item Loop Analysis - Thresholds for feedback loop detection
#'   \item Network Generation - Default sizes and density parameters
#'   \item DAPSIWRM Elements - Framework category definitions
#'   \item Visualization - Colors, shapes, and styling constants
#'   \item Confidence Levels - Connection certainty parameters
#'   \item UI Layout - Spacing, sizing, and timing values
#' }
#'
#' @seealso
#' \code{\link{DAPSIWRM_ELEMENTS}} for framework element types
#' \code{\link{ELEMENT_COLORS}} for visualization colors
#'
#' @name constants
#' @keywords internal
NULL

# =============================================================================
# LOOP ANALYSIS CONSTANTS
# =============================================================================

# Performance thresholds for adaptive loop analysis
LOOP_LARGE_GRAPH_THRESHOLD <- 20      # Nodes count for "large" graph classification
LOOP_MEDIUM_GRAPH_THRESHOLD <- 15     # Nodes count for "medium" graph classification

# Loop detection limits
LOOP_DEFAULT_MIN_LENGTH <- 3          # Minimum meaningful loop length
LOOP_DEFAULT_MAX_LENGTH <- 6          # Default maximum loop length
LOOP_DEFAULT_MAX_LOOPS <- 50          # Default maximum loops to return

# Adaptive limits for large graphs
LOOP_LARGE_MAX_LENGTH <- 4            # Max loop length for large graphs
LOOP_LARGE_MAX_LOOPS <- 20            # Max loops to find in large graphs
LOOP_MEDIUM_MAX_LENGTH <- 5           # Max loop length for medium graphs
LOOP_MEDIUM_MAX_LOOPS <- 30           # Max loops to find in medium graphs

# Performance limits
LOOP_ANALYSIS_TIMEOUT_SECONDS <- 30   # Timeout for loop analysis
LOOP_SAMPLING_THRESHOLD <- 1000       # Max combinations before sampling

# ============================================================================
# NETWORK GENERATION CONSTANTS
# ============================================================================

# Default network sizes
DEFAULT_SIMPLE_LOOP_NODES <- 3
DEFAULT_MARINE_SES_NODES <- 18
DEFAULT_COMPREHENSIVE_SES_NODES <- 24
DEFAULT_RANDOM_NETWORK_NODES <- 15

# Network density targets
TARGET_NETWORK_DENSITY <- 0.15        # Target ~15% edge density
RANDOM_NETWORK_PROBABILITY <- 0.4     # Edge probability for random networks

# Edge attribute ranges
EDGE_WEIGHT_MIN <- 1.0
EDGE_WEIGHT_MAX <- 10.0
EDGE_STRENGTH_MIN <- -5.0
EDGE_STRENGTH_MAX <- 5.0
EDGE_CONFIDENCE_MIN <- 1
EDGE_CONFIDENCE_MAX <- 5

# Specific ranges for marine SES networks
MARINE_WEIGHT_MIN <- 3.0
MARINE_WEIGHT_MAX <- 8.0
MARINE_STRENGTH_MIN <- -2.0
MARINE_STRENGTH_MAX <- 4.0

# ============================================================================
# ML ENSEMBLE CONSTANTS (P2 #26)
# ============================================================================

# Ensemble size configuration
ML_ENSEMBLE_DEFAULT_SIZE <- 5           # Default number of models in ensemble
ML_ENSEMBLE_MIN_SIZE <- 3               # Minimum for meaningful diversity
ML_ENSEMBLE_MAX_SIZE <- 10              # Maximum to limit memory/compute

# Training seeds for reproducibility
ML_ENSEMBLE_SEEDS <- c(42, 123, 456, 789, 1024, 2048, 3072, 4096, 5120, 6144)

# Ensemble aggregation thresholds
ML_ENSEMBLE_AGREEMENT_THRESHOLD <- 0.8  # High agreement = >80% models agree
ML_ENSEMBLE_CONFIDENCE_THRESHOLD <- 0.7 # Minimum confidence for predictions

# Active learning (disagreement-based)
ML_ACTIVE_LEARNING_BATCH_SIZE <- 10     # Samples per active learning round
ML_DISAGREEMENT_HIGH_THRESHOLD <- 0.4   # High disagreement = >40% variance
ML_DISAGREEMENT_LOW_THRESHOLD <- 0.1    # Low disagreement = <10% variance

# Model architecture
ML_EMBEDDING_DIM <- 128                 # Embedding dimension
ML_HIDDEN_DIMS <- c(256, 128, 64)       # Hidden layer dimensions
ML_DROPOUT_RATE <- 0.3                  # Dropout for regularization

# Training hyperparameters
ML_DEFAULT_EPOCHS <- 100                # Default training epochs
ML_DEFAULT_LEARNING_RATE <- 0.001       # Default learning rate
ML_DEFAULT_BATCH_SIZE <- 32             # Default batch size
ML_EARLY_STOPPING_PATIENCE <- 15        # Epochs to wait before early stopping

# ============================================================================
# MARINE SES CATEGORIES
# ============================================================================

# Standard marine SES node groups (legacy naming)
MARINE_SES_CATEGORIES <- c(
  "Activities",
  "Pressures",
  "Drivers",
  "Societal Goods and Services",
  "Ecosystem Services",
  "Marine Processes"
)

# DAPSI(W)R(M) element types (MarineSABRES standard naming)
DAPSIWRM_ELEMENTS <- c(
  "Drivers",
  "Activities",
  "Pressures",
  "Marine Processes & Functioning",
  "Ecosystem Services",
  "Goods & Benefits",
  "Responses"
)

# DAPSI(W)R(M) element ID prefixes (for generating element IDs like "D001", "A002")
ELEMENT_ID_PREFIX <- list(
  drivers    = "D",
  activities = "A",
  pressures  = "P",
  states     = "MPF",   # Marine Processes & Functioning
  impacts    = "ES",    # Ecosystem Services
  welfare    = "GB",    # Goods & Benefits
  responses  = "R",
  measures   = "RM"     # Response Measures
)

# PIMS module ID prefixes
PIMS_ID_PREFIX <- list(
  stakeholder   = "SH",
  engagement    = "ENG",
  communication = "COMM"
)

# Minimum nodes per category
MIN_NODES_PER_CATEGORY <- 1
DEFAULT_NODES_PER_CATEGORY <- 3

# Network size constraints
MIN_MARINE_SES_NODES <- 6             # 1 per category minimum
MAX_MARINE_SES_NODES <- 100           # Performance warning threshold

# ============================================================================
# CENTRALITY ANALYSIS CONSTANTS
# ============================================================================

# Default top N for leverage points
DEFAULT_TOP_N_LEVERAGE <- 10

# ============================================================================
# VISUALIZATION CONSTANTS
# ============================================================================

# Node visualization
DEFAULT_NODE_SIZE <- 40              # Standard node size for network visualizations
LARGE_NODE_SIZE <- 50                # Large node size for graphical SES creator
SMALL_NODE_SIZE <- 25                # Small node size for compact views
MEDIUM_NODE_SIZE <- 30               # Medium node size for moderate views
LEVERAGE_NODE_SIZE <- 45             # Node size for leverage points
MIN_NODE_SIZE <- 15                  # Minimum node size for scaling
MAX_NODE_SIZE <- 50                  # Maximum node size for scaling

DEFAULT_NODE_COLOR <- "lightgray"
LEVERAGE_NODE_COLOR <- "orange"

# Node borders
DEFAULT_BORDER_WIDTH <- 2            # Standard border width
SELECTED_BORDER_WIDTH <- 3           # Border width for selected nodes
GHOST_BORDER_WIDTH <- 3              # Border width for ghost/preview nodes

# Font sizes
FONT_SIZE_SMALL <- 10                # Small font for labels
FONT_SIZE_MEDIUM <- 12               # Medium font for labels
FONT_SIZE_STANDARD <- 14             # Standard font for most text
FONT_SIZE_LARGE <- 16                # Large font for prominent nodes

# Node opacity
NODE_OPACITY_NORMAL <- 1.0           # Full opacity for normal nodes
NODE_OPACITY_GHOST <- 0.4            # Semi-transparent for ghost/preview nodes

# Edge visualization
DEFAULT_EDGE_ARROW_SIZE <- 0.5
DEFAULT_EDGE_WIDTH <- 1
DEFAULT_BASE_EDGE_WIDTH <- 10          # Base edge width for strength scaling
EDGE_WIDTH_THIN <- 0.15              # Thin edge width for subtle connections

# Label configuration
LABEL_WRAP_WIDTH <- 20               # Maximum characters per line in wrapped labels
VERTEX_LABEL_CEX_SMALL <- 0.7        # Small vertex label size

# NOTE: The following constants are defined for future use in edge visualization
# Currently not actively used in the app, but reserved for enhanced edge styling

# Confidence-based alpha values for edge transparency
# CONFIDENCE_ALPHA_LEVELS <- c(
#   0.2,   # Confidence 1 - very low
#   0.35,  # Confidence 2 - low
#   0.55,  # Confidence 3 - medium
#   0.75,  # Confidence 4 - high
#   1.0    # Confidence 5 - very high
# )

# Edge strength colors (for future color-coded edge visualization)
# STRONG_POSITIVE_COLOR <- "rgb(0, 100, 0)"      # Dark green
# MODERATE_POSITIVE_COLOR <- "rgb(34, 139, 34)"  # Medium green
# STRONG_NEGATIVE_COLOR <- "rgb(139, 0, 0)"      # Dark red
# MODERATE_NEGATIVE_COLOR <- "rgb(220, 20, 60)"  # Medium red

# Strength threshold for color differentiation
# EDGE_STRONG_THRESHOLD <- 3.0

# ============================================================================
# DAPSIWRM ELEMENT STYLING (Kumu-style colors and shapes)
# ============================================================================

# Color scheme for DAPSI(W)R(M) elements (following Kumu style guide)
ELEMENT_COLORS <- list(
  "Drivers" = "#776db3",                           # Purple (Kumu style)
  "Activities" = "#5abc67",                        # Green (Kumu style)
  "Pressures" = "#fec05a",                         # Orange (Kumu style)
  "Marine Processes & Functioning" = "#bce2ee",    # Light Blue (Kumu style)
  "Ecosystem Services" = "#313695",                # Dark Blue (Kumu style)
  "Goods & Benefits" = "#fff1a2",                  # Light Yellow (Kumu style)
  "Responses" = "#9C27B0",                         # Purple for management responses
  "Measures" = "#795548"                           # Brown for management measures/instruments
)

# Node shapes for each element type (following Kumu style guide)
# visNetwork available shapes: dot, diamond, square, triangle, triangleDown,
# star, hexagon, ellipse, database, text, circularImage, circle
# Note: hexagon is available! Octagon is not, using star as closest alternative
ELEMENT_SHAPES <- list(
  "Drivers" = "star",                            # Kumu: octagon → star (closest available)
  "Activities" = "hexagon",                      # Kumu: hexagon → hexagon (EXACT MATCH!)
  "Pressures" = "diamond",                       # Kumu: diamond (EXACT MATCH!)
  "Marine Processes & Functioning" = "dot",      # Kumu: pill → dot (circular, label outside)
  "Ecosystem Services" = "square",               # Kumu: square (EXACT MATCH!)
  "Goods & Benefits" = "triangle",               # Kumu: triangle (EXACT MATCH!)
  "Responses" = "triangleDown",                   # Inverted triangle for management responses
  "Measures" = "triangleDown"                     # Same as Responses (Measures are a subtype)
)

# Edge colors (following Kumu style guide)
EDGE_COLORS <- list(
  reinforcing = "#80b8d7",    # Light blue (positive from Kumu)
  opposing = "#dc131e"        # Red (negative from Kumu)
)

# Confidence defaults for network analysis
CONFIDENCE_DEFAULT <- 3

# Opacity mapping per confidence level (1-5 scale)
CONFIDENCE_OPACITY <- c(
  "1" = 0.3,
  "2" = 0.5,
  "3" = 0.7,
  "4" = 0.9,
  "5" = 1.0
)

# Default color/shape for unknown element types
DEFAULT_GROUP_COLOR <- "#95A5A6"
DEFAULT_GROUP_SHAPE <- "ellipse"

# ============================================================================
# DELAY (TEMPORAL LAG) CONSTANTS
# ============================================================================

# Delay categories for temporal lag between cause and effect
DELAY_CATEGORIES <- c("immediate", "short-term", "medium-term", "long-term")

DELAY_LABELS <- c(
  "immediate" = "Immediate",
  "short-term" = "Short-term",
  "medium-term" = "Medium-term",
  "long-term" = "Long-term"
)

DELAY_RANGES <- c(
  "immediate" = "< 1 month",
  "short-term" = "1-6 months",
  "medium-term" = "6 months - 3 years",
  "long-term" = "3+ years"
)

DELAY_DASH_PATTERNS <- list(
  "immediate" = FALSE,
  "short-term" = c(15, 10),
  "medium-term" = c(8, 8),
  "long-term" = c(3, 5)
)

#' Derive delay category from numeric years
#'
#' @param years Numeric value in years (NA returns NA)
#' @return Character delay category or NA_character_
derive_delay_category <- function(years) {
  if (is.na(years)) return(NA_character_)
  if (years <= 1/12) return("immediate")
  if (years < 0.5) return("short-term")
  if (years < 3) return("medium-term")
  return("long-term")
}

#' Convert delay category to visNetwork dash pattern
#'
#' @param delay_category Character delay category or NA
#' @return FALSE (solid) or numeric vector for dashes
delay_to_dashes <- function(delay_category) {
  if (is.null(delay_category) || is.na(delay_category)) return(FALSE)
  DELAY_DASH_PATTERNS[[delay_category]] %||% FALSE
}

# ============================================================================
# NETWORK OPTIMIZATION CONSTANTS
# ============================================================================

# Edge optimization thresholds
MAX_EDGES_BEFORE_OPTIMIZATION <- 30    # Optimize networks with more than this many edges
EDGE_RETENTION_QUANTILE <- 0.7         # Keep top 30% of edges when optimizing (1 - 0.7 = 0.3)

# ============================================================================
# EXPORT CONSTANTS
# ============================================================================

# Export filename date format
EXPORT_DATE_FORMAT <- "%Y%m%d"        # Date format for exported filenames (e.g. "20260208")

# PNG export dimensions
EXPORT_PNG_WIDTH <- 1200              # Default width for exported PNG images
EXPORT_PNG_HEIGHT <- 900              # Default height for exported PNG images

# Shadow effects
SHADOW_SIZE <- 5                      # Size of shadow effect for nodes

# ============================================================================
# VISUALIZATION CONSTANTS (APP-SPECIFIC)
# ============================================================================

# Plot parameters
VERTEX_LABEL_CEX <- 0.7                # Vertex label text size (used in static plots)
HISTOGRAM_BINS <- 15                   # Number of bins for histograms
HISTOGRAM_ALPHA <- 0.7                 # Transparency for histogram bars
MAX_BAR_LENGTH <- 30                   # Maximum bar length in text-based charts

# Risk level thresholds (for color coding)
RISK_LOW_THRESHOLD <- 30               # Below this = low risk (green)
RISK_HIGH_THRESHOLD <- 60              # Above this = high risk (red)

# ============================================================================
# UI LAYOUT CONSTANTS
# ============================================================================

# Box and panel heights (explicit CSS strings for clarity)
UI_BOX_HEIGHT_DEFAULT <- "400px"       # Standard box height for UI elements
UI_BOX_HEIGHT_LARGE <- "500px"         # Large box height for detailed views
UI_BOX_HEIGHT_SMALL <- "300px"         # Small box height for compact views

# Panel widths (explicit CSS strings for clarity)
UI_SIDEBAR_WIDTH <- "300px"            # Standard sidebar width
UI_CONTROLBAR_WIDTH <- "300px"         # Standard controlbar width

# Bootstrap grid column widths (numeric, out of 12 columns)
UI_BOX_WIDTH_FULL <- 12                # Full width (100%)
UI_BOX_WIDTH_HALF <- 6                 # Half width (50%)
UI_BOX_WIDTH_THIRD <- 4                # Third width (~33%)
UI_BOX_WIDTH_QUARTER <- 3              # Quarter width (25%)

# Plot dimensions (numeric for plotly/ggplot)
PLOT_HEIGHT_DEFAULT <- 500             # Default plot height
PLOT_WIDTH_DEFAULT <- 800              # Default plot width
PLOT_MARGINS <- c(0, 0, 2, 0)          # Plot margins: bottom, left, top, right

# UI plot height strings (for *Output() widgets and visNetwork)
PLOT_HEIGHT_XS  <- "200px"             # Compact distribution plots
PLOT_HEIGHT_SM  <- "300px"             # Small charts, histograms
PLOT_HEIGHT_MD  <- "400px"             # Standard charts and plots
PLOT_HEIGHT_LG  <- "500px"             # Large visualizations
PLOT_HEIGHT_XL  <- "600px"             # Full network views
PLOT_HEIGHT_XXL <- "700px"             # Main CLD visualization

# ============================================================================
# UI STYLING CONSTANTS
# ============================================================================

# Common module gradient colors (for card headers, icons, etc.)
UI_GRADIENT_PRIMARY <- list(
  start = "#667eea",
  end = "#764ba2"
)

# Import module colors
IMPORT_MODULE_COLORS <- list(
  gradient_start = "#667eea",
  gradient_end = "#764ba2",
  card_border = "#e0e0e0",
  card_hover = "#667eea",
  success_green = "#27ae60"
)

# Modal/Dialog animation delays (milliseconds - for shinyjs::delay)
MODAL_ANIMATION_DELAY_MS <- 100        # Delay before modal content shows (100ms)
MODAL_FADE_DURATION_MS <- 300          # Modal fade in/out duration (300ms)

# Spinner/Loading styles
SPINNER_BORDER_RADIUS <- "8px"
SPINNER_PADDING <- "15px"
SPINNER_MARGIN_TOP <- "10px"

# Reusable inline CSS style strings
CSS_TEXT_MUTED        <- "color: #666;"
CSS_TEXT_PRIMARY      <- "color: #007bff;"
CSS_TEXT_SUCCESS      <- "color: #28a745;"
CSS_LABEL_BOLD        <- "font-weight: bold; margin-bottom: 3px;"
CSS_LABEL_SEMIBOLD    <- "font-weight: 600; margin-bottom: 10px; display: block;"
CSS_META_ROW          <- "margin-bottom: 8px; font-size: 13px;"
CSS_HINT_TEXT         <- "font-size: 12px; color: #666;"

# ============================================================================
# EXCEL I/O CONSTANTS
# ============================================================================

# Default sheet names
DEFAULT_EDGE_SHEET <- "edges"
DEFAULT_NODE_SHEET <- "nodes"

# Column name candidates for flexible parsing
FROM_COL_NAMES <- c("from", "source", "from_node", "node1", "start")
TO_COL_NAMES <- c("to", "target", "to_node", "node2", "end")
EDGE_SHEET_CANDIDATES <- c("edges", "network", "connections", "links")

# File upload limits
MAX_UPLOAD_SIZE_MB <- 100               # Maximum file size in megabytes (Shiny default)
MAX_UPLOAD_SIZE_BYTES <- MAX_UPLOAD_SIZE_MB * 1024^2  # Computed in bytes
ALLOWED_EXCEL_TYPES <- c("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
                          "application/vnd.ms-excel")                                            # .xls

# ============================================================================
# EXCEL SEMI-QUANTITATIVE STRENGTH MAPPING
# ============================================================================

# Mapping for semi-quantitative strength values to numerical values
STRENGTH_MAPPING <- list(
  "weak" = 1.5,
  "medium" = 3.0,
  "strong" = 4.5,
  "very weak" = 1.0,
  "very strong" = 5.0
)

# ============================================================================
# SEED MANAGEMENT
# ============================================================================

# Default seeds for reproducibility
DEFAULT_RANDOM_SEED <- 123
MARINE_SES_SEED <- 42

# ============================================================================
# AUTO-SAVE CONSTANTS
# ============================================================================

# ADAPTIVE DEBOUNCING - Adjusts save delay based on editing patterns
# During rapid editing (e.g., building a model), use longer debounce for performance
# During casual editing (e.g., tweaking a few elements), use shorter debounce for safety

# Debounce delays (milliseconds)
AUTOSAVE_DEBOUNCE_RAPID_MS <- 5000    # 5 seconds during rapid/active editing
AUTOSAVE_DEBOUNCE_CASUAL_MS <- 2000   # 2 seconds during casual/slow editing

# Pattern detection thresholds
AUTOSAVE_RAPID_THRESHOLD <- 3         # 3+ changes within time window = "rapid editing"
AUTOSAVE_PATTERN_WINDOW_SEC <- 10     # Time window for detecting rapid editing (seconds)

# Auto-save recovery window (hours)
# Maximum age of recovery file to offer for restoration
AUTOSAVE_RECOVERY_WINDOW_HOURS <- 24  # 24 hours

# Auto-save indicator update interval (milliseconds)
# How often to refresh the "last saved X seconds ago" display
AUTOSAVE_INDICATOR_UPDATE_MS <- 10000  # 10 seconds

# ============================================================================
# UI FILTER DEBOUNCING
# ============================================================================
# Debounce delays for UI filter controls to reduce unnecessary re-renders

# Slider input debounce (e.g., year ranges, window sizes)
UI_SLIDER_DEBOUNCE_MS <- 300          # 300ms - fast enough for responsive feel

# Text/search input debounce
UI_TEXT_INPUT_DEBOUNCE_MS <- 400      # 400ms - wait for user to stop typing

# Select input debounce (dropdowns)
UI_SELECT_DEBOUNCE_MS <- 200          # 200ms - minimal delay for selections

# Network visualization update debounce
UI_NETWORK_UPDATE_DEBOUNCE_MS <- 500  # 500ms - expensive network redraws

# ============================================================================
# MARINESABRES PROJECT-SPECIFIC CONSTANTS
# ============================================================================

# Demonstration Areas
DA_SITES <- c(
  "Tuscan Archipelago",
  "Arctic Northeast Atlantic",
  "Macaronesia"
)

# Case studies per demonstration area: display name -> stored da_site value.
# Stored values keep the DA name so wp5_da_for_project() maps them to their DA.
DA_CASE_STUDIES <- list(
  "Tuscan Archipelago" = c("Tuscan Archipelago" = "Tuscan Archipelago"),
  "Arctic Northeast Atlantic" = c(
    "Iceland"       = "Arctic Northeast Atlantic: Iceland",
    "Greenland"     = "Arctic Northeast Atlantic: Greenland",
    "Faroe Islands" = "Arctic Northeast Atlantic: Faroe Islands"
  ),
  "Macaronesia" = c(
    "Azores"         = "Macaronesia: Azores",
    "Madeira"        = "Macaronesia: Madeira",
    "Canary Islands" = "Macaronesia: Canary Islands"
  )
)

# Grouped choices for the PIMS selector: each DA is an optgroup holding the DA
# itself (the value older projects saved) followed by its case studies.
DA_SITE_GROUPED_CHOICES <- lapply(stats::setNames(names(DA_CASE_STUDIES), names(DA_CASE_STUDIES)),
  function(da) as.list(c(stats::setNames(da, da), DA_CASE_STUDIES[[da]])[
    !duplicated(c(da, unname(DA_CASE_STUDIES[[da]])))]))

# Every accepted da_site value (bookmark restore whitelists against this)
DA_SITE_CHOICES <- unique(c(DA_SITES, unname(unlist(DA_CASE_STUDIES))))

# Regional Sea choices (EU MSFD standard naming + global additions)
REGIONAL_SEA_CHOICES <- c(
  "Baltic Sea",
  "North Sea",
  "Celtic Seas",
  "Bay of Biscay and Iberian Coast",
  "Western Mediterranean Sea",
  "Adriatic Sea",
  "Ionian Sea and Central Mediterranean Sea",
  "Aegean-Levantine Sea",
  "Black Sea",
  "Macaronesia",
  "Arctic Ocean",
  "Caribbean Sea"
)

# Ecosystem type choices — basic (for simple wizard-style inputs)
ECOSYSTEM_TYPE_CHOICES <- c(
  "Open coast", "Lagoon", "Estuary", "Offshore", "Deep sea"
)

# Ecosystem type choices — detailed (for template recommendation / multi-select)
ECOSYSTEM_TYPE_CHOICES_DETAILED <- c(
  "Coastal", "Shelf", "Deep Sea", "Pelagic", "Benthic",
  "Rocky Shore", "Sandy Shore", "Mudflat", "Saltmarsh",
  "Seagrass", "Kelp Forest", "Coral Reef", "Mangrove",
  "Estuary", "Lagoon", "Fjord", "Other"
)

# Stakeholder types (Newton & Elliott, 2016)
STAKEHOLDER_TYPES <- c(
  "Inputters",
  "Extractors",
  "Regulators",
  "Affectees",
  "Beneficiaries",
  "Influencers"
)

# ============================================================================
# MESSAGE CONSTANTS
# ============================================================================

MSG_LOOP_COMPLETE <- "Loop analysis complete. Found %d unique feedback loops"
MSG_LOOP_TIMEOUT <- "Loop analysis timeout reached, stopping early"
MSG_NETWORK_CREATED <- "Created %s network with %d nodes and %d edges"
MSG_GRAPH_CONVERTED <- "Graph converted to directed for loop analysis"
MSG_UNDIRECTED_CONVERTED <- "Converting undirected graph to directed for loop analysis"
MSG_LARGE_GRAPH_LIMIT <- "Large graph detected. Limiting search to loops of length %d or less, max %d loops"
MSG_MEDIUM_GRAPH_LIMIT <- "Medium graph detected. Limiting search to loops of length %d or less, max %d loops"

# ============================================================================
# BEGINNER MODE ELEMENT LIMITS
# ============================================================================
BEGINNER_MAX_ELEMENTS_DEFAULT <- 3L   # Default max elements per DAPSIWRM category in beginner mode
BEGINNER_MAX_ELEMENTS_MIN     <- 2L   # Minimum allowed
BEGINNER_MAX_ELEMENTS_MAX     <- 10L  # Maximum allowed (slider range)

# ============================================================================
# DTU DYNAMICS ANALYSIS CONSTANTS
# ============================================================================

DYNAMICS_MAX_BOOLEAN_NODES    <- 20L     # Hard limit for exhaustive Boolean analysis: 2^20 ~ 1M states.
                                         # Was 25 (2^25 ~ 33M states, GBs of RAM in the single shared
                                         # R process on laguna); lowered 2026-10-10 (review N16 follow-up).
DYNAMICS_DEFAULT_ITER         <- 500L    # Default simulation iterations
DYNAMICS_MIN_ITER             <- 50L     # Minimum iterations
DYNAMICS_MAX_ITER             <- 5000L   # Maximum iterations
DYNAMICS_DEFAULT_GREED        <- 100L    # Default Monte Carlo simulations
DYNAMICS_MAX_GREED            <- 2000L   # Maximum Monte Carlo simulations
DYNAMICS_DEFAULT_RF_TREES     <- 1000L   # Default random forest trees
DYNAMICS_DIVERGENCE_THRESHOLD <- 1e10    # Value above which simulation is considered diverged

# Weight mapping: polarity + strength -> numeric weight
DYNAMICS_WEIGHT_MAP <- list(
  "+strong"  =  1.00,
  "+medium"  =  0.50,
  "+weak"    =  0.25,
  "-strong"  = -1.00,
  "-medium"  = -0.50,
  "-weak"    = -0.25
)

# ============================================================================
# REACTIVE PIPELINE DEBOUNCING
# ============================================================================

# Delay before triggering CLD regeneration after ISA changes
# Prevents excessive regenerations during rapid consecutive edits
# Override via environment variable: MARINESABRES_ISA_DEBOUNCE_MS
ISA_DEBOUNCE_MS <- as.numeric(Sys.getenv("MARINESABRES_ISA_DEBOUNCE_MS", "500"))

# ============================================================================
# GRAPHICAL SES CREATOR CONSTANTS
# ============================================================================

# Ghost node rendering (semi-transparent preview nodes in graphical creator)
# NOTE: Ghost node opacity uses NODE_OPACITY_GHOST (defined in Visualization Constants above)
GHOST_EDGE_OPACITY <- 0.4         # 40% opacity for ghost edges
GHOST_NODE_BORDER_DASH <- c(5, 5) # Dashed border pattern

# AI suggestion limits
MAX_SUGGESTIONS_PER_EXPANSION <- 5  # Max number of ghost nodes per expansion
MIN_CLASSIFICATION_CONFIDENCE <- 0.2 # Minimum confidence to show classification

# Network validation
MIN_NETWORK_NODES_FOR_EXPORT <- 2  # Minimum nodes required for ISA export
MIN_NETWORK_EDGES_FOR_EXPORT <- 1  # Minimum edges required for ISA export

# ============================================================================
# CONNECTION & CONFIDENCE CONSTANTS
# ============================================================================

# Connection strength options
CONNECTION_STRENGTH <- c("strong", "medium", "weak")

# Connection polarity options
CONNECTION_POLARITY <- c("+", "-")

# Connection confidence levels (1-5 scale)
CONFIDENCE_LEVELS <- 1:5

# Connection confidence labels
CONFIDENCE_LABELS <- c(
  "1" = "Very Low",
  "2" = "Low",
  "3" = "Medium",
  "4" = "High",
  "5" = "Very High"
)

# ============================================================================
# DOMAIN-SPECIFIC CATEGORY CONSTANTS
# ============================================================================

# Ecosystem service categories
ECOSYSTEM_SERVICE_CATEGORIES <- c(
  "Provisioning",
  "Regulating",
  "Cultural",
  "Supporting"
)

# Pressure types
PRESSURE_TYPES <- c(
  "Exogenic (ExP)",
  "Endogenic Managed (EnMP)"
)

# Spatial scales
SPATIAL_SCALES <- c(
  "Local",
  "Regional",
  "National",
  "International"
)

# Activity scales
ACTIVITY_SCALES <- c(
  "Individual",
  "Group/Sector",
  "National",
  "International"
)

# ============================================================================
# UI LAYOUT CONSTANTS (P2 #23)
# ============================================================================

# Preloader/spinner styling
UI_SPINNER_SIZE <- "60px"
UI_SPINNER_BORDER_WIDTH <- "6px"
UI_SPINNER_BORDER_COLOR <- "rgba(52, 152, 219, 0.2)"
UI_SPINNER_ACTIVE_COLOR <- "#3498db"
UI_SPINNER_MARGIN <- "25px"

# Typography sizes for preloader
UI_ICON_SIZE_LARGE <- "48px"
UI_TITLE_FONT_SIZE <- "22px"
UI_SUBTITLE_FONT_SIZE <- "14px"
UI_SPACING_SMALL <- "8px"
UI_SPACING_MEDIUM <- "15px"

# Color palette for UI elements
UI_PRIMARY_COLOR <- "#3498db"
UI_TEXT_COLOR_DARK <- "#2c3e50"
UI_TEXT_COLOR_LIGHT <- "#7f8c8d"

# Touch target sizes (accessibility)
UI_TOUCH_TARGET_MIN <- "48px"
UI_BUTTON_MIN_HEIGHT <- "44px"

# Animation timings (in ms)
UI_ANIMATION_FAST <- 200
UI_ANIMATION_NORMAL <- 300
UI_ANIMATION_SLOW <- 500

# Network visualization defaults
UI_NETWORK_MIN_HEIGHT <- "400px"
UI_NETWORK_DEFAULT_HEIGHT <- "600px"
UI_CARD_BORDER_RADIUS <- "8px"

# ============================================================================
# WP5 DEMONSTRATION-AREA CONTEXT KEYS
# ============================================================================
# Canonical key set used by the WP5 mechanism KB and (in later phases) the
# indicator registry. Values are lowercase ASCII to match JSON `applies_to_DAs`
# fields without locale-dependent string handling.

WP5_DA_CONTEXTS <- c("macaronesia", "tuscan", "arctic")

# ============================================================================
# WP5 SHARED VOCABULARY (spec 2026-10-11 WS-1)
# ============================================================================
# Codes only. Labels resolve at render time via wp5_vocab_label() /
# i18n key modules.wp5_vocabulary.<vocab>.<code, dots -> underscores>.
# Sources: D5.2 final v5 §1.3-1.5 and Phase-3 rubric (audit A§2.2-2.3);
# EBM framework & implementation guidance (audit C§2, D§3.2-3.4);
# D5.4 NPG dimensions (audit D§1.2); D5.3 graph-change matrix (audit C§1.1).

WP5_CRITERIA <- data.frame(
  code = c("EE", "EC", "EQ", "PI", "FF"),
  stringsAsFactors = FALSE
)
# D5.2 uses PO/FI in the indicator fiches for PI/FF (audit A§2.2)
WP5_CRITERIA$aliases <- I(list(character(), character(), character(), "PO", "FI"))

WP5_CRITERION_SUBDIMENSIONS <- list(
  EQ = c("distributional", "procedural", "recognitional"),
  PI = c("credibility", "manageability", "contestation_risk")
)

WP5_RUBRIC <- list(
  direction          = c("increase", "decrease", "no_change", "uncertain"),
  magnitude          = c("incremental", "moderate", "substantial"),
  timing             = c("short", "medium", "long"),
  confidence         = c("high", "medium", "low"),
  evidence           = c("dataset", "literature", "stakeholder", "da_judgement", "triangulation"),
  uncertainty_driver = c("data_gap", "contested_assumption", "weak_causal_link", "implementation_dependency"),
  indicator_role     = c("primary", "supporting"),
  pathway_segment    = c("pressure", "state", "benefit", "governance_capacity")
)

WP5_TIME_HORIZON_YEARS <- list(short = c(1, 3), medium = c(4, 7), long = c(8, 15))

# EBM policy instruments (R). Source numbering skips 3.5 (audit C§2.1).
EBM_POLICY_INSTRUMENTS <- data.frame(
  code = c("1", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6",
           "2", "2.1", "2.2", "2.3", "2.4", "2.5",
           "3", "3.1", "3.2", "3.3", "3.4", "3.6", "3.7",
           "4", "4.1", "4.2", "4.3"),
  category = c(rep("legal_regulatory", 7), rep("voluntary_information", 6),
               rep("economic_incentive", 7), rep("research_development", 4)),
  level = c("category", rep("type", 6), "category", rep("type", 5),
            "category", rep("type", 6), "category", rep("type", 3)),
  stringsAsFactors = FALSE
)

# EBM management measures (M) with DAPSIWRM target (audit C§2.2)
EBM_MANAGEMENT_MEASURES <- data.frame(
  code = c("spatial.year_round", "spatial.seasonal", "input.capacity", "input.effort",
           "input.technical", "output", "remediation", "restoration.species",
           "restoration.habitat", "nbs.enhance", "nbs.multi_use", "nbs.replace"),
  category = c("spatial", "spatial", "input", "input", "input", "output", "remediation",
               "restoration", "restoration", "nbs", "nbs", "nbs"),
  dapsiwrm_target = c("A|P|C", "A|P|C", "A", "A", "A", "P", "P", "C", "C", "C", "A", "A"),
  stringsAsFactors = FALSE
)

# 11 tenets: 3 measure-level + 8 whole-intervention (audit C§3.3, D§3.4)
EBM_TENETS <- data.frame(
  code = c("ecol_effective", "tech_feasible", "econ_efficient",
           "econ_viable", "socially_desirable", "ethically_defensible", "culturally_inclusive",
           "legally_permissible", "admin_achievable", "communicable", "politically_expedient"),
  scope = c(rep("measure", 3), rep("intervention", 8)),
  stringsAsFactors = FALSE
)

NPG_DIMENSIONS <- c("knowledge", "collaboration", "values_conflict", "legitimacy_equity", "cross_sectoral")

# D5.3 graph-change operations: (+/-) reweight existing edge, (---) new edge, (o) new node
GRAPH_EDIT_OPS <- c("reweight_edge", "new_edge", "new_node")

# ============================================================================
# RESPONSE REGISTER CODES (spec 2026-10-11 WS-3a) — codes stored; labels via
# existing modules.response.measures.<key> translations (values = key suffix)
# ============================================================================
RM_TYPE_CODES <- c(regulatory = "regulatory", economic = "economic", educational = "educational",
                   technical = "technical", institutional = "institutional",
                   voluntary = "voluntary", mixed = "mixed")
RM_TARGET_CODES <- c(drivers = "drivers", activities = "activities", pressures = "pressures",
                     state = "state", multiple = "multiple_levels")
RM_STATUS_CODES <- c(proposed = "proposed", planned = "planned", implemented = "implemented",
                     partially_implemented = "partially_implemented", abandoned = "abandoned")
GOVERNANCE_LEVELS <- c("local", "island", "regional", "national", "eu", "regional_sea", "international")
TENET_LEVELS <- c("minimal", "intermediate", "full")   # intermediate: ecol_effective only (EBM framework)

RM_REGISTER_COLUMNS <- c(
  "ID", "Name", "Type", "Target", "Description", "Mechanism", "TargetElement",
  "Effectiveness", "Feasibility", "Cost", "Status", "Stakeholders", "Barriers", "DateAdded",
  "Kind", "EbmCode", "GovernanceLevel", "CompetentAuthority", "LegalBasis",
  "ImplementingStakeholders", "PairedWith", "PestleTag",
  paste0("Tenet_", c("ecol_effective", "tech_feasible", "econ_efficient",
                     "econ_viable", "socially_desirable", "ethically_defensible", "culturally_inclusive",
                     "legally_permissible", "admin_achievable", "communicable", "politically_expedient")),
  "TenetSource"
)

# Columns shown in the register table and Word reports (codes translated);
# tenet / stakeholder-ID / pairing columns stay in data and in the Excel export.
RM_DISPLAY_COLUMNS <- c("ID", "Name", "Type", "Target", "Kind", "EbmCode", "GovernanceLevel", "PestleTag",
                        "CompetentAuthority", "LegalBasis", "Effectiveness", "Feasibility", "Cost",
                        "Status", "DateAdded")

# ============================================================================
# WP5 INDICATOR REGISTRY (spec 2026-10-11 WS-4)
# ============================================================================
# Element frames carry these columns. Names lowercase to the legacy
# create_empty_element_df() schema (indicator / indicator_unit / data_source),
# so merge_collected_with_existing() (tolower alignment) and the JSON loader
# (lowercases element columns) keep a single column per field.
ISA_INDICATOR_COLUMNS <- c("Indicator", "Indicator_Unit", "Data_Source", "Registry_Id", "Registry_Version", "Policy_Target")
ISA_ELEMENT_KEYS <- c("drivers", "activities", "pressures", "marine_processes",
                      "ecosystem_services", "goods_benefits")
# The six Standard Entry element prefixes. Responses ("r") are deliberately
# absent: WS-4 leaves them untouched (plan ruling 9).
ISA_PREFIX_ELEMENT_KEY <- c(d = "drivers", a = "activities", p = "pressures", mpf = "marine_processes",
                            es = "ecosystem_services", gb = "goods_benefits")
WP5_INDICATOR_SCALE_TYPES <- c("numeric", "ordinal_profile", "count", "categorical")
WP5_INDICATOR_SOURCE_SETS <- c("fiche", "annex1", "posidonia", "arctic")
# A save that records a registry snapshot needs an app that keeps the
# Registry_Id/Registry_Version columns (WS-0 stamp_min_app_version()).
# 1.23.0 shipped WS-0..WS-3b without these columns, so the first release
# carrying WS-4 is 1.24.0.
WP5_INDICATOR_MIN_APP_VERSION <- "1.24.0"

# ============================================================================
# WP5 VALUATION CALCULATOR (spec 2026-10-11 WS-5)
# ============================================================================
# Benefit-transfer unit values and restoration costs come from the WS-2 KB
# (valuation_unit_values); these constants only fix order, defaults and limits.
WP5_VALUATION_HABITAT <- "posidonia_oceanica"
WP5_VALUATION_SERVICES <- c("coastal_protection", "carbon_sequestration", "recreation_tourism",
                            "food_provision", "water_purification")
# NPV sensitivity table (roadmap §6.5: never a single rate). A toolbox addition;
# D5.2 publishes no discount rate or NPV.
WP5_VALUATION_DISCOUNT_RATES <- c(0, 0.03, 0.05, 0.07)
WP5_DEFAULT_TIME_HORIZON <- 20L      # D5.2 §4.8: "a 20-year lifespan for restored meadows"
WP5_VALUATION_MAX_HORIZON <- 100L
WP5_VALUATION_MAX_RATE_PCT <- 20
# ============================================================================
# WP5 IMPACT ASSESSMENT (spec 2026-10-11 WS-6; data + model layer WS-6a)
# ============================================================================
# Stored at data$analysis$impact_assessment. Cell codes come from WP5_RUBRIC
# (WS-1). The lists below are not WS-1 vocabularies; WS-6b labels them.
# Adding a stored field requires raising BOTH IMPACT_SCHEMA_VERSION and
# WP5_IMPACT_MIN_APP_VERSION: an older app's whitelist normaliser silently strips
# unknown fields when it re-saves the project.
IMPACT_SCHEMA_VERSION <- 1L
IMPACT_MAX_SCENARIOS <- 5L       # roadmap §8.3; D5.2 DAs use 3 (Arctic) and 4 (Macaronesia)
# D5.2 Macaronesia scenario description dimensions (audit A§3.3); optional free text
IMPACT_SCENARIO_DIMENSIONS <- c("governance_form", "spatial_scope", "sectoral_activation",
                                "monitoring_data", "compliance_credibility", "financing_capacity")
IMPACT_SCENARIO_SOURCES <- c("user", "wp5_reference")
IMPACT_DISPLACEMENT_ANSWERS <- c("yes", "no", "unsure")   # displacement/leakage prompt (audit A§8.4)
# Free-text sections of the 7-step flow (roadmap §8.4): step 1 characterisation,
# step 5 uncertainty, step 6 trade-offs (auto_draft = WS-6c narrative), step 7.
IMPACT_TEXT_SECTIONS <- list(
  characterisation = c("focal_issue", "spatial_scope", "time_horizon", "stakeholders"),
  uncertainty      = c("notes"),
  trade_offs       = c("text", "auto_draft"),
  recommendations  = c("text")
)
# 1.24.0 shipped without this block, so the first release carrying it is 1.25.0.
WP5_IMPACT_MIN_APP_VERSION <- "1.25.0"

# ============================================================================
# WP5 INTERVENTION DESIGNER (spec 2026-10-14 WS-7a)
# ============================================================================
# D5.3 ordinal grid (C§5.2): strong/medium/weak negative, none, weak/medium/strong positive.
INTERVENTION_GRID_LEVELS <- c(-1, -0.5, -0.25, 0, 0.25, 0.5, 1)
INTERVENTION_GRID_CAP <- 65536          # exhaustive up to this (keeps D5.3's 50,176 Tuscany grid exhaustive); seeded sample above
INTERVENTION_CHUNK <- 2048L             # configurations stepped together
INTERVENTION_N_STEPS <- 1000L           # D5.3 FIN:1198
INTERVENTION_WINDOW <- 100L             # objective judged over the last 100 steps
INTERVENTION_DEFAULT_SEED <- 20261014L  # initial state + sampling seed (recorded in results)
INTERVENTION_TOP_K <- 20L
INTERVENTION_JOB_TIMEOUT_S <- 600
# Stability checks (criterion c) stop once the run has used this share of the
# job timeout; the rest of the rows keep c = NA (spec §4.2(c)).
INTERVENTION_STABILITY_BUDGET_FRACTION <- 0.7
# Evidence priors (C§3; toolbox_extension): max |level| by instrument evidence.
INTERVENTION_EVIDENCE_PRIORS <- c(behavioural = 0.25, regulatory = 0.5)
INTERVENTION_DEPENDENCE_MIN_SUCCESS <- 30L  # fewest successes for a "decisive link" verdict (WS-7b §3.3)
# A designer scenario with re-weighted links (links_modified) needs an app that
# applies them; 1.27.0 and older silently drop them, so Apply stamps 1.28.0.
WP5_DESIGNER_MIN_APP_VERSION <- "1.28.0"

# WP5 WS-8: PESTLE elements (D5.1), in this order everywhere
PESTLE_CODES <- c("political", "economic", "social", "technological", "legal", "environmental")

# ============================================================================
# WP5 GOVERNANCE PROFILES (spec 2026-10-17 WS-9a, D5.4)
# ============================================================================
WP5_GOV_DIMENSIONS <- NPG_DIMENSIONS   # WS-1 vocabulary; labels via wp5_vocab_label("npg", code, i18n)
WP5_GOV_POLARITIES <- c("enabler", "barrier")   # D5.4 "What is working well" / "Areas of improvement"
WP5_POLICY_TARGETS <- c("kmgbf_30x30", "eu_nrr", "msfd_ges_d1", "msfd_ges_d6", "national_mpa_pct")
# PIMS stakeholder register; NERoles = ';'-joined STAKEHOLDER_TYPES codes (D5.4 actor typology),
# SourceId = "d54:<actor id>" for actors loaded from a D5.4 profile
PIMS_STAKEHOLDER_COLUMNS <- c("ID", "Name", "Type", "Sector", "Contact", "Interests", "Role", "Power",
                              "Interest", "Attitude", "EngagementLevel", "DateAdded", "NERoles", "SourceId")
# Translation keys of the PIMS "Type" options (the form stores the translated label)
PIMS_STAKEHOLDER_TYPE_KEYS <- c(
  resource_users = "modules.pims.stakeholder.resource_users",
  industrybusiness = "modules.pims.stakeholder.industrybusiness",
  governmentregulators = "modules.pims.stakeholder.governmentregulators",
  ngocivil_society = "modules.pims.stakeholder.ngocivil_society",
  scientificacademic = "modules.pims.stakeholder.scientificacademic",
  local_communities = "modules.pims.stakeholder.local_communities",
  indigenous_groups = "modules.pims.stakeholder.indigenous_groups",
  other = "modules.isa.ai_assistant.other")
# Older apps rbind() a 12-column stakeholder row onto the 14-column register and drop Policy_Target:
# stamp whenever a project with at least one stakeholder is written or loaded by 1.30 (the register
# always has the 14-column schema), or any element has a non-empty Policy_Target (WS-0 stamp_min_app_version()).
WP5_GOVERNANCE_MIN_APP_VERSION <- "1.30.0"

# ============================================================================
# WP5 GOVERNANCE-READINESS CHECK (spec 2026-10-17 WS-9b, D5.4 questionnaire)
# ============================================================================
READINESS_ID_PREFIX <- "R"            # anonymous respondent ids R001..
READINESS_META_COLUMNS <- c("RespondentId", "EnteredAt", "Source", "Role")
# data$pims$readiness is new in 1.31.0; stamped whenever a project has a respondent
WP5_READINESS_MIN_APP_VERSION <- "1.31.0"

# ============================================================================
# WP5 WORKSHOP ELICITATION (spec 2026-10-18 WS-10, D5.2 ranking poll + Annex 4 tenets)
# ============================================================================
WORKSHOP_ID_PREFIX <- "W"                 # workshops W001..
WORKSHOP_PARTICIPANT_PREFIX <- "P"        # anonymous participants P001.. (per workshop)
WORKSHOP_META_COLUMNS <- c("RespondentId", "EnteredAt", "Source")
WORKSHOP_POLL_CRITERIA <- c("importance", "feasibility", "long_term_impact")
WORKSHOP_POLL_SCALES <- list(pm5 = as.character(-5:5), four = as.character(1:4))   # ASCII hyphen-minus
WORKSHOP_TENET_CODES <- c("completely_disagree", "disagree", "neutral", "agree", "completely_agree")  # points 1..5
WORKSHOP_TENET_ANSWERS <- c(WORKSHOP_TENET_CODES, "dont_know")
WORKSHOP_MIN_VALID <- 3L                  # fewer valid tenet ratings -> no write-back proposal
# data$data$pims$workshops and the register's TenetSource are new in 1.32.0; stamped when a
# project has a workshop or a TenetSource value
WP5_WORKSHOP_MIN_APP_VERSION <- "1.32.0"

# ============================================================================
# END OF CONSTANTS
# ============================================================================

message("Marine SES constants loaded successfully")