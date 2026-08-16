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

        # --- Intervention simulation (token diffusion), fixed seed 0 ---
        await page.wait_for_selector("#intervention-diffusion_summary", timeout=15000)
        hint = (await page.inner_text("#intervention-diffusion_summary")).strip()
        assert "not simulated" in hint, f"expected idle hint, got: {hint!r}"
        await page.select_option("#intervention-diffusion_source", "D001")
        await page.click("#intervention-run_diffusion")
        diff_text = ""
        for _ in range(30):
            await page.wait_for_timeout(500)
            diff_text = (await page.inner_text("#intervention-diffusion_summary")).strip()
            if "elements reached" in diff_text:
                break
        # Sample golden at seed 0: D001 reaches 7 of 17 elements; the top
        # row is P001 with 2000 tokens.
        assert "7 of 17 elements reached by 1000 tokens in 10 steps" in diff_text, \
            f"expected summary, got: {diff_text!r}"
        assert "Anchor damage" in diff_text and "2000" in diff_text, \
            f"expected top row, got: {diff_text!r}"
        # The bar chart must render as an <img> once results exist.
        chart_ok = await page.evaluate(
            "() => { const el = document.getElementById('intervention-diffusion_chart');"
            " return !!el && !!el.querySelector('img'); }"
        )
        assert chart_ok, "diffusion chart did not render an image"
        # Changing the source must invalidate the previous run (no stale
        # table) and a re-run must reflect the NEW source: P002 reaches 13
        # of 17 elements at seed 0, vs D001's 7.
        await page.select_option("#intervention-diffusion_source", "P002")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not simulated" in (await page.inner_text("#intervention-diffusion_summary")):
                break
        stale = (await page.inner_text("#intervention-diffusion_summary")).strip()
        assert "not simulated" in stale, f"stale result survived a source change: {stale!r}"
        await page.click("#intervention-run_diffusion")
        for _ in range(30):
            await page.wait_for_timeout(500)
            diff_text = (await page.inner_text("#intervention-diffusion_summary")).strip()
            if "elements reached" in diff_text:
                break
        assert "13 of 17 elements reached by 1000 tokens in 10 steps" in diff_text, \
            f"expected P002 summary, got: {diff_text!r}"
        print(f"intervention simulation: OK ({diff_text[:90]!r})")
        print("\nintervention e2e assertions pass")
        await browser.close()


asyncio.run(main())
