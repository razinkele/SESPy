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

        # --- realm column (leverage typology) renders with valid labels ---
        await page.wait_for_selector("#leverage-leverage_table table tbody tr", timeout=30000)
        realm_cells = await page.evaluate(
            "() => { const ths = Array.from(document.querySelectorAll("
            "'#leverage-leverage_table table thead th')).map(th => th.textContent.trim());"
            " const i = ths.indexOf('realm');"
            " if (i < 0) return null;"
            " return Array.from(document.querySelectorAll("
            "'#leverage-leverage_table table tbody tr')).map("
            "tr => (tr.querySelectorAll('td')[i]?.textContent || '').trim()); }"
        )
        assert realm_cells is not None, "no 'realm' column header in leverage table"
        # No "—" expected: every sample_ses.json node has a known DAPSIWRM type,
        # so a "—" here means the realm wiring is broken (leverage_realm never
        # called / token always ""). Keeping "—" out of `allowed` makes that fail.
        allowed = {"Parameters", "Feedbacks", "Design", "Intent"}
        assert realm_cells and all(c in allowed for c in realm_cells), \
            f"unexpected realm cell values: {realm_cells}"
        assert "—" not in realm_cells, \
            f"dash in realm cells — wiring broken or unknown type in sample data: {realm_cells}"
        print(f"leverage realm column: OK ({realm_cells})")

        # --- Uncertainty toggle adds the 95% CI column ---
        await page.click("#sespy_nav_leverage")
        await page.wait_for_selector("#leverage-leverage_table table tbody tr", timeout=30000)
        # Use 50 samples to keep the MC run under ~5s on this machine.
        await page.fill("#leverage-n_samples", "50")
        await page.dispatch_event("#leverage-n_samples", "change")
        await page.check("#leverage-show_uncertainty")
        # Table re-renders; poll for the new header (allow up to 30s for MC).
        found_ci = False
        headers = []
        for _ in range(30):
            await page.wait_for_timeout(1000)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#leverage-leverage_table table thead th')).map(th => th.textContent.trim())"
            )
            if any("CI" in h for h in headers):
                found_ci = True
                break
        assert found_ci, f"95% CI column not added after toggling uncertainty: {headers}"
        print("leverage uncertainty CI column: OK")

        await browser.close()


asyncio.run(main())
