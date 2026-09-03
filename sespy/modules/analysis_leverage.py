"""Leverage Point Analysis — port of modules/analysis_leverage.R.

Identifies nodes whose composite betweenness + eigenvector + pagerank
z-score is highest. The R module wraps this in 5 tabs (overview, points,
intervention design, recommendations, comparison); this POC keeps the
core actionable view: ranked table + network sized by leverage score.

The composite-score formula (`leverage_scores` in `sespy/network.py`) is
the same one R computes at network_analysis.R:1390 — switching the data
would produce identical rankings.
"""

from __future__ import annotations

import asyncio
import logging

from pyvis.network import Network
from pyvis.shiny import output_pyvis_network, render_pyvis_network
from shiny import Inputs, Outputs, Session, module, reactive, render, ui
from shiny.types import SilentException

from .. import network as net_analysis
from ..constants import (
    DEFAULT_GROUP_COLOR,
    DEFAULT_GROUP_SHAPE,
    EDGE_COLORS,
    ELEMENT_COLORS,
    ELEMENT_SHAPES,
)
from ..data_structure import IsaData, Project
from ..event_bus import EventBus
from ..i18n import Translator, t

_COMPUTING = object()


def _scale_size(value: float, lo: float, hi: float) -> int:
    if hi <= lo:
        return 28
    return int(18 + ((value - lo) / (hi - lo)) * 42)


def _build_leverage_network(isa: IsaData, scores: dict[str, float]) -> Network:
    net = Network(
        height="500px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#2c3e50",
        cdn_resources="local",
    )
    net.set_options(
        '{"physics": {"enabled": true, "stabilization": {"iterations": 200}},'
        ' "interaction": {"hover": true, "tooltipDelay": 150}}'
    )
    if not isa.elements:
        return net
    values = [scores.get(el.id, 0.0) for el in isa.elements]
    lo, hi = min(values), max(values)
    for el in isa.elements:
        v = scores.get(el.id, 0.0)
        net.add_node(
            el.id,
            label=el.label,
            title=f"{el.type}: {el.label}\nleverage: {v:.3f}",
            color=ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=_scale_size(v, lo, hi),
            font={"size": 14, "multi": "html"},
            widthConstraint={"maximum": 160},
        )
    for c in isa.connections:
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=1.5,
            **net_analysis.delay_edge_kwargs(c),
        )
    return net


