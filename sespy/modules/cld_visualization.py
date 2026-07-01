"""CLD Visualization module — pyvis.shiny edition.

Switched from a hand-rolled vis-network bridge to the official Shiny
integration that ships with the user's pyvis 4.2 fork. Benefits:
  - Per-node `font.size` is honored unambiguously (no network-level shadow).
  - vis-network bundle is served locally as an HTMLDependency, not from CDN.
  - PyVisNetworkController provides fit/select/move-to imperatively.
  - Toolbar UI (search, layout toggle, export) is built in and selectively
    enabled — we keep it light here, but it's available for future expansion.

The trade-off vs. the bridge is that `@render_pyvis_network` rebuilds the
Network on every reactive change. For ~17 nodes this is unnoticeable; the
fork also exposes a diff-based `network_update_data` path for larger graphs.
"""

from __future__ import annotations

from collections.abc import Iterable

from pyvis.network import Network
from pyvis.shiny import (
    PyVisNetworkController,
    output_pyvis_network,
    render_pyvis_network,
)
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import (
    DAPSIWRM_ELEMENTS,
    DAPSIWRM_FONT_SIZE,
    DAPSIWRM_LABEL_WIDTH,
    DAPSIWRM_LEVEL,
    DAPSIWRM_NODE_SIZE,
    DEFAULT_GROUP_COLOR,
    DEFAULT_GROUP_SHAPE,
    EDGE_COLORS,
    ELEMENT_COLORS,
    ELEMENT_SHAPES,
)
from ..data_structure import IsaData, Project, filter_elements
from ..event_bus import EventBus
from ..i18n import t
from ..network import connection_disagreement, delay_edge_kwargs


@module.ui
def cld_viz_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("card.cld")),
        _cld_body(),
        # `sespy-card-canvas` keys the `transform: none !important` guard in
        # sespy-skin.css — a card hover transform on any vis-network ancestor
        # breaks vis.js tooltip positioning (see R bs4dash-custom.css:452).
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


def _cld_body() -> ui.Tag:
    return ui.layout_sidebar(
        ui.sidebar(
            ui.h5(t("cld.display")),
            ui.input_radio_buttons(
                "layout",
                t("cld.layout"),
                {
                    "hierarchical": t("cld.layout.hierarchical"),
                    "physics":      t("cld.layout.physics"),
                },
                selected="hierarchical",
            ),
            ui.input_slider(
                "node_size_scale",
                t("cld.node_size"),
                min=0.5, max=4.0, value=1.0, step=0.1,
            ),
            ui.input_slider(
                "font_size_scale",
                t("cld.label_size"),
                min=0.5, max=4.0, value=1.0, step=0.1,
            ),
            ui.panel_conditional(
                "input.layout == 'hierarchical'",
                ui.input_select(
                    "direction",
                    t("cld.direction"),
                    {
                        "DU": t("cld.direction.DU"),
                        "UD": t("cld.direction.UD"),
                        "LR": t("cld.direction.LR"),
                        "RL": t("cld.direction.RL"),
                    },
                    selected="DU",
                ),
                ui.input_slider(
                    "level_separation",
                    t("cld.row_spacing"),
                    min=40, max=400, value=90, step=10,
                ),
                ui.input_slider(
                    "node_spacing",
                    t("cld.node_spacing"),
                    min=100, max=2000, value=200, step=10,
                ),
            ),
            ui.tags.hr(),
            ui.h5(t("cld.element_types")),
            ui.input_checkbox_group(
                "element_types",
                None,
                {t: t for t in DAPSIWRM_ELEMENTS},
                selected=list(DAPSIWRM_ELEMENTS),
            ),
            ui.tags.hr(),
            ui.input_action_button("fit", t("cld.fit"), class_="btn btn-sm btn-secondary"),
            ui.tags.hr(),
            # Stats live in the sidebar — they're persistent context, not
            # primary content, so they belong here rather than above the canvas.
            ui.div(
                ui.div(ui.output_text("stat_nodes"), class_="cld-stat"),
                ui.div(ui.output_text("stat_edges"), class_="cld-stat"),
                ui.div(ui.output_text("stat_density"), class_="cld-stat"),
                class_="cld-stats cld-stats-sidebar",
            ),
            width=320,
        ),
        ui.div(
            output_pyvis_network(
                "network",
                height="650px",
                show_toolbar=False,    # we provide our own controls in the sidebar
                show_search=False,
                show_layout_switcher=False,
                show_export=True,      # keep export — it's free polish
                show_status=False,
            ),
            ui.tags.small(t("cld.delay_legend"), class_="text-muted"),
            ui.tags.small(t("cld.contested_legend"), class_="text-muted"),
            ui.tags.p(
                ui.output_text("selected_label"),
                style="margin-top: 12px; color: #555;",
            ),
            class_="cld-canvas-wrapper",
        ),
    )


