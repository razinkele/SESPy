"""E2E for P1a link rules in ISA entry (Edit Data): the empty first picker
choice, the polarity prefill from the rule table, and the off-rule note.

Starts from the default sample project (data/sample_ses.json, loaded at
startup): 17 elements, 20 connections. Module id is "entry" (app.py:140), so
every selector is namespaced and scoped (no bare text= selectors).
"""
import asyncio

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"
SRC, TGT = "#entry-new_source", "#entry-new_target"
NOTE = "#entry-off_rule_note .sespy-off-rule-note"
MINUS = 'input[name="entry-new_polarity"][value="-"]:checked'
PLUS = 'input[name="entry-new_polarity"][value="+"]:checked'


async def wait_connections(page, n: int) -> None:
    # Pickers re-render to "" after Add, so the save is proved by the count.
    await page.wait_for_function(
        "n => (document.getElementById('entry-status_line')?.textContent || '')"
        ".includes(n + ' connections')", arg=n, timeout=30000)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        # The nav is server-rendered (cold server ~32 s idle; more under load).
        await page.wait_for_selector("#sespy_nav_entry", timeout=60000)
        await page.click("#sespy_nav_entry")
        await page.wait_for_selector(SRC, timeout=30000)
        await page.wait_for_selector(TGT, timeout=30000)
        await wait_connections(page, 20)

        # ---- default state: both pickers on the empty choice, no note ------
        assert await page.input_value(SRC) == "", "source picker not on the empty choice"
        assert await page.input_value(TGT) == "", "target picker not on the empty choice"
        assert await page.locator(NOTE).count() == 0, "note shown in the default state"
        print("default state: empty pickers, no note")

        # ---- only a source: no note --------------------------------------
        await page.select_option(SRC, "P001")
        await page.wait_for_timeout(1500)
        assert await page.locator(NOTE).count() == 0, "note shown with only a source"
        print("only a source: no note")

        # ---- P -> MPF on a free pair prefills "-" and saves ----------------
        # (P001->MPF1, P002->MPF2 and P003->MPF1 already exist in the sample.)
        await page.select_option(TGT, "MPF2")
        await page.wait_for_selector(MINUS, state="attached", timeout=15000)
        assert await page.locator(NOTE).count() == 0, "note shown for a canonical pair"
        await page.click("#entry-add_connection")
        await wait_connections(page, 21)
        print("P001 -> MPF2: polarity prefilled '-', saved (21 connections)")

        # ---- D -> GB is off-rule: note shown, still saves ------------------
        await page.wait_for_function(
            "() => document.getElementById('entry-new_source')?.value === ''",
            timeout=15000)
        await page.select_option(SRC, "D001")
        await page.select_option(TGT, "GB01")
        await page.wait_for_selector(NOTE, timeout=15000)
        text = (await page.locator(NOTE).text_content()) or ""
        assert "Drivers" in text and "Goods & Benefits" in text, text
        # The radio still shows "-" from the previous add until the seed lands.
        await page.wait_for_selector(PLUS, state="attached", timeout=15000)
        await page.click("#entry-add_connection")
        await wait_connections(page, 22)
        print("D001 -> GB01: off-rule note shown, polarity '+', saved (22 connections)")

        await browser.close()
        print("link-rules e2e: all assertions passed")


asyncio.run(main())
