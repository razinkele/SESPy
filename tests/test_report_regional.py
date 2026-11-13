"""K1 Task 14: the Regional Context section in the HTML, PDF and Word reports,
and the include toggle on the Export Report panel."""
from __future__ import annotations

import io
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
from markupsafe import escape
from shiny import reactive
from shiny.testserver import test_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent / "parity"))

from k1_fixtures import load_k1_fixture  # noqa: E402

import sespy.i18n  # noqa: E402
import sespy.report as report  # noqa: E402
from sespy import data_structure as ds  # noqa: E402
from sespy import kb_report  # noqa: E402
from sespy.event_bus import create_event_bus  # noqa: E402
from sespy.kb_report import HEADINGS  # noqa: E402
from sespy.modules import report_export as mod  # noqa: E402
from sespy.r_kb import VENDORED  # noqa: E402

REPORT = load_k1_fixture("report")
SAMPLE = ROOT / "data" / "sample_ses.json"
GOLDEN = ROOT / "tests" / "fixtures" / "report_default_golden.html"
BOTH_FILES = {"ses_knowledge_db.json", "country_governance_db.json"}


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    # app.py (imported by other tests) installs a process-wide translator.
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: None)


def _project(case: str, *, sea: str | None = None, eco: str | None = None) -> ds.Project:
    c = REPORT[case]
    elements, connections = [], []
    for i, (a, b) in enumerate(c["edges"]):
        elements += [ds.Element(f"a{i}", a, "Pressures"), ds.Element(f"b{i}", b, "States")]
        connections.append(ds.Connection(f"a{i}", f"b{i}"))
    proj = ds.Project.from_isa(ds.IsaData(elements=elements, connections=connections),
                               name="Regional test")
    md = proj.metadata
    md.regional_sea = c["sea"] if sea is None else sea
    md.ecosystem_type = c["ecosystem"] if eco is None else eco
    return proj


def _in_order(html: str, needles: list[str]) -> None:
    pos = 0
    for n in needles:
        at = html.find(n, pos)
        assert at >= 0, f"{n!r} missing or out of order after offset {pos}"
        pos = at + len(n)


def _render(proj, **kw):
    return report.render_html(proj, snapshot=VENDORED, include_regional_context=True, **kw)


def test_html_section_present_baltic():
    html = _render(_project("baltic_lagoon"))
    rc = kb_report.build_regional_context(
        VENDORED.kb(), VENDORED.governance(), "baltic", "Coastal lagoon",
        [tuple(e) for e in REPORT["baltic_lagoon"]["edges"]])
    assert rc is not None and rc.evidence
    needles = [f">{escape(h)}<" for h in HEADINGS]
    # Every heading, in document order, at R's shifted levels.
    _in_order(html, [f"<h2>{HEADINGS[0]}</h2>", f"<h3>{HEADINGS[1]}</h3>",
                     f"<h4>{HEADINGS[2]}</h4>", f"<h4>{HEADINGS[3]}</h4>",
                     f"<h4>{HEADINGS[4]}</h4>", f"<h5>{HEADINGS[5]}</h5>"])
    assert all(n in html for n in needles)
    # Every evidence row, in order, then the report's own Summary after it.
    _in_order(html, [str(escape(r.connection)) for r in rc.evidence] + ["<h2>Summary</h2>"])
    assert html.index(HEADINGS[0]) < html.index("<h2>Summary</h2>")
    assert "Temporal Lag" in html and "Reversibility" in html


def test_html_escapes_user_text():
    proj = _project("baltic_lagoon")
    proj.isa_data.elements[0].label = "Agricultural drainage into lagoon <script>x</script>"
    html = _render(proj)
    assert "<script>x</script>" not in html


def test_irish_sea_governance_only_html():
    html = _render(_project("irish_sea"))
    assert f"<h2>{HEADINGS[0]}</h2>" in html
    _in_order(html, [f"<h4>{HEADINGS[4]}</h4>", f"<h5>{HEADINGS[5]}</h5>"])
    for h in HEADINGS[1:4]:
        assert h not in html


