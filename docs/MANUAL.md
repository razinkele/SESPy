# SESPy User Manual

**Version 1.8.2 · September 2026**

SESPy is the Python port of the MarineSABRES Social-Ecological Systems (SES) Toolbox. It helps a facilitator and a group of stakeholders build a causal loop diagram of a marine social-ecological system, typed with the DAPSI(W)R(M) framework, and then interrogate that diagram: which feedback loops it contains, which elements carry leverage, where governance does not reach the pressures it should, how robust the structure is, and what an intervention might propagate into.

This manual has four parts. Part I gets you started. Part II walks through every panel of the app in the order they appear in the navigation. Part III explains the science behind each analysis, including where SESPy departs from the published method. Part IV lists the references. An appendix covers file formats, URL parameters, a glossary and known limitations.

---

## Contents

**Part I — Getting started**
1. What SESPy is
2. The workflow stepper and navigation
3. The sample project
4. Projects: saving, loading, autosave, recovery, language and theme

**Part II — Panels**
5. Project Setup · 6. Stakeholders · 7. Templates · 8. SES Wizard · 9. Edit Data · 10. Rate Connections · 11. CLD Visualization · 12. Loop Analysis · 13. Network Metrics · 14. Leverage Points · 15. Factor Quadrant · 16. Boolean & Laplacian · 17. Dynamic Simulation · 18. Behaviour Over Time · 19. Intervention · 20. Simplify Network · 21. Import Data · 22. Recent Projects · 23. Export Report · 24. Topbar: Feedback, About, Options, Help

**Part III — Scientific background**
25. DAPSI(W)R(M) typing · 26. Causal loop diagrams · 27. Feedback loops and delay · 28. Centrality and the leverage composite · 29. Vester influence × dependence · 30. Meadows realms and adjusted loop centrality · 31. Social-ecological fit · 32. Governance gap · 33. Governance actor influence and concentration · 34. Cascade vulnerability and the KL early warning · 35. Causal paths · 36. SES subsystem modules (hypermodules) · 37. Uncertainty scoring (D2D) · 38. Loop dominance over time · 39. Token diffusion · 40. Laplacian stability and Boolean attractors · 41. Multi-rater consensus and contested edges · 42. Stakeholder power × interest

**Part IV — References**
43. Foundations · 44. Literature that shaped v1.0 to v1.7

**Appendix**
A. File formats · B. URL parameters · C. Glossary · D. Known limitations

---

# Part I — Getting started

## 1. What SESPy is

A social-ecological system is a place where people, activities, ecology and governance are bound together by cause and effect. The MarineSABRES project (Horizon Europe) works with such systems in European seas, and its R Shiny SES Toolbox lets stakeholder groups draw the causal structure of their own system as a causal loop diagram (CLD) and analyse it. SESPy is a feature-for-feature Python port of that toolbox, built on Python Shiny, NetworkX and pyvis, with a set of newer analyses added from the 2026 literature (Part III).

Everything in SESPy revolves around one object, the project: a list of **elements** (the nodes of the diagram, each typed with a DAPSI(W)R(M) category) and a list of **connections** (directed causal links, each with a polarity, a strength, a confidence and a delay). All analyses read this object; most never change it.

## 2. The workflow stepper and navigation

![The app at start: workflow stepper across the top, navigation on the left, the CLD panel open](docs/screenshots/full_app.png)

Across the top of the page is a six-step **workflow stepper**. It is a guide, not a gate: every step is clickable and you can jump anywhere at any time.

| Step | Opens | Panels that belong to it |
|---|---|---|
| Setup | Project Setup | Project Setup, Stakeholders |
| Get Started | Recent Projects | Recent Projects |
| Create SES | Templates | Templates, SES Wizard, Edit Data, Rate Connections, Import Data |
| Visualize | CLD Visualization | CLD Visualization |
| Analyze | Loop Analysis | Loop Analysis, Network Metrics, Leverage Points, Factor Quadrant, Boolean & Laplacian, Dynamic Simulation, Behaviour Over Time, Intervention, Simplify Network |
| Report | Export Report | Export Report |

Down the left is the **navigation** listing all nineteen panels. The burger icon collapses it to icons only. Pinned to the bottom of the sidebar, below the navigation, sit three **quick actions**: Save Project, Load Project and New Project (section 4). The app opens on CLD Visualization.

In the top right are four small buttons: **Feedback**, **About**, **Options** and **Help** (section 24). The manual you are reading is the Manual tab of the About dialog.

## 3. The sample project

The app starts with a small demo, *Tuscan Archipelago — minimal demo SES*. It has 17 elements and 20 connections and uses every DAPSI(W)R(M) type except Measures. New Project resets to it, so it is always one click away if you want to try an analysis on known data.

| Type | Elements |
|---|---|
| Drivers | Tourism demand, Seafood demand |
| Activities | Recreational boating, Small-scale fishing, Aquaculture |
| Pressures | Anchor damage, Bycatch, Nutrient enrichment |
| Marine Processes & Functioning | Posidonia meadows, Pelagic fish stocks |
| Ecosystem Services | Coastal protection, Food provisioning, Recreational value |
| Goods & Benefits | Tourism revenue, Fisheries income |
| Responses | MPA enforcement, Mooring buoy program |

Loop Analysis finds five feedback loops in it. The three that close through demand (tourism revenue feeding tourism demand, fisheries income feeding seafood demand) each contain one negative link and are balancing; the fisheries one runs through the delayed link from pelagic fish stocks to food provisioning and is flagged oscillation-prone. The two reinforcing loops both run through the mooring buoy programme, whose response to anchor damage adds a second negative link. Numbers quoted in Part II ("on the sample …") refer to this project.

## 4. Projects: saving, loading, autosave, recovery, language and theme

**Save Project** downloads the current project as a JSON file named `sespy-project-<date-time>.json`. It also clears the autosave. **Load Project** accepts a `.json` project file, validates it (Appendix A) and replaces the current project. **New Project** resets to the sample.

**Autosave** writes the project to `~/.sespy/autosave.json` on every change while it is enabled (Options dialog). On the next start, if that file is less than 24 hours old, a message offers to restore it. Saving a project clears the autosave; you can also clear it from Options.

**Recent Projects** (section 22) lists files opened with Load Project.

**Language and theme** are set in the Options dialog. Nine interface languages are available; the language resets to English at the start of each session unless a `?lang=` URL parameter is used (Appendix B). Two themes exist, Light Marine and Deep Ocean (dark).

**The address bar** tracks the active panel as `?view=<panel>`, so a bookmark or a shared link reopens the same panel. It does not carry project data.

---

# Part II — Panels

Each section below names the panel as it appears in the navigation, then covers purpose, controls, outputs, how to read the result, and caveats. Labels are quoted as they appear in English.

