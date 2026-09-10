"""Intervention Analysis — "what if we ablate node(s) X?" scenarios.

Mirrors `modules/analysis_intervention.R`. The user picks one or more
nodes to remove; the module shows the change in centrality (selected
metric) for every remaining node, sorted by delta. Nodes most affected
by the ablation are the ones structurally dependent on the removed
node(s) — useful counterpart to leverage analysis ("removing this
high-leverage node ripples through these other nodes").
"""

from __future__ import annotations

import asyncio
import logging

from pyvis.network import Network
from pyvis.shiny import output_pyvis_network, render_pyvis_network
from shiny import Inputs, Outputs, Session, module, reactive, render, ui
from shiny.types import SilentException

from .. import bayes
from .. import dynamics as dyn
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

#: Sentinel for "BBN task in flight". pgmpy 1.1 imports torch when installed:
#: measured 35–65 s on the FIRST import per server process. The import must
#: therefore run off the event loop (extended task + thread), never at module
#: level (tests/test_no_deprecations.py imports every module cold).
_COMPUTING = object()


def _build_intervention_network(
    isa: IsaData,
    impact: dict[str, dict[str, float]],
    removed_ids: list[str],
) -> Network:
    """Pyvis network: removed nodes greyed out + dashed border;
    surviving nodes coloured by abs(delta) heatmap-style."""
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

    # Heatmap range from max abs delta on surviving nodes
    deltas = [abs(d["delta"]) for d in impact.values()]
    max_delta = max(deltas) if deltas else 0.0

    for el in isa.elements:
        if el.id in removed_ids:
            net.add_node(
                el.id,
                label=el.label + " (ablated)",
                title=f"{el.type}: {el.label}\nRemoved in this scenario",
                color={"background": "#cccccc", "border": "#666",
                       "highlight": {"background": "#cccccc", "border": "#666"}},
                shape="dot",
                size=20,
                opacity=0.4,
                borderDashes=[6, 4],
                font={"size": 12, "color": "#666"},
            )
            continue
        info = impact.get(el.id, {"delta": 0.0})
        delta = info["delta"]
        # Surviving-node colouring: pull toward bio-cyan if positive delta
        # (gained influence), toward coral if negative.
        if max_delta > 0:
            ratio = abs(delta) / max_delta
        else:
            ratio = 0.0
        if delta > 0:
            tint = f"rgba(0, 212, 170, {0.15 + 0.6 * ratio:.2f})"
        elif delta < 0:
            tint = f"rgba(255, 107, 107, {0.15 + 0.6 * ratio:.2f})"
        else:
            tint = ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR)
        net.add_node(
            el.id,
            label=el.label,
            title=(f"{el.type}: {el.label}\n"
                   f"before: {info['before']:.4f}\n"
                   f"after:  {info['after']:.4f}\n"
                   f"Δ:      {delta:+.4f}"),
            color=tint,
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=int(22 + ratio * 28),
            font={"size": 14, "multi": "html"},
            widthConstraint={"maximum": 160},
        )

    for c in isa.connections:
        edge_opacity = (
            0.25 if c.source in removed_ids or c.target in removed_ids else 1.0
        )
        net.add_edge(
            c.source, c.target,
            label=c.polarity,
            color={
                "color": EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
                "opacity": edge_opacity,
            },
            arrows="to",
            width=1.5,
            **net_analysis.delay_edge_kwargs(c),
        )
    return net


