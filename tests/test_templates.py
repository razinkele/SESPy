"""Unit tests for the templates registry + JSON validity."""
from __future__ import annotations

from pathlib import Path

import pytest

from sespy import templates as tpl
from sespy.persistent_storage import load_project


def test_templates_directory_has_at_least_two():
    """Sanity check that we ship multiple starting points."""
    rows = tpl.list_templates()
    assert len(rows) >= 2, f"expected ≥2 built-in templates, got {len(rows)}"


def test_each_template_loads_and_validates():
    """Every shipped template should parse + pass schema validation."""
    rows = tpl.list_templates()
    for info in rows:
        project = load_project(info.file)
        assert project.isa_data.element_count() > 0, info.name
        assert project.isa_data.connection_count() > 0, info.name


def test_templates_have_distinct_names():
    rows = tpl.list_templates()
    names = [r.name for r in rows]
    assert len(names) == len(set(names)), f"duplicate names: {names}"


def test_template_metadata_populated():
    """Each template should have a name and a non-empty description —
    they're shown in the picker."""
    for info in tpl.list_templates():
        assert info.name, info.file
        assert info.description, f"{info.name} missing description"


def test_template_load_roundtrip_via_load_template_helper():
    rows = tpl.list_templates()
    if not rows:
        pytest.skip("no templates installed")
    project = tpl.load_template(rows[0].file)
    assert project.isa_data.element_count() == rows[0].element_count
    assert project.isa_data.connection_count() == rows[0].connection_count


def test_offshore_wind_template_has_responses():
    """Spot-check the offshore wind template includes Response elements
    (R001 spatial planning, R002 noise mitigation) that the analyses
    use as a 'what intervention?' example."""
    project = load_project(
        Path(tpl._templates_dir()) / "offshore_wind.json"
    )
    types = {el.type for el in project.isa_data.elements}
    assert "Responses" in types


# ---- P2: the MarineSABRES group (spec §6.1) -------------------------------

import json
import logging
import shutil
import sys
import tomllib

from sespy.r_template_catalogue import ALWAYS_NON_EMPTY, OUT_DIR

ROOT = Path(__file__).resolve().parents[1]
CAT_DIR = ROOT / OUT_DIR
SUFFIX = " (MarineSABRES)"


def test_list_catalogue_has_the_seven_r_templates():
    rows = tpl.list_catalogue()
    assert len(rows) == 7
    assert rows[0].name == "Caribbean Island - Comprehensive SES Template (MarineSABRES)"
    for r in rows:
        assert r.group == "marinesabres" and r.da_site == ""
        assert r.name.endswith(SUFFIX)
        assert r.file.is_absolute() and r.file.parent == CAT_DIR.resolve()
        for k in ALWAYS_NON_EMPTY:
            v = r.file.name if k == "file" else getattr(r, k)
            assert isinstance(v, str) and v, (r.name, k)
        assert r.element_count > 0 and r.connection_count > 0


def test_list_catalogue_parses_no_project(tmp_path):
    # Unparsable project files cannot matter if only catalogue.json is read.
    d = tmp_path / "marinesabres"
    shutil.copytree(CAT_DIR, d)
    for p in d.glob("*_SES_Template.json"):
        p.write_bytes(b"not json")
    rows = tpl.list_catalogue(d)
    assert len(rows) == 7 and rows[0].element_count == 78


def test_every_catalogue_file_loads_with_the_listed_counts():
    for r in tpl.list_catalogue():
        project = load_project(r.file)
        assert project.isa_data.element_count() == r.element_count, r.name
        assert project.isa_data.connection_count() == r.connection_count, r.name
        assert project.metadata.name == r.name
        assert project.metadata.origin == "r_template"


def test_names_unique_across_both_groups_and_fit_the_wired_buttons():
    from sespy.modules.templates import MAX_TEMPLATES
    rows = tpl.list_catalogue() + tpl.list_templates()
    names = [r.name for r in rows]
    assert len(names) == len(set(names)), names
    assert len(rows) == 11 and len(rows) <= MAX_TEMPLATES


def test_list_templates_ignores_the_marinesabres_subdirectory():
    rows = tpl.list_templates()
    assert {r.group for r in rows} == {"sespy"}
    assert all(r.file.parent == Path(tpl._templates_dir()) for r in rows)
    assert not any(r.name.endswith(SUFFIX) for r in rows)


