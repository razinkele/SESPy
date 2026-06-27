"""Diagnose what bslib uses for the grid layout in page_sidebar."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Find the grid container — walk up from #cld-network looking for
        # display: grid.
        info = await page.evaluate("""() => {
          // Find ALL bslib-sidebar-layout instances and report their
          // parents so we know how to target the outer one specifically.
          const all = Array.from(document.querySelectorAll('.bslib-sidebar-layout'));
          const summary = all.map((el, i) => {
            const p = el.parentElement;
            return {
              idx: i,
              parent_tag: p?.tagName.toLowerCase(),
              parent_cls: p?.className,
              has_card_ancestor: !!el.closest('.sespy-card'),
              grid_cols: getComputedStyle(el).gridTemplateColumns,
            };
          });
          window._allLayouts = all;
          let cur = all.find(el => !el.closest('.sespy-card')) || all[0];
          if (!cur) return { all_layouts: summary };
          const cs = getComputedStyle(cur);
          // Pull all CSS custom properties starting with --
          const vars = {};
          for (let i = 0; i < cs.length; i++) {
            const n = cs[i];
            if (n.startsWith('--')) vars[n] = cs.getPropertyValue(n).trim();
          }
          return {
            tag: cur.tagName.toLowerCase(),
            cls: cur.className,
            parent_chain: (() => {
              const out = [];
              let p = cur.parentElement;
              for (let i = 0; i < 5 && p; i++) {
                out.push(p.tagName.toLowerCase() + '.' + (p.className || '').replace(/ /g, '.'));
                p = p.parentElement;
              }
              return out;
            })(),
            display: cs.display,
            grid_template_columns: cs.gridTemplateColumns,
            all_layouts: summary,
            css_vars_with_sidebar_or_width: Object.fromEntries(
              Object.entries(vars).filter(([k]) =>
                k.toLowerCase().includes('sidebar') ||
                k.toLowerCase().includes('width'))
            ),
          };
        }""")
        import json
        print(json.dumps(info, indent=2))
        await browser.close()


asyncio.run(main())
