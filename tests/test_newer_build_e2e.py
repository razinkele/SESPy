"""E2E for P0b: a project saved by a newer SESPy.

Uploading such a file shows a persistent warning, autosave never writes it
(it would replace the user's last good state with a copy that lost the
newer data), Save names its copy "-older-format", and loading a normal
project afterwards clears the warning and resumes autosave. The resumed
autosave is also the positive control: without it, "no autosave file"
could pass only because autosave was not running at all.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

# Make the repo root importable when this script is run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

from sespy.autosave import autosave_path, clear_autosave

URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
TOKEN_JS = "() => window.localStorage.getItem('sespy_browser_token')"
WARNING = "#shiny-notification-newer-build-warning"


def newer_build_file(dest: Path) -> Path:
    raw = json.loads((ROOT / "data" / "sample_ses.json").read_text(encoding="utf-8"))
    payload = {
        "metadata": {"name": "From the future", "schema_version": 99,
                     "min_sespy_version": "99.0.0"},
        "isa_data": raw.get("isa_data", raw),
        # A block this build does not know; it is dropped on load.
        "response_measures": {"measures": [{"ID": "RM1"}]},
    }
    # And an element field this build does not know (must not crash load).
    payload["isa_data"]["elements"][0]["indicator"] = "SST"
    dest.write_text(json.dumps(payload), encoding="utf-8")
    return dest


async def wait_token(page) -> str:
    for _ in range(40):          # up to 20 s
        token = await page.evaluate(TOKEN_JS)
        if token:
            return token
        await page.wait_for_timeout(500)
    raise AssertionError("browser token never appeared in localStorage")


async def indicator_text(page) -> str:
    return await page.evaluate(
        "() => document.querySelector('.sespy-autosave-indicator')?.textContent || ''"
    )


async def wait_for_autosave(page, path: Path) -> None:
    for _ in range(60):          # up to 30 s
        if path.exists() and "Auto-saved" in await indicator_text(page):
            return
        await page.wait_for_timeout(500)
    raise AssertionError(f"normal project was not autosaved to {path}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        # Save link's href rides the first flush; see test_quick_actions_e2e.
        await page.wait_for_function(
            "() => { const a = document.getElementById('save_project');"
            " return !!a && !a.classList.contains('disabled')"
            " && !!a.getAttribute('href'); }",
            timeout=60000,
        )
        token = await wait_token(page)
        clear_autosave(token=token)
        path = autosave_path(token)
        # Let the recovery check finish: autosave is off until it has run.
        await page.wait_for_timeout(3000)

        # ---- Positive control: a normal project autosaves -----------------
        await page.click("#new_project")
        await wait_for_autosave(page, path)
        good = path.read_bytes()
        print("normal project: autosaved, indicator shown")

        with tempfile.TemporaryDirectory() as tmp:
            # ---- Upload a newer-build file: warning, and no autosave ------
            await page.set_input_files(
                "#load_project", str(newer_build_file(Path(tmp) / "future.json")))
            await page.wait_for_selector(WARNING, timeout=30000)
            text = await page.locator(WARNING).text_content() or ""
            print(f"warning: {text.strip()[:160]!r}")
            assert "newer SESPy" in text, f"unexpected warning text: {text!r}"
            assert "99" in text, "warning does not say which version is needed"

            await page.wait_for_timeout(5000)
            assert path.read_bytes() == good, "a newer-build project was autosaved"
            assert "Auto-saved" not in await indicator_text(page),                 "indicator still claims this project is autosaved"
            print("newer-build project: warning shown, autosave skipped")

            # ---- Save writes a clearly named copy; earlier autosave kept ---
            async with page.expect_download(timeout=30000) as dl_info:
                await page.click("#save_project")
            download = await dl_info.value
            name = download.suggested_filename
            print(f"save filename: {name}")
            assert name.endswith("-older-format.json"), f"unexpected filename {name!r}"
            await page.wait_for_timeout(1000)
            assert path.exists(), "saving the older-format copy deleted the autosave"
            await page.screenshot(path="tests/screenshots/newer_build.png")

            # ---- Closing the warning, then loading another such file ------
            # must warn again (same stamps, so the same details).
            await page.click(f"{WARNING} .shiny-notification-close")
            await page.wait_for_selector(WARNING, state="detached", timeout=10000)
            await page.set_input_files(
                "#load_project", str(newer_build_file(Path(tmp) / "future2.json")))
            await page.wait_for_selector(WARNING, timeout=30000)
            print("second newer-build load: warning shown again")

        # ---- A normal project clears the warning and resumes autosave -----
        before = path.stat().st_mtime_ns     # read first: autosave may be fast
        await page.click("#new_project")
        await page.wait_for_selector(WARNING, state="detached", timeout=30000)
        for _ in range(60):          # up to 30 s
            if path.exists() and path.stat().st_mtime_ns != before:
                break
            await page.wait_for_timeout(500)
        assert path.stat().st_mtime_ns != before,             "autosave did not resume after a normal project loaded"
        print("normal project: warning cleared, autosave resumed")

        clear_autosave(token=token)
        await browser.close()
        print("\nnewer-build e2e assertions pass")


asyncio.run(main())
