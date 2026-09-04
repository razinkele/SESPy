"""Network Metrics Analysis module.

Mirrors the structure of `modules/analysis_metrics.R` (677 lines, 4 tabs in R).
This POC keeps the most useful slice — a metric-picker + top-N table + a
distribution histogram + a pyvis network sized by the chosen metric. The R
module's tabs ("Leverage", "Distribution", "Network View") collapse into
one panel here; per CLAUDE.md, the analysis-module signature contract is
preserved (event_bus, project_data_reactive, i18n).

Why this matters for the port: this is the third reactive consumer of
`event_bus.isa_change` after `cld_visualization` and `analysis_loops`. With
project_io now live, an upload or "New Project" click triggers
`emit_isa_change`, which means three modules invalidate their derived state
in the same tick. If the event-bus pattern can survive three-way coupling
without re-entrancy bugs, the architecture scales.
"""

from __future__ import annotations

from pyvis.network import Network
from pyvis.shiny import output_pyvis_network, render_pyvis_network
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

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

METRIC_LABEL_KEYS: dict[str, str] = {
    "degree":      "metrics.degree",
    "indegree":    "metrics.indegree",
    "outdegree":   "metrics.outdegree",
    "betweenness": "metrics.betweenness",
    "closeness":   "metrics.closeness",
    "eigenvector": "metrics.eigenvector",
    "pagerank":    "metrics.pagerank",
}


def _scaled_size(value: float, lo: float, hi: float, *, smin: int = 18, smax: int = 60) -> int:
    """Linear-interpolate `value` from [lo, hi] to [smin, smax] for vis-network
    node sizing. Equal min and max yield the midpoint so isolated nodes don't
    collapse to a point on graphs where a metric is constant.
    """
    if hi <= lo:
        return (smin + smax) // 2
    frac = (value - lo) / (hi - lo)
    return int(smin + frac * (smax - smin))


def governance_gap_state(r: dict, n_elements: int) -> str:
    """Which degenerate UI state applies to a governance_gap() result —
    '' means render the full block. Order matters: untyped-domination
    outranks no-governance because "map your themes first" is the
    actionable message when both hold (e.g. a raw .qsem import where
    every element is untyped). Pure.

    States: 'none' | 'untyped' | 'no_gov' | 'no_eco' | 'no_press' | ''
    """
    if r["n_edges_considered"] == 0:
        return "none"
    if n_elements and r["n_unclassified"] / n_elements > 0.5:
        return "untyped"
    if r["n_governance"] == 0:
        return "no_gov"
    if r["n_ecological"] == 0:
        return "no_eco"
    if r["gaps_by_type"].get("Pressures", {"n": 0})["n"] == 0:
        return "no_press"
    return ""


def governance_concentration_verdict(gc: dict) -> tuple[str, dict] | None:
    """Translation key + format kwargs for the one-line governance
    concentration verdict (#26), or None below two actors. The wording
    follows the NUMBER THE USER SEES: entropy is rounded to 2 dp first and
    the distributed/concentrated split is taken on that rounded value, so
    one printed entropy can never carry two different verdicts. Pure.
    """
    if gc["n_actors"] < 2:
        return None
    entropy = f"{gc['normalised_entropy']:.2f}"
    if float(entropy) >= 0.5:
        return ("metrics.gov_concentration_distributed",
                {"n": gc["n_actors"], "entropy": entropy})
    return ("metrics.gov_concentration_concentrated",
            {"actor": gc["dominant_actor"],
             "share": f"{gc['dominant_share']:.2f}",
             "n": gc["n_actors"], "entropy": entropy})


