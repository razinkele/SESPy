"""E2E for Rate Connections (QSEM-C2): add a stakeholder, rate a connection,
assert the connection row reflects the new rating (#ratings -> 1, mine -> check)."""
import asyncio

from playwright.async_api import async_playwright

# Verified DataGrid selection idiom (test_stakeholders_e2e.py): click a TD cell,
# not the TR — only a TD click sets aria-selected and propagates to cell_selection.
RATE_ROW = "#rate-connections_table table tbody tr:first-child td:first-child"


async def _set_select(page, el_id: str, value: str):
    """Drive a Shiny <select> via el.value + change event (repo's proven pattern,
    test_stakeholders_e2e.py)."""
    await page.evaluate(
        """([id, v]) => { const el = document.getElementById(id);
          if (el) { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); } }""",
        [el_id, value],
    )


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # 1. Add one stakeholder (pattern from tests/test_stakeholders_e2e.py:95-97).
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_selector("#stakeholders-sh_name", timeout=30000)
        await page.fill("#stakeholders-sh_name", "Port Authority")
        await _set_select(page, "stakeholders-sh_type", "government")  # REQUIRED: save guard rejects blank type
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # 2. Go to Rate Connections.
        await page.click("#sespy_nav_rate")
        await page.wait_for_selector("#rate-connections_table table tbody tr", timeout=30000)
        await page.wait_for_selector("#rate-rater", timeout=30000)  # picker present (register non-empty)

        # 3. Select the first connection row (click a TD — not the TR — per RATE_ROW).
        await page.click(RATE_ROW)
        await page.wait_for_selector("#rate-save_rating", timeout=30000)  # editor rendered

        # 4. Set a rating and save.
        await page.evaluate(
            "() => { const s=document.getElementById('rate-ed_strength');"
            " if(s){ s.value='strong'; s.dispatchEvent(new Event('change',{bubbles:true})); } }"
        )
        await page.click("#rate-save_rating")

        # 5. Assert the first row's #ratings cell became 1 (poll the re-render).
        ok = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if cells and "1" in cells:
                ok = True
                break
        assert ok, f"connection row did not reflect the saved rating: {cells}"
        print("rate connections save: OK")

        # --- C3: make the first connection CONTESTED with a 2nd rater ---
        # 1. Add a second stakeholder.
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_selector("#stakeholders-sh_name", timeout=30000)
        await page.fill("#stakeholders-sh_name", "Coastal NGO")
        await _set_select(page, "stakeholders-sh_type", "government")  # any valid code; reuse C2's proven one
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # 2. Back to Rate Connections; switch the rater to the 2nd stakeholder.
        #    rater_picker is an @render.ui — wait until it has a 2nd option, then
        #    drive by the runtime-generated id via the proven _set_select idiom
        #    (selectedIndex is racy against the async select re-render).
        await page.click("#sespy_nav_rate")
        await page.wait_for_selector("#rate-connections_table table tbody tr", timeout=30000)
        await page.wait_for_function(
            "() => { const s = document.getElementById('rate-rater');"
            " return s && s.options.length >= 2; }",
            timeout=30000,
        )
        ngo_id = await page.evaluate(
            "() => document.getElementById('rate-rater').options[1].value"
        )
        await _set_select(page, "rate-rater", ngo_id)
        await page.wait_for_timeout(500)

        # 3. Switching rater reset sel_idx — RE-CLICK the first row (TD), required.
        await page.click(RATE_ROW)
        await page.wait_for_selector("#rate-save_rating", timeout=30000)

        # Blind mode: rater 2 has NOT rated this connection yet, but rater 1 has.
        # Enabling blind hides the peer value from rater 2 until they submit.
        await page.check("#rate-blind_mode")
        await page.wait_for_timeout(500)
        blind_txt = (await page.text_content("#rate-current_ratings")) or ""
        assert "blind mode" in blind_txt.lower(), f"blind placeholder not shown: {blind_txt!r}"
        assert "/" not in blind_txt, f"peer rating value leaked under blind mode: {blind_txt!r}"

        # 4. Rate it with OPPOSITE polarity ("-") via a native click (the repo's
        #    proven radio idiom — a synthetic .checked may not register), then save.
        await page.click("#rate-ed_polarity input[value='-']")
        await page.click("#rate-save_rating")

        # 4b. Assert the 2nd-rater save landed (#ratings -> 2) BEFORE polling for
        #     the contested marker, so a silent no-op is self-diagnosing.
        saved2 = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells2 = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if cells2 and "2" in cells2:
                saved2 = True
                break
        assert saved2, f"2nd-rater save did not land (#ratings != 2): {cells2}"

        # Reveal: rater 2 has now submitted, so blind mode reveals the full peer list.
        # Re-click the row to ensure sel_idx is current (DataGrid may deselect on re-render).
        await page.click(RATE_ROW)
        await page.wait_for_selector("#rate-save_rating", timeout=30000)
        reveal = False
        rtxt = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            rtxt = (await page.text_content("#rate-current_ratings")) or ""
            if "blind mode" not in rtxt.lower() and "/" in rtxt:
                reveal = True
                break
        assert reveal, f"blind mode did not reveal after submit: {rtxt!r}"

        # 5. Poll until the first row's disagreement cell shows the contested marker.
        contested = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if any("⚠" in c for c in cells):
                contested = True
                break
        assert contested, f"first connection not marked contested: {cells}"

        # 6. Count caption reads 1.
        count_txt = await page.evaluate(
            "() => { const e=document.getElementById('rate-contested_count');"
            " return e ? e.textContent : ''; }"
        )
        assert "1" in count_txt, f"contested count caption wrong: {count_txt!r}"

        # 7. Filter narrows the table to exactly one row.
        await page.check("#rate-contested_only")
        narrowed = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            n = await page.evaluate(
                "() => document.querySelectorAll('#rate-connections_table table tbody tr').length"
            )
            if n == 1:
                narrowed = True
                break
        assert narrowed, f"contested-only filter did not narrow to 1 row (got {n})"
        print("rate connections contested view: OK")

        await browser.close()


asyncio.run(main())
