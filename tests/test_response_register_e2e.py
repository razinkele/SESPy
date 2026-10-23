"""E2E for the Response Register page (P1b, spec §6.1): add, edit, impacts,
milestones, delete without cascade, IDs never reused, Edit keeping Target and
EBM code (the echo guard), and the Excel export.

Every panel lives in one DOM, so every selector is namespaced (#responses-...).
"""
import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "tests" / "screenshots"
TABLE = "responses-measures_table"


async def _text(page, el_id: str) -> str:
    el = await page.query_selector(f"#{el_id}")
    return (await el.inner_text()) if el else ""


async def _poll(page, el_id: str, text: str, *, present=True, timeout_ms=15000, step_ms=500):
    for _ in range(timeout_ms // step_ms):
        if (text in await _text(page, el_id)) == present:
            return
        await page.wait_for_timeout(step_ms)
    where = "in" if present else "to leave"
    raise AssertionError(f"timed out waiting for {text!r} {where} #{el_id}")


async def _row_text(page, table: str, first: str) -> str:
    """The text of the row whose first cell is exactly `first` ("" if none)."""
    return await page.evaluate(
        """([t, f]) => {
          for (const r of document.querySelectorAll('#' + t + ' tbody tr')) {
            const c = r.querySelector('td');
            if (c && c.textContent.trim() === f) return r.innerText;
          }
          return '';
        }""", [table, first])


async def _select_only(page, table: str, first: str):
    """Click the row whose first cell is `first`; exactly that row must end up selected."""
    cell = page.locator(f"#{table} tbody tr td:first-child").filter(
        has_text=re.compile(rf"^\s*{re.escape(first)}\s*$"))
    await cell.first.click()
    await page.wait_for_timeout(600)
    picked = await page.eval_on_selector_all(
        f"#{table} tbody tr[aria-selected='true'] td:first-child",
        "els => els.map(e => e.textContent.trim())")
    assert picked == [first], f"#{table}: selected {picked}, wanted [{first!r}]"


async def _value(page, el_id: str, want: str, timeout_ms=15000):
    for _ in range(timeout_ms // 500):
        if await page.input_value(f"#{el_id}") == want:
            return
        await page.wait_for_timeout(500)
    got = await page.input_value(f"#{el_id}")
    raise AssertionError(f"#{el_id} holds {got!r}, wanted {want!r}")


async def _toast(page, *parts: str):
    """A notification whose own text holds every part (a recovery banner may be up)."""
    await page.wait_for_function(
        """(parts) => Array.from(document.querySelectorAll(
             '#shiny-notification-panel .shiny-notification'))
           .some(n => parts.every(p => (n.textContent || '').includes(p)))""",
        arg=list(parts), timeout=30000)


async def _tab(page, value: str):
    await page.click(f"#responses-response_tabs a[data-value='{value}']")
    await page.wait_for_timeout(800)


async def _add(page, name: str, kind_of_measure: str):
    await page.fill("#responses-rm_name", name)
    await page.select_option("#responses-rm_type", kind_of_measure)
    await page.click("#responses-save_measure")


async def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(accept_downloads=True)).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        # 1. nav (a @render.ui output: it exists only after the first flush)
        await page.wait_for_selector("#sespy_nav_responses", timeout=60000)
        await page.click("#sespy_nav_responses")
        await page.wait_for_function(
            "() => { const el = document.querySelector("
            "  \".tab-content > .tab-pane[data-value='responses']\");"
            " return !!el && el.classList.contains('active'); }", timeout=30000)
        await page.wait_for_selector(f"#{TABLE}", state="visible", timeout=30000)
        print("1. nav: #responses-measures_table visible - PASS")

        # 2. two measures
        await _add(page, "No-take zone", "regulatory")
        await _poll(page, TABLE, "RM001")
        await _add(page, "Mooring buoys", "technical")
        await _poll(page, TABLE, "RM002")
        print("2. add: RM001 and RM002 - PASS")

        # 3. Edit changes RM001's status in place
        await _select_only(page, TABLE, "RM001")
        await page.click("#responses-edit_measure")
        await _value(page, "responses-rm_name", "No-take zone")
        await page.select_option("#responses-rm_status", "implemented")
        await page.wait_for_timeout(400)
        await page.click("#responses-save_measure")
        for _ in range(30):
            if "Implemented" in await _row_text(page, TABLE, "RM001"):
                break
            await page.wait_for_timeout(500)
        row = await _row_text(page, TABLE, "RM001")
        assert "Implemented" in row and "No-take zone" in row, row
        print("3. edit: RM001 is Implemented and still RM001 - PASS")

        # 4. an impact and a milestone for RM002
        await _tab(page, "impacts")
        await page.select_option("#responses-impact_response", "RM002")
        await page.select_option("#responses-impact_problem", "specific_pressure")
        await page.click("#responses-add_impact")
        await _poll(page, "responses-impacts_table", "RM002")
        await _tab(page, "milestones")
        await page.select_option("#responses-impl_response", "RM002")
        await page.fill("#responses-impl_milestone", "Consultation")
        await page.click("#responses-add_milestone")
        await _poll(page, "responses-milestones_table", "Consultation")
        print("4. impacts/milestones: one row each for RM002 - PASS")

        # 5. Delete RM002: no cascade, and the toast says what still refers to it
        await _tab(page, "register")
        await _select_only(page, TABLE, "RM002")
        await page.click("#responses-delete_measures")
        await _toast(page, "Deleted response measure(s)", "2 impact or milestone rows still refer")
        await _poll(page, TABLE, "RM002", present=False)
        assert "No-take zone" in await _text(page, TABLE), "RM001 went too"
        print("5. delete: RM002 gone, references reported - PASS")

        # 6. IDs are not reused
        await _add(page, "Seasonal closure", "regulatory")
        await _poll(page, TABLE, "RM003")
        print("6. add after delete: RM003 - PASS")

        # 7. Edit does not rewrite Target or EBM code (its own echo is guarded)
        await page.evaluate(
            "() => { const d = document.getElementById('responses-rm_kind').closest('details');"
            " if (d) d.open = true; }")
        await page.fill("#responses-rm_name", "Output quota")
        await page.select_option("#responses-rm_type", "regulatory")
        await page.select_option("#responses-rm_kind", "measure")
        await page.select_option("#responses-rm_ebm_code", "output")       # waits for the option
        await _value(page, "responses-rm_target", "pressures")              # R's suggestion
        await page.select_option("#responses-rm_target", "state")
        await page.wait_for_timeout(400)
        await page.click("#responses-save_measure")
        await _poll(page, TABLE, "RM004")
        await page.fill("#responses-rm_name", "Port levy")
        await page.select_option("#responses-rm_kind", "instrument")
        await page.select_option("#responses-rm_ebm_code", "1.1")
        await page.wait_for_timeout(400)
        await page.click("#responses-save_measure")
        await _poll(page, TABLE, "RM005")
        await _select_only(page, TABLE, "RM004")
        await page.click("#responses-edit_measure")
        await _value(page, "responses-rm_name", "Output quota")
        await _value(page, "responses-rm_ebm_code", "output")
        await page.wait_for_timeout(1500)                    # let Edit's own echo come back
        await page.select_option("#responses-rm_status", "planned")
        await page.wait_for_timeout(400)
        await page.click("#responses-save_measure")
        for _ in range(30):
            if "Planned" in await _row_text(page, TABLE, "RM004"):
                break
            await page.wait_for_timeout(500)
        row = await _row_text(page, TABLE, "RM004")
        assert "Planned" in row, row
        assert "State" in row and "Pressures" not in row, f"Target rewritten: {row}"
        assert "Output control (e.g. TAC/quota)" in row, f"EBM code rewritten: {row}"
        print("7. edit keeps Target and EBM code - PASS")

        # 8. the Excel export
        await _tab(page, "milestones")
        async with page.expect_download() as dl_info:
            await page.click("#responses-download_response_xlsx")
        download = await dl_info.value
        assert download.suggested_filename.endswith(".xlsx"), download.suggested_filename
        out = SCREENSHOTS / "_responses.xlsx"
        await download.save_as(out)
        assert out.read_bytes()[:4] == b"PK\x03\x04", "not an xlsx file"
        print("8. export: xlsx with valid magic bytes - PASS")

        await page.screenshot(path=str(SCREENSHOTS / "responses.png"))
        print("\nresponse register e2e: all assertions passed")
        await browser.close()


asyncio.run(main())
