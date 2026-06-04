from sespy.data_structure import (
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)
from sespy.persistent_storage import load_project, save_project_atomic


def _proj_with(stakeholders):
    return Project(
        metadata=ProjectMetadata.new("T"),
        isa_data=IsaData(),
        stakeholders=stakeholders,
    )


# NOTE: the schema-version assertion lives only in test_data_structure.py
# (Step 4) — it's a global concern, not duplicated here.


def test_stakeholder_defaults():
    s = Stakeholder(id="SH001", name="Port Authority")
    assert s.stakeholder_type == ""
    assert s.power == ""
    assert s.created_at == ""


def test_project_roundtrip_preserves_stakeholders():
    s = Stakeholder(
        id="SH001", name="Port Authority", stakeholder_type="government",
        sector="shipping", contact="port@x.eu", interests="navigation",
        role="regulator", power="HIGH", interest="MEDIUM",
        attitude="neutral", engagement_level="consult", created_at="2026-06-04",
    )
    proj = _proj_with([s])
    back = Project.from_dict(proj.to_dict())
    assert back.stakeholders == [s]


def test_from_dict_missing_key_yields_empty_list():
    raw = {"metadata": {"name": "Legacy v2"}, "isa_data": {"elements": [], "connections": []}}
    assert Project.from_dict(raw).stakeholders == []


def test_from_dict_tolerates_unknown_stakeholder_key():
    raw = {
        "metadata": {"name": "T"},
        "isa_data": {"elements": [], "connections": []},
        "stakeholders": [{"id": "SH001", "name": "X", "future_field": 42}],
    }
    out = Project.from_dict(raw).stakeholders
    assert out == [Stakeholder(id="SH001", name="X")]


def test_with_modified_now_preserves_stakeholders():
    s = Stakeholder(id="SH001", name="X")
    proj = _proj_with([s])
    assert proj.with_modified_now().stakeholders == [s]


def test_replace_preserves_other_fields():
    s = Stakeholder(id="SH001", name="X")
    proj = _proj_with([s])
    new_meta = ProjectMetadata.new("Renamed")
    out = proj.replace(metadata=new_meta)
    assert out.metadata.name == "Renamed"
    assert out.stakeholders == [s]
    assert out.isa_data is proj.isa_data


def test_save_path_roundtrip_preserves_stakeholders(tmp_path):
    s = Stakeholder(id="SH001", name="Coastal NGO", stakeholder_type="ngo")
    proj = _proj_with([s])
    p = tmp_path / "proj.json"
    save_project_atomic(proj, p)
    back = load_project(p)
    assert back.stakeholders == [s]
