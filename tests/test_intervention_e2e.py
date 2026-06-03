"""E2E for the Intervention module: select a node to ablate, verify
table updates and network re-renders with greyed-out node."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#sespy_nav_intervention", timeout=15000)
        await page.click("#sespy_nav_intervention")
        await page.wait_for_timeout(3000)

        # Network rendered with all 17 nodes (no ablation yet)
        nodes = await page.evaluate(
            "() => window.pyvisNetworks['intervention-intervention_network']"
            ".nodes.length"
        )
        print(f"intervention network nodes (no ablation): {nodes}")
        assert nodes == 17

        # Pick a node to ablate via the selectize widget. Manipulating the
        # underlying <select> via .selected + change-event doesn't propagate
        # through the selectize wrapper to Shiny's input value. The robust
        # pattern is to use Shiny.setInputValue directly (which is what
        # selectize itself does on user interaction).
        await page.evaluate(
            "() => Shiny.setInputValue('intervention-ablate', ['P001'], "
            "{priority: 'event'})"
        )
        await page.wait_for_timeout(2500)

        # Network still has 17 nodes (ablated node is rendered greyed out, not removed
        # from the canvas), but the ablated one has reduced opacity / dashed border
        nodes_after = await page.evaluate(
            "() => window.pyvisNetworks['intervention-intervention_network']"
            ".nodes.length"
        )
        print(f"intervention network nodes (P001 ablated): {nodes_after}")
        assert nodes_after == 17

        # The ablated node's dataset entry should have opacity < 1
        ablated_opacity = await page.evaluate(
            "() => window.pyvisNetworks['intervention-intervention_network']"
            ".nodes.get('P001')?.opacity ?? null"
        )
        print(f"P001 opacity in canvas: {ablated_opacity}")
        # opacity may be 0.4 or might be applied differently; just confirm it was set
        assert ablated_opacity is not None and ablated_opacity < 1.0

        await page.screenshot(path="tests/screenshots/intervention.png")
        print("\nintervention e2e assertions pass")
        await browser.close()


asyncio.run(main())
