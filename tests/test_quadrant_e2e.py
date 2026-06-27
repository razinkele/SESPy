"""E2E for the Factor Quadrant module."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Click "Factor Quadrant"
        await page.click("#sespy_nav_quadrant")
        await page.wait_for_timeout(2500)  # settle pad

        nav_active = await page.eval_on_selector_all(
            ".sespy-nav-btn.active", "els => els.map(e => e.id)"
        )
        assert nav_active == ["sespy_nav_quadrant"], f"unexpected: {nav_active}"

        # Wait for the late-mounting data_frame <tbody> and the matplotlib <img>
        # rather than racing a fixed sleep (cold first render can exceed 2500ms;
        # mirrors test_simulation_e2e.py / test_boolean_e2e.py).
        await page.wait_for_selector("#quadrant-quadrant_table table tbody tr", timeout=30000)
        await page.wait_for_selector("#quadrant-quadrant_plot img", timeout=30000)

        # Classification table rendered rows
        row_count = await page.evaluate(
            "() => document.querySelectorAll("
            "'#quadrant-quadrant_table table tbody tr').length"
        )
        print(f"quadrant table rows: {row_count}")
        assert row_count > 0, "classification table is empty"

        # The 17-node sample must differentiate into >= 2 distinct quadrants —
        # guards against a degeneracy-guard misfire (all 'undetermined') or an
        # all-same-quadrant classifier bug rendering a caption-only plot yet
        # still passing row_count>0 / img>0. Mirrors test_leverage_e2e.py:34's
        # `assert min(sizes) < max(sizes)`.
        quadrants = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#quadrant-quadrant_table table tbody tr'))"
            ".map(tr => tr.querySelector('td:last-child')?.textContent?.trim())"
            ".filter(Boolean)"
        )
        distinct = set(quadrants)
        print(f"distinct quadrants: {distinct}")
        assert len(distinct) >= 2, f"factors not differentiated: {distinct}"

        # Scatter plot image rendered
        img = await page.evaluate(
            "() => { const i = document.querySelector('#quadrant-quadrant_plot img');"
            " return i ? i.naturalWidth : 0; }"
        )
        assert img > 0, "quadrant plot image did not render"

        # --- mean/median split toggle: D001 reclassifies (verified on the sample) ---
        async def quadrant_by_id():
            return await page.evaluate(
                "() => Object.fromEntries(Array.from(document.querySelectorAll("
                "'#quadrant-quadrant_table table tbody tr')).map(tr => ["
                "tr.querySelector('td:nth-child(2)')?.textContent?.trim(),"
                "tr.querySelector('td:last-child')?.textContent?.trim()]))"
            )

        before = await quadrant_by_id()
        # Toggle the split radio to "median"
        ok = await page.evaluate(
            "() => { const r = document.querySelector("
            "'#quadrant-split input[value=\"median\"]');"
            " if (!r) return false; r.click();"
            " r.dispatchEvent(new Event('change', {bubbles: true})); return true; }"
        )
        assert ok, "#quadrant-split median radio not found"
        # Poll until D001's quadrant cell actually changes (avoids a fixed-sleep
        # race / vacuous pass); `before["D001"]` is passed in as the JS arg.
        await page.wait_for_function(
            "(prev) => { const rows = document.querySelectorAll("
            "'#quadrant-quadrant_table table tbody tr');"
            " for (const tr of rows) {"
            "   if (tr.querySelector('td:nth-child(2)')?.textContent?.trim() === 'D001')"
            "     return tr.querySelector('td:last-child')?.textContent?.trim() !== prev;"
            " } return false; }",
            arg=before["D001"], timeout=30000,
        )
        after = await quadrant_by_id()
        print(f"D001 mean={before.get('D001')} median={after.get('D001')}")
        assert before.get("D001") and after.get("D001"), "D001 row not found"
        assert before["D001"] != after["D001"], \
            f"D001 quadrant did not change on median split: {before.get('D001')}"

        await page.screenshot(path="tests/screenshots/quadrant.png")
        print("\nquadrant e2e assertions pass")
        await browser.close()


asyncio.run(main())
