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
        # Sampling error is now visible: GB01 and A001 differ by 2 arrivals
        # with a +/-32 margin, so they must share a rank rather than being
        # ranked 3 and 4 (issue #19).
        assert "±32" in diff_text, f"expected a 95% margin column, got: {diff_text!r}"
        assert "1501 ±32" in diff_text and "1499 ±32" in diff_text, \
            f"expected margins on the near-tied pair, got: {diff_text!r}"
        assert "rank" in diff_text, f"expected a rank column, got: {diff_text!r}"
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

        # --- Option B: path-set BBN, forward query D001 -> GB01 (2 paths, one
        # '-' hop each, so the target's P(high) must FALL) ---
        await page.wait_for_selector("#intervention-bbn_summary", timeout=15000)
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary"))
        await page.select_option("#intervention-bbn_source", "D001")
        await page.select_option("#intervention-bbn_target", "GB01")
        await page.click("#intervention-run_bbn")
        # The task runs off the flush, so the "computing" line must appear
        # promptly (proves the event loop was not blocked by the import)...
        await page.wait_for_function(
            "() => (document.getElementById('intervention-bbn_summary')?.innerText || '')"
            ".includes('computing')", timeout=10000)
        # ...and the result may take up to ~65 s on a fresh server: the first
        # pgmpy import loads torch. 120 s stays under run_e2e's SCRIPT_TIMEOUT.
        await page.wait_for_function(
            "() => { const s = document.getElementById('intervention-bbn_summary')?.innerText || '';"
            " return s.includes('causal paths') || s.includes('pgmpy'); }", timeout=120000)
        bbn_text = (await page.inner_text("#intervention-bbn_summary")).strip()
        assert "2 causal paths from D001 to GB01" in bbn_text, f"unexpected summary: {bbn_text!r}"
        assert "GB01" in bbn_text and "(-" in bbn_text, \
            f"expected a negative delta on GB01: {bbn_text!r}"
        n_rows = await page.evaluate(
            "() => document.querySelectorAll('#intervention-bbn_table table tbody tr').length")
        assert n_rows == 7, f"expected 7 path-set nodes in the table, got {n_rows}"
        # Changing the direction invalidates the result.
        await page.click("#intervention-bbn_direction input[value='diagnostic']")
        for _ in range(20):
            await page.wait_for_timeout(500)
            if "not computed" in (await page.inner_text("#intervention-bbn_summary")):
                break
        assert "not computed" in (await page.inner_text("#intervention-bbn_summary")), \
            "stale BBN result survived a direction change"
        print(f"intervention bbn: OK ({bbn_text[:80]!r})")
        print("\nintervention e2e assertions pass")
        await browser.close()


asyncio.run(main())
