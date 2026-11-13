"""K1 Task 9: provenance stamped at serialisation (spec §4.1)."""
from __future__ import annotations

import json

from sespy import autosave, r_kb
from sespy.data_structure import IsaData, Project
from sespy.persistent_storage import project_to_bytes, save_project_atomic

LOADED = {
    "ses_knowledge_db.json": {"source": "vendored", "sha256_norm": "old1",
                              "version": "1.0", "vendored_r_tag": "v0"},
    "country_governance_db.json": {"source": "vendored", "sha256_norm": "old2",
                                   "version": "1.0", "vendored_r_tag": "v0"},
}


def _project(ref=None):
    p = Project.from_isa(IsaData())
    if ref is not None:
        p.metadata.reference_data = ref
    return p


def test_to_dict_default_unchanged():
    p = _project(LOADED)
    assert p.to_dict()["metadata"]["reference_data"] == LOADED
    assert p.to_dict(reference_data=None) == p.to_dict()


def test_overlay_in_output_only():
    p = _project(LOADED)
    over = {"x.json": {"source": "shared"}}
    assert p.to_dict(reference_data=over)["metadata"]["reference_data"] == over
    assert json.loads(p.to_json(reference_data=over))["metadata"]["reference_data"] == over
    assert p.metadata.reference_data == LOADED


def test_merge_keeps_unread_loaded_entries():
    snap = r_kb.current()
    meta = _project(LOADED).metadata
    out = r_kb.current_provenance(meta, snap, frozenset({r_kb.KB_NAME}))
    assert out[r_kb.GOVERNANCE_NAME] == LOADED[r_kb.GOVERNANCE_NAME]
    assert out[r_kb.KB_NAME] == snap.provenance(r_kb.KB_NAME)


def test_merge_replaces_read_entries():
    snap = r_kb.current()
    meta = _project(LOADED).metadata
    out = r_kb.current_provenance(meta, snap, frozenset({r_kb.KB_NAME, r_kb.GOVERNANCE_NAME}))
    assert out == {n: snap.provenance(n) for n in (r_kb.KB_NAME, r_kb.GOVERNANCE_NAME)}
    assert meta.reference_data == LOADED          # input not mutated


def test_saved_file_has_no_data_key_and_is_small(tmp_path):
    snap = r_kb.current()
    meta = _project().metadata
    prov = r_kb.current_provenance(meta, snap, frozenset({r_kb.KB_NAME, r_kb.GOVERNANCE_NAME}))
    path = tmp_path / "p.json"
    save_project_atomic(_project(), path, reference_data=prov)
    raw = path.read_bytes()
    assert len(raw) < 50_000
    stamped = json.loads(raw)["metadata"]["reference_data"]
    assert stamped == prov
    for entry in stamped.values():
        assert set(entry) == {"source", "sha256_norm", "version", "vendored_r_tag"}
    assert json.loads(project_to_bytes(_project(), reference_data=prov))[
        "metadata"]["reference_data"] == prov


def test_callers_pass_nothing(tmp_path):
    assert "metadata" in Project.to_dict(_project())
    assert json.loads(project_to_bytes(_project()))["metadata"]["reference_data"] == {}
    save_project_atomic(_project(), tmp_path / "q.json")
    import sespy.r_template_catalogue  # noqa: F401  (its project.to_json() call is unchanged)
    assert _project().to_json().startswith("{")


def test_autosave_overlay_written(tmp_path, monkeypatch):
    monkeypatch.setenv("SESPY_AUTOSAVE_DIR", str(tmp_path))
    monkeypatch.setattr(autosave, "autosave_path", lambda token: tmp_path / "a.json")
    over = {"ses_knowledge_db.json": {"source": "shared"}}
    p = autosave.write_autosave(_project(LOADED), token="t" * 32, reference_data=over)
    assert json.loads(p.read_text("utf-8"))["metadata"]["reference_data"] == over