## 5. Project Setup

![Project Setup](docs/screenshots/pims.png)

**Purpose.** Record the project's context: name, demonstration area, focal issue, definition statement and scope. These fields travel with the project file; the report header itself shows only the project name and the last-modified time.

**Controls.** Under "Project information": "Project name", "Demonstration area" (Tuscan Archipelago, Arctic Northeast Atlantic, Macaronesia), "Focal issue" and "Definition statement". Under "System scope": "Temporal scale" (Daily to Decadal), "Spatial scale" (Local to International) and "System in focus". "Save project information" writes all fields at once and stamps the modification time.

**Outputs.** "Last saved at", "Modified at" and "Schema version" under the scope column. Before the first save in a session the first reads "Not saved this session."

**Caveats.** Fields are re-populated whenever a project is loaded, so switching projects refreshes the form. A blank name is stored as "Untitled Project".

## 6. Stakeholders

![Stakeholders](docs/screenshots/stakeholders.png)

**Purpose.** A stakeholder register with a power × interest grid, engagement and communication planning, summary analytics and exports (section 42).

**Controls.** Five tabs. **Register**: "Add / edit stakeholder" with Name, Type, Sector, Contact, Interests, Role, Power (High/Medium/Low), Interest (High/Medium/Low), Attitude and Engagement level; "Save stakeholder" and "Cancel"; "Edit selected" and "Remove selected" act on the highlighted row of the register table. **Power-Interest Grid** has no controls. **Engagement Planning**: Stakeholder, Engagement method, date, objectives, outcomes, Status, Facilitator, "Add activity". **Communication Plan**: Target audience, Communication type, date, Frequency, key message, responsible person, "Add communication". **Analysis** carries the export buttons: "Download full report (Excel)", "Download Power-Interest grid (PNG)", "Download summary (PDF)".

**Outputs.** The register table. The grid plots every stakeholder with both power and interest set into four quadrants captioned Key players, Keep satisfied, Keep informed and Monitor, followed by a "Grid summary" listing each quadrant's strategy and members and naming anyone not plotted for lack of scores. The engagement and communication logs. The analysis tab shows counts, an engagement-coverage bar and stakeholders by type and sector.

**Reading it.** Key players (high power, high interest) are managed closely; keep satisfied means high power and lower interest; keep informed means lower power and high interest; monitor is the rest.

**Caveats.** Name and Type are required. Stakeholders are also the rater list for Rate Connections (section 10), so register them before rating. The stakeholder register is saved with the project but is not part of the report export.

## 7. Templates

![Templates](docs/screenshots/templates.png)

**Purpose.** Start from a ready-made domain project instead of the sample.

**Controls.** One card per template with its name, size, demonstration area and description, and a "Load" button. Loading replaces the current project, so save first if you want to keep your work; the panel says so at the top.

**Shipped templates.** Coastal Tourism SES (17 elements, 20 connections, Tuscan Archipelago), Minimal Demo (5 and 6, a positive three-cycle plus a mutually activating pair, useful for learning the analyses), Offshore Wind Farm SES (19 and 21, Macaronesia), Small-scale Coastal Fisheries SES (18 and 22, Arctic Northeast Atlantic).

## 8. SES Wizard

![SES Wizard](docs/screenshots/wizard.png)

**Purpose.** Build a diagram from scratch by answering twelve questions in DAPSI(W)R(M) order, then accept suggested connections.

**Controls.** "Start Wizard". If the project already holds data, a dialog asks whether to replace it. A breadcrumb shows the twelve steps: Regional Sea, Ecosystem Type, Countries, Main Issue, then one free-text step each for Drivers, Activities, Pressures, States, Impacts, Welfare and Responses, then Review Connections. Free-text steps take one entry per row with "Add another" and "Remove". "Back", "Next" and, on the last step, "Finish".

**Outputs.** On the last step a table of "Rule-based suggestions" with source, target, polarity, confidence, rationale and an Accept checkbox per row. If an Anthropic API key is configured, a "Generate with Claude API" button adds a second table of model-generated suggestions after a consent dialog that lists exactly which fields are sent.

**Reading it.** Each Next writes the entries as typed elements: Impacts become Ecosystem Services and Welfare becomes Goods & Benefits. Finish appends every accepted suggestion as a connection, de-duplicated by source, target and polarity with the higher confidence winning.

**Caveats.** Entries must be non-empty and unique within a step. The Claude path is optional and every failure falls back to rule-based suggestions with a message saying so. Without any scoring backend the wizard still creates the elements; connections are then added in Edit Data.

## 9. Edit Data

![Edit Data](docs/screenshots/entry.png)

**Purpose.** Edit the element and connection lists by hand. Every change is visible at once in every other panel.

**Controls.** Under "Elements": "Label", "Type" (the seven DAPSI(W)R(M) types), "Add element", "Remove selected element". Under "Connections": "Source", "Target", "Polarity" (+ reinforcing or − opposing), "Delay" (Immediate, Short, Long), "Add connection", "Remove selected connection". Rows are selected by clicking them in the tables.

**Outputs.** The elements table (id, label, type), the connections table (source, target, polarity, strength, delay) and a status line with the counts and a reminder to use Save Project to write to disk.

**Reading it.** Ids are generated from the type prefix (D, A, P, MPF, ES, GB, R). Removing an element also removes every connection that touches it, so the project never holds a dangling reference.

**Caveats.** This panel has no strength or confidence inputs. A new connection gets medium strength and confidence 3; those change only through Rate Connections or an import. Source and target must differ, and duplicate connections are refused.

## 10. Rate Connections

![Rate Connections](docs/screenshots/rate.png)

**Purpose.** Multi-rater elicitation (section 41). Each registered stakeholder records their own view of every connection; a consensus is recomputed and written back so every analysis sees it.

**Controls.** In the sidebar: "Rating as" picks the stakeholder whose rating you are entering, "Show contested only" filters the table to connections whose raters disagree on sign, and "Blind mode (hide others' ratings)" hides the other ratings until you have submitted your own. Selecting a row opens "Your rating": Polarity, Strength (Weak, Medium, Strong), Confidence (1 to 5), Delay, "Save my rating" and "Remove mine".

**Outputs.** A count of contested edges, the connections table with the consensus values, the number of ratings, whether you have rated it, and a disagreement marker; and "Current ratings", one line per rater.

**Reading it.** A warning marker in the disagreement column means the raters disagree on the sign; the tilde shows spread in strength or confidence. Consensus polarity and strength are what the diagram, the loops and every metric use.

**Caveats.** Stakeholders must exist in the register before anyone can rate. No structural editing happens here.

## 11. CLD Visualization

