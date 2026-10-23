"""P2 — sespy.r_template_catalogue: the R template sync (spec §3, §4, §8).

Every sync() here runs against a tmp_path copy of the repo files it reads
(tests/parity/ and docs/parity/R_SYNC.md); the R side is a real git repo
built in tmp_path. Nothing touches the working tree.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sespy import r_template_catalogue as C
from sespy.r_template_mapper import load_r_template
from sespy.regional_seas import get_regional_seas

ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "tests" / "parity"
FIX = PARITY / "r_templates"
RAW = {f: load_r_template(FIX / f) for f in C.TEMPLATE_FILES}
MS = Path(C.OUT_DIR)
LOADER_STUB = b"# stand-in for functions/template_loader.R in the fake R repo\n"
EXPECTED_CATEGORY = {
    "Aquaculture": "Production", "Caribbean": "Multi-Stressor",
    "ClimateChange": "Climate", "Fisheries": "Extraction",
    "OffshoreWind": "Energy", "Pollution": "Pollution", "Tourism": "Recreation",
}
CARIBBEAN = "Caribbean Island - Comprehensive SES Template (MarineSABRES)"


# ---- helpers ------------------------------------------------------------------

def _tree(tmp_path: Path) -> Path:
    """A repo_root holding only what sync() reads: tests/parity/ and R_SYNC.md."""
    root = tmp_path / "repo"
    shutil.copytree(PARITY, root / "tests" / "parity",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    (root / "docs" / "parity").mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "parity" / "R_SYNC.md", root / "docs" / "parity" / "R_SYNC.md")
    return root


def _snap(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", "-c", "core.autocrlf=false",
         "-c", "user.name=p2", "-c", "user.email=p2@example.invalid",
         "-c", "commit.gpgsign=false", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True).stdout


def _fake_r(tmp_path: Path, tag: str = "v1.31.0") -> Path:
    """A real git repo whose app lives in a subdirectory (non-empty prefix),
    holding the pinned inputs, committed and tagged. Returns the app dir."""
    outer = tmp_path / "Rrepo"
    app = outer / "MarineSABRES_SES_Shiny"
    (app / "data").mkdir(parents=True)
    (app / "functions").mkdir()
    for f in C.TEMPLATE_FILES:
        (app / "data" / f).write_bytes((FIX / f).read_bytes().replace(b"\r\n", b"\n"))
    rules = PARITY / "r_rules" / "dapsiwrm_connection_rules.R"
    (app / "functions" / "dapsiwrm_connection_rules.R").write_bytes(
        rules.read_bytes().replace(b"\r\n", b"\n"))
    (app / "functions" / "template_loader.R").write_bytes(LOADER_STUB)
    # P1b inputs: the R sources are only hashed (stubs do); the translation
    # files are parsed by the subset step, so they are the real fixtures.
    for r_path in C.R_SOURCES:
        (app / r_path).write_bytes(f"# stand-in for {r_path}\n".encode("utf-8"))
    (app / "translations" / "modules").mkdir(parents=True)
    for stem in C.TRANSLATION_SUBSETS:
        (app / "translations" / "modules" / f"{stem}.json").write_bytes(
            (PARITY / "r_translations" / f"{stem}.json").read_bytes().replace(b"\r\n", b"\n"))
    subprocess.run(["git", "-c", "core.longpaths=true", "init", "-q", "--template=", str(outer)],
                   check=True, capture_output=True)
    _git(outer, "add", "-A")
    _git(outer, "commit", "-qm", "r")
    _git(outer, "tag", tag)
    return app


@pytest.fixture(scope="module")
def r_app(tmp_path_factory) -> Path:
    """One untouched fake R repo (tag v1.31.0) shared by the read-only tests;
    tests that add an R release build their own with _fake_r(tmp_path)."""
    return _fake_r(tmp_path_factory.mktemp("r"))


def _r_release(app: Path, tag: str, edit) -> None:
    """Edit one R template in the fake repo and tag the result."""
    edit(app)
    _git(app.parent, "commit", "-qam", tag)
    _git(app.parent, "tag", tag)


def _edit_json(path: Path, change) -> None:
    d = json.loads(path.read_bytes().decode("utf-8-sig"))
    change(d)
    path.write_bytes(json.dumps(d, indent=2, ensure_ascii=False).encode("utf-8"))


def _add_off_rule(d: dict) -> None:
    fw = d["dapsiwrm_framework"]       # Goods & Benefits -> Activities is off-rule
    d["connections"].append({"from_id": fw["goods_benefits"][0]["id"],
                             "to_id": fw["activities"][0]["id"], "polarity": "+"})


def _md_block(root: Path) -> str:
    md = (root / C.MD_PATH).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return md.split(C.BEGIN)[1].split(C.END)[0]


def _md_prose(root: Path) -> tuple[str, str]:
    md = (root / C.MD_PATH).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return md.split(C.BEGIN)[0], md.split(C.END)[1]


def _pin(root: Path) -> dict:
    return json.loads((root / C.PIN_PATH).read_bytes().decode("utf-8"))


# ---- category port (§4) -------------------------------------------------------

@pytest.mark.parametrize("stem", C.STEMS)
def test_category_of_the_seven(stem):
    assert C.determine_category(RAW[f"{stem}_SES_Template.json"]) == EXPECTED_CATEGORY[stem]


@pytest.mark.parametrize("regional_context,want", [
    (None, "General"),                                   # no regional_context
    ({}, "General"),                                     # main_issues absent (NULL)
    ({"main_issues": None}, "General"),
    ({"main_issues": []}, "General"),                    # empty list falls through
    ({"main_issues": "Fisheries decline"}, "Extraction"),  # scalar = one issue
    ({"main_issues": ["a", "b"]}, "Multi-Stressor"),
    ({"main_issues": ["fish stocks"]}, "Extraction"),
    ({"main_issues": ["Coastal TOURISM"]}, "Recreation"),
    ({"main_issues": ["aquaculture"]}, "Production"),
    ({"main_issues": ["pollution"]}, "Pollution"),
    ({"main_issues": ["contamination"]}, "Pollution"),
    ({"main_issues": ["climate"]}, "Climate"),
    ({"main_issues": ["warming"]}, "Climate"),
    ({"main_issues": ["Sea Level rise"]}, "Climate"),
    ({"main_issues": ["wind"]}, "Energy"),
    ({"main_issues": ["energy"]}, "Energy"),
    ({"main_issues": ["wind farm"]}, "Production"),      # R's order: farm before wind
    ({"main_issues": ["fish farm"]}, "Extraction"),      # fish before farm
    ({"main_issues": ["xyz"]}, "General"),
])
def test_category_synthetic(regional_context, want):
    raw = {} if regional_context is None else {"regional_context": regional_context}
    assert C.determine_category(raw) == want


# ---- regional-sea label, complexity (§4) --------------------------------------

def test_regional_sea_label():
    assert C.regional_sea_label("north_sea", {}) == get_regional_seas()["north_sea"]["name"]
    assert C.regional_sea_label("north_sea", {}) == "North Sea"
    assert C.regional_sea_label("kelp_coast", {}) == "Kelp Coast"          # unknown slug
    assert C.regional_sea_label("", {"regional_context": {"region": "Caribbean Sea"}}) \
        == "Caribbean Sea"
    assert C.regional_sea_label("", {"regional_context": {"region": "  "}}) == ""
    assert C.regional_sea_label("", {"regional_context": {"region": ["x"]}}) == ""
    assert C.regional_sea_label("", {}) == ""


@pytest.mark.parametrize("raw,want", [
    ({}, "simple"), ({"complexity": None}, "simple"), ({"complexity": ""}, "simple"),
    ({"complexity": "complex"}, "complex"), ({"complexity": "moderate"}, "moderate"),
])
def test_complexity(raw, want):
    assert C.complexity_of(raw) == want


# ---- build (§3.3 steps 2-5) ---------------------------------------------------

def _build() -> dict[str, bytes]:
    return C.build_outputs(RAW, r_tag="v1.31.0", r_commit="4b53b7d")[0]


def test_build_is_deterministic_lf_and_newline_terminated():
    a, b = _build(), _build()
    assert a == b
    assert set(a) == {f"{C.OUT_DIR}/{f}" for f in C.TEMPLATE_FILES} | {C.CATALOGUE_PATH}
    for data in a.values():
        assert data.endswith(b"}\n") and b"\r" not in data
    cat = a[C.CATALOGUE_PATH]          # spec §3.3 step 5: indent=2, ensure_ascii=False
    assert cat == (json.dumps(json.loads(cat), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    # The 7 real names are pure ASCII, so only a non-ASCII name can tell the two settings apart.
    raw = {f: json.loads(json.dumps(r)) for f, r in RAW.items()}
    raw["Aquaculture_SES_Template.json"]["template_name"] = "Ålands skärgård"
    cat = C.build_outputs(raw, r_tag="v1.31.0", r_commit="4b53b7d")[0][C.CATALOGUE_PATH]
    assert "Ålands skärgård (MarineSABRES)".encode("utf-8") in cat and b"\\u00c5" not in cat


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_shipped_project_metadata(fname):
    md = json.loads(_build()[f"{C.OUT_DIR}/{fname}"])["metadata"]
    raw = RAW[fname]
    assert md["name"] == raw["template_name"] + " (MarineSABRES)"
    assert md["modified_at"] == md["created_at"] == raw["metadata"]["created_date"]
    assert md["min_sespy_version"] == "1.15.0"        # schema floor, not the running version
    assert md["origin"] == "r_template"
    assert md["ecosystem_type"] == ""
    assert md["regional_sea"] == ((raw.get("regional_context") or {}).get("regional_sea") or "")


def test_catalogue_shape():
    cat = json.loads(_build()[C.CATALOGUE_PATH])
    assert (cat["r_tag"], cat["r_commit"]) == ("v1.31.0", "4b53b7d")
    rows = cat["templates"]
    assert [r["name"] for r in rows] == sorted((r["name"] for r in rows), key=str.casefold)
    assert rows[0]["name"] == CARIBBEAN and rows[0]["element_count"] == 78
    for r in rows:
        assert tuple(r) == C.CATALOGUE_KEYS
        for k in C.ALWAYS_NON_EMPTY:
            assert isinstance(r[k], str) and r[k], (r["file"], k)
        assert r["element_count"] > 0 and r["connection_count"] > 0
    by_stem = {r["file"][: -len("_SES_Template.json")]: r for r in rows}
    for s, r in by_stem.items():                                  # §4: straight from R
        raw = RAW[f"{s}_SES_Template.json"]
        assert r["description"] == raw["template_description"], s
        assert r["version"] == str(raw["metadata"]["version"]), s
        assert r["source"] == str(raw["metadata"].get("source") or ""), s
    assert {s: r["category"] for s, r in by_stem.items()} == EXPECTED_CATEGORY
    assert by_stem["Caribbean"]["regional_sea_label"] == "Caribbean Sea"
    assert by_stem["OffshoreWind"]["regional_sea_label"] == "North Sea"
    assert by_stem["OffshoreWind"]["complexity"] == "complex"
    assert [s for s, r in by_stem.items() if r["usage_notes"]] == ["Caribbean"]
    assert [s for s, r in by_stem.items() if r["element_count"] == 23] == ["OffshoreWind"]
    assert by_stem["Aquaculture"]["name"] == "Coastal Lagoon (MarineSABRES)"
    assert sum(r["connection_count"] for r in rows) == 320


def test_catalogue_sort_is_case_insensitive():
    raw = {f: json.loads(json.dumps(r)) for f, r in RAW.items()}
    raw["Aquaculture_SES_Template.json"]["template_name"] = "coastal lagoon"
    cat = json.loads(C.build_outputs(raw, r_tag="v1.31.0", r_commit="4b53b7d")[0][C.CATALOGUE_PATH])
    # A case-sensitive sort would put "coastal" after "Tourism".
    assert [r["name"] for r in cat["templates"]][2] == "coastal lagoon (MarineSABRES)"


def test_render_block_golden():
    files = {"tests/parity/r_templates/b.json": "2" * 64, "tests/parity/r_rules/a.R": "1" * 64}
    assert C.render_block("v1.31.0", "4b53b7d", files, []) == (
        "- **R release:** MarineSABRES_SES_Shiny **v1.31.0**, commit `4b53b7d`.\n"
        "\n"
        "| File | Hash |\n"
        "|---|---|\n"
        f"| `tests/parity/r_rules/a.R` | `{'1' * 64}` |\n"
        f"| `tests/parity/r_templates/b.json` | `{'2' * 64}` |\n"
        "\n"
        "**Accepted sync warnings:** none.")
    accepted = [{"template": "Tourism_SES_Template", "kind": "off_rule_link",
                 "from": "GB001", "to": "A001"},
                {"template": "Tourism_SES_Template", "kind": "type_mismatch",
                 "text": "connections[0] x"}]
    assert C.render_block("v1.31.0", "4b53b7d", files, accepted).endswith(
        "\n\n**Accepted sync warnings:**\n"
        "- Tourism_SES_Template: off_rule_link GB001 -> A001\n"
        "- Tourism_SES_Template: type_mismatch connections[0] x")


def test_warning_sort_key_literal_order():
    a = {"template": "A", "kind": "type_mismatch", "text": "z"}
    b = {"template": "B", "kind": "off_rule_link", "from": "X", "to": "Y"}
    c = {"template": "B", "kind": "off_rule_link"}                 # missing from/to sort as ""
    d = {"template": "B", "kind": "off_rule_link", "from": "X", "to": "W"}
    e = {"template": "B", "kind": "type_mismatch", "text": "a"}
    assert sorted([e, b, d, c, a], key=C.warning_sort_key) == [a, c, d, b, e]


# ---- fixture mode (§3.1, §3.3 step 7) -----------------------------------------

def test_fixture_mode_writes_projects_catalogue_and_translations(tmp_path):
    root = _tree(tmp_path)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 0, res.lines
    changed = {p.relative_to(root).as_posix() for p, b in _snap(root).items()
               if before.get(p) != b}
    vendored = {f"{C.VENDORED_DIR}/{s}.json" for s in C.TRANSLATION_SUBSETS}
    assert changed == {f"{C.OUT_DIR}/{f}" for f in C.TEMPLATE_FILES} | {C.CATALOGUE_PATH} | vendored
    pin = _pin(root)
    cat = json.loads((root / C.CATALOGUE_PATH).read_bytes())
    assert (cat["r_tag"], cat["r_commit"]) == (pin["r_tag"], pin["r_commit"])
    for p in [*(root / MS).glob("*.json"), *(root / C.VENDORED_DIR).glob("*.json")]:
        assert b"\r\n" not in p.read_bytes()                  # LF on disk
    assert sum(line.startswith("wrote ") for line in res.lines) == 8 + len(vendored)


def test_check_passes_on_a_crlf_copy(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    for p in (root / MS).glob("*.json"):
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 0, res.lines


def test_check_reports_drift_and_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    _edit_json(root / MS / "Tourism_SES_Template.json",
               lambda d: d["metadata"].update(name="edited"))
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 1
    assert res.lines == [f"differs: {C.OUT_DIR}/Tourism_SES_Template.json"]
    assert _snap(root) == before


def test_check_reports_missing_outputs(tmp_path):
    res = C.sync(repo_root=_tree(tmp_path), from_fixtures=True, check=True)
    # 7 projects + catalogue + the vendored translation subsets
    assert res.code == 1 and len(res.lines) == 8 + len(C.TRANSLATION_SUBSETS)


def test_value_error_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Tourism_SES_Template.json",
               lambda d: d["dapsiwrm_framework"]["drivers"].append(
                   dict(d["dapsiwrm_framework"]["drivers"][0])))     # duplicate id
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and _snap(root) == before
    assert "Tourism_SES_Template" in res.lines[-1] and "duplicate element id" in res.lines[-1]


@pytest.mark.parametrize("change,line", [
    (lambda d: d["metadata"].update(version=""), "Fisheries_SES_Template.json: empty version"),
    (lambda d: d.update(template_description=""), "Fisheries_SES_Template.json: empty description"),
    (lambda d: d.update(connections=[]), "Fisheries_SES_Template.json: connection_count is 0"),
])
def test_empty_always_non_empty_field_writes_nothing(tmp_path, change, line):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Fisheries_SES_Template.json", change)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and line in res.lines and _snap(root) == before


def test_off_rule_link_in_fixture_mode_fails_and_cannot_be_accepted(tmp_path):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Tourism_SES_Template.json", _add_off_rule)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and _snap(root) == before
    assert any(line.startswith("warning (unaccepted): Tourism_SES_Template: off_rule_link ")
               for line in res.lines)
    res = C.sync(repo_root=root, from_fixtures=True, accept_warnings=True)
    assert res.code == 1 and _snap(root) == before


@pytest.mark.parametrize("pin", [
    {"files": {}}, {"r_tag": "", "r_commit": "x"}, [],
    {"r_tag": "v1.31.0", "r_commit": "4b53b7d", "files": []},
    {"r_tag": "v1.31.0", "r_commit": "4b53b7d", "files": {}, "accepted_warnings": "x"},
])
def test_malformed_pin_exits_1_and_writes_nothing(tmp_path, pin):
    root = _tree(tmp_path)
    (root / C.PIN_PATH).write_bytes(json.dumps(pin).encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and "r_tag and r_commit" in res.lines[0] and _snap(root) == before


def test_non_object_template_exits_1_and_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    (root / "tests/parity/r_templates/Tourism_SES_Template.json").write_bytes(b"[1, 2]")
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and res.lines[-1].startswith("conversion failed: ") and _snap(root) == before


@pytest.mark.parametrize("kwargs", [
    {},                                                    # neither r_root nor fixtures
    {"from_fixtures": True, "accept_warnings": True},
    {"from_fixtures": True, "rev": "v1.31.0"},
])
def test_argument_errors_write_nothing(tmp_path, kwargs):
    root = _tree(tmp_path)
    before = _snap(root)
    assert C.sync(repo_root=root, **kwargs).code == 1
    assert _snap(root) == before


# ---- git mode against a fake R repo (§3.1, §3.3, §8) --------------------------

def test_real_run_writes_everything_then_checks_clean(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    prose_before = _md_prose(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 0, res.lines
    pin = _pin(root)
    commit = _git(app, "rev-parse", "--short=7", "v1.31.0^{commit}").strip()
    assert (pin["r_tag"], pin["r_commit"]) == ("v1.31.0", commit)
    assert sorted(pin["files"]) == sorted(C.INPUTS.values()) and len(pin["files"]) == 18
    assert pin["accepted_warnings"] == []
    assert any(line.startswith("hash tests/parity/r_source/template_loader.R: ")
               for line in res.lines)
    assert (root / "tests/parity/r_source/template_loader.R").read_bytes() == LOADER_STUB
    # The block is exactly the generated text; the prose around it is untouched.
    assert _md_block(root) == "\n" + C.render_block("v1.31.0", commit, pin["files"], []) + "\n"
    assert _md_prose(root) == prose_before
    md = (root / C.MD_PATH).read_text(encoding="utf-8")
    assert set(re.findall(r"\b[0-9a-f]{64}\b", md)) == set(pin["files"].values())
    assert "**Accepted sync warnings:** none." in _md_block(root)
    for rel in [C.PIN_PATH, C.MD_PATH, *C.INPUTS.values()]:
        assert b"\r\n" not in (root / rel).read_bytes(), rel
    # Clean afterwards: explicit rev, rev from the new pin, and fixture mode.
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True).code == 0
    assert C.sync(repo_root=root, r_root=app, check=True).code == 0
    assert C.sync(repo_root=root, from_fixtures=True, check=True).code == 0


def test_check_in_git_mode_passes_on_a_crlf_copy(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0").code == 0
    for p in root.rglob("*"):
        if p.is_file():
            p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True)
    assert res.code == 0, res.lines


@pytest.mark.parametrize("rev", ["main", "HEAD", "v1.31", "1.31.0", "v1.31.0-rc1", "v1.31.0\n", ""])
def test_rev_must_be_a_release_tag(tmp_path, r_app, rev):
    root, app = _tree(tmp_path), r_app
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev=rev)
    assert res.code == 1 and "release tag" in res.lines[0] and _snap(root) == before


def test_unknown_tag_and_missing_path_write_nothing(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    before = _snap(root)
    assert C.sync(repo_root=root, r_root=app, rev="v9.9.9").code == 1
    _git(app.parent, "rm", "-q", "MarineSABRES_SES_Shiny/data/Tourism_SES_Template.json")
    _git(app.parent, "commit", "-qm", "drop Tourism")
    _git(app.parent, "tag", "v1.32.0")
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and "data/Tourism_SES_Template.json" in res.lines[0]
    assert _snap(root) == before


@pytest.mark.parametrize("md", [
    "no markers\n",
    f"{C.BEGIN}\n{C.BEGIN}\n{C.END}\n",
    f"{C.BEGIN}\n{C.END}\n{C.END}\n",
    f"{C.END}\n{C.BEGIN}\n",
    None,                                               # R_SYNC.md missing
])
def test_markers_missing_or_duplicated_write_nothing(tmp_path, r_app, md):
    root, app = _tree(tmp_path), r_app
    if md is None:
        (root / C.MD_PATH).unlink()
    else:
        (root / C.MD_PATH).write_bytes(md.encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 1 and _snap(root) == before


def test_off_rule_link_needs_accept_warnings_and_is_persisted(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, _add_off_rule))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    gb, act = fw["goods_benefits"][0]["id"], fw["activities"][0]["id"]
    entry = {"template": "Tourism_SES_Template", "kind": "off_rule_link", "from": gb, "to": act}

    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and _snap(root) == before
    assert f"warning (unaccepted): Tourism_SES_Template: off_rule_link {gb} -> {act}" in res.lines

    fixture = "tests/parity/r_templates/Tourism_SES_Template.json"
    old_hash = _pin(root)["files"][fixture]
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    assert _pin(root)["accepted_warnings"] == [entry]
    new_hash = _pin(root)["files"][fixture]
    assert old_hash != new_hash
    assert f"hash {fixture}: {old_hash} -> {new_hash}" in res.lines      # §3.1 old -> new
    assert _md_block(root).endswith(
        f"**Accepted sync warnings:**\n- Tourism_SES_Template: off_rule_link {gb} -> {act}\n")
    # Accepted from now on, without the flag, in both modes.
    assert C.sync(repo_root=root, r_root=app, check=True).code == 0
    assert C.sync(repo_root=root, from_fixtures=True, check=True).code == 0
    assert C.sync(repo_root=root, r_root=app, rev="v1.32.0").code == 0


def test_type_mismatch_entries_and_sort_order(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    fisheries = app / "data" / "Fisheries_SES_Template.json"
    tourism = app / "data" / "Tourism_SES_Template.json"

    def edit(a):
        _edit_json(tourism, _add_off_rule)
        _edit_json(fisheries, lambda d: d["connections"][0].update(to_type="welfare"))
    _r_release(app, "v1.32.0", edit)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    acc = _pin(root)["accepted_warnings"]
    assert [(w["template"], w["kind"]) for w in acc] == [
        ("Fisheries_SES_Template", "type_mismatch"),
        ("Tourism_SES_Template", "off_rule_link")]
    assert set(acc[0]) == {"template", "kind", "text"}
    assert acc[0]["text"].startswith("connections[0] ") and "to_type 'welfare'" in acc[0]["text"]


def test_persisted_warnings_are_sorted_not_in_production_order(tmp_path):
    # The mapper reports in connection order: GB002 first, then GB001, then
    # the type mismatch on connections[0]. The pin must hold the
    # (template, kind, from, to, text) order instead.
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"

    def edit_tourism(d):
        fw = d["dapsiwrm_framework"]
        for gb in (fw["goods_benefits"][1], fw["goods_benefits"][0]):
            d["connections"].append({"from_id": gb["id"], "to_id": fw["activities"][0]["id"],
                                     "polarity": "+"})
        d["connections"][0]["to_type"] = "welfare"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, edit_tourism))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    gb1, gb2 = fw["goods_benefits"][0]["id"], fw["goods_benefits"][1]["id"]
    act = fw["activities"][0]["id"]
    assert gb1 < gb2
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    acc = _pin(root)["accepted_warnings"]
    assert [(w["kind"], w.get("from"), w.get("to")) for w in acc] == [
        ("off_rule_link", gb1, act), ("off_rule_link", gb2, act), ("type_mismatch", None, None)]


@pytest.mark.parametrize("variant", ["other_template", "other_to", "extra_key"])
def test_accepted_warning_matches_only_on_every_field(tmp_path, variant):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, _add_off_rule))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    entry = {"template": "Tourism_SES_Template", "kind": "off_rule_link",
             "from": fw["goods_benefits"][0]["id"], "to": fw["activities"][0]["id"]}
    if variant == "other_template":
        entry["template"] = "Fisheries_SES_Template"       # ids like A001 repeat across templates
    elif variant == "other_to":
        entry["to"] = fw["activities"][1]["id"]
    else:
        entry["note"] = "x"
    pin = _pin(root)
    pin["accepted_warnings"] = [entry]
    (root / C.PIN_PATH).write_bytes(json.dumps(pin, indent=2).encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and _snap(root) == before


def test_accepted_warning_that_no_longer_occurs_is_dropped(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0").code == 0     # clean baseline
    pin = _pin(root)
    pin["accepted_warnings"] = [{"template": "Tourism_SES_Template", "kind": "off_rule_link",
                                 "from": "GB01", "to": "A01"}]
    (root / C.PIN_PATH).write_bytes(json.dumps(pin, indent=2).encode("utf-8"))
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True)
    assert res.code == 1 and res.lines == [f"differs: {C.PIN_PATH}"]      # only the stale entry
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 0, res.lines
    assert _pin(root)["accepted_warnings"] == []
    assert "**Accepted sync warnings:** none." in _md_block(root)


# ---- CLI wrapper (§3.1) --------------------------------------------------------

def test_cli_passes_arguments_and_the_repo_root(monkeypatch, capsys):
    from scripts import sync_r_templates as cli
    seen = {}

    def fake_sync(**kw):
        seen.update(kw)
        return C.SyncResult(3, ["line one", "line two"])
    monkeypatch.setattr(cli, "sync", fake_sync)
    code = cli.main(["--r-root", "R", "--rev", "v1.31.0", "--check", "--accept-warnings"])
    assert code == 3 and capsys.readouterr().out == "line one\nline two\n"
    assert seen == {"repo_root": ROOT, "r_root": Path("R"), "rev": "v1.31.0",
                    "from_fixtures": False, "check": True, "accept_warnings": True}


def test_cli_runs_as_a_module_from_the_repo_root():
    # Refused before any read or write; --check as a second guard, so even a
    # broken refusal can never write into the real tree.
    r = subprocess.run([sys.executable, "-m", "scripts.sync_r_templates",
                        "--from-fixtures", "--accept-warnings", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "--accept-warnings needs --r-root" in r.stdout


def test_catalogue_module_imports_without_shiny():
    code = "import sys, sespy.r_template_catalogue; sys.exit(1 if 'shiny' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0


# ---- the shipped tree (spec §1 done-when, §8; needs the first real sync) -------

SHIPPED = ROOT / C.OUT_DIR


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_drift_guard_shipped_project_equals_the_conversion(fname):
    from sespy.persistent_storage import load_project
    from sespy.r_template_mapper import convert_r_template
    project, _ = convert_r_template(RAW[fname], key=fname[: -len(".json")])
    raw_shipped = json.loads((SHIPPED / fname).read_bytes().decode("utf-8-sig"))
    assert raw_shipped["isa_data"] == project.to_dict()["isa_data"]
    shipped = load_project(SHIPPED / fname)
    assert shipped.isa_data == project.isa_data
    # Field by field, never Project ==: a round trip stamps min_sespy_version.
    want = project.metadata
    got = shipped.metadata
    assert got.name == want.name + " (MarineSABRES)"
    for f in ("description", "regional_sea", "ecosystem_type", "origin",
              "r_template_version", "created_at"):
        assert getattr(got, f) == getattr(want, f), f


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_raw_r_links_and_signs(fname):
    # Independent of the mapper: the shipped links against R's own JSON.
    raw_links = RAW[fname]["connections"]
    want = {(str(c["from_id"]), str(c["to_id"])): c.get("polarity") or "+" for c in raw_links}
    shipped = json.loads((SHIPPED / fname).read_bytes().decode("utf-8-sig"))["isa_data"]
    got = {(c["source"], c["target"]): c["polarity"] for c in shipped["connections"]}
    assert len(shipped["connections"]) == len(raw_links) == len(want)
    assert got == want


def test_shipped_catalogue_equals_a_fresh_build(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    fresh = json.loads((root / C.CATALOGUE_PATH).read_bytes())
    assert json.loads((ROOT / C.CATALOGUE_PATH).read_bytes().decode("utf-8-sig")) == fresh
    assert (fresh["r_tag"], fresh["r_commit"]) == ("v1.33.0", "4017feb")


def test_committed_tree_has_no_drift():
    # --check never writes, so this is safe on the real working tree (which is
    # CRLF on a core.autocrlf=true checkout).
    res = C.sync(repo_root=ROOT, from_fixtures=True, check=True)
    assert res.code == 0, res.lines


def test_committed_tree_has_no_drift_as_crlf(tmp_path):
    root = _tree(tmp_path)
    shutil.copytree(SHIPPED, root / C.OUT_DIR)
    shutil.copytree(ROOT / C.VENDORED_DIR, root / C.VENDORED_DIR)     # P1b outputs
    for p in [*(root / C.OUT_DIR).glob("*.json"), *(root / C.VENDORED_DIR).glob("*.json")]:
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 0, res.lines


def test_shipped_templates_are_schema_8():
    # P1b: every shipped template is re-stamped by the v1.33.0 sync.
    for fname in C.TEMPLATE_FILES:
        md = json.loads((SHIPPED / fname).read_bytes().decode("utf-8-sig"))["metadata"]
        assert (md["schema_version"], md["min_sespy_version"]) == (8, "1.15.0"), fname


# ---- vendored R translation subsets (P1b spec §7) ---------------------------------

VENDORED = ROOT / C.VENDORED_DIR
TR_FIX = PARITY / "r_translations"


def _vendored(stem: str) -> dict:
    return json.loads((VENDORED / f"{stem}.json").read_bytes().decode("utf-8-sig"))["translation"]


def test_vendored_translations_match_fixture_subsets():
    from sespy.i18n import SUPPORTED_LANGUAGES
    for stem, prefixes in C.TRANSLATION_SUBSETS.items():
        fix = json.loads((TR_FIX / f"{stem}.json").read_bytes().decode("utf-8-sig"))
        want = {k: v for k, v in fix["translation"].items()
                if not prefixes or k.startswith(prefixes)}
        got = json.loads((VENDORED / f"{stem}.json").read_bytes().decode("utf-8-sig"))
        assert list(got) == ["languages", "translation"], stem
        assert got["languages"] == fix["languages"], stem
        assert list(got["translation"]) == list(want), stem        # R's key order
        assert got["translation"] == want, stem                    # texts equal
        for key, entry in got["translation"].items():
            assert all(isinstance(entry.get(lg), str) and entry[lg].strip()
                       for lg in SUPPORTED_LANGUAGES), (stem, key)


def test_vendored_translation_key_counts():
    assert {s: len(_vendored(s)) for s in C.TRANSLATION_SUBSETS} == {
        "response_measures": 142, "response_governance": 26, "wp5_vocabulary": 47,
        "wp5_scenarios": 6, "wp5_governance": 8, "indicator_registry": 10}


def test_vendored_files_are_newline_terminated_json():
    # The sync writes LF; a core.autocrlf=true checkout may turn it into CRLF.
    for stem in C.TRANSLATION_SUBSETS:
        data = (VENDORED / f"{stem}.json").read_bytes().replace(b"\r\n", b"\n")
        assert data.endswith(b"}\n") and b"\r" not in data, stem


def test_translation_prefix_that_selects_nothing_writes_nothing(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setitem(C.TRANSLATION_SUBSETS, "wp5_scenarios", ("modules.wp5_scenarios.no_such.",))
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and _snap(root) == before
    assert any("modules.wp5_scenarios.no_such." in line for line in res.lines), res.lines


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_shipped_project_loads_without_off_rule_warnings(fname, caplog):
    # Spec §7: 0 off-rule links today, so validation logs nothing on sespy.link_rules.
    import logging

    from sespy.persistent_storage import load_project
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        project = load_project(SHIPPED / fname)
    assert project.newer_build == {}
    assert not [r for r in caplog.records if r.name == "sespy.link_rules"]
