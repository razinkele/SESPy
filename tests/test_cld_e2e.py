"""E2E: the main CLD network dashes the seeded delayed edge."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        # CLD is the default tab; wait for its network container to mount so a
        # "tab never rendered" failure is distinct from an "edges empty" timeout.
        await page.wait_for_selector("#cld-network", timeout=30000)
        # Poll until the network DataSet has edges.
        dashes = None
        for _ in range(16):
            res = await page.evaluate(
                "() => { const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s || !s.edges) return null;"
                " const es = s.edges.get();"
                " return { n: es.length, dashes: es.map(e => e.dashes === true) }; }"
            )
            if res and res["n"]:
                dashes = res
                break
            await page.wait_for_timeout(500)
        print("cld edges:", dashes)
        assert dashes is not None, "cld-network edges not readable"
        assert dashes["n"] == 20, f"expected 20 edges (default, unfiltered), got {dashes['n']}"
        flags = dashes["dashes"]
        assert any(flags), "no dashed (delayed) edge in the CLD"
        assert not all(flags), "expected at least one solid (immediate) edge too"

        await page.screenshot(path="tests/screenshots/cld.png")
        print("\ncld e2e assertions pass")
        await browser.close()


asyncio.run(main())
