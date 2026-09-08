# tests/test_bayes_consensus.py
"""Option A: conjugate rater posteriors (spec 2026-09-08-sespy-bayesian-options)."""
from __future__ import annotations

import math

import pytest
from scipy.stats import beta as _beta

from sespy import network
from sespy.data_structure import Connection, Rating


def _conn(*ratings):
    return Connection(source="A", target="B", polarity="+", strength="medium",
                      confidence=3, ratings=list(ratings))


def test_polarity_posterior_no_ratings_is_prior():
    p = network.polarity_posterior(_conn())
    assert p["alpha"] == 1.0 and p["beta"] == 1.0 and p["n"] == 0
    assert p["p_plus"] == 0.5
    assert math.isclose(p["ci_low"], 0.025) and math.isclose(p["ci_high"], 0.975)


def test_polarity_posterior_one_confident_plus():
    p = network.polarity_posterior(_conn(Rating("r1", polarity="+", confidence=5)))
    assert p["alpha"] == 2.0 and p["beta"] == 1.0
    assert math.isclose(p["p_plus"], 2 / 3)
    assert math.isclose(p["ci_low"], _beta.ppf(0.025, 2, 1))
    assert math.isclose(p["ci_high"], _beta.ppf(0.975, 2, 1))


def test_polarity_posterior_weights_by_confidence():
    p = network.polarity_posterior(_conn(
        Rating("r1", polarity="+", confidence=1),   # weight 0.2
        Rating("r2", polarity="-", confidence=3),   # weight 0.6
    ))
    assert math.isclose(p["alpha"], 1.2) and math.isclose(p["beta"], 1.6)
    assert math.isclose(p["p_plus"], 1.2 / 2.8)
    assert p["n"] == 2


def test_rating_weight_clamps():
    assert network._rating_weight(Rating("r", confidence=9)) == 1.0
    assert network._rating_weight(Rating("r", confidence=0)) == 0.2


def test_strength_posterior_no_ratings_is_flat_prior():
    s = network.strength_posterior(_conn())
    assert s["alpha"] == (1.0, 1.0, 1.0)
    assert all(math.isclose(v, 1 / 3) for v in s["mean"].values())
    assert s["map"] == "weak"          # tie -> lowest rank, documented
    assert s["n"] == 0


def test_strength_posterior_map_and_mean():
    s = network.strength_posterior(_conn(
        Rating("r1", strength="strong", confidence=5),
        Rating("r2", strength="medium", confidence=1),
    ))
    assert s["alpha"] == (1.0, 1.2, 2.0)
    assert s["map"] == "strong"
    assert math.isclose(s["mean"]["strong"], 2.0 / 4.2)


def test_bayesian_consensus_no_ratings_is_equivalent_copy():
    c = _conn()
    out = network.bayesian_consensus(c)
    assert out == c and out is not c


def test_bayesian_consensus_sets_posterior_values_and_never_mutates():
    c = _conn(Rating("r1", polarity="-", strength="strong", confidence=5),
              Rating("r2", polarity="-", strength="strong", confidence=5))
    out = network.bayesian_consensus(c)
    assert out.polarity == "-" and out.strength == "strong"
    assert 1 <= out.confidence <= 5
    assert out.delay == c.delay
    assert c.polarity == "+" and c.strength == "medium"     # untouched


def test_bayesian_consensus_confidence_mapping_endpoints():
    # No ratings -> interval width 0.95 -> round(1 + 4*0.05) = 1 ... but no
    # ratings returns a copy, so probe via the helper on a rated edge instead:
    wide = network.bayesian_consensus(_conn(Rating("r1", polarity="+", confidence=1)))
    narrow = network.bayesian_consensus(_conn(*[
        Rating(f"r{i}", polarity="+", confidence=5) for i in range(40)]))
    assert wide.confidence <= 2
    assert narrow.confidence == 5


def test_bayesian_contested_requires_dissent_and_straddle():
    assert network.bayesian_contested(_conn()) is False
    assert network.bayesian_contested(_conn(Rating("r1", polarity="-"))) is False
    assert network.bayesian_contested(_conn(
        Rating("r1", polarity="+"), Rating("r2", polarity="-"))) is True
    assert network.bayesian_contested(_conn(*[
        Rating(f"r{i}", polarity="+", confidence=5) for i in range(10)])) is False
    # Unanimous but few: Beta(3,1) / Beta(5,1) still straddle 0.5 (ci_low 0.292,
    # 0.478), yet the raters AGREE -> never contested. Without the dissent
    # precondition every freshly agreed edge would carry a warning.
    for n in (2, 4):
        assert network.bayesian_contested(_conn(*[
            Rating(f"r{i}", polarity="+", confidence=5) for i in range(n)])) is False
    assert network.bayesian_contested(_conn(Rating("r1"), Rating("r2"), Rating("r3"))) is False
    # Dissent that the posterior CAN resolve (12 '+' vs 1 '-', ci_low 0.661) is not contested.
    assert network.bayesian_contested(_conn(
        *[Rating(f"r{i}", polarity="+", confidence=5) for i in range(12)],
        Rating("x", polarity="-", confidence=5))) is False