@module.ui
def analysis_leverage_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.leverage")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("leverage.about")),
                ui.p(
                    t("leverage.about_text"),
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                ui.tags.hr(),
                ui.input_slider(
                    "top_n",
                    t("metrics.show_top_n"),
                    min=3, max=20, value=8, step=1,
                ),
                ui.tags.hr(),
                ui.input_checkbox("show_uncertainty", t("uncertainty.toggle"), value=False),
                ui.input_numeric("n_samples", t("uncertainty.n_samples"),
                                 value=100, min=50, max=5000, step=50),
                width=240,
            ),
            ui.div(
                ui.h4(t("leverage.highest")),
                ui.output_data_frame("leverage_table"),
                ui.output_ui("leverage_caption"),
                ui.output_ui("uncertainty_status"),
                ui.tags.hr(),
                ui.h4(t("leverage.network_sized")),
                output_pyvis_network(
                    "leverage_network",
                    height="500px",
                    show_toolbar=False, show_search=False,
                    show_layout_switcher=False, show_export=False,
                    show_status=False,
                ),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_leverage_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def scores() -> dict[str, float]:
        event_bus.isa_change.get()
        return net_analysis.leverage_scores(project_data.get().isa_data)

    @reactive.calc
    def cycles_calc() -> list[list[str]]:
        """ONE loop enumeration per ISA change, shared by every consumer.

        `event_bus.isa_change.get()` matches scores() — every isa-derived
        reactive in this module takes that dependency, or it serves a stale
        result after an edit.
        """
        event_bus.isa_change.get()
        return net_analysis.feedback_loops(project_data.get().isa_data)

    @reactive.calc
    def alc_truncated() -> bool:
        # Passes the SHARED list. Calling alc_is_truncated(isa) without it
        # would re-run feedback_loops a second time per render.
        return net_analysis.alc_is_truncated(
            project_data.get().isa_data, cycles=cycles_calc())

    @reactive.calc
    def ranked() -> list[dict]:
        isa = project_data.get().isa_data
        s = scores()
        # The shared enumeration — see cycles_calc() above. feedback_loops is
        # bounded but not free, and it must run ONCE per ISA change, not once
        # per consumer.
        cycles = cycles_calc()
        realms = net_analysis.leverage_realms(isa, cycles=cycles)
        truncated = alc_truncated()
        # Skipped entirely when truncated: the column is suppressed in that
        # case, and on a capped model this is the one non-trivial cost here.
        alc = ({} if truncated
               else net_analysis.adjusted_loop_centrality(isa, cycles=cycles))
        by_id = {el.id: el for el in isa.elements}
        rows = sorted(s.items(), key=lambda kv: kv[1], reverse=True)
        out: list[dict] = []
        for rank, (nid, value) in enumerate(rows, start=1):
            el = by_id.get(nid)
            token = realms.get(nid, "")
            row = {
                "rank": rank,
                "id": nid,
                "label": el.label if el else nid,
                "type":  el.type if el else "",
                "realm": t(f"leverage.realm.{token}") if token else "—",
                "leverage": round(value, 3),
            }
            # Suppressed entirely when truncated: above the cap the SIGN is
            # not reproducible across processes, and the sign is the meaning.
            if not truncated:
                row["alc"] = round(alc.get(nid, 0.0), 3)
            out.append(row)
        return out[: int(input.top_n() or 8)]

    unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>
    _gen = [0]                                  # plain cell — NOT reactive (avoids self-loop)

    @reactive.extended_task
    async def _unc_task(isa, n_samples, gen):
        result = await asyncio.to_thread(
            net_analysis.uncertainty_scores, isa, n_samples=n_samples, seed=0,
        )
        return (gen, result)

    @reactive.effect
    def _unc_trigger():
        _gen[0] += 1
        gen = _gen[0]
        if not input.show_uncertainty():
            unc_state.set(None)
            return
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        n = int(input.n_samples() or 100)
        unc_state.set(_COMPUTING)
        _unc_task(isa, n, gen)

    @reactive.effect
    def _unc_observe():
        try:
            gen, result = _unc_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("leverage uncertainty task failed")
            unc_state.set(None)
            return
        if gen != _gen[0]:
            return
        unc_state.set(result)

    @output
    @render.data_frame
    def leverage_table():
        import pandas as pd

        rows = ranked()
        base_cols = ["rank", "id", "label", "type", "realm", "leverage"]
        if not alc_truncated():
            base_cols.insert(5, "alc")
        if not rows:
            return pd.DataFrame(columns=base_cols)

        unc = unc_state.get()
        data = unc if isinstance(unc, dict) else None   # None when idle OR computing
        if data is None:
            return pd.DataFrame(rows, columns=base_cols)

        lev = data.get("leverage", {})
        enriched = []
        for r in rows:
            u = lev.get(r["id"])
            ci = f"[{u['ci_low']:.2f}, {u['ci_high']:.2f}]" if u else ""
            unstable = (t("uncertainty.unstable")
                        if u and u["ci_low"] < 0 < u["ci_high"] else "")
            enriched.append({**r, t("uncertainty.ci"): ci,
                             t("uncertainty.unstable"): unstable})
        cols = base_cols + [t("uncertainty.ci"), t("uncertainty.unstable")]
        return pd.DataFrame(enriched, columns=cols)

    @output
    @render.ui
    def leverage_caption():
        parts = [ui.p(t("leverage.caption"), class_="text-muted",
                      style="font-size: 0.85rem;")]
        if alc_truncated():
            parts.append(ui.p(t("leverage.alc_truncated"), class_="text-muted",
                              style="font-size: 0.85rem;"))
        return ui.div(*parts)

    @output
    @render.ui
    def uncertainty_status():
        if unc_state.get() is _COMPUTING:
            return ui.p(t("uncertainty.computing"), class_="text-muted")
        return ui.div()

    @output(id="leverage_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_leverage_network(project_data.get().isa_data, scores())
