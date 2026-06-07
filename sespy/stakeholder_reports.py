"""Pure byte-builders for the PIMS Stakeholders export downloads (SH6).

Each function returns file bytes and lazy-imports its heavy library inside the
body (no Shiny / no matplotlib-pyplot global state), so the module stays cheap to
import and the builders are unit-testable by magic bytes.
"""
from __future__ import annotations

from dataclasses import asdict, fields
from io import BytesIO

from sespy.data_structure import Communication, Engagement, Stakeholder
from sespy.stakeholders import level_num


def build_stakeholder_workbook(stakeholders, engagements, communications) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    specs = [
        ("Stakeholders", Stakeholder, stakeholders),
        ("Engagements", Engagement, engagements),
        ("Communications", Communication, communications),
    ]
    wb.active.title = specs[0][0]
    for i, (name, cls, rows) in enumerate(specs):
        ws = wb.active if i == 0 else wb.create_sheet(name)
        names = [f.name for f in fields(cls)]
        ws.append(names)
        for obj in rows:
            d = asdict(obj)
            ws.append([d.get(n, "") for n in names])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_power_interest_png(stakeholders, *, translate) -> bytes:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(8, 6), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.set_xlim(0.5, 3.5)
    ax.set_ylim(0.5, 3.5)
    ax.set_xlabel(translate("stakeholders.grid.interest_axis"))
    ax.set_ylabel(translate("stakeholders.grid.power_axis"))
    ax.set_title(translate("stakeholders.grid.title"))
    ax.axhline(2, color="gray", lw=1, ls="--")
    ax.axvline(2, color="gray", lw=1, ls="--")
    plotted = [s for s in stakeholders
               if level_num(s.power) and level_num(s.interest)]
    for idx, s in enumerate(plotted):
        off = ((idx * 0.37) % 1 - 0.5) * 0.3
        x = level_num(s.interest) + off   # x = interest
        y = level_num(s.power) + off      # y = power
        ax.scatter([x], [y], s=120, color="#2E86AB", zorder=3)
        ax.annotate(s.name, (x, y), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8)
    if not plotted:
        ax.text(2, 2, translate("stakeholders.grid.empty"),
                ha="center", va="center")
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    return buf.getvalue()


def build_summary_pdf(project_name, stats, stakeholders) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    title = f"Stakeholder summary — {escape(str(project_name))}"
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    stat_rows = [["Metric", "Value"]]
    for k in ("total", "types", "sectors", "high_power", "high_interest",
              "engagements", "communications"):
        stat_rows.append([k, str(stats.get(k, 0))])
    story.append(Table(stat_rows))
    story.append(Spacer(1, 18))
    sh_rows = [["Name", "Type", "Power", "Interest"]]
    if stakeholders:
        sh_rows += [[s.name, s.stakeholder_type, s.power, s.interest]
                    for s in stakeholders]
    else:
        sh_rows.append(["No stakeholders", "", "", ""])
    story.append(Table(sh_rows))
    doc.build(story)
    return buf.getvalue()
