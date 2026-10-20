"""Token diffusion in the Intervention panel runs off the reactive flush.

The first token_diffusion call per server process lazily imports scipy.stats
(~7 s cold). Run synchronously in an effect it froze the session with no
feedback; as an extended task the summary says it is running at once, and a
result that a later input change made stale is dropped.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from shiny import reactive
from shiny.testserver import test_server

from sespy import data_structure, i18n
from sespy.event_bus import create_event_bus
from sespy.modules import analysis_intervention as mod

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_ses.json"
RUNNING = "running the intervention simulation"   # diffusion.computing, en


@pytest.fixture(autouse=True)
def english(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", i18n.Translator(
        translations=i18n.load_translations(ROOT / "sespy" / "translations")))


@pytest.fixture
def gated_diffusion(monkeypatch):
    """token_diffusion that blocks until released, then returns the real result."""
    release = threading.Event()
    real = mod.dyn.token_diffusion
    calls = []

    def fake(isa, src, **kw):
        calls.append((src, kw))
        release.wait(timeout=10)
        return real(isa, src, **kw)

    monkeypatch.setattr(mod.dyn, "token_diffusion", fake)
    return release, calls


def _server(input, output, session):
    project = reactive.value(
        data_structure.Project.from_isa(data_structure.load_sample(SAMPLE)))
    mod.analysis_intervention_server(
        "intervention", project_data=project, event_bus=create_event_bus())


def _summary(scope) -> str:
    return scope.get_output("diffusion_summary").value["html"]


def _settle(ts, scope, done, secs=15.0):
    deadline = time.monotonic() + secs
    while time.monotonic() < deadline:
        ts.flush()
        if done(_summary(scope)):
            return
        time.sleep(0.05)


def test_run_shows_computing_then_the_result(gated_diffusion):
    release, calls = gated_diffusion
    with test_server(_server, timeout_secs=20.0) as ts:
        iv = ts.make_scope("intervention")
        # The button starts at 0 (as in the browser): its first value is the
        # init that `ignore_init=True` skips; only the click to 1 runs.
        iv.set_inputs(diffusion_source="D001", n_steps=10, n_tokens=1000, run_diffusion=0)
        assert "not simulated" in _summary(iv)
        iv.set_inputs(run_diffusion=1)
        # The click returns at once with the running line; the task is
        # still blocked in token_diffusion.
        assert RUNNING in _summary(iv), _summary(iv)
        release.set()
        _settle(ts, iv, lambda s: "elements reached" in s)
        assert "7 of 17 elements reached by 1000 tokens in 10 steps" in _summary(iv)
        assert calls == [("D001", {"n_steps": 10, "n_tokens": 1000, "seed": 0})]


def test_input_change_while_running_drops_the_stale_result(gated_diffusion):
    release, _ = gated_diffusion
    with test_server(_server, timeout_secs=20.0) as ts:
        iv = ts.make_scope("intervention")
        iv.set_inputs(diffusion_source="D001", n_steps=10, n_tokens=1000, run_diffusion=0)
        iv.set_inputs(run_diffusion=1)
        assert RUNNING in _summary(iv)
        iv.set_inputs(n_steps=5)           # invalidates the in-flight run
        release.set()
        _settle(ts, iv, lambda s: "elements reached" in s, secs=3.0)
        assert "not simulated" in _summary(iv), _summary(iv)
