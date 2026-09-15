"""E2E for autosave: indicator appears after a data edit, autosave file
ends up on disk."""
import asyncio
import sys
from pathlib import Path

# Make the repo root importable when this script is run standalone
# (e.g. `python tests/test_autosave_e2e.py`) without requiring
# PYTHONPATH=. in the caller's environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

from sespy.autosave import autosave_path, clear_autosave


async def main():
    # Clean slate — remove any leftover autosave from a previous run so
    # the recovery toast doesn't fire and pollute the test.
    clear_autosave()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # The nav is a @render.ui output (dashboard.py sespy_nav_render): it
        # exists only after the session's first flush, and this script runs
        # first, against a just-booted server — the coldest session of the run.
        # run_e2e.py's readiness check is an HTTP 200, which does not cover it.
        await page.wait_for_selector("#sespy_nav_entry", timeout=60000)
        await page.wait_for_timeout(1500)

        # Edit Data → add an element to trigger isa_change
        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(1500)

        # The autosave effect also runs once at session start (project_io.py
        # `_autosave_on_change` is a bare @reactive.effect, no ignore_init), so the
        # indicator already reads "Auto-saved · HH:MM:SS" before any edit. Wait for
        # that baseline and capture it, so the assertion below proves THIS edit saved.
        await page.wait_for_selector(
            ".sespy-autosave-indicator", state="attached", timeout=60000
        )
        indicator_before = await page.evaluate(
            "() => document.querySelector('.sespy-autosave-indicator')?.textContent || ''"
        )

        await page.fill("#entry-new_label", "Autosave test element")
        await page.click("#entry-add_element")

        # Indicator must refresh with a NEW timestamp for this edit
        indicator_text = ""
        for _ in range(60):          # up to 30 s
            indicator_text = await page.evaluate(
                "() => document.querySelector('.sespy-autosave-indicator')?.textContent || ''"
            )
            if "Auto-saved" in indicator_text and indicator_text != indicator_before:
                break
            await page.wait_for_timeout(500)
        print(f"indicator: {indicator_text!r} (was {indicator_before!r})")
        assert "Auto-saved" in indicator_text, \
            f"autosave indicator not visible: {indicator_text!r}"
        assert indicator_text != indicator_before, \
            f"autosave indicator did not refresh after the edit: {indicator_text!r}"

        # File should exist on disk with the new element. The server writes it
        # inside the isa_change effect, and the session-start autosave already
        # created the file with seed data — so poll for the content instead of
        # reading once. read_text is guarded because save_project_atomic uses
        # os.replace, which can momentarily make the path unreadable.
        path = autosave_path()
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
        assert path.exists(), f"autosave file not written at {path}"
        assert "Autosave test element" in text, \
            "autosave file doesn't contain the just-added element"
        print(f"autosave file: {path} ({path.stat().st_size} bytes)")

        await page.screenshot(path="tests/screenshots/autosave.png")
        print("\nautosave e2e assertions pass")
        await browser.close()


asyncio.run(main())
