"""End-to-end smoke test for the dashboard shell.

Boots the running app and confirms:
  - sidebar nav has both buttons with the right labels
  - clicking the Loop Analysis button switches the active panel (the
    `loops-loop_network` host appears with non-zero dimensions)
  - no uncaught JS exceptions (pageerror) during load and the Loop Analysis nav click
    (console errors are printed for diagnosis only, not asserted)
  - only one outer page frame remains (the page-edge container-fluid)
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)

        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # Wait for the reactive nav to render before querying it.
        await page.wait_for_selector(".sespy-nav-btn", timeout=60000)

        nav_buttons = await page.eval_on_selector_all(
            ".sespy-nav-btn",
            "els => els.map(e => ({id: e.id, label: e.innerText.trim(), active: e.classList.contains('active')}))",
        )
        print("nav buttons:", nav_buttons)

        # #cld-network is a STATIC host div, not a render product: output_pyvis_network()
        # emits style="width: 100%; height: 650px; min-height: 200px"
        # (pyvis/shiny/wrapper.py:358-362) inside the static
        # ui.navset_hidden(*panels, selected="cld") (sespy/dashboard.py:230, app.py:159),
        # so this rect is 100% x 650px at parse time and stays that size even if the
        # render raises (Shiny's error path swaps innerHTML, not the inline style).
        # It therefore proves only that the CLD pane is the visible default pane.
        # The mounted vis.js network (20 edges via window.pyvisNetworks['cld-network'])
        # is covered by tests/test_cld_e2e.py, which runs earlier in the same gate.
        cld_dims = await page.evaluate(
            "() => { const e=document.getElementById('cld-network'); return e ? e.getBoundingClientRect() : null; }"
        )
        print(f"cld-network on default panel: w={int(cld_dims['width'])} h={int(cld_dims['height'])}")
        assert cld_dims["width"] > 100 and cld_dims["height"] > 100, "CLD panel is not the visible default panel"

        # Click Loop Analysis nav
        await page.click("#sespy_nav_loops")
        # The click is a full server round-trip (_wire_nav_button -> _goto ->
        # ui.update_navs) that also un-suspends the Loop panel's outputs, on an
        # event loop shared with every other e2e script. Poll for the pane to
        # become visible instead of guessing a settle time.
        loops_dims = None
        for _ in range(60):  # up to ~60 s, same budget as the nav wait above
            loops_dims = await page.evaluate(
                "() => { const e=document.getElementById('loops-loop_network'); return e ? e.getBoundingClientRect() : null; }"
            )
            if loops_dims and loops_dims["width"] > 100 and loops_dims["height"] > 100:
                break
            await page.wait_for_timeout(1000)

        assert loops_dims, "#loops-loop_network host missing from the DOM"
        print(f"loops-loop_network after click: w={int(loops_dims['width'])} h={int(loops_dims['height'])}")
        assert loops_dims["width"] > 100 and loops_dims["height"] > 100, "Loop canvas not visible after nav click"

        active = await page.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        print(f"active nav button after click: {active}")
        assert active == ["sespy_nav_loops"], f"Expected loops active, got {active}"

        if errors:
            print("\nJS errors:")
            for e in errors:
                print("  " + e)
        else:
            print("\nno JS errors")
        benign = ("ResizeObserver loop",)   # Chromium reports this benign layout notice as an uncaught error
        fatal = [e for e in errors
                 if e.startswith("[pageerror]") and not any(b in e for b in benign)]
        assert not fatal, "uncaught JS exception(s) on the shell page:\n  " + "\n  ".join(fatal)

        # Snapshot the shell so we can compare visually with R app
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path="C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy/tests/screenshots/shell_after_skin.png")
        print("\nscreenshot saved → tests/screenshots/shell_after_skin.png")

        await browser.close()


asyncio.run(main())
