"""App-layer i18n: the reactive Translator and the session resolver
(sespy.ui_i18n). The plain library side is tested in tests/test_i18n.py."""
from __future__ import annotations

from pathlib import Path

import pytest
from shiny import module
from shiny.testserver import test_server

import sespy.i18n
import sespy.ui_i18n as u
from sespy.ui_i18n import Translator, get_default, load_translations, set_default, t

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "sespy" / "translations"


@pytest.fixture(scope="module")
def translations() -> dict:
    return load_translations(TRANSLATIONS)


@pytest.fixture(autouse=True)
def _restore_default(monkeypatch):
    # set_default writes process-wide state: put it back after every test.
    monkeypatch.setattr(sespy.i18n, "_default_translator", sespy.i18n._default_translator)


def test_module_scopes_share_the_root_session_translator(translations, monkeypatch):
    # Inside a module server get_current_session() is a SessionProxy. The
    # session translator app.py sets from ?lang= lives on the root session, so
    # get_default() must resolve to it from every scope, nested ones included,
    # not build a fresh clone at the process default per namespace.
    monkeypatch.setattr(sespy.i18n, "_default_translator", Translator(translations=translations))
    seen = {}

    @module.server
    def inner(input, output, session):
        seen["inner"] = get_default()

    @module.server
    def outer(input, output, session):
        seen["outer"] = get_default()
        seen["outer_text"] = t("templates.load")
        inner("child")

    def server(input, output, session):
        root = get_default()
        root.set_language("de")
        seen["root"] = root
        outer("parent")

    with test_server(server):
        pass

    assert seen["outer"] is seen["root"]
    assert seen["inner"] is seen["root"]
    assert seen["outer_text"] == translations["templates.load"]["de"]
    assert sespy.i18n._default_translator._lang == "en"  # the process default is untouched


def test_import_installs_resolver():
    assert sespy.i18n._resolver is u._session_resolver


def test_resolver_outside_session_returns_process_default():
    tr = u.Translator(translations={"a": {"en": "A", "de": "Ä"}})
    set_default(tr)
    assert get_default() is tr
    assert t("a") == "A"


def test_sessions_are_isolated():
    set_default(u.Translator(translations={"a": {"en": "A", "de": "Ä"}}))
    seen = {}

    def server_one(input, output, session):
        get_default().set_language("de")
        seen["one"] = get_default()._lang

    def server_two(input, output, session):
        seen["two"] = get_default()._lang

    with test_server(server_one):
        pass
    with test_server(server_two):
        pass

    assert seen["one"] == "de"
    assert seen["two"] == "en"
    assert sespy.i18n._default_translator._lang == "en"


def test_session_clone_is_reactive_even_for_plain_default(monkeypatch):
    monkeypatch.setattr(sespy.i18n, "_default_translator",
                        sespy.i18n.Translator(translations={"a": {"en": "A"}}))
    seen = {}

    def server(input, output, session):
        seen["tr"] = get_default()

    with test_server(server):
        pass

    assert isinstance(seen["tr"], u.Translator)
    assert hasattr(seen["tr"], "language")


def test_mosaicses_usage_shape(monkeypatch):
    # MosaicSES's bridge release imports these three names from the app-side module.
    from sespy.ui_i18n import Translator as MTranslator
    from sespy.ui_i18n import load_translations as m_load
    from sespy.ui_i18n import set_default as m_set_default

    m_set_default(MTranslator(translations=m_load(ROOT / "sespy" / "translations")))
    seen = {}

    def server(input, output, session):
        seen["tr"] = get_default()

    with test_server(server):
        pass

    assert isinstance(seen["tr"], u.Translator)
    assert seen["tr"] is not sespy.i18n._default_translator   # a per-session clone

    other = sespy.i18n.Translator(translations={})
    monkeypatch.setattr(sespy.i18n, "_default_translator", other)
    assert get_default() is other
