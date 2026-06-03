"""E2E for the Dynamic Simulation module: navigate, click Run Simulation
and Run Monte Carlo, verify both result panels populate."""
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
        await page.wait_for_timeout(1500)

        # ---- Deterministic simulation ----
        await page.click("#simulation-run_sim")
        await page.wait_for_timeout(2500)

        traj_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-trajectory_plot img')"
        )
        print(f"trajectory plot rendered: {traj_visible}")
        assert traj_visible

        # Switch to Final state tab
        await page.click("text=Final state")
        await page.wait_for_timeout(1000)
        final_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-final_state_plot img')"
        )
        assert final_visible, "final state plot did not render"

        # ---- Monte Carlo ----
        # Note: the n_simulations control is an ion-rangeslider, which doesn't
        # respond to plain JS .value assignment. Leave the slider at its default
        # (100) and accept the longer wait. ~10-15s on a small sample dataset.
        await page.click("#simulation-run_mc")

        # Switch to Monte Carlo tab so its outputs are unsuspended.
        await page.click("text=Monte Carlo")

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

        # Histogram plot visible
        hist_visible = await page.evaluate(
            "() => !!document.querySelector('#simulation-mc_histograms img')"
        )
        assert hist_visible, "MC histograms plot did not render"

        await page.screenshot(path="tests/screenshots/simulation.png")
        print("\nsimulation e2e assertions pass")
        await browser.close()


asyncio.run(main())
