"""Probe each ancestor of #cld-network and report any with a visible border."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        result = await page.evaluate("""() => {
          let cur = document.getElementById('cld-network');
          const out = [];
          while (cur && cur.tagName !== 'BODY') {
            const cs = getComputedStyle(cur);
            const has_border = cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none';
            const has_bg = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent';
            out.push({
              tag: cur.tagName.toLowerCase(),
              cls: cur.className,
              border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
              bg: cs.backgroundColor,
              has_border: has_border,
              has_bg: has_bg,
              padding: cs.padding,
              margin: cs.margin,
            });
            cur = cur.parentElement;
          }
          return out;
        }""")
        for i, r in enumerate(result):
            mark = " <-- frame" if r["has_border"] else ""
            print(f"{i:2d} {r['tag']:6s} {r['cls'][:60]:60s} border={r['border']}{mark}")
        await browser.close()


asyncio.run(main())