![CLD Visualization](docs/screenshots/cld.png)

**Purpose.** The interactive causal loop diagram of the whole project. This is the panel the app opens on.

**Controls.** In the sidebar, "Layout" chooses between "Hierarchical (DAPSI)" and "Physics-based". Hierarchical arranges elements in typed rows, from Goods & Benefits at one end through Ecosystem Services, Marine Processes & Functioning, Responses, Pressures and Activities to Drivers at the other; physics lets a force layout settle. "Node size" and "Label size" scale the drawing. In hierarchical mode, "Direction" (Down-Up, Up-Down, Left-Right, Right-Left), "Vertical (row) spacing" and "Horizontal (node) spacing" tune the grid. "Element types" is a checkbox group over the seven DAPSI(W)R(M) types; unticking one hides those elements. "Fit to view" recentres. The sidebar also shows the counts of nodes and edges and the density.

**Outputs.** The diagram. Positive links are drawn in one colour, negative in another; a dashed edge is a delayed link. A thick edge with a warning marker means the raters disagree on its sign (section 10). Clicking a node shows its id below the canvas.

**Reading it.** Colour is type, position is tier in hierarchical mode, dash is delay, thickness is disagreement. Elements that carry no DAPSI(W)R(M) type, for instance themes imported from a QSEM file and left unmapped, are always drawn regardless of the type filter.

## 12. Loop Analysis

![Loop Analysis](docs/screenshots/loops.png)

**Purpose.** Enumerate the feedback loops in the diagram and classify each one.

**Controls.** "Max loop length" (default 6) and "Max loops to find" (default 200) bound the search; "Detect loops" runs it. "Show uncertainty (Monte Carlo)" adds four probability columns computed by resampling the diagram (section 37) with "Monte Carlo samples" draws. "Inspect a loop" picks one loop for the detail view.

**Outputs.** The "Classification" block counts Reinforcing, Balancing and Oscillation-prone loops. The "Detected feedback loops" table lists every loop with its behaviour, whether it is delayed, its type, length and path; a warning marker after the behaviour means one of its edges has a contested sign. With uncertainty on, the columns "Existence %", "Reinforcing %", "Balancing %" and "Contested" appear. "Selected loop" shows the chosen loop as a small diagram with its path spelled out.

**Reading it.** A loop is reinforcing when it has an even number of negative links and balancing when the number is odd (section 27). Oscillation-prone marks a balancing loop that contains a delayed link. The caption says it plainly: this is a structural signature, not a simulation, and actual behaviour depends on gains and delay magnitudes the diagram does not carry.

**Caveats.** Any edit to the project clears the detected set; run "Detect loops" again. Dense diagrams can have more loops than the cap; when that happens other panels that sum over loops say so (section 14).

## 13. Network Metrics

![Network Metrics](docs/screenshots/metrics.png)

**Purpose.** Centrality rankings plus six SES-specific structural diagnostics, stacked in one page.

**Controls.** "Metric" chooses among Degree, Indegree, Outdegree, Betweenness, Closeness, Eigenvector and Pagerank (the labels are spelled as shown). "Show top N" sets the length of the ranking table.

**Outputs, top to bottom.**

1. **Social-ecological fit** (section 31). One number and a caption of the form "x of y edges cross the social–ecological boundary".
2. **Governance gap** (section 32). The pressure-gap fraction, how many pressure nodes lack a direct governance response, and any governance elements with no path into the ecological subsystem. Five plain-language messages cover the degenerate cases, from "not enough structure" to "model is largely untyped — map themes to DAPSI(W)R(M) first".
3. **Governance actor influence** (section 33). A one-line verdict, either "Governance influence is distributed across n actors" or "concentrated in <actor>", with the dominant actor's share and the normalised entropy. Below it, a table of governance elements with betweenness, eigenvector, PageRank and the composite influence.
4. **Cascade vulnerability** (section 34). Button-gated: press "Run cascade analysis". The result names the cascade threshold node, names the early-warning node with both step numbers, and lists every removal step with the surviving connected fraction, the surviving loop count, the single-step drop and the KL divergence.
5. **Causal pathways** (section 35). Button-gated: choose "From" and "To", press "Trace paths". The result counts positive, negative and ambiguous paths and lists each path with its length and polarity.
6. **SES subsystem modules** (section 36). Button-gated: press "Detect subsystem modules". The result counts modules, gives the share of typed elements that belong to one, and lists each module with its tier composition and member labels.
7. **Top-ranked elements**, the table for the chosen metric.
8. **Distribution**, a histogram of the chosen metric.
9. **Network sized by metric**, the diagram with node size proportional to the metric.

![Cascade vulnerability block after running](docs/screenshots/metrics_cascade.png)

**Reading it.** On the sample: fit 0.40 (8 of 20 edges cross the boundary), a governance gap of 0.33 (one of three pressures uncovered), governance concentrated in the mooring buoy programme, the cascade threshold at step 1 (Posidonia meadows) with the KL departure at step 7.

**Caveats.** The three button-gated blocks are cleared by any project change and must be re-run. Each block has its own idle hint so a blank block is never silent.

## 14. Leverage Points

![Leverage Points](docs/screenshots/leverage.png)

**Purpose.** Rank elements by a composite centrality score and place each one on the Meadows ladder of intervention depth.

**Controls.** "Show top N"; "Show uncertainty (Monte Carlo)" with "Monte Carlo samples".

**Outputs.** "Highest leverage elements": rank, id, label, type, realm (Parameters, Feedbacks, Design, Intent), ALC and the leverage score. With uncertainty on, a 95% confidence interval and an "unstable" flag per element. "Network sized by leverage" draws the diagram with node size proportional to the score.

**Reading it.** Score is the sum of standardised betweenness, eigenvector and PageRank (section 28). Realm is the Meadows level an intervention at that element would act on; an Activity that sits inside a detected feedback loop is placed in Feedbacks rather than Design, so two Activities can differ (section 30). ALC sums the signed strength of every loop the element sits in: positive is amplifying, negative is damping, zero means it is on no loop. It is not on the same scale as the leverage score beside it.

**Caveats.** When the model has more feedback loops than the detection limit, the ALC column is hidden and a line explains why: a score summed over a partial loop set is not reproducible.

## 15. Factor Quadrant

![Factor Quadrant](docs/screenshots/quadrant.png)

**Purpose.** Vester's influence × dependence classification of every element (section 29).

**Controls.** "Cross-hair split": Mean or Median.

**Outputs.** "Influence × Dependence map", a scatter with dependence on the horizontal axis and influence on the vertical, split into four quadrants: Active / Driving (top left), Critical / Ambivalent (top right), Buffering / Inert (bottom left), Reactive / Dependent (bottom right). Points are coloured by type and labelled. "Factor classification" tabulates rank, influence, dependence and quadrant.

