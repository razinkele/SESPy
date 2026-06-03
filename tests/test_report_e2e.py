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
        await page.click("#sespy_nav_report")
        await page.wait_for_timeout(2500)

        # Verify the iframe preview rendered — check srcdoc length, more
        # reliable than reaching into contentDocument via playwright.
        preview_srcdoc_len = await page.evaluate(
            "() => document.querySelector('#report-report_preview iframe')"
            "?.getAttribute('srcdoc')?.length || 0"
        )
        print(f"preview iframe srcdoc length: {preview_srcdoc_len}")
        assert preview_srcdoc_len > 1000, "preview srcdoc didn't render"

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
