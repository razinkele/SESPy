# MosaicSES Scenario Studio — Sidecar Load/Save + Drift Banner (Chunk 2) Design

**Status:** Reviewed 2026-08-27 against the code as it then stood — every load-bearing claim re-verified (see §14). Chunk 2 of the Scenario Studio deferred follow-ups (hardening ✓ → **sidecar load/save** → sign engine). Ready for an implementation plan; two decisions are flagged in §14.

**Parent:** `2026-06-13-mosaicses-scenario-studio-design.md` (structural core) + `2026-06-14-mosaicses-scenario-studio-hardening-design.md` (Chunk 1, shipped `f7a2237`).

## 1. Purpose

The Scenario Studio authors scenarios in-session but cannot persist them — close the tab and the work is gone. The library persistence shipped in the core (`save_scenario_set` / `load_scenario_set`), but no UI reaches it, the `drift_banner` only surfaces dangling-target warnings (Chunk 1), and `scenario_name` is one-shot. This chunk adds the in-app save/load file flow, finishes the live name edit, and makes the banner also flag *baseline drift* (a scenario loaded onto a different project than it was authored against).

Scope decision (approved): **minimal save/load + a selector for multi-scenario loads** — not a full "scenario library" with accumulate/rename/delete (deferred). Upload loads a set and activates its first member.

**Amended 2026-08-29 (finding M1).** Download originally saved *only* the active scenario. Shipping the feature showed that to be lossy in the one case the selector exists for: open a 3-scenario file, edit, save, and the other two members are silently gone. Download now preserves the whole loaded set, substituting the active scenario's edited version for its stored one. A freshly authored scenario, which belongs to no loaded set, still downloads as a one-member set. This does not reopen the deferred "scenario library" scope — there is still no accumulate, rename or delete of *saved* scenarios; it only stops save from destroying what open just read.

## 2. Scope

In scope: a `scenario_set_to_json` library helper; download/upload UI mirroring `project_setup.py`; a scenario selector for multi-scenario loads; live `scenario_name` editing; baseline-drift in the `drift_banner`; recording `baseline_name` at scenario creation.

Out of scope (later): accumulating multiple authored scenarios into one file before download; rename/delete of saved scenarios; the sign-propagation engine (Chunk 3).

## 3. Component ① — Library JSON serialization

**File:** `multises/scenario.py`.

