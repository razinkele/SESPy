"""Random signed networks for the Boolean core-search tests.

The matrices use the orientation ``create_boolean_rules`` reads:
``M[i, j]`` is the edge i -> j. Node indices are shuffled so that the
upstream / core / read-out parts are interleaved, which exercises the
column mapping of the kernel.
"""
from __future__ import annotations

import numpy as np

WEIGHTS = (1.0, -1.0, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.7, -0.7)


def _w(rng: np.random.Generator) -> float:
    return float(rng.choice(WEIGHTS))


def random_shape_info(rng: np.random.Generator, n_max: int = 14) -> tuple[np.ndarray, dict]:
    """Return ``(M, info)``. ``info`` records which features the shape has."""
    n_clusters = int(rng.integers(1, 4))
    sizes = [int(rng.integers(1, 5)) for _ in range(n_clusters)]
    # keep room for at least one upstream and one read-out node when possible
    while sum(sizes) > n_max - 2 and max(sizes) > 1:
        sizes[int(np.argmax(sizes))] -= 1
    n_core = sum(sizes)
    room = max(0, n_max - n_core)
    n_up = int(rng.integers(0, min(4, room) + 1))
    room -= n_up
    n_out = int(rng.integers(0, min(4, room) + 1))
    n = n_core + n_up + n_out

    perm = [int(v) for v in rng.permutation(n)]
    clusters, pos = [], 0
    for s in sizes:
        clusters.append(perm[pos:pos + s])
        pos += s
    up = perm[n_core:n_core + n_up]
    out = perm[n_core + n_up:]
    core = perm[:n_core]

    M = np.zeros((n, n))
    info = {"n": n, "clusters": n_clusters, "bridges": 0, "upstream": n_up,
            "fan_in": False, "readouts": n_out, "up_to_readout": 0,
            "float_weights": False}

    # cycle clusters: a ring (a self-loop for size 1) plus random chords
    for cl in clusters:
        for a, b in zip(cl, cl[1:] + cl[:1]):
            M[a, b] = _w(rng)
        for _ in range(int(rng.integers(0, len(cl) + 1))):
            a, b = (int(v) for v in rng.choice(cl, 2))
            M[a, b] = _w(rng)
    # bridges between clusters (mostly one-way, so clusters stay separate SCCs)
    for ci in range(1, n_clusters):
        for _ in range(int(rng.integers(1, 3))):
            src = int(rng.choice(clusters[int(rng.integers(0, ci))]))
            dst = int(rng.choice(clusters[ci]))
            M[src, dst] = _w(rng)
            info["bridges"] += 1
        if rng.random() < 0.2:  # occasional back edge merges two clusters
            src = int(rng.choice(clusters[ci]))
            dst = int(rng.choice(clusters[int(rng.integers(0, ci))]))
            M[src, dst] = _w(rng)
            info["bridges"] += 1
    # upstream chains with fan-in into the core
    targets_hit: dict[int, int] = {}
    for j, u in enumerate(up):
        if j + 1 < len(up) and rng.random() < 0.5:
            M[u, up[j + 1]] = _w(rng)
        for _ in range(int(rng.integers(1, 3))):
            if rng.random() < 0.8 or not out:
                t = int(rng.choice(core))
                targets_hit[t] = targets_hit.get(t, 0) + 1
            else:
                t = int(rng.choice(out))
                info["up_to_readout"] += 1
            M[u, t] = _w(rng)
    info["fan_in"] = any(c >= 2 for c in targets_hit.values())
    # read-out chains below the core
    for j, o in enumerate(out):
        src = out[j - 1] if j > 0 and rng.random() < 0.5 else int(rng.choice(core))
        M[src, o] = _w(rng)
    # upstream to read-out edges
    if up and out and rng.random() < 0.4:
        M[int(rng.choice(up)), int(rng.choice(out))] = _w(rng)
        info["up_to_readout"] += 1

    nz = M[M != 0]
    info["float_weights"] = bool(np.any(np.abs(nz) < 1))
    return M, info


def random_shape(rng: np.random.Generator, n_max: int = 14) -> np.ndarray:
    """A signed matrix mixing cycle clusters, bridges, upstream chains with
    fan-in, read-out chains and upstream-to-read-out edges."""
    return random_shape_info(rng, n_max)[0]


def shape_counts(seeds) -> dict[str, int]:
    """How many of ``seeds`` produce each feature (one count per seed)."""
    counts = {"seeds": 0, "multi_cluster": 0, "bridges": 0, "upstream": 0,
              "fan_in": 0, "readouts": 0, "up_to_readout": 0, "float_weights": 0}
    for seed in seeds:
        _, info = random_shape_info(np.random.default_rng(seed))
        counts["seeds"] += 1
        counts["multi_cluster"] += info["clusters"] >= 2
        counts["bridges"] += info["bridges"] >= 1
        counts["upstream"] += info["upstream"] >= 1
        counts["fan_in"] += info["fan_in"]
        counts["readouts"] += info["readouts"] >= 1
        counts["up_to_readout"] += info["up_to_readout"] >= 1
        counts["float_weights"] += info["float_weights"]
    return counts


def large_multi_cluster(rng: np.random.Generator) -> np.ndarray:
    """34 nodes: three positive-leaning cycle clusters (6 + 6 + 5 = 17 core
    nodes) joined by bridges, 8 upstream nodes feeding the core, 9 read-outs."""
    n = 34
    perm = [int(v) for v in rng.permutation(n)]
    clusters = [perm[0:6], perm[6:12], perm[12:17]]
    up, out = perm[17:25], perm[25:34]
    core = perm[0:17]
    M = np.zeros((n, n))
    pos_w = (1.0, 0.7, 0.3)
    for cl in clusters:
        for a, b in zip(cl, cl[1:] + cl[:1]):
            M[a, b] = float(rng.choice(pos_w))
        for _ in range(3):
            a, b = (int(v) for v in rng.choice(cl, 2))
            M[a, b] = _w(rng)
    M[clusters[0][0], clusters[1][0]] = 0.7
    M[clusters[1][2], clusters[2][0]] = 0.7
    for j, u in enumerate(up):
        if j + 1 < len(up) and j % 2 == 0:
            M[u, up[j + 1]] = 1.0
        M[u, int(rng.choice(core))] = _w(rng)
    for j, o in enumerate(out):
        src = out[j - 1] if j % 3 else int(rng.choice(core))
        M[src, o] = _w(rng)
    return M
