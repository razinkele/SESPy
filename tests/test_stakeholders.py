from sespy.data_structure import (
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)


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
