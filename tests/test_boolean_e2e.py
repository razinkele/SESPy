"""E2E for the Boolean / Laplacian module.

Default sample SES has 17 nodes, which exceeds the Boolean attractor search
cap (12). This test verifies the module handles that path gracefully:
  - Laplacian eigenvalue plot still renders.
  - Stability summary populates.
  - Boolean tab shows the "Use Simplify Network" warning, not a crash.
  - No error alert (alert-danger) appears anywhere — the cap is a *warning*
    (alert-warning), not an error.

The happy path (attractor table populates) is covered by 5 unit tests in
tests/test_dynamics.py against small synthetic networks. This e2e covers the
wire-up and the too-large code branch — the two things unit tests can't reach.
"""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await page.wait_for_selector("#sespy_nav_boolean", timeout=15000)
        await page.click("#sespy_nav_boolean")
        await page.wait_for_timeout(1500)

        # Run analysis
        await page.click("#boolean-run_boolean")
        await page.wait_for_timeout(3000)

        # Eigenvalue plot rendered (img tag inside the plot output)
        plot_visible = await page.evaluate(
            "() => !!document.querySelector('#boolean-eigenvalue_plot img')"
        )
        print(f"eigenvalue plot rendered: {plot_visible}")
        assert plot_visible, "eigenvalue plot did not render"

        # Stability summary populated (a <dl> with at least 3 dt/dd pairs)
        n_dt = await page.evaluate(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length"
        )
        print(f"stability summary <dt> count: {n_dt}")
        assert n_dt >= 3, f"expected stability summary with >=3 fields, got {n_dt}"

        # Switch to the Boolean attractors tab
        await page.click("text=Boolean attractors")
        await page.wait_for_timeout(1500)

        # On the default 17-node sample we expect the too_large warning,
        # not a crash and not a danger error.
        warning_text = await page.evaluate(
            "() => {"
            "  const w = document.querySelector('#boolean-attractor_panel .alert-warning');"
            "  return w ? w.textContent.trim() : null;"
            "}"
        )
        print(f"warning alert: {warning_text!r}")
        assert warning_text is not None, "expected alert-warning in attractor panel"
        assert "Network has" in warning_text and "Simplify Network" in warning_text, \
            f"warning text doesn't match too_large pattern: {warning_text}"

        # No danger-level error alert anywhere on the page
        danger_count = await page.evaluate(
            "() => document.querySelectorAll('.alert-danger').length"
        )
        print(f"alert-danger count: {danger_count}")
        assert danger_count == 0, f"unexpected error alert(s) present: {danger_count}"

        await page.screenshot(path="tests/screenshots/boolean.png")
        print("\nboolean e2e assertions pass")
        await browser.close()


asyncio.run(main())
