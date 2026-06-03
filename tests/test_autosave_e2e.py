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
        await page.wait_for_timeout(1500)

        # Edit Data → add an element to trigger isa_change
        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(1500)
        await page.fill("#entry-new_label", "Autosave test element")
        await page.click("#entry-add_element")
        await page.wait_for_timeout(2000)

        # Indicator should appear
        indicator_text = await page.evaluate(
            "() => document.querySelector('.sespy-autosave-indicator')?.textContent || ''"
        )
        print(f"indicator: {indicator_text!r}")
        assert "Auto-saved" in indicator_text, \
            f"autosave indicator not visible: {indicator_text!r}"

        # File should exist on disk with the new element
        path = autosave_path()
        assert path.exists(), f"autosave file not written at {path}"
        text = path.read_text(encoding="utf-8")
        assert "Autosave test element" in text, \
            "autosave file doesn't contain the just-added element"
        print(f"autosave file: {path} ({path.stat().st_size} bytes)")

        await page.screenshot(path="tests/screenshots/autosave.png")
        print("\nautosave e2e assertions pass")
        await browser.close()


asyncio.run(main())
