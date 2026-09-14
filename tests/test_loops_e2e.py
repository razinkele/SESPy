"""E2E for delay-aware Loop Analysis: detect loops, confirm an oscillation-prone
loop is reported and its delayed edge renders dashed in the loop network."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # The nav is a @render.ui output: it does not exist until the
        # session's first flush (32 s on an idle machine, more under
        # load). Without this the click falls back to Playwright's 30 s
        # default and races startup.
        await page.wait_for_selector("#sespy_nav_loops", timeout=60000)
        await page.click("#sespy_nav_loops")
        await page.wait_for_timeout(1500)
        # Run detection
        await page.click("#loops-detect")
        # Poll until the loops table populates (data_frame <tbody> late-mounts)
        await page.wait_for_selector("#loops-loops_table table tbody tr", timeout=30000)
        # The picker is a separate output_ui-rendered <select> that flushes as its
        # own Shiny message — wait for it too before reading/setting selectedIndex.
        await page.wait_for_selector("#loops-selected_loop", timeout=30000)

        # Behaviour is column 2; find the index of the oscillation-prone row.
        # The picker (#loops-selected_loop) options are in the SAME order as the
        # table rows (both come from classify_loops), so the row index == option index.
        behaviors = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#loops-loops_table table tbody tr')).map("
            "tr => (tr.querySelector('td:nth-child(2)')?.textContent || '').trim())"
        )
        print("behaviors:", behaviors)
        osc_idx = next((i for i, b in enumerate(behaviors) if "scill" in b.lower()), -1)
        assert osc_idx >= 0, f"no oscillation-prone loop reported: {behaviors}"

        # Deterministically select the oscillation-prone loop in the picker.
        ok = await page.evaluate(
            "(i) => { const el=document.getElementById('loops-selected_loop');"
            " if(!el) return false;"
            " el.selectedIndex=i; el.dispatchEvent(new Event('change',{bubbles:true})); return true; }",
            osc_idx,
        )
        assert ok, "#loops-selected_loop not mounted"

        # Pin the poll to the SELECTED loop: the network is already mounted for
        # the DEFAULT loop (analysis_loops.py:324-336 — selected_row() falls back
        # to rows[0]), so a non-empty edge list is NOT evidence of the re-render.
        row_path = await page.evaluate(
            "(i) => { const tr=document.querySelectorAll("
            "'#loops-loops_table table tbody tr')[i]; if(!tr) return null;"
            " const td=tr.querySelectorAll('td');"
            " return (td[5]?.textContent || '').trim(); }",
            osc_idx,
        )
        assert row_path, f"could not read the path cell of loops table row {osc_idx}"

        # Read the rendered loop network's edge `dashes` flags: the delayed edge
        # must be dashed AND at least one edge must be solid. Poll until the
        # network's OWN nodes/edges spell the selected row's path in order
        # (network.py:1770-1771 path == labels joined by ' → ' plus the first
        # label repeated; analysis_loops.py:74 node labels come from the same
        # map), so neither a stale default render nor a reverse-direction loop
        # over the same nodes can satisfy it.
        dashes = None
        for _ in range(60):
            await page.wait_for_timeout(500)
            state = await page.evaluate(
                "(p) => { const s=window.pyvisNetworks && window.pyvisNetworks['loops-loop_network'];"
                " if(!s || !s.nodes || !s.edges) return {dashes: null, ready: false};"
                " const ns=s.nodes.get(), es=s.edges.get();"
                " const lbl={}; ns.forEach(n => { lbl[n.id]=String(n.label); });"
                " const want=p.split(' → ').slice(0, -1);"
                " const seen=new Set(es.map(e => lbl[e.from] + '→' + lbl[e.to]));"
                " const ready = want.length === ns.length && es.length === want.length"
                "   && want.every((l, i) => seen.has(l + '→' + want[(i + 1) % want.length]));"
                " return {dashes: es.map(e => e.dashes === true), ready: ready}; }",
                row_path,
            )
            if state["ready"]:
                dashes = state["dashes"]
                break
        print("dashes:", dashes)
        assert dashes, (
            "loop network never re-rendered for the selected loop "
            f"({row_path})"
        )
        assert any(dashes), "no dashed (delayed) edge in the oscillation-prone loop"
        assert not all(dashes), "expected at least one solid (immediate) edge too"

        await page.screenshot(path="tests/screenshots/loops.png")
        print("\nloops e2e assertions pass")

        # --- Uncertainty toggle adds loop probability columns ---
        await page.fill("#loops-n_samples", "50")
        await page.dispatch_event("#loops-n_samples", "change")
        await page.check("#loops-show_uncertainty")
        found_exist = False
        headers = []
        for _ in range(30):
            await page.wait_for_timeout(1000)
            headers = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#loops-loops_table table thead th')).map(th => th.textContent.trim())"
            )
            if any("%" in h for h in headers):
                found_exist = True
                break
        assert found_exist, f"loop probability columns not added: {headers}"
        print("loops uncertainty probability columns: OK")

        await browser.close()


asyncio.run(main())
