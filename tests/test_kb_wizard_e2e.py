"""E2E for K1 (R knowledge-base parity) in the AI-ISA wizard (spec §7 e2e).

Seven steps, in the spec's order:
  1. Baltic -> Coastal lagoon -> two countries (codes), then Skip step 3.
  2. Step 4 shows KB- and GOV-badged suggestion chips (at most 12).
  3. Select three chips, deselect the middle one: the other two rows keep
     their text and order.
  4. Type a chip's text by hand (trailing space included): the chip lights.
     The chip state is computed on the server, so this is also the browser
     check that typing into a `data-row` input reaches the server.
  5. Back to step 2 and Next again: the country order is unchanged.
  6. Finish, then the report preview carries a Regional Context section.
  7. About's `#about-reference-data` shows "vendored" and "R v1.35.6".

The runner (tests/run_e2e.py) launches the server with SESPY_R_DATA_DIR=off,
so all reference data is the vendored copy. Every selector is scoped by id
under the wizard, report or About panel: all nav panels share one DOM.

Boot the app on port 8000 (SHINY_TESTMODE=1), then run this script.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.async_api import async_playwright

from _testmode import export_value, snapshot

URL = "http://127.0.0.1:8000"
R_TAG = "v1.35.6"
# Not the option order (LT comes before PL in the Baltic list), so a
# selectize rebuilt in DOM order would fail step 5.
CODES = ["PL", "LT"]
STEP_RENDER = "#wizard-wizard_step_render"
CHIPS = "#wizard-chips_drivers"


def _row(target: str, i: int) -> str:
    return f'#wizard-freeform_{target}_container [data-row="{target}_{i}"]'


def _chip(i: int) -> str:
    return f"{CHIPS} #wizard-chip_drivers_{i}"


async def _wait_step(page, label: int) -> None:
    """Wait until the breadcrumb's active pill is step `label` (1-based)."""
    await page.wait_for_function(
        "(n) => (document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent || '').trim().startsWith(n + '.')",
        arg=label, timeout=30000,
    )


async def _click_when_bound(page, sel: str) -> None:
    """Buttons inside re-rendered outputs: a click before Shiny binds the new
    element is lost."""
    await page.wait_for_selector(f"{sel}.shiny-bound-input", timeout=30000)
    await page.click(sel)


async def _row_value(page, target: str, i: int):
    return await page.evaluate("(s) => document.querySelector(s)?.value ?? null",
                               _row(target, i))


async def _wait_row(page, target: str, i: int, value: str) -> None:
    await page.wait_for_function(
        "([s, v]) => document.querySelector(s)?.value === v",
        arg=[_row(target, i), value], timeout=30000,
    )


async def _wait_chip(page, i: int, on: bool) -> None:
    cls = "chip-on" if on else "chip-off"
    await page.wait_for_selector(f"{_chip(i)}.{cls}.shiny-bound-input", timeout=30000)


async def _answers(page) -> dict:
    return export_value(await snapshot(page), "wizard-answers")


async def _wait_answers(page, key: str, expected) -> None:
    got = None
    for _ in range(60):  # 30 s
        got = (await _answers(page)).get(key)
        if got == expected:
            return
        await page.wait_for_timeout(500)
    raise AssertionError(f"answers[{key!r}] = {got!r}, expected {expected!r}")


async def _wait_server_input(page, key: str, expected) -> None:
    got = None
    for _ in range(60):  # 30 s
        got = ((await snapshot(page)).get("input") or {}).get(key)
        if got == expected:
            return
        await page.wait_for_timeout(500)
    raise AssertionError(f"server input {key!r} = {got!r}, expected {expected!r}")


async def _fill_row(page, target: str, i: int, text: str) -> None:
    """Fill a row and blur it (`change` is sent at once, typing is debounced),
    then wait until the server holds the value under this visit's row id."""
    sel = _row(target, i)
    await page.fill(sel, text)
    await page.press(sel, "Tab")
    gen = export_value(await snapshot(page), "wizard-gen")[target]
    await _wait_server_input(page, f"wizard-entry_{gen}_{target}_{i}", text)


async def _selectize_items(page) -> list:
    return await page.evaluate(
        "() => { const s = document.querySelector("
        "'#wizard-wizard_step_render #wizard-answer_countries');"
        " if (!s || !s.selectize) return null;"
        " return Array.from(s.selectize.$control[0].querySelectorAll('.item'))"
        ".map(e => e.getAttribute('data-value')); }"
    )