`save_scenario_set` writes to a path, but the browser download flow needs the JSON *bytes*. Mirror `MultiSES.to_json` / `MultiSES.save`:
- Add `scenario_set_to_json(scenario_set: ScenarioSet) -> str` returning `json.dumps(asdict(scenario_set), indent=2, ensure_ascii=False)`.
- `save_scenario_set` already delegates to `_atomic_write_bytes`; the only change is lifting its `json.dumps(...)` line into `scenario_set_to_json` and calling that instead — behaviour-preserving, and smaller than a first reading of this section suggests.
- Upload reuses the shipped `load_scenario_set(path)` directly (an uploaded file is a datapath). Reconstruction runs each `Intervention.__post_init__`, so a tampered/invalid uploaded scenario raises `ScenarioError` (incl. Chunk 1's `S004`) at load — caught by the UI boundary (§5).

Re-export `scenario_set_to_json` from `multises/__init__.py` alongside the existing scenario API.

**Tests** (`tests/test_scenario.py`): `scenario_set_to_json(ss)` round-trips via `load_scenario_set` (write the string to a tmp file, load, assert equal interventions/metadata); the JSON is valid UTF-8 with `indent=2`.

## 4. Component ② — Record baseline at creation

**File:** `multises_app/modules/scenario_view.py`.

For drift detection to mean anything, an authored scenario must remember which baseline it was built on. In `_add`, when creating the first `Scenario`, set `baseline_name=state.active_multises.get().metadata.name` (currently defaults to `""`). Authored scenarios then show no drift against their own project; loaded scenarios show drift when the current project differs.

## 5. Component ③ — Save / Load UI

**File:** `multises_app/modules/scenario_view.py` (sidebar), mirroring `project_setup.py`.

- **Sidebar additions:** `ui.download_button("download_scenarios", "Save (download .json)")` and `ui.input_file("upload_scenarios", "Open .scenarios.json", accept=[".json"], multiple=False)`.
- **Download** (`@render.download(filename=lambda: f"…-{ts}.scenarios.json")`): build the payload with the pure helper `_active_scenario_set(active, ss)`, passing `state.scenario_set.get()` as `ss`. **When the active scenario is a member of `ss`, the payload is the WHOLE set** with the active member replaced by its current edited version, order preserved, keeping the set's own `metadata.name`. When it is not a member (a freshly authored scenario) or `ss` is absent, fall back to the one-member wrap named after the active scenario. The member substitution is exactly what `_replace_in_set` already does — and its returning the input object unchanged is the "not a member" signal. This works because `state.scenario_set` is kept current: `_add` and `_rename` both write edits back through `_replace_in_set`, so no new syncing is needed. The borrowed set-name in the fallback stays cosmetic, since a one-member set has no other name to carry; `yield scenario_set_to_json(ss).encode("utf-8")`. If `active_scenario` is None, yield an empty-set JSON (nothing authored yet). Timestamp read in the render function, not in a pure helper: the `filename=` lambda may call `datetime.now()` directly, exactly as `project_setup.py:256` does. The rule is that pure/testable helpers take a timestamp as an argument — it does not forbid the renderer from reading the clock.
- **Upload** (`@reactive.effect` on `input.upload_scenarios`): read `finfo[0]["datapath"]`, call `load_scenario_set(path)` inside a broad `try` (mirrors `project_setup._apply_open` — untrusted-file boundary: on any exception, `_log.exception` + `friendly_error` toast, leave state untouched). On success: `state.scenario_set.set(loaded)`; if `loaded.scenarios`, `state.active_scenario.set(loaded.scenarios[0])` and `state.dirty.set(True)`.

## 6. Component ④ — Scenario selector

**File:** `multises_app/modules/scenario_view.py`.

- A `ui.output_ui("scenario_picker")` in the sidebar renders an `ui.input_select("pick_scenario", …)` **only when** `scenario_set` holds ≥2 scenarios (choices = `{scenario.id: scenario.name}`), defaulting to the active scenario's id; otherwise renders nothing (single/zero-scenario loads auto-activate, no clutter).
- A `@reactive.effect @reactive.event(input.pick_scenario)` sets `active_scenario` to the chosen scenario from `scenario_set`.

## 7. Component ⑤ — Live name editing

**File:** `multises_app/modules/scenario_view.py`.

Replace Chunk 1's relabel-only fix: a `@reactive.effect` on `input.scenario_name` that, when an `active_scenario` exists and the trimmed name differs, applies `dataclasses.replace(active_scenario, name=…)` and re-sets it. The name now round-trips through save and shows in the selector, so live editing is meaningful. (Guard against the no-op churn of re-setting an identical name.)

## 8. Component ⑥ — Baseline-drift in the banner

**File:** `multises_app/modules/scenario_view.py`.

Extend the Chunk 1 `drift_banner` (which renders `report.warnings`). Compute the drift line via a **pure helper** `_baseline_drift(active: Scenario | None, current_name: str) -> str | None` (returns the warning text or `None`): drift when `active` exists, `active.baseline_name` is non-empty, and it differs from `current_name` — text "⚠ This scenario was authored against baseline '{authored}'; the current project is '{current}'. Targets may not resolve." `drift_banner` calls `_baseline_drift(active_scenario.get(), active_multises.get().metadata.name)` and renders: the drift line (if any) **and** the W501 warning list (if any); stays inert when neither applies. Drift is informational — the scenario still materialises (unresolved targets become the W501 warnings already surfaced). The pure helper makes the predicate unit-testable without a Shiny harness.

## 9. Data flow

Author → `_add` stamps `baseline_name` → `active_scenario`. **Save:** download serializes `[active_scenario]` via `scenario_set_to_json`. **Load:** `input_file` → `load_scenario_set` (validates each intervention) → `scenario_set` + activate first → selector switches among them → drift banner flags a baseline mismatch. The five diff cards and the W501 surfacing (Chunk 1) are unchanged.

## 10. Error handling

- Upload is an untrusted-file boundary: broad `except` → `_log.exception` + `friendly_error` toast → state untouched (mirrors `project_setup`). Invalid values in an uploaded scenario raise `ScenarioError` (S004) at `load_scenario_set` and are caught here.
- Download with no active scenario yields a valid empty-set JSON (no crash).
- Live-name and selector effects guard against missing `active_scenario` / `scenario_set`.

## 11. Testing

- **Unit** (`test_scenario.py`): `scenario_set_to_json` round-trips through `load_scenario_set`; an uploaded set with a bad channel_type raises `ScenarioError` at load.
- **Module** (`test_scenario_view_logic.py` — the file exists; use it): the upload→activate selection logic and the drift predicate (a helper `_baseline_drift(active, current_name) -> str|None` extracted pure for testability).
- **E2e** (`test_scenario_e2e.py`): the Save download button is present and the Open file input renders; (drift banner visibility is covered at the module/pure-helper level, since driving a file upload + project swap in Playwright is high-cost — note the carve-out).

## 12. Build order

① serialization (library) → ② baseline stamp → ⑤ live name + ⑥ drift predicate (pure helper) → ③ save/load UI → ④ selector. Each is independently testable; ③/④/⑤/⑥ touch `scenario_view.py` in disjoint regions.

## 13. Risks

- **Download bytes vs path:** mitigated by `scenario_set_to_json` (no temp file); `save_scenario_set` keeps its path API for headless callers.
- **Upload of a foreign/old scenario file:** handled by the untrusted-boundary except + per-intervention validation at load.
- **Selector churn:** only render it for ≥2 scenarios; guard the effect against re-activating the already-active id.
- **E2e cost of file flows:** covered by pure-helper/module tests for the logic; the e2e asserts only the controls render.

---

## 14. Review findings (2026-08-27)

**Superseded in part on 2026-08-29:** §2 and §5 were amended after implementation — download now preserves the whole loaded set (finding M1 from the final whole-branch review). See those sections. The two decisions below stand as recorded.

Re-verified against the code: `state.scenario_set` / `active_scenario` / `dirty`
(`state.py:48-50`), `Intervention.__post_init__` validation incl. S004
(`scenario.py:66-99`), `load_scenario_set` field round-trip (`scenario.py:169-189`),
the `project_setup.py` download/upload pattern (`:107, :111, :256, :272, :283`),
`friendly_error`, and the Chunk-1 `drift_banner`. Nothing had drifted; §§3, 5, 11
were corrected for accuracy rather than design.

### Decision A — `created_at` / `modified_at` (must resolve before building)

`Scenario` declares both (`scenario.py:111-112`) and `load_scenario_set` round-trips
them, but **nothing in the codebase ever writes either one** — they are always `""`.
This chunk is where that starts to show: the fields ship inside every downloaded
file, so today's design would emit scenario files with empty timestamps. §7's rename
also does `replace(sc, name=…)` without touching `modified_at`, so a renamed scenario
would misreport when it changed even if the field were populated.

**Recommended (assumed unless overridden): stamp them.** Set `created_at` in `_add`
when the first `Scenario` is constructed, and `modified_at` in `_add` and in the
rename effect, using `datetime.now(timezone.utc).isoformat(timespec="seconds")` —
the same call and format `project_setup.py:52` already uses for project metadata.
Stamping is additive and reversible; the alternative (dropping the fields) is a
schema change requiring a `SCENARIO_SCHEMA_VERSION` bump and a migration path for
any file already written, which is strictly more invasive for a field that costs
one line to populate.

### Decision F — `state.dirty` is becoming overloaded (flagged, not solved here)

`dirty` gates the "Discard unsaved changes?" prompt (`project_setup.py:307, 331`)
and is cleared when the **project** is saved (`:267`). `_add` already sets it for
scenario authoring, and §5 has upload set it too — so this chunk is consistent with
shipped behaviour rather than introducing the problem.

The problem it *does* make consequential: one flag now means both "the project has
unsaved edits" and "scenario work is unpersisted". A user can save the project, watch
the warning clear, and still lose an unsaved scenario. Before this chunk that could
not happen, because scenarios could not be persisted at all.

The clean fix is a separate `scenario_dirty` flag with its own prompt, which is its
own change and explicitly **not** in scope here. Implementers should keep the current
behaviour and not extend `dirty`'s meaning further.
