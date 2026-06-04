# SESPy Spec Corpus — Deep Review (design + scientific validation)

Date: 2026-06-04
Method: 16-agent design-review workflow (one reviewer per spec + synthesis) **plus**
a literature-validation pass through the scite MCP for the scientific spec.
Scope: all 15 specs in `docs/superpowers/specs/`.

---

## Executive summary

The corpus is healthy. The shipped SESPy core specs (Boolean/Simulation, BOT, PIMS,
Wizard SP1–SP3, SP4) are solid and largely accurate against the live code; the
scientific spec is **exceptionally well-cited** (15/15 DOI-bearing citations verified
real, correctly attributed, unretracted, and claim-supporting). The two systemic issues
are (1) **stale "Draft — not yet implemented" status** on already-shipped specs (SP3,
SP4) and (2) **codebase-drift / unverifiable premises in the MosaicSES `multises/`
family**, whose target tree is absent from this checkout. The single most actionable
finding is a **real technical-correctness defect in the brand-new url-bookmarking spec**
(language-restore-via-effect yields a half-translated page; cross-session singleton
translator) — it must be revised before implementation.

---

## Part A — Scientific validation (scite MCP, in-loop, main session)

Validated every DOI-bearing citation in `2026-05-09-mosaicses-scientific-basis.md`.
Each was fetched from scite; existence, attribution, retraction status (editorial
notices), and claim-support were checked. Links: `https://doi.org/<doi>`.

**Result: 15/15 confirmed real, correctly attributed, not retracted, claim-supported.**

| Claim (spec) | Citation | Verdict |
|---|---|---|
| 108 transboundary transitional waters worldwide; Cooperation/Confrontation Index | Povilanskas & Razinkovas-Baziukas 2023, `10.3390/su15139922` | ✅ **verbatim** ("There are 108 transboundary TW (TTW) worldwide") |
| DAPSI(W)R(M) nested/interlinked framework; Responses-as-Measures | Elliott, Burdon & Atkins 2017, `10.1016/j.marpolbul.2017.03.049` | ✅ abstract confirms nested framework |
| "Butterfly" model (State split; supply/demand) | Elliott & O'Higgins 2020, `10.1007/978-3-030-45843-0_4` | ✅ confirmed |
| "Triple whammy" coastal climate+tourism+governance | Polette, Tischer & Elliott 2026, `10.1016/j.ocecoaman.2025.108018` | ✅ real (2026) |
| Arctic nested DAPSI(W)R(M) | Lovecraft & Meek 2019, `10.1016/b978-0-12-814003-1.00039-3` | ✅ confirmed |
| Modes of marine-fish ingress (microtidal↔macrotidal) | Whitfield, Potter & Neira 2023, `10.1111/faf.12745` | ✅ confirmed |
| Ems nursery; P→S→I cascade | Tulp, Chen & Vrooman 2022, `10.18174/583972` | ✅ confirmed |
| <1 km² lagoons as nurseries (blackfin seabass) | Murase et al. 2025, `10.1111/maec.70031` | ✅ real — but **3rd author is Ikehara, not "Mukai"** |
| Estuary weir fragments fish assemblages | Park, Riedel & Ju 2020, `10.3390/jmse8070496` | ✅ confirmed |
| Diel ichthyoplankton recruitment | Bruno, Delpiani & Eduardo 2018, `10.1016/j.ecss.2018.03.015` | ✅ confirmed |
| Otolith Sr/Ca compartment-crossing (Mugil curema) | Avigliano, Ibáñez & Fabré 2021, `10.1002/aqc.3486` | ✅ confirmed |
| Fish-fauna response to hydraulic intervention (Marchica) | Selfati 2023, `10.21608/ejabf.2023.291755` | ✅ real — **record shows a single author; verify "et al."** |
| Curonian eutrophication / cyanobacterial hyperblooms / hypoxia | Aleksandrov, Krek & Bubnova 2018, `10.5200/baltica.2018.31.01` | ✅ confirmed |
| Curonian–Baltic nutrient exchange 2001–2020 | Stakėnienė, Jokšas & Kriaučiūnienė 2023, `10.3390/w15234096` | ✅ confirmed |
| Upwelling Chl-a reduction at Curonian mouth | Dabulevičienė, Vaičiūtė & Kozlov 2020, `10.3390/rs12213661` | ✅ confirmed (see nit) |