async def _start_wizard(page) -> None:
    """Fresh page, wizard Start; the boot project is non-empty, so Start
    opens the Replace modal (handled either way)."""
    await page.goto(URL, wait_until="networkidle")
    await page.wait_for_selector("#sespy_nav_wizard", timeout=60000)
    await page.click("#sespy_nav_wizard")
    await _click_when_bound(page, "#wizard-wizard_start")
    await page.wait_for_function(
        "() => document.querySelector('#wizard-wizard_replace')"
        " || document.querySelector('#wizard-answer_regional_sea')",
        timeout=30000,
    )
    if await page.query_selector("#wizard-wizard_replace"):
        await _click_when_bound(page, "#wizard-wizard_replace")
    await _wait_step(page, 1)


async def step1_context_and_skip(page) -> None:
    print("\n=== 1: Baltic -> Coastal lagoon -> 2 codes -> Skip step 3 ===")
    await _start_wizard(page)
    await page.check(f"{STEP_RENDER} #wizard-answer_regional_sea input[value='baltic']")
    await _wait_server_input(page, "wizard-answer_regional_sea", "baltic")
    await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 2)
    eco = f"{STEP_RENDER} #wizard-answer_ecosystem_type input[value='Coastal lagoon']"
    await page.wait_for_selector(eco, timeout=30000)
    await page.check(eco)
    await _wait_server_input(page, "wizard-answer_ecosystem_type", "Coastal lagoon")
    await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 3)
    # Pick the countries through selectize itself, in click order.
    await page.wait_for_function(
        "() => document.querySelector("
        "'#wizard-wizard_step_render #wizard-answer_countries')?.selectize",
        timeout=30000,
    )
    options = await page.evaluate(
        "() => Object.keys(document.querySelector("
        "'#wizard-wizard_step_render #wizard-answer_countries').selectize.options)"
    )
    assert set(CODES) <= set(options), f"country options are not codes: {options}"
    for code in CODES:
        await page.evaluate(
            "(c) => document.querySelector("
            "'#wizard-wizard_step_render #wizard-answer_countries').selectize.addItem(c)",
            code,
        )
    await _wait_server_input(page, "wizard-answer_countries", CODES)
    await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 4)
    await _wait_answers(page, "countries", CODES)
    await _click_when_bound(page, f"{STEP_RENDER} #wizard-skip_main_issue")
    await _wait_step(page, 5)
    await _wait_answers(page, "main_issue", [])
    await page.wait_for_selector(_row("drivers", 0), timeout=30000)
    print("  ok (countries", CODES, ", step 3 skipped)")


async def step2_badged_chips(page) -> list[str]:
    print("\n=== 2: KB- and GOV-badged chips ===")
    await page.wait_for_selector(f"{CHIPS} .kb-chip.shiny-bound-input", timeout=30000)
    chips = await page.evaluate(
        "(c) => Array.from(document.querySelectorAll(c + ' .kb-chip')).map(b => {"
        " const k = b.cloneNode(true); const badge = k.querySelector('.kb-badge');"
        " const label = badge ? badge.textContent.trim() : null;"
        " if (badge) badge.remove();"
        " return {name: k.textContent.trim(), badge: label}; })",
        CHIPS,
    )
    badges = [c["badge"] for c in chips]
    assert 0 < len(chips) <= 12, f"expected 1-12 chips, got {len(chips)}"
    assert "KB" in badges and "GOV" in badges, f"badges: {badges}"
    assert await page.query_selector(f"{CHIPS} .kb-badge-KB"), "no .kb-badge-KB"
    assert await page.query_selector(f"{CHIPS} .kb-badge-GOV"), "no .kb-badge-GOV"
    caption = await page.text_content(f"{CHIPS} .kb-caption") or ""
    assert "Baltic Sea - Coastal lagoon" in caption, caption
    print(f"  ok ({len(chips)} chips, badges {sorted(set(b for b in badges if b))})")
    return [c["name"] for c in chips]


async def step3_select_and_deselect(page, names: list[str]) -> None:
    print("\n=== 3: select 3 chips, deselect the middle ===")
    for i in range(3):
        await _click_when_bound(page, _chip(i))
        await _wait_row(page, "drivers", i, names[i])
        await _wait_chip(page, i, True)
    await _click_when_bound(page, _chip(1))
    await _wait_chip(page, 1, False)
    await _wait_row(page, "drivers", 1, "")
    rows = [await _row_value(page, "drivers", i) for i in range(3)]
    assert rows == [names[0], "", names[2]], f"rows after deselect: {rows}"
    await _wait_chip(page, 0, True)
    await _wait_chip(page, 2, True)
    # The blanking is a pending server write until the client echoes it.
    for _ in range(60):
        if not export_value(await snapshot(page), "wizard-pending").get("drivers"):
            break
        await page.wait_for_timeout(500)
    else:
        raise AssertionError("pending drivers write never cleared")
    print(f"  ok (rows kept in place: {rows})")


