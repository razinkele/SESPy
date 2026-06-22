"""Influence × Dependence Quadrant — QSEM Phase-1 parity.

Plots every factor by its influence (Σ outgoing edge weight) against its
dependence (Σ incoming edge weight), split at the mean of each axis into the
four Vester quadrants (active / critical / reactive / buffering), with an
'undetermined' state for systems with no structural differentiation. The
scoring lives in `sespy/network.py::influence_dependence`; this module is a thin
presenter mirroring `analysis_leverage.py`.
"""

from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import network as net_analysis
from ..constants import DEFAULT_GROUP_COLOR, ELEMENT_COLORS
from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t

_QUADRANT_KEYS = {
    "active": "quadrant.active",
    "critical": "quadrant.critical",
    "reactive": "quadrant.reactive",
    "buffering": "quadrant.buffering",
    "undetermined": "quadrant.undetermined",
}


@module.ui
def analysis_quadrant_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.quadrant")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("quadrant.about")),
                ui.p(
                    t("quadrant.about_text"),
                    class_="text-muted",
                    style="font-size: 0.85rem;",
                ),
                ui.tags.hr(),
                ui.input_radio_buttons(
                    "split", t("quadrant.split"),
                    {"mean": t("quadrant.split_mean"), "median": t("quadrant.split_median")},
                    selected="mean", inline=True,
                ),
                width=260,
            ),
            ui.div(
                ui.h4(t("quadrant.map")),
                ui.output_plot("quadrant_plot", height="460px"),
                ui.output_ui("skew_caption"),
                ui.tags.hr(),
                ui.h4(t("quadrant.classification")),
                ui.output_data_frame("quadrant_table"),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_quadrant_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def rows() -> dict[str, dict]:
        event_bus.isa_change.get()
        return net_analysis.influence_dependence(project_data.get().isa_data,
                                                 split=input.split())

    @output
    @render.plot
    def quadrant_plot():
        import matplotlib.pyplot as plt

        data = rows()
        isa = project_data.get().isa_data
        type_by_id = {el.id: el.type for el in isa.elements}
        label_by_id = {el.id: el.label for el in isa.elements}

        fig, ax = plt.subplots(figsize=(7, 5))

        undetermined = bool(data) and all(
            r["quadrant"] == "undetermined" for r in data.values()
        )
        if not data or undetermined:
            msg = t("quadrant.empty_no_data") if not data else \
                  t("quadrant.empty_no_differentiation")
            ax.text(0.5, 0.5, msg, ha="center", va="center",
                    transform=ax.transAxes, color="#777")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        infl = [r["influence"] for r in data.values()]
        dep = [r["dependence"] for r in data.values()]
        thr_inf = net_analysis.axis_threshold(infl, input.split())
        thr_dep = net_analysis.axis_threshold(dep, input.split())

        for nid, r in data.items():
            ax.scatter(
                r["dependence"], r["influence"],
                s=140, alpha=0.85, zorder=3,
                color=ELEMENT_COLORS.get(type_by_id.get(nid), DEFAULT_GROUP_COLOR),
                edgecolors="#2d5a7b", linewidths=0.8,
            )
            ax.annotate(
                label_by_id.get(nid, nid),
                (r["dependence"], r["influence"]),
                textcoords="offset points", xytext=(6, 4),
                fontsize=8, color="#2c3e50",
            )

        ax.axvline(thr_dep, color="#aaa", linestyle="--", linewidth=1, zorder=1)
        ax.axhline(thr_inf, color="#aaa", linestyle="--", linewidth=1, zorder=1)

        xhi = max(dep) * 1.05 + 0.5
        yhi = max(infl) * 1.05 + 0.5
        ax.set_xlim(-0.5, xhi)
        ax.set_ylim(-0.5, yhi)
        cap = dict(fontsize=8, color="#999", style="italic")
        ax.text(xhi, yhi, t("quadrant.critical"), ha="right", va="top", **cap)
        ax.text(-0.4, yhi, t("quadrant.active"), ha="left", va="top", **cap)
        ax.text(-0.4, -0.4, t("quadrant.buffering"), ha="left", va="bottom", **cap)
        ax.text(xhi, -0.4, t("quadrant.reactive"), ha="right", va="bottom", **cap)

        ax.set_xlabel(t("quadrant.axis_dependence"))
        ax.set_ylabel(t("quadrant.axis_influence"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def skew_caption():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if input.split() == "mean" and net_analysis.influence_skew(isa):
            return ui.tags.small(t("quadrant.skew_warning"), class_="text-muted")
        return ui.tags.div()   # empty — matches the repo's empty-@render.ui convention

    @output
    @render.data_frame
    def quadrant_table():
        import pandas as pd

        cols = ["rank", "id", "label", "type", "influence", "dependence", "quadrant"]
        data = rows()
        if not data:
            return pd.DataFrame(columns=cols)
        isa = project_data.get().isa_data
        by_id = {el.id: el for el in isa.elements}
        ordered = sorted(data.items(), key=lambda kv: kv[1]["influence"], reverse=True)
        out = []
        for rank, (nid, r) in enumerate(ordered, start=1):
            el = by_id.get(nid)
            out.append({
                "rank": rank,
                "id": nid,
                "label": el.label if el else nid,
                "type": el.type if el else "",
                "influence": round(r["influence"], 3),
                "dependence": round(r["dependence"], 3),
                "quadrant": t(_QUADRANT_KEYS.get(r["quadrant"], r["quadrant"])),
            })
        return pd.DataFrame(out, columns=cols)
