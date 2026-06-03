"""E2E for the AI-ISA Wizard module (SP1).

Six cases:
  1. Empty project — full 12-step run, asserts elements written + Finish deactivates.
  2. Non-empty project — modal Cancel preserves state.
  3. Non-empty project — modal Replace clears isa_data, preserves metadata.
  4. Mid-wizard nav and resume.
  5. Back preserves writes.
  6. Validation failure on freeform step.

Boot the app on port 8000, then run this script.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def _open_wizard(page):
    await page.wait_for_selector("#sespy_nav_wizard", timeout=15000)
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)


async def _start_wizard_empty_via_replace(page):
    """Reset the page, then drive the wizard from boot state through
    Start → modal → Replace. End state: wizard active at step 0, with
    `isa_data` cleared to `IsaData()`.

    The page reload is the cleanest way to guarantee a fresh
    `wizard_active=False` baseline regardless of what previous cases
    left in session reactives — there is no UI affordance to
    deactivate the wizard except by clicking Finish on step 11, which
    is impractical to wire up just to reset between cases.

    Why not click `#new_project` instead of going through Replace?
    Because `#new_project` in `project_io.py` is wired to `_on_new`
    which calls `Project.from_isa(load_sample(SAMPLE))` — it RELOADS
    the sample, it does NOT produce an empty project. Start would
    still see a non-empty project and open the modal anyway. The
    modal-Replace flow is the only path to a truly empty wizard
    state, so we exercise it as the default empty-start helper.
    """
    await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
    await page.wait_for_selector("#sespy_nav_wizard", timeout=15000)
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    await page.click("#wizard-wizard_replace")
    await page.wait_for_timeout(1500)


async def _drive_to_step_11(page):
    """Reusable: drive the wizard from boot through step-10 → Next →
    step 11. Mirrors the navigation portion of case_full_run; copy-adapted
    from the exact `Shiny.setInputValue` / click sequence there.
    Pre-condition: app running on http://127.0.0.1:8000.
    End state: wizard_step == 11; SP3 table rendered; ready for SP4 button click.
    """
    await _start_wizard_empty_via_replace(page)
    # Steps 0-10: pick a value, click Next (mirrors case_full_run verbatim).
    for step in range(11):
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic',"
                " {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast',"
                " {priority: 'event'})"
            )
        elif step in (2, 3):
            target = "countries" if step == 2 else "main_issue"
            value_js = "['Lithuania']" if step == 2 else "['Eutrophication']"
            await page.evaluate(
                f"() => Shiny.setInputValue('wizard-answer_{target}', {value_js},"
                " {priority: 'event'})"
            )
        else:
            target = ["drivers", "activities", "pressures", "states", "impacts", "welfare", "responses"][step - 4]
            await page.fill(f"#wizard-entry_{target}_0", f"E2E {target} sample")
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # End state: wizard is now on step 11 (SP3 table rendered).


async def case_full_run(page):
    print("\n=== case 1: empty project full 12-step run ===")
    # _start_wizard_empty_via_replace navigates and reloads; no need to
    # call _open_wizard separately.
    await _start_wizard_empty_via_replace(page)
    # Steps 0-10: pick a value, click Next.
    for step in range(11):
        # For choice_one and choice_many, set the answer via JS.
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic',"
                " {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast',"
                " {priority: 'event'})"
            )
        elif step in (2, 3):
            target = "countries" if step == 2 else "main_issue"
            value_js = "['Lithuania']" if step == 2 else "['Eutrophication']"
            await page.evaluate(
                f"() => Shiny.setInputValue('wizard-answer_{target}', {value_js},"
                " {priority: 'event'})"
            )
        else:
            target = ["drivers","activities","pressures","states","impacts","welfare","responses"][step-4]
            await page.fill(f"#wizard-entry_{target}_0", f"E2E {target} sample")
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # Step 11: click Finish.
    await page.click("#wizard-wizard_finish")
    await page.wait_for_timeout(1500)
    # Assert: Start button is back in the DOM (wizard_active=False causes
    # `wizard_step_render` to re-render the inactive view, which contains
    # the Start button). Under the conditional-render architecture the
    # button is *absent* from the DOM while the wizard is active, so we
    # check `!== null` rather than CSS visibility.
    present = await page.evaluate(
        "() => document.getElementById('wizard-wizard_start') !== null"
    )
    assert present, "Start button should be present in DOM after Finish"

    # Also assert the 7 freeform-step elements were actually persisted to
    # project_data.isa_data.elements. Without this check, a Finish that
    # silently dropped all writes would still pass the deactivated-state
    # check above. Navigate to Edit Data and look for the labels we
    # entered ("E2E drivers sample", "E2E activities sample", etc.).
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(2500)
    cells_text = await page.evaluate(
        "() => Array.from(document.querySelectorAll("
        "'#entry-elements_table table tbody tr td')).map(c => c.textContent).join('|')"
    )
    expected_labels = [
        "E2E drivers sample", "E2E activities sample", "E2E pressures sample",
        "E2E states sample", "E2E impacts sample", "E2E welfare sample",
        "E2E responses sample",
    ]
    missing = [lbl for lbl in expected_labels if lbl not in cells_text]
    assert not missing, f"missing element labels in elements_table: {missing}"
    print("  ok (wizard deactivated, 7 elements persisted)")


async def case_modal_cancel(page):
    print("\n=== case 2: non-empty project modal Cancel ===")
    # Load Coastal Tourism SES so project is non-empty.
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)
    # Open wizard, click Start — modal opens.
    await _open_wizard(page)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    # Modal Cancel.
    await page.click("#wizard-wizard_cancel_modal")
    await page.wait_for_timeout(800)
    # Assert: modal closed, wizard still inactive (Start button still in DOM).
    # Cancel does not flip `wizard_active`, so the inactive view never
    # re-rendered — but check DOM presence not CSS visibility, since the
    # active view would *remove* the button entirely.
    present = await page.evaluate(
        "() => document.getElementById('wizard-wizard_start') !== null"
    )
    assert present, "Start button should still be present after Cancel"
    print("  ok")


async def case_modal_replace(page):
    print("\n=== case 3: non-empty project modal Replace ===")
    # Load Coastal Tourism (sorted-first template) by name lookup, mirroring
    # case 2's pattern — robust if a future template sorts before it.
    await page.click("#sespy_nav_templates")
    await page.wait_for_timeout(2000)
    cards = await page.evaluate(
        "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
        ".map(e => e.textContent.trim())"
    )
    idx = cards.index("Coastal Tourism SES")
    await page.click(f"#templates-load_template_{idx}")
    await page.wait_for_timeout(2500)
    await _open_wizard(page)
    await page.click("#wizard-wizard_start")
    await page.wait_for_timeout(800)
    # Modal Continue, replace it.
    await page.click("#wizard-wizard_replace")
    await page.wait_for_timeout(1500)
    # Assert: wizard now active. Query the active pill (bg-primary class)
    # to verify which step is current — the breadcrumb renders all 12 pills
    # regardless of current step, so plain text-contains checks would be
    # vacuously true.
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("1."), (
        f"active pill should be '1. ...' for step 0, got {active_pill!r}"
    )
    # Assert: isa_data was actually cleared by Replace. Navigate to Edit
    # Data and verify the elements table is in its empty state. Without
    # this, the active-pill assertion alone passes even if Replace forgot
    # to wipe isa_data — the bug it's MEANT to catch (silent metadata-vs-
    # isa-data confusion was a recurring concern across review rounds).
    #
    # Note on the row-count quirk: `elements_table` in `isa_data_entry.py`
    # falls back to a single placeholder row of empty-string cells when
    # `isa_data.elements` is empty (`pd.DataFrame(rows or [{"id":"",...}])`).
    # So an "empty" table actually has 1 row in the DOM whose cells are
    # all blank. Assert on the joined cell text being empty rather than
    # raw row count, which is what actually distinguishes empty isa_data
    # from leftover Coastal Tourism elements.
    await page.click("#sespy_nav_entry")
    await page.wait_for_timeout(2500)
    cell_text = await page.evaluate(
        "() => Array.from(document.querySelectorAll("
        "'#entry-elements_table table tbody tr td'))"
        ".map(c => c.textContent.trim()).join('|')"
    )
    # Expected when empty: "||" (3 empty cells joined). Anything with
    # actual element labels (e.g. "el_1|Tourism|driver") means Replace
    # did not wipe isa_data.
    assert cell_text.replace("|", "") == "", (
        f"isa_data not cleared by Replace — elements table cells: "
        f"{cell_text!r}"
    )
    # Navigate back to wizard so case 4's helper finds the wizard nav
    # consistently (no cleanup work needed since helper does page.goto).
    print(f"  ok (active pill: {active_pill[:50]}, elements cleared)")


async def case_mid_nav_resume(page):
    print("\n=== case 4: mid-wizard nav and resume ===")
    # Helper reloads to get a fresh `wizard_active=False` baseline,
    # then Start → modal → Replace into an empty active wizard.
    await _start_wizard_empty_via_replace(page)
    # Advance to step 3.
    for step in range(3):
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic', {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast', {priority: 'event'})"
            )
        elif step == 2:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_countries', ['Lithuania'], {priority: 'event'})"
            )
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # Navigate away to CLD.
    await page.click("#sespy_nav_cld")
    await page.wait_for_timeout(1000)
    # Navigate back.
    await page.click("#sespy_nav_wizard")
    await page.wait_for_timeout(1500)
    # Assert active pill is "4. ..." (1-based label for step index 3).
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("4."), (
        f"active pill should be '4. ...' for step 3, got {active_pill!r}"
    )
    print(f"  ok (active: {active_pill[:50]})")


async def case_back_preserves(page):
    print("\n=== case 5: Back preserves writes ===")
    # Continue from case 4's state — wizard is on step 3 (main_issue).
    # First advance through step 3 so we land on step 4 (drivers).
    await page.evaluate(
        "() => Shiny.setInputValue('wizard-answer_main_issue', ['Eutrophication'],"
        " {priority: 'event'})"
    )
    await page.wait_for_timeout(300)
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(500)
    # Now on step 4 (drivers, freeform_multiple). Click Add to expand to a
    # second row, fill BOTH entries, then click Next. Per spec §5 case 5,
    # using 2 entries verifies that BOTH slots pre-populate on re-entry —
    # 1 entry can't distinguish "row[0] preserved" from "everything reset
    # because n_rows=1 by default".
    await page.click("#wizard-add_drivers")
    await page.wait_for_timeout(500)
    await page.fill("#wizard-entry_drivers_0", "Tourism demand")
    await page.fill("#wizard-entry_drivers_1", "Fishing pressure")
    await page.wait_for_timeout(300)
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(500)
    # Now on step 5. Click Back to return to step 4.
    await page.click("#wizard-wizard_back")
    await page.wait_for_timeout(800)
    # Step 4 renders as active pill "5. Drivers".
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("5."), (
        f"active pill should be '5. ...' for step index 4, got {active_pill!r}"
    )
    # Both rows must pre-populate from saved answers.
    val0 = await page.evaluate(
        "() => document.getElementById('wizard-entry_drivers_0')?.value"
    )
    val1 = await page.evaluate(
        "() => document.getElementById('wizard-entry_drivers_1')?.value"
    )
    assert val0 == "Tourism demand", f"row 0 lost: {val0!r}"
    assert val1 == "Fishing pressure", f"row 1 lost: {val1!r}"
    print(f"  ok (both entries preserved: {val0!r}, {val1!r})")


async def case_validation_failure(page):
    print("\n=== case 6: validation failure on freeform step ===")
    # Helper reloads to deactivate any prior wizard state, then Start
    # → modal → Replace into a fresh empty active wizard at step 0.
    await _start_wizard_empty_via_replace(page)
    for step in range(4):
        if step == 0:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_regional_sea', 'baltic', {priority: 'event'})"
            )
        elif step == 1:
            await page.evaluate(
                "() => Shiny.setInputValue('wizard-answer_ecosystem_type', 'Open coast', {priority: 'event'})"
            )
        elif step in (2, 3):
            target = "countries" if step == 2 else "main_issue"
            value_js = "['Lithuania']" if step == 2 else "['Eutrophication']"
            await page.evaluate(
                f"() => Shiny.setInputValue('wizard-answer_{target}', {value_js},"
                " {priority: 'event'})"
            )
        await page.wait_for_timeout(300)
        await page.click("#wizard-wizard_next")
        await page.wait_for_timeout(500)
    # On step 4 with empty driver — click Next.
    await page.fill("#wizard-entry_drivers_0", "   ")  # whitespace-only
    await page.click("#wizard-wizard_next")
    await page.wait_for_timeout(1000)
    # Assert: validation toast appeared AND breadcrumb still shows step 4.
    notif = await page.evaluate(
        "() => document.querySelectorAll('#shiny-notification-panel .shiny-notification').length"
    )
    assert notif >= 1, "expected validation notification"
    # Validation failed → still on step 4, active pill is "5. Drivers".
    active_pill = await page.evaluate(
        "() => document.querySelector('#wizard-wizard_breadcrumb .bg-primary')"
        "?.textContent?.trim() || ''"
    )
    assert active_pill.startswith("5."), (
        f"should still be on step 4 (pill '5. ...'), got {active_pill!r}"
    )
    print("  ok (validation triggered, step did not advance)")


async def case_claude_button_not_rendered_without_env_key(page):
    """No ANTHROPIC_API_KEY → no button at step 11.
    Pre-condition: launch app WITHOUT setting ANTHROPIC_API_KEY."""
    print("\n=== case 7: Claude button hidden without env key ===")
    await _drive_to_step_11(page)
    button = await page.query_selector("#wizard-wizard_claude_generate")
    assert button is None, "expected no button without ANTHROPIC_API_KEY"


async def case_claude_consent_modal_shows_and_dismisses_via_cancel(page):
    """First click on Generate shows consent modal; Cancel dismisses it.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key."""
    print("\n=== case 8: Claude consent modal show + Cancel ===")
    await _drive_to_step_11(page)
    # Verify button is visible (env key was set at app launch).
    await page.wait_for_selector("#wizard-wizard_claude_generate", timeout=5000)
    # Click → consent modal appears.
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # Cancel → modal closes (Bootstrap leaves nodes in DOM with display:none;
    # use state="hidden", not state="detached").
    await page.click("#wizard-wizard_claude_consent_cancel")
    await page.wait_for_selector("text=Send your project to Anthropic?",
                                  state="hidden", timeout=5000)
    # Click button again → modal re-appears (consent did not persist on decline).
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # Cleanup: dismiss modal so subsequent cases start clean.
    await page.click("#wizard-wizard_claude_consent_cancel")


async def case_claude_consent_then_confirm_yields_auth_error(page):
    """Click Generate → Confirm with the fake API key → backend raises
    AuthenticationError → toast shows 'Claude API: invalid API key.
    Used rule-based scoring.' SP3 table remains visible.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key."""
    print("\n=== case 9: Claude consent + Confirm → auth-error toast ===")
    await _drive_to_step_11(page)
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    await page.click("#wizard-wizard_claude_consent_confirm")
    # Wait for the auth error toast (the real backend will reject the fake key).
    # The exact toast text comes from wizard.claude_error_auth.
    await page.wait_for_selector("text=Claude API: invalid API key",
                                  timeout=15000)
    # SP3 table still visible (side-by-side fallback semantics).
    await page.wait_for_selector("#wizard-accept_sp3_0", timeout=2000)


