"""PIMS Stakeholders — register UI + CRUD server. Port of pims_stakeholder_module.R.

A self-contained Shiny module: an add/edit form on the left, a render.data_frame
table on the right with selection-based Edit/Remove. All envelope writes go
through Project.replace() and emit isa_change so autosave fires.
SH2: a second sub-tab adds a matplotlib Power-Interest grid + quadrant summary.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from sespy.data_structure import Project, Stakeholder
from sespy.event_bus import EventBus
from sespy.i18n import Translator
from sespy.i18n import t as _t
from sespy.stakeholder_reports import (
    build_power_interest_png,
    build_stakeholder_workbook,
    build_summary_pdf,
)
from sespy.stakeholders import (
    COMMUNICATION_AUDIENCES,
    COMMUNICATION_FREQUENCIES,
    COMMUNICATION_TYPES,
    ENGAGEMENT_METHODS,
    ENGAGEMENT_STATUSES,
    add_communication,
    add_engagement,
    add_stakeholder,
    communication_rows,
    count_by,
    engagement_rows,
    level_num,
    remove_stakeholder,
    summarize_quadrants,
    update_stakeholder,
)
from sespy.stakeholders import (
    engagement_coverage as compute_engagement_coverage,
)
from sespy.stakeholders import (
    stakeholder_stats as compute_stakeholder_stats,
)

# code -> i18n label-key suffix maps (codes are stored; labels are rendered)
_TYPE_CODES = ["resource_users", "industry", "government", "ngo", "academic",
               "local_community", "indigenous", "other"]
_SECTOR_CODES = ["fisheries", "aquaculture", "tourism", "shipping", "energy",
                 "conservation", "research", "policy", "multiple", "other"]
_LEVEL_CODES = ["HIGH", "MEDIUM", "LOW"]
_ATTITUDE_CODES = ["supportive", "neutral", "resistant", "unknown"]
_ENGAGE_CODES = ["inform", "consult", "involve", "collaborate", "empower"]


def _choices(codes: list[str], group: str, translate) -> dict[str, str]:
    # "" front option so a field can be left blank; label via i18n key.
    out = {"": "—"}
    for c in codes:
        out[c] = translate(f"stakeholders.{group}.{c}")
    return out


def _code_label(code, group, known, translate):
    # Known code -> i18n label; blank -> "(unset)"; unknown -> verbatim.
    if not code:
        return translate("stakeholders.analysis.unset")
    if code in known:
        return translate(f"stakeholders.{group}.{code}")
    return code


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _register_panel() -> ui.Tag:
    """The existing SH1 register content, extracted verbatim (no behaviour change).

    Plain module-level function — NO @module.ui decorator — so the enclosing
    @module.ui on pims_stakeholders_ui applies namespacing at render time.
    """
    return ui.layout_columns(
        ui.card(
            ui.card_header(_t("stakeholders.add_heading")),
            ui.input_text("sh_name", _t("stakeholders.name")),
            ui.input_select("sh_type", _t("stakeholders.type"),
                            _choices(_TYPE_CODES, "type", _t)),
            ui.input_select("sh_sector", _t("stakeholders.sector"),
                            _choices(_SECTOR_CODES, "sector", _t)),
            ui.input_text("sh_contact", _t("stakeholders.contact")),
            ui.input_text_area("sh_interests", _t("stakeholders.interests")),
            ui.input_text_area("sh_role", _t("stakeholders.role")),
            ui.input_select("sh_power", _t("stakeholders.power"),
                            _choices(_LEVEL_CODES, "power", _t)),
            ui.input_select("sh_interest", _t("stakeholders.interest"),
                            _choices(_LEVEL_CODES, "interest", _t)),
            ui.input_select("sh_attitude", _t("stakeholders.attitude"),
                            _choices(_ATTITUDE_CODES, "attitude", _t)),
            ui.input_select("sh_engagement_level", _t("stakeholders.engagement_level"),
                            _choices(_ENGAGE_CODES, "engagement", _t)),
            ui.input_action_button("save_stakeholder", _t("stakeholders.save"),
                                   class_="btn btn-primary"),
            ui.input_action_button("cancel_edit", _t("stakeholders.cancel")),
        ),
        ui.card(
            ui.card_header(_t("stakeholders.title")),
            ui.output_data_frame("stakeholder_table"),
            ui.div(
                ui.input_action_button("edit_selected", _t("stakeholders.edit_selected")),
                ui.input_action_button(
                    "remove_selected", _t("stakeholders.remove_selected")),
            ),
        ),
        col_widths=[5, 7],
    )


def _grid_panel() -> ui.Tag:
    """Power-Interest grid tab content — plot + summary.

    Plain module-level function — NO @module.ui decorator.
    """
    return ui.div(
        ui.output_plot("power_interest_grid", height="520px"),
        ui.tags.hr(),
        ui.output_ui("grid_summary"),
    )


def _engagement_panel() -> ui.Tag:
    """Engagement Planning tab — add-form + activity log. Plain (un-decorated)."""
    status_choices = {
        c: _t(f"stakeholders.activity.status.{c}")
        for c in ENGAGEMENT_STATUSES
    }
    return ui.div(
        ui.h5(_t("stakeholders.activity.add_heading")),
        ui.layout_columns(
            ui.card(
                ui.input_select("eng_stakeholder", _t("stakeholders.activity.stakeholder"), {}),
                ui.input_select("eng_method", _t("stakeholders.activity.method"),
                                _choices(list(ENGAGEMENT_METHODS), "activity.method", _t)),
                ui.input_date("eng_date", _t("stakeholders.activity.date")),
                ui.input_text_area("eng_objectives", _t("stakeholders.activity.objectives")),
                ui.input_text_area("eng_outcomes", _t("stakeholders.activity.outcomes")),
                ui.input_select("eng_status", _t("stakeholders.activity.status"),
                                status_choices, selected="planned"),
                ui.input_text("eng_facilitator", _t("stakeholders.activity.facilitator")),
                ui.input_action_button("add_engagement", _t("stakeholders.activity.add"),
                                       class_="btn-success"),
            ),
            ui.card(
                ui.h5(_t("stakeholders.activity.log_heading")),
                ui.output_data_frame("engagement_table"),
            ),
            col_widths=[5, 7],
        ),
    )


def _communication_panel() -> ui.Tag:
    """Communication Plan tab — add-form + communications log. Plain (un-decorated)."""
    freq_choices = {
        c: _t(f"stakeholders.comm.frequency.{c}")
        for c in COMMUNICATION_FREQUENCIES
    }
    return ui.div(
        ui.h5(_t("stakeholders.comm.add_heading")),
        ui.layout_columns(
            ui.card(
                ui.input_select("comm_audience", _t("stakeholders.comm.audience"),
                                _choices(list(COMMUNICATION_AUDIENCES), "comm.audience", _t)),
                ui.input_select("comm_type", _t("stakeholders.comm.type"),
                                _choices(list(COMMUNICATION_TYPES), "comm.type", _t)),
                ui.input_date("comm_date", _t("stakeholders.comm.date")),
                ui.input_select("comm_frequency", _t("stakeholders.comm.frequency"),
                                freq_choices, selected="one_time"),
                ui.input_text_area("comm_message", _t("stakeholders.comm.message")),
                ui.input_text("comm_responsible", _t("stakeholders.comm.responsible")),
                ui.input_action_button("add_communication", _t("stakeholders.comm.add"),
                                       class_="btn-success"),
            ),
            ui.card(
                ui.h5(_t("stakeholders.comm.log_heading")),
                ui.output_data_frame("communication_table"),
            ),
            col_widths=[5, 7],
        ),
    )


def _analysis_panel() -> ui.Tag:
    """Analysis tab — statistics summary + distribution charts. Plain (un-decorated)."""
    return ui.div(
        ui.h5(_t("stakeholders.analysis.heading")),
        ui.layout_columns(
            ui.card(
                ui.h5(_t("stakeholders.analysis.stats_heading")),
                ui.output_ui("stakeholder_stats"),
            ),
            ui.card(ui.output_plot("engagement_coverage", height="300px")),
            col_widths=[5, 7],
        ),
        ui.layout_columns(
            ui.card(ui.output_plot("type_distribution", height="300px")),
            ui.card(ui.output_plot("sector_distribution", height="300px")),
            col_widths=[6, 6],
        ),
        ui.card(
            ui.h5(_t("stakeholders.analysis.export_heading")),
            ui.download_button("download_stakeholder_xlsx",
                               _t("stakeholders.analysis.export_excel")),
            ui.download_button("download_power_interest_png",
                               _t("stakeholders.analysis.export_png")),
            ui.download_button("download_summary_pdf",
                               _t("stakeholders.analysis.export_pdf")),
        ),
    )


@module.ui
def pims_stakeholders_ui() -> ui.Tag:
    # Static labels resolved via the module-level default translator (`_t`),
    # matching pims_project_ui's pattern.
    return ui.div(
        ui.h3(_t("stakeholders.title")),
        ui.navset_tab(
            ui.nav_panel(_t("stakeholders.tab_register"), _register_panel()),
            ui.nav_panel(_t("stakeholders.tab_grid"), _grid_panel()),
            ui.nav_panel(_t("stakeholders.tab_activity"), _engagement_panel()),
            ui.nav_panel(_t("stakeholders.tab_comm"), _communication_panel()),
            ui.nav_panel(_t("stakeholders.tab_analysis"), _analysis_panel()),
            id="stakeholder_tabs",
        ),
        class_="sespy-card",
    )


@module.server
def pims_stakeholders_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    T = translator
    tr = T.t if T is not None else _t

    editing_id: reactive.Value[str | None] = reactive.value(None)

    def _items() -> list[Stakeholder]:
        return project_data.get().stakeholders

    def _engagements():
        return project_data.get().engagements

    def _communications():
        return project_data.get().communications

    @output
    @render.data_frame
    def stakeholder_table():
        rows = [
            {"name": s.name, "type": s.stakeholder_type, "sector": s.sector,
             "power": s.power, "interest": s.interest,
             "attitude": s.attitude, "engagement": s.engagement_level}
            for s in _items()
        ]
        stub = [{"name": tr("stakeholders.empty"), "type": "", "sector": "",
                 "power": "", "interest": "", "attitude": "", "engagement": ""}]
        return render.DataGrid(pd.DataFrame(rows or stub),
                               selection_mode="row", height="320px")

    def _form_fields() -> dict:
        return {
            "name": input.sh_name().strip(),
            "stakeholder_type": input.sh_type(),
            "sector": input.sh_sector(),
            "contact": input.sh_contact().strip(),
            "interests": input.sh_interests().strip(),
            "role": input.sh_role().strip(),
            "power": input.sh_power(),
            "interest": input.sh_interest(),
            "attitude": input.sh_attitude(),
            "engagement_level": input.sh_engagement_level(),
        }

    def _clear_form() -> None:
        ui.update_text("sh_name", value="")
        ui.update_select("sh_type", selected="")
        ui.update_select("sh_sector", selected="")
        ui.update_text("sh_contact", value="")
        ui.update_text_area("sh_interests", value="")
        ui.update_text_area("sh_role", value="")
        ui.update_select("sh_power", selected="")
        ui.update_select("sh_interest", selected="")
        ui.update_select("sh_attitude", selected="")
        ui.update_select("sh_engagement_level", selected="")

    @reactive.effect
    @reactive.event(input.save_stakeholder, ignore_init=True)
    def _save():
        f = _form_fields()
        if not f["name"] or not f["stakeholder_type"]:
            ui.notification_show(tr("stakeholders.name_type_required"),
                                 type="warning", duration=3)
            return
        eid = editing_id.get()
        if eid is None:
            new_list = add_stakeholder(_items(), f, today=date.today().isoformat())
        else:
            new_list = update_stakeholder(_items(), eid, f)
        # Return to "add" mode: reset editing_id (which gates _repopulate) and
        # clear the form. _repopulate is @reactive.event(editing_id), so the
        # project_data.set below cannot re-fire it and re-fill the form.
        editing_id.set(None)
        project_data.set(project_data.get().replace(stakeholders=new_list))
        event_bus.emit_isa_change()
        _clear_form()

    @reactive.effect
    @reactive.event(input.edit_selected, ignore_init=True)
    def _edit():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        editing_id.set(items[sel["rows"][0]].id)

    # Repopulate the form ONLY when editing_id changes. Gated on editing_id via
    # @reactive.event so unrelated project_data writes (autosave, other modules)
    # cannot re-fire this and clobber the user's in-progress edits. Never
    # subscribe to the sh_* inputs here either. Mirrors pims_project.py:195.
    @reactive.effect
    @reactive.event(editing_id)
    def _repopulate():
        eid = editing_id.get()
        if eid is None:
            return
        match = next((s for s in _items() if s.id == eid), None)
        if match is None:
            return
        ui.update_text("sh_name", value=match.name)
        ui.update_select("sh_type", selected=match.stakeholder_type)
        ui.update_select("sh_sector", selected=match.sector)
        ui.update_text("sh_contact", value=match.contact)
        ui.update_text_area("sh_interests", value=match.interests)
        ui.update_text_area("sh_role", value=match.role)
        ui.update_select("sh_power", selected=match.power)
        ui.update_select("sh_interest", selected=match.interest)
        ui.update_select("sh_attitude", selected=match.attitude)
        ui.update_select("sh_engagement_level", selected=match.engagement_level)

    @reactive.effect
    @reactive.event(input.cancel_edit, ignore_init=True)
    def _cancel():
        editing_id.set(None)
        _clear_form()

    @reactive.effect
    @reactive.event(input.remove_selected, ignore_init=True)
    def _remove():
        sel = stakeholder_table.cell_selection()
        items = _items()
        if not sel or not sel.get("rows") or not items:
            ui.notification_show(tr("stakeholders.select_first"),
                                 type="warning", duration=3)
            return
        sid = items[sel["rows"][0]].id
        project_data.set(project_data.get().replace(
            stakeholders=remove_stakeholder(items, sid)))
        event_bus.emit_isa_change()
        if editing_id.get() == sid:
            editing_id.set(None)
            _clear_form()

    # ------------------------------------------------------------------
    # SH2: Power-Interest grid + quadrant summary
    # ------------------------------------------------------------------

    @output
    @render.plot
    def power_interest_grid():
        import matplotlib.pyplot as plt

        items = [s for s in _items()
                 if level_num(s.power) and level_num(s.interest)]
        fig, ax = plt.subplots()
        ax.set_xlim(0.5, 3.5)
        ax.set_ylim(0.5, 3.5)
        ax.set_xlabel(tr("stakeholders.grid.interest_axis"))
        ax.set_ylabel(tr("stakeholders.grid.power_axis"))
        ax.set_title(tr("stakeholders.grid.title"))
        ax.set_xticks([1, 2, 3])
        ax.set_yticks([1, 2, 3])
        tick_labels = [tr("stakeholders.power.LOW"),
                       tr("stakeholders.power.MEDIUM"),
                       tr("stakeholders.power.HIGH")]
        ax.set_xticklabels(tick_labels)
        ax.set_yticklabels(tick_labels)

        if not items:
            ax.text(2, 2, tr("stakeholders.grid.empty"),
                    ha="center", va="center", wrap=True)
            return fig

        # Quadrant background rects (interest=x, power=y); colors mirror R.
        ax.add_patch(plt.Rectangle((0.5, 0.5), 1.5, 1.5, color="#ececec", zorder=0))  # monitor
        ax.add_patch(plt.Rectangle((2, 0.5), 1.5, 1.5, color="#dceaf6", zorder=0))   # keep_informed
        ax.add_patch(plt.Rectangle((0.5, 2), 1.5, 1.5, color="#fbedcf", zorder=0))  # keep_satisfied
        ax.add_patch(plt.Rectangle((2, 2), 1.5, 1.5, color="#d9f0d9", zorder=0))      # key_players
        ax.axhline(2, color="gray", lw=1.5, ls="--")
        ax.axvline(2, color="gray", lw=1.5, ls="--")
        # Quadrant labels
        ax.text(2.75, 2.75, tr("stakeholders.grid.key_players"),
                ha="center", color="gray", fontweight="bold")
        ax.text(1.25, 2.75, tr("stakeholders.grid.keep_satisfied"),
                ha="center", color="gray")
        ax.text(2.75, 1.25, tr("stakeholders.grid.keep_informed"),
                ha="center", color="gray")
        ax.text(1.25, 1.25, tr("stakeholders.grid.monitor"),
                ha="center", color="gray")

        # Deterministic jitter (stable across re-renders): +/- 0.15 from index.
        for idx, s in enumerate(items):
            off = ((idx * 0.37) % 1 - 0.5) * 0.3
            x = level_num(s.interest) + off
            y = level_num(s.power) + off
            ax.scatter([x], [y], s=120, color="#2E86AB", zorder=3)
            ax.annotate(s.name, (x, y), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8)
        return fig

    @output
    @render.ui
    def grid_summary():
        summary = summarize_quadrants(_items())
        # total counts only the 4 PLOTTED quadrants; "unplotted" (missing
        # power/interest) is reported separately below.
        total = sum(len(summary[q]) for q in ("key_players", "keep_satisfied",
                                              "keep_informed", "monitor"))

        def _block(key: str) -> ui.Tag:
            names = summary[key]
            return ui.div(
                ui.tags.strong(f"{tr('stakeholders.grid.' + key)} ({len(names)})"),
                ui.p(tr(f"stakeholders.grid.{key}.strategy")),
                ui.p(", ".join(names) if names else "—"),
            )

        blocks = [_block(q) for q in ("key_players", "keep_satisfied",
                                      "keep_informed", "monitor")]
        unplotted = summary["unplotted"]
        footer = [ui.tags.hr(),
                  ui.p(f"{tr('stakeholders.grid.total')}: {total}")]
        if unplotted:
            footer.append(ui.p(f"{tr('stakeholders.grid.unplotted')}: "
                               + ", ".join(unplotted)))
        return ui.div(ui.h5(tr("stakeholders.grid.summary_heading")), *blocks, *footer)

    # ------------------------------------------------------------------
    # SH3: Engagement Planning — dropdown, add handler, activity log
    # ------------------------------------------------------------------

    @reactive.effect
    def _populate_eng_stakeholders():
        choices = {"": "—", **{s.id: s.name for s in _items()}}
        with reactive.isolate():
            val = input["eng_stakeholder"]
            current = (val() or "") if val.is_set() else ""
        selected = current if current in choices else ""
        ui.update_select("eng_stakeholder", choices=choices, selected=selected)

    @reactive.effect
    @reactive.event(input.add_engagement, ignore_init=True)
    def _add_engagement():
        sid = input.eng_stakeholder()
        method = input.eng_method()
        if not sid or not method or sid not in {s.id for s in _items()}:
            ui.notification_show(tr("stakeholders.activity.required"),
                                 type="warning", duration=3)
            return
        d = input.eng_date()
        fields_ = {
            "stakeholder_id": sid,
            "method": method,
            "date": d.isoformat() if d else "",
            "objectives": input.eng_objectives().strip(),
            "outcomes": input.eng_outcomes().strip(),
            "status": input.eng_status(),
            "facilitator": input.eng_facilitator().strip(),
        }
        new_list = add_engagement(_engagements(), fields_, today=date.today().isoformat())
        project_data.set(project_data.get().replace(engagements=new_list))
        event_bus.emit_isa_change()
        ui.update_text_area("eng_objectives", value="")
        ui.update_text_area("eng_outcomes", value="")
        ui.update_text("eng_facilitator", value="")

    @output
    @render.data_frame
    def engagement_table():
        rows = engagement_rows(_engagements(), _items(), translate=tr)
        stub = [{"stakeholder": tr("stakeholders.activity.empty"), "method": "",
                 "date": "", "objectives": "", "outcomes": "", "status": "",
                 "facilitator": ""}]
        return render.DataGrid(pd.DataFrame(rows or stub), height="320px")

    # ------------------------------------------------------------------
    # SH4: Communication Plan — add handler + communications log
    # ------------------------------------------------------------------

    @reactive.effect
    @reactive.event(input.add_communication, ignore_init=True)
    def _add_communication():
        audience = input.comm_audience()
        comm_type = input.comm_type()
        if not audience or not comm_type:
            ui.notification_show(tr("stakeholders.comm.required"),
                                 type="warning", duration=3)
            return
        d = input.comm_date()
        fields_ = {
            "audience": audience,
            "comm_type": comm_type,
            "date": d.isoformat() if d else "",
            "frequency": input.comm_frequency(),
            "message": input.comm_message().strip(),
            "responsible": input.comm_responsible().strip(),
        }
        new_list = add_communication(_communications(), fields_,
                                     today=date.today().isoformat())
        project_data.set(project_data.get().replace(communications=new_list))
        event_bus.emit_isa_change()
        ui.update_text_area("comm_message", value="")
        ui.update_text("comm_responsible", value="")

    @output
    @render.data_frame
    def communication_table():
        rows = communication_rows(_communications(), translate=tr)
        stub = [{"audience": tr("stakeholders.comm.empty"), "type": "", "date": "",
                 "frequency": "", "message": "", "responsible": ""}]
        return render.DataGrid(pd.DataFrame(rows or stub), height="320px")

    # ------------------------------------------------------------------
    # SH5: Analysis — statistics summary + distribution charts
    # ------------------------------------------------------------------

    @output
    @render.ui
    def stakeholder_stats():
        s = compute_stakeholder_stats(_items(), _engagements(), _communications())
        if s["total"] == 0:
            return ui.p(tr("stakeholders.analysis.empty"))
        keys = ("total", "types", "sectors", "high_power", "high_interest",
                "engagements", "communications")
        return ui.tags.ul(*[
            ui.tags.li(f"{tr('stakeholders.analysis.' + k)}: {s[k]}")
            for k in keys
        ])

    @output
    @render.plot
    def engagement_coverage():
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        items = _items()
        if not items:
            ax.text(0.5, 0.5, tr("stakeholders.analysis.add_stakeholders"),
                    ha="center", va="center")
            ax.axis("off")
            return fig
        cov = compute_engagement_coverage(items, _engagements())
        ax.bar([tr("stakeholders.analysis.engaged"),
                tr("stakeholders.analysis.not_engaged")],
               [cov, 100 - cov], color=["#2E86AB", "#CCCCCC"])
        ax.set_ylim(0, 100)
        ax.set_ylabel(tr("stakeholders.analysis.percentage"))
        ax.set_title(f"{tr('stakeholders.analysis.coverage_title')} ({round(cov, 1)}%)")
        return fig

    def _distribution_plot(field, known, group, title_key):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        items = _items()
        if not items:
            ax.text(0.5, 0.5, tr("stakeholders.analysis.add_stakeholders"),
                    ha="center", va="center")
            ax.axis("off")
            return fig
        counts = count_by(items, field)
        labels = [_code_label(c, group, known, tr) for c in counts]
        x = range(len(labels))
        ax.bar(x, list(counts.values()), color="#A23B72")
        ax.set_ylabel(tr("stakeholders.analysis.count"))
        ax.set_title(tr(title_key))
        ax.set_xticks(x, labels, rotation=45, ha="right")
        fig.tight_layout()
        return fig

    @output
    @render.plot
    def type_distribution():
        return _distribution_plot("stakeholder_type", _TYPE_CODES, "type",
                                  "stakeholders.analysis.by_type")

    @output
    @render.plot
    def sector_distribution():
        return _distribution_plot("sector", _SECTOR_CODES, "sector",
                                  "stakeholders.analysis.by_sector")

    # ------------------------------------------------------------------
    # SH6: Export downloads (xlsx / png / pdf)
    # ------------------------------------------------------------------

    @render.download_button(filename=lambda: f"stakeholders-{_stamp()}.xlsx")
    def download_stakeholder_xlsx():
        yield build_stakeholder_workbook(_items(), _engagements(), _communications())

    @render.download_button(filename=lambda: f"power-interest-{_stamp()}.png")
    def download_power_interest_png():
        yield build_power_interest_png(_items(), translate=tr)

    @render.download_button(filename=lambda: f"stakeholder-summary-{_stamp()}.pdf")
    def download_summary_pdf():
        stats = compute_stakeholder_stats(_items(), _engagements(), _communications())
        yield build_summary_pdf(project_data.get().metadata.name, stats, _items())
