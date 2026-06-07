from sespy.data_structure import (
    Communication,
    Engagement,
    IsaData,
    Project,
    ProjectMetadata,
    Stakeholder,
)
from sespy.persistent_storage import load_project, save_project_atomic
from sespy.stakeholders import (
    add_communication,
    add_engagement,
    add_stakeholder,
    classify_quadrant,
    communication_rows,
    count_by,
    engagement_coverage,
    engagement_rows,
    level_num,
    remove_communication,
    remove_engagement,
    remove_stakeholder,
    stakeholder_stats,
    summarize_quadrants,
    update_stakeholder,
)


def _proj_with(stakeholders):
    return Project(
        metadata=ProjectMetadata.new("T"),
        isa_data=IsaData(),
        stakeholders=stakeholders,
    )


def _proj_with_eng(stakeholders, engagements):
    return Project(
        metadata=ProjectMetadata.new("T"),
        isa_data=IsaData(),
        stakeholders=stakeholders,
        engagements=engagements,
    )


def _proj_with_comm(communications):
    return Project(
        metadata=ProjectMetadata.new("T"),
        isa_data=IsaData(),
        communications=communications,
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


# --- SH3: Engagement model + persistence -----------------------------------
def test_engagement_defaults():
    e = Engagement(id="ENG001", stakeholder_id="SH001")
    assert e.method == "" and e.outcomes == ""
    assert e.status == "planned"
    assert e.created_at == ""


def test_project_roundtrip_preserves_engagements():
    e = Engagement(id="ENG001", stakeholder_id="SH001", method="workshop",
                   date="2026-06-06", objectives="align", outcomes="agreed",
                   status="completed", facilitator="A. B.", created_at="2026-06-06")
    proj = _proj_with_eng([Stakeholder(id="SH001", name="X")], [e])
    back = Project.from_dict(proj.to_dict())
    assert back.engagements == [e]


def test_from_dict_missing_engagements_key_yields_empty_list():
    raw = {"metadata": {"name": "v3"}, "isa_data": {"elements": [], "connections": []},
           "stakeholders": [{"id": "SH001", "name": "X"}]}
    assert Project.from_dict(raw).engagements == []


def test_from_dict_tolerates_unknown_engagement_key():
    raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
           "engagements": [{"id": "ENG001", "stakeholder_id": "SH001", "future_field": 1}]}
    assert Project.from_dict(raw).engagements == [
        Engagement(id="ENG001", stakeholder_id="SH001")]


def test_from_dict_upgrades_schema_version_on_load():
    raw = {"metadata": {"name": "old", "schema_version": 3},
           "isa_data": {"elements": [], "connections": []},
           "engagements": [{"id": "ENG001", "stakeholder_id": "SH001"}]}
    assert Project.from_dict(raw).metadata.schema_version == 5


def test_with_modified_now_preserves_engagements():
    e = Engagement(id="ENG001", stakeholder_id="SH001")
    proj = _proj_with_eng([], [e])
    assert proj.with_modified_now().engagements == [e]


def test_save_path_roundtrip_preserves_engagements(tmp_path):
    e = Engagement(id="ENG001", stakeholder_id="SH001", method="survey")
    proj = _proj_with_eng([Stakeholder(id="SH001", name="X")], [e])
    p = tmp_path / "proj.json"
    save_project_atomic(proj, p)
    back = load_project(p)
    assert back.engagements == [e]
    assert back.metadata.schema_version == 5


