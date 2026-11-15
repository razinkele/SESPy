"""K1b Task 7: the wizard saves R's strength/confidence, shows them, and
records the connection-DB read for provenance."""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

from sespy import i18n, r_kb
from sespy.autosave import read_autosave, write_autosave
from sespy.data_structure import Connection, ConnectionSuggestion, Element, IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.modules.ai_isa_wizard import ai_isa_wizard_server, _render_suggestions_table
from sespy.persistent_storage import load_project, project_to_bytes, save_project_atomic

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
LANGS = ("en", "es", "fr", "de", "lt", "pt", "it", "no", "el")
KB_NAMES = {"drivers": "Food security", "activities": "Commercial fishing",
            "pressures": "Overfishing", "states": "Fish stock decline",
            "impacts": "Reduced fish provisioning", "welfare": "Income",
            "responses": "Fishing quotas"}
NO_MATCH = {k: f"Zzq{i} xvw" for i, k in enumerate(KB_NAMES)}
FREEFORM = list(KB_NAMES)


@contextmanager
def _wizard(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    monkeypatch.setattr(shiny.ui, "notification_show", lambda *a, **kw: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    holder: list = []

    def server(input, output, session):
        pd = reactive.value(Project.from_isa(IsaData()))
        rr = reactive.value(frozenset())
        holder.append((pd, rr))
        ai_isa_wizard_server("wizard", project_data=pd, event_bus=create_event_bus(),
                             translator=TR, reference_reads=rr)

    with test_server(server) as ts:
        yield ts.make_scope("wizard"), holder


def _click_factory(scope):
    clicks: dict[str, int] = {}

    def click(btn):
        if btn not in clicks:
            scope.set_inputs(**{btn: 0})
            clicks[btn] = 0
        clicks[btn] += 1
        scope.set_inputs(**{btn: clicks[btn]})
    return click


def _drive(scope, names):
    click = _click_factory(scope)
    click("wizard_start")
    answers = {0: ("answer_regional_sea", "baltic"), 1: ("answer_ecosystem_type", "Open coast"),
               2: ("answer_countries", ["LT"]), 3: ("answer_main_issue", ["Eutrophication"])}
    for step in range(11):
        if step in answers:
            scope.set_inputs(**{answers[step][0]: answers[step][1]})
        else:
            target = FREEFORM[step - 4]
            gen = scope.get_export("gen").value[target]
            scope.set_inputs(**{f"entry_{gen}_{target}_0": names[target]})
        click("wizard_next")
    return scope.get_output("wizard_step_render").value["html"], click


def _rows(html):
    """[(src, tgt, pol, strength, confidence)] from the rule-based table."""
    out = []
    for tr in re.findall(r'<tr[^>]*class="wiz-sugg"[^>]*>.*?</tr>', html, re.S):
        src = re.search(r'data-from-id="([^"]+)"', tr).group(1)
        tgt = re.search(r'data-to-id="([^"]+)"', tr).group(1)
        pol = re.search(r'data-pol="([+-])"', tr).group(1)
        st = re.search(r'class="wiz-str"[^>]*>([^<]*)<', tr).group(1)
        cf = re.search(r'class="wiz-conf"[^>]*>([^<]*)<', tr).group(1)
        out.append((src, tgt, pol, st, int(cf)))
    return out


def _accept_all(scope, html):
    n = len(set(re.findall(r'id="wizard-accept_sp3_(\d+)"', html)))
    scope.set_inputs(**{f"accept_sp3_{i}": True for i in range(n)})
    return n


def _conns(holder):
    with reactive.isolate():
        return holder[0][0].get().isa_data.connections


def test_accept_writes_strength_and_confidence(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        html, click = _drive(scope, KB_NAMES)
        rows = _rows(html)
        assert rows and any(r[3] != "medium" or r[4] != 3 for r in rows)
        _accept_all(scope, html)
        click("wizard_finish")
        saved = {(c.source, c.target, c.polarity): (c.strength, c.confidence)
                 for c in _conns(holder)}
        assert saved == {(s, t, p): (st, cf) for s, t, p, st, cf in rows}


def test_flip_and_reverse_keep_strength_confidence(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        html, click = _drive(scope, KB_NAMES)
        src, tgt, pol, st, cf = _rows(html)[0]
        scope.set_inputs(**{f"accept_sp3_{i}": False for i in range(len(_rows(html)))})
        scope.set_inputs(accept_sp3_0=True, pol_sp3_0=(pol != "+"), swap_sp3_0=True)
        click("wizard_finish")
        (c,) = _conns(holder)
        assert (c.source, c.target) == (tgt, src)
        assert c.polarity == ("-" if pol == "+" else "+")
        assert (c.strength, c.confidence) == (st, cf)


def test_step11_records_connection_db_read(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        _drive(scope, KB_NAMES)
        with reactive.isolate():
            reads = holder[0][1].get()
        assert r_kb.CONNECTION_DB_NAME in reads


def _headers(html):
    return [re.sub(r"<[^>]+>", "", h).strip()
            for h in re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)]


def test_rule_table_shows_strength_and_confidence_columns(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    sugg = [ConnectionSuggestion("D001", "A001", "+", 0.8, "r", "strong", 4)]
    html = str(_render_suggestions_table(sugg, prefix="accept_sp3_", title="T",
                                         rule_based=True))
    assert _headers(html) == ["#", "Source", "Target", "Polarity", "Reverse",
                              "Strength", "Confidence", "Rationale", "Accept"]
    assert 'class="wiz-str"' in html and ">strong<" in html


def test_claude_table_labels_score(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    sugg = [ConnectionSuggestion("D001", "A001", "+", 0.8, "r")]
    html = str(_render_suggestions_table(sugg, prefix="accept_sp4_", title="T"))
    assert _headers(html) == ["#", "Source", "Target", "Polarity", "Reverse",
                              "Score", "Rationale", "Accept"]
    assert "0.80" in html


def test_no_rule_rows_shows_message_and_finish_works(monkeypatch):
    with _wizard(monkeypatch) as (scope, holder):
        html, click = _drive(scope, NO_MATCH)
        assert not _rows(html)
        assert TR.t("wizard.no_suggestions") in html.replace("&amp;", "&")
        assert "SP3" not in html and "SP4" not in html
        click("wizard_finish")
        assert _conns(holder) == []
        with reactive.isolate():
            assert len(holder[0][0].get().isa_data.elements) == 7


def test_accepted_strength_confidence_round_trip(tmp_path, monkeypatch):
    from sespy import autosave
    monkeypatch.setattr(autosave, "private_subdir", lambda name: tmp_path)
    conn = Connection(source="D001", target="A001", polarity="+",
                      strength="strong", confidence=4)
    els = [Element("D001", "Food security", "Drivers"),
           Element("A001", "Commercial fishing", "Activities")]
    proj = Project.from_isa(IsaData(elements=els, connections=[conn]))
    p = tmp_path / "p.json"
    save_project_atomic(proj, p)
    (c,) = load_project(p).isa_data.connections
    assert (c.strength, c.confidence) == ("strong", 4)
    raw = json.loads(project_to_bytes(proj))
    assert (raw["isa_data"]["connections"][0]["strength"],
            raw["isa_data"]["connections"][0]["confidence"]) == ("strong", 4)
    write_autosave(proj, token="a" * 32)
    back = read_autosave(token="a" * 32)
    assert back is not None
    (c,) = back.isa_data.connections
    assert (c.strength, c.confidence) == ("strong", 4)
    # a v1.16 file (connection without strength/confidence) -> medium / 3
    raw["isa_data"]["connections"][0].pop("strength")
    raw["isa_data"]["connections"][0].pop("confidence")
    old = tmp_path / "old.json"
    old.write_text(json.dumps(raw), encoding="utf-8")
    (c,) = load_project(old).isa_data.connections
    assert (c.strength, c.confidence) == ("medium", 3)


@pytest.mark.parametrize("key", ["wizard.col_strength", "wizard.col_confidence",
                                 "wizard.col_score", "wizard.no_suggestions",
                                 "wizard.confidence_help_rules"])
def test_keys_cover_all_languages(key):
    tr = load_translations(ROOT / "sespy" / "translations")
    for lang in LANGS:
        assert tr[key].get(lang, "").strip(), (key, lang)
