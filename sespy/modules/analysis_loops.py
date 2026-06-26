"""Loop Detection Analysis module — pyvis.shiny edition.

Mirrors the structure of `modules/analysis_loops.R` (1134 lines, 4 tabs in R).
This POC keeps the **Detect** + **Details** tabs and uses the official
`pyvis.shiny` integration to render the selected feedback loop in place
(no iframe, no second vis-network bundle — shares the one loaded by
the CLD module's pyvis.shiny output).
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
from ..i18n import t

_COMPUTING = object()

_BEHAVIOR_KEY = {
    "reinforcing": "loops.behavior.reinforcing",
    "balancing": "loops.behavior.balancing",
    "oscillating": "loops.behavior.oscillating",
}
_BEHAVIOR_COLOR = {
    "reinforcing": EDGE_COLORS["reinforcing"],
    "balancing": EDGE_COLORS["opposing"],
    "oscillating": "#e8a33d",   # amber — distinct from R/B
}


def _build_loop_network(loop_nodes: list[str], isa: IsaData) -> Network:
    """Build a pyvis.Network showing one feedback loop."""
    from ..constants import normalize_delay
    label_by_id = {el.id: el.label for el in isa.elements}
    type_by_id = {el.id: el.type for el in isa.elements}
    polarity_by_edge = {(c.source, c.target): c.polarity for c in isa.connections}
    delay_by_edge = {(c.source, c.target): normalize_delay(c.delay) for c in isa.connections}

    # See cld_visualization.py: Network height must be a fixed pixel value or
    # bslib's html-fill-container/display:contents chain leaves vis-network
    # unconstrained and it grows to fit content. Match the host height in UI.
    net = Network(
        height="500px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#2c3e50",
        cdn_resources="local",
    )
    net.set_options(
        '{"physics": {"enabled": true, "stabilization": {"iterations": 150}},'
        ' "interaction": {"hover": true, "tooltipDelay": 150}}'
    )

    for nid in loop_nodes:
        node_type = type_by_id.get(nid, "Unknown")
        net.add_node(
            nid,
            label=label_by_id.get(nid, nid),
            title=f"{node_type}: {label_by_id.get(nid, nid)}",
            color=ELEMENT_COLORS.get(node_type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(node_type, DEFAULT_GROUP_SHAPE),
            size=40,
            font={"size": 18, "multi": "html"},
            widthConstraint={"maximum": 200},
        )

    n = len(loop_nodes)
    for i in range(n):
        src, tgt = loop_nodes[i], loop_nodes[(i + 1) % n]
        polarity = polarity_by_edge.get((src, tgt), "+")
        delay = delay_by_edge.get((src, tgt), "immediate")
        is_delayed = delay != "immediate"
        net.add_edge(
            src,
            tgt,
            label=polarity,
            title=f"{polarity} · {delay}",
            color=EDGE_COLORS["reinforcing" if polarity == "+" else "opposing"],
            arrows="to",
            width=3,
            dashes=is_delayed,
        )

    return net


# Public alias kept for the existing test that pokes the payload shape.
def build_loop_payload(loop_nodes: list[str], isa: IsaData) -> dict[str, list[dict]]:
    """Return the {nodes, edges} payload for one loop, via pyvis."""
    net = _build_loop_network(loop_nodes, isa)
    nodes, edges, *_ = net.get_network_data()
    return {"nodes": list(nodes), "edges": list(edges)}


@module.ui
def analysis_loops_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.loops")),
        _loops_body(),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


def _loops_body() -> ui.Tag:
    return ui.layout_sidebar(
        ui.sidebar(
            ui.h5(t("loops.detection_params")),
            ui.input_numeric("max_length", t("loops.max_length"), value=6, min=3, max=10),
            ui.input_numeric("max_loops", t("loops.max_loops"), value=200, min=10, max=2000),
            ui.input_action_button("detect", t("loops.detect"), class_="btn btn-primary"),
            ui.tags.hr(),
            ui.input_checkbox("show_uncertainty", t("uncertainty.toggle"), value=False),
            ui.input_numeric("n_samples", t("uncertainty.n_samples"),
                             value=100, min=50, max=5000, step=50),
            ui.tags.hr(),
            ui.h5(t("loops.classification")),
            ui.output_ui("classification_summary"),
            ui.tags.hr(),
            ui.h5(t("loops.inspect")),
            ui.output_ui("loop_picker"),
            width=320,
        ),
        ui.div(
            ui.h4(t("loops.detected_loops")),
            ui.output_data_frame("loops_table"),
            ui.tags.small(t("loops.disagreement_legend"), class_="text-muted"),
            ui.tags.hr(),
            ui.h4(t("loops.selected_loop")),
            ui.output_ui("loop_narrative"),
            output_pyvis_network(
                "loop_network",
                height="500px",
                show_toolbar=False,
                show_search=False,
                show_layout_switcher=False,
                show_export=False,
                show_status=False,
            ),
        ),
    )


@module.server
def analysis_loops_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
) -> None:
    detected: reactive.Value[list[list[str]]] = reactive.value([])

    @reactive.effect
    @reactive.event(input.detect, ignore_none=False)
    def _run_detection():
        cycles = net_analysis.feedback_loops(
            project_data.get().isa_data,
            max_length=int(input.max_length() or 6),
            max_loops=int(input.max_loops() or 200),
        )
        detected.set(cycles)
        event_bus.emit_analysis_request()

    @reactive.effect
    def _invalidate_on_isa_change():
        event_bus.isa_change.get()
        with reactive.isolate():
            if detected.get():
                detected.set([])

    @reactive.calc
    def classified() -> list[dict]:
        return net_analysis.classify_loops(detected.get(), project_data.get().isa_data)

    unc_state = reactive.value(None)            # None | _COMPUTING | <result dict>
    _gen = [0]                                  # plain cell — NOT reactive (avoids self-loop)

    @reactive.extended_task
    async def _unc_task(isa, cycles, n_samples, gen):
        result = await asyncio.to_thread(
            net_analysis.uncertainty_scores, isa,
            cycles=cycles, n_samples=n_samples, seed=0,
        )
        return (gen, result)

    @reactive.effect
    def _unc_trigger():
        _gen[0] += 1
        gen = _gen[0]
        if not input.show_uncertainty():
            unc_state.set(None)
            return
        cycles = detected.get()
        if not cycles:
            unc_state.set(None)
            return
        isa = project_data.get().isa_data
        n = int(input.n_samples() or 100)
        unc_state.set(_COMPUTING)
        _unc_task(isa, cycles, n, gen)

    @reactive.effect
    def _unc_observe():
        try:
            gen, result = _unc_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("loops uncertainty task failed")
            unc_state.set(None)
            return
        if gen != _gen[0]:
            return
        unc_state.set(result)

    @reactive.calc
    def uncertainty_loops() -> dict[str, dict]:
        unc = unc_state.get()
        if not isinstance(unc, dict):
            return {}
        return {lp["id"]: lp for lp in unc["loops"]}

    @output
    @render.ui
    def classification_summary():
        rows = classified()
        if not rows:
            return ui.tags.p(t("loops.no_loops_yet"), class_="text-muted")
        counts = {b: sum(1 for r in rows if r["behavior"] == b)
                  for b in ("reinforcing", "balancing", "oscillating")}

        def line(b):
            return ui.tags.div(
                ui.tags.strong(str(counts[b])), " ", t(_BEHAVIOR_KEY[b]),
                style=f"color: {_BEHAVIOR_COLOR[b]}; margin-bottom: 4px;",
            )
        children = []
        if unc_state.get() is _COMPUTING:
            children.append(ui.p(t("uncertainty.computing"), class_="text-muted"))
        children += [
            line("reinforcing"), line("balancing"), line("oscillating"),
            ui.tags.div(t("loops.oscillating_disclaimer"),
                        class_="text-muted", style="font-size: 0.72rem; margin-top: 6px;"),
        ]
        return ui.div(*children)

    @output
    @render.ui
    def loop_picker():
        rows = classified()
        if not rows:
            return ui.tags.p(t("loops.detect_first"), class_="text-muted")
        choices = {r["id"]: f"{r['id']} · {t(_BEHAVIOR_KEY[r['behavior']])} · len {r['length']}"
                   for r in rows}
        return ui.input_select("selected_loop", None, choices=choices)

    @output
    @render.data_frame
    def loops_table():
        import pandas as pd
        rows = classified()
        cols = ["id", "behavior", "delayed", "type", "length", "path"]
        if not rows:
            return pd.DataFrame(columns=cols)

        isa = project_data.get().isa_data
        unc = uncertainty_loops()

        def base_row(r):
            behavior = t(_BEHAVIOR_KEY[r["behavior"]])
            if net_analysis.loop_polarity_contested(r["nodes"], isa):
                behavior = f"{behavior} ⚠"
            return {
                "id": r["id"],
                "behavior": behavior,
                "delayed": "✓" if r["delayed"] else "—",
                "type": r["type"],
                "length": r["length"],
                "path": r["path"],
            }

        if not unc:
            return pd.DataFrame([base_row(r) for r in rows], columns=cols)

        ext_cols = cols + [t("loops.existence_pct"), t("loops.reinforcing_pct"),
                           t("loops.balancing_pct"), t("loops.contested")]
        out = []
        for r in rows:
            row = base_row(r)
            u = unc.get(r["id"])
            if u:
                row[t("loops.existence_pct")] = f"{u['existence_prob'] * 100:.0f}%"
                row[t("loops.reinforcing_pct")] = f"{u['reinforcing_prob'] * 100:.0f}%"
                row[t("loops.balancing_pct")] = f"{u['balancing_prob'] * 100:.0f}%"
                row[t("loops.contested")] = "✓" if u["contested"] else ""
            else:
                row[t("loops.existence_pct")] = ""
                row[t("loops.reinforcing_pct")] = ""
                row[t("loops.balancing_pct")] = ""
                row[t("loops.contested")] = ""
            out.append(row)
        return pd.DataFrame(out, columns=ext_cols)

    @reactive.calc
    def selected_row() -> dict | None:
        rows = classified()
        if not rows:
            return None
        try:
            sel_id = input.selected_loop()
        except Exception:
            return rows[0]
        for r in rows:
            if r["id"] == sel_id:
                return r
        return rows[0]

    @output
    @render.ui
    def loop_narrative():
        row = selected_row()
        if row is None:
            return ui.tags.p(t("loops.detect_first"), class_="text-muted")
        color = _BEHAVIOR_COLOR[row["behavior"]]
        parts = [
            ui.tags.span(
                t(_BEHAVIOR_KEY[row["behavior"]]),
                style=(f"display:inline-block; padding:2px 10px; background:{color}; "
                       "color:#fff; border-radius:12px; font-size:12px; margin-right:8px;"),
            ),
        ]
        if row["delayed"] and row["behavior"] != "oscillating":
            parts.append(ui.tags.span(
                t("loops.delay_chip"),
                style=("display:inline-block; padding:2px 8px; background:#e8a33d; "
                       "color:#fff; border-radius:12px; font-size:11px; margin-right:8px;"),
            ))
        parts.append(ui.tags.span(f"length {row['length']}", style="color:#777; margin-right:8px;"))
        parts.append(ui.tags.span(row["path"]))
        return ui.div(*parts, style="margin: 8px 0 12px 0;")

    @output(id="loop_network")
    @render_pyvis_network(height="500px", show_toolbar=False, show_search=False,
                          show_layout_switcher=False, show_export=False, show_status=False)
    def _loop_network():
        row = selected_row()
        if row is None:
            # Empty network placeholder — height matches host so it doesn't
            # collapse via display:contents in bslib's fill chain.
            net = Network(height="500px", width="100%", directed=True,
                          cdn_resources="local")
            return net
        return _build_loop_network(row["nodes"], project_data.get().isa_data)
