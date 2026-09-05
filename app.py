"""Top-level Shiny for Python app — port of the MarineSABRES SES Toolbox.

Uses `sespy.dashboard.dashboard_page` as the visual shell, which mirrors the
R app's bs4Dash layout: dark left sidebar (brand + nav + quick-actions),
main content area with cards, footer.

Two modules wired up so the cross-module reactive contract is exercised:
  * cld_visualization — vis-network canvas with the full CLD
  * analysis_loops    — loop detection + per-loop visualization (pyvis)
Both share `project_data` (source of truth) and `event_bus` (signal channel).
"""

from __future__ import annotations

from pathlib import Path

from shiny import App, Inputs, Outputs, Session, reactive, ui

from sespy import data_structure
from sespy import i18n as _i18n
from sespy.dashboard import (
    NavItem,
    StepperItem,
    dashboard_page,
    dashboard_server,
    workflow_stepper_slot,
)
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, detect_initial_language, load_translations
from sespy.modules.ai_isa_wizard import ai_isa_wizard_server, ai_isa_wizard_ui
from sespy.modules.analysis_boolean import (
    analysis_boolean_server,
    analysis_boolean_ui,
)
from sespy.modules.analysis_bot import analysis_bot_server, analysis_bot_ui
from sespy.modules.analysis_intervention import (
    analysis_intervention_server,
    analysis_intervention_ui,
)
from sespy.modules.analysis_leverage import analysis_leverage_server, analysis_leverage_ui
from sespy.modules.analysis_loops import analysis_loops_server, analysis_loops_ui
from sespy.modules.analysis_metrics import analysis_metrics_server, analysis_metrics_ui
from sespy.modules.analysis_quadrant import analysis_quadrant_server, analysis_quadrant_ui
from sespy.modules.analysis_simplify import (
    analysis_simplify_server,
    analysis_simplify_ui,
)
from sespy.modules.analysis_simulation import (
    analysis_simulation_server,
    analysis_simulation_ui,
)
from sespy.modules.cld_visualization import cld_viz_server, cld_viz_ui
from sespy.modules.import_data import import_data_server, import_data_ui
from sespy.modules.isa_data_entry import isa_data_entry_server, isa_data_entry_ui
from sespy.modules.pims_project import pims_project_server, pims_project_ui
from sespy.modules.pims_stakeholders import (
    pims_stakeholders_server,
    pims_stakeholders_ui,
)
from sespy.modules.project_io import quick_actions_server, quick_actions_ui
from sespy.modules.rate_connections import rate_connections_server, rate_connections_ui
from sespy.modules.recent_projects import recent_projects_server, recent_projects_ui
from sespy.modules.report_export import report_export_server, report_export_ui
from sespy.modules.templates import templates_server, templates_ui
from sespy.modules.topbar_actions import help_panel_ui, topbar_actions_server, topbar_actions_ui

ROOT = Path(__file__).parent
WWW = ROOT / "www"
# The About modal renders docs/MANUAL.md, whose images are relative
# docs/screenshots/*.png paths (so they also work on GitHub). Mount that
# directory at the same relative URL so the paths resolve in-app too.
STATIC_ASSETS = {"/": WWW, "/docs/screenshots": ROOT / "docs" / "screenshots"}
SAMPLE = ROOT / "data" / "sample_ses.json"
TRANSLATIONS_DIR = ROOT / "sespy" / "translations"

# Translator is created at module-import time so the same instance feeds
# UI construction (static labels) AND server-side reactive labels.
T = Translator(translations=load_translations(TRANSLATIONS_DIR))
_i18n.set_default(T)  # so modules can `from sespy.i18n import t` and use `t(...)` directly

