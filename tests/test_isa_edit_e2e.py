"""E2E for the ISA entry edit panels (P1b, spec §6.2): an element's indicator
fields are saved and shown again, a Responses element has no indicator
inputs, and a connection's description is saved. Selectors are namespaced
(#entry-...), since every panel lives in one DOM.
"""
import asyncio
import re

from playwright.async_api import async_playwright


async def _click_row(page, table: str, *patterns: str):
    """Click the row whose leading cells match `patterns`; it alone ends up selected."""
    rows = page.locator(f"#{table} tbody tr")
    for i, pattern in enumerate(patterns, start=1):
        rows = rows.filter(has=page.locator(f"td:nth-child({i})", has_text=re.compile(pattern)))
    await rows.first.locator("td").first.click()
    await page.wait_for_timeout(600)
    n = await page.eval_on_selector_all(f"#{table} tbody tr[aria-selected='true']",
                                        "els => els.length")
    assert n == 1, f"#{table}: {n} rows selected"


async def _bound_click(page, el_id: str):
    """A button inside an output_ui: click it only once Shiny has bound it."""
    await page.wait_for_selector(f"#{el_id}.shiny-bound-input", state="attached",
                                 timeout=30000)
    await page.click(f"#{el_id}")


async def _value(page, el_id: str, want: str, timeout_ms=15000):
    for _ in range(timeout_ms // 500):
        el = await page.query_selector(f"#{el_id}")
        if el and await el.input_value() == want:
            return
        await page.wait_for_timeout(500)
    raise AssertionError(f"#{el_id} never held {want!r}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#sespy_nav_entry", timeout=60000)
        await page.click("#sespy_nav_entry")
        await page.wait_for_function(
            "() => { const el = document.querySelector("
            "  \".tab-content > .tab-pane[data-value='entry']\");"
            " return !!el && el.classList.contains('active'); }", timeout=30000)
        await page.wait_for_selector("#entry-elements_table tbody tr", timeout=30000)
        mpf1 = r"^\s*MPF1\s*$"

        # 1. MPF1's indicator and unit are saved and shown again
        await _click_row(page, "entry-elements_table", mpf1)
        await page.click("#entry-edit_element")
        await page.wait_for_selector("#entry-el_indicator", state="visible", timeout=30000)
        await page.fill("#entry-el_indicator", "Shoot density")
        await page.fill("#entry-el_indicator_unit", "shoots/m2")
        await _bound_click(page, "entry-save_element")
        await page.wait_for_selector("#entry-el_indicator", state="detached", timeout=30000)
        await _click_row(page, "entry-elements_table", mpf1)
        await page.click("#entry-edit_element")
        await _value(page, "entry-el_indicator", "Shoot density")
        await _value(page, "entry-el_indicator_unit", "shoots/m2")
        await _bound_click(page, "entry-cancel_element")
        await page.wait_for_selector("#entry-el_indicator", state="detached", timeout=30000)
        print("1. element: indicator and unit saved and shown again - PASS")

        # 2. a Responses element has no indicator inputs
        await _click_row(page, "entry-elements_table", r"^\s*R001\s*$")
        await page.click("#entry-edit_element")
        await _value(page, "entry-el_label", "MPA enforcement")      # re-rendered for R001
        assert await page.query_selector("#entry-el_indicator") is None, "R001 shows indicators"
        await _bound_click(page, "entry-cancel_element")
        print("2. responses element: no indicator inputs - PASS")

        # 3. the D001 -> A001 connection's description
        d001_a001 = (r"^\s*D001\b", r"^\s*A001\b")
        await _click_row(page, "entry-connections_table", *d001_a001)
        await page.click("#entry-edit_connection")
        await page.wait_for_selector("#entry-conn_description", state="visible", timeout=30000)
        await page.fill("#entry-conn_description", "Visitors bring boats")
        await _bound_click(page, "entry-save_connection")
        await page.wait_for_selector("#entry-conn_description", state="detached", timeout=30000)
        await _click_row(page, "entry-connections_table", *d001_a001)
        await page.click("#entry-edit_connection")
        await _value(page, "entry-conn_description", "Visitors bring boats")
        print("3. connection: description saved and shown again - PASS")

        print("\nisa edit e2e: all assertions passed")
        await browser.close()


asyncio.run(main())
