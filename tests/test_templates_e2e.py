"""E2E for Templates: panel renders, clicking a template loads it,
analysis modules see the new data."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#sespy_nav_templates", timeout=15000)

        # Click Templates nav
        await page.click("#sespy_nav_templates")
        await page.wait_for_timeout(2500)

        # Templates panel should list our shipped templates
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        print("templates listed:", cards)
        assert len(cards) >= 2, f"expected ≥2 templates, got {cards}"
        # Spot-check a known one
        assert any("Offshore Wind" in c for c in cards), \
            f"Offshore Wind template missing: {cards}"

        # Click Load on the first template
        await page.click("#templates-load_template_0")
        await page.wait_for_timeout(2500)

        # Switch to CLD: project_data should now reflect the loaded template
        await page.click("#sespy_nav_cld")
        for _ in range(15):
            n = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if n is not None and n > 0:
                break
            await page.wait_for_timeout(500)
        print(f"CLD nodes after template load: {n}")
        # Each shipped template has at least 15 elements
        assert n is not None and n >= 15, \
            f"CLD didn't reflect template load: {n} nodes"

        await page.screenshot(path="tests/screenshots/templates.png")
        print("\ntemplates e2e assertions pass")
        await browser.close()


asyncio.run(main())
