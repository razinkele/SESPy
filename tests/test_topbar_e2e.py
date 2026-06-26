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
        await pg.click("#tb_about")
        await pg.wait_for_selector(".modal", timeout=10000)
        body = await pg.text_content(".modal") or ""
        assert "Overview" in body and "Changelog" in body, body[:120]
        # dismiss any notification that might block the Close button, then close modal
        await pg.evaluate("document.getElementById('shiny-notification-panel') && (document.getElementById('shiny-notification-panel').style.display='none')")
        await pg.click(".modal .btn-default, .modal button:has-text('Close')")
        print("topbar about: OK")
        await pg.click("#tb_options")
        await pg.wait_for_selector(".modal #theme_select", timeout=10000)
        # pick Deep Ocean → data-theme applied
        await pg.click(".modal input[value='deep-ocean']")
        ok = False
        for _ in range(20):
            await pg.wait_for_timeout(300)
            dt = await pg.get_attribute("html", "data-theme")
            if dt == "deep-ocean":
                ok = True; break
        assert ok, "data-theme not applied"
        print("topbar options/theme: OK")
        # close options modal and wait for it to fully disappear
        await pg.click(".modal button:has-text('Close')")
        await pg.wait_for_selector(".modal", state="hidden", timeout=10000)
        await pg.wait_for_timeout(300)
        # Help modal opens and shows workflow text
        await pg.click("#tb_help")
        await pg.wait_for_selector(".modal", timeout=10000)
        body = await pg.text_content(".modal") or ""
        assert "workflow" in body.lower() or "create" in body.lower(), f"workflow text missing: {body[:200]}"
        print("topbar help: OK")
        await b.close()

asyncio.run(main())
