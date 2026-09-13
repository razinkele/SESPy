"""Final integration smoke: every nav button activates its own tab, and no
output raises while visiting them.

Coverage limit: this script does NOT exercise the language switcher or the
sidebar hamburger, despite what this docstring claimed until now -- those are
covered by tests/test_i18n_e2e.py and tests/test_burger.py respectively.
"""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # Nav is a reactive @render.ui output; wait for it to flush instead of
        # racing a fixed sleep (cold first render can exceed 1.5s, esp. headless/CI).
        await page.wait_for_selector(".sespy-nav-btn", timeout=60000)

        # All 5 nav buttons present
        nav_ids = await page.eval_on_selector_all(
            ".sespy-nav-btn", "els => els.map(e => e.id)"
        )
        print("nav IDs:", nav_ids)
        # Nav grew over time — assert that the core five are present and
        # leave headroom for additions (entry, intervention, recent, report).
        for required in ("sespy_nav_cld", "sespy_nav_loops",
                         "sespy_nav_metrics", "sespy_nav_leverage",
                         "sespy_nav_import"):
            assert required in nav_ids, f"missing {required} in {nav_ids}"

        # Each tab renders without throwing
        for nav_id in nav_ids:
            await page.click(f"#{nav_id}")
            # The `active` class is server-rendered (sespy_nav_render @render.ui),
            # so it moves only after a round-trip that shares the single event
            # loop with the PREVIOUS panel's suspended first render (pyvis CLD,
            # matplotlib, networkx). Poll instead of a fixed sleep, keeping the
            # original assertion so a real mismatch still prints both ids.
            # 60 x 500ms = 30s per tab, and the happy path no longer pays an
            # unconditional 2.5s per tab, so total wall-clock goes DOWN.
            active: list[str] = []
            for _ in range(60):
                active = await page.eval_on_selector_all(
                    ".sespy-nav-btn.active", "els => els.map(e => e.id)"
                )
                if active == [nav_id]:
                    break
                await page.wait_for_timeout(500)
            assert active == [nav_id], f"{nav_id}: active mismatch {active}"
            # The highlight comes from active_panel.set(); switching the PANEL is
            # the separate ui.update_navs call in _goto (sespy/dashboard.py:481),
            # whose docstring warns that `.set` alone "only moves the highlight".
            # Filter by data-value like tests/test_bookmark_e2e.py:23 does: a bare
            # `.tab-content > .tab-pane.active` ALSO matches the nested navset_tab
            # panes inside boolean/bot/simulation/stakeholders/about.
            view = nav_id[len("sespy_nav_"):]
            pane_ok = False
            for _ in range(20):          # 20 x 250ms = 5s after the highlight
                pane_ok = await page.evaluate(
                    "(v) => { const el = document.querySelector"
                    "(`.tab-content > .tab-pane[data-value=\"${v}\"]`);"
                    " return !!el && el.classList.contains('active'); }",
                    view,
                )
                if pane_ok:
                    break
                await page.wait_for_timeout(250)
            assert pane_ok, f"{nav_id}: highlight moved but pane {view!r} is not the active tab-pane"
        print(f"all {len(nav_ids)} tabs activate correctly")
        # "renders without throwing" was never actually checked above: the nav
        # highlight comes from sespy_nav_render (dashboard.py:394-403) and is
        # independent of the revealed panel's outputs, so a panel full of red
        # error boxes still passes `active == [nav_id]`. Shiny reports a render
        # exception by adding `shiny-output-error` to the output element
        # (shiny.js renderError), and navset_hidden (dashboard.py:230) keeps
        # every panel in the DOM -- so ONE document-wide sweep HERE covers all
        # of them, and every panel has now had its 2.5 s.
        # Do NOT move this inside the loop: an output that has not rendered yet
        # carries no error class either, so a per-tab sweep would be vacuous.
        # Do NOT try to settle first by waiting for `.recalculating` to clear:
        # navigating away suspends an output, and its invalidation adds
        # `recalculating` with nothing to remove it while suspended -- such a
        # wait would hang on every panel we left.
        # No class filter is needed: py-shiny sends no error `type`
        # (session/_session.py sets "type": None), so `shiny-output-error-*`
        # subclasses never appear, and req()/SilentException blanks the output
        # silently without any class.
        # Scope: catches render-function exceptions only. A @reactive.effect
        # that raises sets no class, an exception whose str() is empty makes
        # Shiny just empty the element (no class), and a panel whose first
        # render outran its 2.5 s is still in flight and cannot be seen here.
        errored = await page.evaluate(
            "() => Array.from(document.querySelectorAll('.shiny-output-error'))"
            "  .map(el => el.id || el.className)"
        )
        assert errored == [], \
            f"outputs errored while visiting every tab: {errored}"

        # Take a final overview screenshot (back on CLD)
        await page.click("#sespy_nav_cld")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="tests/screenshots/full_app.png")

        print("\nfull-app e2e assertions pass")
        await browser.close()


asyncio.run(main())
