from sespy.data_structure import (
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)
from sespy.persistent_storage import load_project, save_project_atomic
from sespy.stakeholders import (
    add_stakeholder,
    classify_quadrant,
    level_num,
    remove_stakeholder,
    summarize_quadrants,
    update_stakeholder,
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
    assert out.isa_data == proj.isa_data


def test_replace_isa_data_preserves_stakeholders():
    # The exact failure mode this task fixes: 5 of 7 call sites replace
    # isa_data, and the old bare-constructor form dropped stakeholders here.
    s = Stakeholder(id="SH001", name="X")
    proj = _proj_with([s])
    out = proj.replace(isa_data=IsaData())
    assert out.stakeholders == [s]


def test_save_path_roundtrip_preserves_stakeholders(tmp_path):
    s = Stakeholder(id="SH001", name="Coastal NGO", stakeholder_type="ngo")
    proj = _proj_with([s])
    p = tmp_path / "proj.json"
    save_project_atomic(proj, p)
    back = load_project(p)
    assert back.stakeholders == [s]


def test_add_assigns_padded_id_and_created_at():
    out = add_stakeholder([], {"name": "A", "stakeholder_type": "ngo"}, today="2026-06-04")
    assert len(out) == 1
    assert out[0].id == "SH001"
    assert out[0].name == "A"
    assert out[0].created_at == "2026-06-04"


def test_add_is_pure_and_increments_id():
    first = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    second = add_stakeholder(first, {"name": "B"}, today="2026-06-05")
    assert [s.id for s in second] == ["SH001", "SH002"]
    assert len(first) == 1  # original list untouched


def test_update_replaces_by_id_preserving_id_and_created_at():
    items = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    out = update_stakeholder(items, "SH001", {"name": "A2", "power": "HIGH"})
    assert out[0].id == "SH001"
    assert out[0].name == "A2"
    assert out[0].power == "HIGH"
    assert out[0].created_at == "2026-06-04"


def test_remove_drops_by_id():
    items = add_stakeholder([], {"name": "A"}, today="2026-06-04")
    assert remove_stakeholder(items, "SH001") == []


def test_level_num():
    assert level_num("HIGH") == 3
    assert level_num("MEDIUM") == 2
    assert level_num("LOW") == 1
    assert level_num("") is None
    assert level_num("x") is None


def test_classify_quadrant_truth_table():
    assert classify_quadrant("HIGH", "HIGH") == "key_players"
    assert classify_quadrant("MEDIUM", "MEDIUM") == "key_players"   # >=MEDIUM=high
    assert classify_quadrant("HIGH", "LOW") == "keep_satisfied"
    assert classify_quadrant("MEDIUM", "LOW") == "keep_satisfied"
    assert classify_quadrant("LOW", "HIGH") == "keep_informed"
    assert classify_quadrant("LOW", "MEDIUM") == "keep_informed"
    assert classify_quadrant("LOW", "LOW") == "monitor"
    assert classify_quadrant("", "HIGH") is None
    assert classify_quadrant("HIGH", "") is None
    assert classify_quadrant("junk", "HIGH") is None


def test_summarize_quadrants():
    items = [
        Stakeholder(id="SH001", name="Key", power="HIGH", interest="HIGH"),
        Stakeholder(id="SH002", name="Sat", power="HIGH", interest="LOW"),
        Stakeholder(id="SH003", name="Inf", power="LOW", interest="HIGH"),
        Stakeholder(id="SH004", name="Mon", power="LOW", interest="LOW"),
        Stakeholder(id="SH005", name="Blank", power="", interest="HIGH"),
    ]
    out = summarize_quadrants(items)
    assert out["key_players"] == ["Key"]
    assert out["keep_satisfied"] == ["Sat"]
    assert out["keep_informed"] == ["Inf"]
    assert out["monitor"] == ["Mon"]
    assert out["unplotted"] == ["Blank"]
    assert set(out) == {"key_players", "keep_satisfied", "keep_informed", "monitor", "unplotted"}
