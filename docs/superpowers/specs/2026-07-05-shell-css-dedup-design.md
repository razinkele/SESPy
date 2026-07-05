# Shell CSS de-duplication — design

**Date:** 2026-07-05
**Status:** approved (brainstorming)
**Scope:** SESPy `sespy` package + both apps' `www/`. Affects how BOTH SESPy and MosaicSES load the shared shell stylesheets.

## Problem

The shared shell (`sespy/dashboard.py`) injects three stylesheets by relative
href — `sespy-skin.css`, `cld.css`, `themes.css` — resolved against **each app's
own** `static_assets` `www/` directory. So every app that uses the shell keeps
its **own copy** of these files. Consequences observed today:

- The copies have drifted. SESPy's `sespy-skin.css` (871 lines) is a superset;
  MosaicSES's (817 lines) still has the **old** `.sespy-topbar` styling while the
  shared `dashboard.py` now emits the newer `.sespy-titlebar` markup — so
  MosaicSES's title bar is **already mis-styled**.
- `themes.css` exists in SESPy's `www/` but is **missing** from MosaicSES's, so
  MosaicSES links a 404 and its `deep-ocean` dark theme does not work.
- The network-spinner feature (shipped 2026-07-05) had to be manually mirrored
  into both copies — the drift is an active maintenance footgun.

Verified: MosaicSES's skin is a strict **stale subset** of SESPy's — the only
selector unique to it is `.sespy-topbar` (the pre-rename name), and it has zero
mosaic/topology/compartment-specific rules. There is no legitimate app-specific
CSS to preserve; SESPy's versions are cleanly the source of truth. The three CSS
files reference no local `url()` assets (only a Google-Fonts `@import`), so they
are self-contained and safe to relocate.

## Goal

One source of truth: the shell owns its shared CSS as **package data** in the
`sespy` package and serves it via an `HTMLDependency`, so both apps get the
identical current file from the installed package. Delete the per-app copies.
Future shell-CSS changes ship to every app automatically.

Non-goals (YAGNI): an app-specific-override layer (no app needs one today; an app
can add its own `<link>` later), bundling the Google-Fonts import locally,
reconciling the stale `sespy.__version__` (0.0.1) with pyproject (1.2.0).

## Approach

Follow the pattern the bundled `pyvis.shiny` fork already uses for its own
assets (`pyvis/shiny/wrapper.py`): an `htmltools.HTMLDependency` whose `source`
subdir is resolved from `__file__`.

### Components

1. **`sespy/www/`** — new package directory holding the three canonical files,
   seeded from SESPy's current `www/` (the source of truth):
   `sespy-skin.css`, `cld.css`, `themes.css`.

2. **`sespy/dashboard.py`** — replace the three
   `ui.tags.link(rel="stylesheet", href="…")` calls in the `ui.head_content(…)`
   block with a single dependency, keeping the **same load order** (skin → cld →
   themes, so themes can override):

   ```python
   from pathlib import Path
   from htmltools import HTMLDependency
   from sespy import __version__ as _SESPY_VERSION

   _SKIN_DEP = HTMLDependency(
       name="sespy-shell-skin",
       version=_SESPY_VERSION,               # cache key; bump __version__ to bust
       source={"subdir": str(Path(__file__).parent / "www")},
       stylesheet=[
           {"href": "sespy-skin.css"},
           {"href": "cld.css"},
           {"href": "themes.css"},
       ],
   )
   ```

   Include `_SKIN_DEP` in `head_content` where the three `<link>`s were. The
   Font-Awesome CDN `<link>` stays untouched (external).

3. **`pyproject.toml`** — add `"www/*.css"` to `[tool.setuptools.package-data]`
   `sespy = [...]` so wheels/sdists ship the files. (The editable install already
   reads them from the source tree.)

4. **Delete** the now-redundant copies:
   - `SESPy/www/sespy-skin.css`, `SESPy/www/cld.css`, `SESPy/www/themes.css`
   - `MosaicSES/www/sespy-skin.css`, `MosaicSES/www/cld.css`
   Both apps keep `static_assets=str(WWW)` pointing at their (now-empty of these)
   `www/` — harmless, and leaves room for future app-specific static assets.

### Why not the alternatives

- **Symlink / build-copy**: brittle on Windows/OneDrive, and a copy step is the
  same "remember to sync" footgun we are removing. Rejected.
- **Inline `<style>`**: ~30 KB inlined per page, loses browser caching,
  complicates the font `@import`. Rejected.

## Consequences (intended)

- **MosaicSES gains** working `themes.css` (deep-ocean dark theme) and the current
  `.sespy-titlebar` / feedback-table styling — a visible fix of its currently
  broken theme and mis-styled title bar.
- No app-visible change for SESPy (it already had all three current files).
- Adding/editing shell CSS now touches exactly one place.

## Error handling / robustness

- **Cache-busting** is the `HTMLDependency` `version` (`sespy.__version__`).
  Because `__version__` changes rarely, a CSS edit without a version bump can be
  served stale from browser cache until a hard refresh. Accept for a dev tool;
  bump `sespy.__version__` when a CSS change must reach users immediately. (A
  content-hash version is a possible future hardening — out of scope.)
- **Editable vs wheel:** editable install serves from the source tree
  immediately; `package-data` covers the wheel/sdist path. Both correct.
- **`@import` Google Fonts** inside `sespy-skin.css` is browser-resolved
  regardless of how the CSS is served — unaffected.
- **Load order** preserved (skin, cld, themes) so cascade/override behavior is
  identical to today.
- **No circular import:** `sespy/__init__.py` only defines `__version__` (no
  imports), so `from sespy import __version__` inside `sespy/dashboard.py` is
  safe (verified).

## Testing

- **Both apps boot** and the skin applies: assert a known rule resolves, e.g.
  `getComputedStyle(document.querySelector('.pyvis-network-output')).position ===
  'relative'` and the spinner `::before` content is `"Rendering network…"`.
- **MosaicSES dark theme now works:** set `data-theme="deep-ocean"`, assert
  `document.body` background is the dark navy (was a no-op before, themes.css
  404'd).
- **MosaicSES title bar styled:** `.sespy-titlebar` rules now apply (was stale).
- **Dependency serves the CSS:** the shell page loads without a 404 for the
  skin/cld/themes; HTTP 200 on the dependency-scoped URLs.
- **No regression:** SESPy full e2e suite (`tests/run_e2e.py`) stays green; the
  network-spinner CLD e2e still passes (CSS now from the package).
- Manual smoke: both apps visually unchanged for SESPy; MosaicSES title bar +
  dark theme now render correctly.

## Files touched

- Create: `sespy/www/sespy-skin.css`, `sespy/www/cld.css`, `sespy/www/themes.css`
  (git-moved from `SESPy/www/`).
- Modify: `sespy/dashboard.py` (dependency instead of 3 links), `pyproject.toml`
  (package-data).
- Delete: `SESPy/www/{sespy-skin,cld,themes}.css`,
  `MosaicSES/www/{sespy-skin,cld}.css`.

## Cross-repo note

MosaicSES is a SEPARATE git repo; deleting its two CSS files is a MosaicSES-repo
change (its own branch/PR). SESPy CI does not load MosaicSES, so MosaicSES must be
smoke-tested manually (boot it, confirm skin + dark theme + spinner render from
the package).
