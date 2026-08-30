"""E2E for the Dynamic Simulation module: navigate, click Run Simulation
and Run Monte Carlo, verify both result panels populate, and toggle the
loop-dominance overlay on the trajectory plot."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 1000})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await page.wait_for_selector("#sespy_nav_simulation", timeout=15000)
        await page.click("#sespy_nav_simulation")
        # Wait for the run button to mount (condition, not a guessed delay).
        await page.wait_for_selector("#simulation-run_sim", timeout=15000)

        # ---- Deterministic simulation ----
        await page.click("#simulation-run_sim")
        # Wait for the plot image itself rather than a fixed timeout: the render
        # can lag the click under full-suite / CI load, which flaked a bare
        # 2.5s sleep-then-assert.
        await page.wait_for_selector("#simulation-trajectory_plot img", timeout=30000)
        print("trajectory plot rendered: True")

        # ---- Loop-dominance overlay (#22) ----
        # Asserted here, while the Trajectories panel is still the active tab:
        # dominance_summary is an output_ui on that panel and Shiny suspends
        # outputs on inactive nav panels, so this must precede the tab switches
        # below. Deliberately no pixel assertions on the shading -- the numbers
        # are covered by tests/test_network.py; this is a declared coverage
        # limit. What it does prove is that ticking the box drives the server
        # through loop_dominance()/dominance_shifts() without erroring.
        assert await page.is_visible("#simulation-dominance_show")
        assert not await page.is_checked("#simulation-dominance_show"), \
            "loop-dominance toggle should default to off"
        summary_len = await page.eval_on_selector(
            "#simulation-dominance_summary", "el => el.innerText.trim().length"
        )
        assert summary_len == 0, "dominance summary should be empty when off"

        await page.check("#simulation-dominance_show")
        # Condition, not a guessed delay: the summary goes from empty to a
        # shift list (or a translated "no cycles"/"zero gain" note), which only
        # happens once the server has actually run the dominance code.
        await page.wait_for_function(
            "() => { const el = document.querySelector('#simulation-dominance_summary');"
            "        return el && el.innerText.trim().length > 0; }",
            timeout=30000,
        )
        assert await page.is_checked("#simulation-dominance_show")
        # The plot is invalidated by the same input; it must survive the
        # overlay, not vanish behind a render exception.
        await page.wait_for_selector("#simulation-trajectory_plot img", timeout=30000)
        errored = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "    '#simulation-trajectory_plot, #simulation-dominance_summary'))"
            "  .filter(el => el.classList.contains('shiny-output-error')"
            "             || el.querySelector('.shiny-output-error'))"
            "  .map(el => el.id)"
        )
        assert errored == [], f"loop-dominance outputs errored: {errored}"
        print("loop-dominance overlay rendered: True")

        # Toggle back off so the Final state / Monte Carlo sections below run
        # against exactly the state they did before this block existed.
        await page.uncheck("#simulation-dominance_show")
        await page.wait_for_function(
            "() => { const el = document.querySelector('#simulation-dominance_summary');"
            "        return el && el.innerText.trim().length === 0; }",
            timeout=30000,
        )
        print("loop-dominance overlay cleared: True")


        # Switch to Final state tab
        await page.click("text=Final state")
        await page.wait_for_selector("#simulation-final_state_plot img", timeout=30000)

        # ---- Monte Carlo ----
        # Note: the n_simulations control is an ion-rangeslider, which doesn't
        # respond to plain JS .value assignment. Leave the slider at its default
        # (100) and accept the longer wait. ~10-15s on a small sample dataset.
        await page.click("#simulation-run_mc")

        # Switch to Monte Carlo tab so its outputs are unsuspended. Scope the
        # selector to the simulation tabset: a bare text=Monte Carlo now also
        # matches the "Show uncertainty (Monte Carlo)" toggles in the leverage
        # and loops modules (7 matches), and Playwright would pick a hidden one.
        await page.click("#simulation-simulation_tabs a[data-value='Monte Carlo']")

        # Poll for the summary table to populate (MC compute blocks the event
        # loop ~10-15s on the 17-node sample; render arrives shortly after).
        n_rows = 0
        for _ in range(40):
            await page.wait_for_timeout(1000)
            n_rows = await page.evaluate(
                "() => document.querySelectorAll('#simulation-mc_summary table tbody tr').length"
            )
            if n_rows >= 1:
                break
        print(f"MC summary rows: {n_rows}")
        assert n_rows >= 1

        # Completion message visible (looks for "Simulations completed:")
        msg_seen = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#simulation-mc_summary p'))"
            "  .some(p => p.textContent.includes('Simulations completed'))"
        )
        assert msg_seen, "MC completion message not found"

        # Histogram plot visible (render can trail the summary table slightly).
        await page.wait_for_selector("#simulation-mc_histograms img", timeout=15000)

        await page.screenshot(path="tests/screenshots/simulation.png")
        print("\nsimulation e2e assertions pass")
        await browser.close()


asyncio.run(main())
