"""E2E for the PIMS Project Setup module.

Two cases:
  1. Save and round-trip — fill all 5 PIMS fields, click Save, switch
     modules, switch back, assert form values persisted + status block
     shows a recent save timestamp.
  2. Template load populates PIMS form — load Coastal Tourism, navigate
     to PIMS, assert template's metadata fields populate the form.
"""
import asyncio

from playwright.async_api import async_playwright


async def _open_pims(page):
    await page.wait_for_selector("#sespy_nav_pims", timeout=60000)
    await page.click("#sespy_nav_pims")
    await page.wait_for_timeout(1500)


async def case_save_and_round_trip(page):
    print("\n=== case 1: PIMS save and round-trip ===")
    await _open_pims(page)

    # Fill the form.
    await page.fill("#pims-project_name", "E2E Test Project")
    await page.select_option("#pims-da_site", "Macaronesia")
    await page.fill("#pims-focal_issue", "E2E focal issue text.")
    await page.fill("#pims-definition_statement", "E2E definition statement.")
    await page.select_option("#pims-temporal_scale", "Yearly")
    await page.select_option("#pims-spatial_scale", "Regional")
    await page.fill("#pims-system_in_focus", "E2E system in focus.")
    await page.wait_for_timeout(400)

    # Click Save.
    await page.click("#pims-save_project_info")

    # The "Last saved at" block should now show a non-empty timestamp.
    # #pims-current_status is a @render.ui and the save click is a round trip
    # (project_data.set -> emit_isa_change -> synchronous autosave disk write)
    # before it re-renders, so poll instead of a fixed sleep.
    saved_text = None
    for _ in range(120):  # 60 s budget
        saved_text = await page.evaluate(
            "() => {"
            " const dts = document.querySelectorAll('#pims-current_status dt');"
            " for (let i=0; i<dts.length; ++i) {"
            "   if (dts[i].textContent.trim().toLowerCase().includes('last saved'))"
            "     return dts[i].nextElementSibling.textContent.trim();"
            " }"
            " return null;"
            "}"
        )
        if saved_text and "Not saved" not in saved_text:
            break
        await page.wait_for_timeout(500)
    assert saved_text and "Not saved" not in saved_text, (
        f"expected non-empty last-saved timestamp, got {saved_text!r}"
    )

    # Switch to Edit Data and back. Assert each nav round-trip actually landed
    # (same idiom as tests/test_bookmark_e2e.py:23) — navset_hidden never
    # unmounts the PIMS inputs, so without these waits the asserts below only
    # read back what page.fill typed and the round-trip is never exercised.
    await page.click("#sespy_nav_entry")
    await page.wait_for_function(
        "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='entry']\");"
        " return !!el && el.classList.contains('active'); }",
        timeout=60000,
    )
    await page.click("#sespy_nav_pims")
    await page.wait_for_function(
        "() => { const el = document.querySelector(\".tab-content > .tab-pane[data-value='pims']\");"
        " return !!el && el.classList.contains('active'); }",
        timeout=60000,
    )

    # Form values should still be present.
    name = await page.evaluate("() => document.querySelector('#pims-project_name').value")
    assert name == "E2E Test Project", f"name lost on round-trip: {name!r}"

    da = await page.evaluate("() => document.querySelector('#pims-da_site').value")
    assert da == "Macaronesia", f"da_site lost: {da!r}"

    focal = await page.evaluate("() => document.querySelector('#pims-focal_issue').value")
    assert focal == "E2E focal issue text.", f"focal_issue lost: {focal!r}"

    temporal = await page.evaluate("() => document.querySelector('#pims-temporal_scale').value")
    assert temporal == "Yearly", f"temporal_scale lost: {temporal!r}"

    spatial = await page.evaluate("() => document.querySelector('#pims-spatial_scale').value")
    assert spatial == "Regional", f"spatial_scale lost: {spatial!r}"

    print(f"  ok (last saved: {saved_text})")


async def case_template_loads_pims_metadata(page):
    print("\n=== case 2: template load populates PIMS form ===")
    # Load the Coastal Tourism template via the Templates picker.
    await page.click("#sespy_nav_templates")
    # #templates-templates_list is a suspended @render.ui (app.py:137 puts
    # templates_ui("templates") inside the navset_hidden at dashboard.py:230),
    # so its first render — and list_templates() with it — only starts at this
    # nav click, after the _goto/update_navs round-trip. Poll instead of a
    # fixed sleep, which is host-side wall clock and does not stretch when the
    # shared server is loaded.
    cards: list[str] = []
    for _ in range(120):  # 60 s budget
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        if "Coastal Tourism SES" in cards:
            # The h5s are in the DOM before Shiny binds the Load buttons that
            # were inserted with them; an unbound click never increments
            # input.load_template_{idx}, so the load silently never happens.
            await page.wait_for_timeout(300)
            break
        await page.wait_for_timeout(500)
    assert "Coastal Tourism SES" in cards, f"Coastal Tourism SES missing: {cards}"
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")

    await _open_pims(page)
    # load_template() + emit_isa_change/cld_update/template_loaded all run on
    # the single event loop before _load_form_values pushes the template's
    # metadata into the form; da_site holds case 1's "Macaronesia" until then.
    da = None
    for _ in range(120):  # 60 s budget
        da = await page.evaluate("() => document.querySelector('#pims-da_site').value")
        if da == "Tuscan Archipelago":
            break
        await page.wait_for_timeout(500)
    assert da == "Tuscan Archipelago", f"expected Tuscan Archipelago, got {da!r}"
    focal = await page.evaluate("() => document.querySelector('#pims-focal_issue').value")
    assert focal and "tourism" in focal.lower(), f"focal_issue not populated: {focal!r}"
    print(f"  ok (da={da})")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_save_and_round_trip(page)
        await case_template_loads_pims_metadata(page)

        await page.screenshot(path="tests/screenshots/pims_project_e2e.png")
        print("\npims project setup e2e: 2 cases passed")
        await browser.close()


asyncio.run(main())
