"""E2e: ?view restores the active module (panel visible, not just highlighted),
and the URL stays in sync on nav + stepper navigation."""
import asyncio

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})

        # --- Case 1: restore from ?view switches the PANEL, not just the highlight
        print("\n=== case 1: restore ?view=metrics shows the metrics panel ===")
        await page.goto(f"{BASE}/?view=metrics", wait_until="networkidle")
        # The .tab-pane panels live in a sibling `.tab-content` div, NOT inside
        # `#main_nav` (which is the <ul class="nav nav-hidden"> strip). navset_hidden
        # renders every panel into the DOM, so assert the metrics tab-pane is ACTIVE.
        await page.wait_for_function(
            "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='metrics']\");"
            " return !!el && el.classList.contains('active'); }",
            timeout=20000,
        )
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'metrics'",
            timeout=15000,
        )
        print("  ok (metrics panel active + URL settled)")

        # --- Case 2: clicking a nav button updates the URL
        print("\n=== case 2: nav click updates ?view ===")
        await page.click("#sespy_nav_loops")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'loops'",
            timeout=15000,
        )
        print("  ok (?view=loops)")

        # --- Case 3: stepper click tracks active_panel (real value change)
        # Navigate to metrics first so visualize->cld is a genuine change (from the
        # default cld, visualize->cld is a no-op the reactive.Value identity check
        # short-circuits).
        print("\n=== case 3: stepper visualize -> cld (real change) ===")
        await page.click("#sespy_nav_metrics")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'metrics'",
            timeout=15000,
        )
        await page.click("#sespy_step_visualize")
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'cld'",
            timeout=15000,
        )
        print("  ok (?view=cld via stepper)")

        print("\nbookmark e2e assertions pass")
        await browser.close()


asyncio.run(main())
