"""Response register exports (P1b, spec §6.1): R's three-sheet Excel workbook and
R's effectiveness-vs-feasibility plot. openpyxl and matplotlib are imported lazily,
as in stakeholder_reports.py; nothing here imports Shiny."""
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, Callable

from .data_structure import ResponseRegister
from .response_register import (
    IMPACT_COLUMNS,
    MILESTONE_COLUMNS,
    RM_REGISTER_COLUMNS,
    display_value,
    ef_points,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

_RM = "modules.response.measures."
# (x, y, label-key suffix, colour) of the quadrant labels (response_module.R:833-836)
_QUADRANTS = (
    (2.5, 2.5, "high_priorityneffective_feasible", "darkgreen"),
    (1.25, 2.5, "effective_butndifficult", "darkorange"),
    (2.5, 1.25, "easy_butnlimited_impact", "darkorange"),
    (1.25, 1.25, "low_priority", "darkred"),
)


def _cells(rows: list[dict[str, Any]], columns: tuple[str, ...],
           tr: Callable[[str], str]) -> list[list[Any]]:
    # Cost stays a number (None leaves the cell blank), and every other value is
    # written as the page shows it.
    return [[r.get(c) if c == "Cost" else display_value(c, r.get(c), tr) for c in columns]
            for r in rows]


def build_response_workbook(reg: ResponseRegister, tr: Callable[[str], str]) -> bytes:
    """R build_response_excel (response_module.R:1178-1196, called at :869-880):
    sheets Response_Measures, Impact_Matrix and Implementation with R's column
    names as headers. Measures are translated as R's rm_translate_for_display,
    impacts and milestones too, because SESPy stores codes where R stores the
    labels it exports (spec §6.1)."""
    from openpyxl import Workbook

    wb = Workbook()
    sheets = (("Response_Measures", RM_REGISTER_COLUMNS, reg.measures),
              ("Impact_Matrix", IMPACT_COLUMNS, reg.impacts),
              ("Implementation", MILESTONE_COLUMNS, reg.milestones))
    for i, (name, columns, rows) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet(name)
        ws.title = name
        ws.append(list(columns))
        for cells in _cells(rows, columns, tr):
            ws.append(cells)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_ef_figure(measures: list[dict[str, Any]], tr: Callable[[str], str]) -> Figure:
    """R's effectiveness-vs-feasibility plot (response_module.R:796-837): the
    measures rated HIGH/MEDIUM/LOW on both (ef_points), x = feasibility,
    y = effectiveness, Low/Medium/High ticks, dashed lines at 2, the quadrant
    labels and each point's ID above it. With no such measure, empty axes
    titled "Add effectiveness and feasibility ratings" (:811-814)."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7, 5.5), layout="constrained")
    ax = fig.subplots()
    points = ef_points(measures)
    if not points:
        ax.set_title(tr(_RM + "add_effectiveness_and_feasibility_ratings"))
        return fig
    ax.scatter([x for _, x, _ in points], [y for _, _, y in points],
               s=150, color="#457B9D", zorder=3)                      # pch 19, cex 2
    ax.set_xlim(0.5, 3.5)
    ax.set_ylim(0.5, 3.5)
    ticks = [tr(_RM + level) for level in ("low", "medium", "high")]
    ax.set_xticks([1, 2, 3], labels=ticks)
    ax.set_yticks([1, 2, 3], labels=ticks)
    ax.set_xlabel(tr(_RM + "feasibility"))
    ax.set_ylabel(tr(_RM + "effectiveness"))
    ax.set_title(tr(_RM + "response_measure_prioritization_matrix"))
    ax.axhline(2, color="gray", linestyle="--")
    ax.axvline(2, color="gray", linestyle="--")
    for mid, x, y in points:                                  # R text(pos = 3), above
        ax.annotate(mid, (x, y), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=7)
    for x, y, key, colour in _QUADRANTS:
        ax.text(x, y, tr(_RM + key), ha="center", va="center", fontsize=9, color=colour)
    return fig