@module.ui
def analysis_intervention_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.intervention")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("intervention.scenario")),
                ui.p(
                    t("intervention.about_text"),
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                ui.tags.hr(),
                ui.output_ui("ablate_picker"),
                ui.input_radio_buttons(
                    "metric",
                    t("metrics.metric"),
                    {k: k.title() for k in net_analysis.CENTRALITY_METRICS},
                    selected="pagerank",
                ),
                ui.tags.hr(),
                ui.input_action_button(
                    "reset", t("intervention.reset"),
                    class_="btn btn-sm btn-outline-secondary",
                ),
                ui.tags.hr(),
                ui.h5(t("diffusion.title")),
                ui.output_ui("diffusion_controls"),
                ui.input_slider("n_steps", t("diffusion.steps"),
                                min=3, max=30, value=10, step=1),
                ui.input_slider("n_tokens", t("diffusion.tokens"),
                                min=100, max=5000, value=1000, step=100),
                ui.input_action_button(
                    "run_diffusion", t("diffusion.run"),
                    class_="btn btn-sm btn-outline-primary",
                ),
                ui.tags.hr(),
                ui.h5(t("bbn.title")),
                ui.p(t("bbn.about_text"), class_="text-muted", style="font-size: 0.8rem;"),
                ui.output_ui("bbn_controls"),
                ui.output_ui("bbn_evidence_controls"),
                ui.input_radio_buttons(
                    "bbn_direction", t("bbn.direction"),
                    {"forward": t("bbn.forward"), "diagnostic": t("bbn.diagnostic")},
                    selected="forward",
                ),
                ui.input_action_button(
                    "run_bbn", t("bbn.run"),
                    class_="btn btn-sm btn-outline-primary",
                ),
                width=280,
            ),
            ui.div(
                ui.h4(t("intervention.most_affected")),
                ui.output_data_frame("impact_table"),
                ui.tags.hr(),
                ui.h4(t("intervention.network_with")),
                output_pyvis_network(
                    "intervention_network",
                    height="500px",
                    show_toolbar=False, show_search=False,
                    show_layout_switcher=False, show_export=False,
                    show_status=False,
                ),
                ui.tags.hr(),
                ui.h4(t("diffusion.title")),
                ui.output_ui("diffusion_summary"),
                ui.output_plot("diffusion_chart", height="260px"),
                ui.tags.hr(),
                ui.h4(t("bbn.title")),
                ui.output_ui("bbn_summary"),
                ui.output_data_frame("bbn_table"),
                ui.h5(t("bbn.paths_title"), class_="mt-3"),
                ui.p(t("bbn.paths_legend"), class_="text-muted", style="font-size: 0.8rem;"),
                ui.output_data_frame("bbn_paths"),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_intervention_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @output
    @render.ui
    def ablate_picker():
        event_bus.isa_change.get()
        choices = {el.id: f"{el.id} · {el.label}"
                   for el in project_data.get().isa_data.elements}
        return ui.input_selectize(
            "ablate", t("intervention.remove_nodes"),
            choices=choices,
            multiple=True,
            options={"plugins": ["remove_button"]},
        )

    @reactive.effect
    @reactive.event(input.reset, ignore_init=True)
    def _reset():
        ui.update_selectize("ablate", selected=[])

    @reactive.calc
    def chosen_ids() -> list[str]:
        try:
            sel = input.ablate()
        except Exception:
            sel = None
        return list(sel) if sel else []

    @reactive.calc
    def impact() -> dict[str, dict[str, float]]:
        event_bus.isa_change.get()
        ids = chosen_ids()
        if not ids:
            # Empty ablation: every node has zero delta — useful baseline.
            isa = project_data.get().isa_data
            scores = net_analysis.centrality_metrics(isa)[input.metric() or "pagerank"]
            return {nid: {"before": v, "after": v, "delta": 0.0}
                    for nid, v in scores.items()}
        return net_analysis.intervention_impact(
            project_data.get().isa_data,
            ids,
            metric=input.metric() or "pagerank",
        )

    @output
    @render.data_frame
    def impact_table():
        import pandas as pd

        rows = impact()
        if not rows:
            return pd.DataFrame(columns=["id", "label", "before", "after", "delta"])
        by_id = {el.id: el for el in project_data.get().isa_data.elements}
        data = sorted(
            rows.items(),
            key=lambda kv: abs(kv[1]["delta"]),
            reverse=True,
        )
        return pd.DataFrame([
            {
                "id": nid,
                "label": (by_id[nid].label if nid in by_id else nid),
                "type":  (by_id[nid].type  if nid in by_id else ""),
                "before": round(info["before"], 4),
                "after":  round(info["after"], 4),
                "delta":  round(info["delta"], 4),
            }
            for nid, info in data[:15]
        ])

    @output(id="intervention_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_intervention_network(
            project_data.get().isa_data, impact(), chosen_ids(),
        )

    _diffusion_result = reactive.value(None)

    @output
    @render.ui
    def diffusion_controls():
        event_bus.isa_change.get()
        els = project_data.get().isa_data.elements
        if not els:
            return ui.div()
        choices = {el.id: f"{el.id} · {el.label}" for el in els}
        # Keep the user's pick across re-renders (isolate so choosing a
        # source doesn't itself re-render this block), falling back when
        # the model no longer has that element.
        with reactive.isolate():
            try:
                current = input.diffusion_source()
            except Exception:
                current = None
        return ui.input_select(
            "diffusion_source", t("diffusion.source"), choices,
            selected=current if current in choices else els[0].id,
        )

    @reactive.effect
    def _reset_diffusion():
        event_bus.isa_change.get()
        _diffusion_result.set(None)

    @reactive.effect
    def _invalidate_diffusion():
        # Changing the source or the sliders invalidates a previous run —
        # a table computed for another intervention point must never be
        # read as the current one's.
        for read in (input.diffusion_source, input.n_steps, input.n_tokens):
            try:
                read()
            except Exception:
                pass
        _diffusion_result.set(None)

    @reactive.effect
    @reactive.event(input.run_diffusion, ignore_init=True)
    def _run_diffusion():
        try:
            src = input.diffusion_source()
        except Exception:
            src = None
        if not src:
            return
        # Fixed seed: two intervention points then differ by structure
        # rather than by chance, which is the point of comparing them.
        _diffusion_result.set(dyn.token_diffusion(
            project_data.get().isa_data, src,
            n_steps=int(input.n_steps() or 10),
            n_tokens=int(input.n_tokens() or 1000),
            seed=0,
        ))

    @output
    @render.ui
    def diffusion_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 2:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        r = _diffusion_result.get()
        if r is None:
            return ui.p(t("diffusion.hint"), class_="text-muted",
                        style="font-size: 0.85rem;")
        if not r["rows"]:
            return ui.p(t("diffusion.none"), class_="text-muted")
        header = ui.tags.tr(
            ui.tags.th("rank"), ui.tags.th(""), ui.tags.th("arrivals"),
            ui.tags.th("net sign"), ui.tags.th("first step"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(str(row["rank"])),
                ui.tags.td(f"{row['id']} · {row['label']}"),
                ui.tags.td(f"{row['tokens_received']} ±{row['margin']}"),
                ui.tags.td(ui.tags.strong(row["net_sign"])),
                ui.tags.td(str(row["first_arrival_step"])),
            )
            for row in r["rows"]
        ]
        return ui.div(
            ui.p(ui.tags.strong(t(
                "diffusion.summary", reached=r["n_reached"],
                total=len(isa.elements), tokens=r["n_tokens"],
                steps=r["n_steps"]))),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("diffusion.caption"), class_="text-muted",
                 style="font-size: 0.85rem;"),
        )

    @output
    @render.plot
    def diffusion_chart():
        import matplotlib.pyplot as plt

        r = _diffusion_result.get()
        rows = (r or {}).get("rows", [])[:12]
        fig, ax = plt.subplots(figsize=(8, 2.6))
        if rows:
            colours = {"+": "#2e7d32", "-": "#c62828", "~": "#757575"}
            # The table already carries the 95% margin; without it here the
            # chart implies a precision the Monte-Carlo sample does not have
            # (issue #20). A deterministic or single-batch run has margin 0
            # throughout, where caps would be noise rather than information.
            margins = [row["margin"] for row in rows]
            ax.bar(
                range(len(rows)),
                [row["tokens_received"] for row in rows],
                color=[colours[row["net_sign"]] for row in rows],
                yerr=margins if any(margins) else None,
                capsize=3, ecolor="#333333",
            )
            ax.set_xticks(range(len(rows)))
            ax.set_xticklabels([row["label"] for row in rows],
                               rotation=30, ha="right", fontsize=8)
            ax.set_ylabel("arrivals")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    _bbn_result = reactive.value(None)     # None | _COMPUTING | {"error": key} | query dict
    _bbn_gen = [0]                          # plain cell, NOT reactive (avoids a self-loop)

    def _bbn_work(isa, src, tgt, direction, high, low):
        """Runs in a worker thread: the lazy pgmpy import lives here. Order
        matters: the conflict check needs only path_set_dag, so a conflict
        is reported instantly even before the engine has ever been loaded."""
        info = bayes.path_set_dag(isa, src, tgt)
        if not info["nodes"]:
            return {"error": "bbn.no_path"}
        preset = {src: 1} if direction == "forward" else {tgt: 1}
        merged = bayes.merge_evidence(preset, high, low, info["nodes"])
        if merged["conflicts"]:
            return {"error": "bbn.conflict", "ids": merged["conflicts"]}
        try:
            model = bayes.model_from_dag(info)
        except bayes.BayesUnavailable:
            return {"error": "bbn.unavailable"}
        r = bayes.query_path_bbn(model, info, merged["evidence"])
        r["ignored"] = merged["ignored"]
        r["focus"] = bayes.focus_node(src, tgt, merged["evidence"])
        r["paths"] = (bayes.attribute_paths(info, merged["evidence"], r["focus"])
                      if r["focus"] else [])
        r["source"], r["target"] = src, tgt
        return r

    @reactive.extended_task
    async def _bbn_task(isa, src, tgt, direction, high, low, gen):
        return (gen, await asyncio.to_thread(_bbn_work, isa, src, tgt, direction, high, low))

    @output
    @render.ui
    def bbn_controls():
        event_bus.isa_change.get()
        els = project_data.get().isa_data.elements
        if len(els) < 2:
            return ui.div()
        choices = {el.id: f"{el.id} · {el.label}" for el in els}
        with reactive.isolate():
            try:
                cur_s = input.bbn_source()
            except Exception:
                cur_s = None
            try:
                cur_t = input.bbn_target()
            except Exception:
                cur_t = None
        return ui.div(
            ui.input_select("bbn_source", t("bbn.source"), choices,
                            selected=cur_s if cur_s in choices else els[0].id),
            ui.input_select("bbn_target", t("bbn.target"), choices,
                            selected=cur_t if cur_t in choices else els[-1].id),
        )

    @output
    @render.ui
    def bbn_evidence_controls():
        # Reacts to the pair (NOT isolated): the picker choices are the
        # path-set nodes for the current source/target. bbn_controls stays
        # isolated because it renders the very selects read here.
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        try:
            src, tgt = input.bbn_source(), input.bbn_target()
        except Exception:
            return ui.div()
        if not src or not tgt:
            return ui.div()
        info = bayes.path_set_dag(isa, src, tgt)     # networkx only, ≤3 ms on shipped projects
        if not info["nodes"]:
            return ui.p(t("bbn.no_path"), class_="text-muted", style="font-size: 0.8rem;")
        by_id = {el.id: el.label for el in isa.elements}
        choices = {n: f"{n} · {by_id.get(n, n)}" for n in info["nodes"] if n not in (src, tgt)}
        with reactive.isolate():
            def _prev(read):
                try:
                    v = read()
                except Exception:
                    v = None
                return [x for x in (list(v) if v else []) if x in choices]
            prev_hi, prev_lo = _prev(input.bbn_high), _prev(input.bbn_low)
        return ui.div(
            ui.input_selectize("bbn_high", t("bbn.also_high"), choices,
                               multiple=True, selected=prev_hi),
            ui.input_selectize("bbn_low", t("bbn.also_low"), choices,
                               multiple=True, selected=prev_lo),
        )

    @reactive.effect
    def _invalidate_bbn():
        # Any feeding input change clears the previous result (same rule as
        # diffusion): a table computed for another pair must never be read
        # as the current one's.
        event_bus.isa_change.get()
        for read in (input.bbn_source, input.bbn_target, input.bbn_direction,
                     input.bbn_high, input.bbn_low):
            try:
                read()
            except Exception:
                pass
        _bbn_gen[0] += 1          # an in-flight result for the old inputs is now stale
        _bbn_result.set(None)

    @reactive.effect
    @reactive.event(input.run_bbn, ignore_init=True)
    def _run_bbn():
        try:
            src, tgt = input.bbn_source(), input.bbn_target()
        except Exception:
            return
        if not src or not tgt:
            return

        def _picks(read):            # multi selectize: None when nothing chosen
            try:
                v = read()
            except Exception:
                v = None
            return list(v) if v else []

        high, low = _picks(input.bbn_high), _picks(input.bbn_low)
        _bbn_gen[0] += 1
        _bbn_result.set(_COMPUTING)
        _bbn_task(project_data.get().isa_data, src, tgt, input.bbn_direction(),
                  high, low, _bbn_gen[0])

    @reactive.effect
    def _bbn_observe():
        try:
            gen, r = _bbn_task.result()
        except SilentException:
            raise
        except Exception:                       # noqa: BLE001 — real task error: clear, don't crash
            logging.getLogger(__name__).exception("intervention bbn task failed")
            _bbn_result.set(None)
            return
        if gen != _bbn_gen[0]:
            return
        _bbn_result.set(r)

    @output
    @render.ui
    def bbn_summary():
        r = _bbn_result.get()
        if r is None:
            return ui.p(t("bbn.hint"), class_="text-muted", style="font-size: 0.85rem;")
        if r is _COMPUTING:       # must precede `"error" in r`: `in` on object() raises TypeError
            return ui.p(t("bbn.computing"), class_="text-muted", style="font-size: 0.85rem;")
        if "error" in r:
            cls = "text-danger" if r["error"] == "bbn.conflict" else "text-muted"
            # str.format ignores unused kwargs, so `ids` is safe on every key
            return ui.p(t(r["error"], ids=", ".join(r.get("ids", []))), class_=cls)
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        lines = [ui.p(ui.tags.strong(t(
            "bbn.summary", n=r["n_paths"], source=r["source"], target=r["target"],
            trunc=t("bbn.truncated") if r["truncated"] else "")))]
        items = ", ".join(f"{k} {t('bbn.high') if v == 1 else t('bbn.low')}"
                          for k, v in sorted(r["evidence"].items()))
        lines.append(ui.p(t("bbn.evidence", items=items), style="font-size: 0.85rem;"))
        focus = r.get("focus")
        if focus:
            row = next(x for x in r["rows"] if x["id"] == focus)
            lines.append(ui.p(t("bbn.target_line", id=focus, label=by_id.get(focus, focus),
                                base=f"{row['baseline']:.2f}", post=f"{row['p_high']:.2f}",
                                delta=f"{row['delta']:+.2f}")))
        if r.get("ignored"):
            lines.append(ui.p(t("bbn.ignored", ids=", ".join(r["ignored"])),
                              class_="text-muted", style="font-size: 0.85rem;"))
        if r["cut_edges"]:
            lines.append(ui.p(t("bbn.cut", n=len(r["cut_edges"]),
                                edges=", ".join(f"{u}→{v}" for u, v in r["cut_edges"])),
                              class_="text-warning", style="font-size: 0.85rem;"))
        return ui.div(*lines)

    @output
    @render.data_frame
    def bbn_table():
        import pandas as pd

        r = _bbn_result.get()
        cols = ["id", "label", "type", "baseline", "posterior", "delta"]
        if not isinstance(r, dict) or "error" in r:     # None, _COMPUTING, or an error
            return pd.DataFrame(columns=cols)
        by_id = {el.id: el for el in project_data.get().isa_data.elements}
        return pd.DataFrame([{
            "id": x["id"],
            "label": by_id[x["id"]].label if x["id"] in by_id else x["id"],
            "type": by_id[x["id"]].type if x["id"] in by_id else "",
            "baseline": round(x["baseline"], 3),
            "posterior": round(x["p_high"], 3),
            "delta": round(x["delta"], 3),
        } for x in r["rows"]], columns=cols)

    @output
    @render.data_frame
    def bbn_paths():
        import pandas as pd

        r = _bbn_result.get()
        cols = ["path", "length", "polarity", "solo baseline", "solo posterior", "solo delta"]
        if not isinstance(r, dict) or "error" in r:     # None, _COMPUTING, or an error
            return pd.DataFrame(columns=cols)
        by_id = {el.id: el.label for el in project_data.get().isa_data.elements}
        return pd.DataFrame([{
            "path": " → ".join(by_id.get(n, n) for n in x["path"]),
            "length": x["length"],
            "polarity": x["polarity"],
            "solo baseline": round(x["baseline"], 3),
            "solo posterior": round(x["p_high"], 3),
            "solo delta": round(x["delta"], 3),
        } for x in r.get("paths", [])], columns=cols)
