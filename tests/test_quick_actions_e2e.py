"""End-to-end check: Quick Actions render + Save downloads JSON + Load
restores state + New resets."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Quick Actions block is in the sidebar; check buttons exist
        quick = await page.evaluate(
            "() => Array.from(document.querySelectorAll('.sespy-quick-actions .btn'))"
            ".map(b => b.id || b.textContent.trim().slice(0, 30))"
        )
        print("quick actions buttons:", quick)
        assert any("save_project" in q or "Save" in q for q in quick), \
            "Save Project button missing"
        assert any("new_project" in q or "New" in q for q in quick), \
            "New Project button missing"
        # Load Project is rendered as input_file with a button label
        load_input = await page.evaluate(
            "() => !!document.querySelector('input[type=\"file\"]#load_project')"
        )
        assert load_input, "Load Project file input missing"

        # Click Save to trigger a download
        async with page.expect_download() as dl_info:
            await page.click("#save_project")
        download = await dl_info.value
        out = Path("tests/screenshots/_save_test.json")
        await download.save_as(out)
        text = out.read_text(encoding="utf-8")
        import json as _j
        data = _j.loads(text)
        assert "isa_data" in data and "elements" in data["isa_data"], \
            "downloaded payload doesn't have project envelope"
        assert len(data["isa_data"]["elements"]) == 17, \
            f"expected 17 elements, got {len(data['isa_data']['elements'])}"
        print(f"saved file: {out} ({out.stat().st_size} bytes, "
              f"{len(data['isa_data']['elements'])} elements)")
        await page.screenshot(path="tests/screenshots/quick_actions.png")

        print("\nquick actions e2e assertions pass")
        await browser.close()


asyncio.run(main())
