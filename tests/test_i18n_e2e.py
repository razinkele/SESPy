"""End-to-end check: switching the language updates nav + stepper labels live."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        en_labels = await page.eval_on_selector_all(
            ".sespy-nav-btn span:not(.sespy-nav-icon)",
            "els => els.map(e => e.textContent.trim())",
        )
        en_steps = await page.eval_on_selector_all(
            ".sespy-stepper-item",
            "els => els.map(e => e.textContent.trim())",
        )
        print("en nav   :", en_labels)
        print("en steps :", en_steps)
        assert "CLD Visualization" in en_labels
        assert any("Get Started" in s for s in en_steps)

        # Switch to Spanish via the language switcher select
        await page.evaluate("""() => {
          const sel = document.getElementById('__sespy_language__');
          if (sel) { sel.value = 'es'; sel.dispatchEvent(new Event('change', {bubbles: true})); }
        }""")
        await page.wait_for_timeout(1500)

        es_labels = await page.eval_on_selector_all(
            ".sespy-nav-btn span:not(.sespy-nav-icon)",
            "els => els.map(e => e.textContent.trim())",
        )
        es_steps = await page.eval_on_selector_all(
            ".sespy-stepper-item",
            "els => els.map(e => e.textContent.trim())",
        )
        print("es nav   :", es_labels)
        print("es steps :", es_steps)
        assert "Visualización CLD" in es_labels, f"Spanish nav label not found: {es_labels}"
        assert any("Comenzar" in s for s in es_steps), f"Spanish stepper not found: {es_steps}"

        await page.screenshot(path="tests/screenshots/i18n_es.png")
        print("\ni18n e2e assertions pass — labels switched to Spanish on lang change")
        await browser.close()


asyncio.run(main())
