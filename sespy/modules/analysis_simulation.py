"""Dynamic Simulation analysis module.

Mirrors the deterministic-sim + Monte Carlo state-shift parts of
`modules/analysis_simulation.R`. Two run buttons:
  - Run Simulation: deterministic linear iteration; trajectories + final state.
  - Run Monte Carlo: perturbed-matrix sampling; per-node summary + histograms.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot).
"""
from __future__ import annotations

import numpy as np
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from .. import dynamics
from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t


@module.ui
def analysis_simulation_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.simulation")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("simulation.controls")),
                ui.input_slider(
                    "n_iter", t("simulation.n_iter"),
                    min=50, max=2000, value=200, step=50,
                ),
                ui.input_radio_buttons(
                    "initial_state", t("simulation.initial_state"),
                    {
                        "zeros": t("simulation.init_zeros"),
                        "random": t("simulation.init_random"),
                        "uniform": t("simulation.init_uniform"),
                    },
                    selected="random",
                ),
                ui.input_numeric(
                    "sim_seed", t("simulation.seed"), value=42, min=0,
                ),
                ui.input_action_button(
                    "run_sim", t("simulation.run_sim"),
                    class_="btn btn-primary btn-block",
                ),
                ui.tags.hr(),
                ui.h5(t("simulation.mc_controls")),
                ui.input_slider(
                    "n_simulations", t("simulation.n_simulations"),
                    min=10, max=500, value=100, step=10,
                ),
                ui.input_radio_buttons(
                    "kind", t("simulation.kind"),
                    {
                        "uniform": t("simulation.kind_uniform"),
                        "sign_flip": t("simulation.kind_sign_flip"),
                        "gaussian": t("simulation.kind_gaussian"),
                    },
                    selected="uniform",
                ),
                ui.input_numeric(
                    "mc_seed", t("simulation.seed"), value=42, min=0,
                ),
                ui.input_action_button(
                    "run_mc", t("simulation.run_mc"),
                    class_="btn btn-primary btn-block",
                ),
                width=300,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("simulation.tab_trajectories"),
                    ui.output_plot("trajectory_plot", height="400px"),
                ),
                ui.nav_panel(
                    t("simulation.tab_final_state"),
                    ui.output_plot("final_state_plot", height="320px"),
                ),
                ui.nav_panel(
                    t("simulation.tab_mc"),
                    ui.output_ui("mc_summary"),
                    ui.output_plot("mc_histograms", height="500px"),
                ),
                id="simulation_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_simulation_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    sim_store: reactive.Value[dict | None] = reactive.value(None)
    mc_store: reactive.Value[dict | None] = reactive.value(None)

    def _build_matrix() -> tuple[np.ndarray, list[str]] | None:
        """Return (M, node_ids) or None if there is no ISA data.

        Raises ValueError if matrix construction fails — caller is responsible
        for catching and surfacing the error to the UI.
        """
        isa = project_data.get().isa_data
        if not isa.elements:
            return None
        return dynamics.isa_to_numeric_matrix(isa)

    @reactive.effect
    @reactive.event(input.run_sim, ignore_init=True)
    def _run_sim() -> None:
        try:
            built = _build_matrix()
            if built is None:
                sim_store.set({"error": t("simulation.no_data"), "traj": None,
                               "node_ids": []})
                return
            M, node_ids = built
            traj = dynamics.simulate_dynamics(
                M, n_iter=int(input.n_iter() or 200),
                initial_state=input.initial_state() or "random",
                seed=int(input.sim_seed() or 42),
            )
            sim_store.set({"error": None, "traj": traj, "node_ids": node_ids})
        except (ValueError, np.linalg.LinAlgError) as exc:
            sim_store.set({"error": str(exc), "traj": None, "node_ids": []})

    @reactive.effect
    @reactive.event(input.run_mc, ignore_init=True)
    def _run_mc() -> None:
        try:
            built = _build_matrix()
            if built is None:
                mc_store.set({"error": t("simulation.no_data"), "result": None,
                              "node_ids": []})
                return
            M, node_ids = built
            res = dynamics.state_shift_monte_carlo(
                M, n_simulations=int(input.n_simulations() or 100),
                n_iter=int(input.n_iter() or 200),
                kind=input.kind() or "uniform",
                seed=int(input.mc_seed() or 42),
            )
            mc_store.set({"error": None, "result": res, "node_ids": node_ids})
        except (ValueError, np.linalg.LinAlgError) as exc:
            mc_store.set({"error": str(exc), "result": None, "node_ids": []})

    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe ONLY to ISA changes; isolate the result-store reads so
        # this effect doesn't re-fire when Run* updates a store.
        event_bus.isa_change.get()
        with reactive.isolate():
            if sim_store.get() is not None or mc_store.get() is not None:
                ui.notification_show(
                    t("analysis.common.data_changed_rerun"),
                    duration=5,
                    type="warning",
                )

    # ---- Trajectory plot ----

    @output
    @render.plot
    def trajectory_plot():
        import matplotlib.pyplot as plt

        s = sim_store.get()
        fig, ax = plt.subplots(figsize=(10, 4.5))
        if s is None:
            ax.text(0.5, 0.5, t("simulation.click_run"), ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            return fig
        if s.get("error"):
            ax.text(0.5, 0.5, s["error"], ha="center", va="center",
                    transform=ax.transAxes, color="#a02020", wrap=True)
            ax.axis("off")
            return fig
        traj = s["traj"]
        node_ids = s["node_ids"]
        n_steps, n_nodes = traj.shape
        cmap = plt.get_cmap("viridis")
        for j in range(n_nodes):
            ax.plot(
                range(n_steps), traj[:, j],
                color=cmap(j / max(1, n_nodes - 1)),
                label=node_ids[j],
                linewidth=1.2,
            )
        ax.set_xlabel("iteration")
        ax.set_ylabel("value")
        if n_nodes <= 18:
            ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
                      fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    # ---- Final-state bar chart ----

    @output
    @render.plot
    def final_state_plot():
        import matplotlib.pyplot as plt

        s = sim_store.get()
        fig, ax = plt.subplots(figsize=(10, 3.5))
        if s is None or s.get("error") or s.get("traj") is None:
            ax.axis("off")
            return fig
        traj = s["traj"]
        final = traj[-1]
        node_ids = s["node_ids"]
        ax.bar(range(len(final)), final, color="#4a90b8", edgecolor="#2d5a7b")
        ax.set_xticks(range(len(final)))
        ax.set_xticklabels(node_ids, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("final value")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    # ---- Monte Carlo summary + histograms ----

    @output
    @render.ui
    def mc_summary():
        m = mc_store.get()
        if m is None:
            return ui.tags.p(t("simulation.click_run"), class_="text-muted")
        if m.get("error"):
            return ui.tags.div(m["error"], class_="alert alert-danger")
        res = m["result"]
        ok = res["n_simulations"] - res["n_failed"]
        msg = t("simulation.completed").format(
            ok=ok, n=res["n_simulations"], failed=res["n_failed"]
        )
        # Per-node summary table
        import pandas as pd

        node_ids = m["node_ids"]
        rows = []
        for i, nid in enumerate(node_ids):
            s = res["summary"][i]
            rows.append({
                "node": nid,
                "mean": f"{s['mean']:.4f}",
                "sd": f"{s['sd']:.4f}",
                "p5": f"{s['p5']:.4f}",
                "p95": f"{s['p95']:.4f}",
            })
        df = pd.DataFrame(rows)
        return ui.tags.div(
            ui.tags.p(msg, class_="text-info"),
            ui.HTML(df.to_html(index=False, classes="table table-sm table-striped")),
        )

    @output
    @render.plot
    def mc_histograms():
        import matplotlib.pyplot as plt

        m = mc_store.get()
        if m is None or m.get("error") or m.get("result") is None:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.axis("off")
            return fig
        res = m["result"]
        node_ids = m["node_ids"]
        n_nodes = len(node_ids)
        if res["final_states"].size == 0:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, "All simulations diverged.", ha="center", va="center",
                    transform=ax.transAxes)
            ax.axis("off")
            return fig
        # Small multiples: up to 4 cols, ceil(n/4) rows
        ncols = min(4, n_nodes)
        nrows = (n_nodes + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(10, 2.4 * nrows),
                                  squeeze=False)
        for i in range(n_nodes):
            r, c = divmod(i, ncols)
            ax = axes[r][c]
            ax.hist(res["final_states"][:, i], bins=15,
                    color="#4a90b8", edgecolor="#2d5a7b", alpha=0.85)
            ax.set_title(node_ids[i], fontsize=9)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        # Hide unused axes
        for k in range(n_nodes, nrows * ncols):
            r, c = divmod(k, ncols)
            axes[r][c].axis("off")
        fig.tight_layout()
        return fig
