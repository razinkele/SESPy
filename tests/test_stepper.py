"""Verify the workflow stepper renders + tracks active panel changes."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # Stepper is a reactive @render.ui output; wait for it rather than a
        # fixed sleep (cold first render can exceed 1.5s headless/CI).
        await page.wait_for_selector(".sespy-stepper-item", timeout=60000)

        # On the default "cld" panel, "visualize" should be active.
        states = await page.evaluate("""() => {
          const items = Array.from(document.querySelectorAll('.sespy-stepper-item'));
          return items.map(el => ({
            step: el.getAttribute('data-step'),
            label: el.textContent.trim(),
            state: el.classList.contains('active') ? 'active'
                 : el.classList.contains('completed') ? 'completed'
                 : 'future',
          }));
        }""")
        print("on CLD panel:")
        for s in states:
            print(f"  {s['state']:9s} {s['step']:10s} {s['label']}")
        active = [s for s in states if s["state"] == "active"]
        completed = [s for s in states if s["state"] == "completed"]
        assert len(active) == 1 and active[0]["step"] == "visualize"
        # `setup` is first since PIMS Project Setup landed (commit 0c3d1a5).
        assert {s["step"] for s in completed} == {"setup", "start", "create"}

        # Click Loop Analysis -> stepper should jump to "analyze"
        await page.click("#sespy_nav_loops")
        # The nav click is a full server round-trip (dashboard.py
        # _wire_nav_button -> _goto -> ui.update_navs) that re-renders the
        # stepper @render.ui output and un-suspends the Loop Analysis panel's
        # outputs. Poll for the re-render instead of a fixed sleep. This loop
        # never raises, so the assert below still reports what it found.
        for _ in range(60):  # up to 30s
            if await page.evaluate(
                "() => { const el = document.querySelector('.sespy-stepper-item.active');"
                " return !!el && el.getAttribute('data-step') === 'analyze'; }"
            ):
                break
            await page.wait_for_timeout(500)
        states = await page.evaluate("""() => {
          const items = Array.from(document.querySelectorAll('.sespy-stepper-item'));
          return items.map(el => ({
            step: el.getAttribute('data-step'),
            state: el.classList.contains('active') ? 'active'
                 : el.classList.contains('completed') ? 'completed'
                 : 'future',
          }));
        }""")
        active = [s for s in states if s["state"] == "active"]
        assert len(active) == 1 and active[0]["step"] == "analyze", (
            f"expected exactly one active step 'analyze', got {active}"
        )
        print(f"\nafter Loop Analysis click: active = {active[0]['step']} ✓")

        await page.screenshot(path="tests/screenshots/stepper_analyze.png")
        await page.click("#sespy_nav_cld")
        # Same full server round-trip as the loops click; poll so the
        # screenshot below cannot silently capture the "analyze" stepper
        # under the stepper_visualize.png name.
        back: list[str] = []
        for _ in range(60):  # up to 30s
            back = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'.sespy-stepper-item.active')).map(e => e.getAttribute('data-step'))"
            )
            if back == ["visualize"]:
                break
            await page.wait_for_timeout(500)
        assert back == ["visualize"], (
            f"expected active step 'visualize' after the CLD nav click, got {back}"
        )
        await page.screenshot(path="tests/screenshots/stepper_visualize.png")

        print("\nstepper assertions pass")
        await browser.close()


asyncio.run(main())