@pytest.mark.parametrize("sea,eco", [("", None), (None, ""), ("atlantis", None)])
def test_section_absent_when_sea_empty_or_unknown(sea, eco):
    # `atlantis` is an unknown slug: no KB context and no governance entry.
    proj = _project("baltic_lagoon", sea=sea, eco=eco)
    assert report.regional_context_for(proj, VENDORED) is None
    assert HEADINGS[0] not in _render(proj)


def test_section_absent_when_sea_empty():
    assert HEADINGS[0] not in _render(_project("baltic_lagoon", sea=""))


def test_section_absent_for_unknown_slug():
    assert HEADINGS[0] not in _render(_project("baltic_lagoon", sea="atlantis"))


def test_no_snapshot_no_section():
    proj = _project("baltic_lagoon")
    assert report.regional_context_for(proj, None) is None
    assert HEADINGS[0] not in report.render_html(proj, include_regional_context=True)
    assert HEADINGS[0] not in report.render_html(proj, snapshot=None,
                                                 include_regional_context=True)


def test_toggle_off_omits_section():
    html = report.render_html(_project("baltic_lagoon"), snapshot=VENDORED,
                              include_regional_context=False)
    assert HEADINGS[0] not in html


def test_defaults_keep_old_output(monkeypatch):
    class _Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 2, 3, 4)

    monkeypatch.setattr(report, "datetime", _Fixed)
    proj = ds.Project.from_isa(ds.load_sample(SAMPLE), name="Sample SES")
    # The golden predates the h4/h5 rules Task 14 adds to the stylesheet; those
    # two lines are the only permitted difference.
    golden = GOLDEN.read_text(encoding="utf-8")
    # `from_isa` stamps modified_at with the real clock; pin it to the golden's.
    proj.metadata.modified_at = re.search(r"Last modified (\S+)", golden).group(1)
    html = report.render_html(proj)
    css = [ln for ln in html.splitlines(keepends=True)
           if re.match(r"\s+h[45] \{ font-size", ln)]
    assert len(css) == 2
    for ln in css:
        html = html.replace(ln, "", 1)
    # Cycle enumeration (hence loop ids, order and path text) depends on hash order and
    # differs between processes, so compare the loops block as a multiset of lines
    # with the path cells blanked, and everything else exactly.
    block = re.compile(r"<h2>Feedback loops</h2>.*?(?=<h2>Top centrality</h2>)", re.S)
    path_cell = re.compile(r'(<td style="font-size: 9pt;">).*?(</td>)')
    assert block.search(html) and block.search(golden)

    def canon(doc):
        loops = sorted(path_cell.sub(r"\1\2", ln) for ln in block.search(doc).group(0).splitlines())
        return block.sub("", doc), loops

    assert canon(html) == canon(golden)