**Reading it.** Active factors are the best levers: they drive much and are driven little. Critical factors are powerful but feed back on themselves, so pushing them has side effects. Reactive factors are outcomes and good indicators. Buffering factors are low priority. Magnitude only: reinforcing and opposing links both count, so read net direction from the diagram itself. When the influence distribution is hub-skewed the panel suggests the median split.

**Caveats.** With an empty or perfectly uniform diagram the plot says so instead of drawing a meaningless cross-hair.

## 16. Boolean & Laplacian

![Boolean & Laplacian](docs/screenshots/boolean.png)

**Purpose.** Two structural stability views of the signed adjacency matrix (section 40).

**Controls.** "Laplacian direction" (columns, in-degree, or rows, out-degree); "Max nodes (cap on 2^N search)" from 4 to 12; "Run analysis".

**Outputs.** The "Laplacian" tab shows the eigenvalue spectrum as a bar chart and a definition list with spectral radius, algebraic connectivity and a stability class. The "Boolean attractors" tab lists every attractor found by exhaustive search with its type, period, basin size and a representative state.

**Reading it.** The Laplacian spectrum characterises how perturbations spread; the algebraic connectivity is the second-smallest eigenvalue, zero when the graph is disconnected. Boolean attractors are the states or cycles the system settles into when every element is on or off and updates by the sign of its inputs. A large basin means many starting states end there.

**Caveats.** The Boolean search is exhaustive over 2^N states and hard-capped at 12 nodes. The sample has 17, so on a first run the Boolean tab shows the cap message while the Laplacian tab works. The message suggests Simplify Network, but that panel is preview-only (section 20); to run the Boolean search you have to reduce the project in Edit Data. Results are marked stale after any edit until re-run.

## 17. Dynamic Simulation

![Dynamic Simulation](docs/screenshots/simulation.png)

**Purpose.** Iterate the signed, strength-weighted adjacency matrix from an initial state, and repeat under random perturbation.

**Controls.** "Simulation controls": "Iterations" (50 to 2000), "Initial state" (Zeros, Random Gaussian, Uniform 1.0), "Show loop dominance", "Seed (optional)", "Run simulation". "Monte Carlo controls": "Number of simulations", "Perturbation kind" (uniform ±20%, sign flip 10%, Gaussian σ = 0.1), seed, "Run Monte Carlo".

**Outputs.** "Trajectories" plots every element over the iterations. With loop dominance on, the background is shaded by the loop that carries most of the activity at each step and a list of dominance shifts follows (section 38). "Final state" is a bar chart of the last iteration. "Monte Carlo" reports how many runs completed, a per-element table of mean, standard deviation and the 5th and 95th percentiles, and a grid of histograms.

![Monte Carlo tab](docs/screenshots/simulation_montecarlo.png)

**Reading it.** This is a linear iteration, not a calibrated model. Trajectories that grow without bound mean the structure amplifies; decaying ones mean it damps. Loop dominance attributes activity to loops; the caption reminds you that a share is an attribution, not proof of cause, and that timing depends on the initial state.

**Caveats.** With loop dominance on, a run that diverges beyond floating-point range or decays to exactly zero is truncated at that step and a message says so. Results are marked stale after any edit.

## 18. Behaviour Over Time

![Behaviour Over Time](docs/screenshots/bot.png)

**Purpose.** Attach a time series to an element and look at its trend.

**Controls.** "Element"; "Data source" (Manual entry, CSV upload, ISA-derived demo). Manual entry takes a year and a value with "Add point". CSV upload expects columns Year and Value. Demo mode fabricates a series from the element and draws a DEMO DATA watermark. "Year range", "Show trend line", "Show moving average" and its window.

**Outputs.** "Time series" plots the values with a dashed trend and a moving-average line, followed by mean, standard deviation, minimum, maximum and trend slope. "Data" shows the points and offers "Download CSV".

**Caveats.** Series live in the session only. They are not part of the project file and are lost on reload. If the element is deleted elsewhere the data is cleared.

## 19. Intervention

![Intervention](docs/screenshots/intervention.png)

**Purpose.** Two what-if tools: remove elements and watch centrality shift, and inject tokens at one element and watch them spread (section 39).

**Controls.** "Remove these nodes" (multi-select), "Metric", "Reset (no ablation)". In "Intervention simulation": "Intervene at", "Steps", "Tokens", "Run simulation".

**Outputs.** "Most-affected elements" lists the fifteen largest before/after changes of the chosen metric. "Network with ablation" greys out the removed elements and tints survivors by whether they gained or lost influence. "Intervention simulation" reports how many elements were reached, a ranked table of arrivals with net sign and first arrival step, and a bar chart with 95% error bars.

**Reading it.** Tokens follow random outgoing links and flip sign on a negative link. The random draw is fixed, so two intervention points differ by structure rather than chance. Arrivals are still one sample: the ± is the sampling margin, elements too close to separate share a rank, and a net sign of "~" means the split is within sampling error.

**Caveats.** The diffusion always uses the full model and ignores the ablation above it. Any change to the model, the source or the sliders clears the previous result.

## 20. Simplify Network

![Simplify Network](docs/screenshots/simplify.png)

**Purpose.** Preview a reduced diagram.

**Controls.** "Reduction mode": "By minimum strength" with "Keep edges at least" weak, medium or strong, or "Top N edges" with "Keep top N". "Drop now-isolated nodes".

**Outputs.** "Summary" shows elements and connections before and after; "Simplified network" draws the result.

**Caveats.** This panel is preview-only. Nothing is written back to the project and no other panel sees the reduction. To actually shrink a project, delete elements or connections in Edit Data.

## 21. Import Data

![Import Data](docs/screenshots/import.png)

**Purpose.** Bring a diagram in from an Excel workbook or from a QSEM model file.

**Controls.** A file input accepting `.xlsx`, `.xls`, `.qsem` and `.json`. "Assign DAPSIWRM types (QSEM only)" opens a mapping table from QSEM themes to DAPSI(W)R(M) types with heuristic suggestions pre-filled; a theme can be left untyped. "Load into project" commits.

**Outputs.** A preview of the parsed workbook (elements, connections, types) or a list of validation errors.

**Reading it.** An Excel workbook needs an Elements sheet with id, label and type, and a Connections sheet with source and target; names are matched case-insensitively. A `.qsem` file is the JSON node-and-link graph exported by the QSEM app.

**Caveats.** A `.json` uploaded here is read as QSEM, not as a SESPy project. To reopen a saved project use Load Project in the quick actions.

## 22. Recent Projects

![Recent Projects](docs/screenshots/recent.png)

