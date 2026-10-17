"""P1a — "Save project info" keeps the schema-v7 metadata fields (spec §4).

pims_project_server used to rebuild ProjectMetadata field by field, which
would drop origin, r_template_version and min_sespy_version on every save.
"""
from __future__ import annotations

from shiny import reactive
from shiny.testserver import test_server

from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import create_event_bus
from sespy.modules.pims_project import pims_project_server

FORM = dict(project_name="Renamed", da_site="", focal_issue="Eutrophication",
            definition_statement="", temporal_scale="Yearly",
            spatial_scale="Regional", system_in_focus="Lagoon")


def test_save_project_info_keeps_v7_metadata_fields():
    start = Project(ProjectMetadata(
        name="R template", description="from R", regional_sea="Baltic Sea",
        created_at="2026-04-08", modified_at="2026-04-08",
        origin="r_template", r_template_version="2.3",
        min_sespy_version="1.13.0"), IsaData())
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(start)
        holder.append(pd)
        pims_project_server("pims", project_data=pd, event_bus=create_event_bus())

    with test_server(server) as ts:
        scope = ts.make_scope("pims")
        # Every form input must be set, or input.x() aborts the handler.
        # Action buttons ignore their initial value: set 0, then 1.
        scope.set_inputs(**FORM, save_project_info=0)
        scope.set_inputs(save_project_info=1)
        assert ts.is_ok, ts.error
        with reactive.isolate():
            meta = holder[0].get().metadata

    assert meta.name == "Renamed" and meta.focal_issue == "Eutrophication"
    assert (meta.origin, meta.r_template_version, meta.min_sespy_version) == \
        ("r_template", "2.3", "1.13.0")
    assert (meta.description, meta.regional_sea, meta.created_at) == \
        ("from R", "Baltic Sea", "2026-04-08")
    assert meta.modified_at != "2026-04-08"