async def case_back_from_step_11_dismisses_consent_modal(page):
    """Open modal, click Back without dismissing; modal goes away.
    Pre-condition: launch app with ANTHROPIC_API_KEY=test-fake-key.

    Note on the click: Bootstrap renders a .modal-backdrop overlay that
    intercepts pointer events to elements behind the modal. Playwright's
    default page.click() runs an actionability check (waits for the
    target to receive pointer events) that fails with the backdrop
    blocking. Use force=True to dispatch the click programmatically
    (bypasses backdrop), OR fall back to JS-evaluation if force=True is
    insufficient. For modal close-state assertion, use state="hidden"
    rather than state="detached" — Bootstrap modals stay in the DOM
    with display:none after close, not removed.
    """
    print("\n=== case 10: Back-from-11 dismisses consent modal ===")
    await _drive_to_step_11(page)
    await page.click("#wizard-wizard_claude_generate")
    await page.wait_for_selector("text=Send your project to Anthropic?", timeout=5000)
    # The Bootstrap .modal-backdrop overlay intercepts real pointer events to
    # the Back button behind it — even page.click(..., force=True) lands on the
    # backdrop, so the Back handler never fires. Dispatch a programmatic DOM
    # click directly on the element (no hit-testing), which Shiny's action
    # button still registers, incrementing wizard_back so _on_back runs and
    # calls ui.modal_remove().
    await page.eval_on_selector("#wizard-wizard_back", "el => el.click()")
    # Use 'hidden' (display:none) rather than 'detached' (removed from DOM).
    await page.wait_for_selector("text=Send your project to Anthropic?",
                                  state="hidden", timeout=5000)


