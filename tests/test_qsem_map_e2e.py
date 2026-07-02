"""E2E: QSEM import with DAPSIWRM assignment -> CLD gets typed (coloured) nodes."""
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
        # tick "Assign DAPSIWRM types"
        await pg.check("#import-assign_dapsiwrm")
        await pg.wait_for_selector("#import-dapsiwrm_map select", timeout=10000)
        await pg.click("#import-commit")
        # go to CLD, wait for the network, assert DAPSIWRM groups present
        await pg.click("#sespy_nav_cld")
        await pg.wait_for_selector("#cld-network", timeout=30000)
        groups = None
        for _ in range(30):
            groups = await pg.evaluate(
                "() => { const s=window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s||!s.nodes) return null;"
                " return Array.from(new Set(s.nodes.get().map(n => n.group))); }"
            )
            if groups and any(g and g != "" for g in groups):
                break
            await pg.wait_for_timeout(500)
        print("cld groups:", groups)
        assert groups is not None, "cld-network not readable"
        assert any(g in ("Activities", "Pressures", "Marine Processes & Functioning",
                         "Responses", "Ecosystem Services", "Goods & Benefits", "Drivers")
                   for g in groups), f"no DAPSIWRM groups after mapping: {groups}"
        print("qsem-map e2e assertions pass")
        await b.close()


asyncio.run(main())
