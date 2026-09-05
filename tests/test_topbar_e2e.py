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
        # Manual tab (v1.8.0): rendered docs/MANUAL.md with images that load.
        assert "Manual" in body, body[:120]
        await pg.click(".modal .nav-link:has-text('Manual')")
        await pg.wait_for_selector(".modal h1:has-text('SESPy User Manual')", timeout=10000)
        await pg.wait_for_selector(".modal h2:has-text('CLD Visualization')", timeout=10000)
        loaded = await pg.evaluate(
            "() => { const i = document.querySelector('.modal img'); "
            "return i ? (i.complete && i.naturalWidth > 0) : null; }")
        for _ in range(20):
            if loaded:
                break
            await pg.wait_for_timeout(500)
            loaded = await pg.evaluate(
                "() => { const i = document.querySelector('.modal img'); "
                "return i ? (i.complete && i.naturalWidth > 0) : null; }")
        assert loaded is True, f"first manual image did not load (state={loaded!r})"
        print("topbar about manual: OK")
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
                ok = True
                break
        assert ok, "data-theme not applied"
        print("topbar options/theme: OK")
        # close options modal and wait for it to fully disappear
        await pg.click(".modal button:has-text('Close')")
        await pg.wait_for_selector(".modal", state="hidden", timeout=10000)
        await pg.wait_for_timeout(300)
        # Help modal opens and shows workflow text
        await pg.click("#tb_help")
        # v1.9.0: Help is an offcanvas side panel, not a modal. It carries the
        # workflow paragraph and the manual section for the ACTIVE panel (the
        # app opens on CLD Visualization).
        await pg.wait_for_selector("#tb_help_panel.offcanvas.show", timeout=10000)
        # text_content, not inner_text: Shiny gives the output container
        # `display: contents` and Chromium's innerText skips such subtrees.
        body = ""
        for _ in range(20):
            body = await pg.text_content("#tb_help_panel") or ""
            if "CLD Visualization" in body and "Purpose" in body:
                break
            await pg.wait_for_timeout(500)
        assert "workflow" in body.lower() or "create" in body.lower(), f"workflow text missing: {body[:200]}"
        assert "CLD Visualization" in body and "Purpose" in body, f"contextual section missing: {body[:300]}"
        # The panel must not cover the analysis: the CLD canvas stays visible.
        assert await pg.is_visible("#cld-network") or await pg.is_visible("[id^=cld-]"), "analysis hidden behind help panel"
        await pg.click("#tb_help_panel .btn-close")
        await pg.wait_for_selector("#tb_help_panel.offcanvas.show", state="detached", timeout=10000)
        # Closing must clear the section (no hidden manual text left on the
        # page — bare text= selectors elsewhere would match it).
        left = "x"
        for _ in range(20):
            left = (await pg.text_content("#tb_help_section") or "").strip()
            if left == "":
                break
            await pg.wait_for_timeout(250)
        assert left == "", f"help section not cleared on close: {left[:80]!r}"
        print("topbar help: OK")
        await b.close()

asyncio.run(main())
