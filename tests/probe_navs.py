import asyncio

from playwright.async_api import async_playwright


async def m():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
              if m.type in ("error", "warning") else None)
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(6000)
        info = await pg.evaluate("""() => {
          const host = document.getElementById('sespy_nav_render');
          return {
            host_exists: !!host,
            host_class: host?.className,
            host_html_len: host?.innerHTML?.length || 0,
            host_html_preview: host?.innerHTML?.slice(0, 300) || '',
            shiny_outputs: Array.from(document.querySelectorAll('.shiny-html-output, [class*=shiny]')).slice(0, 5).map(e => ({id: e.id, cls: e.className})),
            buttons: Array.from(document.querySelectorAll('.sespy-nav-btn')).map(e => e.id),
          };
        }""")
        import json
        print(json.dumps(info, indent=2))
        for e in errors[:8]:
            print("ERR:", e[:300])
        await b.close()


asyncio.run(m())