**Scientific nits to fix in the spec:**
1. **Murase et al. 2025** — third author should be **Ikehara**, not "Mukai".
2. **Selfati 2023** — scite shows a single author; verify the "et al."
3. **`cci_index (0–10)`** — the source reports an index on a different scale (ICC ≈ 0.7 for the Curonian); note that 0–10 is an operationalization.
4. **Dabulevičienė "inverts the gradient"** — the abstract states upwelling *reduces* Curonian Chl-a; the "inversion" framing is defensible but slightly beyond the abstract — soften or cite the body.
5. **No-DOI citations not independently verifiable here:** Lonsdale et al. 2018, Liu et al. 2013 (has DOI in design doc: `10.5751/es-05873-180226`), Vybernaite-Lubiene 2017, Sosnina 2024, Cheung 2025, Bresciani 2012, Pilkaitytė & Razinkovas 2006, Krevš 2007 — add DOIs.

**Partially validated (the larger corpus):** the companion `mosaicses-design.md` and `scientific-basis.md` contain ~60+ further citations (connectivity theory, telecoupling, Curonian biogeochemistry, ~14 AphiaIDs, and SP4's Anthropic-SDK claims). The 15 foundational DOI'd citations (Part A) and the **AphiaIDs (validated 2026-06-04** via `migratory_species_catalog`: all 12 diadromous IDs match the catalogue; **`126279` is European sturgeon *Acipenser sturio*, NOT an eel-like typo — the earlier flag was a false positive**; `101174` is sea lamprey; minor: §9.5 had mis-grouped the 4 marine-estuarine IDs under the catalogue and omitted Vendace `127178` — now corrected). Still to do: the remaining ~45 DOI'd/no-DOI citations across both docs.

---

## Part B — Multi-agent design review (15 specs)

The following is the synthesized output of the per-spec reviewer agents (verbatim,
lightly formatted). Findings about the **url-bookmarking** spec and the stale-status
issues are the immediately actionable ones.

<!-- BEGIN workflow synthesis -->
[See the workflow result appended below — Critical / Important / Minor / Corpus-wide
patterns / Scientific claims flagged for validation.]
### Critical
- **chunk4c** — target app (`multises_app/` topology/cross_view/comparative, `output_pyvis_network`, named tests) absent from the repo; `git ls-files | grep multises` returns nothing → resolve where MosaicSES lives; do not implement against this checkout.
- **chunk4c** — "chunk-4b shipped to origin/main" unverifiable; base commits `80d0100`/`27e3476` are not valid git objects here → re-confirm base or flag dependency unmet.
- **url-bookmarking** — `set_language(lang)` in a reactive effect only re-renders `@render.ui`; static UI captures language at construction → `?lang=es` opens a half-translated app → apply `?lang` at construction (reuse `detect_initial_language`) or reload.

### Important
- **pims-project-setup** — stepper list is `STEPPER` in app.py:96-103 (not dashboard.py); shipped order is setup→start→create→visualize→analyze→report → fix attribution + order.
- **sp3** — marked "Draft — not yet implemented" but fully implemented (46 tests); `_CONN_TYPES` lives in data_structure.py (imported), not connection_scorer.py → flip status; fix location.
- **sp4** — marked "Draft" but `claude_backend.py`, wizard sum-type/observer/consent, pyproject deps all exist → reconcile to Implemented; convert §12 to a verification checklist.
- **mosaicses-design** — `with_compartment_replaced` called but never defined; generic `<module>_ui` wrong for CLD (actual `cld_viz_ui`/`cld_viz_server`) → define method; explicit symbol table.
- **chunk4a** — multises tree + commit `80d0100`/"241 tests" unverifiable; hard line anchors will rot; single global `window.__mosaicses_get_cross_view_network` accessor risks the wrong pyvis Network → state where tree lives; symbol anchors; per-canvas accessor.
- **chunk4b** — §7 R9 claims a `_module_decorator`/keyword-only-`state` test that is infeasible and not what §8 tests → rewrite R9 to match the runnable §8 test.
- **url-bookmarking** — `parse_bookmark` reinvents lang parsing (ignores tested `detect_initial_language`, which handles `?lang`/`?language`); no `www/*.js` files exist (burger is inline `ui.tags.script`, no `addCustomMessageHandler` precedent); translator `T` is a cross-session singleton → shared `?lang` flips all sessions → reuse detect_initial_language; follow the real inline-script pattern; scope language to construction / document single-user.
- **chunk4c** — moving the `dirty_hint` aria-live region into the collapsible sidebar may make screen readers miss "dirty" announcements while collapsed → keep aria-live outside the collapsible sidebar.
- **burger-js-fix** — built on the false premise "SESPy is not a git repository"; claims test_burger.py is a manual gate though it's in `_EXTRA_SERVER_SCRIPTS` (runs in CI); mandates adding `.tmp/` to .gitignore (already there) → delete git-init section; correct CI framing; drop no-op edit.

### Corpus-wide patterns
- Stale "Draft — not yet implemented" footers on shipped specs (SP3, SP4, MosaicSES).
- MosaicSES codebase-drift: `multises/`+`multises_app/` tree, commits, and test baselines absent from this checkout — every MosaicSES spec must name its target repo/worktree.
- Hard `file.py:NN-MM` anchors that rot — prefer symbol-name anchors / probe-backed assertions.
- Stale test/module/LOC counts — annotate as-of-commit or gate on "0 FAILED + N new".
- `package-data` glob under-specification (subdir JSON missed by top-level `*.json`).
- i18n static-UI-vs-reload model + cross-session singleton translator (the url-bookmarking trap).
- Falsy-guard misuse (`confidence or 3` corrupts a legitimate 0) — use `x if x is not None else default`.
- pyvis multi-network global-accessor / full-screen sizing hazards (chunk4a, chunk4c).

### Also produced (not inlined)
- ~50 **Minor** findings (per-spec wording/anchor/count nits) — in the workflow run output.
- A **~60-citation scientific-validation backlog** across both MosaicSES docs (connectivity theory, telecoupling, Curonian biogeochemistry, ~14 AphiaID→species resolutions for the ICES/WoRMS MCP, SP4 Anthropic-SDK claims). The 15 foundational citations in Part A are validated; the rest is the recommended follow-up.
<!-- END workflow synthesis -->

---

## Part C — Prioritized actions

**Do before implementing url-bookmarking (the active feature):**
1. **Language restore is broken as designed.** `set_language()` in a reactive effect only
   re-renders `@render.ui` content; static UI (panel bodies, module labels, the switcher's
   own value) captures language at construction → `?lang=es` opens a half-translated app.
   Fix: apply `?lang` at **construction time** (reuse the existing, unit-tested
   `detect_initial_language` in `sespy/i18n.py:150-168`, which already handles `?lang`/
   `?language`), or trigger a client reload after setting it. Do **not** restore language
   via an effect.
2. **Cross-session singleton translator.** `T` is module-level (app.py:66-69) and shared
   across sessions → a shared `?lang=es` link flips language for *all* concurrent users.
   Scope language to construction time, or document the single-user assumption + per-session
   translator prerequisite.
3. **Reuse `detect_initial_language`** instead of inventing `parse_bookmark` lang parsing;
   decide whether `?language` (alias) is honored.
4. **No `www/*.js` pattern exists.** The burger toggle is an inline `ui.tags.script` in
   `head_content`; there is no `addCustomMessageHandler`/`send_custom_message` precedent.
   Either follow the inline-script pattern or wire a real `www` file via `ui.tags.script(src=)`
   and `static_assets`; drop the "same as the existing JS/pyvis bridge" claim.
5. Minor: `send_custom_message` is async (use an async effect); define whether
   `build_bookmark` emits default-valued params; clarify the read-effect's dependency.

→ **The `view` half of the design is sound; the `lang` half needs the rework above.**
Recommend revising the spec (re-run brainstorming on the language mechanism) before plan.

**Quick metadata fixes (low effort, high clarity):**
- Flip SP3 and SP4 status footers from "Draft — not yet implemented" to **Implemented**
  (both are shipped, in CI). A planner trusting the footer would redo work.
- PIMS spec: stepper list lives in `app.py:96-103` (`STEPPER`), not dashboard.py; correct
  the stage order to `setup→start→create→visualize→analyze→report`.
- SP3: `_CONN_TYPES` lives in `data_structure.py` (imported by scorer), not connection_scorer.py.

**MosaicSES family (4a/4b/4c + parent design):**
- The `multises/`/`multises_app/` tree, prerequisite commits (`80d0100`,`27e3476`), and
  test baselines are **absent from this checkout**. Before any MosaicSES spec can be planned,
  state which repo/worktree it targets. Replace hard line-number anchors with symbol-name
  anchors. Resolve `with_compartment_replaced` (undefined) and the `cld_viz_ui` naming.

**Corpus-wide hygiene:**
- Reconcile status footers at merge time; annotate test/module/LOC counts as as-of-commit
  or gate on "0 FAILED + N new"; prefer symbol anchors over line numbers; treat
  subdirectory `package-data` JSON as a standard checklist item; standardize
  `x if x is not None else default` over `x or default` for the float→int confidence work.