def test_generation_error_omits_section(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(report, "build_regional_context", boom)
    with caplog.at_level("WARNING", logger="sespy.report"):
        html = _render(_project("baltic_lagoon"))
    assert HEADINGS[0] not in html
    assert "<h2>Summary</h2>" in html
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_edge_ids_without_element_map_to_id(monkeypatch):
    seen = {}

    def spy(kb, gov, sea, eco, edges):
        seen["edges"] = edges
        return None

    monkeypatch.setattr(report, "build_regional_context", spy)
    proj = _project("baltic_lagoon")
    proj.isa_data.connections.append(ds.Connection("ghost_a", "b0"))
    report.regional_context_for(proj, VENDORED)
    assert seen["edges"][-1] == ("ghost_a", REPORT["baltic_lagoon"]["edges"][0][1])
    assert seen["edges"][0] == tuple(REPORT["baltic_lagoon"]["edges"][0])


def test_docx_has_heading_levels_and_table():
    from docx import Document

    proj = _project("baltic_lagoon")
    data = report.render_docx(proj, snapshot=VENDORED, include_regional_context=True)
    doc = Document(io.BytesIO(data))
    heads = [(p.style.name, p.text) for p in doc.paragraphs
             if p.style.name.startswith("Heading")]
    expected = [("Heading 2", HEADINGS[0]), ("Heading 3", HEADINGS[1]),
                ("Heading 4", HEADINGS[2]), ("Heading 4", HEADINGS[3]),
                ("Heading 4", HEADINGS[4]), ("Heading 5", HEADINGS[5])]
    assert [h for h in heads if h in expected] == expected
    tables = [t for t in doc.tables if len(t.columns) == 5]
    assert len(tables) == 1
    assert [c.text for c in tables[0].rows[0].cells] == [
        "Connection", "Rationale", "References", "Temporal Lag", "Reversibility"]
    first = REPORT["baltic_lagoon"]["edges"][0]
    assert tables[0].rows[1].cells[0].text == f"{first[0]} → {first[1]}"
    # Without the toggle the old document has none of it.
    plain = Document(io.BytesIO(report.render_docx(proj, snapshot=VENDORED)))
    assert all(HEADINGS[0] != p.text for p in plain.paragraphs)


def test_pdf_passes_kwargs_through(monkeypatch):
    seen = {}

    def fake_html(project, **kw):
        seen.update(kw)
        return "<html><body>x</body></html>"

    monkeypatch.setattr(report, "render_html", fake_html)
    report.render_pdf(_project("baltic_lagoon"), snapshot=VENDORED, include_regional_context=True)
    assert seen == {"snapshot": VENDORED, "include_regional_context": True}


# ---------------------------------------------------------------------------
# The panel: checkbox and preview, via shiny.testserver
# ---------------------------------------------------------------------------

def test_checkbox_default_true():
    html = str(mod.report_export_ui("report"))
    m = re.search(r'<input[^>]*id="report-include_regional_context"[^>]*>', html)
    assert m and "checked" in m.group(0)
    assert "Include Regional Context" in html


def _panel(proj, *, snapshot=VENDORED):
    holder: list = []

    def server(input, output, session):
        rr = reactive.value(frozenset())
        holder.append(rr)
        mod.report_export_server(
            "report", project_data=reactive.value(proj), event_bus=create_event_bus(),
            snapshot=snapshot, reference_reads=rr)

    return test_server(server), holder


def _preview(scope) -> str:
    return scope.get_output("report_preview").value["html"]


def test_preview_depends_on_toggle():
    ts_cm, _ = _panel(_project("baltic_lagoon"))
    with ts_cm as ts:
        s = ts.make_scope("report")
        s.set_inputs(include_regional_context=True)
        assert HEADINGS[0] in _preview(s)
        s.set_inputs(include_regional_context=False)
        assert HEADINGS[0] not in _preview(s)


def test_report_export_records_reads_only_when_generated():
    # Toggle off: nothing.
    cm, holder = _panel(_project("baltic_lagoon"))
    with cm as ts:
        s = ts.make_scope("report")
        s.set_inputs(include_regional_context=False)
        _preview(s)
        with reactive.isolate():
            assert holder[0].get() == frozenset()
    # Toggle on, sea empty: nothing.
    cm, holder = _panel(_project("baltic_lagoon", sea=""))
    with cm as ts:
        s = ts.make_scope("report")
        s.set_inputs(include_regional_context=True)
        _preview(s)
        with reactive.isolate():
            assert holder[0].get() == frozenset()
    # Toggle on and generated: both names, once.
    cm, holder = _panel(_project("baltic_lagoon"))
    with cm as ts:
        s = ts.make_scope("report")
        s.set_inputs(include_regional_context=True)
        _preview(s)
        with reactive.isolate():
            assert holder[0].get() == frozenset(BOTH_FILES)


def test_panel_without_snapshot_records_nothing():
    cm, holder = _panel(_project("baltic_lagoon"), snapshot=None)
    with cm as ts:
        s = ts.make_scope("report")
        s.set_inputs(include_regional_context=True)
        assert HEADINGS[0] not in _preview(s)
        with reactive.isolate():
            assert holder[0].get() == frozenset()