**Purpose.** Reopen a recently loaded project.

**Outputs.** One card per entry with name, element and connection counts, timestamp and path, with "Load" and "Remove". Up to ten entries are kept in `~/.sespy/recent.json`.

**Caveats.** Only Load Project adds entries, and the path recorded is the browser upload's temporary copy, so entries can disappear when that copy is cleaned up. Save Project is a browser download and does not add an entry.

## 23. Export Report

![Export Report](docs/screenshots/report.png)

**Purpose.** Produce a shareable document.

**Controls.** "Download HTML", "Download PDF", "Download Word".

**Outputs.** A live preview of the report. The document contains a summary (elements, connections, loops, density), the element-type counts, the first twenty feedback loops, the top five elements for each centrality metric, and the top ten leverage points.

**Caveats.** PDF needs WeasyPrint installed (`pip install sespy[pdf]`); HTML and Word always work. The report does not include stakeholders, the quadrant, Boolean or simulation results, or Behaviour Over Time series.

## 24. Topbar: Feedback, About, Options, Help

**Feedback** opens a form with a message, a rating and a category, and lists the ten most recent entries. Entries are stored on the server.

**About** has three tabs: an overview of the app, this manual, and the changelog.

**Options** sets the theme, the language and autosave, shows when the last autosave happened, and can clear the autosave.

**Help** opens a side panel on the right that stays open while you work. It holds a one-paragraph summary of the workflow, a pointer to this manual, and the manual section for the panel you currently have open, with its screenshot. A link at the bottom opens the full manual in the About dialog.

---

# Part III — Scientific background

Each section says what the idea is, how SESPy computes it, where SESPy departs from the source, and how to read the number on screen.

## 25. DAPSI(W)R(M) typing

DAPSI(W)R(M) (Elliott, Burdon and Atkins, 2017) refines the older DPSIR chain for marine management. Drivers of basic human need require Activities, which exert Pressures, which change the State of the natural system (Marine Processes & Functioning in SESPy), which alters the Impacts on human Welfare (Ecosystem Services and Goods & Benefits), which call for Responses as Measures. SESPy uses the framework as a node typology: every element carries one of seven types, and several analyses partition the diagram by tier on that basis. Two partitions are in use, and they differ by design. The social-ecological fit metric (section 31) uses a two-way split: Pressures, Marine Processes & Functioning and Ecosystem Services are ecological; Drivers, Activities, Goods & Benefits and Responses are social; Measures is left out. The subsystem-module detection (section 36) and the governance diagnostics (sections 32 and 33) use a three-way split with the same ecological set, a social tier of Drivers, Activities and Goods & Benefits, and a governance tier of Responses and Measures. In the governance-gap test the pressures are the ecological targets that governance is expected to reach.

## 26. Causal loop diagrams

A CLD is a directed graph whose edges say "a change in A causes a change in B". SESPy stores four attributes on each edge. **Polarity** is + when B moves the same way as A and − when it moves the opposite way. **Strength** (weak, medium, strong) is a coarse weight used by the simulation and the simplifier. **Confidence** (1 to 5) records how sure the group is. **Delay** (immediate, short, long) records whether the effect lags. The diagram is qualitative: it has structure and sign but no calibrated equations, and every analysis in SESPy respects that limit. Signed, weighted edges of this kind are also the substance of fuzzy cognitive maps (Kosko, 1986), which is why a numeric edge weight in an imported workbook is mapped to a signed strength. The QSEM framework (Hulme, Radley and Brown, 2025) formalises structural analysis of exactly such diagrams, and SESPy's factor quadrant, multi-rater elicitation and `.qsem` import follow its conventions.

## 27. Feedback loops and delay

A feedback loop is a directed cycle. Its polarity is the product of its edge polarities: an even number of negative edges gives a **reinforcing** loop, which amplifies change, and an odd number gives a **balancing** loop, which counteracts it. SESPy enumerates simple cycles up to a length bound and a count cap, then classifies each. A balancing loop that contains a delayed edge is additionally flagged **oscillation-prone**, the classic system-dynamics signature of overshoot when a correction arrives late (Sterman, 2000). The flag is structural. Whether oscillation actually occurs depends on gains and delay lengths the diagram does not contain, and the panel says so.

## 28. Centrality and the leverage composite

Three centralities from network science are combined. **Betweenness** counts how often an element lies on shortest paths between others, so it finds brokers. **Eigenvector centrality** scores an element by the scores of its neighbours, so it finds elements embedded in influential clusters. **PageRank** is the stationary distribution of a random walk with restarts, so it finds elements that accumulate influence along directed paths. Each is standardised to a z-score across the whole diagram and the three are summed; the sum is the leverage score. The same composite, restricted to governance elements, is the actor-influence score in section 33, so the two panels agree by construction. Ratnayake et al. (2026) use degree, betweenness and eigenvector centrality in the same way to identify influential elements in a participatory social-ecological map.

## 29. Vester influence × dependence

Frederic Vester's sensitivity model classifies the variables of a system by their **active sum** (how much a variable influences the others, the row sum of the influence matrix) and **passive sum** (how much it is influenced, the column sum). Plotting one against the other and splitting at a cross-hair yields four classes. Active variables drive the system and are the best levers; critical variables are strongly connected in both directions and behave unpredictably when pushed; reactive variables are indicators; buffering variables are inert. SESPy weights each edge by its strength rank (weak 1, medium 2, strong 3) times its confidence (1 to 5), ignores sign, sums outgoing edges for influence and incoming edges for dependence, and offers a mean or median split. The median split is suggested when the influence distribution is hub-skewed, because one dominant element then drags the mean cross-hair away from the bulk of the points.

## 30. Meadows realms and adjusted loop centrality

Donella Meadows (1999) ranked twelve "places to intervene in a system" from shallow (parameters) to deep (the paradigm the system arises from). Abson et al. (2017) grouped them into four realms: **parameters**, **feedbacks**, **design** and **intent**. SESPy assigns a realm to each element from its DAPSI(W)R(M) type, with one structural refinement: Pressures, Ecosystem Services and Goods & Benefits are parameters; Marine Processes & Functioning is feedbacks; Activities and Responses are design, except that an Activity inside a detected feedback loop is promoted to feedbacks; Drivers are intent; Measures carries no realm. The realm column was added after García et al. (2026), and the loop-aware promotion after Geekiyanage et al. (2026) and Brons et al. (2026). This is an operationalisation motivated by those papers, not a method they publish, and the manual states it as such.

