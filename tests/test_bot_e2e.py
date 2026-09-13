"""E2E for the BOT (Behaviour Over Time) module.

Eight cases per spec §5. Loads the Minimal Demo template (5 elements) for
all cases. Mirrors the script style of test_boolean_happy_e2e.py — boot
the app on port 8000, run this script.
"""
import asyncio

from playwright.async_api import async_playwright


async def _load_minimal_demo(page):
    await page.wait_for_selector("#sespy_nav_templates", timeout=60000)
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2500)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    assert "Minimal Demo" in cards, f"Minimal Demo missing: {cards}"
    idx = cards.index("Minimal Demo")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)


async def _open_bot(page):
    await page.click("#sespy_nav_bot")
    await page.wait_for_timeout(1500)


async def _pick_first_element(page):
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    await page.click(".selectize-dropdown-content [data-selectable]:first-child")
    await page.wait_for_timeout(500)


async def case_manual_entry_happy(page):
    print("\n=== case 1: manual entry happy path ===")
    await _open_bot(page)
    await _pick_first_element(page)
    for year, value in [(1990, 12.5), (2000, 15.8), (2010, 18.6)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(800)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot did not render after manual entry"
    n_dt = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary dl dt').length"
    )
    assert n_dt >= 5, f"expected >=5 summary fields, got {n_dt}"
    print("  ok")


async def case_csv_upload_happy(page):
    print("\n=== case 2: csv upload happy path ===")
    await page.click("input[type=radio][value=csv]")
    await page.wait_for_timeout(500)
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_sample.csv")
    await page.wait_for_timeout(2000)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot did not render after csv upload"
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger == 0, f"unexpected error alert: {danger}"
    print("  ok")


async def case_csv_lowercase_columns(page):
    print("\n=== case 3: csv with lowercase columns ===")
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_lowercase.csv")
    await page.wait_for_timeout(2000)
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger == 0, f"lowercase-column csv should succeed: {danger} errors"
    print("  ok")


async def case_csv_bad_data(page):
    print("\n=== case 4: csv with missing value column ===")
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_missing_value_col.csv")
    await page.wait_for_timeout(2000)
    danger = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary .alert-danger').length"
    )
    assert danger >= 1, "expected error alert for missing value column"
    print("  ok")


async def case_synthetic_mode(page):
    print("\n=== case 5: synthetic isa mode ===")
    await page.click("input[type=radio][value=isa]")
    await page.wait_for_timeout(2000)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "synthetic plot did not render"
    n_dt = await page.evaluate(
        "() => document.querySelectorAll('#bot-bot_summary dl dt').length"
    )
    assert n_dt >= 5, f"expected synthetic series to populate summary, got {n_dt} fields"
    print("  ok")


async def case_trend_toggle(page):
    print("\n=== case 6: trend toggle ===")
    await page.click("#bot-show_trend")
    await page.wait_for_timeout(800)
    await page.click("#bot-show_trend")
    await page.wait_for_timeout(800)
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot disappeared after trend toggle"
    print("  ok")


async def case_per_element_persistence(page):
    print("\n=== case 7: per-element data persistence ===")
    await page.click("input[type=radio][value=manual]")
    await page.wait_for_timeout(500)
    for year, value in [(1980, 1.0), (1985, 2.0), (1990, 3.0)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(600)
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    options = await page.evaluate(
        "() => document.querySelectorAll("
        "  '.selectize-dropdown-content [data-selectable]'"
        ").length"
    )
    assert options >= 2, f"need >=2 elements for this case, got {options}"
    await page.click(".selectize-dropdown-content [data-selectable]:nth-child(2)")
    await page.wait_for_timeout(800)
    for year, value in [(2000, 10.0), (2005, 20.0)]:
        await page.fill("#bot-year", str(year))
        await page.fill("#bot-value", str(value))
        await page.click("#bot-add_point")
        await page.wait_for_timeout(600)
    await page.click("#bot-element + .selectize-control")
    await page.wait_for_timeout(500)
    await page.click(".selectize-dropdown-content [data-selectable]:first-child")
    await page.wait_for_timeout(800)
    # Use exact role+name match: "text=Data" would also match "Edit Data" in
    # the outer module tabset (hidden but in the DOM). @render.data_frame mounts
    # the virtual-scroll <tbody> on a later tick than synchronous outputs like
    # plots, and the table is suspended while its tab is hidden, so the server
    # compute starts only on this click. A fixed settle raced it at 800 ms and
    # again at 1500 ms (observed 0 rows, 2026-09-13); poll for the mounted rows
    # instead and keep the assertion, so a real regression still reports a count.
    await page.get_by_role("tab", name="Data", exact=True).click()
    n_rows = 0
    for _ in range(60):
        n_rows = await page.evaluate(
            "() => document.querySelectorAll('#bot-bot_table table tbody tr').length"
        )
        if n_rows >= 3:
            break
        await page.wait_for_timeout(500)
    assert n_rows >= 3, f"element A should have >=3 rows after switch-back, got {n_rows}"
    await page.get_by_role("tab", name="Time series", exact=True).click()
    await page.wait_for_timeout(500)
    print(f"  ok ({n_rows} rows preserved on element A)")


async def case_stale_warning(page):
    print("\n=== case 8: stale-data warning ===")
    # Active BOT element after case 7 is the first option (Driver A · D001).
    # Navigate to Edit Data, delete that row, return to BOT, assert the
    # stale-warning notification fired AND the plot reverted to "no data yet".
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(1500)
    # Click the first row in the elements table to select it. The data-frame
    # output renders a virtual-scroll table; rows are <tr> with role=row.
    await page.click("#entry-elements_table table tbody tr:first-child")
    await page.wait_for_timeout(500)
    await page.click("#entry-remove_element")
    # Match the stale warning's OWN text, and wait for it HERE rather than after
    # the nav click below: the toast carries duration=5, so a wait placed after a
    # server round-trip can miss it entirely under load. _stale_warning fires on
    # isa_change regardless of which panel is visible, so this is the right spot.
    # Counting .shiny-notification was vacuous inside run_e2e.py — test_autosave
    # runs first and leaves an autosave file, so every later session carries the
    # persistent "Recovered work" banner, which satisfied the count whether or
    # not this warning ever fired.
    await page.wait_for_function(
        "() => Array.from(document.querySelectorAll("
        "  '#shiny-notification-panel .shiny-notification'"
        ")).some(n => (n.textContent || '').includes('deleted upstream'))",
        timeout=30000,
    )
    # Return to BOT — the active element no longer exists, so plot reverts.
    await page.click("#sespy_nav_bot")
    await page.wait_for_timeout(1500)
    # And the BOT plot should re-render: the active element id no longer maps
    # to a frame in bot_data_store, so _filtered_frame returns None and the
    # plot displays the "no data yet" message via matplotlib text.
    plot_visible = await page.evaluate(
        "() => !!document.querySelector('#bot-bot_plot img')"
    )
    assert plot_visible, "plot did not re-render after stale element"
    print("  ok (stale-data warning shown, plot reverted)")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await _load_minimal_demo(page)

        await case_manual_entry_happy(page)
        await case_csv_upload_happy(page)
        await case_csv_lowercase_columns(page)
        await case_csv_bad_data(page)
        await case_synthetic_mode(page)
        await case_trend_toggle(page)
        await case_per_element_persistence(page)
        await case_stale_warning(page)

        await page.screenshot(path="tests/screenshots/bot_e2e.png")
        print("\nbot e2e: 8 cases passed")
        await browser.close()


asyncio.run(main())