def test_migrated_v3_saves_as_schema_5_on_disk(tmp_path):
    # Start from a RAW v3 payload (not a fresh project): load -> save ->
    # inspect the RAW JSON so the on-disk version isn't masked by from_dict's
    # upgrade-on-load.
    import json
    old = Project.from_dict({
        "metadata": {"name": "old", "schema_version": 3},
        "isa_data": {"elements": [], "connections": []},
        "engagements": [{"id": "ENG001", "stakeholder_id": "SH001"}],
    })
    p = tmp_path / "old.json"
    save_project_atomic(old, p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["metadata"]["schema_version"] == 5
    assert raw["engagements"][0]["id"] == "ENG001"


# --- SH3: pure engagement helpers ------------------------------------------
def _ident(key):  # mimic Translator.t() returning the key on a miss
    return key


def test_add_engagement_assigns_id_and_created_at():
    out = add_engagement([], {"stakeholder_id": "SH001", "method": "workshop"},
                         today="2026-06-06")
    assert len(out) == 1 and out[0].id == "ENG001"
    assert out[0].created_at == "2026-06-06"
    assert out[0].stakeholder_id == "SH001"


def test_add_engagement_is_pure_and_increments_id():
    first = add_engagement([], {"stakeholder_id": "SH001"}, today="2026-06-06")
    second = add_engagement(first, {"stakeholder_id": "SH002"}, today="2026-06-07")
    assert [e.id for e in second] == ["ENG001", "ENG002"]
    assert len(first) == 1  # original untouched


def test_remove_engagement_drops_by_id():
    items = [Engagement(id="ENG001", stakeholder_id="SH001"),
             Engagement(id="ENG002", stakeholder_id="SH002")]
    out = remove_engagement(items, "ENG001")
    assert [e.id for e in out] == ["ENG002"]


def test_engagement_rows_resolves_name_and_labels():
    sh = [Stakeholder(id="SH001", name="Port Authority")]
    eng = [Engagement(id="ENG001", stakeholder_id="SH001", method="workshop",
                      status="completed", date="2026-06-06")]
    rows = engagement_rows(eng, sh, translate=_ident)
    assert rows[0]["stakeholder"] == "Port Authority"
    assert rows[0]["method"] == "stakeholders.activity.method.workshop"
    assert rows[0]["status"] == "stakeholders.activity.status.completed"
    assert rows[0]["date"] == "2026-06-06"


def test_engagement_rows_dangling_fk_yields_blank_name():
    eng = [Engagement(id="ENG001", stakeholder_id="GONE")]
    rows = engagement_rows(eng, [], translate=_ident)
    assert rows[0]["stakeholder"] == ""


def test_engagement_rows_unknown_code_passes_through_verbatim():
    eng = [Engagement(id="ENG001", stakeholder_id="SH001",
                      method="telepathy", status="vibes")]
    rows = engagement_rows(eng, [Stakeholder(id="SH001", name="X")], translate=_ident)
    assert rows[0]["method"] == "telepathy"     # NOT the i18n key
    assert rows[0]["status"] == "vibes"


def test_engagement_rows_blank_code_is_blank():
    eng = [Engagement(id="ENG001", stakeholder_id="SH001")]  # method="" status="planned"
    rows = engagement_rows(eng, [Stakeholder(id="SH001", name="X")], translate=_ident)
    assert rows[0]["method"] == ""
    assert rows[0]["status"] == "stakeholders.activity.status.planned"


# --- SH4: Communication model + persistence --------------------------------
def test_communication_defaults():
    c = Communication(id="COMM001")
    assert c.audience == "" and c.comm_type == "" and c.message == ""
    assert c.frequency == "one_time"
    assert c.created_at == ""


def test_project_roundtrip_preserves_communications():
    c = Communication(id="COMM001", audience="key_players", comm_type="report",
                      date="2026-06-07", frequency="monthly", message="status",
                      responsible="A. B.", created_at="2026-06-07")
    proj = _proj_with_comm([c])
    back = Project.from_dict(proj.to_dict())
    assert back.communications == [c]


def test_from_dict_missing_communications_key_yields_empty_list():
    raw = {"metadata": {"name": "v4"}, "isa_data": {"elements": [], "connections": []}}
    assert Project.from_dict(raw).communications == []


def test_from_dict_tolerates_unknown_communication_key():
    raw = {"metadata": {"name": "T"}, "isa_data": {"elements": [], "connections": []},
           "communications": [{"id": "COMM001", "audience": "ngos", "future_field": 1}]}
    assert Project.from_dict(raw).communications == [
        Communication(id="COMM001", audience="ngos")]


def test_with_modified_now_preserves_communications():
    c = Communication(id="COMM001", audience="government")
    proj = _proj_with_comm([c])
    assert proj.with_modified_now().communications == [c]


def test_save_path_roundtrip_preserves_communications(tmp_path):
    c = Communication(id="COMM001", comm_type="newsletter")
    proj = _proj_with_comm([c])
    p = tmp_path / "proj.json"
    save_project_atomic(proj, p)
    back = load_project(p)
    assert back.communications == [c]
    assert back.metadata.schema_version == 5


def test_migrated_v4_saves_as_schema_5_on_disk(tmp_path):
    import json
    old = Project.from_dict({
        "metadata": {"name": "old", "schema_version": 4},
        "isa_data": {"elements": [], "connections": []},
        "communications": [{"id": "COMM001", "audience": "ngos"}],
    })
    p = tmp_path / "old.json"
    save_project_atomic(old, p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["metadata"]["schema_version"] == 5
    assert raw["communications"][0]["id"] == "COMM001"


# --- SH4: pure communication helpers ---------------------------------------
def test_add_communication_assigns_id_and_created_at():
    out = add_communication([], {"audience": "key_players", "comm_type": "report"},
                            today="2026-06-07")
    assert len(out) == 1 and out[0].id == "COMM001"
    assert out[0].created_at == "2026-06-07"


def test_remove_communication_drops_by_id():
    items = [Communication(id="COMM001"), Communication(id="COMM002")]
    assert [c.id for c in remove_communication(items, "COMM001")] == ["COMM002"]


def test_communication_rows_maps_known_codes_to_labels():
    c = [Communication(id="COMM001", audience="key_players", comm_type="report",
                       frequency="monthly", date="2026-06-07", message="m",
                       responsible="r")]
    rows = communication_rows(c, translate=_ident)
    assert rows[0]["audience"] == "stakeholders.comm.audience.key_players"
    assert rows[0]["type"] == "stakeholders.comm.type.report"
    assert rows[0]["frequency"] == "stakeholders.comm.frequency.monthly"
    assert rows[0]["date"] == "2026-06-07"
    assert rows[0]["message"] == "m" and rows[0]["responsible"] == "r"


def test_communication_rows_unknown_code_passes_through_verbatim():
    c = [Communication(id="COMM001", audience="aliens", comm_type="smoke_signal",
                       frequency="hourly")]
    rows = communication_rows(c, translate=_ident)
    assert rows[0]["audience"] == "aliens"
    assert rows[0]["type"] == "smoke_signal"
    assert rows[0]["frequency"] == "hourly"


# --- SH5: analysis summary helpers -----------------------------------------
def test_stakeholder_stats_counts():
    sh = [
        Stakeholder(id="SH001", name="A", stakeholder_type="government",
                    sector="fisheries", power="HIGH", interest="HIGH"),
        Stakeholder(id="SH002", name="B", stakeholder_type="ngo",
                    sector="fisheries", power="HIGH", interest="LOW"),
        Stakeholder(id="SH003", name="C", stakeholder_type="ngo",
                    sector="", power="LOW", interest="HIGH"),
    ]
    eng = [Engagement(id="ENG001", stakeholder_id="SH001")]
    comm = [Communication(id="COMM001"), Communication(id="COMM002")]
    s = stakeholder_stats(sh, eng, comm)
    assert s["total"] == 3
    assert s["types"] == 2          # government, ngo (distinct non-empty)
    assert s["sectors"] == 1        # fisheries (blank not counted)
    assert s["high_power"] == 2
    assert s["high_interest"] == 2
    assert s["engagements"] == 1
    assert s["communications"] == 2


def test_stakeholder_stats_empty_is_all_zero():
    s = stakeholder_stats([], [], [])
    assert s == {"total": 0, "types": 0, "sectors": 0, "high_power": 0,
                 "high_interest": 0, "engagements": 0, "communications": 0}


def test_engagement_coverage():
    sh = [Stakeholder(id="SH001", name="A"), Stakeholder(id="SH002", name="B")]
    assert engagement_coverage([], []) == 0.0
    assert engagement_coverage(sh, []) == 0.0
    # one of two engaged, deduped across multiple engagements
    eng = [Engagement(id="ENG001", stakeholder_id="SH001"),
           Engagement(id="ENG002", stakeholder_id="SH001")]
    assert engagement_coverage(sh, eng) == 50.0
    eng2 = eng + [Engagement(id="ENG003", stakeholder_id="SH002")]
    assert engagement_coverage(sh, eng2) == 100.0


def test_count_by_first_seen_order_and_blanks():
    sh = [
        Stakeholder(id="SH001", name="A", stakeholder_type="ngo"),
        Stakeholder(id="SH002", name="B", stakeholder_type="government"),
        Stakeholder(id="SH003", name="C", stakeholder_type="ngo"),
        Stakeholder(id="SH004", name="D", stakeholder_type=""),
    ]
    assert count_by(sh, "stakeholder_type") == {"ngo": 2, "government": 1, "": 1}
    assert count_by([], "sector") == {}