**Adjusted loop centrality (ALC)** is named after Rozhkov, Zellner and Murphy (2025). The published formula was not reachable in full, so SESPy's version is a documented reconstruction: for each element, sum the signed gain of every detected feedback loop it lies on. A positive ALC means the element mostly sits in amplifying loops and a negative one in damping loops; zero means either that it is on no loop or that its amplifying and damping loops cancel. The paper's distinction between loops an element initiates and loops it merely reinforces is not implemented. Because ALC is a sum over loops, it is hidden when the loop enumeration hit its cap.

## 31. Social-ecological fit

Fang, Wang and Duan et al. (2026) evaluate whether the pattern of governance interactions matches the pattern of ecological interactions in a watershed. SESPy takes the simplest structural reading: partition elements into social and ecological subsystems by type and report the fraction of edges that cross the boundary. A higher fit means the diagram couples the two subsystems more densely. It says nothing about whether the coupling is the right one, which is what the next two diagnostics probe.

## 32. Governance gap

Fraga, Defeo and Borthagaray et al. (2026) map governance gaps in a newly designated marine protected area by asking which ecological components no governance actor reaches. SESPy operationalises the idea as a directed coverage test. A **pressure** is covered when a governance element (Response or Measure) has a direct edge into it. The headline is the fraction of pressures left uncovered. A governance element with no directed path into the ecological subsystem at all is reported as an orphan. The test is over Pressures only because pooled or undirected variants scored a healthy demo model badly on topology alone.

## 33. Governance actor influence and concentration

Senghor and Schlüter (2026) show, for two Senegalese fisheries, how hierarchical versus distributed power among governance actors shapes outcomes. SESPy's **actor influence** table is the leverage composite of section 28 restricted to governance elements, computed on the full diagram so cross-boundary influence counts, and sorted. The **concentration** verdict summarises the spread. Influence scores are turned into shares with a softmax, then Shannon entropy (normalised by its maximum), the Gini coefficient and the dominant actor's share are reported. Heredia, Chalcobsky and Fracchia (2026, preprint) tie polycentric governance, several actors of comparable weight, to four decades of resilience at Península Valdés; the verdict sentence reads "distributed" when normalised entropy is at least 0.5 as displayed, else "concentrated in <actor>". Softmax was chosen over min-shifted normalisation because the latter pins the weakest actor's share to zero and would call every two-actor model fully concentrated.

## 34. Cascade vulnerability and the KL early warning

Liu, Li and Zhao et al. (2026) remove nodes from a land-use transition network in order of importance and show that ecological vulnerability responds non-linearly, with thresholds. SESPy removes elements in descending leverage order, up to twenty removals, and tracks, after each removal, the largest weakly connected component as a fraction of the original element count and the number of surviving feedback loops. The **cascade threshold node** is the removal that caused the largest single-step drop in connectivity. Both it and the early-warning node are chosen among the removals actually made, and the caption states how many of the elements were removed.

Kraehling (2026, preprint) proposes an earlier signal: the Kullback–Leibler divergence between successive degree distributions accelerates before connectivity collapses. SESPy computes a smoothed divergence at each step and names the **early-warning node** as the first step whose divergence exceeds twice the median of all earlier steps, with at least two earlier steps required. One limitation must be stated plainly. The rule cannot fire before step 3, and removal runs in descending leverage order, so on hub-shaped models the connectivity collapse is step 1 and the departure can only follow it. On the sample the threshold is step 1 and the departure is step 7. The panel prints both step numbers so a post-threshold departure is never mistaken for a precursor; the signal earns its name when the collapse comes late in the removal order.

## 35. Causal paths

Benito, Aguilar and Ramírez (2026) explain fuzzy cognitive maps by tracing causal chains and their temporal evolution. SESPy implements the static layer: all simple directed paths from one element to another, bounded in length and count, each annotated with its compound polarity, the product of its edge polarities. Counting positive, negative and ambiguous paths answers "how does A influence B, and do the routes agree?". The temporal layer of the paper is out of scope.

## 36. SES subsystem modules (hypermodules)

Pinheiro, Peralta and Lewinsohn (2026) formalise **hypermodules** in tripartite ecological networks: cohesive groups of species that co-cluster across two or more interlinked bipartite networks. A DAPSI(W)R(M) diagram is also multipartite, with ecological, social and governance tiers. SESPy builds the three bipartite tier-pair projections, runs community detection on each, links modules from different projections when they share hinge-tier elements, and reports each connected group of linked modules as one subsystem module whose members are the union of the linked modules' elements, together with a hypermodularity score (the share of typed elements that belong to one). The procedure is a reconstruction rather than a re-implementation: the published algorithm was not reachable in full, congruence works through hinge-tier elements because a cross-tier pair co-occurs in exactly one projection, and the threshold is size-aware because a flat threshold cannot fire on chain-shaped models. Every way a model can yield zero modules has its own explanation on screen.

## 37. Uncertainty scoring (D2D)

Uleman, Crielaard and Elsenburg et al. (2026) propose Diagrams-to-Dynamics: rather than trust one CLD, sample many plausible variants and ask which conclusions survive. SESPy's Monte Carlo option, offered on the Loop Analysis and Leverage Points panels, drops edges and flips signs at random for a chosen number of samples and recomputes. The probability that an edge is dropped, or kept but flipped, falls with its confidence: 0.5 times (5 minus confidence) over 4, so a confidence-5 edge is never perturbed and a confidence-1 edge is perturbed half the time. For each element it reports a 95% interval of the leverage score and an "unstable" flag when that interval straddles zero; for each loop it reports the probability that the loop exists at all and the probabilities of it being reinforcing or balancing, with a "contested" flag when neither dominates. Read a narrow interval as a robust conclusion and a contested loop as one whose behaviour depends on links the group is unsure about.

## 38. Loop dominance over time

Which feedback loop governs the behaviour at a given moment is the classic question of loop-dominance analysis (Ford, 1999; Schoenberg, Davidsen and Eberlein, 2020). Nguyen, Dinh and Tran (2026) and Imtihan, Edinov and Suhaemi (2026) both use shifts in loop dominance to explain transitions in qualitative CLDs. SESPy attributes activity in the linear simulation to loops: at each iteration, each loop's raw activity is the absolute product of its edge weights times the mean absolute state of its nodes, its share is that activity relative to all loops (self-loops are excluded), and the dominant loop is the one with the largest share. A dominance shift is reported when the leading loop changes and holds for several steps. The overlay is explicitly an attribution on one run from one initial state, not a proof that the loop causes the behaviour.

## 39. Token diffusion

Donlan, Arteaga-Bengoa and Carrasco (2026, preprint) evaluate interventions in small-scale fisheries by releasing tokens at an intervention node and letting them random-walk through the CLD. SESPy seeds a chosen number of tokens at one element, moves each along a random outgoing edge per step, flips its sign on a negative edge, and records per element the arrivals, the net sign and the first step of arrival. Because the counts are a random sample, SESPy computes a 95% sampling margin from batch means, draws it as error bars, groups elements whose arrivals cannot be separated into tied ranks, and prints "~" when a separate test on the signed batch means cannot tell positive from negative arrivals apart. The random stream is fixed so that two intervention points can be compared on structure.

