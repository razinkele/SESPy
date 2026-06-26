import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        # all four topbar buttons present (root-scoped ids, no module prefix)
        for bid in ("tb_feedback", "tb_about", "tb_options", "tb_help"):
            await pg.wait_for_selector(f"#{bid}", timeout=30000)
        # Feedback opens + submit records + notification
        await pg.click("#tb_feedback")
        await pg.wait_for_selector(".modal #fb_message", timeout=10000)
        await pg.fill("#fb_message", "e2e feedback check")
        await pg.click("#fb_submit")
        await pg.wait_for_selector(".shiny-notification", timeout=10000)
        print("topbar feedback: OK")
        await b.close()

asyncio.run(main())
