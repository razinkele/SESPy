"""E2E for the Report Export module: tab renders, HTML download fires,
PDF download fires."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Click Export Report nav (last nav)
        # The nav is a @render.ui output: it does not exist until the
        # session's first flush (32 s on an idle machine, more under
        # load). Without this the click falls back to Playwright's 30 s
        # default and races startup.
        await page.wait_for_selector("#sespy_nav_report", timeout=60000)
        await page.click("#sespy_nav_report")
        # The Export Report pane is hidden at startup (app.py initial="cld"),
        # so report_preview is a SUSPENDED output: its first render only starts
        # at the nav click above, and render_html() runs feedback_loops +
        # classify_loops + 5 centrality metrics + leverage_scores first. Poll
        # instead of sleeping, and check the project's own content: the report
        # template's <style> block alone clears the 1000-char threshold.
        state = {"len": 0, "hasData": False}
        for _ in range(120):                     # up to 60 s, the suite's budget
            state = await page.evaluate(
                "() => { const f = document.querySelector("
                "'#report-report_preview iframe');"
                " const s = f ? (f.getAttribute('srcdoc') || '') : '';"
                " return {len: s.length, hasData: s.includes('Tourism demand')}; }"
            )
            if state["hasData"]:
                break
            await page.wait_for_timeout(500)
        preview_srcdoc_len = state["len"]
        print(f"preview iframe srcdoc length: {preview_srcdoc_len}")
        assert preview_srcdoc_len > 1000, "preview srcdoc didn't render"
        assert state["hasData"], (
            f"preview srcdoc rendered without the project's data "
            f"(len={preview_srcdoc_len})"
        )

        # Trigger HTML download
        async with page.expect_download() as dl_info:
            await page.click("#report-download_html")
        html_download = await dl_info.value
        html_path = Path("tests/screenshots/_report.html")
        await html_download.save_as(html_path)
        text = html_path.read_text(encoding="utf-8")
        assert text.startswith("<!DOCTYPE html>")
        assert "Tourism demand" in text
        print(f"HTML report saved ({html_path.stat().st_size} bytes)")

        # Trigger PDF download
        async with page.expect_download() as dl_info:
            await page.click("#report-download_pdf")
        pdf_download = await dl_info.value
        pdf_path = Path("tests/screenshots/_report.pdf")
        await pdf_download.save_as(pdf_path)
        head = pdf_path.read_bytes()[:4]
        assert head == b"%PDF", f"not a PDF: {head!r}"
        print(f"PDF report saved ({pdf_path.stat().st_size} bytes)")

        await page.screenshot(path="tests/screenshots/report_export.png")
        print("\nreport e2e assertions pass")
        await browser.close()


asyncio.run(main())