## 40. Laplacian stability and Boolean attractors

Two views from dynamical systems, ported from the R toolbox. SESPy builds the **graph Laplacian** from the magnitudes of the weighted adjacency matrix, in the chosen direction; signs are dropped for this view but still drive the Boolean rules. Its spectrum is summarised as the spectral radius, the largest eigenvalue modulus, which bounds how fast perturbations can grow, and the algebraic connectivity, the real part of the second-smallest eigenvalue. For an undirected graph the latter is zero exactly when the graph is disconnected; for the directed Laplacian used here it is a heuristic of how well connected the diagram is. A coarse stability class is derived from both. A **Boolean network** treats each element as on or off and updates it by the sign of its weighted inputs; iterating from every one of the 2^N starting states finds the attractors, fixed points or cycles, and their basin sizes. The search is exhaustive, hence the cap of 12 elements.

## 41. Multi-rater consensus and contested edges

QSEM elicitation (Hulme, Radley and Brown, 2025) has several participants rate each connection independently. SESPy stores one rating per rater per connection, aggregates them into a consensus polarity and strength, and flags a connection as **contested** when the raters disagree on its sign. Contested edges are drawn thick with a warning marker on the diagram, propagate a warning into any loop they belong to, and are listed in their own view on the Rate Connections panel. A blind mode hides other raters' answers while a participant rates.

## 42. Stakeholder power × interest

The Stakeholders panel follows the MarineSABRES participatory-information management approach. Each stakeholder carries a power level and an interest level (Low, Medium, High); plotting them yields the four familiar engagement classes (key players to manage closely, keep satisfied, keep informed, monitor), with Medium counted on the high side of the cross-hair. Engagement activities and communications are logged by hand on the panel's own tabs; the class is a guide to what to plan, not something the panel plans for you.

---

# Part IV — References

Bibliographic details were verified against the scite index on 2026-09-05. Preprints are marked; they have not been peer reviewed.

## 43. Foundations

