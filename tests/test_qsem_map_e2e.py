"""E2E: QSEM import with DAPSIWRM assignment -> CLD gets typed (coloured) nodes."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

MODEL = Path(
    r"C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\NiD4OCEAN"
    r"\DST\social ecological system map\Social ecological systems map\Food_web_V_01.qsem"
)

V01_EXPECTED = {
    "Activities",
    "Responses",
    "Pressures",
    "Marine Processes & Functioning",
    "Ecosystem Services",
}
IMPOSSIBLE = {"Drivers", "Goods & Benefits"}


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
        # tick "Assign DAPSIWRM types"
        await pg.check("#import-assign_dapsiwrm")
        await pg.wait_for_selector("#import-dapsiwrm_map select", timeout=10000)
        await pg.click("#import-commit")
        # post-commit barrier — notification only fires on successful commit
        await pg.wait_for_selector(".shiny-notification", timeout=15000)
        # go to CLD, wait for the network
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
        assert V01_EXPECTED <= groups, (
            f"expected DAPSIWRM subset missing from CLD: {V01_EXPECTED - groups}"
        )
        assert not (IMPOSSIBLE & groups), (
            f"impossible groups present (still showing default sample?): {IMPOSSIBLE & groups}"
        )
        print("qsem-map e2e assertions pass")
        await b.close()


asyncio.run(main())
