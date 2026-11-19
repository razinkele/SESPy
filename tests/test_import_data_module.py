"""App test: parse_upload dispatch in sespy.modules.import_data."""
from __future__ import annotations

import json


def test_parse_upload_dispatches_by_extension(tmp_path):
    # The dispatch keys off the ORIGINAL filename, not the temp datapath.
    from sespy.modules.import_data import parse_upload

    data = {"canvas": {"nodes": [{"id": "a", "label": "A"}], "links": []}}
    f = tmp_path / "model.qsem"
    f.write_text(json.dumps(data), encoding="utf-8")

    # .qsem name -> parse_qsem -> valid (1 node, 0 connections)
    qsem_result = parse_upload("model.qsem", f)
    assert qsem_result.valid, qsem_result.errors
    assert qsem_result.project.isa_data.element_count() == 1
    # project is named after the original upload, not Shiny's temp datapath stem
    assert qsem_result.project.metadata.name == "model"

    # same JSON bytes but a .xlsx name -> parse_excel -> invalid (not a real xlsx)
    xlsx_result = parse_upload("model.xlsx", f)
    assert not xlsx_result.valid
