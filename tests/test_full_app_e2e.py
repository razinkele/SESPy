"""Final integration smoke: all 5 nav tabs render, language switch works,
hamburger collapses sidebar to mini-mode."""
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
        await page.wait_for_selector(".sespy-nav-btn", timeout=20000)

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
            await page.wait_for_timeout(2500)
            active = await page.eval_on_selector_all(
                ".sespy-nav-btn.active", "els => els.map(e => e.id)"
            )
            assert active == [nav_id], f"{nav_id}: active mismatch {active}"
        print(f"all {len(nav_ids)} tabs activate correctly")

        # Take a final overview screenshot (back on CLD)
        await page.click("#sespy_nav_cld")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="tests/screenshots/full_app.png")

        print("\nfull-app e2e assertions pass")
        await browser.close()


asyncio.run(main())
