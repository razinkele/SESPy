"""Performance smoke tests for the analytics layer on large graphs.

These are *tripwires*, not microbenchmarks. They build a synthetic SES model
an order of magnitude larger than the shipped sample and assert that the core
network analytics still return within a generous wall-clock budget. The budgets
are deliberately loose (seconds, not milliseconds) so the tests are not flaky on
slow/loaded CI machines — they exist to catch algorithmic regressions that turn
a fast call into an exponential blow-up (see issue #18, where unbounded loop
enumeration ran for minutes on a dense 40-node graph).

If one of these starts failing, the fix is almost never "raise the budget" — it
is "find the accidentally-superlinear code path that was just introduced".
"""

from __future__ import annotations

import random
import time
from contextlib import contextmanager

import pytest

from sespy import network
from sespy.constants import DAPSIWRM_ELEMENTS
from sespy.data_structure import Connection, Element, IsaData


def _build_large_isa(
    *, n_nodes: int = 300, avg_out_degree: int = 4, seed: int = 12345
) -> IsaData:
    """A reproducible large SES model: `n_nodes` typed elements wired with a
    roughly uniform out-degree. Big enough to expose superlinear regressions,
    small enough to stay well within CI limits when the algorithms are sound."""
    rng = random.Random(seed)
    elements = [
        Element(
            id=f"N{i}",
            label=f"node {i}",
            type=DAPSIWRM_ELEMENTS[i % len(DAPSIWRM_ELEMENTS)],
        )
        for i in range(n_nodes)
    ]
    polarities = ("+", "-")
    strengths = ("weak", "medium", "strong")
    connections: list[Connection] = []
    seen: set[tuple[str, str]] = set()
    for i in range(n_nodes):
        for _ in range(avg_out_degree):
            j = rng.randrange(n_nodes)
            if j == i:
                continue
            key = (f"N{i}", f"N{j}")
            if key in seen:
                continue
            seen.add(key)
            connections.append(
                Connection(
                    source=key[0],
                    target=key[1],
                    polarity=rng.choice(polarities),
                    strength=rng.choice(strengths),
                )
            )
    return IsaData(elements=elements, connections=connections)


@contextmanager
def _time_budget(label: str, seconds: float):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    assert elapsed < seconds, (
        f"{label} took {elapsed:.2f}s, exceeding the {seconds:.0f}s budget "
        f"(possible algorithmic regression)"
    )


@pytest.fixture(scope="module")
def large_isa() -> IsaData:
    isa = _build_large_isa()
    # Sanity: the fixture really is large and well-formed.
    assert isa.element_count() == 300
    assert isa.connection_count() > 500
    return isa


def test_basic_metrics_scales(large_isa):
    with _time_budget("basic_metrics", 5.0):
        m = network.basic_metrics(large_isa)
    assert m["nodes"] == 300
    assert m["edges"] == large_isa.connection_count()


def test_centrality_metrics_scales(large_isa):
    with _time_budget("centrality_metrics", 20.0):
        c = network.centrality_metrics(large_isa)
    # Every centrality family should cover every node.
    for family in c.values():
        assert len(family) == 300


def test_feedback_loops_bounded_on_large_graph(large_isa):
    with _time_budget("feedback_loops", 20.0):
        loops = network.feedback_loops(large_isa)
    # The enumeration must honour its caps rather than run away.
    assert all(2 <= len(lp) <= 6 for lp in loops)


def test_leverage_scores_scales(large_isa):
    with _time_budget("leverage_scores", 20.0):
        scores = network.leverage_scores(large_isa)
    assert len(scores) == 300


def test_top_n_by_metric_scales(large_isa):
    with _time_budget("top_n_by_metric", 20.0):
        rows = network.top_n_by_metric(large_isa, "degree", n=10)
    assert len(rows) == 10
