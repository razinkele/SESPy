"""End-to-end check: switching the language updates nav + stepper labels live."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # Nav + stepper are reactive @render.ui outputs; wait for them rather
        # than racing a fixed sleep (cold first render can exceed 1.5s headless/CI).
        await page.wait_for_selector(".sespy-nav-btn", timeout=60000)
        await page.wait_for_selector(".sespy-stepper-item", timeout=60000)

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

        # Switch to Spanish via the language switcher inside the Options modal
        await page.click("#tb_options")
        # 30 s, not 10 s: opening a topbar modal is a websocket round-trip, and
        # this script runs mid-batch when the server is busy. The identical
        # 10 s wait on the feedback modal flaked three gates running before it
        # was raised (bbe4f62); this one was caught by the runner's attempt-1
        # diagnostic on 2026-09-14 — "Timeout 10000ms exceeded ... waiting for
        # locator('.modal #__sespy_language__') to be visible", retry passed.
        await page.wait_for_selector(".modal #__sespy_language__", timeout=30000)
        await page.select_option(".modal #__sespy_language__", "es")
        # Selecting in the <select> only fires a client-side change event; the
        # visible effect is a websocket round-trip — `_switch_language`
        # (sespy/dashboard.py:421-426) writes translator.language, which
        # invalidates BOTH `sespy_nav_render` and `sespy_stepper_render`. A
        # fixed sleep is the only guard on that round-trip, so poll for the
        # translated text instead. The asserts below are unchanged: a genuine
        # i18n regression still fails with the labels it actually saw.
        for _ in range(120):   # up to 60 s, same budget as the first-render waits
            nav_ok = "Visualización CLD" in await page.eval_on_selector_all(
                ".sespy-nav-btn span:not(.sespy-nav-icon)",
                "els => els.map(e => e.textContent.trim())",
            )
            step_ok = any("Comenzar" in s for s in await page.eval_on_selector_all(
                ".sespy-stepper-item",
                "els => els.map(e => e.textContent.trim())",
            ))
            if nav_ok and step_ok:
                break
            await page.wait_for_timeout(500)

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
