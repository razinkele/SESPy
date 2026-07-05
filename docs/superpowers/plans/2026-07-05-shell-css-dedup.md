# Shell CSS De-duplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `sespy` package the single source of the shell's shared CSS (`sespy-skin.css`, `cld.css`, `themes.css`), served via one `HTMLDependency`, so both SESPy and MosaicSES get the identical current file and the per-app copies (and their drift) go away.

**Architecture:** Move the three CSS files into `sespy/www/` (package data). `sespy/dashboard.py` serves them with an `htmltools.HTMLDependency` (`source={"subdir": <sespy/www>}`, `stylesheet=[…]`) in `head_content`, replacing three per-app `ui.tags.link` hrefs — same load order (skin → cld → themes). Delete the app-level copies. This follows the pattern the bundled `pyvis.shiny` fork already uses for its own assets.

**Tech Stack:** Python Shiny, `htmltools` (`HTMLDependency`), setuptools package-data, Playwright e2e via `tests/run_e2e.py`.

## Global Constraints

- Python env: run everything through `micromamba run -n shiny …`. No venvs, no `pip install`.
- Source of truth = SESPy's CURRENT `www/*.css` (superset). MosaicSES's stale/missing copies are discarded, not merged.
- Stylesheet load order MUST stay `sespy-skin.css` → `cld.css` → `themes.css` (themes overrides).
- `HTMLDependency` `version` = `sespy.__version__` (currently `"0.0.1"`). `from sespy import __version__` (or `from . import __version__`) is safe — `sespy/__init__.py` has no imports (no circular import).
- Keep the Font-Awesome CDN `<link>` and the `network_spinner_js` / `burger_js` / `bookmark_js` / `theme_js` scripts exactly as-is.
- Both apps keep `static_assets=str(WWW)` (now empty of these files — harmless).
- ruff is blocking in CI; keep `ruff check` clean.
- MosaicSES is a SEPARATE git repo — its file deletions are committed there and verified by manually booting that app (SESPy CI does not load it).

---

## File Structure

- `sespy/www/{sespy-skin,cld,themes}.css` — NEW package dir; the canonical shared CSS (git-moved from `SESPy/www/`).
- `sespy/dashboard.py` — module-level `_SKIN_DEP = HTMLDependency(...)`; include it in `head_content` where the 3 links were. New imports: `Path`, `HTMLDependency`, `__version__`.
- `pyproject.toml` — add `"www/*.css"` to `[tool.setuptools.package-data].sespy`.
- `tests/test_shell_skin_e2e.py` — NEW characterization e2e: the shell skin is served and applied (guards the refactor).
- Deleted: `SESPy/www/{sespy-skin,cld,themes}.css`, `MosaicSES/www/{sespy-skin,cld}.css`.

---

## Task 1: Characterization e2e — the shell skin is served & applied

Locks current behavior BEFORE refactoring: a skin-provided computed style must resolve. Passes on current `main` (CSS via `www` link); Task 2 keeps it green from the package.

**Files:**
- Create: `tests/test_shell_skin_e2e.py`

