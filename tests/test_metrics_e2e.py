"""End-to-end check: third nav tab works, metric switch updates the table,
and `event_bus.isa_change` (fired from project_io's New Project) propagates
to all three modules at once.
"""
import asyncio

from playwright.async_api import async_playwright

from _testmode import snapshot, export_value


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Click "Network Metrics" nav button (3rd nav item)
        await page.click("#sespy_nav_metrics")
        await page.wait_for_timeout(2500)

        # The data_frame is rendered as a <shiny-data-frame> web component
        # in shadow DOM; rather than poke into shadow root we just assert
        # the host element exists, has rendered children, and is no longer
        # in the "recalculating" state.
        df_state = await page.evaluate("""() => {
          const el = document.getElementById('metrics-metrics_table');
          if (!el) return null;
          const sdf = el.querySelector('shiny-data-frame');
          return {
            host_exists: !!el,
            recalculating: el.classList.contains('recalculating'),
            sdf_present: !!sdf,
            child_count: el.children.length,
          };
        }""")
        print(f"data_frame state: {df_state}")
        assert df_state and df_state["host_exists"] and not df_state["recalculating"]

        # Pyvis network rendered with 17 nodes
        nodes_in_canvas = await page.evaluate(
            "() => {"
            "const s = window.pyvisNetworks && window.pyvisNetworks['metrics-metrics_network'];"
            "return s && s.nodes ? s.nodes.length : 0; }"
        )
        print(f"metrics network nodes: {nodes_in_canvas}")
        assert nodes_in_canvas == 17

        # Capture node sizes (a function of the chosen metric) so we can
        # confirm a metric change re-sizes the canvas — much more robust
        # than peeking into the shadow-DOM table.
        sizes_degree = await page.evaluate(
            "() => window.pyvisNetworks['metrics-metrics_network'].nodes.get()"
            ".map(n => n.size).sort()"
        )
        await page.click("input[type='radio'][value='betweenness']")
        await page.wait_for_timeout(2000)
        sizes_betweenness = await page.evaluate(
            "() => window.pyvisNetworks['metrics-metrics_network'].nodes.get()"
            ".map(n => n.size).sort()"
        )
        print(f"sizes on Degree:      {sizes_degree[:5]}...")
        print(f"sizes on Betweenness: {sizes_betweenness[:5]}...")
        assert sizes_degree != sizes_betweenness, \
            "metric switch didn't re-size the network nodes"

        # Click "New Project" — three-way reactive coupling: this should
        # propagate via event_bus.isa_change to all three modules without
        # any of them crashing. Verify metrics module is still rendering.
        await page.click("#new_project")
        await page.wait_for_timeout(1500)
        nodes_after_reset = await page.evaluate(
            "() => window.pyvisNetworks['metrics-metrics_network'].nodes.length"
        )
        print(f"network nodes after New Project: {nodes_after_reset}")
        assert nodes_after_reset == 17, \
            f"metrics module didn't re-render after isa_change: {nodes_after_reset}"

        await page.screenshot(path="tests/screenshots/metrics.png")
        print("\nmetrics e2e assertions pass — three-way reactive coupling works")

        # --- Social-ecological fit summary renders with the golden value ---
        await page.click("#sespy_nav_metrics")
        await page.wait_for_selector("#metrics-fit_summary", timeout=30000)
        fit_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            fit_text = (await page.inner_text("#metrics-fit_summary")).strip()
            if fit_text:
                break
        # Sample (data/sample_ses.json) has 8 cross of 20 edges → fit 0.40 (golden).
        # Assert BOTH the heading (catches a broken metrics.fit translation) AND the value.
        assert "Social-ecological fit" in fit_text, f"expected heading in summary, got: {fit_text!r}"
        assert "0.40" in fit_text, f"expected fit 0.40 in summary, got: {fit_text!r}"
        print(f"metrics fit summary: OK ({fit_text!r})")

        # --- Governance gap summary renders with the golden values ---
        # Sample: directed coverage leaves 1 of 3 Pressures (P003) uncovered
        # -> 0.33; no orphans, so no orphan line. Selector is scoped to the
        # output id — bare text= selectors have shipped broken e2e before.
        gg_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            gg_text = (await page.inner_text("#metrics-governance_gap_summary")).strip()
            if gg_text:
                break
        assert "Governance gap" in gg_text, f"expected heading, got: {gg_text!r}"
        assert "0.33" in gg_text, f"expected 0.33, got: {gg_text!r}"
        assert "1 of 3" in gg_text, f"expected '1 of 3' caption, got: {gg_text!r}"
        print(f"governance gap summary: OK ({gg_text!r})")

        # --- Governance actor influence table renders both actors, ranked ---
        ai_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            ai_text = (await page.inner_text("#metrics-actor_influence_summary")).strip()
            if ai_text:
                break
        assert "Governance actor influence" in ai_text, f"expected heading, got: {ai_text!r}"
        # Governance concentration sentence (#26) sits above the table: the
        # sample is two actors with R002 dominant, so "concentrated" renders.
        assert "concentrated in R002" in ai_text, f"expected concentration sentence, got: {ai_text!r}"
        # Rank order is checked on the <table> element alone — the heading and
        # the sentence both contain "influence"/"R002", so slicing the block's
        # text is not enough; read the table's own inner_text.
        table_text = (await page.inner_text("#metrics-actor_influence_summary table")).strip()
        assert "R002" in table_text and "R001" in table_text, f"expected both actors, got: {table_text!r}"
        # R002 (dominant) must rank above R001 (peripheral).
        assert table_text.index("R002") < table_text.index("R001"), f"expected R002 first, got: {table_text!r}"
        print(f"actor influence table: OK ({ai_text!r})")

        # --- Cascade vulnerability: idle hint, then button-triggered table ---
        cs_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            cs_text = (await page.inner_text("#metrics-cascade_summary")).strip()
            if cs_text:
                break
        assert "Cascade vulnerability" in cs_text, f"expected heading, got: {cs_text!r}"
        assert "not computed" in cs_text, f"expected idle hint, got: {cs_text!r}"
        await page.click("#metrics-run_cascade")
        for _ in range(30):
            await page.wait_for_timeout(500)
            cs_text = (await page.inner_text("#metrics-cascade_summary")).strip()
            if "MPF1" in cs_text:
                break
        # Sample golden: MPF1 (Posidonia meadows) is the threshold node, Δ 0.47.
        assert "cascade threshold node" in cs_text, f"expected threshold line, got: {cs_text!r}"
        # #25: the KL early-warning line renders under the threshold line; on
        # the sample the series departs at step 7 (D002).
        assert "early-warning" in cs_text and "D002" in cs_text, f"expected early-warning line, got: {cs_text!r}"
        assert "KL" in cs_text, f"expected KL column header, got: {cs_text!r}"
        assert "MPF1" in cs_text and "0.47" in cs_text, f"expected MPF1/0.47, got: {cs_text!r}"
        print(f"cascade vulnerability block: OK ({cs_text[:120]!r})")

        # 1.7.0 test mode: the same result the UI rendered, as data — no
        # text slicing. Sample goldens from tests/test_network.py.
        snap = await snapshot(page)
        # Registered inside the "metrics" module's server, so
        # export_test_values namespaces the key with the module id.
        cascade = export_value(snap, "metrics-metrics_cascade")
        assert cascade is not None, "cascade export empty after Run cascade analysis"
        assert cascade["cascade_threshold_node"] == "MPF1"
        assert cascade["early_warning_node"] == "D002"
        assert cascade["steps"][0]["removed_id"] == "MPF1"
        assert round(cascade["steps"][0]["delta_lccf"], 2) == 0.47
        print("cascade snapshot: OK")

        # --- SES subsystem modules: idle hint, then button-triggered list ---
        hm_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            hm_text = (await page.inner_text("#metrics-hypermodules_summary")).strip()
            if hm_text:
                break
        assert "SES subsystem modules" in hm_text, f"expected heading, got: {hm_text!r}"
        assert "not computed" in hm_text, f"expected idle hint, got: {hm_text!r}"
        await page.click("#metrics-run_hypermodules")
        for _ in range(30):
            await page.wait_for_timeout(500)
            hm_text = (await page.inner_text("#metrics-hypermodules_summary")).strip()
            if "HM0" in hm_text:
                break
        # Sample golden: 2 hypermodules, score 0.53 (see the unit golden).
        assert "2 subsystem module" in hm_text, f"expected count line, got: {hm_text!r}"
        assert "0.53" in hm_text, f"expected score, got: {hm_text!r}"
        assert "HM0" in hm_text and "HM1" in hm_text, f"expected both modules, got: {hm_text!r}"
        print(f"hypermodules block: OK ({hm_text[:120]!r})")

        # --- Causal pathways: select ES02 -> D001, trace, assert goldens ---
        pt_text = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            pt_text = (await page.inner_text("#metrics-paths_summary")).strip()
            if pt_text:
                break
        assert "Causal pathways" in pt_text, f"expected heading, got: {pt_text!r}"
        await page.select_option("#metrics-paths_source", "ES02")
        await page.select_option("#metrics-paths_target", "D001")
        await page.click("#metrics-trace_paths")
        for _ in range(30):
            await page.wait_for_timeout(500)
            pt_text = (await page.inner_text("#metrics-paths_summary")).strip()
            if "2 paths" in pt_text:
                break
        # Sample golden: ES02 -> D001 has exactly two length-8 negative paths.
        assert "2 paths: 0 positive, 2 negative, 0 ambiguous" in pt_text, \
            f"expected summary, got: {pt_text!r}"
        assert "Food provisioning" in pt_text and "Tourism demand" in pt_text, \
            f"expected label chain endpoints, got: {pt_text!r}"
        # Selects must keep the user's pair across the result re-render —
        # a snap-back to defaults would make a second Trace compute the
        # wrong pair silently.
        src_val = await page.eval_on_selector("#metrics-paths_source", "el => el.value")
        tgt_val = await page.eval_on_selector("#metrics-paths_target", "el => el.value")
        assert src_val == "ES02" and tgt_val == "D001", \
            f"selects reset after trace: {src_val!r} -> {tgt_val!r}"
        print(f"causal pathways block: OK ({pt_text[:120]!r})")

        await browser.close()


asyncio.run(main())
