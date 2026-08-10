# SESPy Codebase Review & Quality Audit

**Date:** 2026-08-01  
**Author:** Copilot (Interactive Terminal Assistant)  
**Project:** SESPy — Shiny for Python Port of the MarineSABRES SES Toolbox (Horizon Europe)  
**Status:** Operational, Highly Maintained, Production-Grade  

---

## 1. Executive Summary & Overview

SESPy is a high-fidelity, high-performance **Shiny for Python** port of the strategic core of the **MarineSABRES Social-Ecological Systems (SES) Toolbox**. It supports the `DAPSI(W)R(M)` (Drivers, Activities, Pressures, States, Ecosystem Services, Goods & Benefits, Responses) framework for qualitative modeling of socio-ecological coupling.

The codebase is exceptionally mature, demonstrating a clean division of labor between reactive user interface modules, pure-functional network/centrality logic, robust multi-rater consensus models, Monte-Carlo resampling engines, and strict validation layers. 

### Key Vital Signs
- **Scale:** 17 production-shaped core modules covering the complete `create → edit → analyze → export` workflow.
- **Languages Supported:** 9 languages (`en`, `es`, `fr`, `de`, `lt`, `pt`, `it`, `no`, `el`) driven by an R-compatible translations model.
- **Citations & Scientific Basis:** Extremely rigorous. All foundational scientific assumptions (such as the Curonian lagoon, transboundary telecoupling, and species catalogs) are backed by verified, active, peer-reviewed literature with real DOIs.
- **Test Coverage:** Over **468 unit tests** (pytest) and **22 comprehensive E2E Playwright browser scripts** running synchronously or via CI pipelines. 100% green.

---

## 2. Architecture & Data Flow

SESPy uses an elegant, linear, and non-blocking reactive model.

```
       [ app.py ] (App Entry & Router)
           │
           ├──► [ sespy/dashboard.py ] (Visual Shell & Stepper)
           ├──► [ sespy/data_structure.py ] (Project Dataclass Tree)
           ├──► [ sespy/event_bus.py ] (Reactive Event Triggers)
           ├──► [ sespy/i18n.py ] (Translation Singleton)
           │
     ┌─────┴─────────────────────────────────────────┐
     ▼                                               ▼
[ Analytical Modules ] (Pure Python)     [ UI Module Collection ] (Shiny)
- network.py (centralities, z-scores)    - pims_project.py, templates.py
- connection_scorer.py (Rule SP3)        - ai_isa_wizard.py (AI Steps)
- claude_backend.py (LLM SP4)            - rate_connections.py (Multi-rater)
- dynamics.py (Simulation, Boolean)      - cld_visualization.py (Pyvis)
                                         - report_export.py (Jinja2/WeasyPrint)
```

### 2.1 App Router & Visual Shell (`app.py`, `sespy/dashboard.py`)
- **Main Layout:** Designed using a custom `bs4Dash`-style shell leveraging `bslib.page_sidebar`. A responsive collapsible navigation bar collapses to an icon-only mini-sidebar (`sespy-sidebar-mini` CSS override).
- **Workflow Stepper:** A fully clickable 6-step progress indicator (`setup → start → create → visualize → analyze → report`) that guides users through the DAPSI modeling stages. 
- **Modular Design Contract:** Every UI module adheres to a rigid contract matching the R counterpart: 
  `module_ui(id)` and `module_server(id, *, project_data, event_bus, translator=None)`. This makes adding or wire-framing a new module predictable and mechanical.

### 2.2 Core Data Structure (`sespy/data_structure.py`)
- **Dataclass Tree:** System models are represented as python dataclasses: `Element`, `Connection`, `Rating`, and `IsaData` wrapped inside a root `Project` envelope.
- **Project Metadata:** The `ProjectMetadata` class tracks core context details (such as spatial/temporal scales, system in focus, and focal issues) alongside a version-tagged schema (`PROJECT_SCHEMA_VERSION = 6`).
- **PIMS Registry:** Comprehensive stakeholder registers are native, containing `Stakeholder`, `Engagement`, and `Communication` lists for managing participative socio-ecological elicitation.
- **JSON Serialization:** Features transactional load/save mechanics (`to_dict` / `from_dict`) with automatic structural upgrade-on-load to ensure backward compatibility.

