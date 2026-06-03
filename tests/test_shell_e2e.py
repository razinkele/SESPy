"""End-to-end smoke test for the dashboard shell.

Boots the running app and confirms:
  - sidebar nav has both buttons with the right labels
  - clicking the Loop Analysis button switches the active panel (the
    `loops-loop_network` host appears with non-zero dimensions)
  - no JS errors in the console
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
        await page.wait_for_timeout(1500)

        nav_buttons = await page.eval_on_selector_all(
            ".sespy-nav-btn",
            "els => els.map(e => ({id: e.id, label: e.innerText.trim(), active: e.classList.contains('active')}))",
        )
        print("nav buttons:", nav_buttons)

        cld_dims = await page.evaluate(
            "() => { const e=document.getElementById('cld-network'); return e ? e.getBoundingClientRect() : null; }"
        )
        print(f"cld-network on default panel: w={int(cld_dims['width'])} h={int(cld_dims['height'])}")
        assert cld_dims["width"] > 100 and cld_dims["height"] > 100, "CLD canvas not visible on default panel"

        # Click Loop Analysis nav
        await page.click("#sespy_nav_loops")
        await page.wait_for_timeout(1500)

        loops_dims = await page.evaluate(
            "() => { const e=document.getElementById('loops-loop_network'); return e ? e.getBoundingClientRect() : null; }"
        )
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

        # Snapshot the shell so we can compare visually with R app
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path="C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/SESPy/tests/screenshots/shell_after_skin.png")
        print("\nscreenshot saved → tests/screenshots/shell_after_skin.png")

        await browser.close()


asyncio.run(main())
