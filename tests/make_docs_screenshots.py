#!/usr/bin/env python
"""Shoot documentation screenshots of every SESPy nav panel against a live app.

Standalone Playwright script in the same style as `tests/test_*_e2e.py`: it
drives http://127.0.0.1:<port> (start the server yourself, e.g.
`shiny run --port 8000 app.py` with PYTHONPATH set to the repo root), walks
the 19 nav panels in app.py NAV order, triggers the button-gated analysis
blocks so their results are visible, and writes `<out>/<nav value>.png` for
each panel plus a handful of extras (metrics_cascade, simulation_montecarlo,
about_overview, about_manual, full_app).

Nothing here mutates the loaded project: no New Project, no template load,
no wizard start, no add/remove rows. Every later panel (and the D001/P001
ids used below) depends on the untouched default sample.

Usage:  python tests/make_docs_screenshots.py [--port 8000] [--out docs/screenshots]

Exit status is non-zero if any panel shot could not be produced. A gated
result that did not render in time is a WARN line, not a failure — the shot
is still taken.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent

# app.py NAV order (nav value -> readiness probe). Probe kinds:
#   ("text", sel)   -> inner_text of sel non-empty
#   ("sel", sel)    -> selector present in DOM
#   ("pyvis", key)  -> window.pyvisNetworks[key].nodes registered
NAV_ORDER = [
    ("pims",         ("text",  "#pims-current_status")),
    ("stakeholders", ("sel",   "#stakeholders-stakeholder_table table tbody tr")),
    ("templates",    ("text",  "#templates-templates_list")),
    ("wizard",       ("sel",   "#wizard-wizard_start")),
    ("entry",        ("sel",   "#entry-elements_table table tbody tr")),
    ("rate",         ("sel",   "#rate-connections_table table tbody tr")),
    ("cld",          ("pyvis", "cld-network")),
    ("loops",        ("sel",   "#loops-detect")),
    ("metrics",      ("pyvis", "metrics-metrics_network")),
    ("leverage",     ("pyvis", "leverage-leverage_network")),
    ("quadrant",     ("sel",   "#quadrant-quadrant_plot img")),
    ("boolean",      ("sel",   "#boolean-run_boolean")),
    ("simulation",   ("sel",   "#simulation-run_sim")),
    ("bot",          ("text",  "#bot-element_picker_ui")),
    ("intervention", ("pyvis", "intervention-intervention_network")),
    ("simplify",     ("pyvis", "simplify-simplified_network")),
    ("import",       ("sel",   "#import-preview")),
    ("recent",       ("text",  "#recent-recent_list")),
    ("report",       ("sel",   "#report-report_preview iframe")),   # srcdoc preview: no innerText
]

FADE_MS = 400          # Bootstrap modal/tab fade; a mid-fade shot is translucent
POLL_N, POLL_MS = 20, 500


class Shooter:
    def __init__(self, page, out: Path):
        self.page = page
        self.out = out
        self.written: list[Path] = []
        self.failures: list[str] = []
        self.warnings: list[str] = []

    # ---- generic helpers -------------------------------------------------
    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"WARN {msg}")

    async def poll(self, fn, n: int = POLL_N, ms: int = POLL_MS) -> bool:
        """Poll an async predicate; True as soon as it holds, False on timeout."""
        for _ in range(n):
            try:
                if await fn():
                    return True
            except Exception:
                pass
            await self.page.wait_for_timeout(ms)
        return False

    async def text(self, sel: str) -> str:
        el = await self.page.query_selector(sel)
        return ((await el.inner_text()) if el else "").strip()

    async def poll_text(self, sel: str, pred=None, n: int = POLL_N, ms: int = POLL_MS) -> bool:
        pred = pred or (lambda t: bool(t))

        async def _ok():
            return pred(await self.text(sel))
        return await self.poll(_ok, n, ms)

    async def poll_sel(self, sel: str, n: int = POLL_N, ms: int = POLL_MS) -> bool:
        async def _ok():
            return (await self.page.query_selector(sel)) is not None
        return await self.poll(_ok, n, ms)

    async def poll_pyvis(self, key: str, n: int = 2 * POLL_N, ms: int = POLL_MS) -> bool:
        # Networks register a few seconds after the panel activates (later still
        # if a Monte Carlo from a previous panel is holding the server), so this
        # probe gets twice the default budget.
        async def _ok():
            return await self.page.evaluate(
                "(k) => !!(window.pyvisNetworks && window.pyvisNetworks[k]"
                " && window.pyvisNetworks[k].nodes && window.pyvisNetworks[k].nodes.length)",
                key,
            )
        return await self.poll(_ok, n, ms)

    async def goto_panel(self, value: str) -> None:
        await self.page.click(f"#sespy_nav_{value}")
        await self.page.wait_for_function(
            "(v) => { const a = Array.from(document.querySelectorAll('.sespy-nav-btn.active'))"
            "  .map(e => e.id); return a.length === 1 && a[0] === 'sespy_nav_' + v; }",
            arg=value, timeout=15000,
        )
        await self.page.wait_for_timeout(FADE_MS)

    async def wait_probe(self, value: str, probe) -> bool:
        kind, sel = probe
        if kind == "text":
            ok = await self.poll_text(sel)
        elif kind == "sel":
            ok = await self.poll_sel(sel)
        else:
            ok = await self.poll_pyvis(sel)
        if not ok:
            self.warn(f"{value}: readiness probe {probe} did not render in time")
        return ok

    async def shot(self, name: str) -> Path:
        await self.page.evaluate("() => window.scrollTo(0, 0)")
        path = self.out / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=False)
        print(f"wrote {path} ({path.stat().st_size} bytes)")
        self.written.append(path)
        return path

    async def hide_notifications(self) -> None:
        await self.page.evaluate(
            "() => { const p = document.getElementById('shiny-notification-panel');"
            " if (p) p.style.display = 'none'; }"
        )

    # ---- gated blocks ----------------------------------------------------
    async def uncertainty_toggle(self, ns: str, header_marker: str) -> None:
        """Tick `Show uncertainty (Monte Carlo)` only if it finishes in ~20 s;
        otherwise untick it and wait for the extra column to disappear."""
        n_sel, cb_sel = f"#{ns}-n_samples", f"#{ns}-show_uncertainty"
        if not await self.page.query_selector(cb_sel):
            self.warn(f"{ns}: {cb_sel} not found, uncertainty left off")
            return
        await self.page.fill(n_sel, "50")
        await self.page.dispatch_event(n_sel, "change")
        await self.page.check(cb_sel)

        async def _has_col():
            heads = await self.page.evaluate(
                "(ns) => Array.from(document.querySelectorAll("
                "'#' + ns + '-' + (ns === 'loops' ? 'loops_table' : 'leverage_table')"
                " + ' table thead th')).map(th => th.textContent.trim())", ns)
            return any(header_marker in h for h in heads)
        if await self.poll(_has_col, n=20, ms=1000):
            print(f"{ns}: uncertainty columns rendered")
            return
        self.warn(f"{ns}: uncertainty did not finish within ~20 s, leaving it off")
        await self.page.uncheck(cb_sel)

        async def _no_col():
            return not await _has_col()
        await self.poll(_no_col, n=20, ms=500)

    async def gate_loops(self) -> None:
        await self.page.click("#loops-detect")
        if not await self.poll_sel("#loops-loops_table table tbody tr", n=60):
            self.warn("loops: loops table did not populate after Detect loops")
            return
        await self.poll_sel("#loops-selected_loop")
        # Wait for the loop network to render for the selected loop
        await self.poll_pyvis("loops-loop_network")
        await self.uncertainty_toggle("loops", "%")

    async def gate_metrics(self) -> None:
        # Cascade vulnerability
        await self.poll_text("#metrics-cascade_summary")
        await self.page.click("#metrics-run_cascade")
        if not await self.poll_text("#metrics-cascade_summary",
                                    lambda t: t and "not computed" not in t, n=60):
            self.warn("metrics: cascade result did not render")
        # Causal pathways: prefer D001 -> P001, else the e2e golden ES02 -> D001
        await self.poll_sel("#metrics-paths_source")
        src_opts = await self.page.eval_on_selector_all(
            "#metrics-paths_source option", "els => els.map(e => e.value)")
        tgt_opts = await self.page.eval_on_selector_all(
            "#metrics-paths_target option", "els => els.map(e => e.value)")
        src, tgt = ("D001", "P001") if "D001" in src_opts and "P001" in tgt_opts \
            else ("ES02", "D001")
        if src in src_opts and tgt in tgt_opts:
            before = await self.text("#metrics-paths_summary")
            await self.page.select_option("#metrics-paths_source", src)
            await self.page.select_option("#metrics-paths_target", tgt)
            await self.page.click("#metrics-trace_paths")
            if not await self.poll_text("#metrics-paths_summary",
                                        lambda t: t and t != before and "path" in t.lower(),
                                        n=60):
                self.warn(f"metrics: trace paths {src}->{tgt} did not render")
            else:
                print(f"metrics: traced paths {src} -> {tgt}")
        else:
            self.warn(f"metrics: path selects lack {src}/{tgt}; trace skipped")
        # SES subsystem modules
        await self.page.click("#metrics-run_hypermodules")
        if not await self.poll_text("#metrics-hypermodules_summary",
                                    lambda t: t and "not computed" not in t, n=60):
            self.warn("metrics: subsystem modules result did not render")

    async def gate_boolean(self) -> None:
        await self.page.click("#boolean-run_boolean")
        if not await self.poll_sel("#boolean-eigenvalue_plot img", n=60):
            self.warn("boolean: eigenvalue plot did not render")
        await self.poll(lambda: self.page.evaluate(
            "() => document.querySelectorAll('#boolean-stability_summary dl dt').length >= 3"))

    async def gate_simulation(self) -> None:
        await self.page.check("#simulation-dominance_show")
        await self.page.click("#simulation-run_sim")
        if not await self.poll_sel("#simulation-trajectory_plot img", n=60):
            self.warn("simulation: trajectory plot did not render")
        if not await self.poll_text("#simulation-dominance_summary", n=60):
            self.warn("simulation: loop-dominance summary did not render")

    async def gate_simulation_mc(self) -> None:
        await self.page.click("#simulation-run_mc")
        await self.page.click("#simulation-simulation_tabs a[data-value='Monte Carlo']")
        await self.page.wait_for_timeout(FADE_MS)

        async def _rows():
            return await self.page.evaluate(
                "() => document.querySelectorAll('#simulation-mc_summary table tbody tr').length >= 1")
        if not await self.poll(_rows, n=60, ms=1000):
            self.warn("simulation: Monte Carlo summary did not render")
            return
        if not await self.poll_sel("#simulation-mc_histograms img", n=30):
            self.warn("simulation: Monte Carlo histograms did not render")

    async def gate_intervention(self) -> None:
        # Ablate one node. Drive the selectize widget itself (as the BOT e2e
        # does) so the chosen node shows in the control on the shot; fall back
        # to Shiny.setInputValue (the intervention e2e pattern) if the dropdown
        # does not offer P001.
        try:
            await self.page.click("#intervention-ablate + .selectize-control")
            await self.page.click(
                ".selectize-dropdown-content [data-selectable][data-value='P001']", timeout=3000)
            await self.page.keyboard.press("Escape")
        except Exception:
            self.warn("intervention: selectize pick failed, using Shiny.setInputValue")
            await self.page.evaluate(
                "() => Shiny.setInputValue('intervention-ablate', ['P001'], {priority: 'event'})")
        ok = await self.poll(lambda: self.page.evaluate(
            "() => { const s = window.pyvisNetworks['intervention-intervention_network'];"
            " const n = s && s.nodes && s.nodes.get('P001'); return !!n && n.opacity < 1; }"))
        if not ok:
            self.warn("intervention: ablated node P001 not greyed out in the network")
        # Token diffusion: choose a source, run
        if not await self.poll_sel("#intervention-diffusion_source"):
            self.warn("intervention: diffusion source select missing; run skipped")
            return
        await self.page.select_option("#intervention-diffusion_source", "D001")
        await self.page.click("#intervention-run_diffusion")
        if not await self.poll_text("#intervention-diffusion_summary",
                                    lambda t: "elements reached" in t, n=60):
            self.warn("intervention: token simulation result did not render")
        else:
            await self.poll_sel("#intervention-diffusion_chart img")

    # ---- About modal -----------------------------------------------------
    async def shoot_about(self) -> None:
        await self.hide_notifications()
        await self.page.click("#tb_about")
        await self.page.wait_for_selector(".modal.show", timeout=10000)
        await self.page.wait_for_timeout(FADE_MS)
        await self.shot("about_overview")
        manual = self.page.locator(".modal .nav-tabs a:has-text('Manual')")
        if await manual.count() == 0:
            print("note: About modal has no 'Manual' tab yet; about_manual.png skipped")
        else:
            await manual.first.click()
            await self.page.wait_for_timeout(FADE_MS)
            await self.shot("about_manual")
        await self.page.click(".modal button:has-text('Close')")
        await self.page.wait_for_selector(".modal", state="hidden", timeout=10000)

    # ---- driver ----------------------------------------------------------
    async def run(self, port: int) -> None:
        page = self.page
        await page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
        # Cold-server warm-up: the nav is server-rendered
        await page.wait_for_function(
            "() => document.querySelectorAll('.sespy-nav-btn').length >= 19", timeout=60000)
        await page.wait_for_timeout(1500)
        # Toasts (the autosave "Recovered work" prompt fires a moment after
        # load; others arrive from gated runs) must not land in a doc shot.
        await page.add_style_tag(content="#shiny-notification-panel{display:none !important}")
        theme = await page.get_attribute("html", "data-theme")
        if theme:
            self.warn(f"html[data-theme]={theme!r} — expected the default light theme")
        label = (await page.inner_text("#sespy_nav_loops")).strip()
        if "Loop Analysis" not in label:
            self.warn(f"nav label {label!r} is not English — translator state is process-global")

        # full_app.png: the CLD panel at page load
        active = await page.eval_on_selector_all(".sespy-nav-btn.active", "els => els.map(e => e.id)")
        if active != ["sespy_nav_cld"]:
            print(f"note: active nav at load is {active}, switching to CLD for full_app.png")
            await self.goto_panel("cld")
        await self.poll_pyvis("cld-network")
        await self.shot("full_app")

        for value, probe in NAV_ORDER:
            try:
                await self.goto_panel(value)
                await self.wait_probe(value, probe)
                if value == "loops":
                    await self.gate_loops()
                elif value == "metrics":
                    await self.gate_metrics()
                elif value == "leverage":
                    await self.poll_sel("#leverage-leverage_table table tbody tr")
                    await self.uncertainty_toggle("leverage", "CI")
                elif value == "boolean":
                    await self.gate_boolean()
                elif value == "simulation":
                    await self.gate_simulation()
                elif value == "intervention":
                    await self.gate_intervention()
                await self.hide_notifications()
                await self.shot(value)
                if value == "metrics":
                    # The page scrolls on window. The output_ui wrapper itself
                    # has no box (display: contents via the fill chain), so
                    # scrollIntoView on it is a no-op — target its first
                    # descendant that has a box and park it under the topbar.
                    scroll_y = await page.eval_on_selector(
                        "#metrics-cascade_summary",
                        "el => { const box = Array.from(el.querySelectorAll('*'))"
                        "    .find(c => c.getBoundingClientRect().height > 0) || el;"
                        "  const y = box.getBoundingClientRect().top + window.scrollY - 90;"
                        "  window.scrollTo({top: y, behavior: 'instant'}); return window.scrollY; }")
                    await page.wait_for_timeout(500)
                    if not scroll_y:
                        self.warn("metrics: cascade block did not scroll into view")
                    path = self.out / "metrics_cascade.png"
                    await page.screenshot(path=str(path), full_page=False)
                    print(f"wrote {path} ({path.stat().st_size} bytes)")
                    self.written.append(path)
                elif value == "simulation":
                    await self.gate_simulation_mc()
                    await self.shot("simulation_montecarlo")
            except Exception as exc:  # keep going; report at the end
                self.failures.append(f"{value}: {type(exc).__name__}: {exc}")
                print(f"FAIL {value}: {type(exc).__name__}: {exc}")

        try:
            await self.goto_panel("cld")
            await self.shoot_about()
        except Exception as exc:
            self.failures.append(f"about: {type(exc).__name__}: {exc}")
            print(f"FAIL about: {type(exc).__name__}: {exc}")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--out", default="docs/screenshots")
    args = ap.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900}, color_scheme="light",
            locale="en-GB",
        )
        page = await ctx.new_page()
        shooter = Shooter(page, out)
        try:
            await shooter.run(args.port)
        finally:
            await browser.close()

    print(f"\n{len(shooter.written)} file(s) written to {out}")
    if shooter.warnings:
        print(f"{len(shooter.warnings)} warning(s):")
        for w in shooter.warnings:
            print(f"  - {w}")
    if shooter.failures:
        print(f"{len(shooter.failures)} panel(s) FAILED:")
        for f in shooter.failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