# === Two-mode entry points ===
#
# The SP4 cases require different app-launch conditions:
#   --mode=no-key  : app launched WITHOUT ANTHROPIC_API_KEY
#                    Runs the original 6 cases + case 7 (button hidden check).
#   --mode=fake-key: app launched WITH ANTHROPIC_API_KEY=test-fake-key
#                    Runs cases 8-10 (consent/modal flow + auth-error toast).
#   (default / no --mode arg): original 6 cases only — preserves existing
#                    behavior for anyone running the script without arguments.
#
# Controller invocations:
#   Pass 1:  micromamba run -n shiny python tests/test_wizard_e2e.py --mode=no-key
#   Pass 2:  micromamba run -n shiny python tests/test_wizard_e2e.py --mode=fake-key


async def main_no_key():
    """Original 6 cases + case 7 (button not rendered without ANTHROPIC_API_KEY).
    Launch the app WITHOUT setting ANTHROPIC_API_KEY before running."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_full_run(page)
        await case_modal_cancel(page)
        await case_modal_replace(page)
        await case_mid_nav_resume(page)
        await case_back_preserves(page)
        await case_validation_failure(page)
        await case_claude_button_not_rendered_without_env_key(page)

        await page.screenshot(path="tests/screenshots/wizard_e2e.png")
        print("\nwizard e2e: 7 cases passed (no-key mode)")
        await browser.close()


async def main_fake_key():
    """Cases 8-10: consent/modal flow + auth-error toast.
    Launch the app WITH ANTHROPIC_API_KEY=test-fake-key before running."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_claude_consent_modal_shows_and_dismisses_via_cancel(page)
        await case_claude_consent_then_confirm_yields_auth_error(page)
        await case_back_from_step_11_dismisses_consent_modal(page)

        await page.screenshot(path="tests/screenshots/wizard_e2e_sp4.png")
        print("\nwizard e2e: 3 SP4 cases passed (fake-key mode)")
        await browser.close()


