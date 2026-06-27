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
        await page.wait_for_selector(".sespy-stepper-item", timeout=20000)

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
        await page.wait_for_timeout(900)
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
        assert len(active) == 1 and active[0]["step"] == "analyze"
        print(f"\nafter Loop Analysis click: active = {active[0]['step']} ✓")

        await page.screenshot(path="tests/screenshots/stepper_analyze.png")
        await page.click("#sespy_nav_cld")
        await page.wait_for_timeout(900)
        await page.screenshot(path="tests/screenshots/stepper_visualize.png")

        print("\nstepper assertions pass")
        await browser.close()


asyncio.run(main())
