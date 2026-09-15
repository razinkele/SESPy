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

        await page.wait_for_selector("#sespy_nav_boolean", timeout=60000)
        await page.click("#sespy_nav_boolean")
        # The Laplacian tab's plot output is SUSPENDED while the panel is
        # hidden; when the pane becomes visible it renders a "Click Run"
        # PLACEHOLDER figure that is also an <img>. Wait for that placeholder
        # (strictly stronger than a blind sleep: the <img> exists only after
        # the nav round-trip completed AND the suspended output resumed) and
        # record its src so the post-Run wait can tell the real eigenvalue
        # chart apart from it.
        await page.wait_for_selector("#boolean-eigenvalue_plot img", timeout=60000)
        pre_run_dt = await page.evaluate(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length"
        )
        assert pre_run_dt == 0, (
            "plot already shows a post-run figure; placeholder capture invalid "
            f"(stability summary already has {pre_run_dt} <dt>)"
        )
        await page.evaluate(
            "() => { window.__boolPlaceholderSrc ="
            " document.querySelector('#boolean-eigenvalue_plot img').src; }"
        )

        # Run analysis
        await page.click("#boolean-run_boolean")

        # Eigenvalue plot rendered (img tag inside the plot output). An <img>
        # already existed before Run — the "Click Run" placeholder figure — so
        # waiting for the selector alone would pass instantly and prove nothing.
        # Wait instead for the src to CHANGE away from the captured placeholder
        # AND for the stability summary to populate; both only happen after the
        # analysis actually ran. This is the first matplotlib render in the
        # session and the cold import can take several seconds.
        await page.wait_for_function(
            "() => {"
            "  const i = document.querySelector('#boolean-eigenvalue_plot img');"
            "  if (!i || i.src === window.__boolPlaceholderSrc) return false;"
            "  return document.querySelectorAll('#boolean-stability_summary dl dt').length >= 3;"
            "}",
            timeout=60000,
        )
        plot_rendered = await page.evaluate(
            "() => {"
            "  const i = document.querySelector('#boolean-eigenvalue_plot img');"
            "  return !!i && i.src !== window.__boolPlaceholderSrc;"
            "}"
        )
        print(f"eigenvalue plot rendered: {plot_rendered}")
        assert plot_rendered, \
            "eigenvalue plot still shows the pre-run 'Click Run' placeholder"

        # Stability summary populated (a <dl> with at least 3 dt/dd pairs).
        # It renders a tick after the plot, so wait for it to populate rather
        # than asserting immediately.
        await page.wait_for_function(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length >= 3",
            timeout=15000,
        )
        n_dt = await page.evaluate(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length"
        )
        print(f"stability summary <dt> count: {n_dt}")
        assert n_dt >= 3, f"expected stability summary with >=3 fields, got {n_dt}"

        # Switch to the Boolean attractors tab
        # Scope to this module's navset, never a bare text= match: every panel
        # shares one DOM, so a future label elsewhere would hijack this click.
        await page.click("#boolean-boolean_tabs a[data-value='Boolean attractors']")
        # Wait for the attractor panel's reactive content (the too_large
        # warning alert) rather than racing a fixed sleep.
        await page.wait_for_selector("#boolean-attractor_panel .alert-warning", timeout=15000)

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
