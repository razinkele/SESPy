"""Verify clicking a stepper step navigates to the matching panel."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)

        # Default panel is "cld" → click stepper "Report" → panel switches
        await pg.click("#sespy_step_report")
        await pg.wait_for_timeout(2000)
        active = await pg.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        print(f"after Report stepper click: {active}")
        assert active == ["sespy_nav_report"]

        # Click stepper "Visualize" → switches to CLD
        await pg.click("#sespy_step_visualize")
        await pg.wait_for_timeout(2000)
        active = await pg.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        print(f"after Visualize stepper click: {active}")
        assert active == ["sespy_nav_cld"]

        # Click stepper "Analyze" → switches to first analyze nav (loops)
        await pg.click("#sespy_step_analyze")
        await pg.wait_for_timeout(2000)
        active = await pg.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        print(f"after Analyze stepper click: {active}")
        assert active == ["sespy_nav_loops"]

        print("\nclickable-stepper assertions pass")
        await b.close()


asyncio.run(main())
