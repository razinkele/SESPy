"""K1 Task 10: session snapshot, `reference_reads`, resets and the load check.

`quick_actions_server` is not a module (no `make_scope`): it is composed in
a bare root-level test server. `app.py` is never imported here: its
`server()` reads `clientdata.url_search()` before `test_server` sends client
data, and it pins the process-wide translator.
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest
import shiny
from shiny import reactive, render
from shiny.testserver import test_server

import sespy.i18n
import sespy.modules.project_io as pio
from sespy import r_kb
from sespy.data_structure import IsaData, Project
from sespy.event_bus import create_event_bus
from sespy.modules.project_io import quick_actions_server

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_ses.json"
KB = r_kb.KB_NAME
GOV = r_kb.GOVERNANCE_NAME
TOKEN = "0f8fad5b-d9cb-469f-a165-70867728950e"
SNAP = r_kb.VENDORED


@pytest.fixture(autouse=True)
def _pin_translator(monkeypatch):
    # The translator is process-wide; an earlier app.py import would make
    # t() return English. Pin it so outcomes never depend on test order.
    monkeypatch.setattr(sespy.i18n, "get_default", lambda: None)


@pytest.fixture
def toasts(monkeypatch):
    shown: list[dict] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg=None, **kw: shown.append({"msg": msg, **kw}))
    monkeypatch.setattr(shiny.ui, "notification_remove", lambda *a, **k: None)
    return shown


@pytest.fixture
def no_disk(monkeypatch):
    """No autosave I/O; the recovery check completes at once."""
    monkeypatch.setattr(pio, "housekeeping", lambda: None)
    monkeypatch.setattr(pio, "autosave_age_seconds", lambda **kw: None)
    monkeypatch.setattr(pio, "clear_autosave", lambda **kw: None)
    writes: list[dict] = []
    monkeypatch.setattr(pio, "write_autosave",
                        lambda proj, **kw: writes.append({"proj": proj, **kw}))
    return writes


def _project(ref: dict | None = None) -> Project:
    p = Project.from_isa(IsaData())
    if ref is not None:
        p.metadata.reference_data = ref
    return p


def _entry(sha: str, tag: str = "v1.0.0") -> dict:
    return {"source": "vendored", "sha256_norm": sha, "version": "1.0",
            "vendored_r_tag": tag}


def _make_server(h: dict, *, snapshot=SNAP, with_reads: bool = True):
    """Root-level server: quick actions plus test-only triggers that replace
    the project the way upload / templates do (set, isa_change, load event)."""
    def server(input, output, session):
        pd = reactive.value(_project())
        bus = create_event_bus()
        rr = reactive.value(frozenset()) if with_reads else None
        h.update(pd=pd, bus=bus, rr=rr, session=session)
        quick_actions_server(input, output, session, project_data=pd,
                             event_bus=bus, sample_path=SAMPLE, translator=None,
                             snapshot=snapshot, reference_reads=rr)

        @reactive.effect
        @reactive.event(input.t_load, ignore_init=True)
        def _load():
            if not input.t_load():
                return
            pd.set(h["next"])
            bus.emit_isa_change()
            bus.emit_cld_update()
            bus.emit_project_loaded()

        @reactive.effect
        @reactive.event(input.t_template, ignore_init=True)
        def _template():
            if not input.t_template():
                return
            pd.set(h["next"])
            bus.emit_isa_change()
            bus.emit_cld_update()
            bus.emit_template_loaded()

        @reactive.effect
        @reactive.event(input.t_read, ignore_init=True)
        def _read():
            if not input.t_read():
                return
            r_kb.add_reads(rr, [KB, GOV])

        @reactive.effect
        @reactive.event(input.t_edit, ignore_init=True)
        def _edit():
            if not input.t_edit():
                return
            with reactive.isolate():
                pd.set(pd.get().with_modified_now())
            bus.emit_isa_change()

        @reactive.effect
        @reactive.event(input.t_isa, ignore_init=True)
        def _isa():
            if not input.t_isa():
                return
            bus.emit_isa_change()

    return server


def _prime(ts) -> None:
    # Every button is primed with 0 first; setting one straight to 1 does nothing.
    ts.set_inputs(t_load=0, t_template=0, t_read=0, t_isa=0, t_edit=0, new_project=0)


def _reads(h) -> frozenset:
    with reactive.isolate():
        return h["rr"].get()


def _kb_toasts(shown) -> list[dict]:
    return [t for t in shown if str(t.get("id", "")).startswith("kb-provenance-")]


# ---------------------------------------------------------------- add_reads

def test_add_reads_none_is_noop():
    assert r_kb.add_reads(None, [KB]) is None


def test_add_reads_no_self_invalidation():
    h: dict = {}

    def server(input, output, session):
        rr = reactive.value(frozenset())
        h.update(runs=0, seen=[])

        @render.text
        def out():
            h["runs"] += 1
            r_kb.add_reads(rr, [KB])
            r_kb.add_reads(rr, [KB])
            return "x"

        @reactive.effect
        def _watch():
            h["seen"].append(rr.get())

    with test_server(server) as ts:
        assert ts.get_output("out") == "x"
        ts.flush()
    assert h["runs"] == 1                        # the render never re-ran
    assert h["seen"] == [frozenset(), frozenset({KB})]   # one invalidation


# ------------------------------------------------------------------- resets

def test_reads_reset_on_project_loaded(toasts, no_disk):
    h: dict = {"next": _project()}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_read=1)
        assert _reads(h) == {KB, GOV}
        ts.set_inputs(t_load=1)
        assert _reads(h) == frozenset()


def test_reads_reset_on_template_loaded(toasts, no_disk):
    h: dict = {"next": _project()}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_read=1)
        assert _reads(h) == {KB, GOV}
        ts.set_inputs(t_template=1)
        assert _reads(h) == frozenset()


def test_reads_reset_on_new(toasts, no_disk):
    h: dict = {}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_read=1)
        assert _reads(h) == {KB, GOV}
        ts.set_inputs(new_project=1)
        assert _reads(h) == frozenset()


def test_reads_kept_on_plain_edit(toasts, no_disk):
    h: dict = {}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_read=1)
        ts.set_inputs(t_isa=1)
        assert _reads(h) == {KB, GOV}


# --------------------------------------------------------------- load check

def test_toast_silent_when_equal_to_snapshot(toasts, no_disk):
    ref = {f: SNAP.provenance(f) for f in (KB, GOV)}
    ref["unknown_file.json"] = _entry("feedface")      # not in the snapshot: skipped
    ref["no_hash.json"] = {"source": "vendored"}        # no sha256_norm: ignored
    h: dict = {"next": _project(ref)}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_load=1)
    assert _kb_toasts(toasts) == []


def test_toast_entry_without_hash_is_ignored(toasts, no_disk):
    h: dict = {"next": _project({KB: {"source": "vendored", "version": "1.0"}})}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_load=1)
    assert _kb_toasts(toasts) == []


def _shared_snapshot() -> r_kb.Snapshot:
    files = dict(SNAP.files)
    files[KB] = dataclasses.replace(files[KB], sha256_norm="livehash", source="shared")
    return dataclasses.replace(SNAP, files=files)


@pytest.mark.parametrize("case", ["vendored", "last_parsed_shared"])
def test_toast_differs_for_vendored_and_for_last_parsed_shared(case, toasts, no_disk,
                                                               monkeypatch):
    vend = SNAP.files[KB].sha256_norm
    if case == "vendored":
        # The session runs on a shared copy; the project was saved on vendored.
        snapshot, saved = _shared_snapshot(), vend
    else:
        # The session runs on vendored; the project matches the copy the
        # registry last parsed from the shared directory.
        snapshot, saved = SNAP, "sharedhash"
        monkeypatch.setattr(r_kb, "hashes_for_load_check",
                            lambda name: (SNAP.files[name].sha256_norm,
                                          "sharedhash" if name == KB else None))
    h: dict = {"next": _project({KB: _entry(saved, tag="v9.9.9"),
                                 GOV: SNAP.provenance(GOV)})}
    with test_server(_make_server(h, snapshot=snapshot)) as ts:
        _prime(ts)
        ts.set_inputs(t_load=1)
    kb = _kb_toasts(toasts)
    assert [t["id"] for t in kb] == [f"kb-provenance-{KB}"]
    assert kb[0]["type"] == "warning" and kb[0]["duration"] is None
    assert "v9.9.9" in str(kb[0]["msg"])
    assert "kb-provenance-unavailable" not in str(kb[0]["msg"])
    assert pio.provenance_outcome(_entry(saved), KB, snapshot) == "differs"


def test_toast_unavailable_for_foreign_hash(toasts, no_disk):
    h: dict = {"next": _project({KB: _entry("deadbeef", tag="v0.1.0"),
                                 GOV: _entry("cafebabe", tag="v0.1.0")})}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_template=1)
    kb = _kb_toasts(toasts)
    assert sorted(t["id"] for t in kb) == sorted(f"kb-provenance-{f}" for f in (KB, GOV))
    assert all(t["type"] == "warning" and t["duration"] is None for t in kb)
    assert all("kb-provenance-unavailable" in str(t["msg"]) for t in kb)
    assert pio.provenance_outcome(_entry("deadbeef"), KB, SNAP) == "unavailable"


def test_load_check_skipped_without_snapshot_or_reads(toasts, no_disk):
    h: dict = {"next": _project({KB: _entry("deadbeef")})}
    with test_server(_make_server(h, snapshot=None, with_reads=False)) as ts:
        _prime(ts)
        ts.set_inputs(t_load=1)
    assert _kb_toasts(toasts) == []


def test_load_check_ignores_later_edits(toasts, no_disk):
    h: dict = {"next": _project({KB: _entry("deadbeef")})}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_load=1)
        assert len(_kb_toasts(toasts)) == 1
        ts.set_inputs(t_edit=1)               # project_data changes, no load event
        ts.set_inputs(t_isa=1)
    assert len(_kb_toasts(toasts)) == 1


# -------------------------------------------------------- save and autosave

def test_autosave_includes_reads_after_isa_change(toasts, no_disk):
    h: dict = {}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(sespy_browser_token=TOKEN)
        ts.set_inputs(t_read=1)
        n = len(no_disk)                      # a KB read alone never autosaves
        ts.set_inputs(t_isa=1)
        assert len(no_disk) == n + 1
        with reactive.isolate():
            meta = h["pd"].get().metadata
    assert no_disk[-1]["token"] == TOKEN
    assert no_disk[-1]["reference_data"] == r_kb.current_provenance(
        meta, SNAP, frozenset({KB, GOV}))
    assert set(no_disk[-1]["reference_data"]) == {KB, GOV}


def test_autosave_after_load_drops_previous_reads(toasts, no_disk):
    loaded = {KB: _entry("deadbeef")}
    h: dict = {"next": _project(loaded)}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(sespy_browser_token=TOKEN)
        ts.set_inputs(t_read=1)
        ts.set_inputs(t_load=1)               # isa_change and project_loaded, one flush
    assert no_disk[-1]["reference_data"] == loaded


def test_autosave_passes_none_without_snapshot(toasts, no_disk):
    h: dict = {}
    with test_server(_make_server(h, snapshot=None, with_reads=False)) as ts:
        _prime(ts)
        ts.set_inputs(sespy_browser_token=TOKEN)
        ts.set_inputs(t_isa=1)
    assert no_disk and no_disk[-1]["reference_data"] is None


def test_save_download_carries_provenance(toasts, no_disk, monkeypatch):
    seen: list = []
    monkeypatch.setattr(pio, "project_to_bytes",
                        lambda proj, **kw: seen.append(kw) or b"{}")
    h: dict = {}
    with test_server(_make_server(h)) as ts:
        _prime(ts)
        ts.set_inputs(t_read=1)
        # test_server cannot press a render.download_button. Calling the
        # registered handler through the private `session._downloads` is a
        # private Shiny API, accepted by the K1 plan for this one test.
        with reactive.isolate():
            body = b"".join(h["session"]._downloads["save_project"].handler())
            meta = h["pd"].get().metadata
    assert body == b"{}"
    assert seen == [{"reference_data": r_kb.current_provenance(
        meta, SNAP, frozenset({KB, GOV}))}]


# ------------------------------------------------------------ app.py wiring

def _server_calls():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "server")
    calls = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls[node.func.id] = node
    return calls, tree, fn


def test_app_passes_snapshot_and_reads_to_the_four_servers():
    calls, tree, fn = _server_calls()

    def kw(name):
        return {k.arg for k in calls[name].keywords}

    for name in ("ai_isa_wizard_server", "report_export_server", "quick_actions_server"):
        assert {"snapshot", "reference_reads"} <= kw(name), name
    assert "snapshot" in kw("topbar_actions_server")
    src = ast.unparse(fn)
    assert "r_kb.refresh()" in src and "r_kb.current()" in src
    assert "reactive.value(frozenset())" in src
    top = [ast.unparse(n) for n in tree.body if isinstance(n, ast.Expr)]
    assert any(s.startswith("r_kb.configure(") for s in top)


def _kwonly_defaults(rel: str, fn: str) -> dict:
    # @module.server hides the signature, so read the definitions' source.
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn)
    return {a.arg: (ast.unparse(d) if d is not None else "<required>")
            for a, d in zip(node.args.kwonlyargs, node.args.kw_defaults)}


@pytest.mark.parametrize("rel,fn,names", [
    ("sespy/modules/ai_isa_wizard.py", "ai_isa_wizard_server", ("snapshot", "reference_reads")),
    ("sespy/modules/report_export.py", "report_export_server", ("snapshot", "reference_reads")),
    ("sespy/modules/project_io.py", "quick_actions_server", ("snapshot", "reference_reads")),
    ("sespy/modules/topbar_actions.py", "topbar_actions_server", ("snapshot",)),
])
def test_module_servers_accept_the_new_keywords_as_optional(rel, fn, names):
    kw = _kwonly_defaults(rel, fn)
    for name in names:
        assert kw.get(name) == "None", (fn, name)


def test_provenance_keys_format_in_every_language():
    import json

    data = json.loads((ROOT / "sespy" / "translations" / "core.json").read_text(encoding="utf-8"))
    tr = data["translation"]
    for lang in data["languages"]:
        text = tr["kb.provenance_differs"][lang].format(file=KB, tag="v9.9.9")
        assert KB in text and "v9.9.9" in text, lang
        assert tr["kb.provenance_unavailable"][lang], lang
