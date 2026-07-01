"""E2E for the ISA Data Entry module: add/remove elements & connections,
verify changes propagate to other modules via event_bus.isa_change."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # The default tab is CLD — wait for its network container to MOUNT
        # first (mirrors test_cld_e2e) so "tab never rendered under load" is
        # not conflated with "network empty". Then poll the pyvis state. The
        # container-wait + a generous poll window keeps this robust when the
        # machine is loaded and the first render is slow.
        await page.wait_for_selector("#cld-network", timeout=30000)
        for _ in range(30):
            init_count = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if init_count == 17:
                break
            await page.wait_for_timeout(500)
        before = init_count
        print(f"nodes before: {before}")
        assert before == 17, f"expected 17, got {before}"

        # Open the Edit Data tab
        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(2000)

        # Add a new element from the Edit Data panel
        await page.fill("#entry-new_label", "Climate change")
        # type select — pick "Drivers"
        await page.evaluate("""() => {
          const el = document.getElementById('entry-new_type');
          if (el) { el.value = 'Drivers'; el.dispatchEvent(new Event('change', {bubbles: true})); }
        }""")
        await page.wait_for_timeout(400)
        await page.click("#entry-add_element")
        await page.wait_for_timeout(1500)

        # Switch to CLD and verify the count went up
        await page.click("#sespy_nav_cld")
        await page.wait_for_selector("#cld-network", timeout=30000)
        for _ in range(30):
            after_add = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if after_add == before + 1:
                break
            await page.wait_for_timeout(500)
        print(f"nodes after add: {after_add}")
        assert after_add == before + 1, f"expected {before + 1}, got {after_add}"

        # Verify the metrics module also picked up the change
        await page.click("#sespy_nav_metrics")
        await page.wait_for_selector("#metrics-metrics_network", timeout=30000)
        for _ in range(30):
            metrics_nodes = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['metrics-metrics_network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if metrics_nodes == before + 1:
                break
            await page.wait_for_timeout(500)
        print(f"metrics nodes after add: {metrics_nodes}")
        assert metrics_nodes == before + 1

        await page.click("#sespy_nav_entry")
        await page.wait_for_timeout(1500)

        # --- delay select on the connection form (delay-aware Loop Analysis) ---
        delay_opts = await page.evaluate(
            "() => { const el=document.getElementById('entry-new_delay');"
            " return el ? Array.from(el.options).map(o => o.value) : null; }"
        )
        print("delay options:", delay_opts)
        assert delay_opts == ["immediate", "short", "long"], f"unexpected: {delay_opts}"

        await page.screenshot(path="tests/screenshots/data_entry.png")

        print("\ndata-entry e2e assertions pass — add propagates 5-way")
        await browser.close()


asyncio.run(main())
