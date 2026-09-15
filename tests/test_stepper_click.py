"""Verify clicking a stepper step navigates to the matching panel."""
import asyncio

from playwright.async_api import async_playwright


async def wait_active(pg, expected):
    """Poll `.sespy-nav-btn.active` until it equals `expected` (max 30 s).

    The active class is produced by the `sespy_nav_render` @render.ui output
    (sespy/dashboard.py:394-403), so it moves only after a full server
    round-trip plus a DOM replacement. Returns the LAST observed value so the
    caller's assert still reports the real state on a genuine regression.
    """
    active = []
    for _ in range(60):          # up to 30 s, polled every 500 ms
        active = await pg.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        if active == expected:
            break
        await pg.wait_for_timeout(500)
    return active


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)

        # Default panel is "cld" → click stepper "Report" → panel switches
        await pg.click("#sespy_step_report")
        # The highlight and the pane are two separate calls in _goto
        # (sespy/dashboard.py:480-481). If _wire_step_button (dashboard.py:496-507)
        # ever sets active_panel directly instead of calling _goto -- the trap
        # _goto's own docstring warns about -- the highlight moves and ?view still
        # syncs (it reads active_panel, not the pane), so nothing else in the gate
        # goes red. Assert the pane. Selector pattern from test_bookmark_e2e.py:22-27.
        await pg.wait_for_function(
            "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='report']\");"
            " return !!el && el.classList.contains('active'); }",
            timeout=30000,
        )
        active = await wait_active(pg, ["sespy_nav_report"])
        print(f"after Report stepper click: {active}")
        assert active == ["sespy_nav_report"]

        # Click stepper "Visualize" → switches to CLD
        await pg.click("#sespy_step_visualize")
        # pane assert -- see the rationale on the Report block above
        await pg.wait_for_function(
            "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='cld']\");"
            " return !!el && el.classList.contains('active'); }",
            timeout=30000,
        )
        active = await wait_active(pg, ["sespy_nav_cld"])
        print(f"after Visualize stepper click: {active}")
        assert active == ["sespy_nav_cld"]

        # Click stepper "Analyze" → switches to first analyze nav (loops)
        await pg.click("#sespy_step_analyze")
        # pane assert -- see the rationale on the Report block above
        await pg.wait_for_function(
            "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='loops']\");"
            " return !!el && el.classList.contains('active'); }",
            timeout=30000,
        )
        active = await wait_active(pg, ["sespy_nav_loops"])
        print(f"after Analyze stepper click: {active}")
        assert active == ["sespy_nav_loops"]

        print("\nclickable-stepper assertions pass")
        await b.close()


asyncio.run(main())
