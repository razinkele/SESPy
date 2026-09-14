"""E2e: ?view restores the active module (panel visible, not just highlighted),
and the URL stays in sync on nav + stepper navigation."""
import asyncio

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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
            # First wait of the script: this class arrives in the session's first
            # flush, which networkidle above does not cover.
            timeout=60000,
        )
        await page.wait_for_function(
            "() => new URL(window.location).searchParams.get('view') === 'metrics'",
            timeout=15000,
        )
        print("  ok (metrics panel active + URL settled)")

        # --- Case 2: clicking a nav button updates the URL
        print("\n=== case 2: nav click updates ?view ===")
        # The nav is a @render.ui output: it does not exist until the
        # session's first flush (32 s on an idle machine, more under
        # load). Without this the click falls back to Playwright's 30 s
        # default and races startup.
        await page.wait_for_selector("#sespy_nav_loops", timeout=60000)
        await page.click("#sespy_nav_loops")
        try:
            await page.wait_for_function(
                "() => new URL(window.location).searchParams.get('view') === 'loops'",
                # Case 1 revealed the metrics panel: its suspended outputs (matplotlib
                # hist, pyvis network, networkx summaries) render on the single event
                # loop, and this click's round-trip queues behind them.
                timeout=60000,
            )
        except PlaywrightTimeoutError:
            got = await page.evaluate(
                "() => new URL(window.location).searchParams.get('view')"
            )
            raise AssertionError(
                f"nav click did not sync ?view to 'loops' within 60s (still {got!r})"
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