async def main():
    """Default: original 6 cases only. Preserves existing behavior."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")

        await case_full_run(page)
        await case_modal_cancel(page)
        await case_modal_replace(page)
        await case_mid_nav_resume(page)
        await case_back_preserves(page)
        await case_validation_failure(page)

        await page.screenshot(path="tests/screenshots/wizard_e2e.png")
        print("\nwizard e2e: 6 cases passed")
        await browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wizard e2e test runner")
    parser.add_argument(
        "--mode",
        choices=["no-key", "fake-key"],
        default=None,
        help=(
            "no-key: run original 6 cases + case 7 (app launched without ANTHROPIC_API_KEY); "
            "fake-key: run cases 8-10 (app launched with ANTHROPIC_API_KEY=test-fake-key); "
            "omit to run original 6 cases only (default/legacy behavior)."
        ),
    )
    args = parser.parse_args()

    if args.mode == "no-key":
        asyncio.run(main_no_key())
    elif args.mode == "fake-key":
        asyncio.run(main_fake_key())
    else:
        asyncio.run(main())


# === Deferred cases (require in-process Shiny test infrastructure) ===
#
# The following 3 SP4 e2e cases require ability to inject specific
# `ValidationOutcome` responses into a running Shiny app — which is not
# currently possible with the existing standalone-script + cross-process
# pattern. They are documented here as TODOs for a future SP that adds
# in-process test harness (per spec §11 open questions):
#
# 1. case_claude_consent_then_generate_renders_sp4_table
#    Confirm clicked → SP4 table renders with hardcoded suggestions.
#    Requires: stub `claude_backend.suggest_connections` in app process.
#
# 2. case_observer_failed_status_disables_retry_after
#    RateLimitError with retry_after=30 → button shows
#    "Rate limited — retry in 30 s" and is disabled.
#    Requires: inject RateLimitError from app process.
#
# 3. case_drop_counts_badge_renders_when_validation_drops
#    Specific raw_count > suggestions count → "Showing 3 of 5" badge.
#    Requires: inject ValidationOutcome with specific drop counts.
#
# Until in-process testing exists, these contracts are pinned by the
# unit tests in tests/test_claude_backend.py (orchestrator + observer
# behavior) plus manual smoke tests during release verification.
