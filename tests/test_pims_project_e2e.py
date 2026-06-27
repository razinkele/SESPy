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
    await page.wait_for_selector("#sespy_nav_pims", timeout=15000)
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
    await page.wait_for_timeout(1000)

    # The "Last saved at" block should now show a non-empty timestamp.
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
    assert saved_text and "Not saved" not in saved_text, (
        f"expected non-empty last-saved timestamp, got {saved_text!r}"
    )

    # Switch to Edit Data and back.
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(800)
    await page.click("#sespy_nav_pims")
    await page.wait_for_timeout(1500)

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
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    assert "Coastal Tourism SES" in cards, f"Coastal Tourism SES missing: {cards}"
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)

    await _open_pims(page)
    da = await page.evaluate("() => document.querySelector('#pims-da_site').value")
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