async def step4_hand_typed(page, names: list[str]) -> None:
    print("\n=== 4: hand-typed text selects its chip ===")
    # A trailing space: chips match on the stripped text.
    await _fill_row(page, "drivers", 1, names[3] + " ")
    await _wait_chip(page, 3, True)
    await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 6)
    await _wait_answers(page, "drivers", [names[0], names[3], names[2]])
    print("  ok (chip lit by typing; saved", [names[0], names[3], names[2]], ")")


async def step5_back_keeps_country_order(page, names: list[str]) -> None:
    print("\n=== 5: Back to step 2, Next: country order kept ===")
    for label in (5, 4, 3):
        await _click_when_bound(page, "#wizard-wizard_back")
        await _wait_step(page, label)
        if label == 5:   # the saved drivers come back on re-entry
            await _wait_row(page, "drivers", 1, names[3])
    items = None
    for _ in range(60):
        items = await _selectize_items(page)
        if items and len(items) == len(CODES):
            break
        await page.wait_for_timeout(500)
    assert items == CODES, f"selectize items after Back: {items}"
    await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 4)
    answers = await _answers(page)
    assert answers.get("countries") == CODES, f"countries after Back/Next: {answers}"
    print(f"  ok (order {items})")


async def step6_finish_and_report(page, names: list[str]) -> None:
    print("\n=== 6: Finish, report has Regional Context ===")
    await _click_when_bound(page, f"{STEP_RENDER} #wizard-skip_main_issue")
    await _wait_step(page, 5)
    await _wait_row(page, "drivers", 0, names[0])
    await _click_when_bound(page, "#wizard-wizard_next")
    for label, target in enumerate(
            ["activities", "pressures", "states", "impacts", "welfare", "responses"], 6):
        await _wait_step(page, label)
        await _fill_row(page, target, 0, f"KB e2e {target}")
        await _click_when_bound(page, "#wizard-wizard_next")
    await _wait_step(page, 12)
    await _click_when_bound(page, "#wizard-wizard_finish")
    await page.wait_for_selector(f"{STEP_RENDER} .wizard-complete", timeout=30000)

    await page.click("#sespy_nav_report")
    state = {}
    for _ in range(120):  # 60 s: the preview is a suspended output
        state = await page.evaluate(
            "(n) => { const f = document.querySelector('#report-report_preview iframe');"
            " const s = f ? (f.getAttribute('srcdoc') || '') : '';"
            " return {len: s.length, mine: s.includes(n)}; }",
            names[0],
        )
        if state["mine"]:
            break
        await page.wait_for_timeout(500)
    assert state.get("mine"), f"report preview never showed the wizard's data: {state}"
    frame = page.frame_locator("#report-report_preview iframe")
    heading = frame.locator("h2", has_text="Regional Context")
    assert await heading.count() == 1, "no Regional Context h2 in the report preview"
    assert (await heading.text_content() or "").strip() == "Regional Context"
    print("  ok (Regional Context in the report preview)")


async def step7_about_reference_data(page) -> None:
    print("\n=== 7: About reference data ===")
    await page.evaluate(
        "() => { const p = document.getElementById('shiny-notification-panel');"
        " if (p) p.style.display = 'none'; }")
    await page.click("#tb_about")
    await page.wait_for_selector(".modal #about-reference-data", timeout=30000)
    text = await page.text_content(".modal #about-reference-data") or ""
    assert "vendored" in text, text
    assert f"R {R_TAG}" in text, text
    assert "differs" not in text, text
    print(f"  ok ({' '.join(text.split())[:120]})")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})

        await step1_context_and_skip(page)
        names = await step2_badged_chips(page)
        assert len(names) >= 4, f"need 4 chips, got {names}"
        await step3_select_and_deselect(page, names)
        await step4_hand_typed(page, names)
        await step5_back_keeps_country_order(page, names)
        await step6_finish_and_report(page, names)
        await step7_about_reference_data(page)

        await page.screenshot(path="tests/screenshots/kb_wizard_e2e.png")
        print("\nkb wizard e2e: 7 steps passed")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
