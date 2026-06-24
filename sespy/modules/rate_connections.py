"""Rate Connections — QSEM-C2 multi-rater elicitation UI.

Stakeholders (raters) record their own rating (polarity/strength/confidence/
delay) of an existing connection. Each save upserts one Rating per
(rater, connection) and recomputes the consensus via network.upsert_rating,
then writes through project_data so every analysis sees the new consensus.
Reuses the PIMS Stakeholders register as the rater list. No structural
editing here (that lives in Edit Data).
"""
from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import CONNECTION_POLARITY_LABELS, DELAY_LEVELS
from ..data_structure import IsaData, Rating
from ..event_bus import EventBus
from ..i18n import Translator, t
from .. import network

_STRENGTHS = ("weak", "medium", "strong")


@module.ui
def rate_connections_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("rate.title")),
        ui.layout_sidebar(
            ui.sidebar(ui.output_ui("rater_picker"), width=260),
            ui.div(
                ui.output_data_frame("connections_table"),
                ui.tags.hr(),
                ui.output_ui("rating_editor"),
                ui.tags.hr(),
                ui.h5(t("rate.current_ratings")),
                ui.output_ui("current_ratings"),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def rate_connections_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data,
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    sel_idx: reactive.Value = reactive.value(None)

    @output
    @render.ui
    def rater_picker():
        shs = project_data.get().stakeholders
        if not shs:
            return ui.tags.p(t("rate.no_stakeholders"), class_="text-muted")
        return ui.input_select("rater", t("rate.rating_as"), {s.id: s.name for s in shs})

    @output
    @render.data_frame
    def connections_table():
        import pandas as pd
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        try:
            rater = input.rater()
        except Exception:
            rater = None
        by_id = {el.id: el.label for el in isa.elements}
        cols = ["source", "target", "polarity", "strength", "confidence", "delay", "#ratings", "mine"]
        rows = [{
            "source": f"{c.source} · {by_id.get(c.source, '?')}",
            "target": f"{c.target} · {by_id.get(c.target, '?')}",
            "polarity": c.polarity,
            "strength": c.strength,
            "confidence": c.confidence,
            "delay": c.delay,
            "#ratings": len(c.ratings),
            "mine": "✓" if rater and any(r.rater_id == rater for r in c.ratings) else "—",
        } for c in isa.connections]
        return render.DataGrid(
            pd.DataFrame(rows or [{k: "" for k in cols}]),
            selection_mode="row", height="260px",
        )

    @reactive.effect
    def _track_selection():
        sel = connections_table.cell_selection()
        if sel and sel.get("rows"):
            sel_idx.set(sel["rows"][0])

    @reactive.effect
    @reactive.event(input.rater)
    def _reset_selection_on_rater():
        sel_idx.set(None)

    def _selected():
        """(index, connection) for the cached selection, or (None, None).
        Bounds-guards the empty-project stub row."""
        idx = sel_idx.get()
        if idx is None:
            return None, None
        conns = project_data.get().isa_data.connections
        if idx >= len(conns):
            return None, None
        return idx, conns[idx]

    @output
    @render.ui
    def rating_editor():
        event_bus.isa_change.get()
        try:
            rater = input.rater()
        except Exception:
            rater = None
        _, conn = _selected()
        if not rater or conn is None:
            return ui.tags.p(t("rate.select_connection"), class_="text-muted")
        ex = next((r for r in conn.ratings if r.rater_id == rater), None)
        return ui.div(
            ui.h5(t("rate.your_rating")),
            ui.input_radio_buttons("ed_polarity", t("rate.polarity"),
                                   CONNECTION_POLARITY_LABELS,
                                   selected=ex.polarity if ex else "+", inline=True),
            ui.input_select("ed_strength", t("rate.strength"),
                            {s: t(f"strength.{s}") for s in _STRENGTHS},
                            selected=ex.strength if ex else "medium"),
            ui.input_slider("ed_confidence", t("rate.confidence"), min=1, max=5,
                            value=ex.confidence if ex else 3, step=1),
            ui.input_select("ed_delay", t("rate.delay"),
                            {lvl: t(f"delay.{lvl}") for lvl in DELAY_LEVELS},
                            selected=ex.delay if ex else "immediate"),
            ui.input_action_button("save_rating", t("rate.save"), class_="btn btn-primary"),
            ui.input_action_button("remove_rating", t("rate.remove"),
                                   class_="btn btn-outline-danger", style="margin-left:8px;"),
        )

    @output
    @render.ui
    def current_ratings():
        event_bus.isa_change.get()
        _, conn = _selected()
        if conn is None or not conn.ratings:
            return ui.tags.p("—", class_="text-muted")
        name_by_id = {s.id: s.name for s in project_data.get().stakeholders}
        return ui.tags.ul(*[
            ui.tags.li(f"{name_by_id.get(r.rater_id, r.rater_id)}: "
                       f"{r.polarity}/{r.strength}/{r.confidence}/{r.delay}")
            for r in conn.ratings
        ])

    def _persist(new_conns):
        current = project_data.get()
        project_data.set(current.replace(isa_data=IsaData(
            elements=current.isa_data.elements, connections=new_conns)))
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()

    def _rater_or_warn():
        try:
            rater = input.rater()
        except Exception:
            rater = None
        if not rater:
            ui.notification_show(t("rate.no_stakeholders"), type="warning", duration=3)
        return rater

    @reactive.effect
    @reactive.event(input.save_rating)
    def _save():
        rater = _rater_or_warn()
        if not rater:
            return
        idx, conn = _selected()
        if conn is None:
            ui.notification_show(t("rate.select_connection"), type="warning", duration=3)
            return
        rating = Rating(rater_id=rater,
                        strength=input.ed_strength() or "medium",
                        confidence=int(input.ed_confidence() or 3),
                        polarity=input.ed_polarity() or "+",
                        delay=input.ed_delay() or "immediate")
        conns = list(project_data.get().isa_data.connections)
        conns[idx] = network.upsert_rating(conn, rating)
        _persist(conns)
        ui.notification_show(t("rate.saved"), type="message", duration=2)

    @reactive.effect
    @reactive.event(input.remove_rating)
    def _remove():
        rater = _rater_or_warn()
        if not rater:
            return
        idx, conn = _selected()
        if conn is None:
            ui.notification_show(t("rate.select_connection"), type="warning", duration=3)
            return
        if not any(r.rater_id == rater for r in conn.ratings):
            ui.notification_show(t("rate.nothing_to_remove"), type="warning", duration=3)
            return
        conns = list(project_data.get().isa_data.connections)
        conns[idx] = network.remove_rating(conn, rater)
        _persist(conns)
        ui.notification_show(t("rate.removed"), type="message", duration=2)
