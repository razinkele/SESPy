"""E2E for the Leverage Points module."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Click "Leverage Points"
        await page.click("#sespy_nav_leverage")
        await page.wait_for_timeout(2500)

        nav_active = await page.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        assert nav_active == ["sespy_nav_leverage"], f"unexpected: {nav_active}"

        nodes = await page.evaluate(
            "() => window.pyvisNetworks['leverage-leverage_network'].nodes.length"
        )
        print(f"leverage network nodes: {nodes}")
        assert nodes == 17

        # Sizes vary across nodes (leverage scores aren't all equal)
        sizes = await page.evaluate(
            "() => window.pyvisNetworks['leverage-leverage_network'].nodes.get()"
            ".map(n => n.size)"
        )
        assert min(sizes) < max(sizes), "sizes are uniform — leverage scoring not applied"
        print(f"size range: {min(sizes)}–{max(sizes)}")

        await page.screenshot(path="tests/screenshots/leverage.png")
        print("\nleverage e2e assertions pass")
        await browser.close()


asyncio.run(main())
