"""Boolean / Laplacian analysis module.

Mirrors `modules/analysis_boolean.R`. Two tabs:
  - Laplacian: bar chart of eigenvalue spectrum + stability summary card.
  - Boolean: attractor table from exhaustive 2^N state-space search.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot, no pyvis).
"""
from __future__ import annotations

import numpy as np
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import dynamics
from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t


def _format_state(state_int: int, n: int) -> str:
    """Format integer state as fixed-width binary string, LSB-first by node index.

    Returns an empty string for n == 0. For n > 0, the i-th character of
    the result corresponds to bit i of state_int (the value of node i).
    """
    if n == 0:
        return ""
    return format(state_int, f"0{n}b")[::-1]  # reverse so bit i = node i


@module.ui
def analysis_boolean_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.boolean")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("boolean.controls")),
                ui.input_radio_buttons(
                    "direction",
                    t("boolean.direction"),
                    {"cols": t("boolean.cols"), "rows": t("boolean.rows")},
                    selected="cols",
                ),
                ui.input_slider(
                    "max_nodes",
                    t("boolean.max_nodes"),
                    min=4, max=12, value=12, step=1,
                ),
                ui.tags.hr(),
                ui.input_action_button(
                    "run_boolean",
                    t("boolean.run"),
                    class_="btn btn-primary btn-block",
                ),
                width=280,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("boolean.tab_laplacian"),
                    ui.output_plot("eigenvalue_plot", height="280px"),
                    ui.tags.hr(),
                    ui.output_ui("stability_summary"),
                ),
                ui.nav_panel(
                    t("boolean.tab_boolean"),
                    ui.output_ui("attractor_panel"),
                ),
                id="boolean_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_boolean_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    result_store: reactive.Value[dict | None] = reactive.value(None)

    @reactive.effect
    @reactive.event(input.run_boolean, ignore_init=True)
    def _run() -> None:
        try:
            isa = project_data.get().isa_data
            if not isa.elements:
                result_store.set({"error": t("boolean.no_data"), "stability": None,
                                  "attractors": None, "node_ids": []})
                return
            M, node_ids = dynamics.isa_to_numeric_matrix(isa)
            stability = dynamics.laplacian_stability(M, direction=input.direction() or "cols")
            rules = dynamics.create_boolean_rules(M)
            attractors = dynamics.boolean_attractors(rules, max_nodes=int(input.max_nodes() or 12))
            result_store.set({
                "error": None,
                "stability": stability,
                "attractors": attractors,
                "node_ids": node_ids,
            })
        except (ValueError, np.linalg.LinAlgError) as exc:
            result_store.set({
                "error": str(exc),
                "stability": None,
                "attractors": None,
                "node_ids": [],
            })

    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe ONLY to ISA changes. The reactive read of result_store
        # must be isolated — otherwise this effect re-fires when Run sets
        # result_store and would post a spurious "data changed" notification
        # immediately after a successful run.
        event_bus.isa_change.get()
        with reactive.isolate():
            if result_store.get() is not None:
                ui.notification_show(
                    t("analysis.common.data_changed_rerun"),
                    duration=5,
                    type="warning",
                )

    @output
    @render.plot
    def eigenvalue_plot():
        import matplotlib.pyplot as plt

        r = result_store.get()
        fig, ax = plt.subplots(figsize=(8, 2.6))
        if r is None:
            ax.text(0.5, 0.5, t("boolean.click_run"), ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            fig.tight_layout()
            return fig
        if r.get("error"):
            ax.text(0.5, 0.5, r["error"], ha="center", va="center",
                    color="#a02020", transform=ax.transAxes, wrap=True)
            ax.axis("off")
            fig.tight_layout()
            return fig
        eigvals = r["stability"]["eigenvalues"]
        reals = [v.real for v in eigvals]
        ax.bar(range(len(reals)), reals, color="#4a90b8", edgecolor="#2d5a7b")
        ax.set_xlabel(t("boolean.eigenvalue_index"))
        ax.set_ylabel(t("boolean.real_part"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def stability_summary():
        r = result_store.get()
        if r is None or r.get("error") or r.get("stability") is None:
            return ui.tags.p(t("boolean.click_run"), class_="text-muted")
        s = r["stability"]
        return ui.tags.dl(
            ui.tags.dt(t("boolean.spectral_radius")),
            ui.tags.dd(f"{s['spectral_radius']:.4f}"),
            ui.tags.dt(t("boolean.algebraic_connectivity")),
            ui.tags.dd(f"{s['algebraic_connectivity']:.4f}"),
            ui.tags.dt(t("boolean.stability_class")),
            ui.tags.dd(s["stability_class"]),
        )

    @output
    @render.ui
    def attractor_panel():
        import pandas as pd

        r = result_store.get()
        if r is None:
            return ui.tags.p(t("boolean.click_run"), class_="text-muted")
        if r.get("error"):
            return ui.tags.div(r["error"], class_="alert alert-danger")
        a = r["attractors"]
        node_ids = r["node_ids"]
        n = len(node_ids)

        if a.get("error") == "too_large":
            n_n = a.get("n_nodes", 0)
            if n_n <= 12:
                msg = t("boolean.cap_below_12").format(n=n_n)
            else:
                msg = t("boolean.cap_above_12").format(n=n_n)
            return ui.tags.div(msg, class_="alert alert-warning")

        rows = []
        for att in a.get("attractors", []):
            states = att["states"]
            first = _format_state(states[0], n) if states else ""
            extra = f" + {att['period'] - 1} more" if att["period"] > 1 else ""
            rows.append({
                "type": att["type"],
                "period": att["period"],
                "basin_size": att["basin_size"],
                "representative state": first + extra,
            })
        if not rows:
            return ui.tags.p(t("boolean.no_attractors"))
        df = pd.DataFrame(rows)
        return ui.HTML(df.to_html(index=False, classes="table table-sm table-striped"))
