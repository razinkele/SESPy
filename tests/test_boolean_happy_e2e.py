"""E2E for the Boolean / Laplacian module — happy path.

Companion to ``tests/test_boolean_e2e.py``. The default 17-node sample exceeds
the 12-node Boolean attractor cap, so that test only exercises the warning
branch. This test loads the ``Minimal Demo`` 5-node template (which is below
the cap) and verifies that the attractor table renders with at least one row
end-to-end:
  - Eigenvalue plot still renders.
  - Stability summary populates.
  - Boolean tab shows a populated ``<table>`` (no warning, no danger alert).
"""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        # --- Step 1: load the Minimal Demo template via the Templates panel.
        await page.wait_for_selector("#sespy_nav_templates", timeout=15000)
        await page.click("#sespy_nav_templates")
        await page.wait_for_timeout(2500)

        # Locate the Minimal Demo card by name and click its Load button.
        # Templates are alphabetically sorted; index isn't load-bearing here —
        # find the card by header text and click the button beside it.
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        print("templates listed:", cards)
        assert "Minimal Demo" in cards, \
            f"Minimal Demo template missing from list: {cards}"
        minimal_idx = cards.index("Minimal Demo")
        load_btn = f"#templates-load_template_{minimal_idx}"
        await page.click(load_btn)
        await page.wait_for_timeout(2500)

        # --- Step 2: run the Boolean analysis on the loaded 5-node SES.
        await page.click("#sespy_nav_boolean")
        await page.wait_for_timeout(1500)

        await page.click("#boolean-run_boolean")
        await page.wait_for_timeout(3000)

        # Eigenvalue plot rendered (img tag inside the plot output)
        plot_visible = await page.evaluate(
            "() => !!document.querySelector('#boolean-eigenvalue_plot img')"
        )
        print(f"eigenvalue plot rendered: {plot_visible}")
        assert plot_visible, "eigenvalue plot did not render"

        # Stability summary populated
        n_dt = await page.evaluate(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length"
        )
        print(f"stability summary <dt> count: {n_dt}")
        assert n_dt >= 3, f"expected stability summary with >=3 fields, got {n_dt}"

        # Switch to Boolean attractors tab
        await page.click("text=Boolean attractors")
        await page.wait_for_timeout(1500)

        # No too-large warning — we're below the 12-node cap.
        warning_count = await page.evaluate(
            "() => document.querySelectorAll('#boolean-attractor_panel .alert-warning').length"
        )
        print(f"alert-warning count (should be 0): {warning_count}")
        assert warning_count == 0, \
            "unexpected too-large warning on a 5-node network"

        # No danger alert anywhere on the page.
        danger_count = await page.evaluate(
            "() => document.querySelectorAll('.alert-danger').length"
        )
        print(f"alert-danger count: {danger_count}")
        assert danger_count == 0, f"unexpected error alert(s) present: {danger_count}"

        # Attractor table populated.
        n_rows = await page.evaluate(
            "() => document.querySelectorAll("
            "  '#boolean-attractor_panel table tbody tr'"
            ").length"
        )
        print(f"attractor table rows: {n_rows}")
        assert n_rows >= 1, \
            f"expected >=1 attractor row in table, got {n_rows}"

        await page.screenshot(path="tests/screenshots/boolean_happy.png")
        print("\nboolean happy-path e2e assertions pass")
        await browser.close()


asyncio.run(main())