# Nav items grow as we port more modules. The shape is intentionally
# tree-friendly so submenus (PIMS, SES Creation in the R app) can be added
# later without changing the dashboard signature.
NAV: list[NavItem] = [
    NavItem(id="pims",     icon="clipboard-list",  label="Project Setup",     label_key="nav.pims"),
    NavItem(id="stakeholders", icon="users", label="Stakeholders", label_key="nav.stakeholders"),
    NavItem(id="templates", icon="layer-group",    label="Templates",         label_key="nav.templates"),
    NavItem(id="wizard",   icon="wand-magic-sparkles", label="SES Wizard",  label_key="nav.wizard"),
    NavItem(id="entry",    icon="pen-to-square",   label="Edit Data",         label_key="nav.entry"),
    NavItem(id="rate",     icon="user-pen",        label="Rate Connections",  label_key="nav.rate"),
    NavItem(id="cld",      icon="diagram-project", label="CLD Visualization", label_key="nav.cld"),
    NavItem(id="loops",    icon="rotate-right",    label="Loop Analysis",     label_key="nav.loops"),
    NavItem(id="metrics",  icon="chart-line",      label="Network Metrics",   label_key="nav.metrics"),
    NavItem(id="leverage", icon="bullseye",        label="Leverage Points",   label_key="nav.leverage"),
    NavItem(id="quadrant", icon="table-cells-large", label="Factor Quadrant", label_key="nav.quadrant"),
    NavItem(id="boolean",     icon="square-root-variable", label="Boolean & Laplacian", label_key="nav.boolean"),
    NavItem(id="simulation",  icon="wave-square",         label="Dynamic Simulation",  label_key="nav.simulation"),
    NavItem(id="bot",         icon="chart-area",           label="Behaviour Over Time", label_key="nav.bot"),
    NavItem(id="intervention", icon="hand-pointer", label="Intervention",     label_key="nav.intervention"),
    NavItem(id="simplify",  icon="scissors",        label="Simplify Network",  label_key="nav.simplify"),
    NavItem(id="import",   icon="file-excel",      label="Import Data",       label_key="nav.import"),
    NavItem(id="recent",   icon="folder-open",     label="Recent Projects",   label_key="nav.recent"),
    NavItem(id="report",   icon="file-pdf",        label="Export Report",     label_key="nav.report"),
]

# DAPSI workflow stages — same five steps as the R app's workflow_stepper.R.
# Modules currently cover the middle steps (Visualize/Analyze); the others
# are placeholders showing where future modules slot into the broader flow.
STEPPER: list[StepperItem] = [
    StepperItem(id="setup",     label="Setup",       label_key="stepper.setup"),
    StepperItem(id="start",     label="Get Started", label_key="stepper.start"),
    StepperItem(id="create",    label="Create SES",  label_key="stepper.create"),
    StepperItem(id="visualize", label="Visualize",   label_key="stepper.visualize"),
    StepperItem(id="analyze",   label="Analyze",     label_key="stepper.analyze"),
    StepperItem(id="report",    label="Report",      label_key="stepper.report"),
]

# Map a nav id to its stepper stage so the highlight follows panel changes.
NAV_TO_STEP = {
    "pims": "setup",
    "stakeholders": "setup",
    "templates": "create",
    "wizard": "create",
    "entry": "create",
    "rate": "create",
    "cld": "visualize", "loops": "analyze", "metrics": "analyze",
    "leverage": "analyze", "quadrant": "analyze", "boolean": "analyze", "simulation": "analyze",
    "bot": "analyze",
    "intervention": "analyze", "simplify": "analyze",
    "import": "create",
    "recent": "start", "report": "report",
}