**Interfaces:**
- Produces: a CI-gated e2e (auto-discovered by `run_e2e.py`'s `test_*_e2e.py` glob) asserting `.pyvis-network-output` computed `position === "relative"` (from `sespy-skin.css`), the spinner `::before` resolves (from `sespy-skin.css`), and the `deep-ocean` theme changes `body` background (from `themes.css`).

- [ ] **Step 1: Write the test**

```python
"""E2E: the shell skin (sespy-skin.css + themes.css) is served and applied."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#cld-network", timeout=30000)

        # 1) sespy-skin.css guard: .pyvis-network-output is positioned.
        pos = await page.evaluate(
            "() => getComputedStyle(document.querySelector('.pyvis-network-output')).position"
        )
        print("pyvis-network-output position:", pos)
        assert pos == "relative", f"skin not applied (position={pos!r}) — sespy-skin.css not served?"

        # 2) sespy-skin.css spinner: forcing is-loading resolves the ::before label.
        content = await page.evaluate(
            "() => { const el = document.querySelector('.pyvis-network-output');"
            " el.classList.add('is-loading');"
            " return getComputedStyle(el, '::before').content; }"
        )
        print("spinner ::before content:", content)
        assert "Rendering network" in content, f"spinner rule missing (content={content!r})"

        # 3) themes.css: deep-ocean flips the body background to the dark navy.
        bg = await page.evaluate(
            "() => { document.documentElement.setAttribute('data-theme', 'deep-ocean');"
            " return getComputedStyle(document.body).backgroundColor; }"
        )
        print("deep-ocean body bg:", bg)
        assert bg == "rgb(11, 31, 51)", f"themes.css not applied (bg={bg!r})"

        print("\nshell skin e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run it against current main to confirm it passes (characterization)**

```bash
cd "/c/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy"
micromamba run -n shiny shiny run --port 8000 app.py &   # wait until :8000 serves
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_shell_skin_e2e.py
```

Expected: PASS — prints `shell skin e2e assertions pass`. (This documents current behavior; the CSS is still served via the `www` link at this point.)

- [ ] **Step 3: Lint + commit**

```bash
micromamba run -n shiny ruff check tests
git add tests/test_shell_skin_e2e.py
git commit -m "test(e2e): characterize that the shell skin (skin+themes) is served and applied"
```

---

## Task 2: Move CSS into the package + serve via HTMLDependency (SESPy)

**Files:**
- Create: `sespy/www/{sespy-skin,cld,themes}.css` (git-moved)
- Modify: `sespy/dashboard.py`, `pyproject.toml`
- Delete: `www/{sespy-skin,cld,themes}.css`

**Interfaces:**
- Consumes: the Task 1 e2e (must stay green).
- Produces: `sespy/dashboard.py` module-level `_SKIN_DEP` (an `HTMLDependency`) included in `head_content`.

- [ ] **Step 1: Git-move the three CSS files into the package**

```bash
mkdir -p sespy/www
git mv www/sespy-skin.css sespy/www/sespy-skin.css
git mv www/cld.css        sespy/www/cld.css
git mv www/themes.css     sespy/www/themes.css
# www/ is now empty; keep the dir tracked so app.py's static_assets=str(WWW)
# still resolves on a fresh checkout (room for future app-specific assets).
touch www/.gitkeep
git add www/.gitkeep
```

- [ ] **Step 2: Remove the three `<link>`s WITHOUT wiring the dependency yet (prove the test has teeth)** — in `sespy/dashboard.py`, delete these three lines from the `ui.head_content(…)` block:

```python
            ui.tags.link(rel="stylesheet", href="sespy-skin.css"),
            ui.tags.link(rel="stylesheet", href="cld.css"),
            ui.tags.link(rel="stylesheet", href="themes.css"),
```

- [ ] **Step 3: Run the characterization e2e — expect it to FAIL**

```bash
# restart the app so the change is served, wait for :8000, then:
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_shell_skin_e2e.py
```

Expected: FAIL at `assert pos == "relative"` (skin no longer served). This proves the test guards the refactor.

- [ ] **Step 4: Add the imports** — in `sespy/dashboard.py`, change `from htmltools import Tag` to:

```python
from pathlib import Path

from htmltools import HTMLDependency, Tag
```

and, with the other package imports (e.g. next to `from .i18n import Translator`), add:

```python
from . import __version__ as _SESPY_VERSION
```

- [ ] **Step 5: Define the dependency** — in `sespy/dashboard.py`, add a module-level constant after the `STEP_INPUT_PREFIX = …` constants block (near the top, before the `@dataclass`):

```python
# Shared shell stylesheets, served from the package so every app that uses the
# shell gets the identical current file (no per-app www/ copies to drift). Load
# order matters: skin defines tokens/guards, cld layers on it, themes overrides.
_SKIN_DEP = HTMLDependency(
    name="sespy-shell-skin",
    version=_SESPY_VERSION,
    source={"subdir": str(Path(__file__).parent / "www")},
    stylesheet=[
        {"href": "sespy-skin.css"},
        {"href": "cld.css"},
        {"href": "themes.css"},
    ],
)
```

- [ ] **Step 6: Include the dependency in the head** — in the `ui.head_content(…)` block, put `_SKIN_DEP` where the three links were (before the Font-Awesome link):

```python
        ui.head_content(
            _SKIN_DEP,
            # Font Awesome — needed for the icons in NavItem entries
            ui.tags.link(
                rel="stylesheet",
                href=("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/"
                      "6.5.0/css/all.min.css"),
            ),
            burger_js,
            bookmark_js,
            theme_js,
            network_spinner_js,
        ),
```

- [ ] **Step 7: Run the characterization e2e — expect PASS**

```bash
# restart app, wait for :8000, then:
PYTHONPATH="$PWD" micromamba run -n shiny python tests/test_shell_skin_e2e.py
```

Expected: PASS — `shell skin e2e assertions pass`. The CSS is now served from `sespy/www/` via the dependency.

- [ ] **Step 8: Add package-data** — in `pyproject.toml`, change:

```toml
[tool.setuptools.package-data]
sespy = ["*.json", "translations/*.json", "templates/*.json"]
```

to:

```toml
[tool.setuptools.package-data]
sespy = ["*.json", "translations/*.json", "templates/*.json", "www/*.css"]
```

- [ ] **Step 9: Confirm no stray references to the old www CSS paths remain**

```bash
grep -rnE "www/(sespy-skin|cld|themes)\.css|href=\"(sespy-skin|cld|themes)\.css\"" sespy app.py || echo "no stray refs"
```

Expected: `no stray refs`.

- [ ] **Step 10: Full regression — lint, unit, e2e**

```bash
micromamba run -n shiny ruff check sespy tests app.py
micromamba run -n shiny python -m pytest tests --ignore-glob="*_e2e.py" \
  --ignore=tests/test_burger.py --ignore=tests/test_stepper.py \
  --ignore=tests/test_stepper_click.py -q -p no:cacheprovider
# then the full e2e (boots its own server; stop any app on :8000 first):
micromamba run -n shiny python tests/run_e2e.py --port 8000
```

Expected: ruff clean; unit `474 passed, 1 skipped`; e2e all pass except the known
pre-existing `test_report_e2e.py` PDF/WeasyPrint local-env flake (retry-passes → runner exit 0). The new `test_shell_skin_e2e.py` passes.

- [ ] **Step 11: Commit**

```bash
git add sespy/www sespy/dashboard.py pyproject.toml www
git commit -m "refactor(shell): serve shared CSS from the sespy package via HTMLDependency

Move sespy-skin/cld/themes.css into sespy/www/ (package data) and serve them with
one HTMLDependency from dashboard.py, replacing the three per-app www/ <link>s.
Single source of truth for every app that uses the shell — no more drift."
```

---

## Task 3: Delete MosaicSES's stale copies + verify the fix (MosaicSES repo)

MosaicSES gets the CSS from the `sespy` package now; its own copies are stale (and it was missing `themes.css`). Deleting them makes the package the sole source and fixes its broken dark theme + title bar.

**Files (in `../MosaicSES`):**
- Delete: `www/sespy-skin.css`, `www/cld.css`

**Interfaces:**
- Consumes: the packaged `_SKIN_DEP` from Task 2 (shipped via the editable `sespy` install).

- [ ] **Step 1: Delete the stale copies**

```bash
cd "/c/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES"
git rm www/sespy-skin.css www/cld.css
# www/ is now empty; keep it tracked so static_assets=str(WWW) still resolves.
touch www/.gitkeep
git add www/.gitkeep
```

- [ ] **Step 2: Boot MosaicSES and verify skin + dark theme now come from the package**

```bash
micromamba run -n shiny shiny run --port 8001 app.py &   # wait until :8001 serves
```

Then run this check (writes no repo files):

```bash
PYTHONPATH="$PWD" micromamba run -n shiny python - <<'PY'
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8001", wait_until="networkidle")
        await pg.wait_for_selector("#topology-network", timeout=40000)
        pos = await pg.evaluate("() => getComputedStyle(document.querySelector('.pyvis-network-output')).position")
        bg = await pg.evaluate("() => { document.documentElement.setAttribute('data-theme','deep-ocean'); return getComputedStyle(document.body).backgroundColor; }")
        print("position:", pos, "| deep-ocean bg:", bg)
        assert pos == "relative", "skin not served from package"
        assert bg == "rgb(11, 31, 51)", "themes.css still not applied (dark theme broken)"
        print("MosaicSES skin+theme from package: OK")
        await b.close()
asyncio.run(main())
PY
```

Expected: `position: relative | deep-ocean bg: rgb(11, 31, 51)` and `MosaicSES skin+theme from package: OK`. (Before this change the dark-theme assertion would fail — themes.css was 404.)

- [ ] **Step 3: Stop the app and commit (MosaicSES repo)**

```bash
git add -A
git commit -m "chore: drop local shell CSS copies; use sespy package's shared skin

The sespy shell now serves sespy-skin/cld/themes.css as package data via an
HTMLDependency (razinkele/SESPy), so MosaicSES no longer needs (stale) local
copies. This also restores the deep-ocean dark theme, which was 404ing because
MosaicSES never had themes.css."
```

---

## Notes for the implementer

- `Path(__file__).parent / "www"` resolves to `sespy/www/` because `__file__` is
  `sespy/dashboard.py`. The editable install reads it from the source tree; the
  `package-data` entry covers wheels/sdists.
- Do NOT touch either app's `app.py` — `static_assets=str(WWW)` still points at
  the (now-empty-of-these) app `www/`, which is harmless.
- Cache-busting is the dependency `version` (`sespy.__version__ == "0.0.1"`).
  It changes rarely, so during dev a CSS edit may need a hard refresh; bump
  `sespy/__init__.py`'s `__version__` when a change must reach users.
- The `@import url('…fonts.googleapis.com…')` at the top of `sespy-skin.css` is
  browser-resolved and unaffected by the move.
- MosaicSES has no CI — Task 3's browser check IS its verification; keep it.
