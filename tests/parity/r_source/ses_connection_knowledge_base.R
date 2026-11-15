# data/ses_connection_knowledge_base.R
# Marine SES Connection Knowledge Base
# Purpose: Curated database of common DAPSI(W)R(M) connections from published
#          marine SES case studies. Used to improve AI-assisted connection
#          generation by providing domain-validated connection patterns.
#
# Sources:
#   - Elliott et al. (2017) - DPSIR/DAPSI(W)R(M) framework
#   - Borja et al. (2016) - Marine environmental indicators
#   - Liquete et al. (2013) - Marine ecosystem services
#   - Halpern et al. (2015) - Cumulative human impacts
#   - Costanza et al. (2014) - Ocean economy
#   - HELCOM (2018) - Baltic Sea assessment
#   - UNEP-MAP (2017) - Mediterranean assessment
#
# Author: AI-assisted curation
# Date: 2026-03-14
# Dependencies: None (base R only)

# ==============================================================================
# CONNECTION KNOWLEDGE BASE
# ==============================================================================

#' Marine SES Connection Knowledge Base
#'
#' A curated list of common DAPSI(W)R(M) connections observed in marine
#' social-ecological systems. Each entry contains pattern matching fields,
#' connection properties, and source attribution.
#'
#' @format A list of lists, each containing:
#' \describe{
#'   \item{from_type}{Source element DAPSI(W)R(M) type}
#'   \item{to_type}{Target element DAPSI(W)R(M) type}
#'   \item{from_pattern}{Regex pattern(s) to match source element names}
#'   \item{to_pattern}{Regex pattern(s) to match target element names}
#'   \item{probability}{Base connection probability (0-1)}
#'   \item{polarity}{Connection polarity ("+" or "-")}
#'   \item{strength}{Connection strength ("weak", "medium", "strong")}
#'   \item{source}{Literature source}
#' }
#'
#' @examples
#' \dontrun{
#' # Look up a known connection
#' match <- lookup_knowledge_base("food security", "drivers", "fishing", "activities")
#' }
SES_CONNECTION_DB <- list(

  # ============================================================================
  # FISHING PATHWAY: food security -> fishing -> overfishing -> stock decline
  #                  -> reduced catch -> livelihood loss
  # ============================================================================

  # D -> A: Drivers to Activities (Fishing)
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "food.?secur|protein.?demand|nutrition",
       to_pattern = "fish|trawl|harvest|catch",
       probability = 0.95, polarity = "+", strength = "strong",
       source = "Elliott et al. 2017"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "econom|livelihood|income|employ",
       to_pattern = "commerc.*fish|industr.*fish|fish.*industr",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "subsist|tradition|cultur",
       to_pattern = "artisan.*fish|small.?scale.*fish|subsist.*fish",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Elliott et al. 2017"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "export|trade|market.?demand",
       to_pattern = "fish|aquacultur|shellfish|shrimp",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # A -> P: Activities to Pressures (Fishing)
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "trawl|bottom.*fish|drag",
       to_pattern = "seabed|benthic|habitat.*destruct|physical.*disturb",
       probability = 0.95, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "commerc.*fish|industr.*fish|overfish",
       to_pattern = "overfish|stock.*deplet|extract|biomass.*remov",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "fish|trawl|net|longline",
       to_pattern = "bycatch|discard|non.?target",
       probability = 0.85, polarity = "+", strength = "medium",
       source = "Borja et al. 2016"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "fish|trawl|seine|gillnet",
       to_pattern = "ghost.*net|abandon.*gear|marine.*litter",
       probability = 0.45, polarity = "+", strength = "weak",
       source = "UNEP-MAP 2017"),

  # P -> S: Pressures to States (Fishing)
  list(from_type = "pressures", to_type = "states",
       from_pattern = "overfish|stock.*deplet|extract",
       to_pattern = "fish.*stock.*declin|population.*declin|biomass.*reduc|abundance.*declin",
       probability = 0.95, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "overfish|extract|harvest",
       to_pattern = "trophic.*cascad|food.?web.*chang|ecosystem.*structur",
       probability = 0.82, polarity = "-", strength = "medium",
       source = "Borja et al. 2016"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "bycatch|discard|non.?target",
       to_pattern = "species.*declin|biodiver|threatened|endanger",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "seabed.*disturb|benthic.*destruct|trawl.*damage",
       to_pattern = "habitat.*degrad|benthic.*communit|seabed.*integr",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  # S -> I: States to Impacts (Fishing)
  list(from_type = "states", to_type = "impacts",
       from_pattern = "fish.*stock.*declin|population.*declin|biomass.*reduc",
       to_pattern = "fish.*provision|catch.*reduc|harvest.*reduc|food.*provision",
       probability = 0.93, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "biodiver.*loss|species.*declin",
       to_pattern = "ecosystem.*service|regulat.*service|ecosystem.*function",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  # I -> W: Impacts to Welfare (Fishing)
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "fish.*provision.*reduc|catch.*reduc|harvest.*declin",
       to_pattern = "livelihood|income|employ|econom.*loss",
       probability = 0.92, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "food.*provision.*reduc|food.*supply",
       to_pattern = "food.*secur|nutrition|protein.*supply|hunger",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Elliott et al. 2017"),

  # ============================================================================
  # EUTROPHICATION PATHWAY: population growth -> wastewater -> nutrient loading
  #                         -> algal blooms -> hypoxia -> fish kills
  # ============================================================================

  # D -> A: Drivers to Activities (Eutrophication)
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "populat.*growth|urban|residential",
       to_pattern = "wastewater|sewage|domestic.*discharg",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "food.*product|agricultur.*demand|crop",
       to_pattern = "agricultur|farm|fertili|crop|livestock",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "food.*demand|aquacultur.*demand",
       to_pattern = "aquacultur|fish.*farm|maricult",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  # A -> P: Activities to Pressures (Eutrophication)
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "wastewater|sewage|domestic.*discharg",
       to_pattern = "nutrient.*load|nutrient.*enrich.*sewage|nitrogen|phosphor|organic.*enrich",
       probability = 0.95, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "agricultur|farm|fertili|livestock",
       to_pattern = "nutrient.*runoff|nutrient.*enrich.*agricult|nitrogen|phosphor|diffuse.*pollut",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "aquacultur|fish.*farm|maricult",
       to_pattern = "nutrient.*enrich.*aquacult|nutrient.*enrich|organic.*load|waste.*discharg",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  # P -> S: Pressures to States (Eutrophication)
  list(from_type = "pressures", to_type = "states",
       from_pattern = "nutrient.*load|nutrient.*enrich|nitrogen.*load|phosphor.*load",
       to_pattern = "algal.*bloom|phytoplankton|chlorophyll|eutrophic",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "nutrient.*enrich|nutrient|eutrophic|organic.*enrich",
       to_pattern = "hypox|oxygen.*deplet|anox|dead.*zone",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "nutrient|eutrophic",
       to_pattern = "water.*quality|turbidit|secchi|transparency",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Borja et al. 2016"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "nutrient|eutrophic|algal",
       to_pattern = "seagrass|submerge.*veget|macrophyte",
       probability = 0.85, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # S -> I: States to Impacts (Eutrophication)
  list(from_type = "states", to_type = "impacts",
       from_pattern = "algal.*bloom|eutrophic",
       to_pattern = "recreat.*value|tourism.*impact|aesthet|beach.*closur",
       probability = 0.85, polarity = "-", strength = "medium",
       source = "UNEP-MAP 2017"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "hypox|oxygen.*deplet|dead.*zone",
       to_pattern = "fish.*kill|mortality|fish.*loss|benthic.*loss",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "water.*quality.*declin|turbidit",
       to_pattern = "drinking.*water|water.*supply|water.*treatm",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Borja et al. 2016"),

  # I -> W: Impacts to Welfare (Eutrophication)
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "recreat.*loss|beach.*closur|aesthet.*loss",
       to_pattern = "tourism.*revenue|recreat.*opportunit|quality.*life",
       probability = 0.85, polarity = "-", strength = "medium",
       source = "Costanza et al. 2014"),

  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "fish.*kill|fish.*mortality",
       to_pattern = "livelihood|income|food.*secur|econom",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  # ============================================================================
  # TOURISM PATHWAY: recreation demand -> coastal tourism -> physical
  #                  disturbance -> habitat damage -> aesthetic loss
  # ============================================================================

  # D -> A: Drivers to Activities (Tourism)
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "recreat|leisure|tourism.*demand|holiday",
       to_pattern = "tourism|recreat|beach|diving|snorkel|cruise",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "UNEP-MAP 2017"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "econom.*develop|employ|income.*generat",
       to_pattern = "hotel|resort|coastal.*develop|marina",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # A -> P: Activities to Pressures (Tourism)
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "tourism|beach.*recreat|coast.*tourism",
       to_pattern = "physical.*disturb|tramp|compact|erosion",
       probability = 0.85, polarity = "+", strength = "medium",
       source = "UNEP-MAP 2017"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "diving|snorkel|anchor",
       to_pattern = "coral.*damage|reef.*damage|physical.*damage|anchor.*damage",
       probability = 0.80, polarity = "+", strength = "medium",
       source = "UNEP-MAP 2017"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "cruise|yacht|boat|marina",
       to_pattern = "waste.*discharg|pollut|litter|anti.?foul",
       probability = 0.78, polarity = "+", strength = "medium",
       source = "UNEP-MAP 2017"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "coastal.*develop|hotel|resort|construct",
       to_pattern = "habitat.*loss|coast.*erosion|land.*use.*chang|sediment",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # P -> S: Pressures to States (Tourism)
  list(from_type = "pressures", to_type = "states",
       from_pattern = "physical.*disturb|tramp|erosion",
       to_pattern = "dune|beach|interti|shore.*habitat",
       probability = 0.82, polarity = "-", strength = "medium",
       source = "UNEP-MAP 2017"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "coral.*damage|reef.*damage|anchor.*damage",
       to_pattern = "coral.*cover|reef.*health|coral.*integr",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  # S -> I: States to Impacts (Tourism)
  list(from_type = "states", to_type = "impacts",
       from_pattern = "habitat.*degrad|beach.*erosion|coast.*degrad",
       to_pattern = "aesthet|scenic|recreat.*value|tourism.*attract",
       probability = 0.85, polarity = "-", strength = "medium",
       source = "Liquete et al. 2013"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "coral.*declin|reef.*degrad|biodiver.*loss",
       to_pattern = "diving.*value|tourism.*attract|recreat.*value",
       probability = 0.87, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  # I -> W: Impacts to Welfare (Tourism)
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "tourism.*attract.*loss|recreat.*value.*loss|aesthet.*loss",
       to_pattern = "tourism.*revenue|employ|local.*econom|communit",
       probability = 0.87, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  # ============================================================================
  # CLIMATE PATHWAY: energy demand -> fossil fuels -> CO2 -> warming
  #                  -> coral bleaching -> biodiversity loss
  # ============================================================================

  # D -> A: Drivers to Activities (Climate)
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "energy.*demand|power|electri|transport",
       to_pattern = "fossil.*fuel|oil|gas|coal|combustion",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "energy.*demand|renew",
       to_pattern = "wind.*farm|offshore.*wind|renew.*energy|tidal",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # A -> P: Activities to Pressures (Climate)
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "fossil.*fuel|oil|gas|coal|combust|emission",
       to_pattern = "co2|carbon.*emission|greenhouse|ghg|climat.*chang",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "fossil.*fuel|combust|emission",
       to_pattern = "ocean.*warm|sea.*temp|thermal",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "fossil.*fuel|co2|emission",
       to_pattern = "ocean.*acidif|ph.*declin|carbonate",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # P -> S: Pressures to States (Climate)
  list(from_type = "pressures", to_type = "states",
       from_pattern = "ocean.*warm|sea.*temp|thermal",
       to_pattern = "coral.*bleach|coral.*mortal|reef.*degrad",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "ocean.*warm|climate.*chang|temp.*increas",
       to_pattern = "species.*rang.*shift|distribut.*chang|migrat.*pattern",
       probability = 0.82, polarity = "+", strength = "medium",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "sea.*level.*rise|climat.*chang",
       to_pattern = "coast.*erosion|inundat|flood|submers",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "ocean.*acidif|ph.*declin",
       to_pattern = "calcif|shell|coral.*growth|pteropod|mollus",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "ocean.*warm|climate|temp",
       to_pattern = "sea.*ice|ice.*cover|arctic.*ice|permafrost",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  # S -> I: States to Impacts (Climate)
  list(from_type = "states", to_type = "impacts",
       from_pattern = "coral.*bleach|reef.*degrad|coral.*loss",
       to_pattern = "biodiver.*loss|ecosystem.*service|habitat.*loss|fish.*habitat",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "coast.*erosion|sea.*level|inundat",
       to_pattern = "coastal.*protect|flood.*risk|property.*damage|infrastruc",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "species.*shift|distribut.*chang",
       to_pattern = "fish.*availab|catch.*composit|ecosystem.*function",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # I -> W: Impacts to Welfare (Climate)
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "coastal.*protect.*loss|flood.*risk",
       to_pattern = "displace|property|home|communit.*resili",
       probability = 0.87, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "biodiver.*loss|ecosystem.*service.*loss",
       to_pattern = "well.?being|quality.*life|health|livehood",
       probability = 0.83, polarity = "-", strength = "medium",
       source = "Liquete et al. 2013"),

  # ============================================================================
  # AQUACULTURE PATHWAY: food demand -> aquaculture -> nutrient enrichment
  #                      -> water quality decline
  # ============================================================================

  # D -> A
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "food.*demand|seafood|protein|aquacult.*demand",
       to_pattern = "aquacultur|fish.*farm|maricult|shellfish.*farm",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  # A -> P
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "aquacultur|fish.*farm|maricult",
       to_pattern = "nutrient.*enrich|organic.*load|eutrophic",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "aquacultur|fish.*farm",
       to_pattern = "antibiot|chemic|medicin|pestici",
       probability = 0.50, polarity = "+", strength = "weak",
       source = "Borja et al. 2016"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "aquacultur|fish.*farm",
       to_pattern = "escap|genetic.*introgress|invasive|non.?native",
       probability = 0.45, polarity = "+", strength = "weak",
       source = "Borja et al. 2016"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "aquacultur|fish.*farm|maricult",
       to_pattern = "disease|parasit|pathogen|sea.*lice",
       probability = 0.78, polarity = "+", strength = "medium",
       source = "Borja et al. 2016"),

  # P -> S
  list(from_type = "pressures", to_type = "states",
       from_pattern = "nutrient.*enrich|organic.*load|aquacult.*waste",
       to_pattern = "water.*quality|dissolv.*oxygen|benthic.*condition",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Borja et al. 2016"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "escap|genetic.*introgress",
       to_pattern = "wild.*stock|genetic.*divers|native.*populat",
       probability = 0.50, polarity = "-", strength = "weak",
       source = "Borja et al. 2016"),

  # ============================================================================
  # SHIPPING PATHWAY: trade demand -> shipping -> pollution/noise
  #                   -> marine mammals affected
  # ============================================================================

  # D -> A
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "trade|commerc|import|export|transport",
       to_pattern = "ship|maritim.*transport|cargo|freight|port",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # A -> P
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ship|vessel|cargo|tanker|maritim",
       to_pattern = "underwat.*noise|noise.*pollut|acoustic",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ship|vessel|tanker|port",
       to_pattern = "oil.*spill|bilge|ballast.*water|anti.?foul",
       probability = 0.82, polarity = "+", strength = "medium",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ship|vessel|cargo",
       to_pattern = "invasive.*species|non.?native|ballast.*introduc|invasion|ballast.*mediat",
       probability = 0.78, polarity = "+", strength = "medium",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ship|vessel|tanker|bunker",
       to_pattern = "air.*emission|sox|nox|particulate|co2",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ship|vessel|cargo|port",
       to_pattern = "ship.*strike|collision|marine.*mammal.*disturb",
       probability = 0.50, polarity = "+", strength = "weak",
       source = "Halpern et al. 2015"),

  # P -> S
  list(from_type = "pressures", to_type = "states",
       from_pattern = "underwat.*noise|acoustic|noise.*pollut",
       to_pattern = "marine.*mammal|cetacean|whale|dolphin|seal",
       probability = 0.87, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "oil.*spill|hydrocarbon|contamin",
       to_pattern = "water.*quality|sediment.*quality|benthic|seabird",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "invasive.*species|non.?native|alien.*species|invasion|ballast.*mediat",
       to_pattern = "native.*species|biodiver|communit.*composit|ecosystem.*structur",
       probability = 0.83, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # ============================================================================
  # COASTAL DEVELOPMENT PATHWAY: housing demand -> construction -> habitat loss
  #                               -> ecosystem service decline
  # ============================================================================

  # D -> A
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "housing|urban|populat|migrat|settlement",
       to_pattern = "construct|develop|build|infrastruc|reclamat",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "econom.*develop|industr|port.*demand",
       to_pattern = "port.*develop|harbor|industrial.*develop|dredg",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # A -> P
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "construct|develop|build|reclamat",
       to_pattern = "habitat.*loss|habitat.*destruct|land.*use.*chang|coast.*squeez",
       probability = 0.93, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "dredg|port.*develop|harbor",
       to_pattern = "sediment.*disturb|turbid|suspen.*sediment|seabed.*disturb",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "construct|develop|urban",
       to_pattern = "runoff|storm.?water|imperv|diffuse.*pollut",
       probability = 0.82, polarity = "+", strength = "medium",
       source = "Borja et al. 2016"),

  # P -> S
  list(from_type = "pressures", to_type = "states",
       from_pattern = "habitat.*loss|habitat.*destruct|coast.*squeez",
       to_pattern = "wetland|saltmarsh|mangrove|seagrass|interti",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "habitat.*loss|land.*use.*chang",
       to_pattern = "biodiver|species.*rich|habitat.*area|ecosystem.*extent",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  # S -> I
  list(from_type = "states", to_type = "impacts",
       from_pattern = "wetland.*loss|saltmarsh.*loss|mangrove.*loss",
       to_pattern = "coast.*protect|flood.*buffer|wave.*attenu|storm.*protect",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "habitat.*loss|ecosystem.*loss|biodiver.*loss",
       to_pattern = "ecosystem.*service|provision.*service|regulat.*service|cultural.*service",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  list(from_type = "states", to_type = "impacts",
       from_pattern = "mangrove.*loss|seagrass.*loss|wetland.*loss",
       to_pattern = "carbon.*stor|carbon.*sequest|blue.*carbon",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  # I -> W
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "coast.*protect.*loss|flood.*risk.*increas",
       to_pattern = "property.*damage|displace|insur.*cost|vulnerab",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "ecosystem.*service.*declin|ecosystem.*service.*loss",
       to_pattern = "quality.*life|well.?being|communit.*resili|health",
       probability = 0.83, polarity = "-", strength = "medium",
       source = "Liquete et al. 2013"),

  # ============================================================================
  # POLLUTION PATHWAY: industrial output -> contaminants -> water quality
  #                    -> health impacts
  # ============================================================================

  # D -> A
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "industr|manufactur|chemical|product",
       to_pattern = "industr.*discharg|chemic.*product|manufactur|refin",
       probability = 0.88, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  list(from_type = "drivers", to_type = "activities",
       from_pattern = "consum|plastic|packag|waste",
       to_pattern = "plastic.*product|waste.*dispos|landfill|inciner",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "UNEP-MAP 2017"),

  # A -> P
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "industr.*discharg|chemic|refin|manufactur",
       to_pattern = "heavy.*metal|contamin|toxic|persistent.*organ|pah",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "activities", to_type = "pressures",
       from_pattern = "plastic|waste.*dispos|litter",
       to_pattern = "marine.*litter|microplastic|plastic.*pollut|debris",
       probability = 0.92, polarity = "+", strength = "strong",
       source = "UNEP-MAP 2017"),

  # P -> S
  list(from_type = "pressures", to_type = "states",
       from_pattern = "heavy.*metal|contamin|toxic|pah",
       to_pattern = "sediment.*quality|water.*quality|bioaccumul|biota.*contam",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "pressures", to_type = "states",
       from_pattern = "marine.*litter|microplastic|plastic",
       to_pattern = "ingest|entangl|habitat.*quality|seafloor.*condition",
       probability = 0.82, polarity = "-", strength = "medium",
       source = "UNEP-MAP 2017"),

  # S -> I
  list(from_type = "states", to_type = "impacts",
       from_pattern = "contamin|toxic|bioaccumul",
       to_pattern = "seafood.*safety|health.*risk|food.*safety|shellfish.*closur",
       probability = 0.87, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  # I -> W
  list(from_type = "impacts", to_type = "welfare",
       from_pattern = "health.*risk|seafood.*safety|contamin.*risk",
       to_pattern = "public.*health|cancer|disease|health.*cost",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Borja et al. 2016"),

  # ============================================================================
  # RESPONSE CONNECTIONS: R -> P, R -> A, R -> D (management interventions)
  # ============================================================================

  # R -> P: Responses reducing Pressures
  list(from_type = "responses", to_type = "pressures",
       from_pattern = "mpa|marine.*protect|no.?take|sanctuary",
       to_pattern = "overfish|extract|harvest|fish.*press",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Elliott et al. 2017"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "quota|catch.*limit|tac|total.*allow",
       to_pattern = "overfish|stock.*deplet|extract|biomass.*remov",
       probability = 0.92, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "wastewater.*treat|sewage.*treat|nutrient.*remov",
       to_pattern = "nutrient.*load|nitrogen|phosphor|eutrophic",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "emission.*control|carbon.*tax|renewable",
       to_pattern = "co2|greenhouse|emission|climate",
       probability = 0.82, polarity = "-", strength = "medium",
       source = "Halpern et al. 2015"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "plastic.*ban|litter.*regulat|waste.*manag",
       to_pattern = "marine.*litter|plastic.*pollut|microplastic|debris",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "UNEP-MAP 2017"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "noise.*regulat|speed.*limit|shipping.*lane",
       to_pattern = "underwat.*noise|acoustic|noise.*pollut",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Halpern et al. 2015"),

  list(from_type = "responses", to_type = "pressures",
       from_pattern = "restor|rehabilit|re.?establish|replant",
       to_pattern = "habitat.*loss|habitat.*degrad|ecosystem.*degrad",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Liquete et al. 2013"),

  # R -> A: Responses modifying Activities
  list(from_type = "responses", to_type = "activities",
       from_pattern = "fishing.*ban|moratorium|closed.*season|no.?fish",
       to_pattern = "fish|trawl|harvest",
       probability = 0.92, polarity = "-", strength = "strong",
       source = "Elliott et al. 2017"),

  list(from_type = "responses", to_type = "activities",
       from_pattern = "gear.*restrict|mesh.*size|gear.*ban",
       to_pattern = "trawl|bottom.*fish|dredg",
       probability = 0.88, polarity = "-", strength = "strong",
       source = "HELCOM 2018"),

  list(from_type = "responses", to_type = "activities",
       from_pattern = "eia|impact.*assess|planning.*permit",
       to_pattern = "construct|develop|dredg|reclam",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Elliott et al. 2017"),

  list(from_type = "responses", to_type = "activities",
       from_pattern = "spatial.*plan|marine.*plan|zon",
       to_pattern = "ship|fish|aquacult|wind.*farm|develop",
       probability = 0.78, polarity = "-", strength = "medium",
       source = "Elliott et al. 2017"),

  # R -> D: Responses modifying Drivers
  list(from_type = "responses", to_type = "drivers",
       from_pattern = "education|awareness|campaign|outreach",
       to_pattern = "demand|consum|behavio|preference",
       probability = 0.45, polarity = "-", strength = "weak",
       source = "Elliott et al. 2017"),

  list(from_type = "responses", to_type = "drivers",
       from_pattern = "subsid|incentiv|fund|financ.*support",
       to_pattern = "econom|livelihood|alternat|transit",
       probability = 0.80, polarity = "+", strength = "medium",
       source = "Costanza et al. 2014"),

  # ============================================================================
  # FEEDBACK LOOPS: W -> D, W -> R
  # ============================================================================

  # W -> R: Welfare motivating Responses
  list(from_type = "welfare", to_type = "responses",
       from_pattern = "livelihood.*loss|income.*loss|econom.*declin",
       to_pattern = "subsid|compensat|support|aid|relief",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Elliott et al. 2017"),

  list(from_type = "welfare", to_type = "responses",
       from_pattern = "health.*impact|disease|contamin.*risk",
       to_pattern = "health.*regulat|safety.*standard|monitor|warning",
       probability = 0.83, polarity = "+", strength = "medium",
       source = "Borja et al. 2016"),

  list(from_type = "welfare", to_type = "responses",
       from_pattern = "quality.*life.*declin|well.?being.*declin|communit.*concern",
       to_pattern = "policy|legislat|governance|manag.*plan|action.*plan",
       probability = 0.80, polarity = "+", strength = "medium",
       source = "Elliott et al. 2017"),

  # W -> D: Welfare feeding back to Drivers
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "food.*insecur|hunger|malnutrit",
       to_pattern = "food.*demand|subsist|protein.*need",
       probability = 0.87, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "econom.*loss|unemploy|poverty",
       to_pattern = "econom.*need|livelihood|income.*need|alternat.*livelihood",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "recreat.*loss|quality.*life.*declin",
       to_pattern = "recreat.*demand|tourism.*demand|leisure",
       probability = 0.50, polarity = "+", strength = "weak",
       source = "Elliott et al. 2017"),

  # ============================================================================
  # FEEDBACK LOOP PATTERNS: W -> D (welfare feeding back to drivers)
  # ============================================================================

  # W -> D: Fishing community livelihood loss reducing food security demand
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "fish.*communit.*livelihood.*loss|fish.*livelihood.*declin|artisan.*livelihood",
       to_pattern = "food.*secur.*demand|food.*demand|protein.*demand",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Elliott et al. 2017"),

  # W -> D: Tourism revenue decline reducing coastal development demand
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "tourism.*revenue.*declin|tourism.*income.*loss|visitor.*declin",
       to_pattern = "coastal.*develop.*demand|resort.*demand|hotel.*demand|develop.*pressure",
       probability = 0.80, polarity = "+", strength = "medium",
       source = "Costanza et al. 2014"),

  # W -> D: Coastal property damage increasing flood protection demand
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "coastal.*property.*damage|property.*loss|storm.*damage|flood.*damage",
       to_pattern = "flood.*protect.*demand|coastal.*defence|protect.*demand|resili.*demand",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # W -> D: Food security improvement increasing fishing demand
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "food.*secur.*improv|nutrition.*improv|food.*access.*improv",
       to_pattern = "fish.*demand|seafood.*demand|harvest.*demand",
       probability = 0.75, polarity = "+", strength = "medium",
       source = "Costanza et al. 2014"),

  # W -> D: Cultural identity preservation maintaining traditional fishing demand
  list(from_type = "welfare", to_type = "drivers",
       from_pattern = "cultur.*identity.*preserv|heritage.*preserv|cultur.*continu",
       to_pattern = "tradition.*fish.*demand|artisan.*demand|subsist.*demand|cultur.*practic",
       probability = 0.70, polarity = "+", strength = "weak",
       source = "Elliott et al. 2017"),

  # ============================================================================
  # FEEDBACK LOOP PATTERNS: W -> R (welfare motivating responses)
  # ============================================================================

  # W -> R: Community health impacts driving pollution regulation
  list(from_type = "welfare", to_type = "responses",
       from_pattern = "communit.*health.*impact|public.*health.*concern|health.*effect|contamin.*health",
       to_pattern = "pollut.*regulat|pollut.*control|emission.*standard|discharg.*regulat",
       probability = 0.80, polarity = "+", strength = "strong",
       source = "Borja et al. 2016"),

  # W -> R: Livelihood loss driving fisheries management reform
  list(from_type = "welfare", to_type = "responses",
       from_pattern = "livelihood.*loss|fisher.*income.*loss|fish.*communit.*declin",
       to_pattern = "fisher.*manag.*reform|fish.*policy|fish.*regulat|stock.*recover.*plan",
       probability = 0.75, polarity = "+", strength = "medium",
       source = "Elliott et al. 2017"),

  # W -> R: Property damage from storms driving coastal defence policy
  list(from_type = "welfare", to_type = "responses",
       from_pattern = "property.*damage.*storm|storm.*damage|flood.*property|coastal.*damage",
       to_pattern = "coastal.*defen|flood.*policy|coastal.*protect.*policy|seawall|breakwater",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # ============================================================================
  # FEEDBACK LOOP PATTERNS: R -> D (responses modifying drivers)
  # ============================================================================

  # R -> D: Marine protected area reducing extractive demand
  list(from_type = "responses", to_type = "drivers",
       from_pattern = "mpa|marine.*protect.*area|no.?take.*zone|sanctuary",
       to_pattern = "extract.*demand|resource.*demand|fish.*demand.*area",
       probability = 0.70, polarity = "-", strength = "medium",
       source = "Elliott et al. 2017"),

  # R -> D: Fishing quota restrictions diversifying livelihood demand
  list(from_type = "responses", to_type = "drivers",
       from_pattern = "fish.*quota|catch.*restrict|tac.*restrict|harvest.*limit",
       to_pattern = "diversif.*livelihood|alternat.*livelihood|econom.*diversif|tourism.*demand",
       probability = 0.65, polarity = "+", strength = "medium",
       source = "Costanza et al. 2014"),

  # R -> D: Renewable energy targets increasing offshore energy demand
  list(from_type = "responses", to_type = "drivers",
       from_pattern = "renew.*energy.*target|clean.*energy.*policy|green.*energy|carbon.*neutral",
       to_pattern = "offshore.*energy.*demand|wind.*energy.*demand|tidal.*demand|wave.*energy",
       probability = 0.80, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # ============================================================================
  # MINERAL/AGGREGATE EXTRACTION PATHWAY
  # ============================================================================

  # D -> A: Mineral resource demand driving mining/dredging
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "mineral.*demand|aggregat.*demand|sand.*demand|gravel.*demand|resource.*extract",
       to_pattern = "mining|dredg|aggregat.*extract|seabed.*mining|sand.*extract",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # A -> P: Mining/dredging causing seabed disturbance
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "mining|dredg|aggregat.*extract|seabed.*mining|sand.*extract",
       to_pattern = "seabed.*disturb|habitat.*destruct|benthic.*disturb|sediment.*plume|substrate.*remov",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # P -> S: Seabed disturbance causing benthic decline
  list(from_type = "pressures", to_type = "states",
       from_pattern = "seabed.*disturb|substrate.*remov|benthic.*disturb|dredg.*damage",
       to_pattern = "benthic.*communit.*declin|benthic.*fauna|infauna.*declin|seabed.*habitat.*loss",
       probability = 0.85, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  # S -> I: Benthic decline reducing habitat provision
  list(from_type = "states", to_type = "impacts",
       from_pattern = "benthic.*communit.*declin|benthic.*loss|infauna.*declin|seabed.*habitat",
       to_pattern = "habitat.*provision|nursery.*habitat|shelter.*service|benthic.*ecosystem.*service",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Liquete et al. 2013"),

  # ============================================================================
  # OFFSHORE WIND PATHWAY
  # ============================================================================

  # D -> A: Energy demand driving wind farm construction
  list(from_type = "drivers", to_type = "activities",
       from_pattern = "energy.*demand|electri.*demand|renew.*target|decarbon",
       to_pattern = "wind.*farm.*construct|offshore.*wind|turbine.*install|wind.*energy.*develop",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Costanza et al. 2014"),

  # A -> P: Wind construction causing underwater noise and habitat loss
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "wind.*farm|offshore.*wind|turbine.*install|pile.*driv",
       to_pattern = "underwat.*noise|seabed.*habitat.*loss|electromagnetic|vibrat|construct.*noise",
       probability = 0.90, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # P -> S: Noise/habitat loss affecting marine mammals and seabirds
  list(from_type = "pressures", to_type = "states",
       from_pattern = "underwat.*noise.*wind|construct.*noise|turbine.*noise|wind.*habitat.*loss",
       to_pattern = "marine.*mammal|seabird|cetacean|porpoise|bird.*collision|migrat.*disrupt",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Halpern et al. 2015"),

  # S -> I: Ecosystem effects changing biodiversity/energy service trade-off
  list(from_type = "states", to_type = "impacts",
       from_pattern = "marine.*mammal.*effect|seabird.*effect|wind.*ecosystem|turbine.*ecolog",
       to_pattern = "biodiver.*chang|energy.*service|reef.*effect|ecosystem.*trade.?off",
       probability = 0.75, polarity = "-", strength = "medium",
       source = "Liquete et al. 2013"),

  # ============================================================================
  # INVASIVE SPECIES MANAGEMENT PATHWAY
  # ============================================================================

  # R -> P: Invasive species control reducing invasive pressure
  list(from_type = "responses", to_type = "pressures",
       from_pattern = "invasive.*species.*control|invasive.*manag|eradicat.*program|alien.*species.*control",
       to_pattern = "invasive.*pressure|invasive.*spread|non.?native.*pressure|alien.*species.*impact",
       probability = 0.70, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # R -> A: Biosecurity regulation modifying shipping/aquaculture practices
  list(from_type = "responses", to_type = "activities",
       from_pattern = "biosecur.*regulat|ballast.*convention|ballast.*manag|invasive.*legislat",
       to_pattern = "ship.*practic|ballast.*water.*treat|aquacult.*practic|biosecur.*protocol",
       probability = 0.65, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # A -> P: Ballast water treatment reducing introduction risk
  list(from_type = "activities", to_type = "pressures",
       from_pattern = "ballast.*water.*treat|ballast.*exchang|biosecur.*practic",
       to_pattern = "invasive.*introduc|non.?native.*introduc|alien.*species.*risk|bioinvasion",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "HELCOM 2018"),

  # ============================================================================
  # ARCTIC-SPECIFIC PATTERNS
  # ============================================================================

  # P -> S: Sea ice loss reducing ice-dependent species habitat
  list(from_type = "pressures", to_type = "states",
       from_pattern = "sea.*ice.*loss|ice.*cover.*reduc|arctic.*warm|ice.*melt|ice.*retreat",
       to_pattern = "ice.*depend.*species|polar.*bear|walrus|ice.*seal|arctic.*fauna|ice.*habitat",
       probability = 0.90, polarity = "-", strength = "strong",
       source = "Halpern et al. 2015"),

  # P -> S: Permafrost thaw causing coastal erosion and infrastructure damage
  list(from_type = "pressures", to_type = "states",
       from_pattern = "permafrost.*thaw|permafrost.*degrad|ground.*ice.*melt|thermokarst",
       to_pattern = "coastal.*erosion.*arctic|infrastruc.*damage|shoreline.*retreat|land.*subsid",
       probability = 0.85, polarity = "+", strength = "strong",
       source = "Halpern et al. 2015"),

  # S -> I: Polar ecosystem change reducing indigenous subsistence provision
  list(from_type = "states", to_type = "impacts",
       from_pattern = "polar.*ecosystem.*chang|arctic.*ecosystem|ice.*depend.*declin|arctic.*biodiver",
       to_pattern = "indigenous.*subsist|tradit.*harvest|subsist.*provision|inuit.*livelihood|arctic.*food.*secur",
       probability = 0.80, polarity = "-", strength = "medium",
       source = "Costanza et al. 2014")
)


# ==============================================================================
# SYNONYM DATABASE FOR FUZZY MATCHING
# ==============================================================================

#' Synonym groups for marine SES terminology
#'
#' Maps common marine SES terms to groups of synonyms to enable fuzzy matching
#' when looking up connections in the knowledge base.
#'
#' @format Named list where each key is a canonical term and values are synonyms
SES_SYNONYM_DB <- list(
  fishing     = c("fish", "trawl", "harvest", "catch", "angl", "seine", "gillnet",
                   "longline", "dredge", "netting"),
  aquaculture = c("aquacultur", "maricultur", "fish farm", "shellfish farm",
                   "mussel farm", "oyster farm", "salmon farm", "shrimp farm"),
  pollution   = c("pollut", "contamin", "toxic", "emission", "discharg", "effluent",
                   "runoff", "waste", "sewage", "litter"),
  nutrient    = c("nutrient", "nitrogen", "phosphor", "eutrophic", "fertili",
                   "nitrate", "phosphate", "ammonia"),
  habitat     = c("habitat", "biotope", "ecosystem", "reef", "seagrass", "mangrove",
                   "wetland", "saltmarsh", "kelp", "coral"),
  biodiversity = c("biodiver", "species", "richness", "abundance", "communit",
                    "assemblage", "population", "fauna", "flora"),
  climate     = c("climat", "warm", "temperature", "co2", "carbon", "greenhouse",
                   "acidif", "sea level", "ice"),
  tourism     = c("tourism", "recreat", "leisure", "diving", "snorkel", "beach",
                   "cruise", "yacht", "sail"),
  shipping    = c("ship", "vessel", "cargo", "freight", "port", "harbor",
                   "maritime", "tanker", "transport"),
  development = c("develop", "construct", "build", "urban", "infrastruc",
                   "reclamat", "dredg", "engineer"),
  conservation = c("conserv", "protect", "preserv", "restor", "rehabilit",
                    "mpa", "sanctuary", "reserve"),
  decline     = c("declin", "loss", "reduc", "degrad", "depletion",
                   "collapse", "deteriorat", "diminish", "erosion"),
  increase    = c("increas", "growth", "rise", "expansion", "intensif",
                   "escalat", "proliferat", "amplif"),
  management  = c("manag", "regulat", "govern", "plan", "policy",
                   "legislat", "enforcement", "monitor"),
  livelihood  = c("livelihood", "income", "employ", "job", "wage",
                   "econom.*benefit", "revenue", "profit"),
  health      = c("health", "disease", "illness", "mortality", "morbid",
                   "well.?being", "safety", "risk"),
  food        = c("food", "protein", "nutrition", "seafood", "diet",
                   "sustenance", "provision")
)


# ==============================================================================
# KNOWLEDGE BASE LOOKUP FUNCTIONS
# ==============================================================================

#' Look up a connection in the knowledge base
#'
#' Searches the SES_CONNECTION_DB for entries matching the given element pair.
#' Returns the best match with connection properties.
#'
#' @param from_name Character. Source element name
#' @param from_type Character. Source DAPSI(W)R(M) type
#' @param to_name Character. Target element name
#' @param to_type Character. Target DAPSI(W)R(M) type
#' @param use_synonyms Logical. Whether to expand matching with synonym database (default: TRUE)
#'
#' @return List with match details or NULL if no match found:
#'   \describe{
#'     \item{probability}{Base connection probability (0-1)}
#'     \item{polarity}{Known polarity ("+" or "-")}
#'     \item{strength}{Known strength ("weak", "medium", "strong")}
#'     \item{source}{Literature source}
#'     \item{match_quality}{Match quality: "exact", "synonym", or "partial"}
#'   }
#'
#' @examples
#' \dontrun{
#' result <- lookup_knowledge_base("Food security", "drivers", "Commercial fishing", "activities")
#' # Returns: list(probability = 0.95, polarity = "+", strength = "strong", ...)
#' }
#'
#' @export
lookup_knowledge_base <- function(from_name, from_type, to_name, to_type,
                                   use_synonyms = TRUE) {
  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  best_match <- NULL
  best_score <- 0

  for (entry in SES_CONNECTION_DB) {
    # Must match types
    if (entry$from_type != from_type || entry$to_type != to_type) next

    # Check pattern matches
    from_match <- grepl(entry$from_pattern, from_lower, perl = TRUE)
    to_match <- grepl(entry$to_pattern, to_lower, perl = TRUE)

    if (from_match && to_match) {
      # Exact pattern match - highest quality
      score <- entry$probability * 1.0
      if (score > best_score) {
        best_score <- score
        best_match <- list(
          probability = entry$probability,
          polarity = entry$polarity,
          strength = entry$strength,
          source = entry$source,
          match_quality = "exact"
        )
      }
    } else if (use_synonyms && (from_match || to_match)) {
      # Partial match - try synonym expansion on the non-matching side
      expanded_match <- FALSE
      if (from_match && !to_match) {
        expanded_match <- .synonym_match(to_lower, entry$to_pattern)
      } else if (!from_match && to_match) {
        expanded_match <- .synonym_match(from_lower, entry$from_pattern)
      }

      if (expanded_match) {
        score <- entry$probability * 0.8  # Discount for synonym match
        if (score > best_score) {
          best_score <- score
          best_match <- list(
            probability = entry$probability * 0.9,  # Slightly lower confidence
            polarity = entry$polarity,
            strength = entry$strength,
            source = entry$source,
            match_quality = "synonym"
          )
        }
      }
    }
  }

  return(best_match)
}


#' Check if a text matches a pattern through synonym expansion
#'
#' Expands both the text and pattern using SES_SYNONYM_DB to check for
#' matches that the raw pattern would miss.
#'
#' @param text Character. The text to check
#' @param pattern Character. The regex pattern to match against
#' @return Logical. TRUE if a synonym-based match is found
#' @keywords internal
.synonym_match <- function(text, pattern) {
  # Extract key terms from the pattern (split on regex operators)
  pattern_terms <- unlist(strsplit(pattern, "\\||\\.\\*|\\.|\\?|\\*|\\+|\\(|\\)"))
  pattern_terms <- trimws(pattern_terms)
  pattern_terms <- pattern_terms[nchar(pattern_terms) >= 3]

  if (length(pattern_terms) == 0) return(FALSE)

  # For each synonym group, check if both the text and pattern terms overlap

  for (group_name in names(SES_SYNONYM_DB)) {
    synonyms <- SES_SYNONYM_DB[[group_name]]

    # Does the text contain any synonym from this group?
    text_has_synonym <- any(sapply(synonyms, function(s) grepl(s, text, perl = TRUE)))
    if (!text_has_synonym) next

    # Does any pattern term belong to this synonym group?
    pattern_has_synonym <- any(sapply(pattern_terms, function(pt) {
      any(sapply(synonyms, function(s) grepl(pt, s, perl = TRUE) || grepl(s, pt, perl = TRUE)))
    }))

    if (pattern_has_synonym) return(TRUE)
  }

  return(FALSE)
}


#' Calculate TF-IDF-style keyword weight
#'
#' Computes a weight for each keyword based on how discriminative it is.
#' Common words get lower weights, rare domain-specific terms get higher weights.
#'
#' @param keyword Character. The keyword to weight
#' @return Numeric weight between 0.5 and 2.0
#' @keywords internal
.keyword_idf_weight <- function(keyword) {
  # Common/generic words that appear in many contexts -> lower weight
  common_words <- c("chang", "increas", "decreas", "loss", "impact",
                     "effect", "manag", "develop", "system", "environ",
                     "marine", "coast", "ocean", "sea", "water")

  # Domain-specific terms that are highly discriminative -> higher weight
  rare_words <- c("eutrophic", "hypox", "acidif", "bleach", "trawl",
                   "bycatch", "bioaccumul", "calcif", "permafrost",
                   "denitrif", "anox", "pteropod", "sargassum",
                   "ballast", "anti.?foul", "discarding", "ghost.*net")

  keyword_lower <- tolower(keyword)

  if (any(sapply(rare_words, function(rw) grepl(rw, keyword_lower)))) {
    return(2.0)
  }
  if (any(sapply(common_words, function(cw) grepl(cw, keyword_lower)))) {
    return(0.6)
  }
  return(1.0)  # Default weight
}


#' Calculate enhanced relevance score using knowledge base
#'
#' Combines knowledge base lookup, synonym-expanded matching, and TF-IDF
#' weighted keyword overlap to produce a more accurate relevance score
#' than simple bag-of-words matching.
#'
#' @param from_name Character. Source element name
#' @param to_name Character. Target element name
#' @param from_type Character. Source DAPSI(W)R(M) type
#' @param to_type Character. Target DAPSI(W)R(M) type
#' @param base_keywords Named list of keyword vectors per connection type
#'
#' @return Numeric relevance score between 0 and 1
#'
#' @export
calculate_enhanced_relevance <- function(from_name, to_name, from_type, to_type,
                                          base_keywords = NULL) {
  # Step 1: Check knowledge base for exact/synonym match
  kb_match <- lookup_knowledge_base(from_name, from_type, to_name, to_type)
  if (!is.null(kb_match)) {
    # Knowledge base match - use its probability as base, with quality discount
    kb_score <- switch(kb_match$match_quality,
      "exact"   = kb_match$probability,
      "synonym" = kb_match$probability * 0.9,
      kb_match$probability * 0.8
    )
    return(min(1.0, kb_score))
  }

  # Step 2: TF-IDF weighted keyword matching (fallback)
  from_lower <- tolower(from_name)
  to_lower <- tolower(to_name)

  # Use provided keywords or fall back to connection type keywords
  if (is.null(base_keywords)) {
    base_keywords <- list(
      drivers_activities = c("fish", "food", "econom", "livelihood", "subsistence",
                              "commerc", "industr", "recreat", "tourism", "develop",
                              "demand", "need", "cultural", "spiritual", "energy",
                              "transport", "trade"),
      activities_pressures = c("fish", "extract", "harvest", "develop", "construct",
                                "pollut", "discharge", "emission", "waste", "noise",
                                "disturb", "remov", "introduc", "invasive", "dredg",
                                "trawl", "aquacult", "farm"),
      pressures_states = c("pollut", "nutrient", "contamin", "extract", "remov",
                            "habitat", "species", "abundance", "diversity", "structure",
                            "function", "ecosystem", "chemical", "physical", "biological",
                            "acidif", "warm", "noise", "litter"),
      states_impacts = c("decline", "loss", "degrad", "change", "abundance",
                          "diversity", "habitat", "ecosystem", "service", "provision",
                          "regulat", "cultural", "support", "carbon", "protect"),
      impacts_welfare = c("food", "protein", "nutrition", "income", "livelihood",
                           "employ", "health", "wellbeing", "recreation", "cultural",
                           "spiritual", "aesthetic", "economic", "social", "safety",
                           "property", "displace"),
      responses_pressures = c("regulat", "protect", "conserv", "restor", "manag",
                               "monitor", "enforc", "limit", "restrict", "ban",
                               "quota", "closure", "zone", "designation", "treat",
                               "remov", "clean"),
      welfare_responses = c("concern", "awareness", "demand", "advocacy", "pressure",
                             "policy", "legislation", "management", "action",
                             "intervention", "compens", "support"),
      responses_drivers = c("policy", "awareness", "education", "incentiv", "subsid",
                             "tax", "regulation", "enforcement", "behavior", "demand"),
      responses_activities = c("limit", "restrict", "ban", "regulat", "control",
                                "manage", "permit", "license", "quota", "closure",
                                "zone", "gear.*restrict"),
      welfare_drivers = c("food", "econom", "livelihood", "income", "need",
                           "demand", "subsist", "employ", "security", "poverty")
    )
  }

  key <- paste(from_type, to_type, sep = "_")
  keywords <- base_keywords[[key]]

  if (is.null(keywords)) return(0.5)

  # TF-IDF weighted scoring
  total_weight <- 0
  matched_weight <- 0

  for (kw in keywords) {
    weight <- .keyword_idf_weight(kw)
    total_weight <- total_weight + weight

    from_hit <- grepl(kw, from_lower)
    to_hit <- grepl(kw, to_lower)

    if (from_hit && to_hit) {
      matched_weight <- matched_weight + weight * 1.5  # Both match = bonus
    } else if (from_hit || to_hit) {
      matched_weight <- matched_weight + weight
    }
  }

  # Step 3: Synonym expansion bonus
  synonym_bonus <- 0
  from_words <- unlist(strsplit(gsub("[^a-z ]", "", from_lower), "\\s+"))
  to_words <- unlist(strsplit(gsub("[^a-z ]", "", to_lower), "\\s+"))

  for (group_name in names(SES_SYNONYM_DB)) {
    synonyms <- SES_SYNONYM_DB[[group_name]]
    from_in_group <- any(sapply(synonyms, function(s) any(grepl(s, from_words))))
    to_in_group <- any(sapply(synonyms, function(s) any(grepl(s, to_words))))

    if (from_in_group && to_in_group) {
      synonym_bonus <- synonym_bonus + 0.1
    }
  }
  synonym_bonus <- min(synonym_bonus, 0.3)  # Cap bonus

  # Calculate final score
  if (total_weight == 0) return(0.3)

  keyword_score <- matched_weight / total_weight
  # Normalize to 0.2-0.95 range
  relevance <- 0.2 + 0.75 * min(1.0, keyword_score + synonym_bonus)

  return(min(1.0, relevance))
}


# ==============================================================================
# NEGATION-AWARE PHRASE ANALYSIS
# ==============================================================================

#' Analyze phrase polarity with negation detection
#'
#' Determines if a phrase is semantically positive or negative, accounting for
#' negation words and compound phrases like "pollution reduction" (positive)
#' or "no fishing" (negative effect on fishing).
#'
#' @param phrase Character. The phrase to analyze
#' @return List with:
#'   \describe{
#'     \item{sentiment}{Overall sentiment: "positive", "negative", or "neutral"}
#'     \item{negated}{Logical. Whether the phrase contains negation}
#'     \item{base_sentiment}{Sentiment before negation applied}
#'   }
#'
#' @export
analyze_phrase_polarity <- function(phrase) {
  phrase_lower <- tolower(phrase)

  # Negation words/phrases
  negation_patterns <- c(
    "\\bno\\b", "\\bnot\\b", "\\bnon[- ]", "\\bwithout\\b",
    "\\bprevent", "\\bprohibit", "\\bban\\b", "\\bbanned\\b",
    "\\breduc", "\\bremov", "\\belimin", "\\bavoid",
    "\\bcontrol", "\\blimit", "\\brestrict", "\\bstop",
    "\\bless\\b", "\\black\\b", "\\babsence\\b"
  )

  # Compound phrases where negation + negative = positive
  # e.g., "pollution reduction" = reducing a bad thing = positive
  reversal_compounds <- c(
    "pollut.*reduc", "pollut.*remov", "pollut.*control",
    "emission.*reduc", "emission.*control", "emission.*limit",
    "pressure.*reduc", "stress.*reduc", "risk.*reduc",
    "litter.*reduc", "litter.*remov", "litter.*clean",
    "waste.*reduc", "waste.*treat", "waste.*remov",
    "erosion.*control", "erosion.*prevent",
    "noise.*reduc", "noise.*control",
    "overfish.*prevent", "overfish.*reduc",
    "deforest.*prevent", "habitat.*loss.*prevent",
    "decline.*halt", "decline.*revers",
    "degradat.*halt", "degradat.*revers"
  )

  # Positive keywords
  positive_kw <- c("increas", "improv", "enhanc", "restor", "recover",
                    "growth", "benefit", "gain", "protect", "conserv",
                    "sustain", "resilient", "healthy", "abundant")

  # Negative keywords
  negative_kw <- c("declin", "loss", "degrad", "damag", "destruct",
                    "pollut", "contamin", "overfish", "erosion",
                    "deplet", "collapse", "extinct", "harm",
                    "bleach", "hypox", "mortality")

  # Check for reversal compounds first (highest priority)
  is_reversal <- any(sapply(reversal_compounds, function(p) grepl(p, phrase_lower, perl = TRUE)))
  if (is_reversal) {
    return(list(sentiment = "positive", negated = TRUE, base_sentiment = "negative"))
  }

  # Check for negation
  has_negation <- any(sapply(negation_patterns, function(p) grepl(p, phrase_lower, perl = TRUE)))

  # Check base sentiment
  has_positive <- any(sapply(positive_kw, function(kw) grepl(kw, phrase_lower)))
  has_negative <- any(sapply(negative_kw, function(kw) grepl(kw, phrase_lower)))

  if (has_positive && !has_negative) {
    base_sent <- "positive"
  } else if (has_negative && !has_positive) {
    base_sent <- "negative"
  } else if (has_positive && has_negative) {
    # Both present - context dependent, default to most recent/dominant
    base_sent <- "mixed"
  } else {
    base_sent <- "neutral"
  }

  # Apply negation
  if (has_negation && base_sent == "positive") {
    return(list(sentiment = "negative", negated = TRUE, base_sentiment = base_sent))
  }
  if (has_negation && base_sent == "negative") {
    return(list(sentiment = "positive", negated = TRUE, base_sentiment = base_sent))
  }

  return(list(sentiment = base_sent, negated = has_negation, base_sentiment = base_sent))
}


# ==============================================================================
# INITIALIZATION MESSAGE
# ==============================================================================

message("[INFO] SES Connection Knowledge Base loaded successfully")
message(sprintf("       %d curated connections from published marine SES case studies",
                length(SES_CONNECTION_DB)))
message(sprintf("       %d synonym groups for fuzzy matching", length(SES_SYNONYM_DB)))
