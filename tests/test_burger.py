"""Verify burger toggles sidebar between full and mini modes, and
capture before/after screenshots for visual comparison.
"""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # The nav and its .sespy-nav-icon elements are a reactive @render.ui
        # output; wait for them before toggling so the mini-mode icon check
        # doesn't race the first render (this test was intermittently flaky
        # on a fixed 1.5s sleep).
        await page.wait_for_selector(".sespy-nav-icon", timeout=20000)

        # OUTER toggle — direct child of the page-level sidebar layout,
        # NOT inside a .sespy-card.
        OUTER_TOGGLE = (
            "body > div > .bslib-sidebar-layout > .collapse-toggle, "
            ".bslib-page-sidebar > .bslib-sidebar-layout > .collapse-toggle"
        )

        before = await page.evaluate(
            "() => ({"
            " body_classes: document.body.className,"
            " toggle_present: document.querySelectorAll('.bslib-sidebar-layout > .collapse-toggle').length"
            "})"
        )
        print("before click:", before)
        assert before["toggle_present"] > 0, "no collapse-toggle in DOM"

        await page.screenshot(path="tests/screenshots/burger_open.png")

        # Click the outer toggle (not nested in .sespy-card)
        await page.evaluate("""() => {
          const toggles = document.querySelectorAll('.bslib-sidebar-layout > .collapse-toggle');
          for (const t of toggles) {
            if (!t.closest('.sespy-card')) { t.click(); return; }
          }
        }""")
        await page.wait_for_timeout(800)

        after = await page.evaluate(
            "() => ({"
            " sidebar_w: document.querySelector('.bslib-page-sidebar > .bslib-sidebar-layout > .sidebar')?.getBoundingClientRect().width,"
            " body_classes: document.body.className,"
            " icons_visible: document.querySelectorAll('.sespy-nav-icon').length,"
            " labels_hidden: Array.from(document.querySelectorAll('.sespy-nav-btn > span')).filter(s => !s.classList.contains('sespy-nav-icon')).every(s => getComputedStyle(s).display === 'none')"
            "})"
        )
        print("after click:", after)
        assert "sespy-sidebar-mini" in (after["body_classes"] or ""), \
            "body should have sespy-sidebar-mini class"
        assert after["icons_visible"] > 0, "icons should still be in DOM"
        assert after["labels_hidden"], "all nav-button labels should be hidden in mini mode"
        assert after["sidebar_w"] is None or after["sidebar_w"] < 100, \
            f"sidebar should be ~64px in mini, got {after['sidebar_w']}"

        # Verify the grid actually shrunk so main area got wider
        grid_after = await page.evaluate("""() => {
          const layout = Array.from(document.querySelectorAll('.bslib-sidebar-layout'))
            .find(el => !el.closest('.sespy-card'));
          if (!layout) return null;
          return {
            grid_cols: getComputedStyle(layout).gridTemplateColumns,
            sidebar_w: layout.firstElementChild?.getBoundingClientRect().width,
          };
        }""")
        print(f"grid after click: {grid_after}")
        # The grid template should now start with 64px (or close to it)
        assert grid_after and "64" in grid_after["grid_cols"], \
            f"grid columns didn't shrink: {grid_after['grid_cols']}"

        await page.screenshot(path="tests/screenshots/burger_mini.png")

        # Toggle back via the same outer toggle
        await page.evaluate("""() => {
          const toggles = document.querySelectorAll('.bslib-sidebar-layout > .collapse-toggle');
          for (const t of toggles) {
            if (!t.closest('.sespy-card')) { t.click(); return; }
          }
        }""")
        await page.wait_for_timeout(800)
        back = await page.evaluate("() => document.body.className")
        assert "sespy-sidebar-mini" not in (back or ""), \
            "second click should remove sespy-sidebar-mini"
        print("toggled back to full:", back)

        print("\nall burger assertions pass")
        await browser.close()


asyncio.run(main())
