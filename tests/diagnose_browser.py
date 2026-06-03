"""Diagnostic script: load the running app in headless Chromium and capture
console messages, page errors, and the final DOM state. Not a test — run it
manually after `shiny run --port 8769 app.py`.
"""

import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()

        console_events: list[str] = []
        page.on("console", lambda m: console_events.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_events.append(f"[pageerror] {e}"))

        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        # Give the bridge + initial reactive flush a moment
        await page.wait_for_timeout(2500)

        # Click into the Loop Analysis tab so it materializes in the DOM,
        # then click Detect to populate the network.
        try:
            await page.get_by_role("tab", name="Loop Analysis").click()
            await page.wait_for_timeout(800)
            await page.get_by_role("button", name="Detect loops").click()
            await page.wait_for_timeout(2000)
        except Exception as e:
            console_events.append(f"[click-error] {e}")

        cld_html = await page.evaluate("document.getElementById('cld-network')?.innerHTML || '<missing>'")
        loops_html = await page.evaluate("document.getElementById('loops-loop_network')?.innerHTML || '<missing>'")
        vis_loaded = await page.evaluate("typeof vis !== 'undefined'")
        bridge_loaded = await page.evaluate("typeof Shiny !== 'undefined' && !!Shiny.addCustomMessageHandler")
        net_count = await page.evaluate("document.querySelectorAll('.vis-network').length")

        # Skip the toggle — we want a clean read of the initial render

        # Also dump the underlying layout engine's actual config — vis-network
        # stores hierarchical settings under net.layoutEngine.options
        net_state = await page.evaluate("""() => {
          const state = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
          if (!state || !state.network) return null;
          const net = state.network;
          const opts = net.body && net.body.options ? net.body.options : {};
          const layout = opts.layout || {};
          const hier = layout.hierarchical || {};
          // Probe the layout engine directly
          const le = net.layoutEngine || {};
          const leOpts = le.options || {};
          window._netDiag = {
            body_layout: layout,
            body_options_keys: Object.keys(opts),
            body_physics: opts.physics,
            physics_module_options: net.physics ? net.physics.options : null,
            physics_simulating: net.physics ? net.physics.physicsEnabled : null,
            layoutEngine_options: leOpts,
            layoutEngine_hierarchical: leOpts.hierarchical,
          };
          const nodes = state.nodes ? state.nodes.get() : [];
          const positions = net.getPositions ? net.getPositions() : {};
          const ordered = nodes
            .map(n => ({ id: n.id, group: n.group, level: n.level,
                         y: positions[n.id] ? Math.round(positions[n.id].y) : null,
                         x: positions[n.id] ? Math.round(positions[n.id].x) : null }))
            .sort((a, b) => (a.y == null ? 9e9 : a.y) - (b.y == null ? 9e9 : b.y));
          return {
            hier_enabled: hier.enabled,
            hier_direction: hier.direction,
            hier_levelSeparation: hier.levelSeparation,
            hier_nodeSpacing: hier.nodeSpacing,
            hier_sortMethod: hier.sortMethod,
            physics_enabled: opts.physics ? opts.physics.enabled : null,
            ordered_nodes: ordered,
          };
        }""")
        print("\n=== rendered vis-network state ===")
        import json as _j
        print(_j.dumps(net_state, indent=2, default=str))

        # Deep diag: layout engine internals
        deep = await page.evaluate("""() => window._netDiag""")
        print("\n=== layoutEngine deep state ===")
        print(_j.dumps(deep, indent=2, default=str))

        outer_attrs = await page.evaluate("""() => {
          const el = document.getElementById('cld-network');
          if (!el) return null;
          const cs = getComputedStyle(el);
          // Walk parents up to body to find what sets display: contents
          const chain = [];
          let cur = el;
          while (cur && cur.tagName !== 'BODY') {
            chain.push({
              tag: cur.tagName.toLowerCase(),
              id: cur.id,
              cls: cur.className,
              display: getComputedStyle(cur).display,
              h: cur.getBoundingClientRect().height,
            });
            cur = cur.parentElement;
          }
          return {
            tagName: el.tagName,
            class: el.className,
            inline_style: el.getAttribute('style'),
            computed_display: cs.display,
            computed_height: cs.height,
            offsetHeight: el.offsetHeight,
            child_count: el.children.length,
            parent_tag: el.parentElement?.tagName,
            parent_class: el.parentElement?.className,
            chain: chain,
          };
        }""")
        print("\n=== outer #cld-network attrs + parent chain ===")
        import json as _j
        print(_j.dumps(outer_attrs, indent=2))

        # Visibility check: actual rendered dimensions of every layer
        dims = await page.evaluate("""() => {
          const out = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return { w: Math.round(r.width), h: Math.round(r.height),
                     display: cs.display, visibility: cs.visibility,
                     overflow: cs.overflow, zIndex: cs.zIndex };
          };
          return {
            outer: out('#cld-network'),
            container: out('#cld-network .pyvis-container'),
            canvas_div: out('#cld-network .pyvis-network-canvas'),
            vis_network: out('#cld-network .vis-network'),
            inner_canvas: out('#cld-network canvas'),
          };
        }""")

        print("=== console / errors ===")
        for e in console_events:
            print(e)
        print("\n=== runtime state ===")
        print(f"window.vis loaded:       {vis_loaded}")
        print(f"Shiny + handlers ready:  {bridge_loaded}")
        print(f"vis-network canvases:    {net_count}")
        print(f"\n#cld-network inner:        {cld_html[:200]}")
        print(f"#loops-loop_network inner: {loops_html[:200]}")
        print("\n=== layer dimensions ===")
        import json
        print(json.dumps(dims, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
