"""E2E: the shell skin (sespy-skin.css + themes.css) is served and applied."""
import asyncio

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#cld-network", timeout=30000)

        # 1) sespy-skin.css guard: .pyvis-network-output is positioned.
        pos = await page.evaluate(
            "() => getComputedStyle(document.querySelector('.pyvis-network-output')).position"
        )
        print("pyvis-network-output position:", pos)
        assert pos == "relative", f"skin not applied (position={pos!r}) — sespy-skin.css not served?"

        # 2) sespy-skin.css spinner: forcing is-loading resolves the ::before label.
        content = await page.evaluate(
            "() => { const el = document.querySelector('.pyvis-network-output');"
            " el.classList.add('is-loading');"
            " return getComputedStyle(el, '::before').content; }"
        )
        print("spinner ::before content:", content)
        assert "Rendering network" in content, f"spinner rule missing (content={content!r})"

        # 3) themes.css: deep-ocean flips the body background to the dark navy.
        bg = await page.evaluate(
            "() => { document.documentElement.setAttribute('data-theme', 'deep-ocean');"
            " return getComputedStyle(document.body).backgroundColor; }"
        )
        print("deep-ocean body bg:", bg)
        assert bg == "rgb(11, 31, 51)", f"themes.css not applied (bg={bg!r})"

        print("\nshell skin e2e assertions pass")
        await browser.close()


asyncio.run(main())
