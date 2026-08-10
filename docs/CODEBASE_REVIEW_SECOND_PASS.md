# SESPy Codebase Review (Second Pass)

**Date:** 2026-08-01  
**Scope:** Current `main` working tree with focus on post-hardening regressions and remaining reliability gaps.

## Outcome

The codebase remains stable after recent changes, and the test baseline is green:

- `pytest -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py`
- Result: **474 passed, 1 skipped**

Previously implemented hardening (session-scoped translator retrieval, structured logging in persistence paths, safer PDF dependency handling, and confidence-default fixes in key paths) is present and consistent.

## High-priority findings

### 1) Language bootstrap/persistence path is incomplete

**Files:** `sespy/i18n.py`, `sespy/dashboard.py`, `app.py`  

- `detect_initial_language()` exists but is not used anywhere.
- The code comments describe reload-based handling for static UI strings, but there is no active reload path when language changes.
- Because much of the shell is built statically at app construction time, language switching updates some reactive labels but not all chrome labels consistently.

**Impact:** Inconsistent i18n behavior and user confusion in multilingual sessions.

## Medium-priority findings

### 2) Silent failure paths remain in autosave/save flow

**Files:** `sespy/autosave.py`, `sespy/modules/project_io.py`

- `clear_autosave()` logs errors but suppresses them.
- `quick_actions_server()` has several broad `except Exception: pass` paths around autosave and recent-project updates.

**Impact:** Operational failures can go unnoticed by users and operators, making support/debugging harder.

### 3) Inconsistent fallback style still exists in UI-input numeric defaults

**Files:** `sespy/modules/rate_connections.py`, `sespy/modules/analysis_bot.py`

- Remaining patterns like `int(input.ed_confidence() or 3)` and `int(input.window_size() or 3)` are still present.
- Earlier fixes replaced this pattern in other modules to avoid falsy-value coercion side effects.

**Impact:** Low current risk (input controls constrain values), but inconsistent and easy to regress later.

## Low-priority findings

### 4) Broad catch blocks in core analytics intentionally degrade to zeros, but without observability

**File:** `sespy/network.py`

- Centrality computations catch broad exceptions and return fallback zeros.
- This preserves UX robustness, but there is no warning-level telemetry for unexpected algorithm/runtime failures.

**Impact:** Hidden quality degradation in analysis results when backend numeric failures occur.

## Recommended action plan

1. Wire session-start language initialization explicitly (query param + session translator clone), and define one consistent policy for static-label updates (reload or full reactive rendering).
2. Replace silent `except ...: pass` in autosave/save flows with user-facing notifications plus structured warning logs.
3. Normalize remaining `or <default>` numeric fallback patterns to explicit `None`/empty checks.
4. Add warning logs to analytics fallback branches in `network.py` so fallback-to-zero events are observable.
