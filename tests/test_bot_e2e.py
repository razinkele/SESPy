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
    # The template gallery is a suspended @render.ui: its first render starts at
    # this nav click (server round-trip + card build), so a fixed settle was the
    # only guard and an empty list killed all 8 cases at the assert below.
    cards = []
    for _ in range(120):
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        if cards:
            break
        await page.wait_for_timeout(500)
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
    # Snapshot the plot BEFORE the upload: bot_plot always emits an <img>
    # (placeholder at analysis_bot.py:330-335, error figure at :325-329), and
    # while an output recomputes Shiny only adds a `recalculating` class and
    # reuses the same <img> element -- so case 1's image is still in the DOM
    # and `!!img` below is true whether or not this upload reached the server.
    # Only a CHANGED data: URI proves the re-render happened. Deliberately
    # data-agnostic so the same pattern works for any fixture; case 3 pins its
    # upload with a summary value instead, which this case cannot do because
    # bot_sample.csv is also what the plot already shows from case 1.
    prev_src = await page.evaluate(
        "() => { const i = document.querySelector('#bot-bot_plot img');"
        " return i ? i.src : ''; }"
    )
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_sample.csv")
    # A timeout here is the intended failure mode: it means the CSV upload
    # never re-rendered the plot. The `danger == 0` assert below still
    # distinguishes a successful parse from the error figure.
    await page.wait_for_function(
        "(prev) => { const i = document.querySelector('#bot-bot_plot img');"
        " return !!i && i.src !== prev && i.complete && i.naturalWidth > 0; }",
        arg=prev_src,
        timeout=30000,
    )
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
    # bot_lowercase.csv now carries values distinct from bot_sample.csv (mean
    # 103.0000). With identical values the resulting summary was byte-identical
    # to case 2's, so `danger == 0` passed even if this upload never reached the
    # server. Poll for the new mean, then keep the original error-count assert.
    await page.set_input_files("#bot-csv_upload", "tests/fixtures/bot_lowercase.csv")
    summary = ""
    for _ in range(60):
        summary = await page.evaluate(
            "() => (document.querySelector('#bot-bot_summary') || {}).textContent || ''"
        )
        if "103.0000" in summary:
            break
        await page.wait_for_timeout(500)
    assert "103.0000" in summary, (
        f"lowercase-column csv did not parse (mean 103.0000 missing): {summary!r}"
    )
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
    # `!!img` alone is vacuous here: case 5 already left an <img> in
    # #bot-bot_plot and Shiny keeps the previous render's <img> while an output
    # recomputes, so the assert below is true even if #bot-show_trend is
    # unwired. Require the figure to actually change on each toggle --
    # show_trend defaults to True (analysis_bot.py:82) and _trend_coeffs
    # returns None when it is off (analysis_bot.py:272-274), so the trend line
    # is drawn/removed and the PNG differs both ways.
    async def _snap():
        return await page.evaluate(
            "() => { const i = document.querySelector('#bot-bot_plot img');"
            " return i ? i.src : ''; }"
        )

    async def _wait_changed(prev, label):
        # A timeout here means the trend toggle did not reach the plot.
        await page.wait_for_function(
            "(prev) => { const i = document.querySelector('#bot-bot_plot img');"
            " return !!i && i.src !== prev && i.complete && i.naturalWidth > 0; }",
            arg=prev,
            timeout=30000,
        )
        print(f"  trend {label}: plot re-rendered")

    src_on = await _snap()
    await page.click("#bot-show_trend")      # -> off
    await _wait_changed(src_on, "off")
    src_off = await _snap()
    await page.click("#bot-show_trend")      # -> back on
    await _wait_changed(src_off, "on")

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
    # bot_plot ALWAYS returns a figure - the error path (analysis_bot.py:325-329)
    # and the "no data yet" path (:330-335) both draw text on an axis and return
    # `fig` - and shiny encodes every figure as a data:image/png;base64 <img> src
    # (shiny/render/_render.py:429-437). While an output recomputes shiny only
    # adds a `recalculating` class (shiny.js:2975-2979), so the PREVIOUS render's
    # <img> stays in the DOM and `!!#bot-bot_plot img` is true below no matter
    # what happens. Snapshot the src HERE: the BOT pane has been hidden since the
    # nav click above, so its outputs are suspended and no new value can land
    # between this line and the nav-back - which makes any change observed after
    # the nav-back provably the post-return re-render.
    prev_plot_src = await page.evaluate(
        "() => { const i = document.querySelector('#bot-bot_plot img');"
        " return i ? i.src : ''; }"
    )
    # Return to BOT — the active element no longer exists, so plot reverts.
    await page.click("#sespy_nav_bot")
    # On resume the store has been pruned (analysis_bot.py:243-244) and
    # element_picker_ui re-renders without the deleted id, so the recompute draws
    # either the "no data yet" placeholder (stale id still selected) or the first
    # remaining element's series - either way a different PNG from the snapshot,
    # so this wait cannot hang on a healthy app. A Playwright timeout here is the
    # intended failure mode: it means the BOT plot never re-rendered after the
    # upstream deletion.
    await page.wait_for_function(
        "(prev) => { const i = document.querySelector('#bot-bot_plot img');"
        " return !!i && i.src !== prev && i.complete && i.naturalWidth > 0; }",
        arg=prev_plot_src,
        timeout=30000,
    )
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