PANELS = (
    ui.nav_panel("Project Setup",     pims_project_ui("pims"),                     value="pims"),
    ui.nav_panel("Stakeholders", pims_stakeholders_ui("stakeholders"), value="stakeholders"),
    ui.nav_panel("Templates",         templates_ui("templates"),                   value="templates"),
    ui.nav_panel("SES Wizard",        ai_isa_wizard_ui("wizard"),                 value="wizard"),
    ui.nav_panel("Edit Data",         isa_data_entry_ui("entry"),                  value="entry"),
    ui.nav_panel("Rate Connections", rate_connections_ui("rate"), value="rate"),
    ui.nav_panel("CLD Visualization", cld_viz_ui("cld"),                          value="cld"),
    ui.nav_panel("Loop Analysis",     analysis_loops_ui("loops"),                  value="loops"),
    ui.nav_panel("Network Metrics",   analysis_metrics_ui("metrics"),              value="metrics"),
    ui.nav_panel("Leverage Points",   analysis_leverage_ui("leverage"),            value="leverage"),
    ui.nav_panel("Factor Quadrant",   analysis_quadrant_ui("quadrant"),            value="quadrant"),
    ui.nav_panel("Boolean & Laplacian", analysis_boolean_ui("boolean"),            value="boolean"),
    ui.nav_panel("Dynamic Simulation",  analysis_simulation_ui("simulation"),      value="simulation"),
    ui.nav_panel("Behaviour Over Time", analysis_bot_ui("bot"),                    value="bot"),
    ui.nav_panel("Intervention",      analysis_intervention_ui("intervention"),    value="intervention"),
    ui.nav_panel("Simplify Network",  analysis_simplify_ui("simplify"),            value="simplify"),
    ui.nav_panel("Import Data",       import_data_ui("import"),                    value="import"),
    ui.nav_panel("Recent Projects",   recent_projects_ui("recent"),                value="recent"),
    ui.nav_panel("Export Report",     report_export_ui("report"),                  value="report"),
)

app_ui = dashboard_page(
    *PANELS,
    nav_items=NAV,
    initial="cld",
    title=T.t("ui.app.title"),
    brand_title=T.t("ui.brand.title"),
    pre_panel_slot=ui.TagList(workflow_stepper_slot(), help_panel_ui(T)),
    header_actions=topbar_actions_ui(T),
    quick_actions=quick_actions_ui(T),
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    translator = _i18n.get_default()
    if translator is not None:
        # `clientdata` is a reactive read, so it needs a context — the server
        # body has none. Isolate rather than defer to an effect: the language
        # must be set before the module servers below register their outputs.
        with reactive.isolate():
            initial_lang = detect_initial_language(session.clientdata.url_search())
        translator.set_language(initial_lang)

    project_data = reactive.value(
        data_structure.Project.from_isa(data_structure.load_sample(SAMPLE))
    )
    event_bus = create_event_bus()
    current_theme = reactive.value("light-marine")
    autosave_enabled = reactive.value(True)

    active_panel = dashboard_server(
        input, output, session,
        nav_items=NAV,
        initial="cld",
        stepper_steps=STEPPER,
        nav_to_step=NAV_TO_STEP,
        translator=translator,
    )
    quick_actions_server(
        input, output, session,
        project_data=project_data,
        event_bus=event_bus,
        sample_path=SAMPLE,
        translator=translator,
        autosave_enabled=autosave_enabled,
    )
    topbar_actions_server(
        input, output, session,
        translator=translator,
        current_theme=current_theme,
        autosave_enabled=autosave_enabled,
        active_panel=active_panel,
        nav_items=NAV,
    )

    pims_project_server(
        "pims",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    pims_stakeholders_server(
        "stakeholders",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )

    templates_server(
        "templates",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    ai_isa_wizard_server(
        "wizard",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    isa_data_entry_server(
        "entry",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    rate_connections_server(
        "rate",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    cld_viz_server("cld", project_data=project_data, event_bus=event_bus)
    analysis_loops_server("loops", project_data=project_data, event_bus=event_bus)
    analysis_metrics_server(
        "metrics",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_leverage_server(
        "leverage",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_quadrant_server(
        "quadrant",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_boolean_server(
        "boolean",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_simulation_server(
        "simulation",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_bot_server(
        "bot",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_intervention_server(
        "intervention",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    analysis_simplify_server(
        "simplify",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    import_data_server(
        "import",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    recent_projects_server(
        "recent",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )
    report_export_server(
        "report",
        project_data=project_data,
        event_bus=event_bus,
        translator=translator,
    )


app = App(
    app_ui,
    server,
    static_assets={k: str(v) for k, v in STATIC_ASSETS.items()},
)
