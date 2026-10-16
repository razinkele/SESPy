"""E2E for autosave isolation (port of R 1.20.1 N7).

Each browser has a private token in localStorage; autosave is stored under
it. Browser A's edit is autosaved to A's file, a second browser (fresh
context = fresh localStorage) is never offered A's work, and A itself is
offered recovery when it comes back.
"""
import asyncio
import sys
from pathlib import Path

# Make the repo root importable when this script is run standalone
# (e.g. `python tests/test_autosave_e2e.py`) without requiring
# PYTHONPATH=. in the caller's environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

from sespy.autosave import autosave_path, clear_autosave

URL = "http://127.0.0.1:8000"
TOKEN_JS = "() => window.localStorage.getItem('sespy_browser_token')"
RECOVERY = "#shiny-notification-autosave-recovery"


async def open_app(context):
    page = await context.new_page()
    await page.set_viewport_size({"width": 1280, "height": 900})
    await page.goto(URL, wait_until="networkidle")
    # The nav is a @render.ui output (dashboard.py sespy_nav_render): it
    # exists only after the session's first flush, and this script runs
    # first, against a just-booted server — the coldest session of the run.
    await page.wait_for_selector("#sespy_nav_entry", timeout=60000)
    return page


async def wait_token(page) -> str:
    for _ in range(40):          # up to 20 s
        token = await page.evaluate(TOKEN_JS)
        if token:
            return token
        await page.wait_for_timeout(500)
    raise AssertionError("browser token never appeared in localStorage")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ---- Browser A edits; the autosave lands in A's own file ----------
        ctx_a = await browser.new_context()
        page = await open_app(ctx_a)
        token_a = await wait_token(page)
        clear_autosave(token=token_a)          # clean slate for this token

        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(1500)
        await page.fill("#entry-new_label", "Autosave test element")
        await page.click("#entry-add_element")

        indicator = ""
        for _ in range(60):          # up to 30 s
            indicator = await page.evaluate(
                "() => document.querySelector('.sespy-autosave-indicator')?.textContent || ''"
            )
            if "Auto-saved" in indicator:
                break
            await page.wait_for_timeout(500)
        print(f"indicator: {indicator!r}")
        assert "Auto-saved" in indicator, f"autosave indicator not visible: {indicator!r}"

        # save_project_atomic uses os.replace, which can momentarily make the
        # path unreadable, so poll and guard the read.
        path = autosave_path(token_a)
        text = ""
        for _ in range(60):          # up to 30 s
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    text = ""
                if "Autosave test element" in text:
                    break
            await page.wait_for_timeout(500)
        assert "Autosave test element" in text, \
            f"autosave for browser A not written at {path}"
        assert token_a not in str(path), "autosave file name leaks the raw token"
        print(f"autosave file: {path.name} ({path.stat().st_size} bytes)")
        await page.screenshot(path="tests/screenshots/autosave.png")

        # ---- Browser B (fresh localStorage) is never offered A's work ------
        ctx_b = await browser.new_context()
        page_b = await open_app(ctx_b)
        token_b = await wait_token(page_b)
        assert token_b != token_a, "two browser contexts got the same token"
        await page_b.wait_for_timeout(5000)    # recovery check runs on token arrival
        offered_b = await page_b.locator(RECOVERY).count()
        assert offered_b == 0, "browser B was offered another browser's autosave"
        print("browser B: no recovery offer (isolated)")
        await ctx_b.close()

        # ---- Browser A returns and is offered its own work ----------------
        page_a2 = await open_app(ctx_a)
        assert await wait_token(page_a2) == token_a, "token did not persist"
        await page_a2.wait_for_selector(RECOVERY, timeout=30000)
        print("browser A: recovery offered on return")

        clear_autosave(token=token_a)
        await browser.close()
        print("\nautosave e2e assertions pass")


asyncio.run(main())
