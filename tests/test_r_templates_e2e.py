"""E2E for P2: the MarineSABRES template group in the Templates panel.

Both group headers render with namespaced ids, the "Offshore Wind Energy
(MarineSABRES)" card shows its badges, Load shows the success toast with its
name, and the CLD then shows exactly 23 nodes. The seeded sample already has
17, so polling for n > 0 would prove nothing; OffshoreWind is the only
template with 23 elements, and the CLD shows every DAPSI(W)R(M) type by
default. Namespaced ids only, no bare text= selectors.
"""
import asyncio

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"
LIST = "#templates-templates_list"
NAME = "Offshore Wind Energy (MarineSABRES)"
BADGES = ["Energy", "Complex", "v2.2", "North Sea"]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        # The nav is server-rendered (cold server ~32 s idle; more under load).
        await page.wait_for_selector("#sespy_nav_templates", timeout=60000)
        await page.click("#sespy_nav_templates")
        await page.wait_for_selector(f"{LIST} h5", timeout=60000)

        # ---- both groups, MarineSABRES first ---------------------------------
        await page.wait_for_selector("#templates-group_marinesabres", state="visible", timeout=15000)
        await page.wait_for_selector("#templates-group_sespy", state="visible", timeout=15000)
        order = await page.evaluate(
            """() => {
              const a = document.getElementById('templates-group_marinesabres');
              const b = document.getElementById('templates-group_sespy');
              return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
            }""")
        assert order, "MarineSABRES group should come before SESPy examples"
        print("group headers: MarineSABRES templates, SESPy examples")

        # ---- the Offshore Wind Energy card and its badges --------------------
        cards = await page.evaluate(
            f"() => Array.from(document.querySelectorAll('{LIST} h5'))"
            ".map(e => e.textContent.trim())")
        assert cards.count(NAME) == 1, cards
        idx = cards.index(NAME)
        badges = await page.evaluate(
            """([list, name]) => {
              const h5 = Array.from(document.querySelectorAll(list + ' h5'))
                .find(e => e.textContent.trim() === name);
              const row = h5 && h5.parentElement.querySelector('.sespy-template-badges');
              return row ? Array.from(row.querySelectorAll('.badge'))
                .map(b => b.textContent.trim()) : null;
            }""", [LIST, NAME])
        assert badges == BADGES, badges
        print(f"card {idx}: {NAME} badges {badges}")

        # ---- Load: toast with the name, then exactly 23 CLD nodes ------------
        # The h5s render before Shiny binds the buttons; an unbound click is lost.
        await page.wait_for_selector(f"#templates-load_template_{idx}.shiny-bound-input", timeout=15000)
        await page.click(f"#templates-load_template_{idx}")
        await page.wait_for_function(
            """(name) => Array.from(document.querySelectorAll('.shiny-notification'))
              .some(n => (n.textContent || '').includes('(' + name + ')'))""",
            arg=NAME, timeout=30000)
        print("toast names the template")

        await page.click("#sespy_nav_cld")
        n = None
        for _ in range(60):
            n = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if n == 23:
                break
            await page.wait_for_timeout(500)
        assert n == 23, f"CLD should show the template's 23 elements, got {n}"
        print("CLD shows 23 nodes")

        await browser.close()
        print("r-templates e2e: all assertions passed")


asyncio.run(main())
