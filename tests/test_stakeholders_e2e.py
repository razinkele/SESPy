"""E2E for the PIMS Stakeholders module: add/validate/edit/remove/persist CRUD.

Row-selection discovery (STEP A): Shiny for Python's render.data_frame renders
a native <table> with <tbody> rows carrying data-index and aria-selected
attributes. A real Playwright click on the first <td> of a row sets
aria-selected="true" and propagates the selection to cell_selection()["rows"].
Confirmed working selector: '#stakeholders-stakeholder_table tbody tr td:first-child'
"""
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "tests" / "screenshots"

# Selector that selects the first data row in the stakeholder table.
# Verified interactively: clicking this TD sets aria-selected="true" on the TR
# and propagates selection so cell_selection()["rows"] == [0].
ROW_SELECTOR = "#stakeholders-stakeholder_table tbody tr td:first-child"
TABLE_SELECTOR = "#stakeholders-stakeholder_table"

EMPTY_STUB = "No stakeholders yet — add one above."


async def _table_text(page) -> str:
    el = await page.query_selector(TABLE_SELECTOR)
    return (await el.inner_text()) if el else ""


async def _poll_table_contains(page, text: str, *, timeout_ms=8000, step_ms=500):
    for _ in range(timeout_ms // step_ms):
        if text in await _table_text(page):
            return True
        await page.wait_for_timeout(step_ms)
    raise AssertionError(f"Timed out waiting for {text!r} in stakeholder_table")


async def _poll_table_lacks(page, text: str, *, timeout_ms=8000, step_ms=500):
    for _ in range(timeout_ms // step_ms):
        if text not in await _table_text(page):
            return True
        await page.wait_for_timeout(step_ms)
    raise AssertionError(f"Timed out waiting for {text!r} to leave stakeholder_table")


async def _set_select(page, el_id: str, value: str):
    """Drive a Shiny <select> via el.value + dispatchEvent('change') — the
    repo's proven pattern (mirrors test_data_entry_e2e.py:35-38)."""
    await page.evaluate(
        """([id, v]) => {
          const el = document.getElementById(id);
          if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); }
        }""",
        [el_id, value],
    )
    await page.wait_for_timeout(400)


async def _select_row(page):
    """Click the first data-row cell so cell_selection()["rows"] == [0]."""
    await page.click(ROW_SELECTOR)
    await page.wait_for_timeout(600)


# Name of the stakeholder used to exercise the Power-Interest grid (power=HIGH,
# interest=HIGH → "Key players" quadrant).
KEY_NAME = "TestKey"


async def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(accept_downloads=True)).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # ------------------------------------------------------------------ #
        # 1. NAV — navigate to Stakeholders and confirm the form renders
        # ------------------------------------------------------------------ #
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_timeout(1500)

        sh_name_input = await page.query_selector("#stakeholders-sh_name")
        assert sh_name_input is not None, "#stakeholders-sh_name not found after nav"
        print("1. nav: #stakeholders-sh_name present — PASS")

        # ------------------------------------------------------------------ #
        # 2. ADD — fill form, save, assert row appears
        # ------------------------------------------------------------------ #
        await page.fill("#stakeholders-sh_name", "Port Authority")
        await _set_select(page, "stakeholders-sh_type", "government")
        await page.click("#stakeholders-save_stakeholder")

        await _poll_table_contains(page, "Port Authority")
        print("2. add: 'Port Authority' appears in table — PASS")

        # ------------------------------------------------------------------ #
        # 3. VALIDATION — blank name → toast, no extra row
        # ------------------------------------------------------------------ #
        await page.fill("#stakeholders-sh_name", "")
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # Toast should appear
        toast = await page.query_selector(".shiny-notification")
        assert toast is not None, "Expected validation toast, got none"

        # Table should still contain exactly one data row (Port Authority present,
        # empty stub absent)
        t = await _table_text(page)
        assert "Port Authority" in t, "Expected 'Port Authority' still in table"
        assert EMPTY_STUB not in t, "Unexpected empty-stub after failed add"
        print("3. validation: toast shown, no extra row — PASS")

        # ------------------------------------------------------------------ #
        # 4. EDIT — select row → edit_selected → rename → save → assert
        # ------------------------------------------------------------------ #
        await _select_row(page)
        await page.click("#stakeholders-edit_selected")
        await page.wait_for_timeout(1000)

        # Confirm form was populated (proves row selection worked)
        name_val = await page.input_value("#stakeholders-sh_name")
        assert name_val == "Port Authority", (
            f"Expected form repopulated with 'Port Authority', got {name_val!r}"
        )

        await page.fill("#stakeholders-sh_name", "Port Authority (gov)")
        await page.click("#stakeholders-save_stakeholder")

        await _poll_table_contains(page, "Port Authority (gov)")
        print("4. edit: renamed to 'Port Authority (gov)' in table — PASS")

        # ------------------------------------------------------------------ #
        # 5. REMOVE — select row → remove_selected → assert empty stub
        # ------------------------------------------------------------------ #
        await _select_row(page)
        await page.click("#stakeholders-remove_selected")

        await _poll_table_contains(page, EMPTY_STUB)
        await _poll_table_lacks(page, "Port Authority")
        print("5. remove: row gone, empty stub visible — PASS")

        # ------------------------------------------------------------------ #
        # 6. PERSIST — add a row; navigate away then back; row still present
        # ------------------------------------------------------------------ #
        await page.fill("#stakeholders-sh_name", "Coastal NGO")
        await _set_select(page, "stakeholders-sh_type", "ngo")
        await page.click("#stakeholders-save_stakeholder")
        await _poll_table_contains(page, "Coastal NGO")

        await page.click("#sespy_nav_pims")
        await page.wait_for_timeout(1500)
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_timeout(1500)

        await _poll_table_contains(page, "Coastal NGO")
        print("6. persist: 'Coastal NGO' survives nav away/back — PASS")

        # ------------------------------------------------------------------ #
        # 7. GRID — add a HIGH/HIGH stakeholder, switch to the Power-Interest
        #    Grid sub-tab, assert the plot <img> + key-player summary
        # ------------------------------------------------------------------ #
        await page.fill("#stakeholders-sh_name", KEY_NAME)
        await _set_select(page, "stakeholders-sh_type", "government")
        await _set_select(page, "stakeholders-sh_power", "HIGH")
        await _set_select(page, "stakeholders-sh_interest", "HIGH")
        await page.click("#stakeholders-save_stakeholder")
        await _poll_table_contains(page, KEY_NAME)

        # Switch to the Power-Interest Grid sub-tab (Bootstrap nav-link).
        await page.click(
            "#stakeholders-stakeholder_tabs a[data-value='Power-Interest Grid']"
        )
        await page.wait_for_timeout(800)

        # Plot renders as an <img> (matplotlib @render.plot).
        await page.wait_for_selector(
            "#stakeholders-power_interest_grid img", timeout=10000
        )

        # Summary lists the stakeholder under "Key players".
        txt = ""
        for _ in range(16):
            txt = await page.inner_text("#stakeholders-grid_summary")
            if "Key players" in txt and KEY_NAME in txt:
                break
            await page.wait_for_timeout(500)
        assert "Key players" in txt and KEY_NAME in txt, (
            "grid summary missing key player"
        )
        print("7. grid: plot img + key-player summary — PASS")

        # ------------------------------------------------------------------ #
        # 8. ENGAGEMENT — add an activity for an existing stakeholder; assert it
        #    (method label + resolved stakeholder name) shows in the log
        # ------------------------------------------------------------------ #
        await page.click(
            "#stakeholders-stakeholder_tabs a[data-value='Engagement Planning']"
        )
        await page.wait_for_timeout(800)

        # The dropdown is populated from existing stakeholders via an update-select
        # message that may lag — poll until a real SH### option exists.
        sid = None
        for _ in range(16):
            sid = await page.eval_on_selector(
                "#stakeholders-eng_stakeholder",
                "el => Array.from(el.options).map(o => o.value)"
                ".find(v => v.startsWith('SH'))",
            )
            if sid:
                break
            await page.wait_for_timeout(500)
        assert sid, "engagement stakeholder dropdown has no SH### option"

        # Capture the selected stakeholder's display name to assert name-resolution.
        sh_label = await page.eval_on_selector(
            "#stakeholders-eng_stakeholder",
            "el => { const o = Array.from(el.options)"
            ".find(x => x.value.startsWith('SH')); return o ? o.text : ''; }",
        )
        await _set_select(page, "stakeholders-eng_stakeholder", sid)
        await _set_select(page, "stakeholders-eng_method", "workshop")
        await page.click("#stakeholders-add_engagement")

        eng_txt = ""
        for _ in range(16):
            eng_txt = await page.inner_text("#stakeholders-engagement_table")
            if "Workshop" in eng_txt and sh_label in eng_txt:
                break
            await page.wait_for_timeout(500)
        assert "Workshop" in eng_txt and sh_label in eng_txt, (
            "engagement not in log"
        )
        print("8. engagement: activity added + name-resolved in log — PASS")

        # ------------------------------------------------------------------ #
        # 9. COMMUNICATION — add a communication item; assert it shows in the log
        # ------------------------------------------------------------------ #
        await page.click(
            "#stakeholders-stakeholder_tabs a[data-value='Communication Plan']"
        )
        await page.wait_for_timeout(800)
        await _set_select(page, "stakeholders-comm_audience", "key_players")
        await _set_select(page, "stakeholders-comm_type", "report")
        await page.click("#stakeholders-add_communication")
        comm_txt = ""
        for _ in range(16):
            comm_txt = await page.inner_text("#stakeholders-communication_table")
            if "Report" in comm_txt and "Key players" in comm_txt:
                break
            await page.wait_for_timeout(500)
        assert "Report" in comm_txt and "Key players" in comm_txt, (
            "communication not in log"
        )
        print("9. communication: item added + shown in log — PASS")

        # ------------------------------------------------------------------ #
        # 10. ANALYSIS — switch to the Analysis tab; assert the stats summary
        # ------------------------------------------------------------------ #
        await page.click(
            "#stakeholders-stakeholder_tabs a[data-value='Analysis']"
        )
        await page.wait_for_timeout(800)
        stats_txt = ""
        for _ in range(16):
            stats_txt = await page.inner_text("#stakeholders-stakeholder_stats")
            if "Total stakeholders" in stats_txt:
                break
            await page.wait_for_timeout(500)
        assert "Total stakeholders" in stats_txt, "analysis stats not rendered"
        print("10. analysis: stats summary rendered — PASS")

        # ------------------------------------------------------------------ #
        # 11. EXPORT — the three download buttons fire with the right file types
        # ------------------------------------------------------------------ #
        for btn, ext in (("download_stakeholder_xlsx", ".xlsx"),
                         ("download_power_interest_png", ".png"),
                         ("download_summary_pdf", ".pdf")):
            async with page.expect_download() as dl_info:
                await page.click(f"#stakeholders-{btn}")
            download = await dl_info.value
            assert download.suggested_filename.endswith(ext), (
                f"{btn} -> {download.suggested_filename}")
        print("11. export: xlsx/png/pdf downloads fire — PASS")

        # ------------------------------------------------------------------ #
        # Screenshot + done
        # ------------------------------------------------------------------ #
        await page.screenshot(path=str(SCREENSHOTS / "stakeholders.png"))
        print("\nstakeholders e2e assertions pass")
        await browser.close()


asyncio.run(main())