def _build_metrics_network(
    isa: IsaData,
    metric: str,
    scores: dict[str, float],
) -> Network:
    """A pyvis Network with node sizes proportional to the chosen metric.
    Layout is force-directed (the metric tells you which nodes are central
    — hierarchical would defeat that)."""
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
            title=f"{el.type}: {el.label}\n{metric}: {v:.4f}",
            color=ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            size=_scaled_size(v, lo, hi),
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
def analysis_metrics_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.metrics")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("metrics.metric")),
                ui.input_radio_buttons(
                    "metric",
                    None,
                    {k: k.title() for k in net_analysis.CENTRALITY_METRICS},
                    selected="degree",
                ),
                ui.tags.hr(),
                ui.input_slider(
                    "top_n", t("metrics.show_top_n"),
                    min=3, max=20, value=10, step=1,
                ),
                width=240,
            ),
            ui.div(
                ui.output_ui("fit_summary"),
                ui.tags.hr(),
                ui.output_ui("governance_gap_summary"),
                ui.tags.hr(),
                ui.output_ui("actor_influence_summary"),
                ui.tags.hr(),
                ui.output_ui("cascade_summary"),
                ui.tags.hr(),
                ui.output_ui("paths_summary"),
                ui.tags.hr(),
                ui.output_ui("hypermodules_summary"),
                ui.tags.hr(),
                ui.h4(t("metrics.top_ranked")),
                ui.output_data_frame("metrics_table"),
                ui.tags.hr(),
                ui.h4(t("metrics.distribution")),
                ui.output_plot("metrics_hist", height="220px"),
                ui.tags.hr(),
                ui.h4(t("metrics.network_sized")),
                output_pyvis_network(
                    "metrics_network",
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
def analysis_metrics_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def metrics() -> dict[str, dict[str, float]]:
        # Subscribe to isa_change so a project load/new resets memoization
        # via the reactive graph re-running this calc.
        event_bus.isa_change.get()
        return net_analysis.centrality_metrics(project_data.get().isa_data)

    @reactive.calc
    def chosen_metric() -> str:
        return input.metric() or "degree"

    @reactive.calc
    def top_rows() -> list[dict]:
        return net_analysis.top_n_by_metric(
            project_data.get().isa_data,
            chosen_metric(),
            n=int(input.top_n() or 10),
        )

    @output
    @render.data_frame
    def metrics_table():
        import pandas as pd

        rows = top_rows()
        if not rows:
            return pd.DataFrame(columns=["rank", "id", "label", "type", "value"])
        return pd.DataFrame(rows)

    @output
    @render.plot
    def metrics_hist():
        import matplotlib.pyplot as plt

        scores = list(metrics()[chosen_metric()].values())
        fig, ax = plt.subplots(figsize=(8, 2.4))
        if scores:
            ax.hist(scores, bins=12, color="#4a90b8", edgecolor="#2d5a7b", alpha=0.85)
        ax.set_xlabel(chosen_metric())
        ax.set_ylabel("count")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def fit_summary():
        event_bus.isa_change.get()
        r = net_analysis.social_ecological_fit(project_data.get().isa_data)
        if r["total_edges"] == 0:
            return ui.p(t("metrics.fit_none"), class_="text-muted")
        return ui.div(
            ui.h5(t("metrics.fit")),
            ui.tags.strong(f"{r['fit']:.2f}"),
            ui.p(t("metrics.fit_caption", cross=r["cross_edges"], total=r["total_edges"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )

    @output
    @render.ui
    def governance_gap_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        r = net_analysis.governance_gap(isa)
        state = governance_gap_state(r, len(isa.elements))
        if state in ("none", "untyped", "no_gov"):
            key = {"none": "metrics.gov_gap_none",
                   "untyped": "metrics.gov_gap_untyped",
                   "no_gov": "metrics.gov_gap_no_gov"}[state]
            return ui.p(t(key), class_="text-muted")
        orphan_line = None
        if r["governance_orphans"]:
            labels = {el.id: el.label for el in isa.elements}
            shown = ", ".join(f"{i} · {labels.get(i, i)}"
                              for i in r["governance_orphans"][:5])
            orphan_line = ui.p(
                t("metrics.gov_gap_orphans",
                  n=len(r["governance_orphans"]), ids=shown),
                class_="text-muted", style="font-size: 0.85rem;")
        if state in ("no_eco", "no_press"):
            key = "metrics.gov_gap_no_eco" if state == "no_eco" else "metrics.gov_gap_no_press"
            return ui.div(
                ui.h5(t("metrics.gov_gap")),
                ui.p(t(key), class_="text-muted"),
                orphan_line,
            )
        press = r["gaps_by_type"].get("Pressures", {"n": 0, "uncovered": []})
        return ui.div(
            ui.h5(t("metrics.gov_gap")),
            ui.tags.strong(f"{r['pressure_gap_fraction']:.2f}"),
            ui.p(t("metrics.gov_gap_caption",
                   uncovered=len(press["uncovered"]), n=press["n"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
            orphan_line,
        )

    @output
    @render.ui
    def actor_influence_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if net_analysis.governance_gap(isa)["n_edges_considered"] == 0:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        rows = net_analysis.governance_actor_influence(isa)
        if not rows:
            return ui.p(t("metrics.gov_gap_no_gov"), class_="text-muted")
        header = ui.tags.tr(
            ui.tags.th(""),
            ui.tags.th("betweenness"), ui.tags.th("eigenvector"),
            ui.tags.th("pagerank"), ui.tags.th("influence"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(f"{r['id']} · {r['label']}"),
                ui.tags.td(f"{r['betweenness']:.2f}"),
                ui.tags.td(f"{r['eigenvector']:.2f}"),
                ui.tags.td(f"{r['pagerank']:.2f}"),
                ui.tags.td(ui.tags.strong(f"{r['influence']:.2f}")),
            )
            for r in rows
        ]
        verdict = governance_concentration_verdict(
            net_analysis.governance_concentration(isa))
        concentration = None
        if verdict is not None:
            key, kwargs = verdict
            concentration = ui.p(t(key, **kwargs), class_="mb-2")
        return ui.div(
            ui.h5(t("metrics.actor_influence")),
            concentration,
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("metrics.actor_influence_caption"),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )

    _cascade_result = reactive.value(None)

    @reactive.effect
    def _reset_cascade():
        # Any model change invalidates a previously computed cascade —
        # a stale table must never masquerade as current.
        event_bus.isa_change.get()
        _cascade_result.set(None)

    @reactive.effect
    @reactive.event(input.run_cascade, ignore_init=True)
    def _compute_cascade():
        _cascade_result.set(
            net_analysis.cascade_vulnerability(project_data.get().isa_data))

    @output
    @render.ui
    def cascade_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 3:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        button = ui.input_action_button(
            "run_cascade", t("metrics.cascade_run"),
            class_="btn-sm btn-outline-primary")
        r = _cascade_result.get()
        # empty steps = trivial result from a race with a shrinking model — treat as idle
        if r is None or not r["steps"]:
            return ui.div(
                ui.h5(t("metrics.cascade")),
                button,
                ui.p(t("metrics.cascade_hint"), class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        thr_row = max(r["steps"], key=lambda row: row["delta_lccf"])
        ew_row = next((row for row in r["steps"]
                       if row["removed_id"] == r["early_warning_node"]), None)
        early_warning = (
            t("metrics.cascade_early_warning_none") if ew_row is None else
            t("metrics.cascade_early_warning",
              id=f"{ew_row['removed_id']} · {ew_row['removed_label']}",
              step=ew_row["step"], kl=f"{ew_row['kl_divergence']:.2f}",
              thr_step=thr_row["step"]))
        header = ui.tags.tr(
            ui.tags.th("step"), ui.tags.th(""), ui.tags.th("lccf"),
            ui.tags.th("loops"), ui.tags.th("Δ lccf"), ui.tags.th("KL"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(str(row["step"])),
                ui.tags.td(f"{row['removed_id']} · {row['removed_label']}"),
                ui.tags.td(f"{row['lccf']:.2f}"),
                ui.tags.td(str(row["loop_count"])),
                ui.tags.td(f"{row['delta_lccf']:.2f}"),
                ui.tags.td(f"{row['kl_divergence']:.2f}"),
            )
            for row in r["steps"]
        ]
        return ui.div(
            ui.h5(t("metrics.cascade")),
            button,
            ui.p(ui.tags.strong(
                t("metrics.cascade_threshold",
                  id=f"{thr_row['removed_id']} · {thr_row['removed_label']}",
                  delta=f"{thr_row['delta_lccf']:.2f}")),
                style="margin-top: 0.5rem;"),
            ui.p(ui.tags.strong(early_warning), class_="mb-2"),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            ui.p(t("metrics.cascade_caption",
                   n=len(r["steps"]), total=r["n_ranked"]),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )

    _paths_result = reactive.value(None)

    @reactive.effect
    def _reset_paths():
        # A model change invalidates a previously traced result.
        event_bus.isa_change.get()
        _paths_result.set(None)

    @reactive.effect
    @reactive.event(input.trace_paths, ignore_init=True)
    def _compute_paths():
        _paths_result.set(net_analysis.causal_paths(
            project_data.get().isa_data,
            input.paths_source(), input.paths_target()))

    @output
    @render.ui
    def paths_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 2:
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        choices = {el.id: f"{el.id} · {el.label}" for el in isa.elements}

        def _current(input_val, fallback: str) -> str:
            # Keep the user's selection across re-renders (a trace result
            # re-renders this block); isolate() so typing in the selects
            # doesn't itself re-render, and fall back when the model changed.
            with reactive.isolate():
                try:
                    v = input_val()
                except Exception:
                    v = None
            return v if v in choices else fallback

        controls = ui.div(
            ui.input_select("paths_source", t("metrics.paths_source"), choices,
                            selected=_current(input.paths_source,
                                              isa.elements[0].id)),
            ui.input_select("paths_target", t("metrics.paths_target"), choices,
                            selected=_current(input.paths_target,
                                              isa.elements[-1].id)),
            ui.input_action_button("trace_paths", t("metrics.paths_trace"),
                                   class_="btn-sm btn-outline-primary"),
        )
        r = _paths_result.get()
        if r is None:
            return ui.div(
                ui.h5(t("metrics.paths")), controls,
                ui.p(t("metrics.cascade_hint"), class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        if not r["paths"]:
            return ui.div(
                ui.h5(t("metrics.paths")), controls,
                ui.p(t("metrics.paths_none"), class_="text-muted",
                     style="margin-top: 0.5rem;"),
            )
        labels = {el.id: el.label for el in isa.elements}
        header = ui.tags.tr(
            ui.tags.th(""), ui.tags.th("length"), ui.tags.th("polarity"),
        )
        body = [
            ui.tags.tr(
                ui.tags.td(" → ".join(labels.get(n, n) for n in row["path"])),
                ui.tags.td(str(row["length"])),
                ui.tags.td(ui.tags.strong(row["polarity"])),
            )
            for row in r["paths"]
        ]
        c = r["counts"]
        trunc_line = None
        if r["truncated"]:
            trunc_line = ui.p(t("metrics.paths_truncated", max=len(r["paths"])),
                              class_="text-muted", style="font-size: 0.85rem;")
        return ui.div(
            ui.h5(t("metrics.paths")), controls,
            ui.p(ui.tags.strong(
                t("metrics.paths_summary", n=len(r["paths"]),
                  pos=c["+"], neg=c["-"], amb=c["0"])),
                style="margin-top: 0.5rem;"),
            ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body),
                          class_="table table-sm"),
            trunc_line,
        )

    _hypermodules_result = reactive.value(None)

    @reactive.effect
    def _reset_hypermodules():
        # Any model change invalidates a computed result — a stale table
        # must never masquerade as current. (Same contract as the cascade.)
        event_bus.isa_change.get()
        _hypermodules_result.set(None)

    @reactive.effect
    @reactive.event(input.run_hypermodules, ignore_init=True)
    def _compute_hypermodules():
        _hypermodules_result.set(
            net_analysis.hypermodules(project_data.get().isa_data))

    @output
    @render.ui
    def hypermodules_summary():
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        if len(isa.elements) < 3:
            # gov_gap_none is the card's shared too-small message — the
            # cascade and paths blocks use the same key for this guard.
            return ui.p(t("metrics.gov_gap_none"), class_="text-muted")
        button = ui.input_action_button(
            "run_hypermodules", t("metrics.hypermodules_run"),
            class_="btn-sm btn-outline-primary")
        r = _hypermodules_result.get()
        if r is None:
            return ui.div(
                ui.h5(t("metrics.hypermodules")),
                button,
                ui.p(t("metrics.hypermodules_hint"), class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        if r["note"]:
            return ui.div(
                ui.h5(t("metrics.hypermodules")),
                button,
                ui.p(t(f"metrics.hypermodules_{r['note']}"),
                     class_="text-muted",
                     style="font-size: 0.85rem; margin-top: 0.5rem;"),
            )
        by_id = {el.id: el for el in isa.elements}
        groups: dict[int, list[dict]] = {}
        for row in r["rows"]:
            if row["hypermodule_id"] is not None:
                groups.setdefault(row["hypermodule_id"], []).append(row)
        lines = []
        for hid in sorted(groups):
            rows = groups[hid]
            tiers = {}
            for row in rows:
                tiers[row["tier"]] = tiers.get(row["tier"], 0) + 1
            comp = " · ".join(f"{n} {tname}" for tname, n in sorted(tiers.items()))
            labels = ", ".join(
                (by_id[row["node"]].label if row["node"] in by_id
                 else row["node"])
                for row in rows)
            lines.append(ui.tags.li(
                f"HM{hid} ({len(rows)}): {comp} — {labels}"))
        return ui.div(
            ui.h5(t("metrics.hypermodules")),
            button,
            ui.p(ui.tags.strong(
                t("metrics.hypermodules_score",
                  n=r["n_hypermodules"],
                  score=f"{r['hypermodularity']:.2f}")),
                style="margin-top: 0.5rem;"),
            ui.tags.ul(*lines),
            ui.p(t("metrics.hypermodules_caption"),
                 class_="text-muted", style="font-size: 0.85rem;"),
        )

    @output(id="metrics_network")
    @render_pyvis_network(
        height="500px",
        show_toolbar=False, show_search=False,
        show_layout_switcher=False, show_export=False, show_status=False,
    )
    def _network():
        return _build_metrics_network(
            project_data.get().isa_data,
            chosen_metric(),
            metrics()[chosen_metric()],
        )