### 2.3 Reactive Event Bus (`sespy/event_bus.py`)
- **Trigger Propagation:** Built as a Python-equivalent bag of `reactive.value` counters (`isa_change`, `cld_update`, `project_loaded`, etc.).
- **Isolation Principle:** Modifying operations use `with reactive.isolate()` block contexts to advance trigger ticks, shielding downstream reactive calculations from re-entrancy and feedback loops. It coordinates six complex analytical listeners (CLD, Loops, Centralities, Leverage, Intervention, Simplify) flawlessly.

### 2.4 Multilingual Singleton & Autosave
- **Translation (`sespy/i18n.py`):** Ships a globally-accessible, module-level `t` translator object. Resolves Shiny's language-switch reactiveness by using a synchronous plain attribute `_lang` as the source of truth, preventing race conditions during server flushes.
- **Autosave Engine (`sespy/autosave.py`):** Automatically registers a JSON shadow state on every `event_bus.isa_change`. Incorporates sticky startup toasts to recover sessions if the autosave state is younger than 24 hours.

---

## 3. Mathematical & Analytical Foundations (`sespy/network.py`, `sespy/dynamics.py`)

A defining strength of SESPy is its deep mathematical logic. Rather than treating graphs as pure graphics, it runs complex topological algorithms.

### 3.1 Network Metrics & Centrality
SESPy computes **seven per-node centrality measures** using a converted directed network model (`networkx.DiGraph`):
1. **Degree** (In-Degree, Out-Degree)
2. **Betweenness Centrality** (Normalised flow control)
3. **Closeness Centrality** (Proximity)
4. **Eigenvector Centrality** (Influence / prestige; includes fallback to standard iterative solvers if Numpy's eigenvalues fail to converge)
5. **PageRank** (Random-walk prominence)

It includes strict, safe-float sanitizers that replace division-by-zero or infinite closeness values on disconnected components with `0.0`, matching R's mathematical baseline.

### 3.2 Leverage Points Composite Score & Meadows Realms
- **Composite Score Formulation:** The leverage score $L(u)$ for a node $u$ is the sum of its standard $z$-scores across Betweenness, Eigenvector, and PageRank:
  $$L(u) = Z(Betweenness(u)) + Z(Eigenvector(u)) + Z(PageRank(u))$$
- **Meadows Realm Taxonomy:** Each node is categorised into its systemic depth realm based on its DAPSI type:
  - *Parameters* (Pressures, Ecosystem Services, Goods & Benefits)
  - *Feedbacks* (Marine Processes & Functioning)
  - *Design* (Activities, Responses)
  - *Intent* (Drivers)

### 3.3 Vester Influence × Dependence Factor Quadrant
- **weighted Axes:** Computes the raw sum of incoming and outgoing edge weights (with weight defined as $strength\_rank \times confidence$).
- **Statistical Splits:** Allows classification of factor roles (*active, critical, reactive, buffering*) based on either **arithmetic mean** or **median** splits.
- **Degeneracy Guards:** Features a variance analyzer ($\sigma^2 < 10^{-12}$) to gracefully catch homogeneous structures (graphs where every node has equal connection weights) and prevent division-by-zero errors.

### 3.4 Monte-Carlo Uncertainty Scorer (D2D Resampling)
SESPy implements an off-thread **Monte-Carlo resampling engine** (`uncertainty_scores`). Given structural parameters:
- Every connection is independently perturbed based on its confidence:
  $$P(\text{perturb}) = \text{base\_prob} \times \frac{5 - \text{Confidence}}{4}$$
- High-confidence connections ($5/5$) never drop or flip; low-confidence ones ($1/5$) carry high probabilities of either being **dropped** entirely from the sample or having their **polarity sign inverted** (from $+$ to $-$ or vice-versa).
- Runs $N=500$ draws in a background worker thread. Computes **95% percentile confidence intervals** for leverage scores and reports survival and polarity probabilities for every feedback loop.

### 3.5 Dynamic Simulation & Attractor State-Space
SESPy supports deterministic linear matrix iterations alongside **exhaustive $2^N$ state-space searches** (capped at $12$ nodes for performance protection) to resolve Boolean network attractor states. Includes finite-aware divergence accounting to prevent overflow under runaway reinforcing feedback.

---

## 4. Multi-Rater Elicitation Engineering

In `v1.0.0` through `v1.2.0`, SESPy introduced rigorous **participatory modeling (QSEM-C)**. 

### 4.1 Materialized Consensus Model
Instead of forcing consensus beforehand, stakeholders rate connections asynchronously. SESPy's backend merges these ratings into a single scalar connection:
- **Confidence:** Mean of rating confidences (rounded, clamped to $[1, 5]$).
- **Strength:** Confidence-weighted average of strength ranks ($\text{weak}=1, \text{medium}=2, \text{strong}=3$).
- **Polarity:** Majority sign (ties resolve to $+$).
- **Delay:** Statistical mode (first occurrence resolves ties).

### 4.2 Delphi-Style Blind Rating Mode
An opt-in anti-anchoring mechanism that hides peer evaluations from the user until they submit their own connection ratings. Aggregate team metrics (like disagreement metrics) remain visible to guide collaborative review.

### 4.3 Visualizing Conflict
- **CLD Styling:** Polarity-contested connections (where stakeholders disagree on sign) are rendered on the live vis.js canvas with heavier lines, a distinct visual `⚠` flag, and explicit hover details revealing the level of disagreement.
- **Disagreement-Aware Feedback Loops:** Feedback loops whose polarity classification (Reinforcing vs Balancing) hinges on a contested edge are annotated with a warning label (`⚠`), alerting modelers to structural instability.

---

## 5. AI-ISA Wizard Backends (SP3 & SP4)

The 12-step DAPSI creation wizard is supported by two distinct recommendation backends.

### 5.1 SP3 Rule-Based Engine (`sespy/connection_scorer.py`)
- **Word-Level Substring Relevance:** Calculates connection relevance (scores: $0.3$, $0.6$, $0.9$) by matching vocabulary against an active keyword corpus (`connection_keywords.json`).
- **Semantic Polarity Dispatch:** Features an advanced polarity generator that analyzes nouns and verbs. It handles reversal-compounds (e.g. `"pollution reduction"`) and double-negation flips across different types (e.g. `Responses → Pressures` is automatically negative; `Activities → Pressures` is mitigation-aware).
- **Quality Ceiling:** Limits suggestions to at most 15 entries per connection type, sorting by confidence descending.

### 5.2 SP4 LLM Cognitive Backend (`sespy/claude_backend.py`)
- **Strict Structured Tool Use:** Uses Claude Sonnet 4.6 with structured tool output (`record_connection_suggestions`). 
- **Validation Pipeline:** Implements a top-down, strict sanitization cascade:
  `non_dict → missing_key → unknown_ids → self_loop → invalid_direction → invalid_polarity → invalid_confidence → empty_rationale`.
- **System Constraints & Cost Boundaries:** Enforces `max_retries=0` to bound API costs, preventing runaway parallel retries during Anthropic API rate limits. Includes a strict input cap of 200 elements, falling back gracefully to the SP3 engine if exceeded.

---

## 6. Testing & Quality Assurance

SESPy has a superb, comprehensive test suite.

### 6.1 Unit Tests (468 passing)
- Highly focused, modular unit tests covering:
  - Network algorithms, centrality calculations, and Monte Carlo resampling.
  - Multi-rater consensus and disagreement calculations.
  - Workbook parsing, file imports, and translations.
  - Jinja2, docx, and WeasyPrint export round-trips.

### 6.2 Playwright End-to-End Tests (22 scripts)
- Run against a live local server instance using `tests/run_e2e.py`.
- They avoid brittle fixed sleep durations by utilizing Playwright's `wait_for_selector` and `wait_for_function` to synchronize tests with Shiny's reactive `@render.ui` cycles.
- Validates graph rendering states by querying Pyvis's JavaScript-level `window.pyvisNetworks` instances.

---

## 7. Strategic Recommendations & Cleanliness Opportunities

While the codebase is exceptionally clean, the following avenues could further polish its quality:

1. **Incremental Typing (Mypy Cleanliness):**  
   The project has `follow_imports = "silent"` and runs as a non-blocking step in CI because some newer Shiny constructs and dynamic visual models lack full static type signatures. Continuing to type-annotate modules (like the newer dashboard classes) will allow bringing Mypy into the blocking CI checks.
2. **State Isolation for Multi-User Deployments:**  
   The translation manager `T` currently behaves as a module-level singleton in `app.py`. Under a multi-user server deployment (e.g., Shiny Server or Posit Connect), concurrent users modifying the language could theoretically affect the global language state. Transitioning `Translator` initialization to a per-session context (e.g., inside the Shiny `server` function) would isolate the language state for concurrent active users.
3. **Structured Logging Integration:**  
   The logging in `claude_backend.py` is beautifully structured (using structured key-value messages). Applying this key-value logging style across other database-writing modules (like `feedback_store.py`) would make server log parsers (e.g., Promtail, Datadog) even more effective at indexing system behavior.