- Abson, D. J., Fischer, J., Leventon, J., et al. (2017). Leverage points for sustainability transformation. *Ambio*, 46(1), 30–39. https://doi.org/10.1007/s13280-016-0800-y
- Elliott, M., Burdon, D., & Atkins, J. P. (2017). "And DPSIR begat DAPSI(W)R(M)!" A unifying framework for marine environmental management. *Marine Pollution Bulletin*, 118(1–2), 27–40. https://doi.org/10.1016/j.marpolbul.2017.03.049
- Ford, D. N. (1999). A behavioral approach to feedback loop dominance analysis. *System Dynamics Review*, 15(1), 3–36. DOI `10.1002/(SICI)1099-1727(199921)15:1<3::AID-SDR159>3.0.CO;2-P` ([link](https://doi.org/10.1002/%28SICI%291099-1727%28199921%2915:1%3C3::AID-SDR159%3E3.0.CO;2-P))
- Hulme, A., Radley, D., & Brown, A. D. (2025). The Qualitative Systems Exploration Model (QSEM): A new framework to support the structural analysis of causal loop diagrams within participatory system dynamics. *System Dynamics Review*, 42(1). https://doi.org/10.1002/sdr.70015
- Kosko, B. (1986). Fuzzy cognitive maps. *International Journal of Man-Machine Studies*, 24(1), 65–75. https://doi.org/10.1016/S0020-7373(86)80040-2
- Meadows, D. H. (1999). *Leverage Points: Places to Intervene in a System*. The Sustainability Institute, Hartland, VT. (Report; no DOI.)
- Schoenberg, W., Davidsen, P. I., & Eberlein, R. L. (2020). Understanding model behavior using the Loops that Matter method. *System Dynamics Review*, 36(2), 158–190. https://doi.org/10.1002/sdr.1658
- Sterman, J. D. (2000). *Business Dynamics: Systems Thinking and Modeling for a Complex World*. Irwin/McGraw-Hill, Boston. (Book; no DOI.)
- Vester, F. (2007). *The Art of Interconnected Thinking: Ideas and Tools for a New Approach to Tackling Complexity*. MCB Verlag, Munich. (Book; no DOI.)

## 44. Literature that shaped v1.0 to v1.7

Listed by the SESPy feature each paper informed, with the release that shipped it.

- **Social-ecological fit (v1.0.0).** Fang, T., Wang, L. M., Duan, X., et al. (2026). Assessing social–ecological fit of sustained watershed environmental governance: A network-based evaluation in Dianchi Lake Watershed, China. *Environmental Impact Assessment Review*, 121, 108522. https://doi.org/10.1016/j.eiar.2026.108522
- **Signed edge weights on import (v1.0.0).** Ratnayake, S. S., Hunter, D., Reid, M., et al. (2026). Mapping the social–ecological nexus to determine system properties that maintain sustainability and productivity in village tank cascade systems of Sri Lanka. *Sustainability*, 18(12), 6151. https://doi.org/10.3390/su18126151
- **Meadows realm column (v1.0.0).** García, R. M., Amoroso, M. M., Goya, J. F., et al. (2026). How land-use scenarios shape sustainability? An indicator-based analysis to identify leverage points. *Ecological Indicators*, 188, 115042. https://doi.org/10.1016/j.ecolind.2026.115042
- **Uncertainty scoring (v1.0.0, asynchronous in v1.2.0).** Uleman, J. F., Crielaard, L., Elsenburg, L. K., et al. (2026). Diagrams-to-Dynamics (D2D): Exploring causal loop diagram leverage points under uncertainty. *BMC Medicine*, 24(1). https://doi.org/10.1186/s12916-026-04971-0
- **Governance gap (v1.4.0, issue #13).** Fraga, F., Defeo, O., Borthagaray, A. I., et al. (2026). Social–ecological network analysis of governance gaps in a newly designated marine protected area of the Global South. *Marine Policy*, 191, 107169. https://doi.org/10.1016/j.marpol.2026.107169
- **Governance actor influence (v1.4.0, #14).** Senghor, K., & Schlüter, A. (2026). Unpacking power dynamics and actor interactions across fisheries and marine protected areas governance: a comparative study of Saint Louis and Sangomar, Senegal. *Maritime Studies*, 25(3). https://doi.org/10.1007/s40152-026-00501-z
- **Cascade vulnerability (v1.4.0, #15).** Liu, X. G., Li, Z., Zhao, Y., et al. (2026). Network cascading effects reveal thresholds and nonlinearity in ecological vulnerability. *Environmental Research Letters*, 21(14), 144004. https://doi.org/10.1088/1748-9326/ae83cb
- **Causal paths (v1.4.0, #16).** Benito, D., Aguilar, J., & Ramírez, J. M. (2026). A dynamic explainability method for fuzzy cognitive maps based on causal and temporal evolution analysis. *Applied Soft Computing*, 202, 115925. https://doi.org/10.1016/j.asoc.2026.115925
- **Token diffusion (v1.4.0, #17; sampling-error handling #19 to #21).** Donlan, C. J., Arteaga-Bengoa, R., & Carrasco, S. A. (2026). A systems thinking approach to improve participatory processes in small-scale fisheries management. *Research Square* preprint. https://doi.org/10.21203/rs.3.rs-10397797/v1
- **Loop dominance over time (v1.4.0, #22).** Nguyen, H. D., Dinh, M. N., & Tran, M. T. (2026). Scaling regenerative supply chains in agriculture: An integrated framework of digital MRV, transition finance and socioecological resilience. *Systems Research and Behavioral Science*. https://doi.org/10.1002/sres.70145 — and Imtihan, I., Edinov, S., & Suhaemi, Z. (2026). Analysis of 5R waste management on green economy using causal loop diagram model in West Sumatera. *Indonesian Journal of Urban and Environmental Technology*, 9(2), 697–711. https://doi.org/10.25105/urbanenvirotech.v9i2.22457
- **Leverage depth and adjusted loop centrality (v1.5.0, #23).** Geekiyanage, D., Fernando, T., & Teixeira Fernando, L. (2026). Revealing leverage points of anticipatory action for fisheries through a systems thinking lens in developing island states. *Climate Risk Management*, 53, 100843. https://doi.org/10.1016/j.crm.2026.100843 — Brons, A., Mathijs, E., & Kiel, T. (2026). Leveraging change: a soft systems approach to transforming the EU food system. *Sustainability Science*. https://doi.org/10.1007/s11625-026-01872-2 — Rozhkov, A., Zellner, M., & Murphy, J. T. (2025). Identifying leverage points for sustainable transitions in urban–rural systems: Application of graph theory to participatory causal loop diagramming. *Environmental Science & Policy*, 164, 103996. https://doi.org/10.1016/j.envsci.2025.103996
- **SES subsystem modules (v1.6.0, #24).** Pinheiro, R. B. P., Peralta, G., & Lewinsohn, T. M. (2026). The hypermodular structure of tripartite ecological networks. *Proceedings of the Royal Society B*, 293(2077). https://doi.org/10.1098/rspb.2026.1348
- **Governance concentration (v1.6.1, corrected v1.6.2, #26).** Heredia, F., Chalcobsky, A., & Fracchia, M. (2026). Synergies in coupled human–natural systems: Forty years of evidence for biodiversity recovery and nature-based economic growth. *Research Square* preprint. https://doi.org/10.21203/rs.3.rs-10195628/v1
- **KL-divergence early warning (v1.7.0, #25).** Kraehling, Z. A. (2026). Entropy-based indicators of critical transitions in heavy-tailed networks under progressive node removal. *Research Square* preprint, v3. https://doi.org/10.21203/rs.3.rs-9204974/v3

---

# Appendix

## A. File formats

**Project file (`.json`).** Written by Save Project and read by Load Project. Top-level `elements` (list of objects with `id`, `label`, `type` and optional fields) and `connections` (list with `source`, `target`, `polarity` + or −, `strength` weak/medium/strong, `confidence` 1 to 5, `delay` immediate/short/long). Validation rejects duplicate ids, unknown element types, connections to unknown ids, self-loops and any value outside those vocabularies.

**Excel workbook (`.xlsx`, `.xls`).** Read by Import Data. A sheet named Elements with columns id, label, type and a sheet named Connections with columns source, target; optional polarity, strength, confidence, delay and a numeric weight, which is mapped to a signed strength.

**QSEM model (`.qsem`, or `.json` uploaded on the Import panel).** The node-and-link graph exported by the QSEM app; themes can be mapped to DAPSI(W)R(M) types on import.

**Exports.** Report as `.html`, `.pdf` or `.docx`; stakeholder register as `.xlsx`, `.png` or `.pdf`; Behaviour Over Time data as `.csv`.

## B. URL parameters

- `?view=<panel>` opens that panel; the value is one of the navigation ids (`pims`, `stakeholders`, `templates`, `wizard`, `entry`, `rate`, `cld`, `loops`, `metrics`, `leverage`, `quadrant`, `boolean`, `simulation`, `bot`, `intervention`, `simplify`, `import`, `recent`, `report`). The app keeps this parameter current as you navigate.
- `?lang=<code>` (or `?language=`) sets the interface language for the session: `en`, `es`, `fr`, `de`, `lt`, `pt`, `it`, `no`, `el`.

## C. Glossary

- **ALC** — adjusted loop centrality, the signed sum of loop strengths an element sits on.
- **Balancing loop** — a feedback loop with an odd number of negative links; it counteracts change.
- **CLD** — causal loop diagram.
- **Contested edge** — a connection whose raters disagree on its sign.
- **DAPSI(W)R(M)** — Drivers, Activities, Pressures, State, Impact (on Welfare), Responses (as Measures).
- **Hypermodule** — the union of community-detection modules from at least two tier-pair projections that are linked through shared elements.
- **KL divergence** — Kullback–Leibler divergence, here between successive degree distributions during node removal.
- **lccf** — largest connected component fraction, relative to the original element count.
- **Leverage score** — the sum of standardised betweenness, eigenvector and PageRank.
- **Realm** — the Meadows level (parameters, feedbacks, design, intent) an intervention at an element would act on.
- **Reinforcing loop** — a feedback loop with an even number of negative links; it amplifies change.
- **Token** — a unit of influence that random-walks through the diagram in the intervention simulation.

## D. Known limitations

- Simplify Network is a preview; it does not change the project.
- Behaviour Over Time series are session-only and not saved with the project.
- Recent Projects records the browser upload's temporary path, so entries can vanish; Save Project does not add entries.
- The Boolean attractor search is hard-capped at 12 elements. The sample has 17.
- PDF export requires WeasyPrint; HTML and Word do not.
- The report omits stakeholders, the factor quadrant, Boolean, simulation and Behaviour Over Time results, and reports loops as reinforcing or balancing only.
- The KL early-warning rule cannot fire before step 3 of the cascade, so on hub-shaped models the departure follows the threshold rather than preceding it.
- Loop-based columns (ALC, loop dominance) are hidden or caveated when the loop enumeration hit its cap.
- The hypermodule procedure is a reconstruction of the published method, not a re-implementation.
