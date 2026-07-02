"""E2E: a USER OVERRIDE in the DAPSIWRM mapping table reaches the CLD.

Complements test_qsem_map_e2e (which commits with heuristic defaults only). Here
we change one select before committing, exercising the real dynamic-input read
path (`input[map_{seq}_{i}]()` in _on_commit -> resolve_theme_map). We override
the "LWB" theme — which the heuristic leaves UNTYPED — to "Drivers", a type the
heuristic can NEVER produce for Food_web_V_01. So "Drivers" appearing as a CLD
node group proves the override (not the heuristic, not the default sample) drove
the typing.
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

MODEL = Path(
    r"C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\NiD4OCEAN"
    r"\DST\social ecological system map\Social ecological systems map\Food_web_V_01.qsem"
)


async def main():
    if not MODEL.exists():
        print("model absent — skip")
        return
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.click("#sespy_nav_import")
        await pg.wait_for_timeout(1500)
        await pg.set_input_files("#import-xlsx", str(MODEL))
        await pg.wait_for_selector("#import-commit:not([disabled])", timeout=15000)
        await pg.check("#import-assign_dapsiwrm")
        await pg.wait_for_selector("#import-dapsiwrm_map select", timeout=10000)

        # Override the LWB row's select (heuristic default: "" untyped) -> Drivers.
        lwb_select = pg.locator("#import-dapsiwrm_map tr", has_text="LWB").locator("select")
        await lwb_select.select_option("Drivers")
        await pg.wait_for_timeout(800)  # let the changed value round-trip to the server

        await pg.click("#import-commit")
        await pg.wait_for_selector(".shiny-notification", timeout=15000)
        await pg.click("#sespy_nav_cld")
        await pg.wait_for_selector("#cld-network", timeout=30000)
        result = None
        for _ in range(60):
            result = await pg.evaluate(
                "() => { const s=window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s||!s.nodes) return null;"
                " const nodes=s.nodes.get();"
                " return {count: nodes.length,"
                "         groups: Array.from(new Set(nodes.map(n => n.group)))}; }"
            )
            if result and result["count"] == 94:
                break
            await pg.wait_for_timeout(500)
        print("cld result:", result)
        assert result is not None and result["count"] == 94, (
            f"imported model did not reach CLD (expected 94 nodes): {result}"
        )
        groups = set(result["groups"])
        # "Drivers" can ONLY be present because the LWB override was read on commit.
        assert "Drivers" in groups, (
            f"user override (LWB->Drivers) did not reach the CLD: groups={sorted(groups)}"
        )
        print("qsem-map override e2e assertions pass")
        await b.close()


asyncio.run(main())
