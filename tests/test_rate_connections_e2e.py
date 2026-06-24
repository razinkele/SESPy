"""E2E for Rate Connections (QSEM-C2): add a stakeholder, rate a connection,
assert the connection row reflects the new rating (#ratings -> 1, mine -> check)."""
import asyncio
from playwright.async_api import async_playwright

# Verified DataGrid selection idiom (test_stakeholders_e2e.py): click a TD cell,
# not the TR — only a TD click sets aria-selected and propagates to cell_selection.
RATE_ROW = "#rate-connections_table table tbody tr:first-child td:first-child"


async def _set_select(page, el_id: str, value: str):
    """Drive a Shiny <select> via el.value + change event (repo's proven pattern,
    test_stakeholders_e2e.py)."""
    await page.evaluate(
        """([id, v]) => { const el = document.getElementById(id);
          if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); } }""",
        [el_id, value],
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # 1. Add one stakeholder (pattern from tests/test_stakeholders_e2e.py:95-97).
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_selector("#stakeholders-sh_name", timeout=30000)
        await page.fill("#stakeholders-sh_name", "Port Authority")
        await _set_select(page, "stakeholders-sh_type", "government")  # REQUIRED: save guard rejects blank type
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # 2. Go to Rate Connections.
        await page.click("#sespy_nav_rate")
        await page.wait_for_selector("#rate-connections_table table tbody tr", timeout=30000)
        await page.wait_for_selector("#rate-rater", timeout=30000)  # picker present (register non-empty)

        # 3. Select the first connection row (click a TD — not the TR — per RATE_ROW).
        await page.click(RATE_ROW)
        await page.wait_for_selector("#rate-save_rating", timeout=30000)  # editor rendered

        # 4. Set a rating and save.
        await page.evaluate(
            "() => { const s=document.getElementById('rate-ed_strength');"
            " if(s){ s.value='strong'; s.dispatchEvent(new Event('change',{bubbles:true})); } }"
        )
        await page.click("#rate-save_rating")

        # 5. Assert the first row's #ratings cell became 1 (poll the re-render).
        ok = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if cells and "1" in cells:
                ok = True
                break
        assert ok, f"connection row did not reflect the saved rating: {cells}"
        print("rate connections save: OK")
        await browser.close()


asyncio.run(main())
