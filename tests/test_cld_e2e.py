"""E2E: the main CLD network dashes the seeded delayed edge."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        # CLD is the default tab; wait for its network container to mount so a
        # "tab never rendered" failure is distinct from an "edges empty" timeout.
        await page.wait_for_selector("#cld-network", timeout=30000)
        # Poll until the network DataSet has edges.
        dashes = None
        for _ in range(16):
            res = await page.evaluate(
                "() => { const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];"
                " if (!s || !s.edges) return null;"
                " const es = s.edges.get();"
                " return { n: es.length, dashes: es.map(e => e.dashes === true) }; }"
            )
            if res and res["n"]:
                dashes = res
                break
            await page.wait_for_timeout(500)
        print("cld edges:", dashes)
        assert dashes is not None, "cld-network edges not readable"
        assert dashes["n"] == 20, f"expected 20 edges (default, unfiltered), got {dashes['n']}"
        flags = dashes["dashes"]
        assert any(flags), "no dashed (delayed) edge in the CLD"
        assert not all(flags), "expected at least one solid (immediate) edge too"

        # --- network loading spinner (shared shell) ---
        # End-state only (do NOT race the transient visible spinner):
        #  (1) the sticky marker proves the show path ran (is-loading was added);
        #  (2) is-loading must clear once the graph is up (via <id>_ready or the
        #      8s fallback).
        shown = await page.evaluate(
            "() => document.getElementById('cld-network')"
            "  && document.getElementById('cld-network').getAttribute('data-sespy-net-shown') === '1'"
        )
        assert shown, "#cld-network never entered loading state (spinner show path dead)"
        not_loading = False
        for _ in range(24):  # up to ~12s: covers <id>_ready and the 8s fallback
            not_loading = await page.evaluate(
                "() => { const el = document.getElementById('cld-network');"
                " return !!el && !el.classList.contains('is-loading'); }"
            )
            if not_loading:
                break
            await page.wait_for_timeout(500)
        assert not_loading, "#cld-network stuck in .is-loading after the graph rendered"
        # Provenance: the physics-off CLD MUST hide via the fork's _ready signal,
        # not the 8s fallback. Without this, a broken _ready hide is masked by the
        # fallback (poll window > fallback) and the test would pass while users see
        # an 8s frozen spinner.
        hidden_by = await page.evaluate(
            "() => { const el = document.getElementById('cld-network');"
            " return el && el.getAttribute('data-sespy-net-hidden'); }"
        )
        assert hidden_by == "ready", \
            f"CLD hid via {hidden_by!r}, not '_ready' — fallback masked a broken hide path"
        print("network spinner show->hide (via _ready): OK")

        await page.screenshot(path="tests/screenshots/cld.png")
        print("\ncld e2e assertions pass")
        await browser.close()


asyncio.run(main())