def test_template_info_new_fields_default_for_existing_callers():
    info = tpl.TemplateInfo(file=Path("x.json"), name="n", description="d",
                            da_site="", element_count=1, connection_count=1)
    assert (info.group, info.category, info.complexity, info.version,
            info.regional_sea_label, info.source, info.usage_notes) == ("sespy", "", "", "", "", "", "")


# -- list_catalogue(directory=...) on a tmp copy --------------------------------

def _copy(tmp_path: Path) -> Path:
    d = tmp_path / "marinesabres"
    shutil.copytree(CAT_DIR, d)
    return d


def _edit_catalogue(d: Path, change) -> None:
    cat = json.loads((d / "catalogue.json").read_bytes().decode("utf-8-sig"))
    change(cat)
    (d / "catalogue.json").write_bytes(json.dumps(cat).encode("utf-8"))


def test_missing_catalogue_gives_empty_and_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        assert tpl.list_catalogue(tmp_path) == []
    assert "catalogue unavailable" in caplog.text


@pytest.mark.parametrize("text", ["{not json", "[]", '{"templates": {}}', '{"r_tag": "v1"}'])
def test_unparsable_catalogue_gives_empty_and_warns(tmp_path, caplog, text):
    (tmp_path / "catalogue.json").write_text(text, encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        assert tpl.list_catalogue(tmp_path) == []
    assert "catalogue unavailable" in caplog.text


@pytest.mark.parametrize("change", [
    lambda e: e.pop("usage_notes"),                  # missing key
    lambda e: e.update(name=""),                     # empty always-non-empty field
    lambda e: e.update(category=None),
    lambda e: e.update(source=3),                    # may-be-empty field, wrong type
    lambda e: e.update(element_count=0),
    lambda e: e.update(connection_count="140"),      # non-int
    lambda e: e.update(element_count=True),          # bool is not a count
    lambda e: e.update(file="missing.json"),         # dangling
    lambda e: e.update(file="../catalogue.json"),    # escaping
    lambda e: e.update(file="..\\catalogue.json"),   # Windows escape to the {} target
    lambda e: e.update(file=str(CAT_DIR.parent / "minimal_demo.json")),   # absolute, outside
    lambda e: e.update(file=""),
], ids=["missing-key", "empty-name", "null-category", "int-source", "zero-count",
        "str-count", "bool-count", "dangling", "escape-up", "escape-backslash",
        "absolute", "empty-file"])
def test_bad_entry_is_skipped_with_a_warning(tmp_path, caplog, change):
    d = _copy(tmp_path)
    (tmp_path / "catalogue.json").write_text("{}", encoding="utf-8")      # an escape target
    _edit_catalogue(d, lambda cat: change(cat["templates"][0]))
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        rows = tpl.list_catalogue(d)
    assert len(rows) == 6
    assert "entry 0 skipped" in caplog.text


def test_relative_directory_still_lists_all_seven(tmp_path, monkeypatch):
    _copy(tmp_path)
    monkeypatch.chdir(tmp_path)
    rows = tpl.list_catalogue(Path("marinesabres"))
    assert len(rows) == 7 and all(r.file.is_absolute() for r in rows)


@pytest.mark.skipif(sys.platform != "win32", reason="8.3 short paths are a Windows thing")
def test_short_8dot3_directory_still_lists_all_seven(tmp_path):
    import ctypes
    d = _copy(tmp_path)
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(d), buf, len(buf))
    short = Path(buf.value) if n else d
    if "~" not in str(short):
        pytest.skip("8.3 short names are disabled on this volume")
    assert str(short) != str(d.resolve())
    rows = tpl.list_catalogue(short)
    assert len(rows) == 7


def test_package_data_ships_the_marinesabres_templates():
    with open(ROOT / "pyproject.toml", "rb") as f:
        globs = tomllib.load(f)["tool"]["setuptools"]["package-data"]["sespy"]
    assert "templates/marinesabres/*.json" in globs
    # setuptools expands these with glob semantics: "*" never crosses "/".
    shipped = {p.resolve() for g in globs for p in (ROOT / "sespy").glob(g)}
    wanted = {p.resolve() for p in CAT_DIR.glob("*.json")}
    assert len(wanted) == 8 and wanted <= shipped
