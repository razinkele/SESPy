"""E2E for Templates: panel renders, clicking a template loads it,
analysis modules see the new data."""
import asyncio

from playwright.async_api import async_playwright

TARGET = "Coastal Tourism SES"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#sespy_nav_templates", timeout=60000)

        # Click Templates nav
        await page.click("#sespy_nav_templates")
        # templates_list is a suspended @render.ui inside the hidden pane: its
        # first render (list_catalogue() + list_templates()) begins at this nav
        # click, so wait for the cards instead of sleeping. Shiny swaps an
        # output_ui's innerHTML atomically, so once one h5 is present the whole
        # list is present.
        await page.wait_for_selector("#templates-templates_list h5", timeout=60000)

        # Every h5 in the list is a card name (group headers are h4), in the
        # order of the load_template_<i> buttons: the 7 MarineSABRES templates
        # first, then SESPy's 4 examples.
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        print("templates listed:", cards)
        assert len(cards) == 11, f"expected 7 + 4 templates, got {cards}"
        # Exact names: R's "Offshore Wind Energy (MarineSABRES)" also contains
        # "Offshore Wind", so a substring check would prove nothing.
        assert "Offshore Wind Farm SES" in cards, f"Offshore Wind Farm SES missing: {cards}"
        assert TARGET in cards, f"{TARGET} missing: {cards}"

        # Load the Coastal Tourism SES card, found by its exact h5 text (index
        # 0 is now the Caribbean MarineSABRES template).
        idx = cards.index(TARGET)
        # The h5s render before Shiny binds the buttons; an unbound click is lost.
        await page.wait_for_selector(f"#templates-load_template_{idx}.shiny-bound-input", timeout=15000)
        await page.click(f"#templates-load_template_{idx}")
        # The load can only be proven by its own success toast. Coastal
        # Tourism SES (sespy/templates/coastal_tourism.json) is graph-identical
        # to the seeded sample (same 17 element ids/labels, 20 connections),
        # so NO CLD node count can distinguish "loaded" from "never loaded",
        # and .shiny-notification alone is shared with the autosave
        # "Recovered work" banner. Match the interpolated template name in
        # parentheses: templates.py builds t("templates.loaded") + f" ({info.name})"
        # only on the success path (the except branch's message is
        # f"Couldn't load template: {e}" and never carries the name), and
        # matching the name rather than the translated sentence keeps this
        # language-independent.
        await page.wait_for_function(
            """(name) => Array.from(document.querySelectorAll('.shiny-notification'))
              .some(n => (n.textContent || '').includes('(' + name + ')'))""",
            arg=TARGET,
            timeout=30000,
        )

        # Sanity check only (the toast above is the proof): the CLD still
        # shows 17 nodes, as it would for the seeded sample.
        await page.click("#sespy_nav_cld")
        n = None
        for _ in range(30):
            n = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if n == 17:
                break
            await page.wait_for_timeout(500)
        print(f"CLD nodes after template load: {n}")
        assert n == 17, f"CLD should show 17 nodes after loading Coastal Tourism SES: {n}"

        await page.screenshot(path="tests/screenshots/templates.png")
        print("\ntemplates e2e assertions pass")
        await browser.close()


asyncio.run(main())
