import asyncio

from playwright.async_api import async_playwright


async def m():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.click("#sespy_nav_metrics")
        await pg.wait_for_timeout(2500)

        info = await pg.evaluate("""() => {
          const el = document.getElementById('metrics-metrics_table');
          if (!el) return null;
          // Walk descendants and report row-like elements
          const rows = el.querySelectorAll('tr, [role=row], [class*=row]');
          return {
            class: el.className,
            child_count: el.children.length,
            row_count: rows.length,
            html_head: el.innerHTML.slice(0, 800),
          };
        }""")
        import json
        print(json.dumps(info, indent=2))
        await b.close()


asyncio.run(m())