def _build_pyvis_network(
    isa: IsaData,
    *,
    layout_kind: str,
    direction: str,
    level_sep: int,
    node_sp: int,
    size_scale: float,
    font_scale: float,
) -> Network:
    """Construct a fully-configured pyvis Network for the current view.

    Critical: pyvis's `Network.set_options()` *replaces* `self.options`
    instead of merging — calling it after `Network(layout=...)` silently
    wipes the hierarchical config. Build the full options dict here and
    call `set_options` exactly once. This was the cause of the rendered
    network falling back to physics-based layout despite us asking for
    hierarchical.
    """
    options: dict = {
        "interaction": {"hover": True, "tooltipDelay": 150},
    }

    if layout_kind == "hierarchical":
        options["layout"] = {
            "hierarchical": {
                "enabled": True,
                "direction": direction,
                "levelSeparation": level_sep,
                "nodeSpacing": node_sp,
                "treeSpacing": node_sp,
                "blockShifting": True,
                "edgeMinimization": True,
                "parentCentralization": True,
                "sortMethod": "directed",
            }
        }
        # Match the R app: apply_hierarchical_layout doesn't call visPhysics —
        # physics fights the hierarchical engine, pulling nodes off rows.
        options["physics"] = {"enabled": False}
    else:
        # apply_physics_layout from functions/visnetwork_helpers.R:1000
        options["physics"] = {
            "enabled": True,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -50,
                "centralGravity": 0.01,
                "springLength": 100,
                "springConstant": 0.08,
            },
            "stabilization": {
                "enabled": True,
                "iterations": 1000,
                "updateInterval": 25,
            },
        }

    net = Network(
        height="650px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#2c3e50",
        cdn_resources="local",
    )
    net.set_options(options)

    label_max = max(60, int(DAPSIWRM_LABEL_WIDTH * size_scale))

    for el in isa.elements:
        base_size = DAPSIWRM_NODE_SIZE.get(el.type, 80)
        base_font = DAPSIWRM_FONT_SIZE.get(el.type, 24)
        net.add_node(
            el.id,
            label=el.label,
            title=f"{el.type}: {el.label}",
            color=ELEMENT_COLORS.get(el.type, DEFAULT_GROUP_COLOR),
            shape=ELEMENT_SHAPES.get(el.type, DEFAULT_GROUP_SHAPE),
            level=DAPSIWRM_LEVEL.get(el.type, 25),
            size=max(15, int(base_size * size_scale)),
            font={"size": max(8, int(base_font * font_scale)), "multi": "html"},
            widthConstraint={"maximum": label_max},
            group=el.type,
        )

    for c in isa.connections:
        kwargs = delay_edge_kwargs(c)          # fresh dict per call: {"title": .., "dashes": ..}
        label = c.polarity
        width = 2
        if connection_disagreement(c)["polarity_contested"]:
            label = f"{c.polarity} ⚠"
            width = 6
            kwargs["title"] = f'{kwargs["title"]} · ⚠ {t("cld.contested_sign")}'
        net.add_edge(
            c.source,
            c.target,
            label=label,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=width,
            **kwargs,
        )

    return net


def cld_keep_types(isa: IsaData, selected: Iterable[str]) -> set[str]:
    """Element types to render: the user-selected DAPSIWRM types PLUS any type
    present in the data that the DAPSIWRM checkbox filter doesn't even offer
    (untyped "" or custom QSEM / food-web themes like 'OWFs', 'Policy').

    The `element_types` filter only lists DAPSIWRM types, so it can only ever
    HIDE DAPSIWRM-typed elements. Without this, importing a non-DAPSIWRM model
    (whose elements are mostly type="") filters every node out and the diagram
    renders empty — see the QSEM absent-theme trap. Keeping the unofferable
    types unconditionally means such a model renders in full while DAPSIWRM
    projects keep their per-type toggles unchanged.
    """
    unofferable = {e.type for e in isa.elements} - set(DAPSIWRM_ELEMENTS)
    return set(selected) | unofferable


@module.server
def cld_viz_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
) -> None:
    @reactive.calc
    def filtered() -> IsaData:
        event_bus.cld_update.get()
        isa = project_data.get().isa_data
        return filter_elements(isa, cld_keep_types(isa, input.element_types() or ()))

    # The pyvis renderer fires whenever any reactive input it reads changes —
    # we read every layout/spacing/scale slider so the network rebuilds when
    # the user drags anything.
    @output(id="network")
    @render_pyvis_network(height="650px", show_toolbar=False, show_search=False,
                          show_layout_switcher=False, show_export=True, show_status=False)
    def _network():
        try:
            size_scale = float(input.node_size_scale() or 1.0)
            font_scale = float(input.font_size_scale() or 1.0)
            level_sep = int(input.level_separation() or 90)
            node_sp = int(input.node_spacing() or 200)
            direction = input.direction() or "DU"
        except Exception:
            size_scale = font_scale = 1.0
            level_sep, node_sp, direction = 90, 200, "DU"

        return _build_pyvis_network(
            filtered(),
            layout_kind=input.layout() or "hierarchical",
            direction=direction,
            level_sep=level_sep,
            node_sp=node_sp,
            size_scale=size_scale,
            font_scale=font_scale,
        )

    # Fit-to-view via the controller (sends a custom message instead of
    # re-rendering the network).
    controller = PyVisNetworkController(session.ns("network"), session)

    @reactive.effect
    @reactive.event(input.fit)
    def _fit():
        controller.fit()

    @output
    @render.text
    def stat_nodes():
        return f"Nodes\n{filtered().element_count()}"

    @output
    @render.text
    def stat_edges():
        return f"Edges\n{filtered().connection_count()}"

    @output
    @render.text
    def stat_density():
        n = filtered().element_count()
        m = filtered().connection_count()
        density = m / (n * (n - 1)) if n > 1 else 0.0
        return f"Density\n{density:.4f}"

    @output
    @render.text
    def selected_label():
        # pyvis.shiny pushes selectNode events as input.network_selectNode
        # (a dict with nodeId / nodeData / etc.).
        try:
            event = input.network_selectNode()
        except Exception:
            event = None
        if not event:
            return "Click a node to inspect."
        node_id = event.get("nodeId") if isinstance(event, dict) else None
        return f"Selected: {node_id}" if node_id else "Click a node to inspect."
