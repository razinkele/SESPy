"""Final overview screenshot."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        nav_ids = await page.eval_on_selector_all(
            ".sespy-nav-btn", "els => els.map(e => e.id)"
        )
        print("nav buttons rendered:", len(nav_ids))
        print(" ", nav_ids)

        await page.screenshot(path="tests/screenshots/final.png")
        print("\nfinal screenshot saved")
        await browser.close()


asyncio.run(main())
